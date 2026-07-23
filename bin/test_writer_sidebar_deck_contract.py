#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Writer sidebar-decks contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-writer-sidebar-deck-contract.py"
SPEC = importlib.util.spec_from_file_location("check_writer_sidebar_deck_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

PAGE_CXX = "sw/source/uibase/sidebar/PageStylesPanel.cxx"
PAGE_UI = "sw/uiconfig/swriter/ui/pagestylespanel.ui"
NAV_CXX = "sw/source/uibase/utlui/navipi.cxx"
FACTORY = "sw/source/uibase/sidebar/SwPanelFactory.cxx"


class WriterSidebarDeckContractTest(unittest.TestCase):
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

    def surface(self, registry: dict, sid: str) -> dict:
        return next(s for s in registry["surfaces"] if s["surface_id"] == sid)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- widget bindings ---------------------------------------------------
    def test_widget_id_missing_in_ui_fails(self) -> None:
        source = self.contents[PAGE_UI].replace('id="lbcolor"', 'id="lbcolorX"', 1)
        self.assert_mutation_changed(PAGE_UI, source)
        errors = self.failures(contents=self.with_content(PAGE_UI, source))
        self.assertTrue(any("widget_binding:lbcolor missing from" in e for e in errors), errors)

    def test_widget_class_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.surface(registry, "writer.sidebar.page-styles")["widget_bindings"][0]["gtk_class"] = "GtkButton"
        errors = self.failures(registry=registry)
        self.assertTrue(any("widget_binding:lbcolor class is" in e for e in errors), errors)

    def test_weld_binding_dropped_in_code_fails(self) -> None:
        source = self.contents[PAGE_CXX].replace(
            'weld_menu_button(u"lbcolor"_ustr)', 'weld_menu_button(u"lbcolorX"_ustr)', 1
        )
        self.assert_mutation_changed(PAGE_CXX, source)
        errors = self.failures(contents=self.with_content(PAGE_CXX, source))
        self.assertTrue(any("widget_binding:lbcolor not bound in code" in e for e in errors), errors)

    # -- factory routing ---------------------------------------------------
    def test_factory_dispatch_removed_fails(self) -> None:
        source = self.contents[FACTORY].replace(
            'rsResourceURL.endsWith("/PageStylesPanel")',
            'rsResourceURL.endsWith("/PageStylesPanelX")',
            1,
        )
        self.assert_mutation_changed(FACTORY, source)
        errors = self.failures(contents=self.with_content(FACTORY, source))
        self.assertTrue(any("factory_routing:dispatch missing" in e for e in errors), errors)

    def test_factory_create_call_removed_fails(self) -> None:
        source = self.contents[FACTORY].replace("PageStylesPanel::Create", "PageStylesPanelZ::Create", 1)
        self.assert_mutation_changed(FACTORY, source)
        errors = self.failures(contents=self.with_content(FACTORY, source))
        self.assertTrue(any("factory_routing:create call missing" in e for e in errors), errors)

    # -- PageStyles fill-switch (GRADIENT two-visible + NONE hidden) -------
    def test_gradient_two_visible_flip_fails(self) -> None:
        # GRADIENT is the only branch where the gradient list is shown; flipping it
        # to hide() must be caught (the two-visible set is real).
        source = self.contents[PAGE_CXX].replace(
            "mxBgGradientLB->show();", "mxBgGradientLB->hide();", 1
        )
        self.assert_mutation_changed(PAGE_CXX, source)
        errors = self.failures(contents=self.with_content(PAGE_CXX, source))
        self.assertTrue(
            any("visibility_switch[GRADIENT]" in e and "mxBgGradientLB not shown" in e for e in errors),
            errors,
        )

    def test_none_hidden_flip_fails(self) -> None:
        # The first mxBgColorLB->hide() is the NONE branch; flipping it must fail.
        source = self.contents[PAGE_CXX].replace(
            "mxBgColorLB->hide();", "mxBgColorLB->show();", 1
        )
        self.assert_mutation_changed(PAGE_CXX, source)
        errors = self.failures(contents=self.with_content(PAGE_CXX, source))
        self.assertTrue(
            any("visibility_switch[NONE]" in e and "mxBgColorLB not hidden" in e for e in errors),
            errors,
        )

    def test_trigger_deck_layouting_dropped_fails(self) -> None:
        source = self.contents[PAGE_CXX].replace(
            "m_pPanel->TriggerDeckLayouting();", "// m_pPanel->TriggerDeckLayouting();", 1
        )
        self.assert_mutation_changed(PAGE_CXX, source)
        errors = self.failures(contents=self.with_content(PAGE_CXX, source))
        self.assertTrue(any("method side-effect missing" in e for e in errors), errors)

    # -- Navigator content/global toggle (per-branch isolation) -----------
    def test_navigator_global_branch_hide_flip_fails(self) -> None:
        # m_xContent3ToolBox->hide() is unique to the ToggleTree global-mode branch.
        source = self.contents[NAV_CXX].replace(
            "m_xContent3ToolBox->hide();", "m_xContent3ToolBox->show();", 1
        )
        self.assert_mutation_changed(NAV_CXX, source)
        errors = self.failures(contents=self.with_content(NAV_CXX, source))
        self.assertTrue(
            any("visibility_switch[global-mode]" in e and "m_xContent3ToolBox not hidden" in e for e in errors),
            errors,
        )

    def test_navigator_set_global_mode_side_effect_dropped_fails(self) -> None:
        source = self.contents[NAV_CXX].replace("SetGlobalMode(true)", "SetGlobalModeX(true)", 1)
        self.assert_mutation_changed(NAV_CXX, source)
        errors = self.failures(contents=self.with_content(NAV_CXX, source))
        self.assertTrue(
            any("visibility_switch[global-mode]" in e and "side-effect missing" in e for e in errors),
            errors,
        )

    def test_navigator_lok_carveout_marker_missing_fails(self) -> None:
        source = self.contents[NAV_CXX].replace(
            "if (comphelper::LibreOfficeKit::isActive())", "if (false)", 1
        )
        self.assert_mutation_changed(NAV_CXX, source)
        errors = self.failures(contents=self.with_content(NAV_CXX, source))
        self.assertTrue(any("lok_carveout marker missing" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_surface_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][0]["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)

    def test_expected_surfaces_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["expected_surfaces"] = 5
        errors = self.failures(registry=registry)
        self.assertTrue(any("expected_surfaces:count drift" in e for e in errors), errors)

    def test_missing_required_surface_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.surface(registry, "writer.sidebar.navigator")["surface_id"] = "renamed"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required writer.sidebar.navigator" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
