#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Calc formula-bar contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-calc-formula-bar-contract.py"
SPEC = importlib.util.spec_from_file_location("check_calc_formula_bar_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
INPUTWIN = "sc/source/ui/app/inputwin.cxx"
INPUTWIN_HXX = "sc/source/ui/inc/inputwin.hxx"


class CalcFormulaBarContractTest(unittest.TestCase):
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

    def assert_mutation_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- definition-part token drift (definition.xml is read only) ---------
    def test_token_drift_fails(self) -> None:
        # First occurrence of this idle rect is the combobox (Name Box) part.
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true"><rect stroke="@outline" fill="@surface" '
            'stroke-width="@stroke-thin" radius="@corner-container"/></state>',
            '<state enabled="true"><rect stroke="@outline" fill="@primary" '
            'stroke-width="@stroke-thin" radius="@corner-container"/></state>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("token drift" in e for e in errors), errors)

    def test_missing_part_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<editbox>\n        <part value="Entire" height="@size-standard-control">',
            '<editbox>\n        <part value="Renamed" height="@size-standard-control">',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("missing in definition.xml" in e for e in errors), errors)

    def test_part_attr_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<editbox>\n        <part value="Entire" height="@size-standard-control">',
            '<editbox>\n        <part value="Entire" height="@height-tab">',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("attribute height" in e for e in errors), errors)

    def test_missing_state_fails(self) -> None:
        # First occurrence of this focus rect is the combobox (Name Box) part.
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" focused="true"><rect stroke="@primary" '
            'fill="@surface" stroke-width="@stroke-standard" radius="@corner-container"/></state>',
            "",
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    # -- guarded token consumption / comment-only wiring ------------------
    def test_comment_only_token_wiring_fails(self) -> None:
        source = self.contents[INPUTWIN].replace(
            '    const std::optional<Color> oOutlineVariant = aTokens.findColor("outline-variant");',
            '    // const std::optional<Color> oOutlineVariant = aTokens.findColor("outline-variant");',
            1,
        )
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any(":token-consumption:marker missing" in e for e in errors), errors)

    def test_token_include_required(self) -> None:
        source = self.contents[INPUTWIN].replace("#include <vcl/MaterialTokens.hxx>", "", 1)
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any(":token-consumption:missing #include" in e for e in errors), errors)

    def test_missing_activation_guard_fails(self) -> None:
        source = self.contents[INPUTWIN].replace("VCL_FILE_WIDGET_THEME", "VCL_THEME_RENAMED")
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any("missing activation guard" in e for e in errors), errors)

    def test_missing_high_contrast_guard_fails(self) -> None:
        source = self.contents[INPUTWIN].replace("GetHighContrastMode", "GetSomethingElse", 1)
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any("missing high-contrast guard" in e for e in errors), errors)

    # -- additive paint override ------------------------------------------
    def test_override_must_call_base_paint(self) -> None:
        source = self.contents[INPUTWIN].replace("ToolBox::Paint( rRenderContext, rRect );", "", 1)
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(
            any("override must call the base paint" in e for e in errors), errors
        )

    def test_paint_marker_missing_fails(self) -> None:
        source = self.contents[INPUTWIN].replace("DrawLine(", "DrawNothing(")
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any(":paint-layout:marker missing" in e for e in errors), errors)

    def test_header_marker_missing_fails(self) -> None:
        header = self.contents[INPUTWIN_HXX].replace("bool            mbFormulaRowRTL;", "", 1)
        self.assert_mutation_changed(INPUTWIN_HXX, header)
        errors = self.failures(contents=self.with_content(INPUTWIN_HXX, header))
        self.assertTrue(any(":paint-layout:header marker missing" in e for e in errors), errors)

    # -- centralized field/text token consumption -------------------------
    def test_accessor_missing_token_fails(self) -> None:
        source = self.contents[INPUTWIN].replace(
            "        return oTokens->aSurface;",
            "        return rStyleSettings.GetFieldColor();",
            1,
        )
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(
            any(":field-centralization:" in e and "must contain" in e for e in errors), errors
        )

    def test_call_site_floor_fails(self) -> None:
        # Route one editbox fill site back at the generic slot: drops below floor.
        source = self.contents[INPUTWIN].replace(
            "lcl_getFormulaFieldColor(rStyleSettings)",
            "rStyleSettings.GetFieldColor()",
            1,
        )
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(
            any(":field-centralization:" in e and "call site" in e for e in errors), errors
        )

    # -- 10.4 RTL order swap ----------------------------------------------
    def test_rtl_order_marker_missing_fails(self) -> None:
        source = self.contents[INPUTWIN].replace(
            "mxTextWindow.get(), ToolBoxItemBits::NONE, 7",
            "mxTextWindow.get(), ToolBoxItemBits::NONE, 3",
            1,
        )
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(any(":rtl-order:order marker missing" in e for e in errors), errors)

    def test_rtl_rule_must_consume_direction_fails(self) -> None:
        source = self.contents[INPUTWIN].replace(
            "const tools::Long nLeadingX = mbFormulaRowRTL ? aOutputSize.Width() - 1 : 0;\n"
            "    const tools::Long nTrailingX = mbFormulaRowRTL ? 0 : aOutputSize.Width() - 1;",
            "const tools::Long nLeadingX = 0;\n"
            "    const tools::Long nTrailingX = aOutputSize.Width() - 1;",
            1,
        )
        self.assert_mutation_changed(INPUTWIN, source)
        errors = self.failures(contents=self.with_content(INPUTWIN, source))
        self.assertTrue(
            any(":rtl-order:" in e and "must consume" in e for e in errors), errors
        )

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][0]["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_expected_surfaces_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["expected_surfaces"] = 99
        errors = self.failures(registry=registry)
        self.assertIn("registry:expected_surfaces:count drift", errors)

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

    def test_missing_required_surface_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][0]["surface_id"] = "calc.renamed"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required calc.formula-bar" in e for e in errors), errors)

    def test_owner_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][0]["owner_sources"].append("sc/source/does/not/exist.cxx")
        errors = self.failures(registry=registry)
        self.assertTrue(any(":owner_source:missing" in e for e in errors), errors)

    def test_empty_definition_parts_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][0]["definition_parts"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("definition_parts:non-empty array required" in e for e in errors), errors)

    def test_missing_token_block_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["surfaces"][0]["guarded_token_consumption"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("guarded_token_consumption:object required" in e for e in errors), errors)

    def test_missing_field_block_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["surfaces"][0]["field_token_centralization"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("field_token_centralization:object required" in e for e in errors), errors)

    def test_missing_rtl_block_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["surfaces"][0]["rtl_order"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("rtl_order:object required" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
