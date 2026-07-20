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
It currently assigns an explicit migration policy to all 597 discovered
top-level dialog roots; the automatic file-association and Welcome dialogs were
removed by the no-nag source slice. Registration is coverage, not implementation or runtime
proof. Search-field coverage is governed by the companion registry in the same
directory.

The shared regex source foundation implements ICU/LibreOffice literal and
regular-expression evaluation, `i/g/m/s`, bounded live match testing, token
insertion, and embedded Build/Test/Reference/Examples documentation. It is an
anchored `GtkPopover` owned by the adjacent builder button rather than a modal
dialog. This does not yet integrate the controller with each registered field
or provide build/runtime proof.

The first shared native implementation seam is now present in source: after
final VCL `InitShow` layout, Windows `Dialog` instances are positioned at the
bottom-right of the visible owner/work area with a bounded 16 px inset and
decorated-extent clamping. LibreOfficeKit and non-Windows paths are explicitly
unchanged. This source-level placement does not by itself supply notification
form composition, persistence, customization, stacking, history, management,
or build/runtime evidence.

The notification system must include a full manager, customizable form profile,
bulk operations, and local Git-backed event history so dismissed or deleted
notifications can be restored. The history repository must be local-only, use
redacted structured records, create one atomic user-action commit per
user-visible bulk operation, and never configure remotes or put notification
content in commit messages. A bounded-history maintenance checkpoint may precede
that action commit when compaction is required.

The storage foundation now implements that local bare Git
model: metadata-only by default, fixed `main`, same-process mutex plus permanent
OS-held cross-process operation locking, CAS updates, atomic bulk transitions,
recoverable tombstones, bounded pre-mutation checkpoints, history, and
inverse-commit undo. Compaction expires older commit IDs intentionally while
preserving current records and uses a durable pending marker so later writes
fail closed until pruning completes. Retry validates and reuses an already
installed checkpoint without adding objects or advancing the ref. A lazy
application-owned asynchronous service now owns the synchronous store on one
serialized worker and exposes immutable generation-stamped snapshots. It closes
admission before draining accepted mutations, self-retains pending raw VCL event
links, defers off-main cancellation to VCL, rejects inline repository-test
dispatch, refreshes the snapshot after a CAS conflict, maps one bulk request to
one store call, and uses generated office-configuration accessors for all
display/history preferences.
The detailed boundary is in
[`02-notification-service-architecture.md`](02-notification-service-architecture.md).
It is not yet connected to dialog producers or a visible form, manager,
customization controls, or notification stack, and has no compiled/runtime
evidence.

Promotional or recurring nags are not part of the rewritten product. Donation,
support, survey, first-run welcome, tip, and opt-in solicitation prompts are
removed or default-off. Safety-critical confirmations for data loss, security,
credentials, destructive actions, and required compatibility decisions remain.

Current source removes the automatic donation/Get Involved/What’s New,
Welcome, Tip, Windows file-association, AutoCorrect-explanation, and crash-report
submission paths, including their dead startup UI/configuration and the
unreachable crash-report opt-in. Manual Help and file-association actions
remain. The source contract explicitly requires the
recovery, Safe Mode, extension-compatibility, macro, metadata, read-only, and
credential paths; exact-build startup/runtime evidence is still pending.

## Honest completion rule

A surface is complete only when the implementation, local Windows build,
headless interaction smoke, accessibility capture/audit, visual comparison,
documentation, and pushed source all identify the same commit. Prototype or
registry coverage alone advances no runtime gate. Cross-platform parity is
deferred and cannot be substituted for the current Windows evidence.
