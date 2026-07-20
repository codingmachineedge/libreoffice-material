# 04 — Inputs

> **Status:** Specification of target design — native implementation per
> [ROADMAP.md](../../ROADMAP.md). Required native definition/dispatch targets
> have compiled and executed. The accepted Start Center captures include the
> closed idle `cbFilter` combo, but do not prove its definition-backed pixels or
> any open, focused, disabled, editing, search, spin, or validation state in
> this chapter.

This file specifies the input family: outlined single-line text fields, the
borderless and multiline edit variants, combo boxes and dropdown list boxes,
spin fields and standalone spin buttons, the pill search field with its full
regex-builder pattern, and the Find & Replace field set. Normative sources are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md), the implemented native contract
in
[`vcl/uiconfig/theme_definitions/material/definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml),
and the interactive reference [`site/prototype.html`](../../site/prototype.html).

Implementation labels used throughout:

- **implemented in definition.xml (compiled at commit 577059e274; surface state unverified)** — the native part/state exists in
  the file-widget definition, the exact-source build contains it, and current
  definition/dispatch assertions have executed; no named input state is treated
  as rendered proof without a registered component checkpoint;
- **prototype-only** — shown in `site/prototype.html`, no native counterpart yet;
- **specified here, not yet implemented** — in neither source.

A shared convention for the whole family, decided in the tenth source
milestone: **outlined fields render their idle state on hover**. There is no
`rollover` state on `editbox`, `combobox`, `listbox`, or `spinbox` `Entire`
parts, and this is deliberate — hover feedback belongs to the embedded buttons
(`ButtonDown`, `ButtonUp`), not to the text container. See the milestone-ten
notes in `MATERIAL_DESIGN.md`.

---

## 1. Outlined text field

### 1.1 Anatomy & tokens

| Region | Token use |
| --- | --- |
| Container | `@surface` fill, `corner-container` (12px) radius |
| Outline, idle | `@outline` stroke at `stroke-thin` (1) |
| Outline, focused | `@primary` stroke at `stroke-standard` (2) |
| Input text | `fieldTextColor` → `@on-surface`, `body` type role |
| Placeholder / prompt text | `@on-surface-variant` |
| Floating label (prototype-only) | `label` type role, `@on-surface-variant` idle / `@primary` focused / error base colour when invalid |
| Helper/error text (prototype-only) | 12px text below the container |
| Height | `Entire` part declares `height="@size-standard-control"` (36) natively; prototype dialog fields are 48px, prototype form fields 44px |

The native `editbox` control is **implemented in definition.xml (compiled at commit 577059e274; surface state unverified)**:
`Entire` with `height="@size-standard-control"` and three states. The floating
label — a `label`-role caption cut into the top outline (prototype geometry:
`top:-8px; left:12px; padding:0 4px`, 500-weight 12px, background matching the
dialog surface `--sc`) — is **prototype-only**; native VCL dialogs currently
pair a `GtkLabel` beside the field in `.ui` resources, and moving the caption
into the outline is a later `.ui`/VCL layout work item. The 48px height used by
prototype dialog fields (Save As "File name", Print "Copies") is the
comfortable dialog presentation; the native metric layer intentionally keeps
the single 36px `size-standard-control` value with no density policy yet.

### 1.2 States

| State | Visual treatment | Exact tokens (native where implemented) |
| --- | --- | --- |
| Enabled | 1px outline, surface fill, rounded 12 | `stroke="@outline" fill="@surface" stroke-width="@stroke-thin" radius="@corner-container"` — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Hover | Identical to enabled (deliberate; see family convention) | no `rollover` state declared |
| Focused | 2px primary outline replaces the 1px outline; label (prototype) turns `@primary` | `stroke="@primary" ... stroke-width="@stroke-standard"` — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Pressed | No distinct container treatment; the caret placement is the feedback | — |
| Disabled | 1px `@outline-variant` outline, `@disabled-container` fill, text via `deactiveTextColor` → `@outline` | `stroke="@outline-variant" fill="@disabled-container" stroke-width="@stroke-thin"` — implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Read-only | Enabled container, non-editable text, caret allowed for selection | specified here, not yet implemented |
| Invalid | 2px error outline, error-coloured label and trailing `error` icon (20px), helper line below | prototype-only (`border:2px solid var(--err-base)`, helper `font 12px`, e.g. "The path does not exist."). The native palette declares no base `error` role — only `error-container`/`on-error-container` (style slots `errorColor`/`errorTextColor`). A native invalid state therefore needs a future base-error role; specified here, not yet implemented |
| Focused + invalid | Error outline wins at 2px; focus remains programmatically exposed | prototype-only |

### 1.3 Interaction

- **Pointer:** click places the caret; drag selects; double-click selects a
  word; triple-click selects the line. The whole 36/44/48px container is the
  hit target, not only the text baseline.
- **Keyboard:** standard VCL edit keys — arrows, Home/End,
  Ctrl+Left/Right (word), Shift extends selection, Ctrl+A select all,
  Ctrl+C/X/V clipboard, Ctrl+Z/Y undo/redo, Delete/Backspace. Esc in a dialog
  cancels the dialog, not the field.
- **Mnemonics:** the associated label's mnemonic (`_x` in `.ui`) moves focus to
  the field with Alt+letter.
- **Screen reader:** role *text* / *editable text*, accessible name from the
  associated label (or the floating label once natively implemented), value =
  current text, states focused/editable/disabled exposed through the existing
  UNO accessibility bridge.

### 1.4 Accessibility

- Focus is shown by the container itself (1px→2px `@primary` outline change),
  not by an extra rectangle; the change in both colour and thickness keeps the
  indicator visible without relying on hue alone.
- Contrast targets: `@on-surface` text on `@surface` and the `@outline` stroke
  against `@surface` must meet 4.5:1 (text) and 3:1 (non-text) respectively;
  these are design targets, not measured results. The current screenshot
  registry does not constitute this contrast audit.
- Invalid state is never colour-only: outline colour, trailing icon, and helper
  text that names the problem and the recovery action ("Choose an existing
  folder.") all change together.
- Under resolved high contrast the Material drawing path is bypassed and the
  captured native `StyleSettings` baseline is restored (see `MATERIAL_DESIGN.md`).

### 1.5 Density

| Value | Native (single profile) | Prototype compact | Prototype comfortable |
| --- | ---: | ---: | ---: |
| Control height | 36 (`size-standard-control`) | `--ctrl` 34px (44px form / search rows stay fixed) | `--ctrl` 40px; dialog fields 48px |
| Font size | native `body` role (100% of `StyleSettings`) | 13px | 14px |
| Horizontal padding | renderer-managed | 12px | 14px |

The native metric layer deliberately has no compact/comfortable switch yet;
the prototype's density table in `docs/DESIGN_TOKENS.md` is browser-only.

### 1.6 RTL & localization

- Text alignment, caret behaviour, and selection follow the paragraph
  direction; the container is symmetric so no mirroring is required.
- The floating label (when implemented) anchors to the inline-start corner —
  `left:12px` becomes `right:12px` in RTL.
- Long labels truncate with an ellipsis rather than widening the field; helper
  text wraps to multiple lines rather than truncating, because it carries the
  recovery action.

### 1.7 Platform notes

Windows-first. The theme is enabled only with `VCL_DRAW_WIDGETS_FROM_FILE=1`
and `VCL_FILE_WIDGET_THEME=material`; Windows printer graphics are excluded
from the file-widget initialization path, so printed previews keep default
field rendering. IME composition underlining uses the platform composition
style on top of the Material container.

### 1.8 Verification hooks

- Native command coverage: the required headless draw C++ target has executed
  definition/state dispatch assertions. Extend it with an explicit
  `editbox`/`Entire` three-state stroke-width assertion (`stroke-standard` (2)
  focused versus `stroke-thin` (1) idle); no rendered-pixel comparison exists.
- Screenshot checkpoints per [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md):
  Save As dialog field idle/focused/disabled in light, dark, and high-contrast
  rows of the scenario matrix; state axis `default, focus, disabled, invalid`.
- Hover checkpoint proves the *absence* of a hover delta on the container
  (capture hash equality between idle and hover frames).

---

## 2. Borderless and multiline edit variants

### 2.1 Anatomy & tokens

Two native variants are **implemented in definition.xml (compiled at commit 577059e274; surface state unverified)**:

- `editboxnoborder` — `Entire` with `height="@size-standard-control"` (36):
  enabled state paints `@surface` on `@surface` with `stroke-none`, i.e. the
  field disappears into its parent surface (used inline in toolbars and
  composite controls).
- `multilineeditbox` — `Entire` with **no fixed height** (grows with content):
  same three states as the outlined field (`@outline`/`stroke-thin` idle,
  `@primary`/`stroke-standard` focused, `@outline-variant` + 
  `@disabled-container` disabled), radius `@corner-container`.

### 2.2 States

| State | `editboxnoborder` | `multilineeditbox` |
| --- | --- | --- |
| Enabled | `@surface` fill, `stroke-none` | `@outline` stroke `stroke-thin`, `@surface` fill |
| Focused | `@primary` stroke at `stroke-standard`, radius `@corner-container` — the border materialises on focus | `@primary` stroke at `stroke-standard` |
| Disabled | `@disabled-container` fill, `stroke-none` | `@outline-variant` stroke, `@disabled-container` fill |

All rows implemented in definition.xml (compiled at commit 577059e274; surface state unverified). No hover states, per the
family convention.

### 2.3 Interaction

As §1.3, plus for multiline: Enter inserts a newline (in dialogs where Enter
would activate the default button, the multiline edit consumes it while
focused), Tab moves focus out (Ctrl+Tab inserts a tab character where the
control accepts one), and Up/Down move between lines instead of leaving the
control.

### 2.4 Accessibility

The borderless variant relies on the materialising focus border as its only
container-level focus indicator — this is why its focused state uses the full
`stroke-standard` `@primary` treatment rather than a lighter affordance.
Multiline exposes role *multi-line text*; line and caret positions are exposed
through the existing accessible-text interfaces.

### 2.5 Density

Native: 36px for `editboxnoborder`; content-driven height for multiline.
Prototype does not exhibit these variants directly (prototype-only surfaces use
styled `div`s); no density deltas are defined beyond §1.5.

### 2.6 RTL & localization

As §1.6. Multiline respects per-paragraph direction for bidirectional text.

### 2.7 Platform notes

As §1.7. The borderless edit is the variant most sensitive to parent surface
colour: it inherits legibility from `fieldColor` → `@surface`, so hosts placed
on `@surface-container` must still allocate the field's own `@surface` area.

### 2.8 Verification hooks

- Headless draw: assert `editboxnoborder` enabled state has `stroke-none` and
  that its focused state introduces a visible stroke; assert
  `multilineeditbox` has no fixed part height.
- Screenshot checkpoint: a comment/description multiline field in a shared
  dialog, idle vs focused, LTR and RTL locales.

---

## 3. Combo box and dropdown list box

### 3.1 Anatomy & tokens

Both are composite fields with a trailing dropdown button. Native parts,
**implemented in definition.xml (compiled at commit 577059e274; surface state unverified)**:

| Part | Geometry | Token use |
| --- | --- | --- |
| `Entire` | field container | `@outline`/`@surface`/`stroke-thin`/`corner-container` (combo adds a focused state; listbox `Entire` declares enabled/disabled only) |
| `SubEdit` | inner text area | `@surface` on `@surface`, `stroke-none` — the container, not the sub-edit, draws the outline |
| `ButtonDown` | `width="@size-standard-control" height="@size-standard-control"` (36×36) | `@primary-container` fill, `corner-container` radius, chevron drawn as two `stroke-standard` lines (0.35,0.43→0.5,0.58→0.65,0.43) in `@on-surface-variant` |
| `ListboxWindow` (listbox only) | dropdown popup | `@outline-variant` stroke, `@surface` fill, `stroke-thin`, `corner-container` |
| `Focus` | keyboard focus adornment | four `@primary` lines at `stroke-standard`, inset 0.04–0.96 |

Supporting style slots: `listBoxWindowBackgroundColor` → `@surface`,
`listBoxWindowTextColor` → `@on-surface`, `listBoxWindowHighlightColor` →
`@primary-container`, `listBoxWindowHighlightTextColor` →
`@on-primary-container`. Settings: `listBoxEntryMargin` →
`@space-list-entry` (12), `listBoxPreviewDefaultLogicWidth/Height` →
`@size-list-preview` (18).

The prototype shows the closed dropdown as a 48px field with a floating label
and a trailing `expand_more` glyph (Save As "File type", Print "Printer") —
that 48px presentation and the floating label are prototype-only.

### 3.2 States

| Part | State | Tokens |
| --- | --- | --- |
| `Entire` (combo) | enabled | `@outline`, `@surface`, `stroke-thin`, `corner-container` |
| `Entire` (combo) | enabled + focused | `@primary`, `stroke-standard` |
| `Entire` (both) | disabled | `@outline-variant`, `@disabled-container`, `stroke-thin` |
| `ButtonDown` | enabled | fill `@primary-container`, chevron `@on-surface-variant` |
| `ButtonDown` | enabled + rollover | fill `@primary-hover`, chevron `@on-surface` |
| `ButtonDown` | enabled + pressed | fill `@primary-pressed`, chevron `@on-surface` |
| `ButtonDown` | disabled | fill `@disabled-container`, chevron `@outline` |
| `ListboxWindow` | enabled / disabled | `@outline-variant` stroke; `@surface` vs `@disabled-container` fill |
| `Focus` | any | `@primary` frame at `stroke-standard` |

All implemented in definition.xml (compiled at commit 577059e274; surface state unverified). Selected dropdown rows use the
`listBoxWindowHighlight*` pair (`@primary-container`/`@on-primary-container`).

### 3.3 Interaction

- **Pointer:** clicking the button (or, for a non-editable listbox, anywhere on
  the field) opens the popup; clicking a row commits and closes; wheel over a
  closed listbox cycles values where VCL enables it.
- **Keyboard:** Alt+Down / Alt+Up and F4 toggle the popup; Up/Down move the
  selection (closed or open); Home/End jump; typing performs prefix match in a
  listbox and edits text in an editable combo; Enter commits, Esc closes the
  popup without committing.
- **Mnemonics:** label mnemonic focuses the field.
- **Screen reader:** role *combo box* (editable) or *list box collapsed*;
  exposes expanded/collapsed state, current value, and the popup as a child
  list with position-in-set information.

### 3.4 Accessibility

The 36×36 `ButtonDown` is a full-size target inside the field. Chevron colour
alone never encodes state: rollover/pressed also change the button fill
(`@primary-hover`/`@primary-pressed`), and the disabled chevron dims to
`@outline` on `@disabled-container` — the tenth-milestone disabled-affordance
convention. The dedicated `Focus` part guarantees a visible focus frame even
when the popup owner suppresses the container's focused stroke.

### 3.5 Density

Native: field 36px tall (via the standard control metric), button 36×36,
dropdown row margin 12 (`space-list-entry`), list preview 18×18
(`size-list-preview`). Prototype: rows in the mock dropdowns are 44px
comfortable; density variables `--menu` 30/38px apply to menus rather than
these popups. No native density switch exists.

### 3.6 RTL & localization

In RTL the `ButtonDown` mirrors to the inline-start (visual left) edge and the
text area mirrors accordingly; the shared renderer already carries source
corrections for composite combo and RTL geometry (`MATERIAL_DESIGN.md`,
"shared renderer" notes — compiled at commit 577059e274; surface state unverified). The chevron glyph is direction-neutral and
must not mirror. Long item labels ellipsise in the closed field but the popup
may widen to fit its widest row within screen bounds.

### 3.7 Platform notes

Windows-first. The popup is a native floating window; its `ListboxWindow`
definition gives it the Material outline and radius rather than the platform
drop-shadowed square. High contrast bypasses Material drawing entirely.

### 3.8 Verification hooks

- Headless draw: state-resolution asserts for all four `ButtonDown` states and
  the `ListboxWindow` pair; regression assert that combo `Entire` has a
  focused state while listbox `Entire` does not (focus is part-based there).
- Screenshot checkpoints: closed field idle/focused/disabled; open popup with
  a highlighted row (light/dark); RTL capture showing the mirrored button; the
  scenario-matrix Direction row applies.

---

## 4. Spin field and standalone spin buttons

### 4.1 Anatomy & tokens

**Spin field** (`spinbox`) — **implemented in definition.xml (compiled at commit 577059e274; surface state unverified)** —
declares `orientation="decrease-edit-increase"` on `Entire`: the decrement
button, then the edit area, then the increment button in one horizontal
container. Parts:

| Part | Geometry | Idle tokens |
| --- | --- | --- |
| `Entire` | container | `@outline`/`@surface`/`stroke-thin`/`corner-container`; focused → `@primary`/`stroke-standard`; disabled → `@outline-variant`/`@disabled-container` |
| `SubEdit` | numeric text | `@surface` on `@surface`, `stroke-none` |
| `ButtonDown` | 36×28 (`@size-standard-control` × `@size-compact-control`) | `@primary-container` fill, `corner-container` radius, minus glyph: one `stroke-standard` line (0.35,0.5→0.65,0.5) in `@on-surface-variant` |
| `ButtonUp` | 36×28 | as ButtonDown plus the vertical stroke (0.5,0.31→0.5,0.69) forming a plus glyph |
| `Focus` | focus frame | four `@primary` lines, `stroke-standard` |

**Standalone spin buttons** (`spinbuttons`) — **implemented in definition.xml
(compiled at commit 577059e274; surface state unverified)** — four directional parts `ButtonUp`, `ButtonDown`, `ButtonLeft`,
`ButtonRight`, each 28×28 (`@size-compact-control`) with the smaller
`corner-control` (10px) radius and chevron glyphs drawn in
`@on-primary-container`. These serve vertical and horizontal spinner
arrangements attached to other controls.

### 4.2 States

| Part family | enabled | rollover | pressed | disabled |
| --- | --- | --- | --- | --- |
| `spinbox` Button glyph | `@on-surface-variant` | `@on-surface` | `@on-surface` | `@outline` |
| `spinbox` Button fill | `@primary-container` | `@primary-hover` | `@primary-pressed` | `@disabled-container` |
| `spinbuttons` glyph | `@on-primary-container` | `@on-primary-container` | `@on-primary-container` | `@outline` |
| `spinbuttons` fill | `@primary-container` | `@primary-hover` | `@primary-pressed` | `@disabled-container` |

Note the deliberate difference: the standalone buttons keep the
`@on-primary-container` glyph across hover/press (their fill change is the
feedback), while the in-field buttons brighten the glyph to `@on-surface`.
`Entire` has no hover state (family convention). All rows implemented in
definition.xml (compiled at commit 577059e274; surface state unverified).

### 4.3 Interaction

- **Pointer:** click increments/decrements by one step; press-and-hold
  auto-repeats; wheel over the field steps the value.
- **Keyboard:** Up/Down arrows step; Page Up/Page Down apply the larger step;
  Home/End jump to min/max where the field defines them; typed digits are
  validated against the field's numeric format on commit (Enter or focus-out).
- **Mnemonics:** via the associated label.
- **Screen reader:** role *spin button*; exposes current, minimum, and maximum
  values and value-changed events; the embedded buttons are not separately
  focusable (keyboard stepping covers them).

### 4.4 Accessibility

Buttons are 36×28 targets inside the field and 28×28 standalone — small but
paired with full keyboard stepping, so pointer-only access is never required.
Disabled buttons keep visible dimmed glyphs (`@outline` on
`@disabled-container`) instead of disappearing. Out-of-range typed input is an
invalid state: clamp-and-announce, with the correction visible in the field
(exact invalid visuals: specified here, not yet implemented — see §1.2 error
role note).

### 4.5 Density

Native fixed values: field height 36, in-field buttons 36×28, standalone
buttons 28×28 (`size-compact-control` is the slider/compact role). No density
switch. Prototype control heights (34/40) apply to its generic control rows,
not to a rendered Material spinbox, which the prototype does not mock
directly.

### 4.6 RTL & localization

`decrease-edit-increase` order mirrors in RTL so decrement stays at
inline-start. `ButtonLeft`/`ButtonRight` in `spinbuttons` are *semantic*
horizontal steps: the glyphs point left/right physically, but increment must
follow reading direction in RTL numeric contexts. Locale decimal and group
separators come from the number formatter, not the theme.

### 4.7 Platform notes

Windows-first. Auto-repeat delay/rate follow platform settings. The horizontal
in-field arrangement replaces the stacked half-height Windows spinner; this is
a deliberate Material difference recorded here.

### 4.8 Verification hooks

- Headless draw: asserts for the `orientation="decrease-edit-increase"`
  attribute, the 36×28 vs 28×28 part dimensions resolving from
  `@size-standard-control`/`@size-compact-control`, and all four states of the
  six button parts.
- Screenshot checkpoints: spinbox idle/focused/disabled; each standalone
  direction button in rollover and pressed; RTL mirror capture of the
  decrease/increase order.

---

## 5. Search field and regex builder

Entirely **prototype-only** today: no `search` control exists in
definition.xml. The prototype attaches one shared implementation
(`renderSearch`/`rxBuilder`) to four surfaces — Start Center, the Features
catalog, the component gallery, and the Find & Replace dialog — each with
independent state `{q, flags, regex, open, caret}`.

### 5.1 Anatomy & tokens

| Region | Prototype value | Semantic tokens |
| --- | --- | --- |
| Container | height 44px, `border-radius: var(--r-pill)` (20), background `--sc`, padding `0 8px 0 14px`, 8px gap | `@surface-container`, `corner-pill` |
| Border | `var(--bw) solid var(--outline-v)` (1px light/dark, 2px high contrast) | `@outline-variant`, `stroke-thin` |
| Invalid border | `2px solid var(--err-base)` | base error role (prototype `--err-base`: `#B3261E` light / `#F2B8B5` dark) — not in the native palette |
| Leading icon | `search`, 20px, `--on-sv` | `@on-surface-variant` |
| Input | 14px, `--on-s`; switches to a monospace stack (`Cascadia Code`, Consolas) in regex mode | `@on-surface`, `body` role |
| Clear button | 28×28, appears only when text exists | `corner-small` radius |
| Mode toggle `.*` | height 28, `aria-pressed`; off = outlined `--outline`; on = filled `--p`/`--on-p`; 700-weight 12px monospace | `@primary`, `@on-primary`, `corner-small` |
| Builder toggle | 30×30, `tune` icon 20px, `aria-expanded`; open = `--pc`/`--on-pc` | `@primary-container`, `@on-primary-container` |

### 5.2 The regex-builder popover (prototype-only)

Anchored `top: calc(100% + 6px)`, full field width, `z-index` 70, max-height
340px with internal scroll, `--surface` background, `--outline-v` border,
`corner-container` radius, 14px padding, `0 16px 40px rgba(0,0,0,.28)` shadow,
120ms pop animation. Contents, top to bottom:

1. **Header** — "Regex builder", subtitle "insert tokens · toggle flags · live
   matches", 28×28 close button.
2. **Pattern preview row** — the pattern between literal `/` delimiters in a
   34px monospace well (`--outline` border, `corner-small`), followed by four
   30×30 flag toggles with `aria-pressed`: `i` Ignore case, `g` Global, `m`
   Multiline (`^ $` per line), `s` Dotall (`.` matches newline). Active flags
   fill `--p`/`--on-p`; inactive are outlined.
3. **Token palette** — five labelled groups (700-weight 10px uppercase group
   captions, 0.07em letter-spacing), 28px-high monospace chips
   (`corner-small`, `--outline-v` border):
   - *Anchors:* `^`, `$`, `\b`, `\B`
   - *Classes:* `.`, `\d`, `\D`, `\w`, `\W`, `\s`, `\S`, `[ ]`, `[^ ]`, `a-z` range
   - *Quantifiers:* `*`, `+`, `?`, `{n}`, `{n,}`, `{n,m}`, lazy `*?`
   - *Groups:* capture `( )`, non-capturing `(?: )`, alternation `|`,
     lookahead `(?= )`, negative lookahead `(?! )`
   - *Escapes:* `\.`, `\/`, `\(`, `\t`, `\n`
   Each chip inserts its text at the stored caret and applies a caret-back
   offset so the caret lands *inside* brackets and groups (e.g. `[]` → caret
   between the brackets; `{,}` → caret before the comma). Inserting any token
   switches the field into regex mode.
4. **Status line** — one of three live states:
   - empty query: "Type or build a pattern — *N* items" in `--on-sv`;
   - invalid regex: "Invalid pattern: *engine message*" in the error base
     colour, 600 weight;
   - valid: "**matched** of *total* match", plus the compiled `/pattern/flags`
     display in regex mode. A pill "Clear" text button ends the row.

### 5.3 Behaviour (mode, validity, matching)

- **Literal mode** (default): the query is a case-insensitive substring test.
- **Regex mode:** the query compiles with the active `i/m/s` flags (`g` is
  managed by the engine for counting and stripped for per-item tests, exactly
  as the prototype does). Compilation failure marks the field invalid — 2px
  error border on the pill and the status-line message — while filtering
  safely matches nothing.
- Match counts update on every keystroke, flag toggle, and token insertion;
  focus and caret are preserved across re-renders.
- Native mapping (**specified here, not yet implemented**): the native search
  field will map literal/regex mode onto the ICU regex engine already used by
  LibreOffice search, with `i` ↔ case-insensitivity and `m`/`s` mapped to the
  corresponding ICU flags; the builder becomes a VCL popover reusing the menu
  window part.

### 5.4 Interaction & keyboard

Pointer per §5.1 controls. Keyboard: text editing as §1.3; Esc closes the
builder popover (then clears focus scope, never the query silently); the mode
and flag toggles are Tab-reachable buttons activated with Space/Enter and
expose `aria-pressed`; the builder toggle exposes `aria-expanded`. Token chips
are plain buttons announced by their tooltip names ("Word boundary",
"Non-capturing"). Screen readers see the field as a *text* role named by its
placeholder ("Search recent documents…", "Search every command…", "Find"), and
the live match count must be exposed as a polite status region (specified
here, not yet implemented natively).

### 5.5 Accessibility

Invalid state is triple-coded: border colour, status text naming the engine
error, and match behaviour. Mode is visible (filled `.*` toggle + monospace
input) and programmatic (`aria-pressed`). The 44px pill exceeds minimum
target height; embedded 28–30px buttons rely on adjacent keyboard paths.

### 5.6 Density

The prototype pins the search row at 44px in both density profiles (compact
`--ctrl` 34 does not shrink it); the popover is fixed-metric. Native density
behaviour is deferred with the rest of the density contract.

### 5.7 RTL & localization

The pill mirrors: leading icon inline-start, action cluster inline-end. The
pattern preview and token chips remain LTR monospace runs (regex syntax is
directional), embedded in an RTL layout via bidi isolation. Flag letters and
token glyphs are never translated; tooltips and group captions are.

### 5.8 Platform notes

Windows-first; monospace preference order `Cascadia Code`, Consolas mirrors
the prototype stack. The popover must clip within the work area, flipping
above the field when space below is under its 340px maximum.

### 5.9 Verification hooks

Once a native search control exists: headless asserts for mode toggle state
persistence and invalid-compile handling; screenshot checkpoints — pill idle,
regex-valid with count, regex-invalid (error border + message), open builder
with one active flag — across the theme axis of the scenario matrix in
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md).

---

## 6. Find & Replace field set

**Prototype-only** as a composed surface (dialog anatomy is specified in
[08-dialogs.md](08-dialogs.md)); its constituent fields are the components
above. The prototype (`findReplaceDialog`) composes, in a
`min(680px, 94%)`-wide dialog whose box deliberately keeps `overflow: visible`
so the regex-builder popover can escape:

| Element | Specification |
| --- | --- |
| Find field | the shared 44px pill search field (§5), id `find`, full builder attached |
| Options row | three checkbox options (18px, `corner-checkbox`): **Match case**, **Whole words only**, **Regular expressions** |
| Replace field | 44px outlined input, `--outline` border at `--bw`, `corner-container` radius, floating "Replace" label (500-weight 12px, `--on-sv`, on the dialog surface `--sc`) |
| Result summary | "*N* match(es) in *M* of 5 paragraphs", `@primary` 600-weight; empty query → "Enter a search term or build a pattern." |
| Live preview | scrolling run list (max-height 150px, `corner-container`, `--scl` background); hit rows tint `--pc` at 55% with a 3px `--p` inline-start bar; matches render as `--p`/`--on-p` marks with 3px radius |
| Actions | outlined **Find All**, **Find Next**, **Replace**; filled 40px pill **Replace All** |

### 6.1 Engine-flag mapping

The options and the search field share one state; nothing is duplicated:

| Option | Mapping (as implemented by the prototype) |
| --- | --- |
| Match case | the *inverse* of the `i` flag — checked ⇔ `i` absent; toggling the checkbox toggles the same flag as the builder's `i` button |
| Whole words only | wraps the compiled pattern as `\b(?:pattern)\b` at compile time; composes with both literal and regex modes |
| Regular expressions | identical state to the field's `.*` mode toggle — checking one checks the other |

In literal mode the query is regex-escaped before compilation, so literal
searches honour Match case without regex hazards. Native mapping (**specified
here, not yet implemented**): these bind to the existing LibreOffice search
descriptor (case sensitivity, word-boundary, regular-expression flags) so the
dialog drives the real ICU-backed engine rather than a parallel one.

### 6.2 Interaction & keyboard

Ctrl+H opens Find & Replace (Ctrl+F the find bar). Enter in the Find field =
Find Next; Shift+Enter reverse-find (specified here, not yet implemented);
Alt-mnemonics reach each option and action; Esc closes the dialog. Replace All
reports its outcome ("Replaced *n* occurrence(s)…" / "No matches to replace")
via the shared snackbar (see [07-feedback.md](07-feedback.md)), which screen
readers receive as a polite announcement.

### 6.3 Accessibility, density, RTL, platform

As §§1.4–1.7 and 5.5–5.8 for the constituent fields. The options row wraps at
narrow widths (`flex-wrap`) preserving keyboard order; the preview list is
supplementary — results are always also stated in the text summary, so the
colour-tinted preview is never the sole carrier of match information.

### 6.4 Verification hooks

Screenshot checkpoints: dialog with literal query and count; regex query with
open builder escaping the dialog bounds; Match case + Whole words engaged with
visibly reduced count; invalid pattern state; dark and RTL rows. Interaction
evidence: a scripted Replace All over a fixture document with before/after
document hashes, per the run-manifest format in
[`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md).

---

## Token reference (raw values used above)

Copied from `definition.xml` (light / dark) — reproduced here only for
reviewer convenience; components must reference roles, never these literals.

| Role | Light | Dark |
| --- | --- | --- |
| `@primary` | `#6750A4` | `#D0BCFF` |
| `@primary-container` | `#E8DEF8` | `#4F378B` |
| `@primary-hover` | `#D0BCFF` | `#4F378B` |
| `@primary-pressed` | `#CCC2DC` | `#625B71` |
| `@surface` | `#FFFBFE` | `#141218` |
| `@surface-container` | `#F3EDF7` | `#211F26` |
| `@on-surface` | `#1D1B20` | `#E6E0E9` |
| `@on-surface-variant` | `#49454F` | `#CAC4D0` |
| `@outline` | `#79747E` | `#938F99` |
| `@outline-variant` | `#CAC4D0` | `#49454F` |
| `@disabled-container` | `#E6E0E9` | `#36343B` |
| `@error-container` / `@on-error-container` | `#F9DEDC` / `#410E0B` | `#8C1D18` / `#F9DEDC` |
| prototype `--err-base` (no native role) | `#B3261E` | `#F2B8B5` |

Metrics: `stroke-thin` 1, `stroke-standard` 2, `size-compact-control` 28,
`size-standard-control` 36, `space-list-entry` 12, `size-list-preview` 18.
Shapes: `corner-small` 8, `corner-control` 10, `corner-container` 12,
`corner-pill` 20, `corner-checkbox` 3.
