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
    $actualHash = Get-Sha256Hex -Path $ArtifactPath
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
$hasStartupProfile = $evidence.application.PSObject.Properties.Name -contains `
    'startup_profile'
$startupProfile = if ($hasStartupProfile) {
    [string](Get-RequiredEvidenceValue $evidence 'application.startup_profile')
}

function Get-RequiredEvidenceTimestamp {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$FieldPath
    )

    $value = [string](Get-RequiredEvidenceValue -Object $Object -FieldPath $FieldPath)
    $parsed = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse(
            $value,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind,
            [ref]$parsed
        )) {
        throw "Evidence field must be an ISO-8601 timestamp: $FieldPath"
    }
    return $parsed
}
else {
    # Schema-v2 Start Center manifests accepted before the no-nag extension did
    # not record this field; their legacy semantics are the configured profile.
    'configured'
}
Assert-Evidence (@('configured', 'fresh', 'legacy') -ccontains $startupProfile) `
    'application.startup_profile must be configured, fresh, or legacy.'
$isNoNagRun = $startupProfile -in @('fresh', 'legacy')
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
$expectedEntrypoint = if ($isNoNagRun) {
    'bin/Run-Windows-NoNag-Headless-Smoke.ps1'
}
else {
    'bin/Run-Windows-Headless-Smoke.ps1'
}
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'harness.entrypoint.path') -ceq $expectedEntrypoint) `
    'Harness entrypoint path must be repository-relative.'
$harnessDependencies = @(Get-RequiredEvidenceValue $evidence 'harness.dependencies')
Assert-Evidence ($harnessDependencies.Count -ge $(if ($isNoNagRun) { 5 } else { 4 })) `
    'The harness must identify its validator, MCP client, PNG analyzer, and a11y collector.'
foreach ($dependency in $harnessDependencies) {
    Assert-Hash ([string]$dependency.sha256) 'harness dependency SHA-256'
    Assert-Evidence ([string]$dependency.path -cmatch '^bin/[A-Za-z0-9._-]+$') `
        'Harness dependency path must be repository-relative.'
}
if ($isNoNagRun) {
    Assert-Evidence (@($harnessDependencies | Where-Object {
        [string]$_.path -ceq 'bin/Run-Windows-Headless-Smoke.ps1'
    }).Count -eq 1) 'No-nag evidence must bind the shared runner as a dependency.'
}

$dpi = Get-RequiredEvidenceInteger $evidence 'host.display_scale.dpi'
$scale = Get-RequiredEvidenceInteger $evidence 'host.display_scale.percent'
Assert-Evidence ($dpi -gt 0 -and $scale -gt 0) 'Display DPI and scale must be positive.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence 'host.display_scale.source') -ceq
    'GetDpiForWindow in the low-level list_headless_windows enumeration callback') `
    'Display scale must come from the driver enumeration callback.'
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
    '--quickstart=no',
    '--language=en-US',
    "--pidfile=$pidFile",
    "--accept=pipe,name=$unoPipe;urp"
)) {
    Assert-Evidence (@($applicationArguments | Where-Object { $_ -ceq $requiredArgument }).Count -eq 1) `
        "Application arguments must contain exactly one '$requiredArgument'."
}
if ($isNoNagRun) {
    Assert-Evidence (@($applicationArguments | Where-Object { $_ -ceq '--writer' }).Count -eq 1) `
        'No-nag application arguments must contain exactly one --writer.'
}
else {
    foreach ($requiredArgument in @('--nologo', '--norestore')) {
        Assert-Evidence (@($applicationArguments | Where-Object {
            $_ -ceq $requiredArgument
        }).Count -eq 1) `
            "Configured application arguments must contain exactly one '$requiredArgument'."
    }
}
$forbiddenArguments = if ($isNoNagRun) {
    @('--nologo', '--norestore', '--headless', '--invisible', '--nodefault')
}
else {
    @('--headless', '--invisible', '--nodefault')
}
foreach ($forbiddenArgument in $forbiddenArguments) {
    $forbiddenArgumentMatches = @($applicationArguments | Where-Object {
        $argumentValue = [string]$_
        $argumentValue.Equals(
            $forbiddenArgument,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or $argumentValue.StartsWith(
            "$forbiddenArgument=",
            [System.StringComparison]::OrdinalIgnoreCase
        )
    })
    Assert-Evidence ($forbiddenArgumentMatches.Count -eq 0) `
        "GUI evidence cannot use $forbiddenArgument."
}
foreach ($field in @(
    'application.isolated_profile_root',
    'application.user_profile_root'
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
$profileConfiguration = Get-RequiredEvidenceValue $evidence `
    'application.profile_configuration'
$hasExtendedProfileContract = $evidence.application.PSObject.Properties.Name `
    -contains 'profile_prelaunch_entry_count'
if (-not $hasExtendedProfileContract) {
    Assert-Evidence (-not $isNoNagRun) `
        'No-nag evidence must record the extended disposable-profile contract.'
    Assert-Hash ([string](Get-RequiredEvidenceValue $evidence `
        'application.profile_configuration.sha256')) `
        'application.profile_configuration.sha256'
    Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
        'application.profile_configuration.retained_in_public_evidence')) `
        'The generated profile must remain runtime-only.'
}
else {
    $profilePrelaunchEntryCount = Get-RequiredEvidenceInteger $evidence `
        'application.profile_prelaunch_entry_count'
    $profileSeedArtifacts = @(Get-RequiredEvidenceValue $evidence `
        'application.profile_seed_artifacts')
    $seededLegacyTriggers = @(Get-RequiredEvidenceValue $evidence `
        'application.seeded_legacy_triggers')
    $legacyCrashSeeded = Get-RequiredEvidenceBoolean $evidence `
        'application.legacy_crash_seeded'
    $legacyCrashConfiguration = Get-RequiredEvidenceValue $evidence `
        'application.legacy_crash_configuration'
    if ($startupProfile -ceq 'fresh') {
        Assert-Evidence ($profilePrelaunchEntryCount -eq 0) `
            'Fresh no-nag profile must be empty immediately before launch.'
        Assert-Evidence ($null -eq $profileConfiguration) `
            'Fresh no-nag evidence must not generate registrymodifications.xcu.'
        Assert-Evidence ($profileSeedArtifacts.Count -eq 0 -and
            $seededLegacyTriggers.Count -eq 0 -and -not $legacyCrashSeeded -and
            $null -eq $legacyCrashConfiguration) `
            'Fresh no-nag evidence cannot contain legacy seeds.'
    }
    else {
        Assert-Hash ([string](Get-RequiredEvidenceValue $evidence `
            'application.profile_configuration.sha256')) `
            'application.profile_configuration.sha256'
        Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
            'application.profile_configuration.path') -ceq
            'profile/user/registrymodifications.xcu') `
            'Profile configuration must use its runtime-only profile path.'
        Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
            'application.profile_configuration.retained_in_public_evidence')) `
            'The generated profile must remain runtime-only.'
    }
    if ($startupProfile -ceq 'legacy') {
        Assert-Evidence ($profilePrelaunchEntryCount -eq 2 -and $legacyCrashSeeded) `
            'Legacy no-nag evidence must preserve exactly its user/crash seeds.'
        Assert-Evidence ($profileSeedArtifacts.Count -eq 2) `
            'Legacy no-nag evidence must retain two sanitized seed artifacts.'
        Assert-Hash ([string](Get-RequiredEvidenceValue $evidence `
            'application.legacy_crash_configuration.sha256')) `
            'application.legacy_crash_configuration.sha256'
        Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
            'application.legacy_crash_configuration.path') -ceq
            'profile/crash/dump.ini' -and
            -not (Get-RequiredEvidenceBoolean $evidence `
                'application.legacy_crash_configuration.retained_in_public_evidence')) `
            'Legacy crash configuration must be hash-bound and runtime-only.'
        foreach ($requiredLegacyTrigger in @(
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
        )) {
            Assert-Evidence ($seededLegacyTriggers -ccontains $requiredLegacyTrigger) `
                "Legacy no-nag seed is missing '$requiredLegacyTrigger'."
        }
        Assert-Evidence (@($seededLegacyTriggers | Select-Object -Unique).Count -eq
            $seededLegacyTriggers.Count) `
            'Legacy no-nag trigger identities must be unique and path-qualified.'
        foreach ($seedArtifact in $profileSeedArtifacts) {
            Assert-Hash ([string]$seedArtifact.sha256) 'legacy seed SHA-256'
            $seedPath = Resolve-RunArtifactPath -ManifestRoot $manifestRoot `
                -RelativePath ([string]$seedArtifact.path) -ExpectedDirectory 'logs'
            Assert-ArtifactFileIdentity -ArtifactPath $seedPath -Record $seedArtifact `
                -Description 'Legacy no-nag sanitized seed'
        }
    }
}
Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
    'application.arguments_path_tokenized') `
    'Application arguments must use public-safe run-root tokens.'
Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
    'application.launch_wrapper.retained_in_public_evidence')) `
    'The path-bearing launch wrapper must remain runtime-only.'

Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'environment.VCL_DRAW_WIDGETS_FROM_FILE') -ceq '1') `
    'VCL_DRAW_WIDGETS_FROM_FILE must be exactly 1.'
Assert-Evidence ((Get-RequiredEvidenceValue $evidence `
    'environment.VCL_FILE_WIDGET_THEME') -ceq 'material') `
    'VCL_FILE_WIDGET_THEME must be exactly material.'
if ($isNoNagRun) {
    Assert-Evidence ([string](Get-RequiredEvidenceValue $evidence `
        'environment.CRASH_DUMP_ENABLE') -ceq '<cleared-before-launch>') `
        'No-nag evidence must clear any inherited truthy crash-dump override.'
    Assert-Evidence ($applicationArguments -ccontains '-env:CrashDumpEnable=false') `
        'No-nag evidence must disable dump creation through the bootstrap value.'
}

$hasNoNagContract = $evidence.PSObject.Properties.Name -contains 'no_nag_contract'
if (-not $hasNoNagContract) {
    Assert-Evidence (-not $isNoNagRun) `
        'No-nag evidence must include no_nag_contract.'
}
else {
    $noNagEnabled = Get-RequiredEvidenceBoolean $evidence 'no_nag_contract.enabled'
    Assert-Evidence ($noNagEnabled -eq $isNoNagRun) `
        'no_nag_contract.enabled contradicts application.startup_profile.'
}
if ($isNoNagRun) {
    $observationSeconds = Get-RequiredEvidenceInteger $evidence `
        'no_nag_contract.observation_seconds'
    $observationElapsedMilliseconds = Get-RequiredEvidenceInteger $evidence `
        'no_nag_contract.observation_elapsed_milliseconds'
    $observationStartedAt = Get-RequiredEvidenceTimestamp $evidence `
        'no_nag_contract.observation_started_at_utc'
    $observationCompletedAt = Get-RequiredEvidenceTimestamp $evidence `
        'no_nag_contract.observation_completed_at_utc'
    Assert-Evidence ($observationSeconds -ge 15) `
        'No-nag observation must run for at least 15 seconds.'
    Assert-Evidence ($observationElapsedMilliseconds -ge ($observationSeconds * 1000)) `
        'No-nag monotonic observation duration is shorter than the declared minimum.'
    Assert-Evidence ($observationCompletedAt -ge $observationStartedAt) `
        'No-nag observation completion precedes its start timestamp.'
    Assert-Evidence ((Get-RequiredEvidenceInteger $evidence `
        'no_nag_contract.poll_interval_milliseconds') -eq 500) `
        'No-nag polling must retain its 500-millisecond inter-poll delay.'
    Assert-Evidence ((Get-RequiredEvidenceInteger $evidence `
        'no_nag_contract.startup_poll_count') -gt 0 -and
        (Get-RequiredEvidenceInteger $evidence `
            'no_nag_contract.observation_poll_count') -gt 1) `
        'No-nag evidence must include startup and stable-observation polls.'
    Assert-Evidence (@(Get-RequiredEvidenceValue $evidence `
        'no_nag_contract.denied_text_matches').Count -eq 0) `
        'No-nag evidence recorded former nag text.'
    $formerNagDenylist = @(Get-RequiredEvidenceValue $evidence `
        'no_nag_contract.former_nag_denylist')
    $retainedSafetyPrompts = @(Get-RequiredEvidenceValue $evidence `
        'no_nag_contract.retained_safety_prompts')
    foreach ($requiredDeniedText in @(
        'Tip of the Day', "What's new in", 'Welcome to',
        'for the first time', 'Please take a moment to personalize your settings',
        'You are running version',
        'Default file formats not registered', 'Crash Report',
        'Support the development', 'Help us make',
        'Autocorrection has removed a leading or trailing character'
    )) {
        Assert-Evidence ($formerNagDenylist -ccontains $requiredDeniedText) `
            "No-nag denylist is missing '$requiredDeniedText'."
    }
    foreach ($requiredSafetyPrompt in @(
        'Document Recovery', 'Troubleshoot Mode', 'Incompatible Extensions',
        'Extension Dependencies', 'Macros disabled', 'Security Warning',
        'Hidden Information', 'read-only mode', 'Master Password',
        'Password Required', 'Extension Update'
    )) {
        Assert-Evidence ($retainedSafetyPrompts -ccontains $requiredSafetyPrompt) `
            "No-nag evidence does not preserve '$requiredSafetyPrompt' as an allowed safety prompt."
    }
    $denyKeys = @($formerNagDenylist | ForEach-Object {
        if ([string]::IsNullOrWhiteSpace([string]$_)) {
            throw 'No-nag denylist contains a blank entry.'
        }
        ([string]$_).ToLowerInvariant()
    })
    $safetyKeys = @($retainedSafetyPrompts | ForEach-Object {
        if ([string]::IsNullOrWhiteSpace([string]$_)) {
            throw 'Retained safety-prompt list contains a blank entry.'
        }
        ([string]$_).ToLowerInvariant()
    })
    Assert-Evidence (@($denyKeys | Select-Object -Unique).Count -eq $denyKeys.Count) `
        'No-nag denylist contains duplicate entries.'
    Assert-Evidence (@($safetyKeys | Select-Object -Unique).Count -eq $safetyKeys.Count) `
        'Retained safety-prompt list contains duplicate entries.'
    Assert-Evidence (@($safetyKeys | Where-Object { $denyKeys -contains $_ }).Count -eq 0) `
        'Retained safety prompts must remain disjoint from the former-nag denylist.'
    foreach ($requiredManualAction in @(
        '.uno:TipOfTheDay', '.uno:WhatsNew',
        '.uno:OptionsTreeDialog / OptionsPageID 17100'
    )) {
        Assert-Evidence (@(Get-RequiredEvidenceValue $evidence `
            'no_nag_contract.retained_manual_actions') -ccontains $requiredManualAction) `
            "No-nag evidence is missing retained manual action '$requiredManualAction'."
    }
    Assert-Evidence (-not (Get-RequiredEvidenceBoolean $evidence `
        'no_nag_contract.automatic_file_association_runtime_covered')) `
        'Extracted-payload no-nag evidence cannot claim registry-gated association runtime coverage.'
    $associationLimitation = [string](Get-RequiredEvidenceValue $evidence `
        'no_nag_contract.extracted_msi_association_limitation')
    Assert-Evidence ($associationLimitation -match 'HKLM' -and
        $associationLimitation -match 'Sandbox|VM' -and
        $associationLimitation -match 'does not runtime-prove') `
        'Extracted-MSI association limitation must be explicit and actionable.'
}

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
if ($isNoNagRun) {
    $listenerPid = Get-RequiredEvidenceInteger $evidence 'driver.listener_process.pid'
    $listenerCreationTicks = Get-RequiredEvidenceInteger $evidence `
        'driver.listener_process.creation_ticks'
    $listenerPort = Get-RequiredEvidenceInteger $evidence `
        'driver.listener_process.local_port'
    $mcpUri = [Uri]([string]$evidence.driver.mcp_url)
    Assert-Evidence ($listenerPid -gt 0 -and $listenerCreationTicks -gt 0 -and
        $listenerPort -eq $mcpUri.Port -and
        [string](Get-RequiredEvidenceValue $evidence `
            'driver.listener_process.local_address') -ceq '127.0.0.1' -and
        (Get-RequiredEvidenceBoolean $evidence `
            'driver.listener_process.ancestry_validated_to_server_pid')) `
        'Dedicated listener identity/ancestry does not match the loopback MCP endpoint.'
}

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
$windowThreadId = Get-RequiredEvidenceInteger $evidence 'window.thread_id'
$windowHandle = Get-RequiredEvidenceInteger $evidence 'window.handle'
$windowWidth = [int](Get-RequiredEvidenceValue $evidence 'window.width')
$windowHeight = [int](Get-RequiredEvidenceValue $evidence 'window.height')
$windowDpi = Get-RequiredEvidenceInteger $evidence 'window.dpi'
Assert-Evidence ($windowProcessId -eq $ownedPid -and $windowHandle -gt 0 -and
    $windowThreadId -gt 0) `
    'Resolved window ownership/thread identity does not match the exact payload PID.'
Assert-Evidence ($windowWidth -gt 0 -and $windowHeight -gt 0 -and
    [int](Get-RequiredEvidenceValue $evidence 'window.stable_poll_count') -ge 3) `
    'Resolved window dimensions or stability proof is invalid.'
Assert-Evidence ((-not [string]::IsNullOrWhiteSpace(
    [string](Get-RequiredEvidenceValue $evidence 'window.title')
)) -and ((Get-RequiredEvidenceValue $evidence 'window.class') -ceq 'SALFRAME')) `
    'Resolved window title/class metadata is invalid.'
Assert-Evidence ($windowDpi -eq $dpi) `
    'Resolved window DPI differs from the recorded display scale.'

if ($isNoNagRun) {
    $windowPollRecord = Get-RequiredEvidenceValue $evidence `
        'no_nag_contract.window_poll_log'
    Assert-Hash ([string]$windowPollRecord.sha256) 'no-nag window poll log SHA-256'
    $windowPollPath = Resolve-RunArtifactPath -ManifestRoot $manifestRoot `
        -RelativePath ([string]$windowPollRecord.path) -ExpectedDirectory 'logs'
    Assert-ArtifactFileIdentity -ArtifactPath $windowPollPath -Record $windowPollRecord `
        -Description 'No-nag window poll log'
    $windowPollText = Get-Content -LiteralPath $windowPollPath -Raw
    if ($windowPollText -match '(?i)[A-Z]:(?:\\\\|/)Users(?:\\\\|/)') {
        throw 'No-nag window poll log contains a private Windows user-profile path.'
    }
    try {
        $windowPollReport = $windowPollText | ConvertFrom-Json
    }
    catch {
        throw "No-nag window poll log is invalid JSON: $($_.Exception.Message)"
    }
    Assert-Evidence ([string](Get-RequiredEvidenceValue $windowPollReport 'run_id') -ceq
        [string]$evidence.run_id) 'No-nag window poll log run_id differs from the manifest.'
    Assert-Evidence ((Get-RequiredEvidenceInteger $windowPollReport `
        'owned_process_id') -eq $ownedPid) `
        'No-nag window poll log ownership PID differs from the manifest.'
    Assert-Evidence ([string](Get-RequiredEvidenceValue $windowPollReport `
            'observation_started_at_utc') -ceq
            [string]$evidence.no_nag_contract.observation_started_at_utc -and
        [string](Get-RequiredEvidenceValue $windowPollReport `
            'observation_completed_at_utc') -ceq
            [string]$evidence.no_nag_contract.observation_completed_at_utc -and
        (Get-RequiredEvidenceInteger $windowPollReport `
            'observation_elapsed_milliseconds') -eq
            $observationElapsedMilliseconds) `
        'No-nag poll-log observation duration differs from the manifest.'
    $windowPolls = @(Get-RequiredEvidenceValue $windowPollReport 'polls')
    $startupPolls = @($windowPolls | Where-Object { [string]$_.phase -ceq 'startup' })
    $observationPolls = @($windowPolls | Where-Object {
        [string]$_.phase -ceq 'no-nag-observation'
    })
    Assert-Evidence ($startupPolls.Count -eq [int](Get-RequiredEvidenceValue $evidence `
            'no_nag_contract.startup_poll_count') -and
        $observationPolls.Count -eq [int](Get-RequiredEvidenceValue $evidence `
            'no_nag_contract.observation_poll_count')) `
        'No-nag poll counts differ between the manifest and retained log.'
    $previousPollTimestamp = $null
    $observationPhaseSeen = $false
    foreach ($poll in $windowPolls) {
        Assert-Evidence (@('startup', 'no-nag-observation') -ccontains
            [string]$poll.phase) 'No-nag poll log contains an unknown phase.'
        if ([string]$poll.phase -ceq 'no-nag-observation') {
            $observationPhaseSeen = $true
        }
        else {
            Assert-Evidence (-not $observationPhaseSeen) `
                'No-nag startup polls cannot appear after observation begins.'
        }
        $pollTimestamp = Get-RequiredEvidenceTimestamp $poll 'captured_at_utc'
        if ($null -ne $previousPollTimestamp) {
            Assert-Evidence ($pollTimestamp -ge $previousPollTimestamp) `
                'No-nag poll timestamps are not monotonic.'
        }
        $previousPollTimestamp = $pollTimestamp
        $pollWindows = @($poll.windows)
        Assert-Evidence ((Get-RequiredEvidenceInteger $poll `
            'desktop_window_count') -eq $pollWindows.Count) `
            'No-nag poll desktop-window count is inconsistent.'
        foreach ($pollWindow in $pollWindows) {
            foreach ($deniedText in $formerNagDenylist) {
                Assert-Evidence ([string]$pollWindow.title -notmatch
                    [regex]::Escape([string]$deniedText)) `
                    "No-nag desktop window title contains '$deniedText'."
            }
        }
        $ownedPollWindows = [System.Collections.Generic.List[object]]::new()
        foreach ($pollWindow in $pollWindows) {
            $recordedOwned = Get-RequiredEvidenceBoolean $pollWindow 'payload_owned'
            $pollProcessId = $pollWindow.process_id
            $shouldBeOwned = $false
            if ($null -ne $pollProcessId) {
                $shouldBeOwned = ((Get-RequiredEvidenceInteger $pollWindow `
                    'process_id') -eq $ownedPid)
            }
            Assert-Evidence ($recordedOwned -eq $shouldBeOwned) `
                'No-nag poll contains a forged or missing payload-ownership marker.'
            if ($recordedOwned) { $ownedPollWindows.Add($pollWindow) }
        }
        Assert-Evidence ((Get-RequiredEvidenceInteger $poll `
            'payload_owned_window_count') -eq $ownedPollWindows.Count) `
            'No-nag poll payload-window count is inconsistent.'
        foreach ($ownedPollWindow in $ownedPollWindows) {
            Assert-Evidence ((Get-RequiredEvidenceInteger $ownedPollWindow `
                'process_id') -eq $ownedPid -and
                (Get-RequiredEvidenceInteger $ownedPollWindow 'handle') -gt 0) `
                'No-nag poll marks a window owned by the wrong process or HWND.'
        }
    }
    foreach ($poll in $observationPolls) {
        Assert-Evidence ((Get-RequiredEvidenceInteger $poll `
                'desktop_window_count') -eq 1 -and
            (Get-RequiredEvidenceInteger $poll `
                'payload_owned_window_count') -eq 1) `
            'Every no-nag observation poll must contain exactly one total/owned window.'
        $ownedPollWindows = @($poll.windows | Where-Object {
            (Get-RequiredEvidenceBoolean $_ 'payload_owned')
        })
        Assert-Evidence ($ownedPollWindows.Count -eq 1) `
            'No-nag observation ownership markers are inconsistent.'
        $ownedPollWindow = $ownedPollWindows[0]
        Assert-Evidence ((Get-RequiredEvidenceInteger $ownedPollWindow 'handle') -eq
                $windowHandle -and
            (Get-RequiredEvidenceInteger $ownedPollWindow 'process_id') -eq
                $windowProcessId -and
            (Get-RequiredEvidenceInteger $ownedPollWindow 'thread_id') -eq
                $windowThreadId -and
            (Get-RequiredEvidenceInteger $ownedPollWindow 'dpi') -eq $windowDpi -and
            (Get-RequiredEvidenceInteger $ownedPollWindow 'width') -eq $windowWidth -and
            (Get-RequiredEvidenceInteger $ownedPollWindow 'height') -eq $windowHeight -and
            [string]$ownedPollWindow.class -ceq 'SALFRAME' -and
            [string]$ownedPollWindow.title -ceq [string]$evidence.window.title) `
            'No-nag observation did not retain the exact Writer PID/HWND/thread/DPI/geometry/title.'
    }
    Assert-Evidence ((Get-RequiredEvidenceTimestamp $observationPolls[0] `
            'captured_at_utc') -ge $observationStartedAt -and
        (Get-RequiredEvidenceTimestamp $observationPolls[-1] `
            'captured_at_utc') -le $observationCompletedAt) `
        'No-nag observation poll timestamps fall outside the declared interval.'
}

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
        Assert-Evidence ((Get-RequiredEvidenceInteger $scenario `
                'checkpoint.window_handle') -eq $windowHandle -and
            (Get-RequiredEvidenceInteger $scenario `
                'checkpoint.window_process_id') -eq $windowProcessId -and
            (Get-RequiredEvidenceInteger $scenario `
                'checkpoint.window_thread_id') -eq $windowThreadId -and
            (Get-RequiredEvidenceInteger $scenario `
                'checkpoint.window_dpi') -eq $windowDpi -and
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
            if ($isNoNagRun) {
                $visibleA11yText = [System.Collections.Generic.List[string]]::new()
                foreach ($a11yNode in @(Get-RequiredEvidenceValue $a11yReport 'nodes')) {
                    if (@($a11yNode.states) -notcontains 'VISIBLE' -and
                        @($a11yNode.states) -notcontains 'SHOWING') {
                        continue
                    }
                    foreach ($propertyName in @('name', 'description')) {
                        $property = $a11yNode.PSObject.Properties[$propertyName]
                        if ($null -ne $property -and
                            -not [string]::IsNullOrWhiteSpace([string]$property.Value)) {
                            $visibleA11yText.Add([string]$property.Value)
                        }
                    }
                }
                foreach ($deniedText in $formerNagDenylist) {
                    foreach ($observedText in $visibleA11yText) {
                        Assert-Evidence ($observedText.IndexOf(
                                [string]$deniedText,
                                [System.StringComparison]::OrdinalIgnoreCase
                            ) -lt 0) `
                            "Scenario '$($scenario.id)' a11y tree contains former nag text '$deniedText'."
                    }
                }
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
            if ($isNoNagRun) {
                Assert-Evidence ([string]$scenario.id -ceq
                    "E-NONAG-$($startupProfile.ToUpperInvariant())") `
                    'No-nag scenario ID does not identify its startup profile.'
                Assert-Evidence (Get-RequiredEvidenceBoolean $scenario.checkpoint `
                    'normal_uno_termination_requested') `
                    'No-nag final scenario must request normal UNO termination.'
                Assert-Evidence (@(Get-RequiredEvidenceValue $scenario `
                    'no_nag.denied_text_matches').Count -eq 0) `
                    'No-nag scenario recorded denied accessibility text.'
                Assert-Evidence ([string](Get-RequiredEvidenceValue $scenario `
                    'no_nag.retained_safety_prompt_policy') -ceq
                    'not part of the former-nag denylist') `
                    'No-nag scenario must distinguish retained safety prompts from former nags.'
                Assert-Evidence (@($a11yReport.nodes | Where-Object {
                    [string]$_.role.name -ceq 'MENU_BAR'
                }).Count -gt 0) 'No-nag Writer a11y tree contains no menu bar.'
                foreach ($node in @($a11yReport.nodes)) {
                    if (@($node.states) -notcontains 'VISIBLE' -and
                        @($node.states) -notcontains 'SHOWING') {
                        continue
                    }
                    $nodeText = @([string]$node.name, [string]$node.description) -join "`n"
                    foreach ($deniedText in @(Get-RequiredEvidenceValue $evidence `
                        'no_nag_contract.former_nag_denylist')) {
                        Assert-Evidence ($nodeText -notmatch
                            [regex]::Escape([string]$deniedText)) `
                            "No-nag a11y tree contains '$deniedText'."
                    }
                }
            }
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
    if ($isNoNagRun) {
        Assert-Evidence (Get-RequiredEvidenceBoolean $evidence `
            'cleanup.dedicated_driver_endpoint_closed') `
            'The dedicated MCP listener remained reachable after cleanup.'
        Get-RequiredEvidenceBoolean $evidence `
            'cleanup.dedicated_listener_forced_cleanup' | Out-Null
    }
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
