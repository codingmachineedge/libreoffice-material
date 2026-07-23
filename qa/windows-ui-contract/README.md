# Windows UI coverage contracts

These registries turn the whole-application dialog and search requirements into
fail-closed source inventories. They establish migration scope; they do not
claim native implementation, a successful build, or runtime evidence.

## Dialog notification forms

`dialog-notification-policy.csv` is the exhaustive native dialog registry for
the Windows notification-form migration. It inventories every top-level
`GtkDialog`, `GtkMessageDialog`, and `GtkAssistant` object found in a Git-tracked
or untracked, non-ignored `.ui` file.

Each row must explicitly choose one of these policies:

- `bottom-right-notification-form` routes the dialog through the new
  bottom-right notification surface. `notification_profile` selects its
  customizable form profile; the initial profile is `default`.
- `native-exclusion` keeps a dialog outside that surface. It must have a
  non-empty `exclusion_reason` and cannot silently inherit a profile.

The contract intentionally does not claim that a registered dialog has already
become a complete notification form or been runtime verified; it establishes
complete, reviewable migration coverage. A separate source contract now guards
the first shared implementation seam: Windows VCL dialogs are repositioned only
after their final `InitShow` layout, relative to the visible owner/work area,
with bounded Material inset and work-area clamping. That seam is geometry only.
The current total is 598 roots (`GtkDialog` 521, `GtkMessageDialog` 76,
`GtkAssistant` 1) after the no-nag source slice deleted the automatic Windows
file-association and Welcome dialogs and the shared destructive-confirmation
dialog was added.

### Classification heuristic

The policy column mirrors the runtime router
(`sfx2::NotificationRouter::Classify`, `sfx2/source/notification/NotificationRouter.cxx`),
which keeps a prompt **modal** iff it collects input, confirms a destructive
act, handles credentials, or enforces security, and lets only purely
informational messages route to a notification. A static `.ui` scan **cannot**
prove a dialog is purely informational: most LibreOffice dialogs build their
entries, trees, and even their buttons at the C++ call site (e.g.
`ChartDataDialog`, `DataFormDialog`, and `RetypePass` carry only empty
container shells in their `.ui`). The ledger is therefore deliberately
conservative in the **safe** direction — a dialog stays `native-exclusion`
unless it shows affirmative static evidence of an acknowledgment-only message
box. `bin/check-windows-dialog-notification-contract.py --reclassify`
regenerates the whole column from these `.ui` content signals, in this
precedence:

1. **credential** — a password entry (`GtkEntry` with `visibility=False`) or a
   `password`/`login`/`credential`-family token in the path or id.
2. **security** — a `security`/`macrosecurity`/`certificate`/`signature`/
   `trust`-family token.
3. **destructive** — a `delete`/`remove`/`overwrite`/`discard`/`reset`-family
   token.
4. **input** — any value-entry or selection widget class (`GtkEntry`,
   `GtkSpinButton`, `GtkComboBox*`, `GtkTreeView`, `GtkTextView`,
   `GtkCheckButton`, `GtkRadioButton`, `GtkNotebook`, LibreOffice custom
   `*Entry`/`*ComboBox`/`*TreeView`/`*Edit`/`*Metric` widgets, …).
5. Otherwise a `GtkMessageDialog` routes to
   `bottom-right-notification-form` **only** when its button set is a built-in
   acknowledgment (the `buttons` enum `ok`/`close`, or `<action-widgets>`
   limited to `ok`/`close`/`help`). A message dialog whose buttons come from
   the call site (no `buttons` property and no `<action-widgets>`) cannot be
   cleared and stays modal, as do all `GtkDialog`/`GtkAssistant` shells.

That yields 9 `bottom-right-notification-form` acknowledgment message boxes and
589 `native-exclusion` rows (input 459, interactive 55, destructive 27,
decision 26, credential 14, security 8). Regenerating is idempotent; review any
new acknowledgment message added to the notification set before closing its
surface. The classifier is unit-tested per signal in
`bin/test_windows_dialog_notification_contract.py`
(`RoutingClassifierTest`).

`--update` remains the incremental workflow (below): it defaults **new**
dialogs to `bottom-right-notification-form` for explicit review, so run
`--reclassify` or hand-review after adding an input/destructive/credential
dialog.

`ui_path` plus `object_id` is the stable locator. The two source roots that do
not define a GTK object ID use an empty `object_id`, so their repository path is
the locator; duplicate paths remain forbidden.

Validate the checked-in registry and its regression suite:

```sh
python bin/check-windows-dialog-notification-contract.py
python bin/test_windows_dialog_notification_contract.py
python bin/check-windows-dialog-placement.py
python bin/test_windows_dialog_placement.py
```

After deliberately adding, removing, or changing a root dialog, regenerate the
inventory before reviewing the resulting diff:

```sh
python bin/check-windows-dialog-notification-contract.py --update
```

The update operation preserves policies for exact existing dialog identities
and assigns every new dialog the explicit `bottom-right-notification-form`
policy with the `default` customization profile. Review any intentional native
exclusion by editing that row and documenting a concrete rationale.

## Modal dialog anatomy (WIN-DLG-001)

`dialog-anatomy-policy.json` registers the shared Material
destructive-confirmation dialog and every real `weld::MessageDialog`
destructive confirmation migrated onto it, per
[`docs/design/08-dialogs.md`](../../docs/design/08-dialogs.md) §8.1. The helper
(`sfx2::ConfirmDestructiveAction`,
`include/sfx2/destructiveconfirmation.hxx` /
`sfx2/source/dialog/destructiveconfirmation.cxx`, over
`sfx2/uiconfig/ui/materialdestructiveconfirmdialog.ui`) composes the modal
footer in the shared order `Help | spacer | safe secondary | destructive
primary`, carries the `destructive-action` role (Material `@error-container`)
and a verb-named label on the primary, and binds the **safe** action as both
the initial focus and the Enter default so Enter/Space activation can never
destroy data. Native pixel rendering of the error-container fill and
keyboard-default emphasis remain deferred (MATERIAL_DESIGN milestone 10); this
is source composition/behavior evidence only.

The initial wave converts five confirmations off ad-hoc message boxes:
overwrite a style (`sfx2`), delete sheets with a pivot table and delete sheets
with data (`sc`, previously defaulting Enter to the destructive action), delete
a layer (`sd`), and delete an AutoText category (`sw`).

```sh
python bin/check-material-dialog-anatomy.py
python bin/test_material_dialog_anatomy.py
```

The validator fails closed on a reordered footer, a missing destructive-action
role, a non-verb ("OK") destructive label, a destructive Enter default or
destructive initial focus, a non-warning message type, a migrated call site
that drops the helper header or dispatch, or a registry outside the 3–8
migration wave. It claims no native build, dialog pixels, or runtime
interaction.

## Registered UI inventory closure (WIN-SYS-016)

`ui-registry.json` is the generated, checked-in closure ledger for the
`WIN-SYS-016` registry gate. It enumerates every registered UI surface exactly
once and maps each to one owner and one `WIN-` inventory row (or the explicit
`unassigned` bucket). It is a source-level ledger only: it makes no claim of
native implementation, a successful build, or any runtime evidence.

Two enumeration sources are combined:

- **`.ui` surfaces.** Every tracked or untracked, non-ignored `*.ui` file found
  by the same Git walk `check-windows-dialog-notification-contract.py` uses
  (cached plus non-ignored other files, filtered to paths that still exist).
  One `.ui` file is one surface. This includes the three notification `.ui`
  files (`notificationcard.ui`, `notificationmanager.ui`, `notificationstack.ui`).
- **Native surfaces.** A maintained explicit list of native-only, custom-drawn,
  optional, and platform surfaces the `.ui` walk cannot see: the Start Center
  thumbnail view, the inline Find toolbar, the Writer/Calc/Impress/Draw
  canvases, the MSI install lifecycle UI, the native updater UI, the bottom-right
  notification overlay window, and native window title bars. Each declares its
  own owner, inventory row, and a note explaining why it has no `.ui`.

The owner is the module (first path segment) for `.ui` surfaces and an explicit
declaration for native surfaces. Inventory-row mapping is an explicit,
reviewable table defined in the checker and mirrored into the registry's
`mapping` section: exact-path `overrides` win, then the longest matching
`prefix_rules` entry, otherwise the surface is recorded as `unassigned`. Prefix
attribution is deliberately owner-level: it records which inventory row owns the
surface, not that every dialog in that subtree is that row's exact anatomy.
Per-surface refinement of the `unassigned` bucket is the remaining WIN-SYS-016
work.

**Owner-attribution rubric.** An entry in this ledger records *ownership only* —
which `WIN-` inventory row is responsible for a surface's Windows Material
redesign — and is deliberately **not** a claim that the surface has Material
anatomy, an exact Windows build, or any runtime/pixel evidence. Those gates live
on the owning inventory row and stay independently tracked in
`docs/WINDOWS_UI_INVENTORY.md`; moving a surface out of `unassigned` never moves
any of that row's `M/B/V/I/A/L/P/C` cells. Attribution is chosen by a surface's
primary function, not by the module directory it happens to live in: an exact
`overrides` entry pins a single `.ui` to the row that owns its redesign (used when
a shared subtree contains surfaces owned by different rows), while a `prefix_rules`
entry assigns a whole subtree to the one row that owns it. Shared `cui`/`svx`/
`svtools` tab-page fragments that no single inventory row owns stay `unassigned`
by design, and a residual floor of non-product test/demo/example `.ui` files stays
`unassigned` deliberately — zero-unassigned is not the honest target.

The `unassigned` count is an honest ledger figure, not a silent gap: the current
baseline is **250 of 1270** surfaces (1260 `.ui` plus 10 native), down from 434
after the mega-wave assignment campaign moved 184 surfaces into owning rows via 4
new `prefix_rules` (the `extensions` property-control/wizard/bibliography subtrees
and `formula`) plus per-cluster `overrides` (Options → `WIN-DLG-002`, destructive
queries → `WIN-DLG-001`, recovery → `WIN-SYS-009`, sidebar panels →
`WIN-CON-007`, print → `WIN-DLG-004`, the delegated `presentationdialog.ui` →
`WIN-IM-003`, and the Writer format-dialog and notebookbar remaps). The remaining
250 are chiefly the shared `cui`, `svx`, `svtools`, `extensions`, and `vcl`
dialog sets that no single inventory row owns. The validator reports the count and
does not fail merely because it is non-zero. It fails closed on any drift from a
fresh enumeration: an added, removed, or renamed `.ui`; a newly `unassigned`
surface not already in the checked-in baseline; an unknown inventory ID; a
duplicated surface; or any hand edit.

```sh
python bin/check-windows-ui-registry-closure.py
python bin/test_windows_ui_registry_closure.py
```

After a deliberate `.ui` addition, removal, or rename, or after editing the
mapping table in the checker, regenerate before reviewing the diff:

```sh
python bin/check-windows-ui-registry-closure.py --regenerate
```

Regeneration is deterministic: stable sort, no timestamps. Because other work
may add or modify `.ui` files concurrently, the final integration step
regenerates this registry again; a new surface that lands in an unmapped module
appears in the diff as an added `unassigned` row for review.

## Search fields and regex builders

`search-field-coverage.json` records the audited Windows text-query controls:

- 26 existing shipping search fields, each assigned the
  `adjacent-advanced-builder` contract;
- one planned Start Center `start_search` field, required to remain absent until
  it moves into shipping coverage; and
- 16 explicit exclusions for categorical selectors, range inputs,
  transformation parameters, object names, non-shipping QA controls, and the
  shared builder's own pattern editor.

The validator also scans `.ui` objects for search-like IDs, accessible text,
placeholders, tooltips, and `gtk-find` icons. A new unclassified candidate,
missing or duplicate widget, stale exclusion, wrong widget type, count drift,
or incomplete builder declaration fails the contract.

```sh
python bin/check_search_field_coverage.py
python bin/test_search_field_coverage.py
python bin/check-windows-regex-builder-foundation.py
python bin/test_windows_regex_builder_foundation.py
python bin/check-windows-regex-search-integrations.py
python bin/test_windows_regex_search_integrations.py
```

This is the minimum audited native inventory, not permission to ignore a new
app-owned search bar that the conservative scanner does not infer. Any newly
identified search field must be added and receive the same adjacent advanced
builder before its owning UI surface can close.

The shared native foundation now provides an ICU/LibreOffice search service,
literal and regex modes, `i/g/m/s`, bounded match testing, live errors, token
insertion, and embedded Build/Test/Reference/Examples content. Its
`GtkPopover` is anchored to the adjacent builder button and deliberately is not
a modal or bottom-right dialog.

`regex-search-integrations.json` is the separate source-implementation ledger.
It currently records Calc Go to Sheet as 1 of 26 shipping fields. Its validator
requires direct entry/button adjacency, translated accessible metadata,
controller-owned change dispatch, controller-first destruction, exact legacy
`OUString::indexOf` behavior in the literal case-sensitive default, and one
`utl::TextSearch` construction before the item loop for non-legacy modes.
Comment-only wiring cannot satisfy the source contract. Ten mutations prove
those requirements fail closed. The remaining 25 shipping integrations and
native build/runtime proof remain open; `runtime_verified: false` is intentional
until exact-build interaction evidence exists.

## No unsolicited startup or promotion prompts

The Windows no-nag contract forbids the automatic file-association, Welcome /
What’s New, Tip, donation/Get Involved, AutoCorrect-explanation, and
crash-report submission paths and the misleading crash-report opt-in. It also
requires the explicit Tip, What’s New,
feedback, and Windows association actions plus recovery, Safe Mode, incompatible
extension, read-only, macro, metadata, and credential safeguards to remain.
Mutation tests exercise every forbidden marker, removed surface, and retained
safeguard. This is source evidence; only a current native build and fresh plus
seeded legacy-profile startup runs can establish runtime behavior.

```sh
python bin/check-windows-no-nag-contract.py
python bin/test_windows_no_nag_contract.py
python bin/check-notification-store-contract.py
python bin/test_notification_store_contract.py
```

The notification-store contract covers the public state model, metadata-only
privacy default, deterministic redaction, genuine bare loose-object Git format,
fixed local `main`, process plus OS-held operation guarding, lock/CAS behavior,
atomic bulk transitions, recoverable tombstones, inverse-commit undo, bounded
preferences, pending-checkpoint retry without ref/object growth, schema
registration, and focused CppUnit wiring. It does not claim a visible manager
or runtime proof.

## Material token accessor

`vcl::MaterialTokens` (`include/vcl/MaterialTokens.hxx`,
`vcl/source/gdi/MaterialTokens.cxx`) is the public, queryable named-token table
over the Material widget definition's palette, shape and metric data. It reads
values exclusively from
`vcl/uiconfig/theme_definitions/material/definition.xml` through the existing
`WidgetDefinitionReader` reading path (the additive `readTokenTables` method
reuses `readColorPalette` plus the shape/metric readers). No hex, radius or
metric literal is duplicated in C++: only the semantic token *names* live there,
and the accessor rejects any file whose names diverge from that vocabulary.

`bin/check-material-token-accessor.py` proves 1:1 fidelity: the published name
vocabulary equals the definition's `<palette>` / `<shapes>` / `<metrics>` names
(both schemes identical, declared `std::array` sizes correct), the accessor
restates no hex literal, and it genuinely sources data through the reader path
and is registered as a compiled public VCL export.

```sh
python bin/check-material-token-accessor.py
python bin/test_material_token_accessor.py
```

The 16 mutation tests fail closed on a missing/extra/renamed token, an array
size mismatch, a definition drift, a hard-coded hex literal, a dropped reader
call, or a lost public export/registration. This is source evidence only; no
native build or runtime capture is claimed.

## Impress/Draw shell surfaces

`impress-draw-surfaces.json` registers the Draw/Impress shell and object
surfaces from
[`docs/design/11-impress-draw.md`](../../docs/design/11-impress-draw.md) §11.2 --
the three Draw shell surfaces `draw.tool-rail`, `draw.property-panel`, and
`draw.status-bar`, plus the three shared-weld object surfaces added in Wave-2
Batch B (see the WIN-WR-004/WIN-IM-002 note below). Each surface declares its
owner source(s), the required `definition.xml` parts (with exact
fill/stroke/radius/stroke-width tokens and part sizing), any Material token
consumption, the status text model, and the no-selection/disabled policy.

`bin/check-impress-draw-surface-contract.py` cross-validates every declaration
against the tree:

- the docked tool rail's `toolbar/DrawBackgroundVert` fill, `ThumbVert` grip and
  `toolbar/Button` checked/hover/pressed/focused/disabled-checked states resolve
  to the exact definition tokens (token drift fails closed);
- the property panel's outlined `listbox` field and the normative 28 px
  (`size-compact-control`) `slider/Button` thumb plus horizontal track parts are
  the declared tokens, and `ApplyNoSelectionDisabledPolicy` keeps every
  Fill/Line control `set_visible(true)` + `set_sensitive(false)` (visible but
  disabled, no layout jump) in both the shared `LinePropertyPanelBase` and
  `AreaPropertyPanelBase`;
- the status bar composes `Page N of N · K objects selected`
  (`STR_SD_DRAW_OBJECTS_SELECTED`) in `drviewsa.cxx`, and the zoom control routes
  its Material text color through `vcl::MaterialTokens`, inert under the native
  theme.

```sh
python bin/check-impress-draw-surface-contract.py
python bin/test_impress_draw_surface_contract.py
```

Markers are checked in comment-stripped code, so comment-only wiring, a missing
policy control, a renamed policy method, a dropped status marker, wrong status
copy, or token drift each fail the 30 mutation tests. The dotted canvas grid /
workspace fill (a decorative custom-draw per the §11.2 accessibility note) is
deliberately out of scope and is not faked here. The surfaces are
source-declared for the Windows-first migration target; `runtime_verified` stays
`false` until an exact-build capture exists, and the contract claims no native
build, screenshot, or runtime evidence.

Wave-2 Batch B extends this registry from three to six surfaces
(`expected_surfaces` 6), adding the shared-weld object-property panels and object
bars that back the Writer sidebar (WIN-WR-004) and Impress authoring/object
properties (WIN-IM-002):

- `impress.object-property-panel.possize` -- the Position and Size panel over the
  shared `svx/uiconfig/ui/sidebarpossize.ui`: outlined `spinbox` fields
  (idle/focus/disabled), the Keep-ratio Material `checkbox`, and the
  flip/arrange/align `toolbar` Buttons. `PosSizePropertyPanel::ApplyNoSelectionDisabledPolicy`
  keeps every listed control visible-but-disabled on an empty selection (no layout
  jump) and is additive to `DisableControls`/`NotifyItemUpdate`, so F4 Position and
  Size stays the numeric entry.
- `impress.object-property-panel.shadow` -- the Shadow panel over
  `svx/uiconfig/ui/sidebarshadow.ui`: the normative 28px (`@size-compact-control`)
  `slider` thumb plus its filled/remainder tracks, the angle `combobox`, the Enable
  `checkbox`, and outlined `spinbox` fields, with
  `ShadowPropertyPanel::ApplyNoSelectionDisabledPolicy` additive to `UpdateControls`.
- `impress.object-bars` -- the `GraphicObjectBar` and `TextObjectBar` SfxShells
  whose commands are declared in the `sd` toolbar config XMLs and render through
  `ControlType::Toolbar` as the `toolbar/Entire` background and `toolbar/Button`
  states; no app-side colour code owns the fill and command semantics are unchanged.

All three carry `runtime_verified: false` and, like the original trio, claim no
native build, pixels, or runtime evidence.

## Wave-2 Batch A shell and surface contracts

Wave-2 Batch A (2026-07-21) adds eight fail-closed source contracts, one per
inventory row, that lock a Material shell/navigation/feedback surface against
`definition.xml` token drift and against the guarded native wiring that consumes
it. Each is source evidence only: markers are checked in comment-stripped code,
`runtime_verified` (where present) stays `false`, and none claims a native
build, pixels, or runtime interaction. Validate the whole cohort:

```sh
python bin/check-windows-menu-composition.py
python bin/test_windows_menu_composition.py
python bin/check-windows-sidebar-rail.py
python bin/test_windows_sidebar_rail.py
python bin/check-windows-statusbar-composition.py
python bin/test_windows_statusbar_composition.py
python bin/check-windows-calc-sheet-tabs.py
python bin/test_windows_calc_sheet_tabs.py
python bin/check-windows-startcenter-cards.py
python bin/test_windows_startcenter_cards.py
python bin/check-material-infobar-contract.py
python bin/test_material_infobar_contract.py
python bin/check-windows-find-replace-fieldset.py
python bin/test_windows_find_replace_fieldset.py
python bin/check-windows-link-contract.py
python bin/test_windows_link_contract.py
```

### Menubar, drop menus and context menus (WIN-NAV-001, WIN-NAV-002)

`menu-composition.json` cross-validates the Material menubar/menupopup part and
state declarations, the five composition settings (`menuBarHeight` 38,
`menuItemHeight` 40, `menuPopupMinWidth` 248, `menuAccelColumnGap` 14,
`menuInnerBorder` 6), the `size-menu-indicator` (18) metric, and the
disabled-submenu-arrow `@outline` state against 24 real code markers that carry
them through the `settings -> NWF -> Menu::ImplCalcSize` layout channel: the
`mnMenu*` fields in `vcl/inc/svdata.hxx`, the reader mapping in
`WidgetDefinitionReader.cxx`, the Material-guarded population plus platform
baseline capture/restore in `FileDefinitionWidgetDraw.cxx`, and the layout reads
in `menu.cxx`. Those WIN-NAV-001 mutation tests fail closed on token/metric
drift, a dropped NWF field, a lost baseline restore (which would leak the
Material metrics into non-Material rendering), or a broken disabled-arrow state.
Prototype-only fine geometry (title-drop offset, exact text insets, monospaced
accelerator styling) is out of scope.

Wave-2 Batch B extends the same registry with a `context_menu` section for the
WIN-NAV-002 context-menu delta (design [05](../../docs/design/05-navigation.md)
§2). It adds the `contextMenuKeyboardFirstHighlight` setting -- read into a new
`mbContextMenuKeyboardFirstHighlight` NWF field with the same reversible baseline
capture/restore -- and 18 context-menu markers. New-behaviour markers fail closed
on the Material keyboard-first-highlight policy and its guard, the single native
keyboard-vs-pointer capture at `ImplCallCommand` (`winproc.cxx`, which records
`mbContextMenuByKeyboard = !bMouse` for every context menu), and its one-shot
consumption in `PopupMenu::ImplExecute`. Presence markers pin the shared-VCL
behaviours §2 relies on so they cannot silently regress: on-screen edge-flip and
RTL mirroring in `FloatingWindow::ImplCalcPos`, the `StartPopupMode` anchor feed,
focus save/return around a top-level context execute, Esc dismissal, and the
Writer-canvas (`edtwin.cxx`) / Calc-sheet-tab (`tabcont.cxx`) invocation hooks.
The menu-composition suite is now 39 mutation tests.

### Sidebar rail (WIN-NAV-005)

`sidebar-rail.json` records that the rail is sidebar-framework chrome, not a
`definition.xml` control (design [05](../../docs/design/05-navigation.md) §5.1/
§5.7 and [06](../../docs/design/06-containers.md) §6.7: "No dedicated native rail
part exists"), so its five metrics (48px rail width, 38px button, 22px icon, 4px
gap, 10px top padding) and six state colours live in the sfx2 sidebar `Theme`
and are consumed by `TabBar`/`SidebarController` behind
`VCL_DRAW_WIDGETS_FROM_FILE`. This is a **documented divergence** from the row
plan, which named `definition.xml`; the design chapter wins. The 14 mutation
tests lock the idle/hover/active-deck/focus/disabled palette, the guarded
geometry consumption, and click-active-to-collapse (`OpenThenToggleDeck`). The
22px icon down-scaling and the bespoke inner rule / focus ring delegated to the
shared toolbar part remain open.

### Status bar (WIN-NAV-008)

`statusbar-composition.json` binds the Material 28px status band to its guarded
native wiring. `vcl/source/window/status.cxx` composes the `faceColor ->
@surface-container` fill and the `@outline-variant` `stroke-thin` top rule behind
`VCL_FILE_WIDGET_THEME`; `definition.xml` already carries the band/field tokens
and the zoom-slider parts (thumb idle/hover/focus/disabled, filled/remainder
tracks), which this contract locks against drift; and
`genericstatusbarcontroller.cxx` routes owner-drawn status updates through the
item accessible name (`setAccessibleName`, deliberately not `setText`, so the
band cannot reflow) as accessible value changes while retaining `repaint()`. The
interactive-field hover wash (§8.2) has no dedicated native part and stays
spec-only. 21 mutation tests.

### Calc sheet tabs (WIN-NAV-006)

`calc-sheet-tabs.json` locks the `tabitem`/`tabheader`/`tabpane` token set the
Calc sheet-tab strip maps onto and the additive `ScTabControl::Paint` override
(drawn over `TabBar::Paint`, Material- and high-contrast-guarded via
`vcl::MaterialTokens`) that renders the `@outline-variant` strip top rule and the
`PaintMaterialSheetTabOverlay` user tab-colour accent. The 22 mutation tests
assert the accent strip is **selection-independent** (it must reference
`maMaterialTabColors` and must not reference `IsPageSelected`/`GetCurPageId`, per
design [05](../../docs/design/05-navigation.md) §6.4). The strip band, docked-tab
fills, active-tab grid-join fill, and the Add-Sheet button are drawn by the
svtools `TabBar`/`TabDrawer` base class, out of this row's file scope.

### Start Center document cards (WIN-CON-006)

`startcenter-cards.json` registers the two card grids (`RecentDocsView`,
`TemplateDefaultView`) that draw over `@surface` as Start Center application
drawing, not a `definition.xml` control (design
[06](../../docs/design/06-containers.md) §6.6). The 18 mutation tests lock the
palette/shape token contract and the guarded renderer anatomy in
`startcentercard.cxx` — card container, 118px preview, 74x92 thumbnail, 26x26
corner-small badge chip, ellipsized 13px caption plus 11px meta, `@primary` hover
border, corner-focus keyboard ring, and the filtered-empty message
(`STR_SC_NO_RECENT_MATCH` / `STR_SC_NO_TEMPLATE_MATCH`) — while both views keep
their non-Material `ThumbnailView::Paint` fallthrough. Soft-shadow elevation, the
relative-time meta model, the per-module badge glyph, and the first-run welcome
bitmap are deferred.

### Warning/error banners and infobars (WIN-FBK-006)

`infobar-severity-policy.json` requires every `InfobarType` severity to resolve a
Material container/on-container pair from semantic `StyleSettings` feedback slots
(INFO -> primary-container highlight, WARNING -> warning-container, DANGER ->
error-container) or from the single shared `NotificationTheme` resolved-green
(SUCCESS), never from an infobar-local hex literal; the strip paints the
corner-container 12px radius in code with a high-contrast square bypass; a polite
`AccessibleRole::NOTIFICATION` announcement names the severity in words; and
`infobar.ui` carries the design [07](../../docs/design/07-feedback.md) §7.6
padding/gap/icon geometry. The file documents the INFO/SUCCESS divergence (§7.6 is
a warning/error chapter and defines no INFO/SUCCESS container tokens). 16 mutation
tests. The §7.6 single-line 13px/1.3 text metric is deferred to the Material
typography layer.

### Find & Replace field set (WIN-INP-006)

`find-replace-fieldset.json` locks the `SvxSearchDialog` Material field set
(design [04](../../docs/design/04-inputs.md) §6/6.1): the search combo bound to
the shared `sfx2::RegexSearchController` and its regex builder; Match case
(inverse of ignore-case, driving `TransliterationFlags::IGNORE_CASE`), Whole
words (`SetWordOnly`), and Regular expressions (shared-controller mode via
`SyncRegexControllerFromToggle` with a `loop_breaker_guard`) all driving the one
`SvxSearchItem` descriptor; the Replace field; the notification-role result
summary (`searchlabel`); and exactly one `suggested-action` emphasis, kept on the
Enter-default Find Next. The 25 mutation tests fail closed on a broken binding,
a dropped descriptor effect, a lost loop breaker, or emphasis drift. The floating
Replace label, the supplementary tinted live-preview run list, and the
filled-pill-on-Replace-All visual are deferred with recorded reasons in the JSON.

### Links (WIN-ACT-005)

`link-contract.json` names the two link surfaces — the native `FixedHyperlink`
(`vcl/source/control/fixedhyper.cxx`) and its `weld::LinkButton` wrapper
(`salvtables.cxx`) — and the Material token side the design
[02](../../docs/design/02-actions.md) §5 interaction contract depends on: a
`@primary` focus outline at `corner-focus` (6px) radius replacing the platform
ShowFocus rectangle (rendered only when Material is active and not high
contrast), a hover that keeps the underline with no colour tint, a disabled state
rendering `deactiveTextColor` (`@outline`) as plain non-underlined non-focusable
text, and an exposed visited state (`@visited-link`). The 25 mutation tests cover
both surfaces. The full AT-SPI/IA2 visited accessibility-state flag is deferred
because upstream has no `VISITED` `AccessibleStateType`.

## Wave-2 Batch B shell, surface, and feedback contracts

Wave-2 Batch B (2026-07-22) adds five more fail-closed source contracts -- the
two Calc chrome surfaces, the component-gallery coverage ledger, the
notification-producer ledger, and the sidebar deck/side-panes surface -- and
extends two Batch-A registries (menu composition with the WIN-NAV-002
context-menu delta, documented in its section above, and the Impress/Draw surface
set with the WIN-WR-004/WIN-IM-002 object panels and object bars, documented in
its section above). Each is source evidence only: markers are checked in
comment-stripped code, every `runtime_verified` (where present) stays `false`,
and none claims a native build, pixels, or runtime interaction. Validate the new
cohort:

```sh
python bin/check-calc-chrome-contract.py
python bin/test_calc_chrome_contract.py
python bin/check-calc-formula-bar-contract.py
python bin/test_calc_formula_bar_contract.py
python bin/check-component-gallery-coverage.py
python bin/test_component_gallery_coverage.py
python bin/check-notification-producer-contract.py
python bin/test_notification_producer_contract.py
python bin/check-windows-sidebar-panels.py
python bin/test_windows_sidebar_panels.py
```

### Calc classic chrome (WIN-CA-001)

`calc-chrome.json` pins the Calc classic-chrome *composition* (design
[10](../../docs/design/10-writer-calc.md) 10.1 shared chrome, 10.3 Calc). Because
the toolbars and menu bar are data-driven uiconfig XML, the M-scope of this row is
*pinning composition* -- command identity + order, separator placement,
per-button visibility -- and grounding the Material treatment in the native
toolbar part contract, never re-drawing controls. The checker parses the real
tree fail-closed: the native `toolbar` band (`DrawBackgroundHorz` / `Entire`),
`SeparatorVert`, and nine-state `Button`
(enabled/rollover/pressed/checked/rollover-checked/pressed-checked/focused/disabled/disabled-checked)
parts resolve to the exact fill/stroke/stroke-width/radius tokens in
`definition.xml` (the Button at `@corner-toolbar` = 18px), every declared metric
carries its value, and every palette role resolves in **both** the light and dark
palettes; the FMT.calc formatting toolbar (`formatobjectbar.xml`) and the standard
toolbar (`standardbar.xml`) match their pinned ordered composition exactly (a
reorder, added/removed item, flipped visibility, or moved separator fails closed),
each toolbar's `design_core` commands staying present and visible and its
`preserved_commands` (expert commands such as `.uno:ConditionalFormatMenu`,
`.uno:MergeCells`, `.uno:FreezePanes`) never rebound or removed; and the menu bar
top-level id sequence matches. `density` (compact/comfortable row height and
overflow collapse) and `combo_annotations` (prototype font-name/size widths) are
honest carve-outs whose `status` must stay `specified` -- build-dependent, never
promoted to an implemented claim. 25 mutation tests; the definition file is read
only, never mutated, and `runtime_verified` stays `false`.

### Calc formula bar (WIN-CA-002)

`calc-formula-bar.json` registers the single `ScInputWindow` formula-row surface
(design [10](../../docs/design/10-writer-calc.md) 10.3 formula bar row, 10.4 RTL).
The row is a ToolBox composing the Name Box (`ScPosWnd` combobox), the fx
Function-Wizard / Sum items, and the formula-input window (`ScTextWnd` editbox).
The checker locks what `ScInputWindow` / `ScTextWnd` own natively and additively:
the combobox / editbox / toolbar `definition.xml` parts the built controls
consume, with exact part sizing and per-`<state>` tokens (Name Box idle/focus,
chevron, input idle/focus, fx/Sum idle/hover); the guarded token consumption in
`sc/source/ui/app/inputwin.cxx` -- the `<vcl/MaterialTokens.hxx>` include, the
`VCL_FILE_WIDGET_THEME` activation guard, the high-contrast bypass, the
`MaterialTokens::fromThemeDefinition` sourcing and every `findColor` /
`findMetric` / `findRadius` lookup -- in comment-stripped code; the additive
`ScInputWindow::Paint` override that *calls* `ToolBox::Paint` (never replaces it)
and owner-draws only the `@outline-variant` `stroke-thin` bottom rule
(`PaintMaterialFormulaRowRule`); the centralized `@surface` field-fill /
`@on-surface` text-fill accessors, each holding both the resolved token and its
`StyleSettings` fallback and funnelled through a call-site floor (>=6 field-fill,
>=2 text-fill sites); and the 10.4 Name Box / formula order recorded via
`mbFormulaRowRTL`. The JSON documents honest divergences: the built
combobox/editbox parts carry the suite-wide `@size-standard-control` (36) height
and `@corner-container` (12) radius rather than the chapter's 30px / corner-small;
the fx/Sum hover, Name Box chevron and editbox focus stroke are rendered by the
native parts (existence-guarded only, painting no pixel in this class); and the
10.4 RTL swap itself is specified-but-not-yet-built. 27 mutation tests;
`runtime_verified` stays `false`.

### Component gallery coverage (WIN-CONCEPT-003)

`component-gallery-coverage.json` is the generated, checked-in coverage ledger for
the "Components" verification surface (archive surface #11 from
`docs/design/00-windows-rewrite-contract.md`). Its M-gate is spelled "SRC or test
fixture" -- a source-level artifact, not rendered pixels (pixels are the separate
B/V gate) -- and this ledger is that artifact. The cell list is **generated** from
`definition.xml`, never hand-maintained: silent rot is the failure mode it guards.
Enumeration reuses `bin/check-material-theme.py` -- the full Material theme
contract runs first (a gallery can never be built over a broken theme) and yields
the authoritative part/state counts; the walk here maps every renderable control
(every root child except the non-widget
`palette`/`shapes`/`metrics`/`style`/`settings`/`typography` sections), part, and
declared `<state>` to exactly one gallery cell (a stateless part still yields one
representative cell), cross-checks its totals against the theme contract's counts
so the two parsers cannot silently diverge, and requires every `REQUIRED_PARTS`
control/part to resolve to a cell. The current ledger is 205 cells over 28
controls / 79 parts / 205 states. Default mode fails closed on a missing,
extra/phantom, or drifted cell, count drift, or any hand edit; `--regenerate`
rewrites it deterministically (stable sort, no timestamps). 14 tests. The
inventory owner is `unassigned`; the ledger records only the proposed
`sfx2/uiconfig/ui/componentgallery.ui` fixture home without asserting it exists
yet -- the native `.ui` and rendered pixels remain the separate B/V gate.

### Notification producers (WIN-FBK-005, WIN-FBK-008)

`notification-producer-policy.json` is the audited ledger of native
`NotificationRouter` **producer** call sites -- the paths that emit a bottom-right
notification instead of a transient modal message box (design
[07](../../docs/design/07-feedback.md) 7.5). It is source-implementation evidence
only and validates **only** the registered producers and the shared router seam;
the unrouted legacy-dialog backlog stays in `dialog-notification-policy.csv`, so
this contract never fails on an unrouted dialog, only on an unreal or mislabeled
producer. The checker enforces, fail-closed against comment-stripped source: each
producer's enclosing function, its `sfx2::NotificationRouter::<call>(` call, and
its `"<source>"_ostr` display-source literal are real code; severity is honest (a
`NotifyInfo` notice spells its `NotificationSeverity::<S>` at the call site; a
`NotifyConfirmation` producer declares only Success/Information, the two outcomes
the router maps); every producer is `informational_only` and its display source is
inside the compiled `isApprovedSafeDisplaySource` allowlist (drift from that
allowlist fails here instead of being silently redacted at runtime); and the
shared seam is real (the router header declares `NotifyConfirmation`, the source
defines it forwarding through `NotifyInfo` with both Success and Information, and
`Classify` returns `NotificationRoute::Notification` for the informational case).

The three producers are the printer-busy notice (`viewprn.cxx`, Warning) and the
help-viewer "no matches" notice (`newhelp.cxx`, Information) plus the first
transient **action-confirmation** (WIN-FBK-005): `svx/source/dialog/srchdlg.cxx`'s
Find & Replace "Replace All" outcome is mirrored into the bottom-right stack via
`lcl_NotifyMaterialReplaceOutcome` -> `NotifyConfirmation` -- **Success** for a
completed replacement (the replacement count) and **Information** for the no-match
empty-state outcome (WIN-FBK-008, empty/no-results states). That producer also
declares `wiring_markers` that bind **reachability**, not just existence: the
one-shot arming assignment (`g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());`
in `CommandHdl_Impl` before the synchronous `FID_SEARCH_NOW` dispatch), the
consumption call in the `SetSearchLabel` outcome sink, and the
`VCL_FILE_WIDGET_THEME` opt-in guard literal must all remain live -- so a partial
revert that leaves the producer function defined but unreachable (dead code) fails
closed here instead of passing on the surviving definition. 27 mutation tests; no
native build, notification pixels, or runtime interaction are claimed.

The mega wave (below) extends this ledger to **eight** producers (WIN-FBK-007,
WIN-SHL-003): five acknowledgement-only modal message boxes were converted onto
`sfx2::NotificationRouter::NotifyInfo` and registered — the no-email-client
warning (`mailmodel.cxx`, Warning), the HTML/Basic source-view "search key not
found" notice (`srcview.cxx`, Information), the predefined-label-locked warning
(`labfmt.cxx`, Warning), and the read-only-content notice pair (`wrtsh1.cxx` +
`textfld.cxx`, Information). To keep the convention from silently collapsing back
to one or two modules on a future revert, the registry now carries a
`min_producer_modules` field (value **3**: the distinct module set over
`producers` — `sfx2`, `sw`, `svx` — must have cardinality ≥ 3), asserted
fail-closed alongside the existing per-producer existence checks. Every new
producer is `informational_only`, uses the already-approved `libreoffice.core-ui`
display source, and is added to `required_producers`. `runtime_verified` stays
`false`; replacing a blocking `run()` with a fire-and-forget notice is a genuine
behaviour change that only a Windows build plus a manual walkthrough can confirm
is safe.

### Sidebar deck & side panes (WIN-CON-007)

`sidebar-panels.json` records that the deck, its title bar, the panels, the 12px
scrollbar, the collapse-to-rail and the below-medium overlay are
**sidebar-framework** chrome (design [06](../../docs/design/06-containers.md) §6.7:
"deck layout and the rail belong to the sidebar framework ... restyled per surface
later"), so the Material metrics and colour palette live in the sfx2 sidebar
`Theme` and are consumed by `Deck` / `DeckTitleBar` / `SidebarController` behind
the `VCL_DRAW_WIDGETS_FROM_FILE` Material guard (`IsMaterialDeck`) -- **not** as a
`definition.xml` part. This is a **documented divergence** from the row plan
(which named `definition.xml` and DeckLayouter/Panel/PanelTitleBar/PanelFactory);
the audit found those files need no change (the deck padding routes through the
existing `Int_Deck*Padding` slots, the panel background inherits the deck fill,
and the panel title bar is a `weld::Expander` with no font API) and the design
chapter wins. This row consumes, and does not fork, the NAV-005 rail primitive.
The checker enforces that the framework carries the contract as real, guarded
native wiring: the deck / title / panel fills routed to `@surface` through the
existing `Color_Deck*` / `Color_Panel*` slots (one tonal step brighter than the
`@surface-container` rail so the deck/rail hairline reads); the 14px deck content
inset guarded onto the existing `Int_Deck*Padding` slots; the deck title in the
`title` type role (`@on-surface`, 120% scale, `WEIGHT_SEMIBOLD`); the 12px
Material deck scrollbar; and click-active-to-collapse (`OpenThenToggleDeck` ->
`RequestCloseDeck`) plus the below-medium overlay-degrade predicate
(`ShouldDeckOverlayCanvas`, reading `Int_DeckOverlayMinWidth` = 600 and consumed in
the deck-open path). Each new `Theme` slot is checked as a declared enum member,
registered in both property-name maps, classified in `GetPropertyType`, and *set*
in `UpdateTheme` (metrics to literal density-invariant values, colours from the
Material-mapped `StyleSettings` getter). 22 mutation tests, all against
comment/raw-string-stripped source.

Two items are pinned but explicitly deferred: the 11px uppercase
`@on-surface-variant` section-heading **paint** -- the panel title bar is a
`weld::Expander` with no font API, so `Color_PanelSectionHeadingText` /
`Int_PanelSectionHeadingHeight` fix the colour and height as the source of truth
for the later panel-heading paint row -- and the actual **float-over-canvas**
overlay presentation: until the floating overlay compositor lands, the docked
controller only degrades safely by not force-widening a compact canvas, and the
pixel float-over presentation remains future work. `runtime_verified` is not
claimed; no native build, deck pixels, or runtime interaction are asserted.

## Wave-2 Batch C system-dialog, catalog, and modality contracts

Wave-2 Batch C (2026-07-22) adds twelve fail-closed source contracts covering
the whole-application system-dialog flows (WIN-SYS-001…-011, -015) and the
Features command catalog (WIN-CONCEPT-001). Each is source evidence only:
markers are checked in comment-stripped code, `.ui`/`definition.xml` structure
is parsed with ElementTree, every registry that carries a `runtime_verified`
field keeps it `false` (the checker rejects `true`), every carve-out keeps
`status: specified` (mutation-tested to fail if promoted), and none claims a
native build, pixels, or runtime interaction. Three real destructive
confirmations were migrated onto `sfx2::ConfirmDestructiveAction` and registered
in `dialog-anatomy-policy.json` (Save-As-Template overwrite, delete template
category, remove extension) — taking that shared registry to its 8-migration
cap — and a fourth (the shared basctl `QueryDel` funnel, five callers) was
converted and registered in `macro-surface.json` because the anatomy registry is
full. Those C++ conversions are compile-plausibility-checked against link
dependencies and includes, **not** compiled — a real compile happens only on the
Windows CI leg. Validate the whole cohort:

```sh
python bin/check-windows-file-flow-contract.py
python bin/test_windows_file_flow_contract.py
python bin/check-pdf-export-dialog-contract.py
python bin/test_pdf_export_dialog_contract.py
python bin/check-windows-document-properties-contract.py
python bin/test_windows_document_properties_contract.py
python bin/check-template-manager-contract.py
python bin/test_template_manager_contract.py
python bin/check-extension-manager-contract.py
python bin/test_extension_manager_contract.py
python bin/check-windows-macro-surface.py
python bin/test_windows_macro_surface.py
python bin/check-windows-security-prompt-modality.py
python bin/test_windows_security_prompt_modality.py
python bin/check-windows-recovery-safemode-contract.py
python bin/test_windows_recovery_safemode_contract.py
python bin/check-material-migration-compat-contract.py
python bin/test_material_migration_compat_contract.py
python bin/check-uui-interaction-contract.py
python bin/test_uui_interaction_contract.py
python bin/check-help-about-family.py
python bin/test_help_about_family.py
python bin/check-features-command-catalog.py
python bin/test_features_command_catalog.py
```

### File open/save flows (WIN-SYS-001)

`file-flow-policy.json` (contract `material-windows-file-flow-delegation`) is a
notification-producer + platform-delegation hybrid. `check-windows-file-flow-contract.py`
pins, fail-closed against comment-stripped source: the Windows `IFileDialog`
delegation boundary in `fpicker/source/win32/VistaFilePickerImpl.cxx`
(`FOS_FILEMUSTEXIST | FOS_OVERWRITEPROMPT`, the open/save `TDialogImpl<…>`
templates, and the `QueryInterface<IFileDialogCustomize>()` seam); the
`SystemFilePicker` → `"com.sun.star.ui.dialogs.OfficeFilePicker"` selection seam
in `sfx2/source/dialog/filedlghelper.cxx`; and the three no-`.ui` call-site
message boxes with their resid and whole-token-bound `VclMessageType`/
`VclButtonsType` (losing-scripting-signature Question/YesNo = decision, GPG
encrypt failure Warning/Ok = security, password-length Warning/Ok = credential).
Every box is asserted `modal: true` and `routes_to_notification: false`. A
read-only `cross_references` block re-checks that the querysavedialog/sfx2
password/remotefiles rows stay native-exclusion in `dialog-notification-policy.csv`
without re-registering them. It shares `filedlghelper.cxx`/`VistaFilePickerImpl.cxx`
with WIN-DLG-003 but pins only the delegation/seam/message-box literals, never the
Save-As sheet-drawing lines. 27 mutation tests; `runtime_verified: false`.

### PDF export tabbed dialog (WIN-SYS-002)

`pdf-export-dialog.json` (contract `material-pdf-export-dialog-composition`) is a
calc-chrome-style XML + source composition pin. `check-pdf-export-dialog-contract.py`
resolves the native `definition.xml` parts the tabbed dialog composes (the
8-state `tabitem`/Entire corner-pill, `tabheader`/`tabpane`/`tabbody`,
`windowbackground`/BackgroundDialog, `frame`/Border, the tab metrics, and 8
palette roles in both light and dark); the `pdfoptionsdialog.ui` `GtkNotebook`
`tabcontrol` (`tab-pos=left`) plus footer `ok`/`cancel`/`help` with a
has-default Export; and the `impdialog.cxx` ordered `AddTabPage` sequence
(general → initialview → userinterface → links → security → digitalsignatures,
checked by ascending source position), `SetCurPageId('general')`, each tab's
`Create` factory bound to its own `AddTabPage` call site, and each `SfxTabPage`
`.ui`/root-id binding. A `modal_exclusions` block cross-checks that the CSV
`PdfOptionsDialog` and `WarnPDFDialog` rows stay native-exclusion. Carve-outs
`tab_rail_geometry`, `security_field_anatomy`, and `non_pdf_export` keep
`status: specified`. 29 mutation tests; `runtime_verified: false`.

### Document Properties (WIN-SYS-003)

`document-properties.json` (contract `material-document-properties-composition`)
pins the `SfxDocumentInfoDialog` notebook composition (framed as the
dialog-notebook variant, distinct from the calc-strip tabitem pin).
`check-windows-document-properties-contract.py` resolves the `definition.xml`
native parts (8-state tabitem, tab style block and `noActiveTabTextRaise`/
`centeredTabs` settings, footer pushbutton, metrics, and 12 palette roles in
light and dark); the `documentpropertiesdialog.ui` modal notebook
(`tab-pos=left`, `group-name=icons`) and footer action-widgets (reset/ok/cancel/
help with help secondary); the ordered `dinfdlg.cxx` `AddTabPage` set with the
`RID_L` 32px icon-rail identity and each of the six `SfxTabPage` `.ui` roots
(cmisprops/security optional). The `STR_SFX_QUERY_WRONG_TYPE` wrong-type query is
recorded as an explicit non-destructive carve-out (`status: specified`, never
promoted). 34 mutation tests; `runtime_verified: false`.

### Template manager & save-as-template (WIN-SYS-004)

`template-manager.json` (contract `material-template-manager-composition`) pins
the three template dialog roots (`TemplateDialog`, `SaveAsTemplateDialog`,
`TemplatesCategoryDialog`): `.ui` action-widget footer order and response codes,
has-default primary, required-widget set, the OK labels set at runtime from the
`.cxx` (`STR_NEW_FROM_TEMPLATE`/`STR_SAVEDOC`, not the `.ui`), the
`definition.xml` windowbackground/pushbutton/checkbox/combobox/frame/listbox
parts, and the shared `RegexSearchController` search adjacency pinned (not
re-added). Two of the row's three `ConfirmDestructiveAction` conversions — the
Save-As-Template overwrite (`sfx2/source/doc/saveastemplatedlg.cxx`) and the
delete-template-category (`sfx2/source/doc/templatedlg.cxx`) — are validated by
the shared `check-material-dialog-anatomy.py`; this checker only cross-references
their migration ids so ownership is not doubled. Pixel-geometry/thumbnail-card/
list-item-Paint carve-outs stay `status: specified`. 29 mutation tests;
`runtime_verified: false`.

### Extension manager & dependency dialogs (WIN-SYS-005)

`extension-manager.json` (contract `material-extension-manager-composition`) pins
the nine desktop deployment roots (eight dialogs plus the `extensionmenu`
`GtkMenu`): footer/button-box label + secondary + has-default, native
pushbutton/checkbox/editbox/progress/frame/listnode parts, a read-only
`KeepModal` reconcile of the eight dialog roots against
`dialog-notification-policy.csv`, and the shared search adjacency. The
remove-extension `ConfirmDestructiveAction` conversion
(`desktop/source/deployment/gui/dp_gui_dialog2.cxx`, verb from
`RID_CTX_ITEM_REMOVE`) is registered in `dialog-anatomy-policy.json` and
validated by the shared anatomy checker. Pixel/density/RTL carve-outs stay
`status: specified`. 29 mutation tests; `runtime_verified: false`.

### Macro manager, organizer, IDE & security prompts (WIN-SYS-006)

`macro-surface.json` (contract `windows-macro-surface`) has three parts. Part 1
registers the shared basctl `QueryDel()` funnel
(`basctl/source/basicide/bastypes.cxx`) converted off its raw
`VclMessageType::Question`/`YesNo` box onto `sfx2::ConfirmDestructiveAction`: the
helper gained a per-caller verb parameter and all five callers now pass a verb
resource (`RID_STR_QUERYREPLACEBTN` for replace, `RID_STR_QUERYDELBTN` for the
four deletions), with three new resources in `basctl/inc/strings.hrc`. Because
`dialog-anatomy-policy.json` is at its 8-migration cap, this conversion is
registered here, not there. Part 2 pins `macrowarnmedium.ui` + `secmacrowarnings.cxx`
read-only (cancel/Disable = has-default/RET_CANCEL with `grab_focus`, ok/Enable
without). Part 3 asserts the 16 macro/organizer/security roots (11 basctl IDE
dialogs + 4 cui macro/script dialogs + 1 uui macro-execution prompt) stay
native-exclusion in the CSV. 21 mutation tests; `runtime_verified: false`.

### Certificates, digital signatures & macro-security prompts (WIN-SYS-007)

`security-prompt-modality.json` (contract `windows-security-prompt-modality`)
locks the modality of the five cert/signature/macro-security roots
(`DigitalSignaturesDialog`, `MacroSecurityDialog`, `SelectCertificateDialog`,
`ViewCertDialog`, `CertDialog`). `check-windows-security-prompt-modality.py`
imports `classify_route`/`read_registry`/`_scan_dialog_signals`/`EXCLUSION_REASONS`
from `check-windows-dialog-notification-contract.py` (via the py3.9
`sys.modules`-before-`exec_module` registration, never touching the git-based
`discover_dialogs` path). Four evidence layers per dialog: CSV native-exclusion +
matching reason; the live router `classify_route` over the real `.ui` returns
`KeepModal` with the declared reason; the modal footer action-widget order; and a
comment-stripped `GenericDialogController` bind + `::run()` reachability + the
embedded page roots. The four xmlsec roots classify `security` (partly via the
`xmlsecurity` path substring, recorded in each `classification_note`), and
`CertDialog` classifies `input`. 21 mutation tests; `runtime_verified: false`.

### Safe mode, crash recovery & profile recovery (WIN-SYS-009)

`recovery-safemode.json` (contract `material-recovery-safemode-composition`) pins
the seven real `.ui` roots (svx docrecovery recover/save/broken/progress +
crashreportdlg + safemodedialog, and sfx2 safemodequerydialog): per-dialog
widget-class, exact `<action-widget>` response + order, required-widget
existence, and — enforced fail-closed — the SAFE-default invariant, where
`DocRecoveryRecoverDialog` keeps has-default on `next` (Recover Selected, 101)
while `cancel` (Discard All, -6) must never carry it, and `SafeModeQueryDialog`
keeps has-default on `cancel` (-6) while `ok` (_Restart, -5) must not. It also
pins the SafeMode `radio_restore` active state, the weld bindings in
`docrecovery.cxx`/`SafeModeDialog.cxx` (via an optional-`u`/`_ustr` tolerant
regex), the `definition.xml` grounding with 5 palette roles in `''` and `dark`,
and read-only reconciles the 7 CSV rows plus the 3 retained no-nag safeguards in
`desktop/source/app/app.cxx`. The Discard-All → `ConfirmDestructiveAction`
conversion and the Material dialog anatomy are carve-outs at `status: specified`.
24 mutation tests; `runtime_verified: false`.

### Migration & profile compatibility (WIN-SYS-010)

`migration-compat.json` (contract `material-migration-compat`) pins the
SILENT-migration positive path in `desktop/source/migration/migration.cxx`
(`migrateSettingsIfNecessary`/`doMigration`/`setMigrationCompleted`, the
`MigrationCompleted` idempotency guard, the `SAL_DISABLE_USERMIGRATION` escape,
the `/MIGRATED4` stamp) **paired** with a forbidden-nag blocklist
(`weld::MessageDialog`/`AppendInfoBar`/`UpdateRequiredDialog`/
`MessageDialogController`/`ScopedVclPtrInstance` must be absent from the
comment-stripped migration path). It also pins the compat markers in
`check_ext_deps.cxx` and the compat-gates-migration ordering in `app.cxx`
(`CheckExtensionDependencies();` must precede `Migration::migrateSettingsIfNecessary();`),
and the `Setup.xcs` schema props. It read-only crosschecks the 3 compat dialog
rows (migrwarndlg/dependenciesdialog/updaterequireddialog) stay native-exclusion;
the legacy no-nag seed is a reference-only delegation (existence + one anchor
each), never re-seeded. 17 mutation tests; `runtime_verified: false`.

### Authentication, conflicts & generic error interaction (WIN-SYS-011)

`uui-interaction-policy.json` (contract `material-uui-interaction-modality`) is a
three-way modality lock over the `uui` module. `check-uui-interaction-contract.py`
imports the shared classifier (same py3.9 `sys.modules` registration, never the
git path), re-runs it live on each of the 10 uui `.ui` roots, asserts
native-exclusion, and three-way cross-checks the shared CSV; a completeness lock
requires the registry to cover exactly the uui roots the exhaustive CSV knows.
The four credential dialogs (Login/Master/Password/SetMaster) are proven to hit
the credential branch via a `visibility=False` password `GtkEntry`, and the
password signal must partition the credential set exactly. Modal conflict
`->run()` sites are pinned (`nameclashdlg.cxx`, `iahndl-errorhandler.cxx`,
`iahndl-locking.cxx`), plus the `isInformationalErrorMessageRequest` seam
(`iahndl.cxx`) and the modal `executeErrorDialog` presentation. The
`routing_carveout.status` is locked to `seam-only-not-wired`. 18 mutation tests;
`runtime_verified: false`.

### Help/About and legacy/optional-feature dialogs (WIN-SYS-015)

`help-about-family.json` (contract `windows-help-about-family`) pins
`aboutdialog.ui` (modal `GtkDialog`, single `btnClose` response -7, four
`GtkLinkButton`: btnCredits/btnWebsite/btnReleaseNotes/lbBuildString) and
`tipofthedaydialog.ui` (btnNext, btnLink, single btnOk -5) — the Tip modal claim
is keyed off its CSV native-exclusion row since its `.ui` declares no modal
property. It cross-checks that About/Tip stay native-exclusion, that the family
is absent from `dialog-anatomy-policy.json` destructive migrations
(a `no_destructive_role` guard that fails closed if any About/Tip/hyperlink
destructive migration is ever added), and that all 16 WIN-SYS-015 UI surfaces are
override-mapped in `ui-registry.json`. This row also performed the WIN-SYS-016
registry move: the 15 unassigned `cui` Help/About + legacy surfaces were added to
the closure checker's `OVERRIDES` table (`bin/check-windows-ui-registry-closure.py`),
and `ui-registry.json` was regenerated — `unassigned` 449 → 434, `assigned`
821 → 836, `total_surfaces` 1270 unchanged. 19 mutation tests;
`runtime_verified: false`.

### Features command catalog (WIN-CONCEPT-001)

`features-command-catalog.json` (contract `windows-features-command-catalog`) is
a generated, checked-in coverage ledger — an SRC-level artifact, not rendered
pixels. `check-features-command-catalog.py` binds all 2,433
`site/prototype-features.json` catalog rows to real `.uno` command nodes across
the ten officecfg `Office/UI/*Commands.xcu` files. The officecfg parse walks the
whole `UserInterface` subtree with ElementTree; a dispatch-first resolver (resolve
the base handler, fall back to the verbatim parameterized node) yields the
recorded resolution classes — exact-in-module 2366, base-in-module 53,
base-cross-file 14, **0 unresolved** — and the compound identity
`command`+U+241F+`name` is unique across all duplicate display names. The ledger
regenerates byte-deterministically (`--regenerate`), and the normative binding
rule and the 400-row render cap are documented in the design chapter's
§12.3 "Source binding (normative)" subsection, which the checker cross-checks.
This is a data-coverage ledger whose `source_note` disclaims build/pixels/
dispatch/localization; it carries no `runtime_verified` field, matching the
sibling component-gallery ledger. 22 mutation tests.

## Material unconditional activation (Windows)

`material-default-activation.json` (contract `material-default-activation`) pins
the fix for the defect that made the shipped fork look identical to stock
LibreOffice: the whole Material treatment packaged into every MSI but stayed
**dormant** because upstream reaches the file-defined widget path only when
`VCL_DRAW_WIDGETS_FROM_FILE` is set (`vcl/source/gdi/salgdilayout.cxx` gates
`FileDefinitionWidgetDraw`) and selects the shared theme only when
`VCL_FILE_WIDGET_THEME` == `material`, and no product code set either variable.
The Material assets themselves ship (`vcl/Package_theme_definitions.mk` installs
`material/definition.xml`).

Per operator directive — Material Design is the product — the activation is
**unconditional**: there is no opt-out environment variable and no user override.

`check-material-default-activation.py` cross-validates, fail-closed against real
comment-stripped source, the `#ifdef _WIN32` block that
`desktop/source/app/sofficemain.cxx` adds at the very top of `soffice_main()`,
BEFORE the first pre-existing statement (`sal_detail_initialize(sal::detail::InitializeSoffice`):
the Windows guard; both `_putenv_s` calls with the exact values `"material"` and
`"1"`; the registry's `activation.unconditional: true`; and every
`forbidden_markers` pattern being **ABSENT** from the whole file — the
`LIBREOFFICE_MATERIAL_THEME` opt-out token, `getenv("VCL_FILE_WIDGET_THEME")`,
and `getenv("VCL_DRAW_WIDGETS_FROM_FILE")`. A moved block, a dropped guard, a
drifted `_putenv_s` value, or a **reintroduced opt-out token or `getenv` override
conditional** fails closed. Two `asset_cross_checks` prove the activation cannot
outlive its assets — `salgdilayout.cxx` must still gate on
`VCL_DRAW_WIDGETS_FROM_FILE` and `Package_theme_definitions.mk` must still ship
`material/definition.xml`. (The stock native widget-draw code that
`salgdilayout.cxx` gates is deliberately retained, not deleted: the high-contrast
accessibility precedence and all non-Windows builds still depend on it.)

```sh
python bin/check-material-default-activation.py
python bin/test_material_default_activation.py
```

The 22 mutation tests fail closed on a removed/moved block, a dropped guard, a
`_putenv_s` value drift, a missing source or gate file, an asset-manifest drift,
a **reintroduced opt-out token or `getenv` override conditional** in source, a
registry that drops `unconditional`/`forbidden_markers`, or any other registry
drift (`runtime_verified: true`, wrong contract slug/schema/status, or a promoted
carve-out). This is source + wiring evidence only: `runtime_verified` stays
`false`, the `first_visual_verification` carve-out stays `status: specified`, and
no native build, theme pixels, or runtime observation of the activated theme is
claimed — the first release built after this change is the first shipped binary
with Material active by default.

## Wave-2 Mega wave foundations, surface, and system pins

The mega wave (2026-07-23) adds **33 new fail-closed source contracts** — one
triad (checker + registry + mutation suite) per surface — covering foundations,
widgets, dialogs, navigation chrome, and the Writer / Calc / Impress / Base / Math
application surfaces, plus **562 new mutation tests**. It also extends five
already-landed contracts in place: the Impress/Draw surface set grew from 6 to 10
surfaces (Impress pane/status-bar owner pins, Draw canvas-grid and
selection-overlay guarded colour branches), `startcenter-cards.json` gained the
`unavailable-preview` dimming role, `dialog-anatomy-policy.json`'s
`MAX_MIGRATIONS` rose 8 → 10 with two new destructive-confirmation migrations
(Digital Signatures remove-signature, Start Center clear-recent),
`notification-producer-policy.json` grew from 3 to 8 producers, and the search
registries registered a 13th source-integrated field. Every contract is source /
composition / ledger evidence only: markers are checked in comment-stripped code,
`.ui`/`definition.xml` structure is parsed with ElementTree, every
`runtime_verified` field stays `false` (the checker rejects `true`), and every
carve-out keeps `status: specified`, mutation-tested to fail if promoted. No
native build, pixels, or runtime interaction is claimed by any of them. Because
the honesty contract holds `B/V/I/A/L/P/C` open for every row (no build host
exists), at most `SRC`/`M`-adjacent source evidence advances; the presence-marker
and upstream/D-gate pins (WIN-SHL-002, WIN-CA-004, WIN-MA-001/002, WIN-SYS-014,
WIN-IM-001/003/004, WIN-BA-002, WIN-FND-004/006/007) explicitly do **not** advance
`M`, because existing upstream (non-Material-guarded) source never satisfies it.
Validate the whole cohort:

```sh
python bin/check-windows-theme-resolution-routing.py
python bin/test_windows_theme_resolution_routing.py
python bin/check-windows-elevation-contract.py
python bin/test_windows_elevation_contract.py
python bin/check-windows-reduced-motion-contract.py
python bin/test_windows_reduced_motion_contract.py
python bin/check-windows-density-contract.py
python bin/test_windows_density_contract.py
python bin/check-version-history-seeded-state.py
python bin/test_version_history_seeded_state.py
python bin/check-windows-adaptive-layout-ledger.py
python bin/test_windows_adaptive_layout_ledger.py
python bin/check-windows-icon-theme-pipeline.py
python bin/test_windows_icon_theme_pipeline.py
python bin/check-windows-render-scale-matrix.py
python bin/test_windows_render_scale_matrix.py
python bin/check-windows-pushbutton-contract.py
python bin/test_windows_pushbutton_contract.py
python bin/check-windows-icon-button-contract.py
python bin/test_windows_icon_button_contract.py
python bin/check-windows-options-dialog-contract.py
python bin/test_windows_options_dialog_contract.py
python bin/check-windows-office-filepicker-contract.py
python bin/test_windows_office_filepicker_contract.py
python bin/check-windows-print-dialog-contract.py
python bin/test_windows_print_dialog_contract.py
python bin/check-windows-find-replace-dialog-contract.py
python bin/test_windows_find_replace_dialog_contract.py
python bin/check-windows-notebookbar-composition.py
python bin/test_windows_notebookbar_composition.py
python bin/check-windows-titlebar-composition.py
python bin/test_windows_titlebar_composition.py
python bin/check-windows-command-overflow.py
python bin/test_windows_command_overflow.py
python bin/check-writer-chrome-contract.py
python bin/test_writer_chrome_contract.py
python bin/check-windows-writer-ruler-contract.py
python bin/test_windows_writer_ruler_contract.py
python bin/check-writer-format-dialogs-contract.py
python bin/test_writer_format_dialogs_contract.py
python bin/check-writer-sidebar-deck-contract.py
python bin/test_writer_sidebar_deck_contract.py
python bin/check-windows-writer-review-composition.py
python bin/test_windows_writer_review_composition.py
python bin/check-calc-grid-selection-contract.py
python bin/test_calc_grid_selection_contract.py
python bin/check-windows-calc-sheet-tabs-upstream-pin.py
python bin/test_windows_calc_sheet_tabs_upstream_pin.py
python bin/check-windows-calc-data-dialog-contract.py
python bin/test_windows_calc_data_dialog_contract.py
python bin/check-windows-data-grid-header-selection.py
python bin/test_windows_data_grid_header_selection.py
python bin/check-impress-slideshow-settings-contract.py
python bin/test_impress_slideshow_settings_contract.py
python bin/check-windows-impress-presenter-surfaces.py
python bin/test_windows_impress_presenter_surfaces.py
python bin/check-chart-editor-contract.py
python bin/test_chart_editor_contract.py
python bin/check-windows-base-rail-workspace.py
python bin/test_windows_base_rail_workspace.py
python bin/check-windows-base-addtable-tree-contract.py
python bin/test_windows_base_addtable_tree_contract.py
python bin/check-math-editor-elements-contract.py
python bin/test_math_editor_elements_contract.py
python bin/check-math-editor-contract.py
python bin/test_math_editor_contract.py
```

### Theme resolution routing (WIN-FND-002)

`theme-resolution-routing.json` (contract `material-theme-resolution-routing`)
pins the already-compiled HC-over-dark-over-light precedence chain against drift
with 8 markers anchored to real lines across `FileDefinitionWidgetDraw.cxx`
(HC short-circuit + native-fallback gate), `salnativewidgets-luna.cxx`
(uxtheme.dll ordinal-132 `ShouldAppsUseDarkMode` + AUTO/LIGHT/DARK officecfg
layering), `settings.cxx` (`SAL_FORCE_HC` + officecfg `HighContrast` override,
captured before update), `salgdilayout.cxx` (the `VCL_DRAW_WIDGETS_FROM_FILE`
opt-in), `salframe.cxx` (`SPI_GETHIGHCONTRAST` + the `WM_SETTINGCHANGE` /
`UpdateDarkMode` live-refresh), and `winproc.cxx` (the app-wide
merge→override→set cascade). **Calibration finding:** this row's earlier "SRC
incomplete" framing overstated the gap — the routing chain is fully compiled and
now pinned; the real remaining gates are `BUILD/PX/MATRIX` and platform-signal
completeness, not source. 16 mutation tests; `runtime_verified: false`.

### Elevation strategy (WIN-FND-003)

`elevation-strategy.json` (contract `material-elevation-strategy`) pins the one
implemented elevation channel — the native Frame/Border token quadruple
(`@outline-variant`/`@surface-container`/`@stroke-thin`/`@corner-container`) with
its 2px inset and the three tonal surface roles resolving in both palettes — and
holds the rest honest: each of the 7 §4 shadow-table rows is tagged prototype-only
with no matching native drawable, the three `--scrim` rgba literals byte-match the
foundations chapter (two real drifts in `site/prototype.html` were reconciled to
the doc, never the reverse), and `opacity` is asserted unparseable anywhere in the
widget schema. `M` advances to the border-channel subset; shadow/scrim/opacity
stay `SRC`-open. 13 mutation tests; `runtime_verified: false`.

### Reduced-motion signal (WIN-FND-004)

`reduced-motion-contract.json` (contract `material-reduced-motion`) pins the
pre-existing, non-Material accessibility-motion primitive a future Material motion
layer must route through: the four `MiscSettings` reduced-motion/allow-animation
declarations, `GetUseReducedAnimation()` delegating to the frame, each `Allow*`
officecfg key negating it on the `System` case, the Windows
`SPI_GETCLIENTAREAANIMATION` read, and the `xs:short`/default-0 schema props.
Marker 7 asserts `definition.xml` still carries **zero** motion/duration/easing
tokens — a deliberate `SRC`-gate trip-wire that keeps `M` visibly open: this
contract must never be read as satisfying the row's motion scope. 14 mutation
tests; `runtime_verified: false`.

### Density (WIN-FND-005)

`density-contract.json` (contract `material-density-model`) is a fail-closed
ledger proving the "single compiled profile, selectable density is target-only"
claim stays internally consistent: the 15 native metric roles keep their exact
values, the `<metrics>` element carries zero attributes (corroborated by the
`WidgetDefinitionReaderTest` invalid-fixture that proves the reader rejects a
density attribute), the foundations §6 compact/comfortable target table is present
verbatim (each row `status: specified`), the `calc-chrome.json` density carve-out
stays byte-consistent, and a repo-wide `.ui`/officecfg walk finds zero
density-selector control. It advances no gate beyond the already-`△` compiled
metrics. 15 mutation tests; `runtime_verified: false`.

### Version history seeded state (WIN-CONCEPT-002)

`version-history-seeded-state.json` (contract
`windows-version-history-seeded-state`) is a generated data-coverage ledger over
the inline seeded HISTORY/DOCS fixture in `site/prototype.html` plus a provenance
map to real upstream `versdlg.cxx` SIDs — prototype-internal coverage and
concept-vs-reality provenance, **not** proof of a native auto-commit engine.
Default mode fails closed on a missing/extra/drifted entry; `--regenerate`
rewrites deterministically. This moves the `D/M` cells toward the `✓△` state its
two sibling concept rows already hold. 14 mutation tests; `runtime_verified:
false`.

### Adaptive-layout ledger (WIN-FND-006)

`adaptive-layout-ledger.json` (contract `windows-adaptive-layout-ledger`)
enumerates every below-medium breakpoint the foundations §7 prose describes. It
carries exactly one real anchor — WIN-CON-007's `ShouldDeckOverlayCanvas` /
`Int_DeckOverlayMinWidth = 600` predicate, cross-referenced (not re-asserted) from
`sidebar-panels.json` — plus explicit `target-no-native-anchor` placeholders for
every other surface (WIN-SHL-002/NAV-004/NAV-008/dialog rows). A grep of
`framework/uielement` + `sfx2` fails closed if any other width-driven breakpoint
literal appears without a ledger entry. It does **not** advance WIN-FND-006's own
`SRC/M`: the cross-surface model still has zero other native code. 17 mutation
tests; `runtime_verified: false`.

### Icon-theme pipeline (WIN-FND-007)

`icon-theme-pipeline.json` (contract `windows-icon-theme-pipeline`) pins the
*existing* upstream icon pipeline (the `IconThemeSelector` fallback ids, the
`images_<id>.zip` naming, the literal icon-themes directory set) with a negative
guard that no `material*` icon theme directory exists and
`material_theme_installed: false`. It is an upstream-presence pin plus an absence
guard: `M` stays `·`, because the Material line-icon theme this row's title
promises is unwritten. 18 mutation tests; `runtime_verified: false`.

### Render/scale neutrality (WIN-SYS-014)

`render-scale-matrix.json` (contract `material-render-scale-neutrality`) pins six
render/scale *preconditions* — `FileDefinitionWidgetDraw.cxx` contains none of the
render-method selection identifiers (`renderMethodToUse`/`isVCLSkiaEnabled`/
`SAL_SKIA`/`RenderVulkan`/`RenderMetal`/`SkiaHelper::`), the system-DPI-aware
manifest is exactly `<dpiAware>true</dpiAware>` with no PerMonitor token and is
wired to the executable via `mt.exe -updateresource`, Skia is the Windows default
with a real software-raster fallback path — plus a `specified` matrix carve-out.
It is framed strictly as a regression guard and moves **no** gate; `M` stays `·`.
16 mutation tests; `runtime_verified: false`.

### Push buttons (WIN-ACT-001)

`pushbutton-contract.json` (contract `material-pushbutton-composition`) pins the
13 compiled Entire-state signatures (plain ×5, action ×4, flat ×4) plus the shared
Focus part and the D-020 default-slot text pairing, cross-checks the pushbutton
cell count against `component-gallery-coverage.json`, and carries a **temporary
negative guard**: `extra="outlined"` must not appear in `definition.xml` and the
`ControlType::Pushbutton` branch must still test only `mbIsAction`/`m_bFlatButton`
— so the contract fails closed the instant outlined XML is added without the native
signal, and must be inverted the day that signal lands. `outlined`/`default_emphasis`
stay `status: specified` with non-empty `blocked_on`. 19 mutation tests;
`runtime_verified: false`.

### Icon buttons (WIN-ACT-003)

`icon-button-contract.json` (contract `material-icon-button-composition`) pins the
four real icon-only consumers (infobar close, propertychip remove, notification
dismiss/close) at their exact `.ui` path + object id, each keeping a non-empty
icon-name and translatable tooltip (the only accessible-name channel today), with
Class-A consumers staying `weld_toolbar`-built toolbar children and Class-B
consumers staying `weld_button`-built with their pushbutton fallback. A closed-world
`.ui` walk (its own Git enumeration, not the concurrently-edited registry) fails
closed if a fifth icon-only candidate appears. It proves which shared part each
consumer falls back to, not a standalone icon-button native part. 16 mutation
tests; `runtime_verified: false`.

### Options dialog (WIN-DLG-002)

`options-dialog-composition.json` (contract `material-options-dialog-composition`)
composition-pins `optionsdialog.ui`'s two-pane tree/content shell grounded in the
`definition.xml` `listnode`/`listnet` `@size-tree-node` parts, the footer
action-widget order/response-codes/secondary flags, and the 12 ordered node groups
with their guard conditions. The Apply-button-not-in-action-widgets footer drift,
the not-themeable tree-row selection fill, and the density/adaptive-width and
field-grid/floating-label treatments are honest carve-outs at `status: specified`.
`M` advances to the composition subset. 21 mutation tests; `runtime_verified:
false`.

### Office file picker (WIN-DLG-003)

`office-file-picker-composition.json` (contract
`material-office-file-picker-composition`) pins the fallback Save-As/Office file
picker composition and its surrounding message box, cross-references the win32
delegation seam (`OfficeFilePicker` literal in `filedlghelper.cxx`) and the
`explorerfiledialog.ui`/`foldernamedialog.ui` native-exclusion CSV rows, and
anchors the "breadcrumb row" to the real `current_path` `SvtURLBox` (not the remote
picker's `breadcrumb.ui`). The `.ui` controls are stock GTK widgets with no
Material styling hook, so `M` stays `·` — this is an upstream composition +
delegation pin, honest about the field-styling gap. 14 mutation tests;
`runtime_verified: false`.

### Print dialog (WIN-DLG-004)

`print-dialog.json` (contract `material-print-dialog-composition`) is a
single-`.ui` `GenericDialogController` pin modeled on the PDF-export precedent: the
`definition.xml` native parts the dialog composes, the `printdialog.ui` structure
and footer, and the real four-button preview pager (correcting the design prose's
two-button simplification). It has no compile-time tab sequence — Print's General
page is static and the app-specific pages are runtime-injected — so that is carved
out honestly rather than faked. `M` advances to the composition subset. 20
mutation tests; `runtime_verified: false`.

### Find & Replace dialog closure (WIN-DLG-005)

`find-replace-dialog.json` (contract `windows-native-find-replace-dialog-closure`)
pins that `SvxSearchDialog` stays a `SfxModelessDialogController` (so live
find-as-you-type can never silently become application-modal) and re-runs, in
process, the four satellite contracts the row depends on: `find-replace-fieldset.json`
(WIN-INP-006), `regex-search-integrations.json`'s `document.find-replace` entry,
the shared regex-builder foundation, and the `srchdlg-replace-all-outcome`
notification producer — importing each via the py3.9 `sys.modules`-before-exec
order. Because the Material field set and builder are genuinely source-composed
(INP-006 is already `△`), the dialog row inherits an `M` subset. 16 mutation
tests; `runtime_verified: false`.

### Notebookbar composition (WIN-NAV-004)

`notebookbar-composition.json` (contract `material-notebookbar-composition`) locks
the one guarded-material-source edit in this cluster: behind
`VCL_FILE_WIDGET_THEME`, `NotebookBar::UpdateBackground()` resolves the group-area
wash to `@surface` via a helper mirroring `status.cxx`'s
`lcl_materialStatusColor`, while all four hardcoded per-module accent hexes
(`0x1a85d1`/`0x3cbc45`/`0xe75729`/`0xe5b443`) and their `Merge()` calls stay verbatim
on the native path. Scope is the group-area wash **only**, not the 38px tab-row
band — stated in the registry so it is never over-credited. `M` advances to that
subset. 12 mutation tests; `runtime_verified: false`.

### Window/floating title bars (WIN-NAV-007)

`titlebar-composition.json` (contract `material-titlebar-composition`) pins the
compiled title-bar metrics (window 18 / floating 14) and the active/deactive
style-slot token wiring in `definition.xml` and the generic `StyleSettings` push
in `FileDefinitionWidgetDraw.cxx`, **plus a fail-closed absence guard**: no
`GetActiveColor()`/`GetDeactiveColor()` consumption and no `DWMWA_CAPTION_COLOR`/
`DWMWA_BORDER_COLOR` call may appear in `brdwin.cxx`/`salframe.cxx` —
`consumption.status` must stay `not-wired`, the mirror of the statusbar contract's
"specified" pattern for a fact that is currently false. 16 mutation tests;
`runtime_verified: false`.

### Command overflow (WIN-SHL-002)

`command-overflow.json` (contract `windows-command-overflow`) pins the pre-existing
VCL toolbar-overflow reachability code as presence markers: `ImplToolItem::IsClipped`
(clipped items stay `mbVisible=true`, distinguishing overflow from removal),
`IsItemClipped`/`ImplHasClippedItems`, `UpdateCustomMenu`'s ordered rebuild,
`ImplChangeHighlightUpDn` folding the menu-button into arrow-key cycling,
`ImplDrawMenuButton`'s gated paint, and the `toolbarmanager.cxx` vcl→framework
wiring + `FillOverflowToolbar` order. This code predates and is independent of
Material (no guard, no token), so it must **not** be read as satisfying `M`; `M`
stays `·`. 15 mutation tests; `runtime_verified: false`.

### Writer classic chrome (WIN-WR-001)

`writer-chrome.json` (contract `material-writer-chrome-composition`) is the Writer
clone of the calc-chrome pin: `FMT.writer` = `textobjectbar.xml` and `standard` =
`standardbar.xml` exact ordered composition, the classic menu-bar top-level
sequence (encoding the real Writer-vs-Calc divergence — TableMenu/FormatFormMenu
replacing SheetMenu/DataMenu), and the shared nine-state toolbar Button part at
`@corner-toolbar` reused byte-for-byte from `calc-chrome.json`. `standard`-toolbar
`design_core` is marked inferred; density/combo carve-outs stay `specified`. `M`
advances to the composition subset. 26 mutation tests; `runtime_verified: false`.

### Writer ruler tokens (WIN-WR-002)

`writer-ruler-token-contract.json` (contract `material-writer-ruler-token-contract`)
pins the `definition.xml` `<style>` colour slots, the matching
`SetWindowColor`/`SetFaceColor`/`SetHighlightColor`/… assignments from
`pDefinitionStyle` in `FileDefinitionWidgetDraw.cxx`, and the
`rStyleSettings.Get*Color()` consumer call-sites in `ruler.cxx`/`swruler.cxx` (read
only), with an explicit carve-out for the `ThemeColors::IsThemeEnabled()`
office-theme-colors opt-in path (`status: specified`, officecfg default 0). Canvas
colour and page framing remain build-bound and are not pinned. `M` advances to the
ruler subset. 21 mutation tests; `runtime_verified: false`.

### Writer format dialogs (WIN-WR-003)

`writer-format-dialogs.json` (contract
`material-writer-format-dialogs-composition`) pins the Character / Paragraph /
Table Properties / Picture-Frame `SfxTabDialogController` dialogs — one entry each
(`characterproperties.ui`/`chardlg.cxx`, `paradialog.ui`/`pardlg.cxx`,
`tableproperties.ui`/`tabledlg.cxx`, `picturedialog.ui`+`framedialog.ui`/`frmdlg.cxx`
with an `applies_when` key for the 3-way `m_sDlgType` branch) plus a `shared_pages`
block for the reused svx Border/Area/Transparency pages. The real RID_M vs RID_L
icon-prefix divergence is preserved, never normalized. Mail merge / references /
page layout are out-of-slice carve-outs. `M` advances to the composition subset.
25 mutation tests; `runtime_verified: false`.

### Writer sidebar decks (WIN-WR-004)

`writer-sidebar-decks.json` (contract `material-writer-sidebar-decks`) pins the
Page-Styles and Navigator decks: their owner sources, `.ui` widget bindings
(`{id, gtk_class, weld_accessor}` triples validated against the real GtkBuilder
XML), the `SwPanelFactory` `resource_suffix`→`create_call` routes, and the
content↔global visibility switch (every pinned `show()`/`hide()` per branch plus
`TriggerDeckLayouting`/`SetGlobalMode` side-effects). No new `definition.xml` part
is pinned — the controls are stock weld widgets under generic theming. This is the
dedicated Writer sidebar deck checker the row previously lacked; `M` stays `△`
(subset), now on a real deck-composition basis. 17 mutation tests;
`runtime_verified: false`.

### Writer review composition (WIN-WR-005)

`writer-review-composition.json` (contract `material-writer-review-composition`)
pins the Track Changes toolbar (`changes.xml` 19-line ordered sequence +
`WriterWindowState.xcu` registration), the Comments deck (`Sidebar.xcu` →
`SwPanelFactory` `/CommentsPanel` branch → `CommentsPanel.cxx` loading
`commentspanel.ui`'s 9 weld ids and the nested `commentwidget.ui`'s 6), and the
Manage Changes deck proving Writer **mounts** the shared svx `SvxAcceptChgCtr`
(via `redlndlg.cxx` → `SwRedlineAcceptDlg`), not a stub. Its design ground-truth is
the new ch10 Review subsection. `M` advances to the composition subset. 19 mutation
tests; `runtime_verified: false`.

### Calc grid selection (WIN-CA-003)

`calc-grid-selection.json` (contract `material-calc-grid-selection-consumption`)
pins the real Material-routed selection chain: `definition.xml` accent/highlight
slots → `colorcfg.cxx`'s `GetDefaultColor` routing `CALCCELLFOCUS`/`CALCDBFOCUS`
to `GetAccentColor()` → the `hdrcont.cxx`/`gridwin.cxx`/`gridwin4.cxx` paint sites.
It documents two real caveats honestly: the chain only resolves to `@primary` when
the stored Application-Colors value is `COL_AUTO`, and **gridlines are `divergent`**
— `CALCGRID` has no `case` in `colorcfg.cxx` and falls to a fixed grey, so its
marker fails closed if a silent fix lands without updating the registry status.
`M` stays `△` on the now-properly-pinned subset. 16 mutation tests;
`runtime_verified: false`.

### Calc sheet tabs upstream pin (WIN-CA-004)

`calc-sheet-tabs-upstream-pin.json` (contract
`material-calc-sheet-tabs-upstream-pin`) is read-only verification that the shared
`svtools` `TabBar`/`TabDrawer` symbols the Material WIN-NAV-006 additive paint
delegates to (`TabBar::Paint`, `class TabDrawer`, `drawTab`, `GetPageRect`, …) stay
present and unforked, recording the four confirmed subclasses (Calc, Basic IDE,
Impress, Draw) as a shared-ownership fact. It pins **upstream** infrastructure, not
Material source, so `M` stays `·`. 12 mutation tests; `runtime_verified: false`.

### Calc data dialogs (WIN-CA-005)

`calc-data-dialogs.json` (contract `material-calc-data-dialogs`) pins the outer
shell/footer of the six core Data-menu dialogs (`.ui` root id, controller base +
`_ustr` load-path literals, ordered action-widgets, default/secondary responses)
and a generated `surface_ledger` classifying every remaining Data / chart2 `.ui` as
`standard-anatomy` or `custom-paint-guard-required`. It grounds in no
`definition.xml` part and claims only source composition of the dialog shells —
not that any Material anatomy is applied — so `M` stays `·`. 15 mutation tests;
`runtime_verified: false`.

### Data-grid header/selection (WIN-CON-003)

`data-grid-header-selection.json` (contract `material-data-grid-header-selection`,
`status: partial`) pins what IS wired — the `definition.xml` `<listheader>` Button
states and `<style>` highlight slots, the `FileDefinitionWidgetDraw.cxx` header
setters, and the Base BrowseBox `GetHighlightColor()`/`GetHighlightTextColor()`
consumption — alongside a **negative marker** that Calc's selected-header fill and
active-cell ring still route through `svtools::CALCCELLFOCUS`, not
`GetHighlightColor()`/`GetAccentColor()`. That marker and the registry's
`not_yet_material` status must move in lockstep with any future rewire. `M` stays
`△` on the compiled header subset. 17 mutation tests; `runtime_verified: false`.

### Impress slideshow settings (WIN-IM-003)

`impress-slideshow-settings.json` (contract
`material-impress-slideshow-settings-composition`) pins `presentationdialog.ui`'s 5
`GtkFrame` groups in grid order (Range / Presentation Mode / Presentation Options /
Display / Remote control) and the ok(-5)/cancel(-6)/help(-11) footer, plus 8
method-anchored wiring chains in `present.cxx` (range radios, windowed-forces-
always-on-top-off, pause/monitor/navbar sensitivity, display-name), cross-checking
the CSV native-exclusion row. It grounds in no `definition.xml` part — an upstream
dialog composition + wiring pin — so `M` stays `·`. The `presentationdialog.ui`
override was delegated to the closure ledger. 20 mutation tests; `runtime_verified:
false`.

### Impress presenter surfaces (WIN-IM-004)

`impress-presenter-surfaces.json` (contract `material-impress-presenter-surfaces`)
pins the `presenter.component` service registration and the animation `GtkTreeView`
/ transition `GtkIconView` widget-class facts, and asserts a fail-closed
**absence** marker that `sd/source/console/*` carries zero
`VCL_FILE_WIDGET_THEME`/`MaterialTokens` hooks — its PresenterTheme bitmap pipeline
is architecturally outside the widget-draw path, so no guarded slice is possible
and `M` stays `·`. It also flags the `transitions_icons` IconView vs design "grid"
mismatch. 16 mutation tests; `runtime_verified: false`.

### Chart editor (WIN-CH-001)

`chart-editor.json` (contract `material-chart-editor-composition`) grounds the
embedded chart2 editor treatment in already-compiled native parts, like
calc-chrome: the `toolbar.xml` exact ordered composition (including the two
`visible="false"` items), the 8 top-level `menubar.xml` menus, the 8
`Chart2PanelFactory` `endsWith` routes, the six `sidebar*.ui` panel ids, and the
`definition.xml` toolbar Entire/Button parts resolving in both palettes. The
custom-drawn chart canvas / live-preview / data-table grid / 3D scene stay a
`specified` carve-out (no `.ui`, no themeable part). Registry assignment was already
complete (`chart2/` → WIN-CH-001). 19 mutation tests; `runtime_verified: false`.

### Base navigation rail/workspace (WIN-BA-001)

`base-rail-workspace.json` (contract `material-base-rail-workspace`) locks the
cluster's guarded-material-source edits: reusing the `inputwin.cxx`
env+high-contrast guard idiom, `AppSwapWindow` fills the rail `@surface-container`,
a new named `panelhairline` box in `appborderwindow.ui` is tinted `@outline-variant`,
`OApplicationIconControl` re-points its highlight to `@primary-container`/
`@on-primary-container` via a `ThumbnailView::UpdateColors` override, and
`OTitleWindow` gains a guarded kicker variant. All paint logic stays in dbaccess
files; the shared `thumbnailviewitem.hxx` base is read-only here. `M` advances to
that subset. 17 mutation tests; `runtime_verified: false`.

### Base Add-Table tree (WIN-BA-002)

`base-addtable-tree.json` (contract `material-base-addtable-tree`) pins that the
Add Table/Query dialog's `tablelist` `GtkTreeView` binds the hierarchical
`GtkTreeStore` and wires through the already-compiled generic net-less
`listnode`/`listnet` `definition.xml` part (no custom subclass, no cell-renderer
override), covering both the Query and Relation designers via the shared
`OJoinController`. Because it proves an existing upstream tree routing through a
shared compiled primitive — not a Material application surface — `M` stays `·`.
Table/Query/Form/Report designers (unspecified in ch12) are carved out. 16 mutation
tests; `runtime_verified: false`.

### Math editor & elements (WIN-MA-001)

`math-editor-elements.json` (contract `material-math-editor-elements`) pins the
StarMath editor scroll/view bindings, the `editwindow.ui` scroll policy, the
elements-panel builder ids, the `GtkIconView` activation, and the closed 11-entry
`RID_CATEGORY_*` category list (pinning symbol identity + order, locale-safe).
**Honesty caveat:** marker 4 pins only that the shared `multilineeditbox`
`definition.xml` primitive is unchanged, **not** that Math consumes it — StarMath
has zero MaterialTokens consumption today (`WeldEditView` sources its own
`GetFieldColor()`), so this is a substrate/shared-primitive pin and `M` stays `·`.
17 mutation tests; `runtime_verified: false`.

### Math symbol/placeholder navigation (WIN-MA-002)

`math-editor.json` (contract `material-math-editor`) pins the placeholder-navigation
and error-recovery primitives over stable upstream anchors: `edit.cxx`
`SelNextMark`/`SelPrevMark` on the `<?>` literal, `InsertText` focus-return,
`MarkError`; `view.cxx` SID_NEXTMARK/PREVMARK/NEXTERR/PREVERR dispatch and
`ShowError` text+position pairing; the F4/F3 accelerators; and the
`multilineeditbox` states. **This is a D-gate source pin only** — per the inventory
legend "existing upstream UI source does not satisfy `M`", it proves the substrate
is present and unregressed and must **not** flip `M`, which stays `·`. The three
Material differentiators stay `status: specified`. 17 mutation tests;
`runtime_verified: false`.
