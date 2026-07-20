# Windows UI coverage contracts

These registries turn the whole-application dialog and search requirements into
fail-closed source inventories. They establish migration scope; they do not
claim native implementation, a successful build, or runtime evidence.

## Dialog notification forms

`dialog-notification-policy.csv` is the exhaustive native dialog registry for
the Windows notification-form migration. It inventories every top-level
`GtkDialog`, `GtkMessageDialog`, and `GtkAssistant` object found in a Git-tracked
or untracked, non-ignored `.ui` file.

Each row must explicitly choose one of these policies:

- `bottom-right-notification-form` routes the dialog through the new
  bottom-right notification surface. `notification_profile` selects its
  customizable form profile; the initial profile is `default`.
- `native-exclusion` keeps a dialog outside that surface. It must have a
  non-empty `exclusion_reason` and cannot silently inherit a profile.

There are no exclusions in the initial registry. The contract intentionally
does not claim that a registered dialog has already become a complete
notification form or been runtime verified; it establishes complete,
reviewable migration coverage. A separate source contract now guards the first
shared implementation seam: Windows VCL dialogs are repositioned only after
their final `InitShow` layout, relative to the visible owner/work area, with
bounded Material inset and work-area clamping. That seam is geometry only.
The current total is 597 roots (`GtkDialog` 521, `GtkMessageDialog` 75,
`GtkAssistant` 1) after the no-nag source slice deleted the automatic Windows
file-association and Welcome dialogs.

`ui_path` plus `object_id` is the stable locator. The two source roots that do
not define a GTK object ID use an empty `object_id`, so their repository path is
the locator; duplicate paths remain forbidden.

Validate the checked-in registry and its regression suite:

```sh
python bin/check-windows-dialog-notification-contract.py
python bin/test_windows_dialog_notification_contract.py
python bin/check-windows-dialog-placement.py
python bin/test_windows_dialog_placement.py
```

After deliberately adding, removing, or changing a root dialog, regenerate the
inventory before reviewing the resulting diff:

```sh
python bin/check-windows-dialog-notification-contract.py --update
```

The update operation preserves policies for exact existing dialog identities
and assigns every new dialog the explicit `bottom-right-notification-form`
policy with the `default` customization profile. Review any intentional native
exclusion by editing that row and documenting a concrete rationale.

## Search fields and regex builders

`search-field-coverage.json` records the audited Windows text-query controls:

- 26 existing shipping search fields, each assigned the
  `adjacent-advanced-builder` contract;
- one planned Start Center `start_search` field, required to remain absent until
  it moves into shipping coverage; and
- 16 explicit exclusions for categorical selectors, range inputs,
  transformation parameters, object names, non-shipping QA controls, and the
  shared builder's own pattern editor.

The validator also scans `.ui` objects for search-like IDs, accessible text,
placeholders, tooltips, and `gtk-find` icons. A new unclassified candidate,
missing or duplicate widget, stale exclusion, wrong widget type, count drift,
or incomplete builder declaration fails the contract.

```sh
python bin/check_search_field_coverage.py
python bin/test_search_field_coverage.py
python bin/check-windows-regex-builder-foundation.py
python bin/test_windows_regex_builder_foundation.py
python bin/check-windows-regex-search-integrations.py
python bin/test_windows_regex_search_integrations.py
```

This is the minimum audited native inventory, not permission to ignore a new
app-owned search bar that the conservative scanner does not infer. Any newly
identified search field must be added and receive the same adjacent advanced
builder before its owning UI surface can close.

The shared native foundation now provides an ICU/LibreOffice search service,
literal and regex modes, `i/g/m/s`, bounded match testing, live errors, token
insertion, and embedded Build/Test/Reference/Examples content. Its
`GtkPopover` is anchored to the adjacent builder button and deliberately is not
a modal or bottom-right dialog.

`regex-search-integrations.json` is the separate source-implementation ledger.
It currently records Calc Go to Sheet as 1 of 26 shipping fields. Its validator
requires direct entry/button adjacency, translated accessible metadata,
controller-owned change dispatch, controller-first destruction, exact legacy
`OUString::indexOf` behavior in the literal case-sensitive default, and one
`utl::TextSearch` construction before the item loop for non-legacy modes.
Comment-only wiring cannot satisfy the source contract. Ten mutations prove
those requirements fail closed. The remaining 25 shipping integrations and
native build/runtime proof remain open; `runtime_verified: false` is intentional
until exact-build interaction evidence exists.

## No unsolicited startup or promotion prompts

The Windows no-nag contract forbids the automatic file-association, Welcome /
What’s New, Tip, donation/Get Involved, AutoCorrect-explanation, and
crash-report submission paths and the misleading crash-report opt-in. It also
requires the explicit Tip, What’s New,
feedback, and Windows association actions plus recovery, Safe Mode, incompatible
extension, read-only, macro, metadata, and credential safeguards to remain.
Mutation tests exercise every forbidden marker, removed surface, and retained
safeguard. This is source evidence; only a current native build and fresh plus
seeded legacy-profile startup runs can establish runtime behavior.

```sh
python bin/check-windows-no-nag-contract.py
python bin/test_windows_no_nag_contract.py
python bin/check-notification-store-contract.py
python bin/test_notification_store_contract.py
```

The notification-store contract covers the public state model, metadata-only
privacy default, deterministic redaction, genuine bare loose-object Git format,
fixed local `main`, process plus OS-held operation guarding, lock/CAS behavior,
atomic bulk transitions, recoverable tombstones, inverse-commit undo, bounded
preferences, pending-checkpoint retry without ref/object growth, schema
registration, and focused CppUnit wiring. It does not claim a visible manager
or runtime proof.
