# 03 — Selection

> **Status:** Specification of target design — native implementation per
> [ROADMAP.md](../../ROADMAP.md). Required native definition/dispatch targets
> have compiled and executed against the implemented checkbox, radio, and tab
> contracts. The accepted Start Center runtime proof is scoped to
> Home/focus/Templates and does not exercise the selection-control state or
> pixel matrices specified here.

This file specifies the selection components of LibreOffice Material: the
checkbox (including the tristate/mixed form), the radio button, the switch,
filter chips, list selection, and the suite-wide selected-tab/selected-row
conventions. Normative sources are the design contract in
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md), the token values in
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md), the implemented native contract
in
[`vcl/uiconfig/theme_definitions/material/definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml),
and the interactive mockup in [`site/prototype.html`](../../site/prototype.html).
Implementation status is marked per feature: *implemented in definition.xml
(compiled at commit 577059e274; surface state unverified)*, *prototype-only*, or *specified here, not yet implemented*.
Compilation and executed command/state assertions are native source evidence,
not rendered selection-control proof.

A convention used throughout: the native drawing definitions position geometry
in normalized part coordinates (0–1 of the part cell). At the declared
`size-selection-control` (24) cell, the `0.08–0.92` control box resolves to a
visual box of roughly 20 px inside a 24 px hit cell, which is why the prototype
draws its checkbox and radio glyphs at 20 × 20 px.

---

## 1. Checkbox

### 1.1 Anatomy & tokens

| Region | Description | Tokens |
| --- | --- | --- |
| Hit cell | Square part cell; also the keyboard focus anchor | `size-selection-control` (24) width and height — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Box | Rounded square drawn at `0.08–0.92` of the cell | `corner-checkbox` (3) radius, `stroke-standard` (2) border; state-dependent stroke/fill below |
| Check glyph | Two-segment tick from `(0.27, 0.52)` to `(0.44, 0.69)` to `(0.75, 0.34)` | `@on-primary` stroke, `stroke-standard` |
| Mixed dash | Horizontal bar from `(0.27, 0.5)` to `(0.73, 0.5)` | `@on-primary` stroke, `stroke-standard` |
| Focus ring | Separate `Focus` part: four lines inset at `0.04`/`0.96` forming a square outline | `@primary` stroke, `stroke-standard` |
| Label | Text to the side of the cell (VCL label, not part of the drawn cell) | `radioCheckTextColor` style slot → `@on-surface`; `label` typography role (100 % height, minimum-weight `medium`) |

All of the above is implemented in definition.xml (compiled at commit 577059e274; surface state unverified). The prototype
mirrors it with a 20 × 20 box, `--r-check` radius, a 2 px border, and an 18 px
check icon at stroke width 2.4.

### 1.2 States

Eleven `Entire` states plus the `Focus` part exist natively — the full
enabled/hover/pressed matrix across unchecked, checked, and mixed, and all
three disabled value combinations.

| State (`definition.xml` attributes) | Box stroke | Box fill | Glyph |
| --- | --- | --- | --- |
| `enabled="true"` unchecked | `@on-surface-variant` | `@surface` | — |
| `enabled="true" button-value="true"` | `@primary` | `@primary` | tick `@on-primary` |
| `enabled="true" button-value="mixed"` | `@primary` | `@primary` | dash `@on-primary` |
| `rollover="true"` unchecked | `@primary` | `@primary-container` | — |
| `rollover="true" button-value="true"` | `@primary-action-hover` | `@primary-action-hover` | tick `@on-primary` |
| `rollover="true" button-value="mixed"` | `@primary-action-hover` | `@primary-action-hover` | dash `@on-primary` |
| `pressed="true"` unchecked | `@primary` | `@primary-hover` | — |
| `pressed="true" button-value="true"` | `@primary-action-pressed` | `@primary-action-pressed` | tick `@on-primary` |
| `pressed="true" button-value="mixed"` | `@primary-action-pressed` | `@primary-action-pressed` | dash `@on-primary` |
| `enabled="false"` unchecked | `@outline` | `@disabled-container` | — |
| `enabled="false" button-value="true"` | `@outline` | `@outline` | tick `@disabled-container` |
| `enabled="false" button-value="mixed"` | `@outline` | `@outline` | dash `@disabled-container` |
| Focus (any value) | `Focus` part square outline, `@primary`, `stroke-standard` | — | — |

The disabled-selected and disabled-mixed rows are deliberate affordances: the
value glyph survives in `@disabled-container` on an `@outline` fill, so a
disabled checkbox never loses its value.

### 1.3 Interaction

- **Pointer.** Click anywhere in the cell or on the label toggles the value.
  Hover raises the `rollover` states; the pressed state renders from press
  until release, and the value commits on release inside the control.
- **Keyboard.** Tab/Shift+Tab moves focus; Space toggles. User-settable
  tristate checkboxes cycle unchecked → checked → mixed → unchecked;
  otherwise mixed is programmatic-only and Space resolves it to checked.
- **Mnemonics.** The VCL label mnemonic (Alt+underlined letter) focuses and
  toggles in one action, per existing LibreOffice behaviour.
- **Screen reader.** Toggling announces the new state immediately, including
  "mixed"/"partially checked" for tristate.

### 1.4 Accessibility

- Role `CHECK_BOX`; accessible name from the label including mnemonic
  stripping; state exposes CHECKED and INDETERMINATE per the existing VCL
  accessibility bridge. Specified here, not yet implemented as verified
  behaviour.
- Focus indicator is the drawn `Focus` part (square `@primary` outline), not a
  platform dotted rectangle. Under resolved high contrast, Material drawing is
  bypassed entirely and the captured native `StyleSettings` baseline returns,
  so forced-colour users keep the platform indicator.
- Contrast: value is never colour-only — checked, mixed, and unchecked differ
  by glyph presence and glyph shape, in every enabled and disabled state.
- The light-palette checked pair (`@primary` #6750A4 / `@on-primary` #FFFFFF)
  and dark pair (#D0BCFF / #381E72) are the token-reference values from
  [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md); contrast checks are validator
  targets, not runtime results.

### 1.5 Density

The native metric layer declares a single `size-selection-control` = 24 and no
density selection ([`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md), milestone
7 boundary). The prototype's browser-only density layer changes surrounding
row/label metrics, not the box itself:

| Profile | Row height (`--row`) | Item height (`--item`) | Font (`--fs`) | Box |
| --- | ---: | ---: | ---: | ---: |
| Compact | 26 px | 30 px | 13 px | 20 px visual / 24 px cell |
| Comfortable | 32 px | 40 px | 14 px | 20 px visual / 24 px cell |

A comfortable-density native cell size is specified here, not yet implemented.

### 1.6 RTL & localization

- In RTL locales the box sits to the right of the label; the check glyph is
  **not** mirrored — the tick is a state symbol, not a directional glyph
  (mirroring is semantic per the iconography rules).
- Long labels wrap or truncate per the host dialog; the box stays top-aligned
  with the first text line. Label text never renders inside the 24 px cell.

### 1.7 Platform notes

Windows-first: the file-definition renderer draws identically on every backend
that enables file-defined widgets; Windows printer graphics are excluded from
the initialization path, so printed dialogs fall back to existing drawing.
Resolved high contrast restores the platform baseline on all platforms — a
deliberate difference from themes that restyle forced colours.

### 1.8 Verification hooks

Per the evidence contract style of
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md):

- headless draw test: render `checkbox`/`Entire` at 24 × 24 for all 11 states
  in both palettes; assert box pixels match resolved `@` tokens and that the
  mixed dash is distinguishable from the tick by pixel signature;
- screenshot checkpoint: an Options dialog capture (run-scoped build with
  `VCL_DRAW_WIDGETS_FROM_FILE=1`, `VCL_FILE_WIDGET_THEME=material`) showing
  unchecked, checked, mixed, and a disabled-checked checkbox in one frame;
- accessibility probe: Space toggling and INDETERMINATE exposure over the UNO
  accessibility API on the same run.

---

## 2. Radio button

### 2.1 Anatomy & tokens

| Region | Description | Tokens |
| --- | --- | --- |
| Hit cell | Square part cell | `size-selection-control` (24) — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Ring | Rounded box at `0.08–0.92` | `corner-control` (10) radius, `stroke-standard` (2) |
| Dot | Inner indicator at `0.33–0.67` | `corner-indicator` (4) radius, `stroke-thin` (1), `@on-primary` |
| Focus ring | `Focus` part square outline at `0.04`/`0.96` | `@primary`, `stroke-standard` |
| Label | Side label | `radioCheckTextColor` → `@on-surface`; `label` type role |

Note the native geometry: at the 24 px cell, `corner-control` (10) on the
~20 px ring renders an effectively circular control, and the `0.33–0.67`
indicator is a ~8 px rounded dot. The prototype idealizes this as a true
20 px circle with a 10 px dot.

### 2.2 States

Eight `Entire` states plus `Focus` — implemented in definition.xml (compiled at commit 577059e274; surface state unverified).
Radio has no mixed value.

| State | Ring stroke | Ring fill | Dot |
| --- | --- | --- | --- |
| `enabled="true" button-value="false"` | `@on-surface-variant` | `@surface` | — |
| `enabled="true" button-value="true"` | `@primary` | `@primary` | `@on-primary` |
| `rollover="true" button-value="false"` | `@primary` | `@primary-container` | — |
| `rollover="true" button-value="true"` | `@primary-action-hover` | `@primary-action-hover` | `@on-primary` |
| `pressed="true" button-value="false"` | `@primary` | `@primary-hover` | — |
| `pressed="true" button-value="true"` | `@primary-action-pressed` | `@primary-action-pressed` | `@on-primary` |
| `enabled="false" button-value="false"` | `@outline` | `@disabled-container` | — |
| `enabled="false" button-value="true"` | `@outline` | `@outline` | `@disabled-container` |
| Focus | `Focus` part `@primary` square outline | — | — |

As with the checkbox, the disabled-selected combination keeps its dot (in
`@disabled-container` on the `@outline` fill), so the chosen option in a
disabled group remains identifiable.

### 2.3 Interaction

- **Pointer.** Click selects; selection within a group is mutually exclusive.
  Hover and pressed feedback as per the state table.
- **Keyboard.** Tab enters the group on the selected member (or the first, if
  none is selected); Arrow keys (Up/Left and Down/Right) move selection within
  the group and select as they move, per existing VCL group traversal; Space
  selects the focused member. Tab leaves the whole group.
- **Mnemonics.** Alt+letter on a member's label focuses and selects it.
- **Screen reader.** Announces role, name, selected state, and group position
  (existing VCL position-in-set exposure).

### 2.4 Accessibility

Role `RADIO_BUTTON` with CHECKED state exposure; the group relation comes from
the existing dialog grouping. Focus indicator, high-contrast bypass, and
colour-independence rules are identical to the checkbox: selection is carried
by the dot, never by fill colour alone. Specified here, not yet implemented as
verified behaviour.

### 2.5 Density

Same as checkbox: one native 24 px cell; prototype rows scale 26→32 px and
labels 13→14 px between compact and comfortable. No native density profile yet.

### 2.6 RTL & localization

Mirrored placement (control right of label) in RTL. The dot is symmetric, so no
glyph mirroring applies. Arrow-key direction follows the resolved layout: in
RTL, Left moves to the *next* member in visual order per platform convention —
the existing VCL behaviour is preserved, not redefined here.

### 2.7 Platform notes

Identical file-definition rendering across backends; high-contrast bypass as
above. The rounded-square-as-circle approximation is a deliberate consequence
of the shared rect-based drawing primitives.

### 2.8 Verification hooks

- headless draw test: all 8 `radiobutton`/`Entire` states at 24 × 24, both
  palettes; assert dot presence in exactly the `button-value="true"` states;
- screenshot checkpoint: a dialog radio group with one selected, one hovered,
  and one disabled-selected member;
- keyboard probe: arrow-key traversal order recorded against reading order.

---

## 3. Switch

### 3.1 Anatomy & tokens

The switch is **prototype-only**: `definition.xml` defines no switch control,
and VCL dialogs conventionally use checkboxes for on/off settings. Where a
surface adopts a switch (e.g. the prototype's component gallery "Comfortable
density" row), the target anatomy from `site/prototype.html` is:

| Region | Value (prototype) | Token mapping |
| --- | --- | --- |
| Track | 52 × 32 px, radius 16 px, 2 px padding, 2 px border | On: `@primary` fill and border. Off: `@outline-variant` fill, `@outline` border. Radius is the track half-height (pill form) |
| Thumb | 24 × 24 px circle, shadow `0 1px 3px rgba(0,0,0,.3)` | On: `@on-primary`. Off: `@outline` |
| Label | 14 px text, 12 px gap | `@on-surface`; `label` type role |

The thumb sits at the trailing edge when on and the leading edge when off; the
prototype animates only the track background (`transition: background .15s`).

### 3.2 States

| State | Track | Thumb |
| --- | --- | --- |
| On | `@primary` fill, `@primary` border | `@on-primary` |
| Off | `@outline-variant` fill, `@outline` border | `@outline` |
| Hover / pressed / disabled | Specified here, not yet implemented: follow the checkbox families — hover-on `@primary-action-hover`, hover-off `@primary-container` fill with `@primary` border, disabled track `@disabled-container` with `@outline` border, disabled-on thumb `@disabled-container` on an `@outline` track |
| Focus | Specified here, not yet implemented: square `@primary` outline per the shared `Focus` part convention |

### 3.3 Interaction

Pointer click anywhere on track, thumb, or label toggles. Keyboard: Space
toggles; Tab focuses. A native switch must also honour Home/End or Left/Right
as off/on where the platform convention expects it. Screen readers should see
a toggle-button/checkbox semantic with the checked state — never an
unlabelled slider.

### 3.4 Accessibility

Position is redundant with colour (thumb edge = value), satisfying
colour-independence. Because no native part exists, no accessibility exposure
exists yet; any native adoption must map to `CHECK_BOX` (or the toggle-button
role where available) with CHECKED state. Specified here, not yet implemented.

### 3.5 Density

Prototype uses one 52 × 32 geometry in both densities; only the label font
(13→14 px) and row spacing change. A compact 44 × 24 variant is deliberately
**not** specified: two switch sizes would fragment the toggle family.

### 3.6 RTL & localization

In RTL the on-position is the visual left (trailing edge mirrors). The
prototype expresses thumb position with flex `justify-content`, which mirrors
automatically; a native implementation must mirror the value-to-edge mapping,
not just the drawing.

### 3.7 Platform notes

Native VCL has no switch control type; introducing one is a design decision
beyond the file-definition theme. Until then, dialogs keep checkboxes, and the
switch remains a prototype/panel idiom.

### 3.8 Verification hooks

- prototype check (available now): DOM assertions in `site/prototype.html`
  that the gallery switch toggles `gSwitch` state and swaps
  track/thumb variable pairs;
- future native hooks: only after a switch part enters `definition.xml`; a
  screenshot checkpoint would pair on/off/disabled-on in one capture.

---

## 4. Filter chips

### 4.1 Anatomy & tokens

Filter chips are **prototype-only** (component gallery "Design / Native /
Accessible" chips; toolbar-style chips also appear in the notebookbar mock).
No chip part exists in `definition.xml`; the nearest native analogue is the
checked toolbar button (`toolbar` part with `button-value="true"`). Target
anatomy from `site/prototype.html`:

| Region | Unselected | Selected |
| --- | --- | --- |
| Container | 32 px height, radius `--r-sm` → `corner-small` (8), `--bw` border in `@outline`, transparent fill, padding 0 16 px | Border `@primary`, fill `@primary-container`, padding 0 14 px right / 10 px left |
| Leading check | 18 px check icon, opacity 0 (reserved by markup, hidden) | Opacity 1, drawn in the label colour |
| Label | 13 px, weight 500, `@on-surface` | `@on-primary-container` |

The asymmetric selected padding (10 px leading) makes room for the leading
check without the chip changing width perceptibly.

### 4.2 States

| State | Treatment |
| --- | --- |
| Unselected | `@outline` border, transparent fill, `@on-surface` label, hidden check |
| Selected | `@primary` border, `@primary-container` fill, `@on-primary-container` label, visible leading check |
| Hover | Specified here, not yet implemented: unselected hover fills `@primary-container` at label colour `@on-primary-container`; selected hover deepens to the `@primary-hover` fill used by selected tabs |
| Disabled | Specified here, not yet implemented: `@outline-variant` border, `@disabled-container` fill, `@outline` label; a disabled-selected chip keeps its check per the disabled-affordance rule |
| Focus | Square `@primary` outline per the shared focus convention |

### 4.3 Interaction

Pointer click toggles. Keyboard: chips are buttons — Tab reaches each chip,
Space/Enter toggles. The prototype sets `aria-pressed="true|false"` on every
chip and segmented control button, which is the contract to preserve: a filter
chip is a toggle button, not a checkbox and not a link.

### 4.4 Accessibility

Toggle-button role with pressed state (`aria-pressed` in the prototype; native
adoption maps to the toolbar toggle-button exposure). Selection is triple-coded
— border colour, fill, and the leading check — so colour is never the only
carrier. Contrast pairs are the token-table `primary-container`/
`on-primary-container` values.

### 4.5 Density

Prototype chips are 32 px in both densities (gallery), with 8 px wrap gap;
notebookbar label chips render at 30 px with `corner-pill` (20) radius and
`@outline-variant` borders — a deliberate visual cousin, not the filter-chip
pattern. A 28 px compact filter chip (`size-compact-control`) is specified
here, not yet implemented.

### 4.6 RTL & localization

Leading check mirrors to the right side in RTL along with the asymmetric
padding. Long localized labels stay single-line; chips grow horizontally and
wrap as units within the chip row (`flex-wrap` in the prototype). Truncation
inside a chip is not permitted — a filter whose name is unreadable is not a
usable filter.

### 4.7 Platform notes

None deliberate beyond the suite-wide high-contrast bypass. When chips reach
native surfaces they must be expressed through shared VCL toggle buttons so
Writer, Calc, and the Start Center consume one implementation.

### 4.8 Verification hooks

- prototype check (available now): assert `aria-pressed` flips and the check
  opacity/padding pair tracks it for the three gallery chips;
- future native hooks: once a chip/toggle part exists, headless draws of
  selected+disabled combinations and a Start Center filter-row screenshot
  checkpoint.

---

## 5. List selection

### 5.1 Anatomy & tokens

The selection treatment for lists, list boxes, and drop-down windows is the
`primary-container` pair, implemented in definition.xml (compiled at commit 577059e274; surface state unverified) through the
72-slot style mapping rather than a drawn part:

| Style slot | Token |
| --- | --- |
| `listBoxWindowHighlightColor` | `@primary-container` |
| `listBoxWindowHighlightTextColor` | `@on-primary-container` |
| `highlightColor` | `@primary-container` |
| `highlightTextColor` | `@on-primary-container` |
| `listBoxWindowBackgroundColor` / `listBoxWindowTextColor` | `@surface` / `@on-surface` |
| `alternatingRowColor` | `@surface-container-low` |
| `checkedColor` | `@primary-container` |
| `listBoxEntryMargin` | `@space-list-entry` (12) |

The prototype's gallery list shows the target rendering: 44 px rows, 14 px
horizontal padding, 12 px icon–label gap, selected row filled
`--pc` (`@primary-container`) with a trailing 18 px check in `--p`
(`@primary`), and `@outline-variant` row separators.

### 5.2 States

| Row state | Treatment |
| --- | --- |
| Unselected | `@surface` (or `@surface-container-low` alternating rows), `@on-surface` text |
| Hover | `@primary-container` at reduced prominence is the menu convention (`menuHighlightColor`); plain lists may keep hover-free rows — pointer feedback must not be mistaken for selection |
| Selected | `@primary-container` fill, `@on-primary-container` text, trailing `@primary` check where the widget supports a glyph column |
| Selected + focused row | Selection fill plus the widget's focus outline (`@primary`, `stroke-standard` in drawn parts) |
| Disabled list | Container renders the `listbox` `enabled="false"` part: `@outline-variant` stroke, `@disabled-container` fill |

### 5.3 Interaction

Pointer: single click selects; Ctrl+click toggles in multi-select lists;
Shift+click extends a range. Keyboard: Up/Down move selection; Home/End jump;
Ctrl+Space toggles the focused row in multi-select; type-ahead selects by
prefix (existing VCL behaviour, preserved). Screen readers receive per-row
selection events with SELECTED state.

### 5.4 Accessibility

Selection is exposed through the existing list/tree accessible SELECTED state;
the trailing check gives a non-colour cue wherever the widget template carries
a glyph column, and the `@primary-container`→`@on-primary-container` text
change means selection also alters foreground, not just background.
The contrast of that pair is a validator target (the standalone validator
checks list/selection contrast pairs — source check, not runtime evidence).

### 5.5 Density

Prototype rows: 26 px compact / 32 px comfortable (`--row`); the gallery
document list uses fixed 44 px rows as a comfortable pattern for card-like
lists. Native `listBoxEntryMargin` stays 12 in both until a native density
layer exists.

### 5.6 RTL & localization

Row layout mirrors (icon right, check left in RTL). The trailing check mirrors
because it is positional, not directional. Long entries ellipsize at the end
(start in RTL); selection fill always spans the full row width, not the text
width.

### 5.7 Platform notes

The style-slot route means platform list widgets that bypass VCL styling keep
platform selection colours; that divergence is visible and accepted only
outside the Material-drawn surfaces.

### 5.8 Verification hooks

- headless check: resolve `StyleSettings` under the Material profile and
  assert the four highlight slots equal the palette values (#E8DEF8/#1D192B
  light, #4F378B/#EADDFF dark per the token reference);
- screenshot checkpoint: a drop-down list open with one selected and one
  hovered row in both palettes.

---

## 6. Selected-tab and selected-row conventions

### 6.1 Anatomy & tokens

The suite-wide rule: **persistent selection is `primary-container`; transient
hover of an already-selected thing is `primary-hover`; a disabled selection
keeps an `@outline` stroke so it never disappears.** The native anchors,
implemented in definition.xml (compiled at commit 577059e274; surface state unverified):

- `tabitem`/`Entire` — pill tabs: `height-tab` (40), `space-tab-inline` (12)
  margin, `corner-pill` (20) radius;
- `tabitem`/`MenuItem` — rectangular tab rows: `corner-container` (12) radius;
- `menubar`/`MenuItem` and `menupopup`/`MenuItem` — `selected="true"` fills
  `@primary-hover` (radius `corner-container` and `corner-small` respectively);
- `menupopup`/`MenuItemCheckMark` and `MenuItemRadioMark` at
  `size-menu-indicator` (18): `@primary` marks when enabled, `@outline` marks
  when disabled — the menu-level disabled-selected affordance.

### 6.2 States (tab parts, both variants)

| State | Stroke | Fill | Stroke width |
| --- | --- | --- | --- |
| `enabled="true"` | `@surface-container` | `@surface-container` | `stroke-none` |
| `enabled="true" selected="true"` | `@primary-container` | `@primary-container` | `stroke-none` |
| `enabled="true" rollover="true"` | `@disabled-container` | `@disabled-container` | `stroke-none` |
| `enabled="true" focused="true"` | `@primary` | `@surface-container` | `stroke-standard` |
| `selected="true" rollover="true"` | `@primary` | `@primary-hover` | `stroke-thin` |
| `selected="true" focused="true"` | `@primary` | `@primary-container` | `stroke-standard` |
| `enabled="false"` | `@disabled-container` | `@disabled-container` | `stroke-none` |
| `enabled="false" selected="true"` | `@outline` | `@disabled-container` | `stroke-thin` |

The `enabled="false" selected="true"` rows (both `Entire` and `MenuItem`) are
the milestone-10 additions: a disabled tab control keeps its current page
identifiable. The related settings `noActiveTabTextRaise` and `centeredTabs`
are `true`, and tab text colours route through `activeTabColor`
(`@primary-container`), `tabTextColor` (`@on-surface-variant`), and
`tabHighlightTextColor` (`@on-primary-container`).

### 6.3 Interaction

Tabs: pointer click activates; Ctrl+Tab/Ctrl+Shift+Tab cycle pages; arrow keys
move within the tab strip when it has focus; the focused-but-unselected tab
shows the `focused="true"` outline without activating until Space/Enter
(follow-focus activation stays per existing widget behaviour). Menus: selected
(open) menubar items render `@primary-hover` distinct from the
`@primary-container` hover.

### 6.4 Accessibility

Tabs expose PAGE_TAB with SELECTED; the selected state is coded by fill *and*
by the text-colour change to `@on-primary-container`, and in the
disabled-selected case by the `@outline` stroke — never colour-lightness
alone. The focused states use a `stroke-standard` `@primary` outline as the
visible focus indicator.

### 6.5 Density

`height-tab` is fixed at 40 with 12 px inline margins natively; the prototype's
segmented pill controls (gallery/history/dialog pickers) render 7 px vertical ×
14–16 px horizontal padding at 16 px radius with `aria-pressed`, scaling text
13→14 px across density.

### 6.6 RTL & localization

Tab strips reverse visual order in RTL; `centeredTabs` keeps the group
centred either way. Long tab labels widen the pill up to the container's
scrolling/overflow rules (see [05-navigation.md](05-navigation.md)); labels do
not wrap inside a 40 px tab.

### 6.7 Platform notes

No deliberate per-platform divergence: the same part definitions serve every
file-widget backend; high contrast bypasses to the native baseline.

### 6.8 Verification hooks

- headless draw test: all 16 `tabitem` states (8 × 2 parts), asserting the
  disabled-selected `@outline` stroke survives and differs from plain
  disabled;
- screenshot checkpoints: a dialog tab strip with selected + hovered-selected
  + disabled-selected tabs; a menubar with one open (`selected`) and one
  hovered item;
- style probe: `activeTabColor`/`tabHighlightTextColor` resolution equals the
  palette values in both schemes.

---

*Previous: [02-actions.md](02-actions.md) · Next: [04-inputs.md](04-inputs.md)
· Index: [README.md](README.md)*
