#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Writer format-dialogs contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-writer-format-dialogs-contract.py"
SPEC = importlib.util.spec_from_file_location("check_writer_format_dialogs_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CHARDLG = "sw/source/ui/chrdlg/chardlg.cxx"
TABLEDLG = "sw/source/ui/table/tabledlg.cxx"
FRMDLG = "sw/source/ui/frmdlg/frmdlg.cxx"
CHAR_UI = "sw/uiconfig/swriter/ui/characterproperties.ui"
TABLE_UI = "sw/uiconfig/swriter/ui/tableproperties.ui"
BORDER_CXX = "cui/source/tabpages/border.cxx"
BORDER_UI = "cui/uiconfig/ui/borderpage.ui"


class WriterFormatDialogsContractTest(unittest.TestCase):
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

    def dialog(self, registry: dict, did: str) -> dict:
        return next(d for d in registry["dialogs"] if d["id"] == did)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- shared definition.xml part cross-checks --------------------------
    def test_definition_part_token_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["definition_parts"][0]["states"][0]["tokens"]["radius"] = "@corner-toolbar"
        errors = self.failures(registry=registry)
        self.assertTrue(any("definition_parts:tabitem" in e and "token drift" in e for e in errors), errors)

    def test_definition_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<radius name="corner-pill" value="20"/>', '<radius name="corner-pill" value="19"/>', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("metrics:corner-pill" in e and "metric drift" in e for e in errors), errors)

    def test_tab_style_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["tab_style"]["activeTabColor"] = "@surface"
        errors = self.failures(registry=registry)
        self.assertTrue(any("tab_style:activeTabColor" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("palette:@no-such-role" in e for e in errors), errors)

    # -- dialog composition (.ui) -----------------------------------------
    def test_notebook_tab_pos_drift_fails(self) -> None:
        source = self.contents[CHAR_UI].replace(
            '<property name="tab-pos">left</property>',
            '<property name="tab-pos">top</property>',
            1,
        )
        self.assert_mutation_changed(CHAR_UI, source)
        errors = self.failures(contents=self.with_content(CHAR_UI, source))
        self.assertTrue(any("notebook tab-pos" in e for e in errors), errors)

    def test_table_group_name_drift_fails(self) -> None:
        source = self.contents[TABLE_UI].replace(
            '<property name="group-name">icons</property>',
            '<property name="group-name">iconsX</property>',
            1,
        )
        self.assert_mutation_changed(TABLE_UI, source)
        errors = self.failures(contents=self.with_content(TABLE_UI, source))
        self.assertTrue(any("notebook group-name" in e for e in errors), errors)

    def test_footer_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.dialog(registry, "character")["ui_variants"][0]["footer"][1]["response"] = "-99"
        errors = self.failures(registry=registry)
        self.assertTrue(any("footer[1]" in e and "drift" in e for e in errors), errors)

    def test_variant_root_object_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.dialog(registry, "character")["ui_variants"][0]["dialog_object"] = "NoSuchDialog"
        errors = self.failures(registry=registry)
        self.assertTrue(any("root object 'NoSuchDialog' missing" in e for e in errors), errors)

    def test_ui_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(CHAR_UI))
        self.assertTrue(any("variant" in e and "file missing" in e for e in errors), errors)

    # -- AddTabPage page markers ------------------------------------------
    def test_addtabpage_marker_dropped_fails(self) -> None:
        source = self.contents[CHARDLG].replace(
            'AddTabPage(u"font"_ustr, TabResId(RID_TAB_FONT.aLabel), RID_SVXPAGE_CHAR_NAME,',
            'AddTabPage(u"fontX"_ustr, TabResId(RID_TAB_FONT.aLabel), RID_SVXPAGE_CHAR_NAME,',
            1,
        )
        self.assert_mutation_changed(CHARDLG, source)
        errors = self.failures(contents=self.with_content(CHARDLG, source))
        self.assertTrue(any("page[font]" in e and "AddTabPage marker missing" in e for e in errors), errors)

    def test_addtabpage_comment_only_fails(self) -> None:
        # Commenting the AddTabPage out proves comment-stripping fail-closed.
        source = self.contents[CHARDLG].replace(
            'AddTabPage(u"borders"_ustr, TabResId(RID_TAB_BORDER.aLabel), RID_SVXPAGE_BORDER,',
            '// AddTabPage(u"borders"_ustr, TabResId(RID_TAB_BORDER.aLabel), RID_SVXPAGE_BORDER,',
            1,
        )
        self.assert_mutation_changed(CHARDLG, source)
        errors = self.failures(contents=self.with_content(CHARDLG, source))
        self.assertTrue(any("page[borders]" in e and "AddTabPage marker missing" in e for e in errors), errors)

    # -- RID_M vs RID_L icon-prefix divergence ----------------------------
    def test_icon_prefix_normalized_fails(self) -> None:
        # "Fixing" the Table dialog's RID_L to RID_M (normalizing the divergence) must fail.
        source = self.contents[TABLEDLG].replace(
            "RID_L + RID_TAB_BORDER.sIconName", "RID_M + RID_TAB_BORDER.sIconName", 1
        )
        self.assert_mutation_changed(TABLEDLG, source)
        errors = self.failures(contents=self.with_content(TABLEDLG, source))
        self.assertTrue(
            any("dialogs[table]" in e and "icon_prefix_marker missing" in e for e in errors), errors
        )

    def test_invalid_icon_prefix_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.dialog(registry, "table")["icon_prefix"] = "RID_X"
        errors = self.failures(registry=registry)
        self.assertTrue(any("dialogs[table]:icon_prefix must be one of" in e for e in errors), errors)

    # -- frmdlg 3-way m_sDlgType applies_when -----------------------------
    def test_applies_when_guard_dropped_fails(self) -> None:
        source = self.contents[FRMDLG].replace(
            'm_sDlgType == "PictureDialog"', 'm_sDlgType == "XDialog"'
        )
        self.assert_mutation_changed(FRMDLG, source)
        errors = self.failures(contents=self.with_content(FRMDLG, source))
        self.assertTrue(any("applies_when guard missing" in e for e in errors), errors)

    def test_controller_bind_dropped_fails(self) -> None:
        source = self.contents[CHARDLG].replace(
            'u"modules/swriter/ui/characterproperties.ui"_ustr',
            'u"modules/swriter/ui/characterpropertiesX.ui"_ustr',
            1,
        )
        self.assert_mutation_changed(CHARDLG, source)
        errors = self.failures(contents=self.with_content(CHARDLG, source))
        self.assertTrue(any("controller bind missing" in e for e in errors), errors)

    def test_dialog_source_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(FRMDLG))
        self.assertTrue(any("dialogs[picture-frame]:source" in e and "missing" in e for e in errors), errors)

    def test_missing_required_dialog_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.dialog(registry, "table")["id"] = "renamed"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required table" in e for e in errors), errors)

    # -- shared pages ------------------------------------------------------
    def test_shared_page_bind_marker_dropped_fails(self) -> None:
        source = self.contents[BORDER_CXX].replace(
            'u"cui/ui/borderpage.ui"_ustr, u"BorderPage"_ustr',
            'u"cui/ui/borderpageX.ui"_ustr, u"BorderPage"_ustr',
            1,
        )
        self.assert_mutation_changed(BORDER_CXX, source)
        errors = self.failures(contents=self.with_content(BORDER_CXX, source))
        self.assertTrue(any("shared_pages[border]:bind marker missing" in e for e in errors), errors)

    def test_shared_page_root_object_missing_fails(self) -> None:
        source = self.contents[BORDER_UI].replace('id="BorderPage"', 'id="BorderPageX"', 1)
        self.assert_mutation_changed(BORDER_UI, source)
        errors = self.failures(contents=self.with_content(BORDER_UI, source))
        self.assertTrue(any("shared_pages[border]:page root object" in e for e in errors), errors)

    def test_page_references_unknown_shared_page_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        borders = next(
            p for p in self.dialog(registry, "character")["tab_pages"] if p["id"] == "borders"
        )
        borders["shared_page"] = "nope"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("shared_page 'nope' not declared" in e for e in errors), errors
        )

    # -- carve-outs --------------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["mail_merge"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:mail_merge:status must stay 'specified'" in e for e in errors), errors)

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
