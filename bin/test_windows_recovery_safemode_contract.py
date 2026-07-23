#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the recovery / Safe-Mode composition contract (WIN-SYS-009).

Every mutation perturbs exactly one guarantee against an in-memory copy of the tree
and asserts the checker fails closed; a positive control proves the pristine tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-recovery-safemode-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_recovery_safemode_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CSV = VALIDATOR.POLICY_CSV_PATH
RECOVER = "svx/uiconfig/ui/docrecoveryrecoverdialog.ui"
SAFEMODE = "svx/uiconfig/ui/safemodedialog.ui"
QUERY = "sfx2/uiconfig/ui/safemodequerydialog.ui"
PROGRESS = "svx/uiconfig/ui/docrecoveryprogressdialog.ui"
DOCRECOVERY_CXX = "svx/source/dialog/docrecovery.cxx"
SAFEMODE_CXX = "svx/source/dialog/SafeModeDialog.cxx"
APPCXX = "desktop/source/app/app.cxx"


class RecoverySafeModeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(self, *, registry=None, contents=None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def without_content(self, path: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents.pop(path, None)
        return contents

    def mutate(self, path: str, old: str, new: str) -> dict[str, str]:
        text = self.contents[path]
        replaced = text.replace(old, new, 1)
        self.assertNotEqual(text, replaced, f"mutation anchor not found in {path}: {old!r}")
        return self.with_content(path, replaced)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- safe-default invariant -------------------------------------------
    def test_recover_default_removed_fails(self) -> None:
        contents = self.mutate(
            RECOVER, '<property name="has-default">True</property>', ""
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("safe default lost" in e for e in errors), errors)

    def test_discard_all_becomes_default_fails(self) -> None:
        contents = self.mutate(
            RECOVER,
            '<property name="can-default">True</property>',
            '<property name="can-default">True</property>\n'
            '                <property name="has-default">True</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("became the default" in e for e in errors), errors)

    def test_restart_becomes_default_fails(self) -> None:
        contents = self.mutate(
            QUERY,
            '<property name="label" translatable="yes" context="safemodequerydialog|restart">'
            "_Restart</property>",
            '<property name="label" translatable="yes" context="safemodequerydialog|restart">'
            "_Restart</property>\n"
            '                <property name="has-default">True</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("became the default" in e for e in errors), errors)

    # -- action-widget composition ----------------------------------------
    def test_recover_action_widget_removed_fails(self) -> None:
        contents = self.mutate(
            RECOVER, '<action-widget response="101">next</action-widget>', ""
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("action-widget drift" in e for e in errors), errors)

    # -- SafeMode safeguard controls --------------------------------------
    def test_safemode_radio_removed_fails(self) -> None:
        contents = self.mutate(SAFEMODE, 'id="radio_reset"', 'id="radio_reset_x"')
        errors = self.failures(contents=contents)
        self.assertTrue(any("missing widget 'radio_reset'" in e for e in errors), errors)

    def test_safemode_checkbox_removed_fails(self) -> None:
        contents = self.mutate(
            SAFEMODE, 'id="check_reset_whole_userprofile"', 'id="check_reset_whole_userprofile_x"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("missing widget 'check_reset_whole_userprofile'" in e for e in errors), errors
        )

    def test_safemode_link_removed_fails(self) -> None:
        contents = self.mutate(SAFEMODE, 'id="linkbutton_bugs"', 'id="linkbutton_bugs_x"')
        errors = self.failures(contents=contents)
        self.assertTrue(any("missing widget 'linkbutton_bugs'" in e for e in errors), errors)

    def test_safemode_default_radio_flipped_fails(self) -> None:
        contents = self.mutate(
            SAFEMODE,
            '<property name="active">True</property>',
            '<property name="active">False</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("radio_restore" in e and "composition drift" in e for e in errors), errors
        )

    # -- weld bindings -----------------------------------------------------
    def test_docrecovery_weld_binding_removed_fails(self) -> None:
        contents = self.mutate(
            DOCRECOVERY_CXX, 'weld_button(u"next"_ustr)', 'weld_button(u"nextX"_ustr)'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("missing binding" in e and 'weld_button("next")' in e for e in errors), errors
        )

    def test_safemode_weld_binding_removed_fails(self) -> None:
        contents = self.mutate(
            SAFEMODE_CXX,
            'weld_radio_button(u"radio_restore"_ustr)',
            'weld_radio_button(u"radio_restoreX"_ustr)',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("missing binding" in e and "radio_restore" in e for e in errors), errors
        )

    def test_weld_binding_tolerates_plain_literal(self) -> None:
        # A future migration off the u"..."_ustr wrapper to a plain literal must still match.
        contents = self.mutate(
            DOCRECOVERY_CXX, 'weld_button(u"next"_ustr)', 'weld_button("next")'
        )
        errors = self.failures(contents=contents)
        self.assertFalse(any("missing binding" in e and '"next"' in e for e in errors), errors)

    # -- policy cross-check (read-only) -----------------------------------
    def test_policy_rerouted_fails(self) -> None:
        contents = self.mutate(
            CSV,
            "safemodedialog.ui,SafeModeDialog,GtkDialog,native-exclusion",
            "safemodedialog.ui,SafeModeDialog,GtkDialog,bottom-right-notification-form",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("was rerouted" in e for e in errors), errors)

    def test_policy_row_removed_fails(self) -> None:
        text = self.contents[CSV]
        lines = [ln for ln in text.splitlines(keepends=True) if "CrashReportDialog" not in ln]
        contents = self.with_content(CSV, "".join(lines))
        self.assertNotEqual(text, contents[CSV])
        errors = self.failures(contents=contents)
        self.assertTrue(any("CrashReportDialog" in e and "missing from" in e for e in errors), errors)

    # -- no-nag retained safeguards ---------------------------------------
    def test_retained_safeguard_removed_fails(self) -> None:
        contents = self.mutate(APPCXX, "handleSafeMode();", "handleSafeModeX();")
        errors = self.failures(contents=contents)
        self.assertTrue(any("retained_safeguards" in e and "missing marker" in e for e in errors), errors)

    # -- definition.xml grounding -----------------------------------------
    def test_grounding_part_renamed_fails(self) -> None:
        contents = self.mutate(
            DEFINITION, '<part value="BackgroundDialog">', '<part value="BackgroundDialogX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("windowbackground/BackgroundDialog missing" in e for e in errors), errors
        )

    def test_palette_role_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["grounding_parts"]["palette_roles"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("palette:@no-such-role" in e for e in errors), errors)

    def test_dark_palette_role_dropped_fails(self) -> None:
        # Remove the dark @error-container entry: the grounding must resolve in BOTH schemes.
        text = self.contents[DEFINITION]
        idx = text.find('scheme="dark"')
        self.assertGreater(idx, 0)
        needle = '<color name="error-container"'
        pos = text.find(needle, idx)
        self.assertGreater(pos, 0)
        end = text.find("/>", pos) + 2
        mutated = text[:pos] + text[end:]
        errors = self.failures(contents=self.with_content(DEFINITION, mutated))
        self.assertTrue(
            any("@error-container missing from the dark palette" in e for e in errors), errors
        )

    # -- widget class / parse failures ------------------------------------
    def test_widget_class_drift_fails(self) -> None:
        contents = self.mutate(
            PROGRESS, '<object class="GtkProgressBar" id="progress">',
            '<object class="GtkLabel" id="progress">',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("progress" in e and "class is" in e for e in errors), errors)

    def test_ui_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(RECOVER))
        self.assertTrue(any("file missing" in e for e in errors), errors)

    def test_ui_unparseable_fails(self) -> None:
        errors = self.failures(contents=self.with_content(RECOVER, "<interface><broken"))
        self.assertTrue(any("unparseable xml" in e for e in errors), errors)

    # -- carve-out / registry integrity -----------------------------------
    def test_carveout_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["discard_all_confirmation"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("discard_all_confirmation:status must stay 'specified'" in e for e in errors),
            errors,
        )

    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)


if __name__ == "__main__":
    unittest.main()
