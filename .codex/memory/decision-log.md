# Decision log

## D-001 — preserve the native LibreOffice stack

- Date: 2026-07-16
- State: accepted direction
- Decision: implement product UI in the languages and resource formats of the
  affected LibreOffice modules, primarily C++, VCL/UNO, and XML UI resources.
- Reason: the project objective is a native whole-suite rewrite, not a separate
  web application. The HTML/CSS site is documentation only.

## D-002 — shared primitives before application variants

- Date: 2026-07-16
- State: accepted direction
- Decision: establish semantic tokens and VCL components before migrating
  Writer, Calc, Impress/Draw, Base, Math, and remaining surfaces.
- Reason: suite consistency and accessibility cannot be maintained through
  duplicated application-local styling.

## D-003 — evidence slots remain empty until verified

- Date: 2026-07-16
- State: active policy
- Decision: the public gallery shows labeled empty slots and a count of zero
  until real build captures exist and pass the evidence contract.
- Reason: mock or generated images would overstate implementation progress.

## D-004 — use off-screen desktop automation for UI proof

- Date: 2026-07-16
- State: harness preflight verified; LibreOffice execution pending
- Decision: use `lowlevel-computer-use-mcp` to launch and interact with real GUI
  processes on Windows off-screen desktops or Linux Xvfb displays.
- Reason: repeatable captures should not take over the operator's desktop, and
  window identity plus run metadata must remain attributable.
- Observation: commit `806d9ba85e4afbc2af58d7499496babfa7c68891`
  successfully completed a Notepad-only create/enumerate/capture/cleanup
  preflight. That observation validates harness mechanics only and is excluded
  from LibreOffice Material evidence.

## D-005 — publish a dependency-free static project site

- Date: 2026-07-16
- State: deployed and verified
- Decision: serve `site/index.html` and `site/styles.css` directly through a
  GitHub Pages Actions workflow.
- Reason: a static artifact keeps deployment auditable, accessible, responsive,
  and independent of package registries or externally hotlinked assets.
- Verification: Pages run `29510014215` succeeded and the public index and
  stylesheet returned HTTP `200`.

## D-006 — retain explicit import provenance

- Date: 2026-07-16
- State: active policy
- Decision: distinguish the fork's new root import commit from the upstream
  commit even though their tree objects match.
- Reason: tree equivalence does not preserve or recreate upstream ancestry.

## D-007 — resolve semantic color roles inside the file-widget reader

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: let file-widget definitions declare named palette roles and use
  `@token` references, resolve them before style/action parsing regardless of
  declaration order, and reject malformed colors plus unknown or duplicate
  tokens and control parts.
- Reason: repeated literal colors make cross-suite light/dark/high-contrast
  evolution error-prone, while silently accepting malformed definitions can
  leave VCL callers on inconsistent partial themes.

## D-008 — preserve generic fallbacks when file geometry lacks semantics

- Date: 2026-07-16
- State: active policy
- Decision: do not claim file-widget support for controls whose current caller
  geometry cannot preserve meaning. `LevelBar`, `ListNet`, and Frame borders
  remain on existing fallback paths in this milestone.
- Reason: painting a generic filled level bar would erase its threshold colors,
  the current ListNet caller provides an empty region, and Frame requires a
  verified inner-content contract rather than a pass-through border rectangle.

## D-009 — resolve Material profiles after native settings

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: collect native platform settings first, resolve LibreOffice theme
  overrides, then select the file-widget profile with precedence high contrast
  over dark over light. High contrast restores the captured native framework
  settings and delegates to native controls or LibreOffice's generic drawing
  instead of applying fixed Material colors.
- Reason: accessibility and platform forced-color behavior must outrank brand
  palette selection, while shared immutable definitions keep every graphics
  instance on the same resolved profile.

## D-010 — give standalone spin controls explicit direction and geometry

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: define standalone spin-button parts explicitly as up, down, left,
  and right; draw composite controls into the two exact rectangles supplied by
  the caller; and treat horizontal increment as right and decrement as left.
- Reason: reusing vertical semantics or an enclosing rectangle would reverse
  horizontal meaning and could paint outside the caller-owned control regions.

## D-011 — make runtime profile transitions accessibility-safe

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: capture the resolved pre-Material `StyleSettings` and native widget
  framework values before applying the file theme, restore them before the next
  platform refresh, and recompute per-control native-focus suppression after
  profile changes. Detect Qt high contrast through proxy-style chains and honor
  explicit dark appearance in headless VCL, where no operating-system signal
  exists.
- Reason: switching to high contrast must not retain fixed Material colors or
  leave VCL focus indicators suppressed when drawing falls back to generic
  controls; the same precedence must be observable on Qt and headless paths.

## D-012 — make Material typography native-preserving

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: expose only `body`, `label`, and `title` roles with a 100–200%
  nonshrinking scale and a bounded minimum-weight enum. Do not expose font-family
  selection. Apply each role to a copy of its corresponding captured native
  font, leave icon fonts untouched, and derive repeat refreshes from the same
  native baseline.
- Reason: the prior renderer replaced platform, localized, CJK/CTL, and
  accessibility font choices with a fixed 10-point Liberation Sans font.
  Material hierarchy should alter declared size/minimum weight without erasing
  the operating system's font identity or compounding on menu refreshes.

## D-013 — isolate each Windows evidence driver session

- Date: 2026-07-16
- State: accepted test policy; LibreOffice execution pending
- Decision: use a short-lived low-level driver process/session per accepted
  Windows evidence run, prove window ownership through a unique PID file and
  exact fork executable path, shut down over a unique UNO pipe, and exit the
  driver before claiming off-screen desktop deletion.
- Reason: the long-lived server caches opened desktop handles,
  `close_headless_desktop` does not close applications, and enumeration does not
  report PID. Run isolation prevents stale handles or unrelated LibreOffice
  processes from being mistaken for a clean, attributable test.

## D-014 — close Material colors without breaking partial themes

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: map all 72 `StyleSettings` color slots in the Material definition,
  including accent, list-box collection/selection, alternating rows, and
  warning/error feedback. Represent the ten newly reader-addressable slots as
  optional colors and apply them only when declared. Require every slot and its
  exact semantic token in the Material validator, while leaving the general
  reader compatible with partial bundled and out-of-tree themes.
- Reason: unthemed collection and feedback colors make a light/dark Material
  profile visibly incoherent, but unconditionally applying default-constructed
  values would regress older definitions such as the partial iOS theme.

## D-015 — resolve semantic corners without changing rectangle ABI

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: define eight used, nonzero semantic corner roles in an optional
  root `shapes` section, resolve that section before drawing definitions, and
  let one `radius="@token"` reference populate both existing `mnRx` and `mnRy`
  fields. Keep the token map local to one reader invocation, reject mixed
  singular/legacy radius attributes, leave square rectangles attribute-free,
  and preserve the prior numeric `rx`/`ry` path for legacy and out-of-tree
  themes.
- Reason: 146 Material rectangles repeated 292 equal-axis radius attributes.
  Central roles remove that drift without growing the exported reader object or
  changing the draw-action/renderer ABI. A synthetic zero token would alter the
  existing implicit-square `-1` path, and strict parsing of old numeric values
  would create an unrelated compatibility break.
