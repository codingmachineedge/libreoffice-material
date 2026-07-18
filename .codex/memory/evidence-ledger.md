# Evidence ledger

Accepted LibreOffice Material build/UI evidence entries: **0**.

No native build, headless interaction run, or screenshot has been accepted yet.
Planned scenarios and empty gallery slots are not evidence.

## Accepted runs

| Run ID | Fork commit | Platform | Build | Interaction | Visual | Manifest |
| --- | --- | --- | --- | --- | --- | --- |
| _None_ | — | — | — | — | — | — |

## Non-accepted harness observations

| Date | Driver commit | Subject | Result | Retention | Why excluded |
| --- | --- | --- | --- | --- | --- |
| 2026-07-16 | `806d9ba85e4afbc2af58d7499496babfa7c68891` | Off-screen Notepad on `WinSta0\LibreOfficeMaterialQA` | Create, enumerate, `PrintWindow`, scoped process cleanup, and desktop teardown passed | Capture temporary; not retained | No LibreOffice binary, Material source build, or project UI involved |

The discarded preflight image reported `rendered_ok: true`, dimensions
`1920×1125`, window HWND `37291736`, and SHA-256
`03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3`.
Its hash is retained only to identify the temporary observation; it is not a
link, gallery artifact, or accepted visual result.

## Non-run environment audits

| Date | Scope | Result | Evidence effect |
| --- | --- | --- | --- |
| 2026-07-16 | Fork binary search | No installed, worktree, AppX, WSL, or running `soffice`/LibreOffice binary found | Runtime gate remains closed |
| 2026-07-16 | Detached build worktree | Clean at `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731`; validator and 22 unittest methods pass with 23 color tokens, 8 shape tokens, 15 metric tokens, and 72 style slots; no configure output, build directory, `instdir`, or initialized optional source submodules | Source is prepared, not built |
| 2026-07-16 | Windows build profile | WSL has no distro; selectable VS 2022 lacks ATL/configured CMake; selected SDK 28000 lacks required files; other helpers remain incomplete | No supported build command was run |
| 2026-07-16 | Low-level driver | Clean commit `806d9ba85e4afbc2af58d7499496babfa7c68891`, MCP on `127.0.0.1:8765`; no LibreOffice scenario; launch/PID/teardown limitations recorded | Driver readiness only; no UI evidence |
| 2026-07-16 | Sixth-milestone source audit | Validator reports 8 exact shape roles across 146 rounded and 11 implicit-square rectangles; 16 Python tests and static source checks pass; the C++ reader/tests remain uncompiled | Source consistency only; no renderer or UI evidence |
| 2026-07-16 | Seventh-milestone source audit | Published source `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731` defines 15 native integer roles for 331 existing uses; exact metric/coordinate hashes, 22 validator tests, 38 reader fixtures, Actions run `29527917064`, and Pages run `29527917148` pass | Source consistency only; no compiled, runtime, interaction, or visual evidence |
| 2026-07-16 | Eighth-milestone source audit | Published source `291d134ceea2dd6fa354e2d319b043ffe42aa396` defines full-track progress and four-band level indicators; exact `2/23/3/8/15/72/77/199` validation, 24 Python tests, and 340-row metric closure pass; Actions `29530112458`, Pages `29530112004`, and direct HTTP checks pass; C++ pixel tests are source-only | Source consistency and publication only; no compiled, runtime, interaction, or visual evidence |
| 2026-07-18 | Ninth-milestone source audit | Defines the outlined `Frame`/`Border` container (with a 2px native content-region inset satisfying D-017, see D-018) and the net-less `ListNet`/`Entire` state (D-019); exact `2/23/3/8/15/72/79/201` validation, 26 Python tests, 341-row metric closure (geometry hash `f70697ac…bc714082`; unchanged 676-coordinate hash `0979f2b3…331ed2e`), a new native container source guard, and Start Center UI lint pass on portable CPython 3.12.7; C++ renderer/reader changes are source-only | Source consistency only; no compiled, runtime, interaction, or visual evidence — Actions/Pages verification follows the push |
| 2026-07-18 | Tenth-milestone source audit | A 14-agent coverage audit confirms inventory completeness; adds three disabled-affordance corrections (dimmed `SubmenuArrow`, disabled+checked `toolbar`/`Button`, disabled+selected `tabitem` `Entire`/`MenuItem`) and defers three design-decision gaps (D-020). Exact `2/23/3/8/15/72/79/205` validation, 27 Python tests, 346-row metric closure (geometry hash `dc16a577…65c60515`, coordinate hash `8345cd28…a13c402e8`, 45 patterns), and UI lint pass on portable CPython 3.12.7; XML-only change | Source consistency only; no compiled, runtime, interaction, or visual evidence — Actions/Pages verification follows the push |

These audits are reproducibility facts, not accepted build, interaction, or
visual runs. The verified LibreOffice Material screenshot count remains zero.

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
