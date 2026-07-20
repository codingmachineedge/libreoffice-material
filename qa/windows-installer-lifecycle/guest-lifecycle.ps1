#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:InputRoot = 'C:\Lifecycle\Input'
$script:OutputRoot = 'C:\Lifecycle\Output'
$script:WorkRoot = 'C:\Lifecycle\Work'
$script:ResultsRoot = 'C:\Lifecycle\Results'
$script:ExpectedPath = Join-Path $script:InputRoot 'expected.json'
$script:Snapshots = New-Object 'System.Collections.Generic.List[object]'
$script:Steps = New-Object 'System.Collections.Generic.List[object]'
$script:CleanupErrors = New-Object 'System.Collections.Generic.List[string]'
$script:Preflight = $null
$script:Expected = $null

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$LiteralPath)
    (Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory)]$Value,
        [Parameter(Mandatory)][string]$LiteralPath
    )
    ConvertTo-Json -InputObject $Value -Depth 24 |
        Set-Content -LiteralPath $LiteralPath -Encoding UTF8
}

function Assert-Condition {
    param(
        [Parameter(Mandatory)][bool]$Condition,
        [Parameter(Mandatory)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-FileMatches {
    param(
        [Parameter(Mandatory)][string]$LiteralPath,
        [Parameter(Mandatory)][long]$ExpectedBytes,
        [Parameter(Mandatory)][string]$ExpectedSha256
    )
    $item = Get-Item -LiteralPath $LiteralPath -Force
    Assert-Condition ($item.Length -eq $ExpectedBytes) `
        "Size mismatch for $LiteralPath. Expected $ExpectedBytes, got $($item.Length)."
    $actualHash = Get-Sha256 -LiteralPath $LiteralPath
    Assert-Condition ($actualHash -eq $ExpectedSha256) `
        "SHA-256 mismatch for $LiteralPath. Expected $ExpectedSha256, got $actualHash."
}

function Test-HighIntegrity {
    $whoAmI = Join-Path $env:SystemRoot 'System32\whoami.exe'
    $groups = & $whoAmI /groups /fo csv /nh 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    (($groups -join "`n") -match 'S-1-16-(12288|16384)')
}

function Assert-WindowsSandboxIdentity {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $accountName = [string]$identity.Name
    $userName = ($accountName -split '\\')[-1]
    $sid = [string]$identity.User.Value
    Assert-Condition ($userName -eq 'WDAGUtilityAccount') `
        "Refusing to run outside Windows Sandbox: current account is $accountName."
    Assert-Condition ($sid -match '^S-1-5-21-(?:\d+-){3}504$') `
        "Refusing to run outside Windows Sandbox: unexpected account SID $sid."

    $expectedProfile = 'C:\Users\WDAGUtilityAccount'
    Assert-Condition (
        [string]::Equals(
            [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\'),
            $expectedProfile,
            [StringComparison]::OrdinalIgnoreCase)) `
        "Refusing to run outside Windows Sandbox: unexpected profile $($env:USERPROFILE)."
    $expectedScript = Join-Path $script:InputRoot 'guest-lifecycle.ps1'
    Assert-Condition (
        [string]::Equals(
            [IO.Path]::GetFullPath($PSCommandPath),
            [IO.Path]::GetFullPath($expectedScript),
            [StringComparison]::OrdinalIgnoreCase)) `
        "Refusing to run outside the reviewed mapped entry point: $PSCommandPath"

    $computer = Get-CimInstance Win32_ComputerSystem
    Assert-Condition (
        $computer.Manufacturer -eq 'Microsoft Corporation' -and
        $computer.Model -eq 'Virtual Machine' -and
        $computer.HypervisorPresent) `
        "Refusing to run outside the Windows Sandbox virtual machine boundary."
    Assert-Condition (Test-Path -LiteralPath $script:InputRoot -PathType Container) `
        "Mapped input directory is missing: $($script:InputRoot)"
    Assert-Condition (Test-Path -LiteralPath $script:OutputRoot -PathType Container) `
        "Mapped output directory is missing: $($script:OutputRoot)"

    $probePath = Join-Path $script:InputRoot `
        ('.sandbox-readonly-attestation-' + [guid]::NewGuid().ToString('N'))
    $readOnlyEnforced = $false
    try {
        [IO.File]::WriteAllText($probePath, 'must-not-write')
    }
    catch [UnauthorizedAccessException] {
        $readOnlyEnforced = $true
    }
    finally {
        if (Test-Path -LiteralPath $probePath) {
            Remove-Item -LiteralPath $probePath -Force
        }
    }
    Assert-Condition $readOnlyEnforced `
        'Refusing to run: the Windows Sandbox input mapping is not enforced read-only.'
}

function Invoke-MsiQuery {
    param(
        [Parameter(Mandatory)][string]$DatabasePath,
        [Parameter(Mandatory)][string]$Sql
    )
    $installer = $null
    $database = $null
    $view = $null
    try {
        $installer = New-Object -ComObject WindowsInstaller.Installer
        $database = $installer.GetType().InvokeMember(
            'OpenDatabase', 'InvokeMethod', $null, $installer, @($DatabasePath, 0))
        $view = $database.GetType().InvokeMember(
            'OpenView', 'InvokeMethod', $null, $database, @($Sql))
        $view.GetType().InvokeMember('Execute', 'InvokeMethod', $null, $view, $null) | Out-Null
        $rows = @()
        while ($true) {
            $record = $view.GetType().InvokeMember('Fetch', 'InvokeMethod', $null, $view, $null)
            if ($null -eq $record) {
                break
            }
            try {
                $fieldCount = [int]$record.GetType().InvokeMember(
                    'FieldCount', 'GetProperty', $null, $record, $null)
                $values = @()
                for ($index = 1; $index -le $fieldCount; $index++) {
                    $values += [string]$record.GetType().InvokeMember(
                        'StringData', 'GetProperty', $null, $record, @($index))
                }
                $rows += ,$values
            }
            finally {
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($record)
            }
        }
        $view.GetType().InvokeMember('Close', 'InvokeMethod', $null, $view, $null) | Out-Null
        $rows
    }
    finally {
        if ($view) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($view)
        }
        if ($database) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($database)
        }
        if ($installer) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
        }
    }
}

function Get-MsiIdentity {
    param([Parameter(Mandatory)][string]$LiteralPath)
    $properties = @{}
    foreach ($row in Invoke-MsiQuery -DatabasePath $LiteralPath `
        -Sql 'SELECT `Property`,`Value` FROM `Property`') {
        $properties[[string]$row[0]] = [string]$row[1]
    }
    foreach ($requiredProperty in @(
        'ProductCode',
        'ProductName',
        'ProductVersion',
        'UpgradeCode',
        'ALLUSERS',
        'MSIRESTARTMANAGERCONTROL'
    )) {
        Assert-Condition ($properties.ContainsKey($requiredProperty)) `
            "MSI Property table is missing required value: $requiredProperty"
    }
    $rebootActions = @()
    foreach ($row in Invoke-MsiQuery -DatabasePath $LiteralPath `
        -Sql 'SELECT `Action`,`Condition`,`Sequence` FROM `InstallExecuteSequence`') {
        if ([string]$row[0] -in @('ForceReboot', 'ScheduleReboot')) {
            $rebootActions += [ordered]@{
                action = [string]$row[0]
                condition = [string]$row[1]
                sequence = [string]$row[2]
            }
        }
    }
    [ordered]@{
        product_code = [string]$properties['ProductCode']
        product_name = [string]$properties['ProductName']
        product_version = [string]$properties['ProductVersion']
        upgrade_code = [string]$properties['UpgradeCode']
        all_users = [string]$properties['ALLUSERS']
        restart_manager_control = [string]$properties['MSIRESTARTMANAGERCONTROL']
        reboot_actions = @($rebootActions)
    }
}

function Get-ProductState {
    param([Parameter(Mandatory)][string]$ProductCode)
    $installer = $null
    try {
        $installer = New-Object -ComObject WindowsInstaller.Installer
        [int]$installer.GetType().InvokeMember(
            'ProductState', 'GetProperty', $null, $installer, @($ProductCode))
    }
    finally {
        if ($installer) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
        }
    }
}

function Assert-ProductInstalled {
    param([Parameter(Mandatory)][string]$ProductCode)
    $state = Get-ProductState -ProductCode $ProductCode
    Assert-Condition ($state -eq 5) "Expected installed MSI product $ProductCode; state was $state."
}

function Assert-ProductAbsent {
    param([Parameter(Mandatory)][string]$ProductCode)
    $state = Get-ProductState -ProductCode $ProductCode
    Assert-Condition ($state -eq -1) `
        "Expected unregistered MSI product $ProductCode; state was $state."
}

function Get-RebootSnapshot {
    $sessionManager = Get-ItemProperty `
        -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' `
        -ErrorAction SilentlyContinue
    $updates = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Updates' `
        -ErrorAction SilentlyContinue
    $updateExeVolatileProperty = if ($updates) {
        $updates.PSObject.Properties['UpdateExeVolatile']
    } else { $null }
    $pendingRenameProperty = if ($sessionManager) {
        $sessionManager.PSObject.Properties['PendingFileRenameOperations']
    } else { $null }
    $pendingRename2Property = if ($sessionManager) {
        $sessionManager.PSObject.Properties['PendingFileRenameOperations2']
    } else { $null }
    [ordered]@{
        captured_at_utc = [DateTime]::UtcNow.ToString('o')
        boot_time_utc = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
        cbs_reboot_pending = Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
        cbs_reboot_in_progress = Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootInProgress'
        cbs_packages_pending = Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending'
        windows_update_reboot_required = Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
        pending_file_rename_operations = if ($pendingRenameProperty) {
            @($pendingRenameProperty.Value)
        } else { @() }
        pending_file_rename_operations_2 = if ($pendingRename2Property) {
            @($pendingRename2Property.Value)
        } else { @() }
        update_exe_volatile = if ($updateExeVolatileProperty) {
            $updateExeVolatileProperty.Value
        } else { $null }
        windows_installer_in_progress = Test-Path -LiteralPath `
            'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress'
    }
}

function Get-RebootFingerprint {
    param([Parameter(Mandatory)]$Snapshot)
    ([ordered]@{
        boot_time_utc = $Snapshot.boot_time_utc
        cbs_reboot_pending = $Snapshot.cbs_reboot_pending
        cbs_reboot_in_progress = $Snapshot.cbs_reboot_in_progress
        cbs_packages_pending = $Snapshot.cbs_packages_pending
        windows_update_reboot_required = $Snapshot.windows_update_reboot_required
        pending_file_rename_operations = @($Snapshot.pending_file_rename_operations)
        pending_file_rename_operations_2 = @($Snapshot.pending_file_rename_operations_2)
        update_exe_volatile = $Snapshot.update_exe_volatile
        windows_installer_in_progress = $Snapshot.windows_installer_in_progress
    } | ConvertTo-Json -Depth 10 -Compress)
}

function Add-RebootSnapshot {
    param(
        [Parameter(Mandatory)][string]$StepName,
        [Parameter(Mandatory)][ValidateSet('before', 'after')][string]$Phase,
        [Parameter(Mandatory)]$Snapshot
    )
    $script:Snapshots.Add([ordered]@{
        step = $StepName
        phase = $Phase
        state = $Snapshot
    })
}

function Assert-MsiLogSuccess {
    param([Parameter(Mandatory)][string]$LiteralPath)
    Assert-Condition (Test-Path -LiteralPath $LiteralPath -PathType Leaf) `
        "Windows Installer log is missing: $LiteralPath"
    $text = Get-Content -LiteralPath $LiteralPath -Raw
    Assert-Condition ($text -match '(?im)MainEngineThread is returning 0(?:\s|$)') `
        "Windows Installer log does not record MainEngineThread returning 0: $LiteralPath"
}

function Invoke-MsiStep {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string[]]$OperationArguments,
        [Parameter(Mandatory)][string]$LogName,
        [switch]$BestEffort,
        [switch]$Cleanup
    )
    $logPath = Join-Path $script:ResultsRoot $LogName
    $arguments = @($OperationArguments) + @(
        '/qn',
        '/norestart',
        'REBOOT=ReallySuppress',
        'MSIRESTARTMANAGERCONTROL=DisableShutdown',
        '/L*V!',
        $logPath
    )
    foreach ($argument in $arguments) {
        if ($argument -match '[\s"]') {
            throw "Lifecycle MSI argument unexpectedly requires quoting: $argument"
        }
    }

    $before = Get-RebootSnapshot
    Add-RebootSnapshot -StepName $Name -Phase before -Snapshot $before
    $exitCode = -1
    $startError = $null
    try {
        $process = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\msiexec.exe') `
            -ArgumentList ($arguments -join ' ') -Wait -PassThru -WindowStyle Hidden
        $exitCode = [int]$process.ExitCode
    }
    catch {
        $startError = $_.Exception.Message
    }
    $after = Get-RebootSnapshot
    Add-RebootSnapshot -StepName $Name -Phase after -Snapshot $after
    $rebootStateChanged = (Get-RebootFingerprint -Snapshot $before) -ne `
        (Get-RebootFingerprint -Snapshot $after)
    $step = [ordered]@{
        name = $Name
        command = 'msiexec.exe ' + ($arguments -join ' ')
        log = $LogName
        exit_code = $exitCode
        reboot_state_changed = $rebootStateChanged
        cleanup = [bool]$Cleanup
        start_error = $startError
    }
    $script:Steps.Add($step)

    if ($BestEffort) {
        if ($exitCode -ne 0 -or $rebootStateChanged -or $startError) {
            $script:CleanupErrors.Add(
                "$Name failed or changed reboot state (exit=$exitCode; start_error=$startError).")
        }
        elseif (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
            $script:CleanupErrors.Add("$Name did not produce its required Windows Installer log.")
        }
        else {
            try {
                Assert-MsiLogSuccess -LiteralPath $logPath
            }
            catch {
                $script:CleanupErrors.Add($_.Exception.Message)
            }
        }
        return $step
    }

    if ($startError) {
        throw "Starting $Name failed: $startError"
    }
    Assert-Condition ($exitCode -eq 0) `
        "$Name returned $exitCode. Only exit code 0 is accepted; 3010 and 1641 fail the no-restart gate."
    Assert-Condition (-not $rebootStateChanged) "$Name changed a reboot indicator or OS boot time."
    Assert-MsiLogSuccess -LiteralPath $logPath
    $step
}

function Assert-UpdaterDllHash {
    param([Parameter(Mandatory)][string]$ExpectedSha256)
    $dllPath = Join-Path ([string]$script:Expected.expected_install_root) 'program\updchklo.dll'
    Assert-Condition (Test-Path -LiteralPath $dllPath -PathType Leaf) `
        "Installed updater DLL is missing: $dllPath"
    $actual = Get-Sha256 -LiteralPath $dllPath
    Assert-Condition ($actual -eq $ExpectedSha256) `
        "Installed updater DLL hash mismatch. Expected $ExpectedSha256, got $actual."
}

function Invoke-BestEffortCleanup {
    param(
        [string]$CorrectedProductCode,
        [string]$OldProductCode
    )
    foreach ($candidate in @(
        [pscustomobject]@{ Name = 'cleanup-corrected'; Code = $CorrectedProductCode },
        [pscustomobject]@{ Name = 'cleanup-old'; Code = $OldProductCode }
    )) {
        if ([string]::IsNullOrWhiteSpace($candidate.Code)) {
            continue
        }
        if ((Get-ProductState -ProductCode $candidate.Code) -eq 5) {
            Invoke-MsiStep -Name $candidate.Name `
                -OperationArguments @('/x', $candidate.Code) `
                -LogName ($candidate.Name + '.log') -BestEffort -Cleanup | Out-Null
        }
    }
}

function Publish-Results {
    param(
        [Parameter(Mandatory)][bool]$Passed,
        [string]$ErrorMessage
    )
    Assert-Condition (@(Get-ChildItem -LiteralPath $script:OutputRoot -Force).Count -eq 0) `
        'Mapped output directory was not fresh at publication time.'

    $files = @()
    foreach ($file in Get-ChildItem -LiteralPath $script:ResultsRoot -File | Sort-Object Name) {
        if ($file.Name -in @('artifact-manifest.json', 'COMPLETE.json', 'FAILURE.json')) {
            continue
        }
        $files += [ordered]@{
            path = $file.Name
            bytes = $file.Length
            sha256 = Get-Sha256 -LiteralPath $file.FullName
        }
    }
    $artifactManifest = [ordered]@{
        schema_version = 1
        run_id = [string]$script:Expected.run_id
        created_at_utc = [DateTime]::UtcNow.ToString('o')
        files = $files
    }
    $artifactManifestPath = Join-Path $script:ResultsRoot 'artifact-manifest.json'
    Write-JsonFile -Value $artifactManifest -LiteralPath $artifactManifestPath
    $manifestItem = Get-Item -LiteralPath $artifactManifestPath
    $manifestHash = Get-Sha256 -LiteralPath $artifactManifestPath

    foreach ($file in Get-ChildItem -LiteralPath $script:ResultsRoot -File | Sort-Object Name) {
        $destination = Join-Path $script:OutputRoot $file.Name
        Assert-Condition (-not (Test-Path -LiteralPath $destination)) `
            "Refusing to overwrite mapped output: $destination"
        Copy-Item -LiteralPath $file.FullName -Destination $destination
    }

    $sentinel = [ordered]@{
        schema_version = 1
        run_id = [string]$script:Expected.run_id
        status = if ($Passed) { 'passed' } else { 'failed' }
        completed_at_utc = [DateTime]::UtcNow.ToString('o')
        artifact_manifest_bytes = $manifestItem.Length
        artifact_manifest_sha256 = $manifestHash
        error = $ErrorMessage
    }
    $sentinelName = if ($Passed) { 'COMPLETE.json' } else { 'FAILURE.json' }
    $localSentinel = Join-Path $script:ResultsRoot $sentinelName
    Write-JsonFile -Value $sentinel -LiteralPath $localSentinel
    $temporarySentinel = Join-Path $script:OutputRoot ('.' + $sentinelName + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    Copy-Item -LiteralPath $localSentinel -Destination $temporarySentinel
    Move-Item -LiteralPath $temporarySentinel -Destination (Join-Path $script:OutputRoot $sentinelName)
}

$script:SandboxAttested = $false
Assert-WindowsSandboxIdentity
$script:SandboxAttested = $true

$lifecyclePassed = $false
$failureMessage = $null
$oldProductCode = $null
$correctedProductCode = $null

try {
    Assert-Condition ([Environment]::Is64BitOperatingSystem) 'The lifecycle guest requires 64-bit Windows.'
    Assert-Condition (Test-HighIntegrity) `
        'The Windows Sandbox logon command is not running with a high-integrity administrator token.'
    Assert-Condition (Test-Path -LiteralPath $script:ExpectedPath -PathType Leaf) `
        "Expected-input manifest is missing: $($script:ExpectedPath)"
    Assert-Condition (Test-Path -LiteralPath $script:OutputRoot -PathType Container) `
        "Mapped output directory is missing: $($script:OutputRoot)"
    Assert-Condition (@(Get-ChildItem -LiteralPath $script:OutputRoot -Force).Count -eq 0) `
        'Mapped output directory must be fresh and empty.'
    Assert-Condition (-not (Test-Path -LiteralPath $script:WorkRoot)) `
        "Guest work directory unexpectedly exists: $($script:WorkRoot)"
    Assert-Condition (-not (Test-Path -LiteralPath $script:ResultsRoot)) `
        "Guest results directory unexpectedly exists: $($script:ResultsRoot)"
    New-Item -ItemType Directory -Path $script:WorkRoot | Out-Null
    New-Item -ItemType Directory -Path $script:ResultsRoot | Out-Null

    $script:Expected = Get-Content -LiteralPath $script:ExpectedPath -Raw | ConvertFrom-Json
    Assert-Condition ($script:Expected.schema_version -eq 1) 'Unsupported expected-input schema.'
    $oldInput = Join-Path $script:InputRoot ([string]$script:Expected.old.file_name)
    $correctedInput = Join-Path $script:InputRoot ([string]$script:Expected.corrected.file_name)
    Assert-FileMatches -LiteralPath $oldInput -ExpectedBytes ([long]$script:Expected.old.bytes) `
        -ExpectedSha256 ([string]$script:Expected.old.sha256)
    Assert-FileMatches -LiteralPath $correctedInput `
        -ExpectedBytes ([long]$script:Expected.corrected.bytes) `
        -ExpectedSha256 ([string]$script:Expected.corrected.sha256)

    $oldMsi = Join-Path $script:WorkRoot 'old.msi'
    $correctedMsi = Join-Path $script:WorkRoot 'corrected.msi'
    Copy-Item -LiteralPath $oldInput -Destination $oldMsi
    Copy-Item -LiteralPath $correctedInput -Destination $correctedMsi
    Assert-FileMatches -LiteralPath $oldMsi -ExpectedBytes ([long]$script:Expected.old.bytes) `
        -ExpectedSha256 ([string]$script:Expected.old.sha256)
    Assert-FileMatches -LiteralPath $correctedMsi `
        -ExpectedBytes ([long]$script:Expected.corrected.bytes) `
        -ExpectedSha256 ([string]$script:Expected.corrected.sha256)

    $oldIdentity = Get-MsiIdentity -LiteralPath $oldMsi
    $correctedIdentity = Get-MsiIdentity -LiteralPath $correctedMsi
    $oldProductCode = [string]$oldIdentity.product_code
    $correctedProductCode = [string]$correctedIdentity.product_code
    foreach ($identity in @($oldIdentity, $correctedIdentity)) {
        Assert-Condition ($identity.product_name -match '^LibreOfficeDev\b') `
            "Unexpected MSI product name: $($identity.product_name)"
        Assert-Condition ($identity.product_version -eq $script:Expected.expected_product_version) `
            "Unexpected MSI ProductVersion: $($identity.product_version)"
        Assert-Condition ($identity.upgrade_code -eq $script:Expected.expected_upgrade_code) `
            "Unexpected MSI UpgradeCode: $($identity.upgrade_code)"
        Assert-Condition ($identity.upgrade_code -ne $script:Expected.stable_libreoffice_upgrade_code) `
            'Lifecycle MSI unexpectedly shares the stable LibreOffice UpgradeCode.'
        Assert-Condition ($identity.all_users -eq '1') 'Lifecycle MSI is not machine-wide as expected.'
        Assert-Condition (@($identity.reboot_actions).Count -eq 0) `
            'Lifecycle MSI contains ForceReboot or ScheduleReboot.'
    }
    Assert-Condition ($oldProductCode -ne $correctedProductCode) `
        'Old and corrected packages have the same ProductCode; no major-upgrade exercise is possible.'
    Assert-Condition ($correctedProductCode -eq $script:Expected.corrected.product_code) `
        "Corrected ProductCode mismatch: $correctedProductCode"
    Assert-ProductAbsent -ProductCode $oldProductCode
    Assert-ProductAbsent -ProductCode $correctedProductCode

    $script:Preflight = [ordered]@{
        schema_version = 1
        run_id = [string]$script:Expected.run_id
        captured_at_utc = [DateTime]::UtcNow.ToString('o')
        high_integrity = $true
        old = $oldIdentity
        corrected = $correctedIdentity
        stable_libreoffice_upgrade_code = [string]$script:Expected.stable_libreoffice_upgrade_code
        initial_reboot_state = Get-RebootSnapshot
    }
    Add-RebootSnapshot -StepName '__lifecycle__' -Phase before `
        -Snapshot $script:Preflight.initial_reboot_state

    Invoke-MsiStep -Name 'old-install' -OperationArguments @('/i', $oldMsi) `
        -LogName '01-old-install.log' | Out-Null
    Assert-ProductInstalled -ProductCode $oldProductCode
    Assert-ProductAbsent -ProductCode $correctedProductCode
    Assert-UpdaterDllHash -ExpectedSha256 ([string]$script:Expected.old.updater_dll_sha256)

    Invoke-MsiStep -Name 'corrected-same-version-update' `
        -OperationArguments @(
            '/i', $correctedMsi, 'REINSTALL=ALL', 'REINSTALLMODE=vomus'
        ) -LogName '02-corrected-same-version-update.log' | Out-Null
    Assert-ProductAbsent -ProductCode $oldProductCode
    Assert-ProductInstalled -ProductCode $correctedProductCode
    Assert-UpdaterDllHash -ExpectedSha256 ([string]$script:Expected.corrected.updater_dll_sha256)
    $updateLogPath = Join-Path $script:ResultsRoot '02-corrected-same-version-update.log'
    $updateLog = Get-Content -LiteralPath $updateLogPath -Raw
    Assert-Condition ($updateLog -match '(?i)OLDPRODUCTS') `
        'Same-version update log did not record OLDPRODUCTS.'
    Assert-Condition ($updateLog -match [regex]::Escape($oldProductCode)) `
        'Same-version update log did not record the old ProductCode.'
    Assert-Condition ($updateLog -match '(?i)RemoveExistingProducts') `
        'Same-version update log did not run RemoveExistingProducts.'

    $installedUpdaterDll = Join-Path ([string]$script:Expected.expected_install_root) `
        'program\updchklo.dll'
    $repairProbe = Join-Path $script:WorkRoot 'updchklo.dll.repair-probe'
    Move-Item -LiteralPath $installedUpdaterDll -Destination $repairProbe
    Assert-Condition (-not (Test-Path -LiteralPath $installedUpdaterDll)) `
        'Repair probe did not remove the installed updater DLL.'

    Invoke-MsiStep -Name 'corrected-repair' `
        -OperationArguments @(
            '/i', $correctedMsi, 'REINSTALL=ALL', 'REINSTALLMODE=vomus'
        ) -LogName '03-corrected-repair.log' | Out-Null
    Assert-ProductInstalled -ProductCode $correctedProductCode
    Assert-UpdaterDllHash -ExpectedSha256 ([string]$script:Expected.corrected.updater_dll_sha256)
    Assert-Condition (Test-Path -LiteralPath $repairProbe -PathType Leaf) `
        'Repair probe backup unexpectedly disappeared.'

    Invoke-MsiStep -Name 'corrected-uninstall' `
        -OperationArguments @('/x', $correctedProductCode) `
        -LogName '04-corrected-uninstall.log' | Out-Null
    Assert-ProductAbsent -ProductCode $oldProductCode
    Assert-ProductAbsent -ProductCode $correctedProductCode
    $installedSoffice = Join-Path ([string]$script:Expected.expected_install_root) `
        'program\soffice.exe'
    Assert-Condition (-not (Test-Path -LiteralPath $installedSoffice)) `
        "Installed soffice.exe remains after uninstall: $installedSoffice"

    $requiredSteps = @($script:Expected.required_steps)
    foreach ($requiredStep in $requiredSteps) {
        $matches = @($script:Steps | Where-Object {
            $_.name -eq $requiredStep -and $_.exit_code -eq 0 `
                -and -not $_.reboot_state_changed -and -not $_.cleanup
        })
        Assert-Condition ($matches.Count -eq 1) `
            "Required successful lifecycle step is missing or duplicated: $requiredStep"
    }
    Assert-Condition ($script:Steps.Count -eq $requiredSteps.Count) `
        'Guest recorded an unexpected or missing lifecycle step.'
    Assert-Condition (@($script:Steps | Where-Object { $_.cleanup }).Count -eq 0) `
        'Guest unexpectedly needed cleanup before lifecycle acceptance.'
    $lifecyclePassed = $true
}
catch {
    $failureMessage = $_.Exception.ToString()
}
finally {
    if ($script:SandboxAttested) {
        try {
            Invoke-BestEffortCleanup -CorrectedProductCode $correctedProductCode `
                -OldProductCode $oldProductCode
        }
        catch {
            $script:CleanupErrors.Add($_.Exception.ToString())
        }
    }

    $finalOldState = $null
    $finalCorrectedState = $null
    try {
        if ($oldProductCode) {
            $finalOldState = Get-ProductState -ProductCode $oldProductCode
        }
        if ($correctedProductCode) {
            $finalCorrectedState = Get-ProductState -ProductCode $correctedProductCode
        }
    }
    catch {
        $script:CleanupErrors.Add('Final product-state query failed: ' + $_.Exception.ToString())
    }
    $finalRebootState = $null
    $lifecycleRebootStateChanged = $true
    if ($script:Preflight) {
        try {
            $finalRebootState = Get-RebootSnapshot
            Add-RebootSnapshot -StepName '__lifecycle__' -Phase after `
                -Snapshot $finalRebootState
            $lifecycleRebootStateChanged =
                (Get-RebootFingerprint -Snapshot $script:Preflight.initial_reboot_state) -ne `
                (Get-RebootFingerprint -Snapshot $finalRebootState)
        }
        catch {
            $script:CleanupErrors.Add('Final reboot-state query failed: ' + $_.Exception.ToString())
        }
    }
    $anyRebootStateChanged = @($script:Steps | Where-Object { $_.reboot_state_changed }).Count -gt 0
    $requiredStepCount = if ($script:Expected) {
        @($script:Expected.required_steps).Count
    } else { -1 }
    $hasUnexpectedSteps = $script:Steps.Count -ne $requiredStepCount `
        -or @($script:Steps | Where-Object { $_.cleanup }).Count -ne 0
    $accepted = $lifecyclePassed -and $script:CleanupErrors.Count -eq 0 `
        -and $finalOldState -eq -1 -and $finalCorrectedState -eq -1 `
        -and -not $anyRebootStateChanged -and -not $lifecycleRebootStateChanged `
        -and -not $hasUnexpectedSteps
    if (-not $accepted -and [string]::IsNullOrWhiteSpace($failureMessage)) {
        $failureMessage = 'Lifecycle assertions or final cleanup acceptance failed.'
    }

    try {
        if (-not (Test-Path -LiteralPath $script:ResultsRoot)) {
            New-Item -ItemType Directory -Path $script:ResultsRoot | Out-Null
        }
        if ($script:Preflight) {
            Write-JsonFile -Value $script:Preflight `
                -LiteralPath (Join-Path $script:ResultsRoot 'preflight.json')
        }
        Write-JsonFile -Value ($script:Snapshots.ToArray()) `
            -LiteralPath (Join-Path $script:ResultsRoot 'reboot-snapshots.json')
        $results = [ordered]@{
            schema_version = 1
            run_id = if ($script:Expected) { [string]$script:Expected.run_id } else { 'unknown' }
            status = if ($accepted) { 'passed' } else { 'failed' }
            completed_at_utc = [DateTime]::UtcNow.ToString('o')
            steps = $script:Steps.ToArray()
            reboot_state_changed = $anyRebootStateChanged
            lifecycle_reboot_state_changed = $lifecycleRebootStateChanged
            final_reboot_state = $finalRebootState
            final_old_product_state = $finalOldState
            final_corrected_product_state = $finalCorrectedState
            cleanup_errors = $script:CleanupErrors.ToArray()
            error = $failureMessage
        }
        Write-JsonFile -Value $results -LiteralPath (Join-Path $script:ResultsRoot 'results.json')
        Publish-Results -Passed $accepted -ErrorMessage $failureMessage
    }
    catch {
        try {
            $fallback = [ordered]@{
                schema_version = 1
                run_id = if ($script:Expected) { [string]$script:Expected.run_id } else { 'unknown' }
                status = 'failed'
                completed_at_utc = [DateTime]::UtcNow.ToString('o')
                error = 'Publishing lifecycle results failed: ' + $_.Exception.ToString()
            }
            $fallbackPath = Join-Path $script:OutputRoot 'FAILURE.json'
            if (-not (Test-Path -LiteralPath $fallbackPath)) {
                Write-JsonFile -Value $fallback -LiteralPath $fallbackPath
            }
        }
        catch {
            # The host timeout is the fail-safe if even the narrow output mapping is unavailable.
        }
    }

    if ($script:SandboxAttested) {
        Start-Sleep -Seconds 2
        Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\shutdown.exe') `
            -ArgumentList '/s /t 0' -WindowStyle Hidden | Out-Null
    }
}
