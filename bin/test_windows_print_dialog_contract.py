#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Print dialog contract (WIN-DLG-004).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree (or a
deep copy of the registry) and asserts the checker fails closed, while the pristine production tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-print-dialog-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_print_dialog_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CSV = VALIDATOR.CSV_PATH
DIALOG = "vcl/uiconfig/ui/printdialog.ui"


class PrintDialogContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(self, *, registry: dict | None = None, contents: dict[str, str] | None = None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def replace_once(self, path: str, old: str, new: str) -> dict[str, str]:
        source = self.contents[path]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {path}")
        return self.with_content(path, source.replace(old, new, 1))

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- baseline --------------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- footer ----------------------------------------------------------------
    def test_footer_response_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<action-widget response="-5">ok</action-widget>', '<action-widget response="-99">ok</action-widget>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:action_widgets" in e and "drift" in e for e in errors), errors)

    def test_primary_default_removed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<property name="has-default">True</property>',
            '<property name="has-default">False</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary" in e and "has-default" in e for e in errors), errors)

    def test_primary_label_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<property name="label" translatable="yes" context="printdialog|print">_Print</property>',
            '<property name="label" translatable="yes" context="printdialog|print">_Go</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary:label" in e for e in errors), errors)

    # -- structure -------------------------------------------------------------
    def test_notebook_missing_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<object class="GtkNotebook" id="tabcontrol">', '<object class="GtkNotebook" id="tabcontrolX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:notebook" in e and "missing" in e for e in errors), errors)

    def test_range_radio_reorder_fails(self) -> None:
        # Swap the ids of the first two radios so their document order no longer matches the pin.
        contents = self.replace_once(DIALOG, 'id="rbAllPages"', 'id="rbAllPagesTMP"')
        contents2 = dict(contents)
        contents2[DIALOG] = contents2[DIALOG].replace('id="rbRangePages"', 'id="rbAllPages"', 1)
        contents2[DIALOG] = contents2[DIALOG].replace('id="rbAllPagesTMP"', 'id="rbRangePages"', 1)
        errors = self.failures(contents=contents2)
        self.assertTrue(any("structure:range_group" in e and "order drift" in e for e in errors), errors)

    def test_printer_combo_missing_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<object class="GtkComboBoxText" id="printersbox">', '<object class="GtkComboBoxText" id="printersboxX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:printer_group:combo" in e and "missing" in e for e in errors), errors)

    def test_copies_adjustment_bound_drift_fails(self) -> None:
        contents = self.replace_once(DIALOG, "<property name=\"adjustment\">adjustment2</property>", "<property name=\"adjustment\">adjustment3</property>")
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:copies:spin adjustment" in e for e in errors), errors)

    def test_copies_adjustment_upper_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<object class="GtkAdjustment" id="adjustment2">\n    <property name="lower">1</property>\n    <property name="upper">16384</property>',
            '<object class="GtkAdjustment" id="adjustment2">\n    <property name="lower">1</property>\n    <property name="upper">9999</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:copies:adjustment upper" in e for e in errors), errors)

    def test_pager_button_removed_fails(self) -> None:
        contents = self.replace_once(DIALOG, '<object class="GtkButton" id="btnLast">', '<object class="GtkButton" id="btnLastX">')
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:pager:GtkButton 'btnLast'" in e for e in errors), errors)

    def test_pager_total_label_text_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<property name="label" translatable="yes" context="printdialog|totalnumpages">/ %n</property>',
            '<property name="label" translatable="yes" context="printdialog|totalnumpages">of %n</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:pager:total_label" in e and "label" in e for e in errors), errors)

    def test_previewbox_missing_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<object class="GtkCheckButton" id="previewbox">', '<object class="GtkCheckButton" id="previewboxX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("structure:previewbox" in e and "missing" in e for e in errors), errors)

    # -- native parts (definition.xml) -----------------------------------------
    def test_pushbutton_action_token_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="true" extra="action">\n                <rect stroke="@primary" fill="@primary" stroke-width="@stroke-thin" radius="@corner-pill"/>',
            '<state enabled="true" extra="action">\n                <rect stroke="@primary" fill="@surface" stroke-width="@stroke-thin" radius="@corner-pill"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:pushbutton-action" in e and "token drift" in e for e in errors), errors)

    def test_radiobutton_corner_control_metric_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION, '<radius name="corner-control" value="10"/>', '<radius name="corner-control" value="11"/>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:metric:corner-control" in e for e in errors), errors)

    def test_missing_spinbuttons_part_fails(self) -> None:
        registry = self.registry_copy()
        registry["native_parts"]["present_parts"][0]["part"] = "ButtonUpX"
        errors = self.failures(registry=registry)
        self.assertTrue(any("native_parts:spinbuttons" in e and "missing" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["native_parts"]["palette_roles"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("native_parts:palette:@no-such-role" in e for e in errors), errors)

    # -- modal exclusion (read-only) -------------------------------------------
    def test_modal_exclusion_policy_desync_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "vcl/uiconfig/ui/printdialog.ui,PrintDialog,GtkDialog,native-exclusion",
            "vcl/uiconfig/ui/printdialog.ui,PrintDialog,GtkDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("modal_exclusions" in e and "PrintDialog" in e and "policy is" in e for e in errors), errors)

    # -- carve-outs ------------------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveouts"]["runtime_injected_tabs"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:runtime_injected_tabs:status must stay 'specified'" in e for e in errors), errors)

    # -- registry integrity ----------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)


if __name__ == "__main__":
    unittest.main()
