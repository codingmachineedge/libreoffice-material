[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$validator = Join-Path $repoRoot 'bin\Validate-Windows-Headless-Evidence.ps1'
$runner = Join-Path $repoRoot 'bin\Run-Windows-Headless-Smoke.ps1'
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) `
    ('LibreOfficeMaterialEvidenceContract-' + [guid]::NewGuid().ToString('N'))
$candidatePath = Join-Path $temporaryRoot 'manifest.json'
$screenshotRoot = Join-Path $temporaryRoot 'screenshots'
$logsRoot = Join-Path $temporaryRoot 'logs'
$screenshotPath = Join-Path $screenshotRoot 'focus.png'
$a11yPath = Join-Path $logsRoot 'a11y-focus.json'
$knownAnswerPath = Join-Path $temporaryRoot 'sha256-known-answer.bin'

function Write-Candidate {
    param([Parameter(Mandatory = $true)] [object]$Candidate)
    $Candidate | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $candidatePath -Encoding utf8
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

function Assert-Rejected {
    param(
        [Parameter(Mandatory = $true)] [object]$Candidate,
        [Parameter(Mandatory = $true)] [string]$ExpectedText,
        [switch]$RequireAccepted
    )
    Write-Candidate $Candidate
    try {
        if ($RequireAccepted) {
            & $validator -Path $candidatePath -RequireAccepted | Out-Null
        }
        else {
            & $validator -Path $candidatePath -RequirePassed | Out-Null
        }
    }
    catch {
        if ($_.Exception.Message -notlike "*$ExpectedText*") { throw }
        return
    }
    throw "Validator unexpectedly accepted an invalid candidate: $ExpectedText"
}

function Write-A11yFixture {
    param(
        [Parameter(Mandatory = $true)] [object]$Report,
        [Parameter(Mandatory = $true)] [object]$Candidate
    )

    [System.IO.File]::WriteAllText(
        $a11yPath,
        (($Report | ConvertTo-Json -Depth 10) + "`n"),
        [System.Text.UTF8Encoding]::new($false)
    )
    $item = Get-Item -LiteralPath $a11yPath
    $Candidate.scenarios[0].accessibility.bytes = [long]$item.Length
    $Candidate.scenarios[0].accessibility.sha256 = Get-Sha256Hex -Path $a11yPath
}

New-Item -ItemType Directory -Path $temporaryRoot, $screenshotRoot, $logsRoot `
    -ErrorAction Stop | Out-Null
try {
    [System.IO.File]::WriteAllBytes(
        $knownAnswerPath,
        [System.Text.Encoding]::ASCII.GetBytes('abc')
    )
    $knownAnswer = Get-Sha256Hex -Path $knownAnswerPath
    if ($knownAnswer -ne `
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad') {
        throw "Direct .NET SHA-256 known-answer test failed: $knownAnswer"
    }

    $hash = 'a' * 64
    $commit = 'b' * 40
    # The contract reads only the PNG signature and IHDR dimensions; no image
    # library is needed for this synthetic 1920x1080 header fixture.
    [System.IO.File]::WriteAllBytes($screenshotPath, [byte[]](
        137, 80, 78, 71, 13, 10, 26, 10,
        0, 0, 0, 13, 73, 72, 68, 82,
        0, 0, 7, 128, 0, 0, 4, 56
    ))
    $screenshotItem = Get-Item -LiteralPath $screenshotPath
    $screenshotHash = Get-Sha256Hex -Path $screenshotPath
    $a11yReport = [ordered]@{
        run_id = '20990101-000000-bbbbbbbbbb-windows-headless-light'
        screenshot_sha256 = $screenshotHash
        summary = [ordered]@{
            node_count = 2
            visible_nodes = 2
            errors = 0
            partial = $false
        }
        nodes = @(
            @{ states = @('SHOWING', 'VISIBLE') },
            @{ states = @('SHOWING', 'VISIBLE', 'FOCUSED') }
        )
    }
    $candidate = [ordered]@{
        schema_version = 2
        run_id = '20990101-000000-bbbbbbbbbb-windows-headless-light'
        status = 'passed'
        source_commit = $commit
        source = [ordered]@{
            repository = 'https://github.com/example/libreoffice-material.git'
            commit = $commit
            upstream_baseline = ('c' * 40)
            checkout_clean = $true
            checkout_dirty = $false
            embedded_build_id = $commit
            version_metadata = @{ path = 'program/version.ini'; sha256 = $hash }
        }
        harness = [ordered]@{
            repository = 'https://github.com/example/libreoffice-material.git'
            commit = ('d' * 40)
            checkout_clean = $true
            checkout_dirty = $false
            entrypoint = @{
                path = 'bin/Run-Windows-Headless-Smoke.ps1'
                sha256 = $hash
            }
            dependencies = @(
                @{ path = 'bin/call-lowlevel-mcp.py'; sha256 = $hash },
                @{ path = 'bin/analyze-png.py'; sha256 = $hash },
                @{ path = 'bin/dump-a11y.py'; sha256 = $hash },
                @{ path = 'bin/Validate-Windows-Headless-Evidence.ps1'; sha256 = $hash }
            )
        }
        host = [ordered]@{
            display_scale = @{
                dpi = 144
                percent = 150
                source = 'GetDpiForWindow in the low-level list_headless_windows enumeration callback'
            }
            font_configuration = @{
                source = 'native Windows system fonts'
                run_specific_override = $false
                override_files = @()
            }
        }
        application = [ordered]@{
            executable = @{ path = 'program/soffice.exe'; sha256 = $hash }
            runtime_executable = @{ path = 'program/soffice.bin'; sha256 = $hash }
            updater_library = @{ path = 'program/updchklo.dll'; sha256 = $hash }
            material_theme_definition = @{
                path = 'share/theme_definitions/material/definition.xml'
                sha256 = $hash
            }
            arguments = @(
                '-env:UserInstallation=<run-root-uri>/profile',
                '--nologo', '--norestore', '--quickstart=no', '--language=en-US',
                '--pidfile=<run-root>/soffice.pid',
                '--accept=pipe,name=LibreOfficeMaterialQA-contract;urp'
            )
            arguments_path_tokenized = $true
            launch_wrapper = @{ retained_in_public_evidence = $false }
            isolated_profile_root = 'profile'
            user_profile_root = 'profile/user'
            user_installation_uri = '<run-root-uri>/profile'
            profile_configuration = @{
                path = 'profile/user/registrymodifications.xcu'
                sha256 = $hash
                retained_in_public_evidence = $false
            }
            uno_pipe = 'LibreOfficeMaterialQA-contract'
            pid_file = '<run-root>/soffice.pid'
        }
        environment = [ordered]@{
            VCL_DRAW_WIDGETS_FROM_FILE = '1'
            VCL_FILE_WIDGET_THEME = 'material'
        }
        driver = [ordered]@{
            repository = 'https://github.com/example/lowlevel-computer-use-mcp.git'
            commit = ('e' * 40)
            checkout_clean = $true
            checkout_dirty = $false
            package_name = 'lowlevel-computer-use-mcp'
            package_version = '0.1.0'
            mcp_url = 'http://127.0.0.1:54321/mcp'
            server_pid = 1234
            dedicated_server = $true
            session = [ordered]@{
                harness_windows_session_id = 1
                server_windows_session_id = 1
                same_windows_session = $true
                integrity_match = $true
                integrity_verification_method = 'synthetic same-token inheritance proof'
                server_mandatory_label_measured_directly = $false
                server_reported_is_administrator = $true
                integrity = @{
                    mandatory_label_sid = 'S-1-16-12288'
                    is_administrator = $true
                }
            }
        }
        process = [ordered]@{
            pid = 2222
            pidfile_pid = 2222
            launcher_pid = 1111
            name = 'soffice.bin'
            executable_path = 'program/soffice.bin'
        }
        window = [ordered]@{
            handle = 42
            process_id = 2222
            thread_id = 3333
            title = 'LibreOfficeDev'
            class = 'SALFRAME'
            width = 1920
            height = 1080
            dpi = 144
            stable_poll_count = 3
        }
        scenarios = @([ordered]@{
            id = 'E-START-LIGHT-KEYBOARD'
            inventory_ids = @('WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006')
            requires_focused_accessibility = $true
            automation_result = 'pass'
            result = 'pending_visual_review'
            expected_checkpoints = @('stable owned window', 'nonblank capture')
            checkpoint = @{
                captured_at_utc = '2099-01-01T00:00:00Z'
                window_handle = 42
                window_process_id = 2222
                window_thread_id = 3333
                window_title = 'LibreOfficeDev'
                window_class = 'SALFRAME'
                window_dpi = 144
                normal_uno_termination_requested = $true
            }
            screenshot = @{
                path = 'screenshots/focus.png'
                bytes = [long]$screenshotItem.Length
                sha256 = $screenshotHash
                nonblank = $true
                width = 1920
                height = 1080
            }
            accessibility = @{
                path = 'logs/a11y-focus.json'
                bytes = 0
                sha256 = $hash
                screenshot_sha256 = $screenshotHash
                summary = @{
                    node_count = 2
                    visible_nodes = 2
                    errors = 0
                    partial = $false
                    focused_node_count = 1
                }
            }
        })
        cleanup = [ordered]@{
            normal_uno_termination = $true
            forced_owned_process_cleanup = $false
            remaining_payload_processes = 0
            headless_windows_before_close = 0
            desktop_closed = $true
            dedicated_driver_stopped = $true
            runtime_launch_wrapper_removed = $true
            process_cleanup_error = $null
            desktop_cleanup_error = $null
            dedicated_driver_cleanup_error = $null
            runtime_launch_wrapper_cleanup_error = $null
        }
        review = [ordered]@{
            status = 'pending'
            reviewer = $null
            sensitive_data_review = 'pending'
            reviewed_scenario_ids = @()
            limitations = $null
        }
        error = $null
    }

    Write-A11yFixture -Report $a11yReport -Candidate $candidate

    Write-Candidate $candidate
    $valid = & $validator -Path $candidatePath -RequirePassed | ConvertFrom-Json
    if (-not $valid.valid -or $valid.schema_version -ne 2) {
        throw 'Validator did not accept the complete schema-v2 candidate.'
    }

    $candidate.source.embedded_build_id = 'f' * 40
    Assert-Rejected $candidate 'embedded build ID'
    $candidate.source.embedded_build_id = $commit

    $candidate.source.checkout_clean = 'false'
    Assert-Rejected $candidate 'JSON Boolean'
    $candidate.source.checkout_clean = $true

    $candidate.driver.session.integrity_match = $false
    Assert-Rejected $candidate 'integrity contract'
    $candidate.driver.session.integrity_match = $true

    $candidate.scenarios[0].expected_checkpoints = @()
    Assert-Rejected $candidate 'no expected checkpoints'
    $candidate.scenarios[0].expected_checkpoints = @('stable owned window', 'nonblank capture')

    $candidate.scenarios[0].inventory_ids = @('WIN-SC-2')
    Assert-Rejected $candidate 'invalid inventory ID'
    $candidate.scenarios[0].inventory_ids = @(
        'WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006'
    )

    $candidate.scenarios[0].inventory_ids = @('WIN-FAKE-999')
    Assert-Rejected $candidate 'unknown inventory ID'
    $candidate.scenarios[0].inventory_ids = @(
        'WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006'
    )

    $candidate.scenarios[0].inventory_ids = @('WIN-SC-002', 'WIN-SC-002')
    Assert-Rejected $candidate 'repeats inventory ID'
    $candidate.scenarios[0].inventory_ids = @(
        'WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006'
    )

    $candidate.application.isolated_profile_root = 'C:\Users\person\profile'
    Assert-Rejected $candidate 'private Windows user-profile path'
    $candidate.application.isolated_profile_root = 'profile'

    $candidate.driver.repository = 'https://secret@example.invalid/driver.git'
    Assert-Rejected $candidate 'credential-bearing'
    $candidate.driver.repository = `
        'https://github.com/example/lowlevel-computer-use-mcp.git'

    $candidate.source.version_metadata.sha256 = 'A' * 64
    Assert-Rejected $candidate 'lowercase SHA-256'
    $candidate.source.version_metadata.sha256 = $hash

    $candidate.process.pidfile_pid = 3333
    Assert-Rejected $candidate 'process provenance'
    $candidate.process.pidfile_pid = 2222

    $candidate.window.process_id = '2222'
    Assert-Rejected $candidate 'JSON integer: window.process_id'
    $candidate.window.process_id = 2222

    $candidate.window.thread_id = '3333'
    Assert-Rejected $candidate 'JSON integer: window.thread_id'
    $candidate.window.thread_id = 0
    Assert-Rejected $candidate 'ownership/thread identity'
    $candidate.window.thread_id = 3333

    $candidate.window.dpi = '144'
    Assert-Rejected $candidate 'JSON integer: window.dpi'
    $candidate.window.dpi = 144

    $candidate.scenarios[0].checkpoint.window_thread_id = 4444
    Assert-Rejected $candidate 'incomplete window checkpoint metadata'
    $candidate.scenarios[0].checkpoint.window_thread_id = 3333

    $candidate.driver.session.server_windows_session_id = 2
    Assert-Rejected $candidate 'session IDs are inconsistent'
    $candidate.driver.session.server_windows_session_id = 1

    $candidate.cleanup.forced_owned_process_cleanup = $true
    Assert-Rejected $candidate 'forced payload-process cleanup'
    $candidate.cleanup.forced_owned_process_cleanup = $false

    $candidate.scenarios[0].screenshot.path = 'screenshots/missing.png'
    Assert-Rejected $candidate 'does not exist'
    $candidate.scenarios[0].screenshot.path = 'screenshots/focus.png'

    Assert-Rejected $candidate 'not accepted' -RequireAccepted
    $candidate.status = 'accepted'
    $candidate.scenarios[0].result = 'pass'
    $candidate.review.status = 'pass'
    $candidate.review.reviewer = 'Evidence reviewer'
    $candidate.review.sensitive_data_review = 'pass'
    $candidate.review.reviewed_scenario_ids = @('E-START-LIGHT-KEYBOARD')
    Write-Candidate $candidate
    & $validator -Path $candidatePath -RequireAccepted | Out-Null

    $candidate.review.reviewer = ''
    Assert-Rejected $candidate 'nonblank reviewer' -RequireAccepted
    $candidate.review.reviewer = 'Evidence reviewer'

    $candidate.review.reviewed_scenario_ids = @()
    Assert-Rejected $candidate 'review every scenario ID' -RequireAccepted
    $candidate.review.reviewed_scenario_ids = @('E-START-LIGHT-KEYBOARD')

    $candidate.scenarios[0].screenshot.path = '../outside.png'
    Assert-Rejected $candidate 'escapes' -RequireAccepted
    $candidate.scenarios[0].screenshot.path = 'screenshots/focus.png'

    $candidate.scenarios[0].screenshot.sha256 = 'f' * 64
    Assert-Rejected $candidate 'screenshot/a11y binding differs' -RequireAccepted
    $candidate.scenarios[0].screenshot.sha256 = $screenshotHash

    $candidate.scenarios[0].screenshot.width = 1919
    $candidate.window.width = 1919
    Assert-Rejected $candidate 'PNG IHDR dimensions differ' -RequireAccepted
    $candidate.scenarios[0].screenshot.width = 1920
    $candidate.window.width = 1920

    $a11yReport.screenshot_sha256 = 'f' * 64
    Write-A11yFixture -Report $a11yReport -Candidate $candidate
    Assert-Rejected $candidate 'a11y screenshot hash differs' -RequireAccepted
    $a11yReport.screenshot_sha256 = $screenshotHash
    Write-A11yFixture -Report $a11yReport -Candidate $candidate

    $a11yReport.nodes[1].states = @('SHOWING', 'VISIBLE')
    Write-A11yFixture -Report $a11yReport -Candidate $candidate
    Assert-Rejected $candidate 'requires a focused a11y node' -RequireAccepted
    $a11yReport.nodes[1].states = @('SHOWING', 'VISIBLE', 'FOCUSED')
    Write-A11yFixture -Report $a11yReport -Candidate $candidate

    $a11yReport.summary.partial = 'false'
    Write-A11yFixture -Report $a11yReport -Candidate $candidate
    Assert-Rejected $candidate 'JSON Boolean' -RequireAccepted
    $a11yReport.summary.partial = $false
    Write-A11yFixture -Report $a11yReport -Candidate $candidate

    $candidate.review.status = 'accepted-known-issue'
    Assert-Rejected $candidate 'nonblank limitations' -RequireAccepted
    $candidate.review.limitations = 'Known visual variance documented by reviewer.'
    Write-Candidate $candidate
    & $validator -Path $candidatePath -RequireAccepted | Out-Null

    $runnerText = Get-Content -LiteralPath $runner -Raw
    $validatorText = Get-Content -LiteralPath $validator -Raw
    $qaText = Get-Content -LiteralPath $PSCommandPath -Raw
    $legacyHashCommand = 'Get-' + 'FileHash'
    foreach ($source in @(
        @{ name = 'runner'; text = $runnerText },
        @{ name = 'validator'; text = $validatorText },
        @{ name = 'contract regression'; text = $qaText }
    )) {
        if ($source.text.Contains($legacyHashCommand)) {
            throw "$($source.name) still depends on the legacy file-hash cmdlet."
        }
        if (-not $source.text.Contains(
            '[System.Security.Cryptography.SHA256]::Create()')) {
            throw "$($source.name) is missing the direct .NET SHA-256 helper."
        }
    }

    $identityIndex = $runnerText.IndexOf('$versionMetadataIdentity =')
    $wrapperWriteIndex = $runnerText.IndexOf('Write-Utf8Lf -Path $wrapperPath')
    $wrapperRemovalIndex = $runnerText.IndexOf(
        'Remove-Item -LiteralPath $wrapperPath',
        $wrapperWriteIndex
    )
    $resultsIndex = $runnerText.IndexOf('$results = [ordered]@{')
    if ($identityIndex -lt 0 -or $wrapperWriteIndex -le $identityIndex) {
        throw 'Runner must precompute fallible evidence identities before writing the wrapper.'
    }
    if ($wrapperRemovalIndex -le $wrapperWriteIndex -or `
        $resultsIndex -le $wrapperRemovalIndex) {
        throw 'Runner must remove a path-bearing wrapper when wrapper preflight fails.'
    }

    $ownershipLoopIndex = $runnerText.IndexOf(
        '$deadline = [DateTimeOffset]::UtcNow.AddSeconds(90)'
    )
    $ownershipLoopEndIndex = $runnerText.IndexOf(
        '$scenarioList = [System.Collections.Generic.List[object]]::new()',
        $ownershipLoopIndex
    )
    $pidFileAuthorityIndex = $runnerText.IndexOf(
        '$pidFilePid = $observedPidFilePid',
        $ownershipLoopIndex
    )
    $pidFileResolutionIndex = $runnerText.IndexOf(
        'Get-OwnedProcess -ProcessId $pidFilePid',
        $ownershipLoopIndex
    )
    $ownedPidLatchIndex = $runnerText.IndexOf(
        '$ownedPid = [int]$pidFileOwnedProcess.ProcessId',
        $ownershipLoopIndex
    )
    $windowEnumerationIndex = $runnerText.IndexOf(
        "Invoke-LowLevelTool -Tool 'list_headless_windows'",
        $ownedPidLatchIndex
    )
    if ($ownershipLoopIndex -lt 0 -or $ownershipLoopEndIndex -le $ownershipLoopIndex -or
        $pidFileAuthorityIndex -le $ownershipLoopIndex -or
        $pidFileResolutionIndex -le $pidFileAuthorityIndex -or
        $ownedPidLatchIndex -le $pidFileResolutionIndex -or
        $windowEnumerationIndex -le $ownedPidLatchIndex) {
        throw 'Runner must resolve and latch only the authoritative pidfile PID before driver window-identity validation.'
    }
    $arbitraryPayloadEnumerationIndex = $runnerText.IndexOf(
        'Get-ExactPayloadProcesses -ProgramRoot $programRoot',
        $ownershipLoopIndex
    )
    if ($arbitraryPayloadEnumerationIndex -ge 0 -and
        $arbitraryPayloadEnumerationIndex -lt $ownershipLoopEndIndex) {
        throw 'Runner must not enumerate and latch an arbitrary payload process during ownership establishment.'
    }

    $windowPidFieldIndex = $runnerText.IndexOf(
        '$candidateProcessId = Get-JsonIntegerProperty -Object $observedWindow',
        $windowEnumerationIndex
    )
    $windowThreadFieldIndex = $runnerText.IndexOf(
        '$candidateThreadId = Get-JsonIntegerProperty -Object $observedWindow',
        $windowPidFieldIndex
    )
    $windowDpiFieldIndex = $runnerText.IndexOf(
        '$candidateDpi = Get-JsonIntegerProperty -Object $observedWindow',
        $windowThreadFieldIndex
    )
    $invalidWindowPidIndex = $runnerText.IndexOf(
        'if ($null -eq $candidateProcessId -or $candidateProcessId -le 0)',
        $windowDpiFieldIndex
    )
    $invalidWindowThreadIndex = $runnerText.IndexOf(
        'if ($null -eq $candidateThreadId -or $candidateThreadId -le 0)',
        $invalidWindowPidIndex
    )
    $invalidWindowDpiIndex = $runnerText.IndexOf(
        'if ($null -eq $candidateDpi -or $candidateDpi -le 0)',
        $invalidWindowThreadIndex
    )
    $wrongWindowPidIndex = $runnerText.IndexOf(
        'if ($candidateProcessId -ne [long]$ownedPid)',
        $invalidWindowDpiIndex
    )
    $candidateSnapshotIndex = $runnerText.IndexOf(
        '$candidate = [pscustomobject][ordered]@{',
        $wrongWindowPidIndex
    )
    $stableHandlePidIndex = $runnerText.IndexOf(
        '$stableHandle -eq [long]$candidate.handle -and',
        $candidateSnapshotIndex
    )
    $stableThresholdIndex = $runnerText.IndexOf(
        'if ($ownedPid -and $pidFilePid -and $stableCount -ge 3)',
        $stableHandlePidIndex
    )
    $acceptedWindowIndex = $runnerText.IndexOf(
        '$script:WindowHandle = [long]$candidate.handle',
        $stableThresholdIndex
    )
    if ($windowPidFieldIndex -le $windowEnumerationIndex -or
        $windowThreadFieldIndex -le $windowPidFieldIndex -or
        $windowDpiFieldIndex -le $windowThreadFieldIndex -or
        $invalidWindowPidIndex -le $windowDpiFieldIndex -or
        $invalidWindowThreadIndex -le $invalidWindowPidIndex -or
        $invalidWindowDpiIndex -le $invalidWindowThreadIndex -or
        $wrongWindowPidIndex -le $invalidWindowDpiIndex -or
        $candidateSnapshotIndex -le $wrongWindowPidIndex -or
        $stableHandlePidIndex -le $candidateSnapshotIndex -or
        $stableThresholdIndex -le $stableHandlePidIndex -or
        $acceptedWindowIndex -le $stableThresholdIndex) {
        throw 'Runner must reject incomplete/wrong driver window identity before handle-and-PID stability and acceptance.'
    }

    foreach ($forbiddenHwndProbe in @(
        '[DllImport("user32.dll")]',
        'GetWindowThreadProcessId(IntPtr',
        'public static uint WindowDpi(IntPtr hwnd)',
        'public static uint WindowProcessId(IntPtr hwnd)',
        '::WindowDpi(',
        '::WindowProcessId('
    )) {
        if ($runnerText.Contains($forbiddenHwndProbe)) {
            throw "Runner must consume the driver's atomic window identity instead of local HWND probe: $forbiddenHwndProbe"
        }
    }

    foreach ($needle in @(
        "Join-Path `$programRoot 'version.ini'",
        'upstream_baseline',
        'checkout_dirty',
        'display_scale',
        'user_profile_root',
        'package_version',
        'integrity_match',
        'integrity_verification_method',
        'GetDpiForWindow',
        'Get-JsonIntegerProperty',
        'inventory_ids',
        'automation_result',
        'program/updchklo.dll',
        'share/theme_definitions/material/definition.xml',
        'runtime_launch_wrapper_removed',
        'The pidfile PID is the sole ownership authority',
        'not the required soffice.bin GUI runtime',
        'PID-file process identity changed after ownership was established',
        'window_handoff_diagnostics',
        'inside the same EnumDesktopWindows callback that produced the HWND',
        'list_headless_windows process_id is missing, non-integer, or zero',
        'list_headless_windows thread_id is missing, non-integer, or zero',
        'list_headless_windows dpi is missing, non-integer, or zero',
        'does not match pidfile-owned PID',
        'thread_id = [long]$candidate.thread_id',
        'expected_checkpoints',
        "Join-Path `$runRoot 'manifest.json'",
        '& $evidenceValidatorPath -Path $manifestPath -RequirePassed'
    )) {
        if (-not $runnerText.Contains($needle)) {
            throw "Runner is missing evidence-contract marker: $needle"
        }
    }

    Write-Host 'Windows headless evidence contract regression: PASS'
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
