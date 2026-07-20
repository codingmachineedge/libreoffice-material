# Verified screenshot index

**Current canonical gallery screenshot count: 2.**

Both canonical files come from the corrected exact-source Windows x64 MSI
payload at `fbba560e27db26de605c40aa237c554c1f0744b1` and its light-profile
Start Center run. They establish a real launch and one background navigation
smoke action; they do not complete the light/dark minimum or any whole-suite
acceptance gate. The two images from the earlier accepted `577059e274` run remain
retained as historical proof, but are not duplicated in the canonical gallery.

A 2026-07-16 off-screen Notepad capture was used only to preflight the local
low-level desktop driver. It was temporary, was not committed, and cannot enter
this registry because it does not show LibreOffice. It remains excluded from
the current count.

## Evidence slots

| Slot | Surface | Minimum checkpoint | Current state | Verified file |
| --- | --- | --- | --- | --- |
| E-START-001 | Start center and shared shell | stable launch, light and dark | In progress — corrected light run accepted; dark pending | [`Home / Recent Documents`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/screenshots/start-center-light.png) · [`Templates`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/screenshots/start-center-templates-light.png) · run [`manifest`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/manifest.json) / [`results`](evidence/runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/results.json) |
| E-WRITER-001 | Writer | document open, formatting and sidebar visible | Awaiting genuine capture | — |
| E-CALC-001 | Calc | populated sheet, formula bar and sheet tabs visible | Awaiting genuine capture | — |
| E-IMPRESS-001 | Impress | editing canvas, slide pane and properties visible | Awaiting genuine capture | — |
| E-DIALOG-001 | Shared dialog | keyboard focus, validation, and long labels | Awaiting genuine capture | — |
| E-A11Y-001 | Accessibility modes | high contrast, 200% scale, visible focus | Awaiting genuine capture | — |

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
byte-identical to the corrected run's Home image; its Templates image has its
own recorded hash. It is historical rather than canonical because the older MSI
omitted the fifth updater launch argument. Neither run proves MSI install,
repair, upgrade, uninstall, or restart-suppression lifecycle behavior.
