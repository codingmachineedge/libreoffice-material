# 05 · Navigation & command surfaces

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This chapter specifies the surfaces a user navigates *with*: the menubar and its
drop menus, context menus, tab bars, the notebookbar (ribbon), the sidebar rail,
Calc's sheet tabs, the window title bar, and the status bar. Every colour,
shape, and metric below is a semantic role from
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md); the native part/state names are
quoted from
[`vcl/uiconfig/theme_definitions/material/definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml),
and pixel geometry not yet in the native contract is taken from the interactive
reference [`site/prototype.html`](../../site/prototype.html).

Implementation status legend used throughout:

- **implemented in definition.xml (unbuilt)** — the native file-widget contract
  already declares the part/state; no build has ever executed it;
- **prototype-only** — the value exists only in the HTML mockup;
- **specified here, not yet implemented** — in neither source.

| Component | Native contract | Prototype reference |
| --- | --- | --- |
| Menubar + drop menus | `menubar`, `menupopup` parts — implemented in definition.xml (unbuilt) | menu heights, dropdown geometry |
| Context menus | reuse `menupopup` — implemented in definition.xml (unbuilt) | — |
| Tab bars | `tabitem` `Entire`/`MenuItem`, `tabheader`, `tabpane`, `tabbody` — implemented in definition.xml (unbuilt) | — |
| Notebookbar (ribbon) | toolbar `Button` states only — partial | tab row + 96px group area |
| Sidebar rail | none (toolbar tokens apply) | 48px rail, 38px buttons |
| Calc sheet tabs | `tabitem` tokens apply | 34px strip, 26px tabs |
| Window title bar | `settings` title heights + active/deactive style slots | 42px chrome bar |
| Status bar | `slider` parts for zoom — partial | 28px bar, 120×4px slider |

---

## 1. Menubar and drop menus

### 1.1 Anatomy & tokens

The menubar is a flat band at the top of the application window; each menu title
is a rounded item inside it. An open title spawns a drop menu: an elevated
surface of command items, separators, check/radio marks, and submenu arrows.

| Region | Native part | Tokens | Status |
| --- | --- | --- | --- |
| Menubar band | `menubar`/`Entire` | fill `@surface-container`, `stroke-none` | implemented in definition.xml (unbuilt) |
| Menu title item | `menubar`/`MenuItem` | radius `corner-container`; text `menuBarTextColor → @on-surface` | implemented in definition.xml (unbuilt) |
| Drop-menu container | `menupopup`/`Entire` | fill `@surface`, stroke `@outline-variant` × `stroke-thin`, radius `corner-container` | implemented in definition.xml (unbuilt) |
| Command item | `menupopup`/`MenuItem` | radius `corner-small`; text `menuTextColor → @on-surface` | implemented in definition.xml (unbuilt) |
| Check mark | `menupopup`/`MenuItemCheckMark`, `size-menu-indicator` (18) square | `@primary` glyph, `stroke-standard` | implemented in definition.xml (unbuilt) |
| Radio mark | `menupopup`/`MenuItemRadioMark`, `size-menu-indicator` (18) square | `@primary` fill, radius `corner-indicator`, inset 0.28–0.72 | implemented in definition.xml (unbuilt) |
| Separator | `menupopup`/`Separator` | `@outline-variant` × `stroke-thin`, spanning x 0.08–0.92 | implemented in definition.xml (unbuilt) |
| Submenu arrow | `menupopup`/`SubmenuArrow`, `size-menu-indicator` (18) square | `@on-surface-variant` chevron, `stroke-standard` | implemented in definition.xml (unbuilt) |
| Accelerator text | — | `label` type role, `@on-surface-variant` | prototype-only (12px monospaced column) |

Prototype geometry: the menubar is `--menu` tall (30px compact / 38px
comfortable) with 6px horizontal padding; menu titles carry 5px × 11px padding.
The drop menu opens 4px below its title, has a 248px minimum width, 6px inner
padding, and each item row is `--item` tall (30px compact / 40px comfortable)
with 10px horizontal padding and a 14px gap between label, accelerator, and
arrow columns. All of this block geometry is prototype-only. Where the
prototype rounds menu titles at 8px, the native contract's `corner-container`
reference is authoritative.

### 1.2 States

Menubar title (`menubar`/`MenuItem`):

| State | Visual treatment | Exact tokens |
| --- | --- | --- |
| Idle | blends into the band | fill `@surface-container`, radius `corner-container` |
| Hover (`rollover`) | tonal container | fill `@primary-container`; text `menuBarRolloverTextColor → @on-primary-container` |
| Open (`selected`) | stronger tonal fill | fill `@primary-hover`; text `menuBarHighlightTextColor → @on-primary-container` |

Drop-menu item (`menupopup`/`MenuItem`):

| State | Visual treatment | Exact tokens |
| --- | --- | --- |
| Idle | flat on menu surface | fill `@surface`, radius `corner-small` |
| Hover (`rollover`) | primary-container pill | fill `@primary-container`; text `menuHighlightTextColor → @on-primary-container` |
| Keyboard highlight (`selected`) | stronger tonal fill | fill `@primary-hover` |
| Disabled item text | dimmed via style slot | `deactiveTextColor → @outline` |

Marks and arrow:

| Part · state | Exact tokens |
| --- | --- |
| `MenuItemCheckMark` `enabled="true" pressed="true"` | `@primary` check, `stroke-standard` |
| `MenuItemCheckMark` `enabled="false" pressed="true"` | `@outline` check (dimmed) |
| `MenuItemRadioMark` `enabled="true" pressed="true"` | `@primary` fill, radius `corner-indicator` |
| `MenuItemRadioMark` `enabled="false" pressed="true"` | `@outline` fill |
| `SubmenuArrow` default | `@on-surface-variant` chevron |
| `SubmenuArrow` `enabled="false"` | `@outline` chevron — the milestone-10 dimmed arrow for a disabled submenu parent |

VCL reports a checked mark through the pressed control state, which is why the
mark states pair `pressed="true"` with `enabled`. All states in both tables are
implemented in definition.xml (unbuilt).

### 1.3 Interaction

- **Pointer:** click a title to open; hover-tracking moves between open menus
  without a second click; click outside (the prototype models this with a
  full-window click-away layer) or press `Esc` to dismiss; hovering a submenu
  parent opens its child after the platform hover delay.
- **Keyboard:** `F10` or `Alt` focuses the menubar; `Alt`+mnemonic opens a
  specific menu; `←`/`→` move across titles (wrapping); `↓`/`Enter` opens the
  focused menu; inside a menu `↑`/`↓` cycle items, `→` opens a submenu, `←`
  closes it, `Enter`/`Space` activates, `Esc` closes one level, `Alt` closes
  all. Typed mnemonic letters activate matching items directly.
- **Mnemonics:** underlined characters per localized `.ui`/resource label;
  Windows reveals underlines on `Alt` per system setting.
- **Screen reader:** the band exposes the menu-bar role; titles expose the menu
  role with expanded/collapsed state; items expose the menu-item role, the
  localized label as name, the accelerator as keyboard-shortcut text, and
  checkable items expose their checked state. Retained from existing VCL
  accessibility; not restyled by this theme.

### 1.4 Accessibility

- Hover/highlight pairs `@primary-container` / `@on-primary-container` and the
  base `@on-surface` on `@surface` both exceed 4.5:1 in light and dark palettes.
- Disabled items keep their glyphs: the milestone-10 dimmed `@outline` submenu
  arrow and marks mean a disabled parent still *shows* it has a submenu —
  meaning is not carried by colour alone.
- The keyboard highlight (`selected`, `@primary-hover`) is distinct from hover
  so a screen-magnifier user can find the active row.
- Under resolved high contrast the Material drawing path is bypassed and the
  captured native `StyleSettings` baseline is restored (see
  [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)).

### 1.5 Density

Native `<metrics>` declares no density switching. Prototype targets:

| Metric | Compact | Comfortable |
| --- | ---: | ---: |
| Menubar height (`--menu`) | 30px | 38px |
| Menu item height (`--item`) | 30px | 40px |
| Base font (`--fs`) | 13px | 14px |

The `size-menu-indicator` (18) mark/arrow square is density-invariant.

### 1.6 RTL & localization

In RTL locales the title order, item alignment, accelerator column, and submenu
arrow mirror; submenu open/close keys swap (`←` opens, `→` closes). The chevron
glyph mirrors because it is directional-semantic. Long localized labels widen
the popup beyond the 248px minimum rather than truncating; accelerator text
never wraps.

### 1.7 Platform notes

Windows-first: menu drop alignment, hover-open delay, and `Alt` underline
behaviour follow the platform. The Material popup deliberately keeps a
`stroke-thin` `@outline-variant` border in addition to shadow so elevation
survives low-contrast displays and forced-colour modes.

### 1.8 Verification hooks

Per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md), with
`VCL_DRAW_WIDGETS_FROM_FILE=1` and `VCL_FILE_WIDGET_THEME=material` on the
off-screen desktop:

- `nav-menubar-01` — capture idle/hover/open title states; assert
  `@surface-container`, `@primary-container`, `@primary-hover` fills.
- `nav-menu-02` — open **Edit**; capture item hover, a checked item, a
  separator, and an enabled submenu arrow.
- `nav-menu-03` — a menu with a disabled submenu parent; assert the arrow
  renders in `@outline`, not the enabled `@on-surface-variant`.
- Headless draw tests already cover these part/state tuples in source; they
  have not executed.

---

## 2. Context menus

**Anatomy & tokens.** Context menus are the same `menupopup` control as drop
menus: `Entire` container (`@surface` fill, `@outline-variant` ×
`stroke-thin`, `corner-container`), `MenuItem` rows at `corner-small`, the same
marks, separator, and submenu arrow. Implemented in definition.xml (unbuilt);
no separate context-menu part exists or is needed.

**States.** Identical to §1.2.

**Interaction.** Right-click (or long-press on touch) opens at the pointer;
`Shift+F10` or the `Menu` key opens at the current selection or caret with
placement that keeps the menu on-screen. First item is not pre-highlighted on
pointer invocation; keyboard invocation highlights the first enabled item.
`Esc` dismisses and returns focus to the invoking control.

**Accessibility.** Same role exposure as drop menus; the invoking object keeps
focus until an item is activated, so focus never "escapes" into the popup for
assistive tech that tracks the caret.

**Density / RTL.** As §1.5–1.6; near-edge placement flips to keep the menu
inside the work area, and the flip logic mirrors in RTL.

**Platform notes.** Windows `Menu` key support is required; macOS/Linux
platform menu integration is out of scope for the Windows-first slice.

**Verification hooks.** `nav-context-01` — right-click in the Writer canvas and
in Calc's sheet-tab strip; capture container, hover, and separator rendering.

---

## 3. Tab bars

### 3.1 Anatomy & tokens

Dialog and notebook tab bars use the `tabitem` control, whose native `Entire`
part declares `margin-width="@space-tab-inline"` (12) and
`height="@height-tab"` (40) — implemented in definition.xml (unbuilt). Two part
variants exist:

| Part | Shape | Use |
| --- | --- | --- |
| `tabitem`/`Entire` | radius `corner-pill` | free-standing pill tabs |
| `tabitem`/`MenuItem` | radius `corner-container` | tabs rendered inside a header band |

The strip behind tabs is `tabheader`/`Entire` (`@surface-container`,
`stroke-none`); the page area is `tabpane` and `tabbody` (`@surface` fill,
`@outline-variant` × `stroke-thin`, `corner-container`). Native `<settings>`
declare `noActiveTabTextRaise` and `centeredTabs`, both `true`, so the active
tab neither shifts its label nor left-aligns the row. Tab text colours come
from the style slots `tabTextColor → @on-surface-variant`,
`tabRolloverTextColor → @on-surface`, and
`tabHighlightTextColor → @on-primary-container`.

### 3.2 States

Both parts declare the same eight states (fills/strokes identical; only the
radius role differs). All are implemented in definition.xml (unbuilt):

| State | Visual treatment | Exact tokens (`Entire` shown) |
| --- | --- | --- |
| `enabled` | quiet, blends with header | fill `@surface-container`, `stroke-none`, `corner-pill` |
| `enabled selected` | tonal active pill | fill `@primary-container`, `stroke-none` |
| `enabled rollover` | faint hover wash | fill `@disabled-container`, `stroke-none` |
| `enabled focused` | ring on quiet tab | stroke `@primary` × `stroke-standard`, fill `@surface-container` |
| `enabled selected rollover` | active + hover | stroke `@primary` × `stroke-thin`, fill `@primary-hover` |
| `enabled selected focused` | active + ring | stroke `@primary` × `stroke-standard`, fill `@primary-container` |
| `enabled="false"` | flat disabled | fill `@disabled-container`, `stroke-none` |
| `enabled="false" selected` | current page stays identifiable | stroke `@outline` × `stroke-thin`, fill `@disabled-container` |

The disabled-selected state is the milestone-10 correction: when a whole tab
control is disabled, the current page keeps an `@outline` ring so it never
collapses into its unselected siblings.

### 3.3 Interaction

Pointer: click selects immediately; hover shows the wash without committing.
Keyboard: `Tab` moves focus into the tab bar; `←`/`→` (mirrored in RTL) move
between tabs and select as they move; `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle pages
from anywhere inside the dialog; `Home`/`End` jump to first/last tab. Mnemonic
letters in tab labels activate their page. Screen readers see a page-tab-list
containing page-tabs with the selected state on the active tab. Retained VCL
behaviour; not restyled.

### 3.4 Accessibility

Selection is triple-encoded — `@primary-container` fill, label colour change to
`@on-primary-container`, and (native contract) no text raise, so magnified
views stay stable. The focus ring is a `stroke-standard` `@primary` outline on
the item itself rather than a detached dotted rectangle. Disabled-selected
keeps a visible stroke, satisfying the colour-independence rule.

### 3.5 Density

`height-tab` (40) and `space-tab-inline` (12) are density-invariant native
integers. The prototype renders dialog tab rows at these values under both
density profiles; only label font size follows `--fs` (13px/14px).

### 3.6 RTL & localization

Tab order mirrors; `centeredTabs` keeps the row centred in both directions.
Long localized labels widen individual tabs; when the row overflows, VCL's
existing scroll affordance appears at the mirrored end.

### 3.7 Platform notes

None deliberate: tab behaviour is shared VCL. The pill silhouette replaces the
Windows trapezoid tab in Material drawing only.

### 3.8 Verification hooks

- `nav-tabs-01` — Options-style dialog: capture idle, hover, selected,
  focused, selected-focused tabs; assert `height-tab` = 40 geometry.
- `nav-tabs-02` — disable a tab control with a selected page; assert the
  `@outline`-ringed disabled-selected state on both `Entire` and `MenuItem`.

---

## 4. Notebookbar (ribbon)

### 4.1 Anatomy & tokens

The ribbon chrome variant replaces menubar + twin toolbars with a tab row and a
group area. Prototype anatomy (prototype-only unless noted):

| Region | Size | Tokens |
| --- | --- | --- |
| Tab row | 38px tall, 8px side padding | band `@surface-container`; bottom rule `@outline-variant` × `stroke-thin` |
| Ribbon tab | 6px × 16px padding, top corners rounded 16px | active: `@surface` fill, `@primary` label, 2px `@primary` underline; inactive: transparent, `@on-surface-variant` |
| Menubar toggle | 32×30px icon button, right end | `@on-surface-variant` icon, `corner-small` |
| Group area | 96px tall, 8px padding | `@surface` fill; groups divided by `@outline-variant` × `stroke-thin` rules |
| Big command | 64×72px, 28px icon over 11px label | radius `corner-container` |
| Small command | 34×34px, 20px icon | radius `corner-small` |
| Chip command | 30px tall, 12px side padding | `@surface-container` fill, `@outline-variant` stroke, radius `corner-pill` |
| Group caption | 11px label, `@on-surface-variant`, bottom of group | — |

Command buttons inside groups consume the native `toolbar`/`Button` state set
(hover `@primary-container`, pressed `@primary-hover`, checked `@primary`
outline on `@primary-container`, focus `@primary` × `stroke-standard`, radius
`corner-toolbar`) — implemented in definition.xml (unbuilt); see the actions
chapter ([02-actions.md](02-actions.md)). The tab-row/group-area layout itself
is specified here, not yet implemented natively (notebookbar `.ui` work).

Tab sets per application come from the prototype's `RIBBONTABS` (Writer: File,
Home, Insert, Layout, References, Review, View).

### 4.2 States

Ribbon tabs: inactive → transparent with `@on-surface-variant` label; hover →
`@primary-container` wash; active → `@surface` fill, `@primary` semibold label,
2px `@primary` underline (the underline supplements fill so the active tab is
not colour-only). Disabled tab: `deactiveTextColor → @outline` label, no
underline. Commands follow the toolbar Button table, including the
milestone-10 disabled-checked `@outline` outline.

### 4.3 Interaction

Pointer: single click switches tabs; commands act like toolbar buttons.
Keyboard: `F6`/`Shift+F6` cycle window regions into the tab row; `←`/`→` move
between tabs, `Enter`/`↓` enters the group area; arrows traverse commands in
stable declared order — overflow is a designed state with unchanged keyboard
order, never silent removal. The menubar toggle restores the classic menubar.
Screen readers see a page-tab-list for the row and toolbars/toggle-buttons for
the groups.

### 4.4 Accessibility

Active tab = fill + weight + underline (three cues). Command groups expose
their caption as the accessible container name. All ribbon commands remain
reachable through the menubar toggle for users who rely on menu semantics.

### 4.5 Density

The 38px tab row and 96px group area are fixed in the prototype under both
densities; small commands stay 34×34px. A compact profile may later reduce the
group area, but that is not yet specified anywhere.

### 4.6 RTL & localization

Tab order, group order, and in-group flow mirror. Group captions and chip
labels may grow; groups widen and the area scrolls horizontally rather than
clipping labels.

### 4.7 Platform notes

Windows-first; the ribbon is a LibreOffice notebookbar, not a Windows UI
Ribbon — no contextual tab animation or collapsing pinned state is promised.

### 4.8 Verification hooks

- `nav-ribbon-01` — ribbon chrome in Writer: capture tab row (idle, hover,
  active) and measure the 96px group area.
- `nav-ribbon-02` — keyboard-only traversal `F6 → tabs → group`; record focus
  ring on a small command (`corner-toolbar`, `@primary` × `stroke-standard`).

---

## 5. Sidebar rail

### 5.1 Anatomy & tokens

The rail is the vertical deck switcher on the sidebar's outer edge. Prototype
geometry (prototype-only): the sidebar block is 300px wide, of which the rail
is 48px, on `@surface-container` with an `@outline-variant` × `stroke-thin`
inner rule; the deck fills the remainder on `@surface`. Rail buttons are
38×38px, radius `corner-small`, 22px icons, stacked with a 4px gap below 10px
top padding. Deck entries: Properties, Styles, Gallery, Navigator, Functions.
No dedicated native rail part exists; buttons consume icon-button/toolbar
tokens — specified here, not yet implemented as a distinct native control.

### 5.2 States

| State | Tokens |
| --- | --- |
| Idle | transparent fill, `@on-surface-variant` icon |
| Hover | `@primary-container` fill, `@on-primary-container` icon |
| Active deck | `@primary-container` fill, `@on-primary-container` icon (persistent) |
| Focus | `@primary` × `stroke-standard` ring, `corner-small` (specified here) |
| Disabled | `@outline` icon, no fill |

### 5.3 Interaction

Pointer: click switches decks; clicking the active deck's button collapses the
sidebar to the rail. Keyboard: `Ctrl+F5` (View ▸ Sidebar) toggles/focuses the
sidebar; `F6` reaches it in region order; `↑`/`↓` move along the rail;
`Enter`/`Space` opens the deck; `Esc` returns focus to the document. Each
button exposes a toggle-button role with its deck name and pressed state, plus
a tooltip.

### 5.4 Accessibility

Active deck is fill + icon colour + the visible opened deck itself; tooltips
give text names for icon-only targets; 38px targets exceed the 24px minimum
glyph size and sit in a fixed, predictable hit column.

### 5.5 Density

Rail width (48px) and button size (38px) are density-invariant in the
prototype; deck content follows `--ctrl`/`--fs` (34px/13px compact,
40px/14px comfortable).

### 5.6 RTL & localization

The rail mirrors to the window's leading edge in RTL along with the deck.
Icons do not mirror (they are objects, not directions); tooltips localize.

### 5.7 Platform notes

None deliberate; the rail is shared VCL/sidebar framework chrome.

### 5.8 Verification hooks

- `nav-rail-01` — Writer sidebar: capture rail with active Properties deck,
  hover on Styles; measure 48px rail / 38px buttons.
- `nav-rail-02` — keyboard deck switch via `F6` + arrows; record focus ring.

---

## 6. Calc sheet tabs

### 6.1 Anatomy & tokens

The sheet-tab strip sits between the grid and the status bar. Prototype
geometry (prototype-only): strip 34px tall on `@surface-container` with an
`@outline-variant` × `stroke-thin` top rule, 8px side padding, 2px tab gap.
Each tab is 26px tall with 14px side padding, top corners rounded at
`corner-small`, square bottom (it "docks" into the strip). An Add Sheet button
(28×26px, `corner-small`, 18px `+` icon) ends the row. Native drawing maps
sheet tabs onto the `tabitem` token set — implemented in definition.xml
(unbuilt) at the token level.

### 6.2 States

| State | Tokens |
| --- | --- |
| Inactive | transparent fill, `@on-surface-variant` label, transparent border |
| Hover | `@disabled-container` wash (per `tabitem` `rollover`) |
| Active | `@surface` fill joining the grid, `@primary` semibold label, `@outline-variant` × `stroke-thin` side/top border, open bottom |
| Focus | `@primary` × `stroke-standard` ring (per `tabitem` `focused`) |
| Hidden/protected sheet | strike/lock affordance in the context menu, not colour-only — specified here, not yet implemented |

### 6.3 Interaction

Pointer: click selects; double-click renames in place; drag reorders;
right-click opens the sheet context menu (Insert, Delete, Rename, Move/Copy,
Tab Colour); `Ctrl`+click multi-selects sheets. Keyboard: `Ctrl+Page Down` /
`Ctrl+Page Up` switch sheets; the strip is reachable via `F6`; `Shift+F10`
opens the context menu for the active tab. Screen readers see a
page-tab-list; each tab's name is the sheet name with selected state.

### 6.4 Accessibility

Active tab is fill + weight + border join (not colour-only). A user-set tab
colour renders as an accent strip under the label and never replaces the
selection treatment, so recolouring cannot mask which sheet is active.

### 6.5 Density

The strip (34px) and tabs (26px) are fixed under both prototype densities;
grid columns, by contrast, change width (76px compact / 92px comfortable).

### 6.6 RTL & localization

Tab order mirrors with sheet order; the Add button moves to the mirrored end.
Long sheet names widen tabs; overflow uses the existing scroll buttons at the
strip end rather than shrinking labels.

### 6.7 Platform notes

None deliberate; behaviour is Calc-shared across platforms.

### 6.8 Verification hooks

- `nav-sheettabs-01` — three-sheet document: capture active/inactive/hover
  tabs and the Add button; measure 34px strip and 26px tabs.
- `nav-sheettabs-02` — `Ctrl+Page Down` traversal and rename-in-place entry.

---

## 7. Window title bar

### 7.1 Anatomy & tokens

Prototype anatomy (prototype-only): a 42px bar on `@surface-container` with an
`@outline-variant` × `stroke-thin` bottom rule; 14px leading padding; a 20px
application glyph tinted `@primary`; the document-first title
("Q3 Board Report.odt — LibreOffice Writer" pattern) in `label` type
(13px/500) `@on-surface`; then minimize / maximize / close caption buttons at
46×42px each. The native contract contributes the VCL logical title metrics —
`titleHeight → @height-window-title` (18) and
`floatTitleHeight → @height-floating-title` (14) — and the frame-activation
style slots `activeColor/activeBorderColor → @primary`,
`activeTextColor → @on-primary`, `deactiveColor → @disabled-container`,
`deactiveTextColor → @outline`, `deactiveBorderColor → @outline-variant`; all
implemented in definition.xml (unbuilt). The 42px chrome bar itself is drawn by
the OS/DWM on Windows unless client-side decoration is adopted, which this spec
does not require.

### 7.2 States

| State | Tokens |
| --- | --- |
| Active window | `@surface-container` bar, `@on-surface` title |
| Inactive window | `deactive*` slots: `@disabled-container` / `@outline` / `@outline-variant` |
| Caption hover (min/max) | `@outline-variant` fill |
| Close hover | system signal red with white glyph — a deliberate Windows convention, kept as a platform literal rather than a palette role |
| Floating-window title | `height-floating-title` (14) band, same colour roles |

### 7.3 Interaction

Standard platform behaviour retained: drag to move, double-click to
maximize/restore, `Alt+F4` close, `Alt+Space` system menu, Windows snap
gestures and `Win+←/→`. No custom hit-testing is specified.

### 7.4 Accessibility

The title is the accessible window name (document first, application second).
Caption buttons keep ≥46px targets and platform names. Active/inactive is
conveyed by both fill and text-colour change.

### 7.5 Density

Title metrics are density-invariant native integers (18 / 14); the 42px
prototype bar does not change with density.

### 7.6 RTL & localization

On Windows the caption cluster stays at the trailing edge per platform
mirroring; the icon-and-title group mirrors. Long document names ellipsize in
the middle so both the document extension and application remain visible
(specified here, not yet implemented).

### 7.7 Platform notes

Windows-first: DWM owns the frame; Material supplies colours through the
active/deactive style slots only. The close-hover red is intentionally *not* a
Material palette role.

### 7.8 Verification hooks

- `nav-title-01` — enumerate the off-screen window, capture active vs
  inactive frames, assert `deactive*` slot colours.
- `nav-title-02` — floating toolbar/window title measured at the
  `height-floating-title` (14) metric.

---

## 8. Status bar

### 8.1 Anatomy & tokens

Prototype anatomy (prototype-only for geometry): a 28px bar on
`@surface-container` with an `@outline-variant` × `stroke-thin` top rule, 14px
side padding, and 16px gaps. Left cluster: application status fields in 12px
`label` type, `@on-surface-variant` (Writer: "Page 1 of 3", "842 words, 5,120
characters", "English (USA)", "Default Paragraph Style"; Calc adds
"Average: 1,926; Sum: 15,410"). Right cluster: the numeric zoom readout
("100%") and the zoom slider — a 120px × 4px track (`@outline-variant`,
matching `stroke-track` = 4) with a `@primary` filled portion and a `@primary`
thumb. Natively the slider consumes the `slider` control — `Button` at
`size-compact-control` (28) square, `@primary` fill, radius `corner-control`;
`TrackHorzLeft` `@primary` × `stroke-track`; `TrackHorzRight`
`@outline-variant` × `stroke-track`; focus state `@on-surface` ×
`stroke-standard` — implemented in definition.xml (unbuilt). The status-bar
container itself has no dedicated part; it renders from the `faceColor →
@surface-container` style slot.

### 8.2 States

| Element · state | Tokens |
| --- | --- |
| Field idle | `@on-surface-variant` text |
| Field hover (interactive fields) | `@primary-container` wash, `corner-small` (specified here) |
| Zoom thumb idle | `@primary`, `corner-control` |
| Zoom thumb hover / pressed | `@primary-action-hover` / `@primary-action-pressed`, radius `corner-container` |
| Zoom thumb focus | `@on-surface` × `stroke-standard` ring |
| Disabled slider | `@outline` stroke, `@outline-variant` fill; tracks `@outline-variant` / `@disabled-container` |

### 8.3 Interaction

Pointer: click a field to cycle or open its popup (page count → Go to Page;
language → language menu; zoom readout → Zoom dialog); drag the zoom thumb;
click the track to jump; `Ctrl`+scroll over the document zooms in sync.
Keyboard: the bar joins the `F6` region cycle; `←`/`→` step the focused zoom
slider (mirrored in RTL), `Home`/`End` jump to limits; every field's function
is also reachable through menus (View ▸ Zoom, Tools ▸ Word Count), so the bar
is never the sole path. Screen readers see a status-bar role; fields expose
name and value text; the slider exposes a value with current/min/max.

### 8.4 Accessibility

Zoom level is always shown as text next to the slider, so the control is never
value-by-position only. 12px field text in `@on-surface-variant` on
`@surface-container` passes 4.5:1 in both palettes. Status changes (word
count, save state) must also be exposed as accessible value changes, not just
repaints.

### 8.5 Density

The 28px bar height and 120×4px slider are fixed under both prototype
densities; field text follows `--fs` only in the prototype.

### 8.6 RTL & localization

Field order mirrors; the zoom cluster moves to the mirrored end; slider
direction follows reading direction. Long localized field text ellipsizes
per-field without pushing the zoom cluster out of view; number/percent formats
localize.

### 8.7 Platform notes

None deliberate; the status bar is shared VCL chrome. The miniature 12px round
thumb in the prototype's status bar is a compact presentation of the native
`slider` part contract, whose `Button` geometry (`size-compact-control`)
remains authoritative for hit-testing.

### 8.8 Verification hooks

- `nav-status-01` — Writer at 100%: capture the 28px bar, field cluster, and
  zoom slider; assert `@primary` fill ratio matches the zoom value.
- `nav-status-02` — keyboard zoom via `F6` + arrows; capture the focused-thumb
  `@on-surface` ring; verify the text readout updates with the slider.

---

Cross-references: shared button and toolbar states in
[02-actions.md](02-actions.md); container/scrollbar rules in
[06-containers.md](06-containers.md); the evidence contract in
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md). Nothing in this
chapter is build- or runtime-verified; the verified-capture count is 0.
