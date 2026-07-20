# Evidence storage

This directory contains reviewed, run-scoped LibreOffice Material evidence.
The canonical accepted 2026-07-20 corrected exact-source Windows run contributes
two verified light-profile Start Center screenshots and matching bounded
accessibility trees. Its manifest keeps the remaining matrix and MSI lifecycle
boundary explicit. The earlier `577059e274` software-raster run remains accepted
historical proof rather than the canonical gallery source.

The successful 2026-07-16 Notepad-only driver preflight produced no retained
artifact here. It verified harness mechanics, not LibreOffice rendering, and is
recorded only as a non-accepted observation in the evidence plan and repository
memory.

The canonical accepted run is
[`20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression`](runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/).
The earlier accepted run is retained as historical proof at
[`20260720-012853-577059e274-vs2026-msi-raster`](runs/20260720-012853-577059e274-vs2026-msi-raster/).
The preceding default-GPU run is also retained as a rejected capture because
`PrintWindow` returned a blank client even though the accessibility tree was
nonempty; see
[`20260720-012601-577059e274-vs2026-msi`](runs/20260720-012601-577059e274-vs2026-msi/).

The corrected run proves only its extracted runtime's Start Center UI and
bounded UNO accessibility smoke. It does not run MSI install, repair, upgrade,
uninstall, or restart-suppression lifecycle scenarios.

Before adding artifacts, follow [`../HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md).
A real run belongs under `runs/<run-id>/` with a manifest and results. Do not
create empty run directories or placeholder images: absence is represented by
the truthful registry in [`../SCREENSHOTS.md`](../SCREENSHOTS.md).
