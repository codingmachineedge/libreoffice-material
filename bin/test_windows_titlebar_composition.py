#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material title-bar composition contract (WIN-NAV-007).

Each mutation weakens one guarantee -- a drifted title metric, a remapped title-height
setting, a drifted frame-activation style slot, a dropped palette role, a missing generic
StyleSettings owner marker, a promoted (no-longer-'not-wired') consumption status, or an
absence marker that has appeared in real brdwin.cxx / salframe.cxx code -- and asserts the
checker fails closed on it. A green baseline proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-titlebar-composition.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_titlebar_composition", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
OWNER = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
BRDWIN = "vcl/source/window/brdwin.cxx"
SALFRAME = "vcl/win/window/salframe.cxx"


class TitleBarCompositionContractTest(unittest.TestCase):
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

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- metrics -----------------------------------------------------------
    def test_window_title_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<metric name="height-window-title" value="18"/>',
            '<metric name="height-window-title" value="24"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("metrics:height-window-title" in e and "metric drift" in e for e in errors),
            errors,
        )

    def test_floating_title_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<metric name="height-floating-title" value="14"/>',
            '<metric name="height-floating-title" value="18"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("metrics:height-floating-title" in e and "metric drift" in e for e in errors),
            errors,
        )

    # -- settings ----------------------------------------------------------
    def test_title_height_setting_remapped_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<titleHeight value="@height-window-title"/>',
            '<titleHeight value="@height-floating-title"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("settings:<titleHeight>" in e for e in errors), errors)

    # -- style slots -------------------------------------------------------
    def test_active_slot_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<activeColor value="@primary"/>',
            '<activeColor value="@secondary"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("style_slots:<style><activeColor>" in e for e in errors), errors)

    def test_deactive_slot_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<deactiveColor value="@disabled-container"/>',
            '<deactiveColor value="@surface"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("style_slots:<style><deactiveColor>" in e for e in errors), errors)

    # -- palette -----------------------------------------------------------
    def test_palette_role_removed_from_dark_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="primary" value="#D0BCFF"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("palette:@primary missing from the dark" in e for e in errors), errors)

    # -- owner (generic StyleSettings push) --------------------------------
    def test_owner_marker_missing_fails(self) -> None:
        source = self.contents[OWNER].replace(
            "SetActiveColor(pDefinitionStyle->maActiveColor)", "SetActiveColor(COL_BLACK)", 1
        )
        errors = self.failures(contents=self.with_content(OWNER, source))
        self.assertTrue(
            any("owner:marker missing in code (SetActiveColor(pDefinitionStyle->maActiveColor))" in e
                for e in errors),
            errors,
        )

    def test_owner_comment_only_marker_fails(self) -> None:
        # Comment out the generic title-height push: comment-stripped code no longer
        # carries the marker.
        source = self.contents[OWNER].replace(
            "aStyleSet.SetTitleHeight(", "// aStyleSet.SetTitleHeight(", 1
        )
        errors = self.failures(contents=self.with_content(OWNER, source))
        self.assertTrue(
            any("owner:marker missing in code (SetTitleHeight()" in e for e in errors), errors
        )

    # -- consumption (the honest not-wired half) ---------------------------
    def test_consumption_status_promoted_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["consumption"]["status"] = "wired"
        errors = self.failures(registry=registry)
        self.assertTrue(any("consumption:status" in e for e in errors), errors)

    def test_brdwin_absence_marker_appearing_fails(self) -> None:
        # A future commit that reads GetActiveColor() in brdwin.cxx (genuinely wiring the
        # active/inactive title-bar path) must fail this contract closed.
        source = self.contents[BRDWIN] + (
            "\nColor lcl_probe(const StyleSettings& r) { return r.GetActiveColor(); }\n"
        )
        errors = self.failures(contents=self.with_content(BRDWIN, source))
        self.assertTrue(
            any("consumption:absent-guard" in e and "GetActiveColor(" in e for e in errors),
            errors,
        )

    def test_salframe_dwm_caption_colour_appearing_fails(self) -> None:
        source = self.contents[SALFRAME] + (
            "\nvoid lcl_probe(HWND h, COLORREF c)"
            " { DwmSetWindowAttribute(h, DWMWA_CAPTION_COLOR, &c, sizeof(c)); }\n"
        )
        errors = self.failures(contents=self.with_content(SALFRAME, source))
        self.assertTrue(
            any("consumption:absent-guard" in e and "DWMWA_CAPTION_COLOR" in e for e in errors),
            errors,
        )

    def test_brdwin_absence_marker_in_comment_still_passes(self) -> None:
        # A comment mentioning GetActiveColor must NOT trip the absence guard (only real
        # code counts), so the not-wired fact survives incidental documentation.
        source = self.contents[BRDWIN] + "\n// TODO: someday consume GetActiveColor() here\n"
        errors = self.failures(contents=self.with_content(BRDWIN, source))
        self.assertFalse(any("consumption:absent-guard" in e for e in errors), errors)

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

    def test_theme_flag_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["theme_flag"] = "SOME_OTHER_FLAG"
        errors = self.failures(registry=registry)
        self.assertIn("registry:theme_flag:must be VCL_FILE_WIDGET_THEME", errors)


if __name__ == "__main__":
    unittest.main()
