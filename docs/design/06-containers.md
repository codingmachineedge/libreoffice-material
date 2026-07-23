# 06 — Containers & data display

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md). The native definition/dispatch tests have
> compiled and executed, and the corrected `fbba560e2` extracted runtime ran a
> scoped Start Center smoke with the Material opt-in set. The individual
> container widgets, state tuples, and pixels specified here remain unverified.

This chapter specifies the container and data-display family: lists and list
items, trees, tables and data grids (the Calc grid, Base tables and object
cards), outlined frames, scrollbars, document cards, and side panels. Normative
inputs are [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behavior
contract), [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, compiled at commit 577059e274; surface state unverified), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Implementation status is labelled per feature as *implemented
in definition.xml (compiled at commit 577059e274; surface state unverified)*, *prototype-only*, or *specified here, not yet
implemented*.

---

## 6.1 Lists and list items

### Anatomy & tokens

A list is a vertical stack of single-selection or multi-selection entries inside
an outlined container. The dropped-down list of a combo/list box shares this
anatomy through the `listbox` control.

| Region | Token use | Status |
| --- | --- | --- |
| Closed list box container | `@outline` stroke, `@surface` fill, `stroke-thin`, `corner-container` (`listbox`/`Entire`) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Drop-down window | `@outline-variant` stroke, `@surface` fill, `stroke-thin`, `corner-container` (`listbox`/`ListboxWindow`) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Drop arrow button | `size-standard-control` (36) square; `@primary-container` fill, `corner-container`, chevron `@on-surface-variant` at `stroke-standard` (`listbox`/`ButtonDown`) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Entry margin | `space-list-entry` (12) via `listBoxEntryMargin` setting | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Entry preview (colour/line lists) | `size-list-preview` (18 × 18 logic units) via `listBoxPreviewDefaultLogicWidth/Height` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Selected-entry surface | `listBoxWindowHighlightColor` → `@primary-container`; text `listBoxWindowHighlightTextColor` → `@on-primary-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Standalone list rows (gallery reference) | 44 px row, 14 px horizontal padding, 12 px icon gap, trailing `check` glyph on the selected row | prototype-only |

The prototype's gallery list renders rows at `height:44px; padding:0 14px` with
a `@primary-container` selected row, `@outline-variant` hairline separators, and
the whole list clipped by a `corner-container` (12 px) outline — the target
appearance for `.ui` list widgets.

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Enabled (container) | Outlined field on surface | `@outline` / `@surface` / `stroke-thin` / `corner-container` | definition.xml `listbox`/`Entire` |
| Disabled (container) | Dimmed outline, dim fill | `@outline-variant` / `@disabled-container` | definition.xml `listbox`/`Entire` `enabled="false"` |
| Drop-down open | Elevated window, hairline border | `@outline-variant` / `@surface` | definition.xml `ListboxWindow` |
| Entry hover | Tonal wash | `@primary-container` text `@on-primary-container` (shared highlight slots) | definition.xml `<style>` |
| Entry selected | Tonal container + selection text | `listBoxWindowHighlightColor`/`-TextColor` | definition.xml `<style>` |
| Arrow hover / pressed | Fill steps to `@primary-hover` / `@primary-pressed`, chevron to `@on-surface` | definition.xml `ButtonDown` `rollover`/`pressed` |
| Arrow disabled | `@disabled-container` fill, `@outline` chevron | definition.xml `ButtonDown` `enabled="false"` |
| Focused (whole control) | Perimeter focus at 4 % inset | `@primary` at `stroke-standard` (`listbox`/`Focus`) | definition.xml |

### Interaction

Pointer: click opens the drop-down; click selects and closes;
wheel scrolls the open list. Keyboard: `Alt+Down`/`Alt+Up` open/close,
`Up`/`Down` move the selection, `Home`/`End` jump, type-ahead selects by prefix,
`Enter` commits, `Esc` cancels. Mnemonics activate the associated label's
buddy control. Screen readers receive the existing VCL list/combo roles; the
theme changes drawing only (interaction behavior: existing VCL, restated here —
not altered by this theme).

### Accessibility

Role/name/state exposure is unchanged VCL (`LISTBOX`/`LIST_ITEM` with
`SELECTED`, `FOCUSED`, `EXPANDED` where applicable). The focus indicator is the
definition-backed `Focus` part (`@primary`, `stroke-standard`); the standalone
validator's list/selection contrast-pair checks cover
`listBoxWindowHighlightColor` against its text slot. Selection is carried by
both fill and the trailing check glyph in reference lists — never colour alone.

### Density

Native metrics carry no density selection ([`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)).
Prototype targets: menu-style list items `--item` 30 px compact / 40 px
comfortable; base font 13 px / 14 px; the gallery's document list fixes 44 px
rows in comfortable. Entry margin remains `space-list-entry` = 12 in both
profiles until a native density layer exists.

### RTL & localization

The drop arrow docks to the inline-end (left in RTL); entry padding and icon
gaps mirror. Long labels ellipsize at the inline-end while tooltips expose the
full text; type-ahead follows locale collation. Composite combo/RTL geometry
corrections compiled in the exact-source build but remain surface-unverified.

### Platform notes

Windows-first; active only with `VCL_DRAW_WIDGETS_FROM_FILE=1` and
`VCL_FILE_WIDGET_THEME=material`. Resolved high contrast restores the captured
native `StyleSettings` baseline and bypasses Material drawing entirely. Windows
printer graphics are excluded from the file-widget path.

### Verification hooks

Per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md): headless draw
coverage for `listbox` definition/state command generation has executed in the
required C++ target; no corresponding widget/state pixel comparison or
application-surface capture exists. Screenshot checkpoints: closed/open list
box in light/dark; entry hover, selected, keyboard-focused; disabled container —
captured under a run id `YYYYMMDD-HHMMSS-<commit>-win` with manifest hashes.

### Application: Extension manager list & dependency tree

The Extension manager ([08-dialogs.md](08-dialogs.md) §8.9) reuses this family
with no new anatomy. The installed-extension list is the §6.1 list/list-item
container pattern — one row per extension carrying an icon, name, publisher,
version, status, and an inline action — clipped by the same `corner-container`
outline. The unfulfilled-dependency view is the §6.2 tree pattern with the
connector net suppressed (the empty `listnet`/`Entire` state), and the *Display
Extensions* group is an outlined §6.4 `frame`/`Border`. Only the
container/tree/frame anatomy is design-pinned here: the custom-drawn
per-extension list-item `Paint`
(`desktop/source/deployment/gui/dp_gui_extlistbox.cxx`) is deferred (build-only),
so no list-item pixels are claimed and `runtime_verified` stays false.

---

## 6.2 Trees

### Anatomy & tokens

| Region | Token use | Status |
| --- | --- | --- |
| Expander (disclosure node) | `size-tree-node` (20 × 20); chevron pair at `stroke-standard` in `@on-surface-variant` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Expander focus plate | `@primary` stroke, `@surface` fill, `stroke-thin`, `corner-focus` (6) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Connector net | **None.** `listnet`/`Entire` declares one supported-but-empty `enabled="true"` state; the renderer reports success while drawing nothing, so VCL suppresses its dotted connector nets | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Row selection | `highlightColor` → `@primary-container`, `highlightTextColor` → `@on-primary-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Row background | `@surface` (window) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

The net-less decision is milestone 9: the flat, indentation-only tree that
native GTK and macOS themes already produce, achieved without a VCL behavior
change — the empty `Entire` state is the entire mechanism.

Chevron geometry (fractions of the 20 px node): collapsed points inline-end,
`(0.38, 0.28) → (0.62, 0.50) → (0.38, 0.72)`; expanded points down,
`(0.28, 0.38) → (0.50, 0.62) → (0.72, 0.38)`.

### States

| State | Expander treatment | Tokens |
| --- | --- | --- |
| Enabled, collapsed | End-pointing chevron | `@on-surface-variant`, `stroke-standard` |
| Enabled, expanded (`button-value="true"`) | Down chevron | `@on-surface-variant`, `stroke-standard` |
| Hover (± expanded) | Chevron recolours | `@primary` |
| Focused (± expanded) | Rounded plate + primary chevron | `@primary` stroke / `@surface` fill / `stroke-thin` / `corner-focus` |
| Disabled (± expanded) | Dimmed chevron | `@outline-variant` |

All eight expander states are implemented in definition.xml (compiled at commit 577059e274; surface state unverified). Row
hover/selection colours resolve from the shared `<style>` slots above.

### Interaction

Pointer: click the expander toggles; double-click a row toggles or activates.
Keyboard: `Right` expands (or moves to first child), `Left` collapses (or moves
to parent), `+`/`-`/`*` expand, collapse, expand-all, arrows navigate,
type-ahead selects. (Existing VCL behavior, restated — the theme is
drawing-only.) Screen readers get `TREE`/`TREE_ITEM` with
`EXPANDED`/`COLLAPSED` state changes fired on toggle.

### Accessibility

Expansion is conveyed by chevron direction plus the exposed
`EXPANDED`/`COLLAPSED` accessible state, not colour. The focused expander has a
dedicated visible plate (`corner-focus`) distinct from row selection. Removing
the connector net removes no information: hierarchy remains exposed through
indentation and accessible parent/child relations. Chevron contrast
(`@on-surface-variant` `#49454F` on `#FFFBFE` light) must satisfy the ≥ 3:1
non-text minimum; the disabled `@outline-variant` state is exempt as
disabled affordance.

### Density

The node stays `size-tree-node` = 20 in both profiles (native metrics are
density-free). Prototype row heights follow `--item`: 30 px compact, 40 px
comfortable. Indent step: one node width (20 px) per level — specified here,
not yet implemented.

### RTL & localization

Collapsed chevrons mirror to point inline-start-ward in RTL; the expanded
(down) chevron does not mirror. Indentation mirrors with the writing direction.
Long node labels ellipsize inline-end; full text via tooltip and the
accessible name.

### Platform notes

Suppressing the net matches GTK/macOS platform themes; Windows' classic dotted
net is deliberately dropped for Material. High contrast bypasses Material and
restores the native baseline, including whatever net the fallback renderer
draws — this difference is intentional and documented.

### Verification hooks

Headless checks: `listnode` state coverage (8 states) and a `listnet`
draws-nothing assertion (success + empty command list) have executed in the
required definition/state C++ target. They assert generated commands, not
rendered pixels. Build-time checkpoints: Options dialog tree and Navigator
captured light/dark; keyboard expand/collapse sequence (`Right`, `Left`, `*`)
screenshotted at each step; RTL locale capture showing mirrored chevrons and
indentation.

---

## 6.3 Tables & data grids

### Anatomy & tokens

Three grid surfaces share one language: sortable column headers, the Calc cell
grid, and Base's data tables and object cards.

**Column headers** (`listheader`, used by sortable list/table views):

| Region | Token use | Status |
| --- | --- | --- |
| Header button | `@outline-variant` stroke, `@surface-container` fill, `stroke-thin`, `corner-small` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Sort arrow (`extra="up"`/`extra="down"`) | Chevron at `stroke-standard` in `@on-surface-variant` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

**Calc grid** (prototype-only; region metrics from `site/prototype.html`):

| Region | Value |
| --- | --- |
| Column header row | 26 px tall; `@surface-container` fill, `@on-surface-variant` 12 px medium labels, centred |
| Row header column | 44 px wide, cell height `--row`; same colours |
| Sheet-corner cell | 44 × 26 px |
| Cell | width 76 px compact / 92 px comfortable; height `--row` (26/32); padding 0 8 px; 13 px text `@on-surface` |
| Gridlines | `--bw` (1 px; 2 px high-contrast) `@outline-variant`, right + bottom per cell |
| Active cell | inset selection ring `inset 0 0 0 2px` `@primary` (maps to `stroke-standard`), `@surface` fill |
| Headers of active row/column | `@primary-container` fill, `@on-primary-container` text |
| Numeric alignment | values matching `/^[0-9(]/` right-align (`(` covers negative accounting format); text left-aligns |
| Sheet-tab strip | 34 px bar on `@surface-container`; tabs 26 px, padding 0 14 px, top radius 8 px (`corner-small`) |

**Base data table** (prototype-only):

| Region | Value |
| --- | --- |
| Table container | `@outline-variant` border, `corner-container` (12) radius, clipped corners |
| Header row | `@surface-container` fill; cells padding 10 × 14 px; 12 px semibold `@on-surface-variant` |
| Data rows | padding 10 × 14 px; 13 px `@on-surface`; hairline `@outline-variant` separators, none after the last row |
| Striped rows | odd rows fill `@surface-container-low` — the native `alternatingRowColor` slot resolves to the same role (implemented in definition.xml, compiled at commit 577059e274; surface state unverified) |
| Object cards ("table cards") | grid `minmax(150px, 1fr)`, 12 px gap; card: `@surface` fill, `@outline-variant` border, `corner-container` radius, padding 18 × 12 px; 44 px icon tile on `@primary-container` with `corner-container`; hover: border `@primary`, fill `@primary-container` |

### States

| State | Treatment | Tokens | Source |
| --- | --- | --- | --- |
| Header enabled | Contained button | `@surface-container` / `@outline-variant` / `corner-small` | definition.xml `listheader`/`Button` |
| Header hover | Tonal fill | `@primary-container` | definition.xml `rollover="true"` |
| Header pressed | Primary edge + tonal press | `@primary` stroke, `@primary-hover` fill | definition.xml `pressed="true"` |
| Sorted asc/desc | Up/down chevron | `Arrow` `extra="up"`/`"down"` | definition.xml |
| Cell selected (active) | Inset 2 px ring, no fill change beyond `@surface` | `@primary` ring | prototype-only |
| Range selection | `@primary-container` wash with `@on-primary-container` text (shared `highlightColor` slots) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Row stripe | `@surface-container-low` | definition.xml `alternatingRowColor` |
| Disabled grid | Follows `deactiveColor` → `@disabled-container`, text `@outline` | definition.xml `<style>` |

### Interaction

Calc keyboard (existing behavior, restated): arrows move the active cell;
`Ctrl+Arrow` jumps to data edges; `Tab`/`Shift+Tab` and `Enter`/`Shift+Enter`
advance across/down the range; `Ctrl+Space` selects the column, `Shift+Space`
the row; typing enters edit mode; `F2` toggles edit; `Esc` cancels. Header
click sorts (list views) or selects the column/row (Calc); pointer drag extends
ranges. Screen readers use the existing table/cell interfaces with
row/column indices and selection state.

### Accessibility

The active-cell ring is an inset (never clipped by neighbouring gridlines) and
must remain ≥ 3:1 against both `@surface` and `@surface-container`
(`#6750A4` on `#FFFBFE` passes). Sort order is conveyed by the arrow glyph plus
the accessible sorted state, not colour. Striped rows are a scanning aid only —
`@surface-container-low` against `@surface` is deliberately sub-3:1 and carries
no meaning. Header text at 12 px medium keeps ≥ 4.5:1
(`@on-surface-variant` on `@surface-container`).

### Density

Compact: rows 26 px, columns 76 px, 13 px type. Comfortable: rows 32 px,
columns 92 px, 14 px type. Header row stays 26 px and row-header width stays
44 px in both profiles (prototype values). Native density selection does not
exist yet; these are prototype presentation metrics.

### RTL & localization

RTL sheets mirror: row headers dock to the right, column order runs
right-to-left, and the active-cell ring is unaffected (symmetric). Sort arrows
do not mirror (vertical semantics). Numeric right-alignment is a data-type
rule, not a direction rule: numbers stay end-aligned relative to the cell in
both directions per existing Calc behavior. Locale-dependent digits and
separators come from the document locale, not the UI locale.

### Platform notes

The Calc document canvas is application drawing, not a `definition.xml`
control: gridlines, stripes, and the selection ring resolve through
`StyleSettings` slots (`alternatingRowColor`, `highlightColor`,
`deactiveColor`) that the Material profile populates. Only `listheader` and the
scrollbars around the grid are file-definition controls. Printer output is
excluded from the file-widget path by design.

### Verification hooks

Headless: validator contrast pairs for highlight and alternating-row slots;
`listheader` definition/state draw-command tests have executed, but no pixel
comparison exists. Build checkpoints: Calc smoke
scenario ("enter/formula/save/close one Calc sheet") captured with an active
cell, a range selection, and a sorted list header; compact vs comfortable
captures of the same sheet; RTL locale sheet capture.

---

## 6.4 Outlined frames (Frame/Border)

### Anatomy & tokens

The frame is the milestone 9 group container: a single outlined rectangle
behind a labelled cluster of dialog controls.

| Region | Token use | Status |
| --- | --- | --- |
| Container rectangle | `@outline-variant` stroke, `@surface-container` fill, `stroke-thin` width, `corner-container` (12) radius (`frame`/`Border`, `enabled="true"`) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Group label | `groupTextColor` → `@on-surface-variant`; `label` type role (100 %, medium minimum weight) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Horizontal/vertical rules | `fixedline` separators: `@outline-variant` at `stroke-thin` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

The `@surface-container` fill matches `dialogColor`, so the frame blends into
the dialog it groups — one hairline of structure, no tonal box-in-box. The
shared renderer reports the requested rectangle as the frame's outer bounding
region and reports a content region inset by 2 px on every edge. The inset
matches `decoview`'s generic `DrawFrameStyle::Group` fallback geometry; the
successful native-region result is the signal `decoview` requires before
issuing the file-definition `Border` draw. The control adds exactly one rounded
rectangle and one `stroke-thin` reference; no new tokens.

### States

| State | Treatment | Tokens |
| --- | --- | --- |
| Enabled | Hairline rounded outline, dialog-matching fill | `@outline-variant` / `@surface-container` / `stroke-thin` / `corner-container` |
| Disabled | No dedicated state; child controls carry their own disabled affordances | — |

A single `enabled="true"` state is the entire contract; frames are
non-interactive.

### Interaction

None. Frames take no pointer or keyboard input and never receive focus. The
frame label's mnemonic (where present in `.ui` files) moves focus to the first
child control — existing VCL behavior.

### Accessibility

Exposed as a grouping role whose accessible name is the frame label; children
report it as their labelled-by context. Because the fill matches the dialog,
grouping must never be carried by the outline alone at the semantic level — the
accessible hierarchy carries it. Outline contrast is decorative
(`@outline-variant` is sub-3:1 by design); this is acceptable because the
border conveys no state.

### Density

No intrinsic metrics beyond `stroke-thin` and `corner-container`; interior
padding is owned by `.ui` layout. Specified target: 12 px minimum interior
padding so content clears the 12 px corner radius — specified here, not yet
implemented.

### RTL & localization

The rectangle is symmetric; only the label position mirrors (inline-start).
Long labels ellipsize rather than widening the frame.

### Platform notes

Replaces the native Windows etched group box under the Material theme flags.
High contrast restores the platform group-box rendering (native baseline
bypass).

### Verification hooks

Headless: frame-region reporting (requested outer bounding rectangle plus a
2 px inset content rectangle) and the `Border` draw command are covered by
executed C++ assertions; no rendered-pixel comparison exists. Build checkpoint:
shared Options
dialog capture showing frames in light/dark; a high-contrast capture proving
native fallback.

---

## 6.5 Scrollbars

### Anatomy & tokens

Minimal-trough, no-stepper scrollbars in a 12 px gutter (prototype
`.lo-scroll::-webkit-scrollbar{width:12px;height:12px}`).

| Region | Token use | Status |
| --- | --- | --- |
| Thumb | `@outline` fill, `corner-small` (8) radius; drawn inset within the gutter (fractions 0.2–0.8 across the minor axis at rest) | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Trough (track quarters) | `@surface-container` fill, `corner-small` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Stepper buttons (`ButtonUp/Down/Left/Right`) | Declared with supported-but-empty states — the renderer succeeds while drawing nothing, so no arrows appear | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Prototype trough | Transparent track; thumb `@outline` with 3 px transparent inset border (visible bar ≈ 6 px), 8 px radius | prototype-only |

The prototype's transparent trough versus the native `@surface-container`
trough is a known, deliberate divergence: over app chrome the trough reads as
the surrounding `@surface-container` either way.

### States

| State | Thumb treatment | Minor-axis inset (native fractions) | Tokens |
| --- | --- | --- | --- |
| Enabled | Rest width | 0.20 – 0.80 (60 %) | `@outline` |
| Hover | Grows | 0.15 – 0.85 (70 %) | `@primary` |
| Pressed (drag) | Widest | 0.12 – 0.88 (76 %) | `@primary-action-pressed` |
| Disabled | Narrow, dim | 0.25 – 0.75 (50 %) | `@outline-variant` |

All four thumb states exist for both `ThumbHorz` and `ThumbVert` —
implemented in definition.xml (compiled at commit 577059e274; surface state unverified). Trough hover/press feedback was
deliberately excluded from milestone 10 as an open design decision, so the
trough is state-invariant in the current contract.

### Interaction

Pointer: drag the thumb; click the trough pages toward the pointer; wheel and
precision-touchpad gestures scroll the view. There are no stepper buttons to
click — line-scroll remains available via wheel and keyboard
(`Up`/`Down`/`PageUp`/`PageDown` act on the scrolled view, not the bar).
Scrollbars themselves are not tab stops (existing VCL behavior).

### Accessibility

Exposed as a scrollbar role with orientation and value (existing VCL). Hover
and pressed states change both colour and thumb width, so state is not
colour-only. The rest thumb (`@outline` `#79747E` on `#FFFBFE`) exceeds 3:1;
the disabled thumb is intentionally sub-contrast. Because the gutter is only
12 px, the effective pointer target for the thumb is the full gutter width —
hit-area predictability may not vary even though the drawn thumb grows.

### Density

12 px gutter in both density profiles (prototype); the native definition
expresses thumb size fractionally, so it tracks whatever gutter VCL allocates.
No comfortable-mode widening is currently specified.

### RTL & localization

Vertical scrollbars dock to the inline-end (left edge in RTL interfaces and
RTL Calc sheets). Horizontal thumbs and troughs are symmetric; no glyph
mirroring is involved since steppers are suppressed.

### Platform notes

Replaces Windows' arrow-stepper scrollbars under the Material flags — the most
visible deliberate divergence from platform convention in this family, aligned
with the overlay-style bars of modern Windows apps while remaining a permanent
(non-overlay, non-fading) bar. High contrast restores native scrollbars with
steppers.

### Verification hooks

Headless: scrollbar definition/state draw-command tests, including the empty
stepper states (success + no drawing), have executed; no rendered-pixel
comparison exists. Build checkpoints: Writer
document scrolled mid-way, captures at rest/hover/drag in light and dark;
disabled scrollbar in a short document; RTL capture showing the vertical bar on
the left.

---

## 6.6 Cards (Start Center document cards)

### Anatomy & tokens

The Start Center's Recent Documents and Templates grids are card grids
(prototype-only; region metrics from `site/prototype.html`):

| Region | Value |
| --- | --- |
| Grid | `repeat(auto-fill, minmax(184px, 1fr))`, 16 px gap |
| Card | `@surface` fill, `@outline-variant` border (`--bw`), `corner-container` (12) radius, clipped |
| Preview region | 118 px tall, `@surface-container-low` fill, hairline bottom border |
| Thumbnail placeholder | 74 × 92 px page on `@surface`, `@outline-variant` border, 6 px radius, soft shadow |
| App badge | 26 × 26 px, top-right (8 px, 8 px), `corner-small` radius, `@primary-container` fill, `@on-primary-container` 16 px icon |
| Caption | padding 10 / 12 / 12 px; name 13 px medium `@on-surface`, single line, ellipsized; meta 11 px `@on-surface-variant`, 2 px above-gap |

### States

| State | Treatment | Tokens |
| --- | --- | --- |
| Rest | Hairline outlined card | `@outline-variant` border |
| Hover | Border recolours + elevation | `@primary` border; shadow `0 6px 18px rgba(0,0,0,.12)` (prototype value) |
| Focused | Focus ring outside the border, `corner-focus` geometry | specified here, not yet implemented |
| Pressed/open | Activates the document | — |
| Empty grid | Full-width message, e.g. "No recent match this pattern." — 34 px padding, 13 px `@on-surface-variant` | prototype-only |

### Interaction

Pointer: single click opens the document/template; the card is one target
(badge and caption are not separate controls). Context menu on right-click
(open, remove from list — existing Start Center commands). Keyboard: arrow
keys move a roving selection through the grid in reading order, `Enter` opens,
`Menu`/`Shift+F10` opens the context menu, `Ctrl+F`-driven search filters the
grid live. Screen readers see a list of documents whose accessible name is
"name, application · recency" from the caption content.

### Accessibility

One accessible item per card (role list-item within the grid's list), name from
title plus meta so recency is not visual-only. Hover elevation is decorative;
keyboard focus needs its own visible ring (specified above) because border
recolour alone risks < 3:1 against `@surface-container-low`. Name truncation
must not truncate the accessible name.

### Density

Card metrics are currently density-invariant in the prototype (the grid
reflows by width instead). Adaptive width: `auto-fill/minmax` yields one
column ≈ 400 px window width up to n columns; no horizontal scrolling.

### RTL & localization

Grid flow follows reading direction; the app badge docks top-inline-end. Long
localized names ellipsize; meta strings ("Yesterday", "Last week") come from
localized relative-time strings.

### Platform notes

Cards are Start Center application drawing over `windowbackground`
(`@surface`) — not a `definition.xml` control. The existing native milestones
cover the Start Center surface/header treatment; the card grid itself is
specified here, not yet implemented natively.

### Verification hooks

Build checkpoints (per the "launch and dismiss start center" smoke scenario):
Recent grid in light/dark/high-contrast; hover and keyboard-focused card;
filtered-empty state; 400 px narrow-window reflow; RTL locale capture.

---

## 6.7 Panels & side panes

### Anatomy & tokens

Fixed-width tool regions flanking the document canvas. Prototype region sizes:

| Panel | Width | Fill | Border |
| --- | --- | --- | --- |
| Start Center navigation column | 236 px | `@surface-container` | end hairline `@outline-variant` |
| Writer properties deck + rail | 300 px total; rail 48 px | deck `@surface`; rail `@surface-container` | start hairline |
| Impress slide panel | 172 px | `@surface-container` | end hairline |
| Impress layouts panel / Draw properties | 248 px | `@surface` | start hairline |
| Draw tool rail | 48 px | `@surface-container` | end hairline |
| Base object navigation | 220 px | `@surface-container` | end hairline |

Shared anatomy: panel titles use the `title` type role (120 %, semibold
minimum); section headings are 11 px uppercase `@on-surface-variant` labels;
rail buttons are 38 × 38 px icon buttons with `corner-small` radius; deck
content uses the field/list components from chapters 04–06. All panel metrics
are prototype-only; the native sidebar remains to be restyled.

### States

| State | Treatment | Tokens |
| --- | --- | --- |
| Rail item rest | Transparent, `@on-surface-variant` icon | prototype-only |
| Rail item hover | `@primary-container` wash, `@on-primary-container` icon | prototype-only |
| Rail item active (deck shown) | Persistent `@primary-container` fill | prototype-only |
| Panel scrolled | 12 px Material scrollbar (§ 6.5) | see § 6.5 |
| Collapsed deck | Rail only (48 px) | specified here, not yet implemented |

### Interaction

Pointer: rail buttons switch or toggle decks; the splitter edge resizes where
the surface allows it. Keyboard: `F5` Navigator, `F11` Styles, `Ctrl+F5`
sidebar focus per existing LibreOffice bindings; inside a deck, `Tab` order
follows visual order and `Esc` returns focus to the document. Screen readers
expose each deck as a named panel; rail buttons expose pressed/expanded state.

### Accessibility

The active rail item is conveyed by persistent fill plus the exposed
selected/pressed state. Focus must be visible on every rail button
(`corner-focus` ring — specified here, not yet implemented natively). Decks
are landmarks with the panel title as accessible name; resizing never traps
focus.

### Density

Rail and panel widths are fixed across density profiles in the prototype;
in-deck controls follow their own compact/comfortable metrics (`--ctrl`
34/40 px). Adaptive width: below the medium window class, decks overlay the
canvas instead of compressing it — specified here, not yet implemented.

### RTL & localization

Panels swap edges wholesale in RTL (properties deck to the left, tool rails
mirror). Section labels and long localized headings wrap rather than clip;
rail tooltips carry the full command name.

### Platform notes

Panel chrome consumes `windowbackground` and `fixedline` definitions plus
`StyleSettings` fills (implemented in definition.xml, compiled at commit 577059e274; surface state unverified); deck layout and
the rail belong to the sidebar framework and are restyled per surface later in
[`ROADMAP.md`](../../ROADMAP.md). No platform-specific divergence is intended
beyond the shared high-contrast bypass.

### Verification hooks

Build checkpoints: Writer with properties deck open (light/dark, compact/
comfortable); rail hover/active/focused states; narrow-window overlay behavior;
RTL capture with mirrored panels; keyboard traversal (`Ctrl+F5`, `Tab`, `Esc`)
recorded as an interaction result, not inferred from stills.

---

## Cross-references

- Buttons and icon buttons used inside containers: [02-actions.md](02-actions.md)
- Field and search components hosted in panels: [04-inputs.md](04-inputs.md)
- Sheet tabs and sidebar rail as navigation: [05-navigation.md](05-navigation.md)
- Start Center surface composition: [09-start-center.md](09-start-center.md)
- Calc surface behavior: [10-writer-calc.md](10-writer-calc.md)
- Evidence contract for every hook above: [../HEADLESS_UI_EVIDENCE.md](../HEADLESS_UI_EVIDENCE.md)
