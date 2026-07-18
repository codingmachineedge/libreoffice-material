# 09 — Start Center

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

The Start Center is the suite's launch surface: it opens when no document
window exists and provides recent-document access, template browsing, and
creation entry points for all six applications. Normative inputs are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behavior contract),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, unbuilt), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). The existing native source slice lives in
[`sfx2/uiconfig/ui/startcenter.ui`](../../sfx2/uiconfig/ui/startcenter.ui) and
[`sfx2/source/dialog/backingwindow.cxx`](../../sfx2/source/dialog/backingwindow.cxx);
section 9.10 maps this spec onto it. Implementation status is labelled per
feature as *implemented in definition.xml (unbuilt)*, *prototype-only*, or
*specified here, not yet implemented*.

---

## 9.1 Layout & regions

The surface is a two-region horizontal split. All pixel values below are taken
from the prototype's `startBody()` renderer; the prototype frames the surface
at 600 px height inside its mock window.

| Region | Size | Surface | Status |
| --- | --- | --- | --- |
| Navigation column | 236 px wide, fixed (`flex:0 0 auto`), 10 px inner padding | `@surface-container` fill, trailing hairline `@outline-variant` at `stroke-thin` | prototype-only (native slice paints `workspaceColor` → `@surface-container-low`; see 9.10) |
| Content region | Remaining width, scrollable, 26 px top/bottom × 28 px side padding | `@surface` | prototype-only (native slice: `windowColor` → `@surface`) |

### Navigation column (236 px)

Top-to-bottom anatomy, with exact prototype metrics:

| Element | Metrics | Tokens | Status |
| --- | --- | --- | --- |
| **Open File** pill | 44 px high, `corner-pill` (20), 12 px horizontal padding, 14 px icon gap, 20 px `folder_open` icon, weight-600 14 px label, 6 px bottom margin | `@primary` fill, `@on-primary` text; hover `@primary-action-hover`, pressed `@primary-action-pressed` | pill states implemented in definition.xml (unbuilt) as `pushbutton`/`Entire` `extra="action"`; layout prototype-only |
| **Remote Files** item | 40 px high, `corner-pill`, 12 px padding, 20 px `cloud` icon at `@on-surface-variant` | transparent fill, `@on-surface` text; hover `@primary-container` / `@on-primary-container` | prototype-only |
| Separator | 1 px (`stroke-thin`) rule, 8 px vertical × 6 px horizontal margin | `@outline-variant` | prototype-only |
| View items (**Recent Documents**, **Templates**) | 40 px high, `corner-pill`, 12 px padding, 20 px icons (`history`, `grid_view`) | selected: `@primary-container` fill, `@on-primary-container` text/icon; idle: transparent, `@on-surface` text, `@on-surface-variant` icon | prototype-only; native equivalents are the `open_recent`/`templates_all` toggle buttons |
| **Create** heading | weight-700 11 px, letter-spacing 0.08 em, uppercase, padding 6 px 10 px 8 px | `@on-surface-variant` | prototype-only |
| Create list (six rows) | 40 px rows, `corner-container` (12), 10 px padding, 12 px gap; leading **28 × 28 px app chip** at `corner-small` (8) holding an 18 px icon | chip: `@primary-container` fill, `@on-primary-container` icon; row hover: `@primary-container` / `@on-primary-container` | prototype-only |
| Footer (**Help**, **Extensions**) | two equal-width 34 px buttons, `corner-pill`, weight-500 12 px | transparent, `@on-surface-variant` text; hover `@primary-container` | prototype-only |

The six create rows are Writer Document (`article`), Calc Spreadsheet
(`table_chart`), Impress Presentation (`co_present`), Draw Drawing (`brush`),
Math Formula (`functions`), and Base Database (`database`). Each row launches
the corresponding module; a module absent from the installation renders its row
disabled (the native slice already calls `set_sensitive` from
`SvtModuleOptions` per application).

### Home header

| Element | Metrics | Tokens | Status |
| --- | --- | --- | --- |
| Title "Home" | weight-700 **30 px**, line-height 1.1, letter-spacing −0.02 em, 4 px bottom margin | `@on-surface`; native `title` typography role (120 % scale, semibold minimum) is the closest implemented mapping | header exists in native slice (`welcome_title`, bold, 1.75 × scale attribute); exact prototype metrics prototype-only |
| Subtitle | 14 px, line-height 1.5, 20 px bottom margin; text "Open recent work, explore templates, or create a new document." | prototype paints `@on-surface-variant`; the native slice routes it through `labelTextColor`, which the Material style maps to `@on-surface` — a deviation to reconcile | implemented in native slice (`welcome_subtitle`), colour mapping differs |

### Filter + search row

A single 20 px-bottom-margin flex row with 12 px gaps:

| Element | Metrics | Tokens | Status |
| --- | --- | --- | --- |
| Filter combo | 38 px high, `corner-small` (8), padding 0 10 px 0 14 px, 13 px label, 18 px `expand_more` chevron; label **All Documents** (recent view) or **All Templates** (templates view) | `@outline` border at `stroke-thin` on `@surface`, `@on-surface` text | prototype-only as drawn; the native `cbFilter` combo resolves the implemented `combobox`/`Entire` + `ButtonDown` parts in definition.xml (unbuilt) |
| Search field | 44 px pill, `corner-pill`, leading 20 px `search` icon, 14 px input text, trailing clear button (28 × 28, `corner-small`), regex mode toggle (`.*`, 28 px high, weight-700 12 px monospace), and builder toggle (30 × 30, `tune` icon) | `@surface-container` fill, `@outline-variant` border; invalid pattern: 2 px `error` border; regex mode text switches to a monospace stack | prototype-only; shared search anatomy is specified in [04-inputs](04-inputs.md) |
| Actions button | 38 × 38 px icon button, `corner-small`, 20 px `more_vert` icon | transparent, `@on-surface-variant`; hover `@primary-container` | prototype-only; native `mbActions` menu button hosts Clear Recent Documents / Clear Unavailable Files |

The regex builder popover opens 6 px below the field: `corner-container`
radius, 14 px padding, 340 px maximum height, elevation shadow
`0 16px 40px rgba(0,0,0,.28)`, five token groups (Anchors, Classes,
Quantifiers, Groups, Escapes), `i`/`g`/`m`/`s` flag toggles, and a live status
line (`N of M match /pattern/flags`, or "Invalid pattern: …" in `error` when
compilation fails). The Start Center keeps an independent search state
(`S.rx.start` in the prototype), so a pattern typed here never leaks into
Find & Replace or the Features catalog.

### Document card grid

Cards fill the content region in a responsive grid:
`repeat(auto-fill, minmax(184px, 1fr))` with 16 px gaps — the **184 px minimum
card width** governs reflow at every window width.

Card anatomy (prototype-only; the native equivalents are the
`RecentDocsView`/`TemplateDefaultView` thumbnail views, see 9.10):

| Region | Metrics | Tokens |
| --- | --- | --- |
| Card container | `corner-container` (12), clipped overflow | `@outline-variant` border at `stroke-thin`, `@surface` fill |
| Preview area | **118 px** high, centred content, bottom hairline `@outline-variant` | `@surface-container-low` fill |
| Page thumbnail | 74 × 92 px mock page, 6 px radius, shadow `0 3px 8px rgba(0,0,0,.10)`, placeholder text bars | `@surface` fill, `@outline-variant` border and bars |
| App badge | 26 × 26 px, `corner-small`, 8 px from top-right, 16 px app icon | `@primary-container` fill, `@on-primary-container` icon |
| Caption | padding 10 px 12 px 12 px; title weight-500 13 px single line with ellipsis; meta 11 px, 2 px below | title `@on-surface`, meta `@on-surface-variant` |
| Hover | border colour steps to `@primary`; elevation shadow `0 6px 18px rgba(0,0,0,.12)` | hover is border + shadow, never colour-only |

Meta text formats: recent documents show `<Module> · <relative time>` (e.g.
"Writer · 2 hours ago"); templates show `<Module> template`.

## 9.2 Chrome variants

The Start Center has **no classic/ribbon distinction**: it renders under the
standard menubar only, in both chrome modes. The prototype's chrome toggle
changes document surfaces (Writer, Calc, …) but leaves `startBody()`
untouched; the native `BackingWindow` likewise sits beneath the ordinary
menubar frame. Theme variants do apply: light and dark resolve the Material
palettes in definition.xml; resolved high contrast bypasses Material drawing
entirely and restores the captured native `StyleSettings` baseline (the
prototype's 2 px `--bw` high-contrast borders illustrate intent only).

## 9.3 Recent vs Templates views

One state bit (`scView ∈ {recent, templates}`) switches the content region;
the navigation column marks the active view item with `@primary-container`.

| Aspect | Recent Documents | Templates |
| --- | --- | --- |
| Card source | Pinned + recently used files (native: `RecentDocsView`) | Installed template store (native: `TemplateDefaultView`) |
| Filter label | All Documents | All Templates |
| Search placeholder | "Search recent" | "Search templates" |
| Meta line | Module · relative time | Module template |
| Actions menu | Clear Recent Documents, Clear Unavailable Files (native `clearmenu`) | Manage Templates (native template menus) |

Switching views resets neither the search pattern nor the filter — each view
keeps its own working set but the single Start Center search state applies to
whichever view is visible (prototype behavior; specified here as target).

## 9.4 Key user flows

- **Open an existing file.** Click the Open File pill (or `Alt+O` via the
  native `_Open File` mnemonic) → system file dialog. Enter on a focused
  recent card opens that document directly.
- **Resume recent work.** Default view is Recent Documents; the first card is
  the most recent file. Keyboard: `F6` into the thumbnail grid, arrows to
  select, `Enter` to open.
- **Create a new document.** Click a create row; the module chip identifies
  the application at a glance. Disabled rows communicate uninstalled modules
  without hiding them.
- **Find by pattern.** Type in the search pill for literal case-insensitive
  matching; toggle `.*` for regex mode; open the builder to insert tokens and
  flags with a live match count.
- **Housekeeping.** Actions (`more_vert`) exposes destructive list operations
  behind a menu; they never appear as top-level buttons.

## 9.5 Empty, loading, and error states

| State | Treatment | Status |
| --- | --- | --- |
| No search matches | Full-width grid cell, 34 px padding, centred 13 px `@on-surface-variant` text: "No recent match this pattern." / "No templates match this pattern." | prototype-only |
| Invalid regex | Search border becomes 2 px `error`; builder status line shows the compiler message; the grid keeps the last valid result set rather than emptying | prototype-only |
| No recent documents (first run) | Grid area shows an invitation to create or open a document; the Create list remains the primary affordance | specified here, not yet implemented |
| Unavailable file thumbnails | Cards for missing files keep their caption but dim the preview; Clear Unavailable Files removes them | specified here, not yet implemented (menu item exists natively) |
| Slow thumbnail load | Preview area holds the `@surface-container-low` fill as a placeholder; no spinner for sub-second loads, indeterminate progress only past one second | specified here, not yet implemented |

## 9.6 Density & adaptive width

The prototype's Start Center metrics are **density-invariant**: the 44 px
pill, 40 px rows, 38 px filter row, and card geometry do not change with the
compact/comfortable toggle (`--ctrl` 34/40 px, `--row` 26/32 px elsewhere).
This is a deliberate stance for a launch surface — browsing comfort over grid
density — but a compact profile remains *specified here, not yet implemented*:
compact may reduce view/create rows from 40 px to 34 px and the card gap from
16 px to 12 px, while the 184 px minimum card width and 118 px preview height
hold in both profiles. The native metric layer intentionally has no density
selection yet (see `MATERIAL_DESIGN.md`, desktop-density section).

Adaptive width: the navigation column is fixed at 236 px and never collapses;
the card grid absorbs all remaining width, adding a column each time
`184 px + 16 px` of space becomes available. At very narrow widths the grid
degrades to a single card column before the window's minimum size applies.
Long localized labels in the column ellipsize rather than wrap (the native
`.ui` gives labels `halign` start and truncation).

## 9.7 Keyboard map

The native `BackingWindow::PreNotify` already implements the pane-cycling
keys; the rest restates existing VCL/weld behavior under the target layout.

| Keys | Action | Source |
| --- | --- | --- |
| `F6` | From the column into the visible thumbnail view | native `backingwindow.cxx` |
| `Shift+F6` | From the thumbnail view back to the Open button | native `backingwindow.cxx` |
| `Ctrl+F6` | Focus the visible thumbnail view | native `backingwindow.cxx` |
| `Tab` / `Shift+Tab` | Next/previous control within the focused pane | existing VCL |
| `Alt+O` | Open File (mnemonic `_Open File`) | native `startcenter.ui` |
| Arrow keys | Move card selection in the grid | existing `ThumbnailView` |
| `Enter` / `Space` | Open the selected card / activate the focused button | existing VCL |
| Global accelerators (`Ctrl+O`, `Ctrl+N`, `Ctrl+Q`, …) | Forwarded to the module accelerator table | native `AcceleratorExecute` path |
| `Esc` | Close the regex builder or actions menu | prototype-only (builder); existing VCL (menus) |

## 9.8 Accessibility notes

- Roles: the column controls are buttons/toggle buttons; the view switch pair
  must expose a pressed/selected state (native toggle buttons already do);
  cards are list items of a focusable grid with `SELECTED`/`FOCUSED` states
  via the existing `ThumbnailView` accessible implementation.
- Names: every card's accessible name is its full document/template name plus
  the meta line, not the truncated visual label. Icon-only controls (Actions,
  builder, clear) carry explicit names; the prototype already sets
  `aria-pressed` on the regex toggle and `aria-expanded` on the builder.
- Focus: a persistent visible indicator is required on every stop; native
  pill/field focus uses the definition-backed `Focus` parts (`@primary` at
  `stroke-standard`, 4 % inset) — implemented in definition.xml (unbuilt).
- Colour independence: the selected view item pairs tonal fill with the
  toggle's exposed state; card hover pairs the `@primary` border with
  elevation; regex errors pair the `error` border with a text message.
- Contrast: all text/fill pairs use the palette's contrast-checked role pairs
  (`on-primary` on `primary`, `on-primary-container` on `primary-container`).
  High contrast bypasses Material to the native baseline. No accessibility
  result is claimed — the suite is unbuilt.

## 9.9 RTL & localization

In RTL locales the split mirrors: navigation column on the right with its
hairline on the left, header and captions right-aligned, the app badge moves
to the preview's top-left, and the search pill's leading icon and trailing
controls swap ends. Directional glyphs mirror semantically (`expand_more`
chevrons are direction-neutral; the `history` and `folder_open` glyphs do not
mirror). Relative-time meta strings and the "N of M match" status are fully
translatable, with numerals following the locale. The 236 px column must
tolerate long translations by ellipsizing labels — German
"Tabellendokument erstellen"-class strings must not widen the column.
Verification is part of the localization matrix, not inferred.

## 9.10 Relationship to the native source slice

The first native milestone restyled the existing Start Center rather than
replacing it; the prototype's target anatomy maps onto it as follows.

| Target element | Native counterpart | Notes |
| --- | --- | --- |
| Navigation column | `frame1`/`all_buttons_box`/`buttons_box` in `startcenter.ui` (6 px margins, 8 px spacing; `box1` spacing 16) | background from `GetWorkspaceColor()` → `workspaceColor` → `@surface-container-low`; the prototype uses `@surface-container` — one tonal step to reconcile |
| Open File pill | `open_all` button (`_Open File`) | draws as `pushbutton`/`Entire`; the `extra="action"` filled-pill states exist in definition.xml (unbuilt). Marking this specific button as the surface's action button is not yet wired |
| Remote Files | `open_remote` button | present natively; pill styling prototype-only |
| View items | `open_recent`, `templates_all` `GtkToggleButton`s | toggle semantics native; pill-with-tonal-selection styling prototype-only |
| Create list + 28 px chips | `writer_all` … `database_all` buttons with 32 px document icons | chip anatomy prototype-only; per-module `set_sensitive` already native |
| Home header | `welcome_header` with `welcome_title` (bold, 1.75 × scale) and `welcome_subtitle`, added by the Material slice | title colour `GetWindowTextColor()` → `@on-surface`; subtitle uses `labelTextColor` → `@on-surface`, versus prototype `@on-surface-variant` |
| Filter combo | `cbFilter` (`GtkComboBoxText`) | resolves implemented `combobox` parts in definition.xml (unbuilt) |
| Actions menu | `mbActions` menu button + `clearmenu` | native |
| Search + regex row | — | no native counterpart; specified here, not yet implemented |
| Card grid | `all_recent` (`RecentDocsView` in `scrollrecent`) and `local_view` (`TemplateDefaultView` in `scrolllocal`) | the Material slice reroutes both views' fill/text from `officecfg` Start Center colours to `StyleSettings` (`GetWindowColor`/`GetWindowTextColor` → `@surface`/`@on-surface`; highlights → `@primary-container`/`@on-primary-container`); card anatomy (118 px preview, badge, hover elevation) prototype-only |
| Right box padding | 24 px margins, 12 px spacing added by the slice | prototype uses 26 × 28 px; near-equivalent, to converge |

All native behavior above is **source only, unbuilt, and unexecuted**; it
activates only under `VCL_DRAW_WIDGETS_FROM_FILE=1` with
`VCL_FILE_WIDGET_THEME=material` once a build exists.

## 9.11 Platform notes

Windows-first: the Material initialization path is wired into the Windows VCL
backend (`vcl/win/gdi/salgdi.cxx`), with printer graphics excluded. The Start
Center window frame, minimize/maximize/close controls, and the system file
dialog opened by Open File remain platform-native by design. On backends
without file-defined widgets the surface falls back to existing native
drawing; no Start Center behavior may depend on Material rendering being
active. There are no other deliberate platform differences for this surface.

## 9.12 Verification checkpoints

Per the evidence contract in
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) — off-screen
desktop, ownership-proven process, `PrintWindow` captures registered with
SHA-256 per exact commit. Current verified-capture count: **0**.

| ID | Checkpoint | Proves |
| --- | --- | --- |
| SC-01 | Capture at 1280 × 800, light theme, default state | 236 px column, `@surface-container`-family fill, header hierarchy, card grid |
| SC-02 | Open File pill idle/hover/pressed/focused captures | `extra="action"` pushbutton states and `Focus` part from definition.xml |
| SC-03 | Toggle Recent ↔ Templates | view switch, selected-item tonal state, filter label change |
| SC-04 | Filter combo open capture | `combobox` `Entire`/`ButtonDown`/`ListboxWindow` parts |
| SC-05 | Width sweep 720 → 1600 px | card reflow at 184 px + 16 px increments; no horizontal scroll |
| SC-06 | Cleared recent list | empty state rendering and Create-list prominence |
| SC-07 | Dark and high-contrast captures | dark palette resolution; HC bypass to native baseline |
| SC-08 | Scripted `F6`/`Shift+F6`/`Ctrl+F6` traversal | native pane cycling with visible focus at every stop |
| SC-09 | RTL locale capture | mirrored column, badges, and search field |
| SC-10 | Accessibility tree dump of the surface | roles, names, and toggle/selection state exposure |

Until these are registered, everything in this chapter remains a target.
