# Verification log

This file records checks of documentation and site infrastructure. These checks
do not prove the native LibreOffice UI has been rebuilt or tested.

## 2026-07-16 — initial documentation and site foundation

- **Upstream import comparison:** `git rev-parse` returned tree object
  `68ccb73abac4f7da67f894f11b0802627e90b474` for both fork import commit
  `44d393283e776c7e099763496c57b02ae509cd15` and upstream commit
  `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21`; `git diff --stat` between those
  commits was empty.
- **HTML and Markdown integrity:** a read-only Node checker found 15 unique HTML
  IDs, validated 22 HTML links, validated relative links across 12 Markdown
  files, confirmed 197 balanced CSS brace pairs, and reported no missing local
  target.
- **Media truthfulness:** the checked site and project documentation contained
  no `<img>`, inline `<svg>`, Markdown image embed, or CSS `url()` reference.
- **Whitespace:** full `git diff --check` exited successfully after authored
  documentation/site files were normalized to UTF-8 LF without a byte-order
  mark.
- **Trackability:** Git status reported `docs/` as untracked rather than ignored
  after the Doxygen ignore rule was narrowed for authored Markdown and evidence.

Not verified by these checks:

- GitHub Pages deployment (requires repository settings and a workflow run);
- browser rendering on supported viewport and assistive-technology matrices;
- native LibreOffice build, headless launch, interaction, or screenshot capture.

## 2026-07-16 — low-level off-screen harness preflight

- Driver checkout commit:
  `806d9ba85e4afbc2af58d7499496babfa7c68891`.
- Interface: Cheap Version exact functions from the local
  `lowlevel-computer-use-mcp` repository.
- Created `WinSta0\LibreOfficeMaterialQA` and launched Notepad on it.
- Enumerated `Untitled - Notepad` as HWND `37291736` at `1920×1125`.
- `PrintWindow` capture reported `rendered_ok: true` with SHA-256
  `03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3`.
- Cleanup killed only run-scoped Notepad processes; a subsequent `OpenDesktop`
  returned Win32 error `2`, confirming the named desktop no longer existed.
- The capture was temporary and was not registered, published, or retained.

Scope conclusion: Windows off-screen harness mechanics passed for Notepad. No
LibreOffice binary was built or launched, so accepted Material build/UI evidence
remains zero.

## 2026-07-16 — native verification blocker

The earlier blanket statement that Windows-native prerequisites were
unavailable is superseded by this component-level audit:

- Visual Studio Build Tools 2022 is complete and launchable at `C:\Program`,
  with MSVC 19.44, MSBuild 17.14, and Windows SDKs. ATL, LLVM, and bundled CMake
  were not present in that instance.
- Visual Studio 2026 Enterprise contains MSVC 19.51, Clang 22.1.3, ATL, and
  CMake, but installer state `13` is incomplete/unregistered. ATL was observed
  for toolset 14.51, not the selected 14.52 toolset.
- WSL 2.7.10 is enabled and running with zero installed distributions.
- The available Git Bash environment lacks `make`, `autoconf`, `pkgconf`,
  `flex`, `bison`, `gperf`, `nasm`, and `zip`.
- Java, Ant, and JUnit are absent; the Docker daemon is stopped.
- `git ls-files --eol` reported 149,218 tracked paths: 51,657 with `w/crlf`
  and 17 with `w/mixed`; `autogen.sh` itself reported `i/lf w/crlf`. A fresh
  detached worktree created with `core.autocrlf=false` is required before
  configure rather than normalizing the active development worktree.

Scope conclusion: usable compiler components exist, but there is no complete
supported LibreOffice build profile. `vcl_widget_definition_reader_test` and a
real `soffice` capture were not run.

## 2026-07-16 — local implementation source audit

Read-only inspection of the dirty worktree confirmed source for:

- packaged `vcl/uiconfig/theme_definitions/material/definition.xml`;
- `VCL_FILE_WIDGET_THEME` selection with safe theme-name validation, a
  mutex-protected cache keyed by theme, and fallback to `online`;
- Windows non-printer graphics invoking the existing widget-backend initializer,
  which only selects file definitions when `VCL_DRAW_WIDGETS_FROM_FILE` is
  present;
- definition-aware support reporting for existing fallback behavior;
- Material controls, menus, progress states, expanded reader palette mappings,
  and corresponding unexecuted C++ assertions;
- Start Center spacing/header/surface/recent/template source changes.

Scope conclusion: implementation source exists locally. This inspection is not
a compiler, unit-test, runtime, accessibility, or visual result.

## 2026-07-16 — second Material VCL source milestone validation

- `bin/check-material-theme.py` passed with 19 semantic color tokens, 70
  definition-backed parts, and 172 states. It also checked palette-only color
  literals, unused/unknown token references, required control parts, checkbox
  and radio matrices, combined tab/menu/toolbar states, slider states, and
  selected WCAG contrast pairs.
- The validator passed Python bytecode compilation with the sibling driver's
  isolated Python environment.
- `bin/lint-ui.py sfx2/uiconfig/ui/startcenter.ui` exited successfully.
- PowerShell XML parsing succeeded for the Material definition and five new
  positive/negative reader fixtures.
- Visual Studio Clang 22.1.3 `clang-format --dry-run --Werror` passed for the
  modified C++ files, and `git diff --check` was clean.
- Read-only source reviews found and prompted fixes for unreachable Frame
  drawing, selected+focused menu items, checked+pressed toolbar buttons,
  composite combo RTL geometry, and a one-pixel button-region mismatch. Frame,
  `LevelBar`, and `ListNet` are intentionally left on existing fallback paths
  pending geometry/semantic coverage.

Scope conclusion: source-level validation passed. The new C++ tests and
fixtures have not been compiled or executed, no LibreOffice binary was launched,
and accepted native application evidence remains zero.

## 2026-07-16 — second-milestone project-site refresh

- Local link validation found 16 unique HTML IDs, validated 22 HTML links, and
  validated 46 Markdown links across 12 authored Markdown files.
- The in-app browser rendered the refreshed Phase 1 status at the default
  desktop viewport with `clientWidth = scrollWidth = 1265` and no out-of-bounds
  elements.
- A temporary `390×844` viewport reported `clientWidth = scrollWidth = 375`,
  no out-of-bounds elements, and correctly stacked the hero and implementation
  cards. The viewport override was reset afterward.
- Visual inspection found a sticky-header paint artifact caused by the
  translucent backdrop treatment. Replacing it with an opaque semantic surface
  removed the artifact on the repeated scrolled desktop/mobile capture.
- The browser console reported no messages. Preview tabs and the run-scoped
  local HTTP server were closed after verification.

Scope conclusion: the documentation site refresh is locally render-verified.
Temporary site captures are not LibreOffice application evidence and were not
retained or added to the screenshot registry.

## 2026-07-16 — status-site refresh

- Read-only link checks found 16 unique HTML IDs, validated 22 HTML links, and
  checked relative links across 12 Markdown files.
- CSS inspection found 218 balanced brace pairs and no remaining layout-width
  `100vw`, negative horizontal margin, or `calc(50% - 50vw)` rule.
- The earlier evidence-section and current-roadmap overflow risks were replaced
  with paint-only full bleed and normal layout margins.
- No image element, inline SVG, Markdown image embed, CSS `url()`, missing local
  target, UTF-8 BOM, CRLF, or trailing whitespace was found in scoped files.
- A separate in-app browser session rendered the live local site after the CSS
  fix. Desktop reported `clientWidth = scrollWidth = 1265`; a `390×844`
  viewport reported `clientWidth = scrollWidth = 375`. A DOM geometry scan
  found no element beyond either viewport.
- The hero, direction, evidence, roadmap, and provenance sections were visually
  inspected, and the browser console reported no warnings or errors. These are
  project-site checks only, not LibreOffice application evidence.

## 2026-07-16 — GitHub publication

- Initial Material implementation commit
  `46807f76f9a744fe61732e90f6085cc82eef16f5` was pushed directly to remote
  `main`.
- Repository Pages was configured for GitHub Actions workflow deployment.
- Pages workflow run `29510014215` completed with conclusion `success` for that
  commit.
- The published URL is
  `https://codingmachineedge.github.io/libreoffice-material/`.
- Direct follow-up requests returned HTTP `200` for the published index and
  `styles.css`; the index title was
  `LibreOffice Material — native office UI, thoughtfully renewed`.

Scope conclusion: the documentation/status site is publicly deployed. This
does not change the native application evidence count, which remains zero until
a fork build and LibreOffice headless scenario pass the evidence contract.

## 2026-07-16 — second Material milestone publication

- Commit `c4414aa3919642ebb1079427b5ce27ce77049901` was pushed directly to remote
  `main`.
- GitHub Actions run `29513175997` (`Validate Material UI source`) completed
  with conclusion `success` for that commit.
- GitHub Actions run `29513175965` (`Deploy project site to GitHub Pages`)
  completed with conclusion `success` for that commit.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contained the Phase 1 second-milestone label and the 19-token,
  70-part, 172-state summary; the stylesheet contained the opaque header fix
  and no `backdrop-filter` rule.

## 2026-07-16 — detached LF build worktree preparation

- Created
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` with
  `git -c core.autocrlf=false worktree add --detach` at source commit
  `c4414aa3919642ebb1079427b5ce27ce77049901`.
- The detached worktree was clean. `git ls-files --eol` reported `w/lf` for
  `autogen.sh`, `configure.ac`, `vcl/source/gdi/FileDefinitionWidgetDraw.cxx`,
  and the Material definition.
- `bin/check-material-theme.py` passed from the detached worktree with 19
  tokens, 70 parts, and 172 states.

Scope conclusion: the source is now prepared in a line-ending-safe worktree for
a native configure/build attempt. No toolchain was installed, no C++ target was
run, and no LibreOffice application evidence was created.
