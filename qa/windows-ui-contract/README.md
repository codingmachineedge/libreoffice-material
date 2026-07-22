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

The `unassigned` count is an honest ledger figure, not a silent gap: the current
baseline is 449 of 1270 surfaces (chiefly the shared `cui`, `svx`, `svtools`,
`extensions`, and `vcl` dialog sets that no single inventory row owns). The
validator reports the count and does not fail merely because it is non-zero. It
fails closed on any drift from a fresh enumeration: an added, removed, or
renamed `.ui`; a newly `unassigned` surface not already in the checked-in
baseline; an unknown inventory ID; a duplicated surface; or any hand edit.

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
