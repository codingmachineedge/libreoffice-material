# Project state

Last reviewed: 2026-07-20

## Objective

Modernize the complete LibreOffice GUI using Material Design principles while
retaining the native implementation languages and upstream office-suite
functionality. Prove visible work through real builds and off-screen desktop
testing, publish project documentation and evidence, and preserve upstream
licensing and provenance.

Current delivery and verification scope is Windows. Cross-platform acceptance
gates remain documented as deferred future work rather than being removed or
counted as current evidence.

Exact source `393263ad924eae8d64b4f9a35bd6486ef83578fc` removes the bottom
Donate button, member, icon constant, conditional substitution, and donation
URL dispatch from the footer. Help and Extensions remain. Its focused validator
and six tests, VS 2026 product build, five-target native regression phase, MSI
staging/extraction, and accepted light UI/accessibility smoke pass. Earlier
screenshots that show the old button remain immutable historical evidence. The
light, dark, and forced-high-contrast current-source refreshes are accepted.

## Current milestone

**Phase 1 — tenth Material VCL and Windows updater source milestones published;
corrected exact-source local MSI and canonical light/dark/forced-high-contrast Start Center smoke recorded;
suite-wide work continues. The corrected normal public Latest release and its
four assets are verified, while Phase 0's full reproducibility and installer
lifecycle gates remain open.**

The repository contains an imported LibreOffice source baseline, ten native
Material source milestones, a design contract, roadmap, published GitHub Pages
site, screenshot registry, and headless evidence plan. The third milestone adds
matched light/dark profiles, source-level high-contrast fallback routing,
native-style restoration and dynamic focus-policy refreshes, explicit headless
dark selection, standalone spin controls, and a dedicated headless drawing test
target. The automation harness has advanced from its Notepad preflight to
accepted exact-source LibreOfficeDev Start Center runs, with the corrected
`fbba560e27` payload now supplying the nine-image canonical gallery.
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
references. Definition parsing and state-dispatch command/region assertions
compiled and executed in current Linux, Windows, and local VS 2026 native runs.
The corrected `fbba560e2` extracted runtime also launched with the Material
opt-in set, but individual state tuples remain unexercised and pixel-unverified.
The post-tenth source slice routes the Start Center's `open_all` standard
`suggested-action` class through `VclBuilder` to `PushButton::setAction(true)`,
selecting the existing Material `extra="action"` pushbutton states. Its focused
leaf-button CppUnit regression is included in the native workflow target list.
The canonical Windows rewrite now also has a source-only shared dialog
placement seam (D-028). After final VCL `InitShow` layout, Windows `Dialog`
instances are anchored to the bottom-right of the visible owner/work area with
a bounded 16 px inset and decorated-extent clamping. LibreOfficeKit and
non-Windows geometry remain unchanged. Its static contract and eleven mutation
regressions pass; notification composition, producer routing, customization,
stacking, visible bulk management, and current-build runtime proof remain open.
The source-only notification history foundation (D-031) now supplies a genuine
local bare Git repository, metadata-only default, process mutex plus permanent
OS-held cross-process guard, CAS `main`, atomic bulk state changes, recoverable
tombstones, history, inverse-commit undo, and bounded parentless checkpoints.
A durable pending gate blocks user writes after prune failure, while validated
retry reuses the installed checkpoint without object or ref growth. Its source
contract and all 15 mutation tests pass; thirteen native CppUnit cases are wired
but not compiled, and no visible notification host/manager or configuration
binding is claimed.
The shared search foundation (D-030) now provides ICU/LibreOffice literal and
regex evaluation, `i/g/m/s`, live validation, zero-width progress, bounded
matching, token insertion, and embedded advanced documentation in an anchored
non-modal popover. Its source contract and eight mutations plus UI/accessibility
lint pass; twelve native tests are wired but not yet compiled. The 26 existing
and one planned search-field registry entries still require actual integration
and runtime proof.
The same source line implements D-029: automatic Welcome/What’s New, Tip,
Windows file-association, donation/Get Involved, AutoCorrect-explanation, and
crash-report submission prompts plus their dead configuration/UI and misleading
crash-report opt-in are removed.
Explicit Help/association actions and recovery, Safe Mode, extension,
macro/security, metadata, read-only, and credential warnings remain. The
no-nag contract passes 35 forbidden markers, nine deleted surfaces, sixteen
required suppressions/safeguards/manual actions, and four mutation tests;
current-build fresh/legacy-profile startup proof remains open.
The same slice removes the Windows MSI workflow's contradictory `--disable-cli`
switch, asserts `ENABLE_CLI=TRUE`, and prebuilds the CLI payload that MSI
manifests require. These changes are included in the exact-source local VS 2026
build and extracted MSI payload recorded below.
The Windows-only updater source reads the exact GitHub Latest XML release asset
and accepts one canonical MSI only after strict safe-tag, tag-derived URL,
filename, `application/x-msi` MIME, positive-size, and lowercase SHA-256 checks.
It rejects malformed and legacy persisted state before resume. Download and
install remain opt-in: checks default on weekly, automatic download defaults
off, and a visible Windows Installer launch requires explicit confirmation with
No as the default. There is no silent install. Confirmed bytes are copied with
`CREATE_NEW` into a protected per-run LocalAppData directory with full-access
ACEs limited to SYSTEM, Administrators, and Owner Rights, re-verified, and held
with a final read lock that excludes write/delete replacement. Current source
forwards exactly four major-update arguments: `/i`, the staged MSI,
`REBOOT=ReallySuppress`, and `MSIRESTARTMANAGERCONTROL=DisableShutdown`. It
excludes `REINSTALL=ALL` and `REINSTALLMODE=vomus`, which are retained only for
explicit repair; the focused suite covers the DACL, exclusive create, retained
lock, and exact argument vector. Network/privacy details are recorded in
[`PRIVACY.md`](../../PRIVACY.md).

Every push to `main` starts the Windows release workflow, with manual dispatch
retained. It uploads the validated MSI and update metadata directly to a draft,
verifies the exact target, asset names, upload states, sizes, and digests before
promoting the draft to a normal public non-prerelease Latest release, verifies
the public Latest feed, and removes a failed draft. Only diagnostics use an
Actions artifact. Hosted runs at `e6fc09202` and `2ed96c4a6` completed the
build, native tests, MSI, extraction, and structural validation but failed
publication because pre-promotion validation required the canonical tag URL
while GitHub still exposed its temporary `untagged-*` draft URL. Current source
accepts that draft-only URL state, retains the canonical URL requirement after
promotion, and has a PowerShell 5.1/7 regression validator; a pushed hosted
rerun remains required. The corrected
[`windows-msi-local-20260720-fbba560e2`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2)
release is normal, public, non-draft, non-prerelease, and Latest. It targets
exact source `fbba560e27db26de605c40aa237c554c1f0744b1` and has exactly four
publicly byte-verified assets.

The source-controlled Windows Sandbox lifecycle harness now has a safe `Prepare`
default and explicit `Launch`/`Verify` modes. It pins both historical and
corrected MSI sizes/hashes, maps only fresh narrow input/output directories,
disables networking and device/clipboard redirection, and requires exact-zero
install, same-version update, repair-probe, and uninstall results with
`/norestart`, `REBOOT=ReallySuppress`,
`MSIRESTARTMANAGERCONTROL=DisableShutdown`, unchanged reboot indicators, and an
atomic `COMPLETE.json`. The reviewed guest now positively attests the Windows
Sandbox WDAG identity/VM/read-only mapping before entering any cleanup or
shutdown path, propagates installer-query failures, requires exact unregistered
product states, and the host independently rechecks reboot snapshots plus
normal Sandbox client disposal before persisting `host-verification.json`. Its parser/static validation and host safety
snapshot pass. Fresh prepared run
`20260720-041140-7240676-b3777205bfb344a2977090ba35d643c3`
contains both exact pinned MSI hashes and passes the non-launching `Inspect`
mode. Its first isolated launch returned `1` after the guest completed far
enough to attempt result publication, because PowerShell cannot apply `@(...)`
directly to the generic result lists. Only `FAILURE.json` was retained; no
accepted lifecycle artifacts or host verification exist. Host reboot and
LibreOffice-registration fingerprints stayed identical and cleanup reached
zero Sandbox processes. The reviewed source now uses `.ToArray()`, preserves
JSON array shape, tracks the current packaged Sandbox server/remote-session
names, gracefully closes only a run-bound client after backend exit, and makes
`Verify` require host-retained proof. This remains diagnostic harness evidence
until a fresh lifecycle run passes.
Fresh run `20260720-043916-4641037-b451b45fa51a423c880f7092faa45274`
proved the serialization and packaged-Sandbox disposal fixes, then returned `1`
before any MSI step because `Invoke-MsiQuery` wrapped all 107 Property-table rows
inside one collection. It retained a hash-manifested failure bundle with empty
step/snapshot arrays; host fingerprints again matched and zero Sandbox processes
remained. The query now emits individual rows, requires all pinned MSI properties,
and passes an exact-source PowerShell 5.1 identity probe for both retained MSIs.
Third run `20260720-045143-7859553-08fb3836f8b446dda272e206d296a591`
performed real old-install and corrected same-version MSI commands with exit
code `0` and unchanged guest reboot fingerprints. It then failed closed because
the old ProductCode remained registered at state `5`. The retained update log
shows `OLDPRODUCTS` contained the old ProductCode, but the command incorrectly
passed `REINSTALL=ALL` and `REINSTALLMODE=vomus` to the new ProductCode. Windows
Installer selected no features and skipped `RemoveExistingProducts`. Current
source removes those properties from the major-update command while retaining
them for repair. Cleanup uninstalled the old product with exit `0`,
left both ProductCodes absent, and host before/after safety snapshots matched;
repair, corrected uninstall, `COMPLETE.json`, and host verification were not
accepted. The corrected sequence passes static PowerShell 5.1/7 validation but
must be rerun, so installer lifecycle acceptance remains open.

The exact-source local builds, corrected release, and light/dark/high-contrast Start Center smoke
do not prove a whole-GUI rewrite, updater runtime, installer lifecycle, or any
completed application surface.

Preceding Windows Actions run `29678095646` at
`937b61fd3ad7c83fba2714b6341118e0b778c252` passed configure, `Library_svxcore`,
and its four then-required native C++ targets, then failed only in MSI packaging
because `--disable-cli` suppressed legacy CLI payloads required by the manifest.
The first post-tenth Linux native run, `29695337988`, stopped while compiling
the new `vcl_treeview` fixture because that target did not opt in to the
internal PushButton header required by the focused VCL test. The target now
declares `VCL_INTERNALS`, matching the existing lifecycle test. Subsequent
current-source Linux/Windows runs passed all five targets, and the exact-source
local VS 2026 build plus light/dark/high-contrast Start Center/UNO-tree smoke are registered.
Updater, installer lifecycle, and the broader runtime matrix remain open.
Public assetless release/tag `e` remains non-evidence.

## Recorded facts

- GitHub repository: `Ding-Ding-Projects/libreoffice-material`.
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
  and pixel-oriented C++ test source were present. At that milestone the C++
  targets had not yet compiled or executed; the current required native targets
  now execute definition/state command assertions, while rendered-pixel
  comparisons remain missing.
- Local seventh-milestone validation passes for the full
  `2/23/3/8/15/72/74/190` schema. All 22 Python validator tests pass; 38 metric
  reader fixtures exist (1 positive and 37 negative); the resolved 331-row
  metric geometry hash is `33d4dea2...5135de0`; and the exact 676-row normalized
  coordinate hash is `0979f2b3...331ed2e`. These were static source checks at
  that milestone; the C++ reader and fixtures now compile and execute in the
  current required native targets, without establishing pixel output.
- Published seventh-milestone source validation passes for 2 schemes, 23 color
  tokens each, 3 typography roles, 8 shape tokens, 15 metric tokens, 72 style
  slots, 74 parts, and 190 states. All 22 Python validator unittest methods
  passed at the published source commit. The affected C++ targets were
  unexecuted at that milestone and have since executed in current native runs;
  per-widget/state pixel comparisons remain absent.
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
  and stages only an administratively extractable final MSI. It checks
  safe/short paths and both drives before bootstrap, keeps Git config isolated
  below the build root, and preserves unique phase logs. It never changes the
  active checkout, deletes a build root, reboots, installs the MSI, or launches
  a UI. On 2026-07-20, an explicit VS 2026 build from clean detached source
  `577059e2741185b512c184c64685c16d335d10ea` passed the five native targets
  and CLI payload, completed the product, and produced an unsigned
  199,692,288-byte MSI (SHA `437b059c…54a43`). Administrative extraction
  returned `0` with one `soffice.exe`. The wrapper parent exited before final
  dist staging/manifest copy. Current source now safely quotes the extraction
  command and waits on its hidden `msiexec` client before reading the exit code
  or inspecting payload files; its PowerShell 5.1/7 static validator passes,
  and exact implementation commit `7029dccf4` passed the final phase. All five
  required VS 2026 native targets passed before the full product/MSI build. The
  staged unsigned 199,671,808-byte MSI is `ea503d3a…b934`; waited extraction
  returned `0`, produced 4,885 files / 603,901,200 bytes and one `soffice.exe`,
  embedded build ID `7029dccf4`, and yielded an updater DLL matching the build
  tree at `b8264c74…fea58`.
- Corrected commit `fbba560e27db26de605c40aa237c554c1f0744b1` produced an
  administratively extracted runtime candidate whose canonical off-screen Home
  and Templates smoke passed. Its bounded UNO trees report 96/49 and 111/64
  total/visible nodes, zero errors, and no partial capture; termination was
  normal, matching process/window counts reached zero, and the desktop closed.
  This is runtime-only proof and does not cover MSI install, repair, upgrade,
  uninstall, or restart suppression.
- Corrected release
  [`windows-msi-local-20260720-fbba560e2`](https://github.com/Ding-Ding-Projects/libreoffice-material/releases/tag/windows-msi-local-20260720-fbba560e2)
  was published on 2026-07-20 at 06:44:07 UTC as a normal public, non-draft,
  non-prerelease Latest release targeting exact source
  `fbba560e27db26de605c40aa237c554c1f0744b1`. Its exactly four cache-busted
  public Latest downloads matched the release: MSI 199,688,192 bytes,
  `180e511c065f3e21cd9e4fd0abe31f8886b0cc5ce5ce27a48f2890f83d1afeea`;
  sidecar 102 bytes,
  `e82f022d06665a165b8d0145acac0aae7b39cd9f8b9cbd0f7a1cfa1105021b9e`;
  JSON manifest 1,011 bytes,
  `12e6495e5d5051657dd99e6c0afc6d61941144c1bcde5f792f09a9949bea0fc1`;
  and XML manifest 972 bytes,
  `b686d9e9641360c3962bc27b8b6517b9a76c14c06cd50efbcbcfe485724eab72`.
  This proves publication and public bytes, not updater execution or MSI
  lifecycle behavior. The older `577059e274` release remains historical and
  retains its missing-fifth-launch-argument warning.
- UI driver: sibling repository `lowlevel-computer-use-mcp`, accepted-run commit
  `beed66ca6ed2503e6170ee1e1158247f1c2f0140` (clean `main`, 0/0 from origin).
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
- Canonical verified exact-source Start Center gallery captures: **9**: three
  Help/Extensions-only light-profile files from committed-harness run
  `20260720-143309-393263ad92-windows-headless-light`, three dark files from
  `20260720-144200-393263ad92-windows-headless-dark`, and three
  forced-high-contrast files from
  `20260720-144249-393263ad92-windows-headless-highcontrast`. Every appearance
  includes a visible Tab focus state whose UNO tree exposes the `Open File` push
  button as the sole `FOCUSED` node. The superseded three-image corrected light
  run `20260720-112425-fbba560e27-windows-headless-light`, earlier corrected light run
  `20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression` and older
  `20260720-012853-577059e274-vs2026-msi-raster` pair remain historical accepted
  proof. All three newest appearance runs used exact source
  `393263ad924eae8d64b4f9a35bd6486ef83578fc`; dark and high contrast used clean
  harness `75c119e395b9689e2c97341d5f63128db10c255a`. All used clean, dedicated
  same-token driver `547a102a49169d41da876de217856229ab7c03a1`,
  atomically bound HWND/PID/thread/DPI
  inside the off-screen desktop enumeration callback, and ended with normal UNO
  termination, zero exact-payload processes/windows, a closed desktop, and a
  stopped driver. The corrected extracted runtime launched with
  `VCL_DRAW_WIDGETS_FROM_FILE=1` and `VCL_FILE_WIDGET_THEME=material` set. This
  wording does not claim that every visible control loaded the Material
  definition or that individual widget/state pixels were verified.
- GitHub Pages source: `site/`; public URL:
  `https://ding-ding-projects.github.io/libreoffice-material/`.
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
  compiled-build capture and did not itself change the evidence registry
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
  target design only and is not itself build/runtime evidence. Some linked
  native definition/state assertions have executed and the corrected Start
  Center smoke ran, but the specification's individual surfaces and pixels are
  not verified.
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

1. verify the exact hosted clean-LF Windows auto-release workflow result for
   corrected source; the local VS 2026 wrapper gate is complete at `7029dccf4`;
2. build/runtime-verify accelerated rendering, deeper keyboard traversal,
   shape and metric geometry, and system-driven high-contrast routing; complete
   forced-color/platform signal coverage; and
   implement density-aware metric resolution plus the remaining token families
   and VCL primitives on Windows; retain equivalent cross-platform matrices as
   deferred work outside the current delivery scope;
3. exercise updater download/protected stage/default-No consent/MSI launch and
   run the new disposable Windows Sandbox install/update/repair/uninstall harness
   to prove restart suppression;
4. continue through every phase in `ROADMAP.md` without skipping suite surfaces.

## Known evidence gaps

- no application surface is verified Material-complete;
- no updater download, protected-stage, consent, or MSI-launch flow has been
  runtime-verified;
- the locally staged current MSI is unsigned and not yet the public Latest asset;
- definition/state command and region assertions execute, but individual
  widget/state pixel comparisons remain missing;
- accelerated rendering, deeper keyboard traversal, 200% scaling, localization,
  installer, updater, and suite-wide runtime/accessibility coverage remain pending.

## Multi-repository boundary

The low-level driver is external test tooling, not another deliverable of the
LibreOffice Material product. One product repository remains sufficient, so no
additional project-level master repository or product submodule graph is
currently justified; this does not describe LibreOffice's imported optional
upstream source submodules. If later work creates several independently
versioned product repositories, a separate master repository must pin them as
Git submodules. That orchestration decision does not convert unverified external
state into evidence and must record exact submodule commits.

## 2026-07-20 — asynchronous notification service source checkpoint

- `SfxApplication` now owns a lazy `NotificationCenterService`; profile
  callbacks use a cancellable, self-retaining VCL queue and application teardown
  closes worker admission before delivery, drains accepted requests, joins the
  worker, and releases the service while VCL is alive.
- One serialized worker constructs, calls, and destroys `NotificationStore`.
  Completions carry immutable generation-stamped record/history snapshots;
  compare-and-swap conflicts retain their failure result while refreshing the
  accompanying snapshot to the winning repository head.
- `NotificationConfiguration` maps all 13 generated display/history preferences
  for normalized batch read/write. Test repositories do not touch profile
  configuration. The service preserves the store's metadata-only default and
  maps each selected-ID vector to one atomic store method call.
- Eight new CppUnit cases bring the wired notification target to 21 cases for
  ordering, shutdown durability, concurrent admission, completion-side
  destruction, required off-worker dispatch, conflict refresh, one
  below-threshold action commit per bulk operation, and metadata-only redaction.
  They are registered but not
  compiled in this checkpoint. The static notification contract and all 24
  mutation tests, prototype validator (9/9), XML parse, diff check, and focused
  Clang formatting pass. No visible stack/manager, producer routing, native
  build, or runtime UI behavior is claimed.
