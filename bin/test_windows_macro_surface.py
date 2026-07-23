#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the macro-surface contract (WIN-SYS-006).

Each mutation breaks exactly one pinned guarantee against an in-memory copy of the
registry or the source tree and asserts the checker fails closed. A positive
control proves the pristine tree passes. The real tree is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-macro-surface.py"
SPEC = importlib.util.spec_from_file_location("check_windows_macro_surface", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CSV = VALIDATOR.POLICY_REGISTRY
BASTYPES = "basctl/source/basicide/bastypes.cxx"
STRINGS = "basctl/inc/strings.hrc"
HELPER = "include/sfx2/destructiveconfirmation.hxx"
SECUI = "uui/uiconfig/ui/macrowarnmedium.ui"
SECSRC = "uui/source/secmacrowarnings.cxx"


class MacroSurfaceTest(unittest.TestCase):
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

    # -- shared helper -----------------------------------------------------
    def test_shared_helper_entry_point_renamed_fails(self) -> None:
        text = self.contents[HELPER].replace(
            "bool ConfirmDestructiveAction(weld::Widget* pParent",
            "bool ConfirmDestructiveActionX(weld::Widget* pParent",
            1,
        )
        self.assert_changed(HELPER, text)
        errors = self.failures(contents=self.with_content(HELPER, text))
        self.assertTrue(any("shared_helper:marker" in e for e in errors), errors)

    # -- destructive conversion: present markers ---------------------------
    def test_confirm_dispatch_removed_fails(self) -> None:
        text = self.contents[BASTYPES].replace(
            "return sfx2::ConfirmDestructiveAction(pParent, aConfirm);",
            "return false;",
            1,
        )
        self.assert_changed(BASTYPES, text)
        errors = self.failures(contents=self.with_content(BASTYPES, text))
        self.assertTrue(any("destructive_conversions:present_marker" in e for e in errors), errors)

    def test_include_removed_fails(self) -> None:
        text = self.contents[BASTYPES].replace(
            "#include <sfx2/destructiveconfirmation.hxx>", "", 1
        )
        self.assert_changed(BASTYPES, text)
        errors = self.failures(contents=self.with_content(BASTYPES, text))
        self.assertTrue(any("destructive_conversions:present_marker" in e for e in errors), errors)

    # -- destructive conversion: absent markers (raw box must stay gone) ---
    def test_raw_yesno_box_reintroduced_fails(self) -> None:
        # The raw Question/YesNo destructive box must not come back in real code.
        text = self.contents[BASTYPES].replace(
            "return sfx2::ConfirmDestructiveAction(pParent, aConfirm);",
            "auto eButtons = VclButtonsType::YesNo; (void)eButtons; "
            "return sfx2::ConfirmDestructiveAction(pParent, aConfirm);",
            1,
        )
        self.assert_changed(BASTYPES, text)
        errors = self.failures(contents=self.with_content(BASTYPES, text))
        self.assertTrue(any("destructive_conversions:absent_marker" in e for e in errors), errors)

    # -- destructive conversion: per-caller verb ---------------------------
    def test_overwrite_caller_passing_delete_verb_fails(self) -> None:
        # QueryReplaceMacro must pass the Overwrite verb, never the Delete verb.
        text = self.contents[BASTYPES].replace(
            "QueryDel( rName, IDEResId( RID_STR_QUERYREPLACEMACRO ), "
            "IDEResId( RID_STR_QUERYREPLACEBTN ), pParent )",
            "QueryDel( rName, IDEResId( RID_STR_QUERYREPLACEMACRO ), "
            "IDEResId( RID_STR_QUERYDELBTN ), pParent )",
            1,
        )
        self.assert_changed(BASTYPES, text)
        errors = self.failures(contents=self.with_content(BASTYPES, text))
        self.assertTrue(
            any("call_site[QueryReplaceMacro]" in e for e in errors), errors
        )

    def test_call_site_pattern_missing_fails(self) -> None:
        text = self.contents[BASTYPES].replace(
            "QueryDel( rName, IDEResId( RID_STR_QUERYDELMODULE ), "
            "IDEResId( RID_STR_QUERYDELBTN ), pParent )",
            "QueryDel( rName, IDEResId( RID_STR_QUERYDELMODULE ), pParent )",
            1,
        )
        self.assert_changed(BASTYPES, text)
        errors = self.failures(contents=self.with_content(BASTYPES, text))
        self.assertTrue(any("call_site[QueryDelModule]" in e for e in errors), errors)

    # -- destructive conversion: preserved wording -------------------------
    def test_library_reference_distinction_collapsed_fails(self) -> None:
        # Collapsing "delete the reference to the XX library" into plain "delete the XX library"
        # must fail -- the reference distinction is load-bearing.
        text = self.contents[STRINGS].replace(
            "Do you want to delete the reference to the XX library?",
            "Do you want to delete the XX library?",
            1,
        )
        self.assert_changed(STRINGS, text)
        errors = self.failures(contents=self.with_content(STRINGS, text))
        self.assertTrue(any("preserved_string" in e for e in errors), errors)

    def test_consequence_string_removed_fails(self) -> None:
        text = self.contents[STRINGS].replace(
            'RID_STR_QUERYDELCONSEQUENCE", "This action cannot be undone."',
            'RID_STR_QUERYDELCONSEQUENCE", "Are you sure?"',
            1,
        )
        self.assert_changed(STRINGS, text)
        errors = self.failures(contents=self.with_content(STRINGS, text))
        self.assertTrue(any("preserved_string" in e for e in errors), errors)

    # -- security prompt: safe default -------------------------------------
    def test_footer_response_corrupted_fails(self) -> None:
        ui = self.contents[SECUI].replace(
            '<action-widget response="-6">cancel</action-widget>',
            '<action-widget response="-5">cancel</action-widget>',
            1,
        )
        self.assert_changed(SECUI, ui)
        errors = self.failures(contents=self.with_content(SECUI, ui))
        self.assertTrue(any("security_prompt:footer drift" in e for e in errors), errors)

    def test_safe_button_loses_has_default_fails(self) -> None:
        ui = self.contents[SECUI].replace(
            '<property name="has-default">True</property>', "", 1
        )
        self.assert_changed(SECUI, ui)
        errors = self.failures(contents=self.with_content(SECUI, ui))
        self.assertTrue(
            any("security_prompt:safe button" in e and "has-default" in e for e in errors), errors
        )

    def test_unsafe_button_gains_has_default_fails(self) -> None:
        ui = self.contents[SECUI].replace(
            '<property name="label" translatable="yes" context="macrowarnmedium|ok">'
            "_Enable Macros</property>",
            '<property name="label" translatable="yes" context="macrowarnmedium|ok">'
            '_Enable Macros</property>\n                '
            '<property name="has-default">True</property>',
            1,
        )
        self.assert_changed(SECUI, ui)
        errors = self.failures(contents=self.with_content(SECUI, ui))
        self.assertTrue(
            any("security_prompt:unsafe button" in e and "has-default" in e for e in errors), errors
        )

    def test_safe_button_loses_initial_focus_fails(self) -> None:
        src = self.contents[SECSRC].replace("mxDisableBtn->grab_focus();", "", 1)
        self.assert_changed(SECSRC, src)
        errors = self.failures(contents=self.with_content(SECSRC, src))
        self.assertTrue(
            any("security_prompt:source_present_marker" in e for e in errors), errors
        )

    def test_unsafe_button_grabs_focus_fails(self) -> None:
        src = self.contents[SECSRC].replace(
            "mxDisableBtn->grab_focus();",
            "mxDisableBtn->grab_focus(); mxEnableBtn->grab_focus();",
            1,
        )
        self.assert_changed(SECSRC, src)
        errors = self.failures(contents=self.with_content(SECSRC, src))
        self.assertTrue(
            any("security_prompt:source_absent_marker" in e for e in errors), errors
        )

    # -- modal-surface ledger ----------------------------------------------
    def test_ledger_root_flipped_to_notification_form_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "basctl/uiconfig/basicide/ui/organizedialog.ui,OrganizeDialog,GtkDialog,native-exclusion",
            "basctl/uiconfig/basicide/ui/organizedialog.ui,OrganizeDialog,GtkDialog,"
            "bottom-right-notification-form",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("organizedialog.ui" in e and "CSV policy" in e for e in errors), errors
        )

    def test_ledger_root_removed_from_csv_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "cui/uiconfig/ui/macroselectordialog.ui,MacroSelectorDialog,GtkDialog,"
            'native-exclusion,,"collects input, kept modal (router Classify: KeepModal)"\n',
            "",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("macroselectordialog.ui" in e and "no CSV policy row" in e for e in errors), errors
        )

    def test_csv_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(CSV))
        self.assertTrue(any("policy_registry" in e and "missing" in e for e in errors), errors)

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

    def test_ledger_policy_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["modal_surface_ledger"]["policy"] = "bottom-right-notification-form"
        errors = self.failures(registry=registry)
        self.assertTrue(any("modal_surface_ledger:policy" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
