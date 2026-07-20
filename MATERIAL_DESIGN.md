# Material Design contract

This document translates Material Design 3 ideas into LibreOffice's native
desktop architecture. It is a starting contract, not proof that the current UI
implements these rules.

The complete written design specification — foundations, every shared
component, and every application surface, with per-component anatomy, state,
interaction, accessibility, density, RTL, platform, and verification sections —
lives in [`docs/design/`](docs/design/README.md). This document remains the
short contract; the spec set is its full elaboration and inherits its honesty
rules.

The canonical visual and interaction reference is the interactive prototype at
[`site/prototype.html`](site/prototype.html): a hand-built, dependency-free HTML
rendering of the whole suite (Start Center, Writer, Calc, Impress, Draw, Base,
Math, a component gallery, the full command catalog, version history, and shared
dialogs) across light/dark/high-contrast themes, compact/comfortable density,
and classic/ribbon chrome. Its color, shape, type, and metric values are drawn
from the same semantic roles as
[`vcl/uiconfig/theme_definitions/material/definition.xml`](vcl/uiconfig/theme_definitions/material/definition.xml).
It specifies the target design; it is a mockup, not a screenshot of a compiled
LibreOffice, and it is not build or accessibility evidence.

## Current implementation status

Ten native source milestones now exist, followed by a native-test-backed Start
Center action and Windows MSI configuration follow-up. They package an opt-in Material
file-widget definition, add safe keyed theme selection and definition-aware
fallback in VCL, begin the Start Center surface/header treatment, and implement
matched light and dark palettes of 23 semantic roles each. `open_all` declares
the standard `suggested-action` class, which `VclBuilder` maps to
`PushButton::setAction(true)` so the existing Material `extra="action"` states
can be selected under the opt-in Material renderer. The accompanying Windows
MSI workflow repair restores the legacy CLI payload that its manifests require.
Current Linux, Windows, and local VS 2026 runs passed the five required native
C++ targets. The exact-source local build produced a structurally extracted MSI,
and its payload supplied an accepted light Start Center launch/navigation smoke
with two registered screenshots and two bounded UNO trees. No surface is
Material-complete, and the public release, updater, and broader runtime matrix
remain open. The reader resolves
`@token` references independently of declaration order and rejects invalid
colors, invalid or duplicate palettes, mismatched schemas, unknown or duplicate
tokens, and unknown or duplicate control parts. The theme currently validates
79 definition-backed parts and 205 states, including mixed and disabled
controls, flat buttons, selected-hover/focus tabs, toolbar buttons/grips, list
nodes, borderless and multiline edits, and standalone vertical/horizontal spin
buttons, plus full-track progress and value-sensitive level indicators.

The fourth milestone introduces the first non-color token family: strict
`body`, `label`, and `title` typography roles. Material definitions may select
a 100–200% relative height and one of five bounded minimum-weight policies, but
they cannot select a font family. The renderer derives every role from the
captured native `StyleSettings` baseline on each refresh, preserves script/language,
charset, family, style, pitch, orientation, width, and icon-font identity, and
never reduces a positive native font height. This path is covered by source
tests but remains uncompiled and unexecuted.

The fifth milestone closes the semantic color boundary between the file theme
and all 72 `StyleSettings` color slots. Accent, list-box
collection/selection, alternating-row, warning, and error colors now resolve
from the selected Material profile. Four feedback roles add contrast-checked
warning/error container and text pairs. The ten new reader fields are optional,
so an older or out-of-tree theme that omits them keeps the native values instead
of receiving empty defaults. Material itself requires every slot and exact
semantic mapping.

The sixth milestone introduces eight semantic corner roles. A strict optional
`shapes` section is resolved in the reader's order-independent first pass, and
one `radius="@role"` reference populates both existing native rectangle radius
axes. The 159 rounded Material rectangles use the exact `corner-checkbox`,
`corner-indicator`, `corner-focus`, `corner-small`, `corner-control`,
`corner-container`, `corner-toolbar`, and `corner-pill` roles; the 11 square
rectangles keep their prior implicit geometry. Existing themes that use numeric
`rx` and `ry` attributes retain that legacy path, while mixing the new and old
forms is rejected as ambiguous.

The seventh milestone introduced 15 semantic native integer metric roles. Four
stroke roles, two spacing roles, three title/preview roles, and six control/tab
size roles preserve the exact existing integer geometry while removing
331 repeated literals: 292 `stroke-width` values, 34 explicit part
width/height/margin values, and 5 numeric settings. The optional `metrics`
section is resolved before settings and drawing definitions, but older bundled
or out-of-tree themes may continue using literal numeric values. The reader
resolves setting roles back to the existing decimal-string representation and
part/drawing roles into the existing integer fields, so no public draw-action,
part, settings, or renderer ABI is added for this source slice.

The eighth milestone adds native Material anatomy for determinate progress and
level indicators. An optional `TrackHorzArea` definition paints the complete
control before the `Entire` fill is clipped to the caller's numeric value.
Level fills classify that value into `critical`, `low`, `medium`, and `high`
bands at the existing 25%, 50%, and 75% boundaries, so the generic level-bar
meaning is not flattened into one color. Zero still paints the track; legacy
file themes that define only `Entire` retain their prior fill-only behavior.
These nine new rounded actions reuse the existing shape and metric contracts,
bringing the current definition to 159 rounded rectangles and 346 metric
references (307 strokes, 34 part dimensions/margins, and 5 settings).

The ninth milestone adds native Material anatomy for two controls the reader
already recognized but the theme had not yet defined: the outlined frame
(`ControlType::Frame`/`Border`) and the tree connector net
(`ControlType::ListNet`/`Entire`). The frame is a single outlined container
rectangle—`outline-variant` stroke, `surface-container` fill so it blends into
the dialog it groups, `stroke-thin` width, and the `corner-container` radius—so
it introduces one new rounded rectangle and one `stroke-thin` reference and no
new tokens. The shared renderer now reports a native frame region (bounding and
content equal to the requested rectangle), which is the signal `decoview`
requires before it issues the file-definition `Border` draw. `ListNet` is
declared with a single supported-but-empty `Entire` state: because the renderer
returns success while drawing nothing, VCL's tree view suppresses its own
connector nets, giving the flatter Material tree that native GTK and macOS
themes already produce. Both controls compiled into the exact-source local
build but have not been directly exercised in the accepted UI run.

The tenth milestone closes three disabled-affordance gaps found by auditing
VCL's real native-control draw calls against the definition: cases where a
disabled control tuple VCL genuinely passes collapsed onto a generic state and
lost its meaning. A disabled submenu parent (`MenuPopup`/`SubmenuArrow`,
`ControlState::NONE`) now dims its arrow to `@outline` instead of keeping the
enabled stroke; a disabled but checked toolbar button
(`enabled="false"` + `button-value="true"`) keeps a dimmed `@outline` checked
outline instead of the plain disabled fill; and a disabled tab control keeps its
current page identifiable through `enabled="false" selected="true"` states on
both `tabitem`/`Entire` and `tabitem`/`MenuItem`. All four states reuse existing
tokens, adding four states, three rounded rectangles, one dimmed arrow pair, and
five stroke references with no new token. Three other verified gaps were left out
of this slice because they are design decisions rather than corrections:
emphasizing the keyboard-default push button distinctly from its `action`
siblings (which would restyle every dialog button box), hover feedback on
outlined text/spin fields (the field family intentionally renders its idle state
on hover), and press/hover feedback on scrollbar troughs. This slice compiled
into the exact-source local build, but these state tuples remain visually
unexecuted.

The 684 normalized fractional drawing coordinates remain component-local
literals. They describe proportional glyph and inset geometry rather than
integer metrics; giving individual scalars shared names would obscure the
45 complete coordinate patterns instead of creating reusable primitives.
Typography scaling remains under the typed role contract, and corner radii
remain under the separate shape contract.

The shared renderer also contains source corrections for composite combo and
RTL geometry, toolbar grip regions, slider sizing, definition-backed regions,
and native line/fill cache invalidation. A standalone validator checks token
discipline, the exact shape, metric, and 72-slot style schemas, light/dark
schema parity, unused roles, required control/state coverage,
list/selection/feedback contrast pairs, and native font/geometry-preservation
invariants; dedicated XML-walker, reader, and headless draw C++ coverage plus
negative fixtures are present. The focused required native targets now pass in
Linux and Windows Actions, but broader renderer coverage remains unverified.

This slice is **implemented source, not verified behavior**: required native
targets have compiled and run, but it has not run as a LibreOffice application.
Once a staged compatible build exists, it is intended to be explicitly enabled
with both `VCL_DRAW_WIDGETS_FROM_FILE=1` and
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
| Metric | stroke thickness, fixed control size, title/preview height, and local spacing roles |
| Elevation | level 0–5 expressed through native shadow/surface treatment |
| Spacing | a compact desktop scale with density-aware increments |
| State | hover, focus, pressed, dragged, selected, disabled, read-only, invalid |
| Motion | duration and easing roles, plus an immediate reduced-motion mapping |
| Layout | compact, medium, expanded window classes and platform insets |

Token resolution must incorporate the operating system theme, LibreOffice user
preferences, high-contrast/forced-color requirements, display scale, and the
active density profile. Contrast and legibility outrank brand palette matching.

The current definition contains matched light and dark semantic palettes, an
exact 72-slot style mapping, three native-preserving typography roles, eight
semantic corner roles, and 15 semantic native integer metric roles.
Source selects between them from resolved dark mode; resolved high contrast
takes precedence, restores the captured native style/framework baseline, and
bypasses Material drawing for native or generic fallback. Controls refresh
native-focus suppression when the profile changes so generic fallback can
retain a visible VCL focus indicator. Headless VCL maps an explicit dark
preference because it has no operating-system appearance signal. The accepted
light Start Center run requested this routing, but it does not prove every
control, dark/high-contrast path, or platform backend. The metric layer preserves the existing integer
values and downstream native unit conversions; it does not add density
selection or a new DPI-aware, `dp`, fractional-scale, or comfortable/touch
sizing policy.
Forced-color/platform signal completeness, density, line-height and
letter-spacing typography, density-aware/full radius behavior, elevation, and
motion resolution remain planned.

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

The seventh source milestone centralizes the current values without replacing
their existing downstream native conversions, but it does not satisfy this
density contract. Compact/comfortable profiles and any new DPI, `dp`, zoom, or
input-modality mapping must be implemented and verified separately.

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
