# Headless UI evidence plan

This plan defines how visible LibreOffice Material work will be exercised on a
real GUI process without taking over the operator's desktop. Accepted runs below
are narrow runtime claims; the remaining matrix stays a plan.

## Driver

The intended driver is
[`codingmachineedge/lowlevel-computer-use-mcp`](https://github.com/codingmachineedge/lowlevel-computer-use-mcp).
In the current workspace it is a sibling checkout named
`lowlevel-computer-use-mcp`; it is not vendored into this repository and is not
currently declared as a submodule here.

On Windows the driver exposes Win32 off-screen desktop operations, background
window enumeration and input, and `PrintWindow` capture. On Linux it can use an
Xvfb virtual display. The driver performs unsandboxed desktop and process
operations, so it must run only on a disposable test account or trusted runner.

## Harness preflight record — 2026-07-16

A Windows harness-only preflight completed successfully using local driver
commit `806d9ba85e4afbc2af58d7499496babfa7c68891` and the driver's Cheap Version,
which invokes the same underlying functions as its MCP tools.

| Check | Observed result |
| --- | --- |
| Off-screen desktop | Created `WinSta0\LibreOfficeMaterialQA` |
| Test process | Notepad launched off screen; no LibreOffice binary was involved |
| Window enumeration | `Untitled - Notepad`, HWND `37291736`, `1920×1125` |
| Window capture | `PrintWindow` returned `rendered_ok: true` |
| Temporary capture SHA-256 | `03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3` |
| Scoped cleanup | Only run-scoped Notepad processes were killed |
| Desktop teardown | A follow-up `OpenDesktop` failed with Win32 error `2`, confirming the named desktop was gone |

The capture remained temporary and is intentionally absent from this
repository. It depicts Notepad, not LibreOffice Material, and therefore is not a
gallery asset, accepted run, UI screenshot, or proof of the fork's rendering.
The preflight proves only that this driver revision could create, enumerate,
capture, and clean up a test window on an off-screen Win32 desktop.

## Current driver audit — 2026-07-16

The sibling checkout is clean on `main` at driver commit
`806d9ba85e4afbc2af58d7499496babfa7c68891`. Its HTTP MCP server was observed
listening only on `127.0.0.1:8765`, with the installed scheduled task ready.
No LibreOffice scenario, fixture, macro, or binary exists in the driver repo.

The audited Windows contract has important boundaries:

- `launch_on_headless_desktop` accepts only a desktop name and command; it has
  no per-run environment or working-directory field, so a run-scoped wrapper
  must set Material variables and execute the exact binary/arguments;
- window enumeration reports HWND, title, class, and dimensions, but not PID;
  ownership must therefore be proven through a run-specific `--pidfile`, exact
  executable path, process creation time, and a pre-launch process snapshot;
- `PrintWindow` capture and HWND-targeted background text/click/key operations
  are cross-desktop aware, but modifier-key input is documented as unreliable;
- move, resize, and generic window actions use caller-desktop discovery and are
  not reliable for an off-screen HWND;
- `close_headless_desktop` releases one tracked desktop handle; it does not
  close LibreOffice, and the long-lived server caches additional opened desktop
  handles. Strict desktop-deletion proof therefore requires a dedicated
  short-lived driver process/session that exits after normal app shutdown.

These are audited capabilities and constraints, not a LibreOffice run result.

## Current LibreOffice build and accepted-run records — 2026-07-20

[`LOCAL_WINDOWS_BUILD.md`](LOCAL_WINDOWS_BUILD.md) defines the source-controlled
one-click bootstrap and the explicit VS 2026 profile. A clean detached build at
fork commit `577059e2741185b512c184c64685c16d335d10ea` used Visual Studio 2026
Enterprise, MSVC v145, Clang 22.1.3, and Windows SDK 10.0.26100.0. It passed the
five required native C++ targets and legacy CLI payload check, completed the
LibreOfficeDev product, and produced
`LibreOfficeDev_27.2.0.0.alpha0_Win_x86-64.msi` (199,692,288 bytes; SHA-256
`437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43`).
Windows Installer administrative extraction completed with status `0` and
yielded one `soffice.exe`. The package was unsigned and was not installed during
this run. The
parent build script exited before its final dist copy/manifest step, so this is
not recorded as an end-to-end wrapper success. That older MSI was later
published separately as a normal release; the publication does not change this
run's build or installer-lifecycle boundary.

The extracted MSI payload then supplied two off-screen runs through clean
low-level driver commit `beed66ca6ed2503e6170ee1e1158247f1c2f0140`:

- the default-GPU run kept a stable owned `LibreOfficeDev`/`SALFRAME` process and
  a nonempty 96-node accessibility tree, but `PrintWindow` returned a blank
  client. The rejected capture is preserved under
  [`20260720-012601-577059e274-vs2026-msi`](evidence/runs/20260720-012601-577059e274-vs2026-msi/);
- the software-raster fallback run kept the same exact package and Material
  opt-in, captured a genuine Home/Recent Documents view, used background input
  to navigate to Templates, captured that gallery, and produced two complete
  bounded UNO trees with no collector errors. It shut down normally
  over its unique UNO pipe and released the off-screen desktop. The accepted
  manifest and results are under
  [`20260720-012853-577059e274-vs2026-msi-raster`](evidence/runs/20260720-012853-577059e274-vs2026-msi-raster/).

That second run remains accepted historical proof. A later launch-site audit
found that its product binary forwarded only four of five updater installer
arguments and omitted `REBOOT=ReallySuppress`. Corrected source commit
`fbba560e27db26de605c40aa237c554c1f0744b1` forwards all five arguments and
produced a new extracted candidate. A later Sandbox update log showed that its
two `REINSTALL` properties prevented the new ProductCode from selecting
features even though the MSI found the old ProductCode. Current source instead
uses four major-update arguments—`/i`, the staged MSI,
`REBOOT=ReallySuppress`, and `MSIRESTARTMANAGERCONTROL=DisableShutdown`—and
retains the `REINSTALL` properties only for repair. The focused updater suite
asserts that split, exclusive staging creation, the protected DACL, and the
retained read lock. The five-argument corrected runtime was first
exercised in accepted light run
[`20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/),
whose two captures remain immutable historical proof.

A fresh run of the newest exact `393263ad924eae8d64b4f9a35bd6486ef83578fc`
MSI payload used that same committed harness revision, clean driver commit
`547a102a49169d41da876de217856229ab7c03a1`, and a dedicated same-token MCP
session. The driver sampled HWND/PID/thread/DPI atomically inside its off-screen
desktop enumeration callback. This run supplies the canonical light gallery
trio and visibly verifies that the Start Center footer contains Help and
Extensions but no Donate control:

- Home/Recent Documents captured at `1920×1117`, 201,423 bytes, SHA-256
  `c339a8516ca84489f3a96b53cf63b5e448692cc327c3a7683622d2fa64f5ee84`;
- one background Tab transition exposed a visible `Open File` focus ring in a
  201,691-byte `1920×1117` capture, SHA-256
  `b799b696902744cbb80be340c6319cfa899308031d019bddfa6cd06d2476427b`;
- background pointer navigation reached Templates, whose 209,254-byte
  `1920×1117` capture has SHA-256
  `11e3762201ee5b8e516a4cd32b94092491269e1c9415d4d8c181feaa97fc759c`;
- the three bounded UNO trees reported 93/46, 93/46, and 108/61 total/visible
  nodes, zero errors, and `partial=false`; the focus tree exposes `Open File` as
  its sole `FOCUSED` node;
- normal UNO termination succeeded without forced process cleanup, exact-payload
  processes and headless windows reached zero, the desktop closed, and the
  dedicated driver stopped.

The accepted manifest and results are under
[`20260720-143309-393263ad92-windows-headless-light`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/).
This verifies only that exact extracted runtime UI. It does not execute or
prove MSI install, repair, upgrade, uninstall, or restart-suppression lifecycle
behavior.

The canonical dark and forced-high-contrast runs now use the same exact
`393263ad9` payload with harness `75c119e395b9689e2c97341d5f63128db10c255a`
and driver `547a102a49169d41da876de217856229ab7c03a1`. Both use dedicated
same-token loopback MCP sessions. Keeping
the GUI and the matching Python/UNO collector at the same integrity level avoids
the named-pipe block produced by the elevated always-on service:

- [`20260720-144200-393263ad92-windows-headless-dark`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/)
  forced `ApplicationAppearance=2` and `HighContrast=1`; Home, one background
  Tab focus state, and Templates captured at `1920×1117`. The focus tree exposes
  exactly one `FOCUSED` node, the `Open File` push button. Its three trees report
  93/46, 93/46, and 108/61 total/visible nodes, zero errors, and no truncation;
- [`20260720-144249-393263ad92-windows-headless-highcontrast`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/)
  forced `ApplicationAppearance=1` and `HighContrast=2` and passed the same three
  checkpoints, including the accessible `Open File` focus state and complete
  93/46, 93/46, and 108/61 trees. Both runs visibly show Help and Extensions
  without the retired footer Donate control.

All three canonical appearance runs terminated normally, reached zero
exact-payload processes and headless windows, closed the desktop handle, stopped
the dedicated MCP process tree, and passed visual/sensitive-data review. The
reusable driver is
[`bin/Run-Windows-Headless-Smoke.ps1`](../bin/Run-Windows-Headless-Smoke.ps1);
its PNG analyzer rejects blank captures and its collector emits an optional
progress record so a blocked UNO boundary fails with diagnosable evidence.

The same corrected 199,688,192-byte MSI is now the normal public, non-draft,
non-prerelease Latest release
[`windows-msi-local-20260720-fbba560e2`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2),
published at 2026-07-20T06:44:07Z for exact target
`fbba560e27db26de605c40aa237c554c1f0744b1`. Its four cache-busted public
Latest downloads matched the release bytes; the MSI is 199,688,192 bytes with
SHA-256
`180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`.
Release publication does not expand the accepted UI or MSI-lifecycle scope.

This closes the scoped light, dark, forced-high-contrast, pointer-navigation,
and one-step keyboard-focus Start Center smoke on software raster rendering.
System-driven contrast, deeper keyboard traversal, accelerated capture, 200%
scale, localization/direction, suite applications, dialogs, updater, and MSI
lifecycle coverage remain open. The Material
environment gates were requested; that fact alone does not prove every visible
control used the file definition or that the surface is Material-complete.

## Evidence principles

- test a binary built from the exact recorded fork commit;
- never substitute a design mockup, generated image, or unrelated upstream
  screenshot for a capture;
- keep raw images unchanged; record any crop as a derived file;
- record failures and blank captures instead of selecting only attractive runs;
- remove personal documents, credentials, usernames, and unrelated windows;
- treat an image as evidence only after its manifest and scenario pass review.

## Accessibility collector

`bin/dump-a11y.py` is the source-controlled companion to the low-level
off-screen driver. It must be launched with the matching built
`instdir/program/python.exe`, never a system Python. It connects only to the
run-scoped UNO pipe, obtains the current frame's container-window
`XAccessible` root, and records a bounded read-only tree of role, name,
description, state, child count, and optional parent-relative bounds.

The collector intentionally does not retrieve accessible text, invoke actions,
move focus, or attach listeners. Its traversal is capped at 5,000 nodes, 500
children per node, depth 32, and 256 characters per name/description. Every
limit or per-node failure is recorded as partial evidence rather than silently
discarded. A run must require at least one `SHOWING` or `VISIBLE` node and
pair the JSON output with the matching screenshot SHA-256 in its manifest.
This implements an a11y evidence mechanism; it is not a claim that a runtime
accessibility scenario has passed.

`--progress-output` may be used by automation to record connection, frame,
accessibility-root, collection, write, and termination stages. It is diagnostic
only; the completed tree and screenshot binding remain the acceptance evidence.

## Run identity and storage

Use a run identifier of the form `YYYYMMDD-HHMMSS-<short-commit>-<platform>`.
When real evidence exists, store it under a run directory below
`docs/evidence/runs/`. Each run should contain:

```text
manifest.json
results.json
screenshots/
recordings/        # optional and normally retained outside Git history
logs/
```

Do not create screenshot entries in the public gallery until the referenced
files actually exist. Large recordings should use an approved artifact store or
Git LFS policy before being committed.

The manifest must record:

- fork commit, upstream baseline, dirty-worktree state, and build identifier;
- operating system, architecture, desktop backend, locale, theme, contrast,
  display scale, window size, atomic HWND/process/thread/DPI identity, and font
  configuration;
- LibreOffice command, isolated user-profile location, enabled feature flags,
  and document fixture hashes;
- driver repository commit and MCP/server version;
- scenario identifiers, expected checkpoints, result, and reviewer;
- SHA-256 hash and pixel dimensions of every committed image.

`bin/Run-Windows-Headless-Smoke.ps1` writes schema-v2 `results.json` and
`manifest.json` candidates with these fields. Pass `-SourceRoot` when the exact
clean source checkout is not the harness checkout; its `HEAD` must equal
`-SourceCommit`, and the payload's `program/version.ini` `buildid` must equal
that same full `source.commit`. Every `scenarios[].inventory_ids` list must be
nonempty and contain only stable `WIN-<AREA>-NNN` identifiers from
[`WINDOWS_UI_INVENTORY.md`](WINDOWS_UI_INVENTORY.md). Validation parses that
exact tracked inventory, rejects duplicate scenario references, and rejects IDs
that merely match the shape but do not exist in the inventory.

Both validator modes resolve the portable `screenshots/...` and `logs/...`
paths beneath the manifest directory, reject traversal, re-hash the actual PNG
and a11y JSON, compare byte counts and PNG IHDR dimensions, and validate the
UNO run/screenshot binding and complete accessibility summary. The candidate
records `automation_result: pass` but leaves each scenario
`result: pending_visual_review`; capture existence, input delivery, and a
focused UNO node do not claim that Templates or a visible focus treatment passed
visual review. After real visual and sensitive-data review, set manifest
`status` to `accepted` and every scenario `result` to `pass`, record the
reviewer, and list every scenario exactly once in
`review.reviewed_scenario_ids`. Then run
`bin/Validate-Windows-Headless-Evidence.ps1 -RequireAccepted`. That stricter mode
accepts only `pass` or `accepted-known-issue` review results, requires limitations
for a known issue, and requires a passed sensitive-data review.

Publishable fields use repository-, payload-, or run-relative paths. The exact
launch arguments retain explicit `<run-root>` tokens; the raw path-bearing launch
wrapper and generated profile are runtime-only, and cleanup removes the wrapper.
Never publish a candidate until the sensitive-data review also checks retained
logs for private host paths.

The dedicated MCP server inherits the harness token. The manifest records the
harness mandatory integrity SID, Windows-session equality, and MCP `is_admin`
parity, and explicitly labels the server integrity level as inferred rather than
claiming that its mandatory label was queried directly. Its sanitized origin URL
is read from the sibling checkout rather than inferred from documentation. The
low-level driver's `list_headless_windows` operation records the HWND, owning
process ID, thread ID, and `GetDpiForWindow` result inside the same
`EnumDesktopWindows` callback. The harness consumes that atomic identity instead
of probing an off-screen HWND from the caller desktop. Before capture, the
numeric process ID must equal both the exact payload process and PID-file value,
and the numeric thread ID and DPI must both be positive.

## Fresh and legacy no-nag startup harness

[`bin/Run-Windows-NoNag-Headless-Smoke.ps1`](../bin/Run-Windows-NoNag-Headless-Smoke.ps1)
is the dedicated candidate generator for unsolicited-startup-UI proof. It uses
the same dedicated same-token low-level server, exact process ownership,
PrintWindow capture, bounded UNO collector, and cleanup contract as the Start
Center runner, but launches a blank Writer and deliberately omits every
prompt-suppressive GUI switch. Do not substitute the ordinary Start Center
profile or its launch vector for this test.

Run each profile separately so every candidate has one process/window identity
and one review boundary:

```powershell
$sourceRoot = 'C:\path\to\clean-source'
$payloadRoot = 'C:\path\to\extracted-msi-payload'
$sourceCommit = git -C $sourceRoot rev-parse HEAD
powershell -NoProfile -ExecutionPolicy Bypass `
  -File bin\Run-Windows-NoNag-Headless-Smoke.ps1 `
  -PayloadRoot $payloadRoot -SourceRoot $sourceRoot `
  -SourceCommit $sourceCommit -ProfileMode Fresh

powershell -NoProfile -ExecutionPolicy Bypass `
  -File bin\Run-Windows-NoNag-Headless-Smoke.ps1 `
  -PayloadRoot $payloadRoot -SourceRoot $sourceRoot `
  -SourceCommit $sourceCommit -ProfileMode Legacy
```

The payload is accepted only when `program/version.ini` contains exactly one
40-character `buildid` equal to `-SourceCommit`, and both the source checkout
and sibling low-level driver are clean. `Fresh` creates the profile directory
but requires zero entries immediately before launch; it never pre-creates
`registrymodifications.xcu`. `Legacy` writes a fixed seed that turns the former
first-run, Tip, Welcome/What’s New, promotion, file-association, AutoCorrect
explanation, and crash-report flags on. Its parseable crash seed points to a
nonexistent run-scoped dump and loopback discard URL while
`-env:CrashDumpEnable=false` prevents dump creation. Both modes clear any
inherited `CRASH_DUMP_ENABLE` value in their private wrapper before launch,
because LibreOffice treats every nonempty value, including `0`, as enabled.
The legacy registry document is also closed-schema checked for exact namespace,
path-qualified property set, `oor:op`, lexical type, and value. Sanitized copies
of both legacy seed files are retained under `logs/` and hash-bound in the
manifest.

Both modes launch exactly one blank Writer with an isolated user-installation
URI, `--writer`, `--quickstart=no`, `--language=en-US`, a unique PID file, and a
unique UNO pipe. They must not use `--nologo`, `--norestore`, `--headless`,
`--invisible`, or `--nodefault`. Startup enumerations are retained, ownership is
reconciled to the exact PID-file `soffice.bin`, and the stable phase polls at
500 ms for at least 15 monotonic seconds. Encoded profile URI percents survive
the batch expansion pass, and delayed expansion is disabled in both the outer
and private command processors. Every stable poll must contain exactly one
total and payload-owned Writer `SALFRAME` with the recorded PID, HWND, thread,
and DPI. Thus a prompt from a helper process fails too. The exact loopback
listener PID and creation time must trace to the dedicated MCP root; cleanup
independently proves the root exited and that its endpoint closed.

The screenshot must be nonblank and at least 640×480. Its SHA-256 is passed to
the matching built Python/UNO collector; the tree must be complete, nonempty,
visible, error-free, and expose a menu bar. Titles plus visible/showing
accessible names and descriptions deny the former Tip, Welcome/What’s New, association solicitation,
crash-report, donation/Get Involved, and AutoCorrect-explanation text. Recovery,
Troubleshoot/Safe Mode, macro security, read-only, credential, and extension
compatibility prompts are intentionally not denied. The manual Tip, What’s New,
and Options file-association commands remain source-guarded and are recorded as
retained actions, not silently exercised by startup smoke. Evidence validation
recomputes PID ownership for every retained window and independently rescans
the complete accessibility artifact instead of trusting its summary field.

Each candidate retains `screenshots/writer-<profile>-startup-no-nags.png`, its
paired `logs/a11y-writer-<profile>-startup-no-nags.json`, and
`logs/window-polls.json`. It still requires visual and sensitive-data review
before `Validate-Windows-Headless-Evidence.ps1 -RequireAccepted` can accept it.
No such fresh or legacy candidate has been run or accepted for this harness
slice yet.

An administratively extracted MSI payload is not installed under the historical
product-registration keys in `HKLM`. The old automatic file-association check
returned before showing UI when that registration was absent. Consequently,
zero association prompts in this extracted-payload harness is not runtime proof
of that registry-gated branch; use an MSI-installed disposable Windows Sandbox
or VM for the remaining check. Do not mutate the host registry to manufacture
that proof.

## Windows off-screen workflow

The tool names below are the low-level MCP operations expected by this plan.
Exact arguments belong in the run manifest or automation macro.

1. Require `instdir/program/soffice.exe` to exist, hash it, record the exact
   source commit, and verify the detached build worktree is clean.
2. Create a unique run ID, desktop name, UNO pipe, and empty profile under
   `%LOCALAPPDATA%\Temp\LibreOfficeMaterialQA\<run-id>`; fail if the profile
   pre-exists or is nonempty.
3. Snapshot processes whose executable path is the exact fork `instdir/program`
   directory, then start a dedicated short-lived driver session.
4. Call `create_headless_desktop` with the run-scoped desktop name.
5. Call `launch_on_headless_desktop` with a wrapper command that sets
   `VCL_DRAW_WIDGETS_FROM_FILE=1`, `VCL_FILE_WIDGET_THEME=material`, and
   `SAL_LOG=+WARN.vcl.gdi`, then executes the exact fork binary.
6. For ordinary Start Center evidence, launch with an isolated
   `-env:UserInstallation=file:///...` URL, `--nologo`, `--norestore`,
   `--quickstart=no`, `--language=en-US`, a unique `--pidfile`, and unique
   `--accept=pipe,name=...;urp`. Do not use `--headless`, `--invisible`, or
   `--nodefault`, because each suppresses the Start Center GUI. The dedicated
   no-nag procedure above intentionally uses a different blank-Writer launch
   vector and omits all five suppression switches.
7. Poll `list_headless_windows` for at most 90 seconds. Resolve a nonempty
   LibreOffice/SALFRAME title/class with positive dimensions. Require numeric
   `process_id`, `thread_id`, and `dpi` fields sampled by the enumeration
   callback; missing, zero, or wrong-owner values are retry diagnostics, never
   accepted evidence.
8. Read the PID file and require that PID's executable path to be inside the
   exact fork build. Require the enumerated `process_id` to equal that PID, then
   bind stability to the same HWND plus process ID for three consecutive polls;
   never hard-code an HWND or query it from the caller desktop.
9. Capture the resolved window and require successful/rendered flags, positive
   dimensions, nonblank pixel statistics, expected title/class, SHA-256, and
   visual review before driving input.
10. Use runtime-resolved child HWNDs and background-capable operations; record
    any coordinate input and avoid relying on modifier chords.
11. Run `bin/dump-a11y.py` with the built Python/UNO runtime, its exact unique
    pipe, `--require-visible`, and the screenshot hash. Require a nonempty
    JSON tree before treating screenshot-based smoke steps as accessibility
    evidence.
12. Shut down normally over the unique UNO pipe with the built Python/UNO
    runtime, then poll until the recorded PID and windows disappear.
13. If normal termination fails, preserve a failure capture/log and terminate
    only after revalidating that exact PID, path, and creation time. Never kill
    every process named `soffice.exe`.
14. Release the desktop, end the dedicated driver process so cached desktop
    handles close, and verify cleanup.
15. Hash files, write results, review for sensitive data, and only then add
    accepted captures to the screenshot registry.

For the current opt-in Material slice, the future LibreOffice launch environment
must include `VCL_DRAW_WIDGETS_FROM_FILE=1` and
`VCL_FILE_WIDGET_THEME=material`. The manifest must record both values. Their
presence alone does not prove that the definition loaded or rendered.

`show_headless_desktop` is reserved for a human-only step such as authentication
and should not be needed for deterministic LibreOffice test fixtures. If it is
used, the manifest must say why and when the desktop was hidden again.

## Linux virtual-display workflow

1. Start a run-scoped Xvfb display with `create_virtual_display`.
2. Launch the built binary with `launch_on_virtual_display` and an isolated
   profile.
3. Enumerate windows using `list_virtual_display_windows`.
4. Route deterministic input to that display and capture with
   `screenshot_virtual_display` plus window-specific tools when available.
5. Collect logs and stop the display with `stop_virtual_display` in cleanup.

Wayland-native coverage requires a separate documented runner; Xvfb evidence
must not be labeled as native Wayland evidence.

## Minimum scenario matrix

Every materially changed surface should cover applicable rows:

| Axis | Required cases |
| --- | --- |
| Theme | light, dark, system/high contrast |
| Display | 100%, 125% or platform fractional scale, 200% |
| Window | compact, medium, expanded; maximized where relevant |
| Input | keyboard-only path and pointer path |
| Direction | left-to-right and right-to-left representative locale |
| Text | default locale, long translation, representative CJK/CTL |
| State | default, hover, focus, pressed, selected, disabled, invalid where applicable |
| Motion | normal and reduced-motion preference |
| Rendering | supported accelerated path and software fallback |

The initial smoke scenarios are:

- launch and dismiss start center;
- create/open/save/close one Writer document;
- enter/formula/save/close one Calc sheet;
- create/present/close one Impress deck;
- open shared Options and one file picker;
- traverse primary commands with keyboard focus;
- repeat a representative scenario in dark and high-contrast modes.

## Capture acceptance

A capture is accepted only when all are true:

- the image file exists and its hash matches the manifest;
- the scenario completed at the recorded commit;
- window ownership and expected UI state are confirmed;
- the image is not blank, occluded, stale, stretched, or from another build;
- no sensitive or unrelated desktop content appears;
- the registry links to that exact real file;
- a reviewer records pass, fail, or accepted-known-issue.

Visual approval does not prove interaction, accessibility, localization,
performance, or document fidelity. Those results remain separate fields.

## Failure and cleanup rules

- preserve the first failing screenshot and relevant logs;
- cap retries and report flaky scenarios explicitly;
- kill a process only after normal shutdown and timeout handling fail;
- always release off-screen desktop or virtual-display resources;
- do not run destructive driver operations against processes outside the
  run-scoped allowlist;
- never enable unattended elevated execution on a shared workstation.

## Publication gate

After review, update [`SCREENSHOTS.md`](SCREENSHOTS.md), the project site's
evidence count, the roadmap state, and `.codex/memory/evidence-ledger.md` in the
same change. Until then, public evidence slots stay empty.
