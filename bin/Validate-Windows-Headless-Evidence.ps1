[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [switch]$RequirePassed,

    [switch]$RequireAccepted
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$inventoryPath = Join-Path $repositoryRoot 'docs\WINDOWS_UI_INVENTORY.md'
if (-not (Test-Path -LiteralPath $inventoryPath -PathType Leaf)) {
    throw "Windows UI inventory does not exist: $inventoryPath"
}
$inventoryText = Get-Content -LiteralPath $inventoryPath -Raw
$inventoryMatches = [regex]::Matches(
    $inventoryText,
    '(?m)^\| (WIN-[A-Z]+-[0-9]{3}) \|'
)
$knownInventoryIds = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::Ordinal
)
foreach ($inventoryMatch in $inventoryMatches) {
    $inventoryId = $inventoryMatch.Groups[1].Value
    if (-not $knownInventoryIds.Add($inventoryId)) {
        throw "Windows UI inventory contains duplicate stable ID: $inventoryId"
    }
}
if ($knownInventoryIds.Count -eq 0) {
    throw 'Windows UI inventory contains no stable WIN-* IDs.'
}

function Get-RequiredEvidenceValue {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$FieldPath
    )

    $current = $Object
    foreach ($part in $FieldPath.Split('.')) {
        if ($null -eq $current -or
            -not ($current.PSObject.Properties.Name -contains $part)) {
            throw "Evidence field is missing: $FieldPath"
        }
        $current = $current.$part
    }
    return $current
}

function Get-RequiredEvidenceBoolean {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$FieldPath
    )

    $value = Get-RequiredEvidenceValue -Object $Object -FieldPath $FieldPath
    if ($value -isnot [bool]) {
        throw "Evidence field must be a JSON Boolean: $FieldPath"
    }
    return [bool]$value
}

function Get-RequiredEvidenceInteger {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$FieldPath
    )

    $value = Get-RequiredEvidenceValue -Object $Object -FieldPath $FieldPath
    $integerTypes = @(
        [byte], [sbyte], [int16], [uint16], [int32], [uint32], [int64], [uint64]
    )
    if ($integerTypes -notcontains $value.GetType()) {
        throw "Evidence field must be a JSON integer: $FieldPath"
    }
    return [long]$value
}

function Assert-Evidence {
    param(
        [Parameter(Mandatory = $true)] [bool]$Condition,
        [Parameter(Mandatory = $true)] [string]$Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Hash {
    param([Parameter(Mandatory = $true)] [string]$Value, [string]$Name)
    Assert-Evidence ($Value -cmatch '^[0-9a-f]{64}$') "$Name must be a lowercase SHA-256 hash."
}

function Assert-Commit {
    param([Parameter(Mandatory = $true)] [string]$Value, [string]$Name)
    Assert-Evidence ($Value -cmatch '^[0-9a-f]{40}$') "$Name must be a lowercase full commit ID."
}

function Resolve-RunArtifactPath {
    param(
        [Parameter(Mandatory = $true)] [string]$ManifestRoot,
        [Parameter(Mandatory = $true)] [string]$RelativePath,
        [Parameter(Mandatory = $true)] [string]$ExpectedDirectory
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath) -or
        [System.IO.Path]::IsPathRooted($RelativePath) -or
        $RelativePath.Contains('\') -or
        $RelativePath -notmatch '^[A-Za-z0-9._/-]+$') {
        throw "Artifact path must be a portable run-relative path: $RelativePath"
    }
    $segments = @($RelativePath.Split('/'))
    if ($segments.Count -lt 2 -or $segments[0] -cne $ExpectedDirectory -or
        @($segments | Where-Object { $_ -in @('', '.', '..') }).Count -ne 0) {
        throw "Artifact path escapes or does not belong to '$ExpectedDirectory': $RelativePath"
    }
    $root = [System.IO.Path]::GetFullPath($ManifestRoot).TrimEnd('\', '/')
    $candidate = [System.IO.Path]::GetFullPath(
        (Join-Path $root ($RelativePath.Replace('/', [System.IO.Path]::DirectorySeparatorChar)))
    )
    $prefix = $root + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Artifact path resolves outside the manifest directory: $RelativePath"
    }
    return $candidate
}

function Assert-ArtifactFileIdentity {
    param(
        [Parameter(Mandatory = $true)] [string]$ArtifactPath,
        [Parameter(Mandatory = $true)] [object]$Record,
        [Parameter(Mandatory = $true)] [string]$Description
    )

    if (-not (Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) {
        throw "$Description does not exist: $ArtifactPath"
    }
    $item = Get-Item -LiteralPath $ArtifactPath
    Assert-Evidence ([long]$Record.bytes -eq [long]$item.Length) `
        "$Description byte count does not match the file."
    $actualHash = (Get-FileHash -LiteralPath $ArtifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-Evidence ([string]$Record.sha256 -ceq $actualHash) `
        "$Description SHA-256 does not match the file."
}

function Get-PngHeaderDimensions {
    param([Parameter(Mandatory = $true)] [string]$PngPath)

    $header = [byte[]]::new(24)
    $stream = [System.IO.File]::OpenRead($PngPath)
    try {
        $read = $stream.Read($header, 0, $header.Length)
    }
    finally {
        $stream.Dispose()
    }
    if ($read -ne 24) { throw "PNG is too short to contain IHDR: $PngPath" }
    $signature = [byte[]](137, 80, 78, 71, 13, 10, 26, 10)
    for ($index = 0; $index -lt $signature.Length; $index++) {
        if ($header[$index] -ne $signature[$index]) {
            throw "PNG signature is invalid: $PngPath"
        }
    }
    if ([System.Text.Encoding]::ASCII.GetString($header, 12, 4) -cne 'IHDR') {
        throw "PNG first chunk is not IHDR: $PngPath"
    }
    $ihdrLength = ([uint32]$header[8] * 16777216) +
        ([uint32]$header[9] * 65536) + ([uint32]$header[10] * 256) + $header[11]
    if ($ihdrLength -ne 13) { throw "PNG IHDR length is invalid: $PngPath" }
    $width = ([uint32]$header[16] * 16777216) +
        ([uint32]$header[17] * 65536) + ([uint32]$header[18] * 256) + $header[19]
    $height = ([uint32]$header[20] * 16777216) +
        ([uint32]$header[21] * 65536) + ([uint32]$header[22] * 256) + $header[23]
    return [pscustomobject]@{ width = [long]$width; height = [long]$height }
}

$resolved = [System.IO.Path]::GetFullPath($Path)
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
    throw "Evidence manifest does not exist: $resolved"
}
$manifestText = Get-Content -LiteralPath $resolved -Raw
if ($manifestText -match '(?i)[A-Z]:(?:\\\\|/)Users(?:\\\\|/)') {
    throw 'Evidence manifest contains a private Windows user-profile path.'
}
$evidence = $manifestText | ConvertFrom-Json
$manifestRoot = Split-Path -Parent $resolved

Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'schema_version') -eq 2) `
    'Windows headless evidence must use schema version 2.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'run_id') -match '^[A-Za-z0-9._-]+$') `
    'run_id is invalid.'
foreach ($repositoryField in @('source.repository', 'harness.repository', 'driver.repository')) {
    $repositoryValue = [string](Get-RequiredEvidenceValue $evidence $repositoryField)
    Assert-Evidence (-not [string]::IsNullOrWhiteSpace($repositoryValue) -and
        $repositoryValue -notmatch '^(?i)https?://[^/@]+@' -and
        $repositoryValue -notmatch '^(?i)(file:|[A-Za-z]:[\\/]|\\\\)') `
        "$repositoryField is missing, credential-bearing, or host-local."
}

$sourceCommit = [string](Get-RequiredEvidenceValue $evidence 'source.commit')
$embeddedBuildId = [string](Get-RequiredEvidenceValue $evidence 'source.embedded_build_id')
Assert-Commit $sourceCommit 'source.commit'
Assert-Evidence ([string](Get-RequiredEvidenceValue $evidence 'source_commit') -ceq
    $sourceCommit) 'source_commit must equal source.commit.'
Assert-Commit ([string](Get-RequiredEvidenceValue $evidence 'source.upstream_baseline')) `
    'source.upstream_baseline'
Assert-Evidence ($embeddedBuildId -eq $sourceCommit) `
    'The embedded build ID must equal the exact source commit.'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'source.checkout_clean') `
    'The source checkout must be clean.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence 'source.checkout_dirty')) `
    'The source dirty-worktree state contradicts checkout_clean.'
Assert-Hash ([string](Get-RequiredEvidenceValue $evidence 'source.version_metadata.sha256')) `
    'source.version_metadata.sha256'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'source.version_metadata.path') -ceq 'program/version.ini') `
    'Source version metadata path must be payload-relative.'

Assert-Commit ([string](Get-RequiredEvidenceValue $evidence 'harness.commit')) 'harness.commit'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'harness.checkout_clean') `
    'The evidence harness checkout must be clean.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence 'harness.checkout_dirty')) `
    'The harness dirty-worktree state contradicts checkout_clean.'
Assert-Hash ([string](Get-RequiredEvidenceValue $evidence 'harness.entrypoint.sha256')) `
    'harness.entrypoint.sha256'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'harness.entrypoint.path') -ceq 'bin/Run-Windows-Headless-Smoke.ps1') `
    'Harness entrypoint path must be repository-relative.'
$harnessDependencies = @(Get-RequiredEvidenceValue $evidence 'harness.dependencies')
Assert-Evidence ($harnessDependencies.Count -ge 4) `
    'The harness must identify its validator, MCP client, PNG analyzer, and a11y collector.'
foreach ($dependency in $harnessDependencies) {
    Assert-Hash ([string]$dependency.sha256) 'harness dependency SHA-256'
    Assert-Evidence ([string]$dependency.path -cmatch '^bin/[A-Za-z0-9._-]+$') `
        'Harness dependency path must be repository-relative.'
}

$dpi = [int](Get-RequiredEvidenceValue $evidence 'host.display_scale.dpi')
$scale = [int](Get-RequiredEvidenceValue $evidence 'host.display_scale.percent')
Assert-Evidence ($dpi -gt 0 -and $scale -gt 0) 'Display DPI and scale must be positive.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'host.display_scale.source') -ceq
    'GetDpiForWindow on the runtime-resolved SALFRAME HWND') `
    'Display scale must come from the resolved target window.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
    'host.font_configuration.run_specific_override')) `
    'This harness contract expects native fonts without a run-specific override.'
Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'host.font_configuration.source')
)) 'The exact font-configuration source must be recorded.'
Get-RequiredEvidenceValue $evidence 'host.font_configuration.override_files' | Out-Null

$profileUri = [string](Get-RequiredEvidenceValue $evidence 'application.user_installation_uri')
$unoPipe = [string](Get-RequiredEvidenceValue $evidence 'application.uno_pipe')
$pidFile = [string](Get-RequiredEvidenceValue $evidence 'application.pid_file')
$applicationArguments = @(Get-RequiredEvidenceValue $evidence 'application.arguments')
foreach ($requiredArgument in @(
    "-env:UserInstallation=$profileUri",
    '--nologo',
    '--norestore',
    '--quickstart=no',
    '--language=en-US',
    "--pidfile=$pidFile",
    "--accept=pipe,name=$unoPipe;urp"
)) {
    Assert-Evidence (@($applicationArguments | Where-Object { $_ -ceq $requiredArgument }).Count -eq 1) `
        "Application arguments must contain exactly one '$requiredArgument'."
}
foreach ($forbiddenArgument in @('--headless', '--invisible', '--nodefault')) {
    Assert-Evidence (-not ($applicationArguments -contains $forbiddenArgument)) `
        "GUI evidence cannot use $forbiddenArgument."
}
foreach ($field in @(
    'application.isolated_profile_root',
    'application.user_profile_root',
    'application.profile_configuration.path'
)) {
    Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
        [string](Get-RequiredEvidenceValue $evidence $field)
    )) "$field must be recorded."
}
Assert-Hash ([string](Get-RequiredEvidenceValue $evidence 'application.executable.sha256')) `
    'application.executable.sha256'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'application.executable.path') -ceq
    'program/soffice.exe') 'Application executable path must be payload-relative.'
foreach ($payloadIdentity in @(
    @{ field = 'application.runtime_executable'; path = 'program/soffice.bin' },
    @{ field = 'application.updater_library'; path = 'program/updchklo.dll' },
    @{
        field = 'application.material_theme_definition'
        path = 'share/theme_definitions/material/definition.xml'
    }
)) {
    Assert-Hash ([string](Get-RequiredEvidenceValue $evidence `
        ($payloadIdentity.field + '.sha256'))) ($payloadIdentity.field + '.sha256')
    Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
        ($payloadIdentity.field + '.path')) -ceq $payloadIdentity.path) `
        "$($payloadIdentity.field) must use its exact payload-relative path."
}
Assert-Hash ([string](Get-RequiredEvidenceValue $evidence 'application.profile_configuration.sha256')) `
    'application.profile_configuration.sha256'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
    'application.arguments_path_tokenized') `
    'Application arguments must use public-safe run-root tokens.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
    'application.launch_wrapper.retained_in_public_evidence')) `
    'The path-bearing launch wrapper must remain runtime-only.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
    'application.profile_configuration.retained_in_public_evidence')) `
    'The generated profile must remain runtime-only.'

Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'environment.VCL_DRAW_WIDGETS_FROM_FILE') -ceq '1') `
    'VCL_DRAW_WIDGETS_FROM_FILE must be exactly 1.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'environment.VCL_FILE_WIDGET_THEME') -ceq 'material') `
    'VCL_FILE_WIDGET_THEME must be exactly material.'

Assert-Commit ([string](Get-RequiredEvidenceValue $evidence 'driver.commit')) 'driver.commit'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'driver.checkout_clean') `
    'The low-level driver checkout must be clean.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence 'driver.checkout_dirty')) `
    'The low-level driver dirty-worktree state contradicts checkout_clean.'
Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'driver.package_version')
)) 'The exact low-level MCP server package version must be recorded.'
Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'driver.package_name')
)) 'The exact low-level MCP server package name must be recorded.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'driver.mcp_url') -match
    '^http://127\.0\.0\.1:\d+/mcp$') `
    'The dedicated MCP endpoint must be an exact loopback URL.'
Assert-Evidence ([int](Get-RequiredEvidenceValue $evidence 'driver.server_pid') -gt 0) `
    'The dedicated MCP server root PID must be recorded.'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'driver.dedicated_server') `
    'Accepted evidence requires a dedicated MCP server.'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'driver.session.same_windows_session') `
    'The driver and harness must share the exact Windows session.'
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'driver.session.integrity_match') `
    'The driver and harness integrity contract was not proven.'
Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'driver.session.integrity_verification_method')
)) 'The server integrity verification method must be explicit.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'driver.session.integrity.mandatory_label_sid') -match '^S-1-16-\d+$') `
    'The harness mandatory integrity SID is invalid.'
$harnessSessionId = Get-RequiredEvidenceInteger $evidence `
    'driver.session.harness_windows_session_id'
$serverSessionId = Get-RequiredEvidenceInteger $evidence `
    'driver.session.server_windows_session_id'
Assert-Evidence ($harnessSessionId -ge 0 -and $serverSessionId -eq $harnessSessionId) `
    'Recorded driver/harness Windows session IDs are inconsistent.'
$harnessAdmin = Get-RequiredEvidenceBoolean $evidence `
    'driver.session.integrity.is_administrator'
$serverAdmin = Get-RequiredEvidenceBoolean $evidence `
    'driver.session.server_reported_is_administrator'
Assert-Evidence ($harnessAdmin -eq $serverAdmin) `
    'Recorded driver/harness administrator states are inconsistent.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
    'driver.session.server_mandatory_label_measured_directly')) `
    'The current contract must not claim a directly measured server mandatory label.'

$ownedPid = Get-RequiredEvidenceInteger $evidence 'process.pid'
$pidFilePid = Get-RequiredEvidenceInteger $evidence 'process.pidfile_pid'
$launcherPid = Get-RequiredEvidenceInteger $evidence 'process.launcher_pid'
Assert-Evidence ($ownedPid -gt 0 -and $pidFilePid -eq $ownedPid -and $launcherPid -gt 0) `
    'Owned, PID-file, and launcher process provenance is incomplete or inconsistent.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'process.executable_path') -cmatch
    '^program/soffice(\.bin|\.exe)$') `
    'Owned process executable must use its exact payload-relative path.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'process.name') -ceq 'soffice.bin') `
    'Owned runtime process must be soffice.bin.'
$windowProcessId = Get-RequiredEvidenceInteger $evidence 'window.process_id'
$windowHandle = Get-RequiredEvidenceInteger $evidence 'window.handle'
$windowWidth = [int](Get-RequiredEvidenceValue $evidence 'window.width')
$windowHeight = [int](Get-RequiredEvidenceValue $evidence 'window.height')
$windowDpi = [int](Get-RequiredEvidenceValue $evidence 'window.dpi')
Assert-Evidence ($windowProcessId -eq $ownedPid -and $windowHandle -gt 0) `
    'Resolved window ownership does not match the exact payload PID.'
Assert-Evidence ($windowWidth -gt 0 -and $windowHeight -gt 0 -and
    [int](Get-RequiredEvidenceValue $evidence 'window.stable_poll_count') -ge 3) `
    'Resolved window dimensions or stability proof is invalid.'
Assert-Evidence ((-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'window.title')
)) -and ((Get-RequiredEvidenceValue $evidence 'window.class') -ceq 'SALFRAME')) `
    'Resolved window title/class metadata is invalid.'
Assert-Evidence ($windowDpi -eq $dpi) `
    'Resolved window DPI differs from the recorded display scale.'

if ($RequirePassed -or $RequireAccepted) {
    $allowedStatus = if ($RequireAccepted) { 'accepted' } else { 'passed' }
    Assert-Evidence ($evidence.status -ceq $allowedStatus) `
        "Evidence status is not $allowedStatus."
    $scenarios = @($evidence.scenarios)
    Assert-Evidence ($scenarios.Count -gt 0) 'A passed run must contain scenarios.'
    Assert-Evidence (@($scenarios | ForEach-Object { [string]$_.id } |
        Select-Object -Unique).Count -eq $scenarios.Count) `
        'Scenario IDs must be unique.'
    foreach ($scenario in $scenarios) {
        Assert-Evidence (-not [string]::IsNullOrWhiteSpace([string]$scenario.id)) `
            'Every scenario must have an ID.'
        $inventoryIds = @($scenario.inventory_ids)
        Assert-Evidence ($inventoryIds.Count -gt 0) `
            "Scenario '$($scenario.id)' has no Windows inventory IDs."
        $scenarioInventoryIds = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::Ordinal
        )
        foreach ($inventoryId in $inventoryIds) {
            Assert-Evidence ([string]$inventoryId -cmatch '^WIN-[A-Z]+-[0-9]{3}$') `
                "Scenario '$($scenario.id)' has invalid inventory ID '$inventoryId'."
            Assert-Evidence ($scenarioInventoryIds.Add([string]$inventoryId)) `
                "Scenario '$($scenario.id)' repeats inventory ID '$inventoryId'."
            Assert-Evidence ($knownInventoryIds.Contains([string]$inventoryId)) `
                "Scenario '$($scenario.id)' references unknown inventory ID '$inventoryId'."
        }
        $focusInventory = @($inventoryIds | Where-Object {
            $_ -in @('WIN-SC-002', 'WIN-ACT-006', 'WIN-SC-006')
        }).Count -gt 0
        $requiresFocusedAccessibility = Get-RequiredEvidenceBoolean $scenario `
            'requires_focused_accessibility'
        if ($focusInventory) {
            Assert-Evidence $requiresFocusedAccessibility `
                "Focus scenario '$($scenario.id)' must require focused accessibility evidence."
        }
        Assert-Evidence ($scenario.automation_result -ceq 'pass') `
            "Scenario '$($scenario.id)' automation did not pass."
        $expectedScenarioResult = if ($RequireAccepted) {
            'pass'
        }
        else {
            'pending_visual_review'
        }
        Assert-Evidence ($scenario.result -ceq $expectedScenarioResult) `
            "Scenario '$($scenario.id)' result is not $expectedScenarioResult."
        Assert-Evidence (@($scenario.expected_checkpoints).Count -gt 0) `
            "Scenario '$($scenario.id)' has no expected checkpoints."
        foreach ($expectedCheckpoint in @($scenario.expected_checkpoints)) {
            Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
                [string]$expectedCheckpoint
            )) "Scenario '$($scenario.id)' contains a blank expected checkpoint."
        }
        Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
            [string]$scenario.checkpoint.captured_at_utc
        )) "Scenario '$($scenario.id)' has no capture timestamp."
        Assert-Evidence ([long]$scenario.checkpoint.window_handle -eq $windowHandle -and
            [int]$scenario.checkpoint.window_process_id -eq $windowProcessId -and
            [int]$scenario.checkpoint.window_dpi -eq $windowDpi -and
            [string]$scenario.checkpoint.window_title -ceq [string]$evidence.window.title -and
            [string]$scenario.checkpoint.window_class -ceq [string]$evidence.window.class) `
            "Scenario '$($scenario.id)' has incomplete window checkpoint metadata."
        Get-RequiredEvidenceBoolean $scenario.checkpoint `
            'normal_uno_termination_requested' | Out-Null
        Assert-Hash -Value ([string]$scenario.screenshot.sha256) `
            -Name "scenario '$($scenario.id)' screenshot SHA-256"
        $screenshotNonblank = Get-RequiredEvidenceBoolean $scenario.screenshot 'nonblank'
        Assert-Evidence ($screenshotNonblank -and
            [int]$scenario.screenshot.width -eq $windowWidth -and
            [int]$scenario.screenshot.height -eq $windowHeight) `
            "Scenario '$($scenario.id)' screenshot is invalid."
        Assert-Evidence ([string]$scenario.accessibility.screenshot_sha256 -ceq
            [string]$scenario.screenshot.sha256) `
            "Scenario '$($scenario.id)' screenshot/a11y binding differs."
        $screenshotArtifactPath = Resolve-RunArtifactPath -ManifestRoot $manifestRoot `
            -RelativePath ([string]$scenario.screenshot.path) `
            -ExpectedDirectory 'screenshots'
        $a11yArtifactPath = Resolve-RunArtifactPath -ManifestRoot $manifestRoot `
            -RelativePath ([string]$scenario.accessibility.path) `
            -ExpectedDirectory 'logs'

        # Bind automation results to the actual retained artifacts for both
        # candidate and accepted validation; acceptance adds human review below.
            Assert-ArtifactFileIdentity -ArtifactPath $screenshotArtifactPath `
                -Record $scenario.screenshot `
                -Description "Scenario '$($scenario.id)' screenshot"
            $pngDimensions = Get-PngHeaderDimensions -PngPath $screenshotArtifactPath
            Assert-Evidence (
                [long]$scenario.screenshot.width -eq $pngDimensions.width -and
                [long]$scenario.screenshot.height -eq $pngDimensions.height
            ) "Scenario '$($scenario.id)' PNG IHDR dimensions differ from the manifest."

            Assert-Hash -Value ([string]$scenario.accessibility.sha256) `
                -Name "scenario '$($scenario.id)' a11y SHA-256"
            Assert-ArtifactFileIdentity -ArtifactPath $a11yArtifactPath `
                -Record $scenario.accessibility `
                -Description "Scenario '$($scenario.id)' a11y report"
            try {
                $a11yText = Get-Content -LiteralPath $a11yArtifactPath -Raw
                if ($a11yText -match '(?i)[A-Z]:(?:\\\\|/)Users(?:\\\\|/)') {
                    throw 'a11y report contains a private Windows user-profile path'
                }
                $a11yReport = $a11yText | ConvertFrom-Json
            }
            catch {
                throw "Scenario '$($scenario.id)' a11y report is invalid JSON: $($_.Exception.Message)"
            }
            Assert-Evidence ([string](Get-RequiredEvidenceValue $a11yReport 'run_id') -ceq
                [string]$evidence.run_id) `
                "Scenario '$($scenario.id)' a11y run_id differs from the manifest."
            Assert-Evidence ([string](Get-RequiredEvidenceValue $a11yReport `
                'screenshot_sha256') -ceq [string]$scenario.screenshot.sha256) `
                "Scenario '$($scenario.id)' a11y screenshot hash differs from the PNG."
            $a11ySummary = Get-RequiredEvidenceValue $a11yReport 'summary'
            $a11yPartial = Get-RequiredEvidenceBoolean $a11ySummary 'partial'
            Assert-Evidence (-not $a11yPartial) `
                "Scenario '$($scenario.id)' a11y report is partial."
            Assert-Evidence ([int](Get-RequiredEvidenceValue $a11ySummary 'errors') -eq 0) `
                "Scenario '$($scenario.id)' a11y report contains errors."
            Assert-Evidence ([int](Get-RequiredEvidenceValue $a11ySummary 'visible_nodes') -gt 0) `
                "Scenario '$($scenario.id)' a11y report has no visible nodes."
            Assert-Evidence ([int](Get-RequiredEvidenceValue $a11ySummary 'node_count') -gt 0) `
                "Scenario '$($scenario.id)' a11y report has no nodes."
            $focusedNodeCount = @(
                @(Get-RequiredEvidenceValue $a11yReport 'nodes') | Where-Object {
                    @($_.states) -contains 'FOCUSED'
                }
            ).Count
            if ($requiresFocusedAccessibility) {
                Assert-Evidence ($focusedNodeCount -gt 0) `
                    "Scenario '$($scenario.id)' requires a focused a11y node but has none."
            }
            $recordedA11yPartial = Get-RequiredEvidenceBoolean `
                $scenario.accessibility.summary 'partial'
            Assert-Evidence (
                [int]$scenario.accessibility.summary.node_count -eq [int]$a11ySummary.node_count -and
                [int]$scenario.accessibility.summary.visible_nodes -eq [int]$a11ySummary.visible_nodes -and
                [int]$scenario.accessibility.summary.errors -eq [int]$a11ySummary.errors -and
                $recordedA11yPartial -eq $a11yPartial -and
                [int]$scenario.accessibility.summary.focused_node_count -eq $focusedNodeCount
            ) "Scenario '$($scenario.id)' recorded a11y summary differs from the report."
    }
    Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
        'cleanup.normal_uno_termination') `
        'Normal UNO termination did not complete.'
    Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
        'cleanup.forced_owned_process_cleanup')) `
        'A passed run cannot require forced payload-process cleanup.'
    Assert-Evidence ([int]$evidence.cleanup.remaining_payload_processes -eq 0) `
        'Payload processes remain after cleanup.'
    Assert-Evidence ([int](Get-RequiredEvidenceValue $evidence `
        'cleanup.headless_windows_before_close') -eq 0) `
        'Headless windows remained immediately before desktop close.'
    Assert-Evidence (Get-RequiredEvidenceBoolean $evidence 'cleanup.desktop_closed') `
        'The off-screen desktop was not closed.'
    Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
        'cleanup.dedicated_driver_stopped') `
        'The dedicated MCP server process tree was not stopped.'
    Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
        'cleanup.runtime_launch_wrapper_removed') `
        'The path-bearing runtime launch wrapper was not removed.'
    foreach ($errorField in @(
        'process_cleanup_error',
        'desktop_cleanup_error',
        'dedicated_driver_cleanup_error',
        'runtime_launch_wrapper_cleanup_error'
    )) {
        Assert-Evidence ($null -eq $evidence.cleanup.$errorField) `
            "Cleanup field '$errorField' contains an error."
    }
    Assert-Evidence ($null -eq (Get-RequiredEvidenceValue $evidence 'error')) `
        'A passed or accepted run cannot contain a top-level error.'
}

if ($RequireAccepted) {
    $reviewStatus = [string](Get-RequiredEvidenceValue $evidence 'review.status')
    Assert-Evidence (@('pass', 'accepted-known-issue') -ccontains $reviewStatus) `
        'Accepted evidence requires review.status pass or accepted-known-issue.'
    Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
        [string](Get-RequiredEvidenceValue $evidence 'review.reviewer')
    )) 'Accepted evidence requires a nonblank reviewer.'
    Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
        'review.sensitive_data_review') -ceq 'pass') `
        'Accepted evidence requires a passed sensitive-data review.'
    if ($reviewStatus -ceq 'accepted-known-issue') {
        Assert-Evidence (-not [string]::IsNullOrWhiteSpace(
            [string](Get-RequiredEvidenceValue $evidence 'review.limitations')
        )) 'accepted-known-issue review requires nonblank limitations.'
    }
    $scenarioIds = @($scenarios | ForEach-Object { [string]$_.id })
    $reviewedScenarioIds = @(
        Get-RequiredEvidenceValue $evidence 'review.reviewed_scenario_ids' |
            ForEach-Object { [string]$_ }
    )
    Assert-Evidence ($reviewedScenarioIds.Count -eq $scenarioIds.Count -and
        @($reviewedScenarioIds | Select-Object -Unique).Count -eq $scenarioIds.Count) `
        'Accepted evidence must review every scenario ID exactly once.'
    foreach ($scenarioId in $scenarioIds) {
        Assert-Evidence ($reviewedScenarioIds -ccontains $scenarioId) `
            "Accepted review does not cover scenario '$scenarioId'."
    }
}

[pscustomobject]@{
    valid = $true
    schema_version = 2
    path = $resolved
    status = $evidence.status
} | ConvertTo-Json -Compress
