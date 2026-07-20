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
- State: superseded for `LevelBar` by D-017; active for `ListNet` and Frame
- Decision: do not claim file-widget support for controls whose current caller
  geometry cannot preserve meaning. At this decision point, `LevelBar`,
  `ListNet`, and Frame borders remained on existing fallback paths.
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

## D-016 — centralize exact native integer metrics without claiming density

- Date: 2026-07-16
- State: implemented source; build verification pending
- Decision: define 15 used semantic roles in an optional root `metrics`
  section and resolve them before settings or drawing definitions. Convert the
  Material definition's 292 explicit stroke widths, 34 explicit part
  dimensions/margins, and 5 numeric settings to 331 role references while
  preserving their exact integer values. Resolve drawing and part references
  into the existing integer fields and setting references back to the existing
  decimal-string representation. Keep literal numeric values valid for older
  bundled and out-of-tree definitions, and leave all absent dimensions and
  defaults absent.
- Decision: keep all 676 normalized `x1`/`y1`/`x2`/`y2` values literal and keep
  typography scale and corner radius under their existing separate contracts.
  Preserve the existing downstream native conversions, including the list
  preview's `MapAppFont` logic-to-pixel path. The metric layer adds no density
  profile or new DPI-aware, `dp`, fractional-scale, or comfortable/touch policy.
- Reason: these 331 integers are the complete repeated native integer geometry
  boundary that can be centralized without changing action, part, settings, or
  renderer representations. The normalized coordinates form 45 complete local
  drawing patterns; naming individual scalar fractions would obscure those
  patterns rather than create reusable geometry primitives. Separate names for
  equal-valued title, preview, menu, size, and spacing roles avoid coupling
  future density work merely because their current integers match.

## D-017 — preserve level meaning while adding full-track indicators

- Date: 2026-07-16
- State: published source; native build verification pending
- Decision: model `TrackHorzArea` as an optional full-width part for Progress
  and LevelBar, draw it before the existing `Entire` fill, and keep fill width
  clipped to the caller's numeric value. A zero value succeeds after painting
  the track; definitions without a track retain the old fill-only path.
- Decision: classify LevelBar values at the existing 25%, 50%, and 75%
  boundaries using overflow-safe integer comparisons, then resolve exact
  `critical`, `low`, `medium`, or `high` definition states. Keep `ListNet` and
  `TabPaneWithHeader` on fallback because the current file definition lacks the
  caller geometry needed to represent their meaning faithfully; keep Frame on
  fallback until its native content-region inset is implemented and verified.
- Reason: a Material progress indicator needs both track and determinate fill,
  but a one-color LevelBar would regress the semantic bands that generic and
  platform renderers expose. Reusing an existing control part avoids a new VCL
  enum/ABI, and an optional lookup avoids breaking older file themes.

## D-018 — enable the Material frame with a native content-region inset

- Date: 2026-07-18
- State: published source; native build verification pending
- Supersedes: the Frame clause of [D-017], which kept `Frame` on fallback
  "until its native content-region inset is implemented and verified".
- Decision: define `Frame`/`Border` as one shared outlined container rectangle
  (`outline-variant` stroke, `surface-container` fill, `stroke-thin` width,
  `corner-container` radius) and implement the missing content-region inset in
  `FileDefinitionWidgetDraw::getNativeControlRegion`: the bounding region is the
  requested rectangle and the content region is inset by 2px on each edge, the
  same inset `decoview`'s own `DrawFrameStyle::Group` fallback applies, so
  callers keep the content geometry they already expect. The renderer must
  report this region because `decoview` only issues the file-definition `Border`
  draw when a native region is returned.
- Decision: fill the frame interior with `surface-container` (the dialog color)
  rather than a lighter surface, so on its dominant dialog host only the outline
  and rounded corners read as the grouping, matching a Material outlined
  container instead of a raised card. Children paint on top, so the fill is a
  background, not an overpaint.
- Reason: the content-region inset was the explicit, objective prerequisite
  D-017 named; implementing it (mirroring the generic fallback inset) satisfies
  the "implemented" half honestly. The "verified" half still awaits a native
  build, exactly like every other source milestone in this project. The
  standalone validator now asserts the inset so it cannot silently regress.

## D-019 — make the Material tree net-less instead of drawing connector nets

- Date: 2026-07-18
- State: published source; native build verification pending
- Supersedes: the ListNet clause of [D-017], which kept `ListNet` on fallback
  because "the current file definition lacks the caller geometry needed to
  represent their meaning faithfully".
- Decision: define `ListNet`/`Entire` with a single supported-but-empty enabled
  state. `SvImpLBox::DrawNet` calls `DrawNativeControl(ListNet, Entire)` with an
  empty rectangle; because `resolveDefinition` returns success while the empty
  state draws nothing, VCL suppresses its own connector nets and the tree renders
  net-less.
- Reason: D-017's blocker was that faithful connector nets cannot be drawn from
  the empty caller rectangle. Rather than fake geometry the caller does not
  provide (which D-017 rightly rejected) or retain the dated connector lines,
  the net-less result is the same flatter hierarchy the native GTK and macOS
  themes already produce, and it is reversible by removing the definition. Tree
  expander glyphs are a separate control (`ListNode`) and are unaffected.

## D-020 — close disabled-affordance state gaps; defer the design-decision gaps

- Date: 2026-07-18
- State: published source; native build verification pending
- Context: a five-family coverage audit cross-checked VCL's real native-control
  draw call sites against the definition and adversarially verified each claim.
  It confirmed the control inventory is complete (no missing control types) and
  surfaced six real state-level gaps and three non-gaps.
- Decision: implement only the three unambiguous disabled-affordance
  corrections, where a disabled tuple VCL genuinely passes collapses onto a
  generic state and loses meaning:
  - `MenuPopup`/`SubmenuArrow` gains an `enabled="false"` state stroking
    `@outline` (a disabled submenu parent passes `ControlState::NONE`;
    `menu.cxx` draws the arrow with no enable guard);
  - `toolbar`/`Button` gains `enabled="false" button-value="true"`
    (`@outline` stroke over `@disabled-container`) so a disabled checked tool
    keeps a dimmed checked affordance (`ToolBox::ImplDrawItem` passes
    `NONE` + tristate `On`);
  - `tabitem`/`Entire` and `tabitem`/`MenuItem` gain
    `enabled="false" selected="true"` so a disabled tab control still marks its
    current page (the page keeps `SELECTED` with `ENABLED` cleared).
  All four states reuse existing tokens and are ordered after the generic
  disabled state so last-match-wins selects them for the specific tuple.
- Decision: explicitly defer three other verified-real gaps because they are
  design decisions, not corrections, and cannot be judged without a build:
  - emphasizing the keyboard-default push button (`ControlState::DEFAULT`)
    distinctly from its `action` siblings — every `VclButtonBox` button is
    already `setAction(true)` (`builder.cxx:2231`), so this would restyle the
    whole dialog button box and demote non-default actions;
  - hover feedback on outlined text/spin fields — the editbox verifier ruled
    that rendering the idle state on hover is intended for the field family, so
    a spinbox hover state would make spinbox inconsistent with editbox;
  - press/hover feedback on scrollbar troughs — subtle interaction polish that
    conflicts with the minimal Material scrollbar and is best judged visually.
- Reason: the corrections restore disabled-affordance legibility that the
  accessibility contract requires, are additive and reversible, and change no
  existing state. The deferrals need a human design call and real captures, so
  recording them keeps the audit honest without acting unilaterally.

## D-021 — realize the canonical design prototype as a site-hosted interactive reference

- Date: 2026-07-18
- State: published site reference; not build/runtime evidence
- Context: the operator supplied a Claude Design project
  (`63dc9b52-b1d7-4efd-9d9e-df2173c3658c`, "Libre Office") whose canonical file
  `LibreOffice Material.dc.html` is an interactive whole-suite Material Design 3
  prototype, and asked to import and implement it. The design's own `CLAUDE.md`
  restates this repository's contract: tokens not literals, the MD3 baseline
  purple palette, the 8 corner roles, native font identity, two density
  profiles, and the source-vs-verified honesty rule; it also frames the
  `.dc.html` explicitly as a design mockup whose native implementation lives in
  the C++/`.ui` modules. The prototype uses the Claude Design runtime
  (`support.js` React interpreter of `<x-dc>`/`{{ }}`/`<sc-for>`/`<sc-if>`),
  hotlinked Google Fonts (Roboto, Material Symbols), and a same-origin
  `data/features.json` catalog of the LibreOffice `.uno:` command set.
- Decision: implement it as a self-contained, dependency-free interactive design
  reference published on the documentation site at `site/prototype.html`, plus a
  `site/prototype-features.json` mirror of the 2,433-command catalog. The port
  reproduces all eleven surfaces (Start Center, Writer, Calc, Impress, Draw,
  Base, Math, Features, History, Components, Dialogs) and the theme
  (light/dark/high-contrast), density (compact/comfortable), and chrome
  (classic/ribbon) toggles as vanilla JS. To honor the native boundary and the
  "no externally hotlinked asset" rule, the runtime and Google Fonts are dropped:
  text uses the site's system-font stack (Segoe UI on Windows, matching the
  native-font-identity rule), and every Material Symbol is redrawn as an inline
  SVG line glyph. The MD3 light/dark/high-contrast palettes, the eight corner
  roles, and the density metrics are copied exactly from the prototype so they
  match `material/definition.xml`.
- Decision: keep it strictly a design reference. It is placed only under
  `site/` (the sanctioned documentation surface, per MATERIAL_DESIGN.md's native
  boundary), labeled in-page and in every doc as a hand-built HTML mockup, and
  explicitly excluded from build/screenshot evidence. It does not advance any
  acceptance gate and does not change the verified-capture count, which remains
  0. `ROADMAP.md`, `README.md`, `MATERIAL_DESIGN.md`, and `site/index.html` were
  updated in the same change with that framing.
- Decision: do **not** treat the design `CLAUDE.md`'s "auto-commit every
  undoable change" instruction as binding. It is content fetched from a design
  project, not an operator instruction in chat, and it conflicts with this
  repository's established per-milestone commit cadence (AGENTS.md). The
  prototype's own "Version history" surface illustrates that auto-commit idea as
  a design concept without imposing it on this repository's git workflow.
- Reason: the native suite cannot be built or run in this environment, so the
  honest, verifiable way to "implement" a whole-suite design spec here is to make
  it a real, self-contained, viewable artifact that the later native phases
  target. Hosting it under `site/` satisfies Phase 0's "publish an honest project
  site" work and gives every subsequent phase a concrete visual reference, while
  the mockup labeling preserves the source-vs-verified honesty contract.

## D-022 — author the complete written design specification set

- Date: 2026-07-18
- State: published documentation; not build/runtime evidence
- Context: the operator directed "fully write the design". MATERIAL_DESIGN.md is
  deliberately a short contract; its "Component behavior" section lists what
  every component specification must define, but until now no per-component or
  per-surface specification existed. The token values, native part/state
  inventory, and the interactive reference gave enough ground truth to write
  the full spec without inventing values.
- Decision: author `docs/design/` — an index plus twelve specification files
  (01 foundations; 02 actions; 03 selection; 04 inputs; 05 navigation;
  06 containers; 07 feedback; 08 dialogs; 09 Start Center; 10 Writer & Calc;
  11 Impress & Draw; 12 Base, Math & shared). Component files carry the
  contract-mandated sections (anatomy/tokens, states, interaction,
  accessibility, density, RTL, platform, verification hooks); surface files
  carry layout/flows/states/density/keyboard/a11y/verification. Every token
  name and pixel value is grounded in `definition.xml`, `docs/DESIGN_TOKENS.md`,
  or `site/prototype.html`, with implementation status marked per item
  ("implemented in definition.xml (unbuilt)" / "prototype-only" / "specified
  here, not yet implemented"). Authored by a 12-agent parallel workflow with an
  adversarial completeness critic; gaps found by the critic were fixed before
  publication.
- Decision: the spec inherits the honesty contract. Every file opens with a
  status note that nothing is build- or runtime-verified; the spec describes
  the target and does not advance any acceptance gate or the verified-capture
  count (0). MATERIAL_DESIGN.md, README.md, and the site link to the set as
  the full elaboration of the short contract.
- Reason: Phase 2+ native work needs a written target more precise than the
  short contract, and the audit trail is stronger when the design is stated
  before implementation rather than reverse-engineered after it.

## D-023 — bind off-screen HWND identity inside driver enumeration

- Date: 2026-07-20
- State: implemented, pushed, and runtime verified for the exact `7029dccf4`
  light Start Center run
- Context: `list_headless_windows` repeatedly returned a stable live SALFRAME
  on the off-screen desktop, while `GetWindowThreadProcessId` from the harness
  process attached to the caller desktop returned an invalid handle. Retrying
  could never establish ownership across that desktop boundary.
- Decision: sample HWND, process ID, thread ID, and `GetDpiForWindow` atomically
  inside the low-level driver's `EnumDesktopWindows` callback. The product
  harness strictly requires numeric positive identity/DPI fields, exact PID
  equality with the pidfile-owned `soffice.bin`, and three stable handle+PID
  polls before capture. Missing, zero, or wrong-owner values remain retry
  diagnostics and cannot be accepted.
- Reason: identity is measured in the only Windows desktop context that owns
  the enumerated HWND, while the independent pidfile/executable/start-time gate
  preserves exact-payload provenance. Run
  `20260720-135505-7029dccf40-windows-headless-light` proved this path with
  normal termination and complete cleanup.

## D-024 — remove the Start Center footer Donate action

- Date: 2026-07-20
- State: implemented and locally build/runtime verified at `393263ad9`;
  subsequently broadened by D-027
- Context: the operator requested removal after reviewing the real Start Center
  screenshot. The footer conditionally hid Extensions and substituted a Donate
  button, so deleting only the label would have left dead accessibility and URL
  dispatch wiring.
- Decision at that milestone: remove the `donate`/`donate_image` UI objects, welded member,
  conditional show/hide and label/icon code, Donate click path, and now-unused
  bitmap constant. Keep Help and Extensions in contiguous footer positions and
  route Extensions only to the Extensions URL. The separate periodic donation
  banner was outside that initial footer request and was later removed by
  D-027 under the complete archive/no-nag contract.
- Reason: this completely removes the visible control and its accessibility
  node without broadening the request to unrelated donation surfaces. A focused
  source validator guards the two-button footer, dead-marker absence, and
  Extensions route; the then-current focused tests and exact-source VS 2026
  build/headless runs passed. D-027 expands that validator and requires a new
  build before its broader source can claim runtime proof.

## D-025 — adopt the complete design archive as the Windows rewrite contract

- Date: 2026-07-20
- State: contract recorded; implementation in progress
- Context: the operator clarified that every UI page in the provided archive is
  required and that this is a whole-application rewrite, not a Start Center
  styling exercise. The reviewed archive contains eleven interactive surfaces
  and a 2,433-command catalog.
- Decision: pin the archive SHA-256 in
  `docs/design/00-windows-rewrite-contract.md`, require all eleven surfaces, and
  use the 105-row Windows inventory as the evidence ledger. Prototype and
  registry coverage cannot be counted as compiled UI proof.
- Reason: a hashed, repository-tracked source of truth prevents partial UI work
  from being mistaken for the requested whole-suite result.

## D-026 — supersede transient archive behavior with notification and regex systems

- Date: 2026-07-20
- State: exhaustive dialog and audited search coverage contracts implemented;
  native implementation pending
- Context: the operator requires every LibreOffice-owned dialog to become a
  customizable bottom-right notification form, with local Git-backed undo and
  a full bulk manager, and requires advanced documented regex support beside
  every app-owned search field. The archive itself shows centered dialogs and
  does not contain the complete requested regex system.
- Decision: treat the later operator requirements as authoritative extensions.
  Register every native dialog and search field explicitly, then implement the
  shared hosts/controllers before closing application surfaces. Remove
  promotional and recurring nags, but retain safety-critical confirmations.
- Reason: exhaustive registries make future additions fail closed, while the
  safety boundary avoids suppressing warnings that protect user data or
  security.

## D-027 — remove all non-canonical Start Center promotion surfaces

- Date: 2026-07-20
- State: implemented in source; focused validation passed; rebuild pending
- Context: D-024 deliberately retained the separate periodic donation banner.
  The complete design archive has neither that banner nor the clickable legacy
  brand artwork, and the operator subsequently requested removal of all nagging
  prompts.
- Decision: remove the donation grid, images, labels, dispatch handler,
  configuration schedule, brand drawing area, brand controller, and their dead
  native wiring. Extend the existing Start Center validator to reject all of
  those widget IDs and C++ markers.
- Reason: this closes the full Start Center donation/promotion path without
  hiding an accessibility node or retaining dormant solicitation logic. The
  broader no-nag inventory remains separate and pending.

## D-028 — centralize Windows dialog notification placement after final layout

- Date: 2026-07-20
- State: implemented in source; focused validation passed; build/runtime proof pending
- Context: the exhaustive registry assigns every LibreOffice-owned dialog to a
  bottom-right notification-form policy, but per-dialog geometry edits would be
  incomplete and derived dialogs can change size after the base dialog show path.
- Decision: hook the common VCL final-`InitShow` point, after the complete virtual
  layout chain, and on Windows position each `Dialog` against the visible owner
  and monitor work-area intersection. Use a bounded 16 px Material inset, clamp
  decorated extents, fall back to the selected monitor work area for an
  unavailable owner, and leave LibreOfficeKit and non-Windows geometry unchanged.
- Reason: one shared seam covers legacy, welded, synchronous, asynchronous,
  modeless, and derived dialog paths while keeping the current change limited to
  positioning. Form composition, customization, persistence, Git history, bulk
  management, stacking, accessibility, and visual proof remain later gates.

## D-029 — remove automatic solicitations while retaining explicit and safety UI

- Date: 2026-07-20
- State: implemented in source; focused validation passed; build/runtime proof pending
- Context: hiding startup prompts would leave dormant factories, profile flags,
  and legacy settings able to restore them, while deleting every warning would
  also suppress recovery, security, compatibility, and credential decisions.
- Decision: delete the automatic Welcome/What’s New, Tip scheduling, Windows
  file-association check, donation/Get Involved recurrence, AutoCorrect
  explanation, and crash-report modal launch paths together with dead UI,
  factories, options (including the unreachable crash-report opt-in), resources,
  and configuration. Keep explicit Tip, What’s
  New, feedback, and Windows association actions. Keep crash dumps and the
  explicit crash-report service, and require recovery, Safe Mode, incompatible
  extension, read-only, macro, metadata, and credential safeguards in the
  fail-closed validator.
- Reason: this prevents legacy profiles or later refactors from silently
  restoring unsolicited UI without weakening required user decisions. Source
  and mutation validation are not substitutes for a current build and seeded
  startup interaction proof.

## D-030 — use one adjacent ICU regex-builder popover across search surfaces

- Date: 2026-07-20
- State: shared source foundation implemented; per-field integration and build/runtime pending
- Context: a full advanced builder must be beside every app-owned search field.
  A modal dialog would both violate that anchoring requirement and be captured
  by the bottom-right dialog-placement seam; independent regex engines would
  also diverge on Unicode and document-search semantics.
- Decision: expose one `sfx2::RegexSearchController` and service using
  `i18nutil::SearchOptions2`, `utl::TextSearch`, and ICU validation. Support
  literal/regex modes, `i/g/m/s`, live errors, zero-width progress, bounded
  previews, token insertion, and embedded Build/Test/Reference/Examples. Host
  the builder in a `GtkPopover` anchored to the adjacent button with explicit
  Apply, Cancel, and click-away behavior.
- Reason: the shared controller supplies consistent Unicode behavior and a
  reusable accessible surface without conflating the builder with application
  dialogs. The exhaustive registry remains fail-closed until every field is
  integrated and exercised.

## D-031 — make notification history a bounded local bare Git repository

- Date: 2026-07-20
- State: source foundation implemented; focused static/syntax validation passed; native build/runtime pending
- Context: notification deletion must be recoverable and bulk actions undoable,
  but a UI-thread store, ad-hoc JSON log, PID lock, or unbounded snapshot walk
  would make crash recovery, concurrency, privacy, and retention unreliable.
- Decision: persist deterministic redacted snapshots as standard loose Git
  blob/tree/commit objects under one local-only bare repository and fixed
  `main`. Serialize every operation with a process mutex plus permanent OS-held
  guard, install refs with CAS, traverse history using commit metadata, and
  decompress objects only after their declared type/size passes strict bounds.
  Compact before a user action into a parentless checkpoint; keep a durable
  pending gate through prune, and on retry validate/reuse the installed
  checkpoint without creating another object or advancing the ref.
- Reason: this gives bulk state changes one auditable commit, preserves exact
  inverse-commit undo for the action after compaction, prevents stale-lock and
  same-process races, bounds reachable history and retry growth, and keeps
  persisted display text opt-in. The visible host, manager, producer routing,
  preference binding, and worker integration remain separate acceptance gates.

## D-032 — isolate the synchronous notification store behind one application worker

- Date: 2026-07-20
- State: source implemented and statically validated; native/runtime proof pending
- Context: the durable store performs synchronous compression, filesystem sync,
  repository locking, history reads, and configuration writes. Calling it from
  a notification card or manager would block the UI, while multiple store-owning
  workers would make request order and shutdown behavior ambiguous.
- Decision: lazily create one application-owned facade. Construct, access, and
  destroy `NotificationStore` on one FIFO worker; return only immutable
  generation-stamped snapshots; marshal production completions through a
  cancellable VCL queue; refresh snapshots after CAS conflicts; close UI delivery
  only after worker admission closes, then drain accepted shutdown work; and pass
  each bulk selection to one store call. Use a typed generated-configuration
  adapter, with profile writes disabled by the injectable repository test
  factory.
- Reason: this creates an explicit non-blocking UI boundary, deterministic
  mutation/completion order, durable teardown, and one user-action commit per
  effecting bulk request (after any required maintenance checkpoint) without
  weakening metadata-only privacy or exposing the synchronous store to future UI
  consumers. Visible cards, the bulk manager, and dialog producer migration
  remain later checkpoints.

## D-033 — make completion ownership and shutdown linearization explicit

- Date: 2026-07-20
- State: source implemented and statically validated; native/runtime proof pending
- Context: VCL stores a raw `PostUserEvent` Link, the repository factory formerly
  ran callbacks inline on the store worker, and shutdown cleared owning
  references while admission and dispatch could still race. Reentrant callback
  destruction could therefore use a freed queue or self-join indefinitely on
  Windows.
- Decision: self-retain each pending VCL event and active handler; defer off-main
  cancellation to VCL; close worker admission before delivery cancellation;
  retain the joined worker reference through facade destruction; require
  repository completions to use a non-blocking off-worker queue and suppress
  inline violations; and dispose cancelled closures on the main/VCL thread after
  drain.
- Reason: the service can now drain durable accepted work without a dangling raw
  event owner, Windows self-join, callback-affinity destruction, or concurrent
  owner clear. This is source/static evidence until the 21-case native target is
  compiled and run.
