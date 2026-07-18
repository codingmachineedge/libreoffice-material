# 11 — Impress & Draw

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This chapter specifies the two page-canvas applications: the Impress
presentation shell (slide panel, 16:9 canvas card, layouts panel) and the Draw
shell (tool rail, dotted canvas grid, shape property panel), plus the shared
object-selection and manipulation conventions and the presenter/animation
surfaces. Normative inputs are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behavior contract),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, unbuilt), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Every feature is labelled *implemented in definition.xml
(unbuilt)*, *prototype-only*, or *specified here, not yet implemented*.
Interaction behavior described below is existing LibreOffice behavior restated
as the target unless explicitly marked otherwise; the theme changes drawing,
not command semantics.

---

## 11.1 Impress — presentation shell

### Layout & regions

The prototype's Impress body is a three-column, 560 px-tall working area inside
the shared window shell (`width:min(1200px,97vw)`, 42 px title bar, 28 px
status bar). From start to end:

| Region | Size (prototype) | Fill / border tokens | Status |
| --- | --- | --- | --- |
| Slide panel | 172 px fixed width; padding 12 px vertical, 10 px horizontal; 10 px inter-thumbnail gap; vertical scroll | `@surface-container` fill; end border hairline `@outline-variant` (`stroke-thin`) | prototype-only geometry; panel fill/border roles implemented in definition.xml (unbuilt) via `windowbackground` + `fixedline` |
| Canvas region | Remaining flex width; 24 px padding; content centred | `@surface-container-low` workspace fill | prototype-only |
| Slide canvas card | `max-width: 640px`, aspect ratio 16:9; 6 px corner radius; internal padding 44 px top/bottom, 52 px sides; shadow `0 8px 30px rgba(0,0,0,.16)` | `@surface` fill, hairline `@outline-variant` border | prototype-only (document rendering itself is out of chrome scope) |
| Layouts panel | 248 px fixed width; 14 px padding; “Layouts” heading (600 weight, 14 px, 14 px bottom margin); 3-column grid, 8 px gap | `@surface` fill; start border hairline `@outline-variant` | prototype-only |
| Status bar | 28 px; `Slide N of 8 · Default · English (USA)`; right-aligned zoom label and slider | `@surface-container` fill, top hairline `@outline-variant` | prototype-only |

**Slide panel thumbnails.** Each entry is a row of slide number plus preview
card:

- number label: 11 px, weight 500, `@on-surface-variant`, in a 12 px column
  with 20 px top padding so it aligns optically with the card;
- preview card: **120 × 68 px** (≈16:9), `@surface` fill, 5 px radius,
  hairline `@outline-variant` border when unselected;
- selected slide: **2 px `@primary` border** (the `stroke-standard` weight)
  plus a small elevation shadow (`0 2px 10px rgba(0,0,0,.14)`), so selection is
  carried by border weight *and* elevation, not hue alone;
- in-thumbnail title text: 8 px, weight 600, `@on-surface`.

The native counterpart of this panel is a VCL value set/preview list drawn on
`windowbackground`/`BackgroundWindow` (`@surface`, implemented in
definition.xml, unbuilt) with `scrollbar` parts for overflow: `ThumbVert`
`@outline` at rest, `@primary` on hover, `@primary-action-pressed` while
dragged, over `@surface-container` track parts, all at `corner-small` —
implemented in definition.xml (unbuilt). The per-thumbnail selection border and
shadow are specified here, not yet implemented in the native definition.

**Layouts panel cells.** Six layout previews in a 3-column grid; each cell has
a 4:3 aspect ratio, `corner-small` (8 px) radius, and a 24 px
`@on-surface-variant` glyph. Unselected cells: `@surface` fill with hairline
`@outline-variant` border. Selected cell: `@primary-container` fill with a
2 px `@primary` border. This mirrors the `tabitem`/`MenuItem` selected pattern
(`@primary-container` fill, `@primary` stroke) already implemented in
definition.xml (unbuilt); the grid-cell packaging itself is prototype-only.

### Chrome variants

**Classic** (prototype `classicCommand()`):

- menu bar at `--menu` height (30 px compact / 38 px comfortable) with the
  Impress menu set *File, Edit, View, Insert, Format, Slide, Slide Show,
  Tools, Window, Help*; open menus use `menubar`/`MenuItem` states
  (`@primary-container` rollover, `@primary-hover` selected, `corner-container`
  radius — implemented in definition.xml, unbuilt);
- standard toolbar and Impress formatting toolbar, each at `--tb` height
  (38 px / 48 px), on `toolbar`/`Entire` `@surface-container`;
- the formatting row contains a 150 px font-name combo (`Liberation Sans`), a
  54 px size combo (`18`), bold/italic/underline, font colour, three alignment
  toggles, then the shape insertion group (Rectangle, Ellipse, Line, Text Box)
  and **Start from First Slide** (`play_arrow`). Toolbar buttons are 34 × 34 px
  with `corner-small` radius in the prototype; natively they consume
  `toolbar`/`Button` with `corner-toolbar` (18) — implemented in
  definition.xml (unbuilt), including checked (`button-value="true"`:
  `@primary` stroke on `@primary-container`), pressed (`@primary-hover`),
  focused (`@primary` at `stroke-standard`), and the disabled-but-checked state
  (`@outline` stroke on `@disabled-container`).

**Ribbon**: a 38 px tab row on `@surface-container` with the Impress tab set
*File, Home, Insert, Slide Show, Review, View* (active tab: `@surface` fill,
`@primary` text, 2 px `@primary` underline), above a 96 px group strip with
64 × 72 px big buttons, 34 × 34 px small buttons, and 30 px pill chips —
prototype-only; the native notebookbar mapping is specified in
[05 — Navigation](05-navigation.md).

### Key user flows

1. **Navigate slides.** Click a thumbnail (prototype `set:slide:N`) or press
   `Page Up`/`Page Down` in the canvas; the status bar updates to
   `Slide N of 8`. Selection moves the 2 px `@primary` border and shadow to the
   new thumbnail.
2. **New slide.** `Ctrl+M` or *Slide ▸ New Slide* (command catalog entry
   `New Slide — Ctrl+M`). The new thumbnail is inserted after the current one
   and becomes selected.
3. **Apply a layout.** Click a cell in the Layouts panel (prototype
   `set:layout:i`); the cell takes the selected treatment and the canvas
   placeholders rearrange. Keyboard: the grid is a single tab stop; arrow keys
   move between cells, `Space`/`Enter` applies.
4. **Start the show.** `F5` (*Start Slide Show*) or the toolbar
   `play_arrow` button; `Shift+F5` starts from the current slide (existing
   binding restated). See §11.4 for the presenter surface.
5. **Master and transitions.** *View ▸ Master Slide*, *Slide ▸ Transition*,
   *Slide ▸ Animation* — catalogued commands; their dedicated panels are
   specified here, not yet implemented (§11.4).

### Empty, loading and error states

- **New deck:** one title slide; the slide panel shows a single selected
  thumbnail and the Layouts panel is fully populated (layouts never empty).
- **Loading large decks:** thumbnails populate progressively top-down; a
  pending thumbnail renders as the plain `@surface` card with hairline
  `@outline-variant` border and no title text — specified here, not yet
  implemented. No skeleton shimmer: motion must not decorate loading
  (see [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) motion rules).
- **Unrenderable media on a slide:** the placeholder keeps its bounds and
  shows an `@error-container` / `@on-error-container` notice naming the asset
  and a *Relink…* recovery action — specified here, not yet implemented; the
  colour pair is implemented in definition.xml (unbuilt) and validator-checked
  for contrast.

### Density & adaptive width

Native metrics carry no density selection
([`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)); the prototype's browser
density layer gives the target chrome numbers:

| Value | Compact | Comfortable |
| --- | ---: | ---: |
| Toolbar height `--tb` | 38 px | 48 px |
| Menu bar height `--menu` | 30 px | 38 px |
| Menu item height `--item` | 30 px | 40 px |
| Base font `--fs` | 13 px | 14 px |

The slide panel (172 px), layouts panel (248 px), and thumbnail size
(120 × 68 px) are fixed across both densities in the prototype. Adaptive
width (specified here, not yet implemented): in the *medium* window class the
Layouts panel collapses into a sidebar deck toggle; in *compact* the slide
panel narrows to a numbered strip (number + 48 px micro-thumbnail) and the
Layouts deck becomes an overflow dialog. No command disappears: overflow is a
designed state with stable keyboard order.

### Keyboard map

| Key | Action | Scope |
| --- | --- | --- |
| `Ctrl+M` | New slide | anywhere in shell |
| `Page Up` / `Page Down` | Previous / next slide | canvas, slide panel |
| `Home` / `End` | First / last slide | slide panel |
| `Tab` / `Esc` | Enter next placeholder / leave placeholder editing | canvas |
| `F5` / `Shift+F5` | Slide show from first / current slide | anywhere |
| `F4` | Position and Size dialog | object selected |
| `F6` / `Shift+F6` | Cycle panes: slide panel → canvas → layouts panel → status | shell |
| Arrow keys | Move selected object (grid step); with `Alt`, fine step | canvas |
| `Ctrl+M` conflicts, mnemonics | Menu mnemonics per existing `.ui` accelerators | menus |

All bindings are existing LibreOffice bindings restated; the theme adds no new
chords. Every pane must be reachable via `F6` without pointer use.

### Accessibility notes

- The slide panel exposes a list of slides with accessible name
  “Slide *n* of *m*: *title*” and `SELECTED`/`FOCUSED` states through the
  existing VCL a11y hierarchy (restated, not altered by the theme).
- Thumbnail selection is never colour-only: 2 px border weight plus elevation
  differ from the 1 px hairline rest state; the focused thumbnail additionally
  carries the shared focus treatment (`@primary` at `stroke-standard`,
  `corner-focus`), specified here, not yet implemented for this panel.
- Layout cells expose name (“Title, Content”, etc.) and `SELECTED`; the glyph
  plus fill change carries state redundantly.
- Zoom slider in the status bar must publish value (%) and support arrow-key
  adjustment; the native `slider` control (see §11.2) already defines a
  focused thumb state — implemented in definition.xml (unbuilt).
- No contrast measurement is claimed anywhere in this chapter; pairs such as
  `@error-container`/`@on-error-container` are checked by the standalone
  validator as source invariants only.

### Verification checkpoints

Per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) (smoke
scenario “create/present/close one Impress deck”):

1. Launch the fork build with `VCL_DRAW_WIDGETS_FROM_FILE=1` and
   `VCL_FILE_WIDGET_THEME=material`; capture the Impress shell at 1200 px
   width, light and dark, compact density.
2. Checkpoint: slide panel with slides 1–3 present; selected thumbnail shows
   the 2 px selection border; unselected thumbnails show hairline borders.
3. Checkpoint: toolbar checked/unchecked/disabled/disabled-checked states on
   the alignment toggles (`toolbar`/`Button` incl. `button-value` states).
4. Keyboard-only run: `F6` cycle, `Ctrl+M`, `Page Down`, layout apply via
   arrows + `Enter`; record focus visibility at each stop.
5. RTL locale run: mirrored panel order (see RTL rules below) captured at the
   same checkpoints.
6. Zero captures exist today; the registry stays empty until these runs exist.

---

## 11.2 Draw — drawing shell

### Layout & regions

| Region | Size (prototype) | Fill / border tokens | Status |
| --- | --- | --- | --- |
| Tool rail | 48 px fixed width; buttons 38 × 38 px; 4 px gap; 10 px top padding | `@surface-container` fill; end hairline `@outline-variant` | prototype-only geometry; rail fill = `toolbar`/`DrawBackgroundVert`, implemented in definition.xml (unbuilt) |
| Canvas workspace | Remaining flex; 24 px padding | `@surface-container-low` with a dotted grid: 1 px `@outline-variant` dots on a **22 px** square cell (`radial-gradient` in the prototype) | prototype-only |
| Page card | `max-width: 620px`, aspect ratio 4:3; square corners; shadow `0 8px 30px rgba(0,0,0,.14)` | `@surface` fill, hairline `@outline-variant` border | prototype-only |
| Property panel | 248 px fixed width; 14 px padding | `@surface` fill; start hairline `@outline-variant` | prototype-only |
| Status bar | 28 px; `Page 1 of 1 · 0 objects selected` + zoom | `@surface-container` | prototype-only |

**Tool rail.** Seven tools in the prototype: Select (`near_me`, active by
default), Move, Rectangle, Ellipse, Line, Text, Curve. Buttons are
38 × 38 px, `corner-small` (8 px) radius, 22 px glyphs; the active tool uses
`@primary-container` fill with `@on-primary-container` glyph, inactive tools
are transparent with `@on-surface-variant` glyphs. Natively the rail is a
docked vertical toolbar: background `toolbar`/`DrawBackgroundVert`
(`@surface-container`), drag grip `ThumbVert` (`@outline-variant`,
`corner-indicator`), and buttons `toolbar`/`Button` with `corner-toolbar` — the
checked tool maps to `button-value="true"` (`@primary` `stroke-thin` outline on
`@primary-container`), hover to `rollover` (`@primary-container`), press to
`pressed` (`@primary-hover`), keyboard focus to `focused` (`@primary` at
`stroke-standard`), and a disabled-but-checked tool keeps `@outline` on
`@disabled-container`. All of these states are implemented in definition.xml
(unbuilt). The prototype's 8 px cell radius versus the native
`corner-toolbar` 18 px is a deliberate divergence to resolve in the
prototype's favour only if a later definition slice changes the role; until
then the native contract (18) is normative for VCL toolbars.

**Property panel (Fill / Line).** From the prototype:

- “Properties” heading: 600 weight, 14 px, 14 px bottom margin;
- section labels (“FILL”, “LINE”): 11 px, weight 700, 0.06 em letter-spacing,
  uppercase, `@on-surface-variant`, 8 px bottom margin;
- fill row: a 40 × 36 px swatch (`corner-small`, current fill
  `@primary-container`, hairline `@outline-variant` border) beside a 36 px-high
  outlined “Color” drop-down field (`@outline` hairline, `corner-small`,
  13 px text). Natively the drop-down is the `listbox` control
  (`Entire`/`ButtonDown`/`ListboxWindow` — implemented in definition.xml,
  unbuilt; see [06 — Containers](06-containers.md));
- line-width row: 40 px tall with a horizontal slider — 4 px track
  (the `stroke-track` metric), filled portion `@primary`, remainder
  `@outline-variant`, and in the prototype an 18 px round `@primary` thumb at
  40 %.

The native slider is implemented in definition.xml (unbuilt) with different,
normative thumb anatomy: `slider`/`Button` is **28 × 28 px**
(`size-compact-control`) with `corner-control` (10) radius at rest, growing to
`corner-container` (12) on hover/press, `@primary` fill,
`@primary-action-hover`/`@primary-action-pressed` feedback, a focused state of
`@on-surface` ring at `stroke-standard` over `@primary` fill, and a disabled
thumb of `@outline-variant` fill (its `@outline` stroke is declared at
`stroke-none`, so no stroke is visible — see 07 §7.3). Track parts:
`TrackHorzLeft` `@primary` and `TrackHorzRight` `@outline-variant`, both at
`stroke-track` (4); disabled tracks drop to `@outline-variant` /
`@disabled-container`. The prototype's circular 18 px thumb is prototype-only
presentation; VCL sliders follow the definition.

### Chrome variants

Classic menus: *File, Edit, View, Insert, Format, Page, Shape, Tools, Window,
Help*. The Draw formatting toolbar carries Select, Rectangle, Ellipse, Basic
Shapes, Line, Curve, Insert Text Box, then Fill Color, Line Width, Line Color,
then Flip and Rotate. Ribbon tabs: *File, Home, Insert, Page, Review, View*.
Both variants share the token treatment described for Impress in §11.1;
duplicated tool commands between rail and toolbar remain synchronized checked
state (one command, two `toolbar`/`Button` instances).

### Key user flows

1. **Draw a shape.** Activate a tool (click, or toolbar keyboard navigation);
   the rail button takes the checked treatment; drag on the canvas creates the
   object, which becomes selected (§11.3). Status bar count updates from
   `0 objects selected`.
2. **Edit fill/line.** With an object selected, the property panel binds to
   it; choosing a fill colour or dragging the width slider applies live.
   `F4` opens Position and Size for numeric geometry (catalogued command).
3. **Arrange/align.** *Shape ▸ Arrange*, *Format ▸ Align* (catalogued);
   connectors and layers (*Insert ▸ Layer*) follow existing behavior restated.
4. **Escape hatch.** `Esc` always returns to the Select tool and clears any
   in-progress drag — specified here, not yet implemented as a guarantee.

### Empty, loading and error states

- **Empty page:** dotted grid plus the empty page card; the property panel
  shows the page's own fill/line values rather than hiding — specified here,
  not yet implemented. Status reads `0 objects selected` (prototype).
- **No selection:** panel controls remain visible but disabled, using the
  definition's disabled states (`@disabled-container` fills, `@outline-variant`
  strokes) so layout does not jump — implemented in definition.xml for the
  controls (unbuilt); the panel policy is specified here.
- **Missing linked image:** placeholder bounds retained with an
  `@error-container`/`@on-error-container` notice and *Relink…* action —
  specified here, not yet implemented.

### Density & adaptive width

Chrome heights follow the shared density table in §11.1. The 48 px rail and
248 px property panel are fixed in both prototype densities; the rail's
38 × 38 px buttons sit between the metric roles `size-standard-control` (36)
and `height-tab` (40) and are prototype-only until a native rail slice picks
one. Adaptive width (specified here, not yet implemented): *medium* collapses
the property panel to a sidebar toggle; *compact* additionally overflows rail
tools past the first six into a bottom-of-rail overflow menu with stable
keyboard order.

### Keyboard map

| Key | Action |
| --- | --- |
| `Esc` | Deselect / abort drag / return to Select tool |
| `Tab` / `Shift+Tab` | Cycle object selection on the page |
| Arrow keys | Move selected object; `Alt`+arrows fine step; `Shift`+drag constrains |
| `F4` | Position and Size dialog |
| `F6` / `Shift+F6` | Cycle panes: rail → canvas → property panel → status |
| `Ctrl+Shift+G` / `Ctrl+Alt+Shift+G` | Group / ungroup (existing bindings restated) |
| `+`/`-` on numeric fields, arrows on slider | Adjust width slider by one step; `Home`/`End` min/max |

### Accessibility notes

- Rail tools expose role *toggle button*, name (tooltip text: “Select”,
  “Rectangle”, …), and pressed state; checked state is carried by outline plus
  fill, not hue alone (`button-value` outline at `stroke-thin`).
- The canvas exposes the existing Draw a11y object tree (shapes with
  name/description/bounds); the theme does not alter it.
- The width slider exposes value/min/max and the definition's focused-thumb
  ring (`@on-surface` at `stroke-standard`) provides a non-colour focus cue —
  implemented in definition.xml (unbuilt).
- The dotted grid is decorative: 1 px `@outline-variant` dots must never be
  load-bearing for alignment information exposed to assistive tech (snap
  values are announced via the status bar and Position and Size dialog).

### Verification checkpoints

1. Capture the Draw shell light/dark/compact/comfortable at 1200 px; verify
   rail `DrawBackgroundVert` fill, grip, and checked-tool outline against
   `toolbar` parts in definition.xml.
2. Checkpoint: slider thumb at rest (28 px, `corner-control`), hover
   (`corner-container`, `@primary-action-hover`), focused ring, and disabled —
   the four `slider`/`Button` states plus both horizontal track parts.
3. Checkpoint: property panel disabled set with `0 objects selected`, then
   enabled set with one selected object; status-bar text matches.
4. Keyboard-only run: tool activation, shape creation via keyboard placement,
   `Tab` cycling, `F4`, `Esc` recovery.
5. RTL capture per the shared matrix (below); dotted-grid rendering must be
   verified for moiré/scale artefacts at 125 % and 200 % display scale.

---

## 11.3 Object selection & manipulation conventions (shared)

These conventions apply to Impress and Draw canvases identically (and to
embedded draw objects suite-wide).

- **Selected object:** a 2 px `@primary` outline (`stroke-standard`) drawn on
  the object bounds — shown in the prototype's “Concept” object
  (`@primary-container` fill, 2 px `@primary` border). Prototype-only; the
  canvas overlay is application drawing, not a `definition.xml` control.
- **Unselected object strokes** belong to the document, not the theme; the
  prototype's `@outline` 2 px circle (“Audience”) and `@warning-container`
  card (“Launch plan”) are sample content only.
- **Selection handles:** eight square handles, `size-selection-control` / 3
  (8 px) square, `@surface` fill with `@primary` stroke at `stroke-standard`,
  `corner-checkbox` (3) radius; rotation mode swaps to round handles with a
  distinct pivot marker — specified here, not yet implemented.
- **Marquee (rubber-band):** `stroke-thin` `@primary` dashed rectangle with no
  fill; the palette deliberately defines no translucent overlay role, so a
  tinted marquee interior is out of contract until a scrim role exists —
  specified here, not yet implemented.
- **State redundancy:** selection is always outline + handles (+ status-bar
  count in Draw), never a hue shift alone; focus-visible on the canvas object
  follows the selection outline, and keyboard `Tab` order is document z-order.
- **Snapping feedback:** momentary `@primary` guide lines at `stroke-thin`;
  reduced-motion mode suppresses any animated snapping easing — specified
  here, not yet implemented.

## 11.4 Presenter, animation and transition surfaces

The prototype has no coverage of the presenter console, custom-animation deck,
or slide-transition deck; the command catalog lists them (*Custom Animation —
Slide ▸ Animation*, *Slide Transition — Slide ▸ Transition*, *Presenter
Console — Slide Show ▸ Presenter Console*, *Start Slide Show — F5*). All three
surfaces are therefore **specified here, not yet implemented**:

- **Presenter console:** inverse-themed (`@inverse-surface` chrome with
  `@inverse-on-surface` text, matching the tooltip/snackbar family) so the
  presenter view reads as distinct chrome; current-slide, next-slide and notes
  panes; timer as `label`-role typography; all controls reachable by keyboard
  and exposed with names/states. No motion beyond slide change itself.
- **Animation deck:** a sidebar list of effects using standard list rows
  (`space-list-entry` = 12 margin) with per-row reorder controls; preview is
  user-invoked, never autoplaying, and honours reduced motion.
- **Transition deck:** a grid of transition cells reusing the Layouts-panel
  cell pattern (§11.1); “None” is always the first, fully supported option.

Until a native slice and prototype coverage exist, no token, geometry, or
capture claims are made for these surfaces beyond the mappings above.

## RTL & localization (both shells)

- Horizontal order mirrors: Impress becomes layouts panel → canvas → slide
  panel; Draw becomes property panel → canvas → tool rail. Panel hairlines
  swap edges; `F6` order follows visual order.
- Slide numbers and status text localize with existing number formatting; the
  8 px thumbnail titles and long localized layout names truncate with
  ellipsis and expose full names via tooltip/a11y name.
- The width slider mirrors direction in RTL (filled `TrackHorzRight` side);
  the definition's separate left/right track parts make this a pure part-swap.
- Directional tool glyphs mirror only when semantically directional
  (per [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) iconography rules):
  Rotate/Flip glyphs mirror; Ellipse/Rectangle do not.

## Platform notes (Windows-first)

Windows is the first verification target
([`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) off-screen
workflow); Windows printer graphics are excluded from the file-widget
initialization path, so printed slide/page output never routes through
Material chrome drawing. Resolved high contrast bypasses Material drawing
entirely and restores the captured native baseline — the dotted Draw grid and
selection conventions must remain legible under that fallback, which is a
verification obligation, not a current result. No other deliberate platform
divergence is specified for these two shells.
