[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceCommit,

    [string]$SourceRoot = '',

    [ValidateSet('Light', 'Dark', 'HighContrast')]
    [string]$Appearance = 'Light',

    [string]$DriverRoot = '',

    [string]$OutputRoot = '',

    [string]$RunId = '',

    [string]$McpUrl = '',

    [ValidateSet('Configured', 'Fresh', 'Legacy')]
    [string]$StartupProfile = 'Configured',

    [ValidateRange(15, 120)]
    [int]$ObservationSeconds = 15,

    [string]$EvidenceEntrypointPath = '',

    [switch]$KeyboardFocus,

    [switch]$Templates
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ($StartupProfile -ne 'Configured' -and ($KeyboardFocus -or $Templates)) {
    throw 'Fresh/Legacy no-nag startup runs do not accept Start Center interaction switches.'
}

$script:NoNagDeniedText = @(
    'Tip of the Day',
    'Did you know?',
    "What's new in",
    'Welcome to',
    'for the first time',
    'Please take a moment to personalize your settings',
    'You are running version',
    'Default file formats not registered',
    'Perform check on startup',
    'Crash Report',
    'Send Crash Report',
    'Support the development',
    'Help us make',
    'Autocorrection has removed a leading or trailing character'
)
$script:RetainedSafetyPromptText = @(
    'Document Recovery',
    'Troubleshoot Mode',
    'Incompatible Extensions',
    'Extension Dependencies',
    'Macros disabled',
    'Security Warning',
    'Hidden Information',
    'read-only mode',
    'Master Password',
    'Password Required',
    'Extension Update'
)
$script:NoNagForbiddenLaunchArguments = @(
    '--nologo',
    '--norestore',
    '--headless',
    '--invisible',
    '--nodefault'
)
$script:NoNagDeniedMatches = [System.Collections.Generic.List[object]]::new()

Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public static class LibreOfficeMaterialProcessPath
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inheritHandle, uint processId);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool QueryFullProcessImageName(
        IntPtr process, uint flags, StringBuilder path, ref uint size);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static string Get(uint processId)
    {
        const uint QueryLimitedInformation = 0x1000;
        IntPtr process = OpenProcess(QueryLimitedInformation, false, processId);
        if (process == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            uint size = 32768;
            var path = new StringBuilder((int)size);
            if (!QueryFullProcessImageName(process, 0, path, ref size))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            return path.ToString();
        }
        finally
        {
            CloseHandle(process);
        }
    }

}
'@

function Write-Utf8Lf {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$Text
    )

    $normalized = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    [System.IO.File]::WriteAllText(
        $Path,
        $normalized,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [object]$Value
    )

    Write-Utf8Lf -Path $Path -Text (($Value | ConvertTo-Json -Depth 20) + "`n")
}

function Get-JsonIntegerProperty {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$PropertyName
    )

    $property = $Object.PSObject.Properties[$PropertyName]
    if ($null -eq $property -or $null -eq $property.Value) {
        return $null
    }
    $integerTypes = @(
        [byte], [sbyte], [int16], [uint16], [int32], [uint32], [int64], [uint64]
    )
    if ($integerTypes -notcontains $property.Value.GetType()) {
        return $null
    }
    return [long]$property.Value
}

function Find-NoNagTextMatches {
    param([Parameter(Mandatory = $true)] [AllowEmptyCollection()] [string[]]$Text)

    $matches = [System.Collections.Generic.List[object]]::new()
    foreach ($candidate in @($Text)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        foreach ($denied in $script:NoNagDeniedText) {
            if ($candidate.IndexOf(
                    $denied,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0) {
                $matches.Add([ordered]@{
                    denied = $denied
                    observed = $candidate
                })
            }
        }
    }
    return $matches.ToArray()
}

function Assert-NoNagLaunchArguments {
    param([Parameter(Mandatory = $true)] [string[]]$Arguments)

    foreach ($argument in $Arguments) {
        foreach ($forbidden in $script:NoNagForbiddenLaunchArguments) {
            if ($argument -ieq $forbidden -or
                $argument.StartsWith(
                    "$forbidden=",
                    [System.StringComparison]::OrdinalIgnoreCase
                )) {
                throw "No-nag startup cannot use suppressive launch argument '$argument'."
            }
        }
    }
    if (@($Arguments | Where-Object { $_ -ceq '--writer' }).Count -ne 1) {
        throw 'No-nag startup must request exactly one blank Writer document.'
    }
}

function Record-WindowEnumeration {
    param(
        [Parameter(Mandatory = $true)] [object]$Enumeration,
        [Parameter(Mandatory = $true)] [string]$Phase,
        [AllowNull()] [object]$OwnedProcessId
    )

    $windows = [System.Collections.Generic.List[object]]::new()
    foreach ($window in @($Enumeration.windows)) {
        $processId = Get-JsonIntegerProperty -Object $window -PropertyName 'process_id'
        $record = [ordered]@{
            handle = Get-JsonIntegerProperty -Object $window -PropertyName 'handle'
            process_id = $processId
            thread_id = Get-JsonIntegerProperty -Object $window -PropertyName 'thread_id'
            title = [string]$window.title
            class = [string]$window.class
            width = Get-JsonIntegerProperty -Object $window -PropertyName 'width'
            height = Get-JsonIntegerProperty -Object $window -PropertyName 'height'
            dpi = Get-JsonIntegerProperty -Object $window -PropertyName 'dpi'
            payload_owned = ($null -ne $OwnedProcessId -and
                $null -ne $processId -and
                [long]$processId -eq [long]$OwnedProcessId)
        }
        $windows.Add($record)
    }
    $ownedWindows = @($windows.ToArray() | Where-Object { $_.payload_owned })
    $entry = [ordered]@{
        captured_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        phase = $Phase
        desktop_window_count = [int]$Enumeration.count
        payload_owned_window_count = $ownedWindows.Count
        windows = @($windows.ToArray())
    }
    $script:WindowPollLog.Add($entry)
    Write-JsonFile -Path $script:WindowPollLogPath -Value ([ordered]@{
        run_id = $script:RunId
        owned_process_id = $script:WindowPollOwnedProcessId
        observation_started_at_utc = $script:ObservationStartedAtUtc
        observation_completed_at_utc = $script:ObservationCompletedAtUtc
        observation_elapsed_milliseconds = $script:ObservationElapsedMilliseconds
        polls = @($script:WindowPollLog.ToArray())
    })
    return $entry
}

function Sync-WindowPollOwnership {
    param([Parameter(Mandatory = $true)] [int]$OwnedProcessId)

    $script:WindowPollOwnedProcessId = $OwnedProcessId
    foreach ($entry in @($script:WindowPollLog.ToArray())) {
        $ownedCount = 0
        foreach ($window in @($entry.windows)) {
            $isOwned = ($null -ne $window.process_id -and
                [long]$window.process_id -eq [long]$OwnedProcessId)
            $window.payload_owned = $isOwned
            if ($isOwned) { $ownedCount++ }
        }
        $entry.payload_owned_window_count = $ownedCount
    }
    Write-JsonFile -Path $script:WindowPollLogPath -Value ([ordered]@{
        run_id = $script:RunId
        owned_process_id = $OwnedProcessId
        observation_started_at_utc = $script:ObservationStartedAtUtc
        observation_completed_at_utc = $script:ObservationCompletedAtUtc
        observation_elapsed_milliseconds = $script:ObservationElapsedMilliseconds
        polls = @($script:WindowPollLog.ToArray())
    })
}

function Assert-NoNagWindowEnumeration {
    param(
        [Parameter(Mandatory = $true)] [object]$Entry,
        [Parameter(Mandatory = $true)] [long]$ExpectedHandle,
        [Parameter(Mandatory = $true)] [int]$ExpectedProcessId,
        [long]$ExpectedThreadId = 0,
        [int]$ExpectedDpi = 0,
        [int]$ExpectedWidth = 0,
        [int]$ExpectedHeight = 0,
        [string]$ExpectedTitle = '',
        [switch]$RequireSingleWriter
    )

    $allWindows = @($Entry.windows)
    if ([int]$Entry.desktop_window_count -ne $allWindows.Count) {
        throw 'No-nag desktop-window count differs from its retained inventory.'
    }
    $owned = @($allWindows | Where-Object { $_.payload_owned })
    $titleMatches = @(Find-NoNagTextMatches -Text @(
        $allWindows | ForEach-Object { [string]$_.title }
    ))
    if ($titleMatches.Count -ne 0) {
        foreach ($match in $titleMatches) { $script:NoNagDeniedMatches.Add($match) }
        throw "Former nag text appeared in an owned window title: $($titleMatches | ConvertTo-Json -Compress)"
    }
    if ($RequireSingleWriter) {
        if ($allWindows.Count -ne 1 -or $owned.Count -ne 1) {
            throw "No-nag observation expected exactly one total and payload-owned top-level window, found $($allWindows.Count) total / $($owned.Count) owned."
        }
        if ([long]$owned[0].handle -ne $ExpectedHandle -or
            [int]$owned[0].process_id -ne $ExpectedProcessId -or
            [long]$owned[0].thread_id -ne $ExpectedThreadId -or
            [int]$owned[0].dpi -ne $ExpectedDpi -or
            [int]$owned[0].width -ne $ExpectedWidth -or
            [int]$owned[0].height -ne $ExpectedHeight -or
            [string]$owned[0].class -cne 'SALFRAME' -or
            [string]$owned[0].title -cne $ExpectedTitle) {
            throw 'No-nag observation lost the exact PID/HWND/thread/DPI/geometry/title-owned Writer SALFRAME.'
        }
    }
}

function Assert-NoNagA11yReport {
    param([Parameter(Mandatory = $true)] [object]$Report)

    $observedText = [System.Collections.Generic.List[string]]::new()
    foreach ($node in @($Report.nodes)) {
        if (@($node.states) -notcontains 'VISIBLE' -and
            @($node.states) -notcontains 'SHOWING') {
            continue
        }
        foreach ($propertyName in @('name', 'description')) {
            $property = $node.PSObject.Properties[$propertyName]
            if ($null -ne $property -and
                -not [string]::IsNullOrWhiteSpace([string]$property.Value)) {
                $observedText.Add([string]$property.Value)
            }
        }
    }
    $matches = @(Find-NoNagTextMatches -Text $observedText.ToArray())
    if ($matches.Count -ne 0) {
        foreach ($match in $matches) { $script:NoNagDeniedMatches.Add($match) }
        throw "Former nag text appeared in the Writer accessibility tree: $($matches | ConvertTo-Json -Compress)"
    }
    $menuBars = @($Report.nodes | Where-Object { [string]$_.role.name -ceq 'MENU_BAR' })
    if ($menuBars.Count -eq 0) {
        throw 'No-nag Writer accessibility proof contains no menu bar.'
    }
    return $matches
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)] [string]$Path)

    $stream = $null
    $algorithm = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
        $algorithm = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $algorithm.ComputeHash($stream)
        return [System.BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if ($null -ne $algorithm) { $algorithm.Dispose() }
    }
}

function Invoke-EvidenceGit {
    param(
        [Parameter(Mandatory = $true)] [string]$Root,
        [Parameter(Mandatory = $true)] [string[]]$Arguments
    )

    $output = @(& git -C $Root @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Git failed in '$Root': git $($Arguments -join ' '): $($output -join "`n")"
    }
    return $output
}

function Get-GitEvidenceIdentity {
    param(
        [Parameter(Mandatory = $true)] [string]$Root,
        [Parameter(Mandatory = $true)] [string]$ExpectedCommit,
        [Parameter(Mandatory = $true)] [string]$Description
    )

    $resolved = [System.IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "$Description checkout does not exist: $resolved"
    }
    $top = (Invoke-EvidenceGit -Root $resolved -Arguments @('rev-parse', '--show-toplevel') |
        Select-Object -First 1).Trim()
    $head = (Invoke-EvidenceGit -Root $resolved -Arguments @('rev-parse', '--verify', 'HEAD') |
        Select-Object -First 1).Trim().ToLowerInvariant()
    if ($head -ne $ExpectedCommit.ToLowerInvariant()) {
        throw "$Description checkout is at $head, not expected commit $ExpectedCommit."
    }
    $dirtyEntries = @(Invoke-EvidenceGit -Root $resolved -Arguments @(
        'status', '--porcelain=v1', '--untracked-files=all'
    ))
    if ($dirtyEntries.Count -ne 0) {
        throw "$Description checkout must be clean for evidence: $($dirtyEntries -join '; ')"
    }
    $repository = @(Invoke-EvidenceGit -Root $resolved -Arguments @(
        'config', '--get', 'remote.origin.url'
    )) | Select-Object -First 1
    $repositoryValue = if ($repository) {
        $candidateRepository = $repository.Trim()
        if ($candidateRepository -match '^(?i)https?://[^/@]+@') {
            $candidateRepository = $candidateRepository -replace `
                '^(?i)(https?://)[^/@]+@', '$1'
        }
        if ($candidateRepository -match '^(?i)(file:|[A-Za-z]:[\\/]|\\\\)') {
            '<local-repository>'
        }
        else {
            $candidateRepository
        }
    }
    else { $null }
    return [ordered]@{
        repository = $repositoryValue
        commit = $head
        checkout_clean = $true
        dirty_worktree_entries = @()
    }
}

function Get-EvidenceFileIdentity {
    param(
        [Parameter(Mandatory = $true)] [string]$Path,
        [Parameter(Mandatory = $true)] [string]$PublicPath,
        [switch]$RuntimeOnly
    )

    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    $identity = [ordered]@{
        path = $PublicPath
        bytes = [long]$item.Length
        sha256 = Get-Sha256Hex -Path $item.FullName
    }
    if ($RuntimeOnly) {
        $identity.Add('retained_in_public_evidence', $false)
    }
    return $identity
}

function Get-CurrentIntegrityEvidence {
    $whoami = Join-Path $env:SystemRoot 'System32\whoami.exe'
    $groups = @(& $whoami /groups /fo csv /nh 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "whoami could not resolve the harness token integrity: $($groups -join "`n")"
    }
    $matches = [regex]::Matches(($groups -join "`n"), 'S-1-16-(\d+)')
    $rids = @($matches | ForEach-Object { [int]$_.Groups[1].Value } | Select-Object -Unique)
    if ($rids.Count -ne 1) {
        throw "Expected one mandatory integrity SID, found: $($rids -join ', ')"
    }
    $rid = [int]$rids[0]
    $label = switch ($rid) {
        { $_ -ge 20480 } { 'protected'; break }
        { $_ -ge 16384 } { 'system'; break }
        { $_ -ge 12288 } { 'high'; break }
        { $_ -ge 8448 } { 'medium-plus'; break }
        { $_ -ge 8192 } { 'medium'; break }
        { $_ -ge 4096 } { 'low'; break }
        default { 'untrusted' }
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return [ordered]@{
        mandatory_label_sid = "S-1-16-$rid"
        mandatory_label_rid = $rid
        level = $label
        is_administrator = $principal.IsInRole(
            [System.Security.Principal.WindowsBuiltInRole]::Administrator
        )
    }
}

function Invoke-LowLevelTool {
    param(
        [Parameter(Mandatory = $true)] [string]$Tool,
        [hashtable]$Arguments = @{},
        [int]$TimeoutSeconds = 60
    )

    $argumentsJson = $Arguments | ConvertTo-Json -Compress -Depth 10
    # Base64 avoids Windows PowerShell 5.1's destructive native-argument quote
    # handling, including nested quotes in a launch command line.
    $argumentsBase64 = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($argumentsJson)
    )
    $output = & uv run --directory $script:ResolvedDriverRoot python `
        $script:McpClientPath --url $script:McpUrl --tool $Tool `
        --arguments-base64 $argumentsBase64 --timeout $TimeoutSeconds 2>&1
    $exitCode = $LASTEXITCODE
    $outputText = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    if ($exitCode -ne 0) {
        throw "Low-level MCP tool '$Tool' failed with exit code ${exitCode}: $outputText"
    }
    try {
        return $outputText | ConvertFrom-Json
    }
    catch {
        throw "Low-level MCP tool '$Tool' returned invalid JSON: $outputText"
    }
}

function Get-FreeLoopbackPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    try {
        $listener.Start()
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Get-ExactPayloadProcesses {
    param([Parameter(Mandatory = $true)] [string]$ProgramRoot)

    $prefix = [System.IO.Path]::GetFullPath($ProgramRoot).TrimEnd('\') + '\'
    $matches = [System.Collections.Generic.List[object]]::new()
    foreach ($process in @(Get-Process -Name 'soffice', 'soffice.bin' -ErrorAction SilentlyContinue)) {
        try {
            $actual = [System.IO.Path]::GetFullPath(
                [LibreOfficeMaterialProcessPath]::Get([uint32]$process.Id)
            )
            if ($actual.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $matches.Add([pscustomobject]@{
                    ProcessId = $process.Id
                    Name = $process.ProcessName
                    ExecutablePath = $actual
                    CreationDate = $process.StartTime
                })
            }
        }
        catch [System.ArgumentException] {
            # The process exited between enumeration and the path query.
        }
        catch [System.InvalidOperationException] {
            # The process exited between enumeration and the path query.
        }
        catch [System.ComponentModel.Win32Exception] {
            # OpenProcess/QueryFullProcessImageName reports an exit race as a
            # Win32 error.  Preserve access/path failures for living processes.
            if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
                throw
            }
        }
    }
    return $matches.ToArray()
}

function Get-OwnedProcess {
    param(
        [Parameter(Mandatory = $true)] [int]$ProcessId,
        [Parameter(Mandatory = $true)] [string]$ProgramRoot
    )

    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    $prefix = [System.IO.Path]::GetFullPath($ProgramRoot).TrimEnd('\') + '\'
    $actual = [System.IO.Path]::GetFullPath(
        [LibreOfficeMaterialProcessPath]::Get([uint32]$ProcessId)
    )
    if (-not $actual.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Run PID $ProcessId belongs to '$actual', outside exact payload '$prefix'."
    }
    return [pscustomobject]@{
        ProcessId = $process.Id
        Name = $process.ProcessName
        ExecutablePath = $actual
        CreationDate = $process.StartTime
    }
}

function ConvertTo-WindowsCommandLineArgument {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Argument,
        [switch]$ForceQuote
    )

    if (-not $ForceQuote -and $Argument.Length -gt 0 -and
        $Argument -notmatch '[\s"]') {
        return $Argument
    }

    # ProcessStartInfo.ArgumentList is unavailable on Windows PowerShell 5.1.
    # Quote according to CommandLineToArgvW so Python receives spaces, quotes,
    # empty arguments, and trailing backslashes without mutation.
    $quoted = [System.Text.StringBuilder]::new()
    [void]$quoted.Append('"')
    $pendingBackslashes = 0
    foreach ($character in $Argument.ToCharArray()) {
        if ($character -eq '\') {
            $pendingBackslashes++
            continue
        }
        if ($character -eq '"') {
            [void]$quoted.Append(('\' * (($pendingBackslashes * 2) + 1)))
            [void]$quoted.Append('"')
            $pendingBackslashes = 0
            continue
        }
        if ($pendingBackslashes -gt 0) {
            [void]$quoted.Append(('\' * $pendingBackslashes))
            $pendingBackslashes = 0
        }
        [void]$quoted.Append($character)
    }
    if ($pendingBackslashes -gt 0) {
        [void]$quoted.Append(('\' * ($pendingBackslashes * 2)))
    }
    [void]$quoted.Append('"')
    return $quoted.ToString()
}

function Invoke-PayloadPython {
    param(
        [Parameter(Mandatory = $true)] [AllowEmptyString()] [string[]]$Arguments,
        [int]$TimeoutSeconds = 75
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:PayloadPython
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = (@($Arguments | ForEach-Object {
        ConvertTo-WindowsCommandLineArgument -Argument $_
    }) -join ' ')
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw 'Payload Python process did not start.'
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-ControlledProcessTree -RootProcess $process `
                -Description 'payload Python collector' `
                -TimeoutMilliseconds 15000
            throw "Payload Python exceeded the ${TimeoutSeconds}-second timeout and its validated exact process tree was stopped."
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $outputText = (@($stdout, $stderr) | Where-Object { $_ }) -join "`n"
        if ($process.ExitCode -ne 0) {
            throw "Payload Python failed with exit code $($process.ExitCode): $outputText"
        }
        return $outputText
    }
    finally {
        $process.Dispose()
    }
}

function Stop-ControlledProcessTree {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$RootProcess,
        [string]$Description = 'controlled process tree',
        [int]$TimeoutMilliseconds = 15000
    )

    $RootProcess.Refresh()
    if ($RootProcess.HasExited) {
        return
    }

    $rootProcessId = [int]$RootProcess.Id
    $snapshot = @(Get-CimInstance -ClassName Win32_Process -Property `
        ProcessId, ParentProcessId, CreationDate)
    $rootRecord = @($snapshot | Where-Object {
        [int]$_.ProcessId -eq $rootProcessId
    } | Select-Object -First 1)
    if ($rootRecord.Count -ne 1) {
        $RootProcess.Refresh()
        if (-not $RootProcess.HasExited) {
            throw "Could not identify $Description root PID $rootProcessId before cleanup."
        }
        return
    }

    $tree = [System.Collections.Generic.List[object]]::new()
    $tree.Add([pscustomobject]@{
        ProcessId = $rootProcessId
        ParentProcessId = [int]$rootRecord[0].ParentProcessId
        CreationTicks = ([DateTime]$rootRecord[0].CreationDate).ToUniversalTime().Ticks
        Depth = 0
    })
    for ($index = 0; $index -lt $tree.Count; $index++) {
        $parent = $tree[$index]
        foreach ($child in @($snapshot | Where-Object {
            [int]$_.ParentProcessId -eq [int]$parent.ProcessId
        })) {
            $tree.Add([pscustomobject]@{
                ProcessId = [int]$child.ProcessId
                ParentProcessId = [int]$child.ParentProcessId
                CreationTicks = ([DateTime]$child.CreationDate).ToUniversalTime().Ticks
                Depth = [int]$parent.Depth + 1
            })
        }
    }

    foreach ($record in @($tree.ToArray() | Sort-Object Depth -Descending)) {
        $processId = [int]$record.ProcessId
        $current = @(Get-CimInstance -ClassName Win32_Process `
            -Filter "ProcessId = $processId" -Property ProcessId, CreationDate)
        if ($current.Count -eq 0) {
            continue
        }
        $currentTicks = ([DateTime]$current[0].CreationDate).ToUniversalTime().Ticks
        if ($currentTicks -ne [long]$record.CreationTicks) {
            throw "Refusing to stop reused PID $processId while cleaning $Description."
        }
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }

    $RootProcess.WaitForExit($TimeoutMilliseconds) | Out-Null
    $RootProcess.Refresh()
    if (-not $RootProcess.HasExited) {
        throw "$Description root PID $rootProcessId did not stop."
    }

    foreach ($record in $tree.ToArray()) {
        $processId = [int]$record.ProcessId
        $current = @(Get-CimInstance -ClassName Win32_Process `
            -Filter "ProcessId = $processId" -Property ProcessId, CreationDate)
        if ($current.Count -eq 0) {
            continue
        }
        $currentTicks = ([DateTime]$current[0].CreationDate).ToUniversalTime().Ticks
        if ($currentTicks -eq [long]$record.CreationTicks) {
            throw "$Description still contains PID $processId."
        }
    }
}

function Stop-ExactPayloadProcesses {
    param(
        [Parameter(Mandatory = $true)] [string]$ProgramRoot,
        [int]$TimeoutSeconds = 15
    )

    $forced = $false
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $remaining = @(Get-ExactPayloadProcesses -ProgramRoot $ProgramRoot)
        if ($remaining.Count -eq 0) {
            return [pscustomobject]@{
                forced = $forced
                remaining = 0
            }
        }

        foreach ($remainingProcess in $remaining) {
            $remainingPid = [int]$remainingProcess.ProcessId
            try {
                Get-OwnedProcess -ProcessId $remainingPid `
                    -ProgramRoot $ProgramRoot | Out-Null
            }
            catch {
                if (-not (Get-Process -Id $remainingPid -ErrorAction SilentlyContinue)) {
                    continue
                }
                throw
            }

            try {
                Stop-Process -Id $remainingPid -Force -ErrorAction Stop
                $forced = $true
            }
            catch {
                if (Get-Process -Id $remainingPid -ErrorAction SilentlyContinue) {
                    throw
                }
            }
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTimeOffset]::UtcNow -lt $deadline)

    $remaining = @(Get-ExactPayloadProcesses -ProgramRoot $ProgramRoot)
    if ($remaining.Count -ne 0) {
        throw "Exact payload processes did not stop in ${TimeoutSeconds} seconds: $($remaining | ConvertTo-Json -Compress)"
    }
    return [pscustomobject]@{
        forced = $forced
        remaining = 0
    }
}

function Analyze-Screenshot {
    param([Parameter(Mandatory = $true)] [string]$Path)

    $output = & uv run --directory $script:ResolvedDriverRoot python `
        $script:PngAnalyzerPath $Path 2>&1
    $exitCode = $LASTEXITCODE
    $outputText = ($output | ForEach-Object { $_.ToString() }) -join "`n"
    if ($exitCode -ne 0) {
        throw "Screenshot analysis failed with exit code ${exitCode}: $outputText"
    }
    $analysis = $outputText | ConvertFrom-Json
    if (-not $analysis.nonblank -or $analysis.width -lt 640 -or $analysis.height -lt 480) {
        throw "Screenshot '$Path' is blank or unexpectedly small."
    }
    return $analysis
}

function Assert-A11yReport {
    param(
        [Parameter(Mandatory = $true)] [object]$Report,
        [switch]$RequireFocused
    )

    if ($Report.PSObject.Properties.Name -contains 'fatal_error') {
        throw "Accessibility collection failed: $($Report.fatal_error)"
    }
    if ($Report.summary.node_count -le 0 -or $Report.summary.visible_nodes -le 0) {
        throw 'Accessibility collection returned no visible nodes.'
    }
    if ($Report.summary.partial -or $Report.summary.errors -ne 0) {
        throw "Accessibility collection was partial or reported errors: $($Report.summary | ConvertTo-Json -Compress)"
    }
    $focused = @($Report.nodes | Where-Object { @($_.states) -contains 'FOCUSED' })
    if ($RequireFocused -and $focused.Count -eq 0) {
        throw 'Keyboard focus scenario exposed no FOCUSED accessibility node.'
    }
    return [ordered]@{
        node_count = [int]$Report.summary.node_count
        visible_nodes = [int]$Report.summary.visible_nodes
        errors = [int]$Report.summary.errors
        partial = [bool]$Report.summary.partial
        focused_node_count = $focused.Count
        focused_nodes = @($focused | ForEach-Object {
            [ordered]@{ path = @($_.path); role = $_.role.name; name = $_.name }
        })
    }
}

function Capture-State {
    param(
        [Parameter(Mandatory = $true)] [string]$Slug,
        [Parameter(Mandatory = $true)] [string]$ScenarioId,
        [Parameter(Mandatory = $true)] [string]$ScenarioName,
        [Parameter(Mandatory = $true)] [string[]]$InventoryIds,
        [Parameter(Mandatory = $true)] [string[]]$ExpectedCheckpoints,
        [Parameter(Mandatory = $true)] [string]$InputDescription,
        [switch]$RequireFocused,
        [switch]$Terminate
    )

    $screenshotPath = Join-Path $script:ScreenshotsRoot "$Slug.png"
    $capture = Invoke-LowLevelTool -Tool 'screenshot' -Arguments @{
        hwnd = [long]$script:WindowHandle
        output_path = $screenshotPath
    } -TimeoutSeconds 60
    if (-not $capture.rendered_ok) {
        throw "PrintWindow did not render '$Slug'."
    }
    $image = Analyze-Screenshot -Path $screenshotPath
    if ([int]$capture.width -ne [int]$image.width -or
        [int]$capture.height -ne [int]$image.height) {
        throw "Capture dimensions and PNG dimensions disagree for '$Slug'."
    }
    # Evidence archives move between machines; never persist a host-absolute
    # artifact path in the candidate manifest.
    $image.path = "screenshots/$Slug.png"

    $a11yPath = Join-Path $script:LogsRoot "a11y-$Slug.json"
    $progressPath = Join-Path $script:LogsRoot "a11y-$Slug-progress.json"
    $arguments = @(
        $script:A11yCollectorPath,
        '--pipe', $script:UnoPipe,
        '--output', $a11yPath,
        '--run-id', $script:RunId,
        '--screenshot-sha256', [string]$image.sha256,
        '--progress-output', $progressPath,
        '--timeout', '45',
        '--require-visible'
    )
    if ($Terminate) {
        $arguments += '--terminate'
    }
    Invoke-PayloadPython -Arguments $arguments -TimeoutSeconds 75 | Out-Null
    $a11y = Get-Content -LiteralPath $a11yPath -Raw | ConvertFrom-Json
    $a11ySummary = Assert-A11yReport -Report $a11y -RequireFocused:$RequireFocused
    $noNagMatches = @()
    if ($StartupProfile -ne 'Configured') {
        $noNagMatches = @(Assert-NoNagA11yReport -Report $a11y)
    }
    $a11yFile = Get-Item -LiteralPath $a11yPath
    $a11yHash = Get-Sha256Hex -Path $a11yPath

    return [ordered]@{
        id = $ScenarioId
        slug = $Slug
        name = $ScenarioName
        inventory_ids = @($InventoryIds)
        automation_result = 'pass'
        result = 'pending_visual_review'
        input = $InputDescription
        requires_focused_accessibility = [bool]$RequireFocused
        expected_checkpoints = @($ExpectedCheckpoints)
        checkpoint = [ordered]@{
            captured_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
            window_handle = [long]$script:WindowHandle
            window_process_id = [int]$script:WindowProcessId
            window_thread_id = [long]$script:WindowThreadId
            window_title = [string]$script:WindowTitle
            window_class = [string]$script:WindowClass
            window_dpi = [int]$script:WindowDpi
            normal_uno_termination_requested = [bool]$Terminate
        }
        screenshot = $image
        capture_api = 'PrintWindow through low-level computer-use MCP'
        accessibility = [ordered]@{
            path = "logs/a11y-$Slug.json"
            bytes = [long]$a11yFile.Length
            sha256 = $a11yHash
            screenshot_sha256 = [string]$a11y.screenshot_sha256
            summary = $a11ySummary
        }
        no_nag = if ($StartupProfile -ne 'Configured') {
            [ordered]@{
                denied_text_matches = @($noNagMatches)
                retained_safety_prompt_policy = 'not part of the former-nag denylist'
            }
        }
        else { $null }
    }
}

function Get-CimProcessIdentity {
    param([Parameter(Mandatory = $true)] [int]$ProcessId)

    $records = @(Get-CimInstance -ClassName Win32_Process `
        -Filter "ProcessId = $ProcessId" -Property ProcessId, ParentProcessId, CreationDate)
    if ($records.Count -eq 0) { return $null }
    if ($records.Count -ne 1) {
        throw "Expected one process identity for PID $ProcessId, found $($records.Count)."
    }
    return [pscustomobject]@{
        process_id = [int]$records[0].ProcessId
        parent_process_id = [int]$records[0].ParentProcessId
        creation_ticks = ([DateTime]$records[0].CreationDate).ToUniversalTime().Ticks
        creation_date = ([DateTime]$records[0].CreationDate).ToUniversalTime().ToString('o')
    }
}

function Get-ValidatedLoopbackListenerIdentity {
    param(
        [Parameter(Mandatory = $true)] [int]$Port,
        [Parameter(Mandatory = $true)] [System.Diagnostics.Process]$RootProcess
    )

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port `
        -ErrorAction Stop | Where-Object { $_.LocalAddress -eq '127.0.0.1' })
    $listenerPids = @($listeners | ForEach-Object { [int]$_.OwningProcess } |
        Select-Object -Unique)
    if ($listenerPids.Count -ne 1) {
        throw "Expected one dedicated loopback listener on port $Port, found $($listenerPids.Count)."
    }

    $rootIdentity = Get-CimProcessIdentity -ProcessId ([int]$RootProcess.Id)
    if ($null -eq $rootIdentity) {
        throw "Dedicated driver root PID $($RootProcess.Id) exited before listener ownership was bound."
    }
    $expectedRootTicks = $RootProcess.StartTime.ToUniversalTime().Ticks
    if ([long]$rootIdentity.creation_ticks -ne $expectedRootTicks) {
        throw "Dedicated driver root PID $($RootProcess.Id) was reused before listener ownership was bound."
    }

    $listenerIdentity = Get-CimProcessIdentity -ProcessId $listenerPids[0]
    $cursor = $listenerIdentity
    $visited = [System.Collections.Generic.HashSet[int]]::new()
    while ($null -ne $cursor -and $visited.Add([int]$cursor.process_id)) {
        if ([int]$cursor.process_id -eq [int]$rootIdentity.process_id -and
            [long]$cursor.creation_ticks -eq [long]$rootIdentity.creation_ticks) {
            return $listenerIdentity
        }
        if ([int]$cursor.parent_process_id -le 0) { break }
        $cursor = Get-CimProcessIdentity -ProcessId ([int]$cursor.parent_process_id)
    }
    throw "Loopback listener PID $($listenerIdentity.process_id) is not the dedicated driver root or its live descendant."
}

function Stop-RecordedProcessIdentity {
    param(
        [Parameter(Mandatory = $true)] [object]$Identity,
        [int]$TimeoutMilliseconds = 15000
    )

    $current = Get-CimProcessIdentity -ProcessId ([int]$Identity.process_id)
    if ($null -eq $current) { return $false }
    if ([long]$current.creation_ticks -ne [long]$Identity.creation_ticks) {
        throw "Refusing to stop reused listener PID $($Identity.process_id)."
    }
    Stop-Process -Id ([int]$Identity.process_id) -Force -ErrorAction Stop
    $deadline = [DateTimeOffset]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        Start-Sleep -Milliseconds 100
        $current = Get-CimProcessIdentity -ProcessId ([int]$Identity.process_id)
        if ($null -eq $current) { return $true }
        if ([long]$current.creation_ticks -ne [long]$Identity.creation_ticks) {
            return $true
        }
    } while ([DateTimeOffset]::UtcNow -lt $deadline)
    throw "Dedicated listener PID $($Identity.process_id) did not stop."
}

function ConvertTo-WindowsBatchCommandLineArgument {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Argument
    )

    if ($Argument -match "[`r`n]") {
        throw 'A Windows batch launch argument cannot contain a newline.'
    }

    # A literal URI escape such as %20 is parsed as the second batch argument
    # followed by "0" inside a .cmd file. Doubling every percent preserves the
    # literal percent through the one batch-expansion pass. Force quotes around
    # cmd metacharacters even when the Windows argv value contains no spaces.
    $batchEscaped = $Argument.Replace('%', '%%')
    $forceQuote = $batchEscaped -match '[&|<>^()]'
    return ConvertTo-WindowsCommandLineArgument -Argument $batchEscaped `
        -ForceQuote:$forceQuote
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$payloadFull = [System.IO.Path]::GetFullPath($PayloadRoot)
$programRoot = Join-Path $payloadFull 'program'
$script:PayloadPython = Join-Path $programRoot 'python.exe'
$soffice = Join-Path $programRoot 'soffice.exe'
$sofficeBin = Join-Path $programRoot 'soffice.bin'
$updaterLibrary = Join-Path $programRoot 'updchklo.dll'
$materialThemeDefinition = Join-Path $payloadFull `
    'share\theme_definitions\material\definition.xml'
$script:McpClientPath = Join-Path $PSScriptRoot 'call-lowlevel-mcp.py'
$script:PngAnalyzerPath = Join-Path $PSScriptRoot 'analyze-png.py'
$script:A11yCollectorPath = Join-Path $PSScriptRoot 'dump-a11y.py'
$evidenceValidatorPath = Join-Path $PSScriptRoot 'Validate-Windows-Headless-Evidence.ps1'
$script:McpUrl = $McpUrl

if (-not $DriverRoot) {
    $script:ResolvedDriverRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $repoRoot '..\lowlevel-computer-use-mcp')
    )
}
else {
    $script:ResolvedDriverRoot = [System.IO.Path]::GetFullPath($DriverRoot)
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'LibreOfficeMaterialQA'
}
$outputFull = [System.IO.Path]::GetFullPath($OutputRoot)

foreach ($required in @(
    $soffice,
    $sofficeBin,
    $updaterLibrary,
    $materialThemeDefinition,
    $script:PayloadPython,
    $script:McpClientPath,
    $script:PngAnalyzerPath,
    $script:A11yCollectorPath,
    $evidenceValidatorPath,
    (Join-Path $script:ResolvedDriverRoot 'pyproject.toml')
)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file is missing: $required"
    }
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required to run the sibling low-level MCP client environment.'
}

$driverCommit = (& git -C $script:ResolvedDriverRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $driverCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not resolve the sibling low-level driver commit.'
}
$driverStatus = @(& git -C $script:ResolvedDriverRoot status --porcelain)
if ($LASTEXITCODE -ne 0 -or $driverStatus.Count -ne 0) {
    throw 'The sibling low-level driver checkout must be clean for accepted evidence.'
}

$sourceLower = $SourceCommit.ToLowerInvariant()
$driverIdentity = Get-GitEvidenceIdentity -Root $script:ResolvedDriverRoot `
    -ExpectedCommit $driverCommit -Description 'Low-level driver'
$harnessCommit = (& git -C $repoRoot rev-parse --verify HEAD).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $harnessCommit -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not resolve the evidence harness commit.'
}
$resolvedSourceRoot = if ($SourceRoot) {
    [System.IO.Path]::GetFullPath($SourceRoot)
}
else {
    $repoRoot
}
$sourceIdentity = Get-GitEvidenceIdentity -Root $resolvedSourceRoot `
    -ExpectedCommit $sourceLower -Description 'Source'
$harnessIdentity = Get-GitEvidenceIdentity -Root $repoRoot `
    -ExpectedCommit $harnessCommit -Description 'Harness'

$provenanceText = @(Invoke-EvidenceGit -Root $resolvedSourceRoot -Arguments @(
    'show', "$($sourceLower):docs/PROVENANCE.md"
)) -join "`n"
$baselineMatches = [regex]::Matches(
    $provenanceText,
    '(?m)^\| Upstream commit \| `([0-9a-f]{40})` \|\s*$'
)
if ($baselineMatches.Count -ne 1) {
    throw 'The exact source commit must declare one upstream baseline in docs/PROVENANCE.md.'
}
$upstreamBaseline = $baselineMatches[0].Groups[1].Value

$versionIniPath = Join-Path $programRoot 'version.ini'
if (-not (Test-Path -LiteralPath $versionIniPath -PathType Leaf)) {
    throw "Payload version metadata is missing: $versionIniPath"
}
$versionIniText = Get-Content -LiteralPath $versionIniPath -Raw
$buildIdMatches = [regex]::Matches(
    $versionIniText,
    '(?im)^\s*buildid\s*=\s*([0-9a-f]{40})\s*$'
)
if ($buildIdMatches.Count -ne 1) {
    throw 'Payload program/version.ini must contain exactly one 40-character buildid.'
}
$embeddedBuildId = $buildIdMatches[0].Groups[1].Value.ToLowerInvariant()
if ($embeddedBuildId -ne $sourceLower) {
    throw "Payload build ID $embeddedBuildId does not match source commit $sourceLower."
}

$driverProjectText = Get-Content -LiteralPath `
    (Join-Path $script:ResolvedDriverRoot 'pyproject.toml') -Raw
$driverNameMatches = [regex]::Matches(
    $driverProjectText,
    '(?m)^name\s*=\s*"([^"]+)"\s*$'
)
$driverVersionMatches = [regex]::Matches(
    $driverProjectText,
    '(?m)^version\s*=\s*"([^"]+)"\s*$'
)
if ($driverNameMatches.Count -ne 1 -or $driverVersionMatches.Count -ne 1) {
    throw 'Could not resolve one low-level MCP package name and version from pyproject.toml.'
}
$driverPackageName = $driverNameMatches[0].Groups[1].Value
$driverPackageVersion = $driverVersionMatches[0].Groups[1].Value
$integrityEvidence = Get-CurrentIntegrityEvidence

$shortCommit = $sourceLower.Substring(0, 10)
$appearanceSlug = $Appearance.ToLowerInvariant()
$startupProfileSlug = $StartupProfile.ToLowerInvariant()
$runModeSlug = if ($StartupProfile -eq 'Configured') {
    $appearanceSlug
}
else {
    "nonag-$startupProfileSlug"
}
if (-not $RunId) {
    $RunId = '{0}-{1}-windows-headless-{2}' -f `
        (Get-Date -Format 'yyyyMMdd-HHmmss'), $shortCommit, $runModeSlug
}
if ($RunId -notmatch '^[A-Za-z0-9._-]+$') {
    throw 'RunId may contain only letters, numbers, dot, underscore, and hyphen.'
}
$script:RunId = $RunId
$runRoot = Join-Path $outputFull $RunId
if (Test-Path -LiteralPath $runRoot) {
    throw "Run directory already exists: $runRoot"
}
$script:ScreenshotsRoot = Join-Path $runRoot 'screenshots'
$script:LogsRoot = Join-Path $runRoot 'logs'
$profileRoot = Join-Path $runRoot 'profile'
$profileUserRoot = Join-Path $profileRoot 'user'
New-Item -ItemType Directory -Path $script:ScreenshotsRoot, $script:LogsRoot, $profileRoot -Force | Out-Null

$appearanceValue = if ($Appearance -eq 'Dark') { 2 } else { 1 }
$highContrastValue = if ($Appearance -eq 'HighContrast') { 2 } else { 1 }
$profileConfig = $null
$profileConfigPath = $null
$profileConfigurationIdentity = $null
$legacyCrashConfigurationIdentity = $null
$profileSeedArtifacts = [System.Collections.Generic.List[object]]::new()
$legacyTriggerNames = @()
$legacyCrashSeeded = $false
if ($StartupProfile -eq 'Configured') {
    New-Item -ItemType Directory -Path $profileUserRoot -Force | Out-Null
    $profileConfig = @"
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="FirstRun" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Appearance"><prop oor:name="ApplicationAppearance" oor:op="fuse"><value>$appearanceValue</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Accessibility"><prop oor:name="HighContrast" oor:op="fuse"><value>$highContrastValue</value></prop></item>
</oor:items>
"@
    $profileConfigPath = Join-Path $profileUserRoot 'registrymodifications.xcu'
    Write-Utf8Lf -Path $profileConfigPath -Text $profileConfig
}
elseif ($StartupProfile -eq 'Legacy') {
    New-Item -ItemType Directory -Path $profileUserRoot -Force | Out-Null
    # BEGIN LEGACY NO-NAG REGISTRY SEED
    $profileConfig = @'
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Misc">
<prop oor:name="FirstRun" oor:op="fuse"><value>true</value></prop>
<prop oor:name="CrashReport" oor:op="fuse"><value>true</value></prop>
<prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>true</value></prop>
<prop oor:name="LastTipOfTheDayShown" oor:op="fuse"><value>-1</value></prop>
<prop oor:name="PerformFileExtCheck" oor:op="fuse"><value>true</value></prop>
<prop oor:name="ShowDonation" oor:op="fuse"><value>true</value></prop>
</item>
<item oor:path="/org.openoffice.Setup/Product">
<prop oor:name="ooSetupLastVersion" oor:op="fuse"><value>1.0</value></prop>
<prop oor:name="WhatsNew" oor:op="fuse"><value>true</value></prop>
<prop oor:name="WhatsNewDialog" oor:op="fuse"><value>true</value></prop>
<prop oor:name="LastTimeGetInvolvedShown" oor:op="fuse"><value>1</value></prop>
<prop oor:name="LastTimeDonateShown" oor:op="fuse"><value>1</value></prop>
</item>
<item oor:path="/org.openoffice.Office.UI.Infobar/Enabled">
<prop oor:name="Donate" oor:op="fuse"><value>true</value></prop>
<prop oor:name="GetInvolved" oor:op="fuse"><value>true</value></prop>
<prop oor:name="WhatsNew" oor:op="fuse"><value>true</value></prop>
<prop oor:name="AutoCorrLeadTrail" oor:op="fuse"><value>true</value></prop>
</item>
</oor:items>
'@
    # END LEGACY NO-NAG REGISTRY SEED
    $legacyTriggerNames = @(
        'Office.Common/Misc/FirstRun',
        'Office.Common/Misc/CrashReport',
        'Office.Common/Misc/ShowTipOfTheDay',
        'Office.Common/Misc/LastTipOfTheDayShown',
        'Office.Common/Misc/PerformFileExtCheck',
        'Office.Common/Misc/ShowDonation',
        'Setup/Product/ooSetupLastVersion',
        'Setup/Product/WhatsNew',
        'Setup/Product/WhatsNewDialog',
        'Setup/Product/LastTimeGetInvolvedShown',
        'Setup/Product/LastTimeDonateShown',
        'Office.UI/Infobar/Enabled/Donate',
        'Office.UI/Infobar/Enabled/GetInvolved',
        'Office.UI/Infobar/Enabled/WhatsNew',
        'Office.UI/Infobar/Enabled/AutoCorrLeadTrail'
    )
    $profileConfigPath = Join-Path $profileUserRoot 'registrymodifications.xcu'
    Write-Utf8Lf -Path $profileConfigPath -Text $profileConfig
    $publicProfileSeedPath = Join-Path $script:LogsRoot 'legacy-profile-seed.xcu'
    Write-Utf8Lf -Path $publicProfileSeedPath -Text $profileConfig
    $profileSeedArtifacts.Add((Get-EvidenceFileIdentity `
        -Path $publicProfileSeedPath -PublicPath 'logs/legacy-profile-seed.xcu'))

    $crashRoot = Join-Path $profileRoot 'crash'
    New-Item -ItemType Directory -Path $crashRoot -Force | Out-Null
    $crashConfigPath = Join-Path $crashRoot 'dump.ini'
    $crashConfig = @"
DumpFile=$runRoot\crash\nonexistent-probe.dmp
Version=legacy-profile-probe
URL=http://127.0.0.1:9/
"@
    Write-Utf8Lf -Path $crashConfigPath -Text $crashConfig
    $legacyCrashConfigurationIdentity = Get-EvidenceFileIdentity `
        -Path $crashConfigPath -PublicPath 'profile/crash/dump.ini' -RuntimeOnly
    $publicCrashSeedPath = Join-Path $script:LogsRoot 'legacy-crash-seed.ini'
    $publicCrashConfig = @'
DumpFile=<run-root>\crash\nonexistent-probe.dmp
Version=legacy-profile-probe
URL=http://127.0.0.1:9/
'@
    Write-Utf8Lf -Path $publicCrashSeedPath -Text $publicCrashConfig
    $profileSeedArtifacts.Add((Get-EvidenceFileIdentity `
        -Path $publicCrashSeedPath -PublicPath 'logs/legacy-crash-seed.ini'))
    $legacyCrashSeeded = $true
}

if ($StartupProfile -eq 'Fresh' -and
    @(Get-ChildItem -LiteralPath $profileRoot -Force).Count -ne 0) {
    throw 'Fresh no-nag profile must be empty before launch preparation.'
}

$script:UnoPipe = "LibreOfficeMaterialQA-$shortCommit-$runModeSlug-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$desktopName = "LOMaterialQA-$shortCommit-$runModeSlug-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
if ($desktopName.Length -gt 64) {
    throw 'Generated desktop name exceeds the driver contract.'
}
$pidPath = Join-Path $runRoot 'soffice.pid'
$stdoutPath = Join-Path $script:LogsRoot 'soffice.stdout.log'
$stderrPath = Join-Path $script:LogsRoot 'soffice.stderr.log'
$wrapperPath = Join-Path $runRoot 'launch-headless.cmd'
if ($wrapperPath.Contains('%')) {
    throw 'OutputRoot cannot contain a percent sign because cmd.exe expands it before the private launch wrapper starts.'
}
$profileUri = [System.Uri]::new($profileRoot).AbsoluteUri
$acceptArgument = "--accept=pipe,name=$($script:UnoPipe);urp"
$publicProfileUri = '<run-root-uri>/profile'
$publicPidPath = '<run-root>/soffice.pid'
$applicationArguments = $null
$publicApplicationArguments = $null
if ($StartupProfile -eq 'Configured') {
    $applicationArguments = @(
        "-env:UserInstallation=$profileUri", '--nologo', '--norestore',
        '--quickstart=no', '--language=en-US', "--pidfile=$pidPath", $acceptArgument
    )
    $publicApplicationArguments = @(
        "-env:UserInstallation=$publicProfileUri", '--nologo', '--norestore',
        '--quickstart=no', '--language=en-US', "--pidfile=$publicPidPath", $acceptArgument
    )
}
# BEGIN NO-NAG APPLICATION ARGUMENTS
else {
    $applicationArguments = @(
        "-env:UserInstallation=$profileUri", '--writer', '--quickstart=no',
        '--language=en-US', "--pidfile=$pidPath", $acceptArgument
    )
    $publicApplicationArguments = @(
        "-env:UserInstallation=$publicProfileUri", '--writer', '--quickstart=no',
        '--language=en-US', "--pidfile=$publicPidPath", $acceptArgument
    )
    if ($StartupProfile -ne 'Configured') {
        # Never assign a nonempty CRASH_DUMP_ENABLE value: CrashReporter treats
        # even "0" as enabled. The private wrapper removes an inherited value,
        # and this bootstrap value disables dump creation in both disposable
        # no-nag profiles. The legacy dump.ini still seeds the historical
        # prompt condition without pointing at a real dump.
        $applicationArguments += '-env:CrashDumpEnable=false'
        $publicApplicationArguments += '-env:CrashDumpEnable=false'
    }
    Assert-NoNagLaunchArguments -Arguments $applicationArguments
    Assert-NoNagLaunchArguments -Arguments $publicApplicationArguments
}
# END NO-NAG APPLICATION ARGUMENTS
$applicationCommandLine = @($applicationArguments | ForEach-Object {
    ConvertTo-WindowsBatchCommandLineArgument -Argument $_
}) -join ' '
$sofficeCommandToken = ConvertTo-WindowsBatchCommandLineArgument -Argument $soffice
$stdoutCommandToken = ConvertTo-WindowsBatchCommandLineArgument -Argument $stdoutPath
$stderrCommandToken = ConvertTo-WindowsBatchCommandLineArgument -Argument $stderrPath
$noNagCrashEnvironment = if ($StartupProfile -ne 'Configured') {
    # Remove an inherited truthy process override so the explicit bootstrap
    # CrashDumpEnable=false value remains authoritative.
    'set "CRASH_DUMP_ENABLE="'
}
else { '' }
$wrapper = @"
@echo off
setlocal DisableDelayedExpansion
set "VCL_DRAW_WIDGETS_FROM_FILE=1"
set "VCL_FILE_WIDGET_THEME=material"
set "SAL_SKIA=raster"
set "SAL_DISABLEGL=1"
set "SAL_LOG=+WARN.vcl.gdi"
$noNagCrashEnvironment
$sofficeCommandToken $applicationCommandLine 1>$stdoutCommandToken 2>$stderrCommandToken
exit /b %ERRORLEVEL%
"@
$existing = @(Get-ExactPayloadProcesses -ProgramRoot $programRoot)
if ($existing.Count -ne 0) {
    throw "Exact payload already has running processes: $($existing | ConvertTo-Json -Compress)"
}

# Finish every fallible provenance/hash probe before writing the path-bearing
# runtime wrapper. A failed preflight therefore cannot strand that private file.
$versionMetadataIdentity = Get-EvidenceFileIdentity -Path $versionIniPath `
    -PublicPath 'program/version.ini'
$expectedEvidenceEntrypointPath = if ($StartupProfile -eq 'Configured') {
    [System.IO.Path]::GetFullPath($PSCommandPath)
}
else {
    [System.IO.Path]::GetFullPath(
        (Join-Path $PSScriptRoot 'Run-Windows-NoNag-Headless-Smoke.ps1')
    )
}
$resolvedEvidenceEntrypointPath = if ($EvidenceEntrypointPath) {
    [System.IO.Path]::GetFullPath($EvidenceEntrypointPath)
}
else {
    [System.IO.Path]::GetFullPath($PSCommandPath)
}
if (-not $resolvedEvidenceEntrypointPath.Equals(
        $expectedEvidenceEntrypointPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
    throw "Startup profile '$StartupProfile' requires evidence entrypoint '$expectedEvidenceEntrypointPath'."
}
$publicEntrypointPath = if ($StartupProfile -eq 'Configured') {
    'bin/Run-Windows-Headless-Smoke.ps1'
}
else {
    'bin/Run-Windows-NoNag-Headless-Smoke.ps1'
}
$harnessEntrypointIdentity = Get-EvidenceFileIdentity `
    -Path $resolvedEvidenceEntrypointPath -PublicPath $publicEntrypointPath
$harnessDependencyList = [System.Collections.Generic.List[object]]::new()
$harnessDependencyList.Add((Get-EvidenceFileIdentity -Path $script:McpClientPath `
    -PublicPath 'bin/call-lowlevel-mcp.py'))
$harnessDependencyList.Add((Get-EvidenceFileIdentity -Path $script:PngAnalyzerPath `
    -PublicPath 'bin/analyze-png.py'))
$harnessDependencyList.Add((Get-EvidenceFileIdentity -Path $script:A11yCollectorPath `
    -PublicPath 'bin/dump-a11y.py'))
$harnessDependencyList.Add((Get-EvidenceFileIdentity -Path $evidenceValidatorPath `
    -PublicPath 'bin/Validate-Windows-Headless-Evidence.ps1'))
if ($StartupProfile -ne 'Configured') {
    $harnessDependencyList.Add((Get-EvidenceFileIdentity -Path $PSCommandPath `
        -PublicPath 'bin/Run-Windows-Headless-Smoke.ps1'))
}
$harnessDependencyIdentities = @($harnessDependencyList.ToArray())
$sofficeIdentity = Get-EvidenceFileIdentity -Path $soffice `
    -PublicPath 'program/soffice.exe'
$runtimeIdentity = Get-EvidenceFileIdentity -Path $sofficeBin `
    -PublicPath 'program/soffice.bin'
$updaterIdentity = Get-EvidenceFileIdentity -Path $updaterLibrary `
    -PublicPath 'program/updchklo.dll'
$themeIdentity = Get-EvidenceFileIdentity -Path $materialThemeDefinition `
    -PublicPath 'share/theme_definitions/material/definition.xml'
$pythonIdentity = Get-EvidenceFileIdentity -Path $script:PayloadPython `
    -PublicPath 'program/python.exe'
if ($profileConfigPath) {
    $profileConfigurationIdentity = Get-EvidenceFileIdentity -Path $profileConfigPath `
        -PublicPath 'profile/user/registrymodifications.xcu' -RuntimeOnly
}
$harnessWindowsSessionId = [int](Get-Process -Id $PID -ErrorAction Stop).SessionId

try {
    Write-Utf8Lf -Path $wrapperPath -Text $wrapper
    $launchWrapperIdentity = Get-EvidenceFileIdentity -Path $wrapperPath `
        -PublicPath 'launch-headless.cmd' -RuntimeOnly
}
catch {
    if (Test-Path -LiteralPath $wrapperPath -PathType Leaf) {
        Remove-Item -LiteralPath $wrapperPath -Force -ErrorAction SilentlyContinue
    }
    throw
}

$results = [ordered]@{
    schema_version = 2
    run_id = $RunId
    status = 'running'
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    completed_at_utc = $null
    source_commit = $sourceLower
    source = [ordered]@{
        repository = $sourceIdentity.repository
        commit = $sourceLower
        upstream_baseline = $upstreamBaseline
        checkout_clean = $sourceIdentity.checkout_clean
        checkout_dirty = (-not $sourceIdentity.checkout_clean)
        dirty_worktree_entries = @($sourceIdentity.dirty_worktree_entries)
        embedded_build_id = $embeddedBuildId
        version_metadata = $versionMetadataIdentity
    }
    harness = [ordered]@{
        repository = $harnessIdentity.repository
        commit = $harnessCommit
        checkout_clean = $harnessIdentity.checkout_clean
        checkout_dirty = (-not $harnessIdentity.checkout_clean)
        dirty_worktree_entries = @($harnessIdentity.dirty_worktree_entries)
        entrypoint = $harnessEntrypointIdentity
        dependencies = @($harnessDependencyIdentities)
    }
    appearance = if ($StartupProfile -eq 'Configured') { $Appearance } else { 'SystemDefault' }
    profile_values = if ($StartupProfile -eq 'Configured') {
        [ordered]@{
            ApplicationAppearance = $appearanceValue
            HighContrast = $highContrastValue
        }
    }
    else { $null }
    environment = [ordered]@{
        VCL_DRAW_WIDGETS_FROM_FILE = '1'
        VCL_FILE_WIDGET_THEME = 'material'
        SAL_SKIA = 'raster'
        SAL_DISABLEGL = '1'
        SAL_LOG = '+WARN.vcl.gdi'
        CRASH_DUMP_ENABLE = if ($StartupProfile -ne 'Configured') {
            '<cleared-before-launch>'
        }
        else { '<not-modified>' }
    }
    host = [ordered]@{
        operating_system = [System.Environment]::OSVersion.VersionString
        architecture = $env:PROCESSOR_ARCHITECTURE
        host_locale = [Globalization.CultureInfo]::CurrentCulture.Name
        ui_locale = [Globalization.CultureInfo]::CurrentUICulture.Name
        desktop_backend = 'Win32 off-screen desktop with per-window PrintWindow capture'
        display_scale = [ordered]@{
            dpi = $null
            percent = $null
            reference_dpi = 96
            source = 'GetDpiForWindow in the low-level list_headless_windows enumeration callback'
        }
        font_configuration = [ordered]@{
            source = 'native Windows system fonts inherited by LibreOffice VCL'
            run_specific_override = $false
            override_files = @()
        }
    }
    application = [ordered]@{
        executable = $sofficeIdentity
        runtime_executable = $runtimeIdentity
        updater_library = $updaterIdentity
        material_theme_definition = $themeIdentity
        python_executable = $pythonIdentity
        arguments = @($publicApplicationArguments)
        arguments_path_tokenized = $true
        launch_wrapper = $launchWrapperIdentity
        startup_profile = $startupProfileSlug
        isolated_profile_root = 'profile'
        user_profile_root = 'profile/user'
        user_installation_uri = $publicProfileUri
        profile_configuration = $profileConfigurationIdentity
        legacy_crash_configuration = $legacyCrashConfigurationIdentity
        profile_prelaunch_entry_count = $null
        profile_seed_artifacts = @($profileSeedArtifacts.ToArray())
        seeded_legacy_triggers = @($legacyTriggerNames)
        legacy_crash_seeded = [bool]$legacyCrashSeeded
        uno_pipe = $script:UnoPipe
        uno_accept_argument = $acceptArgument
        pid_file = $publicPidPath
        document_fixtures = @()
    }
    driver = [ordered]@{
        repository = $driverIdentity.repository
        commit = $driverCommit
        checkout_clean = $true
        checkout_dirty = $false
        package_name = $driverPackageName
        package_version = $driverPackageVersion
        mcp_url = $null
        transport = 'streamable HTTP over dedicated loopback endpoint'
        dedicated_server = $false
        server_pid = $null
        listener_process = $null
        desktop_name = $desktopName
        session = [ordered]@{
            mode = 'dedicated same-token server process'
            harness_pid = $PID
            harness_windows_session_id = $harnessWindowsSessionId
            server_windows_session_id = $null
            same_windows_session = $null
            token_inheritance = 'Start-Process inherited the harness token'
            integrity = $integrityEvidence
            integrity_verification_method = 'Harness mandatory label measured with whoami; dedicated server label inferred from Start-Process token inheritance, same Windows session, and MCP is_admin parity; server mandatory label is not read directly.'
            server_mandatory_label_measured_directly = $false
            server_reported_is_administrator = $null
            integrity_match = $null
        }
    }
    process = $null
    window = $null
    window_handoff_diagnostics = @()
    no_nag_contract = [ordered]@{
        enabled = ($StartupProfile -ne 'Configured')
        observation_seconds = if ($StartupProfile -ne 'Configured') {
            $ObservationSeconds
        }
        else { 0 }
        poll_interval_milliseconds = 500
        observation_started_at_utc = $null
        observation_completed_at_utc = $null
        observation_elapsed_milliseconds = $null
        startup_poll_count = 0
        observation_poll_count = 0
        window_poll_log = $null
        former_nag_denylist = @($script:NoNagDeniedText)
        denied_text_matches = @()
        retained_safety_prompts = @($script:RetainedSafetyPromptText)
        retained_manual_actions = @(
            '.uno:TipOfTheDay',
            '.uno:WhatsNew',
            '.uno:OptionsTreeDialog / OptionsPageID 17100'
        )
        automatic_file_association_runtime_covered = $false
        extracted_msi_association_limitation = 'An administratively extracted MSI payload is not registered under HKLM. The historical automatic association check returns before prompting unless the product is installed, so this run does not runtime-prove that registry-gated path. Use an MSI-installed disposable Windows Sandbox or VM for that proof.'
    }
    scenarios = @()
    review = [ordered]@{
        status = 'pending'
        reviewer = $null
        sensitive_data_review = 'pending'
        reviewed_scenario_ids = @()
        limitations = $null
    }
    cleanup = [ordered]@{
        normal_uno_termination = $false
        forced_owned_process_cleanup = $false
        remaining_payload_processes = -1
        process_cleanup_error = $null
        headless_windows_before_close = $null
        desktop_closed = $false
        desktop_cleanup_error = $null
        dedicated_driver_stopped = $null
        dedicated_driver_endpoint_closed = $null
        dedicated_listener_forced_cleanup = $false
        dedicated_driver_cleanup_error = $null
        runtime_launch_wrapper_removed = $false
        runtime_launch_wrapper_cleanup_error = $null
    }
    error = $null
}

$desktopCreated = $false
$dedicatedDriver = $null
$dedicatedListenerIdentity = $null
$driverPort = $null
$ownedPid = $null
$ownedProcessStartTimeUtcTicks = $null
$pidFilePid = $null
$pidFileResolutionError = $null
$windowHandoffDiagnostics = [System.Collections.Generic.List[string]]::new()
$script:WindowPollLog = [System.Collections.Generic.List[object]]::new()
$script:WindowPollLogPath = Join-Path $script:LogsRoot 'window-polls.json'
$script:WindowPollOwnedProcessId = $null
$script:ObservationStartedAtUtc = $null
$script:ObservationCompletedAtUtc = $null
$script:ObservationElapsedMilliseconds = $null
$normalTermination = $false
$fatal = $null
$script:WindowHandle = $null
$script:WindowTitle = $null
$script:WindowClass = $null
$script:WindowProcessId = $null
$script:WindowThreadId = $null
$script:WindowDpi = $null
try {
    if ($McpUrl) {
        throw 'External MCP URLs cannot provide accepted same-token server provenance; omit -McpUrl to use the dedicated server.'
    }
    else {
        $driverPort = Get-FreeLoopbackPort
        $script:McpUrl = "http://127.0.0.1:$driverPort/mcp"
        $driverStdout = Join-Path $script:LogsRoot 'lowlevel-mcp.stdout.log'
        $driverStderr = Join-Path $script:LogsRoot 'lowlevel-mcp.stderr.log'
        $uvPath = (Get-Command uv -ErrorAction Stop).Source
        $dedicatedDriver = Start-Process -FilePath $uvPath -ArgumentList @(
            'run',
            '--directory', $script:ResolvedDriverRoot,
            'lowlevel-computer-use-mcp',
            '--http',
            '--host', '127.0.0.1',
            '--port', [string]$driverPort
        ) -WindowStyle Hidden -RedirectStandardOutput $driverStdout `
            -RedirectStandardError $driverStderr -PassThru
        $results.driver.dedicated_server = $true
        $results.driver.server_pid = [int]$dedicatedDriver.Id
    }
    $results.driver.mcp_url = $script:McpUrl

    $serverDeadline = [DateTimeOffset]::UtcNow.AddSeconds(30)
    $serverReady = $false
    while ([DateTimeOffset]::UtcNow -lt $serverDeadline) {
        if ($dedicatedDriver -and $dedicatedDriver.HasExited) {
            throw "Dedicated low-level MCP server exited with code $($dedicatedDriver.ExitCode)."
        }
        try {
            Invoke-LowLevelTool -Tool 'get_screen_size' -Arguments @{} `
                -TimeoutSeconds 5 | Out-Null
            $serverReady = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $serverReady) {
        throw "Low-level MCP server did not become ready at $($script:McpUrl)."
    }
    $dedicatedDriver.Refresh()
    $dedicatedListenerIdentity = Get-ValidatedLoopbackListenerIdentity `
        -Port $driverPort -RootProcess $dedicatedDriver
    $results.driver.listener_process = [ordered]@{
        pid = [int]$dedicatedListenerIdentity.process_id
        parent_pid = [int]$dedicatedListenerIdentity.parent_process_id
        creation_ticks = [long]$dedicatedListenerIdentity.creation_ticks
        creation_date = [string]$dedicatedListenerIdentity.creation_date
        local_address = '127.0.0.1'
        local_port = [int]$driverPort
        ancestry_validated_to_server_pid = $true
    }
    $serverProcess = Get-Process -Id $dedicatedDriver.Id -ErrorAction Stop
    $serverAdmin = Invoke-LowLevelTool -Tool 'is_admin' -Arguments @{} `
        -TimeoutSeconds 15
    $results.driver.session.server_windows_session_id = [int]$serverProcess.SessionId
    $results.driver.session.same_windows_session = (
        [int]$serverProcess.SessionId -eq
        [int]$results.driver.session.harness_windows_session_id
    )
    $results.driver.session.server_reported_is_administrator = [bool]$serverAdmin.is_admin
    $results.driver.session.integrity_match = (
        $results.driver.session.same_windows_session -and
        ([bool]$serverAdmin.is_admin -eq [bool]$integrityEvidence.is_administrator)
    )
    if (-not $results.driver.session.integrity_match) {
        throw 'Dedicated low-level MCP server did not match the harness Windows session/integrity contract.'
    }

    Invoke-LowLevelTool -Tool 'create_headless_desktop' -Arguments @{ name = $desktopName } | Out-Null
    $desktopCreated = $true
    $prelaunchProfileEntries = @(Get-ChildItem -LiteralPath $profileRoot -Force)
    $results.application.profile_prelaunch_entry_count = $prelaunchProfileEntries.Count
    if ($StartupProfile -eq 'Fresh' -and $prelaunchProfileEntries.Count -ne 0) {
        throw 'Fresh no-nag profile was not empty immediately before launch.'
    }
    if ($StartupProfile -eq 'Legacy') {
        if ($prelaunchProfileEntries.Count -ne 2 -or
            -not (Test-Path -LiteralPath $profileConfigPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $crashConfigPath -PathType Leaf)) {
            throw 'Legacy no-nag profile changed after its fixed user/crash seeds were prepared.'
        }
        if ((Get-Sha256Hex -Path $profileConfigPath) -cne
            [string]$profileConfigurationIdentity.sha256) {
            throw 'Legacy no-nag registry seed changed before launch.'
        }
        if ((Get-Sha256Hex -Path $crashConfigPath) -cne
            [string]$legacyCrashConfigurationIdentity.sha256) {
            throw 'Legacy no-nag crash seed changed before launch.'
        }
    }
    $launchCommand = 'cmd.exe /d /v:off /c call "{0}"' -f $wrapperPath
    $launcher = Invoke-LowLevelTool -Tool 'launch_on_headless_desktop' -Arguments @{
        name = $desktopName
        command = $launchCommand
    }

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(90)
    $stableHandle = $null
    $stableProcessId = $null
    $stableThreadId = $null
    $stableDpi = $null
    $stableWidth = $null
    $stableHeight = $null
    $stableTitle = $null
    $stableCount = 0
    $lastWindows = $null
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $pidPath -PathType Leaf) {
            $pidText = (Get-Content -LiteralPath $pidPath -Raw).Trim()
            if ($pidText -match '^\d+$') {
                $observedPidFilePid = [int]$pidText
                if ($pidFilePid -and $observedPidFilePid -ne [int]$pidFilePid) {
                    throw "LibreOffice PID file changed from $pidFilePid to $observedPidFilePid."
                }
                if (-not $pidFilePid) {
                    $pidFilePid = $observedPidFilePid
                }
            }
            elseif ($pidText) {
                $pidFileResolutionError = "PID file contains non-numeric text '$pidText'."
            }
        }

        # The pidfile PID is the sole ownership authority.  Never latch an
        # arbitrary exact-payload process observed during the launcher handoff.
        if ($pidFilePid) {
            if (-not (Get-Process -Id $pidFilePid -ErrorAction SilentlyContinue)) {
                throw "PID-file process $pidFilePid is no longer running before window ownership was established."
            }

            $pidFileOwnedProcess = $null
            try {
                $pidFileOwnedProcess = Get-OwnedProcess -ProcessId $pidFilePid `
                    -ProgramRoot $programRoot
            }
            catch [System.ArgumentException] {
                if (-not (Get-Process -Id $pidFilePid -ErrorAction SilentlyContinue)) {
                    throw "PID-file process $pidFilePid exited while its executable path was resolved."
                }
                $pidFileResolutionError = $_.Exception.Message
            }
            catch [System.InvalidOperationException] {
                if (-not (Get-Process -Id $pidFilePid -ErrorAction SilentlyContinue)) {
                    throw "PID-file process $pidFilePid exited while its executable path was resolved."
                }
                $pidFileResolutionError = $_.Exception.Message
            }
            catch [System.ComponentModel.Win32Exception] {
                if (-not (Get-Process -Id $pidFilePid -ErrorAction SilentlyContinue)) {
                    throw "PID-file process $pidFilePid exited while its executable path was resolved."
                }
                $pidFileResolutionError = $_.Exception.Message
            }
            catch {
                if (-not (Get-Process -Id $pidFilePid -ErrorAction SilentlyContinue)) {
                    throw "PID-file process $pidFilePid exited while its executable path was resolved."
                }
                throw
            }

            if ($pidFileOwnedProcess) {
                $pidFileExecutableName = [System.IO.Path]::GetFileName(
                    [string]$pidFileOwnedProcess.ExecutablePath
                )
                if ($pidFileExecutableName -ine 'soffice.bin') {
                    throw "PID-file process $pidFilePid resolved to '$($pidFileOwnedProcess.ExecutablePath)', not the required soffice.bin GUI runtime."
                }

                $currentStartTimeUtcTicks = (
                    [DateTime]$pidFileOwnedProcess.CreationDate
                ).ToUniversalTime().Ticks
                if (-not $ownedPid) {
                    $ownedPid = [int]$pidFileOwnedProcess.ProcessId
                    $ownedProcessStartTimeUtcTicks = $currentStartTimeUtcTicks
                    $pidFileResolutionError = $null
                    $results.process = [ordered]@{
                        pid = $ownedPid
                        pidfile_pid = [int]$pidFilePid
                        launcher_pid = [int]$launcher.pid
                        name = [string]$pidFileOwnedProcess.Name
                        executable_path = 'program/' + $pidFileExecutableName
                        creation_date = [string]$pidFileOwnedProcess.CreationDate
                    }
                }
                elseif ([int]$pidFileOwnedProcess.ProcessId -ne [int]$ownedPid -or
                    $currentStartTimeUtcTicks -ne [long]$ownedProcessStartTimeUtcTicks) {
                    throw "PID-file process identity changed after ownership was established for PID $ownedPid."
                }
            }
        }
        $lastWindows = Invoke-LowLevelTool -Tool 'list_headless_windows' -Arguments @{
            name = $desktopName
        } -TimeoutSeconds 15
        if ($StartupProfile -ne 'Configured') {
            $startupPoll = Record-WindowEnumeration -Enumeration $lastWindows `
                -Phase 'startup' -OwnedProcessId $ownedPid
            $results.no_nag_contract.startup_poll_count = `
                [int]$results.no_nag_contract.startup_poll_count + 1
            Assert-NoNagWindowEnumeration -Entry $startupPoll `
                -ExpectedHandle 0 -ExpectedProcessId $(if ($ownedPid) { $ownedPid } else { 0 })
        }

        # Window ownership, thread identity, and DPI are sampled by the driver
        # inside the same EnumDesktopWindows callback that produced the HWND.
        # A local process cannot safely query an HWND on the off-screen desktop.
        $candidate = $null
        foreach ($observedWindow in @($lastWindows.windows)) {
            $classProperty = $observedWindow.PSObject.Properties['class']
            $titleProperty = $observedWindow.PSObject.Properties['title']
            $candidateWidth = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'width'
            $candidateHeight = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'height'
            if ($null -eq $classProperty -or $null -eq $titleProperty -or
                [string]$classProperty.Value -cne 'SALFRAME' -or
                [string]::IsNullOrWhiteSpace([string]$titleProperty.Value) -or
                [string]$titleProperty.Value -notmatch 'LibreOffice' -or
                $null -eq $candidateWidth -or $candidateWidth -lt 640 -or
                $null -eq $candidateHeight -or $candidateHeight -lt 480) {
                continue
            }

            $candidateHandle = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'handle'
            $candidateProcessId = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'process_id'
            $candidateThreadId = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'thread_id'
            $candidateDpi = Get-JsonIntegerProperty -Object $observedWindow `
                -PropertyName 'dpi'
            $handleLabel = if ($null -eq $candidateHandle) {
                '<invalid>'
            }
            else {
                [string]$candidateHandle
            }

            if ($null -eq $candidateHandle -or $candidateHandle -le 0) {
                $diagnostic = 'Rejected SALFRAME candidate: list_headless_windows handle is missing, non-integer, or zero.'
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }
            if ($null -eq $candidateProcessId -or $candidateProcessId -le 0) {
                $diagnostic = "Rejected SALFRAME HWND ${handleLabel}: list_headless_windows process_id is missing, non-integer, or zero."
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }
            if ($null -eq $candidateThreadId -or $candidateThreadId -le 0) {
                $diagnostic = "Rejected SALFRAME HWND ${handleLabel}: list_headless_windows thread_id is missing, non-integer, or zero."
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }
            if ($null -eq $candidateDpi -or $candidateDpi -le 0) {
                $diagnostic = "Rejected SALFRAME HWND ${handleLabel}: list_headless_windows dpi is missing, non-integer, or zero."
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }
            if (-not $ownedPid) {
                continue
            }
            if ($candidateProcessId -ne [long]$ownedPid) {
                $diagnostic = "Rejected SALFRAME HWND ${handleLabel}: list_headless_windows process_id $candidateProcessId does not match pidfile-owned PID $ownedPid."
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }
            if ($StartupProfile -ne 'Configured' -and
                [string]$titleProperty.Value -notmatch 'Writer') {
                $diagnostic = "Rejected SALFRAME HWND ${handleLabel}: blank-Writer no-nag startup has not reached its Writer title."
                if (-not $windowHandoffDiagnostics.Contains($diagnostic)) {
                    $windowHandoffDiagnostics.Add($diagnostic)
                }
                continue
            }

            $candidate = [pscustomobject][ordered]@{
                handle = [long]$candidateHandle
                process_id = [long]$candidateProcessId
                thread_id = [long]$candidateThreadId
                title = [string]$titleProperty.Value
                class = [string]$classProperty.Value
                width = [long]$candidateWidth
                height = [long]$candidateHeight
                dpi = [long]$candidateDpi
            }
            break
        }
        $results.window_handoff_diagnostics = @($windowHandoffDiagnostics.ToArray())

        if ($candidate) {
            if ($stableHandle -eq [long]$candidate.handle -and
                $stableProcessId -eq [long]$candidate.process_id -and
                $stableThreadId -eq [long]$candidate.thread_id -and
                $stableDpi -eq [long]$candidate.dpi -and
                $stableWidth -eq [long]$candidate.width -and
                $stableHeight -eq [long]$candidate.height -and
                $stableTitle -ceq [string]$candidate.title) {
                $stableCount++
            }
            else {
                $stableHandle = [long]$candidate.handle
                $stableProcessId = [long]$candidate.process_id
                $stableThreadId = [long]$candidate.thread_id
                $stableDpi = [long]$candidate.dpi
                $stableWidth = [long]$candidate.width
                $stableHeight = [long]$candidate.height
                $stableTitle = [string]$candidate.title
                $stableCount = 1
            }
        }
        else {
            $stableHandle = $null
            $stableProcessId = $null
            $stableCount = 0
        }
        if ($ownedPid -and $pidFilePid -and $stableCount -ge 3) {
            $script:WindowHandle = [long]$candidate.handle
            $script:WindowProcessId = [int]$candidate.process_id
            $script:WindowThreadId = [long]$candidate.thread_id
            $script:WindowDpi = [int]$candidate.dpi
            $results.host.display_scale.dpi = $script:WindowDpi
            $results.host.display_scale.percent = [int][Math]::Round(
                ($script:WindowDpi * 100.0) / 96.0
            )
            $results.process.pidfile_pid = [int]$pidFilePid
            $script:WindowTitle = [string]$candidate.title
            $script:WindowClass = [string]$candidate.class
            $results.window = [ordered]@{
                handle = [long]$candidate.handle
                process_id = [int]$candidate.process_id
                thread_id = [long]$candidate.thread_id
                title = [string]$candidate.title
                class = [string]$candidate.class
                width = [int]$candidate.width
                height = [int]$candidate.height
                dpi = [int]$candidate.dpi
                stable_poll_count = $stableCount
            }
            break
        }
        Start-Sleep -Milliseconds 750
    }
    if (-not $ownedPid -or -not $script:WindowHandle) {
        $pidFileDetail = if ($pidFileResolutionError) {
            " Last PID-file resolution error: $pidFileResolutionError"
        }
        elseif (-not $pidFilePid) {
            ' No numeric LibreOffice PID file was observed.'
        }
        else {
            ''
        }
        throw "LibreOffice did not expose a stable PID-file-owned window in 90 seconds.$pidFileDetail Last windows: $($lastWindows | ConvertTo-Json -Compress -Depth 8)"
    }

    $scenarioList = [System.Collections.Generic.List[object]]::new()
    if ($StartupProfile -ne 'Configured') {
        if ([string]$script:WindowTitle -notmatch 'Writer') {
            throw "No-nag startup resolved '$($script:WindowTitle)', not a blank Writer window."
        }
        Sync-WindowPollOwnership -OwnedProcessId $ownedPid
        foreach ($startupEntry in @($script:WindowPollLog.ToArray())) {
            Assert-NoNagWindowEnumeration -Entry $startupEntry `
                -ExpectedHandle $script:WindowHandle -ExpectedProcessId $ownedPid
        }

        $script:ObservationStartedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
        $observationStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        do {
            $observationWindows = Invoke-LowLevelTool -Tool 'list_headless_windows' `
                -Arguments @{ name = $desktopName } -TimeoutSeconds 15
            $observationEntry = Record-WindowEnumeration `
                -Enumeration $observationWindows -Phase 'no-nag-observation' `
                -OwnedProcessId $ownedPid
            Assert-NoNagWindowEnumeration -Entry $observationEntry `
                -ExpectedHandle $script:WindowHandle -ExpectedProcessId $ownedPid `
                -ExpectedThreadId $script:WindowThreadId -ExpectedDpi $script:WindowDpi `
                -ExpectedWidth $results.window.width `
                -ExpectedHeight $results.window.height `
                -ExpectedTitle $script:WindowTitle `
                -RequireSingleWriter
            $results.no_nag_contract.observation_poll_count = `
                [int]$results.no_nag_contract.observation_poll_count + 1
            Start-Sleep -Milliseconds 500
        } while ($observationStopwatch.Elapsed.TotalSeconds -lt $ObservationSeconds)
        $observationStopwatch.Stop()
        $script:ObservationCompletedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
        $script:ObservationElapsedMilliseconds = [long]$observationStopwatch.ElapsedMilliseconds
        if ($script:ObservationElapsedMilliseconds -lt ($ObservationSeconds * 1000)) {
            throw 'No-nag observation ended before its monotonic minimum duration.'
        }
        $results.no_nag_contract.observation_started_at_utc = `
            $script:ObservationStartedAtUtc
        $results.no_nag_contract.observation_completed_at_utc = `
            $script:ObservationCompletedAtUtc
        $results.no_nag_contract.observation_elapsed_milliseconds = `
            $script:ObservationElapsedMilliseconds
        Sync-WindowPollOwnership -OwnedProcessId $ownedPid

        $profileUpper = $StartupProfile.ToUpperInvariant()
        $scenarioList.Add((Capture-State `
            -Slug "writer-$startupProfileSlug-startup-no-nags" `
            -ScenarioId "E-NONAG-$profileUpper" `
            -ScenarioName "$StartupProfile profile blank Writer startup without unsolicited UI" `
            -InventoryIds @('WIN-SYS-008', 'WIN-SYS-010', 'WIN-WR-001', 'WIN-FBK-006') `
            -ExpectedCheckpoints @(
                'blank Writer launched without suppressive UI flags',
                'exactly one PID/HWND-owned Writer SALFRAME throughout the observation',
                'former nag text absent from every owned title and the complete UNO tree',
                'retained recovery, security, compatibility, credential, and read-only prompts were not denied'
            ) -InputDescription 'none; disposable profile startup observation'))
    }
    else {
        $appearanceUpper = $Appearance.ToUpperInvariant()
        $scenarioList.Add((Capture-State -Slug "start-center-$appearanceSlug" `
            -ScenarioId "E-START-$appearanceUpper" `
            -ScenarioName "$Appearance Start Center Home and Recent Documents" `
            -InventoryIds @('WIN-SC-001', 'WIN-SHL-001') `
            -ExpectedCheckpoints @(
                'stable owned LibreOffice SALFRAME window',
                'rendered nonblank screenshot with exact dimensions and SHA-256',
                'nonempty complete UNO accessibility tree with visible nodes'
            ) -InputDescription 'none; initial stable Start Center state'))

        if ($KeyboardFocus) {
            Invoke-LowLevelTool -Tool 'win_send_keys' -Arguments @{
                hwnd = [long]$script:WindowHandle
                keys = @('tab')
            } | Out-Null
            Start-Sleep -Milliseconds 750
            $scenarioList.Add((Capture-State `
                -Slug "start-center-$appearanceSlug-keyboard-focus" `
                -ScenarioId "E-START-$appearanceUpper-KEYBOARD" `
                -ScenarioName 'Background Tab navigation exposes keyboard focus' `
                -InventoryIds @('WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006') `
                -ExpectedCheckpoints @(
                    'background Tab input delivered to the owned window',
                    'at least one FOCUSED UNO accessibility node',
                    'rendered nonblank screenshot retained for visual review'
                ) -InputDescription 'low-level MCP win_send_keys: tab' -RequireFocused))
        }

        if ($Templates) {
            Invoke-LowLevelTool -Tool 'mouse_click' -Arguments @{
                hwnd = [long]$script:WindowHandle
                x = 140
                y = 330
                button = 'left'
                clicks = 1
            } | Out-Null
            Start-Sleep -Seconds 2
            $scenarioList.Add((Capture-State `
                -Slug "start-center-templates-$appearanceSlug" `
                -ScenarioId "E-START-$appearanceUpper-TEMPLATES" `
                -ScenarioName 'Background pointer navigation to Templates' `
                -InventoryIds @('WIN-SC-003', 'WIN-SC-005') `
                -ExpectedCheckpoints @(
                    'background pointer click delivered at recorded client coordinates',
                    'rendered nonblank post-input screenshot retained for visual review',
                    'nonempty complete post-input UNO accessibility tree with visible nodes'
                ) -InputDescription 'low-level MCP mouse_click at client coordinates (140, 330)'))
        }
    }

    $finalScenario = $scenarioList[$scenarioList.Count - 1]
    $finalSlug = [string]$finalScenario.slug
    $terminatedScenario = Capture-State -Slug $finalSlug `
        -ScenarioId ([string]$finalScenario.id) `
        -ScenarioName ([string]$finalScenario.name) `
        -InventoryIds @($finalScenario.inventory_ids) `
        -ExpectedCheckpoints @($finalScenario.expected_checkpoints) `
        -InputDescription ([string]$finalScenario.input) -Terminate `
        -RequireFocused:($KeyboardFocus -and -not $Templates)
    $scenarioList[$scenarioList.Count - 1] = $terminatedScenario
    $results.scenarios = $scenarioList.ToArray()
    $normalTermination = $true
    $results.cleanup.normal_uno_termination = $true

    $exitDeadline = [DateTimeOffset]::UtcNow.AddSeconds(30)
    while ([DateTimeOffset]::UtcNow -lt $exitDeadline) {
        $remaining = @(Get-ExactPayloadProcesses -ProgramRoot $programRoot)
        $windowsAfter = Invoke-LowLevelTool -Tool 'list_headless_windows' -Arguments @{
            name = $desktopName
        } -TimeoutSeconds 15
        if ($remaining.Count -eq 0 -and [int]$windowsAfter.count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
    $remaining = @(Get-ExactPayloadProcesses -ProgramRoot $programRoot)
    $windowsAfter = Invoke-LowLevelTool -Tool 'list_headless_windows' -Arguments @{
        name = $desktopName
    } -TimeoutSeconds 15
    if ($remaining.Count -ne 0 -or [int]$windowsAfter.count -ne 0) {
        throw 'LibreOffice did not fully exit after normal UNO termination.'
    }
    $results.status = 'passed'
}
catch {
    $fatal = $_.Exception
    $results.status = 'failed'
    $results.error = "{0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message
}
finally {
    try {
        $processCleanup = Stop-ExactPayloadProcesses -ProgramRoot $programRoot
        $results.cleanup.forced_owned_process_cleanup = [bool]$processCleanup.forced
        $results.cleanup.remaining_payload_processes = [int]$processCleanup.remaining
        if ($results.status -eq 'passed' -and $processCleanup.forced) {
            throw 'A passed run required forced payload-process cleanup.'
        }
    }
    catch {
        $results.cleanup.process_cleanup_error = $_.Exception.Message
        if (-not $fatal) { $fatal = $_.Exception }
        $results.status = 'failed'
        if (-not $results.error) {
            $results.error = "Cleanup process error: $($_.Exception.Message)"
        }
    }
    finally {
        try {
            $remaining = @(Get-ExactPayloadProcesses -ProgramRoot $programRoot)
            $results.cleanup.remaining_payload_processes = [int]$remaining.Count
        }
        catch {
            $results.cleanup.remaining_payload_processes = -1
            if (-not $results.cleanup.process_cleanup_error) {
                $results.cleanup.process_cleanup_error = $_.Exception.Message
            }
            if (-not $fatal) { $fatal = $_.Exception }
            $results.status = 'failed'
            if (-not $results.error) {
                $results.error = "Cleanup process verification error: $($_.Exception.Message)"
            }
        }
    }

    if ($desktopCreated) {
        try {
            $windowsFinal = Invoke-LowLevelTool -Tool 'list_headless_windows' -Arguments @{
                name = $desktopName
            } -TimeoutSeconds 15
            $results.cleanup.headless_windows_before_close = [int]$windowsFinal.count
            $closed = Invoke-LowLevelTool -Tool 'close_headless_desktop' -Arguments @{
                name = $desktopName
            } -TimeoutSeconds 15
            $results.cleanup.desktop_closed = [bool]$closed.closed
            if (-not $closed.closed) {
                throw 'The long-lived low-level MCP server did not close its desktop handle.'
            }
            if ([int]$windowsFinal.count -ne 0) {
                throw 'Headless windows remained immediately before desktop close.'
            }
        }
        catch {
            $results.cleanup.desktop_cleanup_error = $_.Exception.Message
            if (-not $fatal) { $fatal = $_.Exception }
            $results.status = 'failed'
            if (-not $results.error) {
                $results.error = "Desktop cleanup error: $($_.Exception.Message)"
            }
        }
    }
    if ($dedicatedDriver) {
        try {
            $driverCleanupFailures = [System.Collections.Generic.List[string]]::new()
            try {
                if (-not $dedicatedDriver.HasExited) {
                    Stop-ControlledProcessTree -RootProcess $dedicatedDriver `
                        -Description 'dedicated low-level MCP driver' `
                        -TimeoutMilliseconds 15000
                }
            }
            catch {
                $driverCleanupFailures.Add("root tree: $($_.Exception.Message)")
            }
            try {
                if ($null -ne $dedicatedListenerIdentity) {
                    $results.cleanup.dedicated_listener_forced_cleanup = `
                        [bool](Stop-RecordedProcessIdentity `
                            -Identity $dedicatedListenerIdentity `
                            -TimeoutMilliseconds 15000)
                }
            }
            catch {
                $driverCleanupFailures.Add("listener identity: $($_.Exception.Message)")
            }
            try {
                $remainingListeners = @(Get-NetTCPConnection -State Listen `
                    -LocalPort $driverPort -ErrorAction SilentlyContinue |
                    Where-Object { $_.LocalAddress -eq '127.0.0.1' })
                $results.cleanup.dedicated_driver_endpoint_closed = `
                    ($remainingListeners.Count -eq 0)
                if (-not $results.cleanup.dedicated_driver_endpoint_closed) {
                    throw "Dedicated loopback port $driverPort is still listening."
                }
            }
            catch {
                $driverCleanupFailures.Add("endpoint: $($_.Exception.Message)")
            }
            $dedicatedDriver.Refresh()
            $results.cleanup.dedicated_driver_stopped = (
                $dedicatedDriver.HasExited -and
                [bool]$results.cleanup.dedicated_driver_endpoint_closed
            )
            if (-not $results.cleanup.dedicated_driver_stopped) {
                $driverCleanupFailures.Add('dedicated root/listener cleanup remained incomplete')
            }
            if ($driverCleanupFailures.Count -ne 0) {
                throw ($driverCleanupFailures -join '; ')
            }
        }
        catch {
            $results.cleanup.dedicated_driver_cleanup_error = $_.Exception.Message
            if (-not $fatal) { $fatal = $_.Exception }
            $results.status = 'failed'
            if (-not $results.error) {
                $results.error = "Dedicated driver cleanup error: $($_.Exception.Message)"
            }
        }
        finally {
            $dedicatedDriver.Dispose()
        }
    }
    try {
        if (Test-Path -LiteralPath $wrapperPath -PathType Leaf) {
            Remove-Item -LiteralPath $wrapperPath -Force -ErrorAction Stop
        }
        $results.cleanup.runtime_launch_wrapper_removed = `
            -not (Test-Path -LiteralPath $wrapperPath)
        if (-not $results.cleanup.runtime_launch_wrapper_removed) {
            throw 'Runtime-only launch wrapper remains after cleanup.'
        }
    }
    catch {
        $results.cleanup.runtime_launch_wrapper_cleanup_error = $_.Exception.Message
        if (-not $fatal) { $fatal = $_.Exception }
        $results.status = 'failed'
        if (-not $results.error) {
            $results.error = "Launch-wrapper cleanup error: $($_.Exception.Message)"
        }
    }
    if ($StartupProfile -ne 'Configured') {
        try {
            if ($ownedPid -and $script:WindowPollLog.Count -gt 0) {
                Sync-WindowPollOwnership -OwnedProcessId $ownedPid
            }
            if (Test-Path -LiteralPath $script:WindowPollLogPath -PathType Leaf) {
                $results.no_nag_contract.window_poll_log = Get-EvidenceFileIdentity `
                    -Path $script:WindowPollLogPath -PublicPath 'logs/window-polls.json'
            }
            $results.no_nag_contract.denied_text_matches = `
                @($script:NoNagDeniedMatches.ToArray())
        }
        catch {
            if (-not $fatal) { $fatal = $_.Exception }
            $results.status = 'failed'
            if (-not $results.error) {
                $results.error = "No-nag poll-log finalization error: $($_.Exception.Message)"
            }
        }
    }
    $results.completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $resultsPath = Join-Path $runRoot 'results.json'
    $manifestPath = Join-Path $runRoot 'manifest.json'
    Write-JsonFile -Path $resultsPath -Value $results
    Write-JsonFile -Path $manifestPath -Value $results
    if ($results.status -eq 'passed') {
        try {
            & $evidenceValidatorPath -Path $manifestPath -RequirePassed | Out-Null
        }
        catch {
            $results.status = 'failed'
            $results.error = "Evidence contract validation failed: $($_.Exception.Message)"
            if (-not $fatal) { $fatal = $_.Exception }
            Write-JsonFile -Path $resultsPath -Value $results
            Write-JsonFile -Path $manifestPath -Value $results
        }
    }
}

if ($fatal) {
    throw "Headless smoke failed; evidence retained at '$runRoot': $($fatal.Message)"
}
$results | ConvertTo-Json -Depth 20
