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
| WIN-ACT-005 | links | `vcl` style slots; dialog/application owners | colors compiled; focus/hover/underline contract incomplete | E-BLD | SRC, PX, MATRIX, FLOW, A11Y | `✓ △ △ · · · · · ·` |
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
| WIN-INP-005 | search field and regex builder | shared `sfx2::RegexSearchController`; 26-field registry | ICU/LibreOffice engine and anchored advanced popover implemented in source; per-field integration/build/runtime pending | E-PROT | SRC, BUILD, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ · · · · · · ·` |
| WIN-INP-006 | Find & Replace field set | `svx` dialog owner; shared `sfx2` builder foundation available | upstream fields plus unintegrated shared regex foundation; Material composition/runtime pending | E-PROT | SRC, BUILD, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ △ · · · · · · ·` |
| WIN-NAV-001 | menubar and drop menus | `framework/source/uielement`, `vcl` menu parts | native parts compiled; full shell composition/build unverified | E-BLD | SRC and BUILD for full menu composition, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-NAV-002 | context menus | application dispatch + `vcl` menu parts | shared parts compiled; full composition/build unverified | E-BLD | SRC and BUILD for full context-menu composition, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-NAV-003 | tab bars | `vcl` tab parts; dialog owners | sixteen state tuples compiled | E-BLD | PX, MATRIX, FLOW, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-NAV-004 | notebookbar/ribbon | `framework`, per-app `uiconfig` | upstream surface exists; Material composition target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-NAV-005 | sidebar rail | `sfx2`, `svx/source/sidebar`, app decks | upstream surface exists; Material rail target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |
| WIN-NAV-006 | Calc sheet tabs | `sc/source/ui` | upstream surface exists; Material composition target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-NAV-007 | window/floating title bars | Windows `vcl/win`, `framework`, OS frame | metrics compiled; active/inactive integration unverified | E-BLD | SRC, PX, MATRIX, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-NAV-008 | status bar | `sfx2`, application shells, `vcl` slider/parts | upstream surface exists; Material composition target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-CON-001 | lists/list items | `vcl` list parts; application owners | native container/selection parts compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-002 | trees | `vcl` tree/listnet paths | expanders and net suppression compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-003 | tables/data grids | `vcl` headers; `sc`, `dbaccess` compositions | header/selection slots compiled; grids target only | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ △ · · · · · ·` |
| WIN-CON-004 | outlined frames/separators | `vcl` frame/fixedline parts | native anatomy compiled | E-BLD | PX, MATRIX, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-005 | scrollbars | `vcl` scrollbar parts | native tracks/thumb/states compiled | E-BLD | PX, MATRIX, FLOW, A11Y, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-CON-006 | Start Center document cards | `sfx2` recent/template views | colors compiled and cards visible; target anatomy/states incomplete | E-BLD, E-SC | SRC, hover/focus/empty PX, MATRIX, FLOW, A11Y, PERF | `✓ △ △ △ △ △ · · ·` |
| WIN-CON-007 | panels and side panes | `sfx2`, `svx/source/sidebar`, app decks | shared fills compiled; Material layout target only | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ △ △ · · · · · ·` |
| WIN-FBK-001 | determinate progress | `vcl` progress parts | full track/fill implementation compiled | E-BLD | PX, MATRIX, A11Y, PERF | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-002 | value-sensitive level indicators | `vcl` levelbar parts | four semantic bands compiled | E-BLD | PX, MATRIX, A11Y | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-003 | sliders | `vcl` slider paths | native geometry/RTL corrections compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-004 | tooltips | `vcl` tooltip/style slots | native plate/text roles compiled | E-BLD | PX, MATRIX, FLOW, A11Y, LOC | `✓ ✓ ✓ · · · · · ·` |
| WIN-FBK-005 | toasts/snackbars | unassigned shared shell owner | prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-FBK-006 | warning/error banners and infobars | `sfx2/source/dialog/infobar.cxx`, `vcl` style slots | colors compiled; Material composition target only | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
| WIN-FBK-007 | toast-on-action convention | unassigned shared shell owner | prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, PERF | `✓ · · · · · · · ·` |
| WIN-FBK-008 | empty/no-results states | each surface owner | target/prototype only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |

## Shared shell, dialogs, and Start Center

The design owners are chapters [08](design/08-dialogs.md) and
[09](design/09-start-center.md); Phase 2 is the roadmap owner.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-SHL-001 | shared window shell/chrome | `framework`, `sfx2`, `vcl/win` | shared primitives compiled; Material shell composition incomplete | E-BLD, E-SC | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ △ △ △ △ · · ·` |
| WIN-SHL-002 | adaptive command layout and overflow | `framework/source/uielement`, app shells | target/prototype only | E-PROT | SRC, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-SHL-003 | notifications, infobars, snackbars | `sfx2/source/notification`, `sfx2/source/dialog/infobar.cxx`; visible host/manager owner pending | bounded local Git store, bulk state model, history/undo and preference schema implemented in source; producer routing and Material composition pending | E-PROT | BUILD, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ △ · · · · · · ·` |
| WIN-DLG-001 | modal dialog anatomy, scrim, destructive confirmation | `vcl` dialog/weld paths plus each dialog owner | background/buttons partly compiled; composition target only | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC | `✓ △ △ · · · · · ·` |
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
| WIN-WR-004 | sidebar: properties, styles, navigation | `sw/source/uibase/sidebar`, `svx/source/sidebar` | target/prototype only | E-PROT | SRC, `writer-surface-sidebar`, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-WR-005 | review, comments, tracked changes, collaboration, search, error states | `sw/source/uibase`, `svx`, `sfx2` | roadmap target only | E-PROT | SRC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-WR-006 | Writer keyboard/HC/round-trip suite | `sw` UI tests and document filters | acceptance target only | none | SRC, `writer-surface-keyboard/hc`, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-CA-001 | Calc shared chrome/formatting toolbar | `sc/source/ui`, `framework`, `sfx2` | target/prototype; only shared parts compiled | E-BLD, E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-CA-002 | formula bar/name box/function controls | `sc/source/ui` | target/prototype only | E-PROT | SRC, `calc-surface-formula-row`, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |
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
| WIN-IM-002 | Impress authoring and object properties | `sd/source/ui`, `svx` drawing/sidebar | roadmap/design target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-IM-003 | slide show and multi-display presentation | `sd/source/ui/slideshow`, `slideshow`, Windows display paths | roadmap target only | none | SRC, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-IM-004 | presenter console, animations, transitions | `sd/source/ui`, `sdext`; Material owner not assigned | specified only; absent from prototype | none | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DR-001 | Draw tool rail, canvas, property panel, status | `sd/source/ui`, `svx` drawing/sidebar | target/prototype; shared primitives compiled | E-BLD, E-PROT | SRC, Draw checkpoints 1-3, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DR-002 | object select/drag/resize/rotate/align/layer | `sd/source/ui`, `svx/source/svdraw` | specified target; no Material overlay source | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-DR-003 | keyboard/pointer parity and scaling grid | `sd`, `svx`, `winaccessibility` | acceptance target only | none | SRC, Draw checkpoints 4-5, MATRIX, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-BA-001 | Base navigation rail/object workspace | `dbaccess/source/ui` | target/prototype; shared primitives compiled | E-BLD, E-PROT | SRC, Base capture matrix, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-BA-002 | database tables/query/form/report workflows | `dbaccess`, `forms`, `reportdesign`, `reportbuilder` | roadmap target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-MA-001 | Math canvas/editor/elements panel | `starmath/source`, `formula` | target/prototype; shared multiline primitive compiled | E-BLD, E-PROT | SRC, Math capture matrix, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-MA-002 | symbol insertion, placeholder navigation and error recovery | `starmath/source` | design target only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ · · · · · · · ·` |
| WIN-CH-001 | chart creation/editing across Calc/Writer/Impress | `chart2/source/controller`, application embeddings | roadmap target only; no dedicated design chapter | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `△ · · · · · · · ·` |
| WIN-CONCEPT-001 | Features command catalog | native owner unassigned; candidate `framework`; prototype data `site/prototype-features.json` | prototype-only design concept | E-PROT | SRC, 400-row/identity/dispatch checks, MATRIX, A11Y, LOC, PERF | `✓ · · · · · · · ·` |
| WIN-CONCEPT-002 | Version history | native owner unassigned; candidate `sfx2`/document model | prototype-only design concept | E-PROT | SRC, seeded-state/restore/compare checks, MATRIX, A11Y, LOC, PERF, COMPAT | `✓ · · · · · · · ·` |
| WIN-CONCEPT-003 | Components gallery | `site/prototype.html`; future native fixture owner unassigned | prototype-only verification surface | E-PROT | SRC or test fixture, PX, MATRIX, FLOW, A11Y, LOC | `✓ · · · · · · · ·` |

## Remaining Windows system flows

These are Phase 2, Phase 6, Phase 7, or Phase 8 requirements that are not fully
owned by one application chapter. A row with an upstream owner but no complete
Material redesign remains `M·`.

| Stable ID | Component/surface | Module and source ownership | Implementation status | Evidence | Missing Windows gates | Checklist `D M B V I A L P C` |
| --- | --- | --- | --- | --- | --- | --- |
| WIN-SYS-001 | common Open/Save/file flows | `sfx2/source/dialog`, `fpicker/source/win32` | roadmap/dialog target; upstream flow only | E-PROT | SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `✓ · · · · · · · ·` |
| WIN-SYS-002 | export flows including PDF | `filter/source`, `sfx2/source/doc` | roadmap target; upstream flow only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-003 | document properties | `sfx2/source/dialog/dinfdlg.cxx`, `sfx2/uiconfig/ui/documentpropertiesdialog.ui` | roadmap target; upstream dialog only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-004 | template manager/save-as-template flows | `sfx2/source/doc/templatedlg.cxx`, `sfx2/uiconfig/ui/templatedlg.ui` | roadmap target; upstream dialogs only | E-SC (entry point only) | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF | `△ · · · · · · · ·` |
| WIN-SYS-005 | extension manager and dependency dialogs | `desktop/source/deployment/gui` | roadmap target; upstream dialogs only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-006 | macro manager, organizer, IDE and security prompts | `cui/source/dialogs`, `basctl/source/basicide`, `basic`, `scripting` | Phase 6 target; upstream surfaces only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-007 | certificates, digital signatures and macro security | `xmlsecurity/source/dialogs`, `cui/source/options/certpath.cxx` | Phase 6 target; upstream dialogs only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-008 | onboarding/welcome | shared startup path; former Welcome controller/UI removed | canonical no-nag contract implemented; dedicated fresh/legacy blank-Writer harness source/mutations pass; exact-build capture/runtime pending | none | BUILD, E-NONAG-FRESH/LEGACY, FLOW, A11Y, LOC, COMPAT | `✓ ✓ · · · · · · ·` |
| WIN-SYS-009 | safe mode, crash recovery and profile recovery | `sfx2/source/safemode`, `framework/source/services/autorecovery.cxx`, `desktop/source/app` | Phase 7 target; upstream flows only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-010 | migration and profile compatibility | `desktop/source/migration`, `framework`, `configmgr` | fixed legacy no-nag seed/harness source exists; broader migration inventory and exact-build runtime remain open | none | D detail, SRC, E-NONAG-LEGACY, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-011 | authentication, conflicts and generic error interaction | `uui/source` | remaining-dialog target; upstream dialogs only | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, COMPAT | `△ · · · · · · · ·` |
| WIN-SYS-012 | updater check/download/stage/consent UI | `extensions/source/update/check` | Windows Material source compiled/focused-tested; runtime UI absent | E-UPD | PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT, LIFE | `✓ ✓ ✓ · · · · · ·` |
| WIN-SYS-013 | MSI install/update/repair/uninstall UI and restart suppression | `instsetoo_native`, `setup_native/source/win32`, updater launch path | MSI/release built; lifecycle acceptance rejected/pending | E-UPD | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT, LIFE | `△ △ ✓ · · · · · ·` |
| WIN-SYS-014 | GPU/software, remote desktop, fractional scale, multi-monitor | `vcl/win`, application shells | Phase 7 matrix target; software Start Center subset only | E-SC | SRC, BUILD for remaining paths, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT | `✓ · △ △ △ △ · · ·` |
| WIN-SYS-015 | Help/About and legacy/optional-feature dialogs | `cui`, `sfx2`, optional modules | Phase 6 catch-up target; no closed owner list | none | D detail, SRC, PX, MATRIX, FLOW, A11Y, LOC, PERF, COMPAT, REGISTRY | `△ · · · · · · · ·` |
| WIN-SYS-016 | registered UI inventory closure | build/config registries, every module `uiconfig`, optional features | explicitly planned; generated enumeration absent | none | REGISTRY, owner/evidence mapping for every enumerated surface | `✓ · · · · · · · ·` |

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
