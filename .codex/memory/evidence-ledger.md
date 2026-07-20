# Evidence ledger

Accepted LibreOffice Material build/UI evidence entries: **1 run / 2 screenshots**.

The accepted entry is deliberately narrow: exact-source local MSI build and
administrative extraction, light Start Center launch/navigation on software
raster rendering, and paired bounded UNO-tree collection. Planned scenarios and
empty gallery slots are not evidence.
The public assetless release/tag `e` contains no build and does not change this
ledger.

## Accepted runs

| Run ID | Fork commit | Platform | Build | Interaction | Visual | Manifest |
| --- | --- | --- | --- | --- | --- | --- |
| `20260720-012853-577059e274-vs2026-msi-raster` | `577059e2741185b512c184c64685c16d335d10ea` | Windows 11 Pro x64; VS 2026; 150% scale | Five native targets and CLI payload passed; unsigned 199,692,288-byte MSI SHA `437b059c…54a43`; administrative extraction exit `0`; wrapper final dist stage incomplete | Stable owned Start Center, background navigation to Templates, two bounded UNO trees with no collector errors, normal shutdown and desktop cleanup | 2 accepted light-profile `1920×1117` PNGs; dark and broader matrix pending | [`manifest`](../../docs/evidence/runs/20260720-012853-577059e274-vs2026-msi-raster/manifest.json) · [`results`](../../docs/evidence/runs/20260720-012853-577059e274-vs2026-msi-raster/results.json) |

## Non-accepted harness observations

| Date | Driver commit | Subject | Result | Retention | Why excluded |
| --- | --- | --- | --- | --- | --- |
| 2026-07-16 | `806d9ba85e4afbc2af58d7499496babfa7c68891` | Off-screen Notepad on `WinSta0\LibreOfficeMaterialQA` | Create, enumerate, `PrintWindow`, scoped process cleanup, and desktop teardown passed | Capture temporary; not retained | No LibreOffice binary, Material source build, or project UI involved |
| 2026-07-20 | `beed66ca6ed2503e6170ee1e1158247f1c2f0140` | Exact MSI payload, default-GPU Start Center | Stable owned window and 96-node bounded UNO tree; `PrintWindow` client was blank | Failure capture and run metadata retained under [`20260720-012601-577059e274-vs2026-msi`](../../docs/evidence/runs/20260720-012601-577059e274-vs2026-msi/) | Blank capture is not gallery evidence; software-raster retry accepted separately |

The discarded preflight image reported `rendered_ok: true`, dimensions
`1920×1125`, window HWND `37291736`, and SHA-256
`03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3`.
Its hash is retained only to identify the temporary observation; it is not a
link, gallery artifact, or accepted visual result.

## Non-accepted build attempts

| Date | Source / run | Result | Evidence effect |
| --- | --- | --- | --- |
| 2026-07-18 | `d6f66b686551b0d03cc3317fb18a80e74879cce1` / Actions `29662095462` | Configure stopped because Perl `Archive::Zip` was missing; build, required native regression targets, packaging, and artifact staging did not run | No binary, installer, test result, interaction result, or visual evidence; workflow repair and rerun remain pending |
| 2026-07-18 | `542e4077b61507e634af8ee0f8925b1de47a6db2` / Actions `29665678719` | Dependency installation passed, then prerequisite validation stopped at missing `nasm`; configure, tests, build, packaging, and staging did not run | No binary, installer, test result, interaction result, or visual evidence; Linux dependency list corrected and a genuine Windows MSI workflow added for a new run |

Release/tag `e` points at the same commit but has no assets. It is a non-build
remote marker, not a successful release or accepted artifact.

## Non-run environment audits

| Date | Scope | Result | Evidence effect |
| --- | --- | --- | --- |
| 2026-07-16 | Fork binary search | No installed, worktree, AppX, WSL, or running `soffice`/LibreOffice binary found | Runtime gate remains closed |
| 2026-07-16 | Detached build worktree | Clean at `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731`; validator and 22 unittest methods pass with 23 color tokens, 8 shape tokens, 15 metric tokens, and 72 style slots; no configure output, build directory, `instdir`, or initialized optional source submodules | Source is prepared, not built |
| 2026-07-18 | Windows build profile refresh | Local VS Build Tools 2022 has MSVC and CMake but lacks ATL and CRT merge modules; SDK 26100 is complete; no Cygwin or supported WSL helper is installed; checkout is CRLF | No supported local build command was run; the new hosted workflow uses a clean LF checkout and validates every missing component before configure |
| 2026-07-19 | One-click local Windows source automation | `Build-Windows.cmd`/`bin/Build-Windows.ps1` parsed successfully; default bootstrap is isolated VS 2022/Cygwin, one hidden UAC child, isolated Cygwin Git, safe short roots, per-invocation logs, LF snapshot, native target sequence, and final-MSI extraction. Read-only preflight on clean `6e489f62a` correctly found missing dedicated VS 2022/Cygwin and left default tool/build roots absent; no bootstrap was run | Source automation and prerequisite evidence only; no native build, installer, runtime interaction, or visual evidence |
| 2026-07-16 | Low-level driver | Clean commit `806d9ba85e4afbc2af58d7499496babfa7c68891`, MCP on `127.0.0.1:8765`; no LibreOffice scenario; launch/PID/teardown limitations recorded | Driver readiness only; no UI evidence |
| 2026-07-16 | Sixth-milestone source audit | Validator reports 8 exact shape roles across 146 rounded and 11 implicit-square rectangles; 16 Python tests and static source checks pass; the C++ reader/tests remain uncompiled | Source consistency only; no renderer or UI evidence |
| 2026-07-16 | Seventh-milestone source audit | Published source `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731` defines 15 native integer roles for 331 existing uses; exact metric/coordinate hashes, 22 validator tests, 38 reader fixtures, Actions run `29527917064`, and Pages run `29527917148` pass | Source consistency only; no compiled, runtime, interaction, or visual evidence |
| 2026-07-16 | Eighth-milestone source audit | Published source `291d134ceea2dd6fa354e2d319b043ffe42aa396` defines full-track progress and four-band level indicators; exact `2/23/3/8/15/72/77/199` validation, 24 Python tests, and 340-row metric closure pass; Actions `29530112458`, Pages `29530112004`, and direct HTTP checks pass; C++ pixel tests are source-only | Source consistency and publication only; no compiled, runtime, interaction, or visual evidence |
| 2026-07-18 | Ninth-milestone source audit | Published source `1e2dca2f76c5f7481451ad0f419a7053222e55df` defines the outlined `Frame`/`Border` container (with a 2px native content-region inset satisfying D-017, see D-018) and the net-less `ListNet`/`Entire` state (D-019); exact `2/23/3/8/15/72/79/201` validation, 26 Python tests, 341-row metric closure (geometry hash `f70697ac…bc714082`; unchanged 676-coordinate hash `0979f2b3…331ed2e`), source-validation run `29648977365`, and Pages run `29648977400` pass; C++ renderer/reader changes are source-only | Source consistency and publication only; no compiled, runtime, interaction, or visual evidence |
| 2026-07-18 | Tenth-milestone source audit | Published source `18714cc1c7421225dd66b925e6295e13b56a7a7a` closes three disabled-affordance gaps and defers three design-decision gaps (D-020); exact `2/23/3/8/15/72/79/205` validation, 27 Python tests, 346-row metric closure (geometry hash `dc16a577…65c60515`, coordinate hash `8345cd28…a13c402e8`, 45 patterns), source-validation run `29650136950`, and Pages run `29650136963` pass; XML-only change | Source consistency and publication only; no compiled, runtime, interaction, or visual evidence |

These historical audits remain reproducibility facts rather than visual runs.
Current accepted screenshot status is maintained in
[`docs/SCREENSHOTS.md`](../../docs/SCREENSHOTS.md).

## Entry requirements

An entry may be added only when:

- source state, tool versions, platform, build configuration, and artifact are
  recorded;
- scenario results include failures as well as passes;
- every linked file exists and its SHA-256 matches the manifest;
- screenshots are genuine captures of the stated build and window;
- sensitive-data and blank/stale-image reviews pass;
- a reviewer and absolute review date are recorded.

Use `docs/HEADLESS_UI_EVIDENCE.md` for the full run contract and
`docs/SCREENSHOTS.md` for the public visual registry.
