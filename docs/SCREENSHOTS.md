# Verified screenshot index

**Current canonical gallery screenshot count: 9.**

The canonical light trio comes from the newest exact-source Windows x64 MSI
payload at `7029dccf40b4d9851e0ea9f9bb2c03ad5ae405b3`; the canonical dark and
forced-high-contrast trios remain accepted evidence for the earlier corrected
`fbba560e27db26de605c40aa237c554c1f0744b1` payload. Together they
establish real launch, background Templates navigation, and one keyboard Tab
focus transition in each appearance. They do not establish 200% scaling,
accelerated rendering, localization, suite applications, dialogs, updater UI,
or the MSI lifecycle. The two earlier accepted light runs remain historical
proof, but are not duplicated in the canonical gallery.

A 2026-07-16 off-screen Notepad capture was used only to preflight the local
low-level desktop driver. It was temporary, was not committed, and cannot enter
this registry because it does not show LibreOffice. It remains excluded from
the current count.

## Evidence slots

| Slot | Surface | Minimum checkpoint | Current state | Verified file |
| --- | --- | --- | --- | --- |
| E-START-001 | Start center and shared shell | stable launch, light and dark | Passed for scoped Home/focus/Templates software-raster smoke; broader shell work remains | Light [`Home`](evidence/runs/20260720-135505-7029dccf40-windows-headless-light/screenshots/start-center-light.png) / [`keyboard focus`](evidence/runs/20260720-135505-7029dccf40-windows-headless-light/screenshots/start-center-light-keyboard-focus.png) / [`Templates`](evidence/runs/20260720-135505-7029dccf40-windows-headless-light/screenshots/start-center-templates-light.png) · dark [`Home`](evidence/runs/20260720-033252-fbba560e27-windows-headless-dark/screenshots/start-center-dark.png) / [`keyboard focus`](evidence/runs/20260720-033252-fbba560e27-windows-headless-dark/screenshots/start-center-dark-keyboard-focus.png) / [`Templates`](evidence/runs/20260720-033252-fbba560e27-windows-headless-dark/screenshots/start-center-templates-dark.png) · light run [`manifest`](evidence/runs/20260720-135505-7029dccf40-windows-headless-light/manifest.json) / [`results`](evidence/runs/20260720-135505-7029dccf40-windows-headless-light/results.json) |
| E-WRITER-001 | Writer | document open, formatting and sidebar visible | Awaiting genuine capture | — |
| E-CALC-001 | Calc | populated sheet, formula bar and sheet tabs visible | Awaiting genuine capture | — |
| E-IMPRESS-001 | Impress | editing canvas, slide pane and properties visible | Awaiting genuine capture | — |
| E-DIALOG-001 | Shared dialog | keyboard focus, validation, and long labels | Awaiting genuine capture | — |
| E-A11Y-001 | Accessibility modes | high contrast, 200% scale, visible focus | In progress — forced high contrast and visible Tab focus accepted; 200% scale pending | [`Home`](evidence/runs/20260720-033338-fbba560e27-windows-headless-highcontrast/screenshots/start-center-highcontrast.png) · [`keyboard focus`](evidence/runs/20260720-033338-fbba560e27-windows-headless-highcontrast/screenshots/start-center-highcontrast-keyboard-focus.png) · [`Templates`](evidence/runs/20260720-033338-fbba560e27-windows-headless-highcontrast/screenshots/start-center-templates-highcontrast.png) · run [`manifest`](evidence/runs/20260720-033338-fbba560e27-windows-headless-highcontrast/manifest.json) / [`results`](evidence/runs/20260720-033338-fbba560e27-windows-headless-highcontrast/results.json) |

## Adding a verified image

1. Complete a run using [`HEADLESS_UI_EVIDENCE.md`](HEADLESS_UI_EVIDENCE.md).
2. Confirm the image, manifest, hashes, scenario result, and sensitive-data
   review all pass.
3. Commit the real image inside its evidence run directory.
4. Replace the dash in **Verified file** with a relative link to that existing
   file and add its run identifier.
5. Update the public site, roadmap, and repository memory in the same change.

Never pre-populate the index with a future path: a link appearing here is a
claim that the referenced artifact exists and has passed review.

## Historical accepted proof

The first accepted light-profile run,
[`20260720-012853-577059e274-vs2026-msi-raster`](evidence/runs/20260720-012853-577059e274-vs2026-msi-raster/),
remains immutable evidence for the older extracted payload. Its Home image is
byte-identical to the current canonical run's Home image; its Templates image
has its own recorded hash. Corrected light run
[`20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/)
also remains immutable historical evidence for the exact current payload. The
fresh committed-harness run supersedes both only as the canonical gallery source
because it adds a verified light keyboard-focus state and dedicated-driver
cleanup proof. None of these runs proves MSI install, repair, upgrade, uninstall,
or restart-suppression lifecycle behavior.
