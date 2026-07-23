#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Options dialog contract (WIN-DLG-002).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree (or a
deep copy of the registry) and asserts the checker fails closed, while the pristine production tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-options-dialog-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_options_dialog_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CSV = VALIDATOR.CSV_PATH
DIALOG = "cui/uiconfig/ui/optionsdialog.ui"
IMPL = "cui/source/options/treeopt.cxx"


class OptionsDialogContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(self, *, registry: dict | None = None, contents: dict[str, str] | None = None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
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

    # -- dialog shell ----------------------------------------------------------
    def test_dialog_modal_removed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="modal">True</property>', '<property name="modal">False</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("modal=True" in e for e in errors), errors)

    def test_tree_model_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="model">liststore1</property>', '<property name="model">liststore2</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("dialog_composition:tree model" in e for e in errors), errors)

    def test_headers_visible_flipped_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="headers-visible">False</property>', '<property name="headers-visible">True</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("headers-visible must be False" in e for e in errors), errors)

    def test_tree_lines_disabled_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<property name="enable-tree-lines">True</property>', '<property name="enable-tree-lines">False</property>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("enable-tree-lines must be True" in e for e in errors), errors)

    def test_liststore_column_count_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["dialog_composition"]["liststore"]["columns"] = 3
        errors = self.failures(registry=registry)
        self.assertTrue(any("liststore has" in e and "columns" in e for e in errors), errors)

    def test_regex_builder_missing_fails(self) -> None:
        contents = self.replace_once(DIALOG, 'id="searchEntry_regex_builder"', 'id="searchEntry_regex_builderX"')
        errors = self.failures(contents=contents)
        self.assertTrue(any("search_field:regex_builder" in e for e in errors), errors)

    # -- footer + Apply drift --------------------------------------------------
    def test_footer_response_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG, '<action-widget response="-5">ok</action-widget>', '<action-widget response="-99">ok</action-widget>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:action_widgets" in e and "drift" in e for e in errors), errors)

    def test_primary_default_removed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<property name="can-default">True</property>\n                <property name="has-default">True</property>',
            '<property name="can-default">True</property>\n                <property name="has-default">False</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary:OK button must be has-default" in e for e in errors), errors)

    def test_apply_becomes_action_widget_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<action-widget response="-6">cancel</action-widget>',
            '<action-widget response="-6">cancel</action-widget>\n      <action-widget response="200">apply</action-widget>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:apply_drift" in e and "is now an action-widget" in e for e in errors), errors)

    def test_apply_button_removed_fails(self) -> None:
        contents = self.replace_once(DIALOG, '<object class="GtkButton" id="apply">', '<object class="GtkButton" id="applyX">')
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:apply_drift" in e and "Apply button vanished" in e for e in errors), errors)

    # -- node groups -----------------------------------------------------------
    def test_addgroup_marker_missing_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            "SID_SC_EDITOPTIONS_RES[0].first), pScMod, pScMod, SID_SC_EDITOPTIONS",
            "SID_SC_EDITOPTIONS_RES[0].first), pScMod, pScMod, SID_SC_EDITOPTIONSXX",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("node_groups:Calc" in e and "AddGroup marker" in e for e in errors), errors)

    def test_node_group_reorder_fails(self) -> None:
        registry = self.registry_copy()
        groups = registry["node_groups"]
        groups[0], groups[1] = groups[1], groups[0]
        errors = self.failures(registry=registry)
        self.assertTrue(any("node_groups" in e and "out of order" in e for e in errors), errors)

    def test_res_array_missing_in_hrc_fails(self) -> None:
        registry = self.registry_copy()
        registry["node_groups"][0]["res_array"] = "SID_FAKE_OPTIONS_RES"
        errors = self.failures(registry=registry)
        self.assertTrue(any("resource array SID_FAKE_OPTIONS_RES[] missing" in e for e in errors), errors)

    # -- native tree parts -----------------------------------------------------
    def test_windowbackground_token_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<part value="BackgroundDialog"><state><rect stroke="@surface-container" fill="@surface-container" stroke-width="@stroke-none"/></state></part>',
            '<part value="BackgroundDialog"><state><rect stroke="@surface-container" fill="@primary" stroke-width="@stroke-none"/></state></part>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("tree_parts:windowbackground-dialog" in e and "token drift" in e for e in errors), errors)

    def test_tree_metric_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION, '<metric name="size-tree-node" value="20"/>', '<metric name="size-tree-node" value="21"/>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("tree_parts:metric:size-tree-node" in e for e in errors), errors)

    def test_tree_palette_role_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["tree_parts"]["palette_roles"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("tree_parts:palette:@no-such-role" in e for e in errors), errors)

    # -- modal exclusion + carve-outs ------------------------------------------
    def test_modal_exclusion_policy_desync_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "cui/uiconfig/ui/optionsdialog.ui,OptionsDialog,GtkDialog,native-exclusion",
            "cui/uiconfig/ui/optionsdialog.ui,OptionsDialog,GtkDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("modal_exclusion" in e and "OptionsDialog" in e and "policy is" in e for e in errors), errors)

    def test_carveout_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveouts"]["tree_row_selection_fill"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:tree_row_selection_fill:status must stay 'specified'" in e for e in errors), errors)

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


if __name__ == "__main__":
    unittest.main()
