# LibreOffice Material — full design specification

> **Status:** specification of the *target* design. The native suite is
> source-only and unbuilt; nothing in these documents is build- or
> runtime-verified, and the verified-capture count remains **0**. The
> normative contracts behind this spec are
> [`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (design contract),
> [`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
> [`vcl/uiconfig/theme_definitions/material/definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
> (implemented native token/part/state contract), and the interactive
> reference [`site/prototype.html`](../../site/prototype.html) (hand-built
> mockup, not a build capture).

This directory is the complete written design: foundations, every shared
component, and every application surface. Each component spec defines anatomy
and token use, the full state table, pointer/keyboard/screen-reader
interaction, accessibility exposure, compact/comfortable density values, RTL
and localization behavior, deliberate platform differences, and the
verification hooks that will later prove it against a real build. Each surface
spec defines layout and regions, chrome variants, key flows,
empty/loading/error states, adaptive width behavior, a keyboard map, and
verification checkpoints.

## Reading order

| # | File | Covers |
| --- | --- | --- |
| 01 | [Foundations](01-foundations.md) | Principles, token model, theme resolution, elevation, motion, density, adaptive layout, iconography |
| 02 | [Actions](02-actions.md) | Filled/tonal/outlined/text buttons, toolbar buttons, icon buttons, links, disabled affordances |
| 03 | [Selection](03-selection.md) | Checkbox, radio, switch, chips, selection conventions |
| 04 | [Inputs](04-inputs.md) | Text fields, edits, combos, spin buttons, search + regex builder, Find & Replace fields |
| 05 | [Navigation](05-navigation.md) | Menubar, menus, tabs, notebookbar, sidebar rail, sheet tabs, title/status bars |
| 06 | [Containers](06-containers.md) | Lists, trees, tables/grids, frames, scrollbars, cards, panels |
| 07 | [Feedback](07-feedback.md) | Progress, level indicators, sliders, tooltips, snackbars, banners, empty states |
| 08 | [Dialogs](08-dialogs.md) | Modal anatomy, Options, Save As, Print, Find & Replace, scrim and keyboard rules |
| 09 | [Start Center](09-start-center.md) | Navigation column, Home, search, document card grid |
| 10 | [Writer & Calc](10-writer-calc.md) | Page canvas, properties sidebar, formula bar, grid, sheet tabs |
| 11 | [Impress & Draw](11-impress-draw.md) | Slide panel, canvas, layouts, tool rail, object properties |
| 12 | [Base, Math & shared](12-base-math-shared.md) | Database shell, formula editor, Features catalog, history, suite-wide rules |

## How a spec becomes "done"

A component or surface graduates only through the verification gate in
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md): shared tokens and components
consumed, deterministic states for every input method, passing accessibility /
localization / scaling / theme matrices, performance within budget, and real
captures registered for an exact commit per
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md). Until then a spec
is a target, not a claim.
