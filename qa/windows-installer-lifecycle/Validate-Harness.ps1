#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$hostPath = Join-Path $repoRoot 'bin\Test-WindowsInstallerLifecycle.ps1'
$guestPath = Join-Path $PSScriptRoot 'guest-lifecycle.ps1'
$failures = New-Object 'System.Collections.Generic.List[string]'

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)
    $script:failures.Add($Message)
}

function Assert-Match {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Message
    )
    if ($Text -notmatch $Pattern) {
        Add-Failure -Message $Message
    }
}

function Assert-NotMatch {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][string]$Message
    )
    if ($Text -match $Pattern) {
        Add-Failure -Message $Message
    }
}

function Assert-Count {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Pattern,
        [Parameter(Mandatory)][int]$Expected,
        [Parameter(Mandatory)][string]$Message
    )
    $actual = [regex]::Matches($Text, $Pattern).Count
    if ($actual -ne $Expected) {
        Add-Failure -Message "$Message Expected $Expected, found $actual."
    }
}

foreach ($path in @($hostPath, $guestPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure -Message "Required harness file is missing: $path"
        continue
    }
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $path, [ref]$tokens, [ref]$parseErrors)
    foreach ($parseError in $parseErrors) {
        Add-Failure -Message (
            "PowerShell parse error in {0}:{1}: {2}" -f $path,
            $parseError.Extent.StartLineNumber, $parseError.Message)
    }
    $duplicateFunctions = @(
        $ast.FindAll({
            param($node)
            $node -is [Management.Automation.Language.FunctionDefinitionAst]
        }, $true) |
            Group-Object Name |
            Where-Object { $_.Count -gt 1 }
    )
    foreach ($duplicateFunction in $duplicateFunctions) {
        Add-Failure -Message (
            "Duplicate PowerShell function in {0}: {1} ({2} definitions)" -f
            $path, $duplicateFunction.Name, $duplicateFunction.Count)
    }
}

if ($failures.Count -eq 0) {
    $hostText = Get-Content -LiteralPath $hostPath -Raw
    $guestText = Get-Content -LiteralPath $guestPath -Raw

    Assert-Match $hostText "\[string\]\`$Mode\s*=\s*'Prepare'" `
        'The host default must remain prepare-only.'
    Assert-Match $hostText "'Inspect'\s*\{" `
        'The host must expose a non-launching prepared-run inspection mode.'
    Assert-Match $hostText "'Launch'\s*\{" `
        'The host must require the explicit Launch mode.'
    Assert-Match $hostText 'Start-Process\s+-FilePath\s+\$sandboxExecutable' `
        'Launch mode must start only the resolved Windows Sandbox executable.'
    Assert-NotMatch $hostText '(?i)msiexec\.exe|WindowsInstaller\.Installer' `
        'The host script must never invoke or automate Windows Installer.'
    Assert-Match $hostText "launch_requires_explicit_mode\s*=\s*\`$true" `
        'The prepared manifest must record the explicit launch boundary.'
    Assert-Match $hostText 'Assert-FreshOutput\s+-Run\s+\$run' `
        'Launch must reject a reused output directory.'
    Assert-Match $hostText 'Assert-WsbPolicy\s+-Run\s+\$Run' `
        'Launch must revalidate the generated Sandbox isolation policy.'
    Assert-Match $hostText "expectedNames\s*=\s*@\('old\.msi', 'corrected\.msi', 'expected\.json', 'guest-lifecycle\.ps1'\)" `
        'Launch must enforce the narrow mapped-input allowlist.'
    Assert-Match $hostText 'Assert-OutputArtifacts\s+-Run\s+\$run' `
        'Launch and Verify must validate the completion bundle.'
    Assert-Match $hostText 'artifact_manifest_sha256' `
        'The host must validate the guest artifact-manifest hash.'
    Assert-Match $hostText 'Host reboot or LibreOffice registration state changed' `
        'The host must compare its own safety snapshot before and after Sandbox.'
    Assert-Match $hostText "host-verification\.json" `
        'Host must persist its post-disposal and safety result outside the guest sentinel.'
    foreach ($processName in @(
        'WindowsSandbox.exe',
        'WindowsSandboxClient.exe',
        'WindowsSandboxRemoteSession.exe',
        'WindowsSandboxServer.exe'
    )) {
        if (-not $hostText.Contains($processName)) {
            Add-Failure -Message "Host disposal tracking is missing: $processName"
        }
    }
    Assert-Match $hostText 'Wait-ForWindowsSandboxDisposal\s+-Run\s+\$run' `
        'Sandbox disposal must be bound to the exact prepared run.'
    foreach ($requiredDisposalText in @(
        '[IO.Path]::GetFullPath($Run.WsbPath)',
        'MicrosoftWindows\.WindowsSandbox_',
        'cw5n1h2txyewy',
        'CloseMainWindow()'
    )) {
        if (-not $hostText.Contains($requiredDisposalText)) {
            Add-Failure -Message "Run-bound Sandbox disposal is missing: $requiredDisposalText"
        }
    }
    Assert-Match $hostText "Wait-ForWindowsSandboxProcessExit\s+-Names\s+@\('WindowsSandboxServer\.exe'\)[\s\S]*?CloseMainWindow\(\)" `
        'The Sandbox backend must exit normally before the run-bound client receives a graceful close request.'
    Assert-NotMatch $hostText '(?i)Stop-Process|taskkill|TerminateProcess|\.Kill\(|kill_process' `
        'The host harness must never force-kill a Sandbox process.'
    Assert-Match $hostText 'function\s+Assert-HostVerification' `
        'Host-retained lifecycle proof must have a dedicated validator.'
    Assert-Count $hostText 'Assert-HostVerification\s+-Run\s+\$run' 2 `
        'Launch and Verify must both require host-retained lifecycle proof.'

    foreach ($requiredText in @(
        '<VGpu>Disable</VGpu>',
        '<Networking>Disable</Networking>',
        '<AudioInput>Disable</AudioInput>',
        '<VideoInput>Disable</VideoInput>',
        '<PrinterRedirection>Disable</PrinterRedirection>',
        '<ClipboardRedirection>Disable</ClipboardRedirection>',
        '<SandboxFolder>C:\Lifecycle\Input</SandboxFolder>',
        '<SandboxFolder>C:\Lifecycle\Output</SandboxFolder>',
        '<ReadOnly>true</ReadOnly>',
        '<ReadOnly>false</ReadOnly>'
    )) {
        if (-not $hostText.Contains($requiredText)) {
            Add-Failure -Message "Generated .wsb is missing required setting: $requiredText"
        }
    }
    $wsbMatch = [regex]::Match(
        $hostText, '(?s)<Configuration>.*?</Configuration>')
    if (-not $wsbMatch.Success) {
        Add-Failure -Message 'The generated .wsb XML template was not found.'
    }
    else {
        try {
            [void][xml]$wsbMatch.Value
        }
        catch {
            Add-Failure -Message "The generated .wsb XML template is malformed: $($_.Exception.Message)"
        }
    }

    foreach ($pin in @(
        '437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43',
        '180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea',
        '199692288',
        '199688192',
        'windows-msi-local-20260720-577059e274',
        'windows-msi-local-20260720-fbba560e2'
    )) {
        if (-not $hostText.Contains($pin)) {
            Add-Failure -Message "Pinned release metadata is missing: $pin"
        }
    }

    foreach ($step in @(
        'old-install',
        'corrected-same-version-update',
        'corrected-repair',
        'corrected-uninstall'
    )) {
        Assert-Count $guestText ("Invoke-MsiStep\s+-Name\s+'" + [regex]::Escape($step) + "'") 1 `
            "Guest must invoke lifecycle step exactly once: $step."
    }
    Assert-Match $guestText 'New-Object\s+-ComObject\s+WindowsInstaller\.Installer' `
        'Guest preflight must use the Windows Installer COM API.'
    Assert-Count $guestText '(?m)^\s*\$rows\s*$' 1 `
        'MSI query results must return each row rather than one nested row collection.'
    Assert-NotMatch $guestText '(?m)^\s*,\$rows\s*$' `
        'MSI query results must not wrap every row in one outer array.'
    Assert-Match $guestText '\$properties\.ContainsKey\(\$requiredProperty\)' `
        'MSI identity parsing must require every pinned Property-table field.'
    Assert-Match $guestText 'function\s+Assert-WindowsSandboxIdentity' `
        'Guest must positively attest the Windows Sandbox boundary.'
    Assert-Match $guestText "WDAGUtilityAccount" `
        'Guest attestation must require the documented Windows Sandbox account.'
    Assert-Match $guestText "S-1-5-21-\(\?:\\d\+-\)\{3\}504" `
        'Guest attestation must require the WDAGUtilityAccount SID RID.'
    Assert-Match $guestText 'sandbox-readonly-attestation' `
        'Guest attestation must prove that the mapped input is read-only.'
    Assert-Match $guestText 'Assert-WindowsSandboxIdentity\r?\n\$script:SandboxAttested\s*=\s*\$true' `
        'Guest must complete attestation before enabling cleanup or shutdown.'
    Assert-Match $guestText "'OpenDatabase',\s*'InvokeMethod'" `
        'Guest preflight must open MSI databases read-only.'
    Assert-Match $guestText "'ProductState',\s*'GetProperty'" `
        'Guest preflight and cleanup must query MSI registration state.'
    foreach ($argument in @(
        '/norestart',
        'REBOOT=ReallySuppress',
        'MSIRESTARTMANAGERCONTROL=DisableShutdown',
        '/L*V!'
    )) {
        if (-not $guestText.Contains($argument)) {
            Add-Failure -Message "Guest MSI safety or updater argument is missing: $argument"
        }
    }
    $updateBlock = [regex]::Match(
        $guestText,
        '(?s)Invoke-MsiStep -Name ''corrected-same-version-update''.*?Assert-ProductAbsent -ProductCode \$oldProductCode'
    ).Value
    if ([string]::IsNullOrWhiteSpace($updateBlock)) {
        Add-Failure -Message 'Guest same-version update block is missing.'
    }
    else {
        Assert-Match $updateBlock "-OperationArguments\s+@\('/i',\s*\`$correctedMsi\)" `
            'Major-update operation must install the corrected MSI with /i.'
        Assert-NotMatch $updateBlock 'REINSTALL(?:MODE)?=' `
            'Major-update operation must not use repair-only REINSTALL properties.'
    }
    $repairBlock = [regex]::Match(
        $guestText,
        '(?s)Invoke-MsiStep -Name ''corrected-repair''.*?Assert-ProductInstalled -ProductCode \$correctedProductCode'
    ).Value
    if ([string]::IsNullOrWhiteSpace($repairBlock)) {
        Add-Failure -Message 'Guest corrected repair block is missing.'
    }
    else {
        foreach ($repairArgument in @('REINSTALL=ALL', 'REINSTALLMODE=vomus')) {
            if (-not $repairBlock.Contains($repairArgument)) {
                Add-Failure -Message "Guest repair argument is missing: $repairArgument"
            }
        }
    }
    Assert-Match $guestText '\$exitCode\s+-eq\s+0' `
        'Guest MSI acceptance must require exact exit code 0.'
    Assert-Match $guestText '3010 and 1641 fail the no-restart gate' `
        'Guest must explicitly reject both reboot-success exit codes.'
    Assert-Match $guestText "Add-RebootSnapshot\s+-StepName\s+\`$Name\s+-Phase\s+before" `
        'Guest must snapshot reboot state before each MSI operation.'
    Assert-Match $guestText "Add-RebootSnapshot\s+-StepName\s+\`$Name\s+-Phase\s+after" `
        'Guest must snapshot reboot state after each MSI operation.'
    Assert-Match $guestText 'MainEngineThread is returning 0' `
        'Guest must require a successful Windows Installer log terminator.'
    Assert-Match $guestText 'Move-Item\s+-LiteralPath\s+\$installedUpdaterDll' `
        'Repair must use the corrected updater DLL as a missing-file probe.'
    Assert-Match $guestText 'Invoke-BestEffortCleanup' `
        'Guest finally handling must retain best-effort MSI cleanup.'
    Assert-Match $guestText 'Publish-Results\s+-Passed\s+\$accepted' `
        'Guest must base completion publication on final acceptance.'
    Assert-Match $guestText 'ConvertTo-Json\s+-InputObject\s+\$Value' `
        'Guest JSON publication must preserve empty and singleton arrays.'
    foreach ($listName in @('Snapshots', 'Steps', 'CleanupErrors')) {
        Assert-Match $guestText ("\`$script:" + $listName + '\.ToArray\(\)') `
            "Guest must serialize the generic $listName list through ToArray()."
    }
    Assert-NotMatch $guestText '@\(\$script:(?:Snapshots|Steps|CleanupErrors)\)' `
        'Guest must not use PowerShell array subexpressions directly on generic lists.'
    Assert-Match $guestText 'Move-Item\s+-LiteralPath\s+\$temporarySentinel' `
        'Guest completion publication must use an atomic final sentinel move.'
    Assert-Match $guestText "if \(\`$Passed\) \{ 'COMPLETE\.json' \} else \{ 'FAILURE\.json' \}" `
        'COMPLETE.json must be selected only for a passed lifecycle.'
    Assert-NotMatch $guestText 'catch\s*\{\s*-1\s*\}' `
        'Windows Installer query failures must not be collapsed into an absent state.'
    Assert-Match $guestText '\$finalOldState\s+-eq\s+-1\s+-and\s+\$finalCorrectedState\s+-eq\s+-1' `
        'Guest completion must require exact successful unregistered product states.'
    Assert-Match $guestText '\$hasUnexpectedSteps[\s\S]*?-and\s+-not\s+\$hasUnexpectedSteps' `
        'Guest completion must reject extra or cleanup lifecycle steps.'
    Assert-Match $hostText 'final_old_product_state\s+-ne\s+-1' `
        'Host verification must require the exact unregistered old-product state.'
    Assert-Match $hostText 'final_corrected_product_state\s+-ne\s+-1' `
        'Host verification must require the exact unregistered corrected-product state.'
    Assert-NotMatch $guestText '(?i)Remove-ItemProperty|reg(?:\.exe)?\s+delete|REBOOT=Force|/forcerestart|shutdown\.exe[^\r\n]*/r' `
        'Guest must never delete reboot indicators or request a restart.'
    Assert-Match $guestText "-ArgumentList\s+'/s /t 0'" `
        'Guest may only shut down the disposable Sandbox after publication.'
    Assert-Match $guestText 'if\s*\(\$script:SandboxAttested\)\s*\{[\s\S]*?shutdown\.exe' `
        'Guest shutdown must be gated by successful Sandbox attestation.'
    foreach ($hash in @(
        '363db7d0ebfa878f084751aea4d6069e03ede53d71252c3007f11fd984834ade',
        '32f80adfcd5097ef54f13951b748a5703439aef0dbb751d6a4c5d3e6102446a3'
    )) {
        if (-not $hostText.Contains($hash)) {
            Add-Failure -Message "Updater DLL discriminator hash is missing from pinned inputs: $hash"
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    throw "Windows installer lifecycle harness validation failed with $($failures.Count) error(s)."
}

Write-Host 'Windows installer lifecycle harness static validation: PASS' -ForegroundColor Green
