# Canonical Windows UI rewrite contract

The operator-provided `Libre Office.zip` archive is the visual and interaction
source of truth for the current Windows-only rewrite. The reviewed archive has
SHA-256
`0b79406d3cf60afadeeb732e148a1c28379d4465eb330d419a56a322863d244b`.
Its primary source is `LibreOffice Material.dc.html`; `data/features.json`
supplies the 2,433-command feature catalog. The repository's self-contained
[`site/prototype.html`](../../site/prototype.html) is the reviewable mirror, not
runtime evidence.

## Required surfaces

The native rewrite covers all eleven archive surfaces rather than treating the
Start Center as a proxy for the suite:

1. Foundations
2. Start Center
3. Writer
4. Calc
5. Impress
6. Draw
7. Base
8. Math
9. Features
10. History
11. Components

Dialogs, notification forms, regex builders, menus, sidebars, toolbars,
notebookbars, status bars, pickers, and transient states belong to the owning
surface and to the shared-shell work. The 105-row
[`Windows UI inventory`](../WINDOWS_UI_INVENTORY.md) remains the acceptance
ledger; a shared implementation does not automatically close any row.

## Design tokens

The archive defines the following core Material roles, supplemented by the
complete token specification in [`DESIGN_TOKENS.md`](../DESIGN_TOKENS.md):

| Role | Light | Dark |
| --- | --- | --- |
| Primary | `#6750A4` | `#D0BCFF` |
| Primary container | `#E8DEF8` | `#4F378B` |
| Surface | `#FFFBFE` | `#141218` |
| Surface container | `#F3EDF7` | `#211F26` |
| On surface | `#1D1B20` | `#E6E0E9` |
| Outline | `#79747E` | `#938F99` |
| Outline variant | `#CAC4D0` | `#49454F` |
| Error | `#B3261E` | `#F2B8B5` |

Canonical corner radii are `3`, `4`, `6`, `8`, `10`, `12`, `18`, and `20`
pixels. Native controls must retain Windows accessibility, localization,
keyboard, high-contrast, scaling, reduced-motion, and bidirectional-text
behavior while resolving these semantic roles.

## Operator requirements that supersede the archive

Two later requirements intentionally override transient behavior shown in the
archive:

- every LibreOffice-owned dialog migrates to a customizable notification form
  anchored at the bottom-right of its owning work area;
- every app-owned search field supports regular expressions and has an adjacent
  advanced builder with embedded reference, examples, flags, live validation,
  and test text.

The exhaustive dialog registry is
[`qa/windows-ui-contract/dialog-notification-policy.csv`](../../qa/windows-ui-contract/dialog-notification-policy.csv).
It currently assigns an explicit migration policy to all 599 discovered
top-level dialog roots. Registration is coverage, not implementation or runtime
proof. Search-field coverage is governed by the companion registry in the same
directory.

The notification system must include a full manager, customizable form profile,
bulk operations, and local Git-backed event history so dismissed or deleted
notifications can be restored. The history repository must be local-only, use
redacted structured records, create one atomic commit per user-visible bulk
operation, and never configure remotes or put notification content in commit
messages.

Promotional or recurring nags are not part of the rewritten product. Donation,
support, survey, first-run welcome, tip, and opt-in solicitation prompts are
removed or default-off. Safety-critical confirmations for data loss, security,
credentials, destructive actions, and required compatibility decisions remain.

## Honest completion rule

A surface is complete only when the implementation, local Windows build,
headless interaction smoke, accessibility capture/audit, visual comparison,
documentation, and pushed source all identify the same commit. Prototype or
registry coverage alone advances no runtime gate. Cross-platform parity is
deferred and cannot be substituted for the current Windows evidence.
