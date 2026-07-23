# 10 — Writer & Calc

> **Status:** Specification of target Writer/Calc composition — shared native
> definitions compiled in the exact-source local build, but these application
> surfaces are not runtime-verified; see [`ROADMAP.md`](../../ROADMAP.md).

This chapter specifies the two flagship document surfaces: the Writer text
document window and the Calc spreadsheet window. Normative inputs are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behaviour
contract), [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native token/part/state contract, compiled at `577059e274`), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Every feature is labelled *implemented in definition.xml
(compiled; surface state unverified)*, *prototype-only*, or *specified here, not yet implemented*. Shared
controls used on these surfaces (toolbar buttons, fields, combos, tabs, lists,
scrollbars, progress) are specified in chapters
[02](02-actions.md)–[07](07-feedback.md); this chapter defines their
composition into the two surfaces.

---

## 10.1 Shared application chrome

Both surfaces sit inside the same window shell, in one of two chrome variants
selected by the user (View ▸ User Interface): **classic** (menu bar plus two
toolbar rows) or **ribbon** (tab row plus a grouped command strip). Neither
variant removes commands; they re-arrange the identical command set.

### Layout & regions (prototype geometry)

| Region | Size (prototype) | Tokens | Status |
| --- | --- | --- | --- |
| Window container | `min(1200px, 97vw)` wide, 11px outer radius, `stroke-thin` `@outline-variant` border on `@surface` | `@surface`, `@outline-variant` | prototype-only (native windows use OS frames) |
| Title bar | 42px high; app icon 20px in `@primary`; caption buttons 46×42px | `@surface-container` fill, `stroke-thin` `@outline-variant` bottom rule | prototype-only; native title metrics come from `height-window-title` (18) via `titleHeight` — implemented in definition.xml (compiled; surface state unverified) |
| Menu bar (classic) | `--menu`: 30px compact / 38px comfortable; items `5px 11px` padding, 8px radius | open item `@primary-container` / `@on-primary-container` | native `menuBarColor` = `@surface-container`, `menuBarRolloverColor` = `@primary-container` — implemented in definition.xml (compiled; surface state unverified). The prototype paints the bar on `--surface`; the native style mapping is authoritative. |
| Standard toolbar (classic) | `--tb`: 38px compact / 48px comfortable; buttons 34×34px, icons 20px; separators 1×22px | toolbar background `@surface-container` (`toolbar`/`Entire`, `DrawBackgroundHorz`); separators `@outline-variant` at `stroke-thin` (`SeparatorVert`) | implemented in definition.xml (compiled; surface state unverified) |
| Formatting toolbar (classic) | same `--tb` height; combos 30px high | see §10.2/§10.3 composition | composition prototype-only; button/combo parts implemented in definition.xml (compiled; surface state unverified) |
| Ribbon tab row | 38px high; tabs `6px 16px` padding, `16px 16px 0 0` radius, 2px `@primary` underline when active | active tab `@surface` fill, `@primary` text; row on `@surface-container` | prototype-only (notebookbar restyle not yet in native source) |
| Ribbon command strip | 96px high, 8px padding; big buttons 64×72px (28px icon + 11px label); small buttons 34×34px; chips 30px high at `corner-pill` | groups divided by `stroke-thin` `@outline-variant` rules, group captions 11px `@on-surface-variant` | prototype-only |
| Status bar | 28px high, `0 14px` padding; text 12px `@on-surface-variant`; zoom slider 120px wide, 4px track, 12px thumb | `@surface-container` fill, `stroke-thin` `@outline-variant` top rule; slider fill `@primary` | prototype-only composition; native slider parts (`slider`/`TrackHorzLeft` `@primary` at `stroke-track`) implemented in definition.xml (compiled; surface state unverified) |

Native toolbar buttons resolve through `toolbar`/`Button`, which defines nine
states — enabled, rollover (`@primary-container`), pressed (`@primary-hover`),
checked (`button-value="true"`: `@primary` stroke at `stroke-thin` over
`@primary-container`), rollover+checked, pressed+checked, focused (`@primary`
at `stroke-standard`), disabled (`@disabled-container`), and disabled+checked
(`@outline` stroke over `@disabled-container`) — all at `corner-toolbar`
(18px). Implemented in definition.xml (compiled; surface state unverified). The prototype rounds its
34px toolbar buttons at `--r-sm` (8px); the native `corner-toolbar` role is
authoritative for the built control.

### Chrome-variant rules

- Switching chrome is a layout change only: command identity, shortcuts and
  mnemonics are identical in both variants (per the
  [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) non-goal of never removing
  expert commands).
- In ribbon chrome a **Toggle Menu Bar** icon button (32×30px, far right of
  the tab row — prototype-only) restores the classic menu bar without
  restarting.
- Overflow is a designed state: when the window narrows, toolbar and ribbon
  groups collapse right-to-left into an overflow menu with stable keyboard
  order; controls never silently disappear (specified here, not yet
  implemented).

---

## 10.2 Writer

Reference document in the prototype: *Q3 Board Report.odt — LibreOffice
Writer*.

### Layout & regions

The body below the command area is a horizontal split: document canvas
(flexible) and properties sidebar (fixed 300px). Prototype body height is
560px inside the mockup shell; a real window fills the remaining client area.

| Region | Size (prototype) | Tokens | Status |
| --- | --- | --- | --- |
| Document canvas | flexible width; vertical padding 26px; scrollable | prototype background `@surface-container-low` | **canvas colour is not Material-token-wired**: the real canvas-outside-page fill is `SwViewOption::GetDocColor()` → `svtools::ColorConfig` `DOCCOLOR`, whose default is the hardcoded auto pair `COL_WHITE` (light) / `Color(0x1C1C1C)` (dark), **not** the `workspaceColor`/`@surface-container-low` slot the prototype implies. `DOCCOLOR` reaches `StyleSettings` only in the forced-high-contrast branch, and there via `GetWindowColor()`/`@surface`. Composition prototype-only |
| Page | 640px wide (`max-width: 92%`), centred; `64px 72px` inner padding; min-height 760px | `@surface` fill; `stroke-thin` `@outline-variant` border; shadow `0 4px 20px rgba(0,0,0,.10)` | prototype-only (page rendering is document content, not chrome) |
| Properties sidebar | 300px total: 252px panel + 48px icon rail; `stroke-thin` `@outline-variant` left rule | panel on `@surface`, rail on `@surface-container` | prototype-only composition |
| Sidebar rail | 48px wide; buttons 38×38px at `corner-small`, 22px icons, 4px gap, 10px top padding | active `@primary-container` / `@on-primary-container`; inactive transparent / `@on-surface-variant` | prototype-only; hover/checked treatment matches `toolbar`/`Button` semantics (implemented in definition.xml; compiled, surface state unverified) |
| Panel content | 14px padding; panel title 14px semibold; section headings 11px uppercase `@on-surface-variant` | title/label typography via native `title`/`label` roles (120%/semibold, 100%/medium) | typography roles implemented in definition.xml (compiled; surface state unverified) |

Rail entries (top to bottom, prototype): Properties, Styles, Gallery,
Navigator, Functions. Exactly one rail entry is active; its deck fills the
panel.

#### Character and paragraph panels

The Properties deck stacks a **Character** section and a **Paragraph**
section:

- Font-name field: 36px high (matches `size-standard-control` = 36), flexible
  width, `stroke-thin` `@outline` border at `corner-small` in the prototype,
  value *Liberation Serif*, trailing 18px chevron in `@on-surface-variant`.
  The built control is a `combobox` — `@outline` stroke on `@surface` at
  `corner-container`, `@primary` at `stroke-standard` when focused, and a
  36×36 (`size-standard-control`) `ButtonDown` chevron zone on
  `@primary-container` — implemented in definition.xml (compiled; surface state unverified).
- Font-size field: 56×36px in the prototype, value *12*; built as a
  `spinbox`/`combobox` with the same state set.
- Character toggle row: six 34×34px icon toggles at `corner-small` — Bold,
  Italic, Underline, Strikethrough, Font Colour, Highlight (prototype set).
- Paragraph toggle row: six toggles — Align Left, Centre, Right, Justified,
  Bulleted List, Numbered List. Alignment toggles are a mutually exclusive
  set; character toggles are independent.
- Insight chip: 40px high, `0 12px` padding, `corner-container` radius,
  `@primary-container` fill with `@on-primary-container` text and a 20px
  leading icon; prototype content "Spacing above paragraph: 0.00"".
  Prototype-only.

#### Page style and Navigator panels

Two further Writer-owned sidebar decks route to real production panel classes
through `SwPanelFactory` and carry a load-bearing visibility state machine each;
their outer deck chrome is already covered generically by the WIN-CON-007
sidebar-deck contract, so only their content composition is documented here
(pinned source-only by `qa/windows-ui-contract/writer-sidebar-decks.json`):

- **Page style panel** (WriterPageDeck ▸ Styles = `PageStylesPanel` over
  `pagestylespanel.ui`): the background group exposes four fill controls —
  colour, gradient, hatching, bitmap — as a **mutually exclusive** set switched
  by the fill-type combo. `PageStylesPanel::Update()`'s `switch` over the fill
  style shows exactly one control (or, for GRADIENT, the colour + gradient pair)
  and hides the rest, then relayouts via `TriggerDeckLayouting()`. Controls are
  stock weld widgets (combobox, colour list box) already themed generically —
  implemented in definition.xml (compiled; surface state unverified) — no
  panel-specific token treatment.
- **Navigator panel** (NavigatorDeck = `SwNavigationPI` over
  `navigatorpanel.ui`): a single content-tree ⇄ global-tree toggle
  (`ToggleTree()` shows the content-tree widget set and hides the global set, or
  the mirror, calling `SetGlobalMode()`), plus the six content-type toolbars.
  Tree-row height, indent, icon and selection pixels are deferred to a
  build-time checkpoint (see [06-containers](06-containers.md)); this deck's
  Material composition is specified here, not yet implemented.

#### Formatting toolbar composition (classic)

Left to right (prototype `FMT.writer`), separated by 1×22px `@outline-variant`
rules:

1. Paragraph-style combo, 180px (*Default Paragraph Style*);
2. font-name combo, 140px (*Liberation Serif*); font-size combo, 54px (*12*);
3. Bold, Italic, Underline, Strikethrough;
4. Font Colour, Highlighting;
5. Align Left, Centre, Right, Justified;
6. Bulleted List, Numbered List;
7. Increase Indent, Decrease Indent.

Combos are 30px high with `stroke-thin` `@outline` borders at `corner-small`
in the prototype; toggle buttons show checked state as `@primary-container`
fill with `@on-primary-container` glyph and expose `aria-pressed`.
Composition prototype-only; each control's parts and states implemented in
definition.xml (compiled; surface state unverified).

#### Review, tracked changes and comments composition

Writer's review/collaboration surfaces are real, registered upstream chrome that
today carry zero Material-specific differentiation; their composition/wiring is
pinned source-only by `qa/windows-ui-contract/writer-review-composition.json`,
and every line here is **specified here, not yet implemented**:

- **Track Changes toolbar** (`sw/uiconfig/swriter/toolbar/changes.xml`,
  `private:resource/toolbar/changes`): a fixed ordered command sequence spanning
  review + comments + tracked-changes + collaboration — Show/Record changes
  toggles, Previous/Next, Accept / Reject (single, all, to-next),
  Insert Comment / comment-on-change, Protect, and the file-level
  Compare/Merge Documents. It reuses the generic nine-state `toolbar`/`Button`
  part at `@corner-toolbar` (no new tokens).
- **Comments deck** (Sidebar.xcu `CommentsDeck`/`CommentsPanel` →
  `SwPanelFactory` → `CommentsPanel` over `commentspanel.ui` + `commentwidget.ui`):
  a filter/options header (author, date, show-time/resolved/reference, sort) over
  a stack of per-thread comment widgets (author/date/time labels, reply and
  resolve controls, text view).
- **Manage Changes deck** (Sidebar.xcu `SwManageChangesDeck` → `SwRedlineAcceptPanel`
  over `managechangessidebar.ui`): mounts the **shared** svx accept/reject control
  `SvxAcceptChgCtr` (`svx/source/dialog/ctredlin.cxx`) rather than a Writer-private
  widget — so this deck is a real mount of shared review infrastructure, and the
  control's own internal layout is owned at the svx level, not duplicated here.

Search within these surfaces (comment filter, find bar) and document-level error
states are covered by other rows and the generic banner pattern respectively, so
they are deliberately out of this composition.

#### Format dialogs (Character, Paragraph, Table, Picture/Frame)

Writer's high-traffic tab dialogs are applications of the shared modal anatomy
and the left-icon-rail tab-dialog pattern (the same generic dialog chrome
documented in [08-dialogs](08-dialogs.md) and the tab-bar native part contract
in [05-navigation](05-navigation.md) §3) — **no novel visual design**. Four are
pinned as real `SfxTabDialogController` left-icon-rail notebooks
(`qa/windows-ui-contract/writer-format-dialogs.json`): Character
(`characterproperties.ui` / `chardlg.cxx`), Paragraph (`paradialog.ui` /
`pardlg.cxx`), Table Properties (`tableproperties.ui` / `tabledlg.cxx`) and
Picture/Frame (`picturedialog.ui` + `framedialog.ui` / `frmdlg.cxx`, one class
serving three dialog identities). Each is a modal notebook with a left tab rail
and the shared reset/ok/cancel/help footer, and each reuses shared svx tab pages
(Border, Area, Transparency) validated once and cross-referenced rather than
re-drawn. Composition/anatomy only; icon downscale, rail width, and pill
geometry are build-host pixel gates, so this is specified here, not yet
implemented (`runtime_verified: false`).

### Key user flows

- **Type and format:** caret in page → select text → toggle Bold via toolbar,
  sidebar, or Ctrl+B; all three routes drive the same command and all
  reflected toggles update together.
- **Style application:** paragraph-style combo or F11 Styles deck; the combo
  shows the style at the caret at all times (status bar mirrors it).
- **Navigate:** F5 opens the Navigator deck in the sidebar rail rather than a
  floating window by default (specified here, not yet implemented).
- **Sidebar deck switch:** click a rail icon or Ctrl+F5 to move focus into the
  sidebar; the active deck persists per application.

### Empty, loading and error states

- **Empty document:** the page renders immediately with the caret in the
  first paragraph; no placeholder art. Status bar reads "Page 1 of 1" with a
  zero word count (specified here, not yet implemented).
- **Loading/long operations:** file open and pagination progress use the
  determinate `progress` control — `@outline-variant` `TrackHorzArea` under a
  `@primary` `Entire` fill at `corner-indicator` — hosted in the status bar;
  implemented in definition.xml (compiled; surface state unverified), placement specified here.
- **Errors:** document-level problems (read-only, recovery, failed save) use
  the banner pattern from [07-feedback](07-feedback.md) with
  `@error-container` / `@on-error-container` and always pair the message with
  a recovery action; never colour alone.

### Density & adaptive width

| Value | Compact | Comfortable |
| --- | ---: | ---: |
| Toolbar row height `--tb` | 38px | 48px |
| Menu bar height `--menu` | 30px | 38px |
| Menu/list item height `--item` | 30px | 40px |
| Base font size `--fs` / line height | 13px / 1.35 | 14px / 1.45 |

These are the prototype's browser density metrics
([`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md)); the native metric layer
currently fixes single integer roles (`size-standard-control` 36,
`height-tab` 40) and does not yet implement density selection — that remains
specified here, not yet implemented. The page keeps `max-width: 92%` of the
canvas, so it shrinks before the sidebar does; below the medium window class
the sidebar collapses to its 48px rail only, and the formatting toolbar
overflows from the right (specified here, not yet implemented).

### Keyboard map

| Key | Action | Source |
| --- | --- | --- |
| Ctrl+B / Ctrl+I / Ctrl+U | Bold / Italic / Underline | command catalog (prototype `FEATURES` data) |
| Ctrl+L / Ctrl+E / Ctrl+R / Ctrl+J | Align left / centre / right / justified | command catalog |
| Ctrl+M | Clear direct formatting | command catalog |
| F11 | Paragraph styles | command catalog |
| F5 | Navigator | command catalog |
| F7 / Ctrl+F7 | Spelling / Thesaurus | command catalog |
| Ctrl+F / Ctrl+H | Find / Find & Replace | command catalog |
| Ctrl+Enter | Insert page break | command catalog |
| Ctrl+Shift+J | Full screen | command catalog |
| F6 / Shift+F6 | Cycle focus: menu/ribbon → toolbars → sidebar → document | upstream behaviour preserved |
| Alt+letter | Menu mnemonics (classic chrome) | upstream behaviour preserved |

All upstream defaults are preserved; the redesign never rebinds or removes
expert shortcuts.

### Accessibility notes

- The document canvas exposes the existing Writer document accessibility tree
  unchanged; chrome work never alters content semantics.
- Sidebar rail buttons expose role *toggle button* (rail) with accessible
  names equal to their deck titles; the active deck is exposed as pressed.
- Formatting toggles expose pressed state; alignment exposes a
  radio-group-like single selection. State is never conveyed by fill colour
  alone: checked toolbar buttons also carry the `stroke-thin` `@primary`
  outline (implemented in definition.xml; compiled, surface state unverified).
- Focus indicators follow chapter [01](01-foundations.md): `stroke-standard`
  `@primary` outlines defined per control part; generic fallback retains the
  VCL focus rectangle when Material drawing is bypassed under high contrast.
- The insight chip's `@primary-container`/`@on-primary-container` pairing and
  all text-on-container pairs must meet ≥ 4.5:1 contrast in both palettes
  (validator-checked contrast pairs; no runtime accessibility result exists).

### Verification checkpoints

Evidence per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md);
scenario identifiers `writer-surface-*`. Writer surface-specific capture count: 0.

1. `writer-surface-canvas`: headless capture of an open document; assert the
   canvas pixel outside the page equals `@surface-container-low` (`#F7F2FA`
   light / `#1D1B20` dark) and the page area equals `@surface`.
2. `writer-surface-toolbar-states`: drive rollover/pressed/checked/disabled
   on a formatting toggle; assert the four `toolbar`/`Button` fills and the
   `@primary` checked outline, including disabled+checked keeping the
   `@outline` ring.
3. `writer-surface-sidebar`: capture sidebar at 300px; assert 48px rail,
   active-rail `@primary-container` fill, and combobox `ButtonDown` chevron
   zone at 36px (`size-standard-control`).
4. `writer-surface-keyboard`: scripted F6 cycle and Ctrl+B round-trip; assert
   toggle state parity between toolbar and sidebar controls.
5. `writer-surface-hc`: repeat checkpoint 1–2 under forced high contrast;
   assert Material drawing is bypassed and the native baseline focus
   indicator remains visible.

---

## 10.3 Calc

Reference document in the prototype: *2026 Operating Budget.ods — LibreOffice
Calc*.

### Layout & regions

Top to bottom below the command area: formula bar row, grid (flexible), sheet
tab bar, status bar.

#### Formula bar row

Height equals the toolbar row (`--tb`: 38px compact / 48px comfortable),
`0 8px` padding, on `@surface` with a `stroke-thin` `@outline-variant` bottom
rule. Contents left to right (prototype geometry):

| Element | Size | Treatment | Status |
| --- | --- | --- | --- |
| Name Box | 96×30px | current reference (e.g. `D4`) in 13px medium `@on-surface`; `stroke-thin` `@outline` border, `corner-small`; trailing 18px chevron | prototype-only composition; the built control is a `combobox` (implemented in definition.xml; compiled, surface state unverified) |
| Function Wizard | 32×30px | text glyph `fx`, bold 14px in `@primary`; hover `@primary-container` | prototype-only; opens the wizard (Ctrl+F2) |
| Sum | 32×30px | Σ glyph, 17px in `@on-surface-variant`; hover `@primary-container` / `@on-primary-container` | prototype-only |
| Formula input | flexible, 30px high | `stroke-thin` `@outline` border at `corner-small` on `@surface`, `0 12px` padding, 13px `@on-surface` text | prototype-only composition; the built control is an `editbox` — `@outline`/`@surface` idle, `@primary` at `stroke-standard` focused, height role `size-standard-control` (implemented in definition.xml; compiled, surface state unverified) |

The prototype derives the formula display from the selected cell: numeric
cells render as `=` plus the raw value with thousands separators stripped.

#### Grid

The grid is application-drawn (not a VCL native-control part). Its **idle**
header colours (face, label, rule line) do flow through the 72-slot
`StyleSettings` mapping — implemented in definition.xml (compiled; surface state
unverified) — but its **selection and gridline** colours route through
`svtools::ColorConfig` (Tools ▸ Options ▸ Application Colors) instead, not the
file-widget/definition.xml pipe (see the grid-colour-routing note below). Its
geometry rules are specified here and mirrored by the prototype.

| Element | Value | Tokens | Status |
| --- | --- | --- | --- |
| Corner cell | 44×26px | `@surface-container` fill | prototype-only |
| Column headers | 26px high, one per column | idle `@surface-container` fill, 12px medium `@on-surface-variant` text; `stroke-thin` `@outline-variant` cell rules | prototype-only geometry; colours via `highlightColor` family below |
| Row headers | 44px wide, `--row` high | same idle/selected treatment as column headers | prototype-only geometry |
| Header selection highlight | header containing the active cell | **fill `@primary`** (via `CALCCELLFOCUS` → `GetAccentColor()`, not `@primary-container`); label text `@on-primary-container` (`GetHighlightTextColor()`) | source-declared, runtime unverified; see grid-colour-routing note below |
| Data columns | **76px compact / 92px comfortable** default width | — | prototype-only density rule |
| Data rows | `--row`: **26px compact / 32px comfortable** | `stroke-thin` `@outline-variant` gridlines (**target only — not yet Material-routed**) | prototype-only density rule; gridline colour (`CALCGRID`) resolves through the fixed `cAutoColors` default, not `@outline-variant` — see note below |
| Cells | `0 8px` inline padding, 13px `@on-surface` text | text starts with a digit or `(` → right-aligned; otherwise left-aligned | prototype-only heuristic illustrating the standard numeric/text alignment rule |
| Cell selection ring | 2px inset ring (`stroke-standard`) in `@primary`; selected cell fill `@surface` against the transparent grid | `@primary`, `@surface` | prototype-only; the `accentColor` = `@primary` slot is compiled in definition.xml, but Calc's cursor does **not** read it directly — it resolves through `svtools::ColorConfig`'s `CALCCELLFOCUS` entry (default → `GetAccentColor()` → `@primary`), and only when the stored Application-Colors value is "Automatic" — see note below |
| Alternating rows (where enabled) | `@surface-container-low` via `alternatingRowColor` | implemented in definition.xml (compiled; surface state unverified) |

The prototype grid shows 8 columns (A–H) and 14 rows with an income-statement
fixture (`Category/Q1…Q4/Total`, totals row `15,410`).

**Note — grid colour routing (source-verified, runtime unverified).** Calc's
grid is not on the file-widget/definition.xml colour pipe for its selection and
gridline colours; it routes through `svtools::ColorConfig`
(`svtools/source/config/colorcfg.cxx`) instead. `CALCCELLFOCUS`/`CALCDBFOCUS` —
which paint the active-cell cursor ring, the AutoFilter/DB-range highlight, the
autofill handle and the selected-header fill — default to
`StyleSettings::GetAccentColor()` (= the compiled `accentColor` = `@primary`
slot) **only** when the user's stored Application-Colors value is `COL_AUTO`
("Automatic"); a customized profile bypasses the Material accent entirely. The
selected-header fill is therefore `@primary` paired with `@on-primary-container`
label text — a pairing whose contrast is a build-bound verification follow-up,
not a current claim. Gridlines (`CALCGRID`) are **not** special-cased in
`ColorConfig::GetDefaultColor` at all: they fall through to the fixed
`cAutoColors` table (`COL_GRAY3` light / `COL_GRAY7` dark), so the
"`@outline-variant` gridlines" target above is a divergence from the wired code,
not an implemented mapping. Density (compact/comfortable column-width and
row-height defaults) likewise has no native selection code and stays specified,
not implemented. These facts are pinned source-only (`runtime_verified: false`)
by `qa/windows-ui-contract/calc-grid-selection.json` (WIN-CA-003) and
`qa/windows-ui-contract/data-grid-header-selection.json` (WIN-CON-003).

#### Sheet tab bar

34px high, `0 8px` padding, on `@surface-container` with a `stroke-thin`
`@outline-variant` top rule. Tabs are 26px high with `0 14px` padding and an
`8px 8px 0 0` top radius: active tab `@surface` fill, `@primary` semibold 12px
text, `stroke-thin` `@outline-variant` border with the bottom edge open into
the grid; inactive tabs transparent with `@on-surface-variant` regular text.
An Add Sheet icon button (28×26px, `corner-small`) follows the last tab.
Prototype tabs: *Income*, *Balance*, *Cash flow*; status bar mirrors
"Sheet 1 of 3". This composition is prototype-only; the generic native tab
control (`tabitem`, `height-tab` = 40, `corner-pill`, with
`centeredTabs`/`noActiveTabTextRaise` settings) is implemented in
definition.xml (compiled; surface state unverified) and applies to dialog tabs, not the sheet bar — the
sheet bar keeps its own top-radius document-tab shape deliberately.

### Dense-grid density rules

Calc is the canonical dense surface, so density changes column geometry, not
only chrome:

| Value | Compact | Comfortable |
| --- | ---: | ---: |
| Default column width | 76px | 92px |
| Row height `--row` | 26px | 32px |
| Formula bar row `--tb` | 38px | 48px |
| Sheet tab bar | 34px (both) | 34px (both) |
| Grid font | 13px | 14px |

Compact is the default for keyboard/mouse expert use per the density contract
in [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md). Explicit user column
widths and row heights always override the density default; density only
moves the defaults. These are prototype density metrics; the native metric
layer does not yet implement density selection (specified here, not yet
implemented).

### Key user flows

- **Select and edit:** click or arrow to a cell (selection ring follows);
  type to replace, F2 to edit in place, or edit in the formula input; Enter
  commits down, Tab commits right, Esc cancels.
- **Reference navigation:** type a reference or named range into the Name Box
  and press Enter to jump/select.
- **Sum a range:** select target cell → Σ button proposes `=SUM(...)` over
  the adjacent range → Enter commits.
- **Sheet management:** click a tab to switch; Add Sheet appends; tab context
  menu holds rename/move/delete (menu control per [05](05-navigation.md)).

### Empty, loading and error states

- **Empty sheet:** the grid renders immediately with A1 selected; headers and
  gridlines are the only chrome. No placeholder art.
- **Loading/recalculation:** long recalculations show determinate `progress`
  in the status bar (`@primary` on `@outline-variant`, `corner-indicator`) —
  control implemented in definition.xml (compiled; surface state unverified), placement specified here.
- **Cell errors:** overflow (`###`) and error values (`Err:…`, `#NAME?`)
  render in the cell in `@on-surface` with the error explained in the status
  bar on selection; validation failures use `@error-container` /
  `@on-error-container` feedback per [07-feedback](07-feedback.md), never
  colour alone (specified here, not yet implemented).

### Keyboard map

| Key | Action | Source |
| --- | --- | --- |
| Arrows / Ctrl+Arrows | Move cell / jump to data edge | upstream behaviour preserved |
| F2 | Edit active cell | upstream behaviour preserved |
| Enter / Shift+Enter / Tab / Shift+Tab | Commit and move down/up/right/left | upstream behaviour preserved |
| Ctrl+1 | Number format (Format Cells) | command catalog |
| Ctrl+F2 | Function Wizard | command catalog |
| Ctrl+Shift+L | AutoFilter | command catalog |
| Ctrl+B / Ctrl+I / Ctrl+U | Bold / Italic / Underline | command catalog |
| Ctrl+F / Ctrl+H | Find / Find & Replace | command catalog |
| Ctrl+PageDown / Ctrl+PageUp | Next / previous sheet | upstream behaviour preserved |
| F5 | Navigator | command catalog |
| F6 / Shift+F6 | Cycle focus: chrome → formula bar → grid → sheet tabs | upstream behaviour preserved |

The formatting toolbar composition for Calc (classic chrome) is: font-name
combo 150px (*Liberation Sans*), size combo 54px (*10*); Bold, Italic,
Underline; Font Colour, Background Colour; Align Left/Centre/Right; Currency,
Percent, Add Decimal, Delete Decimal; Merge Cells (prototype `FMT.calc`,
prototype-only composition).

### Accessibility notes

- The grid exposes the existing Calc spreadsheet accessibility interfaces
  (table, cell, selection); chrome work does not modify them.
- The active cell is reported by name (reference), value, and formula; the
  Name Box mirrors the reference for sighted users and is itself focusable
  and editable.
- Selection is never colour-only: the active cell carries the 2px ring, and
  its row/column headers change both fill and text colour
  (`@primary-container` + `@on-primary-container`, a validator-checked
  contrast pair).
- Sheet tabs expose role *page tab* with selected state; Add Sheet is a named
  button. Numeric right alignment is presentation, not semantics — screen
  readers receive the cell value and format description.
- High contrast bypasses Material drawing and restores the platform baseline,
  keeping the native focus and selection indicators (implemented in
  definition.xml routing; compiled, surface state unverified).

### Verification checkpoints

Scenario identifiers `calc-surface-*`, evidence per
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md). Verified-capture
count today: 0.

1. `calc-surface-formula-row`: capture the formula bar; assert Name Box
   96px wide, field heights 30px, `editbox` focus state switching from
   `stroke-thin` `@outline` to `stroke-standard` `@primary`.
2. `calc-surface-grid-selection`: move the selection by keyboard; assert the
   2px `@primary` inset ring, and header highlight flipping to
   `@primary-container`/`@on-primary-container` in both light and dark
   palettes.
3. `calc-surface-density`: capture identical sheets in compact and
   comfortable; assert 76px vs 92px default columns and 26px vs 32px rows,
   and that explicit user widths survive the switch.
4. `calc-surface-sheet-tabs`: switch sheets by pointer and Ctrl+PageDown;
   assert active-tab `@surface`/`@primary` treatment and status-bar sheet
   counter parity.
5. `calc-surface-alignment`: fixture with text, numeric, and error cells;
   assert numeric right alignment, text left alignment, and error rendering
   accompanied by a status-bar explanation.
6. `calc-surface-hc`: repeat checkpoint 2 under forced high contrast; assert
   the native baseline selection/focus rendering replaces Material drawing.

---

## 10.4 RTL & localization (shared)

Both applications follow the suite mirroring rules in
[01 — Foundations](01-foundations.md) and the grid mirroring specification in
[06 — Containers §6.3](06-containers.md); this section records what is
Writer/Calc-specific.

**Writer.** In an RTL interface the properties sidebar and its 48 px rail move
to the window's leading (left) edge while the page canvas keeps the document's
own writing direction — UI mirroring never re-orders document text. Paragraph
alignment buttons are semantic, not geometric: "start" and "end" alignment
follow the paragraph direction, so their icons mirror while justify does not.
The ruler (planned surface) mirrors its origin with the page. Long localized
style names in the style combo truncate with an ellipsis at the trailing edge
and expose the full name via tooltip and accessible name.

**Calc.** An RTL locale flips the sheet itself: column `A` starts at the right
edge, the row-header column sits on the right, and horizontal keyboard motion
is logical (`Tab`/`Right` advance toward increasing columns regardless of
visual direction) per 06 §6.3. The name box and formula bar swap their order in
the formula row; formula text remains logically ordered with bidi-neutral
operator rendering. Sheet tabs run right-to-left in the tab bar. Numeric cell
alignment stays on the number-trailing side, and locale decimal/thousands
separators come from the i18n framework, never from the theme.

**Both.** Menu accelerators, mnemonics, and sidebar labels take translated
strings of at least 1.5× English length without clipping (long-string checks
are part of the localization matrix in `ROADMAP.md`); no chrome string is
baked into a definition or drawing. These behaviors are specified here and are
not yet implemented or verified in a build.
