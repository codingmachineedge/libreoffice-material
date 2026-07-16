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

## Current LibreOffice build blocker

A corrected host audit found a usable Visual Studio Build Tools 2022
installation, but no complete supported LibreOffice build profile. WSL 2.7.10
is enabled with zero installed distributions, the Unix/configuration and Java
tooling is incomplete, and the active imported worktree is unsuitable for a
configure run because most tracked files were materialized with CRLF endings.
A fresh LF worktree and a completed build profile are required. The
`vcl_widget_definition_reader_test` C++ target was therefore not run, no
`soffice` binary containing these changes was launched, and no real LibreOffice
headless capture exists.

## Evidence principles

- test a binary built from the exact recorded fork commit;
- never substitute a design mockup, generated image, or unrelated upstream
  screenshot for a capture;
- keep raw images unchanged; record any crop as a derived file;
- record failures and blank captures instead of selecting only attractive runs;
- remove personal documents, credentials, usernames, and unrelated windows;
- treat an image as evidence only after its manifest and scenario pass review.

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

1. Build LibreOffice and record the artifact plus source state.
2. Create an isolated LibreOffice user profile containing no personal data.
3. Call `create_headless_desktop` with a unique run-scoped name.
4. Call `launch_on_headless_desktop` to start the built `soffice` binary with
   the isolated profile and deterministic test fixture.
5. Poll `list_headless_windows` until the expected start center or document
   window is stable; fail with a timeout rather than waiting forever.
6. Use `list_child_windows` and background-capable input methods where reliable.
   Prefer semantic control handles over fixed screen coordinates.
7. Exercise the scenario and capture required checkpoints with `screenshot`
   using the target window handle.
8. Verify every capture is nonblank, has the expected dimensions, and belongs
   to the expected process/window title.
9. Close the application normally, collect logs, and call
   `close_headless_desktop` even after a failed scenario.
10. Hash files, write results, review for sensitive data, and only then add
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
