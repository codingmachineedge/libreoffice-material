#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Impress/Draw surface contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-impress-draw-surface-contract.py"
SPEC = importlib.util.spec_from_file_location("check_impress_draw_surface_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
DRVIEWSA = "sd/source/ui/view/drviewsa.cxx"
SCALECTRL = "sd/source/ui/app/scalectrl.cxx"
STRINGS = "sd/inc/strings.hrc"
LINE_PANEL = "svx/source/sidebar/line/LinePropertyPanelBase.cxx"
AREA_PANEL = "svx/source/sidebar/area/AreaPropertyPanelBase.cxx"
POSSIZE_PANEL = "svx/source/sidebar/possize/PosSizePropertyPanel.cxx"
SHADOW_PANEL = "svx/source/sidebar/shadow/ShadowPropertyPanel.cxx"
GRAPHIC_BAR = "sd/source/ui/view/GraphicObjectBar.cxx"
TEXT_BAR_XML = "sd/uiconfig/sdraw/toolbar/textobjectbar.xml"


class ImpressDrawSurfaceContractTest(unittest.TestCase):
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

    # -- definition-part token drift --------------------------------------
    def test_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="DrawBackgroundVert"><state><rect stroke="@surface-container" '
            'fill="@surface-container"',
            '<part value="DrawBackgroundVert"><state><rect stroke="@surface-container" '
            'fill="@surface"',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("token drift" in e for e in errors), errors)

    def test_missing_part_fails(self) -> None:
        definition = self.contents[DEFINITION].replace('value="DrawBackgroundVert"', 'value="Renamed"', 1)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("missing in definition.xml" in e for e in errors), errors)

    def test_slider_thumb_size_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="Button" width="@size-compact-control" height="@size-compact-control">',
            '<part value="Button" width="@size-compact-control" height="@size-standard-control">',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("attribute height" in e for e in errors), errors)

    def test_missing_button_state_fails(self) -> None:
        # Drop the checked (button-value) toolbar Button state.
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" button-value="true"><rect stroke="@primary" '
            'fill="@primary-container" stroke-width="@stroke-thin" radius="@corner-toolbar"/></state>',
            "",
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    # -- status model ------------------------------------------------------
    def test_status_marker_missing_fails(self) -> None:
        source = self.contents[DRVIEWSA].replace("GetMarkedObjectList().GetMarkCount()", "0", 1)
        errors = self.failures(contents=self.with_content(DRVIEWSA, source))
        self.assertTrue(any(":status-model:marker missing" in e for e in errors), errors)

    def test_status_resource_missing_fails(self) -> None:
        strings = self.contents[STRINGS].replace("STR_SD_DRAW_OBJECTS_SELECTED", "STR_RENAMED", 2)
        errors = self.failures(contents=self.with_content(STRINGS, strings))
        self.assertTrue(any("not defined in" in e for e in errors), errors)

    def test_status_resource_wrong_copy_fails(self) -> None:
        strings = self.contents[STRINGS].replace(" · %1 objects selected", " · %1 items", 1)
        errors = self.failures(contents=self.with_content(STRINGS, strings))
        self.assertTrue(any("lacks 'objects selected'" in e for e in errors), errors)

    # -- token consumption / comment-only wiring --------------------------
    def test_comment_only_wiring_fails(self) -> None:
        source = self.contents[SCALECTRL].replace(
            "        GetStatusBar().SetControlForeground(*oColor);",
            "        // GetStatusBar().SetControlForeground(*oColor);",
            1,
        )
        errors = self.failures(contents=self.with_content(SCALECTRL, source))
        self.assertTrue(any(":token-consumption:marker missing" in e for e in errors), errors)

    def test_token_include_required(self) -> None:
        source = self.contents[SCALECTRL].replace("#include <vcl/MaterialTokens.hxx>", "", 1)
        errors = self.failures(contents=self.with_content(SCALECTRL, source))
        self.assertTrue(any(":token-consumption:missing #include" in e for e in errors), errors)

    # -- disabled policy ---------------------------------------------------
    def test_policy_missing_visible_fails(self) -> None:
        source = self.contents[LINE_PANEL].replace("    mxTBColor->set_visible(true);\n", "", 1)
        errors = self.failures(contents=self.with_content(LINE_PANEL, source))
        self.assertTrue(
            any("not kept visible (no layout jump)" in e for e in errors), errors
        )

    def test_policy_missing_disable_fails(self) -> None:
        # Target the disable line inside the policy method (the visible+sensitive
        # pairing is unique to it), not the unrelated existing update paths.
        source = self.contents[AREA_PANEL].replace(
            "    mxSldTransparent->set_visible(true);\n    mxSldTransparent->set_sensitive(false);\n",
            "    mxSldTransparent->set_visible(true);\n",
            1,
        )
        errors = self.failures(contents=self.with_content(AREA_PANEL, source))
        self.assertTrue(any("mxSldTransparent not disabled" in e for e in errors), errors)

    def test_policy_method_missing_fails(self) -> None:
        source = self.contents[LINE_PANEL].replace(
            "void LinePropertyPanelBase::ApplyNoSelectionDisabledPolicy()",
            "void LinePropertyPanelBase::SomethingElse()",
            1,
        )
        errors = self.failures(contents=self.with_content(LINE_PANEL, source))
        self.assertTrue(any(":disabled-policy:method" in e and "not found" in e for e in errors), errors)

    # -- owner markers -----------------------------------------------------
    def test_owner_marker_missing_fails(self) -> None:
        toolbar = "sd/uiconfig/sdraw/toolbar/toolbar.xml"
        source = self.contents[toolbar].replace(".uno:SelectObject", ".uno:Nope", 1)
        errors = self.failures(contents=self.with_content(toolbar, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    # -- object-property panels (possize / shadow) -------------------------
    def test_checkbox_token_drift_fails(self) -> None:
        # The checkbox Entire unchecked state is declared only by the new
        # object-property-panel surfaces; radius="@corner-checkbox" is unique to it.
        definition = self.contents[DEFINITION].replace(
            'stroke="@on-surface-variant" fill="@surface" stroke-width="@stroke-standard" '
            'radius="@corner-checkbox"',
            'stroke="@on-surface-variant" fill="@surface-container" stroke-width="@stroke-standard" '
            'radius="@corner-checkbox"',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("token drift" in e for e in errors), errors)

    def test_possize_policy_missing_visible_fails(self) -> None:
        source = self.contents[POSSIZE_PANEL].replace(
            "    mxCbxScale->set_visible(true);\n", "", 1
        )
        errors = self.failures(contents=self.with_content(POSSIZE_PANEL, source))
        self.assertTrue(
            any("mxCbxScale not kept visible (no layout jump)" in e for e in errors), errors
        )

    def test_possize_policy_missing_disable_fails(self) -> None:
        # Target the disable line inside the policy method (the visible+sensitive
        # pairing is unique to it), not the unrelated existing sensitivity paths.
        source = self.contents[POSSIZE_PANEL].replace(
            "    mxMtrAngle->set_visible(true);\n    mxMtrAngle->set_sensitive(false);\n",
            "    mxMtrAngle->set_visible(true);\n",
            1,
        )
        errors = self.failures(contents=self.with_content(POSSIZE_PANEL, source))
        self.assertTrue(any("mxMtrAngle not disabled" in e for e in errors), errors)

    def test_possize_policy_method_missing_fails(self) -> None:
        source = self.contents[POSSIZE_PANEL].replace(
            "void PosSizePropertyPanel::ApplyNoSelectionDisabledPolicy()",
            "void PosSizePropertyPanel::SomethingElse()",
            1,
        )
        errors = self.failures(contents=self.with_content(POSSIZE_PANEL, source))
        self.assertTrue(any(":disabled-policy:method" in e and "not found" in e for e in errors), errors)

    def test_shadow_policy_missing_disable_fails(self) -> None:
        source = self.contents[SHADOW_PANEL].replace(
            "    mxShowShadow->set_visible(true);\n    mxShowShadow->set_sensitive(false);\n",
            "    mxShowShadow->set_visible(true);\n",
            1,
        )
        errors = self.failures(contents=self.with_content(SHADOW_PANEL, source))
        self.assertTrue(any("mxShowShadow not disabled" in e for e in errors), errors)

    def test_shadow_owner_marker_missing_fails(self) -> None:
        source = self.contents[SHADOW_PANEL].replace(
            'weld_scale(u"transparency_slider"', 'weld_scale(u"nope"', 1
        )
        errors = self.failures(contents=self.with_content(SHADOW_PANEL, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    # -- object bars -------------------------------------------------------
    def test_object_bar_marker_missing_fails(self) -> None:
        source = self.contents[TEXT_BAR_XML].replace(".uno:Bold", ".uno:Nope", 1)
        errors = self.failures(contents=self.with_content(TEXT_BAR_XML, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    def test_object_bar_shell_marker_missing_fails(self) -> None:
        source = self.contents[GRAPHIC_BAR].replace(
            "SFX_IMPL_INTERFACE(GraphicObjectBar", "SFX_IMPL_INTERFACE(Renamed", 1
        )
        errors = self.failures(contents=self.with_content(GRAPHIC_BAR, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    def test_missing_required_object_bars_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"] = [
            s for s in registry["surfaces"] if s["surface_id"] != "impress.object-bars"
        ]
        registry["expected_surfaces"] = len(registry["surfaces"])
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required impress.object-bars" in e for e in errors), errors)

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

    def test_missing_required_surface_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"] = [
            s for s in registry["surfaces"] if s["surface_id"] != "draw.status-bar"
        ]
        registry["expected_surfaces"] = len(registry["surfaces"])
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required draw.status-bar" in e for e in errors), errors)

    def test_owner_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"][2]["owner_sources"].append("sd/source/does/not/exist.cxx")
        errors = self.failures(registry=registry)
        self.assertTrue(any(":owner_source:missing" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
