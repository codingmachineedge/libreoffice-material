# LibreOffice Material

An experimental LibreOffice engineering fork exploring a suite-wide Material
Design 3 interface while retaining LibreOffice's native implementation stack,
document engine, file-format support, and accessibility foundations.

> **Current development focus: Phase 1 — tenth Material VCL milestone plus a
> post-tenth Start Center and Windows MSI source follow-up.**
> Phase 0's native-build and application-evidence gate remains open. Semantic
> widget tokens, full-track progress indicators, value-sensitive level
> indicators, native outlined frames, net-less tree connectors, stricter VCL
> definition parsing, broader state coverage, Start Center changes, and a
> consent-based Windows updater are present in source, and the current source
> has passed its five required native C++ targets in Linux Actions run
> [`29695793821`](https://github.com/codingmachineedge/libreoffice-material/actions/runs/29695793821)
> and in Windows Actions run
> [`29695815101`](https://github.com/codingmachineedge/libreoffice-material/actions/runs/29695815101).
> That Windows run also completed the full LibreOfficeDev installation-set build
> and the legacy CLI payload check; it did not stage an MSI artifact.
> The whole GUI has not been rewritten, and no application surface is
> Material-complete. **There is no verified installer or downloadable build
> yet** — the Windows run found a staging-rule defect after building the MSI:
> recursive discovery included two retained intermediate MSI databases alongside
> the final package. The workflow now scopes discovery to the final success-only
> `install\en-US` directory, and a rerun is required before an artifact exists.
> No LibreOffice application run has been accepted; the interactive
> [design reference](https://codingmachineedge.github.io/libreoffice-material/prototype.html)
> (a mockup, not the app). To run the actual editor, install upstream LibreOffice
> from [libreoffice.org](https://www.libreoffice.org/download/), which does not
> include these Material changes. An automated pipeline
> ([`build-installer.yml`](.github/workflows/build-installer.yml)) attempts a
> Linux build, while [`windows-installer.yml`](.github/workflows/windows-installer.yml)
> now provides a manually dispatched Visual Studio 2022/Cygwin path for a real
> Windows x64 MSI. Both publish **only** after genuine packages pass structural
> validation. Run `29695815101` at
> `e4dc8a850c982f33d8722fc203f86591b2993e8b` proves the repaired CLI payload,
> required native targets, and full installation-set build, but no staged MSI,
> runtime, release, headless UI, or accessibility result is accepted yet. A public
> assetless release/tag named `e` exists, but it contains no build and does not
> satisfy the project's gates.

[Project site](https://codingmachineedge.github.io/libreoffice-material/) ·
[Interactive preview](https://codingmachineedge.github.io/libreoffice-material/prototype.html) ·
[Roadmap](ROADMAP.md) ·
[Material specification](MATERIAL_DESIGN.md) ·
[Full design spec](docs/design/README.md) ·
[Headless UI evidence plan](docs/HEADLESS_UI_EVIDENCE.md) ·
[Screenshot index](docs/SCREENSHOTS.md)

## What is true today

| Area | State | Evidence |
| --- | --- | --- |
| LibreOffice source baseline | Imported | This repository's initial tree matches upstream commit `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21` |
| Material design direction | Initial specification | [`MATERIAL_DESIGN.md`](MATERIAL_DESIGN.md) |
| Material VCL implementation | Tenth milestone plus a native-test-backed Start Center follow-up | Light/dark profile routing, complete semantic `StyleSettings` color mapping, native-preserving type roles, semantic shape/metric roles, full-track progress and value-sensitive level indicators, native outlined frames and net-less tree connectors, disabled-affordance state completeness, strict source validation, high-contrast fallback, shared renderer fixes, and Start Center source changes are present. The standard `suggested-action` UI class reaches `PushButton::setAction(true)` through `VclBuilder`, selecting the existing Material `extra="action"` states; `CppunitTest_vcl_treeview` passed in current Linux and Windows runs, while runtime gates remain open |
| Whole-suite implementation | Incomplete | Phased work remains in [`ROADMAP.md`](ROADMAP.md) |
| Verified UI screenshots | None yet | The truthful empty registry is in [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md) |
| Headless harness | Preflight passed; LibreOffice not run | A temporary Notepad-only driver preflight proved the off-screen mechanics, not this UI; see [`docs/HEADLESS_UI_EVIDENCE.md`](docs/HEADLESS_UI_EVIDENCE.md) |
| Interactive design reference | Published mockup | [`site/prototype.html`](site/prototype.html) — 11 suite surfaces, a regex builder on every search bar, and a Find & Replace dialog; guarded by [`bin/validate-prototype.mjs`](bin/validate-prototype.mjs) (7/7) and the `prototype-check` CI |
| Windows updater | Source implemented; native test/build evidence, no runtime evidence | Windows-only update source reads the exact GitHub Latest XML asset, rejects untrusted or legacy state, verifies the canonical MSI metadata and bytes, stages through protected LocalAppData, and requires default-No consent before a visible install; an installer artifact, updater exercise, and release remain pending; see [Privacy](PRIVACY.md) |
| Installer / release | Full Windows install set built; MSI staging rerun pending | [`windows-installer.yml`](.github/workflows/windows-installer.yml) pins VS 2022, retains and checks the legacy CLI bridge payload, runs the required native targets, and now selects only the final `install\en-US` MSI rather than LibreOffice's retained intermediate databases. Run `29695815101` built the set but stopped before upload at the old selection rule; no artifact or release is claimed |

This table is deliberately conservative. A roadmap item changes state only when
its code, build result, interaction checks, and committed visual evidence agree.

## Material VCL source milestones

The implementation is intentionally opt-in and shared-layer first. The current
source includes:

- a packaged `material/definition.xml` file-widget theme with matching light and
  dark palettes of 23 semantic color roles each, 79 definition-backed parts,
  and 205 component states;
- eight semantic corner roles resolved order-independently by the native XML
  reader into both existing rectangle radius axes; all 159 rounded Material
  rectangles use one named role while the 11 square rectangles remain
  attribute-free, and legacy numeric `rx`/`ry` definitions stay supported;
- 15 semantic native integer metric roles for strokes, control dimensions,
  spacing, tab/title heights, and list-preview geometry; 346 integer values now
  resolve through those roles—307 drawing strokes, 34 explicit part
  dimensions/margins, and 5 numeric settings—while the existing native action,
  part, and settings representations remain unchanged;
- all 684 normalized `x1`/`y1`/`x2`/`y2` coordinate values remain local
  literals because they describe proportional component geometry rather than
  integer metrics; typography scaling and rectangle corners retain their
  separate semantic contracts;
- an exact 72-slot Material style contract that closes the ten previously
  native-dependent accent, list-box collection, alternating-row, warning, and
  error colors; these newer reader fields remain optional so partial legacy and
  out-of-tree file themes preserve native values when a role is omitted;
- typed `body`, `label`, and `title` roles with bounded relative scaling and a
  strict minimum-weight vocabulary; each role copies the captured platform font,
  applies the declared nonshrinking height scale, and only raises weight to the
  declared minimum, so family, style, charset, language, pitch, orientation,
  width, and icon fonts remain native;
- order-independent color, shape, and metric `@token` resolution and strict
  rejection of malformed colors, shapes, or metrics, invalid or duplicate token
  sections, mismatched palette schemas, unknown references, ambiguous radius
  declarations, and unknown or duplicate control parts; older bundled and
  out-of-tree definitions retain their existing literal numeric geometry path;
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
- native Material progress and level indicators that draw an optional full
  track before the clipped fill; level fills retain the existing four value
  bands through `critical`, `low`, `medium`, and `high` semantic states, while
  legacy file themes with only an `Entire` fill keep their prior path;
- a native Material outlined frame (`ControlType::Frame`/`Border`) that reuses
  the shared container outline, surface-container fill, thin stroke, and
  container corner roles; the renderer now reports a native frame region so
  `decoview` issues the file-definition border draw, and a net-less Material
  tree (`ControlType::ListNet`/`Entire`) that is supported yet draws nothing so
  VCL suppresses its own connector nets for a flatter tree;
- disabled-affordance state completeness for three controls that previously
  collapsed a disabled tuple onto a generic state: a dimmed `SubmenuArrow` when a
  submenu parent is disabled, a dimmed-but-checked toolbar button
  (`enabled="false"` + `button-value="true"`), and a disabled-but-selected tab
  (`Entire` and `MenuItem`) so a disabled tab control still identifies its
  current page;
- shared renderer corrections for composite combo geometry and RTL placement,
  toolbar grips, standalone spin geometry and direction, native control regions,
  slider sizing, and raw graphics-state invalidation;
- a standalone source validator for exact color, shape, metric, 72-slot style,
  and typography contracts, required parts and states, light/dark schema parity,
  unused tokens, native font/geometry-preservation invariants, and selected
  WCAG contrast pairs—including list selection and warning/error feedback—plus
  reader, XML-walker, and headless draw C++ coverage with negative XML fixtures;
- Start Center spacing, a Home header/subtitle, surface roles, and recent/template
  text and fill colors derived from VCL style settings; `open_all` now uses the
  standard `suggested-action` class, which VCL preserves as the push-button
  action state used by the existing Material `extra="action"` definitions.

The local static validator passes with 2 schemes, 23 semantic color tokens per
scheme, 3 semantic typography roles, 8 semantic shape tokens, 15 semantic
metric roles, 72 style slots, 79 parts, and 205 states.
The static validator remains source validation, but the current five required
native C++ targets—including the focused `vcl_treeview` builder fixture—passed
in Linux and Windows Actions. No `soffice` application scenario has run, no
surface is verified Material-complete, and the screenshot count remains 0.
Controls whose current file-widget geometry cannot preserve native semantics
continue through LibreOffice's existing fallback.

The metric roles preserve the current integer values and existing downstream
native conversions exactly. This token layer adds **no** density profile or new
DPI-aware, `dp`, fractional-scale, or touch-target policy; those require later
renderer and runtime work backed by real builds and captures.

Once a compatible LibreOffice build exists, the intended Windows opt-in is to
set both variables before launching the built application:

```powershell
$env:VCL_DRAW_WIDGETS_FROM_FILE = "1"
$env:VCL_FILE_WIDGET_THEME = "material"
```

These variables describe the source path; they are not a successful-run claim.
The `vcl_widget_definition_reader_test` and
`vcl_file_definition_widget_draw_test` targets have passed in the hosted current
source runs, while a real `soffice` launch remains pending a successfully staged
MSI artifact.

## Windows updater source milestone

The Windows package source now enables LibreOffice's consent-based updater
against one exact feed:
`https://github.com/codingmachineedge/libreoffice-material/releases/latest/download/windows-update-manifest.xml`.
GitHub's Latest route supplies the workflow-generated XML for the normal stable
release. The parser accepts one Windows x64 MSI only when its safe release tag,
tag-derived GitHub URL, canonical `LibreOfficeMaterial-Windows-x64.msi` name,
`application/x-msi` MIME type, positive byte count, and lowercase SHA-256 all
match. Legacy or malformed persisted update state is discarded before a resume.

After download, the complete file is checked by size and SHA-256. A confirmed
install copies those bytes with `CREATE_NEW` into a protected, per-run
LocalAppData directory whose DACL is limited to the user, Administrators, and
SYSTEM; it verifies the staged copy and retains a final read lock that excludes
write/delete replacement. The only install action is a visible Windows
Installer launch after an explicit confirmation whose default is **No**. There
is no silent install path.

Automatic update checking is enabled by default on a weekly interval. Automatic
download is disabled by default, and download and installation remain user
opt-in. Network and data-handling details are in [`PRIVACY.md`](PRIVACY.md).
This describes implemented source, not runtime proof: Linux and Windows native
tests plus the Windows installation-set build have completed, but the updater's
published-release path, installer exercise, headless UI smoke test, and
accessibility smoke test are still pending.

The stable release workflow is likewise source-only at this point. On `main` it
creates a draft release, validates the exact target, asset names, upload states,
sizes, and digests, then promotes that verified draft to a normal public,
non-prerelease Latest release and checks the public Latest feed. A failed draft
is cleaned up. No run has yet completed that path.

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

The interactive reference at
[`site/prototype.html`](site/prototype.html) is the intended Material look and
interaction drawn as a self-contained, dependency-free HTML page (system fonts,
inline SVG icons, no web fonts or CDN). Every search bar in it carries a full
regex builder — token palette, `i`/`g`/`m`/`s` flags, live validity and match
count — filtering the real Start Center, command-catalog, and gallery data, and
the Dialogs surface includes a working Find & Replace that runs the same builder
over live document text. The token contract behind it is documented in
[`docs/DESIGN_TOKENS.md`](docs/DESIGN_TOKENS.md), and
[`bin/validate-prototype.mjs`](bin/validate-prototype.mjs) is a dependency-free
Node check of the prototype's self-containment, tokens, icons, and regex engine
(`node bin/validate-prototype.mjs`). Every color, corner, and metric mirrors
the semantic roles in
[`vcl/uiconfig/theme_definitions/material/definition.xml`](vcl/uiconfig/theme_definitions/material/definition.xml).
It is a design specification aid, **not** a screenshot of a compiled LibreOffice
and **not** build evidence; it does not change the verified-capture count, which
remains 0.

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

> **Current build gate:** no complete supported *local* LibreOffice build
> profile exists. The local Visual Studio 2022 Build Tools instance has MSVC
> and CMake but lacks ATL and the CRT merge modules required for packaging; the
> installed Windows SDK 26100 is complete, but no supported Cygwin or WSL helper
> environment is installed. The manually dispatched hosted Windows workflow
> supplies and validates those prerequisites against a clean LF checkout.
> Current-source Linux run `29695793821` and Windows run `29695815101` passed
> all five required native C++ targets; the latter also built the full Windows
> installation set. It stopped at MSI staging because recursive discovery saw
> two intermediate databases as well as the final package. The corrected final
> directory rule awaits a rerun. No staged installer, LibreOffice application
> run, normal release, headless UI smoke, accessibility smoke, or accepted
> capture has occurred yet.

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
