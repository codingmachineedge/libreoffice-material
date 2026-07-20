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
- 15 explicit exclusions for categorical selectors, range inputs,
  transformation parameters, object names, and non-shipping QA controls.

The validator also scans `.ui` objects for search-like IDs, accessible text,
placeholders, tooltips, and `gtk-find` icons. A new unclassified candidate,
missing or duplicate widget, stale exclusion, wrong widget type, count drift,
or incomplete builder declaration fails the contract.

```sh
python bin/check_search_field_coverage.py
python bin/test_search_field_coverage.py
```

This is the minimum audited native inventory, not permission to ignore a new
app-owned search bar that the conservative scanner does not infer. Any newly
identified search field must be added and receive the same adjacent advanced
builder before its owning UI surface can close.
