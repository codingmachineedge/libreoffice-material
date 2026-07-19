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
