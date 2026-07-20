# Disposable Windows installer lifecycle gate

This harness exercises the released Windows x64 MSI only inside Windows
Sandbox. It does not install, repair, upgrade, or uninstall anything on the
host. It also never deletes a pending-restart registry value. A changed reboot
indicator, exit code `3010`, or exit code `1641` fails the gate; closing the
disposable Sandbox removes all guest state.

The two pinned inputs are the exact normal releases at source commits
`577059e2741185b512c184c64685c16d335d10ea` and
`fbba560e27db26de605c40aa237c554c1f0744b1`. The guest verifies their byte
counts, SHA-256 values, ProductCodes, shared LibreOfficeDev UpgradeCode, and
absence of `ForceReboot` / `ScheduleReboot` in `InstallExecuteSequence` before
any mutation.

## Prerequisites

- 64-bit Windows 11 Pro with Windows Sandbox, Hyper-V, the Hyper-V hypervisor,
  and Virtual Machine Platform enabled;
- an active hypervisor and at least 8 GB of memory available to the Sandbox;
- network access during preparation so the host can fetch the two exact-tag
  GitHub assets;
- no need to install the Windows SDK or any test framework.

The generated Sandbox has networking, vGPU, audio input, video input, printer
redirection, and clipboard redirection disabled. It maps only a pinned input
directory as read-only and a new empty result directory as writable.
Before any MSI query or mutation, the guest positively requires the documented
`WDAGUtilityAccount` identity and SID RID, its Sandbox profile and reviewed
mapped entry point, Microsoft's virtual-machine identity, active hypervisor,
and enforced read-only input mapping. Failure occurs outside the cleanup and
shutdown block, so accidentally invoking the guest script on the host cannot
reach MSI cleanup or `shutdown.exe`.

## Static validation

Run the dependency-free source validator first:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\qa\windows-installer-lifecycle\Validate-Harness.ps1
```

Validate the hosted release publication state machine separately:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\qa\windows-installer-lifecycle\Validate-ReleaseWorkflow.ps1
```

This parses both PowerShell files and checks the launch boundary, pinned
release metadata, Sandbox isolation settings, lifecycle steps, exact updater
properties, reboot snapshots, zero-only acceptance, completion publication,
and absence of restart-flag deletion. The release-workflow validator executes
the workflow's actual URL-state helper against draft and published fixtures:
GitHub's temporary `untagged-*` URL is valid before promotion, while the
canonical tag URL remains mandatory after a normal release is published.

## Review-first execution

Preparation is deliberately the default and never starts Windows Sandbox:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\bin\Test-WindowsInstallerLifecycle.ps1 -Mode Prepare
```

The command prints a unique run directory and the exact explicit launch
command. Before launch, review `run-manifest.json`, `input\expected.json`, and
`LibreOfficeMaterial-InstallerLifecycle.wsb` in that directory.

Revalidate those reviewed bytes and policies without launching anything:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\bin\Test-WindowsInstallerLifecycle.ps1 `
  -Mode Inspect `
  -RunDirectory 'C:\absolute\prepared\run-directory'
```

Launch only the reviewed prepared run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\bin\Test-WindowsInstallerLifecycle.ps1 `
  -Mode Launch `
  -RunDirectory 'C:\absolute\prepared\run-directory'
```

The host revalidates every prepared byte against the hard-coded release pins
and the current reviewed repository guest source, requires an empty output directory,
checks Sandbox/Hyper-V readiness, records host reboot and LibreOffice
registration state, launches the generated `.wsb`, and polls for an atomic
guest sentinel. It first requires the Sandbox backend to exit on the guest's
own shutdown request. If the current packaged remote-session UI remains, the
host binds its command line to the exact reviewed `.wsb`, validates the
Microsoft package path, and requests `CloseMainWindow()`; it never terminates
the guest backend or force-kills a timed-out process. Only after every tracked
legacy/current Sandbox process is absent and the host-safety checks pass does it write
`host-verification.json` in the run root.

The guest performs, in order:

1. old exact-tag MSI install;
2. corrected same-version major update with a plain `/i corrected.msi` command;
3. corrected repair after moving `program\updchklo.dll` aside as the repair
   probe, using `REINSTALL=ALL` and `REINSTALLMODE=vomus` only for this
   maintenance operation;
4. corrected ProductCode uninstall.

Every operation uses `/qn`, `/norestart`, `REBOOT=ReallySuppress`,
`MSIRESTARTMANAGERCONTROL=DisableShutdown`, and flushed verbose logging. The
old updater DLL hash must change to the corrected hash during update, repair
must restore the missing corrected DLL, and both ProductCodes must be absent at
the end with successful Windows Installer `ProductState = -1` queries. COM query
errors fail closed. Before/after fingerprints must match for every step and the
whole lifecycle, and the host independently recomputes each comparison. A
`COMPLETE.json` file is published only after every assertion and best-effort
final cleanup succeed.

Revalidate a completed result bundle without launching anything:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File .\bin\Test-WindowsInstallerLifecycle.ps1 `
  -Mode Verify `
  -RunDirectory 'C:\absolute\prepared\run-directory'
```

`Verify` requires both the byte-pinned guest completion bundle and the retained
`host-before.json`, `host-after.json`, and `host-verification.json`. It rejects
changed snapshot hashes, changed host safety state, or nonzero recorded Sandbox
processes.

## First live diagnostic

The retained run
`20260720-041140-7240676-b3777205bfb344a2977090ba35d643c3`
was launched on an isolated low-level off-screen desktop. It failed closed with
exit code `1` while PowerShell tried to apply `@(...)` directly to a generic
`List[object]` during result publication. It produced only `FAILURE.json`; no
step logs, `COMPLETE.json`, or `host-verification.json` were accepted. The
before/after host reboot and LibreOffice-registration fingerprints were
identical, and cleanup left zero tracked Sandbox processes.

The guest now calls `.ToArray()` for snapshot, step, and cleanup collections and
uses `ConvertTo-Json -InputObject` so empty and singleton arrays retain their
shape. The host also recognizes `WindowsSandboxRemoteSession.exe` and
`WindowsSandboxServer.exe`. Parser/static checks and PowerShell 5.1/7
serialization probes pass, but only a fresh complete run can close the runtime
gate.

### Second live diagnostic

Fresh run
`20260720-043916-4641037-b451b45fa51a423c880f7092faa45274`
sealed the corrected guest and both MSI hashes, passed `Inspect`, and launched
on a new off-screen desktop. It proved the array serialization fix by publishing
valid empty arrays plus a byte-pinned artifact manifest. It then failed closed
before any MSI step because `Invoke-MsiQuery` returned all 107 Property-table
rows inside one outer collection, so strict-mode identity parsing could not find
`ProductCode`. Exit code was `1`, both host safety snapshots matched, the new
server-first/run-bound client disposal completed, and zero Sandbox processes
remained.

The query helper now emits its rows directly, requires all pinned Property-table
keys, and reads them by hashtable index. A PowerShell 5.1 probe executing the
exact reviewed function definitions against both retained MSIs returned the
expected distinct ProductCodes, shared test UpgradeCode/version, machine-wide
scope, zero reboot actions, and restart-manager property. This still is not
installer lifecycle proof.

### Third live diagnostic

Fresh run
`20260720-045143-7859553-08fb3836f8b446dda272e206d296a591`
passed sealed-input inspection, installed the old MSI with exit code `0`, and
ran the corrected same-version command with exit code `0`. Neither step changed
the guest reboot fingerprint. The post-update assertion then failed closed
because the old ProductCode remained registered with Windows Installer state
`5`. Its log proves the corrected MSI found the old ProductCode, but the command
incorrectly supplied repair-only `REINSTALL=ALL` and `REINSTALLMODE=vomus`
properties to a new ProductCode. Windows Installer therefore selected no
features and skipped `RemoveExistingProducts`. Repair and the corrected-product
uninstall were not attempted, so this is not lifecycle acceptance.

Best-effort cleanup uninstalled the old ProductCode with exit code `0`, left
both ProductCodes absent, reported no cleanup error or reboot-state change, and
published byte-pinned failure artifacts. The host before/after reboot and
LibreOffice-registration snapshots were identical. The packaged Sandbox client
did not complete its normal disposal deadline, so no `host-verification.json`
or `COMPLETE.json` was accepted. The retained result therefore documents two
real successful MSI operations and a precise same-version upgrade-sequencing
gap, not a passed update/repair/uninstall lifecycle. The source updater and
harness now use a plain `/i` major-upgrade command and retain the `REINSTALL`
properties only for the explicit repair step; a fresh run is still required.

## Evidence boundary

Preparing or statically validating this harness is not installer lifecycle
proof. Acceptance requires a real Sandbox run whose host-verified output
contains the four zero-exit lifecycle logs, before/after reboot snapshots,
`results.json`, a byte-verified `artifact-manifest.json`, and the atomic
`COMPLETE.json` sentinel, followed by verified Sandbox client disposal. The
current source updater and the lifecycle harness
both supply `MSIRESTARTMANAGERCONTROL=DisableShutdown`; the corrected public
`fbba560e2` release predates that protection and still carries the two
repair-only reinstall properties, so it must not be reported as runtime proof
for the current four-argument major-update command.
