#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Calc sheet-tabs upstream-symbol pin (WIN-CA-004)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-calc-sheet-tabs-upstream-pin.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_calc_sheet_tabs_upstream_pin", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

TABBAR_HXX = "include/svtools/tabbar.hxx"
TABBAR_CXX = "svtools/source/control/tabbar.cxx"
SC_TABCONT = "sc/source/ui/inc/tabcont.hxx"


class CalcSheetTabsUpstreamPinTest(unittest.TestCase):
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

    # -- source-symbol drift fails closed ----------------------------------
    def test_base_paint_symbol_removed_fails(self) -> None:
        source = self.contents[TABBAR_CXX].replace(
            "void TabBar::Paint(vcl::RenderContext& rRenderContext, const tools::Rectangle& rect)",
            "void TabBar::PaintRenamed(vcl::RenderContext& rRenderContext, const tools::Rectangle& rect)",
            1,
        )
        self.assert_changed(TABBAR_CXX, source)
        errors = self.failures(contents=self.with_content(TABBAR_CXX, source))
        self.assertTrue(any("symbol absent" in e and "TabBar::Paint" in e for e in errors), errors)

    def test_tabdrawer_symbol_removed_fails(self) -> None:
        source = self.contents[TABBAR_CXX].replace("class TabDrawer", "class DrawerTab", 1)
        self.assert_changed(TABBAR_CXX, source)
        errors = self.failures(contents=self.with_content(TABBAR_CXX, source))
        self.assertTrue(any("symbol absent" in e and "TabDrawer" in e for e in errors), errors)

    def test_header_symbol_removed_fails(self) -> None:
        source = self.contents[TABBAR_HXX].replace("GetPageArea()", "GetPageAreaX()", 1)
        self.assert_changed(TABBAR_HXX, source)
        errors = self.failures(contents=self.with_content(TABBAR_HXX, source))
        self.assertTrue(any("symbol absent" in e and "GetPageArea" in e for e in errors), errors)

    def test_commented_out_symbol_fails(self) -> None:
        # A commented-out definition must not satisfy the pin (comments are stripped).
        source = self.contents[TABBAR_CXX].replace(
            "void TabBar::AddTabClick()", "// void TabBar::AddTabClick()", 1
        )
        self.assert_changed(TABBAR_CXX, source)
        errors = self.failures(contents=self.with_content(TABBAR_CXX, source))
        self.assertTrue(any("symbol absent" in e and "AddTabClick" in e for e in errors), errors)

    def test_upstream_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(TABBAR_CXX))
        self.assertTrue(any("missing" in e for e in errors), errors)

    # -- subclass shared-ownership fact ------------------------------------
    def test_subclass_base_removed_fails(self) -> None:
        source = self.contents[SC_TABCONT].replace(": public TabBar,", ": public RenamedBase,", 1)
        self.assert_changed(SC_TABCONT, source)
        errors = self.failures(contents=self.with_content(SC_TABCONT, source))
        self.assertTrue(
            any("subclasses" in e and "ScTabControl" in e for e in errors), errors
        )

    # -- registry integrity ------------------------------------------------
    def test_advances_m_gate_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["advances_m_gate"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("advances_m_gate:must be false" in e for e in errors), errors)

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

    def test_read_only_flipped_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["upstream_files"][0]["read_only"] = False
        errors = self.failures(registry=registry)
        self.assertTrue(any("read_only:must be true" in e for e in errors), errors)

    def test_missing_required_upstream_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["upstream_files"] = [
            e for e in registry["upstream_files"] if e.get("file") != TABBAR_CXX
        ]
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required" in e and TABBAR_CXX in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
