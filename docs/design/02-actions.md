# 02 — Actions

> **Status:** Specification of target design — native implementation per
> [ROADMAP.md](../../ROADMAP.md). Required native definition/dispatch targets
> have compiled and executed. Accepted light, dark, and forced-high-contrast
> Start Center runs show the Open File action and one visible Tab-focus
> checkpoint whose bounded UNO tree identifies `Open File` as the sole focused
> push button. Other actions, state matrices, and component pixels in this
> chapter remain unverified.

This chapter specifies every command-invoking control: push buttons (filled,
tonal, outlined, text), toolbar buttons, icon buttons, split/combo command
buttons, hyperlinks, and the Start Center primary "Open File" action. Normative
sources are the design contract
([MATERIAL_DESIGN.md](../../MATERIAL_DESIGN.md)), the token reference
([DESIGN_TOKENS.md](../DESIGN_TOKENS.md)), the implemented native contract
([definition.xml](../../vcl/uiconfig/theme_definitions/material/definition.xml)),
and the interactive reference ([prototype.html](../../site/prototype.html)).
Each statement is tagged with its implementation status: *implemented in
definition.xml (compiled at commit 577059e274; surface state unverified)*, *prototype-only*, or *specified here, not yet
implemented*. These labels describe source provenance; runtime evidence is
called out separately and never inferred from compilation or dispatch tests.

## Token quick reference

Semantic roles used throughout this chapter. Raw hex appears only in this
table; all component rules below use role names.

| Role | Light | Dark | Use in this chapter |
| --- | ---: | ---: | --- |
| `@primary` | `#6750A4` | `#D0BCFF` | Filled-button face, selected/checked strokes, focus ring, link colour |
| `@on-primary` | `#FFFFFF` | `#381E72` | Filled-button label |
| `@primary-container` | `#E8DEF8` | `#4F378B` | Tonal-button face, hover fills |
| `@on-primary-container` | `#1D192B` | `#EADDFF` | Tonal-button label, hover label |
| `@primary-hover` / `@primary-pressed` | `#D0BCFF` / `#CCC2DC` | `#4F378B` / `#625B71` | Tonal hover/pressed fills |
| `@primary-action-hover` / `@primary-action-pressed` | `#7965AF` / `#5B3F91` | `#C4AEFF` / `#B69DF8` | Filled (action) hover/pressed fills |
| `@outline` | `#79747E` | `#938F99` | Outlined-button border, disabled glyphs, disabled-checked outline |
| `@outline-variant` | `#CAC4D0` | `#49454F` | Separators, weakest disabled strokes |
| `@disabled-container` | `#E6E0E9` | `#36343B` | All disabled faces |
| `@surface-container` | `#F3EDF7` | `#211F26` | Toolbar/idle toolbar-button face |
| `@visited-link` | `#7D5260` | `#EFB8C8` | Visited hyperlinks |

Shape and metric roles: `corner-pill` (20), `corner-toolbar` (18),
`corner-control` (10), `corner-small` (8), `corner-focus` (6),
`corner-indicator` (4); `stroke-thin` (1), `stroke-standard` (2),
`size-compact-control` (28), `size-standard-control` (36). All are declared in
the native `<shapes>`/`<metrics>` sections (implemented in definition.xml,
compiled at commit 577059e274; surface state unverified). The prototype adds a browser-only density layer with control height
`--ctrl` = 34 px compact / 40 px comfortable.

---

## 1. Push buttons (filled, tonal, outlined, text)

### 1.1 Anatomy & tokens

A push button is a single pill container plus a label; optionally a leading
icon. Regions:

| Region | Token consumption |
| --- | --- |
| Container | Variant fill/stroke (table below); `radius="@corner-pill"`; `stroke-width="@stroke-thin"` |
| Label | `label` typography role (100 % native height, minimum-weight `medium`); variant text colour from the `<style>` button slots |
| Focus ring | `pushbutton`/`Focus` part: four `@primary` lines at `stroke-standard` inset 4 % from each edge (normalized `0.04–0.96`) — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

The four MD3 variants map onto the native `pushbutton`/`Entire` states as
follows. VCL distinguishes an *action* button (dialog button-box members are
`setAction(true)`) from an ordinary button and from a *flat* button; the
Material definition assigns filled treatment to `extra="action"`, tonal to the
plain state, and text to `extra="flat"`.

| Variant | Native state selector | Face | Label colour (`<style>`) | Status |
| --- | --- | --- | --- | --- |
| **Filled** | `extra="action"` | fill+stroke `@primary` | `actionButtonTextColor` = `@on-primary` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| **Tonal** | (no `extra`) | fill+stroke `@primary-container` | `buttonTextColor` = `@on-primary-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| **Text** | `extra="flat"` | idle state empty (no drawing) | `flatButtonTextColor` = `@primary` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| **Outlined** | — | transparent fill, `@outline` border at `stroke-thin`, `@primary` label, `corner-pill` | — | prototype-only (component gallery: `border: var(--bw) solid var(--outline)`, 40 px height, `0 24px` padding) |

The outlined variant has no native `pushbutton` state yet; adding one requires
either a new `extra` value or a `.ui`-level style class and is tracked as
future work.

Prototype geometry (reference values): filled/tonal/outlined buttons are 40 px
high with `0 24px` horizontal padding; text buttons use `0 16px`; dialog
footers use `0 28px` for the filled confirm and `0 20px` for outlined/text
(`fillBtn`/`outBtn`/`ghostBtn` in prototype.html). Labels render at
`font: 500 14px`.

### 1.2 States

All states below are implemented in definition.xml (compiled at commit 577059e274; surface state unverified) unless noted.

| State | Tonal (plain) | Filled (`extra="action"`) | Text (`extra="flat"`) |
| --- | --- | --- | --- |
| Enabled | `@primary-container` fill/stroke | `@primary` fill/stroke | no container drawn |
| Hover (`rollover`) | `@primary-hover` | `@primary-action-hover` | `@primary-container` fill, `stroke-none`, label `flatButtonRolloverTextColor` = `@on-primary-container` |
| Pressed | `@primary-pressed` | `@primary-action-pressed` | `@primary-hover` fill, `stroke-none` |
| Selected (`selected="true"`) | `@primary` fill/stroke (toggle-style push buttons) | — | — |
| Focused | `Focus` part overlay: `@primary` ring, `stroke-standard` | same | same |
| Disabled | `@disabled-container` fill/stroke | `@disabled-container` fill/stroke | empty state (nothing drawn) |

Disabled label colour follows the deactivated style slots
(`deactiveTextColor` = `@outline`), matching the prototype's disabled gallery
button (`background: var(--disabled); color: var(--outline)`). All containers
keep `radius="@corner-pill"` in every state, so shape never changes with
state.

### 1.3 The keyboard-default button (deliberately deferred — D-020)

MD3 would emphasise the keyboard-default button beyond its siblings. The
coverage audit behind decision **D-020**
(`.codex/memory/decision-log.md`) verified that VCL passes
`ControlState::DEFAULT` for the default push button, but deferred styling it
distinctly: every `VclButtonBox` member is already `setAction(true)`
(`builder.cxx:2231`), so a distinct default treatment would restyle the whole
dialog button box and demote non-default actions. Consequently the `<style>`
section deliberately pairs `defaultActionButtonTextColor` and
`actionButtonTextColor` (both `@on-primary`), and `defaultButtonTextColor` and
`buttonTextColor` (both `@on-primary-container`). The default button therefore
currently looks identical to its action siblings; the affordance is the
platform focus/default border plus Enter activation. Revisiting this requires
a real build and captures. Status: deferred by design decision, recorded in
D-020.

### 1.4 Interaction

- **Pointer:** press starts on button-down inside the container; activation on
  button-up inside it. Leaving the container while pressed reverts to hover;
  re-entering restores pressed. No action fires on drag-out release.
- **Keyboard:** `Space` activates the focused button. `Enter` activates the
  dialog default button from anywhere in the dialog; on a focused non-default
  button `Enter` activates that button (native VCL behaviour). `Esc` activates
  the cancel button of a dialog. `Tab`/`Shift+Tab` move focus in button-box
  order.
- **Mnemonics:** `Alt`+underlined character activates the button directly,
  including when focus is elsewhere in the dialog. Mnemonic underlines follow
  the platform reveal convention (see Platform notes).
- **Screen reader:** exposed as role *push button* with the label as
  accessible name (mnemonic marker stripped); pressed/toggled state exposed
  for `selected` toggle buttons.

### 1.5 Accessibility

- Role/name/state via the existing VCL accessibility bridge; no
  Material-specific divergence.
- Focus indicator: the `Focus` part ring (`@primary`, `stroke-standard`) is
  always drawn for keyboard focus; it must remain visible in both palettes. In
  resolved high contrast, Material drawing is bypassed entirely and the native
  `StyleSettings` baseline is restored, so the platform focus rectangle
  applies; controls refresh native-focus suppression on profile change so
  generic fallback keeps a visible indicator (implemented routing, compiled at commit 577059e274; surface state unverified).
- Contrast targets: label-to-face ≥ 4.5:1, container boundary and focus ring
  ≥ 3:1 against adjacent surface. The standalone validator checks declared
  feedback/selection contrast pairs; button-pair contrast measurement is a
  verification hook (§1.8), not a current claim.
- Colour independence: disabled state changes both face and label; the text
  variant additionally loses its container in disabled, and toggle state pairs
  fill change with label-colour change. No state is carried by hue alone.

### 1.6 Density

| Value | Compact | Comfortable | Source |
| --- | ---: | ---: | --- |
| Button height | 34 px | 40 px | prototype `--ctrl` density variable (prototype-only) |
| Label size / line | 13 px / 1.35 | 14 px / 1.45 | prototype `--fs` (prototype-only) |
| Native integer baseline | `size-standard-control` = 36 | — | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

The native metric layer preserves the single 36 px integer and adds no density
selection; compact/comfortable is a separate planned contract
(MATERIAL_DESIGN.md, "Desktop density"). Hit area never shrinks below the
drawn container; padding, not target size, absorbs density change.

### 1.7 RTL & localization

- Pill geometry is symmetric; no mirroring of the container.
- Leading icons become trailing in RTL; label alignment flips with text
  direction.
- Long labels: buttons grow horizontally to fit the localized label (VCL
  button-box sizing); labels are never ellipsized in dialog button boxes.
  German/Finnish-length labels must not wrap; verification includes a longest-
  translation pass.
- The `label` typography role preserves native script/charset/family, so CJK
  and complex-script labels inherit correct fonts without theme interference.

### 1.8 Platform notes (Windows-first)

- Mnemonic underlines stay hidden until `Alt` is pressed (Windows convention);
  other platforms follow their native reveal rules.
- Windows printer graphics are excluded from the file-widget initialization
  path; printed dialogs fall back to existing drawing.
- The theme activates only with `VCL_DRAW_WIDGETS_FROM_FILE=1` and
  `VCL_FILE_WIDGET_THEME=material`; unsupported parts retain fallback drawing.

### 1.9 Verification hooks

Per the evidence contract style in
[HEADLESS_UI_EVIDENCE.md](../HEADLESS_UI_EVIDENCE.md) (off-screen Win32
desktop, run-scoped process ownership, `PrintWindow` capture registered
against an exact commit):

- headless draw test: request `pushbutton`/`Entire` for each state tuple
  (plain, `rollover`, `pressed`, `selected`, `disabled`, ×`action`/`flat`) and
  assert sampled pixels resolve to the palette values of the expected roles in
  both light and dark;
- capture checkpoint: a fixture dialog showing all four variants × six states;
  compare against the component-gallery row in prototype.html;
- validator: part/state coverage for `pushbutton` and stability of the
  `corner-pill` reference count;
- keyboard script: `Tab` traversal order, `Space`/`Enter`/`Esc` activation,
  mnemonic activation with menu closed.

---

## 2. Toolbar buttons

### 2.1 Anatomy & tokens

A toolbar button is the command face inside `toolbar` containers
(`Entire`/`DrawBackgroundHorz`/`DrawBackgroundVert` fill
`@surface-container`). Regions:

| Region | Token consumption |
| --- | --- |
| Face | `toolbar`/`Button` part; `radius="@corner-toolbar"` (18) — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Icon | LibreOffice icon pipeline glyph, 20 px optical size in the prototype |
| Checked outline | `@primary` (`stroke-thin`) when `button-value="true"` |

Geometry note: the prototype renders toolbar icon buttons at **34 × 34 px**
with `border-radius: var(--r-sm)` (`corner-small`, 8) — prototype-only. The
native definition assigns `@corner-toolbar` (18), which on a 34 px face clamps
to near-circular. This radius divergence between the two references is a known
reconciliation item; the native `@corner-toolbar` value is authoritative for
the native theme until a build allows visual judgement.

### 2.2 States

All implemented in definition.xml (compiled at commit 577059e274; surface state unverified); state list is the `toolbar`
`Button` part verbatim. Later, more specific states are ordered after generic
ones so last-match-wins selects the exact tuple (D-020).

| State | Face | Stroke |
| --- | --- | --- |
| Enabled | `@surface-container` | none (`stroke-none`) |
| Hover (`rollover`) | `@primary-container` | none |
| Pressed | `@primary-hover` | none |
| Checked (`button-value="true"`) | `@primary-container` | `@primary`, `stroke-thin` |
| Checked + hover | `@primary-hover` | `@primary`, `stroke-thin` |
| Checked + pressed | `@primary-pressed` | `@primary`, `stroke-thin` |
| Focused | `@surface-container` | `@primary`, `stroke-standard` |
| Disabled | `@disabled-container` | none |
| **Disabled + checked** | `@disabled-container` | **`@outline`, `stroke-thin`** |

The disabled-checked row is the milestone-10 affordance rule: a disabled but
checked tool (VCL passes `ControlState::NONE` with tristate `On` from
`ToolBox::ImplDrawItem`) keeps a dimmed `@outline` checked outline instead of
collapsing onto the plain disabled fill, so checked-ness survives disabling
without colour vibrancy (D-020; implemented in definition.xml, compiled at commit 577059e274; surface state unverified).

### 2.3 Interaction

- **Pointer:** click activates; toggle commands flip `button-value`. Hover
  shows the tooltip (command name + shortcut) after the platform delay.
- **Keyboard:** toolbars are reachable via `F6`/`Shift+F6` (pane cycling);
  within a toolbar, arrow keys move between items, `Return`/`Space` activates,
  `Esc` returns focus to the document. `F10` targets the menu bar, not
  toolbars.
- **Screen reader:** role *push button* or *toggle button* (checked state
  exposed for toggles); accessible name from the command label, description
  from the tooltip.

### 2.4 Accessibility

- The focused state has a dedicated visual (`@primary` ring at
  `stroke-standard`) distinct from hover; keyboard users always see it.
- Checked is encoded by outline + fill, never fill alone; disabled-checked
  retains the outline cue (colour-independent within palette luminance).
- Contrast: checked outline `@primary` and disabled-checked outline `@outline`
  against `@surface-container`/`@disabled-container` must meet ≥ 3:1 (hook,
  not claim). High contrast bypasses Material drawing entirely.

### 2.5 Density

Prototype toolbar height `--tb`: 38 px compact / 48 px comfortable
(prototype-only); item faces 34 px in both, with breathing room absorbing the
difference. The native definition declares no toolbar-item size metric; item
size continues to come from icon size + VCL toolbar layout. Comfortable
density must grow spacing, not shrink icon targets.

### 2.6 RTL & localization

Item order mirrors in RTL; overflow chevron moves to the inline-start end.
Icon mirroring is semantic, not automatic (MATERIAL_DESIGN.md, Iconography):
directional glyphs (undo/redo, indent) mirror; content glyphs (bold, table) do
not. Text-bearing toolbar items size to the localized label.

### 2.7 Platform notes

Toolbar grips (`ThumbHorz`/`ThumbVert`, `@outline-variant`,
`corner-indicator`) and separators (`@outline-variant`, `stroke-thin`) are
implemented in definition.xml (compiled at commit 577059e274; surface state unverified). Grip-region source corrections exist
in the shared renderer. Press/hover feedback on scrollbar troughs was
explicitly deferred in D-020 and does not apply here.

### 2.8 Verification hooks

- headless draw: all nine `toolbar`/`Button` state tuples sampled against
  role values, explicitly including `enabled="false" button-value="true"` →
  `@outline` stroke over `@disabled-container`;
- capture checkpoint: Writer standard toolbar with one command disabled and
  one checked-then-disabled (e.g. Bold applied to a read-only document);
- keyboard script: `F6` reach, arrow traversal, `Esc` return-to-document.

---

## 3. Icon buttons

### 3.1 Anatomy & tokens

A standalone icon-only button (sidebar rail items, dialog close, search clear,
card action "more"). Native drawing reuses the `toolbar`/`Button` face where
the control is a toolbar item; elsewhere the prototype defines the reference
treatment (prototype-only):

| Variant | Size | Radius | Idle | Hover |
| --- | ---: | --- | --- | --- |
| Standard (toolbar/status) | 34 × 34 px | `corner-small` | transparent, glyph `on-surface-variant` | `primary-container` fill, glyph `on-primary-container` |
| Rail / prominent | 38 × 38 px | `corner-small` | transparent; active item `primary-container` fill | same fill |
| Dense (in-field, e.g. search clear) | 28–30 px | `corner-small` | transparent | `outline-variant` or `primary-container` fill |

Glyphs render at 20–22 px optical size. A native standalone icon-button part
does not exist in definition.xml; status: prototype-only, native mapping via
`toolbar`/`Button` where applicable, otherwise specified here, not yet
implemented.

### 3.2 States

Same state model as toolbar buttons (§2.2): hover fill `@primary-container`,
pressed `@primary-hover`, toggle-on adds the `@primary` outline, disabled
glyph `@outline` on `@disabled-container`. Focus uses a `@primary`
`stroke-standard` ring.

### 3.3–3.7 Interaction, accessibility, density, RTL, platform

As §2.3–§2.7, with these deltas:

- Icon-only controls **must** carry an accessible name (tooltip text doubles
  as the name); an unnamed icon button fails review.
- Minimum pointer target 34 px in compact; comfortable spacing raises
  effective target ≥ 38 px without resizing glyphs.
- The window caption controls in the prototype (46 × 42 px, close hover
  red) are OS chrome illustration, not part of this contract.

### 3.8 Verification hooks

- accessibility dump: every icon button in a captured surface reports a
  non-empty accessible name;
- capture checkpoint: sidebar rail idle/hover/active/focused set.

---

## 4. Split and combo command buttons

### 4.1 Anatomy & tokens

Two composites carry a command plus an opening affordance:

1. **Toolbar split/dropdown items** (e.g. font colour, paste special): the
   command face uses `toolbar`/`Button` states (§2.2); VCL's `ToolBox` draws
   the dropdown arrow itself. definition.xml defines no separate toolbar
   arrow part, so the arrow inherits icon colouring. A dedicated
   dropdown-zone treatment (hairline `@outline-variant` divider between
   halves, independent hover per half) is **specified here, not yet
   implemented**.
2. **Combo/list command fields** (`combobox`, `listbox`): implemented in
   definition.xml (compiled at commit 577059e274; surface state unverified). The `ButtonDown` part is
   `size-standard-control` × `size-standard-control` (36 × 36) with
   `radius="@corner-container"` and a two-line chevron
   (`stroke-standard`, normalized `0.35,0.43 → 0.5,0.58 → 0.65,0.43`):

| State | ButtonDown face | Chevron |
| --- | --- | --- |
| Enabled | `@primary-container` | `@on-surface-variant` |
| Hover | `@primary-hover` | `@on-surface` |
| Pressed | `@primary-pressed` | `@on-surface` |
| Disabled | `@disabled-container` | `@outline` |

Spin variants: in-field `spinbox` `ButtonUp`/`ButtonDown` are 36 × 28
(`size-standard-control` × `size-compact-control`) with plus/minus glyphs;
standalone `spinbuttons` are 28 × 28 (`size-compact-control`) at
`corner-control` with chevrons in `@on-primary-container`, including
`ButtonLeft`/`ButtonRight` horizontal parts — all implemented in
definition.xml (compiled at commit 577059e274; surface state unverified). Full field behaviour is chapter
[04 — Inputs](04-inputs.md); only the button halves are normative here.

### 4.2 Interaction

- **Pointer:** primary zone fires the last-used/default command; arrow zone
  opens the menu. On toolbar split items, press-and-hold on the primary zone
  also opens the menu (native VCL behaviour).
- **Keyboard:** `Return`/`Space` fires the primary command;
  `Alt+Down` or `F4` opens the dropdown (combo/list convention); `Esc` closes
  without firing. Arrow keys inside the open menu follow menu rules
  ([05 — Navigation](05-navigation.md)).
- **Screen reader:** primary zone as *push button*, with
  expanded/collapsed state exposed for the dropdown; combo fields expose role
  *combo box* with the button as its open affordance.

### 4.3 Accessibility, density, RTL, platform

- Both halves must be independently focus-visible when split focus exists;
  until the split treatment is implemented, the whole item carries one focus
  ring.
- RTL: `ButtonDown` docks to the inline-end of the field; the shared renderer
  already contains source corrections for composite combo and RTL geometry
  (compiled at commit 577059e274; surface state unverified). `ButtonLeft`/`ButtonRight` swap meaning with direction; the
  downward chevron itself never mirrors.
- Density: button halves keep the native 36/28 integers; the prototype shows
  field heights of 34/40 px by density (prototype-only).

### 4.4 Verification hooks

- headless draw: `combobox`/`listbox`/`spinbox`/`spinbuttons` button parts
  across all four states, both palettes; RTL layout pass asserting the
  chevron zone is at the inline-end;
- capture checkpoint: Calc name box and a toolbar split item, open and
  closed;
- keyboard script: `F4`/`Alt+Down` open, `Esc` close, primary activation.

---

## 5. Links

### 5.1 Anatomy & tokens

Inline hyperlink text (dialogs, Start Center lists, help panes).

| Aspect | Token | Status |
| --- | --- | --- |
| Unvisited colour | `linkColor` = `@primary` | implemented in definition.xml `<style>` (compiled at commit 577059e274; surface state unverified) |
| Visited colour | `visitedLinkColor` = `@visited-link` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified); palette values `#7D5260` light / `#EFB8C8` dark; the prototype's high-contrast mockup uses `#4A0052` (prototype-only) |
| Underline | always underlined in body copy; underline may be omitted only in clearly navigational lists where position conveys interactivity | specified here, not yet implemented |
| Hover | underline persists; colour unchanged (no hover tint) | specified here, not yet implemented |
| Focus | `@primary` focus outline at `corner-focus` radius | specified here, not yet implemented |

### 5.2 States, interaction, accessibility

- States: enabled, hover, focused, visited, disabled (disabled links render as
  `deactiveTextColor` = `@outline` plain text, no underline, not focusable).
- Keyboard: `Tab` reaches links in reading order; `Enter` activates. Pointer:
  single click; middle-click/modifier behaviour follows the host context.
- Screen reader: role *link*, visited state exposed.
- Colour independence: the underline (or list affordance) carries
  interactivity, so `@primary` vs `@visited-link` hue is never the only cue.
  Contrast: both link colours against `@surface`/`@surface-container` ≥ 4.5:1
  (verification hook).

### 5.3 Density, RTL, platform, verification

Links follow surrounding `body` typography in both densities. RTL inherits
bidirectional text layout; no glyph mirroring. Windows-first: link cursor is
the platform hand cursor. Hooks: style-slot resolution test that
`visitedLinkColor` resolves to `@visited-link` in both palettes; capture of a
dialog containing an unvisited and a visited link.

---

## 6. Start Center primary "Open File" action

### 6.1 Anatomy & tokens

The single highest-emphasis action in the suite shell, first item of the Start
Center navigation column ([09 — Start Center](09-start-center.md)). Prototype
reference values (prototype-only): height **44 px** (deliberately taller than
the 40 px standard to mark the primary entry point), `corner-pill` radius,
face `primary`, label `on-primary` at `font: 600 14px`, leading `folder_open`
glyph at 20 px, 14 px icon–label gap, `0 12px` padding, 6 px bottom margin
separating it from the "Remote Files" text-style sibling (40 px, transparent
face).

Native mapping: a filled push button — `pushbutton`/`Entire` with
`extra="action"` (§1), hover `@primary-action-hover`, pressed
`@primary-action-pressed`, focus ring from the `Focus` part. `open_all` now
declares `suggested-action`; `VclBuilder` maps that standard UI class to
`PushButton::setAction(true)`, selecting the existing action state when
Material drawing is enabled. The focused builder mapping passes in current Linux
and Windows native runs. Accepted Start Center captures now show the action at
rest and with a visible Tab-focus indicator, and the corresponding bounded UNO
tree reports `Open File` as the sole focused push button. The specified 44 px
geometry, exact Material pixels, hover/pressed states, and activation flow
remain unverified.

### 6.2 Behaviour

- Activation opens the system file-open dialog scoped to supported document
  types; it never destroys state (safe, repeatable action).
- Keyboard: first element in the Start Center focus order; `Enter`/`Space`
  activate; mnemonic per localized label.
- Accessibility: role *push button*, name "Open File" (localized); the icon is
  decorative and not exposed separately.
- Density/adaptive: keeps 44 px in both densities (primary-action exception);
  at compact window widths the navigation column collapses per the Start
  Center spec while this action remains visible, never overflowed.
- RTL: icon leads at inline-start; column mirrors.

### 6.3 Verification hooks

Completed scope: accepted light, dark, and forced-high-contrast Home/focus
captures register the visible action and one Tab-focus transition; they do not
identify the renderer command or token values from pixels. Remaining hooks:

- capture checkpoint: add hover and pressed states and component-level pixel
  checks to the existing rest/focus evidence;
- flow check: activation from a cold start opens the file dialog on the
  off-screen desktop with run-scoped process ownership per
  [HEADLESS_UI_EVIDENCE.md](../HEADLESS_UI_EVIDENCE.md);
- comparison: rendered geometry versus the prototype navigation column.

---

## Disabled-affordance summary (milestone 10 rules)

Cross-cutting rules this chapter's controls obey, all implemented in
definition.xml (compiled at commit 577059e274; surface state unverified) and recorded in D-020:

1. Disabled faces are always `@disabled-container`; disabled glyphs and labels
   dim to `@outline` (chevrons, spin glyphs) or `@outline-variant` (weakest
   strokes) — never invisible.
2. State that survives disabling stays visible: a disabled checked toolbar
   button keeps a `@outline` `stroke-thin` outline at `corner-toolbar`; a
   disabled submenu parent dims its arrow to `@outline`; a disabled tab strip
   keeps its selected page marked.
3. Specific disabled tuples are declared after the generic disabled state so
   last-match-wins selection picks the richer affordance.
4. Three related gaps are deferred as design decisions pending a build:
   default-button emphasis (§1.3), hover on outlined fields, and scrollbar
   trough feedback.
