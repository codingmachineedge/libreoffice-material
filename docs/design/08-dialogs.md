# 08 — Dialogs & overlays

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This chapter specifies the modal dialog family: the shared modal anatomy and its
scrim, keyboard, and elevation rules, followed by the four reference dialog
surfaces realized in the prototype — Options, Save As, Print, and Find &
Replace. Normative inputs are [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)
(component-behavior contract), [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md)
(token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, unbuilt), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Implementation status is labelled per feature as *implemented in
definition.xml (unbuilt)*, *prototype-only*, or *specified here, not yet
implemented*. Button variants are specified in [02-actions.md](02-actions.md);
field and search anatomy in [04-inputs.md](04-inputs.md); the snackbar used for
Replace All reporting in [07-feedback.md](07-feedback.md).

---

## 8.1 Modal dialog — shared anatomy

### Anatomy & tokens

A modal dialog is a `@surface-container` sheet centred over a scrimmed
application window. From top to bottom: title row, content region, and a footer
button row separated by a hairline.

| Region | Token use | Status |
| --- | --- | --- |
| Dialog background | `windowbackground`/`BackgroundDialog` fills `@surface-container`; `<style>` maps `dialogColor` → `@surface-container`, `dialogTextColor` → `@on-surface` | implemented in definition.xml (unbuilt) |
| Container | `@surface-container` (`--sc`) sheet, `--bw` (1 px; 2 px high contrast) `@outline-variant` border, **16 px** corner radius, shadow `0 24px 64px rgba(0,0,0,.4)`, width `min(W px, 94%)` | prototype-only (`dlgWrap`) |
| Scrim | Full-window overlay: light `rgba(20,18,24,.38)`, dark `rgba(0,0,0,.6)`, high contrast `rgba(0,0,0,.65)` (`--scrim`) | prototype-only (`PAL.*.scrim`) |
| Title row | `18px/1` at weight 600 on `@on-surface`; padding `18px 20px 14px`; trailing 34 × 34 px close icon button (`corner-small` radius, 20 px glyph, `@on-surface-variant`) | prototype-only; native `title` type role = 120 % scale, `semibold` minimum; `height-window-title` = 18 |
| Content region | Consumes field, selection, list, and frame components from chapters 03–06 on the `@surface-container` sheet; grouped regions may use the native outlined frame (`frame`/`Border`: `@outline-variant` stroke, `@surface-container` fill, `stroke-thin`, `corner-container`) | frame implemented in definition.xml (unbuilt) |
| Footer button row | Order **Help \| spacer \| secondary \| primary**; padding `14px 20px`, 10 px gap, `stroke-thin` `@outline-variant` top hairline; all buttons 40 px tall, `corner-pill` (20) radius | prototype-only (`dlgFooter`); button states implemented in definition.xml (unbuilt) |
| Primary (filled) button | `@primary` fill, `@on-primary` text, padding `0 28px`; native `pushbutton` `extra="action"` states | implemented in definition.xml (unbuilt); geometry prototype-only |
| Secondary (outlined) button | Transparent fill, `--bw` `@outline` border, `@primary` text, padding `0 20px` | prototype-only — the native default `pushbutton` renders tonally (`@primary-container`); see [02-actions.md](02-actions.md) |
| Tertiary (text) button | Transparent, `@primary` text, padding `0 20px` (`ghostBtn`, used for *Reset*) | prototype-only; native `extra="flat"` pushbutton |
| Entrance motion | `lo-pop`: 160 ms ease from `opacity:0; translateY(-4px); scale(.98)` | prototype-only; must honour reduced motion |

The 16 px dialog radius is a deliberate container-family value sitting between
`corner-container` (12) and `corner-toolbar` (18); it is currently a prototype
literal, not a declared shape role. `definition.xml` draws the dialog sheet
square-cornered (`BackgroundDialog` has no radius) because the OS window frame
owns the outer corner on Windows — see Platform notes.

### States

Dialog-level states compose from the parts above; the button states are the
native `pushbutton` contract.

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Open (modal) | Scrim over the app; sheet elevated | `--scrim`; sheet `@surface-container` + border + shadow | prototype-only |
| Primary enabled | Filled pill | `@primary` / `@on-primary` (`extra="action"`) | definition.xml `pushbutton` |
| Primary hover / pressed | Fill steps | `@primary-action-hover` / `@primary-action-pressed` | definition.xml `pushbutton` `rollover`/`pressed` `extra="action"` |
| Secondary (native default) enabled / hover / pressed | Tonal pill steps | `@primary-container` → `@primary-hover` → `@primary-pressed` | definition.xml `pushbutton` `Entire` |
| Text button hover / pressed | Wash appears | `@primary-container` / `@primary-hover` (`extra="flat"`) | definition.xml `pushbutton` |
| Any button disabled | Dim fill, no state change | `@disabled-container`; text `deactiveTextColor` → `@outline` | definition.xml `pushbutton` `enabled="false"` |
| Button focused | Perimeter focus rectangle at 4 % inset | `@primary` at `stroke-standard` (`pushbutton`/`Focus`) | definition.xml |
| Keyboard-default emphasis | Distinct emphasis for the Enter-default button beyond `action` styling | — | specified here, not yet implemented — deliberately deferred per [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) milestone 10 |

### Interaction — dismissal and keyboard rules

- **Focus trap.** While a modal dialog is open, `Tab`/`Shift+Tab` cycle only
  through the dialog's controls, wrapping at either end. Focus never reaches
  the scrimmed window. On open, focus lands on the first interactive control
  (or the field named in the flow, e.g. the file name in Save As); on close,
  focus returns to the invoking control.
- **`Esc`** dismisses the dialog as *Cancel* — identical to the Cancel button
  and the title-row close button. No data is committed.
- **`Enter`** activates the keyboard-default button (*OK* / *Save* / *Print*)
  unless focus is on a multiline edit or a control that consumes Enter; the
  default is always the footer primary except in the destructive pattern below.
- **`Space`** activates the focused control; arrow keys move within radio
  groups and lists without leaving the group.
- **Mnemonics.** Every label carries an `Alt+letter` mnemonic (existing VCL
  behavior, restated — not altered by this theme). `F1` opens Help, matching
  the footer Help button.
- Clicking the scrim does **not** dismiss a modal dialog (data-loss guard);
  this differs from transient overlays such as menus and the regex-builder
  popover, which close on outside click and `Esc`.

### Destructive-confirmation pattern

*Specified here, not yet implemented.* When a dialog confirms an irreversible
act (overwrite on save, "Don't Save", Replace All across a selection larger
than the document view):

- the message states the object and consequence, and offers a recovery route
  where one exists (per the accessibility contract, errors identify problem
  **and** recovery);
- footer order stays Help \| spacer \| safe secondary \| destructive primary;
- the destructive button uses `@error-container` fill with
  `@on-error-container` text (the only feedback pair the native palette
  declares — there is no base `error` role in `definition.xml`);
- initial focus and the `Enter` default bind to the **safe** action; the
  destructive action requires explicit navigation, so `Enter`-mashing cannot
  destroy data;
- the destructive label names the verb ("Delete 3 sheets", never "OK").

### Scrim & elevation rules

The scrim is a single full-window layer per modal level; stacked modals do not
multiply scrims. Elevation is expressed by **three cues together** — tonal
step (`@surface-container` sheet on `@surface` app), `@outline-variant`
hairline, and shadow — so containment survives high contrast, where the
prototype raises `--bw` to 2 px and flattens shadows against `#000000`
outlines. Per [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md), elevation must
never be encoded only by a low-contrast shadow. Transient overlays inside a
dialog (drop-downs, the regex builder) sit above the sheet with their own
`@surface` fill, hairline, and lighter shadow (`0 16px 40px rgba(0,0,0,.28)`),
never a second scrim.

### Accessibility

Role/name/state exposure is unchanged VCL: the dialog exposes a dialog role
named by its title; the title text is the accessible name source. Focus
indicator is the definition-backed `Focus` part (`@primary`,
`stroke-standard`) plus the field focus treatment (2 px `@primary` border).
Contrast: `@on-surface` on `@surface-container` and `@on-primary` on
`@primary` are covered by the standalone validator's contrast-pair checks;
the scrim never carries meaning. Color independence: the default button is
identified to assistive technology as the default, not merely by fill;
disabled states keep their glyphs (chapter 02). No accessibility result is
claimed — the suite is unbuilt.

### Density

Native metrics carry no density selection. The prototype's dialogs currently
pin their control geometry independent of the compact/comfortable toggle:
buttons 40 px, fields 44–48 px, title 18 px, against prototype density
variables of `--ctrl` 34/40 px and `--fs` 13/14 px. Target: dialog fields and
buttons adopt `--ctrl`, keeping the footer at one row height per density.
Native `size-standard-control` (36) remains the drawn control height reference.

### RTL & localization

The footer mirrors as a whole: Help stays at the inline start, the primary at
the inline end. Title-row close button moves to the inline start’s opposite
edge with the layout. Chevrons and breadcrumb separators mirror; the regex
pattern preview does **not** — regex source is directional LTR text and keeps
`direction:ltr` (specified here, not yet implemented). Long localized button
labels widen buttons via padding; action labels are never truncated — the
footer may wrap to a second line preserving order.

### Platform notes (Windows-first)

- Native dialogs remain OS-decorated top-level windows: Windows 11 rounds and
  shadows the frame itself, so the 16 px radius and custom shadow apply to the
  prototype rendering and to any future in-window (frameless) dialog surface —
  a deliberate difference, not a defect.
- OS-native file pickers may replace Save As per platform convention; the
  Material Save As in 8.3 is the in-suite variant.
- Windows printer graphics are excluded from the file-widget initialization
  path ([`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)); the Print dialog's
  preview must therefore never depend on file-theme drawing of printer DCs.

### Verification hooks

Per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md): run id
`YYYYMMDD-HHMMSS-<short-commit>-<platform>`, manifest + SHA-256 per capture.

- Headless: validator coverage of `pushbutton` (all 13 `Entire` states),
  `windowbackground`/`BackgroundDialog`, and `frame`/`Border` already runs
  source-side; a build adds headless draw tests for the same tuples.
- Screenshot checkpoints: dialog at rest (light/dark/HC × 100 %/150 % scale);
  footer order; focus ring on each footer button; disabled primary.
- Interaction: scripted `Esc`, `Enter`, and full `Tab` cycle proving the trap.
  The audited driver notes modifier-key input is unreliable cross-desktop, so
  mnemonic (`Alt+letter`) checks need a dedicated scenario or a documented
  caveat in `results.json`.

---

## 8.2 Options dialog

Invoked with `Tools ▸ Options…` (`Alt+F12`). Prototype title:
**Options — LibreOffice Writer**.

### Layout & regions

Two-pane master–detail inside a 760 px sheet (`min(760px, 94%)`), body height
340 px in the prototype.

| Region | Geometry (prototype) | Treatment |
| --- | --- | --- |
| Navigation tree | 220 px column, padding `0 8px 8px`, scrollable | Rows 34 px, `corner-small` radius, 2 px vertical rhythm; group rows carry `chevron_right`/`expand_more` 18 px glyphs; child rows indent 16 px |
| Selected nav row | — | `@primary-container` fill, `@on-primary-container` text ("General" in the reference) |
| Content pane | Remaining width; `@surface` background, `--bw` `@outline-variant` left hairline, `border-top-left-radius:12px` (`corner-container`), padding `20px 22px`, scrollable | Section heading `600 14px`; two-column field grid, gap `16px 14px` |
| Fields | 44 px outlined fields, `corner-container` radius, floating 11 px labels at `top:-7px` | Focused: 2 px `@primary` border, label `@primary`; invalid: 2 px `--err-base` border, label `--err-base`, 12 px message below |
| Footer | Help \| spacer \| Reset (text) \| Cancel (outlined) \| OK (filled) | Shared footer anatomy (8.1) |

The tree consumes the container-tree spec ([06-containers.md](06-containers.md));
natively its disclosure glyphs are `listnode` (`size-tree-node` = 20) and the
connector net is suppressed by the empty `listnet`/`Entire` state — both
implemented in definition.xml (unbuilt). The pane split itself is
prototype-only.

### Chrome variants

None — Options renders identically under classic and ribbon (notebookbar)
chrome; only the invoking surface differs.

### Key user flows

1. **Navigate → edit → commit.** Expand a group, pick a page, edit fields, OK
   commits all pages, Cancel discards, Reset restores the visible page's
   values (text button, guarded by the destructive pattern when it discards
   nonobvious state).
2. **Validation.** The reference page shows the pattern: a focused Email field
   (2 px `@primary`) and an invalid Backup path (`/backups/old`) with message
   "The path does not exist. Choose an existing folder." — problem plus
   recovery, in `--err-base` (prototype); natively the message pair uses
   `errorColor`/`errorTextColor` → `@error-container`/`@on-error-container`.

### Empty / loading / error states

Pages load synchronously; if a page cannot populate (e.g. no Java runtime),
the pane shows an explanatory body-role message with a recovery action — never
a blank pane (specified here, not yet implemented). Field-level errors as
above; OK stays enabled and refocuses the first invalid field rather than
silently dropping input.

### Density & adaptive width

Below ~808 px window width the sheet caps at 94 % and the field grid drops to
one column; the tree keeps 220 px until the sheet is narrower than 560 px,
then collapses to a page drop-down above the pane (specified here, not yet
implemented). Density per 8.1.

### Keyboard map

| Keys | Action |
| --- | --- |
| `Alt+F12` | Open Options |
| `Tab` / `Shift+Tab` | Cycle dialog controls (trapped) |
| `Up`/`Down`, `Left`/`Right` | Move / collapse / expand in the tree |
| `Enter` | OK (default); on a tree group: toggle expand |
| `Esc` | Cancel |
| `F1` | Help |

### Accessibility notes

Tree exposes standard VCL tree roles with `EXPANDED`/`SELECTED`; the content
pane is labelled by the selected page name so page switches are announced.
Selected nav row is carried by fill **and** selection state, not color alone.

### Verification checkpoints

Capture: default page, expanded "LibreOffice Writer" group, selected
"General", focused field, invalid field with message — light/dark/HC.
Scripted: full tree traversal by keyboard; `Esc` discards a dirty field;
`Enter` commits from the tree without activating a row toggle.

---

## 8.3 Save As dialog

Invoked with `File ▸ Save As…` (`Ctrl+Shift+S`). 560 px sheet.

### Layout & regions

| Region | Geometry (prototype) | Treatment |
| --- | --- | --- |
| Breadcrumb row | 13 px text, 18 px `folder` glyph, 16 px `chevron_right` | Path ancestors `@on-surface-variant`, current folder ("Reports") `@on-surface` |
| File name field | 48 px, `corner-container`, `@surface` fill | Focused on open: 2 px `@primary` border, floating label `@primary` on `--sc` |
| File type drop-down | 48 px outlined field with trailing 20 px `expand_more` | "ODF Text Document (.odt)"; consumes list box anatomy (06) |
| Password option | 20 px checkbox, `corner-checkbox` (3) radius, `@primary` fill with 15 px `@on-primary` check | Label "Save with password" |
| Footer | spacer \| Cancel (outlined) \| Save (filled) | No Help button in the prototype reference; target keeps the Help slot at inline start when help exists |

### Chrome variants

Identical under classic and ribbon chrome. On Windows the OS file picker may
substitute for full filesystem browsing (8.1 Platform notes); this surface is
the in-suite Material variant.

### Key user flows

Save: name pre-selected for overwrite typing → optional type change →
`Enter`/Save. Overwriting an existing file raises the destructive-confirmation
pattern (8.1) with the safe default on Cancel. Choosing "Save with password"
chains the password dialog before commit.

### Empty / loading / error states

Empty file name disables Save (dim `@disabled-container` fill) and `Enter`
refocuses the name field. Invalid characters mark the field with the 2 px
`--err-base` treatment and a recovery message. Slow network folders show the
determinate/indeterminate progress treatment from
[07-feedback.md](07-feedback.md) in the breadcrumb row, never a frozen sheet
(specified here, not yet implemented).

### Density & adaptive width

Single column throughout; the sheet caps at 94 % width below ~596 px. Field
heights follow the 8.1 density target.

### Keyboard map

`Ctrl+Shift+S` open · `Tab` cycle (trapped) · `Enter` Save · `Esc` Cancel ·
`Alt+Down` open the type drop-down · `Space` toggle the password checkbox.

### Accessibility notes

The name field's floating label ("File name") is its accessible name; the
breadcrumb is exposed as static text describing the destination. Checkbox
state is exposed as checked/unchecked, drawn per the native `checkbox`
contract (chapter 03) — never color-only.

### Verification checkpoints

Capture: fresh dialog with focused name field; open type drop-down; checked
password option; disabled Save on empty name. Scripted: `Esc` returns focus to
the document; overwrite path raises confirmation with safe default.

---

## 8.4 Print dialog

Invoked with `File ▸ Print…` (`Ctrl+P`). 720 px sheet.

### Layout & regions

| Region | Geometry (prototype) | Treatment |
| --- | --- | --- |
| Preview column | 220 px wide; page thumbnail 170 × 220 px, `@surface` fill, `--bw` `@outline-variant` border, 6 px radius, shadow `0 6px 18px rgba(0,0,0,.14)` | Grey `@outline-variant` placeholder text bars in the prototype; a build renders the real page |
| Pager | Two 32 px circular outlined icon buttons (`chevron_left`/`chevron_right`, 18 px) around a "1 / 3" label | `@on-surface-variant` label, 13 px |
| Printer field | 48 px outlined drop-down, trailing 20 px `expand_more` | "HP LaserJet Pro M404", floating label "Printer" |
| Copies field | 48 px, 120 px wide, shown focused (2 px `@primary`) | Floating label "Copies" in `@primary` |
| Range radios | Column, 10 px gap, under a `500 13px` "Range" heading | **All pages** / **Pages: 1-3** / **Selection**; 20 px circular radio, 2 px border (`@primary` selected, `@on-surface-variant` idle), 10 px `@on-primary` dot |
| Footer | spacer \| Cancel (outlined) \| Print (filled) | Shared footer anatomy |

The prototype draws these radios as 20 px circles; the native `radiobutton`
contract draws a 24 px (`size-selection-control`) rounded square at
`corner-control` (10) — the native drawing wins for the build; the circular
form is prototype-only. State tokens (idle/hover/pressed/disabled) follow
chapter 03.

### Chrome variants

Identical under classic and ribbon chrome.

### Key user flows

Print with defaults (`Ctrl+P`, `Enter`); change range (choosing "Pages"
focuses its edit for a range string); page through the preview; switch
printer. Selecting "Selection" with no document selection disables that radio
rather than failing at print time.

### Empty / loading / error states

Preview shows an indeterminate progress treatment while rendering
(07-feedback); no printers found replaces the printer field with an
explanatory message and a "Use PDF export" recovery action (specified here,
not yet implemented). Printer errors use the `@error-container` /
`@on-error-container` pair.

### Density & adaptive width

Below ~766 px the preview column stacks above the controls; the thumbnail
keeps its 170 × 220 aspect. Density per 8.1.

### Keyboard map

`Ctrl+P` open · `Tab` cycle (trapped) · `Up`/`Down` within the radio group ·
`Left`/`Right` page the preview when the pager has focus · `Enter` Print ·
`Esc` Cancel.

### Accessibility notes

The radio group is named "Range"; the pager announces "page 1 of 3" on
change. The preview is decorative for AT purposes — all printable state is
reachable through the labelled controls. Windows printer DCs bypass file-theme
drawing (8.1), so nothing in this dialog's evidence may claim themed printer
output.

### Verification checkpoints

Capture: default state; "Pages" selected; preview on page 2; disabled
"Selection". Scripted: radio traversal with arrows stays in-group; `Enter`
does not activate a focused radio's dialog default incorrectly.

---

## 8.5 Find & Replace dialog

Invoked with `Edit ▸ Find & Replace…` (`Ctrl+H`); the toolbar's Find & Replace
button routes to the same surface. 680 px sheet; uniquely, the sheet uses
`overflow:visible` so the regex-builder popover may escape the container.

### Layout & regions

| Region | Geometry (prototype) | Treatment |
| --- | --- | --- |
| Find field | 44 px pill (`corner-pill`), `--sc` fill, 20 px `search` glyph, hairline `@outline-variant` border | Invalid regex: border becomes 2 px `--err-base`; regex mode switches the input to a monospace stack |
| Field trailing controls | Clear (28 px), `.*` mode toggle (28 px tall, `aria-pressed`; `@primary`/`@on-primary` when active), builder toggle (30 px, `tune` glyph, `aria-expanded`) | Shared search anatomy — see [04-inputs.md](04-inputs.md) |
| Options row | Three 18 px checkboxes (`corner-checkbox`), gap `14px 22px` | **Match case** (inverts the `i` flag), **Whole words only**, **Regular expressions** (mirrors the `.*` toggle) |
| Replace field | 44 px outlined input (`corner-container`), floating label "Replace", placeholder "Replace with…" | A real `<input>` in the prototype (`id="fr-replace"`), preserving native caret across re-renders |
| Match summary | `600 12px` row: "Document" + summary in `@primary` | "N match(es) in M of 5 paragraphs", or the empty-state prompt |
| Document preview | Scrollable region, `max-height:150px`, `--scl` fill, `corner-container` radius, hairline border | One row per paragraph run; matched rows get a 3 px `@primary` left bar and a 55 % `@primary-container` wash |
| Match highlight | `<mark>` on `@primary` with `@on-primary` text, 3 px radius, `0 1px` padding | Live per keystroke |
| Footer | Find All, Find Next \| spacer \| Replace (outlined), **Replace All** (filled, `0 22px` padding) | Search actions inline-start, mutating actions inline-end |

### Integrated regex builder (prototype-only)

The builder popover opens from the field: `top: calc(100% + 6px)`, full field
width, `z-index:70`, `max-height:340px`, `@surface` fill, `corner-container`
radius, shadow `0 16px 40px rgba(0,0,0,.28)`, 14 px padding, 120 ms `lo-pop`
entrance. Contents:

- **Pattern preview** between literal `/` delimiters, monospace, with four
  30 px flag toggles — `i` (ignore case), `g` (global), `m` (multiline),
  `s` (dotall) — as `aria-pressed` buttons (`@primary` fill when on).
- **Token groups** — Anchors, Classes, Quantifiers, Groups, Escapes — as
  28 px monospace chips (e.g. `\b`, `[ ]`, `{n,m}`, `(?: )`, `\.`); a chip
  inserts its token at the caret, landing the caret inside brackets/groups.
- **Status line**: empty → "Type or build a pattern — N items"; invalid →
  "Invalid pattern: *message*" in `--err-base` weight 600; valid → matched
  count in `@primary` with `/pattern/flags` echoed in regex mode; plus a
  Clear pill.

Compilation rules (prototype behavior, the target semantics): literal mode is
a case-insensitive substring with metacharacters escaped; Match case strips
the `i` flag; **Whole words only** wraps the pattern as `\b(?:pattern)\b`;
invalid patterns match nothing and surface the error instead of throwing.

### Replace All reporting

`Replace All` reports through the suite snackbar (07-feedback): fixed,
bottom-centred 26 px above the edge, `@inverse-surface` fill with
`inverse-on-surface` text, 8 px radius, `13px 20px` padding, auto-dismissed
after 1.9 s. Messages: "Replaced N occurrence(s) with “X”" or "No matches to
replace". The count is computed across all paragraph runs with the global
flag. Target additions (specified here, not yet implemented): the snackbar is
announced politely to AT, and a document-wide Replace All above a size
threshold uses the destructive-confirmation pattern with undo as the recovery
action.

### Chrome variants

Identical under classic and ribbon chrome; the dialog is modeless against the
document in the target (find-as-you-type needs the canvas live), while the
prototype stages it modally over a scrim for demonstration.

### Key user flows

Type → matches highlight live in the preview and summary; toggle `.*` or the
"Regular expressions" checkbox (they mirror each other) → monospace pattern
editing with the builder one click away; insert tokens → caret lands inside
`()`/`[]`; `Replace All` → snackbar report; invalid pattern → red field
border plus builder error, actions find nothing rather than erroring.

### Empty / loading / error states

Empty query: summary reads "Enter a search term or build a pattern." and no
rows are washed. Invalid regex: error treatments above. No matches:
"0 matches in 0 of 5 paragraphs" and Replace All reports "No matches to
replace" — every state is textual, not color-only.

### Density & adaptive width

Sheet caps at 94 % below ~723 px; the options row wraps (`flex-wrap`); the
builder popover always spans the field width and scrolls beyond 340 px.
Control heights follow the 8.1 density target.

### Keyboard map

`Ctrl+H` open (`Ctrl+F` opens the lighter find bar) · `Enter` in the Find
field = Find Next · `Tab` cycle (trapped while staged modally) · `Esc` closes
the builder popover first, then the dialog · `Space` toggles option
checkboxes · `Alt+Down` on the field opens the builder (specified here, not
yet implemented).

### Accessibility notes

The `.*` toggle exposes `aria-pressed` and the builder toggle `aria-expanded`
(prototype attributes; native equivalents are toggle-button pressed state and
expanded state). The Replace input carries `aria-label="Replace with"`. Match
results are announced via the summary line text change; highlights pair
`@primary` fill with the row's left bar so matches survive monochrome
rendering. `@on-primary` on `@primary` is a validator-checked pair.

### Verification checkpoints

Capture: literal match state ("revenue", 4 matches highlighted), regex mode
with builder open, invalid-pattern error, whole-word difference, Replace All
snackbar — light/dark/HC. Scripted: caret-placement after token insertion;
flag toggles change the live count deterministically; `Esc` layering
(builder → dialog); snackbar text matches the computed count.

---

## Cross-references

- Buttons and disabled affordances: [02-actions.md](02-actions.md)
- Checkboxes and radios: [03-selection.md](03-selection.md)
- Fields, search, and regex-builder input anatomy: [04-inputs.md](04-inputs.md)
- Trees, lists, frames: [06-containers.md](06-containers.md)
- Progress, snackbars: [07-feedback.md](07-feedback.md)
- Evidence format for every checkpoint above:
  [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md)
