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
| 2026-07-16 | Detached build worktree | Clean at `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`; validator and seven unittest methods pass; no configure output, build directory, `instdir`, or initialized optional source submodules | Source is prepared, not built |
| 2026-07-16 | Windows build profile | WSL has no distro; selectable VS 2022 lacks ATL/configured CMake; selected SDK 28000 lacks required files; other helpers remain incomplete | No supported build command was run |
| 2026-07-16 | Low-level driver | Clean commit `806d9ba85e4afbc2af58d7499496babfa7c68891`, MCP on `127.0.0.1:8765`; no LibreOffice scenario; launch/PID/teardown limitations recorded | Driver readiness only; no UI evidence |

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
