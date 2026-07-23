#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the data-grid header/selection contract (WIN-CON-003)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-data-grid-header-selection.py"
SPEC = importlib.util.spec_from_file_location("check_windows_data_grid_header_selection", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
WIDGETDRAW = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
HEADBAR = "vcl/source/treelist/headbar.cxx"
BRWBOX2 = "svtools/source/brwbox/brwbox2.cxx"
HDRCONT = "sc/source/ui/view/hdrcont.cxx"
GRIDWIN = "sc/source/ui/view/gridwin.cxx"


class DataGridHeaderSelectionTest(unittest.TestCase):
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

    def assert_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    def surface(self, registry: dict, surface_id: str) -> dict:
        return next(s for s in registry["surfaces"] if s["surface_id"] == surface_id)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- definition.xml listheader + style slots ---------------------------
    def test_listheader_button_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state rollover="true"><rect stroke="@outline-variant" fill="@primary-container" '
            'stroke-width="@stroke-thin" radius="@corner-small"/></state>',
            '<state rollover="true"><rect stroke="@outline-variant" fill="@surface" '
            'stroke-width="@stroke-thin" radius="@corner-small"/></state>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("listheader_part:button" in e and "token drift" in e for e in errors), errors
        )

    def test_listheader_state_removed_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state pressed="true"><rect stroke="@primary" fill="@primary-hover" '
            'stroke-width="@stroke-thin" radius="@corner-small"/></state>',
            "",
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    def test_style_slot_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<alternatingRowColor value="@surface-container-low"/>',
            '<alternatingRowColor value="@surface"/>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("style_slots:alternatingRowColor" in e and "token drift" in e for e in errors),
            errors,
        )

    # -- FileDefinitionWidgetDraw style pipe -------------------------------
    def test_style_pipe_unconditional_marker_removed_fails(self) -> None:
        source = self.contents[WIDGETDRAW].replace(
            "aStyleSet.SetHighlightColor(pDefinitionStyle->maHighlightColor);",
            "aStyleSet.SetHighlightColorX(pDefinitionStyle->maHighlightColor);",
            1,
        )
        self.assert_changed(WIDGETDRAW, source)
        errors = self.failures(contents=self.with_content(WIDGETDRAW, source))
        self.assertTrue(any("style_pipe:unconditional marker missing" in e for e in errors), errors)

    def test_style_pipe_guarded_marker_removed_fails(self) -> None:
        source = self.contents[WIDGETDRAW].replace(
            "aStyleSet.SetAlternatingRowColor(*pDefinitionStyle->moAlternatingRowColor);",
            "aStyleSet.SetAltRowColorX(*pDefinitionStyle->moAlternatingRowColor);",
            1,
        )
        self.assert_changed(WIDGETDRAW, source)
        errors = self.failures(contents=self.with_content(WIDGETDRAW, source))
        self.assertTrue(any("style_pipe:guarded marker missing" in e for e in errors), errors)

    # -- dbaccess positive pins --------------------------------------------
    def test_dbaccess_header_marker_removed_fails(self) -> None:
        source = self.contents[HEADBAR].replace(
            "DrawNativeControl(ControlType::ListHeader, ControlPart::Button,",
            "DrawNativeControlX(ControlType::ListHeader, ControlPart::Button,",
            1,
        )
        self.assert_changed(HEADBAR, source)
        errors = self.failures(contents=self.with_content(HEADBAR, source))
        self.assertTrue(
            any("surface[dbaccess-header]" in e and "positive marker missing" in e for e in errors),
            errors,
        )

    def test_dbaccess_selection_marker_removed_fails(self) -> None:
        source = self.contents[BRWBOX2].replace(
            "const Color &rHighlightFillColor = rSettings.GetHighlightColor();",
            "const Color &rHighlightFillColor = COL_WHITE;",
            1,
        )
        self.assert_changed(BRWBOX2, source)
        errors = self.failures(contents=self.with_content(BRWBOX2, source))
        self.assertTrue(
            any("surface[dbaccess-selection]" in e and "positive marker missing" in e for e in errors),
            errors,
        )

    def test_calc_header_idle_marker_removed_fails(self) -> None:
        source = self.contents[HDRCONT].replace(
            "Color aFaceColor(rStyleSettings.GetFaceColor());", "Color aFaceColor(COL_WHITE);", 1
        )
        self.assert_changed(HDRCONT, source)
        errors = self.failures(contents=self.with_content(HDRCONT, source))
        self.assertTrue(
            any("surface[calc-header-idle]" in e and "positive marker missing" in e for e in errors),
            errors,
        )

    # -- NEGATIVE markers + dual-update discipline -------------------------
    def test_selected_fill_rewired_fails_closed(self) -> None:
        # Rewiring the selected-header fill onto GetHighlightColor removes the CALCCELLFOCUS
        # negative marker: must fail closed until the status is flipped to 'compiled'.
        source = self.contents[HDRCONT].replace(
            "Color aColor = mod->GetColorConfig().GetColorValue(svtools::CALCCELLFOCUS).nColor;",
            "Color aColor = rStyleSettings.GetHighlightColor();",
            1,
        )
        self.assert_changed(HDRCONT, source)
        errors = self.failures(contents=self.with_content(HDRCONT, source))
        self.assertTrue(
            any("surface[calc-header-selected-fill]" in e and "not_material_marker gone" in e for e in errors),
            errors,
        )

    def test_active_cell_ring_accent_appears_fails_closed(self) -> None:
        # Injecting a GetAccentColor( call into gridwin.cxx trips the absent-marker guard,
        # proving the active-cell ring is being pulled onto the Material accent pipe.
        source = self.contents[GRIDWIN] + "\nColor probe() { return anon.GetAccentColor(); }\n"
        self.assert_changed(GRIDWIN, source)
        errors = self.failures(contents=self.with_content(GRIDWIN, source))
        self.assertTrue(
            any("surface[calc-active-cell-ring]" in e and "absent_marker now PRESENT" in e for e in errors),
            errors,
        )

    def test_status_promoted_without_positive_markers_fails(self) -> None:
        # Flipping a not_yet_material surface to 'compiled' without adding positive markers
        # (the other half of the dual update) must fail closed.
        registry = copy.deepcopy(self.registry)
        self.surface(registry, "calc-active-cell-ring")["status"] = "compiled"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("surface[calc-active-cell-ring]" in e and "compiled surface needs markers" in e for e in errors),
            errors,
        )

    def test_illegal_surface_status_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.surface(registry, "calc-active-cell-ring")["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("status:must be one of" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_registry_status_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["status"] = "compiled"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:status:must be 'partial'" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)

    def test_missing_required_surface_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"] = [
            s for s in registry["surfaces"] if s["surface_id"] != "dbaccess-selection"
        ]
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("missing required" in e and "dbaccess-selection" in e for e in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
