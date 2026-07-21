#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Calc sheet-tab contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-calc-sheet-tabs.py"
SPEC = importlib.util.spec_from_file_location("check_windows_calc_sheet_tabs", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
TABCONT = "sc/source/ui/view/tabcont.cxx"
TABCONT_HXX = "sc/source/ui/inc/tabcont.hxx"


class CalcSheetTabContractTest(unittest.TestCase):
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
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("token drift" in e for e in errors), errors)

    def test_missing_part_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<tabheader><part value="Entire">', '<tabheader><part value="Renamed">', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("missing in definition.xml" in e for e in errors), errors)

    def test_part_attr_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            'height="@height-tab"', 'height="@size-standard-control"', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("attribute height" in e for e in errors), errors)

    def test_missing_state_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" focused="true"><rect stroke="@primary" '
            'fill="@surface-container" stroke-width="@stroke-standard" radius="@corner-pill"/></state>',
            "",
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    # -- guarded token consumption / comment-only wiring ------------------
    def test_comment_only_token_wiring_fails(self) -> None:
        source = self.contents[TABCONT].replace(
            '    const std::optional<Color> oOutlineVariant = aTokens.findColor("outline-variant");',
            '    // const std::optional<Color> oOutlineVariant = aTokens.findColor("outline-variant");',
            1,
        )
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(any(":token-consumption:marker missing" in e for e in errors), errors)

    def test_token_include_required(self) -> None:
        source = self.contents[TABCONT].replace("#include <vcl/MaterialTokens.hxx>", "", 1)
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(any(":token-consumption:missing #include" in e for e in errors), errors)

    def test_missing_activation_guard_fails(self) -> None:
        source = self.contents[TABCONT].replace("VCL_FILE_WIDGET_THEME", "VCL_THEME_RENAMED")
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(any("missing activation guard" in e for e in errors), errors)

    def test_missing_high_contrast_guard_fails(self) -> None:
        source = self.contents[TABCONT].replace("GetHighContrastMode", "GetSomethingElse", 1)
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(any("missing high-contrast guard" in e for e in errors), errors)

    # -- additive paint override ------------------------------------------
    def test_override_must_call_base_paint(self) -> None:
        source = self.contents[TABCONT].replace("TabBar::Paint( rRenderContext, rRect );", "", 1)
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(
            any("override must call the base paint" in e for e in errors), errors
        )

    def test_paint_marker_missing_fails(self) -> None:
        # Replace every occurrence (the marker also appears in a code comment,
        # which the checker strips) so it is genuinely absent from the code.
        source = self.contents[TABCONT].replace("GetPageArea()", "GetNothing()")
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(any(":paint-layout:marker missing" in e for e in errors), errors)

    def test_header_marker_missing_fails(self) -> None:
        header = self.contents[TABCONT_HXX].replace(
            "Paint( vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect ) override;",
            "",
            1,
        )
        self.assert_mutation_changed(TABCONT_HXX, header)
        errors = self.failures(contents=self.with_content(TABCONT_HXX, header))
        self.assertTrue(any(":paint-layout:header marker missing" in e for e in errors), errors)

    # -- colour-strip independence (accessibility) ------------------------
    def test_accent_consulting_selection_fails(self) -> None:
        source = self.contents[TABCONT].replace(
            "        rRenderContext.SetFillColor( aColor );",
            "        if (IsPageSelected(nPageId)) rRenderContext.SetFillColor( aColor );",
            1,
        )
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(
            any(":color-strip:" in e and "must not consult the selection state" in e for e in errors),
            errors,
        )

    def test_accent_must_draw_from_colour_map(self) -> None:
        source = self.contents[TABCONT].replace(
            "        rRenderContext.DrawRect( aAccent );", "", 1
        )
        self.assert_mutation_changed(TABCONT, source)
        errors = self.failures(contents=self.with_content(TABCONT, source))
        self.assertTrue(
            any(":color-strip:" in e and "must draw from the colour map" in e for e in errors),
            errors,
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
        self.assertTrue(any("missing required calc.sheet-tabs" in e for e in errors), errors)

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


if __name__ == "__main__":
    unittest.main()
