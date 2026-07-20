[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PayloadRoot,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceCommit,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Fresh', 'Legacy')]
    [string]$ProfileMode,

    [string]$SourceRoot = '',

    [string]$DriverRoot = '',

    [string]$OutputRoot = '',

    [string]$RunId = '',

    [ValidateRange(15, 120)]
    [int]$ObservationSeconds = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$runner = Join-Path $PSScriptRoot 'Run-Windows-Headless-Smoke.ps1'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Shared Windows headless runner is missing: $runner"
}

$forward = @{
    PayloadRoot = $PayloadRoot
    SourceCommit = $SourceCommit
    StartupProfile = $ProfileMode
    ObservationSeconds = $ObservationSeconds
    EvidenceEntrypointPath = $PSCommandPath
}
if ($SourceRoot) { $forward.SourceRoot = $SourceRoot }
if ($DriverRoot) { $forward.DriverRoot = $DriverRoot }
if ($OutputRoot) { $forward.OutputRoot = $OutputRoot }
if ($RunId) { $forward.RunId = $RunId }

# The shared engine owns launch argument construction. This entrypoint selects
# only the fresh/legacy no-nag policy and cannot add UI-suppression switches.
& $runner @forward
