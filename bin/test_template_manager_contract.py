#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material template-manager composition contract (WIN-SYS-004)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-template-manager-contract.py"
SPEC = importlib.util.spec_from_file_location("check_template_manager_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
TEMPLATEDLG = "sfx2/uiconfig/ui/templatedlg.ui"
SAVEASDLG = "sfx2/uiconfig/ui/saveastemplatedlg.ui"
CATEGORYDLG = "sfx2/uiconfig/ui/templatecategorydlg.ui"
TEMPLATEDLG_CXX = "sfx2/source/doc/templatedlg.cxx"


class TemplateManagerContractTest(unittest.TestCase):
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

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

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

    def test_status_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertIn("registry:status:must be source-declared", errors)

    def test_theme_flag_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["theme_flag"] = "SOMETHING"
        errors = self.failures(registry=registry)
        self.assertTrue(any("theme_flag" in e for e in errors), errors)

    def test_empty_dialogs_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialogs"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:dialogs:non-empty array required" in e for e in errors), errors)

    def test_duplicate_dialog_id_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialogs"].append(copy.deepcopy(registry["dialogs"][0]))
        errors = self.failures(registry=registry)
        self.assertTrue(any("id:duplicate" in e for e in errors), errors)

    # -- carve-out / regex honesty guards ----------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["thumbnail_card"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:thumbnail_card:status" in e for e in errors), errors)

    def test_regex_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["regex_search"]["status"] = "implemented-here"
        errors = self.failures(registry=registry)
        self.assertTrue(any("regex_search:status" in e for e in errors), errors)

    # -- definition.xml part cross-checks (read only, via registry) --------
    def test_part_token_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialog_parts"]["parts"]["dialog_surface"]["states"][0]["tokens"]["fill"] = "@surface"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("dialog_parts:dialog_surface" in e and "token drift" in e for e in errors), errors
        )

    def test_palette_role_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialog_parts"]["palette_colors"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("dialog_parts:palette:@no-such-role" in e for e in errors), errors)

    def test_metric_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialog_parts"]["metrics"][0]["value"] = "999"
        errors = self.failures(registry=registry)
        self.assertTrue(any("metric drift" in e for e in errors), errors)

    # -- definition.xml part cross-checks (read only, via content) ---------
    def test_definition_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="BackgroundDialog"><state><rect stroke="@surface-container" '
            'fill="@surface-container" stroke-width="@stroke-none"/></state></part>',
            '<part value="BackgroundDialog"><state><rect stroke="@surface-container" '
            'fill="@surface" stroke-width="@stroke-none"/></state></part>',
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("dialog_parts:dialog_surface" in e and "token drift" in e for e in errors), errors
        )

    def test_definition_missing_part_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<frame><part value="Border">', '<frame><part value="BorderX">', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("missing in definition.xml" in e for e in errors), errors)

    def test_definition_missing_state_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" focused="true"><rect stroke="@primary" fill="@surface" '
            'stroke-width="@stroke-standard" radius="@corner-container"/></state>',
            "",
            1,
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    def test_definition_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DEFINITION))
        self.assertTrue(any("definition:file missing" in e for e in errors), errors)

    # -- .ui composition pinning ------------------------------------------
    def test_action_widget_response_flip_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace(
            '<action-widget response="-5">ok</action-widget>',
            '<action-widget response="-8">ok</action-widget>',
            1,
        )
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(any("footer composition drift" in e for e in errors), errors)

    def test_action_widget_reorder_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace(
            '      <action-widget response="-11">help</action-widget>\n'
            '      <action-widget response="-5">ok</action-widget>\n',
            '      <action-widget response="-5">ok</action-widget>\n'
            '      <action-widget response="-11">help</action-widget>\n',
            1,
        )
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(any("footer composition drift" in e for e in errors), errors)

    def test_removed_has_default_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace(
            '                <property name="has-default">True</property>\n', "", 1
        )
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(any("must carry has-default" in e for e in errors), errors)

    def test_required_widget_renamed_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace(
            'id="filter_application"', 'id="filter_applicationX"', 1
        )
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(
            any("required_widget:filter_application" in e and "missing" in e for e in errors), errors
        )

    def test_saveas_footer_drift_fails(self) -> None:
        source = self.contents[SAVEASDLG].replace(
            '<action-widget response="-6">cancel</action-widget>',
            '<action-widget response="-7">cancel</action-widget>',
            1,
        )
        self.assert_mutation_changed(SAVEASDLG, source)
        errors = self.failures(contents=self.with_content(SAVEASDLG, source))
        self.assertTrue(
            any("dialog[SaveAsTemplateDialog]" in e and "footer composition drift" in e for e in errors),
            errors,
        )

    def test_category_required_widget_missing_fails(self) -> None:
        source = self.contents[CATEGORYDLG].replace(
            'id="category_entry"', 'id="category_entryX"', 1
        )
        self.assert_mutation_changed(CATEGORYDLG, source)
        errors = self.failures(contents=self.with_content(CATEGORYDLG, source))
        self.assertTrue(
            any("dialog[TemplatesCategoryDialog]" in e and "category_entry" in e for e in errors),
            errors,
        )

    def test_ui_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(TEMPLATEDLG))
        self.assertTrue(any("file missing" in e for e in errors), errors)

    def test_ui_unparseable_fails(self) -> None:
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, "<interface><broken"))
        self.assertTrue(any("unparseable xml" in e for e in errors), errors)

    # -- regex-search adjacency pin ----------------------------------------
    def test_regex_builder_removed_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace(
            'id="search_filter_regex_builder"', 'id="search_filter_regex_builderX"'
        )
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(any("regex_search" in e for e in errors), errors)

    def test_regex_field_removed_fails(self) -> None:
        source = self.contents[TEMPLATEDLG].replace('id="search_filter"', 'id="search_filterX"')
        self.assert_mutation_changed(TEMPLATEDLG, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG, source))
        self.assertTrue(any("regex_search:field" in e for e in errors), errors)

    # -- runtime-set primary label pin (comment-stripped source) -----------
    def test_primary_label_marker_removed_fails(self) -> None:
        source = self.contents[TEMPLATEDLG_CXX].replace(
            "mxOKButton->set_label(SfxResId(STR_NEW_FROM_TEMPLATE))",
            "mxOKButton->set_label(SfxResId(STR_NEW_FROM_TEMPLATE_X))",
            1,
        )
        self.assert_mutation_changed(TEMPLATEDLG_CXX, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG_CXX, source))
        self.assertTrue(any("primary_label:runtime-set label marker" in e for e in errors), errors)

    def test_primary_label_marker_only_in_comment_fails(self) -> None:
        # The marker moved into a comment must NOT satisfy the contract (comment-stripped scan).
        source = self.contents[TEMPLATEDLG_CXX].replace(
            "    mxOKButton->set_label(SfxResId(STR_NEW_FROM_TEMPLATE));",
            "    // mxOKButton->set_label(SfxResId(STR_NEW_FROM_TEMPLATE));",
            1,
        )
        self.assert_mutation_changed(TEMPLATEDLG_CXX, source)
        errors = self.failures(contents=self.with_content(TEMPLATEDLG_CXX, source))
        self.assertTrue(any("primary_label:runtime-set label marker" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
