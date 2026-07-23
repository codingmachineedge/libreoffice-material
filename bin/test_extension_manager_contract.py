#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material extension-manager composition contract (WIN-SYS-005)."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-extension-manager-contract.py"
SPEC = importlib.util.spec_from_file_location("check_extension_manager_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
POLICY = VALIDATOR.POLICY_PATH
EXTMGR = "desktop/uiconfig/ui/extensionmanager.ui"
DEPS = "desktop/uiconfig/ui/dependenciesdialog.ui"
UPDATEDLG = "desktop/uiconfig/ui/updatedialog.ui"
INSTALLFORALL = "desktop/uiconfig/ui/installforalldialog.ui"
EXTMENU = "desktop/uiconfig/ui/extensionmenu.ui"


class ExtensionManagerContractTest(unittest.TestCase):
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

    def _dialog(self, registry: dict, dialog_id: str) -> dict:
        for dialog in registry["dialogs"]:
            if dialog.get("id") == dialog_id:
                return dialog
        raise AssertionError(f"dialog {dialog_id} not found")

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

    # -- honesty guards ----------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["carveouts"]["list_item_paint"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveouts:list_item_paint:status" in e for e in errors), errors)

    def test_regex_status_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["regex_search"]["status"] = "implemented-here"
        errors = self.failures(registry=registry)
        self.assertTrue(any("regex_search:status" in e for e in errors), errors)

    # -- definition.xml part cross-checks ----------------------------------
    def test_part_token_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialog_parts"]["parts"]["progress_bar"]["states"][0]["tokens"]["fill"] = "@surface"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("dialog_parts:progress_bar" in e and "token drift" in e for e in errors), errors
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
            '<state enabled="true" extra="action">', '<state enabled="true" extra="actionZ">', 1
        )
        self.assert_mutation_changed(DEFINITION, definition)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("no <state> matching" in e for e in errors), errors)

    def test_definition_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DEFINITION))
        self.assertTrue(any("definition:file missing" in e for e in errors), errors)

    # -- .ui footer / button-box composition -------------------------------
    def test_action_widget_response_flip_fails(self) -> None:
        source = self.contents[UPDATEDLG].replace(
            '<action-widget response="-5">ok</action-widget>',
            '<action-widget response="-8">ok</action-widget>',
            1,
        )
        self.assert_mutation_changed(UPDATEDLG, source)
        errors = self.failures(contents=self.with_content(UPDATEDLG, source))
        self.assertTrue(
            any("dialog[UpdateDialog]" in e and "footer composition drift" in e for e in errors),
            errors,
        )

    def test_informational_gains_second_decision_button_fails(self) -> None:
        source = self.contents[DEPS].replace(
            '      <action-widget response="-5">ok</action-widget>\n    </action-widgets>',
            '      <action-widget response="-5">ok</action-widget>\n'
            '      <action-widget response="-6">cancel</action-widget>\n    </action-widgets>',
            1,
        )
        self.assert_mutation_changed(DEPS, source)
        errors = self.failures(contents=self.with_content(DEPS, source))
        self.assertTrue(
            any("dialog[Dependencies]" in e and "footer composition drift" in e for e in errors),
            errors,
        )

    def test_button_label_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self._dialog(registry, "ExtensionManagerDialog")["buttons"][0]["label"] = "_Wrong"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("dialog[ExtensionManagerDialog]" in e and "label drift" in e for e in errors), errors
        )

    def test_button_secondary_flag_drift_via_registry_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        for button in self._dialog(registry, "ExtensionManagerDialog")["buttons"]:
            if button["id"] == "updatebtn":
                button["secondary"] = False
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("updatebtn" in e and "secondary flag drift" in e for e in errors), errors
        )

    def test_primary_missing_default_fails(self) -> None:
        source = self.contents[INSTALLFORALL].replace(
            '<property name="has-default">True</property>', "", 1
        )
        self.assert_mutation_changed(INSTALLFORALL, source)
        errors = self.failures(contents=self.with_content(INSTALLFORALL, source))
        self.assertTrue(
            any("dialog[InstallForAllDialog]" in e and "has-default" in e for e in errors), errors
        )

    def test_menu_class_drift_fails(self) -> None:
        source = self.contents[EXTMENU].replace(
            'class="GtkMenu" id="menu"', 'class="GtkBox" id="menu"', 1
        )
        self.assert_mutation_changed(EXTMENU, source)
        errors = self.failures(contents=self.with_content(EXTMENU, source))
        self.assertTrue(any("menu[menu]" in e and "class is" in e for e in errors), errors)

    def test_ui_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(EXTMGR))
        self.assertTrue(any("file missing" in e for e in errors), errors)

    def test_ui_unparseable_fails(self) -> None:
        errors = self.failures(contents=self.with_content(EXTMGR, "<interface><broken"))
        self.assertTrue(any("unparseable xml" in e for e in errors), errors)

    # -- KeepModal reconciliation (dialog-notification-policy.csv) ----------
    def test_modal_policy_demotion_fails(self) -> None:
        policy = self.contents[POLICY].replace(
            "extensionmanager.ui,ExtensionManagerDialog,GtkDialog,native-exclusion",
            "extensionmanager.ui,ExtensionManagerDialog,GtkDialog,bottom-right",
            1,
        )
        self.assert_mutation_changed(POLICY, policy)
        errors = self.failures(contents=self.with_content(POLICY, policy))
        self.assertTrue(
            any("modal_policy:ExtensionManagerDialog" in e and "must stay" in e for e in errors),
            errors,
        )

    def test_modal_policy_missing_row_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["modal_policy"]["roots"].append(
            {"ui_path": "desktop/uiconfig/ui/nonexistent.ui", "object_id": "Nope"}
        )
        errors = self.failures(registry=registry)
        self.assertTrue(any("modal_policy:Nope:no row" in e for e in errors), errors)

    def test_modal_policy_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(POLICY))
        self.assertTrue(any("modal_policy:policy file missing" in e for e in errors), errors)

    # -- regex-search adjacency pin ----------------------------------------
    def test_regex_builder_removed_fails(self) -> None:
        source = self.contents[EXTMGR].replace(
            'id="search_regex_builder"', 'id="search_regex_builderX"'
        )
        self.assert_mutation_changed(EXTMGR, source)
        errors = self.failures(contents=self.with_content(EXTMGR, source))
        self.assertTrue(any("regex_search" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
