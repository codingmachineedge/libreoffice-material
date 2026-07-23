#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the WIN-FND-006 adaptive-layout ledger."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-adaptive-layout-ledger.py"
SPEC = importlib.util.spec_from_file_location("check_windows_adaptive_layout_ledger", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class AdaptiveLayoutLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.sibling, self.scanned, self.design_text = VALIDATOR.load_repository(
            REPOSITORY
        )

    def failures(self, *, registry=None, sibling=..., scanned=None, design_text=...) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.sibling if sibling is ... else sibling,
            self.scanned if scanned is None else scanned,
            self.design_text if design_text is ... else design_text,
        )

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    def native_entry(self, registry: dict) -> dict:
        for entry in registry["anchors"]:
            if entry.get("status") == "native-anchor":
                return entry
        raise AssertionError("no native anchor in registry")

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- cross-reference with the sidebar-panels contract ------------------
    def test_threshold_value_disagreement_fails(self) -> None:
        registry = self.registry_copy()
        self.native_entry(registry)["threshold_value"] = 999
        errors = self.failures(registry=registry)
        self.assertTrue(any("cross_reference:" in e and "disagrees" in e for e in errors), errors)

    def test_consuming_function_disagreement_fails(self) -> None:
        registry = self.registry_copy()
        self.native_entry(registry)["consuming_function"] = "ShouldSomethingElse"
        errors = self.failures(registry=registry)
        self.assertTrue(any("cross_reference:consuming_function" in e for e in errors), errors)

    def test_sibling_missing_fails(self) -> None:
        errors = self.failures(sibling=None)
        self.assertTrue(any("cross_reference:" in e and "missing" in e for e in errors), errors)

    def test_sibling_drift_detected(self) -> None:
        # If the sidebar-panels contract changed the locked value, the ledger must
        # stop agreeing rather than silently pass.
        sibling = copy.deepcopy(self.sibling)
        for metric in sibling["metrics"]:
            if metric.get("slot") == "Int_DeckOverlayMinWidth":
                metric["value"] = 720
        errors = self.failures(sibling=sibling)
        self.assertTrue(any("cross_reference:Int_DeckOverlayMinWidth" in e for e in errors), errors)

    def test_unknown_locked_slot_fails(self) -> None:
        registry = self.registry_copy()
        self.native_entry(registry)["threshold_slot"] = "Int_PhantomMinWidth"
        # scanned still reports the real slot only -> negative-space + cross-ref both fire.
        errors = self.failures(registry=registry)
        self.assertTrue(any("cross_reference:Int_PhantomMinWidth" in e for e in errors), errors)

    # -- negative-space guard ----------------------------------------------
    def test_new_unenumerated_breakpoint_fails(self) -> None:
        errors = self.failures(scanned=sorted(self.scanned + ["Int_ToolbarOverflowMinWidth"]))
        self.assertTrue(
            any("negative_space" in e and "does not enumerate" in e for e in errors), errors
        )

    def test_enumerated_anchor_disappeared_fails(self) -> None:
        errors = self.failures(scanned=[])
        self.assertTrue(
            any("negative_space" in e and "no longer present" in e for e in errors), errors
        )

    # -- enumeration completeness ------------------------------------------
    def test_missing_target_placeholder_fails(self) -> None:
        registry = self.registry_copy()
        registry["anchors"] = [
            e for e in registry["anchors"] if e.get("inventory_row") != "WIN-SHL-002"
        ]
        errors = self.failures(registry=registry)
        self.assertTrue(any("WIN-SHL-002" in e and "placeholder" in e for e in errors), errors)

    def test_no_native_anchor_fails(self) -> None:
        registry = self.registry_copy()
        for entry in registry["anchors"]:
            if entry.get("status") == "native-anchor":
                entry["status"] = "target-no-native-anchor"
        errors = self.failures(registry=registry)
        self.assertTrue(any("at least one native-anchor" in e for e in errors), errors)

    def test_bad_status_fails(self) -> None:
        registry = self.registry_copy()
        registry["anchors"][1]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("status must be" in e for e in errors), errors)

    # -- design prose cross-reference --------------------------------------
    def test_missing_design_anchor_fails(self) -> None:
        errors = self.failures(design_text="no adaptive layout section here")
        self.assertTrue(any("design_ref:" in e and "section anchor" in e for e in errors), errors)

    def test_missing_class_marker_fails(self) -> None:
        text = self.design_text.replace("toolbars overflow from the end", "toolbars stay put")
        self.assertNotEqual(text, self.design_text)
        errors = self.failures(design_text=text)
        self.assertTrue(any("window-class behaviour" in e for e in errors), errors)

    def test_missing_design_file_fails(self) -> None:
        errors = self.failures(design_text=None)
        self.assertTrue(any("design chapter is missing" in e for e in errors), errors)

    # -- meta --------------------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:contract" in e for e in errors), errors)

    def test_inventory_row_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["inventory_row"] = "WIN-FND-999"
        errors = self.failures(registry=registry)
        self.assertTrue(any("inventory_row:must be WIN-FND-006" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
