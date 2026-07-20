# Evidence storage

This directory contains reviewed, run-scoped LibreOffice Material evidence.
Three canonical accepted 2026-07-20 exact-source Windows runs
contribute nine verified Start Center screenshots and matching bounded
accessibility trees: three light, three dark, and three forced high contrast.
Each appearance includes a visible one-step Tab focus state.
Their manifests keep the remaining matrix and MSI lifecycle boundary explicit.
The earlier light software-raster runs and superseded dark run remain accepted
historical proof rather than canonical gallery sources.

The successful 2026-07-16 Notepad-only driver preflight produced no retained
artifact here. It verified harness mechanics, not LibreOffice rendering, and is
recorded only as a non-accepted observation in the evidence plan and repository
memory.

The canonical accepted runs are the newest-source
[`light`](runs/20260720-143309-393263ad92-windows-headless-light/),
[`dark`](runs/20260720-140327-7029dccf40-windows-headless-dark/), and
[`forced-high-contrast`](runs/20260720-033338-fbba560e27-windows-headless-highcontrast/)
registrations.
The light run is the first exact-source runtime proof after removal of the
footer Donate control; dark and forced high contrast remain accepted historical
appearance evidence until they are refreshed from that source.
The earlier corrected light run is retained as historical proof at
[`20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression`](runs/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/),
as is the older-payload run at
[`20260720-012853-577059e274-vs2026-msi-raster`](runs/20260720-012853-577059e274-vs2026-msi-raster/).
The preceding default-GPU run is also retained as a rejected capture because
`PrintWindow` returned a blank client even though the accessibility tree was
nonempty; see
[`20260720-012601-577059e274-vs2026-msi`](runs/20260720-012601-577059e274-vs2026-msi/).

The corrected runs prove only their extracted runtime's scoped Start Center UI
and bounded UNO accessibility smoke. They do not run MSI install, repair,
upgrade, uninstall, or restart-suppression lifecycle scenarios.

Before adding artifacts, follow [`../HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md).
A real run belongs under `runs/<run-id>/` with a manifest and results. Do not
create empty run directories or placeholder images: absence is represented by
the truthful registry in [`../SCREENSHOTS.md`](../SCREENSHOTS.md).
