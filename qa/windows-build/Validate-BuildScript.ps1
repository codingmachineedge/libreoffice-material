#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$buildScriptPath = Join-Path $repoRoot 'bin\Build-Windows.ps1'
$failures = New-Object 'System.Collections.Generic.List[string]'

function Add-Failure {
    param([Parameter(Mandatory)][string]$Message)
    $script:failures.Add($Message)
}

if (-not (Test-Path -LiteralPath $buildScriptPath -PathType Leaf)) {
    Add-Failure -Message "Build script is missing: $buildScriptPath"
}
else {
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $buildScriptPath, [ref]$tokens, [ref]$parseErrors)
    foreach ($parseError in $parseErrors) {
        Add-Failure -Message (
            'PowerShell parse error at line {0}: {1}' -f
            $parseError.Extent.StartLineNumber, $parseError.Message)
    }

    $packagingFunctions = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq 'Invoke-MsiPackagingValidation'
    }, $true))
    if ($packagingFunctions.Count -ne 1) {
        Add-Failure -Message (
            'Expected exactly one Invoke-MsiPackagingValidation function; found {0}.' -f
            $packagingFunctions.Count)
    }
    else {
        $packagingText = $packagingFunctions[0].Extent.Text
        if ($packagingText -match '(?m)^\s*&\s*\$msiexec\b') {
            Add-Failure -Message (
                'Administrative extraction must not directly invoke msiexec; its GUI client can detach.')
        }
        foreach ($requiredPattern in @(
            '\$extractArguments\s*=\s*@\(',
            '\$extractCommandLine\s*=\s*Join-WindowsCommandLine\s+\$extractArguments',
            'Start-Process\s+-FilePath\s+\$msiexec',
            '-ArgumentList\s+\$extractCommandLine',
            '-WindowStyle\s+Hidden',
            '-Wait',
            '-PassThru',
            '\$extractExitCode\s*=\s*\[int\]\$extractProcess\.ExitCode'
        )) {
            if ($packagingText -notmatch $requiredPattern) {
                Add-Failure -Message "Administrative extraction is missing invariant: $requiredPattern"
            }
        }

        $startIndex = $packagingText.IndexOf('Start-Process', [StringComparison]::Ordinal)
        $payloadIndex = $packagingText.IndexOf('$soffice =', [StringComparison]::Ordinal)
        if ($startIndex -lt 0 -or $payloadIndex -lt 0 -or $startIndex -ge $payloadIndex) {
            Add-Failure -Message (
                'The waited administrative extraction must precede payload inspection.')
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Host 'Windows build wrapper static validation: PASS' -ForegroundColor Green
