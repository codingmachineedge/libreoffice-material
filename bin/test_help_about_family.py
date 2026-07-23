#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Help/About family contract (WIN-SYS-015).

Each mutation breaks exactly one pinned guarantee against an in-memory copy of the
registry, a source ``.ui``, or a shared policy/registry file and asserts the
checker fails closed. A positive control proves the pristine tree passes. The real
tree is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-help-about-family.py"
SPEC = importlib.util.spec_from_file_location("check_help_about_family", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CSV = VALIDATOR.POLICY_REGISTRY
ANATOMY = VALIDATOR.ANATOMY_REGISTRY
UIREG = VALIDATOR.UI_REGISTRY
ABOUT_UI = "cui/uiconfig/ui/aboutdialog.ui"
TIP_UI = "cui/uiconfig/ui/tipofthedaydialog.ui"


class HelpAboutFamilyTest(unittest.TestCase):
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

    def ui_registry_with(self, surface: str, inventory_id: str, mapped_by: str) -> str:
        reg = json.loads(self.contents[UIREG])
        found = False
        for s in reg["surfaces"]:
            if s["surface"] == surface:
                s["inventory_id"] = inventory_id
                s["mapped_by"] = mapped_by
                found = True
        self.assertTrue(found, f"surface {surface} not present to mutate")
        return json.dumps(reg, indent=2, ensure_ascii=False) + "\n"

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- anatomy: About ----------------------------------------------------
    def test_about_root_renamed_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<object class="GtkDialog" id="AboutDialog">',
            '<object class="GtkDialog" id="AboutDialogX">',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(any("anatomy_pinned[AboutDialog]:top-level" in e for e in errors), errors)

    def test_about_modal_property_removed_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<property name="modal">True</property>',
            '<property name="modal">False</property>',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(
            any("anatomy_pinned[AboutDialog]:.ui must declare modal=True" in e for e in errors),
            errors,
        )

    def test_about_dismiss_response_corrupted_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<action-widget response="-7">btnClose</action-widget>',
            '<action-widget response="-5">btnClose</action-widget>',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(any("anatomy_pinned[AboutDialog]:footer drift" in e for e in errors), errors)

    def test_about_second_action_widget_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<action-widget response="-7">btnClose</action-widget>',
            '<action-widget response="-7">btnClose</action-widget>\n'
            '      <action-widget response="-5">btnExtra</action-widget>',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(any("anatomy_pinned[AboutDialog]:footer drift" in e for e in errors), errors)

    def test_about_link_button_renamed_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<object class="GtkLinkButton" id="btnCredits">',
            '<object class="GtkLinkButton" id="btnCreditsX">',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(
            any("anatomy_pinned[AboutDialog]:widget 'btnCredits' missing" in e for e in errors),
            errors,
        )

    def test_about_link_button_class_changed_fails(self) -> None:
        ui = self.contents[ABOUT_UI].replace(
            '<object class="GtkLinkButton" id="btnWebsite">',
            '<object class="GtkButton" id="btnWebsite">',
            1,
        )
        self.assert_changed(ABOUT_UI, ui)
        errors = self.failures(contents=self.with_content(ABOUT_UI, ui))
        self.assertTrue(
            any("anatomy_pinned[AboutDialog]:widget 'btnWebsite' class" in e for e in errors),
            errors,
        )

    # -- anatomy: Tip (modal keyed off CSV) --------------------------------
    def test_tip_dismiss_response_corrupted_fails(self) -> None:
        ui = self.contents[TIP_UI].replace(
            '<action-widget response="-5">btnOk</action-widget>',
            '<action-widget response="-7">btnOk</action-widget>',
            1,
        )
        self.assert_changed(TIP_UI, ui)
        errors = self.failures(contents=self.with_content(TIP_UI, ui))
        self.assertTrue(any("anatomy_pinned[TipOfTheDayDialog]:footer drift" in e for e in errors), errors)

    def test_tip_nav_button_missing_fails(self) -> None:
        ui = self.contents[TIP_UI].replace(
            '<object class="GtkButton" id="btnNext">',
            '<object class="GtkButton" id="btnNextX">',
            1,
        )
        self.assert_changed(TIP_UI, ui)
        errors = self.failures(contents=self.with_content(TIP_UI, ui))
        self.assertTrue(
            any("anatomy_pinned[TipOfTheDayDialog]:widget 'btnNext' missing" in e for e in errors),
            errors,
        )

    def test_tip_modal_csv_row_flipped_fails(self) -> None:
        # Tip has no .ui modal property; flipping its CSV KeepModal row must fail the modal claim.
        csv_text = self.contents[CSV].replace(
            "cui/uiconfig/ui/tipofthedaydialog.ui,TipOfTheDayDialog,GtkDialog,native-exclusion",
            "cui/uiconfig/ui/tipofthedaydialog.ui,TipOfTheDayDialog,GtkDialog,"
            "bottom-right-notification-form",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("anatomy_pinned[TipOfTheDayDialog]:modal_source=csv" in e for e in errors), errors
        )

    # -- notification policy ----------------------------------------------
    def test_about_notification_row_flipped_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "cui/uiconfig/ui/aboutdialog.ui,AboutDialog,GtkDialog,native-exclusion",
            "cui/uiconfig/ui/aboutdialog.ui,AboutDialog,GtkDialog,bottom-right-notification-form",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("notification_policy:cui/uiconfig/ui/aboutdialog.ui" in e for e in errors), errors
        )

    # -- no destructive role ----------------------------------------------
    def test_family_added_as_destructive_migration_fails(self) -> None:
        anat = json.loads(self.contents[ANATOMY])
        anat.setdefault("migrations", []).append(
            {"id": "cui-aboutdialog-destructive", "file": "cui/source/dialogs/about.cxx",
             "act": "spurious", "verb": "Delete"}
        )
        text = json.dumps(anat, indent=2, ensure_ascii=False) + "\n"
        errors = self.failures(contents=self.with_content(ANATOMY, text))
        self.assertTrue(any("no_destructive_role" in e and "aboutdialog" in e for e in errors), errors)

    # -- family registry attribution --------------------------------------
    def test_family_surface_reverted_to_unassigned_fails(self) -> None:
        text = self.ui_registry_with("cui/uiconfig/ui/thesaurus.ui", "unassigned", "unassigned")
        errors = self.failures(contents=self.with_content(UIREG, text))
        self.assertTrue(
            any("family:cui/uiconfig/ui/thesaurus.ui:inventory_id" in e for e in errors), errors
        )

    def test_family_surface_reassigned_by_prefix_fails(self) -> None:
        text = self.ui_registry_with("cui/uiconfig/ui/hyphenate.ui", "WIN-SYS-015", "prefix")
        errors = self.failures(contents=self.with_content(UIREG, text))
        self.assertTrue(
            any("family:cui/uiconfig/ui/hyphenate.ui:mapped_by" in e for e in errors), errors
        )

    def test_family_surface_moved_to_other_row_fails(self) -> None:
        text = self.ui_registry_with("cui/uiconfig/ui/aboutdialog.ui", "WIN-DLG-002", "override")
        errors = self.failures(contents=self.with_content(UIREG, text))
        self.assertTrue(
            any("family:cui/uiconfig/ui/aboutdialog.ui:inventory_id" in e for e in errors), errors
        )

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_status_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertIn("registry:status:must be source-declared", errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)

    def test_expected_family_mismatch_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["family"] = registry["family"][:-1]
        errors = self.failures(registry=registry)
        self.assertTrue(any("family:expected_family" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
