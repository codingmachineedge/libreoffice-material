#requires -Version 5.1
<#
.SYNOPSIS
    One-click bootstrap and Windows x64 MSI build for LibreOffice Material.

.DESCRIPTION
    The default All phase provisions a dedicated Visual Studio 2022 Build Tools
    and Cygwin toolchain when needed, verifies the exact build prerequisites,
    creates an LF-only detached source snapshot, then configures, tests, builds,
    and structurally validates the final MSI.

    It never alters the active checkout, deletes a build root, installs the
    resulting MSI, launches LibreOffice, reboots Windows, or force-closes a
    process. An interrupted build may be continued only with -Resume after its
    saved source state matches exactly.
#>
[CmdletBinding()]
param(
    [ValidateSet('All', 'Preflight', 'Bootstrap', 'Configure', 'Tests', 'Build', 'Package')]
    [string] $Phase = 'All',

    [ValidateRange(1, 64)]
    [int] $Jobs = 3,

    [ValidateNotNullOrEmpty()]
    [string] $ToolRoot = (Join-Path $env:ProgramData 'LibreOfficeMaterialTools'),

    [ValidateNotNullOrEmpty()]
    [string] $BuildRoot = (Join-Path $env:LOCALAPPDATA 'LibreOfficeMaterialBuild'),

    [ValidateRange(40, 4096)]
    [int] $MinimumFreeGiB = 80,

    [switch] $NoBootstrap,

    [switch] $Resume
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$script:ToolRoot = [IO.Path]::GetFullPath($ToolRoot).TrimEnd('\')
$script:BuildRoot = [IO.Path]::GetFullPath($BuildRoot).TrimEnd('\')
$script:VsInstallPath = Join-Path $script:ToolRoot 'VS2022'
$script:CygwinRoot = Join-Path $script:ToolRoot 'cygwin64'
$script:BootstrapDirectory = Join-Path $script:ToolRoot 'bootstrap'
$script:SourceSnapshot = Join-Path $script:BuildRoot 'source'
$script:BuildDirectory = Join-Path $script:BuildRoot 'build'
$script:TarballDirectory = Join-Path $script:BuildRoot 'tarballs'
$script:LogsDirectory = Join-Path $script:BuildRoot 'logs'
$script:StatePath = Join-Path $script:BuildRoot 'build-state.json'
$script:BootstrapManifestPath = Join-Path $script:ToolRoot 'bootstrap-manifest.json'
$script:Git = $null
$script:DownloadRecords = New-Object 'System.Collections.Generic.List[object]'

$script:RequiredVsComponents = @(
    'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    'Microsoft.VisualStudio.Component.VC.ATL',
    'Microsoft.VisualStudio.Component.VC.Redist.MSM',
    'Microsoft.VisualStudio.Component.VC.CMake.Project'
)

$script:VsBootstrapComponents = @(
    'Microsoft.VisualStudio.Workload.VCTools',
    'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
    'Microsoft.VisualStudio.Component.VC.ATL',
    'Microsoft.VisualStudio.Component.VC.Redist.MSM',
    'Microsoft.VisualStudio.Component.VC.CMake.Project',
    'Microsoft.VisualStudio.Component.Windows11SDK.26100',
    'Microsoft.Net.Component.4.8.1.SDK',
    'Microsoft.Net.ComponentGroup.4.8.1.DeveloperTools'
)

$script:CygwinPackages = @(
    'autoconf', 'automake', 'bison', 'cabextract', 'diffutils', 'file',
    'flex', 'gawk', 'gettext-devel', 'git', 'gperf', 'libxml2-devel',
    'libxslt', 'make', 'nasm', 'ninja', 'patch', 'perl', 'perl-Archive-Zip',
    'perl-Font-TTF', 'perl-IO-String', 'pkg-config', 'python3', 'rsync',
    'unzip', 'wget', 'which', 'zip'
)

$script:LibreOfficeTools = @(
    [pscustomobject]@{
        Name = 'make.exe'
        Url = 'https://dev-www.libreoffice.org/bin/cygwin/make-4.2.1-msvc.exe'
        Sha256 = '146d6f2b0ea57647b11b506a95048a7be73232e1feeeccbc1013651f992423d8'
    },
    [pscustomobject]@{
        Name = 'pkgconf-2.4.3.exe'
        Url = 'https://dev-www.libreoffice.org/extern/pkgconf-2.4.3.exe'
        Sha256 = '791cd6dbc56f7268fbf9c4652d6634b0f5c59687ab4e504565e58245952edd41'
    }
)

function Write-Section {
    param([Parameter(Mandatory)][string] $Message)

    Write-Host ''
    Write-Host ('=== {0} ===' -f $Message) -ForegroundColor Cyan
}

function Get-FullPath {
    param([Parameter(Mandatory)][string] $Path)

    [IO.Path]::GetFullPath($Path).TrimEnd('\')
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function New-RequiredDirectory {
    param([Parameter(Mandatory)][string] $Path)

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        throw ('Expected a directory but found a file: {0}' -f $Path)
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-Item -ItemType Directory -Path $Path -ErrorAction Stop | Out-Null
    }
}

function Get-GitExecutable {
    $command = Get-Command git.exe -ErrorAction SilentlyContinue
    if (-not $command) {
        $command = Get-Command git -ErrorAction SilentlyContinue
    }
    if (-not $command) {
        throw 'Git for Windows is required to create and verify the isolated LF source snapshot.'
    }
    $command.Source
}

function Invoke-Git {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $output = @(& $script:Git @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw ('git {0} failed with exit code {1}.' -f ($Arguments -join ' '), $LASTEXITCODE)
    }
    $output
}

function Assert-CleanSourceCheckout {
    $reportedRoot = (Invoke-Git @('-C', $script:RepositoryRoot, 'rev-parse', '--show-toplevel') | Select-Object -First 1).Trim()
    if ((Get-FullPath $reportedRoot) -ine (Get-FullPath $script:RepositoryRoot)) {
        throw ('Script repository root differs from Git root: {0}' -f $reportedRoot)
    }

    $changes = @(Invoke-Git @('-C', $script:RepositoryRoot, 'status', '--porcelain=v1', '--untracked-files=all'))
    if ($changes.Count -gt 0) {
        throw 'The active source checkout is not clean. Commit or preserve its changes before building; the script will not snapshot an ambiguous worktree.'
    }

    $commit = (Invoke-Git @('-C', $script:RepositoryRoot, 'rev-parse', '--verify', 'HEAD') | Select-Object -First 1).Trim()
    if ($commit -notmatch '^[0-9a-f]{40}$') {
        throw ('Git did not return a full source commit: {0}' -f $commit)
    }
    $commit
}

function Test-PendingReboot {
    foreach ($key in @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    )) {
        if (Test-Path -LiteralPath $key) {
            return $true
        }
    }
    try {
        $sessionManager = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -ErrorAction Stop
        if ($null -ne $sessionManager.PendingFileRenameOperations) {
            return $true
        }
    }
    catch {
        # A missing value is normal.
    }
    $false
}

function Get-VsWherePath {
    $programFilesX86 = [Environment]::GetFolderPath('ProgramFilesX86')
    $path = Join-Path $programFilesX86 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $path
    }
}

function Get-DedicatedVisualStudio {
    $vswhere = Get-VsWherePath
    if (-not $vswhere) {
        return $null
    }

    $candidates = @(& $vswhere -all -version '[17.0,18.0)' -products '*' -requires $script:RequiredVsComponents -property installationPath)
    if ($LASTEXITCODE -ne 0) {
        throw ('vswhere failed with exit code {0}.' -f $LASTEXITCODE)
    }

    $expectedPath = Get-FullPath $script:VsInstallPath
    $installationPath = $candidates | Where-Object {
        $_ -and ((Get-FullPath $_.Trim()) -ieq $expectedPath)
    } | Select-Object -First 1
    if (-not $installationPath) {
        return $null
    }

    $installationPath = Get-FullPath $installationPath.Trim()
    $cmake = Join-Path $installationPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    $atl = Get-ChildItem -LiteralPath (Join-Path $installationPath 'VC\Tools\MSVC') -Recurse -Filter 'atlbase.h' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    $redistRoot = Join-Path $installationPath 'VC\Redist\MSVC'
    $msmX86 = Get-ChildItem -LiteralPath $redistRoot -Recurse -Filter 'Microsoft_VC143_CRT_x86.msm' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    $msmX64 = Get-ChildItem -LiteralPath $redistRoot -Recurse -Filter 'Microsoft_VC143_CRT_x64.msm' -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not (Test-Path -LiteralPath $cmake -PathType Leaf) -or -not $atl -or -not $msmX86 -or -not $msmX64) {
        return $null
    }

    [pscustomobject]@{
        InstallationPath = $installationPath
        CMake = $cmake
        AtlHeader = $atl.FullName
        MsmX86 = $msmX86.FullName
        MsmX64 = $msmX64.FullName
    }
}

function Get-CompleteWindowsSdk {
    try {
        $kitsRoot = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' -ErrorAction Stop).KitsRoot10
    }
    catch {
        return $null
    }
    if (-not $kitsRoot -or -not (Test-Path -LiteralPath $kitsRoot -PathType Container)) {
        return $null
    }

    $binRoot = Join-Path $kitsRoot 'bin'
    if (-not (Test-Path -LiteralPath $binRoot -PathType Container)) {
        return $null
    }

    $candidates = Get-ChildItem -LiteralPath $binRoot -Directory -ErrorAction Stop |
        Where-Object { $_.Name -match '^10\.0\.\d+\.0$' } |
        Sort-Object { [version]$_.Name } -Descending
    foreach ($candidate in $candidates) {
        $version = $candidate.Name
        $required = @(
            (Join-Path $kitsRoot ('Include\{0}\um\adoint.h' -f $version)),
            (Join-Path $kitsRoot ('Include\{0}\um\SqlUcode.h' -f $version)),
            (Join-Path $kitsRoot ('Include\{0}\um\usp10.h' -f $version)),
            (Join-Path $kitsRoot ('Lib\{0}\um\x64\user32.lib' -f $version)),
            (Join-Path $kitsRoot ('bin\{0}\x64\midl.exe' -f $version)),
            (Join-Path $kitsRoot ('bin\{0}\x86\MsiInfo.exe' -f $version)),
            (Join-Path $kitsRoot ('bin\{0}\x86\MsiDb.exe' -f $version)),
            (Join-Path $kitsRoot ('bin\{0}\x86\MsiTran.exe' -f $version)),
            (Join-Path $kitsRoot ('bin\{0}\x86\uuidgen.exe' -f $version))
        )
        if (-not ($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })) {
            return [pscustomobject]@{
                Root = $kitsRoot
                Version = $version
                MsiInfo = Join-Path $kitsRoot ('bin\{0}\x86\MsiInfo.exe' -f $version)
            }
        }
    }
    $null
}

function Get-Registry32Value {
    param(
        [Parameter(Mandatory)][Microsoft.Win32.RegistryKey] $Registry,
        [Parameter(Mandatory)][string] $SubKey,
        [Parameter(Mandatory)][string] $Name
    )

    $key = $Registry.OpenSubKey($SubKey)
    if (-not $key) {
        return $null
    }
    try {
        $value = $key.GetValue($Name)
        if ($null -eq $value) {
            return $null
        }
        [string] $value
    }
    finally {
        $key.Dispose()
    }
}

function Get-LegacyCliTools {
    $registry = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry32
    )
    try {
        $cscRoot = Get-Registry32Value $registry 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Client' 'InstallPath'
        $csc = if ($cscRoot) { Join-Path $cscRoot 'csc.exe' } else { $null }
        if (-not $csc -or -not (Test-Path -LiteralPath $csc -PathType Leaf)) {
            return $null
        }

        $al = $null
        $mscoree = $null
        foreach ($version in @('4.8.1', '4.8', '4.7.2', '4.7.1', '4.7', '4.6.2', '4.6.1', '4.6')) {
            $baseKey = 'SOFTWARE\Microsoft\Microsoft SDKs\NETFXSDK\' + $version
            $toolRoot = Get-Registry32Value $registry ($baseKey + '\WinSDK-NetFx40Tools') 'InstallationFolder'
            $alCandidates = @()
            if ($toolRoot) {
                $alCandidates += Join-Path $toolRoot 'al.exe'
                $alCandidates += Join-Path $toolRoot 'bin\al.exe'
            }
            foreach ($candidate in $alCandidates) {
                if (-not $al -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                    $al = $candidate
                }
            }

            $kitsRoot = Get-Registry32Value $registry $baseKey 'KitsInstallationFolder'
            $candidateMscoree = if ($kitsRoot) { Join-Path $kitsRoot 'Lib\um\x64\mscoree.lib' } else { $null }
            if (-not $mscoree -and $candidateMscoree -and (Test-Path -LiteralPath $candidateMscoree -PathType Leaf)) {
                $mscoree = $candidateMscoree
            }
        }

        if (-not $al -or -not $mscoree) {
            return $null
        }
        [pscustomobject]@{
            Csc = $csc
            Al = $al
            Mscoree = $mscoree
        }
    }
    finally {
        $registry.Dispose()
    }
}

function Test-CygwinToolchain {
    $bash = Join-Path $script:CygwinRoot 'bin\bash.exe'
    if (-not (Test-Path -LiteralPath $bash -PathType Leaf)) {
        return [pscustomobject]@{ Ready = $false; Reason = ('Cygwin bash is missing at {0}' -f $bash) }
    }

    $toolDirectory = Join-Path $script:CygwinRoot 'opt\lo\bin'
    foreach ($tool in $script:LibreOfficeTools) {
        $path = Join-Path $toolDirectory $tool.Name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            return [pscustomobject]@{ Ready = $false; Reason = ('LibreOffice tool is missing: {0}' -f $path) }
        }
        $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $tool.Sha256) {
            return [pscustomobject]@{ Ready = $false; Reason = ('LibreOffice tool hash mismatch: {0}' -f $path) }
        }
    }

    $validation = @'
test "$(uname -o)" = Cygwin
export PATH="/opt/lo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
for tool in autoconf automake bison flex gawk gperf nasm ninja patch perl python3 rsync unzip wget zip; do
  command -v "$tool"
done
perl -MArchive::Zip -e 1
perl -MFont::TTF::Font -e 1
/opt/lo/bin/make.exe --version | tee /tmp/libreoffice-material-make-version.txt
grep -q 'Built for Windows' /tmp/libreoffice-material-make-version.txt
/opt/lo/bin/pkgconf-2.4.3.exe --version
test "$(command -v nasm)" = /usr/bin/nasm
nasm_version="$(nasm -v | awk '{ print $3 }')"
printf 'NASM %s\n' "$nasm_version"
test "$(printf '%s\n' 2.16 "$nasm_version" | sort -V | head -n 1)" = 2.16
'@
    & $bash --noprofile --norc -o igncr -eo pipefail -c $validation
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        return [pscustomobject]@{ Ready = $false; Reason = ('Cygwin tool validation failed with exit code {0}.' -f $exitCode) }
    }
    [pscustomobject]@{ Ready = $true; Reason = $null }
}

function Test-HostPrerequisites {
    $errors = New-Object 'System.Collections.Generic.List[string]'
    if (-not [Environment]::Is64BitOperatingSystem) {
        $errors.Add('A 64-bit Windows operating system is required.')
    }
    if (Test-PendingReboot) {
        $errors.Add('Windows has a pending reboot. Reboot manually before a native build.')
    }

    $visualStudio = Get-DedicatedVisualStudio
    if (-not $visualStudio) {
        $errors.Add(('Dedicated Visual Studio 2022 Build Tools at {0} is absent or incomplete.' -f $script:VsInstallPath))
    }

    $sdk = Get-CompleteWindowsSdk
    if (-not $sdk) {
        $errors.Add('No complete Windows SDK with desktop headers, MIDL, and x86 MSI database tools was found.')
    }

    $legacyCli = Get-LegacyCliTools
    if (-not $legacyCli) {
        $errors.Add('The legacy CLI prerequisites are incomplete: 32-bit-registry csc.exe, al.exe, and x64 mscoree.lib are required.')
    }

    $cygwin = Test-CygwinToolchain
    if (-not $cygwin.Ready) {
        $errors.Add($cygwin.Reason)
    }

    [pscustomobject]@{
        Ready = ($errors.Count -eq 0)
        Errors = @($errors)
        VisualStudio = $visualStudio
        Sdk = $sdk
        LegacyCli = $legacyCli
        Cygwin = $cygwin
    }
}

function Assert-HostPrerequisites {
    $result = Test-HostPrerequisites
    if (-not $result.Ready) {
        $details = ($result.Errors | ForEach-Object { ' - ' + $_ }) -join [Environment]::NewLine
        throw ('Windows build preflight failed:{0}{1}' -f [Environment]::NewLine, $details)
    }
    $result
}

function Invoke-Download {
    param(
        [Parameter(Mandatory)][string] $Url,
        [Parameter(Mandatory)][string] $Destination
    )

    $temporary = $Destination + '.download.' + [guid]::NewGuid().ToString('N')
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & $curl.Source --fail --location --retry 5 --retry-delay 5 --connect-timeout 30 --output $temporary $Url
        if ($LASTEXITCODE -ne 0) {
            throw ('Download failed with exit code {0}: {1}' -f $LASTEXITCODE, $Url)
        }
    }
    else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $Url -OutFile $temporary -UseBasicParsing
    }
    if (-not (Test-Path -LiteralPath $temporary -PathType Leaf)) {
        throw ('Download did not create the expected temporary file: {0}' -f $temporary)
    }
    $temporary
}

function Get-SignedDownload {
    param(
        [Parameter(Mandatory)][string] $Name,
        [Parameter(Mandatory)][string] $Url,
        [Parameter(Mandatory)][string] $Destination,
        [Parameter(Mandatory)][string] $SignerPattern
    )

    if (-not (Test-Path -LiteralPath $Destination -PathType Leaf)) {
        $temporary = Invoke-Download $Url $Destination
        $signature = Get-AuthenticodeSignature -LiteralPath $temporary
        if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -notmatch $SignerPattern) {
            throw ('{0} download has an invalid or unexpected Authenticode signature. Retained for inspection: {1}' -f $Name, $temporary)
        }
        Move-Item -LiteralPath $temporary -Destination $Destination -ErrorAction Stop
    }

    $signature = Get-AuthenticodeSignature -LiteralPath $Destination
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or $signature.SignerCertificate.Subject -notmatch $SignerPattern) {
        throw ('{0} has an invalid or unexpected Authenticode signature: {1}' -f $Name, $Destination)
    }
    $record = [pscustomobject]@{
        Name = $Name
        Url = $Url
        Path = $Destination
        Sha256 = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        Signature = $signature.Status
        Signer = $signature.SignerCertificate.Subject
    }
    $script:DownloadRecords.Add($record)
    $record
}

function Get-PinnedDownload {
    param(
        [Parameter(Mandatory)][string] $Name,
        [Parameter(Mandatory)][string] $Url,
        [Parameter(Mandatory)][string] $Destination,
        [Parameter(Mandatory)][string] $Sha256
    )

    $expectedHash = $Sha256.ToLowerInvariant()
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $actualHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw ('{0} exists but its SHA-256 differs from the pinned LibreOffice value. It was not replaced: {1}' -f $Name, $Destination)
        }
    }
    else {
        $temporary = Invoke-Download $Url $Destination
        $actualHash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw ('{0} download SHA-256 mismatch. Retained for inspection: {1}' -f $Name, $temporary)
        }
        Move-Item -LiteralPath $temporary -Destination $Destination -ErrorAction Stop
    }

    $record = [pscustomobject]@{
        Name = $Name
        Url = $Url
        Path = $Destination
        Sha256 = $expectedHash
        Signature = 'SHA-256 pinned'
        Signer = $null
    }
    $script:DownloadRecords.Add($record)
    $record
}

function Invoke-Installer {
    param(
        [Parameter(Mandatory)][string] $Name,
        [Parameter(Mandatory)][string] $FilePath,
        [Parameter(Mandatory)][string[]] $Arguments
    )

    Write-Host ('Installing or repairing {0}...' -f $Name) -ForegroundColor Yellow
    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 3010) {
        throw ('{0} completed but Windows requires a reboot. Reboot manually, then rerun this script.' -f $Name)
    }
    if ($exitCode -ne 0) {
        throw ('{0} failed with exit code {1}.' -f $Name, $exitCode)
    }
}

function Write-BootstrapManifest {
    param([Parameter(Mandatory)] $Prerequisites)

    $manifest = [ordered]@{
        schema = 1
        generated_utc = [DateTime]::UtcNow.ToString('o')
        tool_root = $script:ToolRoot
        visual_studio = [ordered]@{
            installation_path = $Prerequisites.VisualStudio.InstallationPath
            cmake = $Prerequisites.VisualStudio.CMake
            atl_header = $Prerequisites.VisualStudio.AtlHeader
            crt_merge_module_x86 = $Prerequisites.VisualStudio.MsmX86
            crt_merge_module_x64 = $Prerequisites.VisualStudio.MsmX64
        }
        windows_sdk = [ordered]@{
            root = $Prerequisites.Sdk.Root
            version = $Prerequisites.Sdk.Version
            msi_info = $Prerequisites.Sdk.MsiInfo
        }
        legacy_cli = [ordered]@{
            csc = $Prerequisites.LegacyCli.Csc
            al = $Prerequisites.LegacyCli.Al
            mscoree = $Prerequisites.LegacyCli.Mscoree
        }
        cygwin = [ordered]@{
            root = $script:CygwinRoot
            packages = $script:CygwinPackages
        }
        downloads = @($script:DownloadRecords)
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $script:BootstrapManifestPath -Encoding utf8
}

function Invoke-Bootstrap {
    if (-not (Test-Administrator)) {
        throw 'Bootstrap must run elevated so it can install the isolated toolchain.'
    }
    if (Test-PendingReboot) {
        throw 'Windows has a pending reboot. Reboot manually before installing build prerequisites.'
    }

    New-RequiredDirectory $script:ToolRoot
    New-RequiredDirectory $script:BootstrapDirectory
    $transcript = Join-Path $script:BootstrapDirectory 'bootstrap.log'
    Start-Transcript -Path $transcript -Append | Out-Null
    try {
        Write-Section 'Bootstrap isolated Windows build prerequisites'
        if (-not (Get-DedicatedVisualStudio)) {
            $vsBootstrapper = Get-SignedDownload 'Visual Studio 2022 Build Tools bootstrapper' 'https://aka.ms/vs/17/release/vs_buildtools.exe' (Join-Path $script:BootstrapDirectory 'vs_buildtools.exe') 'Microsoft Corporation'
            $vsArguments = @('--quiet', '--wait', '--norestart', '--nocache', '--installPath', $script:VsInstallPath)
            foreach ($component in $script:VsBootstrapComponents) {
                $vsArguments += @('--add', $component)
            }
            Invoke-Installer 'Visual Studio 2022 Build Tools' $vsBootstrapper.Path $vsArguments
        }

        if (-not (Get-LegacyCliTools)) {
            $netFx = Get-SignedDownload '.NET Framework 4.8.1 Developer Pack' 'https://go.microsoft.com/fwlink/?linkid=2203306' (Join-Path $script:BootstrapDirectory 'ndp481-devpack-enu.exe') 'Microsoft Corporation'
            Invoke-Installer '.NET Framework 4.8.1 Developer Pack' $netFx.Path @('/q', '/norestart')
        }

        $cygwinSetup = Get-SignedDownload 'Cygwin setup' 'https://cygwin.com/setup-x86_64.exe' (Join-Path $script:BootstrapDirectory 'setup-x86_64.exe') 'Cygwin'
        $cygwinArguments = @(
            '-q', '-n', '-N', '-d',
            '-R', $script:CygwinRoot,
            '-s', 'https://mirrors.kernel.org/sourceware/cygwin/',
            '-P', ($script:CygwinPackages -join ',')
        )
        Invoke-Installer 'Cygwin and LibreOffice build packages' $cygwinSetup.Path $cygwinArguments

        $loToolDirectory = Join-Path $script:CygwinRoot 'opt\lo\bin'
        New-RequiredDirectory $loToolDirectory
        foreach ($tool in $script:LibreOfficeTools) {
            Get-PinnedDownload $tool.Name $tool.Url (Join-Path $loToolDirectory $tool.Name) $tool.Sha256 | Out-Null
        }

        $prerequisites = Assert-HostPrerequisites
        Write-BootstrapManifest $prerequisites
        Write-Host ('Bootstrap manifest: {0}' -f $script:BootstrapManifestPath) -ForegroundColor Green
    }
    finally {
        Stop-Transcript | Out-Null
    }
}

function Invoke-ElevatedBootstrap {
    $powerShell = Join-Path $PSHOME 'powershell.exe'
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
        '-File', $PSCommandPath,
        '-Phase', 'Bootstrap',
        '-Jobs', $Jobs,
        '-ToolRoot', $script:ToolRoot,
        '-BuildRoot', $script:BuildRoot,
        '-MinimumFreeGiB', $MinimumFreeGiB
    )
    Write-Host 'Requesting one UAC consent prompt for the hidden dependency bootstrap...' -ForegroundColor Yellow
    $process = Start-Process -FilePath $powerShell -Verb RunAs -WindowStyle Hidden -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        $log = Join-Path $script:BootstrapDirectory 'bootstrap.log'
        throw ('Elevated bootstrap failed with exit code {0}. See {1}' -f $process.ExitCode, $log)
    }
}

function Assert-FreeDiskSpace {
    $root = [IO.Path]::GetPathRoot($script:BuildRoot)
    if (-not $root -or $root.Length -lt 2) {
        throw ('Could not identify the drive for build root: {0}' -f $script:BuildRoot)
    }
    $drive = Get-PSDrive -Name $root.Substring(0, 1) -PSProvider FileSystem -ErrorAction Stop
    $freeGiB = [math]::Floor($drive.Free / 1GB)
    if ($freeGiB -lt $MinimumFreeGiB) {
        throw ('Build root drive {0} has {1} GiB free; at least {2} GiB is required.' -f $drive.Root, $freeGiB, $MinimumFreeGiB)
    }
    Write-Host ('Build drive free space: {0} GiB' -f $freeGiB) -ForegroundColor DarkGray
}

function Initialize-BuildRoot {
    param([Parameter(Mandatory)][string] $SourceCommit)

    if (Test-Path -LiteralPath $script:BuildRoot -PathType Leaf) {
        throw ('Build root is a file: {0}' -f $script:BuildRoot)
    }
    $entries = @()
    if (Test-Path -LiteralPath $script:BuildRoot -PathType Container) {
        $entries = @(Get-ChildItem -LiteralPath $script:BuildRoot -Force)
    }

    if ($entries.Count -gt 0) {
        if (-not $Resume) {
            throw ('Build root already contains data: {0}. Nothing was removed. Inspect it, then use -Resume only for this exact source commit.' -f $script:BuildRoot)
        }
        if (-not (Test-Path -LiteralPath $script:StatePath -PathType Leaf)) {
            throw ('Cannot resume without saved build state: {0}' -f $script:StatePath)
        }
        $state = Get-Content -LiteralPath $script:StatePath -Raw | ConvertFrom-Json
        if ($state.source_commit -ne $SourceCommit -or (Get-FullPath $state.repository_root) -ine (Get-FullPath $script:RepositoryRoot)) {
            throw 'Refusing to resume a build root belonging to another source commit or repository. Nothing was removed.'
        }
    }
    else {
        New-RequiredDirectory $script:BuildRoot
        $state = [ordered]@{
            schema = 1
            created_utc = [DateTime]::UtcNow.ToString('o')
            repository_root = $script:RepositoryRoot
            source_commit = $SourceCommit
            build_profile = 'windows-cygwin-vs2022-msi'
        }
        $state | ConvertTo-Json | Set-Content -LiteralPath $script:StatePath -Encoding utf8
    }

    foreach ($directory in @($script:BuildDirectory, $script:TarballDirectory, $script:LogsDirectory)) {
        New-RequiredDirectory $directory
    }
}

function Initialize-LfSourceSnapshot {
    param([Parameter(Mandatory)][string] $SourceCommit)

    if (Test-Path -LiteralPath $script:SourceSnapshot -PathType Leaf) {
        throw ('Source snapshot path is a file: {0}' -f $script:SourceSnapshot)
    }
    if (-not (Test-Path -LiteralPath $script:SourceSnapshot -PathType Container)) {
        Write-Section 'Create detached LF source snapshot'
        & $script:Git -C $script:RepositoryRoot -c core.autocrlf=false -c core.eol=lf worktree add --detach $script:SourceSnapshot $SourceCommit
        if ($LASTEXITCODE -ne 0) {
            throw ('Git could not create the LF source snapshot (exit code {0}).' -f $LASTEXITCODE)
        }
    }

    $snapshotCommit = (Invoke-Git @('-C', $script:SourceSnapshot, 'rev-parse', '--verify', 'HEAD') | Select-Object -First 1).Trim()
    if ($snapshotCommit -ne $SourceCommit) {
        throw ('Existing source snapshot is at {0}, not requested {1}. Nothing was removed.' -f $snapshotCommit, $SourceCommit)
    }
    $changes = @(Invoke-Git @('-C', $script:SourceSnapshot, 'status', '--porcelain=v1', '--untracked-files=all'))
    if ($changes.Count -gt 0) {
        throw ('LF source snapshot is dirty. Nothing was removed: {0}' -f $script:SourceSnapshot)
    }
    $eol = @(Invoke-Git @('-C', $script:SourceSnapshot, 'ls-files', '--eol', 'autogen.sh', 'configure.ac', 'distro-configs/LibreOfficeWin64.conf'))
    if ($eol -match 'w/(crlf|mixed)') {
        throw ('LF source snapshot contains CRLF-sensitive build inputs. Nothing was normalized automatically: {0}' -f $script:SourceSnapshot)
    }
    $eol | ForEach-Object { Write-Host $_ }
}

function Invoke-CygwinScript {
    param(
        [Parameter(Mandatory)][string] $Name,
        [Parameter(Mandatory)][string] $ScriptText
    )

    $bash = Join-Path $script:CygwinRoot 'bin\bash.exe'
    $log = Join-Path $script:LogsDirectory ($Name + '.log')
    Write-Section $Name
    & $bash --noprofile --norc -o igncr -eo pipefail -c $ScriptText 2>&1 | Tee-Object -FilePath $log
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw ('{0} failed with exit code {1}. See {2}' -f $Name, $exitCode, $log)
    }
}

function Assert-ConfiguredBuild {
    $config = Join-Path $script:BuildDirectory 'config_host.mk'
    if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
        throw ('No configured build exists at {0}. Run -Phase Configure or the default All phase first.' -f $script:BuildDirectory)
    }
}

function Invoke-Configure {
    $configure = @'
export PATH="/opt/lo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
src_dir="$(cygpath -u "$SOURCE_CHECKOUT")"
build_dir="$(cygpath -u "$LO_BUILD_DIR")"
tarball_dir="$(cygpath -u "$LO_TARBALL_DIR")"
tarball_arg="$(cygpath -m "$tarball_dir")"
test -n "$HOME"
mkdir -p "$HOME" "$build_dir" "$tarball_dir"
if ! /usr/bin/git config --global --get-all safe.directory | grep -Fx "$src_dir" >/dev/null 2>&1; then
  /usr/bin/git config --global --add safe.directory "$src_dir"
fi
/usr/bin/git -C "$src_dir" rev-parse --verify HEAD
cd "$build_dir"
"$src_dir/autogen.sh" \
  --host=x86_64-pc-cygwin \
  --with-visual-studio=2022 \
  --with-windows-sdk=10.0 \
  --with-package-format=msi \
  --with-external-tar="$tarball_arg" \
  --with-lang=en-US \
  --enable-online-update \
  --with-privacy-policy-url=https://github.com/codingmachineedge/libreoffice-material/blob/main/PRIVACY.md \
  --enable-python=fully-internal \
  --without-java \
  --without-junit \
  --without-dotnet \
  --without-help \
  --without-helppack-integration \
  --without-myspell-dicts \
  --without-doxygen \
  --without-fonts \
  --with-galleries=no \
  --disable-odk \
  --disable-ccache \
  --disable-pdfium \
  --enable-database-connectivity \
  --disable-cairo-canvas
grep -Eq '^export BUILD_TYPE=.*[[:space:]]DBCONNECTIVITY([[:space:]]|$)' config_host.mk
grep -qx 'export ENABLE_CLI=TRUE' config_host.mk
'@
    Invoke-CygwinScript 'configure' $configure
}

function Invoke-NativeTests {
    $tests = @'
export PATH="/opt/lo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(cygpath -u "$LO_BUILD_DIR")"
/opt/lo/bin/make.exe -j"$BUILD_JOBS" Library_svxcore
for target in \
  CppunitTest_tools_test \
  CppunitTest_extensions_test_update \
  CppunitTest_vcl_widget_definition_reader_test \
  CppunitTest_vcl_file_definition_widget_draw_test \
  CppunitTest_vcl_treeview
do
  /opt/lo/bin/make.exe -j"$BUILD_JOBS" "$target"
done
for target in cli_ure unoil
do
  /opt/lo/bin/make.exe -j"$BUILD_JOBS" "$target"
done
for file in \
  cli_basetypes.dll cli_ure.dll cli_uretypes.dll cli_cppuhelper.dll cli_oootypes.dll \
  policy.1.0.cli_basetypes.dll policy.1.0.cli_ure.dll \
  policy.1.0.cli_uretypes.dll policy.1.0.cli_cppuhelper.dll \
  policy.1.0.cli_oootypes.dll \
  cli_basetypes.config cli_ure.config cli_uretypes.config \
  cli_cppuhelper.config cli_oootypes.config
do
  test -s "instdir/program/$file"
done
'@
    Invoke-CygwinScript 'native-tests' $tests
}

function Invoke-ProductBuild {
    $build = @'
export PATH="/opt/lo/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$(cygpath -u "$LO_BUILD_DIR")"
/opt/lo/bin/make.exe -j"$BUILD_JOBS" build
'@
    Invoke-CygwinScript 'product-build' $build
}

function Invoke-MsiPackagingValidation {
    Write-Section 'Stage and structurally validate final MSI'
    $finalDirectory = Join-Path $script:BuildDirectory 'workdir\installation\LibreOfficeDev\msi\install\en-US'
    if (-not (Test-Path -LiteralPath $finalDirectory -PathType Container)) {
        throw ('The final MSI directory was not produced: {0}' -f $finalDirectory)
    }
    $msis = @(Get-ChildItem -LiteralPath $finalDirectory -Filter '*.msi' -File -ErrorAction Stop)
    if ($msis.Count -ne 1) {
        $candidates = if ($msis.Count -gt 0) { ($msis | ForEach-Object FullName) -join '; ' } else { '(none)' }
        throw ('Expected exactly one final MSI under {0}, found {1}: {2}' -f $finalDirectory, $msis.Count, $candidates)
    }

    $runId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $msis[0].BaseName
    $stage = Join-Path (Join-Path $script:BuildRoot 'dist-windows') $runId
    $extract = Join-Path (Join-Path $script:BuildRoot 'msi-check') $runId
    New-RequiredDirectory $stage
    New-RequiredDirectory $extract
    $extractLog = Join-Path $stage ($msis[0].BaseName + '-admin-extract.log')
    $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
    & $msiexec /a $msis[0].FullName /qn ('TARGETDIR=' + $extract) /L*V $extractLog
    $extractExitCode = $LASTEXITCODE
    if ($extractExitCode -notin @(0, 3010)) {
        throw ('Administrative extraction failed with exit code {0}. See {1}' -f $extractExitCode, $extractLog)
    }
    $soffice = @(Get-ChildItem -LiteralPath $extract -Recurse -Filter 'soffice.exe' -File -ErrorAction SilentlyContinue)
    if ($soffice.Count -ne 1) {
        throw ('Administrative extraction must contain exactly one soffice.exe; found {0}.' -f $soffice.Count)
    }

    $canonicalName = 'LibreOfficeMaterial-Windows-x64.msi'
    $destination = Join-Path $stage $canonicalName
    Copy-Item -LiteralPath $msis[0].FullName -Destination $destination -ErrorAction Stop
    $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    ($hash + '  ' + $canonicalName) | Set-Content -LiteralPath ($destination + '.sha256') -Encoding ascii
    $sourceCommit = (Get-Content -LiteralPath $script:StatePath -Raw | ConvertFrom-Json).source_commit
    $manifest = [ordered]@{
        file = $canonicalName
        bytes = (Get-Item -LiteralPath $destination).Length
        sha256 = $hash
        source_commit = $sourceCommit
        administrative_extract = 'passed'
        administrative_extract_exit_code = $extractExitCode
        payload = $soffice[0].FullName.Substring($extract.Length).TrimStart('\')
        runtime_verified = $false
        signed = $false
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $stage 'windows-msi-manifest.json') -Encoding utf8
    Write-Host ('Final MSI: {0}' -f $destination) -ForegroundColor Green
    Write-Host ('SHA-256: {0}' -f $hash) -ForegroundColor Green
    Write-Host ('Administrative extract: {0}' -f $extract) -ForegroundColor DarkGray
}

function Invoke-BuildPhases {
    $hadCl = Test-Path Env:CL
    $oldCl = $env:CL
    try {
        $env:CL = '/FS'
        $env:SOURCE_CHECKOUT = $script:SourceSnapshot
        $env:LO_BUILD_ROOT = $script:BuildRoot
        $env:LO_BUILD_DIR = $script:BuildDirectory
        $env:LO_TARBALL_DIR = $script:TarballDirectory
        $env:BUILD_JOBS = [string] $Jobs

        if ($Phase -in @('All', 'Configure')) {
            Invoke-Configure
        }
        if ($Phase -in @('All', 'Tests')) {
            Assert-ConfiguredBuild
            Invoke-NativeTests
        }
        if ($Phase -in @('All', 'Build')) {
            Assert-ConfiguredBuild
            Invoke-ProductBuild
        }
        if ($Phase -in @('All', 'Package')) {
            Assert-ConfiguredBuild
            Invoke-MsiPackagingValidation
        }
    }
    finally {
        if ($hadCl) {
            $env:CL = $oldCl
        }
        else {
            Remove-Item Env:CL -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-WithBuildMutex {
    param([Parameter(Mandatory)][scriptblock] $Action)

    $mutex = New-Object System.Threading.Mutex($false, 'Local\LibreOfficeMaterialWindowsBuild')
    $held = $false
    try {
        $held = $mutex.WaitOne(0)
        if (-not $held) {
            throw 'Another LibreOffice Material Windows bootstrap or build is already running in this session.'
        }
        & $Action
    }
    finally {
        if ($held) {
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}

try {
    if ($env:OS -ne 'Windows_NT') {
        throw 'This script supports Windows only.'
    }
    $script:Git = Get-GitExecutable

    if ($Phase -eq 'Preflight') {
        Write-Section 'Read-only Windows build preflight'
        $commit = Assert-CleanSourceCheckout
        Assert-FreeDiskSpace
        $prerequisites = Assert-HostPrerequisites
        Write-Host ('Source commit: {0}' -f $commit) -ForegroundColor Green
        Write-Host ('Dedicated Visual Studio: {0}' -f $prerequisites.VisualStudio.InstallationPath) -ForegroundColor Green
        Write-Host ('Windows SDK: {0}' -f $prerequisites.Sdk.Version) -ForegroundColor Green
        Write-Host 'Preflight passed. No dependencies, source files, or build outputs were changed.' -ForegroundColor Green
        return
    }

    $initialPrerequisites = Test-HostPrerequisites
    if (-not $initialPrerequisites.Ready -and -not $NoBootstrap) {
        if (Test-Administrator) {
            Invoke-WithBuildMutex { Invoke-Bootstrap }
        }
        else {
            Invoke-ElevatedBootstrap
        }
    }
    Assert-HostPrerequisites | Out-Null

    if ($Phase -eq 'Bootstrap') {
        Write-Host 'Bootstrap passed. No source snapshot or build output was created.' -ForegroundColor Green
        return
    }

    Invoke-WithBuildMutex {
        $sourceCommit = Assert-CleanSourceCheckout
        Assert-FreeDiskSpace
        Initialize-BuildRoot $sourceCommit
        Initialize-LfSourceSnapshot $sourceCommit
        Invoke-BuildPhases
    }
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
