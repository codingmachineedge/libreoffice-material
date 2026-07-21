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
- **Static gate**: all **29** build-free validators pass at this tip (21
  pre-existing + 8 added this session). Run them with `py`/`node` from the
  repo root; the list is in `bin/` (`check-*` + `test_*` pairs plus
  `validate-prototype.mjs`).

## Important boundaries

- **No build or runtime evidence exists for any of the above.** The `B V I A
  L P C` inventory gates are untouched. The next build host (or the hosted
  `windows-installer.yml` CI on a `main` push) must compile the five required
  native targets, run the registered CppUnit coverage (notification view
  model, store service, regex foundation), and produce fresh headless
  evidence before any runtime claim.
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
  messages; wave-2 starts with the dependency-free rows (menubar, sidebar
  rail, status bar, Start Center cards, Calc chrome).
- Operator-instruction note: the user-level requirement for
  English/Cantonese/bilingual language modes has not been implemented for this
  fork; LibreOffice's own localization pipeline (including zh-* locales) is
  the existing mechanism, and reconciling that requirement with upstream l10n
  norms is an open operator decision recorded here rather than silently
  dropped.

## Resume guidance

1. On a build host: run the local bootstrap/build per
   `docs/LOCAL_WINDOWS_BUILD.md`, then the five required native targets plus
   the newly registered CppUnit coverage, then the headless harness matrix
   (light/dark/high-contrast) against the exact `version.ini` SHA before
   claiming any `B`/`V` gate.
2. Wave 2 of the full-UI rewrite: implement the dependency-free wave-2 rows
   first, each with its own fail-closed contract following the established
   checker + mutation-suite pattern.
3. Producer migration: build the producer registry + checker described above,
   then migrate informational-only prompts in bounded, registered tranches.

## Repository state

- `main` contains all work described here; the task branch
  `claude/handoff-ultracode-onlyfans-opus-da0bf6` is merged and deleted after
  remote ancestor proof.
- The retained `codex/*` branches from the 2026-07-20 handoff were verified as
  ancestors of the pushed `origin/main` and deleted (branch cleanup section of
  this session).
