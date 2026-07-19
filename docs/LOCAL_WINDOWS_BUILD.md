# Local Windows build

[<code>../Build-Windows.cmd</code>](../Build-Windows.cmd) is the one-click entry
point for the repository's supported Windows x64 build profile. It calls
[<code>bin/Build-Windows.ps1</code>](../bin/Build-Windows.ps1), whose default
<code>All</code> phase bootstraps, configures, tests, packages, and validates an MSI.

Run it from a PowerShell or Command Prompt window so the long native-build log
stays visible:

~~~powershell
.\Build-Windows.cmd
~~~

The first run can take several hours and needs at least 80 GiB free on the
build-root drive. It asks for one UAC consent prompt only when installation is
needed. That elevated bootstrap runs hidden and logs to
<code>%ProgramData%\LibreOfficeMaterialTools\bootstrap\bootstrap.log</code>;
it does not open a separate PowerShell window for each dependency. The regular
build stays in the invoking terminal.

## What the script provisions

Unless <code>-NoBootstrap</code> is supplied, the script automatically installs or
repairs an isolated toolchain:

- Visual Studio <strong>2022</strong> Build Tools at
  <code>%ProgramData%\LibreOfficeMaterialTools\VS2022</code>, with MSVC x64/x86,
  ATL, CRT merge modules, CMake, Windows SDK 26100, and the .NET Framework
  4.8.1 developer tools;
- Cygwin at <code>%ProgramData%\LibreOfficeMaterialTools\cygwin64</code>, with
  the exact Autotools, Perl, NASM, Ninja, archive, XML, Git, Python, and
  packaging packages used by the Windows CI profile;
- LibreOffice's Windows GNU Make and <code>pkgconf-2.4.3.exe</code> under
  <code>cygwin64\opt\lo\bin</code>.

The Visual Studio, Cygwin, and .NET bootstrap installers must have valid
expected Authenticode signers. The two LibreOffice-specific executables must
match source-pinned SHA-256 values:

| File | SHA-256 |
| --- | --- |
| <code>make.exe</code> | <code>146d6f2b0ea57647b11b506a95048a7be73232e1feeeccbc1013651f992423d8</code> |
| <code>pkgconf-2.4.3.exe</code> | <code>791cd6dbc56f7268fbf9c4652d6634b0f5c59687ab4e504565e58245952edd41</code> |

After provisioning, it independently verifies the VS 2022 component set,
ATL and CRT merge modules, a complete Windows SDK including MIDL and x86 MSI
tools, the legacy CLI .NET Framework tools, Cygwin packages, Perl modules,
Windows-built Make, pinned <code>pkgconf</code>, and NASM 2.16 or newer. A bootstrap
manifest records those validated paths, package names, signers, and hashes.

It never substitutes the host's Visual Studio 2026 installation for the
required VS 2022 profile.

## Source and output safety

The script requires a clean active repository. It then creates a detached,
LF-only worktree at
<code>%LOCALAPPDATA%\LibreOfficeMaterialBuild\source</code>, so it never
normalizes or edits the development checkout. The out-of-tree build, external
tarball cache, logs, MSI extraction, staged installer, checksums, and manifest
are all below <code>%LOCALAPPDATA%\LibreOfficeMaterialBuild</code> by default.

It never deletes a build root. If a prior build exists, inspect it and resume
only when its <code>build-state.json</code> names the exact current source commit:

~~~powershell
.\Build-Windows.cmd -Resume
~~~

Choose larger volumes without changing the active checkout:

~~~powershell
.\Build-Windows.cmd -ToolRoot 'G:\LibreOfficeMaterialTools' -BuildRoot 'G:\LibreOfficeMaterialBuild'
~~~

The script stops rather than restarting Windows, overwriting a hash-mismatched
bootstrap tool, deleting a stale output, or force-closing a process. If an
installer returns the reboot-required code, reboot manually and rerun it.

## Build contract

The <code>All</code> phase uses the same Windows profile as
[<code>windows-installer.yml</code>](../.github/workflows/windows-installer.yml):

1. <code>autogen.sh</code> configures Cygwin + Visual Studio 2022 MSI packaging with
   fully internal Python, <code>--without-dotnet</code>, and
   <code>--enable-database-connectivity</code>;
2. it asserts <code>DBCONNECTIVITY</code> and <code>ENABLE_CLI=TRUE</code>;
3. it links <code>Library_svxcore</code>, runs the five required CppUnit targets
   serially, and builds and checks the legacy CLI payload;
4. it runs <code>make build</code>;
5. it accepts exactly one MSI only from
   <code>workdir\installation\LibreOfficeDev\msi\install\en-US</code>,
   administratively extracts it, and requires exactly one <code>soffice.exe</code>.

The canonical staged result, SHA-256 file, MSI manifest, extraction log, and
administrative extraction stay in a unique
<code>dist-windows\&lt;timestamp&gt;-&lt;msi-name&gt;</code> directory. The script does not
install the MSI or launch the application. Use the isolated off-screen harness
defined in [<code>HEADLESS_UI_EVIDENCE.md</code>](HEADLESS_UI_EVIDENCE.md) for
runtime verification.

For a non-mutating availability check, use:

~~~powershell
.\Build-Windows.cmd -Phase Preflight
~~~

For a strict existing-toolchain build that may not install anything, use:

~~~powershell
.\Build-Windows.cmd -NoBootstrap
~~~

The current host preflight is expected to report no dedicated VS 2022/Cygwin
profile until this bootstrap runs. Adding this script is source automation only:
no local native build, MSI, LibreOffice launch, or accepted UI evidence is
claimed here.
