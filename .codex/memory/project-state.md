# Project state

Last reviewed: 2026-07-16

## Objective

Modernize the complete LibreOffice GUI using Material Design principles while
retaining the native implementation languages and upstream office-suite
functionality. Prove visible work through real builds and off-screen desktop
testing, publish project documentation and evidence, and preserve upstream
licensing and provenance.

## Current milestone

**Phase 1 — sixth Material VCL source milestone, in progress. Phase 0's native
build/evidence gate remains open.**

The repository contains an imported LibreOffice source baseline, six native
Material source milestones, a design contract, roadmap, published GitHub Pages
site, screenshot registry, and headless evidence plan. The third milestone adds
matched light/dark profiles, source-level high-contrast fallback routing,
native-style restoration and dynamic focus-policy refreshes, explicit headless
dark selection, standalone spin controls, and a dedicated headless drawing test
target. The automation harness has passed a Notepad-only off-screen preflight.
The fourth milestone adds strict semantic typography roles that derive from the
captured native font baseline instead of replacing platform/user fonts.
The fifth milestone closes all 72 `StyleSettings` color slots with exact
Material mappings, including list/collection and warning/error feedback roles,
while keeping the ten additions optional for partial legacy themes.
The sixth milestone adds eight semantic corner roles, resolves a single named
radius into both existing native rectangle axes, converts all 146 rounded
Material rectangles, and preserves the 11 implicit square rectangles plus the
legacy numeric `rx`/`ry` path.
The native source has not been built or run as LibreOffice, so this does not
prove a whole-GUI rewrite or any completed application surface.

## Recorded facts

- GitHub repository: `codingmachineedge/libreoffice-material`.
- Default branch observed locally: `main`.
- Upstream: `LibreOffice/core`.
- Imported upstream commit: `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21`.
- Fork import commit: `44d393283e776c7e099763496c57b02ae509cd15`.
- Initial Material implementation commit:
  `46807f76f9a744fe61732e90f6085cc82eef16f5`.
- Second Material VCL source milestone commit:
  `c4414aa3919642ebb1079427b5ce27ce77049901`.
- Third Material VCL source milestone commit:
  `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8`.
- Fourth Material VCL source milestone commit:
  `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`.
- Fifth Material VCL source milestone commit:
  `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`.
- The two commits shared tree object
  `68ccb73abac4f7da67f894f11b0802627e90b474` when verified.
- Initial native source slice: packaged Material definition; opt-in file-widget
  theme selection/cache/fallback; definition-aware support; palette reader
  coverage; Material control/menu/progress states; and Start Center
  spacing/header/surface/recent/template treatment.
- Second Material VCL source milestone: 19 semantic light color tokens with
  order-independent resolution; strict invalid/unknown/duplicate definition
  rejection; 70 definition-backed parts and 172 states; expanded reader tests
  and negative fixtures; combo/RTL, toolbar grip, region, slider, and graphics
  cache corrections; and a standalone static source validator.
- Third Material VCL source milestone: matched light/dark palettes with 19
  tokens each; 74 definition-backed parts and 190 states; strict multi-palette
  parsing; resolved dark-profile selection; high-contrast native/generic
  fallback; captured pre-Material style/framework restoration; dynamic
  native-focus recomputation; Qt proxy/no-native high-contrast detection;
  explicit headless dark selection; shared theme state; standalone directional
  spin controls; and a dedicated public-API headless draw CppUnit target.
- Fourth Material VCL source milestone: typed `body`, `label`, and `title`
  roles; exact role/attribute/scale/minimum-weight parsing; native family, style,
  charset, language, pitch, orientation, width, and icon-font preservation;
  nonshrinking relative size policy; baseline-derived idempotent refresh;
  accessibility-safe title-height minima; expanded XML-walker APIs/tests; and
  malformed typography fixtures.
- Fifth Material VCL source milestone: 23-token light/dark palettes; an exact
  72-slot Material style schema; optional accent, list-box, alternating-row,
  warning, and error reader fields; conditional renderer application that
  preserves omitted legacy values; and source-level real-renderer dispatch,
  idempotence, and high-contrast fallback assertions.
- Sixth Material VCL source milestone: eight strict semantic corner roles;
  optional order-independent `shapes` parsing; singular `radius="@token"`
  resolution into the existing `mnRx`/`mnRy` fields; local token storage that
  avoids exported reader-layout changes; 146 converted rounded rectangles and
  11 unchanged implicit squares; legacy numeric radius compatibility; and 23
  new malformed-shape reader fixtures.
- Local source validation passes for 2 schemes, 23 color tokens each, 3
  typography roles, 8 shape tokens, 72 style slots, 74 parts, 190 states,
  selected WCAG contrast pairs, native font/shape source invariants, XML
  parsing, and whitespace. All 16 Python validator unittest methods pass. The
  affected C++ targets remain unexecuted.
- GitHub Actions source-validation run `29517978358` completed successfully for
  third-milestone commit `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8`.
- GitHub Actions source-validation run `29522004268` completed successfully for
  fourth-milestone commit `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`,
  including the new validator unittest step.
- GitHub Actions source-validation run `29524039805` completed successfully for
  fifth-milestone commit `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`;
  semantic theme validation, all validator unittests, and Start Center lint each
  passed.
- A detached build worktree exists at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build`, pinned
  to `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`. The modified VCL settings,
  renderer, reader, tests, validator, and Material definition all report
  `w/lf`; the validator and its eleven unittest methods pass from that clean
  worktree.
- Required runtime opt-in: `VCL_DRAW_WIDGETS_FROM_FILE=1` and
  `VCL_FILE_WIDGET_THEME=material`.
- UI driver: sibling repository `lowlevel-computer-use-mcp`, preflighted at
  commit `806d9ba85e4afbc2af58d7499496babfa7c68891`.
- A read-only driver audit found the same clean commit serving MCP on
  `127.0.0.1:8765`. Launch has no environment/cwd fields; window enumeration
  has no PID; generic move/resize/window actions are not off-screen reliable;
  desktop close does not close the app; and long-lived server handle caching
  requires a short-lived driver session for strict teardown proof.
- 2026-07-16 harness preflight: created
  `WinSta0\LibreOfficeMaterialQA`, launched and enumerated an off-screen Notepad
  window (HWND `37291736`, `1920×1125`), captured it through `PrintWindow` with
  `rendered_ok: true`, killed only run-scoped Notepad processes, and confirmed
  teardown when `OpenDesktop` returned Win32 error `2`.
- Temporary preflight capture SHA-256:
  `03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3`;
  it was not retained because it was unrelated to LibreOffice.
- Verified LibreOffice Material screenshots: **0**.
- GitHub Pages source: `site/`; public URL:
  `https://codingmachineedge.github.io/libreoffice-material/`.
- Pages uses GitHub Actions workflow mode. Run `29510014215` deployed commit
  `46807f76f9a744fe61732e90f6085cc82eef16f5` successfully on 2026-07-16;
  follow-up endpoint checks returned HTTP `200` for both `/` and `styles.css`.
- Pages run `29513175965` deployed second-milestone commit
  `c4414aa3919642ebb1079427b5ce27ce77049901` successfully; the live index and
  stylesheet returned HTTP `200` and exposed the refreshed milestone/counts.
- Pages run `29517978373` deployed third-milestone commit
  `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8` successfully; the live index and
  stylesheet returned HTTP `200`, exposed the exact unbuilt profile counts, and
  kept the verified-capture count at `0`.
- Pages run `29522004306` deployed fourth-milestone commit
  `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba` successfully; the live index and
  stylesheet returned HTTP `200`, exposed 3 typography roles alongside the
  color/part/state counts, and kept the verified-capture count at `0`.
- Pages run `29524040737` deployed fifth-milestone commit
  `a644ed9abb6d5112f182ff7ec6e0826b1754c89e` successfully; the live index and
  stylesheet returned HTTP `200`, exposed the exact 23-token, 72-style-slot,
  74-part, 190-state summary, and kept the verified-capture count at `0`.

## Required next gates

1. complete a supported LibreOffice build profile and document a reproducible
   native build from the prepared detached LF worktree;
2. run `tools_test`, `vcl_widget_definition_reader_test`, and
   `vcl_file_definition_widget_draw_test` against the local Material changes;
3. launch the built start center with the two opt-in variables and an isolated
   profile on the proven headless desktop;
4. preserve the first LibreOffice baseline manifest, result, logs, and reviewed
   screenshot;
5. build/runtime-verify light/dark, focus, shape geometry, and high-contrast
   routing, complete forced-color/platform signal coverage, and implement the
   remaining token families and VCL primitives;
6. continue through every phase in `ROADMAP.md` without skipping suite surfaces.

## Known evidence gaps

- no native fork build is registered in the evidence ledger;
- no headless LibreOffice Material scenario is registered;
- no screenshot is registered;
- no application surface is verified Material-complete;
- the detached LF worktree is clean, but the host has no complete supported
  LibreOffice build profile: WSL 2.7.10 has zero distributions; selectable VS
  2022 lacks ATL and its configured CMake; registry-selected SDK 28000 lacks
  required desktop/MSI files that installed SDK 26100 contains; OpenJDK 21 is
  outside `PATH`; and Ant/JUnit plus other helpers are absent. The C++ unit
  targets and real application capture have not run.

## Multi-repository boundary

The low-level driver is external test tooling, not another deliverable of the
LibreOffice Material product. One product repository remains sufficient, so no
additional project-level master repository or product submodule graph is
currently justified; this does not describe LibreOffice's imported optional
upstream source submodules. If later work creates several independently
versioned product repositories, a separate master repository must pin them as
Git submodules. That orchestration decision does not convert unverified external
state into evidence and must record exact submodule commits.
