#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the PDF export dialog contract (WIN-SYS-002).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree and
asserts the checker fails closed, while the pristine production tree passes. The real repository
is never mutated: every mutation is applied to the ``contents`` map ``load_repository`` returns
or to a deep copy of the registry.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-pdf-export-dialog-contract.py"
SPEC = importlib.util.spec_from_file_location("check_pdf_export_dialog_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CSV = VALIDATOR.CSV_PATH
IMPL = "filter/source/pdf/impdialog.cxx"
DIALOG = "filter/uiconfig/ui/pdfoptionsdialog.ui"
GENERAL = "filter/uiconfig/ui/pdfgeneralpage.ui"


class PdfExportDialogContractTest(unittest.TestCase):
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

    # -- definition.xml native parts (read-only) -------------------------------
    def test_tabitem_selected_token_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="true" selected="true"><rect stroke="@primary-container" '
            'fill="@primary-container" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
            '<state enabled="true" selected="true"><rect stroke="@primary-container" '
            'fill="@surface" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:tabitem" in e and "token drift" in e for e in errors), errors)

    def test_tabitem_missing_state_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="true" focused="true"><rect stroke="@primary" '
            'fill="@surface-container" stroke-width="@stroke-standard" radius="@corner-pill"/></state>',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:tabitem" in e and "no <state> matching" in e for e in errors), errors)

    def test_tabpane_token_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<tabpane><part value="Entire"><state><rect stroke="@outline-variant" '
            'fill="@surface" stroke-width="@stroke-thin" radius="@corner-container"/></state></part></tabpane>',
            '<tabpane><part value="Entire"><state><rect stroke="@outline-variant" '
            'fill="@primary" stroke-width="@stroke-thin" radius="@corner-container"/></state></part></tabpane>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:tabpane" in e and "token drift" in e for e in errors), errors)

    def test_missing_part_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION, '<tabpane><part value="Entire">', '<tabpane><part value="EntireX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:tabpane" in e and "missing in definition.xml" in e for e in errors), errors)

    def test_metric_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION, '<metric name="height-tab" value="40"/>', '<metric name="height-tab" value="38"/>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:metric:height-tab" in e and "metric drift" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["native_parts"]["palette_roles"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("native_parts:palette:@no-such-role" in e for e in errors), errors)

    def test_part_attr_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<part value="Entire" margin-width="@space-tab-inline" height="@height-tab">',
            '<part value="Entire" margin-width="@space-tab-inline" height="@height-window-title">',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("native_parts:tabitem:part attr height" in e for e in errors), errors)

    # -- pdfoptionsdialog.ui composition ---------------------------------------
    def test_notebook_tab_pos_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="tab-pos">left</property>', '<property name="tab-pos">top</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("notebook:tab-pos" in e for e in errors), errors)

    def test_notebook_id_renamed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<object class="GtkNotebook" id="tabcontrol">', '<object class="GtkNotebook" id="tabcontrolX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("notebook:GtkNotebook" in e and "missing" in e for e in errors), errors)

    def test_footer_response_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<action-widget response="-5">ok</action-widget>', '<action-widget response="-99">ok</action-widget>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:action_widgets" in e and "drift" in e for e in errors), errors)

    def test_primary_default_removed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="has-default">True</property>', '<property name="has-default">False</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary" in e and "has-default" in e for e in errors), errors)

    def test_primary_label_drift_fails(self) -> None:
        contents = self.replace_once(DIALOG, ">E_xport</property>", ">Export</property>")
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary:label" in e for e in errors), errors)

    def test_dialog_ui_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DIALOG))
        self.assertTrue(any("dialog_ui:file missing" in e for e in errors), errors)

    # -- impdialog.cxx tab composition -----------------------------------------
    def test_tab_out_of_order_fails(self) -> None:
        # Registry declares initialview before general, but source composes general first.
        registry = self.registry_copy()
        seq = registry["tab_sequence"]
        seq[0], seq[1] = seq[1], seq[0]
        errors = self.failures(registry=registry)
        self.assertTrue(any("out of order" in e for e in errors), errors)

    def test_addtabpage_marker_removed_fails(self) -> None:
        contents = self.replace_once(IMPL, 'AddTabPage(u"links"_ustr', 'AddTabPage(u"linksX"_ustr')
        errors = self.failures(contents=contents)
        self.assertTrue(any("tab_sequence" in e and 'AddTabPage(u"links"_ustr' in e for e in errors), errors)

    def test_setcurpageid_changed_fails(self) -> None:
        contents = self.replace_once(
            IMPL, 'SetCurPageId(u"general"_ustr)', 'SetCurPageId(u"security"_ustr)'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("SetCurPageId" in e and "default page changed" in e for e in errors), errors)

    def test_create_class_unbound_from_addtabpage_fails(self) -> None:
        # The Create factory also appears at its own definition, so only the AddTabPage-bound
        # occurrence (trailing comma) is severed here; the checker must still fail closed.
        contents = self.replace_once(IMPL, "ImpPDFTabViewerPage::Create,", "ImpPDFTabViewerPageX::Create,")
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("create_class" in e and "ImpPDFTabViewerPage::Create" in e and "AddTabPage" in e for e in errors),
            errors,
        )

    def test_page_binding_drift_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            'u"filter/ui/pdflinkspage.ui"_ustr, u"PdfLinksPage"_ustr',
            'u"filter/ui/pdflinkspageX.ui"_ustr, u"PdfLinksPage"_ustr',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("page binding" in e and "PdfLinksPage" in e for e in errors), errors)

    def test_commented_out_addtabpage_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            'AddTabPage(u"general"_ustr, TabResId(RID_TAB_ORGANIZER.aLabel), ImpPDFTabGeneralPage::Create,',
            '// AddTabPage(u"general"_ustr, TabResId(RID_TAB_ORGANIZER.aLabel), ImpPDFTabGeneralPage::Create,',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any('AddTabPage(u"general"_ustr' in e for e in errors), errors)

    # -- page .ui bindings -----------------------------------------------------
    def test_page_root_id_removed_fails(self) -> None:
        contents = self.replace_once(GENERAL, 'id="PdfGeneralPage"', 'id="PdfGeneralPageX"')
        errors = self.failures(contents=contents)
        self.assertTrue(any("root object id" in e and "PdfGeneralPage" in e for e in errors), errors)

    def test_group_frame_removed_fails(self) -> None:
        contents = self.replace_once(
            GENERAL,
            'context="pdfgeneralpage|label1">Range</property>',
            'context="pdfgeneralpage|label1">RangeX</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("group frame" in e and "Range" in e for e in errors), errors)

    def test_page_ui_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(GENERAL))
        self.assertTrue(any("ui_source file missing" in e for e in errors), errors)

    # -- shared CSV modal exclusions (read-only) -------------------------------
    def test_modal_exclusion_policy_desync_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "filter/uiconfig/ui/pdfoptionsdialog.ui,PdfOptionsDialog,GtkDialog,native-exclusion",
            "filter/uiconfig/ui/pdfoptionsdialog.ui,PdfOptionsDialog,GtkDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("modal_exclusions" in e and "PdfOptionsDialog" in e and "policy is" in e for e in errors),
            errors,
        )

    def test_modal_exclusion_row_removed_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            'filter/uiconfig/ui/warnpdfdialog.ui,WarnPDFDialog,GtkMessageDialog,native-exclusion,,'
            '"collects input, kept modal (router Classify: KeepModal)"\n',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("modal_exclusions" in e and "WarnPDFDialog" in e and "absent" in e for e in errors),
            errors,
        )

    # -- honest carve-outs -----------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveouts"]["tab_rail_geometry"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("carveouts:tab_rail_geometry:status must stay 'specified'" in e for e in errors), errors
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

    def test_definition_file_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["definition_file"] = "vcl/uiconfig/theme_definitions/other.xml"
        errors = self.failures(registry=registry)
        self.assertIn("registry:definition_file:unexpected path", errors)


if __name__ == "__main__":
    unittest.main()
