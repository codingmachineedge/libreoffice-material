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
- **Static gate**: all **45** build-free validators pass at this tip (29 from
  the wave-1 tip + 16 wave-2 Batch A: 8 checker/mutation-suite pairs). Run them
  with `py`/`node` from the repo root; the list is in `bin/` (`check-*` +
  `test_*` pairs plus `validate-prototype.mjs`).

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
- **Wave-2 Batch B is an UNVALIDATED WIP snapshot** on
  `origin/claude/wave2-batch-b` (`7785d5282`), stopped mid-implementation on
  operator request. It contains partial work for nine rows (WIN-NAV-002,
  WIN-CON-007, WIN-WR-004, WIN-FBK-005, WIN-FBK-008, WIN-CA-001, WIN-CA-002,
  WIN-IM-002, WIN-CONCEPT-003) plus five new checker/registry pairs. The accidental debris (`design/**` archive extraction, stray `e*.txt`)
  has already been stripped at this tip, and main's weld include fixes are
  merged in. Before ANY merge: complete the nine rows and run the full
  build-free gate to green. Do not delete this branch until its work is merged or
  consciously superseded.
- **Wave-2 Batch C (staged, not started)**: WIN-SYS-001, -002, -003, -004,
  -005, -006, -007, -009, -010, -011, -015 (system dialog flows),
  WIN-CONCEPT-001 (Features catalog), plus the 15 honest-gap search fields
  if their contract extensions are attempted. Wave 3 (31 rows) is
  build-host-bound per the audit.
- **Recurring defect to watch**: agent editors twice flipped whole files to
  CRLF (`menu.cxx`, `svdata.hxx`, `sw/qa/unit/swmodeltestbase.cxx`); a
  wholesale line-ending flip in a diff is a defect, not a change. A third
  instance hit `solenv/sanitizers/ui/sfx.suppr` while fixing the a11y gate
  below and was caught and reverted to LF before commit — check `git diff
  --stat` for suspiciously large line counts on small edits.

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

## Resume guidance

1. DONE as of `2cd1c5cf3`/`ce7276f8e`: the five required native targets
   compile and their registered CppUnit coverage (notification view
   model, store service, regex foundation) runs green on both hosted CI
   legs. Still open: the headless harness matrix (no-nag proof, UI
   screenshots) needs an actual running build host — CI does not produce
   that evidence — before claiming any `B`/`V` gate.
2. Finish wave-2 Batch B from the WIP branch (strip debris, complete, gate,
   merge), then Batch C, each row with its fail-closed contract per the
   established checker + mutation-suite pattern.
3. Producer migration: extend the notification-producer registry in bounded,
   registered informational-only tranches (never input/destructive/
   credential/security prompts).

## Repository state

- `main` contains all work described here; the task branch
  `claude/handoff-ultracode-onlyfans-opus-da0bf6` is merged and deleted after
  remote ancestor proof.
- The retained `codex/*` branches from the 2026-07-20 handoff were verified as
  ancestors of the pushed `origin/main` and deleted (branch cleanup section of
  this session).
