#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Calc Data-menu dialog family contract (WIN-CA-005)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-calc-data-dialog-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_calc_data_dialog_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

SORT_UI = "sc/uiconfig/scalc/ui/sortdialog.ui"
SORT_CXX = "sc/source/ui/dbgui/sortdlg.cxx"
PFILT_CXX = "sc/source/ui/dbgui/pfiltdlg.cxx"
DATABROWSER = "chart2/source/controller/dialogs/DataBrowser.hxx"


class CalcDataDialogContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
            REPOSITORY,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def assert_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    def dialog(self, registry: dict, dialog_id: str) -> dict:
        return next(d for d in registry["pinned_dialogs"] if d["dialog_id"] == dialog_id)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- Part A: pinned dialog shells --------------------------------------
    def test_dialog_id_renamed_fails(self) -> None:
        source = self.contents[SORT_UI].replace('id="SortDialog"', 'id="SortDialogX"', 1)
        self.assert_changed(SORT_UI, source)
        errors = self.failures(contents=self.with_content(SORT_UI, source))
        self.assertTrue(any("missing/renamed" in e for e in errors), errors)

    def test_action_widget_removed_fails(self) -> None:
        source = self.contents[SORT_UI].replace(
            '<action-widget response="101">reset</action-widget>', "", 1
        )
        self.assert_changed(SORT_UI, source)
        errors = self.failures(contents=self.with_content(SORT_UI, source))
        self.assertTrue(any("action-widget footer drift" in e for e in errors), errors)

    def test_footer_default_role_drift_fails(self) -> None:
        source = self.contents[SORT_UI].replace(
            '<property name="has-default">True</property>',
            '<property name="has-default">False</property>',
            1,
        )
        self.assert_changed(SORT_UI, source)
        errors = self.failures(contents=self.with_content(SORT_UI, source))
        self.assertTrue(any("footer default drift" in e for e in errors), errors)

    def test_footer_secondary_role_drift_fails(self) -> None:
        source = self.contents[SORT_UI].replace(
            '<property name="secondary">True</property>',
            '<property name="secondary">False</property>',
            1,
        )
        self.assert_changed(SORT_UI, source)
        errors = self.failures(contents=self.with_content(SORT_UI, source))
        self.assertTrue(any("footer secondary drift" in e for e in errors), errors)

    def test_ui_load_literal_drift_fails(self) -> None:
        source = self.contents[SORT_CXX].replace(
            "modules/scalc/ui/sortdialog.ui", "modules/scalc/ui/sortdialogX.ui", 1
        )
        self.assert_changed(SORT_CXX, source)
        errors = self.failures(contents=self.with_content(SORT_CXX, source))
        self.assertTrue(any(".ui load-path literal" in e and "missing" in e for e in errors), errors)

    def test_dialog_id_literal_drift_fails(self) -> None:
        source = self.contents[SORT_CXX].replace('"SortDialog"', '"SortDialogX"')
        self.assert_changed(SORT_CXX, source)
        errors = self.failures(contents=self.with_content(SORT_CXX, source))
        self.assertTrue(any("dialog-id literal" in e and "missing" in e for e in errors), errors)

    def test_per_dialog_controller_base_enforced(self) -> None:
        # ScPivotFilterDlg uses GenericDialogController; asserting the wrong (shared)
        # base must fail closed, proving the per-dialog base is not collapsed.
        registry = copy.deepcopy(self.registry)
        self.dialog(registry, "PivotFilterDialog")["controller_base"] = "SfxTabDialogController"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("PivotFilterDialog" in e and "controller base" in e for e in errors), errors
        )

    # -- Part B: generated surface ledger ----------------------------------
    def test_ledger_reclassification_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        for entry in registry["surface_ledger"]["entries"]:
            if entry["classification"] == "standard-anatomy":
                entry["classification"] = "custom-paint-guard-required"
                break
        errors = self.failures(registry=registry)
        self.assertTrue(any("drifted from generated classification" in e for e in errors), errors)

    def test_ledger_missing_entry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surface_ledger"]["entries"] = registry["surface_ledger"]["entries"][1:]
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing from ledger" in e for e in errors), errors)

    def test_ledger_stale_entry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surface_ledger"]["entries"].append(
            {"ui_file": "chart2/uiconfig/ui/phantom.ui", "classification": "standard-anatomy", "evidence": None}
        )
        errors = self.failures(registry=registry)
        self.assertTrue(any("no in-scope source" in e for e in errors), errors)

    def test_ledger_counts_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surface_ledger"]["counts"]["custom_paint"] = 999
        errors = self.failures(registry=registry)
        self.assertTrue(any("counts drift" in e for e in errors), errors)

    def test_custom_paint_evidence_gone_fails_generation(self) -> None:
        # If a custom-paint owner drops its guard member, generation must fail closed.
        mutated = self.contents[DATABROWSER].replace(
            "class DataBrowser : public ::svt::EditBrowseBox",
            "class DataBrowser : public SomeOtherBase",
            1,
        )
        self.assert_changed(DATABROWSER, mutated)
        errors = self.failures(contents=self.with_content(DATABROWSER, mutated))
        self.assertTrue(any("generation failed" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
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
