# Headless UI evidence plan

This plan defines how visible LibreOffice Material work will be exercised on a
real GUI process without taking over the operator's desktop. It is a plan, not a
claim that a Material UI test run has already passed.

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

## Current LibreOffice build blocker

No local fork executable exists. [`LOCAL_WINDOWS_BUILD.md`](LOCAL_WINDOWS_BUILD.md)
defines the source-controlled one-click bootstrap for an isolated VS
2022/Cygwin profile and the opt-in exact-path VS 2026 profile. On 2026-07-19,
this host completed the relevant bootstrap/preflight work, and the explicit VS
2026 Enterprise profile completed an isolated configure at
`a6d9f9a7dbdf10c08afe2eb03239e702ec5172ef`. The subsequent native build reached
third-party compilation but stopped on MSVC v145 C++20's `mdds`
conditional-`noexcept` C2382; the source contains a narrowly scoped workaround
awaiting a fresh full build. This records build diagnosis only—there is still no
completed local binary, MSI, LibreOffice launch, or off-screen scenario. The
hosted Windows workflow still supplies and validates its prerequisites against
a clean LF checkout.

Current-source Linux Actions run `29695793821` and Windows Actions run
`29695815101` at `e4dc8a850c982f33d8722fc203f86591b2993e8b` passed the five
required native C++ targets. The Windows run also passed the legacy CLI payload
check and completed the full LibreOfficeDev installation-set build.

That Windows run did not produce a downloadable artifact: the staging script
recursively collected three MSI files, two of which were LibreOffice working
databases under `idt_files`; its exact-one safety check stopped before upload.
The workflow now scopes collection to the success-only final
`LibreOfficeDev\msi\install\en-US` directory and retains exact-one,
administrative-extraction, and `soffice.exe` checks. A hosted rerun is required
before this plan can claim an MSI or an off-screen LibreOffice scenario.

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
