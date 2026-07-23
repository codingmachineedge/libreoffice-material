# 08 — Dialogs & overlays

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md). Required native definition/dispatch targets
> have compiled and executed. The accepted application proof is limited to the
> Start Center; no dialog, overlay, dialog interaction, accessibility, or pixel
> checkpoint specified in this chapter has been registered.

This chapter specifies the modal dialog family: the shared modal anatomy and its
scrim, keyboard, and elevation rules, followed by the four reference dialog
surfaces realized in the prototype — Options, Save As, Print, and Find &
Replace. Sections 8.6–8.16 then apply that shared anatomy — together with the
destructive-confirmation, notification-routing, link (§5 of
[02-actions.md](02-actions.md)), and input (04) contracts it references — to the
real upstream Windows system-dialog families: PDF export, Document Properties,
Template Manager, the Extension manager, macro manager and security prompts,
certificate/signature prompts, document recovery and Safe Mode, migration
decisions, credential dialogs, and Help/About. Each of those is a composition
applied to an existing dialog, never a new visual design and never a
prototype-realized surface. Normative inputs are [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)
(component-behavior contract), [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md)
(token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, compiled at commit 577059e274; surface state unverified), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Implementation status is labelled per feature as *implemented in
definition.xml (compiled at commit 577059e274; surface state unverified)*, *prototype-only*, or *specified here, not yet
implemented*. These labels describe source provenance; executed native
definition/state assertions are not dialog runtime proof. Button variants are
specified in [02-actions.md](02-actions.md);
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
| Dialog background | `windowbackground`/`BackgroundDialog` fills `@surface-container`; `<style>` maps `dialogColor` → `@surface-container`, `dialogTextColor` → `@on-surface` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Container | `@surface-container` (`--sc`) sheet, `--bw` (1 px; 2 px high contrast) `@outline-variant` border, **16 px** corner radius, shadow `0 24px 64px rgba(0,0,0,.4)`, width `min(W px, 94%)` | prototype-only (`dlgWrap`) |
| Scrim | Full-window overlay: light `rgba(20,18,24,.38)`, dark `rgba(0,0,0,.6)`, high contrast `rgba(0,0,0,.65)` (`--scrim`) | prototype-only (`PAL.*.scrim`) |
| Title row | `18px/1` at weight 600 on `@on-surface`; padding `18px 20px 14px`; trailing 34 × 34 px close icon button (`corner-small` radius, 20 px glyph, `@on-surface-variant`) | prototype-only; native `title` type role = 120 % scale, `semibold` minimum; `height-window-title` = 18 |
| Content region | Consumes field, selection, list, and frame components from chapters 03–06 on the `@surface-container` sheet; grouped regions may use the native outlined frame (`frame`/`Border`: `@outline-variant` stroke, `@surface-container` fill, `stroke-thin`, `corner-container`) | frame implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Footer button row | Order **Help \| spacer \| secondary \| primary**; padding `14px 20px`, 10 px gap, `stroke-thin` `@outline-variant` top hairline; all buttons 40 px tall, `corner-pill` (20) radius | prototype-only (`dlgFooter`); button states implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Primary (filled) button | `@primary` fill, `@on-primary` text, padding `0 28px`; native `pushbutton` `extra="action"` states | implemented in definition.xml (compiled at commit 577059e274; surface state unverified); geometry prototype-only |
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

*Source-implemented 2026-07-21 (unbuilt): the shared
`sfx2::ConfirmDestructiveAction` helper realizes this pattern with the safe
action holding both initial focus and the Enter default; the real destructive
confirmations enumerated across this chapter are converted and registered in the
fail-closed `dialog-anatomy-policy.json` contract. No build or runtime evidence
exists yet.* When a dialog confirms an irreversible
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
disabled states keep their glyphs (chapter 02). No **dialog** accessibility
result is claimed: the accepted bounded UNO trees cover only the Start Center,
not any surface in this chapter.

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

- Native source gate: validator coverage of `pushbutton` (all 13 `Entire`
  states), `windowbackground`/`BackgroundDialog`, and `frame`/`Border` runs
  source-side, and the required native definition/draw target has compiled and
  executed command/region assertions for these contracts. No dialog pixels
  have been compared.
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
implemented in definition.xml (compiled at commit 577059e274; surface state unverified). The pane split itself is
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

### Source binding

The dialog shell is source-pinned by
[`bin/check-windows-options-dialog-contract.py`](../../bin/check-windows-options-dialog-contract.py)
against [`options-dialog-composition.json`](../../qa/windows-ui-contract/options-dialog-composition.json):
the modal `optionsdialog.ui` tree (`GtkTreeView` `pages` over a `GtkTreeStore`,
tree-lines on, headers off), the twelve ordered top-level option groups from
`cui/inc/treeopt.hrc` with their `AddGroup` guard conditions, the footer
action-widget order and response codes, and the shared native `listnode` /
`listnet` tree parts in `definition.xml` (resolved in both palettes). The
already-realized `RegexSearchController` on `searchEntry` /
`searchEntry_regex_builder` is cited read-only as a satisfied dependency
([04-inputs.md](04-inputs.md), WIN-INP-005), never re-integrated here.

One honest **footer-drift carve-out** is pinned: the master–detail footer above
names Help \| Reset \| Cancel \| OK (four action-widgets —
`help` / `revert` / `cancel` / `ok`), but the real `.ui` button box also carries
a fifth **Apply** button (`ApplyHdl_Impl`) that has no response code and is
**absent** from `<action-widgets>`. The contract pins Apply as
present-but-not-an-action-widget so it can never be silently added to or dropped
from the action set. Row-selection fill (`@primary-container`), the exhaustive
per-group leaf-page set, the adaptive tree→dropdown collapse, and the
field-grid / floating-label treatment are held as `status: specified`
carve-outs — no source pins them yet. `runtime_verified` is false; no dialog
pixels are claimed.

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

### 8.3.1 File-flow platform delegation & surrounding message boxes

*Application of the 8.1 Platform notes and the 8.1 destructive-confirmation
carve-out — no novel visual design.* The common Open/Save file flows split into
a platform-delegated picker and a small set of in-suite message boxes; this
subsection pins the Material boundary between them.

**Platform delegation (Windows).** On Windows the Open/Save picker is the
OS-owned native `IFileDialog` (`CLSID_FileOpenDialog` / `CLSID_FileSaveDialog`,
`fpicker/source/win32`), and its overwrite confirmation is drawn by the OS from
the `FOS_OVERWRITEPROMPT` flag — both are out of Material scope and are never
re-skinned or faked as a Material sheet. The in-suite Material Save As sheet
(8.3) is the fallback variant, selected across the
`SystemFilePicker → OfficeFilePicker` seam in
`sfx2/source/dialog/filedlghelper.cxx` when the OS picker is unavailable; that
in-suite picker and its pixels belong to WIN-DLG-003 and are not respecified
here. Because the OS owns the overwrite prompt on this path, **no
`sfx2::ConfirmDestructiveAction` conversion is applied here** (contrast the 8.1
destructive-confirmation pattern): the platform already guards the overwrite.

**Surrounding call-site message boxes.** The save flow raises three C++
call-site message boxes in `filedlghelper.cxx` that have no `.ui` file. The
`.ui`-only notification policy cannot see them, so they are classified here
under the same NotificationRouter taxonomy ([07-feedback.md](07-feedback.md)
§7.5) and all stay modal:

| Message box | Shape | Class | Routing |
| --- | --- | --- | --- |
| Losing scripting signature | Question / Yes-No | decision | modal; never routed to the bottom-right stack |
| GPG encryption failure | Warning / OK | security acknowledgment | modal; security prompts stay modal |
| Password too short | Warning / OK | credential-adjacent acknowledgment | modal; never routed |

None is a pure informational acknowledgment eligible for the §7.5 bottom-right
stack, so none is converted to a snackbar. The boxes are repositioned by the
shared Windows dialog-placement seam (`vcl` `dialog.cxx`/`event.cxx`), and the
related `.ui` roots that *do* exist — `querysavedialog`, the sfx2 `password`
dialog, and `remotefilesdialog` — keep their `native-exclusion` policy in
`dialog-notification-policy.csv` (walked read-only, not re-registered here).
Status: the delegation boundary and the three call-site boxes are source-pinned
(unbuilt) by
[`bin/check-windows-file-flow-contract.py`](../../bin/check-windows-file-flow-contract.py);
`runtime_verified` is false and no picker pixels are claimed.

### 8.3.2 In-suite Office file picker — source binding

When the OS `IFileDialog` is unavailable the in-suite Material Save As sheet
(§8.3) is drawn by the fallback `OfficeFilePicker`
(`fpicker/source/office/iodlg.cxx`, `fpicker/uiconfig/ui/explorerfiledialog.ui`).
It is an application of the **Modal dialog — shared anatomy** (§8.1) — the same
`@surface-container` sheet, footer order, scrim, and focus-trap rules — with no
novel visual design of its own. It is source-pinned by
[`bin/check-windows-office-filepicker-contract.py`](../../bin/check-windows-office-filepicker-contract.py)
against
[`office-file-picker-composition.json`](../../qa/windows-ui-contract/office-file-picker-composition.json),
which binds the four §8.3 regions to their real widget ids — **breadcrumb row →
`current_path`**, file name → `file_name`, file type → `file_type`, password →
`password` — and their `weld_*` bindings.

A load-bearing correction is pinned here: the §8.3 *Breadcrumb row* is the plain
`current_path` `SvtURLBox` combo, **not** `breadcrumb.ui` — that control belongs
exclusively to the already-native-excluded remote-files picker
(`RemoteFilesDialog`), so a guard forbids any `breadcrumb` reference in
`iodlg.cxx` to keep the pin honest. The picker's own overwrite-confirmation box
(`STR_SVT_ALREADYEXISTOVERWRITE`, Question / Yes-No) is the source backing for
§8.3's "Overwriting an existing file raises the destructive-confirmation pattern
… with the safe default on Cancel": any outcome other than *Yes* aborts the
write, and the box stays modal. `explorerfiledialog.ui` and `foldernamedialog.ui`
keep their `native-exclusion` classification, and the upstream `OfficeFilePicker`
seam is cited read-only. `runtime_verified` is false; no picker pixels are
claimed.

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

## 8.6 Export options — tabbed dialog (PDF)

*Application of the 8.1 shared modal anatomy and the 8.2 Options master–detail
navigation to the real PDF options dialog
(`filter/uiconfig/ui/pdfoptionsdialog.ui`, built by
`filter/source/pdf/impdialog.cxx`) — no novel visual design.*

### Anatomy & tokens

The export sheet is the same `@surface-container` modal sheet with the same
footer contract as 8.1: **Help \| spacer \| secondary Cancel \| primary
Export** (`.ui` action widgets `ok`/`E_xport` = −5, `cancel` = −6, `help` =
−11). Unlike the destructive-confirmation pattern, the **primary is the `Enter`
default** here because Export is non-destructive; the 8.1 destructive pattern is
explicitly **not** used (no `@error-container` primary, no safe-action default).

### Vertical tab navigation

The dialog is a data-driven `SfxTabDialogController`: a `GtkNotebook`
(`tab-pos=left`) is the export analogue of the 8.2 Options navigation tree — a
left tab list selecting a detail page. It reuses the native `tabitem` states
(selected → `@primary-container` / `@on-primary-container`, focus → `@primary`
ring) from `definition.xml` rather than a new control. The exact rail width and
24 px icon geometry are *specified here, not yet implemented* — `definition.xml`
declares no rail-width metric, so the rail dimensions cannot be pinned build-free.

### Content grouping & tab set

Each page groups its options in outlined `frame`/`Border` regions
(`@outline-variant` stroke, `@surface-container` fill, `stroke-thin`,
`corner-container`), per the 8.1 content-region rule. `AddTabPage` composes six
pages in a fixed order, each bound to its own `.ui`:

| Order | Tab / page root | Grouped regions |
| --- | --- | --- |
| 1 | General (`PdfGeneralPage`) | Range, Images, Watermark, General |
| 2 | Initial View (`PdfViewPage`) | Panes, Magnification, Page Layout |
| 3 | User Interface (`PdfUserInterfacePage`) | Window Options, User Interface Options, Transitions, Collapse Outlines |
| 4 | Links (`PdfLinksPage`) | General, Cross-document Links |
| 5 | Security (`PdfSecurityPage`) | File Encryption and Permission, Printing, Changes, Content |
| 6 | Digital Signatures (`PdfSignPage`) | X.509 Certificate |

The tab/notebook/frame parts are *implemented in definition.xml (compiled at
commit 577059e274; surface state unverified)*; the ordered composition is
source-pinned (unbuilt).

### Interaction & modal policy

`Esc` = Cancel, `Enter` = Export, focus trap and `F1` = Help per 8.1. The
PDF/UA accessibility pre-export warning (`WarnPDFDialog`, `impdialog.cxx`
`OkHdl`) is an informational modal that **stays modal** — it is not folded into
the §7.5 bottom-right stack. The input-collecting export dialog is a
`native-exclusion` / KeepModal root in `dialog-notification-policy.csv`, so it
can never be reclassified out of modal.

### Verification hooks

Source-pinned by
[`bin/check-pdf-export-dialog-contract.py`](../../bin/check-pdf-export-dialog-contract.py)
(notebook + Export-default footer, each tab's Create class + page `.ui` root +
group frames, the native `tabitem`/`tabpane`/`tabbody`/`frame` parts, and the
KeepModal exclusions). Tab-rail geometry, per-field signing anatomy, and
non-PDF export formats (EPUB/XHTML) are carved out spec-only; `runtime_verified`
is false and no dialog pixels are claimed.

---

## 8.7 Document Properties — multi-tab (icon-rail) dialog

*Application of the 8.1 shared anatomy and the 8.2 Options navigation treatment
to the upstream Document Properties dialog
(`sfx2/uiconfig/ui/documentpropertiesdialog.ui`, driven by
`sfx2/source/dialog/dinfdlg.cxx`) — no novel visual design.* Its entire Material
treatment is delivered by shared vcl parts; nothing in `dinfdlg.cxx` draws
anything Material.

### Layout & regions

Title row + a left **icon-tab rail** + content pane + footer. The rail derives
from the 8.2 navigation-tree treatment: the selected tab is `@primary-container`
fill / `@on-primary-container` text; the content pane is `@surface` with an
`@outline-variant` hairline and `corner-container` radius. The real `.ui` footer
is **Reset (`reset`, 101, text) \| OK (`ok`, −5, filled) \| Cancel (`cancel`,
−6, outlined) \| Help (`help`, −11, secondary)**, mapped onto the 8.1 footer
order.

### Native tab part contract

| Part | Treatment | Status |
| --- | --- | --- |
| `tabitem` (8 states) | `corner-pill` radius; selected fill `@primary-container`, text `@on-primary-container`; focus `@primary` ring | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| `tabheader` strip | `@surface-container` band | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| `tabpane`/`tabbody` | content frame on `@surface-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

These are the same native parts documented in [05-navigation.md](05-navigation.md);
no re-drawing is specified here. The `notebook` is `tab-pos=left` with the
`icons` group; the rail identity is the `RID_L` (`cmd/32/`) 32 px large-icon set.
The 32 px icon downscale, pill hover-raise, and rail width are the native
parts' pixel gate — *specified here, not yet implemented* (deferred to a build
host).

### Tab page set

Six master–detail pages, each an `SfxTabPage` with its own `.ui` root:
**General** (`RID_TAB_ORGANIZER`), **Description**, **Custom Properties**,
**CMIS Properties** (conditional), **Security** (conditional), **Font**. The
fields, checkboxes, and frames *inside* each page are the shared components of
chapters [03](03-selection.md)/[04](04-inputs.md)/[06](06-containers.md) and are
not respecified here.

### Interaction & keyboard

Reuse the 8.1 focus-trap / `Esc` = Cancel / `Enter` = OK-default / arrow-in-rail
rules and the 8.2 page-switch announcement, restated for the notebook:
`Ctrl+Tab` and arrow keys move the rail selection; the content pane is labelled
by the selected tab so page switches are announced. `STR_SFX_QUERY_WRONG_TYPE`
(the OK/Cancel query raised when a custom-property value does not fit its
declared type, `dinfdlg.cxx`) is an explicit **non-destructive carve-out**: it
coerces a typed value and destroys no data, so it is deliberately **not**
converted to `sfx2::ConfirmDestructiveAction`.

### Accessibility, RTL, density, platform, verification

Accessibility, RTL/localization, density, and platform behaviour inherit 8.1 and
8.2 by reference. No dialog runtime or pixel evidence is claimed (only the Start
Center bounded trees are accepted, per the chapter status banner). Source-pinned
by
[`bin/check-windows-document-properties-contract.py`](../../bin/check-windows-document-properties-contract.py)
(the native icon-tab part contract in both palettes plus the `.ui`/`.cxx`
composition); the inline custom-property row editor (`linefragment.ui`) and
`EditDurationDialog` treatment are deferred; `runtime_verified` is false.

---

## 8.8 Template Manager & Save As Template

*Application of the 8.1 shared modal anatomy and destructive-confirmation
pattern to the template flows — no novel visual design.*

### Anatomy & controls

The three roots are `@surface-container` modal sheets with the 8.1 footer order
**Help \| spacer \| secondary \| primary**:

- **Template Manager** (`SfxTemplateManagerDlg`, `templatedlg.ui`) — Help \|
  Close \| filled primary *New from Template* (`STR_NEW_FROM_TEMPLATE`), plus a
  secondary *Show this dialog at startup* checkbox.
- **Save As Template** (`saveastemplatedlg.ui`) — Help \| Cancel \| filled
  *Save* (`STR_SAVEDOC`).
- **Templates Category** (`templatecategorydlg.ui`) — the category picker.

Controls derive from chapter [04](04-inputs.md): the search field with the regex
builder pill is the **already-realized** `RegexSearchController` on
`search_filter` + `search_filter_regex_builder` (cross-referenced, never
restated); the two `GtkComboBoxText` filters and the `_Manage` menu button; the
thumbnail/list view toggle pair (chapter [03](03-selection.md) toggle state);
the *Set as default template* and *Enter template name* fields (04); and the
category tree (chapter [06](06-containers.md) list/tree).

### Destructive confirmations

Two irreversible acts apply the 8.1 destructive-confirmation pattern through the
shared `sfx2::ConfirmDestructiveAction` helper — safe **Cancel** holds the
initial focus and the `Enter` default, and the destructive primary uses
`@error-container`:

| Act | Verb | Safe default | Source | Status |
| --- | --- | --- | --- | --- |
| Overwrite an existing template | Overwrite | Cancel | `saveastemplatedlg.cxx` `OkClickHdl` (`STR_QMSG_TEMPLATE_OVERWRITE`) | source-implemented (unbuilt) |
| Delete a template category | Delete | Cancel | `templatedlg.cxx` `OnCategoryDelete` (`STR_QMSG_SEL_FOLDER_DELETE`) | source-implemented (unbuilt) |

Both are real conversions of the former ad-hoc `weld::MessageDialog`
confirmations, registered in the shared `dialog-anatomy-policy.json` contract
and validated against source by
[`bin/check-material-dialog-anatomy.py`](../../bin/check-material-dialog-anatomy.py)
alongside the other 8.1 destructive-confirmation migrations. No build or runtime
evidence exists; pixel, density, RTL, and card-thumbnail treatment are carved
out spec-only. The Start Center **Templates** entry point that reaches this
dialog is mapped in [09-start-center.md](09-start-center.md) §9.3/§9.10.

---

## 8.9 Extension manager & dependency dialogs

*Application of the archive-backed patterns to
`desktop/source/deployment/gui` — no novel visual design.*

### Shared shell

The Extensions dialog (`extensionmanager.ui`/`ExtensionManagerDialog`) and its
satellites — `dependenciesdialog.ui`, `updatedialog.ui`,
`updateinstalldialog.ui`, `updaterequireddialog.ui`, `installforalldialog.ui`,
`licensedialog.ui`, `showlicensedialog.ui`, and the `extensionmenu.ui` menu —
are modal `@surface-container` sheets applying the 8.1 modal anatomy (title row,
content region, footer **Help \| spacer \| secondary \| primary**, scrim, focus
trap, `Esc` = Cancel, `Enter` = default).

### Action set & links

Options / Check for Updates / Add / Remove / Enable and the Close/Help footer map
to the chapter [02](02-actions.md) button variants (filled default *Add*,
tonal/text secondaries). *Get more extensions online…* maps to the link contract
(§5 of [02-actions.md](02-actions.md)). The extension **search field + regex
builder toggle** is the shared search anatomy of chapter [04](04-inputs.md)
(WIN-INP-005) — cross-referenced, not respecified.

### Remove-extension destructive confirmation

Removing an extension applies the 8.1 destructive-confirmation pattern:
`@error-container` primary, verb label **Remove**, and the safe **Cancel** holds
initial focus and the `Enter` default so `Enter`-mashing cannot uninstall.
Source-implemented (unbuilt) as `ExtMgrDialog::removeExtensionWarn` in
`dp_gui_dialog2.cxx` via `sfx2::ConfirmDestructiveAction`, registered in
`dialog-anatomy-policy.json` and validated by
[`bin/check-material-dialog-anatomy.py`](../../bin/check-material-dialog-anatomy.py).

### Feedback & modal policy

The add/update/remove progress bar applies the chapter [07](07-feedback.md) §7.1
determinate progress. The dependency-check, install-for-all, license-accept, and
update-required prompts **stay modal** and are **not** routed to the §7.5
bottom-right notification stack — each collects a decision or consent, so it
holds the `native-exclusion` / KeepModal classification in
`dialog-notification-policy.csv` (cite [07-feedback.md](07-feedback.md)
§7.5/§7.8). The per-extension list-item and dependency-tree container anatomy is
documented in [06-containers.md](06-containers.md); the custom-drawn list-item
`Paint` (`dp_gui_extlistbox.cxx`) is deferred (build-only). `runtime_verified`
is false.

---

## 8.10 Macro manager, organizer & security prompts

*Application of existing archive-backed patterns to the Basic macro organizer and
macro-execution security prompt — no novel visual design.*

### 8.10.1 Delete & replace confirmations

The Basic macro/library/module/dialog delete and replace confirmations funnel
through the single shared `QueryDel()` helper in
`basctl/source/basicide/bastypes.cxx` (delete macro, replace macro, delete
dialog, delete library / library-reference, delete module). Their **target**
treatment is the 8.1 destructive-confirmation pattern — object plus the shared
consequence *This action cannot be undone.*, footer **Help \| spacer \| safe
Cancel \| verb-named destructive primary** at `@error-container`, with the safe
action holding initial focus and the `Enter` default, routed through
`sfx2::ConfirmDestructiveAction`. Status: **specified here, not yet
implemented** — `QueryDel` currently raises an ad-hoc
`VclMessageType::Question` / `VclButtonsType::YesNo` box in which the
destructive answer is `Enter`-answerable; the conversion is a documented
deferral, not a shipped change.

### 8.10.2 Macro-execution security prompt

The Enable/Disable-macros prompt (`uui/uiconfig/ui/macrowarnmedium.ui`,
`uui/source/secmacrowarnings.cxx`) applies the 8.1 modal rules with a
**security-decision safe default**: *Disable Macros* is both the GTK default and
the initially-focused control (`grab_focus`), and *Enable Macros* requires
deliberate navigation — generalizing the 8.1 destructive safe-default principle
to a security decision and honouring the
[00-windows-rewrite-contract.md](00-windows-rewrite-contract.md) rule that
security/credential/destructive prompts stay modal and never route to the
bottom-right notification form. This preserves existing safe behaviour so no
refactor lets an accidental `Enter` run untrusted macros.

### 8.10.3 Manager & organizer dialogs

The macro selector tree, the Basic organizer two-pane, the assign dialog, and the
library/module managers are consumers of the 8.1 shared modal anatomy plus
chapter [06](06-containers.md) trees/lists, chapter [02](02-actions.md) buttons,
and chapter [04](04-inputs.md) fields. Modality is retained; no bespoke geometry
is claimed.

### 8.10.4 Scope carve-out

The Basic IDE code editor itself (`baside2*`, watch/stack/object-catalog,
breakpoint gutter — custom-drawn, no `.ui`-composable anatomy) and the
macro-security-**level** / certificate / signature dialogs (owned by 8.11 /
WIN-SYS-007) are explicitly deferred to a build host. This is a documented
deferral, not a gap. Routing rationale (why these stay modal, not snackbars)
lives in [07-feedback.md](07-feedback.md) §7.5 and the NotificationRouter
classification.

---

## 8.11 Security-classified prompts — modal application

*Application of the 8.1 shared modal anatomy and the 8.2 master–detail treatment
to the certificate/signature/macro-security family
(`xmlsecurity/source/dialogs`, `cui/source/options/certpath.cxx`) — no novel
visual design.*

### Anatomy & per-dialog footers

Each root is a `@surface-container` modal sheet with the 8.1 footer order and
keyboard dismissal rules. The real modal footers observed in the `.ui` files:

| Dialog | Footer (response codes) |
| --- | --- |
| `DigitalSignaturesDialog` | Help (−11) \| Close (−7) |
| `MacroSecurityDialog` | Reset (101) \| OK (−5) \| Cancel (−6) \| Help (−11) |
| `SelectCertificateDialog` | OK (−5) \| Cancel (−6) \| Help (−11) |
| `ViewCertDialog` | OK (−5) \| Help (−11) |
| `CertDialog` (certpath) | Add (101) \| Cancel (−6) \| OK (−5) \| Help (−11) |

### Tabbed surfaces

The two tabbed security surfaces apply the 8.2 Options notebook anatomy as
embedded page composition, not redraw: **Macro Security**
(`SecurityLevelPage` / `SecurityTrustPage`) and the **Certificate Viewer**
(`CertGeneral` / `CertDetails` / `CertPage`).

### Classification & routing precedence

Per the *Next checkpoint* in
[02-notification-service-architecture.md](02-notification-service-architecture.md)
(prompts that enforce security keep their modal semantics) and
[07-feedback.md](07-feedback.md) §7.5 (`NotificationRouter::Classify` never
forces security prompts to the toast stack), the four `xmlsecurity` roots stay
modal via the **security** exclusion, while certpath's `CertDialog` stays modal
via the **input** precedence rather than the security token — an honest
distinction, not a re-label.

### Destructive action within a modal

The *Remove signature* action inside `DigitalSignaturesDialog`
(`xmlsecurity/source/dialogs/digitalsignaturesdialog.cxx`, `canRemove`) applies
the 8.1 destructive-confirmation pattern (verb label *Remove*, safe **Cancel**
as default and initial focus) — reuse, not novel design. Status:
**source-implemented (unbuilt)** — the former ad-hoc `VclMessageType::Question`
/ `VclButtonsType::YesNo` box (`STR_XMLSECDLG_QUERY_REALLYREMOVE`) is converted
to `sfx2::ConfirmDestructiveAction` and registered as
`xmlsecurity-digitalsignatures-remove-signature` in the fail-closed
[`dialog-anatomy-policy.json`](../../qa/windows-ui-contract/dialog-anatomy-policy.json)
contract, validated against source by
[`bin/check-material-dialog-anatomy.py`](../../bin/check-material-dialog-anatomy.py).
No build or runtime evidence exists; `runtime_verified` is false.

### Verification hooks

Source-pinned by
[`bin/check-windows-security-prompt-modality.py`](../../bin/check-windows-security-prompt-modality.py)
(CSV `native-exclusion` rows, the live router classifier returning KeepModal,
the modal footers, and synchronous `GenericDialogController::run()`
reachability). `SecurityOptionsDialog`, `signatureline`, and `signsignatureline`
are deliberately excluded (adjacent rows). No native build, no dialog pixels;
`runtime_verified` is false.

---

## 8.12 Document recovery, crash report & Safe Mode

These surfaces are **preserved safeguards**, not nags: the
[00-windows-rewrite-contract.md](00-windows-rewrite-contract.md) contract
explicitly requires the recovery, Safe Mode, and extension-compatibility paths
and excludes them from the removed-nag set. They are styled and anchored under
the 8.1 shared modal anatomy but are never removed or rerouted.

### Anatomy mapping

*Application of 8.1 plus chapters [03](03-selection.md)/[06](06-containers.md)/[07](07-feedback.md)
— no novel design:*

| Surface | Element | Mapped pattern |
| --- | --- | --- |
| `DocRecoveryRecoverDialog` / `DocRecoverySaveDialog` / `DocRecoveryBrokenDialog` | recover/save/broken file lists | 06 container tree on a `@surface-container` sheet |
| `DocRecoveryRecoverDialog` + `DocRecoveryProgressDialog` | the two `progress` bars | §7.1 determinate progress |
| `SafeModeDialog` | four radio groups + nested checkboxes | 03 selection on the 8.1 sheet |
| `CrashReportDialog` | Send / Do-Not-Send / Close footer; Privacy-Policy + crash-id links; troubleshoot checkbox | 8.1 footer + the link contract (§5 of [02-actions.md](02-actions.md)) |

Footer order is normalized to **Help \| spacer \| secondary \| primary**.

### Safe-default invariant

Applying the 8.1 destructive-confirmation reasoning:
`DocRecoveryRecoverDialog` keeps **Recover Selected** (response 101,
`has-default`) as the `Enter` default while **Discard All** (response −6) stays a
non-default explicit action; `SafeModeQueryDialog` keeps the safe **Cancel**
(`has-default`) as the `Enter` default over **Restart**. Native `@error-container`
emphasis on *Discard All* is *specified here, not yet implemented* — converting
it to `sfx2::ConfirmDestructiveAction` is a behavioural change needing runtime
validation and is deferred.

### Chrome, flows, states, keyboard, a11y, platform

Chrome variants, key user flows, empty/loading/error states, density, the
keyboard map, and accessibility notes inherit 8.1 by reference. Platform notes
are Windows-first: Safe Mode restart and autorecovery re-entry. The crash-report
acknowledgment **stays modal** — an 8.1 dialog, never a §7.5 bottom-right
snackbar — reconciled with the `dialog-notification-policy.csv` KeepModal
classification. Source-pinned by
[`bin/check-windows-recovery-safemode-contract.py`](../../bin/check-windows-recovery-safemode-contract.py)
(seven recovery/crash/Safe-Mode roots, their weld bindings, native-part
grounding in both palettes, the seven KeepModal rows, and the retained
safeguards); `runtime_verified` is false.

---

## 8.13 Migration & profile-compatibility decisions

*Application of the 8.1 shared modal anatomy and the
[00-windows-rewrite-contract.md](00-windows-rewrite-contract.md) no-nag boundary
— no novel visual design.*

### Anatomy (inherits 8.1)

The compatibility dialogs are `@surface-container` modal sheets with the standard
**Help \| spacer \| secondary \| primary** footer and the 8.1 scrim, keyboard,
and focus-trap rules — restated by reference, not respecified.

### Migration flow (silent)

Settings migration surfaces **no acknowledgment prompt**: the startup order runs
the extension-compatibility check before silent settings migration
(`desktop/source/app/app.cxx` orders `CheckExtensionDependencies()` **before**
`Migration::migrateSettingsIfNecessary()`), and the migration path is guarded
for idempotency by `MigrationCompleted` and the `SAL_DISABLE_USERMIGRATION`
fake-success escape. This is the chapter-00 rule "migration is silent /
default-off nags removed".

### Retained compatibility decisions

Each is a *required* compatibility decision that stays modal
(`native-exclusion`), with the non-committal option as the `Esc`-equivalent safe
escape — applying the 8.1 "safe action reachable by `Esc`" reasoning **without**
the destructive `@error-container` styling (these are compatibility choices, not
data-loss confirmations):

| Dialog | Options | Safe escape |
| --- | --- | --- |
| `UpdateRequiredDialog` (desktop) | Check for Updates / Disable all / Cancel | Cancel / Disable all |
| `Dependencies` (desktop) | Continue / Cancel | Cancel |
| `MigrationWarnDialog` (dbaccess) | Yes / Later | Later |

### No-nag boundary

Per chapter-00 "Promotional or recurring nags are not part of the rewritten
product", these required decisions sit explicitly **outside** the removed-nag
set, alongside recovery, Safe Mode, and extension-compatibility. Accessibility,
RTL, and localization inherit 8.1 by reference.

### Verification hooks

Source-pinned by
[`bin/check-material-migration-compat-contract.py`](../../bin/check-material-migration-compat-contract.py)
(silent-migration positive path + forbidden-nag blocklist, the
compat-check-gates-migration ordering, the three retained decisions kept
native-exclusion, and the `Setup.xcs` profile-compat schema), with the
E-NONAG-LEGACY dependency delegated read-only to
[`bin/check-windows-nonag-headless-harness.py`](../../bin/check-windows-nonag-headless-harness.py).
This is source + policy evidence, not runtime proof; `runtime_verified` is false.

---

## 8.14 Credential & authentication dialogs (uui)

*Application of the 8.1 modal anatomy (focus trap, `Esc` = Cancel, the scrim
never dismisses) to the `uui/source` login / password / master-password /
auth-fallback / unknown-auth family — no novel visual design; the existing
dialog part/token table is reused.*

Credential prompts sit at the **top of `NotificationRouter::Classify`
precedence** and therefore **never** route to the bottom-right stack. The ten
uui interaction roots are `AuthFallbackDlg`, `FilterSelectDialog`, `LoginDialog`,
`MacroWarnMedium`, `MasterPasswordDialog`, `PasswordDialog`,
`SetMasterPasswordDialog`, `SimpleNameClashDialog`, `SSLWarnDialog`, and
`UnknownAuthDialog`; the four that hit the **credential** branch —
`LoginDialog`, `MasterPasswordDialog`, `PasswordDialog`, `SetMasterPasswordDialog`
— are each anchored on a `visibility=False` password `GtkEntry`. Conflict prompts
(`SimpleNameClashDialog` plus the C++ conflict/lock handlers) stay modal on real
`weld::MessageDialog … ->run()` call sites. The generic-error routing seam and
its informational-only carve-out are documented in
[07-feedback.md](07-feedback.md) §7.9. Source-pinned by
[`bin/check-uui-interaction-contract.py`](../../bin/check-uui-interaction-contract.py);
no uui producer is wired, so nothing is claimed routed. `runtime_verified` is
false.

---

## 8.15 Help/About & informational dialogs

The **informational-modal** variant is an application of the 8.1 shared anatomy —
title row + content region + footer — but with a **single non-destructive dismiss
default** (Close/OK) and **no destructive primary**. It cites the 8.1
destructive-confirmation pattern explicitly as the pattern it does **not** use.

### About %PRODUCTNAME (`cui/aboutdialog.ui`)

A modal `AboutDialog` with a product-identity content region (logo, version and
build strings, copyright). The Credits / Website / Release-Notes / build-id
`GtkLinkButton` surfaces consume the link contract (§5 of
[02-actions.md](02-actions.md)): `@primary` corner-focus ring, tintless-underline
hover. Single **Close** dismiss (`btnClose`, response −7).

### Tip of the Day (`cui/tipofthedaydialog.ui`)

A navigational informational dialog: Next-tip advance (`btnNext`), Link-out
(`btnLink`), and a single **OK** dismiss (`btnOk`, response −5). The
show-on-startup toggle is cross-referenced to the WIN-SYS-008 no-nag onboarding
contract (tip/welcome solicitation is default-off per chapter-00), not respecified
here.

### Modal, not routed

Grounded in the §7 notification policy, Help/About informational dialogs stay
**modal** (`dialog-notification-policy.csv` `native-exclusion` / router
KeepModal) because they are interactive dialog shells, not acknowledgment-only
prompts, so they are never folded into the bottom-right notification stack.

*Provenance: the Help/About family is source-pinned and registry-assigned; no
build, pixel, or runtime evidence is claimed (the chapter status banner's Start
Center scope is unchanged).*

---

## 8.16 Legacy & optional-feature dialogs (owner-level)

The hyperlink, thesaurus, hyphenate, Hangul/Hanja, and expert-config
(`aboutconfig`) surfaces inherit the 8.1 base anatomy and the chapter
[04](04-inputs.md) input-field treatment. Because they collect input they stay
**KeepModal** per §7. They are claimed by WIN-SYS-015 at **owner-level registry
granularity**, with per-surface anatomy pinning explicitly deferred — an honest
carve-out mirroring the closure ledger's owner-level prefix attribution. No
build, pixel, or runtime evidence is claimed; `runtime_verified` is false.

---

## Cross-references

- Buttons, disabled affordances, and the link contract (§5): [02-actions.md](02-actions.md)
- Checkboxes and radios: [03-selection.md](03-selection.md)
- Fields, search, and regex-builder input anatomy: [04-inputs.md](04-inputs.md)
- Tabs and native tab parts (§8.6, §8.7, §8.11): [05-navigation.md](05-navigation.md)
- Trees, lists, frames (§8.9 extension list, §8.12 recovery lists): [06-containers.md](06-containers.md)
- Progress, snackbars, and why security/credential/recovery prompts stay modal
  (§8.9–§8.14): [07-feedback.md](07-feedback.md) §7.1/§7.5/§7.9
- Notification routing precedence for security prompts (§8.11):
  [02-notification-service-architecture.md](02-notification-service-architecture.md)
- Retained safeguards and the no-nag boundary (§8.12, §8.13, §8.15):
  [00-windows-rewrite-contract.md](00-windows-rewrite-contract.md)
- Template Manager entry point from the Start Center (§8.8):
  [09-start-center.md](09-start-center.md) §9.3/§9.10
- Evidence format for every checkpoint above:
  [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md)
