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
TEXT_OBJECT_BAR = "sd/source/ui/view/drtxtob.cxx"
GRAPHIC_BAR_XML = "sd/uiconfig/sdraw/toolbar/graphicobjectbar.xml"
TEXT_BAR_XML = "sd/uiconfig/sdraw/toolbar/textobjectbar.xml"
IMPRESS_MODULE = "sd/source/ui/framework/module/ImpressModule.cxx"
LAYOUTPANEL_UI = "sd/uiconfig/simpress/ui/layoutpanel.ui"
SDR_GRID = "svx/source/sdr/contact/viewobjectcontactofsdrpage.cxx"
SDR_PAINT = "svx/source/svdraw/sdrpaintwindow.cxx"


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

    def test_possize_owner_marker_missing_fails(self) -> None:
        source = self.contents[POSSIZE_PANEL].replace(
            'weld_check_button(u"ratio"', 'weld_check_button(u"nope"', 1
        )
        errors = self.failures(contents=self.with_content(POSSIZE_PANEL, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

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

    def test_graphic_object_bar_xml_marker_missing_fails(self) -> None:
        source = self.contents[GRAPHIC_BAR_XML].replace(".uno:TransformDialog", ".uno:Nope", 1)
        errors = self.failures(contents=self.with_content(GRAPHIC_BAR_XML, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    def test_text_object_bar_shell_marker_missing_fails(self) -> None:
        source = self.contents[TEXT_OBJECT_BAR].replace(
            "SFX_IMPL_INTERFACE(TextObjectBar", "SFX_IMPL_INTERFACE(Renamed", 1
        )
        errors = self.failures(contents=self.with_content(TEXT_OBJECT_BAR, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    def test_missing_required_object_bars_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"] = [
            s for s in registry["surfaces"] if s["surface_id"] != "impress.object-bars"
        ]
        registry["expected_surfaces"] = len(registry["surfaces"])
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required impress.object-bars" in e for e in errors), errors)

    # -- impress.pane-composition (owner markers, empty definition_parts) ---
    def test_pane_composition_owner_marker_missing_fails(self) -> None:
        source = self.contents[IMPRESS_MODULE].replace(
            "new SlideSorterModule(", "new Nope(", 1
        )
        errors = self.failures(contents=self.with_content(IMPRESS_MODULE, source))
        self.assertTrue(any(":owner-marker:" in e for e in errors), errors)

    def test_pane_composition_layoutpanel_ui_marker_missing_fails(self) -> None:
        # layoutpanel.ui is not C++, so the marker match is a plain substring.
        source = self.contents[LAYOUTPANEL_UI].replace("GtkIconView", "GtkFlowBox", 1)
        errors = self.failures(contents=self.with_content(LAYOUTPANEL_UI, source))
        self.assertTrue(any(":owner-marker:GtkIconView missing" in e for e in errors), errors)

    # -- impress.status-bar (status model, distinct from draw.status-bar) ---
    def test_impress_status_marker_missing_fails(self) -> None:
        # GetLayoutName() belongs to the Impress status model; the Draw branch
        # markers are unrelated, so this only trips impress.status-bar.
        source = self.contents[DRVIEWSA].replace(
            "mpActualPage->GetLayoutName()", "mpActualPage->Renamed()", 1
        )
        errors = self.failures(contents=self.with_content(DRVIEWSA, source))
        self.assertTrue(
            any("status-model:marker missing in code (GetLayoutName())" in e for e in errors),
            errors,
        )

    def test_impress_status_resource_missing_fails(self) -> None:
        strings = self.contents[STRINGS].replace(
            '"STR_SD_PAGE_COUNT", "Slide %1 of %2"', '"STR_RENAMED", "Slide %1 of %2"', 1
        )
        errors = self.failures(contents=self.with_content(STRINGS, strings))
        self.assertTrue(any("STR_SD_PAGE_COUNT not defined in" in e for e in errors), errors)

    def test_impress_status_wrong_copy_fails(self) -> None:
        strings = self.contents[STRINGS].replace(
            'NC_("STR_SD_PAGE_COUNT", "Slide %1 of %2")',
            'NC_("STR_SD_PAGE_COUNT", "Page %1 of %2")',
            1,
        )
        errors = self.failures(contents=self.with_content(STRINGS, strings))
        self.assertTrue(any("lacks 'Slide %1 of %2'" in e for e in errors), errors)

    # -- draw.canvas-grid (guarded @outline-variant grid dot color) --------
    def test_canvas_grid_missing_include_fails(self) -> None:
        source = self.contents[SDR_GRID].replace("#include <vcl/MaterialTokens.hxx>\n", "", 1)
        errors = self.failures(contents=self.with_content(SDR_GRID, source))
        self.assertTrue(any(":token-consumption:missing #include" in e for e in errors), errors)

    def test_canvas_grid_marker_missing_fails(self) -> None:
        source = self.contents[SDR_GRID].replace(
            'findColor("outline-variant")', 'findColor("nope")', 1
        )
        errors = self.failures(contents=self.with_content(SDR_GRID, source))
        self.assertTrue(
            any('token-consumption:marker missing in code (findColor("outline-variant"))' in e
                for e in errors),
            errors,
        )

    def test_canvas_grid_comment_only_wiring_fails(self) -> None:
        source = self.contents[SDR_GRID].replace(
            'return aTokens.findColor("outline-variant");',
            '// return aTokens.findColor("outline-variant");',
            1,
        )
        errors = self.failures(contents=self.with_content(SDR_GRID, source))
        self.assertTrue(any(":token-consumption:marker missing" in e for e in errors), errors)

    def test_canvas_grid_ordering_not_contiguous_fails(self) -> None:
        # Defeat the high-contrast short-circuit (Material would then also apply
        # under resolved high contrast). GetHighContrastMode() stays present, so
        # only the ordering guard-structure check fires.
        source = self.contents[SDR_GRID].replace(
            "if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())\n"
            "        return std::nullopt;",
            "if (false && Application::GetSettings().GetStyleSettings().GetHighContrastMode())\n"
            "        return std::nullopt;",
            1,
        )
        errors = self.failures(contents=self.with_content(SDR_GRID, source))
        self.assertTrue(
            any(":token-ordering:guard structure not contiguous" in e for e in errors), errors
        )

    # -- draw.selection-overlay-guide-color (guarded @primary stripe color) -
    def test_overlay_guide_missing_include_fails(self) -> None:
        source = self.contents[SDR_PAINT].replace("#include <vcl/MaterialTokens.hxx>\n", "", 1)
        errors = self.failures(contents=self.with_content(SDR_PAINT, source))
        self.assertTrue(any(":token-consumption:missing #include" in e for e in errors), errors)

    def test_overlay_guide_marker_missing_fails(self) -> None:
        source = self.contents[SDR_PAINT].replace('findColor("primary")', 'findColor("nope")', 1)
        errors = self.failures(contents=self.with_content(SDR_PAINT, source))
        self.assertTrue(
            any('token-consumption:marker missing in code (findColor("primary"))' in e
                for e in errors),
            errors,
        )

    def test_overlay_guide_stripe_marker_missing_fails(self) -> None:
        source = self.contents[SDR_PAINT].replace("setStripeColorA(", "setStripeRenamedA(", 1)
        errors = self.failures(contents=self.with_content(SDR_PAINT, source))
        self.assertTrue(
            any("token-consumption:marker missing in code (setStripeColorA()" in e for e in errors),
            errors,
        )

    def test_overlay_guide_ordering_not_contiguous_fails(self) -> None:
        # Turn the guarded else-if into a bare if: the Material tint would then run
        # even when high contrast already set the stripe colors, so it no longer
        # loses to high contrast. GetHighContrastMode() stays present.
        source = self.contents[SDR_PAINT].replace(
            "else if (const std::optional<Color> oColor = lcl_getMaterialOverlayGuideColor())",
            "if (const std::optional<Color> oColor = lcl_getMaterialOverlayGuideColor())",
            1,
        )
        errors = self.failures(contents=self.with_content(SDR_PAINT, source))
        self.assertTrue(
            any(":token-ordering:guard structure not contiguous" in e for e in errors), errors
        )

    def test_overlay_guide_ordering_missing_high_contrast_fails(self) -> None:
        source = self.contents[SDR_PAINT].replace(
            "if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())",
            "if (false)",
            1,
        )
        errors = self.failures(contents=self.with_content(SDR_PAINT, source))
        self.assertTrue(
            any(":token-ordering:high-contrast marker missing" in e for e in errors), errors
        )

    def test_missing_required_canvas_grid_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["surfaces"] = [
            s for s in registry["surfaces"] if s["surface_id"] != "draw.canvas-grid"
        ]
        registry["expected_surfaces"] = len(registry["surfaces"])
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required draw.canvas-grid" in e for e in errors), errors)

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
