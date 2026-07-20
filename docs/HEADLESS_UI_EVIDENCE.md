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
produced a new extracted candidate. The corrected runtime was exercised through
the same clean driver commit and is now the canonical gallery run:

- Home/Recent Documents captured at `1920×1117`, 203,493 bytes, SHA-256
  `e4a21bd16c99ef360749dd72557a8d5a9df7c38d0a51122e8ca0058c57464501`;
- background navigation reached Templates, whose `1920×1117`, 212,506-byte
  capture has SHA-256
  `1f9f0e9614c0eb6bd0c0e9cea6909982a8900ed532e03f7bbdd72751a87294ab`;
- paired bounded UNO trees reported 96/49 and 111/64 total/visible nodes, zero
  errors, and `partial=false`;
- normal UNO termination succeeded, matching run-scoped processes and headless
  windows both reached zero, and the off-screen desktop closed.

Its manifest and results are under
[`20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/).
This verifies only the corrected extracted runtime UI. It does not execute or
prove MSI install, repair, upgrade, uninstall, or restart-suppression lifecycle
behavior.

The same corrected 199,688,192-byte MSI is now the normal public, non-draft,
non-prerelease Latest release
[`windows-msi-local-20260720-fbba560e2`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2),
published at 2026-07-20T06:44:07Z for exact target
`fbba560e27db26de605c40aa237c554c1f0744b1`. Its four cache-busted public
Latest downloads matched the release bytes; the MSI is 199,688,192 bytes with
SHA-256
`180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`.
Release publication does not expand the accepted UI or MSI-lifecycle scope.

This closes only the light-profile Start Center launch/navigation smoke on
software raster rendering. Dark, system/high contrast, accelerated capture,
keyboard-only/focus, 200% scale, localization/direction, suite applications,
dialogs, updater, and MSI lifecycle coverage remain open. The Material
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
  display scale, window size, and font configuration;
- LibreOffice command, isolated user-profile location, enabled feature flags,
  and document fixture hashes;
- driver repository commit and MCP/server version;
- scenario identifiers, expected checkpoints, result, and reviewer;
- SHA-256 hash and pixel dimensions of every committed image.

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
6. Launch with an isolated `-env:UserInstallation=file:///...` URL,
   `--nologo`, `--norestore`, `--quickstart=no`, `--language=en-US`, a unique
   `--pidfile`, and unique `--accept=pipe,name=...;urp`. Do not use `--headless`,
   `--invisible`, or `--nodefault`, because each suppresses the Start Center GUI.
7. Poll `list_headless_windows` for at most 60 seconds. Resolve a nonempty,
   stable LibreOffice/SALFRAME window for three consecutive polls; never
   hard-code an HWND.
8. Read the PID file and require that PID's executable path to be inside the
   exact fork build before accepting window ownership.
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
