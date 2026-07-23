#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the chart editor composition contract (WIN-CH-001).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree and
asserts the checker fails closed, while the pristine production tree passes. The real repository is
never mutated: every mutation is applied to the ``contents`` map ``load_repository`` returns or to a
deep copy of the registry.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-chart-editor-contract.py"
SPEC = importlib.util.spec_from_file_location("check_chart_editor_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
TOOLBAR = "chart2/uiconfig/toolbar/toolbar.xml"
MENUBAR = "chart2/uiconfig/menubar/menubar.xml"
FACTORY = "chart2/source/controller/sidebar/Chart2PanelFactory.cxx"
SIDEBAR_ELEMENTS = "chart2/uiconfig/ui/sidebarelements.ui"


class ChartEditorContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
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

    # -- definition.xml native toolbar parts -----------------------------------
    def test_chrome_part_token_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["chrome_parts"]["entire"]["tokens"]["fill"] = "@surface"
        errors = self.failures(registry=registry)
        self.assertTrue(any("chrome_parts:entire" in e and "token drift" in e for e in errors), errors)

    def test_chrome_palette_role_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["chrome_parts"]["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("chrome_parts:palette:@no-such-role" in e for e in errors), errors)

    def test_definition_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DEFINITION))
        self.assertTrue(any("definition:file missing" in e for e in errors), errors)

    # -- toolbar.xml composition -----------------------------------------------
    def test_toolbar_visibility_drift_fails(self) -> None:
        contents = self.replace_once(
            TOOLBAR,
            '<toolbar:toolbaritem xlink:href=".uno:ScaleText" toolbar:visible="false"/>',
            '<toolbar:toolbaritem xlink:href=".uno:ScaleText"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("visibility drift" in e and ".uno:ScaleText" in e for e in errors), errors)

    def test_toolbar_command_drift_fails(self) -> None:
        contents = self.replace_once(
            TOOLBAR,
            '<toolbar:toolbaritem xlink:href=".uno:FormatSelection"/>',
            '<toolbar:toolbaritem xlink:href=".uno:FormatSelectionX"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("command drift" in e for e in errors), errors)

    def test_toolbar_item_removed_fails(self) -> None:
        contents = self.replace_once(
            TOOLBAR, ' <toolbar:toolbaritem xlink:href=".uno:Legend"/>\n', ""
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("sequence:length" in e for e in errors), errors)

    def test_toolbar_design_core_hidden_fails(self) -> None:
        contents = self.replace_once(
            TOOLBAR,
            '<toolbar:toolbaritem xlink:href=".uno:DiagramType"/>',
            '<toolbar:toolbaritem xlink:href=".uno:DiagramType" toolbar:visible="false"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("design_core:.uno:DiagramType" in e and "hidden" in e for e in errors), errors
        )

    def test_toolbar_preserved_removed_fails(self) -> None:
        contents = self.replace_once(
            TOOLBAR,
            ' <toolbar:toolbaritem xlink:href=".uno:NewArrangement" toolbar:visible="false"/>\n',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("preserved_commands:.uno:NewArrangement removed" in e for e in errors), errors
        )

    # -- menubar.xml composition -----------------------------------------------
    def test_menu_top_level_drift_fails(self) -> None:
        contents = self.replace_once(
            MENUBAR, 'menu:id=".uno:InsertMenu"', 'menu:id=".uno:InsertMenuX"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("menu:top_level" in e and "drift" in e for e in errors), errors)

    # -- Chart2PanelFactory.cxx routes -----------------------------------------
    def test_factory_route_removed_fails(self) -> None:
        contents = self.replace_once(
            FACTORY, 'rsResourceURL.endsWith("/ColorsPanel")', 'rsResourceURL.endsWith("/ColorsPanelX")'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("factory:route" in e and "/ColorsPanel" in e for e in errors), errors)

    def test_factory_implementation_name_drift_fails(self) -> None:
        contents = self.replace_once(
            FACTORY,
            'u"org.libreoffice.comp.chart2.sidebar.ChartPanelFactory"_ustr',
            'u"org.libreoffice.comp.chart2.sidebar.ChartPanelFactoryX"_ustr',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("factory:implementation_name" in e for e in errors), errors)

    def test_factory_route_commented_out_fails(self) -> None:
        # A commented-out route is stripped and must not satisfy the marker.
        contents = self.replace_once(
            FACTORY,
            'else if (rsResourceURL.endsWith("/AxisPanel"))',
            '// else if (rsResourceURL.endsWith("/AxisPanel"))',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("factory:route" in e and "/AxisPanel" in e for e in errors), errors)

    # -- sidebar .ui panel ids -------------------------------------------------
    def test_sidebar_panel_id_removed_fails(self) -> None:
        contents = self.replace_once(
            SIDEBAR_ELEMENTS,
            '<object class="GtkGrid" id="ChartElementsPanel">',
            '<object class="GtkGrid" id="ChartElementsPanelX">',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("sidebar_panels" in e and "ChartElementsPanel" in e for e in errors), errors
        )

    # -- honest carve-outs -----------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveouts"]["chart_canvas"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("carveouts:chart_canvas:status must stay 'specified'" in e for e in errors), errors
        )

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

    def test_inventory_row_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["inventory_row"] = "WIN-CH-000"
        errors = self.failures(registry=registry)
        self.assertIn("registry:inventory_row:must be WIN-CH-001", errors)

    def test_definition_file_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["definition_file"] = "vcl/uiconfig/theme_definitions/other.xml"
        errors = self.failures(registry=registry)
        self.assertIn("registry:definition_file:unexpected path", errors)


if __name__ == "__main__":
    unittest.main()
