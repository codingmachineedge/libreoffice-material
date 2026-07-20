# Verification log

This file records source, documentation, and site integrity checks. These checks
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

## 2026-07-16 — third Material VCL source milestone validation

- `bin/check-material-theme.py` reported
  `Material theme OK: 2 schemes, 19 tokens each, 74 parts, 190 states`. It
  validated palette schema parity, token references, required standalone spin
  parts and interaction matrices, unused tokens, and selected per-scheme
  contrast pairs.
- Python AST parsing passed for the validator, `bin/lint-ui.py` passed for the
  Start Center, and PowerShell XML parsing passed for the Material definition
  plus all 13 reader fixtures.
- Visual Studio Clang 22.1.3 changed-line formatting was applied where needed;
  the final tracked-diff dry run reported no remaining changes and the complete
  new headless draw test passed `--dry-run --Werror`. `git diff --check` also
  passed.
- Independent read-only reviews found and prompted fixes for an invalid Qt
  damage-path cast, Qt/Cairo overwriting the file/LibreOfficeKit widget backend,
  and menu-local refreshes losing resolved forced-high-contrast enable or
  disable values. A deeper runtime review also caught stale Material style and
  native-focus state during dynamic high-contrast fallback, a Qt proxy/no-native
  high-contrast signal gap, and missing explicit dark selection in headless
  VCL. The corrected damage, settings, locking, focus, profile, and spin paths
  were re-audited with no remaining source-level correctness blocker reported.
- Non-blocking source caveats remain: Qt high contrast reaches LibreOffice's
  generic drawing because the raw backend does not expose `QtGraphics_Controls`;
  shared per-theme profile state is last-writer-wins for a hypothetical mix of
  light and dark frames; and a platform menu highlight-text override can
  supersede the Material value. None has runtime evidence yet.
- A final read-only compile/API/link audit found matching baseline method
  declarations, definitions, and visibility; valid Qt5/Qt6 proxy APIs and Svp
  override includes; refreshed focus call sites; registered production/test
  objects; and exported spin/toolbar value classes for Windows CppUnit linkage.
  This was static inspection, not compilation or linking.
- The source now declares `vcl_widget_definition_reader_test` and
  `vcl_file_definition_widget_draw_test`; neither target was compiled or run.

Scope conclusion: static source checks pass for the third milestone. No
LibreOffice binary was built or launched, no headless LibreOffice interaction
ran, and accepted application screenshots remain **0**.

## 2026-07-16 — third-milestone project-site refresh

- Local integrity checks found 16 unique HTML IDs, validated 22 HTML links, and
  validated 36 local Markdown links across 11 authored Markdown files. No local
  target was missing and the site still contains no image/SVG/CSS URL asset.
- The in-app browser rendered the third-milestone page at the default desktop
  viewport with `clientWidth = scrollWidth = 1265` and no element outside the
  horizontal viewport.
- A temporary `390×844` override produced
  `clientWidth = scrollWidth = 375`, a single-column hero, no horizontal
  offender, and legible milestone/profile cards. The viewport override was
  reset afterward.
- The rendered page exposed the exact
  `2 schemes · 19 tokens each · 74 parts · 190 states · unbuilt` status and a
  verified-capture count of `0`. The browser console contained no warnings or
  errors.

Scope conclusion: the local documentation site is render-verified for this
refresh. Temporary browser images were not retained and are not LibreOffice
application evidence.

## 2026-07-16 — third Material milestone publication

- Commit `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8` was pushed directly to
  remote `main`.
- GitHub Actions source-validation run `29517978358` completed successfully for
  that commit.
- GitHub Pages run `29517978373` completed successfully for that commit.
- Direct follow-up requests returned HTTP `200` for the published index and
  `styles.css`. The index contained the exact
  `2 schemes · 19 tokens each · 74 parts · 190 states · unbuilt` status and a
  verified-capture count of `0`.
- The clean detached worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` was
  moved without reset from `c4414aa3919642ebb1079427b5ce27ce77049901` to
  `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8`. It remains detached and clean;
  `autogen.sh`, `configure.ac`, the Material renderer/definition, and the new
  headless drawing test report `w/lf`.
- `bin/check-material-theme.py` passed there with 2 schemes, 19 tokens each,
  74 parts, and 190 states; `git diff --check` was clean.

Scope conclusion: source validation, publication, and the line-ending-safe
build-worktree pin are verified for the third milestone. No C++ target or
LibreOffice binary ran, and accepted application screenshots remain **0**.

## 2026-07-16 — fourth Material VCL source milestone validation

- `bin/check-material-theme.py` reported
  `Material theme OK: 2 schemes, 19 tokens each, 3 typography roles, 74 parts,
  190 states`. The checks cover the canonical semantic type roles, exact schema,
  scale bounds, native-font source invariants, palette/profile parity, widget
  coverage, and selected contrast pairs.
- Seven Python unittest methods exercised 30 validator scenarios. They include
  canonical success; duplicate, missing, unknown, nested, text, family-injection,
  scale, weight, processing-instruction, palette-content, settings, and native
  source-guard failures. All passed.
- The Start Center UI linter and Python bytecode compilation passed. PowerShell
  XML parsing passed for 31 relevant files; all 29 reader fixture references
  resolve to an existing file.
- Visual Studio Clang 22.1.3 `--dry-run --Werror` passed for every changed C++
  and header file. `git diff --check` passed. All 38 changed or untracked scoped
  text files are UTF-8 without a byte-order mark and use LF rather than CRLF.
- Workflow YAML parsing passed. Local integrity checks found 16 unique HTML IDs,
  validated 22 HTML links, validated 38 local Markdown targets across 12
  authored files, found balanced CSS, and confirmed that the project site has
  no image, SVG, or CSS URL asset.
- The in-app browser reloaded the local fourth-milestone site. Desktop reported
  `clientWidth = scrollWidth = 1265`; a `390×844` mobile viewport reported
  `clientWidth = scrollWidth = 390`, a single-column hero, and no element beyond
  either horizontal viewport. The exact fourth-milestone source summary and
  verified-capture count `0` were present; browser logs were empty. The viewport
  override was reset, the tab was finalized, and the run-scoped local server was
  stopped.
- Independent source audits found no remaining compile-, API-, link-, parser-,
  fixture-, or build-registration blocker. Minimum-weight tests cover stronger
  native-weight preservation and production `preserve`, `medium`, and
  `semibold` application. This is static inspection, not compilation.
- A fresh host audit still found no supported runnable build profile or
  LibreOffice binary. The low-level driver remains external test tooling with
  no LibreOffice scenario or attributable fork window to capture.

Scope conclusion: repository-side source and project-site checks pass for the
fourth milestone. No affected C++ target was compiled or executed, no
LibreOffice process or window ran, no native renderer behavior was observed,
and accepted application screenshots remain **0**.

## 2026-07-16 — fourth Material milestone publication

- Source commit `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba` was pushed directly to
  remote `main`; the GitHub API subsequently reported the same SHA for remote
  `main`.
- GitHub Actions source-validation run `29522004268` completed successfully.
  Its semantic-theme validation, validator unittest, and Start Center lint
  steps each reported `success`.
- GitHub Pages run `29522004306` completed successfully for the same source
  commit. The Pages API continued to report workflow deployment mode.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contained the exact fourth-milestone color/type/part/state summary
  and a verified-capture count of `0`.
- The clean detached LF worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` was
  moved without reset from `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8` to
  `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`. Key configure, validator, Material
  definition, reader, renderer, and typography source files report `w/lf`.
- From that detached worktree, the validator again reported 2 schemes, 19
  tokens each, 3 typography roles, 74 parts, and 190 states; all seven validator
  unittest methods passed; `git diff --check` and worktree status were clean.

Scope conclusion: the fourth source milestone is published, its repository-side
CI and project site are green, and the line-ending-safe build worktree is pinned
to the exact source commit. No C++ target or LibreOffice binary ran, and accepted
application screenshots remain **0**.

## 2026-07-16 — fifth Material VCL source milestone validation

- `bin/check-material-theme.py` reported
  `Material theme OK: 2 schemes, 23 tokens each, 3 typography roles, 72 style
  slots, 74 parts, 190 states`.
- Eleven Python unittest methods passed. The new mutations cover exact and
  unique style mappings, section/child attributes, text, nesting, processing
  instructions, feedback-token values, list/selection/warning/error contrast,
  and native source patterns. A final audit found that nested palette-color
  content and extra attributes were initially accepted; exact `name`/`value`
  attributes, content rejection, and root/settings processing-instruction
  rejection were added and the full suite passed again.
- The native source guard found all ten optional reader fields, their XML
  mappings, conditional renderer setters, the three new public `StyleSettings`
  setter definitions, and the SVP test's real `SalGraphics::UpdateSettings`
  dispatch. A structural check independently counted 72 `ColorSet` fields,
  62 existing plus 10 optional `WidgetDefinitionStyle` fields, and 72 unique
  Material style elements.
- Python bytecode compilation, the Start Center UI linter, and `git diff
  --check` passed. The Material definition and 29 reader fixture XML files
  parsed successfully. All three workflow YAML files parsed successfully.
- Visual Studio Clang 22.1.3 changed-line formatting was applied; a subsequent
  changed-line dry run reported no remaining changes. Every changed text file
  checked at this stage was UTF-8 without a byte-order mark and LF-only.
- Static site integrity found 16 unique IDs, validated 22 HTML links and 38
  local Markdown targets across 12 authored files, found balanced CSS, and
  confirmed no image, inline SVG, or CSS URL asset. The stale roadmap card was
  corrected to fifth milestone. No fifth-milestone browser-render claim is
  made.
- Independent read-only audits found no concrete C++ declaration, definition,
  map-lifetime, setter-resolution, CppUnit registration, or cross-platform link
  blocker after the corrections. This remains static inspection, not a build.

Scope conclusion: repository-side source and static project-site checks pass
for the fifth milestone. No affected C++ target was compiled or executed, no
LibreOffice binary or window ran, the low-level headless driver had no fork
binary to test, and accepted application screenshots remain **0**.

## 2026-07-16 — fifth Material milestone publication

- Source commit `a644ed9abb6d5112f182ff7ec6e0826b1754c89e` was pushed directly to
  remote `main`; an authenticated `gh api` query reported the same SHA for the
  remote branch.
- GitHub Actions run `29524039805` (`Validate Material UI source`) completed
  successfully. Its semantic theme validation, validator unittest, and Start
  Center lint steps each reported `success`.
- GitHub Pages run `29524040737` completed successfully for the same source
  commit. The Pages API continued to report workflow deployment mode.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contained the exact fifth-milestone
  `2 schemes · 23 color tokens · 3 type roles · 72 style slots · 74 parts ·
  190 states · unbuilt` summary, `Source milestone 5`, and a verified-capture
  count of `0`.
- The clean detached LF worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` was
  moved without reset from `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba` to
  `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`. All scoped source files report
  `w/lf`; the validator again reported 2 schemes, 23 tokens each, 3 typography
  roles, 72 style slots, 74 parts, and 190 states; all eleven validator unittest
  methods passed; `git diff --check` and worktree status were clean.

Scope conclusion: the fifth source milestone is published, its repository-side
CI and project site are green, and the line-ending-safe build worktree is pinned
to the exact source commit. No C++ target or LibreOffice binary ran, and accepted
application screenshots remain **0**.

## 2026-07-16 — sixth Material VCL source milestone validation

- `bin/check-material-theme.py` reported
  `Material theme OK: 2 schemes, 23 tokens each, 3 typography roles, 8 shape
  tokens, 72 style slots, 74 parts, 190 states`.
- All 16 Python unittest methods passed. Shape mutations cover the exact token
  schema and values, duplicate/missing/misplaced sections and roles, attributes,
  text, nesting, processing instructions, malformed/literal/unknown references,
  shape/color namespace separation, legacy `rx`/`ry` rejection in Material,
  complete token use, exact geometry counts, and section-order independence.
- The native reader performs a first-pass parse of an optional `shapes` section
  into invocation-local storage. A singular `radius="@token"` resolves to both
  existing `mnRx`/`mnRy` fields; mixed singular and legacy axes fail, while the
  radius-absent numeric branch is unchanged. No exported reader data member,
  draw-action structure, or renderer call changed.
- The Material definition contains exactly 8 roles and 157 rectangles: 146 use
  one semantic radius reference, 11 remain implicit squares, and none use
  legacy axes. Exact use counts are checkbox 12, indicator 10, focus 2, small
  19, control 26, container 51, toolbar 8, and pill 18.
- The reader C++ source test adds an order-independent positive fixture that
  exercises all eight values and asserts equal resolved axes, pins the existing
  numeric `5`/`5` behavior, and references 23 new invalid-shape fixtures. The
  negative loop asserts each fixture exists before expecting parser rejection,
  preventing a missing file from false-passing. All 53 unique reader fixture
  references resolve; the Material definition plus all 53 fixture XML files
  parse successfully.
- Python bytecode compilation, the Start Center UI linter, all three workflow
  YAML parses, `git diff --check`, and Visual Studio Clang 22.1.3 formatting
  checks passed. All 38 changed source/documentation files were UTF-8 without a
  byte-order mark and LF-only at this stage.
- Static site integrity found 16 unique IDs, validated 22 HTML links and 38
  local Markdown targets across 12 authored files, found balanced CSS, and
  confirmed no image, inline SVG, or CSS URL asset. The site truthfully reports
  source milestone 6, 8 shape tokens, an unbuilt state, and 0 verified captures.
- Independent static inspection found no C++ signature-plumbing, walker-stack,
  integer-overflow, legacy-compatibility, class-layout, draw-action ABI, or
  renderer blocker after formatting and fixture additions.

Scope conclusion: repository-side source and static project-site checks pass
for the sixth milestone. No affected C++ target was compiled or executed, no
LibreOffice binary or window ran, the low-level headless driver still has no
fork binary to test, and accepted application screenshots remain **0**.

## 2026-07-16 — sixth Material milestone publication

- Source commit `3fe772f6068f6820f37c8297f431b39127f4e4d1` was pushed directly to
  remote `main`; an authenticated `gh api` query reported the same SHA for the
  remote branch.
- GitHub Actions run `29525519723` (`Validate Material UI source`) completed
  successfully. Its semantic-theme validation, validator unittest, and Start
  Center lint steps each reported `success`.
- GitHub Pages run `29525520389` completed successfully for the same source
  commit. Configure, upload, and deploy steps each reported `success`, and the
  Pages API continued to report workflow deployment mode.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contained the exact sixth-milestone
  `2 schemes · 23 color tokens · 3 type roles · 8 shape tokens · 72 style slots
  · 74 parts · 190 states · unbuilt` summary, `Source milestone 6`, and the
  statement that verified application screenshots remain at zero. No
  sixth-milestone browser-render claim is made.
- The clean detached LF worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` was
  moved without reset from `a644ed9abb6d5112f182ff7ec6e0826b1754c89e` to
  `3fe772f6068f6820f37c8297f431b39127f4e4d1`. All scoped source files report
  `w/lf`; the validator again reported 2 schemes, 23 tokens each, 3 typography
  roles, 8 shape tokens, 72 style slots, 74 parts, and 190 states; all 16
  validator unittest methods passed; worktree status remained clean.

Scope conclusion: the sixth source milestone is published, its repository-side
CI and project site are green, and the line-ending-safe build worktree is pinned
to the exact source commit. No C++ target or LibreOffice binary ran, and accepted
application screenshots remain **0**.

## 2026-07-16 — seventh semantic metric source and documentation inventory

- The in-progress source worktree is based on metadata commit
  `dede94fa450446746b7dae4a1c4c3534841dfd92`; seventh-milestone changes are
  uncommitted at this inventory point, so publication evidence is not yet
  recorded.
- The Material definition declares exactly 15 semantic native integer roles:
  four stroke roles, two spacing roles, three title/preview roles, and six fixed
  control-size roles. Equal current values retain separate semantic names where
  future density or component policy must be independently adjustable.
- Exactly 331 existing integer uses reference those roles: all 292 explicit
  drawing `stroke-width` attributes, all 34 explicit part
  width/height/margin attributes, and all 5 numeric settings. The conversion
  preserves the prior integers and does not materialize any absent dimension,
  margin, coordinate, or setting.
- Exactly 676 normalized coordinate scalars remain literal across 169 drawing
  actions and 45 complete coordinate patterns. They are proportional component
  geometry, not integer metrics. The 8 shape roles/146 rounded rectangle
  references and 3 typography roles retain their separate contracts.
- The optional generic reader path is designed to resolve metric references
  into existing integer fields or decimal setting strings while keeping literal
  numeric geometry compatible for older bundled and out-of-tree definitions.
  No draw-action, part, settings, or renderer ABI is claimed to change.
- Public and durable project documentation labels this source milestone seven,
  keeps the whole-GUI roadmap incomplete, and states that the token layer keeps
  existing downstream native conversions but adds no density profile or new
  DPI-aware, `dp`, fractional-scale, or touch-sizing policy.
- A read-only closure check counted 15 exact declarations and 331 references
  with the expected per-role distribution, plus 292 strokes, 34 part geometry
  attributes, 5 settings, and 676 unchanged coordinate scalars. Scoped `git
  diff --check` passed; all 8 changed documentation/site/memory files were UTF-8
  without a byte-order mark and LF-only. Static HTML inspection found 16 unique
  IDs and validated all 22 links; 36 local targets across 11 authored Markdown
  files resolved.

Scope conclusion: this entry records source structure and documentation scope,
not successful seventh-milestone validation or runtime behavior. No affected
C++ target has been compiled or executed, no LibreOffice binary or window has
run, and accepted application screenshots remain **0**.

## 2026-07-16 — seventh semantic metric source validation

- The standalone validator reports exactly 2 palette schemes, 23 color tokens
  per scheme, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style
  slots, 74 parts, and 190 states. Both the workspace Python 3.9 launcher and
  the low-level driver's isolated Python environment passed the same checks.
- All 22 Python unittest methods pass. Mutations cover the strict metric schema,
  exact semantic contexts and counts, equal-valued role swaps, balanced
  different-valued swaps, reserved-reference separation, normalized coordinate
  bounds/completeness, raw-string/comment source decoys, and parser-call failure
  propagation.
- The 331 resolved setting/part/stroke rows hash to
  `33d4dea20362213e99c3e931d0b238de5904608d8f80cb5b9ce4142705135de0`.
  Their sequence matches the prior literal values exactly. The 676 unchanged
  path-bound normalized coordinate rows hash to
  `0979f2b3d1d4dff15278fb6b1d1d708795d207045cb339d3ad42a9dcb331ed2e`.
- Native reader coverage contains 38 metric fixtures: one positive
  declaration-after-use case and 37 rejection cases. All are well-formed XML,
  referenced exactly once, UTF-8 without a byte-order mark, and LF-only.
- Independent compile-risk, validator-adversarial, and truth/site audits found
  no remaining static blocker. The truth audit corrected an overbroad
  `device-space` description: the 15 roles now accurately preserve existing
  native integer values and downstream conversions, including list-preview
  `MapAppFont` logic-to-pixel behavior, without claiming a new density/DPI/dp
  policy.
- Clang-format dry-run for the affected C++ files, Start Center UI lint, all 91
  reader XML fixture parses, repository diff checks, documentation links, site
  IDs/links, and UTF-8/LF/no-BOM checks pass.

Scope conclusion: the seventh source slice passes repository-side static gates
but is not yet published at this entry. No C++ target or LibreOffice binary ran,
and accepted application screenshots remain **0**.

## 2026-07-16 — seventh Material milestone publication

- Source commit `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731` was pushed directly to
  remote `main`; an authenticated `gh api` query reported the same SHA for the
  remote branch.
- GitHub Actions run `29527917064` (`Validate Material UI source`) completed
  successfully for that exact commit. Semantic theme validation, all validator
  unittests, and Start Center UI lint each reported `success`.
- GitHub Pages run `29527917148` completed successfully for the same source
  commit. Configure, upload, and deploy steps each reported `success`; the Pages
  API reports workflow mode with HTTPS enforcement.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contains the seventh-milestone description, `15 metric roles`, the
  exact `Fifteen roles replace 331 integer literals` statement, `Source
  milestone 7`, and the statement that the accepted screenshot count remains
  zero. This is an HTTP/content check, not a browser-render claim.
- The clean detached LF worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` moved
  without reset from `3fe772f6068f6820f37c8297f431b39127f4e4d1` to
  `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731`. The validator again reported the
  exact `2/23/3/8/15/72/74/190` tuple and all 22 unittest methods passed from
  that clean worktree.
- The sibling low-level driver remains clean at
  `806d9ba85e4afbc2af58d7499496babfa7c68891`. The short-lived GitHub tunnel was
  terminated and port `18765` was confirmed not listening after verification.

Scope conclusion: the seventh source milestone is published, its repository
static CI and project site are green, and the prepared LF build worktree is
pinned to the exact source commit. No C++ target or LibreOffice binary ran, and
accepted application screenshots remain **0**.

## 2026-07-16 — eighth indicator source validation

- The in-progress worktree is based on metadata commit
  `551e52e0598b7fff509542154c1a3332ac917f6f`; publication evidence is not yet
  recorded in this entry.
- The Material definition adds `TrackHorzArea` to Progress and introduces
  LevelBar with `TrackHorzArea` plus `Entire`. Nine new exact states/actions
  produce a 77-part, 199-state definition with 166 rectangles: 155 use one of
  the existing eight semantic corner roles and 11 remain implicit squares.
- The shared renderer draws an optional full track before the numeric fill,
  keeps track-only zero values successful, dispatches direct non-`Entire`
  requests normally, and preserves fill-only legacy definitions. Level values
  are mapped at exact 25%, 50%, and 75% boundaries without multiplying large
  native widths.
- The standalone validator reports exactly 2 schemes, 23 color tokens per
  scheme, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style slots,
  77 parts, and 199 states. All 24 Python unittest methods pass in the sibling
  low-level driver's isolated Python environment.
- Exact indicator state attributes, token anatomy, nonempty actions, required
  tracks, four level bands, and disabled states are validator-enforced. Native
  source guards strip comments and raw strings and require the optional-track,
  zero-value, threshold, direct-part, and C++ pixel-test paths.
- Nine new `@stroke-none` uses bring the exact metric reference total to 340:
  301 strokes, 34 part dimensions/margins, and 5 settings. The resolved geometry
  hash is
  `0345bb83fae32d79a5b596cc4f17046737a453de0d345a1fa144f737b9b35140`;
  all 676 existing normalized coordinates and their
  `0979f2b3...331ed2e` hash remain unchanged.
- Reader C++ assertions cover all four level colors and exact boundary values;
  headless drawing C++ source covers full-track/clipped-fill pixels, track-only
  zero, direct support reporting, and the 24/25, 49/50, and 74/75 transitions.
  These C++ targets have not compiled or executed on this host.

Scope conclusion: repository-side semantic validation, 24 validator unittests,
formatting, and diff checks pass for the eighth slice at this entry. No affected
C++ target or LibreOffice binary ran, the low-level headless driver has no fork
binary to launch, and accepted application screenshots remain **0**.

## 2026-07-16 — eighth Material milestone publication

- Source commit `291d134ceea2dd6fa354e2d319b043ffe42aa396` was pushed directly to
  remote `main`; an authenticated `gh api` query reported the identical SHA for
  the remote branch.
- GitHub Actions run `29530112458` (`Validate Material UI source`) completed
  successfully for that exact commit. Semantic theme validation, all 24
  validator unittests, and Start Center UI lint each reported `success`.
- GitHub Pages run `29530112004` completed successfully for the same source
  commit. Configure, upload, and deploy steps each reported `success`.
- Direct requests to the published index and stylesheet returned HTTP `200`.
  The index contains the eighth-milestone label, exact `77 parts · 199 states ·
  unbuilt` source tuple, indicator milestone heading, and truthful zero-capture
  statements. This is an HTTP/content check, not a browser-render claim.
- The clean detached LF worktree at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` moved
  without reset from `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731` to
  `291d134ceea2dd6fa354e2d319b043ffe42aa396`. The validator again reported the
  exact `2/23/3/8/15/72/77/199` tuple, all 24 unittest methods passed, and the
  seven indicator source/fixture files checked were UTF-8, LF-only, and without
  byte-order marks.
- Six narrow independent audit-agent attempts and one final consolidated retry
  ended in the same remote `stream disconnected` service error before returning
  findings. The primary release review therefore inspected the complete staged
  C++/validator/XML/documentation diff directly; no independent-agent result is
  claimed.
- The short-lived GitHub CLI tunnel process was terminated and port `18765` was
  confirmed not listening after verification.

Scope conclusion: the eighth source milestone is published, its repository
static CI and project site are green, and the prepared LF build worktree is
pinned to the exact source commit. No C++ target or LibreOffice binary ran, and
accepted application screenshots remain **0**.

## 2026-07-18 — ninth container source validation

- The Material definition adds the two reader-recognized controls that were
  still on fallback: `frame`/`Border` (one outlined container rectangle) and
  `listnet`/`Entire` (a supported-but-empty state). This raises the definition
  from 77 to 79 parts and 199 to 201 states, and from 155 to 156 rounded
  rectangles (the 11 implicit squares are unchanged).
- The frame rectangle reuses existing tokens only — `outline-variant` stroke,
  `surface-container` fill, `stroke-thin` width, `corner-container` radius — so
  it adds one rounded rectangle and one `stroke-thin` reference and no new
  token. `stroke-thin` usage moves from 45 to 46 and the exact metric reference
  total from 340 to 341 (302 strokes, 34 part dimensions/margins, 5 settings).
- The resolved metric-geometry hash becomes
  `f70697ac8fc47cc952e2312afa9a02f88aed27fb69f1cb60a1bddd32bc714082`. Because the
  frame rectangle omits explicit `x1`/`y1`/`x2`/`y2`, the 676 normalized
  coordinate scalars and their `0979f2b3...331ed2e` hash are unchanged.
- `FileDefinitionWidgetDraw::getNativeControlRegion` now returns a native
  `Frame`/`Border` region — bounding equal to the requested rectangle and the
  content region inset by 2px on each edge, matching `decoview`'s
  `DrawFrameStyle::Group` fallback — which satisfies the content-region-inset
  prerequisite D-017 set for enabling the frame (see D-018). `ListNet` returns
  success while drawing nothing so VCL suppresses its own connector nets (see
  D-019).
- The standalone validator reports exactly 2 schemes, 23 color tokens per
  scheme, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style slots,
  79 parts, and 201 states. All 26 Python unittest methods pass on a portable
  CPython 3.12.7 interpreter, and the Start Center UI lint passes. A new native
  container source guard requires the `Frame`/`ListNet` renderer cases, the 2px
  content inset, and the reader's `frame`/`listnet`/`Border` mappings, and two
  new regression fixtures lock the frame/listnet parts and the guard itself.

Scope conclusion: repository-side semantic validation, 26 validator unittests,
and the UI lint pass for the ninth slice. No affected C++ target or LibreOffice
binary was compiled or run, the low-level headless driver still has no fork
binary to launch, and accepted application screenshots remain **0**. GitHub
Actions and Pages verification follow the push to `main`.

## 2026-07-18 — tenth disabled-affordance source validation

- A five-family coverage audit (14 agents; VCL native-draw call sites vs the
  Material definition, each claim adversarially verified) confirmed the control
  inventory is complete and surfaced six real state gaps plus three non-gaps.
  This slice implements the three unambiguous disabled-affordance corrections and
  defers the three design-decision gaps (see D-020).
- New states: `menupopup`/`SubmenuArrow` `enabled="false"` (two `@outline`
  lines), `toolbar`/`Button` `enabled="false" button-value="true"` (one rounded
  rect), and `tabitem`/`Entire` and `tabitem`/`MenuItem`
  `enabled="false" selected="true"` (one rounded rect each). Four new states, no
  new part, no new token.
- Metric closure moves from 341 to 346 references: `stroke-standard` 153→155
  (the disabled arrow's two lines) and `stroke-thin` 46→49 (the three disabled
  rects), i.e. 307 strokes, 34 part dimensions/margins, and 5 settings. The
  eight new normalized coordinates (the disabled arrow lines, reusing the
  enabled arrow's two patterns) raise the coordinate total 676→684 while the
  pattern count stays 45. New geometry hashes:
  metric `dc16a577f59c30ce215aeebb3c930617477572ec31884feebe43585e65c60515`,
  coordinate `8345cd2865759bc8a73f9a7845af2b5d420ea4812c75bcdfe3ba038a13c402e8`.
- The standalone validator reports exactly 2 schemes, 23 color tokens per
  scheme, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style slots,
  79 parts, and 205 states. All 27 Python unittest methods pass on portable
  CPython 3.12.7 and the Start Center UI lint passes; a new regression fixture
  asserts each disabled affordance is present and dimmed distinctly from the
  state it previously collapsed onto.

Scope conclusion: repository-side semantic validation, 27 validator unittests,
and the UI lint pass for the tenth slice. No affected C++ target or LibreOffice
binary was compiled or run, and accepted application screenshots remain **0**.
GitHub Actions and Pages verification follow the push to `main`.

## 2026-07-18 — ninth and tenth milestone publication closure

- Ninth-milestone source commit
  `1e2dca2f76c5f7481451ad0f419a7053222e55df` is published on `main`.
  GitHub Actions source-validation run `29648977365` completed successfully;
  semantic theme validation, all 26 validator unittests, and Start Center UI
  lint each reported `success`.
- GitHub Pages run `29648977400` completed successfully for the same ninth
  milestone commit. This closes repository-side publication only; it is not a
  native build or runtime result.
- Tenth-milestone source commit
  `18714cc1c7421225dd66b925e6295e13b56a7a7a` is published on `main`.
  GitHub Actions source-validation run `29650136950` completed successfully;
  semantic theme validation, all 27 validator unittests, and Start Center UI
  lint each reported `success`.
- GitHub Pages run `29650136963` completed successfully for the same tenth
  milestone commit. This closes repository-side publication only; it is not a
  native build or runtime result.

Scope conclusion: the ninth and tenth source milestones have successful source
validation and Pages publication records. No affected C++ target or LibreOffice
binary ran, and accepted application screenshots remain **0**.

## 2026-07-18 — build gate inventory before workflow repair

- The detached LF worktree previously recorded at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` is no
  longer present. A fresh detached worktree with `core.autocrlf=false` must be
  created and pinned before a local native build attempt.
- Build-installer Actions run `29662095462` at commit
  `d6f66b686551b0d03cc3317fb18a80e74879cce1` completed with `failure` during
  configure because Perl `Archive::Zip` was missing. Build, required native
  regression targets, packaging, and artifact staging did not run.
- The workflow is being repaired to enforce required dependencies and the
  `tools_test`, `vcl_widget_definition_reader_test`, and
  `vcl_file_definition_widget_draw_test` gates before packaging. This entry is
  the pre-rerun state, not a claim that the repair or a build has passed.
- Public release/tag `e` points at `d6f66b686` but contains no assets. It is not
  a genuine build or installer release and does not enter the evidence ledger.

Scope conclusion: no native LibreOffice build, installer, C++ test result,
headless application run, or accepted capture exists at this inventory point.

## 2026-07-19 — first full Windows build reached; dbtools link blocker isolated

- Exact-source Windows Actions run `29674799914` at
  `b010f8a655267c502ee8d739a0c0904049a8e63d` passed all four required native
  targets: `CppunitTest_tools_test`, `CppunitTest_extensions_test_update`,
  `CppunitTest_vcl_widget_definition_reader_test`, and
  `CppunitTest_vcl_file_definition_widget_draw_test`.
- The first workflow attempt to reach the full `make build` gate then failed
  linking `svxcorelo.dll` with 29 unresolved `dbtools::*` and
  `connectivity::*` externals. The workflow had explicitly selected the
  upstream work-in-progress `--disable-database-connectivity` mode, while the
  desktop svx form objects still import those APIs and svxcore links dbtools
  only when `DBCONNECTIVITY` is present in `BUILD_TYPE`.
- The repair explicitly enables database connectivity and asserts the
  generated `config_host.mk` contains `DBCONNECTIVITY` before any long native
  target starts. It does not add ad-hoc exports or bypass the supported
  dependency graph.
- MSI staging, upload, and release publication were skipped. The expected tag
  `windows-msi-19-1-b010f8a655` was not created; the diagnostic artifact is
  `windows-build-diagnostics-29674799914`.

Scope conclusion: the exact native regression gates are proved for this failed
attempt, but no MSI, release, LibreOffice runtime smoke, or accepted screenshot
is claimed until the repaired exact-source rerun completes.

## 2026-07-19 — Start Center action and MSI CLI source repair

- Source commit: `1e97d960be2b4d736dc00ec6a4d76fb4cf5dc905`.
- The standard GTK `suggested-action` class is now retained by the generic UI
  builder until the leaf widget exists, then mapped by `VclBuilder` to
  `PushButton::setAction(true)`. `startcenter.ui` applies it to `open_all`, so
  the existing Material `pushbutton`/`Entire` `extra="action"` states become
  selectable under the opt-in renderer. A focused `VclBuilder` CppUnit fixture
  covers a leaf suggested button and a plain control; both focused native
  workflows now include `CppunitTest_vcl_treeview`.
- Windows Actions run `29678095646` at
  `937b61fd3ad7c83fba2714b6341118e0b778c252` passed configure, `Library_svxcore`,
  and the prior four required native C++ targets, then failed only in MSI
  packaging because `--disable-cli` omitted legacy CLI bridge payloads that the
  MSVC MSI manifests require. The workflow repair removes that contradictory
  switch, asserts `ENABLE_CLI=TRUE`, builds `cli_ure` and `unoil`, and verifies
  the required DLL, policy-DLL, and configuration payload before `make build`.
  `--without-dotnet` remains because the modern .NET feature is independent of
  the legacy CLI bridge.
- Local source checks passed: `python bin/check-material-theme.py` reported
  `2/23/3/8/15/72/79/205`; `python -m unittest
  bin/test_material_theme_validator.py` ran 27 tests; `python
  bin/lint-ui.py` accepted both `startcenter.ui` and the new fixture; `node
  bin/validate-prototype.mjs` passed all 7 checks; Python parsed the three
  changed workflow files and both UI XML files; and `git diff --check` passed.

Scope conclusion: this is a source/configuration repair only. The new CppUnit
test, repaired Windows package, MSI extraction, and off-screen LibreOffice
runtime interaction are not claimed until the post-repair native runs finish.

## 2026-07-19 — vcl_treeview fixture compile follow-up

- The first current-source Linux native run, `29695337988` at
  `1e97d960be2b4d736dc00ec6a4d76fb4cf5dc905`, failed while compiling
  `vcl/qa/cppunit/treeviewtest.cxx`: the new focused fixture includes the
  internal `PushButton` declaration, but the `vcl_treeview` CppUnit target did
  not declare `VCL_INTERNALS`. No test body, package, or application runtime
  ran in that attempt.
- The target-specific follow-up declares `VCL_INTERNALS`, matching the existing
  `vcl_lifecycle` CppUnit target that tests the same VCL control API. Its native
  rerun remains required before any build or runtime result is recorded.

## 2026-07-19 — current-source native reruns and MSI staging follow-up

- Linux Actions run `29695793821` at
  `e4dc8a850c982f33d8722fc203f86591b2993e8b` passed `tools_test`,
  `extensions_test_update`, `vcl_widget_definition_reader_test`,
  `vcl_file_definition_widget_draw_test`, and `vcl_treeview`, including the new
  `suggested-action` builder fixture.
- Windows Actions run `29695815101` at the same commit passed configure,
  `Library_svxcore`, those five required native targets, the `ENABLE_CLI` legacy
  payload assertions, and the full LibreOfficeDev installation-set build. Its
  staging step stopped before upload because a recursive MSI search found three
  files: two retained `idt_files` working databases and the final
  `LibreOfficeDev\msi\install\en-US\libreofficedev272.msi` package.
- The workflow now scopes MSI discovery to that final success-only directory,
  retains exact-one candidate enforcement, and reports candidate paths on any
  mismatch. This is a staging-rule repair, not an accepted artifact, release, or
  runtime result; a non-main hosted rerun is required before the low-level
  off-screen desktop scenario can start.

## 2026-07-19 — local one-click Windows bootstrap source validation

- Added `Build-Windows.cmd`, `bin/Build-Windows.ps1`, and
  `docs/LOCAL_WINDOWS_BUILD.md`. The default script contract is a dedicated
  VS 2022 Build Tools/Cygwin bootstrap, an LF detached snapshot, the hosted
  configure/test/build order, and exact-final-MSI administrative extraction.
- The bootstrap uses one hidden elevated PowerShell child only when prerequisites
  are missing; it requests one UAC consent, writes a bootstrap transcript, and
  does not open a PowerShell window per installer. The ordinary build runs in
  the caller's terminal.
- Static validation only: the PowerShell parser accepted
  `bin/Build-Windows.ps1`, and `git diff --check` was clean at the script
  validation point. No bootstrap installer, native local build, MSI,
  LibreOffice runtime, or application screenshot ran as part of that check.
- Hardening review added fail-fast root/reparse/path-length checks, both-drive
  capacity checks before installers, exact publisher-CN and pinned-hash checks,
  one encoded hidden UAC child, isolated Cygwin Git/configuration, immutable
  per-invocation logs and MSI staging, profile revalidation on resume, and
  non-force cleanup only of a clean successful-run source snapshot. Parser,
  material validator, 27 Python validator tests, prototype validator, and
  whitespace checks passed after that revision.

Scope conclusion: the local profile is reproducible source automation, not
build or runtime evidence.

## 2026-07-19 — local one-click Windows preflight

- Ran `cmd.exe /d /c "Build-Windows.cmd -Phase Preflight"` from clean commit
  `6e489f62a`. It reported 2,217 GiB free on the default shared C: drive, then
  correctly stopped with the dedicated VS 2022 and isolated Cygwin profiles
  absent. The SDK and legacy CLI checks did not report an error.
- The expected nonzero preflight exit left both
  `C:\ProgramData\LibreOfficeMaterialTools` and
  `%USERPROFILE%\lo-material` absent. No installer, native build, MSI,
  LibreOffice launch, or runtime capture occurred.

## 2026-07-19 — main Windows MSI publication gate

- The non-main Windows run `29701798057` at
  `94c159c2d62f7ed2df68aec71d79ef51c71d9cfb` passed configure, the required
  native targets, legacy CLI payload generation, the full installation-set
  build, and administrative MSI extraction. It uploaded a 184 MB artifact;
  the job then intentionally failed at the stable-publication guard because
  that validation branch is not `main`.
- The main workflow now also requires Visual Studio's C++/CLI component before
  beginning its long build, matching the legacy bridge's `/clr` compilation
  requirement. A clean `main` run and normal public release are still required.

## 2026-07-19 — local bootstrap hash-verifier compatibility follow-up

- The first real local all-phase bootstrap installed the dedicated VS 2022 and
  isolated Cygwin profiles, then its final validation reported that
  `Get-FileHash` could not be resolved in the no-profile child. The matching
  Cygwin package/tool validation passed after installation; no native source
  build, MSI, LibreOffice launch, or runtime capture completed in that attempt.
- The local builder now computes the same lowercase SHA-256 values through the
  .NET cryptography API at every pinned-download, tool, and MSI-artifact check,
  so validation does not depend on PowerShell utility-module auto-loading.
  A `PendingFileRenameOperations` value created by the installer was cleared
  only after the operator explicitly authorized removal of restart flags.
- This is a bootstrap compatibility repair, not native-build or runtime
  evidence. A fresh local preflight and all-phase build remain required.

## 2026-07-19 — local Cygwin preflight execution repair

- A fresh local preflight showed that the Cygwin probe's multiline `bash -c`
  payload was split by Windows PowerShell native argument marshalling, and that
  a fresh Cygwin shell needs its POSIX path established before the first
  `uname` call. The probe now sets that path first and is sent to `bash -s` on
  standard input; its normal version output is suppressed so the helper returns
  only its readiness object.
- With that repair, `Build-Windows.cmd -Phase Preflight` passed the installed
  isolated-toolchain checks and reached the intentional clean-checkout guard.
  It stopped only because this repair itself was not yet committed. No native
  build, MSI, LibreOffice launch, or runtime capture ran in that invocation.

## 2026-07-19 — local configure command-transport follow-up

- The first all-phase local attempt successfully created and LF-checked its
  detached source snapshot at `5c0c4ae2a11a0a604278ae518fe08621ad796e16`, then
  failed before `autogen.sh` because the shared configure runner still supplied
  its multiline shell program through `bash -c`. The native build, MSI, and
  application runtime did not start.
- The common Cygwin runner now uses the same stdin transport as the proven
  preflight probe, covering configure, profile assertion, native tests, and
  product build. The clean failed-run root is preserved rather than overwritten;
  the repaired commit will use a distinct isolated build root for a fresh run.
- A no-profile runner smoke emitted both stdout and a warning on stderr, logged
  both streams, and returned successfully; stderr is now merged inside Bash so
  ordinary configure warnings cannot abort the PowerShell controller.

## 2026-07-19 — local Skia Clang prerequisite follow-up

- The fresh all-phase configure at
  `bfca68c6756f1ae0559847cbb3926aa31126374b` passed the MSVC, SDK, legacy CLI,
  Autotools, and Windows MSI profile checks, then stopped before any native
  target because LibreOffice's default Skia configuration could not find
  `VC\Tools\Llvm\bin\clang-cl.exe`. The installed VS profile contained
  `clang-format.exe` and `clang-tidy.exe`, but not that compiler; the configure
  log records `checking for clang-cl... no` before the fatal show-includes
  probe.
- The local bootstrap now requires Visual Studio's
  `Microsoft.VisualStudio.Component.VC.Llvm.Clang` component and verifies its
  exact `clang-cl.exe` payload alongside the existing MSVC/C++/CLI/ATL/CMake
  requirements. This preserves the full Windows profile rather than disabling
  Skia. The common Cygwin runner also establishes its POSIX path centrally so
  the profile assertion can invoke `cygpath` after configure.
- No local native target, MSI, LibreOffice launch, or runtime capture completed
  in this attempt. The clean failed-run root remains preserved; the repaired
  profile requires a fresh bootstrap, preflight, and all-phase build.

## 2026-07-19 — explicit local Visual Studio 2026 profile

- The local Windows build source exposes an explicit
  `-VisualStudioYear 2026` profile alongside its unchanged isolated VS 2022
  default. A verified existing VS 2026 installation is selected only by
  providing its exact `-VisualStudioInstallPath`; normal bootstrap may prepare
  other prerequisites but refuses to alter an incomplete host Visual Studio
  installation. Without that option, the opt-in profile uses its own
  `%ProgramData%\LibreOfficeMaterialTools\VS2026` Build Tools root.
- The VS 2026 profile uses the VS 18 version range, v145 CRT merge modules, and
  a separate `windows-cygwin-vs2026-msi` build profile. VS 2022 and VS 2026
  resume state is intentionally incompatible, and the configured compiler path
  is checked against an explicitly supplied host path. The current CI workflow
  remains pinned to VS 2022.
- This is a source/documentation profile change only. No VS 2026 bootstrap,
  preflight, native target, MSI, LibreOffice launch, headless UI smoke,
  accessibility smoke, or release result is claimed by this entry.

## 2026-07-19 — VS 2026 Enterprise toolchain preflight

- The previously canceled Visual Studio Enterprise 2026 instance at
  `C:\Program Files\Microsoft Visual Studio\18\Enterprise` completed and
  launched normally. A narrow additive modify installed the missing C++/CLI,
  LLVM/Clang, and VC145 merge-module payloads with restart suppression; no
  components were removed.
- `vswhere` matched that exact VS 18 installation for the required C++
  component set. Clang 22.1.3 ran from VS 2026's host-native
  `VC\Tools\Llvm\x64\bin\clang-cl.exe`, and both
  `Microsoft_VC145_CRT_{x86,x64}.msm` files were present. The wrapper and
  `configure.ac` were updated to accept that layout while retaining VS 2022's
  legacy flat LLVM layout.
- The standard CBS and Windows Update reboot keys were absent. The sole
  pending-reboot signal was six temporary-file entries in
  `PendingFileRenameOperations`; the explicitly authorized cleanup removed that
  value and a follow-up check was clear.
- `Build-Windows.cmd -Phase Preflight -NoBootstrap -VisualStudioYear 2026`
  with the exact Enterprise path and a fresh `lo-material-vs2026` build root
  passed at source commit `12605eabf6bfdea93a0d4c49c5e2c8a3ab5e25b2`.
  This is toolchain/preflight evidence only: no configure, native target, MSI,
  LibreOffice launch, UI smoke, accessibility smoke, or release result is
  claimed.

## 2026-07-19 — VS 2026 v145 C++20 mdds compatibility follow-up

- The explicit Enterprise VS 2026 profile completed an isolated configure at
  source commit `a6d9f9a7dbdf10c08afe2eb03239e702ec5172ef` in the preserved
  `C:\Users\cntow\lo-material-vs2026` build root. The native build reached
  third-party compilation and stopped in `mdds-3.2.1` with C2382 on the
  matching conditional `noexcept` declaration/definition of
  `flat_segment_tree::operator==`.
- The failure reproduces with MSVC 19.51/v145 in C++20 mode, does not reproduce
  with the installed VS 2022 toolset, and is isolated to that mdds operation;
  the analogous `segment_tree` and `multi_type_matrix` syntax checks pass. The
  source now registers a patch that omits the conditional exception
  specification only for `_MSC_VER` 1950–1959 in C++20-or-newer mode. It
  dry-runs against the unpacked tarball and passed direct v145 and VS 2022
  syntax checks.
- This is a compiler diagnosis and source compatibility repair. The failed build
  root is retained, and a fresh exact-current-source build is still required
  before claiming a native target, MSI, application launch, headless UI smoke,
  accessibility smoke, or release.

## 2026-07-19 — canonical GitHub release identity follow-up

- The former `codingmachineedge/libreoffice-material` remote returned GitHub's
  relocation notice. The authoritative public repository is
  `Ding-Ding-Projects/libreoffice-material`; its default branch remains `main`,
  the active publishing credential has write access, and `origin` now uses the
  canonical URL. Its Pages endpoint is
  `https://ding-ding-projects.github.io/libreoffice-material/`.
- The updater's trusted asset prefix, generated installer update URLs, privacy
  URL, update fixtures, public documentation, and Pages canonical URLs were
  switched together to the canonical owner. This avoids accepting a redirect as
  identity proof or shipping an MSI whose updater rejects its own normal
  release asset.
- A fresh build snapshot at `d5a1229978a0d5732f88ba52f5dadc40b4d90fa5` was
  intentionally stopped during dependency download once this release-blocking
  mismatch was discovered; its root remains preserved for audit/cache reuse and
  is not a build result. The next release candidate must use the pushed
  canonical-owner source commit.

## 2026-07-19 — canonical workflow release identity sweep

- Before native compilation began, both workflow configure paths were checked
  and corrected to use the canonical `Ding-Ding-Projects` privacy-policy URL.
  The local wrapper already used that URL; keeping the Windows and Linux CI
  invocations aligned prevents a future workflow-built MSI from reintroducing
  the old repository identity.
- The incomplete source-copy root for `4fd5d9aa6` was deliberately stopped and
  retained before configure. It is not build evidence. The next candidate must
  use the pushed follow-up commit that contains the CI identity correction.

## 2026-07-20 — exact-source VS 2026 product, MSI, and Start Center evidence

- Clean detached source `577059e2741185b512c184c64685c16d335d10ea` used
  Visual Studio 2026 Enterprise 18.7.11925.98, MSVC 19.51.36248/v145
  14.51.36231, Clang 22.1.3, and Windows SDK 10.0.26100.0. The five required
  native targets (`tools_test`, `extensions_test_update`,
  `vcl_widget_definition_reader_test`,
  `vcl_file_definition_widget_draw_test`, and `vcl_treeview`) passed, as did
  the legacy CLI payload check and full LibreOfficeDev product build.
- The final `LibreOfficeDev_27.2.0.0.alpha0_Win_x86-64.msi` is 199,692,288
  bytes with SHA-256
  `437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43`.
  Authenticode reports `NotSigned`. Windows Installer administrative extraction
  completed successfully with status `0`; the stabilized payload contains 4,929
  files, 605,001,099 bytes, and exactly one `soffice.exe`. The wrapper parent
  exited before final dist staging/manifest copy, so the wrapper is not claimed
  as an end-to-end success. The MSI was not installed.
- Extracted `program\soffice.exe` is 537,600 bytes, SHA-256
  `a0ac5360f303435ca89406fd8e648affc30a6e53382af0b901a85f3a5a45c410`;
  `program\soffice.bin` is 2,719,744 bytes, SHA-256
  `beb398080f8ed27c44c9425499c1fdd0171648751253c9f2c176943a7fb330ea`.
- Clean sibling driver commit
  `beed66ca6ed2503e6170ee1e1158247f1c2f0140` launched the exact extracted
  payload on a run-scoped Win32 off-screen desktop with an isolated profile and
  unique UNO pipe. The first, default-GPU `PrintWindow` capture was blank even
  though the owned `LibreOfficeDev`/`SALFRAME` window was stable and the bounded
  UNO collector returned 96 nodes, 49 visible, with no collector errors. The
  failure is preserved as run `20260720-012601-577059e274-vs2026-msi`.
- The retry set `SAL_SKIA=raster` and `SAL_DISABLEGL=1`, retained the Material
  opt-in, and produced two reviewed nonblank `1920×1117` captures. Home/Recent
  Documents is SHA-256
  `e4a21bd16c99ef360749dd72557a8d5a9df7c38d0a51122e8ca0058c57464501`;
  Templates after a successful background client click is SHA-256
  `30667f9c9c8163183dc6f7d780113e52b90d710dca0ac64044afd5b5243ef378`.
  Their paired bounded UNO trees report 96/49 and 111/64 total/visible nodes,
  no collector errors, and no truncation. The exact process terminated normally
  over its unique pipe, headless window count reached zero, and the named
  desktop closed successfully. Run
  `20260720-012853-577059e274-vs2026-msi-raster` is accepted for these narrow
  light Start Center checkpoints only.
- Dark/high-contrast, accelerated capture, keyboard/focus, 200% scale,
  localization/direction, suite applications, dialogs, updater, and MSI
  install/upgrade/uninstall/restart-suppression coverage remain open. The
  Material environment was requested, but that alone does not prove every
  control used the file definition or that the Start Center is complete.

## 2026-07-20 — per-push normal Windows release workflow source validation

- `windows-installer.yml` now triggers on every push to `main` and retains
  manual dispatch. Per-SHA concurrency does not allow a newer push to cancel or
  replace an older pending source commit. The validated MSI and three metadata
  files are uploaded directly to a draft GitHub Release; only diagnostics use
  an Actions artifact. Exact asset/digest/target checks precede promotion to a
  public normal, non-prerelease Latest release.
- Official `actionlint` 1.7.12, `git diff --check`, and focused semantic
  assertions passed locally. This is workflow-source validation; no canonical
  public release existed at the time of this entry, so the first pushed run must
  still be followed through build, publication, Latest, and public asset checks.

## 2026-07-20 — running-app evidence push and Pages publication

- Screenshot/docs commit `b0e3ea76639796aa5612dbce0333e394a5073f4c` was pushed
  to `origin/main`. It registers and embeds the two accepted off-screen Windows
  Start Center captures from run
  `20260720-012853-577059e274-vs2026-msi-raster` without altering their pixels.
- Pages run
  [`29720519782`](https://github.com/Ding-Ding-Projects/libreoffice-material/actions/runs/29720519782)
  completed successfully for that exact commit. The published inputs retain
  SHA-256
  `e4a21bd16c99ef360749dd72557a8d5a9df7c38d0a51122e8ca0058c57464501`
  for Home/Recent Documents and
  `30667f9c9c8163183dc6f7d780113e52b90d710dca0ac64044afd5b5243ef378`
  for Templates.

## 2026-07-20 — first normal public Windows release and Latest-byte proof

- A normal public, non-draft, non-prerelease release was published at
  [`windows-msi-local-20260720-577059e274`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-577059e274)
  on 2026-07-20 at 06:06:42 UTC. It targets product source
  `577059e2741185b512c184c64685c16d335d10ea` and contains exactly four uploaded
  assets: `LibreOfficeMaterial-Windows-x64.msi`, its `.sha256` sidecar,
  `windows-msi-manifest.json`, and `windows-update-manifest.xml`.
- After an initial propagation 404, cache-busted unauthenticated downloads
  through the public Latest route succeeded for all four assets and matched the
  local release bytes and SHA-256 values exactly: XML 976 bytes,
  `08bb30f0f0a6a9c11d5845367f3dedf2189079758fd6ae2d4b288ce6d8591465`;
  JSON manifest 943 bytes,
  `8f720b8f7552905a0375dc1ef900d3ea114e9b1518e2281ddc45a2ac4815d04c`;
  sidecar 102 bytes,
  `79d6d0be5c4bf57954cd047421bf8bacd6b33b2c6d2cad6bfe4a0096fdc102a5`;
  and MSI 199,692,288 bytes,
  `437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43`.
- Hosted per-push Windows run
  [`29720519794`](https://github.com/Ding-Ding-Projects/libreoffice-material/actions/runs/29720519794)
  for `b0e3ea76639796aa5612dbce0333e394a5073f4c` remains in progress and has not
  published its own per-push release. The release above is real public release
  proof, but it is the older binary described in the next entry.

## 2026-07-20 — updater launch-argument omission and corrected VS 2026 candidate

- A launch-site audit found that `buildWindowsInstallerCommand` generated five
  installer arguments but `UpdateCheck::install()` passed only the first four to
  `osl_executeProcess`. The fifth argument, `REBOOT=ReallySuppress`, was therefore
  absent from the launched command in source/product commit `577059e274`. The
  already-published release must not be treated as restart-suppression or updater
  runtime proof.
- Local commit `fbba560e27db26de605c40aa237c554c1f0744b1` replaces the
  fixed four-pointer list with an array sized from the command's argument array
  and forwards all five entries. The focused Visual Studio 2026
  `CppunitTest_extensions_test_update` target passed, followed by a successful
  incremental full LibreOfficeDev product and MSI build.
- The corrected unsigned MSI is 199,688,192 bytes with SHA-256
  `180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`.
  Windows Installer administrative extraction returned `0`; the payload contains
  4,885 files and 603,901,200 bytes. Extracted `program\updchklo.dll` is 571,392
  bytes and exactly matches the built DLL at SHA-256
  `32f80adfcd5097ef54f13951b748a5703439aef0dbb751d6a4c5d3e6102446a3`.
- The corrected MSI's low-level headless UI/UNO rerun passed as recorded below;
  publication had not yet occurred at this checkpoint, and the later release
  entry below supersedes that boundary. No updater download,
  protected-stage, consent, installer launch, restart-suppression runtime,
  install, repair, upgrade, or uninstall result is claimed.

## 2026-07-20 — corrected extracted-runtime headless UI and UNO proof

- Corrected source commit `fbba560e27db26de605c40aa237c554c1f0744b1`
  supplied accepted run
  `20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression` through
  clean low-level driver commit
  `beed66ca6ed2503e6170ee1e1158247f1c2f0140`. The isolated off-screen Windows
  run requested the Material file-widget profile and used Skia software raster.
- Home/Recent Documents is 203,493 bytes at `1920×1117`, SHA-256
  `e4a21bd16c99ef360749dd72557a8d5a9df7c38d0a51122e8ca0058c57464501`.
  Templates after background navigation is 212,506 bytes at `1920×1117`,
  SHA-256
  `1f9f0e9614c0eb6bd0c0e9cea6909982a8900ed532e03f7bbdd72751a87294ab`.
  Both passed nonblank, occlusion/staleness/stretch, and sensitive-content review.
- The paired bounded UNO trees contain 96/49 and 111/64 total/visible nodes,
  report zero collector errors, and are not partial. Normal UNO termination
  succeeded; matching run-scoped processes and headless windows both reached
  zero, and the off-screen desktop closed.
- These two corrected images now supply the canonical README, screenshot
  registry, and Pages gallery. The earlier accepted
  `20260720-012853-577059e274-vs2026-msi-raster` run remains historical proof.
  This corrected result verifies only extracted-runtime Start Center UI/UNO
  smoke; it does not execute MSI install, repair, upgrade, uninstall, or
  restart-suppression lifecycle behavior.

## 2026-07-20 — corrected normal public release and Latest-byte proof

- Corrected release
  [`windows-msi-local-20260720-fbba560e2`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2)
  was published at 2026-07-20T06:44:07Z. GitHub reports it as public,
  non-draft, non-prerelease, and Latest, targeting exact product source
  `fbba560e27db26de605c40aa237c554c1f0744b1`.
- The release contains exactly four public assets. Cache-busted unauthenticated
  downloads through the public Latest route matched each published asset size
  and SHA-256 exactly:
  - `LibreOfficeMaterial-Windows-x64.msi`: 199,688,192 bytes,
    `180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`;
  - `LibreOfficeMaterial-Windows-x64.msi.sha256`: 102 bytes,
    `e82f022d06665a165b8d0145acac0aae7b39cd9f8b9cbd0f7a1cfa1105021b9e`;
  - `windows-msi-manifest.json`: 1,011 bytes,
    `12e6495e5d5051657dd99e6c0afc6d61941144c1bcde5f792f09a9949bea0fc1`;
  - `windows-update-manifest.xml`: 972 bytes,
    `b686d9e9641360c3962bc27b8b6517b9a76c14c06cd50efbcbcfe485724eab72`.
- This supersedes the older `windows-msi-local-20260720-577059e274` release as
  the update candidate. The older release remains historical with its warning:
  that product omitted the fifth updater launch argument and is not
  restart-suppression or updater-runtime proof.
- Publication and public-byte verification do not execute the updater or prove
  MSI install, repair, upgrade, uninstall, or restart-suppression lifecycle
  behavior. Those runtime gates remain open.

## 2026-07-20 — dark and forced-high-contrast headless UI/a11y proof

- Two additional accepted off-screen Windows runs exercised the exact corrected
  extracted runtime from source commit
  `fbba560e27db26de605c40aa237c554c1f0744b1`. Both used a clean low-level
  computer-use driver at `beed66ca6ed2503e6170ee1e1158247f1c2f0140`, a
  dedicated same-token loopback MCP server, and Skia software raster. The
  same-token server avoids the integrity boundary that prevented the UNO
  accessibility collector from attaching through the already-running elevated
  server.
- Dark run `20260720-033252-fbba560e27-windows-headless-dark` accepted Home,
  keyboard focus, and Templates captures at `1920x1117`, with SHA-256 values
  `0fc0eaac0224b501f3322c992d8ff2e5cae0f790982bbb32371f58c04812d78e`,
  `0e415762290b45abcfdce3233517388d90a0f3972bec02452aceb7e368498587`,
  and `742395d2f1a229ab44f994a26854ea55017f1e54414e0e5ae347a26da6aca74c`.
- Forced-high-contrast run
  `20260720-033338-fbba560e27-windows-headless-highcontrast` accepted the same
  three scenarios at `1920x1117`, with SHA-256 values
  `60548b299305d2a9174574cb002efa6750a22b64c7e324bd76528761e3562d09`,
  `6f4821bbb9e7d2be8ccbf42830c9e3ed0e16c1800fed1809a0c2fd1a39753264`,
  and `483072f7fb84cc01f894588a5745ebf3efc23930eae9a680ab60591f9b53bf23`.
- Each Home/focus tree contains 96 total and 49 visible nodes; each Templates
  tree contains 111 total and 64 visible nodes. Every tree reports zero errors
  and `partial=false`. Both keyboard-focus trees expose exactly one focused UNO
  node: the `Open File` push button. Normal UNO termination succeeded, matching
  run-scoped processes and headless windows reached zero, each desktop closed,
  and each dedicated driver stopped.
- The reusable `bin/Run-Windows-Headless-Smoke.ps1` harness now captures these
  bounded scenarios, hashes/nonblank-checks every PNG, records staged UNO
  progress, verifies the exact payload process path, and enforces normal
  cleanup. This proves Start Center light/dark/high-contrast smoke and one Tab
  focus transition only; broader modules, dialogs, localization, and 200% scale
  remain open.

## 2026-07-20 — updater hardening and disposable lifecycle harness source gate

- Current source extends the interactive updater launch to six arguments by
  adding `MSIRESTARTMANAGERCONTROL=DisableShutdown` after
  `REBOOT=ReallySuppress`. The VS 2026
  `CppunitTest_extensions_test_update` target passed with regressions that
  verify all six forwarded process arguments, exclusive `CREATE_NEW` staging,
  the protected three-ACE SYSTEM/Administrators/Owner Rights DACL, and a
  retained read lock that rejects write/delete opens.
- The new Windows Sandbox lifecycle harness pins the exact old and corrected
  public release MSI bytes, disables guest networking and device/clipboard
  redirection, maps only a read-only input and fresh writable output, and
  requires zero-only install, same-version update, repair, and uninstall
  results. It records before/after restart-state fingerprints and never removes
  pending-restart values. A post-review hardening pass added fail-closed
  WDAG/SID/profile/VM/read-only-map attestation outside the lifecycle
  `try/finally`, gates cleanup and shutdown on that attestation, propagates
  Windows Installer query errors, requires exact unregistered final states,
  pins the prepared guest to the reviewed repository source, recomputes all
  step/whole-lifecycle reboot comparisons on the host, bounds sentinel files,
  waits for normal Sandbox client disposal, and writes `host-verification.json`
  only after those post-guest checks pass. PowerShell parsing, the
  dependency-free source validator, and strict-mode host snapshot checks passed.
  A direct host-side invocation regression exited `1` in 0.276 seconds with
  `Refusing to run outside Windows Sandbox: current account is CRUISE\\cntow`,
  before lifecycle setup; no `shutdown.exe` process appeared.
- This is a source/static harness gate only. No Windows Sandbox MSI lifecycle
  run had executed at this checkpoint, so install/update/repair/uninstall and
  restart-suppression runtime proof remain open.

## 2026-07-20 — pinned lifecycle preparation and non-launching inspection

- Safe-default preparation created run
  `20260720-041140-7240676-b3777205bfb344a2977090ba35d643c3` without starting
  Windows Sandbox or `msiexec`. Its input directory contains only the reviewed
  guest, expected manifest, and the two exact-tag MSI files. The old MSI is
  199,692,288 bytes at SHA-256
  `437b059c7dd5ed7a60c2ae4f47f2a1905cf97ef4e136e98183e08658d7654a43`;
  the corrected MSI is 199,688,192 bytes at SHA-256
  `180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`.
- The first post-download policy check exposed Windows PowerShell XML-adapter
  shorthand that was unsafe under strict mode. The host validator now selects
  each mapped-folder child explicitly and exposes a non-launching `Inspect`
  mode. Parser/static validation and `Inspect` both pass on the retained fresh
  run, whose output mapping remains empty.
- This is pinned preparation evidence only. Windows Sandbox was not launched,
  and no install/update/repair/uninstall or restart-suppression runtime result is
  claimed.

## 2026-07-20 — first isolated lifecycle launch failed closed

- Retained run
  `20260720-041140-7240676-b3777205bfb344a2977090ba35d643c3` was launched
  through the sibling low-level driver on off-screen desktop
  `LOMaterialMSI-41398b5b-0419`. The guest published only `FAILURE.json`, and the
  host wrapper returned exact exit code `1`; there is no `COMPLETE.json`, step
  log bundle, or `host-verification.json`.
- The captured failure is PowerShell `System.ArgumentException: Argument types
  do not match` from array-subexpression binding over the guest's generic
  `List[object]` collections. A standalone PowerShell 5.1 reproduction failed
  for `@($list)` and passed for `$list.ToArray()`.
- `host-before.json` and `host-after.json` have identical reboot and
  LibreOffice-registration fingerprints: no LibreOffice registration, no CBS
  or Windows Update reboot marker, no pending rename entry, and no Windows
  Installer operation. After the backend exited, the packaged remote-session UI
  was closed through the low-level process cleanup path without force, leaving
  zero tracked Sandbox processes/windows; the off-screen desktop was released.
- The source fix serializes all three generic collections with `.ToArray()` and
  `ConvertTo-Json -InputObject`, tracks the current
  `WindowsSandboxServer.exe`/`WindowsSandboxRemoteSession.exe` pair, waits for
  backend exit, and only gracefully closes an exact-run/package-bound client.
  `Verify` now requires the retained host snapshots, their hashes, unchanged
  safety fingerprint, and recorded zero-process disposal.
- PowerShell parsing, the dependency-free static validator, PowerShell 5.1 and
  7 array-shape probes, and direct-host WDAG refusal all pass. This failed run is
  diagnostic only and proves no install/update/repair/uninstall result.

## 2026-07-20 — second isolated launch reached MSI identity preflight

- Fresh prepared run
  `20260720-043916-4641037-b451b45fa51a423c880f7092faa45274`
  passed `Inspect` with an empty output map, old/corrected MSI hashes
  `437b059c…a43` / `180e511c…eea`, guest SHA-256 `878676d5…448e`, and WSB
  SHA-256 `fa747271…20a9`. It launched through the low-level off-screen desktop
  `LOMaterialMSI-e6fc0920-0444`.
- The serialization fix worked: the guest published valid empty JSON arrays,
  `results.json`, a byte-pinned `artifact-manifest.json`, and atomic
  `FAILURE.json`. It failed before any MSI step with strict-mode
  `PropertyNotFoundException` for `ProductCode`; wrapper exit was exact `1` and
  no `host-verification.json` was accepted.
- The query helper's final `,$rows` emitted one object containing all 107 rows,
  so identity parsing saw no `ProductCode` key. The source now returns `$rows`,
  requires the six pinned Property-table keys, and uses indexed hashtable reads.
  A PowerShell 5.1 probe executing the exact three reviewed function definitions
  against both retained MSI bytes returned old ProductCode
  `{F6673D3A-81F6-462E-934F-19438F08C9EA}`, corrected ProductCode
  `{2BD7C198-30D4-4BC6-AE7C-52B7F5DBAF71}`, expected test UpgradeCode/version,
  `ALLUSERS=1`, `MSIRESTARTMANAGERCONTROL=0`, and zero authored reboot actions.
- Host before/after fingerprints were identical, no host LibreOffice
  registration appeared, the server-first/run-bound graceful client disposal
  path completed, the off-screen window count reached zero, and the desktop was
  released. This is diagnostic/preflight evidence only; no MSI operation ran.

## 2026-07-20 — fresh committed-harness light Start Center acceptance

- Run `20260720-112425-fbba560e27-windows-headless-light` accepted the exact
  corrected extracted payload at source
  `fbba560e27db26de605c40aa237c554c1f0744b1`. It used committed harness
  `1bb67261794d190f099c92d9dfdd48722785db34`, clean low-level driver
  `beed66ca6ed2503e6170ee1e1158247f1c2f0140`, and a dedicated same-token
  loopback MCP session rather than the elevated always-on service.
- Home, visible `Open File` keyboard focus, and Templates were captured through
  `PrintWindow` at `1920x1117`. Their independently rechecked SHA-256 values are
  `e4a21bd16c99ef360749dd72557a8d5a9df7c38d0a51122e8ca0058c57464501`,
  `1039f641b724a1b6776f6773e740ce8a81163286439615830f8f5ada16e3ab13`,
  and `6fd05519a89c9b962fcc980f60a6efcc4e176e3b523e0790e0eec00f27066e5f`.
  All three are nonblank, complete full-window captures and passed visual and
  sensitive-data review.
- The screenshot-bound UNO trees report 96/49, 96/49, and 111/64 total/visible
  nodes, zero errors, and `partial=false`. The keyboard tree contains exactly
  one focused node, the `Open File` push button; the Templates tree records its
  selected bundled template list item.
- Normal UNO termination succeeded without forced owned-process cleanup. Exact
  payload processes and headless windows reached zero, the off-screen desktop
  closed, and the dedicated driver stopped with no recorded cleanup error.
- This three-image run replaces the earlier corrected light pair only as the
  canonical gallery source. Runs
  `20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression` and
  `20260720-012853-577059e274-vs2026-msi-raster` remain immutable historical
  accepted proof. The public canonical gallery now contains nine images: three
  light, three dark, and three forced high contrast.
- The result proves only scoped Start Center software-raster runtime,
  pointer-navigation, and one Tab focus transition. It does not prove all
  Material widget states, accelerated rendering, 200% scale, localization,
  suite modules/dialogs, updater execution, or MSI lifecycle behavior.

## 2026-07-20 — newest exact-build light Start Center acceptance

- Run `20260720-135505-7029dccf40-windows-headless-light` accepted the
  extracted runtime from exact source
  `7029dccf40b4d9851e0ea9f9bb2c03ad5ae405b3`, whose VS 2026 MSI/package gate
  had already passed. It used harness
  `861555ee914178cf05f9e39362f6b58bd6d1990f` and clean driver
  `547a102a49169d41da876de217856229ab7c03a1`.
- The driver measured HWND, owning PID, GUI thread ID, and 144 DPI atomically
  inside `EnumDesktopWindows`; the enumerated PID matched the pidfile-owned
  `soffice.bin` PID for three stable polls. This replaces the invalid
  caller-desktop HWND probe without weakening ownership proof.
- Home, visible `Open File` keyboard focus, and Templates produced three
  nonblank `1920x1117` PNGs with the registered hashes `e4a21b…4501`,
  `1039f6…ab13`, and `6fd055…66e5`. Their bound UNO trees contain 96/49,
  96/49, and 111/64 total/visible nodes, zero errors, and no partial result.
- Visual and sensitive-data review passed. Normal UNO termination completed,
  forced cleanup was false, payload processes/windows reached zero, and the
  desktop, dedicated driver, and path-bearing launch wrapper all closed or
  were removed. This is scoped Start Center UI/a11y evidence, not MSI lifecycle
  or updater-runtime proof.

## 2026-07-20 — newest exact-build dark Start Center acceptance

- Run `20260720-140327-7029dccf40-windows-headless-dark` accepted the forced
  dark profile from exact source `7029dccf40b4d9851e0ea9f9bb2c03ad5ae405b3`
  with harness `c61a423cd5a764686d703e57a7a6d5889903ba1e` and clean driver
  `547a102a49169d41da876de217856229ab7c03a1`.
- Home, visible `Open File` keyboard focus, and Templates produced three clean
  `1920x1117` captures with registered hashes `0fc0ea…d78e`, `0e4157…8587`,
  and `742395…a74c`. The bound UNO trees contain 96/49, 96/49, and 111/64
  total/visible nodes with zero errors and no partial result; `Open File` is the
  sole focused node at the keyboard checkpoint.
- Atomic driver-side HWND/PID/thread/DPI matched the pidfile-owned
  `soffice.bin`, visual and sensitive-data review passed, UNO termination was
  normal, forced cleanup was false, and processes/windows/desktop/driver/wrapper
  cleanup completed. The older `fbba560e27` dark run remains historical proof.

## 2026-07-20 — third isolated lifecycle launch reached real MSI update work

- Fresh run
  `20260720-045143-7859553-08fb3836f8b446dda272e206d296a591`
  passed the reviewed Sandbox inspection and exact old/corrected MSI byte pins.
  The guest old-install and corrected same-version commands both returned exit
  code `0`; neither changed the guest reboot fingerprint.
- Post-update verification failed closed because the old ProductCode
  `{F6673D3A-81F6-462E-934F-19438F08C9EA}` remained registered at Windows
  Installer state `5`. The packages have distinct ProductCodes and the same
  test UpgradeCode/version, but this same-version command did not automatically
  remove the old product. Repair and corrected-product uninstall were not run.
- Best-effort cleanup uninstalled the old ProductCode with exit code `0`, left
  both ProductCodes at state `-1`, reported no cleanup errors, and retained
  hash-manifested install/update/cleanup logs plus `FAILURE.json`. Host
  before/after reboot and LibreOffice-registration snapshots were identical.
- The packaged Sandbox client missed its normal disposal deadline, so the run
  has no accepted `host-verification.json` or `COMPLETE.json`. It proves two
  real no-restart MSI operations and the sequencing gap only; lifecycle
  acceptance remains open.

## 2026-07-20 — hosted normal-release draft URL correction

- Windows Actions run `29729295399` at
  `2ed96c4a608cfd7a9b8c5afa1ce14e24301a0817` passed linking, native C++ tests,
  the full product build, MSI generation, administrative extraction, staging,
  and structural validation. Publication alone failed after 36 polls, and
  cleanup removed the exact failed draft/tag.
- The pre-promotion predicate incorrectly required the final canonical tag URL
  while GitHub exposes a draft as `releases/tag/untagged-*`. Current workflow
  source accepts that temporary URL only while `isDraft=true`; published-state
  verification still requires the canonical tag URL.
- `qa/windows-installer-lifecycle/Validate-ReleaseWorkflow.ps1` executes the
  actual helper against draft, valid-published, and invalid-published fixtures,
  rejects a pre-promotion canonical-URL regression, requires post-promotion URL
  equality, and checks final-poll predicate diagnostics. It passes under
  PowerShell 5.1 and 7; `actionlint` and the existing lifecycle validator pass.
- The source correction is committed locally at
  `113971316830b2cb88ffa291ed42481ca68fba6d`; hosted normal non-prerelease
  publication for the next pushed SHA remains to be verified.

## 2026-07-20 — major-upgrade command diagnosis and source correction

- The third Sandbox run's corrected MSI does contain the expected inclusive
  Upgrade-table row and action sequence. Its verbose update log records the old
  ProductCode in `OLDPRODUCTS`, so product discovery and MSI authoring were not
  the cause of the retained old registration.
- The update command incorrectly supplied `REINSTALL=ALL` and
  `REINSTALLMODE=vomus` to the corrected MSI's new ProductCode. Windows
  Installer set `Preselected=1`, left every feature with a null requested/action
  state, and skipped `RemoveExistingProducts` as a maintenance/uninstall case.
  Those properties describe maintenance of an installed ProductCode, not the
  initial feature selection for a major upgrade.
- Current updater source now launches exactly `/i`, the staged MSI,
  `REBOOT=ReallySuppress`, and
  `MSIRESTARTMANAGERCONTROL=DisableShutdown`. The lifecycle update step matches
  that command, while its separate repair step retains `REINSTALL=ALL` and
  `REINSTALLMODE=vomus`.
- The C++ regression expects the exact four-entry updater vector. The lifecycle
  validator additionally rejects either reinstall property in the update block
  and requires both in the repair block. The dependency-free harness validator
  passes under Windows PowerShell 5.1 and PowerShell 7. This remains source and
  static evidence until the native C++ target and a fresh Sandbox lifecycle run
  complete.

## 2026-07-20 — corrected updater vector compiled with Visual Studio 2026

- Clean detached source at
  `150841ef58285e61e7576bda43ca11af93f924c7` was selected in the retained
  VS 2026 build root and incrementally rebuilt against its existing configured
  Windows x64 product cache.
- `CppunitTest_extensions_test_update` completed successfully with all 11 tests,
  including the exact four-argument Windows Installer command, protected
  exclusive staging, and retained read-lock regressions. This is compiled native
  evidence for the command construction, not updater UI or MSI lifecycle proof.

## 2026-07-20 — local packaging wait-race correction

- An incremental VS 2026 `make build` completed at updater source commit
  `150841ef58285e61e7576bda43ca11af93f924c7` and emitted the final MSI. A
  subsequent local wrapper `Package` attempt started administrative extraction,
  then immediately inspected the output and failed because `soffice.exe` had not
  appeared yet. The same run-bound `msiexec.exe` continued after the wrapper
  exited and completed the extraction with one `soffice.exe`, reproducing the
  previously documented parent/installer race.
- `bin/Build-Windows.ps1` now uses its existing Windows argument encoder and a
  hidden `Start-Process -Wait -PassThru` invocation, reads that exact process's
  exit code, and only then inspects the payload. The new dependency-free
  `qa/windows-build/Validate-BuildScript.ps1` rejects a direct `msiexec`
  invocation and requires the waited/hidden/quoted ordering. It passes under
  Windows PowerShell 5.1 and PowerShell 7.
- This is source/static correction plus a diagnostic extraction. A fresh run
  must still produce the canonical staged MSI, checksum, manifest, successful
  extraction log, and exact-source provenance before the wrapper gate closes.

## 2026-07-20 — exact-source VS 2026 wrapper completion

- Exact implementation commit
  `7029dccf40b4d9851e0ea9f9bb2c03ad5ae405b3` passed the five required native
  targets: `tools_test` 102 tests, `extensions_test_update` 11,
  `vcl_widget_definition_reader_test` 9,
  `vcl_file_definition_widget_draw_test` 6, and `vcl_treeview` 2. The required
  `cli_ure`/`unoil` payloads and legacy CLI files were present.
- The subsequent full VS 2026 product/MSI build completed and embedded exact
  `buildid=7029dccf40b4d9851e0ea9f9bb2c03ad5ae405b3`. The corrected wrapper then
  waited for administrative extraction, received exit code `0`, and staged the
  canonical MSI, checksum, JSON manifest, and retained verbose extraction log.
- The unsigned staged MSI is 199,671,808 bytes with SHA-256
  `ea503d3ab4327a3d3936384ceee2c0ef89b7380e5331c017b946d62f13a2b934`.
  Its extraction contains 4,885 files / 603,901,200 bytes, exactly one
  `soffice.exe`, and exactly one 571,392-byte `updchklo.dll`. The extracted and
  build-tree updater DLL hashes match at
  `b8264c74dc07d989b5e056ca8c156e9dd8c2b07181189d3d475f49e52b7fea58`.
- MSI inspection records ProductCode
  `{047F908B-F338-4F1B-B464-F3C1E9438FDE}`, test UpgradeCode
  `{910006D2-BDF1-440C-89D3-8F1DD93790FE}`, inclusive same-version
  `OLDPRODUCTS` detection, `FindRelatedProducts` sequence 100,
  `RemoveExistingProducts` sequence 675, and no `ForceReboot` or
  `ScheduleReboot` action. This closes local build/package provenance, not
  install/update/repair/uninstall or hosted release acceptance.

## 2026-07-20 — footer Donate removal built and accepted in light

- Exact source `393263ad924eae8d64b4f9a35bd6486ef83578fc` passed the focused
  six-test footer validator, VS 2026 `make build`, all five wrapper native test
  targets plus CLI payload checks, MSI staging, and administrative extraction.
- The new unsigned 199,651,328-byte MSI has SHA-256
  `7e8b10575d3a70f8a09f8e5a2f9dcd911b890441fa2493670c4721fa18fd00e9`.
  Its manifest and embedded `program/version.ini` build ID both bind to the
  exact source commit; the extracted `startcenter.ui` contains Help and
  Extensions and contains neither footer `donate` nor `donate_image` IDs.
- Accepted off-screen run
  `20260720-143309-393263ad92-windows-headless-light` captured Home, visible
  `Open File` Tab focus, and Templates at `1920×1117`. Its complete UNO trees
  contain 93/46, 93/46, and 108/61 total/visible nodes with zero errors and no
  truncation. All three reviewed screenshots visibly omit the footer Donate
  control. Normal UNO termination and every process/window/desktop/driver
  cleanup gate passed without forced payload cleanup.
- This is light-profile runtime evidence only. Dark and forced-high-contrast
  post-removal refreshes were then completed in runs
  `20260720-144200-393263ad92-windows-headless-dark` and
  `20260720-144249-393263ad92-windows-headless-highcontrast`. Both accepted
  Home/focus/Templates, the 93/46, 93/46, and 108/61 complete tree counts, the
  two-action footer, normal termination, and full cleanup. Broader
  dialogs/suite surfaces, updater UI, and MSI lifecycle acceptance remain open.

## 2026-07-20 — centralized Windows dialog placement source contract

- `bin/check-windows-dialog-placement.py` passed against the shared VCL
  post-`InitShow` hook, Windows and LibreOfficeKit guards, visible owner/work-area
  anchoring, bounded 16 px inset, and decorated-extent clamping.
- `bin/test_windows_dialog_placement.py` passed all 11 mutation regressions;
  Python byte-compilation, `git diff --check`, and focused Clang formatting also
  passed.
- This is source/static evidence only. No current VS 2026 build, dialog capture,
  keyboard flow, accessibility audit, scaling/multi-monitor test, or
  notification-manager behavior is claimed.

## 2026-07-20 — Windows unsolicited-prompt removal source contract

- `bin/check-windows-no-nag-contract.py` passed with nine deleted prompt
  surfaces, 35 forbidden automatic/promotion markers, and 16 retained
  suppressions, safeguards, or manual actions.
- `bin/test_windows_no_nag_contract.py` passed all four mutation families; the
  Start Center no-donate validator and all eight regressions also passed.
- Modified UI, configuration, and test-profile XML parsed successfully; deleted
  controller/UI build references are absent; `git diff --check` passed. The
  retained modified Options and manual Tip UIs now pass `gla11y` with zero
  warnings after the dead crash-report opt-in was removed and their static,
  year-range, and illustration semantics were made explicit.
- No current native compile or startup run is claimed. Fresh and seeded legacy
  profiles must prove zero unsolicited UI while retained safety/manual flows
  remain actionable.

## 2026-07-20 — shared anchored regex-builder source foundation

- `bin/check-windows-regex-builder-foundation.py` passed the shared
  ICU/LibreOffice engine, literal/regex modes, `i/g/m/s`, bounded and zero-width
  matching, anchored `GtkPopover`, Apply/Cancel/click-away behavior, and native
  test/build wiring contract; all eight mutation regressions passed.
- `bin/lint-ui.py` and `bin/gla11y` passed the new builder with zero warnings.
  The existing search-field registry still passes independently.
- Twelve focused native CppUnit cases are registered but not yet compiled or run.
  No per-field integration, visible builder interaction, accessibility runtime,
  performance limit, or exact-build proof is claimed.

## 2026-07-20 — local Git notification-history source foundation

- `bin/check-notification-store-contract.py` passed the public state model,
  deterministic metadata-only redaction, genuine bare loose-object Git format,
  fixed local `main`, permanent process/OS operation guard, lock/CAS ordering,
  recoverable tombstones, inverse-commit undo, bounded preferences, schema, and
  focused native-test wiring contract.
- `bin/test_notification_store_contract.py` passed all 15 mutations, including
  guard lifetime, metadata-only history traversal, type-specific streaming
  inflate limits, pre-mutation compaction, pending-marker validation, and
  installed-checkpoint reuse after repeated prune failure.
- Thirteen native CppUnit cases are wired for model/bulk behavior, privacy,
  reload/races/contention, 129-commit compaction, exact undo, crash recovery,
  repeated forced prune failure, and preference bounds. The notification source
  also passed a focused clang-cl syntax-only probe with temporary generated
  header/zlib stubs; no repository-native compile or runtime behavior is claimed.

## 2026-07-20 — asynchronous notification service source checkpoint

- `python bin/check-notification-store-contract.py`: passed the serialized
  worker/store lifetime, immutable snapshot, conflict refresh, generated
  configuration, shutdown ordering, application lifetime, and single-call bulk
  additions alongside every earlier storage/privacy invariant.
- `python -m unittest bin/test_notification_store_contract.py`: 18/18 mutation
  tests passed, including new worker lifetime, bulk dispatch, and complete
  generated-accessor guards.
- `node bin/validate-prototype.mjs`: 9/9 passed; the target notification and
  regex-builder surfaces remain intact.
- `git diff --check`, Python byte-compilation, notification schema XML parsing,
  and Clang format dry-run for all new C++/test files passed.
- Five native service CppUnit cases are wired into
  `CppunitTest_sfx2_notificationstore` but were not compiled or run. No shared
  retained build directory was used, and no application/runtime proof is
  claimed for this source checkpoint.

## 2026-07-20 — adversarial notification-service lifecycle review

- Compared the branch against requested `origin/main` `e439db6f8`, then
  rechecked after the remote advanced to `01bed9c7d`. The in-tree
  `salhelper::Thread`, VCL user-event, application-lifetime, generated
  configuration, and CppUnit build APIs were inspected without using a retained
  build root; the later standalone C++20 notification-test corrections were
  mirrored without rebasing or merging.
- Fixed raw VCL Link lifetime during reentrant destruction, concurrent
  enqueue/shutdown owner races, launch-failure teardown, worker admission order,
  off-main event cancellation, and the former inline-dispatch Windows self-join
  path. Cancelled callback closures now remain owned for main/VCL-side disposal.
- `python bin/check-notification-store-contract.py` and all 24 mutation tests
  pass. Twenty-one native notification CppUnit cases are wired, including
  concurrent admission, completion-side service destruction, and
  missing-dispatcher rejection, but are not compiled or run in this source-only
  review.
