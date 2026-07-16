# Project state

Last reviewed: 2026-07-16

## Objective

Modernize the complete LibreOffice GUI using Material Design principles while
retaining the native implementation languages and upstream office-suite
functionality. Prove visible work through real builds and off-screen desktop
testing, publish project documentation and evidence, and preserve upstream
licensing and provenance.

## Current milestone

**Phase 1 — second Material VCL source milestone, in progress. Phase 0's native
build/evidence gate remains open.**

The repository contains an imported LibreOffice source baseline, two native
Material source milestones, a design contract, roadmap, published GitHub Pages
site, screenshot registry, and headless evidence plan. The second milestone
adds semantic tokens, a strict definition reader, expanded shared-control state
coverage, renderer corrections, and source validation. The automation harness
has passed a Notepad-only off-screen preflight. The native source has not been
built or run as LibreOffice, so this does not prove a whole-GUI rewrite or any
completed application surface.

## Recorded facts

- GitHub repository: `codingmachineedge/libreoffice-material`.
- Default branch observed locally: `main`.
- Upstream: `LibreOffice/core`.
- Imported upstream commit: `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21`.
- Fork import commit: `44d393283e776c7e099763496c57b02ae509cd15`.
- Initial Material implementation commit:
  `46807f76f9a744fe61732e90f6085cc82eef16f5`.
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
- Local source validation passes for 19 tokens, 70 parts, 172 states, selected
  WCAG contrast pairs, the Start Center UI linter, XML parsing, C++ formatting,
  and whitespace. The C++ unit target remains unexecuted.
- Required runtime opt-in: `VCL_DRAW_WIDGETS_FROM_FILE=1` and
  `VCL_FILE_WIDGET_THEME=material`.
- UI driver: sibling repository `lowlevel-computer-use-mcp`, preflighted at
  commit `806d9ba85e4afbc2af58d7499496babfa7c68891`.
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

## Required next gates

1. create a detached LF worktree, complete a supported LibreOffice build
   profile, and document a reproducible native build for the fork;
2. run `vcl_widget_definition_reader_test` against the local Material changes;
3. launch the built start center with the two opt-in variables and an isolated
   profile on the proven headless desktop;
4. preserve the first LibreOffice baseline manifest, result, logs, and reviewed
   screenshot;
5. implement dynamic dark/high-contrast/platform color resolution and the
   remaining non-color token families and VCL primitives;
6. continue through every phase in `ROADMAP.md` without skipping suite surfaces.

## Known evidence gaps

- no native fork build is registered in the evidence ledger;
- no headless LibreOffice Material scenario is registered;
- no screenshot is registered;
- no application surface is verified Material-complete;
- Build Tools 2022 is usable, but the host has no complete supported
  LibreOffice build profile: WSL 2.7.10 has zero distributions, required
  Unix/configuration and Java tooling is incomplete, and the active imported
  worktree was mostly materialized with CRLF endings. The C++ unit target and
  real application capture have not run.

## Multi-repository boundary

The low-level driver is external test tooling, not another deliverable of the
LibreOffice Material product. One product repository remains sufficient, so no
master repository or submodule graph is currently justified. If later work
creates several independently versioned product repositories, a separate master
repository must pin them as Git submodules. That orchestration decision does not
convert unverified external state into evidence and must record exact submodule
commits.
