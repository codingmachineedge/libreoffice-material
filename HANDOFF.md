# Windows-only handoff — 2026-07-21

This handoff supersedes the 2026-07-20 handoff. It was produced on a different
host (`Administrator` Windows 11 machine) than the previous `cntow` build host;
no local build root exists here, so every change below is source-implemented
and statically validated only.

## What is complete at this tip

- **Notification center, visible layer**: the asynchronous snapshot facade now
  has its native UI in source — `NotificationPresenter` (application-lifetime,
  snapshot-consuming, teardown-tolerant), `NotificationOverlayWindow` +
  `NotificationStackController` + `NotificationCard` (bottom-right
  per-work-area stack, severity styling via `NotificationTheme`),
  `NotificationManagerController` (folders, bulk actions mapping to single
  service requests, preferences), and the `NotificationRouter` facade whose
  classification keeps input/destructive/credential/security prompts modal.
  Two producers route through it: the help-search no-matches notice
  (`newhelp.cxx`) and the printer-busy notice (`viewprn.cxx`).
- **Regex search program**: the integration contract generalized twice into a
  strict parameterized form — four matcher strategies (in-handler legacy
  literal, options-handoff, native-regex-option-sync, controller-driven
  declared search sites), four default modes (including
  regex-native-case-insensitive), per-entry match subjects, and a 67-test
  fail-closed mutation suite. **12 of 27** registered shipping fields are
  source-integrated; **15** carry reviewed honest-gap analyses recorded in the
  2026-07-21 workflow journals (stacked auto-dismiss popovers, typeahead index,
  bidirectional similarity matchers, remote threaded catalog, split UNO
  toolbar ownership, stub surface, multi-collection branching filters,
  URL-based help engines).
- **Wave 1 of the full-UI rewrite** (from the 76-row audit plan):
  - WIN-DLG-001 (partial): `sfx2::ConfirmDestructiveAction` implements the
    §8.1 destructive-confirmation pattern (safe action = initial focus and
    Enter default); five real confirmations converted; fail-closed
    `check-material-dialog-anatomy.py` + `dialog-anatomy-policy.json`;
    `dialog-notification-policy.csv` reconciled with the router's modal
    exclusions.
  - WIN-DR-001 (partial): public `vcl` `MaterialTokens` accessor with 1:1
    fidelity contract (`check-material-token-accessor.py`), Impress/Draw
    surface contract (`check-impress-draw-surface-contract.py` +
    `impress-draw-surfaces.json`), property-panel no-selection policy, Draw
    status model. Dotted canvas-grid custom draw deferred to a build host.
  - WIN-SYS-016 (partial): deterministic UI-closure ledger
    (`check-windows-ui-registry-closure.py --regenerate` →
    `ui-registry.json`): 1270 surfaces, 821 assigned, 449 explicit unassigned
    baseline that fails closed on growth.
- **Wave 2 Batch A of the full-UI rewrite** (eight dependency-free
  shell/navigation/feedback rows, each behind the Material file-widget guard
  and locked by a new fail-closed checker + JSON registry + mutation suite):
  - Whole-row source scope: WIN-NAV-001 menubar/drop-menu anatomy carried
    through the settings→NWF→`Menu::ImplCalcSize` channel plus the
    disabled-arrow `@outline` plumbing (`menu-composition`, 18 tests over 24
    code markers); WIN-FBK-006 four-severity infobar Material container/
    on-container roles with a code-painted corner-container radius, high-contrast
    square bypass, and polite `AccessibleRole::NOTIFICATION` announcement
    (`material-infobar`, 16 tests); WIN-ACT-005 native `FixedHyperlink` +
    `weld::LinkButton` interaction contract with a `@primary` corner-focus ring
    and tracked/queryable visited state (`link-contract`, 25 tests).
  - Partial source with named residual deltas: WIN-NAV-005 48px sidebar rail
    via the sfx2 sidebar `Theme` slots consumed by `TabBar` (`sidebar-rail`, 14
    tests); WIN-NAV-008 28px status band with `@outline-variant` top rule and
    accessible owner-draw value changes (`statusbar-composition`, 21 tests);
    WIN-CON-006 Recent/Template Start Center card anatomy (`startcenter-cards`,
    18 tests); WIN-INP-006 Find & Replace Material field set driving one
    `SvxSearchItem` ICU descriptor with a loop-safe regex-toggle sync
    (`find-replace-fieldset`, 25 tests); WIN-NAV-006 Calc `ScTabControl` strip
    top rule and selection-independent tab-colour accent (`calc-sheet-tabs`, 22
    tests). No build or runtime evidence exists for any of it.
- **Static gate**: all **54** build-free Material validators pass at this tip.
  Enumeration method (run yourself, not inherited): every `bin/check-*.py` that
  reads a `qa/windows-ui-contract` registry or Material source — 26, i.e. all
  `bin/check-*.py` except the six stock upstream linters (`check-autocorr`,
  `check-icon-sizes`, `check-implementer-notes`, `check-missing-export-asserts`,
  `check-missing-unittests`, `check-sid-slots`) — plus every `bin/test_*.py`
  mutation suite (27) plus `bin/validate-prototype.mjs` (1) = **54**. Wave-2
  Batch B added exactly five checker+suite pairs (calc-chrome,
  calc-formula-bar, component-gallery-coverage, notification-producer,
  sidebar-panels) = 10 new files over the enumerated pre-Batch-B baseline of
  **44** on `main`. (The earlier handoff's "45" was a one-off over-count;
  re-enumerating the actual `main` tree yields 44.) All 54 were run green here
  with `py`/`node` from the repo root: 26 checkers exit 0, 27 suites pass,
  `validate-prototype.mjs` reports 9/9.

## Important boundaries

- **Updated 2026-07-22**: the five required native targets now DO compile
  and run green on both Linux (`29889642528`) and Windows
  (`29889642513`), including the notification view model/store-service/
  regex-foundation CppUnit coverage — see "CI iteration continued" below.
  That is real build+run evidence for those specific native targets and
  for the Windows MSI packaging step, but it is **not** the same as
  headless UI/screenshot evidence for the Material rewrite itself: the
  `B V I A L P C` inventory gates covering the actual on-screen appearance
  of wave-1/wave-2 surfaces are still untouched, and no screenshots exist.
  Do not conflate "CI is green" with "the UI looks/behaves as designed."
- The previous handoff's retained build root
  `C:\Users\cntow\lo-material-vs2026-577059e27` does not exist on this host.
  The Package-phase resume commands from the 2026-07-20 handoff apply only on
  a host that still has that root.
- The 15 honest-gap search fields need either targeted contract extensions
  (each gap analysis names the exact blocker) or per-surface rework (e.g.
  focus-model changes for the two auto-dismiss popover hosts) before
  integration; do not force them through the existing strategies.
- The 597-root dialog policy registry now carries explicit modal exclusions;
  the remaining informational roots still need producer-by-producer routing
  through `NotificationRouter` with registration in a producer registry
  (planned as `notification-producers.json` — designed in the wave-1 plan but
  NOT yet implemented; WIN-SHL-003's infobar Material anatomy is likewise
  still open).
- The full-UI audit plan (76 rows: 6 wave-1, 39 wave-2, 31 wave-3/build-bound,
  with per-row file lists, validators, and dependencies) is preserved in the
  2026-07-21 session scratchpad journals and summarized in the wave-1 commit
  messages. Wave-2 Batch A has now landed the eight dependency-free shell rows
  above (menubar, infobars, links, sidebar rail, status bar, Start Center
  cards, Find & Replace field set, Calc sheet tabs) at source level; the
  remaining wave-2 rows (Batch B onward) and all wave-3/build-bound rows are
  still open, as is build/runtime proof for everything in Batch A.
- Operator-instruction note: the user-level requirement for
  English/Cantonese/bilingual language modes has not been implemented for this
  fork; LibreOffice's own localization pipeline (including zh-* locales) is
  the existing mechanism, and reconciling that requirement with upstream l10n
  norms is an open operator decision recorded here rather than silently
  dropped.

## Final session state (2026-07-21, late-session ASAP handoff)

- **Merged and pushed on `main` (tip `b420ce9ae`)**: wave 1 (WIN-DLG-001
  partial, WIN-DR-001, WIN-SYS-016, gallery.search) AND wave-2 Batch A —
  eight rows: WIN-NAV-001 menubar composition, WIN-NAV-005 sidebar rail
  (partial), WIN-NAV-008 status bar, WIN-CON-006 Start Center cards,
  WIN-FBK-006 four-severity Material infobars, WIN-INP-006 Find & Replace
  field set (partial), WIN-ACT-005 links, WIN-NAV-006 Calc sheet-tab accents
  (partial). The complete build-free gate is green at this tip: 22
  checker+mutation pairs plus `check_search_field_coverage` and
  `validate-prototype.mjs`.
- **First compiler contact happened via CI**: the Linux focused-native run
  `29874968034` failed on two missing includes in the notification UI, fixed
  at `b420ce9ae` (weld `Container.hxx`/`Builder.hxx`). Expect FURTHER compile
  errors across this session's large C++ surface — the next continuation's
  FIRST task is iterating the hosted CI (or a local build) until the five
  required native targets compile, before any new feature work. The Windows
  MSI run for the pre-fix tip was in progress at handoff time and will fail
  the same way; watch the run triggered by `b420ce9ae` instead.
- **Wave-2 Batch B is MERGED to `main` (merge commit `c8c8eb7e3`) and all
  four CI workflows are CONFIRMED GREEN on that tip**: `Validate Linux
  native sources` (run `29940490742`), `Build Windows MSI` (run
  `29940490959`, release `windows-msi-82-1-c8c8eb7e33` published),
  `Windows UI contract` (run `29940490825` — first run of the reconciled
  25-pair static gate in CI), and `Validate Material UI source` (run
  `29940490795`). The task branch `claude/wave2-batch-b` was deleted after
  remote ancestor proof. That CI green covers compilation, the five
  required native targets, and the static contracts — it is NOT
  UI/screenshot evidence; the `B V I A L P C` gates below stay untouched. Nine rows were assessed (WIN-NAV-002, WIN-CON-007,
  WIN-WR-004, WIN-FBK-005, WIN-FBK-008, WIN-CA-001, WIN-CA-002, WIN-IM-002,
  WIN-CONCEPT-003) and locked by **five new fail-closed contracts** (calc-chrome
  → WIN-CA-001, calc-formula-bar → WIN-CA-002, component-gallery-coverage →
  WIN-CONCEPT-003, notification-producer → WIN-FBK-005/WIN-FBK-008,
  sidebar-panels → WIN-CON-007) plus **two extended contracts**
  (menu-composition gained 18 context-menu markers and a 39-test suite for
  WIN-NAV-002; impress-draw-surfaces gained the shared svx PosSize/Shadow and
  the Draw/Impress object-bar surfaces, 6 surfaces / 30 tests, for
  WIN-WR-004/WIN-IM-002). The component-gallery mutation suite was authored (14
  tests) and the CI workflow `windows-ui-contract.yml` was reconciled to run
  every Material checker+suite pair. **Two honest scope notes**: WIN-WR-004
  landed as the shared svx PosSize/Shadow field anatomy only — the planned
  dedicated `writer-surface-sidebar` checker was NOT built and the Writer
  properties/styles/navigation deck composition is untouched; and WIN-FBK-008
  landed as the design 07 §7.8 empty-state outcome for the Find & Replace and
  help-search routed producers only, carried by the notification-producer
  contract, not the general empty/no-results pattern. All 54 build-free
  validators are green at this tip. **Honesty boundary unchanged**: this is
  source-implementation evidence only — no native build ran, and no
  notification/formula/menu/sidebar/gallery runtime, pixels, or screenshots were
  produced for any Batch B row; the `B V I A L P C` inventory gates stay
  untouched, and CI-green ≠ UI-verified.
- **Wave-2 Batch C is LANDED IN SOURCE (2026-07-22)**: all twelve staged rows
  (WIN-SYS-001, -002, -003, -004, -005, -006, -007, -009, -010, -011, -015
  system-dialog flows + WIN-CONCEPT-001 Features catalog) are now locked by
  **twelve new fail-closed build-free triads** (checker + JSON registry +
  mutation suite each), **290 mutation tests total** (27 file-flow + 29
  pdf-export + 34 doc-properties + 29 template-manager + 29 extension-manager +
  21 macro-surface + 21 security-prompt + 24 recovery-safemode + 17
  migration-compat + 18 uui + 19 help-about + 22 features-catalog), all green
  here. The contracts: file-flow delegation (`material-windows-file-flow-delegation`,
  WIN-SYS-001), PDF export tabbed dialog (-002), Document Properties notebook
  (-003), template manager (-004), extension manager (-005), macro surface
  (-006), security-prompt modality (-007), recovery/Safe-Mode (-009),
  migration/compat (-010), uui interaction (-011), Help/About family (-015),
  and the Features command-catalog coverage ledger (WIN-CONCEPT-001, 2,433 rows
  bound to real `.uno` nodes across ten officecfg `*Commands.xcu`, 0 unresolved).
- **Four destructive-confirmation C++ conversions (compile-plausibility only)**:
  Batch C migrated four real confirmations onto `sfx2::ConfirmDestructiveAction`
  — **three** registered in `dialog-anatomy-policy.json` (Save-As-Template
  overwrite `sfx2/source/doc/saveastemplatedlg.cxx`, delete template category
  `sfx2/source/doc/templatedlg.cxx`, remove extension
  `desktop/source/deployment/gui/dp_gui_dialog2.cxx`), taking that shared
  registry from 5 to its 8-migration cap (`MAX_MIGRATIONS` was NOT raised; zero
  headroom remains — any further row needs coordination), and **one** (the
  shared basctl `QueryDel` funnel with five callers,
  `basctl/source/basicide/bastypes.cxx` + three new resources in
  `basctl/inc/strings.hrc`) registered in `macro-surface.json` because the
  anatomy registry is full. All four C++ edits are compile-plausibility-checked
  (link deps, includes, `SFX2_DLLPUBLIC` export) but **not compiled** — the real
  compile happens only on the Windows CI leg.
- **WIN-SYS-016 reassignment (ui-registry)**: the WIN-SYS-015 row moved the 15
  unassigned cui Help/About + legacy surfaces into the
  `bin/check-windows-ui-registry-closure.py` `OVERRIDES` table and regenerated
  `qa/windows-ui-contract/ui-registry.json`: `unassigned` 449→434, `assigned`
  821→836, `total_surfaces` 1270 unchanged (1260 `.ui` + 10 native). Verified by
  re-running the closure checker (`assigned=836, unassigned=434`).
- **D-detail design chapters + integrator index landed**: the design chapters
  gained the Batch-C detail (08-dialogs §8.3.1 + §8.6–§8.16, 07-feedback §7.1
  recovery addendum + §7.9 uui error-routing, 06-containers extension-list note,
  09-start-center template destination, 12-base-math §12.3 catalog
  source-binding); `qa/windows-ui-contract/README.md` gained a "Wave-2 Batch C"
  section (one contract subsection per triad + a runner block);
  `.github/workflows/windows-ui-contract.yml` gained 24 Batch-C steps (12 check +
  12 test, all referenced scripts verified present, YAML valid); and the twelve
  `docs/WINDOWS_UI_INVENTORY.md` rows were flipped (D `△`→`✓` for -002/-003/-004/
  -005/-006/-007/-009/-010/-011/-015, M `·`→`△` for all twelve including
  WIN-SYS-001 and WIN-CONCEPT-001) with honest per-row contract descriptions.
- **Static gate recomputed to 79, method stated (verify yourself, not
  inherited)**: the full build-free gate = every Material `bin/check-*.py` except
  the six stock upstream linters (`check-autocorr`, `check-icon-sizes`,
  `check-implementer-notes`, `check-missing-export-asserts`,
  `check-missing-unittests`, `check-sid-slots`) = **38**, plus
  `bin/check_search_field_coverage.py` = **1**, plus every `bin/test_*.py` = **39**,
  plus `bin/validate-prototype.mjs` = **1** → **79** scripts, all green here
  (`py`/`node` from repo root, 0 failures). Batch C added exactly 12 checkers +
  12 suites = 24 over the prior tip. **Reconciliation**: the earlier handoff
  reported the pre-Batch-C gate as "54", but that figure omitted
  `check_search_field_coverage.py` from the checker tally while counting its
  suite; a consistent enumeration of that same tip is 55, and 55 + 24 = **79**.
  The staging brief's "78" estimate inherited that earlier off-by-one.
- **Honesty boundary unchanged for Batch C**: source-implemented only. Every
  registry with a `runtime_verified` field keeps it `false` (the checkers reject
  `true`), all carve-outs stay `status: specified` (mutation-tested to fail if
  promoted), and no build/pixel/screenshot/runtime evidence is claimed for any
  Batch C row — the `B V I A L P C` inventory gates stay untouched. All 24 new
  Batch-C files and every edited index/narrative file are LF-only (0 CR bytes,
  verified). Wave 3 (31 rows) is build-host-bound per the audit.
- **Recurring defect to watch**: agent editors twice flipped whole files to
  CRLF (`menu.cxx`, `svdata.hxx`, `sw/qa/unit/swmodeltestbase.cxx`); a
  wholesale line-ending flip in a diff is a defect, not a change. A third
  instance hit `solenv/sanitizers/ui/sfx.suppr` while fixing the a11y gate
  below and was caught and reverted to LF before commit. A **fourth instance**
  flipped six Batch-B source files (`sc/source/ui/app/inputwin.cxx`,
  `sc/source/ui/inc/inputwin.hxx`,
  `svx/source/sidebar/possize/PosSizePropertyPanel.{cxx,hxx}`,
  `svx/source/sidebar/shadow/ShadowPropertyPanel.{cxx,hxx}`) and was normalized
  back to LF in commit `851fcd6dd` (6 files, 5120 insertions / 5120 deletions —
  a pure line-ending revert). A **fifth instance** re-flipped
  `sw/qa/unit/swmodeltestbase.cxx` in the working tree; it was caught and
  restored to LF before any commit (now byte-identical to `main`, verified
  CRLF=0). Check `git diff --stat` for suspiciously large line counts on small
  edits, and confirm line endings with a byte-level scan — Git Bash
  `grep $'\r'` gives FALSE positives on this host, so use Python
  `open(f,'rb').read().count(b'\r')` instead.

## CI iteration continued (2026-07-21/22, `df5239f63`)

- **Windows MSI `sfx.a11yerrors` fatal (was blocking `Build Windows MSI` on
  every push since `b420ce9ae`)**: `bin/gla11y` flagged 6 new FATAL warnings
  in the wave-1 notification `.ui` files — `sev_strip`/`sev_icon`
  (`notificationcard.ui`), `header_icon` (`notificationmanager.ui`, all
  decorative, no-labelled-by), `overflow_button` (`notificationstack.ui`,
  `button-no-label` — its text is set at runtime via
  `NotificationStackController::set_label`), and `list_view`/`history_view`
  (`notificationmanager.ui`, `no-labelled-by`). Fixed: suppression entries in
  `solenv/sanitizers/ui/sfx.suppr` for the four decorative/runtime-labelled
  widgets (matching existing precedent — `documentinfopage.ui` icon,
  `loadtemplatedialog.ui` drawing area, `extrabutton.ui` button), plus real
  translatable `tooltip-text` on the two tree views since they carry primary
  content. Verified locally by running `bin/gla11y` directly against the
  three files with `-s solenv/sanitizers/ui/sfx.suppr`: 0 new fatals.
- **`Validate Linux native sources` failing since `62fa5d025`** (when the
  `sfx2_regexsearch`/`sfx2_notificationstore` CppunitTests were added): those
  targets pull `Library_svxcore` into the build graph via `services.rdb` for
  the first time in this workflow. `svx/Library_svxcore.mk` compiles
  `svx/source/{fmcomp,form}/*` unconditionally and only gates the `dbtools`
  *link* on `DBCONNECTIVITY` — identical to upstream `LibreOffice/core`, so
  not a regression to "fix" in that file. With
  `--disable-database-connectivity` (present in `build-installer.yml` since
  its first commit), `gridcell.cxx`/`fmgridcl.cxx`/`formcontroller.cxx` etc.
  reference `dbtools::`/`connectivity::` symbols that never get linked in →
  `undefined reference` → `Library_svxcore` link failure →
  `CppunitTest_sfx2_regexsearch` target failure. Fix: removed
  `--disable-database-connectivity` from `build-installer.yml`.
  `configure.ac` documents that flag as "Work in progress, use only if you
  are hacking on it"; `windows-installer.yml` never disables it and links
  svxcore fine, so this restores the default/supported configuration rather
  than patching around it in vendor makefiles.
- **Full build-free gate reran green** after both fixes (all 29 checker/test
  pairs + `validate-prototype.mjs`).
- **Pushed as `df5239f63`** on top of `4896547c0`. CONFIRMED: the
  `DBCONNECTIVITY` fix was correct — run `29882830508` restored external
  tarballs, configured, and got all the way through `Library_svxcore`
  linking and most of `CppunitTest_sfx2_regexsearch`/
  `CppunitTest_sfx2_notificationstore` (1h40m total). No missing
  system-dep/tarball issue was observed; `apt-get build-dep libreoffice`
  did cover the newly-enabled DB connectivity stack.
- **New failure surfaced by getting further: a SIGSEGV**, not a build
  error. `NotificationViewModelTest::testVisibleCardsNewestFirstAndCap`
  crashed inside `cppu::_copyConstructAnyFromData`. Full chain from the
  coredump backtrace: `NotificationViewModel::MakeRow` →
  `lclRelativeTime` (`NotificationViewModel.cxx`) → `SfxResId` →
  `SvtSysLocale`/`SvtSysLocaleOptions_Impl` → `utl::ConfigManager::
  acquireTree`/`addConfigItem`. None of that can run safely without a
  bootstrapped UNO type-description manager and configuration provider.
  Root cause: `sfx2/CppunitTest_sfx2_notificationstore.mk` never called
  `gb_CppunitTest_use_ure` / `_use_vcl` / `_use_rdb(...,services)` /
  `_use_configuration` — its sibling `CppunitTest_sfx2_regexsearch.mk`
  already has all four (and passed earlier in the very same run, proving
  the pattern works in this CI environment). Fix: added the same four
  macros to `notificationstore.mk`. Pushed as `2cd1c5cf3`.
- **Cross-platform confirmation**: `df5239f63`'s `Build Windows MSI` run
  (`29882830485`) finished independently ~2h48m after it started (it does
  not share the Linux job's concurrency-cancel group) and hit the *exact
  same* crash at the *exact same* test — `Run required native C++
  regression tests` got through `CppunitTest_sfx2_regexsearch` fine, then
  `CppunitTest_sfx2_notificationstore` died silently right after starting
  `NotificationViewModelTest::testVisibleCardsNewestFirstAndCap` (no
  CppUnit failure message, abrupt step termination — Windows equivalent
  of the Linux SIGSEGV). It also independently confirms the Windows a11y
  fix: `Link critical Windows desktop library` (the step containing the
  `sfx.a11yerrors` gate) passed cleanly. Since `sfx2/
  CppunitTest_sfx2_notificationstore.mk` is a platform-agnostic gbuild
  file, the `2cd1c5cf3` fix applies to both platforms identically — this
  was expected, not a second bug.
- **`Validate Linux native sources` run `29889642528` on `2cd1c5cf3`:
  CONFIRMED GREEN** (11m30s, ccache warm) — `Linux focused native C++
  tests` job passed outright, all five required targets including the
  two sfx2 CppunitTests.
- **`Build Windows MSI` run `29889642513` on `2cd1c5cf3`: CONFIRMED GREEN**
  (2h54m29s, full MSI build + native regression tests). One pre-existing,
  non-fatal annotation (`C:\cygwin64\bin\git.exe` exit 128, `.github#16`)
  appeared but did not affect the run's success and is unrelated to this
  session's changes (present on prior failing runs too, e.g.
  `29882830485`) — not investigated further since it did not block a
  green result; revisit only if it starts failing the build outright.
- **BOTH REQUIRED CI LEGS ARE GREEN AT `main` TIP `ce7276f8e`** (and every
  commit from `2cd1c5cf3` onward, since later pushes were docs-only). The
  five required native targets (`tools_test`, `extensions_test_update`,
  `vcl_widget_definition_reader_test`, `vcl_file_definition_widget_draw_test`,
  `vcl_treeview`) plus the two sfx2 CppunitTests
  (`sfx2_regexsearch`, `sfx2_notificationstore`) are now genuinely
  build+run verified on both Linux and Windows — this is real runtime
  evidence, not just source-implemented. The Windows MSI artifact itself
  (installer packaging) was also produced successfully in this run.

## Unconditional Material activation (2026-07-22) — root cause of "no Material UI in newest release"

- **User report diagnosed**: "no Material UI in the newest release." Root cause
  is not a rendering regression — the entire Material treatment was **dormant in
  every shipped MSI**. Upstream reaches the file-defined widget path only when
  `VCL_DRAW_WIDGETS_FROM_FILE` is set (`vcl/source/gdi/salgdilayout.cxx`) and
  selects the shared theme only when `VCL_FILE_WIDGET_THEME` == `material` (the
  app-level theme-name guards), and **nothing in the product set either
  variable**. The Material assets *did* package
  (`vcl/Package_theme_definitions.mk` installs `material/definition.xml`), but
  every release through `windows-msi-82-1-c8c8eb7e33` — and every tag published
  since — shipped them inactive, so the fork looked identical to stock
  LibreOffice unless an operator exported both variables by hand
  (the old manual opt-in `README.md` documented).
- **Operator directive recorded (same-day flip to UNCONDITIONAL)**: the fix
  first landed as default-on **with an opt-out** (`LIBREOFFICE_MATERIAL_THEME=off`
  plus a respect-existing `getenv` override). The operator then directed that
  **Material Design IS the product — no opting out** — so the opt-out and the
  override were removed the **same day** and the contract was flipped to
  unconditional.
- **Fix as it now stands**: a `#ifdef _WIN32` block at the very top of
  `soffice_main()` (`desktop/source/app/sofficemain.cxx`), before the first
  pre-existing statement (`sal_detail_initialize`) and before any consumer reads
  the variables, **unconditionally** forces `VCL_FILE_WIDGET_THEME=material` and
  `VCL_DRAW_WIDGETS_FROM_FILE=1` via plain C runtime (`_putenv_s`) on every
  Windows launch. There is **no opt-out variable and no override**: both writes
  always run, so **stock native widget rendering is not a supported mode on
  Windows**. The **only** runtime path that bypasses Material is the system
  forced-colors / high-contrast precedence inside VCL, which stays as an
  **accessibility requirement, not an opt-out**. The Linux CI leg and the
  CppunitTests never enter `soffice_main`, so they stay stock.
- **Honest non-goal (stock rendering code stays)**: making activation
  unconditional does **not** mean deleting the stock/native widget-draw code.
  That code remains a **non-goal to remove** because the high-contrast /
  forced-colors accessibility precedence path and all non-Windows builds (Linux,
  macOS, headless) still depend on it. The flip removes the *user-facing opt-out
  and override*, not the fallback rendering machinery those other paths require.
- **Source contract flipped**: `material-default-activation`
  (`qa/windows-ui-contract/material-default-activation.json` +
  `bin/check-material-default-activation.py` + 22-test
  `bin/test_material_default_activation.py`) now cross-validates, against
  comment-stripped source — the `#ifdef _WIN32` guard, both `_putenv_s` calls
  with exact values before the first statement, `activation.unconditional: true`
  in the registry, and every `forbidden_markers` pattern (the
  `LIBREOFFICE_MATERIAL_THEME` opt-out token and either `getenv` override
  conditional) being **ABSENT** from the whole file. Reintroducing an opt-out or
  override fails closed. It still proves the `salgdilayout` gate and the
  `material/definition.xml` asset ship so the activation cannot outlive its
  assets. `runtime_verified` is `false` and the `first_visual_verification`
  carve-out stays `status: specified`. The 22 mutation tests include fail-closed
  inversions: a reintroduced opt-out token, a `getenv` override around either
  write, and a registry that drops `unconditional`/`forbidden_markers` all fail.
- **First-active-release boundary (honesty)**: the **first release built after
  this push is the first shipped binary in which Material is active by default**.
  This is source-implemented wiring only — no build ran on this host, the change
  is compile-plausibility only (a real compile happens on the ~3h Windows CI
  leg), and whether every surface renders as designed remains **unverified** until
  a real installed MSI is inspected. No pixel/screenshot/runtime evidence is
  claimed; the `B V I A L P C` inventory gates stay untouched.
- **Static gate now 81 (verify yourself, not inherited)**: the full build-free
  gate = every Material `bin/check-*.py` except the six stock upstream linters
  (`check-autocorr`, `check-icon-sizes`, `check-implementer-notes`,
  `check-missing-export-asserts`, `check-missing-unittests`, `check-sid-slots`) =
  **39**, plus `bin/check_search_field_coverage.py` = **1**, plus every
  `bin/test_*.py` = **40**, plus `bin/validate-prototype.mjs` = **1** → **81**
  scripts, all green here (`py`/`node` from repo root, 0 failures). That is the
  Batch C tip's **79** plus exactly the two new files
  (`check-material-default-activation.py` + `test_material_default_activation.py`)
  = **81**. The docs/index/workflow updates for this change (MATERIAL_DESIGN.md,
  README.md, ROADMAP.md, this file, `qa/windows-ui-contract/README.md`,
  `.github/workflows/windows-ui-contract.yml`) carry no new script.

## Wave-2 Mega wave landed in source (2026-07-23)

- **43 kept rows across 16 clusters + 1 integrator**, delivered as **33 new
  fail-closed triads** (checker + JSON registry + mutation suite each) plus **five
  in-place extensions** of already-landed contracts. **562 new mutation tests**,
  all green here. Source-implemented only: no native build ran, every
  `runtime_verified` stays `false`, every carve-out stays `status: specified`
  (mutation-tested against promotion), and no build/pixel/screenshot/runtime
  evidence is claimed — the `B V I A L P C` inventory gates are untouched.
- **Cluster-by-cluster (new triads unless noted):**
  - foundations-a: theme-resolution-routing (WIN-FND-002, 16), elevation-strategy
    (WIN-FND-003, 13), reduced-motion (WIN-FND-004, 14), density (WIN-FND-005, 15),
    version-history-seeded-state (WIN-CONCEPT-002, 14) — plus the two prototype
    writes (`site/prototype.html` two box-shadow drifts reconciled to the doc; a
    VERSION HISTORY FIXTURE check in `validate-prototype.mjs`).
  - foundations-b: adaptive-layout-ledger (WIN-FND-006, 17), icon-theme-pipeline
    (WIN-FND-007, 18), render-scale-matrix (WIN-SYS-014, 16).
  - widget-dialog-pins: pushbutton (WIN-ACT-001, 19), icon-button (WIN-ACT-003,
    16), options-dialog (WIN-DLG-002, 21), office-file-picker (WIN-DLG-003, 14),
    print-dialog (WIN-DLG-004, 20).
  - search-fields: find-replace-dialog closure (WIN-DLG-005, 16); the INP-005 13th
    field (certificate-chooser) via a real `certificatechooser.cxx`
    enumeration/`matchCertificate`-predicate refactor + `selectcertificatedialog.ui`,
    extending `regex-search-integrations.json` (72 tests) and `search-field-coverage.json`.
  - notifications (WIN-FBK-007/WIN-SHL-003): five acknowledgement modals converted
    onto `NotifyInfo` (`mailmodel.cxx`, `srcview.cxx`, `labfmt.cxx`, `wrtsh1.cxx`,
    `textfld.cxx` + two `strings.hrc`), `notification-producer-policy.json` grew
    3→8 producers with a `min_producer_modules=3` floor.
  - destructive-confirm (WIN-DLG-001/WIN-SC-004): `MAX_MIGRATIONS` 8→10 with two
    conversions — Digital Signatures remove-signature (`digitalsignaturesdialog.cxx`
    + `xmlsecurity/inc/strings.hrc`) and Clear Recent Documents (`backingwindow.cxx`).
  - startcenter-cards (WIN-SC-005): `unavailable-preview` dimming role + first-run
    native fallback pin; a default-false virtual `ThumbnailViewItem::isUnavailable()`
    in the shared base header, overridden on `RecentDocsViewItem`.
  - nav-chrome: notebookbar (WIN-NAV-004, 12 — the guarded `@surface` group-area
    edit in `notebookbar.cxx`), titlebar (WIN-NAV-007, 16), command-overflow
    (WIN-SHL-002, 15).
  - writer: chrome (WIN-WR-001, 26), ruler (WIN-WR-002, 21), format-dialogs
    (WIN-WR-003, 25), sidebar-decks (WIN-WR-004, 17), review (WIN-WR-005, 19).
  - calc-containers: grid-selection (WIN-CA-003, 16), sheet-tabs-upstream-pin
    (WIN-CA-004, 12), data-dialogs (WIN-CA-005, 15), data-grid-header-selection
    (WIN-CON-003, 17).
  - impress-draw-surfaces: `impress-draw-surfaces.json` extended 6→10 surfaces
    (WIN-IM-001 pane/status owner pins; WIN-DR-001 `draw.canvas-grid` and WIN-DR-002
    `draw.selection-overlay-guide-color` guarded colour branches in
    `viewobjectcontactofsdrpage.cxx`/`sdrpaintwindow.cxx`).
  - impress-chart: slideshow-settings (WIN-IM-003, 20), presenter-surfaces
    (WIN-IM-004, 16), chart-editor (WIN-CH-001, 19).
  - base-math: base-rail-workspace (WIN-BA-001, 17 — guarded Material source across
    four dbaccess surfaces + `appborderwindow.ui`), base-addtable-tree (WIN-BA-002,
    16), math-editor-elements (WIN-MA-001, 17), math-editor (WIN-MA-002, 17).
  - registry-closure (WIN-SYS-016): `ui-registry.json` regenerated, 184 surfaces
    moved out of `unassigned` (836→1020 assigned, 434→250 unassigned; 1270 total
    unchanged) via 4 new prefix rules + per-cluster overrides; 39-test suite green.
  - docs-stable + docs-influx: additive design detail across chapters 01/02/04/05/
    10/11 and 06/07/08/09/12 (including the new ch10 Review subsection and ch12 §12.6
    Chart embedded-editor section) — pattern applications, honest status labels.
- **Guarded-material-source / conversion edits (compile-plausibility only, NOT
  compiled here)**: `notebookbar.cxx` (NAV-004), `viewobjectcontactofsdrpage.cxx`
  (DR-001) and `sdrpaintwindow.cxx` (DR-002) — both svx files have cross-application
  blast radius into Calc/Writer/Base marquees, and both guarded branches are
  sequenced to LOSE to `GetHighContrastMode()` (a review gate the marker-presence
  validators cannot enforce); the four dbaccess surfaces (BA-001); the five NotifyInfo
  conversions; the two destructive-confirmation conversions; and the
  `certificatechooser.cxx` predicate split. A real compile happens only on the ~3h
  Windows CI leg.
- **Calibration finding applied (WIN-FND-002)**: the row's earlier "SRC incomplete"
  framing overstated the gap — the theme-resolution routing chain is fully compiled
  and now pinned; the real remaining gates are `BUILD/PX/MATRIX` and platform-signal
  completeness, not source. The inventory row's status/missing-gates cells were
  corrected; no glyph was moved.
- **M held open for the presence/upstream/D-gate pins (honesty legend)**: WIN-SHL-002,
  WIN-CA-004, WIN-CA-005, WIN-DLG-003, WIN-MA-001, WIN-MA-002, WIN-SYS-014,
  WIN-IM-001, WIN-IM-003, WIN-IM-004, WIN-BA-002, WIN-FND-004, WIN-FND-006, WIN-FND-007
  all landed a pin but do **not** advance `M` — existing upstream (non-Material-guarded)
  source never satisfies it. `M` advanced `·`→`△` only where a genuine Material
  source or definition.xml-grounded composition contract landed (FND-003, DLG-002/004/005,
  NAV-004, WR-001/002/003/005, CA-003 reinforced, CON-003 reinforced, DR-002, BA-001,
  FBK-007, CH-001 also flips `D`→`✓`, CONCEPT-002).
- **Three rows parked (recorded in the inventory with honest reasons)**: WIN-SEL-003
  (design-detail-only, switch has zero native footprint — D already ticked),
  WIN-SEL-004 (none-feasible build-free — filter chips have no native/`.ui`/app source
  to pin), WIN-SHL-001 (none-feasible build-free — every real shell-chrome surface is
  already pinned by a sibling row or has no source to guard).
- **Static gate recomputed to 147, method stated (verify yourself, not inherited)**:
  the full build-free gate = every Material `bin/check-*.py` except the six stock
  upstream linters (`check-autocorr`, `check-icon-sizes`, `check-implementer-notes`,
  `check-missing-export-asserts`, `check-missing-unittests`, `check-sid-slots`) =
  **72**, plus `bin/check_search_field_coverage.py` = **1**, plus every
  `bin/test_*.py` = **73**, plus `bin/validate-prototype.mjs` = **1** → **147**
  scripts, all green here (`py`/`node` from repo root, 0 failures). That is the
  default-activation tip's **81** plus exactly the 33 new checkers + 33 new suites =
  66. `.github/workflows/windows-ui-contract.yml` gained the 66 matching steps under
  a "Mega wave" comment (YAML valid, 143 steps, all referenced scripts verified
  present, triggers/job/runner unchanged), and `qa/windows-ui-contract/README.md`
  gained a "Wave-2 Mega wave" section (one subsection per triad + a runner block +
  the owner-attribution rubric + the `min_producer_modules` note).
- **CRLF watch (sixth incident)**: the Edit tool flipped the whole
  `windows-ui-contract.yml` to CRLF; caught with a byte-level Python scan and
  normalized back to LF before proceeding. All five integrator files verified 0 CR
  bytes. Git Bash `grep $'\r'` gives false positives on this host — use
  `open(f,'rb').read().count(b'\r')`.

## Resume guidance

1. DONE as of `2cd1c5cf3`/`ce7276f8e`: the five required native targets
   compile and their registered CppUnit coverage (notification view
   model, store service, regex foundation) runs green on both hosted CI
   legs. Still open: the headless harness matrix (no-nag proof, UI
   screenshots) needs an actual running build host — CI does not produce
   that evidence — before claiming any `B`/`V` gate.
2. DONE: Wave-2 Batch B is merged to `main` (`c8c8eb7e3`) with all four CI
   workflows confirmed green and release `windows-msi-82-1-c8c8eb7e33`
   published. Wave-2 Batch C is now LANDED IN SOURCE (12 fail-closed triads + 4
   `ConfirmDestructiveAction` conversions + the WIN-SYS-016 ui-registry
   reassignment + the D-detail design chapters + the README/workflow/inventory
   registration), all 79 build-free validators green locally — but it is NOT yet
   committed/pushed and NOT yet CI-confirmed. The next step is one merged push
   and watching all four CI workflows (expect the Windows leg to be the first
   real compile of the four C++ conversions; if any fails, iterate the compile
   before new feature work). After Batch C: the 15 honest-gap search-field
   contract extensions (each gap analysis names its exact blocker), then wave-3
   source-side slices (their `B V I A L P C` gates remain build-host-bound).
   The **2026-07-23 mega wave** (43 rows, 33 new triads, +66 gate scripts →
   **147**) is now LANDED IN SOURCE on top of the default-activation tip and all
   147 build-free validators are green locally, but it is NOT yet committed/pushed
   and NOT yet CI-confirmed. Next step: one merged push and watch all four CI
   workflows — the Windows leg is the first real compile of the mega-wave
   guarded/converted C++ (`notebookbar.cxx`, `viewobjectcontactofsdrpage.cxx`,
   `sdrpaintwindow.cxx`, the four dbaccess rail surfaces, the five NotifyInfo
   conversions, the two destructive conversions, and the `certificatechooser.cxx`
   predicate split); if any fails, iterate the compile before new work. Remaining
   after that: build-host-bound `B V I A L P C` evidence for every row; the three
   parked rows (WIN-SEL-003/WIN-SEL-004/WIN-SHL-001, each needing a design decision
   plus a build host); and per-surface refinement of the 250-entry `ui-registry`
   unassigned baseline.
3. Producer migration: extend the notification-producer registry in bounded,
   registered informational-only tranches (never input/destructive/
   credential/security prompts).
4. Build-host-bound evidence: every Batch A and Batch B row still needs its
   `B V I A L P C` gates proved on a real Windows build host —
   source-implemented and CI-green are not build/runtime/pixel proof.

## Repository state

- `main` contains all work described here; the task branch
  `claude/handoff-ultracode-onlyfans-opus-da0bf6` is merged and deleted after
  remote ancestor proof.
- The retained `codex/*` branches from the 2026-07-20 handoff were verified as
  ancestors of the pushed `origin/main` and deleted (branch cleanup section of
  this session).
