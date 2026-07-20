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

The first run can take several hours and needs at least 80 GiB free on each
tool/build drive (checked before any installer starts). It asks for one UAC
consent prompt only when installation is needed. That elevated bootstrap runs hidden and logs to
<code>%ProgramData%\LibreOfficeMaterialTools\bootstrap\bootstrap.log</code>;
it does not open a separate PowerShell window for each dependency. The regular
build stays in the invoking terminal.

## What the script provisions

Unless <code>-NoBootstrap</code> is supplied, the default VS 2022 profile
automatically installs or repairs an isolated toolchain:

- Visual Studio <strong>2022</strong> Build Tools at
  <code>%ProgramData%\LibreOfficeMaterialTools\VS2022</code>, with MSVC x64/x86,
  C++/CLI, the C++ Clang compiler, ATL, CRT merge modules, CMake, Windows SDK 26100, and the .NET
  Framework 4.8.1 developer tools;
- Cygwin at <code>%ProgramData%\LibreOfficeMaterialTools\cygwin64</code>, with
  the exact Autotools, Perl, NASM, Ninja, archive, XML, Git, Python, and
  packaging packages used by the Windows CI profile, cached locally below the
  bootstrap directory;
- LibreOffice's Windows GNU Make and <code>pkgconf-2.4.3.exe</code> under
  <code>cygwin64\opt\lo\bin</code>.

Visual Studio 2022 remains the default and matches the current Windows CI
workflow. The source-controlled local VS 2026 profile is deliberately opt-in.
To use a verified existing host installation, name both the VS year and the
exact installation path, and keep the first build root distinct:

~~~powershell
.\Build-Windows.cmd -VisualStudioYear 2026 -VisualStudioInstallPath 'C:\Program Files\Microsoft Visual Studio\18\Enterprise' -BuildRoot "$env:USERPROFILE\lo-material-vs2026"
~~~

The supplied path is verified as the selected VS 2026 toolchain. Normal
bootstrap may still provision the other prerequisites, but it refuses to
modify an incomplete host Visual Studio installation. It never silently finds,
repairs, or substitutes a host installation. Without
<code>-VisualStudioInstallPath</code>, the explicit VS 2026 profile instead
uses the separate dedicated Build Tools root
<code>%ProgramData%\LibreOfficeMaterialTools\VS2026</code>. In either case,
VS 2026 is a local-only profile until the CI workflow is intentionally changed.
VS 2022 and VS 2026 resume state is not interchangeable.
Older build-state schema 1 roots are preserved and rejected rather than changed
in place because they do not record the Visual Studio installation path; use a
new build root for this profile-aware schema.

The isolated Cygwin <code>git</code> package is also the default snapshot
provider, so the script does not install a separate system-wide Git client.

The Visual Studio and .NET bootstrap installers must have a valid
<code>CN=Microsoft Corporation</code> Authenticode signer; Cygwin setup must
have a valid <code>CN=Jon Turney</code> signer. The two LibreOffice-specific
executables must match source-pinned SHA-256 values:

| File | SHA-256 |
| --- | --- |
| <code>make.exe</code> | <code>146d6f2b0ea57647b11b506a95048a7be73232e1feeeccbc1013651f992423d8</code> |
| <code>pkgconf-2.4.3.exe</code> | <code>791cd6dbc56f7268fbf9c4652d6634b0f5c59687ab4e504565e58245952edd41</code> |

After provisioning, it independently verifies the selected Visual Studio
component set, including C++/CLI, the C++ Clang compiler, ATL and the selected
profile's CRT merge modules, a complete Windows SDK including MIDL and x86 MSI
tools, the legacy CLI .NET Framework tools, every requested Cygwin package, the
Perl <code>Archive::Zip</code>, <code>Font::TTF</code>, and <code>IO::String</code>
modules, Windows-built Make, pinned <code>pkgconf</code>, and NASM 2.16 or newer.
A bootstrap manifest records the selected profile, validated paths, package
names, signers, and hashes.
The Clang check accepts the established VS 2022
<code>VC\Tools\Llvm\bin</code> payload layout and the VS 2026 host-native
<code>VC\Tools\Llvm\x64\bin</code> layout.

## Source and output safety

The script requires a clean active repository. It then creates a detached,
LF-only worktree at <code>%USERPROFILE%\lo-material\source</code>, so it never
normalizes or edits the development checkout. The out-of-tree build, external
tarball cache, isolated Cygwin Git configuration, logs, MSI extraction, staged
installer, checksums, and manifest are all below
<code>%USERPROFILE%\lo-material</code> by default.

It refuses filesystem roots, repository-overlapping roots, wildcard or
symlink/junction roots, roots with spaces or longer than 80 characters, and existing
non-resumable build roots before it installs dependencies. It never deletes a
build root. A successful full <code>All</code> run removes only its own clean
detached source snapshot; an interrupted build retains that snapshot for
inspection or <code>-Resume</code>. If a prior build exists, inspect it and
resume only when its <code>build-state.json</code> names the exact current
source commit:

~~~powershell
.\Build-Windows.cmd -Resume
~~~

Choose larger volumes without changing the active checkout:

~~~powershell
.\Build-Windows.cmd -ToolRoot 'G:\LibreOfficeMaterialTools' -BuildRoot 'G:\LibreOfficeMaterialBuild'
~~~

Keep an overridden build root short (80 characters or fewer) and free of
spaces; for example, <code>C:\lo-material</code> is suitable when it is
user-writable. LibreOffice's <code>autogen.sh</code> has the same no-space
requirement for the repository path.

The script stops rather than restarting Windows, overwriting a hash-mismatched
bootstrap tool, deleting a stale output, or force-closing a process. If an
installer returns the reboot-required code, reboot manually and rerun it.

## Build contract

The default <code>All</code> phase uses the same VS 2022 Windows profile as
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

The explicit VS 2026 local profile follows the same configure, test, package,
and structural-validation sequence with <code>--with-visual-studio=2026</code>.
When an explicit host path is selected, the wrapper verifies that configuration
uses that exact installation rather than a different discovered VS 2026 copy.
This does not change the CI runner or establish CI, native-build, installer,
runtime, UI, or accessibility evidence.

The canonical staged result, SHA-256 file, MSI manifest, extraction log, and
administrative extraction stay in a collision-resistant unique
<code>dist-windows\&lt;timestamp&gt;-&lt;msi-name&gt;-&lt;GUID&gt;</code> directory. Cygwin
phase logs are likewise isolated in a per-invocation directory, so a
<code>-Resume</code> run does not overwrite prior failure evidence. The script
does not install the MSI or launch the application. Use the isolated off-screen
harness defined in [<code>HEADLESS_UI_EVIDENCE.md</code>](HEADLESS_UI_EVIDENCE.md)
for runtime verification.

For a non-mutating availability check, use:

~~~powershell
.\Build-Windows.cmd -Phase Preflight
~~~

For the explicit VS 2026 host profile's availability check, keep the build root
separate and provide the exact verified path:

~~~powershell
.\Build-Windows.cmd -Phase Preflight -VisualStudioYear 2026 -VisualStudioInstallPath 'C:\Program Files\Microsoft Visual Studio\18\Enterprise' -BuildRoot "$env:USERPROFILE\lo-material-vs2026"
~~~

For a strict existing-toolchain build that may not install anything, use:

~~~powershell
.\Build-Windows.cmd -NoBootstrap
~~~

With <code>-VisualStudioYear 2026</code>, <code>-NoBootstrap</code> is optional
only after the selected dedicated or explicitly named host profile passes normal
preflight. An explicit host path is still never a fallback: if it is incomplete,
the script stops rather than modifying it.

On 2026-07-19, this host's first bootstrap installed the dedicated VS 2022 and
isolated Cygwin profiles. A later clean preflight passed that installed profile,
then the first real configure exposed a missing VS C++ Clang compiler. The script
now treats that compiler and its <code>clang-cl.exe</code> payload as required so
an incomplete toolchain is repaired before configure.
On 2026-07-19, the explicit Enterprise 2026 host path above passed this document's
no-bootstrap preflight after its C++/CLI, Clang, and VC145 merge-module payloads
were installed. An isolated `-NoBootstrap` configure subsequently completed at
`a6d9f9a7dbdf10c08afe2eb03239e702ec5172ef`; its first native build reached the
bundled `mdds` dependency and exposed C2382 in v145 C++20 conditional
`noexcept` handling. `external/mdds/msvc-v145-cxx20-noexcept.patch.1` preserves
the upstream specification except for that exact v145 C++20-or-newer compiler
range. The patch passed direct VS 2026 and VS 2022 syntax checks and dry-runs
against the unpacked `mdds-3.2.1` tarball.

On 2026-07-20, a fresh explicit VS 2026 build from clean detached source
`577059e2741185b512c184c64685c16d335d10ea` passed all five required native
targets, validated the legacy CLI payload, completed LibreOfficeDev, and
produced a 199,692,288-byte unsigned MSI with SHA-256
`437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43`.
Windows Installer administrative extraction completed with status `0`; the
extracted runtime supplied the registered light Start Center UI and bounded UNO
tree smoke. The wrapper's parent process exited before the final dist copy and
manifest stage, so a fully completed one-click wrapper rerun remains required.
The MSI was not installed during this build run. It was later published as the
normal, non-prerelease `windows-msi-local-20260720-577059e274` release and all
four public Latest assets were byte-verified, but that older binary omitted the
fifth generated updater launch argument. Commit `fbba560e2` corrects the launch,
and its incremental VS 2026 product/MSI rebuild, administrative extraction, and
headless UI/UNO rerun passed. No installer lifecycle or restart-suppression
runtime result is implied. Exact runtime boundaries are in
[`HEADLESS_UI_EVIDENCE.md`](HEADLESS_UI_EVIDENCE.md).
