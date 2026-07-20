# 07 — Feedback

> **Status:** Specification of target design — native implementation per
> [`ROADMAP.md`](../../ROADMAP.md); nothing here is build- or runtime-verified.

This chapter specifies the feedback family: determinate progress indicators,
value-sensitive level indicators, sliders, tooltips, toasts/snackbars,
warning and error banners, the prototype's toast-on-action convention, and
empty/no-results states. Normative inputs are
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md) (component-behavior contract),
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) (token values),
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml)
(the implemented native part/state contract, compiled at commit 577059e274; surface state unverified), and
[`site/prototype.html`](../../site/prototype.html) (interactive mockup, not a
build capture). Implementation status is labelled per feature as *implemented
in definition.xml (compiled at commit 577059e274; surface state unverified)*, *prototype-only*, or *specified here, not yet
implemented*.

## Token reference for this chapter

Raw hex appears only in this table; every component below consumes the
semantic role. Values are the native palette declarations in
[`definition.xml`](../../vcl/uiconfig/theme_definitions/material/definition.xml).

| Semantic role | Light | Dark | Consumed by |
| --- | ---: | ---: | --- |
| `@primary` | `#6750A4` | `#D0BCFF` | Progress fill, slider filled track/thumb, high level band |
| `@primary-hover` | `#D0BCFF` | `#4F378B` | Medium level band |
| `@primary-action-hover` | `#7965AF` | `#C4AEFF` | Slider thumb hover |
| `@primary-action-pressed` | `#5B3F91` | `#B69DF8` | Slider thumb pressed |
| `@outline-variant` | `#CAC4D0` | `#49454F` | Progress/level/slider tracks, disabled fills |
| `@disabled-container` | `#E6E0E9` | `#36343B` | Disabled tracks |
| `@warning-container` | `#FFDDB3` | `#5F4100` | Warning banner surface, low level band |
| `@on-warning-container` | `#2A1800` | `#FFDDB3` | Warning banner text/icon |
| `@error-container` | `#F9DEDC` | `#8C1D18` | Error banner surface, critical level band |
| `@on-error-container` | `#410E0B` | `#F9DEDC` | Error banner text/icon |
| `@inverse-surface` | `#313033` | `#E6E0E9` | Tooltip surface, snackbar surface |
| `@inverse-on-surface` | `#F4EFF4` | `#322F35` | Tooltip text |
| `@on-surface-variant` | `#49454F` | `#CAC4D0` | Empty-state and counter text |

The prototype's dark-mode `--inv-s` is deliberately `#2B2930` (dark), not the
native dark `@inverse-surface` above — see [§7.5](#75-toasts--snackbars).

---

## 7.1 Determinate progress indicators

### Anatomy & tokens

A determinate progress bar has two regions declared by the native `progress`
control. The eighth milestone introduced full-track anatomy: an optional
`TrackHorzArea` definition paints the complete control first, then the
`Entire` fill is clipped to the caller's numeric value. Zero still paints the
track; legacy file themes that define only `Entire` retain their prior
fill-only behaviour.

| Region | Token use | Status |
| --- | --- | --- |
| Track (full width) | `@outline-variant` fill, `stroke-none`, `corner-indicator` (4 px) — `progress`/`TrackHorzArea` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Value fill (clipped to value) | `@primary` fill, `stroke-none`, `corner-indicator` — `progress`/`Entire` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Bar height 4 px, both track and fill rounded at `--r-ind` | prototype gallery, 64 % example fill | prototype-only |

The `corner-indicator` role (4 px) equals the bar height in the prototype, so
both ends of the track and of the clipped fill render fully rounded. The
native radius resolves through `radius="@corner-indicator"` into both
rectangle radius axes.

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Enabled track | Neutral hairless track | `@outline-variant` fill, `stroke-none`, `corner-indicator` | definition.xml `progress`/`TrackHorzArea` `enabled="true"` |
| Enabled fill | Primary fill clipped to value | `@primary` fill, `stroke-none`, `corner-indicator` | definition.xml `progress`/`Entire` `enabled="true"` |
| Disabled track | Dim track | `@disabled-container` fill | definition.xml `TrackHorzArea` `enabled="false"` |
| Disabled fill | Fill collapses to track tone | `@outline-variant` fill | definition.xml `Entire` `enabled="false"` |
| Zero value | Track only, no fill; still painted | `TrackHorzArea` alone | milestone 8 contract |

Hover, pressed, and focus states do not exist: progress is output-only and
never a pointer or focus target.

### Interaction

None. Progress accepts no pointer or keyboard input and is skipped by `Tab`
traversal. The hosting surface (status bar, dialog) announces progress
changes; the bar itself only paints the numeric value VCL passes in.

### Accessibility

The control keeps VCL's existing progress-bar accessible role with the
current/minimum/maximum value exposure; the theme changes drawing only.
Because the disabled fill (`@outline-variant`) intentionally converges on the
enabled track colour, disabled progress must additionally be conveyed by the
host (dimmed label, disabled container) — colour is never the only carrier.
Value must be available as text where the operation is long-running (e.g.
"64 %" in a status label), since a 4 px bar is not readable at high zoom
alone.

### Density

The 4 px bar height and `corner-indicator` = 4 px do not change between the
prototype's compact and comfortable profiles; density affects the surrounding
row height (`--row` 26 px compact / 32 px comfortable), not the track. The
native metric layer carries no density selection
([`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md)).

### RTL & localization

In RTL locales the fill originates at the visual right and grows leftwards;
the clip region mirrors with the writing direction. The track/fill anatomy is
symmetric, so no glyph mirroring is involved. Percentage text formatting
follows the locale.

### Platform notes

Windows-first. Windows printer graphics are excluded from the file-definition
initialization path, so printed dialogs never route through this drawing.
Unsupported parts fall back to existing native drawing.

### Verification hooks

- Headless draw coverage for `progress` parts exists in source but has not
  executed; the standalone validator enforces required control/state coverage.
- Future capture checkpoints per
  [`docs/HEADLESS_UI_EVIDENCE.md`](../HEADLESS_UI_EVIDENCE.md): bar at 0 %
  (track only), a mid value, and 100 %, in light/dark, enabled/disabled;
  confirm the zero-value track paints and the fill clip matches the passed
  value; repeat one case in an RTL locale to prove mirror direction.

---

## 7.2 Value-sensitive level indicators

### Anatomy & tokens

A level bar shares the progress anatomy — full `TrackHorzArea` plus a clipped
`Entire` fill — but classifies the caller's value into `critical`, `low`,
`medium`, and `high` bands at the existing 25 %, 50 %, and 75 % boundaries
(milestone 8), so the generic level-bar meaning is not flattened into one
colour.

| Region | Token use | Status |
| --- | --- | --- |
| Track | `@outline-variant` fill, `stroke-none`, `corner-indicator` — `levelbar`/`TrackHorzArea` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Critical fill (< 25 %) | `@error-container` — `levelbar`/`Entire` `extra="critical"` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Low fill (25–49 %) | `@warning-container` — `extra="low"` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Medium fill (50–74 %) | `@primary-hover` — `extra="medium"` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| High fill (≥ 75 %) | `@primary` — `extra="high"` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Gallery band strip: four 8 px segments, 4 px gaps, `--r-ind` radius | prototype-only |

The prototype's gallery renders the four bands side by side (`--err`,
`--warn`, `--p-hover`, `--p`) as a reference strip; the native control shows
one band colour at a time, chosen by the current value.

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Enabled track | As progress track | `@outline-variant`, `corner-indicator` | definition.xml `levelbar`/`TrackHorzArea` |
| Critical | Error-container fill | `@error-container` | `Entire` `enabled="true" extra="critical"` |
| Low | Warning-container fill | `@warning-container` | `extra="low"` |
| Medium | Primary-hover fill | `@primary-hover` | `extra="medium"` |
| High | Primary fill | `@primary` | `extra="high"` |
| Disabled track | Dim track | `@disabled-container` | `TrackHorzArea` `enabled="false"` |
| Disabled fill | Band colour collapses to neutral | `@outline-variant` | `Entire` `enabled="false"` |

### Interaction

Output-only, exactly as progress (§7.1): no pointer, keyboard, or focus
behaviour.

### Accessibility

The band colour alone must never carry the level's meaning: the host exposes
the numeric value through the existing accessible value interface, and
password-strength or quality surfaces must pair the bar with a text label
("Weak", "Strong", or a number). The `critical`/`low` bands reuse the
contrast-checked `error-container`/`warning-container` pairs from the
milestone-5 feedback roles, which the standalone validator covers.

### Density

Identical to progress: track geometry is density-independent; the prototype's
reference strip fixes 8 px segment height in both profiles.

### RTL & localization

Fill direction mirrors with the writing direction; band thresholds are
value-based and unaffected. Any textual level label is localized by the host.

### Platform notes

As §7.1. Legacy themes without `extra` band states retain single-colour
fill-only behaviour, which is a deliberate compatibility path, not a Material
variant.

### Verification hooks

- Future captures must sample values straddling each boundary — e.g. 24/25,
  49/50, 74/75, 100 — and assert the fill colour switches bands exactly at
  25/50/75 %, in light and dark palettes.
- Validator checks on the warning/error container text pairs remain the only
  contrast evidence; the build and Start Center smoke do not constitute a
  runtime contrast result.

---

## 7.3 Sliders

### Anatomy & tokens

The native `slider` control declares a square thumb (`Button`) and four track
parts — horizontal left/right and vertical upper/lower — drawn as centred
lines at the `stroke-track` metric.

| Region | Token use | Status |
| --- | --- | --- |
| Thumb | `@size-compact-control` (28) square; `@primary` fill, `stroke-none`, `corner-control` (10 px) — `slider`/`Button` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Filled track (before thumb) | `@primary` line, `stroke-track` (4) — `TrackHorzLeft` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Remaining track (after thumb) | `@outline-variant` line, `stroke-track` — `TrackHorzRight` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Vertical unfilled (above) | `@outline-variant` line, `stroke-track` — `TrackVertUpper` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Vertical filled (below) | `@primary` line, `stroke-track` — `TrackVertLower` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Gallery reference: 20 px hit strip, 4 px track, 18 px circular thumb with `0 1px 4px rgba(0,0,0,.3)` shadow | prototype-only |

The 4 px track is the dedicated `stroke-track` metric role, distinct from the
1/2 px border strokes. The prototype's 18 px round thumb is the target visual
weight; the native 28 px `size-compact-control` Button is the hit and drawing
region within which that thumb reads. The shared renderer carries source
corrections for slider sizing (compiled at commit 577059e274; surface state unverified).

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Enabled thumb | Primary block, control radius | `@primary`, `corner-control` | definition.xml `Button` `enabled="true"` |
| Hover thumb | Lightens/deepens to action-hover; radius grows to container | `@primary-action-hover`, `corner-container` | `rollover="true"` |
| Pressed thumb | Action-pressed fill, container radius | `@primary-action-pressed`, `corner-container` | `pressed="true"` |
| Focused thumb | Primary fill with on-surface ring | `@on-surface` stroke at `stroke-standard` (2), `@primary` fill, `corner-container` | `focused="true"` |
| Disabled thumb | Neutral fill, no visible stroke | `@outline-variant` fill (`@outline` stroke declared at `stroke-none`) | `enabled="false"` |
| Enabled filled track | Primary at 4 px | `@primary`, `stroke-track` | `TrackHorzLeft`/`TrackVertLower` |
| Enabled remaining track | Neutral at 4 px | `@outline-variant`, `stroke-track` | `TrackHorzRight`/`TrackVertUpper` |
| Disabled filled track | Collapses to neutral | `@outline-variant` | `TrackHorzLeft`/`TrackVertLower` `enabled="false"` |
| Disabled remaining track | Dim container tone | `@disabled-container` | `TrackHorzRight`/`TrackVertUpper` `enabled="false"` |

The hover/pressed radius step from `corner-control` (10 px) to
`corner-container` (12 px) is the slider's state affordance in addition to the
colour change, mirroring the icon-button family.

### Interaction

Pointer: press-drag the thumb; click on the track moves the thumb toward or
to the pointer per existing VCL slider behaviour; the prototype's gallery
slider is a simplified click target that advances the value by 15 % and wraps
from ≥ 90 back to 20 (prototype-only demonstrator, not the native contract).
Keyboard: `Left`/`Down` decrease, `Right`/`Up` increase by the line step,
`PageUp`/`PageDown` by the page step, `Home`/`End` jump to minimum/maximum
(existing VCL behaviour; restated, not altered by this theme). Mnemonics focus
the slider through its label's buddy relation. Screen readers receive the
existing VCL slider value interface with current/min/max.

### Accessibility

Role/name/value exposure is unchanged VCL. The focus indicator is the
definition-backed focused thumb (`@on-surface` ring at `stroke-standard`),
which does not rely on colour alone: the ring adds geometry to the thumb. The
filled/unfilled track split provides a value cue redundant with the thumb
position. The 28 px `size-compact-control` region keeps the target above the
track's 4 px visual height, preserving hit-area predictability.

### Density

The native thumb consumes `size-compact-control` = 28 with no density
selection. Prototype: the surrounding control row uses `--ctrl` 34 px compact
/ 40 px comfortable; the track (4 px) and thumb (18 px visual) are fixed. The
status-bar zoom slider in the prototype renders a reduced 12 px thumb on a
120 px × 4 px track inside the 28 px status bar — a deliberate compact
variant, prototype-only.

### RTL & localization

Horizontal sliders mirror: the filled `TrackHorzLeft` segment renders on the
visual right in RTL and `Left`/`Right` keys follow visual direction per
existing VCL handling. Vertical sliders do not mirror (filled remains the
lower segment). Value formatting is host-localized.

### Platform notes

Windows-first; the shared renderer's slider-sizing corrections and composite
RTL geometry corrections live in shared VCL source (compiled at commit 577059e274; surface state unverified). Unsupported
slider parts fall back to native drawing.

### Verification hooks

- Headless draw coverage exists for slider parts (unexecuted); the validator
  enforces state coverage and token discipline (`stroke-track` used only for
  tracks).
- Future captures: thumb in all five states; horizontal LTR vs RTL fill
  direction; vertical fill from bottom; a keyboard-only run proving
  `Home`/`End`/arrow steps change the accessible value.

---

## 7.4 Tooltips

### Anatomy & tokens

A tooltip is a single inverse-surface plate with the small corner radius.

| Region | Token use | Status |
| --- | --- | --- |
| Plate | `@inverse-surface` fill and stroke, `stroke-none`, `corner-small` (8 px) — `tooltip`/`Entire` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Text | `helpTextColor` → `@inverse-on-surface`; surface slot `helpColor` → `@inverse-surface` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |

Because the native dark palette declares `@inverse-surface` as a light value
(`#E6E0E9`) with a dark `@inverse-on-surface`, native tooltips follow the
standard MD3 inversion: dark plate on light themes, light plate on dark
themes. This is the opposite of the snackbar's deliberate always-dark chrome
(§7.5) — the divergence is scoped to the snackbar/control bar, not to
tooltips. The prototype relies on browser-native `title` tooltips and does
not restyle them (prototype gap, not a design decision).

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Shown | Inverse plate, no border | `@inverse-surface`, `corner-small`, `stroke-none` | definition.xml `tooltip`/`Entire` (single state) |

Tooltips have no hover/focus/pressed/disabled states of their own; the single
`Entire` state is the complete native contract.

### Interaction

Pointer: appears after the platform hover delay over the anchor, follows
existing VCL help behaviour, and dismisses on pointer-out, click, or key
press. Keyboard: extended tips remain reachable via the existing help key
path (`Shift+F1` "What's This" behaviour is unchanged VCL). Tooltips never
take focus and never intercept input.

### Accessibility

The tooltip text is exposed through the existing accessible-description
mechanism of the anchor control; the plate itself is not a focus target. The
`@inverse-surface`/`@inverse-on-surface` pairing provides strong text
contrast in both palettes. Tooltips must not be the only place a control's
name exists — toolbar buttons keep their accessible names independent of the
tip. Under resolved high contrast, Material drawing is bypassed and the
captured native `StyleSettings` baseline is restored.

### Density

Tooltip padding follows existing VCL help-window metrics; no Material metric
role is consumed beyond `corner-small`. Density profiles do not alter the
plate.

### RTL & localization

Tooltip text wraps and aligns per writing direction; placement flips to keep
the plate on-screen. Long translations wrap rather than truncate; the plate
grows vertically.

### Platform notes

Windows-first. The tooltip plate replaces the classic yellow help balloon
colour via the `helpColor` slot; platform-native tooltip windows that bypass
VCL drawing are out of scope for this definition.

### Verification hooks

- Future captures: a toolbar tooltip in light and dark proving the inversion
  (dark plate on light, light plate on dark), plus a long-translation wrap
  case; a screen-reader pass confirming the description is announced from the
  anchor.

---

## 7.5 Toasts / snackbars

### Anatomy & tokens

A snackbar (the prototype calls it a toast) is a transient confirmation plate
that appears bottom-centre of the window. There is no native `snackbar`
control in `definition.xml`; the anatomy below is the prototype reference and
is otherwise *specified here, not yet implemented* natively.

| Region | Prototype value | Status |
| --- | --- | --- |
| Plate | fixed, bottom 26 px, horizontally centred; padding 13 px 20 px; radius 8 px (= `corner-small`); background `--inv-s`; text `--on-inv-s`; shadow `0 10px 30px rgba(0,0,0,.4)` | prototype-only |
| Content row | icon + message, 12 px gap; leading `bolt` icon at 20 px in `--p`; message at `500 13px/1` | prototype-only |
| Entrance | `lo-pop` 160 ms ease (opacity 0, translateY(−4px), scale .98 → identity) | prototype-only |
| Auto-dismiss | 1 900 ms; a newer toast supersedes the pending dismissal (token guard) | prototype-only |

**Deliberate dark-chrome divergence.** The prototype's `--inv-s` matches the
native light `@inverse-surface` (`#313033`) but deliberately uses `#2B2930`
in dark mode instead of the native dark `@inverse-surface` (`#E6E0E9`): the
control bar and snackbar remain dark chrome with light `--on-inv-s` text in
every theme, rather than following the MD3 light inverse-surface convention.
This is recorded as intentional fidelity to the source design in both
[`docs/DESIGN_TOKENS.md`](../DESIGN_TOKENS.md) and the prototype's palette
comment. A future native snackbar must implement this divergence explicitly
rather than reusing `@inverse-surface` unmodified in dark mode — unlike
tooltips, which do invert (§7.4).

### States

| State | Visual treatment | Source |
| --- | --- | --- |
| Shown | Dark plate, light text, elevated shadow; `lo-pop` entrance | prototype `#toast.show` |
| Superseded | New message replaces content; timer restarts; no stacking | prototype token guard |
| Dismissed | Removed after 1 900 ms; no exit animation | prototype |

Snackbars are non-interactive in the current design: no action button,
no hover state, no dismissal control. If a future surface needs an action,
it must be added to this spec first.

### Interaction

None directly: the snackbar accepts no pointer or keyboard input and never
takes focus. It reports the outcome of an action performed elsewhere (e.g.
Find & Replace posts "Replaced 3 occurrences …" or "No matches to replace").
Under reduced motion the 160 ms entrance must map to an immediate appearance
per the motion contract in
[`MATERIAL_DESIGN.md`](../../MATERIAL_DESIGN.md).

### Accessibility

The prototype marks the toast `role="status"` with `aria-live="polite"`, so
assistive technology announces the message without focus theft; the native
equivalent must use the corresponding non-interruptive announcement path.
Because the plate auto-dismisses in under 2 seconds, the same information
must remain available elsewhere (status bar, dialog result) — the snackbar is
reinforcement, never the sole record. Text contrast uses the inverse pair in
all themes; in the prototype's high-contrast palette the plate is `#000000`
on `#FFFFFF` text.

### Density

Plate metrics (13 px × 20 px padding, 13 px text) are fixed across compact
and comfortable profiles; only its distance from other chrome changes with
window size.

### RTL & localization

The plate stays bottom-centre in both directions; the icon leads in reading
order, so it renders to the right of the text in RTL. Long messages widen the
plate up to the window margin, then wrap.

### Platform notes

Windows-first. A native implementation would be a borderless VCL float on
the document frame; no OS notification-centre integration is implied —
snackbars are in-window feedback only.

### Verification hooks

- Once a native snackbar exists: captures of the plate in light, dark, and
  high contrast proving the always-dark chrome (and the high-contrast
  exception), a reduced-motion run showing immediate appearance, and an
  accessibility trace showing a polite announcement without focus change.
- Until then, the behaviour is verifiable only in the prototype and no
  runtime claim is made.

---

## 7.6 Warning & error banners

### Anatomy & tokens

A banner is an inline, persistent message strip inside a dialog or panel.
The colour pairs are the milestone-5 feedback roles, wired to native
`StyleSettings` slots and contrast-checked by the standalone validator.

| Region | Token use | Status |
| --- | --- | --- |
| Warning surface | `warningColor` → `@warning-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Warning text/icon | `warningTextColor` → `@on-warning-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Error surface | `errorColor` → `@error-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Error text/icon | `errorTextColor` → `@on-error-container` | implemented in definition.xml (compiled at commit 577059e274; surface state unverified) |
| Reference geometry: 12 px 16 px padding, `corner-container` (12 px) radius, 12 px icon-text gap, 20 px leading icon, `400 13px/1.3` text | prototype gallery banner ("Document contains unsaved changes.") | prototype-only |

The banner uses the *container* pairs; the base `error` role (`#B3261E`
light / `#F2B8B5` dark, prototype `--err-base`) is reserved for invalid field
outlines and helper text (chapter [04 — Inputs](04-inputs.md)), not for banner
surfaces.

### States

| State | Visual treatment | Tokens | Source |
| --- | --- | --- | --- |
| Warning | Warning container strip, leading `warning` icon | `@warning-container` / `@on-warning-container`, `corner-container` | style slots + prototype geometry |
| Error | Error container strip, leading `error` icon | `@error-container` / `@on-error-container`, `corner-container` | style slots; specified here, not yet implemented as a composed banner |
| Dismissed | Banner removed by resolving the condition or an explicit host action | — | specified here, not yet implemented |

Banners have no hover/pressed states; if a banner carries an action, that
action is a standard text or tonal button per
[02 — Actions](02-actions.md), placed at the trailing edge.

### Interaction

The banner itself is static content; embedded action buttons follow the
normal button keyboard and pointer contract and join the `Tab` order at their
document position. Banners must not steal focus when they appear.

### Accessibility

Per the accessibility contract, an error identifies both the problem and a
recovery action — banner text must say what happened and what to do, not
merely recolour. Severity is carried by the icon and wording in addition to
the container colour (colour-independence). The container/text pairs are
contrast-checked by the validator at source level; no runtime contrast result
exists. Screen readers should receive newly shown banners through a polite
live announcement while the text remains persistently readable, unlike the
snackbar.

### Density

Reference padding (12 px 16 px) and 13 px text are fixed; comfortable density
increases surrounding spacing, not banner internals.

### RTL & localization

Icon leads in reading order and mirrors position in RTL; the `warning` and
`error` glyphs are symmetric and are not mirrored semantically. Long
translations wrap to multiple lines at `1.3` line height; the strip grows
vertically and the icon stays top-aligned with the first line.

### Platform notes

Windows-first; the strips are ordinary VCL/`.ui` containers using the style
slots, so they inherit high-contrast bypass automatically (native baseline
restored, Material drawing bypassed).

### Verification hooks

- Validator: warning/error container-pair contrast checks (source-level).
- Future captures: one warning and one error banner in light/dark, a
  long-translation two-line wrap, an RTL mirror case, and a keyboard run
  proving an embedded action is reachable without pointer.

---

## 7.7 The toast-on-action convention (prototype)

The prototype implements a suite-wide demonstrator rule: **every actionable
control that does not yet navigate or open a real surface confirms its
activation with a toast**. Status: prototype-only; it exists so reviewers can
see that each control is wired, and it is not part of the native target
design.

Mechanics, as implemented:

- a capture-phase click listener on the app root toasts the `title` or text
  label of any `<button>` press;
- disabled buttons and anything inside a `[data-silent]` zone are skipped
  (e.g. the gallery's disabled button specimen);
- actions that already produce their own toast or are pure navigation are
  excluded by prefix (`toast:`, `menuitem:`, `feat:`, `menu:`, `set:featCat`,
  `frreplaceall`);
- functional actions post outcome toasts instead: Replace All posts
  "Replaced *N* occurrence(s) with …" or "No matches to replace"; command
  chips and Math symbols toast their labels.

For the native suite the equivalent principle is retained in spirit only:
every command must produce observable feedback (document change, dialog,
status-bar message, or snackbar) — silent activation is a defect. The
blanket label-toast is a mockup affordance and must not ship.

---

## 7.8 Empty & no-results states

### Anatomy & tokens

Empty states are quiet text placards on the surface they replace — no
illustration, no card.

| Instance | Treatment | Status |
| --- | --- | --- |
| Start Center, filtered card grid | "No recent match this pattern." / "No templates match this pattern." — spans the full grid row, 34 px padding, centred, `@on-surface-variant`, `400 13px/1.5` | prototype-only |
| Gallery command search counter | "*N* of *M* commands match — open the builder for tokens & flags"; the count is `@primary` at weight 700 | prototype-only |
| Features catalog header | "*N* of *M* commands" beside the title; capped lists append "Showing the first 400 matches — refine your search to narrow further." (14 px 12 px padding, centred, `@on-surface-variant`, 12 px text) | prototype-only |
| Find & Replace outcome | "No matches to replace" via snackbar (§7.5) | prototype-only |

The pattern-sensitive wording ("… match this pattern") acknowledges the regex
search builder: the message names the cause (the active pattern), satisfying
the error contract's problem-plus-recovery rule — the recovery action is
editing or clearing the pattern in the search field that remains focused
above the placard.

### States

An empty state has exactly one visual state. It appears when the filtered
result count is zero and disappears when results exist; it never replaces the
search field or filter controls that caused it, so the user always retains
the recovery path.

### Interaction

The placard itself is inert. Focus stays in the search field; live filtering
re-renders results on each keystroke while preserving caret position
(prototype behaviour). No keyboard interaction targets the placard.

### Accessibility

The result counter ("*N* of *M*") is the accessible record of the filter
outcome and should be exposed as a polite live region so zero-result
transitions are announced. Colour-independence holds: emptiness is conveyed
by text, not by a colour change. The `@on-surface-variant` placard text on
`@surface`/`@surface-container` follows the same contrast expectations as
secondary text throughout the suite (validated at source level only).

### Density

Placard padding (34 px in the Start Center grid) is a comfortable-profile
prototype value; compact surfaces may reduce it proportionally to the row
metric, but the message text size follows the base font (`--fs` 13 px compact
/ 14 px comfortable).

### RTL & localization

Centred text needs no mirroring; counters format per locale. Translations
may be substantially longer — the placard wraps at `1.5` line height and the
grid cell grows. The "*N* of *M*" pattern must be a translatable format
string, not concatenation, in native code.

### Platform notes

None beyond the suite defaults; empty states are plain text on existing
surfaces.

### Verification hooks

- Future captures: Start Center with a pattern matching zero documents
  (placard shown, search field retained), the same in RTL and one long
  translation; a screen-reader trace of the zero-result announcement; a
  keyboard-only recovery (edit pattern, results return).
- These feedback scenarios remain prototype-only even though a separate light
  Start Center smoke now exists; see the current registry in
  [`docs/SCREENSHOTS.md`](../SCREENSHOTS.md).

---

Previous: [06 — Containers & data display](06-containers.md) ·
Next: [08 — Dialogs](08-dialogs.md) ·
Index: [README](README.md)
