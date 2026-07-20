# LibreOffice Material roadmap

This roadmap covers a whole-GUI modernization, not a theme preview. It is
ordered so shared native primitives are proved before individual applications
diverge. Dates are intentionally omitted until build capacity and baseline
metrics are recorded.

Status vocabulary:

- **planned** — scoped but no accepted implementation evidence;
- **in progress** — implementation exists but one or more acceptance gates fail;
- **verified** — code, build, interaction, accessibility, and visual evidence all
  pass at a recorded commit;
- **blocked** — a named external dependency prevents further work.

No phase is currently marked verified.

## Phase 0 — reproducible foundation

**Status: in progress**

- preserve and document the exact LibreOffice upstream baseline;
- establish the Material design contract and token vocabulary;
- publish an honest project site and screenshot registry;
- publish an interactive, dependency-free Material design reference on the site
  as the whole-suite visual and interaction target — 11 suite surfaces, a regex
  builder on every search bar, and a Find & Replace dialog (explicitly a
  hand-built mockup, not a build screenshot);
- guard that reference and the build path in CI: a dependency-free validator
  (`bin/validate-prototype.mjs`) and `prototype-check.yml` check its
  self-containment, tokens, icons, and regex engine, while `build-installer.yml`
  attempts a Linux package and every `main` push (or manual dispatch) starts
  `windows-installer.yml`. The Windows workflow pins Visual Studio 2022,
  provisions Cygwin, runs the required native tests, uploads the validated MSI
  directly to an exact draft release, and only then publishes a normal public,
  non-prerelease Latest Windows x64 MSI release;
- define native build profiles and artifact retention rules, including a
  source-controlled local Windows bootstrap/build entry point;
- preflight the low-level computer-use driver and an off-screen desktop;
- connect that proven harness to a built LibreOffice binary and isolated profile;
- establish a repository-memory ledger for decisions, evidence, and progress.

Current evidence: the Windows harness preflight passed on 2026-07-16 using a
temporary Notepad process. On 2026-07-20, the harness advanced to the real
LibreOfficeDev MSI payload and accepted two light-profile Start Center captures
plus two bounded UNO trees with no collector errors. The local
[one-click Windows script](docs/LOCAL_WINDOWS_BUILD.md) now provisions an
isolated VS 2022 C++/CLI/C++ Clang/Cygwin profile, validates it, and creates a
clean LF source snapshot. On 2026-07-19, its first bootstrap installed the
dedicated VS 2022/Cygwin profile and a clean preflight passed; the first real
configure then exposed the absent C++ Clang compiler required by the default
Skia build. The local bootstrap now requires that component before retrying.
The hosted Windows workflow uses a clean LF checkout and a pinned runner that
supplies its prerequisites. Current
source Linux run `29695793821` and Windows run `29695815101` both passed
`tools_test`, `extensions_test_update`, `vcl_widget_definition_reader_test`,
`vcl_file_definition_widget_draw_test`, and `vcl_treeview`; the Windows run also
passed the legacy CLI payload check and built the full LibreOfficeDev
installation set.

The local script's default remains the isolated, CI-matching VS 2022 profile.
It also has an explicit local-only VS 2026 selection through
`-VisualStudioYear 2026`. A verified existing host installation can be selected
only by also passing its exact `-VisualStudioInstallPath`; an incomplete host
path stops rather than being repaired or silently substituted. Without that
path, the opt-in profile uses its dedicated
`%ProgramData%\LibreOfficeMaterialTools\VS2026` Build Tools root. Use a distinct
build root such as `$env:USERPROFILE\lo-material-vs2026` for its first run. The
CI workflow remains pinned to VS 2022 for now.
The local checker recognizes both the VS 2022 `Llvm\bin` layout and VS 2026's
host-native `Llvm\x64\bin` Clang layout.
On 2026-07-19, the named VS 2026 Enterprise host passed no-bootstrap preflight
after C++/CLI, Clang, and VC145 merge modules were installed, then completed an
isolated configure at `a6d9f9a7dbdf10c08afe2eb03239e702ec5172ef`. Its first
native build reached third-party compilation and exposed MSVC v145's C++20
`mdds` conditional-`noexcept` incompatibility. The source now carries a
bounded v145 C++20 workaround. A fresh exact-source build at
`577059e2741185b512c184c64685c16d335d10ea` then passed all five required
native targets, validated the legacy CLI payload, completed the product, and
produced an unsigned 199,692,288-byte MSI. Windows Installer administrative
extraction returned status `0` with one `soffice.exe`, and that extracted
runtime supplied the accepted Start Center UI and bounded UNO-tree smoke.

Run `29695815101` did not upload an MSI: its staging script recursively matched
two retained LibreOffice working databases as well as the final installer. The
workflow now inspects only the success-only final `LibreOfficeDev\msi\install\en-US`
directory and still requires exactly one MSI plus administrative extraction and
`soffice.exe` validation. That corrected staging rule needs a hosted rerun. The
local wrapper's parent process exited after successful extraction but before its
final dist staging/manifest copy, so an end-to-end wrapper run and public normal
release remain open.

The local script is intentionally non-destructive: it checks safe short roots,
both tool/build-drive free space, and a clean checkout before installing
dependencies when Git is already available; it uses isolated Cygwin Git rather
than installing a global Git client. It does not normalize the development
checkout, delete a prior build root, silently use a host Visual Studio
installation, reboot Windows, or install its MSI. Its
VS 2022 default and VS 2026 build state cannot resume each other's work. A
complete successful full run removes only its verified-clean temporary LF
worktree. The completed VS 2026 build proves the selected toolchain/product path;
the wrapper's final staging/manifest phase still requires a clean rerun.

The source now contains a Windows-only consent-based update path. It reads the
exact GitHub Latest XML asset and accepts only one safe tag-derived GitHub URL
for the canonical MSI with exact `application/x-msi` MIME, positive size, and
lowercase SHA-256 metadata. It rejects legacy or malformed persisted state,
checks the completed download, and on confirmation copies it with `CREATE_NEW`
into protected LocalAppData staging with a user/Administrators/SYSTEM DACL,
re-verifies it, and retains a final read lock against write/delete replacement.
The visible MSI launch requires explicit default-No consent; silent install is
not implemented, and it passes `REBOOT=ReallySuppress` so it cannot request or
force a Windows restart. Automatic checks default on weekly, while automatic
download is off and download/install remain opt-in. See [`PRIVACY.md`](PRIVACY.md).
A bounded read-only UNO accessibility-tree collector now accompanies the
off-screen desktop plan. It runs with the matching built Python runtime and
records window roles, names, states, child counts, and optional bounds without
reading document text or invoking UI actions. The accepted light Start Center
run collected two complete bounded trees with no collector errors; this is a
collector smoke result, not a full accessibility audit.
The required native targets, local Windows MSI, and light Start Center headless
smoke have completed for exact source `577059e274`. Public release, updater and
installer lifecycle, the remaining UI/accessibility matrix, and the wrapper's
final dist staging phase remain pending.

An interactive, dependency-free Material design reference for the whole suite is
published at [`site/prototype.html`](site/prototype.html): a hand-built HTML
rendering of all eleven surfaces (Start Center, Writer, Calc, Impress, Draw,
Base, Math, Features, History, Components, Dialogs) with light/dark/high-contrast
themes, compact/comfortable density, classic/ribbon chrome, a regex builder on
every search bar, and a Find & Replace dialog. Its tokens mirror
`material/definition.xml` (documented in
[`docs/DESIGN_TOKENS.md`](docs/DESIGN_TOKENS.md)), and
[`bin/validate-prototype.mjs`](bin/validate-prototype.mjs) guards its invariants
(7/7). It specifies the design the native work targets and is **not** a capture
of a compiled build, so it does not advance any acceptance gate or the
verified-capture count. The exact-source local MSI and Start Center evidence are
tracked separately; no validated public installer release exists. The historical
assetless release/tag `e` contains no build and does not satisfy any
release or evidence gate. Neither package workflow publishes unless a real
package is produced and validated.

Exit gate:

- a clean checkout can reproduce the chosen build;
- the start center can be launched on a headless desktop;
- an unedited baseline screenshot and manifest can be captured and reviewed;
- documentation distinguishes current evidence from planned work.

## Phase 1 — Material foundations in VCL

**Status: in progress — native C++ targets and light Start Center smoke passed;
remaining runtime matrix pending**

Implemented source milestones:

- packaged `material/definition.xml` with matched light and dark palettes of 23
  semantic roles each, 79 definition-backed parts, and 205 control states;
- exact semantic coverage for all 72 `StyleSettings` color slots, including the
  formerly native-dependent accent, list-box collection/selection,
  alternating-row, warning, and error roles; the ten additions are optional in
  the general reader so partial legacy themes keep their native values;
- opt-in `VCL_FILE_WIDGET_THEME=material` selection behind the existing
  `VCL_DRAW_WIDGETS_FROM_FILE` gate, with safe theme names, shared immutable
  definitions, and successful-load caching keyed by theme and scheme; failed
  requests attempt `online`, which is absent from this imported desktop tree;
- source-level profile selection from resolved dark mode, with high contrast
  taking precedence and bypassing Material colors for native or generic
  fallback drawing;
- capture/restore of the pre-Material native style/framework baseline, plus
  dynamic focus-policy refreshes so a switch to generic high-contrast fallback
  does not retain Material colors or suppress VCL focus indicators;
- semantic `body`, `label`, and `title` typography roles with strict parsing,
  100–200% nonshrinking scale bounds, explicit minimum weights, and native
  font identity preservation across app, help, field, control, menu, tab, and
  title slots;
- eight semantic corner roles with strict, order-independent native reader
  resolution; 159 rounded Material rectangles now use one role reference each,
  11 square rectangles remain implicit, and legacy numeric `rx`/`ry` themes
  retain their existing path;
- 15 semantic native integer metric roles with strict, order-independent native
  reader resolution; 346 current integer uses reference those roles—307 drawing
  strokes, 34 explicit part dimensions/margins, and 5 numeric settings—while
  generic legacy themes retain literal numeric compatibility;
- exact geometry preservation across that conversion: the 684 normalized
  fractional drawing coordinates stay literal, implicit dimensions remain
  implicit, and typography scale and corner radius keep their separate token
  contracts;
- Qt proxy/no-native high-contrast signal handling and explicit dark-profile
  selection when headless VCL has no operating-system appearance signal;
- support reporting limited to definition-backed parts so unsupported parts
  preserve their existing fallback;
- order-independent semantic color, shape, and metric `@token` resolution with
  strict rejection of invalid colors, radii, or integer metrics, invalid
  or duplicate token sections, mismatched palette schemas, ambiguous radius
  attributes, unknown references, and unknown or duplicate parts;
- expanded mixed/disabled controls, flat buttons, selected-hover/focus tabs,
  toolbar buttons and grips, list nodes, edit variants, scrollbars, sliders,
  menus, progress, surfaces, and standalone vertical/horizontal spin buttons;
- full-track progress indicators and value-sensitive level indicators in the
  shared file-widget renderer: the optional track spans the control, the fill
  remains clipped to the caller's numeric value, and level states preserve the
  four existing 25% semantic bands without changing legacy fill-only themes;
- native anatomy for the two reader-recognized controls the theme had not yet
  defined: an outlined frame (`Frame`/`Border`) drawn as one shared container
  rectangle and reported through a new native frame region so `decoview` issues
  its border draw, and a net-less tree connector (`ListNet`/`Entire`) that is
  supported but draws nothing so VCL suppresses its own connector nets; both add
  no new tokens and only one `stroke-thin` reference and one rounded rectangle;
- disabled-affordance state completeness: a dimmed disabled `SubmenuArrow`, a
  dimmed-but-checked toolbar button, and a disabled-but-selected tab (`Entire`
  and `MenuItem`), closing three cases where a disabled tuple VCL passes
  previously collapsed onto a generic state and lost its meaning;
- composite combo/RTL geometry, native-region and slider sizing corrections,
  exact standalone spin geometry/direction, and native graphics line/fill cache
  invalidation;
- local static validation for color/shape/metric token discipline, an exact
  72-slot Material style schema, required parts/states, unused tokens,
  light/dark schema parity, exact geometry closure, and selected contrast pairs,
  with reader and headless drawing C++ targets plus negative fixtures; the
  headless target includes source coverage that dispatches settings through the
  real file renderer.

The standalone validator passes with 2 schemes, 23 color tokens each, 3
typography roles, 8 shape tokens, 15 metric roles, 72 style slots, 79 parts, and
205 states. The five required native C++ targets have compiled and executed in
current Linux and Windows runs, while none of this source has run in a
LibreOffice application scenario yet. The metric roles preserve the current
integers and existing downstream native conversions; they add no density
profile or new DPI-aware, `dp`, fractional-scale, or touch-sizing policy.

- build/runtime verification of light/dark, focus, and high-contrast routing,
  plus complete forced-color and platform-signal coverage;
- remaining typography properties (line height and letter spacing),
  density-aware spacing/metric profiles, density-aware/full shape semantics,
  elevation, opacity, motion, and density selection;
- remaining dragged, read-only, invalid, and platform-specific state layers;
- reusable focus rings and keyboard modality handling;
- core button, icon button, checkbox, radio, switch, text field, list, tab,
  tooltip, menu, progress, and surface primitives;
- build-backed C++ and pixel/region regression coverage across platforms.

Exit gate:

- primitives render through native VCL paths on supported desktop platforms;
- token values are centralized and application code does not hard-code Material
  colors;
- every state is keyboard reachable and has accessible semantics;
- headless light, dark, high-contrast, and scaling evidence is recorded.

## Phase 2 — shared shell and common surfaces

**Status: in progress — initial Start Center source, native builder coverage,
and light launch/navigation smoke passed; broader shell runtime pending**

The Start Center source slice adds spacing, a Home header/subtitle, distinct
navigation/content/container surfaces, and VCL-derived recent/template colors.
Its `open_all` button now uses the standard `suggested-action` semantic, which
`VclBuilder` preserves as the push-button action state selecting the existing
Material `extra="action"` styling. Its focused `VclBuilder` fixture passed in
the current Linux, Windows, and local VS 2026 native runs. The exact-source MSI
payload has now displayed and captured the light Start Center Home and Templates
states; dark/high-contrast, visible action-state exercise, and broader shared
shell scenarios remain open.

- start center, window chrome integration, menubar/command surfaces, status bar,
  sidebar shell, notebookbar variants, infobars, snackbars, and notifications;
- common file, print, export, properties, options, extension, and template flows;
- adaptive command layout for compact, medium, and expanded window widths;
- shared empty, loading, error, and destructive-confirmation states.

Exit gate:

- shared surfaces no longer require application-specific Material forks;
- shortcuts and menu mnemonics remain intact;
- common flows pass headless keyboard and screenshot matrices.

## Phase 3 — Writer

**Status: planned**

- document canvas framing, rulers, navigation, styles, properties, review, and
  collaboration surfaces;
- formatting, tables, images, references, mail merge, and page-layout flows;
- comments, tracked changes, search, accessibility checks, and error states.

Exit gate:

- the agreed Writer workflow suite passes with keyboard-only operation;
- no regression is detected in document rendering or round-trip compatibility;
- representative widths, locales, themes, and scaling factors have evidence.

## Phase 4 — Calc

**Status: planned**

- formula bar, sheet tabs, headers, selection affordances, filters, sort, data,
  pivot, chart, and conditional-formatting surfaces;
- dense-grid interaction rules that preserve spreadsheet throughput;
- large-sheet performance and assistive-technology navigation checks.

Exit gate:

- core spreadsheet workflows pass at performance and accessibility budgets;
- formula and grid behavior remain independent of visual token changes;
- dense and touch-friendly profiles have recorded evidence.

## Phase 5 — Impress and Draw

**Status: planned**

- slide/page panes, canvas controls, object properties, master views, animation,
  transitions, presenter console, and drawing tool surfaces;
- drag, resize, rotate, selection, alignment, layering, and multi-object states;
- presentation and multi-display regression coverage.

Exit gate:

- authoring and presenting workflows pass on supported display configurations;
- pointer, keyboard, and assistive selection paths are equivalent;
- animation honors reduced-motion preferences.

## Phase 6 — Base, Math, charts, and remaining UI

**Status: planned**

- Base database, query, form, and report workflows;
- Math formula editor and symbol selection;
- chart editing, macros, extensions, certificates, recovery, onboarding, and
  legacy dialogs not covered by shared-shell work;
- complete inventory closure for every registered UI surface.

Exit gate:

- the UI inventory contains no unclassified or silently excluded surface;
- platform-specific and optional-feature dialogs have owners and evidence;
- fallback rendering is explicit where Material behavior is unavailable.

## Phase 7 — suite-wide hardening

**Status: planned**

- screen-reader and keyboard audits across platforms;
- high contrast, forced colors, color-vision, reduced-motion, and zoom checks;
- bidirectional text, long translations, CJK/CTL fonts, and locale formatting;
- startup, memory, paint, input-latency, and large-document performance budgets;
- GPU/software rendering, remote desktop, fractional scaling, and multi-monitor
  matrices;
- migration, safe mode, crash recovery, and profile compatibility.

Exit gate:

- defined accessibility and performance budgets pass in CI or recorded labs;
- P0/P1 visual defects are closed and no critical workflow lacks evidence;
- release notes identify known exceptions without hiding them.

## Phase 8 — release readiness and upstreamability

**Status: in progress — updater and stable-release automation source only;
native and release proof pending**

- complete native validation of the Windows updater and stable packaging path;
- preserve the exact GitHub Latest XML, strict MSI metadata/hash checks,
  protected staging, explicit consent, and no-silent-install contract;
- publish through the draft-first workflow only after exact target, asset,
  digest, normal-release, and public Latest checks pass;
- contributor, design-review, and regression-triage documentation;
- licensing, attribution, trademark, privacy, and security reviews;
- split generally useful improvements into reviewable upstream proposals;
- publish a signed evidence index and supported-platform statement.

Exit gate:

- every whole-GUI requirement maps to accepted evidence or a documented,
  user-visible exception;
- release artifacts reproduce from tagged source;
- the project no longer needs a milestone disclaimer to explain unfinished core
  surfaces.

## Cross-phase acceptance matrix

Every visible component or workflow must be checked against:

| Dimension | Minimum evidence |
| --- | --- |
| Build | exact commit, platform, configuration, and successful artifact |
| Visual | genuine capture at agreed themes, scale factors, and widths |
| Interaction | pointer and keyboard path with expected state transitions |
| Accessibility | role/name/state, focus order, contrast, zoom, and motion behavior |
| Localization | long-string, bidirectional, and representative CJK/CTL coverage |
| Performance | comparison against an agreed upstream baseline |
| Compatibility | document results and user profile behavior unchanged unless specified |

The live evidence contract is in [`docs/HEADLESS_UI_EVIDENCE.md`](docs/HEADLESS_UI_EVIDENCE.md).
