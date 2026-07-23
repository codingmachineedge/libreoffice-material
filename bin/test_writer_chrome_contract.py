#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Writer classic chrome contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-writer-chrome-contract.py"
SPEC = importlib.util.spec_from_file_location("check_writer_chrome_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
FMT = "sw/uiconfig/swriter/toolbar/textobjectbar.xml"
STD = "sw/uiconfig/swriter/toolbar/standardbar.xml"
MENU = "sw/uiconfig/swriter/menubar/menubar.xml"


class WriterChromeContractTest(unittest.TestCase):
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

    # -- definition.xml chrome-part cross-checks (read only) ---------------
    def test_button_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none" radius="@corner-toolbar"/></state>',
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface" stroke-width="@stroke-none" radius="@corner-toolbar"/></state>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("chrome_parts:button" in e and "token drift" in e for e in errors), errors)

    def test_button_missing_state_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" focused="true"><rect stroke="@primary" '
            'fill="@surface-container" stroke-width="@stroke-standard" radius="@corner-toolbar"/></state>',
            "",
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    def test_band_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="DrawBackgroundHorz"><state><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none"/></state></part>',
            '<part value="DrawBackgroundHorz"><state><rect stroke="@surface-container" '
            'fill="@surface" stroke-width="@stroke-none"/></state></part>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("chrome_parts:band" in e and "token drift" in e for e in errors), errors)

    def test_missing_part_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="DrawBackgroundHorz">', '<part value="DrawBackgroundHorzX">', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("missing in definition.xml" in e for e in errors), errors)

    def test_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<radius name="corner-toolbar" value="18"/>',
            '<radius name="corner-toolbar" value="16"/>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("metric drift" in e for e in errors), errors)

    def test_separator_token_drift_via_registry_fails(self) -> None:
        # A registry that expects the wrong separator stroke must be caught against
        # the real (correct) definition.xml -- proves the separator path compares.
        registry = copy.deepcopy(self.registry)
        registry["chrome_parts"]["separator"]["tokens"]["stroke"] = "@primary"
        errors = self.failures(registry=registry)
        self.assertTrue(any("chrome_parts:separator" in e and "token drift" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["chrome_parts"]["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("chrome_parts:palette:@no-such-role" in e for e in errors), errors)

    # -- toolbar composition pinning --------------------------------------
    def test_command_identity_drift_fails(self) -> None:
        source = self.contents[FMT].replace(
            'xlink:href=".uno:Bold"', 'xlink:href=".uno:BoldX"', 1
        )
        self.assert_mutation_changed(FMT, source)
        errors = self.failures(contents=self.with_content(FMT, source))
        self.assertTrue(any("command drift" in e for e in errors), errors)

    def test_visibility_flip_fails(self) -> None:
        source = self.contents[FMT].replace(
            '<toolbar:toolbaritem xlink:href=".uno:CharFontName"/>',
            '<toolbar:toolbaritem xlink:href=".uno:CharFontName" toolbar:visible="false"/>',
            1,
        )
        self.assert_mutation_changed(FMT, source)
        errors = self.failures(contents=self.with_content(FMT, source))
        self.assertTrue(any("visibility drift" in e for e in errors), errors)
        # And a hidden design-core command is separately flagged.
        self.assertTrue(any("present but hidden" in e for e in errors), errors)

    def test_separator_removed_composition_drift_fails(self) -> None:
        source = self.contents[FMT].replace(" <toolbar:toolbarseparator/>\n", "", 1)
        self.assert_mutation_changed(FMT, source)
        errors = self.failures(contents=self.with_content(FMT, source))
        self.assertTrue(
            any("composition drift" in e or ":sequence:length" in e for e in errors), errors
        )

    def test_preserved_expert_command_removed_fails(self) -> None:
        # Rename a hidden expert command in place (keeps length -> targeted failure):
        # the expert command must never be rebound or removed.
        source = self.contents[FMT].replace(
            'xlink:href=".uno:Overline"', 'xlink:href=".uno:OverlineX"', 1
        )
        self.assert_mutation_changed(FMT, source)
        errors = self.failures(contents=self.with_content(FMT, source))
        self.assertTrue(
            any("preserved_commands" in e and "removed" in e for e in errors), errors
        )

    def test_standard_toolbar_command_drift_fails(self) -> None:
        source = self.contents[STD].replace(
            'xlink:href=".uno:Save"', 'xlink:href=".uno:SaveX"', 1
        )
        self.assert_mutation_changed(STD, source)
        errors = self.failures(contents=self.with_content(STD, source))
        self.assertTrue(any("toolbar[standard]" in e and "command drift" in e for e in errors), errors)

    def test_toolbar_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(FMT))
        self.assertTrue(any("file missing" in e for e in errors), errors)

    def test_toolbar_unparseable_fails(self) -> None:
        errors = self.failures(contents=self.with_content(FMT, "<toolbar:toolbar><broken"))
        self.assertTrue(any("unparseable xml" in e for e in errors), errors)

    # -- menu bar composition ---------------------------------------------
    def test_menu_top_level_drift_fails(self) -> None:
        source = self.contents[MENU].replace(
            '<menu:menu menu:id=".uno:ViewMenu">', '<menu:menu menu:id=".uno:ViewMenuX">', 1
        )
        self.assert_mutation_changed(MENU, source)
        errors = self.failures(contents=self.with_content(MENU, source))
        self.assertTrue(any("menu:top_level" in e for e in errors), errors)
        self.assertTrue(any("menu:design_core" in e and ".uno:ViewMenu" in e for e in errors), errors)

    def test_menu_writer_specific_toplevel_drift_fails(self) -> None:
        # Writer's TableMenu is the real Writer-vs-Calc divergence; renaming it must
        # break the pinned top-level sequence and the design-core presence check.
        source = self.contents[MENU].replace(
            '<menu:menu menu:id=".uno:TableMenu">', '<menu:menu menu:id=".uno:SheetMenu">', 1
        )
        self.assert_mutation_changed(MENU, source)
        errors = self.failures(contents=self.with_content(MENU, source))
        self.assertTrue(any("menu:top_level" in e for e in errors), errors)
        self.assertTrue(any("menu:design_core" in e and ".uno:TableMenu" in e for e in errors), errors)

    def test_menu_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(MENU))
        self.assertTrue(any("menu:file missing" in e for e in errors), errors)

    # -- honest carve-out guards ------------------------------------------
    def test_density_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["density"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("density:status:must stay 'specified'" in e for e in errors), errors)

    def test_combo_annotations_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["combo_annotations"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("combo_annotations:status:must stay 'specified'" in e for e in errors), errors
        )

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

    def test_missing_required_toolbar_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["toolbars"][0]["id"] = "renamed"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required FMT.writer" in e for e in errors), errors)

    def test_empty_sequence_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["toolbars"][0]["sequence"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("sequence:non-empty array required" in e for e in errors), errors)

    def test_design_core_dropped_from_registry_still_present(self) -> None:
        # If the registry drops a design_core entry it is a weaker contract, but the
        # empty-array guard must still fire when someone blanks it entirely.
        registry = copy.deepcopy(self.registry)
        registry["toolbars"][0]["design_core"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("design_core:non-empty array required" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
