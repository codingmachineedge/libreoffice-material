# Windows build-wrapper regression

`Validate-BuildScript.ps1` is a dependency-free PowerShell 5.1-compatible gate
for the local Windows packaging wrapper. It parses `bin/Build-Windows.ps1` and
requires administrative MSI extraction to:

- construct one safely quoted Windows command line with the wrapper's existing
  argument encoder;
- launch `msiexec.exe` hidden through `Start-Process`;
- wait for that exact client and read its exit code before inspecting payload
  files; and
- reject the direct PowerShell invocation that can return while the Windows
  Installer service is still extracting.

Run it without building or launching an installer:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\qa\windows-build\Validate-BuildScript.ps1
```

This validator proves the control-flow invariant only. Accepted packaging still
requires one real administrative extraction, exactly one `soffice.exe`, a staged
canonical MSI/checksum/manifest, and recorded byte/hash provenance.
