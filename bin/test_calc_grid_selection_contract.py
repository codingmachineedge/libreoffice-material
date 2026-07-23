#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Calc grid header/selection colour contract (WIN-CA-003)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-calc-grid-selection-contract.py"
SPEC = importlib.util.spec_from_file_location("check_calc_grid_selection_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
COLORCFG = "svtools/source/config/colorcfg.cxx"
HDRCONT = "sc/source/ui/view/hdrcont.cxx"
GRIDWIN = "sc/source/ui/view/gridwin.cxx"
GRIDWIN4 = "sc/source/ui/view/gridwin4.cxx"


class CalcGridSelectionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
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

    def assert_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- definition.xml token/palette fidelity -----------------------------
    def test_style_slot_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<accentColor value="@primary"/>', '<accentColor value="@surface"/>', 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("style_slots:accentColor" in e and "token drift" in e for e in errors), errors)

    def test_palette_role_missing_in_dark_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="primary" value="#D0BCFF"/>', "", 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("@primary missing from the dark palette" in e for e in errors), errors)

    # -- colorcfg accent bridge --------------------------------------------
    def test_colorcfg_bridge_marker_removed_fails(self) -> None:
        source = self.contents[COLORCFG].replace("case CALCCELLFOCUS:", "case CALCCELLFOCUS_X:", 1)
        self.assert_changed(COLORCFG, source)
        errors = self.failures(contents=self.with_content(COLORCFG, source))
        self.assertTrue(any("colorcfg_bridge:marker missing" in e for e in errors), errors)

    # -- sc paint call sites -----------------------------------------------
    def test_header_marker_removed_fails(self) -> None:
        source = self.contents[HDRCONT].replace(
            "Color aColor = mod->GetColorConfig().GetColorValue(svtools::CALCCELLFOCUS).nColor;",
            "Color aColor = COL_LIGHTBLUE;",
            1,
        )
        self.assert_changed(HDRCONT, source)
        errors = self.failures(contents=self.with_content(HDRCONT, source))
        self.assertTrue(any("header_highlight:marker missing" in e for e in errors), errors)

    def test_cell_cursor_marker_removed_fails(self) -> None:
        source = self.contents[GRIDWIN].replace(
            "Color aCursorColor = mod->GetColorConfig().GetColorValue(svtools::CALCCELLFOCUS).nColor;",
            "Color aCursorColor = COL_BLACK;",
            1,
        )
        self.assert_changed(GRIDWIN, source)
        errors = self.failures(contents=self.with_content(GRIDWIN, source))
        self.assertTrue(any("cell_cursor" in e and "marker missing" in e for e in errors), errors)

    def test_commented_out_marker_fails(self) -> None:
        # Comment-out the DB-range consumption; comments are stripped, so it must fail closed.
        source = self.contents[GRIDWIN].replace(
            "Color aDBColor = mod->GetColorConfig().GetColorValue(svtools::CALCDBFOCUS).nColor;",
            "// Color aDBColor = mod->GetColorConfig().GetColorValue(svtools::CALCDBFOCUS).nColor;",
            1,
        )
        self.assert_changed(GRIDWIN, source)
        errors = self.failures(contents=self.with_content(GRIDWIN, source))
        self.assertTrue(any("cell_cursor" in e and "marker missing" in e for e in errors), errors)

    def test_source_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(COLORCFG))
        self.assertTrue(any("source" in e and "missing" in e for e in errors), errors)

    # -- carve-out honesty guards ------------------------------------------
    def test_density_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["density"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:density:status:must stay 'specified'" in e for e in errors), errors)

    def test_alignment_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["alignment"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:alignment:status:must stay 'specified'" in e for e in errors), errors)

    def test_gridlines_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["gridlines"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:gridlines:status:must stay 'divergent'" in e for e in errors), errors)

    def test_gridlines_present_marker_removed_fails(self) -> None:
        source = self.contents[GRIDWIN4].replace("svtools::CALCGRID ", "svtools::CALCGRIDX ", 1)
        self.assert_changed(GRIDWIN4, source)
        errors = self.failures(contents=self.with_content(GRIDWIN4, source))
        self.assertTrue(any("gridlines:present_marker missing" in e for e in errors), errors)

    def test_gridlines_absent_marker_now_present_fails_closed(self) -> None:
        # Simulate a future commit that Material-routes CALCGRID by adding a switch case:
        # the checker must fail closed until the registry status is flipped in the SAME change.
        source = self.contents[COLORCFG].replace(
            "case CALCDBFOCUS:",
            "case CALCGRID:\n            aRet = Application::GetSettings().GetStyleSettings().GetAccentColor();\n            break;\n\n        case CALCDBFOCUS:",
            1,
        )
        self.assert_changed(COLORCFG, source)
        errors = self.failures(contents=self.with_content(COLORCFG, source))
        self.assertTrue(any("gridlines:absent_marker now PRESENT" in e for e in errors), errors)

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

    def test_definition_file_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["definition_file"] = "vcl/uiconfig/theme_definitions/other.xml"
        errors = self.failures(registry=registry)
        self.assertIn("registry:definition_file:unexpected path", errors)


if __name__ == "__main__":
    unittest.main()
