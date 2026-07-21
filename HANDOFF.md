# Windows-only handoff — 2026-07-20

This handoff is the pushed `main` tip `2498c3893` (the source/build SHA immediately
before this documentation-only commit is
`f8f7d8f6e5c3b638ae710652afcf6681f409225f`).

## What is complete at this tip

- The repository is clean on `main` and the handoff tip is pushed to
  `origin/main` (`https://github.com/Ding-Ding-Projects/libreoffice-material.git`).
- A local VS 2026 build completed with the retained build root
  `C:\Users\cntow\lo-material-vs2026-577059e27`.
- The built payload (for the pre-handoff source SHA above) is at
  `C:\Users\cntow\lo-material-vs2026-577059e27\build\instdir`; its
  `program/version.ini` build ID is the exact handoff SHA above.
- Native notification-store and regex tests, the notification/regex/no-donate/
  dialog-placement contracts, the release-workflow validator, and the
  no-nag harness static/regression suite passed during this work.
- The accepted configured Start Center smoke run at source SHA
  `9d2219bad8249bbdb25fce9b1edae5c81228c8cb` produced a nonblank 1920×1117
  PrintWindow screenshot and a complete accessibility tree (92 nodes, 45
  visible, 0 errors). Retained evidence:
  `C:\Users\cntow\lo-material-vs2026-577059e27\headless-evidence-final\20260720-205155-9d2219bad8-windows-headless-light`.
- The headless harness now starts the checked-out low-level MCP executable
  directly, tolerates whole-second Windows process timestamps, accepts empty
  no-nag text collections, filters normal non-SALFRAME helper/IME windows from
  the user-facing no-nag inventory, and tolerates the URP bridge disposal race
  after a successful accessibility-triggered office termination.

## Important boundaries

- The current native source is not yet a complete rewrite of every page in the
  supplied Libre Office design ZIP. The notification backend/facade and the
  first Calc regex integration are present, but the full native notification
  manager, all notification producer routing, and the remaining search-field
  regex builders still need implementation and visual verification.
- The MSI package phase and final current-SHA public release verification have
  not been run for `f8f7d8f6e5c3b638ae710652afcf6681f409225f`.
- The most recent Fresh no-nag run reached a stable single Writer `SALFRAME`,
  but its final UNO accessibility call exposed a bridge-disposal race. The
  termination handling fix is in this handoff SHA and must be re-run against
  this exact payload before claiming accepted Fresh/Legacy no-nag evidence.
- The stale host reboot marker
  `*1\\??\\C:\Windows\System32\gamingservicesproxy_11.dll.0` could not be
  deleted because this shell is non-administrator. `Build-Windows.ps1` ignores
  only that exact known stale marker and still fails on any unknown pending
  reboot state; no registry value was falsely claimed to be removed.

## Resume commands

Run from the repository root with the retained VS 2026 build root:

```powershell
powershell -ExecutionPolicy Bypass -File .\bin\Build-Windows.ps1 -Phase Package -Jobs 2 `
  -BuildRoot 'C:\Users\cntow\lo-material-vs2026-577059e27' `
  -VisualStudioYear 2026 `
  -VisualStudioInstallPath 'C:\Program Files\Microsoft Visual Studio\18\Enterprise' `
  -NoBootstrap -Resume
```

Then re-run the configured and `Fresh`/`Legacy` low-level headless harnesses
against the exact `program/version.ini` SHA, inspect the PNG with the visual
review tool, validate each manifest with
`bin/Validate-Windows-Headless-Evidence.ps1 -RequirePassed`, update
`README.md`, `ROADMAP.md`, and the docs evidence page, and push before release
work.

## Retained branches/worktrees

The completed source branches remain available for audit and must not be
deleted until the next continuation has verified their tips are ancestors of
the pushed default branch and performed the repository-mandated cleanup:

- `codex/notification-service`
- `codex/regex-calc-goto`
- `codex/headless-nonag-harness`

Their work was merged into `main`; the linked worktree directories are retained
for this handoff and should be removed only after remote proof and a clean
default checkout.
