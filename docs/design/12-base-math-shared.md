# 12 — Base, Math & shared suite surfaces

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This chapter specifies the two remaining application shells — the Base database
window and the Math formula editor — and the two shared suite surfaces that the
interactive reference introduces as design concepts: the **Features** command
catalog and the **Version history** browser. It closes with the suite-wide
consistency rules that any new surface must satisfy. Normative inputs are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behaviour contract),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, unbuilt), and
[`site/prototype.html`](../../site/prototype.html) (hand-built interactive
mockup, not a build capture). Implementation status is labelled per feature as
*implemented in definition.xml (unbuilt)*, *prototype-only*, or *specified
here, not yet implemented*.

Shared components are specified in their own chapters — buttons in
[02 — Actions](02-actions.md), search and text fields in
[04 — Inputs](04-inputs.md), menus/tabs/toolbars in
[05 — Navigation](05-navigation.md), lists/trees/tables/cards in
[06 — Containers](06-containers.md). This chapter defines only their
composition into surfaces.

---

## 12.1 Base — database shell

### Layout & regions

The Base window is a two-pane shell: a fixed database navigation rail and a
scrolling object workspace. Prototype region values (the prototype renders the
body region at 560 px tall under the shared chrome):

| Region | Size & treatment | Tokens | Status |
| --- | --- | --- | --- |
| Database nav rail | 220 px fixed width; `@surface-container` fill; right hairline `@outline-variant` at `stroke-thin`; 12 px vertical / 8 px horizontal padding | `@surface-container`, `@outline-variant`, `stroke-thin` | prototype-only |
| Rail kicker ("Database") | Uppercase label, 11 px/700, 0.06 em letter-spacing, `@on-surface-variant` | `label` role styling | prototype-only |
| Rail entries (Tables, Queries, Forms, Reports) | Full-width buttons, 40 px tall, 0 12 px padding, 12 px icon gap, 20 px icon, 13 px/500 label, `corner-container` (12 px) radius | selected `@primary-container` / `@on-primary-container`; rest transparent / `@on-surface` | prototype-only |
| Object workspace | Remaining width, `@surface` fill, 20 px 24 px padding, own scroll region | `@surface` | prototype-only |
| Section heading ("Tables") | 16 px/600 `@on-surface`, 16 px bottom margin | `title` role styling | prototype-only |
| Object card grid | `repeat(auto-fill, minmax(150px, 1fr))`, 12 px gap, 26 px bottom margin | — | prototype-only |
| Object card | Column layout, 18 px 12 px padding, `@outline-variant` hairline, `corner-container` radius, `@surface` fill; 44 × 44 px icon tile (`corner-container`, `@primary-container` / `@on-primary-container`, 24 px glyph); 13 px/500 `@on-surface` label | see row | prototype-only |
| Data table (record browser) | Rounded `corner-container` container with `@outline-variant` hairline, clipped corners; header row + striped body rows | see § States | prototype-only composition; header parts implemented in definition.xml (unbuilt) |

Data-table anatomy, from the prototype's Customers browser:

- **Header row** — `@surface-container` fill, bottom hairline
  `@outline-variant`; cells 10 px 14 px padding, 12 px/600
  `@on-surface-variant`; flexible column ratios (2 : 2 : 1 for
  Company / Contact / City in the reference).
- **Body rows** — cells 10 px 14 px padding, 13 px/400 `@on-surface`;
  alternate rows filled `@surface-container-low` (zebra striping); hairline
  `@outline-variant` separators between rows, none after the last row.

The native mapping for the header is the `listheader` control — `Button` part
(`@surface-container` fill, `@outline-variant` hairline, `corner-small`
radius; `rollover` steps the fill to `@primary-container`; `pressed` to
`@primary-hover` with a `@primary` stroke) and `Arrow` part with `extra="up"`
and `extra="down"` sort chevrons in `@on-surface-variant` at
`stroke-standard` — implemented in definition.xml (unbuilt). Alternating-row
colour resolves from the Material profile through the fifth-milestone
`StyleSettings` mapping — implemented in definition.xml (unbuilt). Tree views
elsewhere in Base (relation and query designers) use the net-less Material
tree: `listnode` disclosure at `size-tree-node` (20 px) and the empty
`listnet`/`Entire` state that suppresses connector nets — implemented in
definition.xml (unbuilt).

### Chrome variants

Classic chrome gives Base the shared menubar plus standard and formatting
toolbars (`menubar`, `toolbar` parts — implemented in definition.xml,
unbuilt). Ribbon chrome uses the Base tab set **File, Home, Insert, Tools,
View** (prototype `RIBBONTABS.base`) rendered with the shared notebookbar
treatment from [05 — Navigation](05-navigation.md). Both variants expose
identical commands; the ribbon is a re-grouping, never a subset.

### Key user flows

1. **Switch object container.** Selecting Tables, Queries, Forms, or Reports
   swaps the workspace content; exactly one rail entry is selected at all
   times, shown by the `@primary-container` treatment plus an API-exposed
   selected state (non-colour carrier).
2. **Open an object.** Cards respond to hover (border steps to `@primary`,
   fill to `@primary-container`) and open on double-click or `Enter`.
3. **Browse records.** The striped table supports column sort via header
   click / `Enter` on a focused header, with sort direction shown by the
   `listheader`/`Arrow` chevron and announced as a state change.

### Empty, loading & error states

- **Empty container** — centred empty-state card per
  [07 — Feedback](07-feedback.md): icon tile, one-line explanation, and a
  primary action ("Create Table…"). Specified here, not yet implemented.
- **Loading (opening a database or large record set)** — determinate progress
  uses the native `progress` control with the `TrackHorzArea` full-track
  anatomy (implemented in definition.xml, unbuilt); indeterminate connection
  waits use the shared indeterminate treatment.
- **Connection error** — inline banner using `@error-container` /
  `@on-error-container` naming both the failure and the recovery action
  ("Edit connection settings…"), per the accessibility contract. Specified
  here, not yet implemented.

### Density & adaptive width

Prototype density resolves the shared browser-only variables: rows `--row`
26 px compact / 32 px comfortable; controls `--ctrl` 34 / 40 px; base font
`--fs` 13 / 14 px; line height 1.35 / 1.45. The 220 px rail width is
density-invariant. Below the medium width class the rail collapses to an
icon-only 56 px rail with tooltips (specified here, not yet implemented);
the card grid reflows automatically through its 150 px minimum column. The
native metric layer does not yet implement density selection.

### Keyboard map

| Key | Action |
| --- | --- |
| `F6` / `Shift+F6` | Cycle panes: rail → workspace → status bar |
| `Up` / `Down` | Move rail selection; move record selection in the table |
| `Enter` | Open focused rail entry, card, or record |
| `Tab` | Next control inside the active pane |
| `Ctrl+F` | Record search (shared search field, [04 — Inputs](04-inputs.md)) |
| `Alt`+mnemonic | Menu access; mnemonics underline on `Alt` per platform rule |

### Accessibility notes

The rail is exposed as a list with `selected` state per entry; cards expose
name ("Customers, table") and the double-click affordance as a default
action; the record table exposes row/column headers so screen readers
announce cell coordinates. Striping is decorative: row identity never relies
on the `@surface-container-low` stripe alone. Focus uses the shared
`@primary` `stroke-standard` indicator at `corner-focus` radius.

### RTL & localization

Per the suite rule, an RTL interface moves the 220 px database rail to the
window's trailing edge and mirrors the card grid's fill direction; the record
table mirrors like any data grid ([06 §6.3](06-containers.md)) with logical
keyboard motion. Object names (tables, queries, forms, reports) are user data
and render in their own directionality inside mirrored chrome. Long localized
rail labels truncate with a tooltip carrying the full name. Specified here,
not yet implemented.

### Verification checkpoints

Per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md), once a
build exists: capture the Base shell on the off-screen desktop in light,
dark, and high-contrast at 100 % / 200 % scale; verify rail selection and
card hover states from keyboard-only traversal; verify `listheader` sort
chevron states (`extra="up"` / `extra="down"`) against the definition;
verify zebra striping resolves from the profile's alternating-row slot and
disappears cleanly in high contrast (native baseline restored).

---

## 12.2 Math — formula editor

### Layout & regions

Math is a three-region vertical shell: rendered formula canvas, monospace
command editor, and elements panel. Prototype values (560 px body):

| Region | Size & treatment | Tokens | Status |
| --- | --- | --- | --- |
| Formula canvas | Flexible top region, `@surface-container-low` fill, content centred, 24 px padding | `@surface-container-low` | prototype-only |
| Render card | Auto-sized card on the canvas: `@surface` fill, `@outline-variant` hairline, `corner-container` radius, 44 px 60 px padding; formula set in a serif face at 34 px, 1.4 line height, `@on-surface` | see row | prototype-only |
| Command editor strip | Bottom region behind a top hairline `@outline-variant`; editor pane takes remaining width with 14 px 18 px padding | `@outline-variant`, `stroke-thin` | prototype-only |
| Command editor | Monospace multiline field, ≥ 80 px min-height, `@outline` hairline at `stroke-thin`, `corner-container` radius, 12 px 14 px padding, 15 px text at 1.6 line height, `@surface` fill | maps to `multilineeditbox`/`Entire` | field states implemented in definition.xml (unbuilt); geometry prototype-only |
| Elements panel | 240 px fixed width, left hairline `@outline-variant`, 14 px padding; "Elements" title 13 px/600 `@on-surface` | — | prototype-only |
| Symbol grid | 5 equal columns, 6 px gap; each cell square (1 : 1), `@outline-variant` hairline, `corner-small` (8 px) radius, `@surface` fill, serif glyph at 18 px `@on-surface` | see row | prototype-only |

The reference grid shows twenty symbols (`+ − × ÷ ± √ ∑ ∫ ≠ ≤ ≥ ∞ π θ ∂ α β Δ
∈ →`); the real panel is category-paged (Unary/Binary, Relations, Set
Operations, Functions, …) with the same cell anatomy. The reference editor
content `E = m c^2 newline sum from{i=1} to{n} x_i` illustrates the StarMath
markup the editor holds; the render card shows its typeset result.

The command editor consumes the native `multilineeditbox` contract: enabled
`@outline` / `@surface` at `stroke-thin`, focused `@primary` at
`stroke-standard`, disabled `@outline-variant` / `@disabled-container` — all
at `corner-container` radius — implemented in definition.xml (unbuilt). The
serif rendering face on the canvas is the document face, not chrome: the
typography contract's family preservation applies to UI roles only and never
restyles formula output.

### Chrome variants

Classic chrome: menubar plus standard toolbar. Ribbon chrome: the reduced
Math tab set **File, Home, View** (prototype `RIBBONTABS.math`). Math has no
formatting toolbar; formula appearance is controlled by markup and the
Format menu.

### Key user flows

1. **Type markup.** Text entered in the command editor re-renders the canvas
   after the idle re-render interval; rendering never blocks typing (motion
   contract: no decorative animation on routine typing).
2. **Insert an element.** Clicking a symbol cell (hover: `@primary-container`
   fill, `@on-primary-container` glyph, `@primary` border) inserts its markup
   at the caret and returns focus to the editor.
3. **Navigate placeholders.** `F4` moves to the next `<?>` placeholder in the
   markup; the canvas highlights the corresponding sub-expression. Specified
   here, not yet implemented.

### Empty, loading & error states

- **Empty document** — the canvas shows a dimmed placeholder formula and a
  one-line hint pointing at the editor; the editor holds focus on open.
- **Markup error** — the offending token is underlined in the editor using
  the error text slot, and an inline message in `@on-error-container` on
  `@error-container` names the token and position; the last valid render
  stays on the canvas rather than blanking. Specified here, not yet
  implemented.
- **Loading** — Math documents are small; no dedicated loading state beyond
  the shared busy indicator.

### Density & adaptive width

Editor row metrics follow the shared density table (13 / 14 px base text;
1.35 / 1.45 line height); the symbol grid keeps five columns at both
densities because cell size derives from the fixed 240 px panel. Below the
compact width class the elements panel folds into a toggleable overlay
(View ▸ Elements), and the editor strip keeps a 40 % minimum height share so
markup never collapses below roughly three lines. Specified here, not yet
implemented.

### Keyboard map

| Key | Action |
| --- | --- |
| `F6` / `Shift+F6` | Cycle: canvas → editor → elements panel |
| `F4` | Next placeholder (`<?>`) in markup |
| Arrow keys | Caret movement in editor; cell movement in the symbol grid |
| `Enter` / `Space` | Insert focused symbol from the grid |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo markup edits |

### Accessibility notes

The editor is a standard multiline text control with full caret and
selection exposure. Symbol cells expose their command name ("sum", "integral")
— never only the glyph — so screen readers do not depend on symbol font
rendering. The rendered canvas exposes the formula's linear (markup) form as
its accessible value. Error identification pairs position + token + recovery
text, satisfying the error clause of the accessibility contract.

### RTL & localization

Chrome mirrors per the suite rule (elements panel to the leading edge in an
RTL interface), but the markup command editor itself stays left-to-right —
StarMath markup is a formal notation, like the regex-builder preview
([04 §5](04-inputs.md)), and reordering its tokens visually would corrupt
meaning. The rendered formula follows mathematical layout conventions
independent of UI direction. The symbol grid mirrors its fill direction;
symbol names (not glyph shapes) localize. Specified here, not yet implemented.

### Verification checkpoints

Headless checks: `multilineeditbox` enabled/focused/disabled captures against
the definition tuples; symbol-grid keyboard traversal producing the same
insertions as pointer clicks; markup-error state capture verifying the error
container pair and the preserved last-good render; light/dark/HC and
100 % / 200 % scale rows from the evidence matrix.

---

## 12.3 Features — command catalog (shared surface, design concept)

The Features surface is a suite-level command inventory: every UNO command in
the product, searchable and scoped by application. It is prototype-only as a
surface; it consumes only shared components, so a native implementation
introduces no new controls.

### Layout & regions

Three panes at 600 px prototype body height: scope rail (220 px), capped
command list (flexible), detail pane (300 px).

| Region | Size & treatment | Status |
| --- | --- | --- |
| Scope rail | 220 px; `@surface-container`; right hairline `@outline-variant`; "Applications" kicker (11 px/700 uppercase, 0.08 em tracking) | prototype-only |
| Scope entries | 36 px tall, 0 10 px padding, 10 px gap, 20 px icon, 13 px/500 label, `corner-container` radius; trailing per-scope **count** in 11 px monospace at 70 % opacity; selected `@primary-container` / `@on-primary-container` | prototype-only |
| List header | Title "Features" 24 px/700 (−0.02 em) + live "N of M commands" summary 13 px `@on-surface-variant`; full-width shared search field (44 px pill, `@surface-container` fill, regex mode + builder per [04 — Inputs](04-inputs.md)); bottom hairline | prototype-only |
| Command list | Scroll region, 8 px 12 px padding; rows 9 px 12 px padding at `corner-container` radius; leading 8 × 8 px `@primary` square (2 px radius); name 13 px/500 single-line ellipsis; trailing module chip 11 px/500, 3 px 8 px padding, `corner-pill` radius, `@surface-container` fill, `@on-surface-variant` text | prototype-only |
| Detail pane | 300 px; `@surface-container`; left hairline; 18 px padding; scope · category kicker; command name 22 px/700; UNO identity chip (`@surface` fill, hairline, `corner-container`, 12 px monospace); token note card (`@primary-container` / `@on-primary-container`, 14 px padding); full-width 44 px "Run command" filled pill (`@primary` / `@on-primary`) | prototype-only |

Eleven scopes are defined: All features, Common, Writer, Calc, Draw &
Impress, Charts, Math, Base, Reports, Basic IDE, and Bibliography. The data
source is [`site/prototype-features.json`](../../site/prototype-features.json),
a 2,433-row mirror of the LibreOffice command inventory with rows of the form
`[name, scope, category, uno-command]`; a curated fallback list serves
contexts where the catalog cannot be fetched.

### Selection identity (normative)

Display names repeat across modules ("Insert Table" exists in more than one
application), so a row's selection identity is the compound key
**UNO command + U+241F (unit separator) + display name** — never the name
alone and never a list index. Stale or transport-missing selections reconcile
in a fixed order: match the key in the filtered list, then in the full
catalog, then fall back to the first filtered row, then the first catalog
row; the resolved key is written back so the state is always a real,
uniquely-keyed row. Any native implementation must preserve this identity
rule (specified here, not yet implemented natively).

### Capped list (normative)

The list renders at most **400** matches, then appends a non-interactive
notice: "Showing the first 400 matches — refine your search to narrow
further." The "N of M commands" summary always reports the true match count,
so the cap never silently hides results.

### Key user flows

Scope filtering (rail), text/regex search (shared search field with match
counters), row selection (updates detail pane), and command execution (Run
command pill; in a native surface this dispatches the UNO command in the
current document context).

### Empty, loading & error states

Zero matches keep the header count ("0 of 2,433 commands") and show the
shared empty-state pattern with a "Clear search" action. An invalid regex
follows the shared search-field error treatment (error border + message)
without clearing the list. Catalog-fetch failure falls back to the curated
list with a banner noting reduced coverage (prototype behaviour; a native
surface reads a bundled inventory and has no fetch failure mode).

### Density & adaptive width

Row and control heights follow the shared density table. Below the expanded
width class the detail pane becomes an overlay invoked from the row; below
compact, the scope rail collapses to icons with counts in tooltips.
Specified here, not yet implemented.

### Keyboard map

`F6` cycles rail → search → list → detail; `Up`/`Down` move list selection;
type-to-search focuses the search field; `Enter` on a row moves focus to the
detail pane; `Enter` on Run command executes. The search field's regex
toggle and builder follow [04 — Inputs](04-inputs.md).

### Accessibility notes

Scope entries expose label + count as one accessible name ("Writer, 384
commands" pattern); the truncation notice is exposed as a list status, not a
row; the UNO chip gives every command a programmatic, locale-independent
identifier that assistive tech can read verbatim. Selected rows carry the
selected state through the API, not only the `@primary-container` wash.

### Verification checkpoints

Once native: verify the compound-key selection survives re-filtering and
scope switches (keyboard-only script); verify the 400-row cap plus true
counts against a seeded inventory; capture rail/list/detail in light, dark,
and HC; verify regex-error and zero-match states; confirm Run command
dispatches the recorded UNO command in a scripted document.

---

## 12.4 Version history (shared surface, design concept)

A suite-level timeline of automatically committed document versions.
Prototype-only as a surface; its premise — "every undoable change is
auto-committed" — is a product design concept, specified here, not yet
implemented.

### Layout & regions

Three panes at 600 px prototype body height under a surface header:

| Region | Size & treatment | Status |
| --- | --- | --- |
| Header | 16 px 20 px padding, bottom hairline; title "Version history" 22 px/700; explanatory subtitle 13 px `@on-surface-variant`; trailing scope toggle (This document / Whole project) as a segmented pill group — 7 px 14 px padding, 16 px radius segments, 12 px/600, active `@primary` / `@on-primary`, container `@surface-container` with hairline | prototype-only |
| Timeline rail | 308 px; `@surface-container`; right hairline; day-group kickers (11 px/700 uppercase, 0.08 em tracking, 14 px 8 px 6 px padding); entry rows 8 px 10 px padding at `corner-container` radius | prototype-only |
| Timeline entry | Leading 12 px dot with 2 px ring — `@primary` fill + ring when selected or current, otherwise `@surface` fill with `@outline` ring; action title 13 px/500 ellipsis; timestamp 11 px `@on-surface-variant`; current version carries a "NOW" badge (9 px/600, 3 px 7 px padding, 6 px radius, `@primary` / `@on-primary`); selected row `@primary-container` / `@on-primary-container` | prototype-only |
| Snapshot preview | Flexible centre, `@surface-container-low` fill, 22 px padding; renderable snapshots show a 600 px document page card (max 94 % width, `@surface` fill, hairline, page shadow, 52 px 60 px padding, ≥ 520 px tall); non-renderable snapshots show a 420 px centred card with a 64 px `@primary-container` icon tile, the file name, and "Snapshot from *time*" | prototype-only |
| Detail pane | 300 px; `@surface-container`; left hairline; 18 px padding; "Snapshot" kicker; time 20 px/700; action description; author and commit-hash chips (38 px tall, `corner-container`, `@surface` fill, hairline, 18 px person/tag icons, hash in 12 px monospace); word-delta chips (`+N words` on `@primary-container` / `@on-primary-container`, `−N` on `@error-container` / `@on-error-container`, `corner-small`, 12 px/600 monospace) | prototype-only |
| Detail actions | "Restore this version" — 44 px filled pill `@primary` / `@on-primary` with restore icon, shown only for restorable snapshots; "Current version" — 44 px static pill `@disabled-container` (`disabled-container` palette role) with `@on-surface-variant` text on the current entry; "Compare with current" — 44 px outlined pill (`@outline` stroke, `@primary` text); "Branch" and "Export" — 40 px text pills | prototype-only |

### Key user flows

Select a timeline entry to preview that exact document state; toggle scope
between the open document and the whole project; restore (replaces the
working copy after confirmation — an explicit dialog, since restore is
destructive to unsaved state); compare with current; branch or export a
snapshot. Restore must never be a single silent click.

### Empty, loading & error states

A new document shows a single "NOW" entry and an explanatory empty state in
the preview pane. Snapshot loading uses the shared determinate progress
control. A snapshot that cannot be rendered falls back to the metadata card
(file icon, name, time) rather than an error — the fallback is a designed
state, not a failure. Failed restores raise the shared error banner naming
the recovery action.

### Density & adaptive width

Row metrics follow the shared density table. Below expanded width the detail
pane overlays; below medium the preview collapses behind the timeline
(master–detail navigation).

### Keyboard map

`F6` cycles header → timeline → preview → detail; `Up`/`Down` traverse
entries across group headers; `Enter` opens the focused entry's detail;
`Escape` returns from an overlaid detail pane to the timeline.

### Accessibility notes

Group kickers are exposed as list headings. The current version is announced
through state ("current"), not only the badge; word deltas pair sign + colour
so meaning survives monochrome rendering. The timeline dot is decorative —
selection is carried by the list item's selected state.

### Verification checkpoints

Native checks when the concept lands: timeline keyboard traversal order;
restore confirmation flow (no single-event destructive path); light/dark/HC
capture of dot/badge/delta treatments; verification that the preview shows
the exact recorded document state for a seeded history fixture; scope-toggle
persistence across reopen.

---

## 12.5 Suite-wide consistency rules for new surfaces

These rules generalize what Base, Math, Features, and Version history — and
the earlier surface chapters — already do. Every new surface must satisfy
them before it can enter the verification gate in
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md).

1. **Tokens only.** Surfaces consume semantic roles (`@primary-container`,
   `corner-container`, `stroke-thin`, `size-standard-control`, …); raw
   colours, radii, and repeated geometry belong in
   [`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
   or the token reference, never in surface code.
2. **The rail pattern.** Left navigation rails are 220 px wide on
   `@surface-container` with a `stroke-thin` `@outline-variant` hairline, an
   uppercase 11 px kicker in `@on-surface-variant`, and full-width entries at
   `corner-container` radius whose selected state is `@primary-container` /
   `@on-primary-container` plus an API-exposed selected state. Base, Features,
   the Start Center, and the Options dialog all instantiate this pattern.
3. **The three-pane pattern.** Browsing surfaces use rail (220 px) →
   flexible list/content → detail pane (300 px, `@surface-container`, left
   hairline). Detail panes end in full-width 44 px pill actions: filled
   `@primary` for the primary action, outlined for the secondary, text pills
   for tertiary.
4. **Cards and containers.** Content cards sit on `@surface` with
   `@outline-variant` hairlines at `corner-container` (12 px); hover raises
   the border to `@primary` and the fill to `@primary-container`. Icon tiles
   are `@primary-container` / `@on-primary-container` squares at
   `corner-container`.
5. **Data tables.** Header rows on `@surface-container` with
   `@on-surface-variant` labels; body stripes on `@surface-container-low`;
   hairline row separators; sort state carried by the `listheader` arrow
   parts and announced, never colour-only.
6. **Selection identity.** List selection is keyed by a stable, unique,
   locale-independent identity (Features: UNO command + name), reconciled
   against real rows — never by index or display string alone.
7. **Bounded lists.** Unbounded inventories cap rendering (Features: 400)
   while reporting true counts and a visible refinement notice.
8. **Keyboard completeness.** `F6`/`Shift+F6` cycles panes on every surface;
   every pointer flow has a keyboard equivalent; destructive actions require
   explicit confirmation.
9. **Honest states.** Every surface defines empty, loading, and error states
   with a named recovery action, using the shared feedback components.
10. **Honest status.** New surface specs label every feature as implemented
    in definition.xml (unbuilt), prototype-only, or specified here, not yet
    implemented — and claim no build, capture, or accessibility result until
    the evidence contract in
    [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) is satisfied
    for an exact commit. The verified-capture count for everything in this
    chapter is currently **0**.
