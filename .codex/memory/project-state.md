# Project state

Last reviewed: 2026-07-19

## Objective

Modernize the complete LibreOffice GUI using Material Design principles while
retaining the native implementation languages and upstream office-suite
functionality. Prove visible work through real builds and off-screen desktop
testing, publish project documentation and evidence, and preserve upstream
licensing and provenance.

## Current milestone

**Phase 1 — tenth Material VCL and Windows updater source milestones published;
suite-wide work continues. Phase 0's native build/evidence gate remains open.**

The repository contains an imported LibreOffice source baseline, ten native
Material source milestones, a design contract, roadmap, published GitHub Pages
site, screenshot registry, and headless evidence plan. The third milestone adds
matched light/dark profiles, source-level high-contrast fallback routing,
native-style restoration and dynamic focus-policy refreshes, explicit headless
dark selection, standalone spin controls, and a dedicated headless drawing test
target. The automation harness has passed a Notepad-only off-screen preflight.
The fourth milestone adds strict semantic typography roles that derive from the
captured native font baseline instead of replacing platform/user fonts.
The fifth milestone closes all 72 `StyleSettings` color slots with exact
Material mappings, including list/collection and warning/error feedback roles,
while keeping the ten additions optional for partial legacy themes.
The sixth milestone adds eight semantic corner roles, resolves a single named
radius into both existing native rectangle axes, converts all 146 rounded
Material rectangles, and preserves the 11 implicit square rectangles plus the
legacy numeric `rx`/`ry` path.
The seventh milestone adds 15 semantic native integer metric roles and converts
331 existing integer uses—292 drawing strokes, 34 explicit part dimensions or
margins, and 5 numeric settings—without changing their values. All 676
normalized fractional coordinates stay literal, and the shape and typography
contracts remain separate. Existing downstream native conversions remain
unchanged; this source centralization adds no density profile or new DPI-aware,
`dp`, fractional-scale, or touch-sizing policy.
The eighth milestone adds optional full-width `TrackHorzArea` anatomy to the
native file renderer for progress and level indicators, keeps `Entire` as the
numeric-value-clipped fill, paints the track at zero, and maps level values to
the existing critical/low/medium/high 25% bands. Fill-only legacy definitions
retain their previous renderer path.
The ninth milestone defines the two reader-recognized controls that were still
on fallback: an outlined `Frame`/`Border` container drawn as one shared rounded
rectangle, with `getNativeControlRegion` now returning a native frame region and
a 2px content-region inset (the prerequisite D-017 required, see D-018); and a
net-less `ListNet`/`Entire` state that returns success while drawing nothing so
VCL suppresses its own tree connector nets (D-019).
The tenth milestone follows a 14-agent coverage audit (VCL native-draw calls vs
the definition) that confirmed inventory completeness and closes three
disabled-affordance gaps: a dimmed disabled `SubmenuArrow`, a disabled-but-checked
`toolbar`/`Button`, and a disabled-but-selected `tabitem` (`Entire` and
`MenuItem`). Three other verified gaps (default-button emphasis, field hover,
scrollbar-trough feedback) are deferred as design decisions (D-020). The Material
definition now has 79 parts, 205 states, 159 rounded rectangles, and 346 metric
references; these changes remain uncompiled and unexecuted.
The post-tenth source slice routes the Start Center's `open_all` standard
`suggested-action` class through `VclBuilder` to `PushButton::setAction(true)`,
selecting the existing Material `extra="action"` pushbutton states. Its focused
leaf-button CppUnit regression is included in the native workflow target list.
The same slice removes the Windows MSI workflow's contradictory `--disable-cli`
switch, asserts `ENABLE_CLI=TRUE`, and prebuilds the CLI payload that MSI
manifests require. These are source/configuration changes only; no new native
build, package, or runtime evidence is claimed here.
The Windows-only updater source reads the exact GitHub Latest XML release asset
and accepts one canonical MSI only after strict safe-tag, tag-derived URL,
filename, `application/x-msi` MIME, positive-size, and lowercase SHA-256 checks.
It rejects malformed and legacy persisted state before resume. Download and
install remain opt-in: checks default on weekly, automatic download defaults
off, and a visible Windows Installer launch requires explicit confirmation with
No as the default. There is no silent install. Confirmed bytes are copied with
`CREATE_NEW` into a protected per-run LocalAppData directory with a
user/Administrators/SYSTEM DACL, re-verified, and held with a final read lock
that excludes write/delete replacement. Network/privacy details are recorded in
[`PRIVACY.md`](../../PRIVACY.md).

The Windows release workflow is draft-first on `main`: it verifies the exact
target, asset names, upload states, sizes, and digests before promoting the
draft to a normal public non-prerelease Latest release, verifies the public
Latest feed, and removes a failed draft. This is implemented automation source,
not a successful-release claim.

The current native source has not completed native CI or run as LibreOffice, so
these milestones do not prove a whole-GUI rewrite, updater runtime, installer,
release, or any completed application surface.

Preceding Windows Actions run `29678095646` at
`937b61fd3ad7c83fba2714b6341118e0b778c252` passed configure, `Library_svxcore`,
and its four then-required native C++ targets, then failed only in MSI packaging
because `--disable-cli` suppressed legacy CLI payloads required by the manifest.
The first post-tenth Linux native run, `29695337988`, stopped while compiling
the new `vcl_treeview` fixture because that target did not opt in to the
internal PushButton header required by the focused VCL test. The target now
declares `VCL_INTERNALS`, matching the existing lifecycle test; its rerun is
pending. No current-source native CI/build, runtime, installer, normal release,
headless UI smoke, accessibility smoke, or accepted capture has completed.
Public assetless release/tag `e` remains non-evidence.

## Recorded facts

- GitHub repository: `codingmachineedge/libreoffice-material`.
- Default branch observed locally: `main`.
- Upstream: `LibreOffice/core`.
- Imported upstream commit: `63584e7f9f0cdc74b0e004bcbf88e5c3b42dba21`.
- Fork import commit: `44d393283e776c7e099763496c57b02ae509cd15`.
- Initial Material implementation commit:
  `46807f76f9a744fe61732e90f6085cc82eef16f5`.
- Second Material VCL source milestone commit:
  `c4414aa3919642ebb1079427b5ce27ce77049901`.
- Third Material VCL source milestone commit:
  `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8`.
- Fourth Material VCL source milestone commit:
  `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`.
- Fifth Material VCL source milestone commit:
  `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`.
- Sixth Material VCL source milestone commit:
  `3fe772f6068f6820f37c8297f431b39127f4e4d1`.
- Seventh Material VCL source milestone commit:
  `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731`.
- Eighth Material VCL source milestone commit:
  `291d134ceea2dd6fa354e2d319b043ffe42aa396`.
- Ninth Material VCL source milestone commit:
  `1e2dca2f76c5f7481451ad0f419a7053222e55df`.
- Tenth Material VCL source milestone commit:
  `18714cc1c7421225dd66b925e6295e13b56a7a7a`.
- Post-tenth Start Center action and Windows CLI repair source commit:
  `1e97d960be2b4d736dc00ec6a4d76fb4cf5dc905`.
- The imported upstream and fork import commits shared tree object
  `68ccb73abac4f7da67f894f11b0802627e90b474` when verified.
- Initial native source slice: packaged Material definition; opt-in file-widget
  theme selection/cache/fallback; definition-aware support; palette reader
  coverage; Material control/menu/progress states; and Start Center
  spacing/header/surface/recent/template treatment.
- Second Material VCL source milestone: 19 semantic light color tokens with
  order-independent resolution; strict invalid/unknown/duplicate definition
  rejection; 70 definition-backed parts and 172 states; expanded reader tests
  and negative fixtures; combo/RTL, toolbar grip, region, slider, and graphics
  cache corrections; and a standalone static source validator.
- Third Material VCL source milestone: matched light/dark palettes with 19
  tokens each; 74 definition-backed parts and 190 states; strict multi-palette
  parsing; resolved dark-profile selection; high-contrast native/generic
  fallback; captured pre-Material style/framework restoration; dynamic
  native-focus recomputation; Qt proxy/no-native high-contrast detection;
  explicit headless dark selection; shared theme state; standalone directional
  spin controls; and a dedicated public-API headless draw CppUnit target.
- Fourth Material VCL source milestone: typed `body`, `label`, and `title`
  roles; exact role/attribute/scale/minimum-weight parsing; native family, style,
  charset, language, pitch, orientation, width, and icon-font preservation;
  nonshrinking relative size policy; baseline-derived idempotent refresh;
  accessibility-safe title-height minima; expanded XML-walker APIs/tests; and
  malformed typography fixtures.
- Fifth Material VCL source milestone: 23-token light/dark palettes; an exact
  72-slot Material style schema; optional accent, list-box, alternating-row,
  warning, and error reader fields; conditional renderer application that
  preserves omitted legacy values; and source-level real-renderer dispatch,
  idempotence, and high-contrast fallback assertions.
- Sixth Material VCL source milestone: eight strict semantic corner roles;
  optional order-independent `shapes` parsing; singular `radius="@token"`
  resolution into the existing `mnRx`/`mnRy` fields; local token storage that
  avoids exported reader-layout changes; 146 converted rounded rectangles and
  11 unchanged implicit squares; legacy numeric radius compatibility; and 23
  new malformed-shape reader fixtures.
- Seventh Material VCL source milestone: 15 strict semantic native integer metric
  roles; optional order-independent `metrics` parsing; reference resolution into
  the existing stroke, part, and decimal setting representations; 331 converted
  integer uses split into 292 strokes, 34 part geometry attributes, and 5
  settings; 676 unchanged normalized coordinates; and legacy literal numeric
  compatibility for bundled and out-of-tree definitions.
- Eighth Material VCL source milestone: optional full-width progress/level
  tracks rendered before the clipped `Entire` fill; overflow-safe 25%, 50%, and
  75% level-band selection; zero-value track painting; direct track-part
  dispatch; and compatibility with legacy definitions that omit the track.
  Material adds 3 parts and 9 states/actions without adding token families.
- Local eighth-milestone validation passes for the full
  `2/23/3/8/15/72/77/199` schema. All 24 Python validator tests pass; the
  resolved 340-row metric geometry hash is
  `0345bb83fae32d79a5b596cc4f17046737a453de0d345a1fa144f737b9b35140`;
  the 676-row normalized coordinate hash remains unchanged. Exact indicator
  anatomy, each level band, track-only zero behavior, source-guard patterns,
  and pixel-oriented C++ test source are present, but the C++ targets remain
  uncompiled and unexecuted.
- Local seventh-milestone validation passes for the full
  `2/23/3/8/15/72/74/190` schema. All 22 Python validator tests pass; 38 metric
  reader fixtures exist (1 positive and 37 negative); the resolved 331-row
  metric geometry hash is `33d4dea2...5135de0`; and the exact 676-row normalized
  coordinate hash is `0979f2b3...331ed2e`. These are static source checks only;
  the C++ reader and fixtures remain uncompiled and unexecuted.
- Published seventh-milestone source validation passes for 2 schemes, 23 color
  tokens each, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style
  slots, 74 parts, and 190 states. All 22 Python validator unittest methods
  passed at the published source commit; the affected C++ targets remain
  unexecuted.
- Published sixth-milestone source validation passed for 2 schemes, 23 color
  tokens each, 3 typography roles, 8 shape tokens, 72 style slots, 74 parts,
  190 states, selected WCAG contrast pairs, native font/shape source
  invariants, XML parsing, and whitespace. All 16 Python validator unittest
  methods passed at that published source commit.
- GitHub Actions source-validation run `29517978358` completed successfully for
  third-milestone commit `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8`.
- GitHub Actions source-validation run `29522004268` completed successfully for
  fourth-milestone commit `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba`,
  including the new validator unittest step.
- GitHub Actions source-validation run `29524039805` completed successfully for
  fifth-milestone commit `a644ed9abb6d5112f182ff7ec6e0826b1754c89e`;
  semantic theme validation, all validator unittests, and Start Center lint each
  passed.
- GitHub Actions source-validation run `29525519723` completed successfully for
  sixth-milestone commit `3fe772f6068f6820f37c8297f431b39127f4e4d1`;
  semantic theme validation, all validator unittests, and Start Center lint each
  passed.
- GitHub Actions source-validation run `29527917064` completed successfully for
  seventh-milestone commit `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731`;
  semantic theme validation, all 22 validator unittests, and Start Center lint
  each passed.
- GitHub Actions source-validation run `29530112458` completed successfully for
  eighth-milestone commit `291d134ceea2dd6fa354e2d319b043ffe42aa396`;
  semantic theme validation, all 24 validator unittests, and Start Center lint
  each passed. Pages deployment run `29530112004` also completed successfully
  for that exact source commit.
- GitHub Actions source-validation run `29648977365` completed successfully for
  ninth-milestone commit `1e2dca2f76c5f7481451ad0f419a7053222e55df`;
  semantic theme validation, all 26 validator unittests, and Start Center lint
  each passed. Pages deployment run `29648977400` also completed successfully
  for that exact source commit.
- GitHub Actions source-validation run `29650136950` completed successfully for
  tenth-milestone commit `18714cc1c7421225dd66b925e6295e13b56a7a7a`;
  semantic theme validation, all 27 validator unittests, and Start Center lint
  each passed. Pages deployment run `29650136963` also completed successfully
  for that exact source commit.
- The detached LF worktree formerly prepared at
  `C:\Users\Administrator\Documents\GitHub\libreoffice-material-build` is no
  longer present. A fresh detached worktree with `core.autocrlf=false` must be
  created and pinned to the intended source commit before a native build.
- Build-installer run `29662095462` at
  `d6f66b686551b0d03cc3317fb18a80e74879cce1` stopped during configure because
  Perl `Archive::Zip` was missing. Build, native regression tests, packaging,
  and artifact staging did not run; no installer was produced.
- Public release/tag `e` is assetless and points at `d6f66b686`; it is not a
  genuine build release and does not change the accepted evidence count.
- Windows updater source uses the exact GitHub Latest XML route, strict
  tag/URL/name/MIME/size/SHA validation, legacy-state rejection, protected
  LocalAppData `CREATE_NEW` staging with a restrictive DACL and final read lock,
  and a visible default-No MSI consent gate; automatic checks default weekly/on,
  automatic download defaults off, and silent install is absent.
- Stable Windows publication is draft-first on `main`; an exact verified draft
  is promoted to a normal public non-prerelease Latest release only after its
  target and assets pass, with failed-draft cleanup.
- Current-source Linux run `29695793821` and Windows run `29695815101` at
  `e4dc8a850c982f33d8722fc203f86591b2993e8b` passed all five required native
  C++ targets. The Windows run also passed the legacy CLI payload check and
  completed the LibreOfficeDev installation-set build, but did not upload an
  MSI because recursive staging included two LibreOffice intermediate databases
  alongside the final package. The workflow now restricts collection to the
  final `LibreOfficeDev\msi\install\en-US` directory; its rerun is pending.
- Required runtime opt-in: `VCL_DRAW_WIDGETS_FROM_FILE=1` and
  `VCL_FILE_WIDGET_THEME=material`.
- Local build automation: `Build-Windows.cmd` calls `bin/Build-Windows.ps1`.
  It provisions a dedicated VS 2022/Cygwin profile in one hidden UAC bootstrap,
  validates signatures, hashes, and packaging tools, builds from an LF snapshot,
  and stages only an administratively extractable final MSI. It never changes the
  active checkout, deletes a build root, reboots, installs the MSI, or launches
  a UI. The source script parsed successfully but has not run a local build.
- UI driver: sibling repository `lowlevel-computer-use-mcp`, preflighted at
  commit `806d9ba85e4afbc2af58d7499496babfa7c68891`.
- A read-only driver audit found the same clean commit serving MCP on
  `127.0.0.1:8765`. Launch has no environment/cwd fields; window enumeration
  has no PID; generic move/resize/window actions are not off-screen reliable;
  desktop close does not close the app; and long-lived server handle caching
  requires a short-lived driver session for strict teardown proof.
- 2026-07-16 harness preflight: created
  `WinSta0\LibreOfficeMaterialQA`, launched and enumerated an off-screen Notepad
  window (HWND `37291736`, `1920×1125`), captured it through `PrintWindow` with
  `rendered_ok: true`, killed only run-scoped Notepad processes, and confirmed
  teardown when `OpenDesktop` returned Win32 error `2`.
- Temporary preflight capture SHA-256:
  `03C6A068ACAAB96579621CE0BFC4F447C0F43E8EB23DDB5B8665A580E062BFA3`;
  it was not retained because it was unrelated to LibreOffice.
- Verified LibreOffice Material screenshots: **0**.
- GitHub Pages source: `site/`; public URL:
  `https://codingmachineedge.github.io/libreoffice-material/`.
- Interactive Material design reference published at `site/prototype.html`, with
  a 2,433-command `site/prototype-features.json` mirror of the LibreOffice
  `.uno:` catalog. It is a self-contained, dependency-free HTML rendering of all
  eleven suite surfaces (Start Center, Writer, Calc, Impress, Draw, Base, Math,
  Features, History, Components, Dialogs) with light/dark/high-contrast,
  compact/comfortable, and classic/ribbon toggles, ported from the operator's
  Claude Design project `63dc9b52-b1d7-4efd-9d9e-df2173c3658c`. System fonts and
  inline SVG icons replace the design's hotlinked Google Fonts and its React
  `support.js` runtime; the MD3 palettes, eight corner roles, and density metrics
  match `material/definition.xml`. It is a hand-built design mockup, not a
  compiled-build capture, and does not change the verified-capture count of 0
  (D-021). Every search bar (Start Center, Features command catalog, Components
  gallery) carries a full regex builder — token palette, i/g/m/s flags, live
  validity and match count — filtering real data; the Features list keys
  selection on a unique UNO+name identity so the catalog's 214 duplicate command
  names no longer collide. A five-dimension adversarial review
  (`wf_e8395840-a9f`) confirmed self-containment and the honesty contract and
  drove these fixes.
- Complete written design specification published at `docs/design/` (D-022):
  an index plus twelve files (~46,000 words) covering foundations, actions,
  selection, inputs, navigation, containers, feedback, dialogs, Start Center,
  Writer/Calc, Impress/Draw, and Base/Math/shared surfaces. Component files
  carry anatomy/states/interaction/accessibility/density/RTL/platform/
  verification sections; surface files carry layout/flows/states/density/
  keyboard/a11y/verification. Authored by a 12-agent workflow
  (`wf_65acdda7-e4c`) whose completeness critic verified zero invented tokens,
  zero honesty violations, and coverage of all 19 components required by
  MATERIAL_DESIGN.md; its three minor gaps (RTL sections in chapters 10/12, a
  slider-stroke wording) were fixed before publication. The spec describes the
  target design only — nothing in it is build- or runtime-verified.
- Pages uses GitHub Actions workflow mode. Run `29510014215` deployed commit
  `46807f76f9a744fe61732e90f6085cc82eef16f5` successfully on 2026-07-16;
  follow-up endpoint checks returned HTTP `200` for both `/` and `styles.css`.
- Pages run `29513175965` deployed second-milestone commit
  `c4414aa3919642ebb1079427b5ce27ce77049901` successfully; the live index and
  stylesheet returned HTTP `200` and exposed the refreshed milestone/counts.
- Pages run `29517978373` deployed third-milestone commit
  `ddeec51e886f4642718eaa626ea2f48cdd9aa6a8` successfully; the live index and
  stylesheet returned HTTP `200`, exposed the exact unbuilt profile counts, and
  kept the verified-capture count at `0`.
- Pages run `29522004306` deployed fourth-milestone commit
  `7c33dd2462aaa6ee168f8ff711d89026f9b0d1ba` successfully; the live index and
  stylesheet returned HTTP `200`, exposed 3 typography roles alongside the
  color/part/state counts, and kept the verified-capture count at `0`.
- Pages run `29524040737` deployed fifth-milestone commit
  `a644ed9abb6d5112f182ff7ec6e0826b1754c89e` successfully; the live index and
  stylesheet returned HTTP `200`, exposed the exact 23-token, 72-style-slot,
  74-part, 190-state summary, and kept the verified-capture count at `0`.
- Pages run `29525520389` deployed sixth-milestone commit
  `3fe772f6068f6820f37c8297f431b39127f4e4d1` successfully; the live index and
  stylesheet returned HTTP `200`, exposed the exact 8-shape-token summary and
  `Source milestone 6`, and kept the verified-capture count at `0`.
- Pages run `29527917148` deployed seventh-milestone commit
  `2ce2cfd3e7489dc0acd6ce09f7e5461546fbb731` successfully; the live index and
  stylesheet returned HTTP `200`, exposed 15 metric roles, the exact 331-use
  summary and `Source milestone 7`, and kept the accepted-capture count at `0`.

## Required next gates

1. rerun the hosted clean-LF Windows staging rule, validate the emitted MSI, and
   record its exact commit, hash, and configuration;
2. launch the staged built start center with the two opt-in variables and an isolated
   profile on the proven headless desktop;
3. preserve the first LibreOffice baseline manifest, result, logs, and reviewed
   screenshot;
4. build/runtime-verify light/dark, focus, shape and metric geometry, and
   high-contrast routing; complete forced-color/platform signal coverage; and
   implement density-aware metric resolution plus the remaining token families
   and VCL primitives;
5. continue through every phase in `ROADMAP.md` without skipping suite surfaces.

## Known evidence gaps

- no native fork build is registered in the evidence ledger;
- no headless LibreOffice Material scenario is registered;
- no screenshot is registered;
- no application surface is verified Material-complete;
- no updater download, protected-stage, consent, or MSI-launch flow has been
  runtime-verified;
- no local native build is registered. A one-click source bootstrap now exists,
  but this host has Visual Studio 2026 rather than its dedicated VS 2022
  instance and no isolated Cygwin profile until the bootstrap is run. The hosted
  Windows workflow supplies its prerequisites. Current-source Linux and Windows
  native targets passed, and the latter built its full installation set, but MSI
  staging selected two intermediate databases as well as the final package. The
  corrected staging rule, installer/release, real application capture, headless
  smoke, and accessibility smoke remain pending.

## Multi-repository boundary

The low-level driver is external test tooling, not another deliverable of the
LibreOffice Material product. One product repository remains sufficient, so no
additional project-level master repository or product submodule graph is
currently justified; this does not describe LibreOffice's imported optional
upstream source submodules. If later work creates several independently
versioned product repositories, a separate master repository must pin them as
Git submodules. That orchestration decision does not convert unverified external
state into evidence and must record exact submodule commits.
