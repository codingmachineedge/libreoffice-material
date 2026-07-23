#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Document Properties composition contract.

Every mutation breaks exactly one pinned guarantee against an in-memory copy of
the registry or the source tree and asserts the checker fails closed. A positive
control proves the pristine tree passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-document-properties-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_document_properties_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
DIALOG_UI = "sfx2/uiconfig/ui/documentpropertiesdialog.ui"
DINFDLG = "sfx2/source/dialog/dinfdlg.cxx"
TABS_HRC = "include/vcl/tabs.hrc"
SECURITY_UI = "sfx2/uiconfig/ui/securityinfopage.ui"


class DocumentPropertiesContractTest(unittest.TestCase):
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

    # -- definition.xml native part cross-checks ---------------------------
    def test_selected_tabitem_recolor_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" selected="true"><rect stroke="@primary-container" '
            'fill="@primary-container" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            '<state enabled="true" selected="true"><rect stroke="@primary-container" '
            'fill="@surface" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabitem/Entire" in e and "token drift" in e for e in errors), errors)

    def test_dropped_tabitem_state_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="false" selected="true"><rect stroke="@outline" '
            'fill="@disabled-container" stroke-width="@stroke-thin" radius="@corner-pill"/></state>',
            "",
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabitem/Entire" in e and "no <state> matching" in e for e in errors), errors)

    def test_tabitem_radius_drift_fails(self) -> None:
        # @corner-pill -> @corner-container on the inactive tabitem state.
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            '<state enabled="true"><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none" radius="@corner-container"/></state>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabitem/Entire" in e and "radius" in e for e in errors), errors)

    def test_tabpane_fill_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<tabpane><part value="Entire"><state><rect stroke="@outline-variant" '
            'fill="@surface" stroke-width="@stroke-thin" radius="@corner-container"/></state></part></tabpane>',
            '<tabpane><part value="Entire"><state><rect stroke="@outline-variant" '
            'fill="@surface-container" stroke-width="@stroke-thin" radius="@corner-container"/></state></part></tabpane>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabpane/Entire" in e and "token drift" in e for e in errors), errors)

    def test_missing_tabheader_fails(self) -> None:
        definition = self.contents[DEFINITION].replace("<tabheader>", "<tabheaderX>", 1).replace(
            "</tabheader>", "</tabheaderX>", 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabheader/Entire" in e and "missing" in e for e in errors), errors)

    def test_pushbutton_footer_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true">\n'
            '                <rect stroke="@primary-container" fill="@primary-container" '
            'stroke-width="@stroke-thin" radius="@corner-pill"/>\n'
            '            </state>',
            '<state enabled="true">\n'
            '                <rect stroke="@primary-container" fill="@surface" '
            'stroke-width="@stroke-thin" radius="@corner-pill"/>\n'
            '            </state>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("pushbutton/Entire" in e and "token drift" in e for e in errors), errors)

    def test_frame_border_missing_fails(self) -> None:
        definition = self.contents[DEFINITION].replace('<frame><part value="Border">', '<frame><part value="BorderX">', 1)
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("frame/Border" in e and "part missing" in e for e in errors), errors)

    def test_part_attr_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="Entire" margin-width="@space-tab-inline" height="@height-tab">',
            '<part value="Entire" margin-width="@space-tab-inline" height="@height-window-title">',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tabitem/Entire" in e and "part attribute drift" in e for e in errors), errors)

    # -- tab style / settings ---------------------------------------------
    def test_active_tab_color_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<activeTabColor value="@primary-container"/>',
            '<activeTabColor value="@surface-container"/>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tab_style:activeTabColor" in e for e in errors), errors)

    def test_tab_highlight_text_color_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<tabHighlightTextColor value="@on-primary-container"/>',
            '<tabHighlightTextColor value="@on-surface"/>',
            1,
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tab_style:tabHighlightTextColor" in e for e in errors), errors)

    def test_centered_tabs_setting_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<centeredTabs value="true"/>', '<centeredTabs value="false"/>', 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("tab_settings:centeredTabs" in e for e in errors), errors)

    # -- metrics / palette -------------------------------------------------
    def test_height_tab_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<metric name="height-tab" value="40"/>', '<metric name="height-tab" value="36"/>', 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("metrics:height-tab" in e and "metric drift" in e for e in errors), errors)

    def test_corner_pill_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<radius name="corner-pill" value="20"/>', '<radius name="corner-pill" value="16"/>', 1
        )
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("metrics:corner-pill" in e and "metric drift" in e for e in errors), errors)

    def test_palette_role_missing_in_dark_only_fails(self) -> None:
        # Remove the on-primary-container role from the dark palette only.
        definition = self.contents[DEFINITION]
        dark_index = definition.find('<palette scheme="dark">')
        self.assertNotEqual(dark_index, -1)
        head, tail = definition[:dark_index], definition[dark_index:]
        tail = tail.replace('<color name="on-primary-container"', '<color name="on-primary-containerX"', 1)
        definition = head + tail
        self.assert_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("palette:@on-primary-container missing from the dark palette" in e for e in errors),
            errors,
        )

    def test_palette_role_added_to_registry_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("palette:@no-such-role" in e for e in errors), errors)

    # -- dialog composition ------------------------------------------------
    def test_notebook_tab_pos_rail_to_top_fails(self) -> None:
        ui = self.contents[DIALOG_UI].replace(
            '<property name="tab-pos">left</property>',
            '<property name="tab-pos">top</property>',
            1,
        )
        self.assert_changed(DIALOG_UI, ui)
        errors = self.failures(contents=self.with_content(DIALOG_UI, ui))
        self.assertTrue(any("notebook tab-pos" in e for e in errors), errors)

    def test_notebook_renamed_fails(self) -> None:
        ui = self.contents[DIALOG_UI].replace(
            '<object class="GtkNotebook" id="tabcontrol">',
            '<object class="GtkNotebook" id="tabcontrolX">',
            1,
        )
        self.assert_changed(DIALOG_UI, ui)
        errors = self.failures(contents=self.with_content(DIALOG_UI, ui))
        self.assertTrue(any("notebook" in e and "GtkNotebook missing" in e for e in errors), errors)

    def test_modal_lost_fails(self) -> None:
        ui = self.contents[DIALOG_UI].replace(
            '<property name="modal">True</property>',
            '<property name="modal">False</property>',
            1,
        )
        self.assert_changed(DIALOG_UI, ui)
        errors = self.failures(contents=self.with_content(DIALOG_UI, ui))
        self.assertTrue(any("must declare modal=True" in e for e in errors), errors)

    def test_footer_reorder_fails(self) -> None:
        # Swap ok and cancel action-widget order.
        ui = self.contents[DIALOG_UI].replace(
            '      <action-widget response="-5">ok</action-widget>\n'
            '      <action-widget response="-6">cancel</action-widget>\n',
            '      <action-widget response="-6">cancel</action-widget>\n'
            '      <action-widget response="-5">ok</action-widget>\n',
            1,
        )
        self.assert_changed(DIALOG_UI, ui)
        errors = self.failures(contents=self.with_content(DIALOG_UI, ui))
        self.assertTrue(any("footer[" in e and "drift" in e for e in errors), errors)

    def test_footer_help_secondary_lost_fails(self) -> None:
        # Drop the secondary packing property on the help button.
        ui = self.contents[DIALOG_UI].replace(
            '                <property name="position">3</property>\n'
            '                <property name="secondary">True</property>\n',
            '                <property name="position">3</property>\n',
            1,
        )
        self.assert_changed(DIALOG_UI, ui)
        errors = self.failures(contents=self.with_content(DIALOG_UI, ui))
        self.assertTrue(any("secondary flag" in e for e in errors), errors)

    def test_dialog_ui_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DIALOG_UI))
        self.assertTrue(any("dialog_composition:ui:file missing" in e for e in errors), errors)

    # -- programmatic page set --------------------------------------------
    def test_addtabpage_removed_fails(self) -> None:
        source = self.contents[DINFDLG].replace(
            'AddTabPage(u"description"_ustr, TabResId(RID_TAB_DESCRIPTION.aLabel), SfxDocumentDescPage::Create,',
            'AddTabPage(u"descriptionX"_ustr, TabResId(RID_TAB_DESCRIPTION.aLabel), SfxDocumentDescPage::Create,',
            1,
        )
        self.assert_changed(DINFDLG, source)
        errors = self.failures(contents=self.with_content(DINFDLG, source))
        self.assertTrue(any("tab_pages[description]:add_marker" in e for e in errors), errors)

    def test_rid_l_icon_downgraded_to_rid_m_fails(self) -> None:
        source = self.contents[DINFDLG].replace(
            "RID_L + RID_TAB_ORGANIZER.sIconName", "RID_M + RID_TAB_ORGANIZER.sIconName", 1
        )
        self.assert_changed(DINFDLG, source)
        errors = self.failures(contents=self.with_content(DINFDLG, source))
        self.assertTrue(any("tab_pages[general]:icon_marker" in e for e in errors), errors)

    def test_rid_l_rail_prefix_changed_fails(self) -> None:
        source = self.contents[TABS_HRC].replace(
            'RID_L = u"cmd/32/"_ustr', 'RID_L = u"cmd/16/"_ustr', 1
        )
        self.assert_changed(TABS_HRC, source)
        errors = self.failures(contents=self.with_content(TABS_HRC, source))
        self.assertTrue(any("icon_rail_source" in e for e in errors), errors)

    def test_out_of_file_security_bind_renamed_fails(self) -> None:
        source = self.contents[SECURITY_UI]
        errors = self.failures(contents=self.without_content(SECURITY_UI))
        self.assertTrue(any("tab_pages[security]:page_ui:file missing" in e for e in errors), errors)

    def test_page_root_id_renamed_fails(self) -> None:
        ui = self.contents["sfx2/uiconfig/ui/documentinfopage.ui"].replace(
            'id="DocumentInfoPage"', 'id="DocumentInfoPageX"', 1
        )
        self.assert_changed("sfx2/uiconfig/ui/documentinfopage.ui", ui)
        errors = self.failures(contents=self.with_content("sfx2/uiconfig/ui/documentinfopage.ui", ui))
        self.assertTrue(any("tab_pages[general]:page root object" in e for e in errors), errors)

    def test_controller_bind_missing_fails(self) -> None:
        source = self.contents[DINFDLG].replace(
            'u"sfx/ui/documentpropertiesdialog.ui"_ustr', 'u"sfx/ui/documentpropertiesdialogX.ui"_ustr', 1
        )
        self.assert_changed(DINFDLG, source)
        errors = self.failures(contents=self.with_content(DINFDLG, source))
        self.assertTrue(any("tab_page_source:controller_bind" in e for e in errors), errors)

    # -- carve-out discipline ---------------------------------------------
    def test_wrong_type_query_carveout_promoted_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["wrong_type_query"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("carveouts:wrong_type_query:status must stay 'specified'" in e for e in errors),
            errors,
        )

    def test_wrong_type_query_marker_removed_fails(self) -> None:
        source = self.contents[DINFDLG].replace("STR_SFX_QUERY_WRONG_TYPE", "STR_SFX_QUERY_OK", 1)
        self.assert_changed(DINFDLG, source)
        errors = self.failures(contents=self.with_content(DINFDLG, source))
        self.assertTrue(any("carveouts:wrong_type_query" in e and "code marker" in e for e in errors), errors)

    def test_rail_geometry_carveout_promoted_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["rail_pixel_geometry"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("carveouts:rail_pixel_geometry:status must stay 'specified'" in e for e in errors),
            errors,
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


if __name__ == "__main__":
    unittest.main()
