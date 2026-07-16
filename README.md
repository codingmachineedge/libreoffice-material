# LibreOffice Material

An experimental LibreOffice engineering fork exploring a suite-wide Material
Design 3 interface while retaining LibreOffice's native implementation stack,
document engine, file-format support, and accessibility foundations.

> **Current development focus: Phase 1 — sixth Material VCL source milestone.**
> Phase 0's native-build and application-evidence gate remains open. Semantic
> widget tokens, stricter VCL definition parsing, broader state coverage, and
> Start Center changes are present in source, but they have **not** been compiled
> or run as LibreOffice. The whole GUI has not been rewritten, and no application
> surface is Material-complete.

[Project site](https://codingmachineedge.github.io/libreoffice-material/) ·
[Roadmap](ROADMAP.md) ·
[Material specification](MATERIAL_DESIGN.md) ·
[Headless UI evidence plan](docs/HEADLESS_UI_EVIDENCE.md) ·
[Screenshot index](docs/SCREENSHOTS.md)

## What is true today

| Area | State | Evidence |
| --- | --- | --- |
| LibreOffice source baseline | Imported | This repository's initial tree matches upstream commit `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21` |
| Material design direction | Initial specification | [`MATERIAL_DESIGN.md`](MATERIAL_DESIGN.md) |
| Material VCL implementation | Sixth source milestone, unbuilt | Light/dark profile routing, complete semantic `StyleSettings` color mapping, native-preserving type roles, eight semantic corner roles, strict source validation, high-contrast fallback, shared renderer fixes, and Start Center source changes are present; build and runtime gates remain open |
| Whole-suite implementation | Incomplete | Phased work remains in [`ROADMAP.md`](ROADMAP.md) |
| Verified UI screenshots | None yet | The truthful empty registry is in [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md) |
| Headless harness | Preflight passed; LibreOffice not run | A temporary Notepad-only driver preflight proved the off-screen mechanics, not this UI; see [`docs/HEADLESS_UI_EVIDENCE.md`](docs/HEADLESS_UI_EVIDENCE.md) |

This table is deliberately conservative. A roadmap item changes state only when
its code, build result, interaction checks, and committed visual evidence agree.

## Material VCL source milestones

The implementation is intentionally opt-in and shared-layer first. The current
source includes:

- a packaged `material/definition.xml` file-widget theme with matching light and
  dark palettes of 23 semantic color roles each, 74 definition-backed parts,
  and 190 component states;
- eight semantic corner roles resolved order-independently by the native XML
  reader into both existing rectangle radius axes; all 146 rounded Material
  rectangles use one named role while the 11 square rectangles remain
  attribute-free, and legacy numeric `rx`/`ry` definitions stay supported;
- an exact 72-slot Material style contract that closes the ten previously
  native-dependent accent, list-box collection, alternating-row, warning, and
  error colors; these newer reader fields remain optional so partial legacy and
  out-of-tree file themes preserve native values when a role is omitted;
- typed `body`, `label`, and `title` roles with bounded relative scaling and a
  strict minimum-weight vocabulary; each role copies the captured platform font,
  applies the declared nonshrinking height scale, and only raises weight to the
  declared minimum, so family, style, charset, language, pitch, orientation,
  width, and icon fonts remain native;
- order-independent color and shape `@token` resolution and strict rejection of
  malformed colors or shapes, invalid or duplicate token sections, mismatched
  palette schemas, unknown references, ambiguous radius declarations, and
  unknown or duplicate control parts;
- selection through `VCL_FILE_WIDGET_THEME`, with a restricted safe theme name,
  shared immutable definitions, and a mutex-protected cache keyed by theme and
  resolved light/dark scheme; a failed request attempts `online`, which is not
  packaged in this imported desktop tree, and otherwise leaves the file theme
  inactive;
- native settings collected and captured before the opt-in Material pass, with
  the resolved precedence high contrast over dark over light; high contrast
  restores the pre-Material style/framework baseline and delegates to native or
  generic forced-color drawing;
- runtime profile transitions recompute native-focus suppression for buttons,
  tabs, and list boxes so generic fallback retains a visible VCL focus
  indicator; Qt proxy styles preserve their high-contrast signal, and headless
  VCL honors an explicitly selected dark appearance;
- definition-aware support reporting so parts absent from the selected file
  theme stay on their existing fallback path;
- expanded mixed, disabled, hover, pressed, focus, selected, flat-button,
  toolbar, list-node, edit, scrollbar, slider, tab, menu, progress, and
  standalone vertical/horizontal spin-button coverage;
- shared renderer corrections for composite combo geometry and RTL placement,
  toolbar grips, standalone spin geometry and direction, native control regions,
  slider sizing, and raw graphics-state invalidation;
- a standalone source validator for exact color, shape, 72-slot style, and
  typography contracts, required parts and states, light/dark schema parity,
  unused tokens, native font-preservation invariants, and selected WCAG
  contrast pairs—including list selection and warning/error feedback—plus
  reader, XML-walker, and headless draw C++ coverage with negative XML fixtures;
- Start Center spacing, a Home header/subtitle, surface roles, and recent/template
  text and fill colors derived from VCL style settings.

The local static validator passes with 2 schemes, 23 semantic color tokens per
scheme, 3 semantic typography roles, 8 semantic shape tokens, 72 style slots,
74 parts, and 190 states.
This is source validation only: no affected C++ test target or `soffice` has
run, no application surface is verified Material-complete, and the screenshot
count remains 0. Controls whose current file-widget geometry cannot preserve
native semantics continue through LibreOffice's existing fallback.

Once a compatible LibreOffice build exists, the intended Windows opt-in is to
set both variables before launching the built application:

```powershell
$env:VCL_DRAW_WIDGETS_FROM_FILE = "1"
$env:VCL_FILE_WIDGET_THEME = "material"
```

These variables describe the source path; they are not a successful-run claim.
The `vcl_widget_definition_reader_test` and
`vcl_file_definition_widget_draw_test` targets and a real `soffice` launch have
not run on this worktree.

## Product direction

LibreOffice Material aims to modernize the complete desktop experience rather
than place a cosmetic skin over a few screenshots. The intended scope includes:

- shared application chrome, menus, command surfaces, sidebars, status bars,
  dialogs, pickers, notifications, and start center;
- Writer, Calc, Impress, Draw, Base, Math, and shared editing components;
- Material 3 color, type, shape, elevation, state, density, and motion tokens;
- keyboard-first operation, screen-reader semantics, high contrast, reduced
  motion, localization, bidirectional text, and platform conventions;
- responsive/adaptive behavior that respects information-dense desktop work.

The implementation remains native LibreOffice code. Product UI changes should
use the languages and resource formats already used by the affected upstream
module—primarily C++, VCL, UNO, and XML `.ui`/configuration resources. The
static HTML and CSS under [`site/`](site/) are only the project website; they
are not a replacement runtime for LibreOffice.

## Architecture at a glance

Materialization should flow from shared primitives into suite surfaces:

1. semantic tokens and platform-aware theme resolution;
2. VCL widgets, focus/state behavior, and rendering primitives;
3. shared framework chrome and reusable dialogs;
4. application-specific surfaces in Writer, Calc, Impress/Draw, Base, and Math;
5. accessibility, localization, performance, and headless visual verification.

The core upstream areas remain the natural integration points:

| Module | Relevance |
| --- | --- |
| [`vcl/`](vcl/) | Widget toolkit, rendering abstraction, platform backends, and theme behavior |
| [`framework/`](framework/) | Menus, toolbars, status bars, and application chrome |
| [`sfx2/`](sfx2/) | Shared document framework and shell behavior |
| [`svx/`](svx/) | Shared drawing and editing controls |
| [`cui/`](cui/) | Common dialogs and option surfaces |
| [`desktop/`](desktop/) | Application bootstrap and start-center integration |
| [`sw/`](sw/) | Writer |
| [`sc/`](sc/) | Calc |
| [`sd/`](sd/) | Impress and Draw |

See [`MATERIAL_DESIGN.md`](MATERIAL_DESIGN.md) for component rules and
[`ROADMAP.md`](ROADMAP.md) for sequencing and acceptance gates.

## Evidence, not mock completion

No screenshot is shown until it is captured from a build of this repository and
registered with its commit, environment, test scenario, and result. Empty cards
on the project site are **evidence slots**, not mockups or generated UI claims.

The verification driver is the sibling
[`lowlevel-computer-use-mcp`](https://github.com/codingmachineedge/lowlevel-computer-use-mcp)
project. It can launch real GUI applications on an off-screen desktop, target
windows without focusing them, and capture window images. A 2026-07-16 preflight
using driver commit `806d9ba85e4afbc2af58d7499496babfa7c68891`
successfully created and removed an off-screen Win32 desktop around Notepad.
That temporary capture was unrelated to LibreOffice, was not retained, and is
not registered as project evidence. The driver is not currently vendored into
this repository. Exact preflight facts, the future LibreOffice capture contract,
and safety rules are in [`docs/HEADLESS_UI_EVIDENCE.md`](docs/HEADLESS_UI_EVIDENCE.md).

## Building LibreOffice

This fork retains the upstream LibreOffice build chain. LibreOffice is a large,
cross-platform native project; consult The Document Foundation's current
[platform build instructions](https://wiki.documentfoundation.org/Development/How_to_build)
and the imported build files before configuring a machine.

> **Current build gate:** the detached LF worktree is clean, but no complete
> supported LibreOffice build profile exists. WSL 2.7.10 has no distribution;
> the selectable Visual Studio 2022 instance lacks ATL and its configured
> bundled CMake; and the Windows SDK registry selects incomplete SDK 28000
> instead of the usable 26100 desktop SDK. A complete OpenJDK 21 exists outside
> `PATH`, while Ant/JUnit and other required build helpers remain absent. No
> native C++ test or LibreOffice application run has occurred.

The imported checkout was also materialized mostly with CRLF worktree endings.
Use a fresh detached worktree created with `core.autocrlf=false` for any native
configure/build attempt rather than normalizing the development worktree.

At the imported baseline, the upstream README records these minimum build
baselines:

| Platform | Imported upstream build baseline |
| --- | --- |
| Windows | WSL helper plus Visual Studio 2022; runtime baseline Windows 10 |
| macOS | macOS 13 or later with Xcode 14.3 or later; runtime baseline macOS 11 |
| Linux | GCC 13 or Clang 18 with libstdc++ 11; RHEL/CentOS 9-class baseline |
| Java | JDK 17 or later |
| Python | Python 3.11 |

Typical source builds start with the upstream `autogen.sh`/`configure` flow and
then use `make`. Platform-specific dependencies and supported switches change,
so the TDF build documentation and [`distro-configs/`](distro-configs/) are the
authority. [LODE](https://wiki.documentfoundation.org/Development/lode) can help
prepare Windows and macOS development environments.

For extension development rather than core changes, use the
[LibreOffice SDK](https://api.libreoffice.org/) and
[Developer's Guide](https://wiki.documentfoundation.org/Documentation/DevGuide).

## Upstream provenance

This is an independent experimental fork of
[`LibreOffice/core`](https://github.com/LibreOffice/core), the office-suite
source maintained by The Document Foundation and its contributor community.

- Upstream remote: `https://github.com/LibreOffice/core.git`
- Imported upstream commit: `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21`
- Import commit in this repository: `44d393283e776c7e099763496c57b02ae509cd15`
- Import method: a new root commit with a tree identical to that upstream commit;
  the original upstream history is available through the `upstream` remote.

See [`docs/PROVENANCE.md`](docs/PROVENANCE.md) for reproducible verification.
LibreOffice Material is not an official The Document Foundation distribution,
and no endorsement is implied.

## Contributing

Start with the design contract and the earliest incomplete roadmap gate. Keep
changes narrow enough to build and verify, preserve existing shortcuts and
accessibility semantics, and attach genuine headless evidence for visible UI
changes. Never add generated or staged images as if they were application
captures.

When changing native product UI:

1. identify the shared component before adding an application-local variant;
2. use semantic tokens instead of hard-coded colors or elevations;
3. test keyboard, focus, high-contrast, localization, and reduced-motion paths;
4. record the exact commit and environment in the evidence manifest;
5. update the roadmap and repository memory only after the acceptance gate
   passes.

## License and attribution

LibreOffice source is open source and copyleft-licensed. Retain the license
headers and notices of every file you modify. The authoritative license texts
shipped with this source tree are [`COPYING`](COPYING),
[`COPYING.LGPL`](COPYING.LGPL), and [`COPYING.MPL`](COPYING.MPL); entirely new
LibreOffice source files should follow [`TEMPLATE.SOURCECODE.HEADER`](TEMPLATE.SOURCECODE.HEADER).

LibreOffice is backed by The Document Foundation. LibreOffice and The Document
Foundation names and marks belong to their respective owners. Project-specific
documentation and site work must not erase upstream authorship or licensing.
