#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Writer ruler token contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-writer-ruler-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_writer_ruler_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
BRIDGE = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
SWRULER = "sw/source/uibase/misc/swruler.cxx"
RULER = "svtools/source/control/ruler.cxx"


class WriterRulerContractTest(unittest.TestCase):
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

    def assert_mutation_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- definition.xml <style> slot cross-checks (read only) --------------
    def test_style_slot_token_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["style_slots"][0]["token"] = "@primary"
        errors = self.failures(registry=registry)
        self.assertTrue(any("style_slots:windowColor" in e and "token drift" in e for e in errors), errors)

    def test_style_slot_missing_in_definition_fails(self) -> None:
        definition = self.contents[DEFINITION].replace('<windowColor value="@surface"/>', "", 1)
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("style_slots:windowColor missing" in e for e in errors), errors)

    def test_style_slot_definition_value_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<dialogColor value="@surface-container"/>',
            '<dialogColor value="@surface"/>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("style_slots:dialogColor" in e and "token drift" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("palette:@no-such-role" in e for e in errors), errors)

    def test_definition_unparseable_fails(self) -> None:
        errors = self.failures(contents=self.with_content(DEFINITION, "<definition><broken"))
        self.assertTrue(any("unparseable xml" in e for e in errors), errors)

    # -- FileDefinitionWidgetDraw bridge ----------------------------------
    def test_bridge_assignment_commented_out_fails(self) -> None:
        # Commenting the assignment out proves the comment-stripping fail-closed path.
        source = self.contents[BRIDGE].replace(
            "aStyleSet.SetWindowColor(pDefinitionStyle->maWindowColor);",
            "// aStyleSet.SetWindowColor(pDefinitionStyle->maWindowColor);",
            1,
        )
        self.assert_mutation_changed(BRIDGE, source)
        errors = self.failures(contents=self.with_content(BRIDGE, source))
        self.assertTrue(any("bridge:assignment missing in code" in e for e in errors), errors)

    def test_bridge_function_marker_missing_fails(self) -> None:
        source = self.contents[BRIDGE].replace(
            "bool FileDefinitionWidgetDraw::updateSettings(AllSettings& rSettings, bool bUseDarkMode)",
            "bool FileDefinitionWidgetDraw::updateSettingsRenamed(AllSettings& rSettings, bool bUseDarkMode)",
            1,
        )
        self.assert_mutation_changed(BRIDGE, source)
        errors = self.failures(contents=self.with_content(BRIDGE, source))
        self.assertTrue(any("bridge:function marker missing" in e for e in errors), errors)

    def test_bridge_source_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(BRIDGE))
        self.assertTrue(any("bridge:source" in e and "missing" in e for e in errors), errors)

    # -- swruler.cxx comment-toggle paint path ----------------------------
    def test_swruler_delegation_marker_commented_out_fails(self) -> None:
        source = self.contents[SWRULER].replace(
            "SvxRuler::Paint(rRenderContext, rRect);",
            "// SvxRuler::Paint(rRenderContext, rRect);",
            1,
        )
        self.assert_mutation_changed(SWRULER, source)
        errors = self.failures(contents=self.with_content(SWRULER, source))
        self.assertTrue(
            any("writer.ruler.comment-toggle" in e and "delegation marker missing" in e for e in errors),
            errors,
        )

    def test_swruler_color_marker_dropped_fails(self) -> None:
        source = self.contents[SWRULER].replace(
            "rStyleSettings.GetButtonTextColor()", "rStyleSettings.GetFieldTextColor()"
        )
        self.assert_mutation_changed(SWRULER, source)
        errors = self.failures(contents=self.with_content(SWRULER, source))
        self.assertTrue(
            any("writer.ruler.comment-toggle" in e and "marker missing in code" in e for e in errors),
            errors,
        )

    def test_swruler_source_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(SWRULER))
        self.assertTrue(
            any("writer.ruler.comment-toggle" in e and "source" in e and "missing" in e for e in errors),
            errors,
        )

    # -- shared ruler.cxx band paint path ---------------------------------
    def test_ruler_page_track_marker_dropped_fails(self) -> None:
        source = self.contents[RULER].replace(
            "aRulerColor = rStyleSettings.GetWindowColor();",
            "aRulerColor = rStyleSettings.GetFieldColor();",
            1,
        )
        self.assert_mutation_changed(RULER, source)
        errors = self.failures(contents=self.with_content(RULER, source))
        self.assertTrue(
            any("writer.ruler.shared-band" in e and "marker missing in code" in e for e in errors),
            errors,
        )

    def test_ruler_border_marker_dropped_fails(self) -> None:
        source = self.contents[RULER].replace(
            "rStyleSettings.GetFaceColor()", "rStyleSettings.GetDisableColor()"
        )
        self.assert_mutation_changed(RULER, source)
        errors = self.failures(contents=self.with_content(RULER, source))
        self.assertTrue(
            any("writer.ruler.shared-band" in e and "marker missing in code" in e for e in errors),
            errors,
        )

    # -- ThemeColors carve-out --------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveout"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveout:status:must stay 'specified'" in e for e in errors), errors)

    def test_carveout_branch_marker_missing_fails(self) -> None:
        source = self.contents[RULER].replace(
            "if (ThemeColors::IsThemeEnabled())", "if (false)", 1
        )
        self.assert_mutation_changed(RULER, source)
        errors = self.failures(contents=self.with_content(RULER, source))
        self.assertTrue(any("carveout:branch marker missing" in e for e in errors), errors)

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

    def test_status_must_be_source_declared(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["status"] = "runtime-verified"
        errors = self.failures(registry=registry)
        self.assertIn("registry:status:must be source-declared", errors)

    def test_empty_style_slots_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["style_slots"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("style_slots:non-empty array required" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
