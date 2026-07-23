# Windows UI inventory

This is the measurable Windows-only closure ledger for every surface named by
the [roadmap](../ROADMAP.md) and the [design specification](design/README.md).
It records repository state at `a9cc4db959144dcb35b6f0691fbf11fb9f6fcdc5`.
The IDs are permanent: close or supersede a row; do not renumber or reuse it.

This is a surface inventory, not a claim that every upstream `.ui` file has
already been enumerated. `WIN-SYS-016` is the explicit registry-closure gate
that must produce that lower-level enumeration before Phase 6 can close.

## Status and gate contract

The checklist is `D M B V I A L P C`:

| Gate | Meaning |
| --- | --- |
| `D` | target behavior is specified in the design chapters |
| `M` | Material-specific native source implements the whole row scope |
| `B` | that implementation is compiled/tested in an exact Windows build |
| `V` | accepted genuine Windows captures cover the applicable visual matrix |
| `I` | pointer and keyboard flows pass with expected state transitions |
| `A` | roles, names, states, focus order, contrast, zoom, and motion pass |
| `L` | RTL, long-string, and representative CJK/CTL rows pass |
| `P` | agreed Windows performance budgets pass |
| `C` | document/profile/round-trip compatibility checks pass |

`✓` means the gate is complete for the entire row, `△` means accepted evidence
covers only a named subset, and `·` means missing or not run. Existing upstream
UI source does **not** satisfy `M`; a compiled shared VCL primitive does **not**
satisfy an application-surface `B`; and the HTML prototype satisfies only `D`.

Evidence keys:

- `E-BLD` — the exact-source Windows MSI/installation set and five required
  native targets at
  [`393263ad924eae8d64b4f9a35bd6486ef83578fc`](https://github.com/Ding-Ding-Projects/libreoffice-material/commit/393263ad924eae8d64b4f9a35bd6486ef83578fc),
  recorded in the [roadmap](../ROADMAP.md) and
  [local build record](LOCAL_WINDOWS_BUILD.md). This proves compilation and
  focused source tests, not a rendered component.
- `E-SC` — nine accepted Start Center images plus bounded UNO trees: light,
  dark, and forced high contrast, each at Home, visible Tab focus, and
  Templates. The light trio is from exact source
  [`393263ad924eae8d64b4f9a35bd6486ef83578fc`](https://github.com/Ding-Ding-Projects/libreoffice-material/commit/393263ad924eae8d64b4f9a35bd6486ef83578fc);
  dark and high contrast use that same exact source. Exact run manifests:
  [light](evidence/runs/20260720-143309-393263ad92-windows-headless-light/manifest.json),
  [dark](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/manifest.json),
  and [forced high contrast](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/manifest.json).
  See also the [screenshot index](SCREENSHOTS.md) and
  [evidence contract](HEADLESS_UI_EVIDENCE.md).
- `E-PROT` — the dependency-free [interactive prototype](../site/prototype.html)
  and its 9/9 validator. It is design evidence only, never build/runtime proof.
- `E-UPD` — focused Windows updater source tests and the locally built current
  major-upgrade implementation at
  [`7029dccf4`](https://github.com/Ding-Ding-Projects/libreoffice-material/commit/7029dccf4),
  plus the historical corrected-launch
  [`fbba560e2` normal public release](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2),
  as recorded in the [roadmap](../ROADMAP.md). No accepted updater UI or
  install-lifecycle run exists.

Missing-gate keys: `SRC` native Material implementation; `BUILD` exact Windows
compilation/test of that row's Material scope; `PX` build-backed
component/state pixel checks; `MATRIX` applicable theme, 100/125/200% scale,
window width, state, accelerated/software and reduced-motion rows; `FLOW`
pointer/keyboard workflow; `A11Y`; `LOC`; `PERF`; `COMPAT`; `LIFE` Windows MSI
install/update/repair/uninstall and restart-suppression lifecycle; `REGISTRY`
generated enumeration of every registered/optional UI surface.

## Shared foundations and components

All rows in this section are specified by chapters
[01](design/01-foundations.md), [02](design/02-actions.md),
[03](design/03-selection.md), [04](design/04-inputs.md),
[05](design/05-navigation.md), [06](design/06-containers.md), and
[07](design/07-feedback.md). The common native owner is `vcl`, principally
`vcl/uiconfig/theme_definitions/material/definition.xml` and
`vcl/source/gdi/FileDefinitionWidgetDraw.cxx`; framework-owned composition is
called out separately.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-FND-001 | color, shape, typography, metric and 72-slot style bridge | `vcl` theme definition + reader/draw paths | native token/part/state source compiled; surface consumption unproved | E-BLD | PX, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ ✓ ✓ · · · · · ·` |
| WIN-FND-002 | theme resolution: light, dark, system high contrast | `vcl` settings/theme initialization | routing source compiled; system-HC/platform paths incomplete; only Start Center sampled | E-BLD, E-SC | SRC and BUILD for system-driven HC/platform signals, PX, MATRIX | `✓ △ △ △ · △ · · ·` |
| WIN-FND-003 | elevation, opacity, shadow and scrim | `vcl` plus future shared shell owner | target/prototype only except border channel | E-PROT | SRC, PX, MATRIX, A11Y | `✓ · · · · · · · ·` |
| WIN-FND-004 | motion and reduced motion | unassigned shared `vcl`/`framework` owner | target/prototype only | E-PROT | SRC, MATRIX, FLOW, A11Y, PERF | `✓ · · · · · · · ·` |
| WIN-FND-005 | compact/comfortable density | `vcl` metrics plus application layout owners | fixed native metrics compiled; selectable density target only | E-BLD, E-PROT | SRC, PX, MATRIX, PERF, COMPAT | `✓ △ △ · · · · · ·` |
| WIN-FND-006 | compact/medium/expanded adaptive layout | `framework`, `sfx2`, application shells | target/prototype only | E-PROT | SRC, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-FND-007 | iconography and Windows asset pipeline | `icon-themes`, `vcl`, application commands | existing icon pipeline; Material icon contract not implemented | E-PROT | SRC, MATRIX, A11Y, LOC | `✓ · · · · · · · ·` |
| WIN-ACT-001 | push buttons: filled/tonal/outlined/text | `vcl` pushbutton parts; `VclBuilder` action mapping | filled/tonal/flat states compiled; outlined/default emphasis incomplete | E-BLD, E-SC | SRC, PX, MATRIX, FLOW, A11Y | `✓ △ △ △ △ △ · · ·` |
| WIN-ACT-002 | toolbar buttons | `vcl`; `framework/source/uielement` consumers | native states compiled; no surface checkpoint | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-ACT-003 | icon buttons | shared toolbar/VCL paths; surface owners | partial shared-source mapping; no row-scoped Windows build evidence | E-PROT | SRC, BUILD, PX, MATRIX, FLOW, A11Y | `✓ △ · · · · · · ·` |
| WIN-ACT-004 | split/combo command buttons | `vcl` combo/list/spin parts; `framework` controllers | component parts and RTL corrections compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-ACT-005 | links | `vcl` style slots; dialog/application owners | native FixedHyperlink + weld::LinkButton source-implement the §5 interaction contract (token @primary corner-focus ring replacing the platform focus rectangle, tintless-underline hover, disabled @outline plain non-focusable text, tracked/queryable visited state), locked by the link contract; visited a11y-state flag deferred (no upstream VISITED type) | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ △ · · · · · ·` |
| WIN-ACT-006 | Start Center Open File action | `sfx2/uiconfig/ui/startcenter.ui`, `vcl` builder/theme | action mapping compiled; idle/focus runtime subset | E-BLD, E-SC | hover/press, open-file FLOW, PX, MATRIX, A11Y | `✓ ✓ ✓ △ △ △ · · ·` |
| WIN-SEL-001 | checkbox | `vcl` checkbox parts; dialog owners | eleven native states compiled; no rendered fixture | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-SEL-002 | radio button | `vcl` radiobutton parts; dialog owners | eight native states compiled; no rendered fixture | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-SEL-003 | switch | no native owner assigned | prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y | `✓ · · · · · · · ·` |
| WIN-SEL-004 | filter chips | no native owner assigned; application consumers | prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |
| WIN-SEL-005 | list selection | `vcl` style/list paths | highlight slots and list parts compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-SEL-006 | selected tabs/rows | `vcl` tab/menu/list parts | state tuples compiled; no rendered strip/row | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-INP-001 | outlined text field | `vcl` editbox parts; surface owners | native states compiled; no field checkpoint | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-INP-002 | borderless and multiline edits | `vcl` edit parts; application owners | native parts compiled; no LTR/RTL checkpoint | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-INP-003 | combo/drop-down list box | `vcl` parts; `framework` controllers | parts compiled; closed Start Center field visible only | E-BLD, E-SC | open-popup PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ △ · △ · · ·` |
| WIN-INP-004 | spin field and standalone spin buttons | `vcl` spin parts | source/geometry corrections compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-INP-005 | search field and regex builder | shared `sfx2::RegexSearchController`; 27-field registry | ICU/LibreOffice engine and anchored advanced popover implemented in source; 12 of 27 shipping fields source-integrated under the four-strategy parameterized contract (67 mutation tests) and 15 fields carry documented architectural honest-gap analyses; build/runtime pending | E-PROT | SRC, BUILD, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-INP-006 | Find & Replace field set | `svx` dialog owner; shared `sfx2` builder foundation | whole Material field set source-composed against §6/6.1 (Match case, Whole words, Regular expressions all drive one SvxSearchItem ICU descriptor via a loop-safe regex-toggle sync) plus Replace field, notification-role result summary and emphasized 5-action set, locked by the find-replace-fieldset contract; live-preview run list, floating Replace label and filled-pill Replace-All deferred | E-PROT | SRC, BUILD, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-NAV-001 | menubar and drop menus | `framework/source/uielement`, `vcl` menu parts | native menu anatomy (248px popup min-width, 6px inner border, comfortable band/row minimums, 14px accel column) source-composed through the settings->NWF->`Menu::ImplCalcSize` channel behind the Material guard, plus the disabled-arrow @outline plumbing, locked by the menu-composition contract; prototype-only fine geometry (title-drop offset, exact text insets, monospaced accel) and build proof pending | E-BLD | BUILD, PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ △ · · · · · ·` |
| WIN-NAV-002 | context menus | application dispatch + `vcl` menu parts | context-menu composition now source-locked in the shared menu channel behind the Material guard: keyboard-first-highlight capture/consume, `rRect` placement feed into `StartPopupMode`, `SaveFocus`/`EndSaveFocus` focus save-return across the floating window, and top-level Esc dismissal, carried by the extended menu-composition contract (18 context-menu markers, 39-test suite); whole-composition build proof still pending | E-BLD | BUILD for full context-menu composition, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-NAV-003 | tab bars | `vcl` tab parts; dialog owners | sixteen state tuples compiled | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-NAV-004 | notebookbar/ribbon | `framework`, per-app `uiconfig` | upstream surface exists; Material composition target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-NAV-005 | sidebar rail | `sfx2`, `svx/source/sidebar`, app decks | 48px @surface-container rail with 38px corner-small buttons (4px gap under 10px top padding) and the idle/hover/active-deck/focus/disabled palette wired natively via the sfx2 sidebar `Theme` slots consumed by `TabBar` behind the Material guard, click-active-to-collapse preserved, locked by the sidebar-rail contract; 22px icon down-scaling and the bespoke @outline-variant rule + @primary focus ring (delegated to the shared toolbar part) remain | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ · · · · · · ·` |
| WIN-NAV-006 | Calc sheet tabs | `sc/source/ui` | `ScTabControl` additively renders (over `TabBar::Paint`, Material-guarded) the @outline-variant strip top rule and the selection-independent user tab-colour accent strip (design 05 §6.4), locked by the calc-sheet-tabs token/paint contract; the 34px strip band, 26px docked-tab geometry, active-tab @surface grid-join fill and the 28x26 Add-Sheet button stay in the svtools TabBar/TabDrawer base class (outside this row's file scope) | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-NAV-007 | window/floating title bars | Windows `vcl/win`, `framework`, OS frame | metrics compiled; active/inactive integration unverified | E-BLD | SRC, PX, MATRIX, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-NAV-008 | status bar | `sfx2`, application shells, `vcl` slider/parts | Material 28px band source-composed in vcl `status.cxx` (faceColor->@surface-container fill + @outline-variant top rule), zoom-slider parts and band/field tokens locked in definition.xml, and owner-draw status updates exposed as accessible value changes via the generic controller, all guarded behind VCL_FILE_WIDGET_THEME and locked by the statusbar-composition contract; field-hover wash stays spec-only (§8.2) and the 28/14/16/12px geometry is prototype-only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-CON-001 | lists/list items | `vcl` list parts; application owners | native container/selection parts compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-002 | trees | `vcl` tree/listnet paths | expanders and net suppression compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-003 | tables/data grids | `vcl` headers; `sc`, `dbaccess` compositions | header/selection slots compiled; grids target only | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ △ · · · · · ·` |
| WIN-CON-004 | outlined frames/separators | `vcl` frame/fixedline parts | native anatomy compiled | E-BLD | PX, MATRIX, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-005 | scrollbars | `vcl` scrollbar parts | native tracks/thumb/states compiled | E-BLD | PX, MATRIX, FLOW, A11Y, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-006 | Start Center document cards | `sfx2` recent/template views | RecentDocsView/TemplateDefaultView draw the full Material card anatomy natively (container, 118px preview, 74x92 thumbnail, corner-small badge chip, ellipsized caption, @primary hover border, corner-focus ring, filtered-empty message), token-resolved and guarded, locked by the startcenter-cards contract; per-module badge glyph, soft-shadow elevation, relative-time meta model and first-run welcome bitmap remain | E-BLD, E-SC | SRC, hover/focus/empty PX, MATRIX, FLOW, A11Y, PERF | `✓ △ △ △ △ △ · · ·` |
| WIN-CON-007 | panels and side panes | `sfx2`, `svx/source/sidebar`, app decks | sidebar deck / side-pane Material layout source-composed behind the Material guard (deck `@surface` fills, 14px inset, deck-title role, 12px Material scrollbar, `OpenThenToggleDeck` collapse-to-rail, `ShouldDeckOverlayCanvas` below-medium overlay-degrade) and locked by the sidebar-panels contract; panel section-heading paint and float-over-canvas overlay are documented deferrals, and the new layout source carries no build/pixels | E-BLD, E-PROT | SRC (deferrals), PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ △ · · · · · ·` |
| WIN-FBK-001 | determinate progress | `vcl` progress parts | full track/fill implementation compiled | E-BLD | PX, MATRIX, A11Y, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-002 | value-sensitive level indicators | `vcl` levelbar parts | four semantic bands compiled | E-BLD | PX, MATRIX, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-003 | sliders | `vcl` slider paths | native geometry/RTL corrections compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-004 | tooltips | `vcl` tooltip/style slots | native plate/text roles compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-005 | toasts/snackbars | `sfx2` `NotificationRouter` producer seam; `svx/source/dialog/srchdlg.cxx`, `sfx2` viewprn/newhelp producers | transient confirmations fold into the bottom-right notification stack (design 07 §7.5, no standalone snackbar plate): the Find & Replace Replace-All Success card routes via `lcl_NotifyMaterialReplaceOutcome` → `NotifyConfirmation` alongside the two Batch-A routed producers (printer-busy Warning, help-search Information), audited fail-closed (informational-only, `SafeDisplayText`, wiring-marker reachability) by the notification-producer contract; broad 597-root producer migration and build/pixels pending | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-FBK-006 | warning/error banners and infobars | `sfx2/source/dialog/infobar.cxx`, `vcl` style slots | all four InfobarType severities resolve Material container/on-container roles (INFO->primary-container, WARNING->warning-container, DANGER->error-container, SUCCESS->shared NotificationTheme resolved-green) with zero infobar-local hex, the corner-container 12px radius is code-painted with a high-contrast square bypass, and a polite AccessibleRole::NOTIFICATION announcement plus the 7.6 padding/gap/icon geometry are in place, locked by the infobar-severity contract; only the 7.6 13px/1.3 text metric is deferred to the Material typography layer | E-BLD, E-PROT | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ △ · · · · · ·` |
| WIN-FBK-007 | toast-on-action convention | unassigned shared shell owner | prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, PERF | `✓ · · · · · · · ·` |
| WIN-FBK-008 | empty/no-results states | each surface owner; `svx/source/dialog/srchdlg.cxx` + `sfx2` help-search routed outcomes | narrowed landing: the design 07 §7.8 no-results outcome ships for two routed producers only — Find & Replace "Search key not found" (Information-severity card) and the help-search no-matches notice — carried by the notification-producer contract; the general empty/no-results pattern across lists, grids, cards and other surfaces stays target/prototype, so this row is NOT whole-row done | E-PROT | SRC (remaining surfaces), PX, MATRIX, FLOW, A11Y, LOC | `✓ △ · · · · · · ·` |

## Shared shell, dialogs, and Start Center

The design owners are chapters [08](design/08-dialogs.md) and
[09](design/09-start-center.md); Phase 2 is the roadmap owner.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-SHL-001 | shared window shell/chrome | `framework`, `sfx2`, `vcl/win` | shared primitives compiled; Material shell composition incomplete | E-BLD, E-SC | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ △ △ △ △ · · ·` |
| WIN-SHL-002 | adaptive command layout and overflow | `framework/source/uielement`, app shells | target/prototype only | E-PROT | SRC, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-SHL-003 | notifications, infobars, snackbars | `sfx2/source/notification` (store, async facade, presenter, overlay stack, manager, router), `sfx2/source/dialog/infobar.cxx` | store, async snapshot facade, native manager window, bottom-right per-work-area stack, router facade with modal-semantics exclusions, and two routed producers implemented in source; broad 597-root producer migration and infobar Material anatomy pending | E-PROT | BUILD, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-DLG-001 | modal dialog anatomy, scrim, destructive confirmation | `vcl` dialog/weld paths, `sfx2::ConfirmDestructiveAction`, each dialog owner | background/buttons partly compiled; shared destructive-confirmation helper (safe action holds initial focus and Enter default), five converted confirmations, fail-closed dialog-anatomy contract, and policy-CSV modal reconciliation in source; sheet/scrim composition and keyboard-default emphasis pending | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-DLG-002 | Options dialog | `cui/source/options`, `cui/uiconfig/ui/optionsdialog.ui` | upstream dialog exists; Material two-pane target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DLG-003 | Save As and Windows file picker | `sfx2/source/dialog/filedlghelper.cxx`, `fpicker/source/win32` | upstream Windows flow exists; Material/fallback contract unverified | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ · · · · · · · ·` |
| WIN-DLG-004 | Print dialog | `vcl/uiconfig/ui/printdialog.ui`, `sfx2/source/doc/printhelper.cxx` | upstream dialog exists; Material composition target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DLG-005 | Find & Replace dialog + regex builder | `svx/uiconfig/ui/findreplacedialog.ui`, `svx/source/dialog`; builder unassigned | upstream dialog exists; redesign/builder target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-SC-001 | Start Center Home/shared shell | `sfx2/source/dialog/backingwindow.cxx`, `sfx2/uiconfig/ui/startcenter.ui` | Current Help/Extensions-only footer built and accepted in light, dark, and forced high contrast | E-BLD, E-SC | SC-01 dimensions, width/scale/render MATRIX, PX, FLOW, LOC, PERF, COMPAT | `✓ ✓ ✓ △ △ △ · · ·` |
| WIN-SC-002 | Open File focus/action flow | same `sfx2` source + `vcl` builder | visible Tab focus and UNO node accepted; hover/press/activation open flow absent | E-SC | SC-02 complete states, file-dialog FLOW, MATRIX, A11Y | `✓ ✓ ✓ △ △ △ · · ·` |
| WIN-SC-003 | Recent ↔ Templates navigation | `sfx2` recent/template views | Home/Templates states accepted; transition coverage partial | E-SC | SC-03 pointer+keyboard transition, selection semantics, MATRIX | `✓ ✓ ✓ △ △ △ · · ·` |
| WIN-SC-004 | filter combo, search and actions | `sfx2` combo/actions; search redesign unassigned | closed combo visible; popup/search/builder target unimplemented | E-SC, E-PROT | SRC, SC-04, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ △ · △ · · ·` |
| WIN-SC-005 | recent/template cards and empty/loading/error | `sfx2` views | native colors visible; target card/state composition incomplete | E-SC, E-PROT | SRC, SC-05/06, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ △ △ △ △ · · ·` |
| WIN-SC-006 | full traversal, RTL and surface semantics | `sfx2`, `winaccessibility`, `vcl` | one focus transition and bounded tree accepted only | E-SC | SC-08/09; SC-10 complete roles/states; LOC, MATRIX | `✓ △ △ △ △ △ · · ·` |

## Writer and Calc

Chapter [10](design/10-writer-calc.md) owns these targets. Existing upstream
application code is present, but no Writer- or Calc-specific Material surface
capture is registered.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-WR-001 | Writer shared chrome, classic toolbar and ribbon | `sw/source/uibase`, `framework`, `sfx2` | target/prototype; only shared parts compiled | E-BLD, E-PROT | SRC, writer toolbar/ribbon checkpoints, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-WR-002 | document canvas, ruler and page framing | `sw/source/uibase`, `sw/source/core` | target/prototype only | E-PROT | SRC, `writer-surface-canvas`, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-WR-003 | formatting, tables, images, references, mail merge, page layout | `sw/source/uibase`, shared `svx`/`sfx2` | roadmap target; no Material surface slice | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-WR-004 | sidebar: properties, styles, navigation | `sw/source/uibase/sidebar`, `svx/source/sidebar` | narrowed landing: the shared-weld svx Position-and-Size and Shadow sidebar panels are source-composed (outlined spinbox fields, Keep-ratio Material checkbox, normative 28px shadow slider thumb, angle combobox listbox, no-selection disabled policy) and registered in the impress-draw-surface contract; the planned dedicated `writer-surface-sidebar` checker was NOT built and the Writer properties/styles/navigation deck composition remains target/prototype — this row's Material scope is narrowed to the shared svx field anatomy | E-PROT | SRC, `writer-surface-sidebar` (not built), MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-WR-005 | review, comments, tracked changes, collaboration, search, error states | `sw/source/uibase`, `svx`, `sfx2` | roadmap target only | E-PROT | SRC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-WR-006 | Writer keyboard/HC/round-trip suite | `sw` UI tests and document filters | acceptance target only | none | SRC, `writer-surface-keyboard/hc`, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-CA-001 | Calc shared chrome/formatting toolbar | `sc/source/ui`, `framework`, `sfx2` | Calc classic-chrome composition pinned (FMT.calc + standard toolbar command identity/order, separator placement, per-button visibility) and grounded in the native toolbar part contract (nine-state Button at `@corner-toolbar`=18, band/entire/separator token roles), locked by the calc-chrome contract; density selection and prototype combo geometry are recorded spec-only carve-outs, and no build/pixels exist for the row scope | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-CA-002 | formula bar/name box/function controls | `sc/source/ui` | `ScInputWindow` formula row (Name Box `ScPosWnd` combobox, fx Function-Wizard and Sum items, formula-input window) additively painted over `ToolBox::Paint` behind the Material guard: guarded `@corner-container` token consumption, `@surface`/`@on-surface` centralization, and the `@outline-variant` bottom rule, locked by the calc-formula-bar contract (built as `calc-formula-bar-contract`, reconciling the planned `calc-surface-formula-row` name); RTL order is specified-not-built (design 10 §10.4) and delegated to native `ToolBox` mirroring | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ · · · · · · ·` |
| WIN-CA-003 | grid, headers, selection, alignment, dense profiles | `sc/source/ui`, `sc/source/core` | target/prototype; E-BLD covers shared highlight slots, not this application row | E-BLD (shared primitive only), E-PROT | SRC, BUILD, grid-selection/density/alignment/HC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-CA-004 | sheet tabs/status bar | `sc/source/ui` | target/prototype only | E-PROT | SRC, `calc-surface-sheet-tabs`, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |
| WIN-CA-005 | filters, sort, data, pivot, charts, conditional formatting | `sc/source/ui`, `sc/source/core`, `chart2` | roadmap target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-CA-006 | large-sheet and assistive navigation suite | `sc` UI/performance/accessibility tests | acceptance target only | none | SRC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |

## Impress, Draw, Base, Math, charts, and design-concept surfaces

Chapters [11](design/11-impress-draw.md) and
[12](design/12-base-math-shared.md) own the written targets. Their current
surface-specific accepted Windows capture count is zero.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-IM-001 | Impress slide pane, canvas, layouts and status | `sd/source/ui` | target/prototype; shared primitives compiled | E-BLD, E-PROT | SRC, checkpoints 1-3, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-IM-002 | Impress authoring and object properties | `sd/source/ui`, `svx` drawing/sidebar | the Draw/Impress graphic and text object bars (`GraphicObjectBar`/`TextObjectBar` SfxShells, commands declared in the toolbar-config XML, rendered through `ControlType::Toolbar` Button) are registered and marker-locked in the impress-draw-surface contract; the full authoring and object-properties Material scope beyond the object-bar command anatomy remains target/prototype | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-IM-003 | slide show and multi-display presentation | `sd/source/ui/slideshow`, `slideshow`, Windows display paths | roadmap target only | none | SRC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-IM-004 | presenter console, animations, transitions | `sd/source/ui`, `sdext`; Material owner not assigned | specified only; absent from prototype | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DR-001 | Draw tool rail, canvas, property panel, status | `sd/source/ui`, `svx` drawing/sidebar, `vcl` MaterialTokens | public MaterialTokens accessor with 1:1 fidelity contract, tool-rail definition-part contract, property-panel no-selection/disabled policy, and the page/objects status model registered in the impress-draw surface contract; dotted canvas-grid custom draw pending | E-BLD, E-PROT | SRC, Draw checkpoints 1-3, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-DR-002 | object select/drag/resize/rotate/align/layer | `sd/source/ui`, `svx/source/svdraw` | specified target; no Material overlay source | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DR-003 | keyboard/pointer parity and scaling grid | `sd`, `svx`, `winaccessibility` | acceptance target only | none | SRC, Draw checkpoints 4-5, MATRIX, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-BA-001 | Base navigation rail/object workspace | `dbaccess/source/ui` | target/prototype; shared primitives compiled | E-BLD, E-PROT | SRC, Base capture matrix, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-BA-002 | database tables/query/form/report workflows | `dbaccess`, `forms`, `reportdesign`, `reportbuilder` | roadmap target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-MA-001 | Math canvas/editor/elements panel | `starmath/source`, `formula` | target/prototype; shared multiline primitive compiled | E-BLD, E-PROT | SRC, Math capture matrix, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-MA-002 | symbol insertion, placeholder navigation and error recovery | `starmath/source` | design target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ · · · · · · · ·` |
| WIN-CH-001 | chart creation/editing across Calc/Writer/Impress | `chart2/source/controller`, application embeddings | roadmap target only; no dedicated design chapter | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `△ · · · · · · · ·` |
| WIN-CONCEPT-001 | Features command catalog | native owner unassigned; candidate `framework`; prototype data `site/prototype-features.json` | Features command catalog bound to source by the catalog contract (`windows-features-command-catalog`): all 2,433 `prototype-features.json` rows resolve to real `.uno` nodes across the ten officecfg `*Commands.xcu` files (dispatch-first resolver, 0 unresolved, unique `command`␟`name` identity) as a deterministically regenerable coverage ledger, with the 400-row render cap and binding rule pinned in design §12.3; this is an SRC-level coverage ledger, not a native surface or pixels; runtime evidence absent | E-PROT | SRC (native surface), PX, MATRIX, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-CONCEPT-002 | Version history | native owner unassigned; candidate `sfx2`/document model | prototype-only design concept | E-PROT | SRC, seeded-state/restore/compare checks, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-CONCEPT-003 | Components gallery | `site/prototype.html`; future native fixture owner unassigned | source-level coverage ledger landed: the component-gallery-coverage contract binds the gallery to every state generated from `definition.xml` (205 cells), reusing check-material-theme, with a dedicated 14-test mutation suite; the native `.ui` fixture and rendered pixels remain the separate B/V gate (M-gate coverage only, no native surface) | E-PROT | SRC (native fixture), PX, MATRIX, FLOW, A11Y, LOC | `✓ △ · · · · · · ·` |

## Remaining Windows system flows

These are Phase 2, Phase 6, Phase 7, or Phase 8 requirements that are not fully
owned by one application chapter. A row with an upstream owner but no complete
Material redesign remains `M·`.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-SYS-001 | common Open/Save/file flows | `sfx2/source/dialog`, `fpicker/source/win32` | file-flow delegation + surrounding message boxes source-locked by the file-flow contract (`material-windows-file-flow-delegation`): the win32 `IFileDialog`/`FOS_OVERWRITEPROMPT` delegation boundary, the `SystemFilePicker`→`OfficeFilePicker` selection seam, and the three no-`.ui` call-site message boxes (losing-scripting-signature=decision, GPG=security, password-length=credential — all modal, none routed); shared with WIN-DLG-003 but only the delegation/seam/message-box literals are owned; runtime evidence absent | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-002 | export flows including PDF | `filter/source`, `sfx2/source/doc` | PDF export tabbed dialog composition-pinned by the pdf-export contract (`material-pdf-export-dialog-composition`): the `definition.xml` 8-state tabitem/tabheader/tabpane native parts, the `pdfoptionsdialog.ui` left-rail `GtkNotebook` + Export-default footer, and the `impdialog.cxx` ordered `AddTabPage` sequence/`SetCurPageId`/per-page roots, with the CSV `PdfOptionsDialog`/`WarnPDFDialog` rows reconciled native-exclusion; tab-rail geometry, security-field anatomy and non-PDF export stay `specified` carve-outs; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-003 | document properties | `sfx2/source/dialog/dinfdlg.cxx`, `sfx2/uiconfig/ui/documentpropertiesdialog.ui` | Document Properties notebook composition-pinned by the doc-properties contract (`material-document-properties-composition`): the `definition.xml` 8-state tabitem, tab style/settings, metrics and 12 palette roles (light+dark); the `documentpropertiesdialog.ui` left-rail modal notebook + footer; and the `dinfdlg.cxx` ordered `AddTabPage` set with the `RID_L` 32px icon-rail identity and six `SfxTabPage` roots; `STR_SFX_QUERY_WRONG_TYPE` is a non-destructive `specified` carve-out; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-004 | template manager/save-as-template flows | `sfx2/source/doc/templatedlg.cxx`, `sfx2/uiconfig/ui/templatedlg.ui` | template dialogs composition-pinned by the template-manager contract (`material-template-manager-composition`): the three roots' footer order/has-default/required widgets, runtime-set OK labels from the `.cxx`, `definition.xml` parts and pinned `RegexSearchController` search adjacency; two destructive confirmations (Save-As-Template overwrite, delete category) migrated onto `sfx2::ConfirmDestructiveAction` and registered in `dialog-anatomy-policy.json`; thumbnail/list-item/pixel carve-outs `specified`; runtime evidence absent | E-SC (entry point only) | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-SYS-005 | extension manager and dependency dialogs | `desktop/source/deployment/gui` | extension-manager surfaces composition-pinned by the extension-manager contract (`material-extension-manager-composition`): the nine desktop roots' footer/button-box, native parts, a read-only `KeepModal` reconcile against the CSV, and the search adjacency; the remove-extension destructive confirmation migrated onto `sfx2::ConfirmDestructiveAction` and registered in `dialog-anatomy-policy.json`; pixel/density/RTL carve-outs `specified`; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-006 | macro manager, organizer, IDE and security prompts | `cui/source/dialogs`, `basctl/source/basicide`, `basic`, `scripting` | macro/organizer/security surface locked by the macro-surface contract (`windows-macro-surface`): the shared basctl `QueryDel()` funnel (five callers) migrated onto `sfx2::ConfirmDestructiveAction` with per-caller verb resources (registered in `macro-surface.json`, since the anatomy registry is at its 8-slot cap), `macrowarnmedium.ui`/`secmacrowarnings.cxx` disable-default modality pinned read-only, and 16 macro/organizer/security roots asserted native-exclusion; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-007 | certificates, digital signatures and macro security | `xmlsecurity/source/dialogs`, `cui/source/options/certpath.cxx` | certificate/signature/macro-security prompts modality-locked by the security-prompt contract (`windows-security-prompt-modality`): the five cert roots verified native-exclusion four ways (CSV reason, live router `KeepModal`, modal footer order, `GenericDialogController` bind + `::run()` reachability + embedded page roots); the four xmlsec roots classify `security`, `CertDialog` `input`; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-008 | onboarding/welcome | shared startup path; former Welcome controller/UI removed | canonical no-nag contract implemented; dedicated fresh/legacy blank-Writer harness source/mutations pass; exact-build capture/runtime pending | none | BUILD, E-NONAG-FRESH/LEGACY, FLOW, A11Y, LOC, COMPAT | `✓ ✓ · · · · · · ·` |
| WIN-SYS-009 | safe mode, crash recovery and profile recovery | `sfx2/source/safemode`, `framework/source/services/autorecovery.cxx`, `desktop/source/app` | recovery/crash/Safe-Mode composition-pinned by the recovery-safemode contract (`material-recovery-safemode-composition`): seven `.ui` roots' widget-class/action-widget order and the fail-closed SAFE-default invariant (Recover keeps default; Discard All/Restart never do), SafeMode restore-radio active, weld bindings, `definition.xml` grounding, and a read-only reconcile of the 7 CSV rows + 3 no-nag safeguards; Discard-All→`ConfirmDestructiveAction` and Material anatomy are `specified` carve-outs; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-010 | migration and profile compatibility | `desktop/source/migration`, `framework`, `configmgr` | migration/profile-compat pinned by the migration-compat contract (`material-migration-compat`): the silent-migration positive path (`migrateSettingsIfNecessary`/`MigrationCompleted` guard/`SAL_DISABLE_USERMIGRATION`/`/MIGRATED4`) paired with a forbidden-nag blocklist, the compat-gates-migration ordering in `app.cxx`, the `Setup.xcs` schema props, and a read-only crosscheck of 3 compat dialog rows; the legacy seed is reference-only; runtime evidence absent | none | SRC, E-NONAG-LEGACY, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-011 | authentication, conflicts and generic error interaction | `uui/source` | uui authentication/conflict/error interaction modality-locked by the uui-interaction contract (`material-uui-interaction-modality`): the 10 uui roots re-classified live native-exclusion with a completeness lock, the four credential dialogs proven to hit the credential branch, and the modal conflict `->run()` sites + `isInformationalErrorMessageRequest` seam pinned; `routing_carveout` locked `seam-only-not-wired`; runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-012 | updater check/download/stage/consent UI | `extensions/source/update/check` | Windows Material source compiled/focused-tested; runtime UI absent | E-UPD | PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT, LIFE | `✓ ✓ ✓ · · · · · ·` |
| WIN-SYS-013 | MSI install/update/repair/uninstall UI and restart suppression | `instsetoo_native`, `setup_native/source/win32`, updater launch path | MSI/release built; lifecycle acceptance rejected/pending | E-UPD | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT, LIFE | `△ △ ✓ · · · · · ·` |
| WIN-SYS-014 | GPU/software, remote desktop, fractional scale, multi-monitor | `vcl/win`, application shells | Phase 7 matrix target; software Start Center subset only | E-SC | SRC, BUILD for remaining paths, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · △ △ △ △ · · ·` |
| WIN-SYS-015 | Help/About and legacy/optional-feature dialogs | `cui`, `sfx2`, optional modules | Help/About family locked by the help-about contract (`windows-help-about-family`): `aboutdialog.ui` (btnClose -7 + four link buttons) and `tipofthedaydialog.ui` (btnNext/btnLink/btnOk -5) pinned, About/Tip reconciled native-exclusion and absent from destructive migrations, and all 16 WIN-SYS-015 UI surfaces override-mapped; the 15 unassigned cui Help/About surfaces were moved into the WIN-SYS-016 closure `OVERRIDES` table (see the regenerated counts on that row); runtime evidence absent | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-SYS-016 | registered UI inventory closure | `bin/check-windows-ui-registry-closure.py`, `qa/windows-ui-contract/ui-registry.json` | deterministic regenerable enumeration in source: 1270 surfaces (1260 `.ui` plus 10 explicit native-only) each mapped to one owner and one inventory row, 836 assigned via reviewable prefix/override tables (the Batch-C WIN-SYS-015 move added 15 cui Help/About surfaces to the override table), 434 in the explicit unassigned baseline that fails closed on growth; per-surface assignment of that baseline remains | none | per-surface row assignment of the 434-entry unassigned baseline | `✓ △ · · · · · · ·` |

## Measurable closure rules

1. The exact pre-inventory records linked under `E-BLD`, `E-SC`, and `E-UPD`
   are grandfathered for the baseline credits shown here even though their
   historical manifests do not name these later-created stable IDs. No other
   historical result gains credit by analogy or inheritance.
2. Every future checklist-credit change requires an accepted schema-v2
   evidence manifest containing the exact `source.commit` and one or more
   `scenarios[].inventory_ids` arrays naming each affected stable ID. Prototype
   screenshots never change `B`, `V`, `I`, or `A`.
3. An application row cannot inherit `B` or `V` from a shared primitive. It
   needs a Material-specific application/source slice and a real Windows run.
4. Every accepted surface run applies the scenario matrix in
   [the evidence contract](HEADLESS_UI_EVIDENCE.md) and records genuine image,
   interaction, accessibility, localization, performance, and compatibility
   results as applicable.
5. Phase 6 cannot close until `WIN-SYS-016` emits a deterministic list of all
   registered `.ui`, native-only, optional-feature, and Windows-platform
   surfaces; every emitted item must map to one owner and one inventory ID.
6. Whole-roadmap completion requires every applicable checklist cell to be
   `✓`, or a documented user-visible exception approved under the Phase 8 exit
   gate. The current scoped Start Center proof is progress, not suite closure.
