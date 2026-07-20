# 01 — Foundations

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This file defines the ground rules every component and surface specification in
this directory inherits: the design principles, the four token families and
their exact values, how a theme is resolved, how elevation and motion are
expressed, the density and adaptive-layout models, iconography rules, and
writing conventions. The normative sources are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (contract),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`vcl/uiconfig/theme_definitions/material/definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native contract, compiled at commit 577059e274; surface state unverified), and
[`site/prototype.html`](../../site/prototype.html) (hand-built interactive
mockup, not a build capture). Throughout this spec, every statement is tagged
with one of three provenance levels:

- **implemented in definition.xml (compiled at commit 577059e274; surface state unverified)** — the native file-widget theme
  declares it and the build contains it; the accepted run requested the opt-in,
  but no named component state is treated as rendered proof without a registered checkpoint;
- **prototype-only** — only the HTML mockup demonstrates it;
- **specified here, not yet implemented** — a target this spec sets that
  neither source currently contains.

## 1. Design principles

Derived directly from the goals and non-goals in
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md):

1. **One system, whole suite.** A single coherent visual and interaction system
   across Start Center, Writer, Calc, Impress, Draw, Base, and Math. Shared
   behaviour is implemented once in shared native layers (VCL, framework)
   before any application-local code. A Writer-only Material control is a
   design smell.
2. **Density is a feature.** Professional office work depends on speed and
   information density. Material hierarchy must improve scanning without
   inflating working space; mobile dimensions are never copied into desktop
   workflows wholesale.
3. **Accessibility, theming, and localization are first-class.** Light, dark,
   high contrast, display scaling, bidirectional text, and assistive-technology
   exposure are part of the initial design of every component, not follow-up
   themes.
4. **Chrome is independent of documents.** Document rendering and file-format
   behaviour never change as a side effect of chrome work.
5. **Nothing expert is removed.** Every existing command, shortcut, menu, and
   platform integration survives the redesign. Overflow is a designed state
   with stable keyboard order, not a place where controls disappear.
6. **Native only.** Product changes are C++ in VCL/framework/application code,
   UNO where required, and XML `.ui`/configuration resources. No web runtime
   enters the desktop GUI; HTML under `site/` serves documentation only.
7. **Honesty over optimism.** Exact-source build and light Start Center smoke
   evidence now exists, but the suite is not complete. No claim extends beyond
   the registered run and checkpoints in
   [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md).

## 2. The token model

Components consume **semantic roles, never literals**. A role names intent
(`primary`, `corner-control`, `size-standard-control`); a palette, renderer, or
density profile resolves the concrete value. The shared contract has four
families — color, shape, type, and metric — all implemented in
`definition.xml` (compiled at commit 577059e274; surface state unverified). Elevation, motion, spacing-scale, state-layer, and
layout token families are contract requirements from `MATERIAL_DESIGN.md` that
remain **specified here, not yet implemented** natively.

### 2.1 Color roles

The native `<palette>` sections declare 23 matched roles for light and dark
(implemented in definition.xml, compiled at commit 577059e274; surface state unverified). The native theme has **no**
high-contrast palette: when resolved high contrast takes precedence, native
code restores the captured platform `StyleSettings` baseline and bypasses
Material drawing entirely. The high-contrast column below therefore documents
only the prototype's `PAL.hc` mockup palette (prototype-only).

| Semantic role | Light | Dark | High contrast (prototype-only) | Prototype variable |
|---|---:|---:|---:|---|
| `primary` | `#6750A4` | `#D0BCFF` | `#3800A0` | `--p` |
| `on-primary` | `#FFFFFF` | `#381E72` | `#FFFFFF` | `--on-p` |
| `primary-container` | `#E8DEF8` | `#4F378B` | `#E4D6FF` | `--pc` |
| `on-primary-container` | `#1D192B` | `#EADDFF` | `#10004D` | `--on-pc` |
| `primary-hover` | `#D0BCFF` | `#4F378B` | `#280078` | `--p-hover` |
| `primary-pressed` | `#CCC2DC` | `#625B71` | `#1C0056` | `--p-pressed` |
| `primary-action-hover` | `#7965AF` | `#C4AEFF` | `#280078` | `--pa-hover` |
| `primary-action-pressed` | `#5B3F91` | `#B69DF8` | `#1C0056` | `--pa-pressed` |
| `surface` | `#FFFBFE` | `#141218` | `#FFFFFF` | `--surface` |
| `surface-container` | `#F3EDF7` | `#211F26` | `#FFFFFF` | `--sc` |
| `surface-container-low` | `#F7F2FA` | `#1D1B20` | `#F0F0F0` | `--scl` |
| `on-surface` | `#1D1B20` | `#E6E0E9` | `#000000` | `--on-s` |
| `on-surface-variant` | `#49454F` | `#CAC4D0` | `#141414` | `--on-sv` |
| `outline` | `#79747E` | `#938F99` | `#000000` | `--outline` |
| `outline-variant` | `#CAC4D0` | `#49454F` | `#000000` | `--outline-v` |
| `disabled-container` | `#E6E0E9` | `#36343B` | `#C4C4C4` | `--disabled` |
| `inverse-surface` | `#313033` | `#E6E0E9` | `#000000` | `--inv-s` (see note) |
| `inverse-on-surface` | `#F4EFF4` | `#322F35` | `#FFFFFF` | `--on-inv-s` |
| `warning-container` | `#FFDDB3` | `#5F4100` | `#FFE0A3` | `--warn` |
| `on-warning-container` | `#2A1800` | `#FFDDB3` | `#3A2500` | `--on-warn` |
| `error-container` | `#F9DEDC` | `#8C1D18` | `#FFD6D2` | `--err` |
| `on-error-container` | `#410E0B` | `#F9DEDC` | `#5A0000` | `--on-err` |
| `visited-link` | `#7D5260` | `#EFB8C8` | `#4A0052` | `--visited` |

Notes on deliberate divergences and prototype extras:

- **Inverse surface in dark mode.** The prototype's `--inv-s` is `#2B2930` in
  dark mode rather than the native dark `inverse-surface` (`#E6E0E9`): its
  control bar and snackbar remain dark chrome with light text in every theme,
  instead of following the MD3 light inverse-surface convention. This is
  recorded fidelity to the source design, not an oversight (prototype-only).
- **Base error.** The native palette declares no base `error` role, only
  `error-container`/`on-error-container`. The prototype adds `--err-base`
  (`#B3261E` light, `#F2B8B5` dark, `#B3000C` high contrast) for invalid-field
  strokes and error text on plain surfaces (prototype-only; a native base
  `error` role is specified here, not yet implemented).
- **Desktop and scrim.** `--desk` (`#E7E0EC` light, `#0B0A0E` dark, `#000000`
  high contrast) and `--scrim` (`rgba(20,18,24,.38)` light, `rgba(0,0,0,.6)`
  dark, `rgba(0,0,0,.65)` high contrast) are prototype presentation values with
  no native role.

### 2.2 Shape roles

Eight semantic corner radii, declared by the native `<shapes>` section
(implemented in definition.xml, compiled at commit 577059e274; surface state unverified). In drawing definitions,
`radius="@role"` resolves the role into both native rectangle radius axes; the
current definition contains 159 rounded rectangles consuming these roles and
11 deliberately square rectangles. Mixing `radius="@role"` with legacy numeric
`rx`/`ry` in one rectangle is rejected as ambiguous.

| Native role | Radius | Prototype variable | Canonical use |
|---|---:|---|---|
| `corner-checkbox` | `3` | `--r-check` | Checkbox box |
| `corner-indicator` | `4` | `--r-ind` | Small inner indicators (radio dot) |
| `corner-focus` | `6` | `--r-focus` | Focus outlines |
| `corner-small` | `8` | `--r-sm` | Small controls, menu items, toolbar buttons |
| `corner-control` | `10` | `--r-ctrl` | Standard controls (fields, radios) |
| `corner-container` | `12` | `--r-cont` | Containers, frames, popovers, cards |
| `corner-toolbar` | `18` | `--r-tb` | Toolbar-scale surfaces |
| `corner-pill` | `20` | `--r-pill` | Pill buttons, search fields, chips |

### 2.3 Typography roles

The native `<typography>` contract declares exactly three roles (implemented
in definition.xml, compiled at commit 577059e274; surface state unverified):

| Role | Relative height | Minimum-weight policy |
|---|---:|---|
| `body` | `100%` | `preserve` |
| `label` | `100%` | `medium` |
| `title` | `120%` | `semibold` |

The contract is **native-preserving**: a theme may request only a bounded
100–200% relative height and one of five bounded minimum-weight policies. It
cannot choose a font family. On every refresh the renderer derives each role
from the captured native `StyleSettings` baseline and preserves
script/language, charset, family, style, pitch, orientation, width, and
icon-font identity; scaling never reduces a positive native font height.
Weight is a minimum policy, not permission to replace the native font.

The prototype is not the native typography implementation: it illustrates
hierarchy with a browser stack (`Segoe UI Variable Text`, `Segoe UI`,
`system-ui`, `Roboto`, `sans-serif`) and component-local CSS font
declarations (prototype-only). Line-height and letter-spacing token roles for
the native side remain specified here, not yet implemented.

### 2.4 Metric roles

The native `<metrics>` section declares exactly 15 semantic integer roles
(implemented in definition.xml, compiled at commit 577059e274; surface state unverified). They centralize what were previously
331 repeated literals; the definition currently carries 346 metric references
(307 strokes, 34 part dimensions/margins, 5 settings). The native contract
preserves existing integer geometry and downstream unit conversions — it does
**not** itself add density selection, `dp`, fractional scaling, or a
comfortable/touch sizing policy.

| Category | Native role | Value | Purpose |
|---|---|---:|---|
| Stroke | `stroke-none` | `0` | No outline or track stroke |
| Stroke | `stroke-thin` | `1` | Thin borders and separators |
| Stroke | `stroke-standard` | `2` | Standard control, focus, and glyph strokes |
| Stroke | `stroke-track` | `4` | Slider track thickness |
| Spacing | `space-list-entry` | `12` | List-entry margin |
| Spacing | `space-tab-inline` | `12` | Inline tab-item margin |
| Title/preview | `height-floating-title` | `14` | Floating-window title height |
| Title/preview | `height-window-title` | `18` | Window title height |
| Title/preview | `size-list-preview` | `18` | List preview logic width and height |
| Control/tab | `size-menu-indicator` | `18` | Menu check/radio/submenu indicator |
| Control/tab | `size-tree-node` | `20` | Tree disclosure-node size |
| Control/tab | `size-selection-control` | `24` | Checkbox and radio control size |
| Control/tab | `size-compact-control` | `28` | Compact controls (slider buttons) |
| Control/tab | `size-standard-control` | `36` | Standard control size |
| Control/tab | `height-tab` | `40` | Tab-item height |

The 684 normalized fractional drawing coordinates inside component definitions
(for example the checkbox tick `x1="0.27" y1="0.52"`) remain component-local
by design: they describe proportional glyph and inset geometry, and naming
individual scalars would obscure the 45 complete coordinate patterns.

### 2.5 The 72-slot style bridge and settings

Between tokens and legacy VCL sits the `<style>` section: an exact mapping of
all 72 `StyleSettings` color slots onto semantic roles (implemented in
definition.xml, compiled at commit 577059e274; surface state unverified). Representative mappings:

| StyleSettings slot | Semantic role |
|---|---|
| `faceColor`, `dialogColor`, `menuBarColor`, `inactiveTabColor` | `@surface-container` |
| `windowColor`, `fieldColor`, `menuColor`, `listBoxWindowBackgroundColor` | `@surface` |
| `workspaceColor`, `alternatingRowColor` | `@surface-container-low` |
| `checkedColor`, `highlightColor`, `menuHighlightColor`, `activeTabColor`, `menuBarRolloverColor` | `@primary-container` |
| `highlightTextColor`, `menuHighlightTextColor`, `tabHighlightTextColor` | `@on-primary-container` |
| `activeColor`, `accentColor`, `linkColor`, `activeBorderColor` | `@primary` |
| `disableColor`, `deactiveColor` | `@disabled-container` |
| `deactiveTextColor`, `shadowColor` | `@outline` / `@outline` |
| `warningColor`/`warningTextColor` | `@warning-container`/`@on-warning-container` |
| `errorColor`/`errorTextColor` | `@error-container`/`@on-error-container` |
| `helpColor`/`helpTextColor` | `@inverse-surface`/`@inverse-on-surface` |

The ten feedback/selection fields added in the fifth milestone are optional in
the reader, so older or out-of-tree themes that omit them keep native values;
Material itself requires every slot. The `<settings>` block additionally fixes
`noActiveTabTextRaise="true"`, `centeredTabs="true"`, and binds
`listBoxEntryMargin` to `@space-list-entry`, `titleHeight` to
`@height-window-title`, `floatTitleHeight` to `@height-floating-title`, and
both list-box preview logic dimensions to `@size-list-preview` (implemented in
definition.xml, compiled at commit 577059e274; surface state unverified).

### 2.6 Token discipline and validation

Rules for every spec in this directory:

- reference roles, never raw hex or repeated integers, outside a designated
  token-reference table;
- new components must consume existing roles before proposing new ones; a new
  role requires light **and** dark values and a contrast-checked pairing;
- the standalone validator (source-only, covered by tests that have not
  executed) checks token discipline, the exact shape/metric/72-slot schemas,
  light/dark schema parity, unused roles, required control/state coverage
  (currently 79 parts and 205 states), list/selection/feedback contrast pairs,
  and native font/geometry-preservation invariants.

## 3. Theme resolution order

Resolution precedence, highest first (implemented in definition.xml and VCL
source, compiled at commit 577059e274; surface state unverified):

1. **High contrast.** Resolved high contrast takes precedence over everything.
   It **restores the captured native `StyleSettings`/framework baseline** and
   bypasses Material drawing in favour of native or generic fallback. Material
   never paints its own high-contrast approximation; the platform's
   forced-color rendering is the accessible baseline. Controls refresh
   native-focus suppression when the profile changes so generic fallback keeps
   a visible VCL focus indicator.
2. **Dark.** Source selects the dark `<palette scheme="dark">` from the
   resolved dark-mode signal. Headless VCL maps an explicit dark preference
   because it has no operating-system appearance signal.
3. **Light.** The default `<palette>`.

The whole routing is opt-in behind `VCL_DRAW_WIDGETS_FROM_FILE=1` plus
`VCL_FILE_WIDGET_THEME=material`, Windows printer graphics are excluded from
the initialization path, and unsupported file-theme parts retain existing
fallback drawing. Forced-color/platform signal completeness remains planned.

The prototype mirrors the same order as a manual three-way switch
(Light/Dark/High contrast) and adds two presentation rules of its own: in high
contrast every border widens from `--bw: 1px` to `--bw: 2px`, and a
`@media (forced-colors: active)` rule gives every hoverable control a
`1px solid ButtonText` border (both prototype-only). Its `PAL.hc` palette is a
mockup of what a forced-color platform would supply, not a native palette.

## 4. Elevation strategy

Elevation communicates containment and temporary overlap, and must never be
encoded only by a low-contrast shadow. The strategy is a triad, in priority
order:

1. **Borders.** Every raised or overlapping surface carries a `stroke-thin`
   outline in `@outline-variant` (or `@outline` for stronger separation). This
   is the only elevation channel the native definition currently implements —
   for example the outlined frame (`ControlType::Frame`/`Border`) is exactly
   `@outline-variant` stroke, `@surface-container` fill, `stroke-thin`,
   `corner-container` (implemented in definition.xml, compiled at commit 577059e274; surface state unverified). Borders
   survive high contrast; shadows do not.
2. **Tonal surfaces.** Containment is layered through the three surface roles:
   `@surface` (documents, menus, fields), `@surface-container` (chrome,
   dialogs, panels), `@surface-container-low` (workspace, alternating rows).
3. **Shadows.** The prototype adds soft shadows on genuinely overlapping
   surfaces (prototype-only; native shadow/elevation resolution is specified
   here, not yet implemented):

| Surface (prototype) | Shadow |
|---|---|
| Application window shell | `0 30px 70px rgba(0,0,0,.30), 0 6px 16px rgba(0,0,0,.16)` |
| Modal dialogs | `0 24px 64px rgba(0,0,0,.4)` |
| Menus and dropdowns | `0 12px 32px rgba(0,0,0,.24)` |
| Search/regex popovers | `0 16px 40px rgba(0,0,0,.28)` |
| Snackbar/toast | `0 10px 30px rgba(0,0,0,.4)` |
| Writer page on workspace | `0 4px 20px rgba(0,0,0,.10)` |
| Impress/Draw canvas | `0 8px 30px rgba(0,0,0,.16)` / `0 8px 30px rgba(0,0,0,.14)` |

Every shadowed surface above also has the border and tonal treatment, so
removing shadows (high contrast, reduced transparency, or a platform without
composited shadows) removes no information. Modal overlap additionally uses
the prototype scrim values listed in §2.1.

## 5. Motion principles

Motion explains continuity and state change; it never decorates routine
typing, selection, or document navigation, never blocks input, and must honour
reduced motion. Native duration/easing token roles are **specified here, not
yet implemented**; the values below are the prototype's working set
(prototype-only) and are the targets for the eventual native roles.

| Motion role (target) | Prototype value | Used for |
|---|---|---|
| Entrance, small overlay | `120 ms`, `ease`, `lo-pop` | Menus, dropdowns, search popovers |
| Entrance, large overlay | `160 ms`, `ease`, `lo-pop` | Dialogs, snackbar |
| State-color change | `120 ms` background/color transition | Segmented buttons, hoverable chrome |
| Transform slide | `150 ms` transform transition | Skip-link reveal, switch thumb |

The single entrance pattern `lo-pop` animates from
`opacity: 0; translateY(-4px) scale(.98)` to identity — a short fade-drop, no
bounce, no overshoot. Nothing animates on theme, density, or chrome switches;
the prototype re-renders instantly, and the native suite must do the same.

**Reduced motion mapping:** the prototype clamps every animation and
transition to `0.001 ms` under `@media (prefers-reduced-motion: reduce)` —
i.e. the reduced-motion variant of every transition is the completed end state,
immediately. The native mapping (specified here, not yet implemented) is
identical: when the platform reports reduced motion, all Material motion roles
resolve to zero duration; no motion is merely slowed or replaced with a
different effect.

## 6. Density model

Two intentional profiles per the contract: **compact** (keyboard/mouse, data
grids, expert workflows) and **comfortable** (touch, high zoom, larger
targets). Focus visibility and hit-area predictability may not vary between
profiles; only geometry does.

The prototype implements the model end to end (prototype-only):

| Variable | Compact | Comfortable | Governs |
|---|---:|---:|---|
| `--ctrl` | `34px` | `40px` | Standard control height |
| `--row` | `26px` | `32px` | Grid/list row height |
| `--tb` | `38px` | `48px` | Toolbar height |
| `--menu` | `30px` | `38px` | Menubar height |
| `--item` | `30px` | `40px` | Menu/list item height |
| `--fs` | `13px` | `14px` | Base font size |
| line height | `1.35` | `1.45` | Body line height |

Component-specific density rules exist where global padding would harm the
surface: the prototype's Calc column width is `76px` compact / `92px`
comfortable, and Calc's grid, Writer's rulers, and dense property panels get
per-component rules in their own spec files rather than inherited padding.

The native side deliberately does **not** yet have density: the 15 metric
roles of §2.4 centralize today's single-profile integer geometry
(`size-standard-control` `36`, `height-tab` `40`, `size-compact-control` `28`,
and so on) while preserving downstream native unit conversions. Mapping the
metric roles onto compact/comfortable variants — and any new DPI, `dp`,
zoom, or input-modality policy — is specified here, not yet implemented, and
must be verified separately once a build exists.

## 7. Adaptive layout

Window width, not device labels, drives layout. Shared chrome defines three
window classes — all specified here, not yet implemented natively; the
prototype renders a single desktop shell of `min(1200px, 97vw)` width and does
not yet demonstrate the narrower classes:

| Class | Target width range | Behaviour |
|---|---|---|
| Compact | under ~720 px | Sidebars collapse to rails/overlays; toolbars overflow into a designed overflow menu with stable keyboard order; dialogs go near-full-width (the prototype already caps dialogs at `min(680px, 94%)`) |
| Medium | ~720–1200 px | One docked sidebar at a time; toolbars overflow from the end; status bar drops low-priority panes |
| Expanded | ~1200 px and above | Full chrome: docked sidebars, complete toolbars, full status bar — the prototype's reference arrangement |

Rules that hold in every class: every command remains reachable (overflow is a
designed state, never silent removal); keyboard order is stable across
reflows; dialogs, sidebars, command surfaces, and localized labels get
narrow-window checks; multi-monitor placement, fractional scaling, and OS
insets are part of the desktop layout contract. The evidence scenario matrix
in [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) already
requires compact, medium, and expanded window cases per surface.

## 8. Iconography

Two pipelines, deliberately distinct:

**Prototype inline icons (prototype-only).** The mockup uses a self-contained
registry of line glyphs: a `24px` viewBox grid (`viewBox="0 0 24 24"`),
`fill="none"`, `stroke="currentColor"`, `stroke-width="2"`, round line caps
and joins. Icons are sized through font-size (default optical size `20px`;
`16`/`18` in dense chrome, `26` in the masthead) and inherit text colour, so
every state change is automatic and colour-independent. Icons are marked
`aria-hidden="true"`; the accessible name always lives on the host control.
Small filled details (menu dots, play glyph) opt in with explicit
`fill="currentColor" stroke="none"`.

**Native icons (target).** The real application uses the established
LibreOffice icon-theme pipeline and native raster/vector asset rules — the
prototype's inline-SVG approach is not the native mechanism. Requirements
carried over from the contract: consistent optical size, stroke, state, and
directionality; **semantic mirroring** — RTL mirroring is applied per glyph
meaning (chevrons, indent, undo/redo mirror; glyphs like search or warning do
not), never automatically to every icon; no externally hotlinked asset in a
build or the site; generated art is not accepted as runtime or evidence
imagery without an explicit reviewed asset decision. A Material line-icon
theme for the native pipeline is specified here, not yet implemented.

Menu and popup indicator glyphs drawn by the theme itself (checks, radio dots,
submenu arrows) are sized by `@size-menu-indicator` (`18`) and drawn with
`stroke-standard` strokes (implemented in definition.xml, compiled at commit 577059e274; surface state unverified).

## 9. Writing and terminology

- **Commands** use LibreOffice's established title-style capitalization and a
  trailing ellipsis when they open a dialog: `Open…`, `Save As…`,
  `Find & Replace…`, `Options…` (as in the prototype's menu data).
- **Shortcuts** are written with `+` and no spaces: `Ctrl+O`,
  `Ctrl+Shift+S`, `Alt+F12`, `Shift+F5`; function keys bare: `F5`, `F11`.
- **Window titles** follow `Document name — LibreOffice App` with a spaced em
  dash, e.g. `Q3 Board Report.odt — LibreOffice Writer` (prototype
  convention).
- **Product terms** keep upstream names: Start Center, sidebar, status bar,
  Notebookbar/ribbon chrome, sheet tabs. Do not invent Material-branded
  synonyms for existing LibreOffice concepts.
- **Spec prose** is British-neutral engineering language: no marketing, no
  superlatives.
- **Honesty vocabulary** is fixed: `site/prototype.html` is a *prototype* or
  *mockup*, never a *screenshot*; native work is *implemented source* before a
  build and *compiled; surface state unverified* after a build; *verified* is reserved for results registered under
  the evidence contract; the current registry is linked wherever completeness
  might otherwise be implied.
- **Errors** must identify both the problem and a recovery action (contract
  rule; see the feedback spec, [`07-feedback.md`](07-feedback.md)).

## 10. Verification hooks

Foundations are proved indirectly — every component capture exercises them —
plus the following dedicated checks, in the
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md) format. None have
run; the build blocker is recorded there.

1. **Validator run (headless, no GUI).** Execute the standalone validator
   against `definition.xml`: token discipline, shape/metric/72-slot schemas,
   light/dark parity, 79-part/205-state coverage, contrast pairs, and
   font/geometry-preservation invariants must pass at the recorded commit.
2. **Theme-resolution captures.** One representative surface (Start Center)
   captured under light, dark, and platform high contrast in the same run,
   launched with `VCL_DRAW_WIDGETS_FROM_FILE=1` and
   `VCL_FILE_WIDGET_THEME=material`. Checkpoints: dark palette selected from
   the resolved dark signal; high contrast shows the *native* baseline (no
   Material fills) with a visible focus indicator.
3. **Token spot-checks.** Pixel probes on accepted captures: pushbutton fill
   equals `@primary-container` (`#E8DEF8` light), field fill equals
   `@surface`, dialog face equals `@surface-container`; corner radii of a
   pill button and a container measure 20 and 12 device-independent pixels at
   100% scale.
4. **Scale matrix.** The same checkpoints at 100%, 125% (or platform
   fractional), and 200% display scale; typography roles must never render
   below the native baseline height.
5. **Motion/reduced-motion pair.** Once native motion exists: a normal run and
   a reduced-motion run of one menu open and one dialog open; the
   reduced-motion capture pair must show identical end states with no
   intermediate frames.
6. **Window-class checks.** Compact, medium, and expanded window captures per
   the scenario matrix, verifying overflow order and command reachability.

Each run records the manifest fields, run identity
(`YYYYMMDD-HHMMSS-<short-commit>-<platform>`), and capture-acceptance review
defined by the evidence plan. Until such runs exist, everything in this file
remains target design.
