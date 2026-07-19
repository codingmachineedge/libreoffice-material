# Material Design 3 token reference

## Overview

The LibreOffice Material theme and its interactive prototype consume design values through semantic roles, never through component-local literals. A role describes intent—such as `primary`, `corner-control`, or `size-standard-control`—so a palette, renderer, or density profile can resolve the concrete value for its context.

The shared contract has four token families:

- **Color:** semantic foregrounds, backgrounds, borders, feedback, and inverse surfaces.
- **Shape:** semantic corner radii for controls and containers.
- **Type:** native-preserving body, label, and title roles.
- **Metric:** semantic integer strokes, spacing, heights, and control sizes.

The authoritative native contract is `vcl/uiconfig/theme_definitions/material/definition.xml`. The browser reference in `site/prototype.html` mirrors that contract through shorter CSS custom properties and adds its own high-contrast palette and compact/comfortable density model. `MATERIAL_DESIGN.md` defines the native-preservation and verification boundaries.

## Color roles

The light and dark columns below use the native palette values from `vcl/uiconfig/theme_definitions/material/definition.xml` wherever that palette declares the role. The native definition has no Material high-contrast palette: when resolved high contrast takes precedence, native code restores the captured platform `StyleSettings` baseline and bypasses Material drawing. The high-contrast hex values shown here therefore document only `site/prototype.html`'s `PAL.hc` mockup palette.

| Semantic role | Light | Dark | High contrast (prototype only) | Prototype equivalent and notes |
|---|---:|---:|---:|---|
| `primary` | `#6750A4` | `#D0BCFF` | `#3800A0` | `--p` / `PAL.*.p` |
| `on-primary` | `#FFFFFF` | `#381E72` | `#FFFFFF` | `--on-p` / `PAL.*.onP` |
| `primary-container` | `#E8DEF8` | `#4F378B` | `#E4D6FF` | `--pc` / `PAL.*.pc` |
| `on-primary-container` | `#1D192B` | `#EADDFF` | `#10004D` | `--on-pc` / `PAL.*.onPc` |
| `surface` | `#FFFBFE` | `#141218` | `#FFFFFF` | `--surface` / `PAL.*.surface` |
| `surface-container` | `#F3EDF7` | `#211F26` | `#FFFFFF` | `--sc` / `PAL.*.sc` |
| `on-surface` | `#1D1B20` | `#E6E0E9` | `#000000` | `--on-s` / `PAL.*.onS` |
| `on-surface-variant` | `#49454F` | `#CAC4D0` | `#141414` | `--on-sv` / `PAL.*.onSv` |
| `outline` | `#79747E` | `#938F99` | `#000000` | `--outline` / `PAL.*.outline` |
| `outline-variant` | `#CAC4D0` | `#49454F` | `#000000` | `--outline-v` / `PAL.*.outlineV` |
| `error` | `#B3261E` | `#F2B8B5` | `#B3000C` | Prototype-only base error: `--err-base` / `PAL.*.errBase`. The native palette does not declare an `error` role; it declares `error-container` (`#F9DEDC` light, `#8C1D18` dark) and `on-error-container` (`#410E0B` light, `#F9DEDC` dark), exposed by the prototype as `--err` and `--on-err`. |
| `inverse-surface` | `#313033` | `#E6E0E9` | `#000000` | Native values are shown. Prototype `--inv-s` matches light (`#313033`) and uses `#000000` in high contrast, but deliberately uses `#2B2930` in dark mode: its control bar and snackbar remain dark chrome with light `--on-inv-s` text instead of following the MD3 light inverse-surface convention. |

The prototype's light and dark values otherwise match the corresponding native roles in this table. Its `--err` name is shorthand for the native `error-container`, not for the base `error` row.

## Shape roles

The eight radii are declared by the native `<shapes>` section in `vcl/uiconfig/theme_definitions/material/definition.xml`. `site/prototype.html` assigns the matching pixel values to its `--r-*` variables.

| Native role | Radius | Prototype variable |
|---|---:|---|
| `corner-checkbox` | `3px` | `--r-check` |
| `corner-indicator` | `4px` | `--r-ind` |
| `corner-focus` | `6px` | `--r-focus` |
| `corner-small` | `8px` | `--r-sm` |
| `corner-control` | `10px` | `--r-ctrl` |
| `corner-container` | `12px` | `--r-cont` |
| `corner-toolbar` | `18px` | `--r-tb` |
| `corner-pill` | `20px` | `--r-pill` |

In native drawing definitions, `radius="@role"` resolves the selected role into both native rectangle radius axes. The prototype uses the corresponding CSS variable anywhere CSS expects a `border-radius`.

## Typography roles

The native `<typography>` contract in `vcl/uiconfig/theme_definitions/material/definition.xml` declares three roles:

| Role | Relative height | Minimum-weight policy |
|---|---:|---|
| `body` | `100%` | `preserve` |
| `label` | `100%` | `medium` |
| `title` | `120%` | `semibold` |

As specified in `MATERIAL_DESIGN.md`, a theme may request only a bounded `100–200%` relative height and one of five bounded minimum-weight policies; it cannot choose a font family. Weight is a minimum policy, not permission to replace the native font identity. On every refresh the renderer derives each role from the captured native `StyleSettings` baseline and preserves script/language, charset, family, style, pitch, orientation, width, and icon-font identity. Scaling never reduces a positive native font height.

`site/prototype.html` is not the native typography implementation. It uses a browser font stack (`Segoe UI Variable Text`, `Segoe UI`, `system-ui`, `Roboto`, `sans-serif`) and component-local CSS font declarations to illustrate hierarchy.

## Metric roles

The native `<metrics>` section in `vcl/uiconfig/theme_definitions/material/definition.xml` declares exactly 15 semantic integer roles. They preserve the existing integer geometry and downstream native unit conversions; the native contract does not itself add density selection, `dp`, fractional scaling, or a comfortable/touch sizing policy.

| Category | Native role | Integer value | Purpose |
|---|---|---:|---|
| Stroke | `stroke-none` | `0` | No outline or track stroke. |
| Stroke | `stroke-thin` | `1` | Thin borders and separators. |
| Stroke | `stroke-standard` | `2` | Standard control, focus, and glyph strokes. |
| Stroke | `stroke-track` | `4` | Slider track thickness. |
| Spacing | `space-list-entry` | `12` | List-entry margin. |
| Spacing | `space-tab-inline` | `12` | Inline tab-item margin. |
| Title/preview | `height-floating-title` | `14` | Floating-window title height. |
| Title/preview | `height-window-title` | `18` | Window title height. |
| Title/preview | `size-list-preview` | `18` | Default list preview logic width and height. |
| Control/tab | `size-menu-indicator` | `18` | Popup-menu check, radio, and submenu indicator size. |
| Control/tab | `size-tree-node` | `20` | Tree disclosure-node size. |
| Control/tab | `size-selection-control` | `24` | Checkbox and radio control size. |
| Control/tab | `size-compact-control` | `28` | Compact controls such as slider buttons. |
| Control/tab | `size-standard-control` | `36` | Standard control size. |
| Control/tab | `height-tab` | `40` | Tab-item height. |

The prototype adds a separate browser-only density layer in `site/prototype.html`:

| Prototype density | `--ctrl` | `--row` | `--tb` | `--menu` | `--item` | `--fs` | Line height |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compact | `34px` | `26px` | `38px` | `30px` | `30px` | `13px` | `1.35` |
| Comfortable | `40px` | `32px` | `48px` | `38px` | `40px` | `14px` | `1.45` |

High-contrast prototype borders use `--bw: 2px`; light and dark use `--bw: 1px`. These density and border-width values are prototype presentation metrics, not additional native `<metrics>` roles.

## Native-to-prototype mapping

`site/prototype.html` selects `PAL.light`, `PAL.dark`, or `PAL.hc`, then exposes the palette through compact CSS variable names. The main correspondences are:

| Native contract role or family | Prototype CSS variable |
|---|---|
| `primary`, `on-primary` | `--p`, `--on-p` |
| `primary-container`, `on-primary-container` | `--pc`, `--on-pc` |
| `surface`, `surface-container`, `surface-container-low` | `--surface`, `--sc`, `--scl` |
| `on-surface`, `on-surface-variant` | `--on-s`, `--on-sv` |
| `outline`, `outline-variant` | `--outline`, `--outline-v` |
| `inverse-surface`, `inverse-on-surface` | `--inv-s`, `--on-inv-s` (with the deliberate dark `--inv-s` divergence described above) |
| `warning-container`, `on-warning-container` | `--warn`, `--on-warn` |
| `error-container`, `on-error-container` | `--err`, `--on-err` |
| Eight `corner-*` roles | Eight `--r-*` variables listed in the shape table |
| Native integer metrics | Semantic native `@role` references; the prototype instead resolves its separate `--ctrl`, `--row`, `--tb`, `--menu`, and `--item` density variables |

Components in both surfaces should refer to these semantic names. Literal palette colors, radii, or repeated native geometry belong in the relevant contract or palette definition, not in an individual component.

## Honesty and verification status

This page documents the token contract present in source. It does not establish application runtime behavior. Required current-source native C++ targets and the Windows installation-set build have completed, while the verified-capture count remains **0**. The interactive surface in `site/prototype.html` is a hand-built HTML mockup, not a screenshot of a compiled LibreOffice build.

Those limits match the implementation status recorded in `MATERIAL_DESIGN.md`: validators and focused native tests describe invariants, but no application execution, screenshot, accessibility result, or runtime capture is claimed here.
