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
- define native build profiles and artifact retention rules;
- preflight the low-level computer-use driver and an off-screen desktop;
- connect that proven harness to a built LibreOffice binary and isolated profile;
- establish a repository-memory ledger for decisions, evidence, and progress.

Current evidence: the Windows harness preflight passed on 2026-07-16 using a
temporary Notepad process, but no LibreOffice build or window was involved. The
host has usable Visual Studio Build Tools 2022, but no complete supported
LibreOffice build profile: WSL 2.7.10 has no installed distribution/helper, and
required Unix/configuration and Java tooling remains incomplete.

Exit gate:

- a clean checkout can reproduce the chosen build;
- the start center can be launched on a headless desktop;
- an unedited baseline screenshot and manifest can be captured and reviewed;
- documentation distinguishes current evidence from planned work.

## Phase 1 — Material foundations in VCL

**Status: in progress — source only; build and runtime verification pending**

Implemented source milestones:

- packaged `material/definition.xml` with a 19-role static light semantic
  palette, 70 definition-backed parts, and 172 control states;
- opt-in `VCL_FILE_WIDGET_THEME=material` selection behind the existing
  `VCL_DRAW_WIDGETS_FROM_FILE` gate, with safe theme names, a keyed cache, and
  fallback to the `online` definition;
- support reporting limited to definition-backed parts so unsupported parts
  preserve their existing fallback;
- order-independent semantic `@token` resolution with strict rejection of
  invalid colors, unknown or duplicate tokens, and unknown or duplicate parts;
- expanded mixed/disabled controls, flat buttons, selected-hover/focus tabs,
  toolbar buttons and grips, list nodes, edit variants, scrollbars, sliders,
  menus, progress, and surfaces;
- composite combo/RTL geometry, native-region and slider sizing corrections,
  plus native graphics line/fill cache invalidation;
- local static validation for token discipline, required parts/states, unused
  tokens, and selected contrast pairs, with expanded unexecuted C++ reader tests
  and negative fixtures.

The standalone validator passes with 19 tokens, 70 parts, and 172 states. None
of the C++ source has been compiled or executed in LibreOffice yet.

- dynamic light, dark, high-contrast, forced-color, and platform token mapping;
- typography, spacing, shape, elevation, opacity, motion, and density tokens;
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

**Status: in progress — initial Start Center source only; runtime pending**

The Start Center source slice adds spacing, a Home header/subtitle, distinct
navigation/content/container surfaces, and VCL-derived recent/template colors.
It has not been built, displayed, or captured.

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

**Status: planned**

- stable packaging and upgrade path;
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
