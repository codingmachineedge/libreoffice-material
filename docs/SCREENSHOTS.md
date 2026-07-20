# Verified screenshot index

**Current canonical gallery screenshot count: 9.**

The canonical light, dark, and forced-high-contrast trios come from the newest
exact-source Windows x64 MSI payload at
`393263ad924eae8d64b4f9a35bd6486ef83578fc` and verify the
Help/Extensions-only footer. Together they
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
| E-START-001 | Start center and shared shell | stable launch, light and dark | Passed for scoped exact-source Home/focus/Templates software-raster smoke in all three appearance profiles; broader shell work remains | Light [`Home`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/screenshots/start-center-light.png) / [`keyboard focus`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/screenshots/start-center-light-keyboard-focus.png) / [`Templates`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/screenshots/start-center-templates-light.png) · dark [`Home`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/screenshots/start-center-dark.png) / [`keyboard focus`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/screenshots/start-center-dark-keyboard-focus.png) / [`Templates`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/screenshots/start-center-templates-dark.png) · light run [`manifest`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/manifest.json) / [`results`](evidence/runs/20260720-143309-393263ad92-windows-headless-light/results.json) · dark run [`manifest`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/manifest.json) / [`results`](evidence/runs/20260720-144200-393263ad92-windows-headless-dark/results.json) |
| E-NONAG-FRESH | Blank Writer, genuinely fresh profile | no suppression flags; one owned Writer window for at least 15 seconds; former-nag titles/a11y absent | Dedicated source harness and mutation contract pass; exact-build run and review pending | — |
| E-NONAG-LEGACY | Blank Writer, seeded legacy profile | all former first-run/promotion/association/AutoCorrect/crash triggers enabled safely; one owned Writer window; former-nag titles/a11y absent | Dedicated source harness and mutation contract pass; exact-build run and review pending | — |
| E-WRITER-001 | Writer | document open, formatting and sidebar visible | Awaiting genuine capture | — |
| E-CALC-001 | Calc | populated sheet, formula bar and sheet tabs visible | Awaiting genuine capture | — |
| E-IMPRESS-001 | Impress | editing canvas, slide pane and properties visible | Awaiting genuine capture | — |
| E-DIALOG-001 | Shared dialog | keyboard focus, validation, and long labels | Awaiting genuine capture | — |
| E-A11Y-001 | Accessibility modes | high contrast, 200% scale, visible focus | In progress — exact-source forced high contrast and visible Tab focus accepted; 200% scale pending | [`Home`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/screenshots/start-center-highcontrast.png) · [`keyboard focus`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/screenshots/start-center-highcontrast-keyboard-focus.png) · [`Templates`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/screenshots/start-center-templates-highcontrast.png) · run [`manifest`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/manifest.json) / [`results`](evidence/runs/20260720-144249-393263ad92-windows-headless-highcontrast/results.json) |

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
