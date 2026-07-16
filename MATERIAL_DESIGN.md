# Material Design contract

This document translates Material Design 3 ideas into LibreOffice's native
desktop architecture. It is a starting contract, not proof that the current UI
implements these rules.

## Current implementation status

Two native source milestones now exist. They package an opt-in Material
file-widget definition, add safe keyed theme selection and definition-aware
fallback in VCL, begin the Start Center surface/header treatment, and implement
a static light palette of 19 semantic roles. The reader resolves `@token`
references independently of declaration order and rejects invalid colors,
unknown or duplicate tokens, and unknown or duplicate control parts. The theme
currently validates 70 definition-backed parts and 172 states, including mixed
and disabled controls, flat buttons, selected-hover/focus tabs, toolbar
buttons/grips, list nodes, and borderless and multiline edits.

The shared renderer also contains source corrections for composite combo and
RTL geometry, toolbar grip regions, slider sizing, definition-backed regions,
and native line/fill cache invalidation. A standalone validator checks token
discipline, unused roles, required control/state coverage, and selected contrast
pairs; expanded C++ reader tests and negative fixtures are present but have not
executed.

This slice is **implemented source, not verified behavior**: it has not been
compiled or run as LibreOffice. Once a compatible build exists, it is intended
to be explicitly enabled with both `VCL_DRAW_WIDGETS_FROM_FILE=1` and
`VCL_FILE_WIDGET_THEME=material`. Windows printer graphics are excluded from
the new initialization path, and unsupported file-theme parts retain existing
fallback drawing.

## Goals

- create one coherent visual and interaction system across the entire suite;
- preserve the speed and information density required by professional office
  workflows;
- implement reusable behavior in shared native layers before application code;
- make light, dark, high-contrast, scaling, localization, and accessibility
  first-class rather than follow-up themes;
- keep document rendering and file-format behavior independent from chrome work.

## Non-goals

- replacing the native desktop application with the project website;
- shipping a static color theme and calling the whole GUI complete;
- copying mobile dimensions into every desktop workflow;
- removing expert commands, shortcuts, menus, or platform integrations;
- inventing screenshot evidence before a corresponding build exists.

## Native implementation boundary

Product changes stay in the language and resource conventions of their
LibreOffice modules. In practice that means C++ in VCL/framework/application
code, UNO interfaces where required, and XML `.ui` or configuration resources
for declared surfaces. New web runtime dependencies are out of scope for the
desktop GUI. HTML and CSS under `site/` serve only the documentation website.

Shared behavior belongs in shared modules. A Writer-only Material button is a
design smell if the same control can be expressed once in VCL and consumed by
Writer, Calc, Impress, Draw, Base, and Math.

## Semantic token model

Components consume semantic roles, never palette indices. The first token API
should cover:

| Family | Example semantic roles |
| --- | --- |
| Color | primary, on-primary, primary-container, surface, surface-container, outline, error, inverse-surface |
| Type | display, headline, title, body, label, code/data; each with size, weight, line height, and letter spacing |
| Shape | none, extra-small, small, medium, large, extra-large, full |
| Elevation | level 0–5 expressed through native shadow/surface treatment |
| Spacing | a compact desktop scale with density-aware increments |
| State | hover, focus, pressed, dragged, selected, disabled, read-only, invalid |
| Motion | duration and easing roles, plus an immediate reduced-motion mapping |
| Layout | compact, medium, expanded window classes and platform insets |

Token resolution must incorporate the operating system theme, LibreOffice user
preferences, high-contrast/forced-color requirements, display scale, and the
active density profile. Contrast and legibility outrank brand palette matching.

The current file-widget definition implements only a static light semantic
color layer. Dynamic dark, high-contrast, forced-color, platform, density,
typography, shape, elevation, and motion resolution remain planned.

## Component behavior

Each component specification must define:

- visual anatomy and semantic token use;
- role, accessible name, description, value, and state exposure;
- hover, focus-visible, pressed, selected, invalid, disabled, and read-only
  states where relevant;
- pointer, touch, keyboard, mnemonic, and screen-reader interactions;
- compact and comfortable density behavior;
- bidirectional layout, long labels, and font fallback;
- platform differences that are deliberate rather than accidental;
- headless scenarios and screenshot checkpoints.

The initial shared set includes buttons, icon buttons, toggles, fields, search,
tabs, menus, lists, trees, tables, tooltips, progress, dialogs, banners,
snackbars, navigation containers, toolbars, status surfaces, and side panels.

## Desktop density

Material hierarchy should improve scanning without sacrificing working space.
LibreOffice needs at least two intentional density profiles:

- **compact** for keyboard/mouse use, data grids, and expert workflows;
- **comfortable** for touch, high zoom, and users who prefer larger targets.

Minimum target size and spacing may vary by input modality, but focus visibility
and hit-area predictability may not. Calc's grid, Writer's rulers, and dense
property panels need component-specific rules rather than global padding.

## Adaptive layout

Window width, not device labels, drives layout. Shared chrome should define
compact, medium, and expanded arrangements while preserving access to every
command. Overflow is a designed state with stable keyboard order—not a place
where controls silently disappear.

Narrow-window checks are required for dialogs, sidebars, command surfaces, and
localized labels. Multi-monitor placement, fractional scaling, and OS insets are
part of the desktop layout contract.

## Accessibility contract

- every action is keyboard reachable without pointer-only intermediate states;
- focus order follows reading and task order, with a persistent visible focus
  indicator;
- color is never the only carrier of meaning;
- semantic roles/names/states are exposed through existing accessibility APIs;
- text and UI remain operable under zoom, high contrast, and forced colors;
- meaningful motion has a reduced or removed alternative;
- errors identify both the problem and a recovery action;
- bidirectional and translated content are verified, not inferred.

Passing a screenshot review cannot substitute for accessibility evidence.

## Motion and elevation

Motion explains continuity and state change; it does not decorate routine
typing, selection, or document navigation. All transitions must avoid blocking
input, honor reduced motion, and stay within measured performance budgets.

Elevation communicates containment and temporary overlap. Native platform
rendering may express it with shadows, borders, tonal surfaces, or a combination
that remains legible in high contrast. Elevation must never be encoded only by a
low-contrast shadow.

## Iconography and assets

Prefer the established LibreOffice icon pipeline and native raster/vector asset
rules. Icons need consistent optical size, stroke, state, and directionality;
mirroring is semantic, not automatic for every glyph. No externally hotlinked
asset belongs in a build or the project site. Generated art is not accepted as
runtime or evidence imagery without an explicit, reviewed asset decision.

## Verification gate

A surface can be called Material-complete only when:

1. it consumes shared semantic tokens and components where applicable;
2. all states and input methods have deterministic behavior;
3. accessibility, localization, scaling, and theme matrices pass;
4. performance and document behavior stay within agreed budgets;
5. real screenshots and interaction results are registered for the exact commit;
6. any platform exception is visible in documentation.

See [`ROADMAP.md`](ROADMAP.md) and
[`docs/HEADLESS_UI_EVIDENCE.md`](docs/HEADLESS_UI_EVIDENCE.md) for sequencing and
the evidence format.
