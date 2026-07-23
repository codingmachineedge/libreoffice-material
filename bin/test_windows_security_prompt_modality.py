#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the security-prompt modality contract (WIN-SYS-007).

Each mutation breaks exactly one pinned guarantee against an in-memory copy of
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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-security-prompt-modality.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_security_prompt_modality", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CSV = VALIDATOR.POLICY_REGISTRY
DIGSIG_UI = "xmlsecurity/uiconfig/ui/digitalsignaturesdialog.ui"
DIGSIG_SRC = "xmlsecurity/source/dialogs/digitalsignaturesdialog.cxx"
MACROSEC_SRC = "xmlsecurity/source/dialogs/macrosecurity.cxx"
CHOOSER_SRC = "xmlsecurity/source/dialogs/certificatechooser.cxx"
SECLEVEL_UI = "xmlsecurity/uiconfig/ui/securitylevelpage.ui"


class SecurityPromptModalityTest(unittest.TestCase):
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

    # -- Layer 1: CSV native-exclusion policy ------------------------------
    def test_csv_flip_to_notification_form_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "xmlsecurity/uiconfig/ui/digitalsignaturesdialog.ui,DigitalSignaturesDialog,GtkDialog,"
            'native-exclusion,,"security/trust decision, kept modal (router Classify: KeepModal)"',
            "xmlsecurity/uiconfig/ui/digitalsignaturesdialog.ui,DigitalSignaturesDialog,GtkDialog,"
            "bottom-right-notification-form,default,",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("dialog[DigitalSignaturesDialog]:CSV policy" in e for e in errors), errors
        )

    def test_csv_reason_drift_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "xmlsecurity/uiconfig/ui/macrosecuritydialog.ui,MacroSecurityDialog,GtkDialog,"
            'native-exclusion,,"security/trust decision, kept modal (router Classify: KeepModal)"',
            "xmlsecurity/uiconfig/ui/macrosecuritydialog.ui,MacroSecurityDialog,GtkDialog,"
            'native-exclusion,,"collects input, kept modal (router Classify: KeepModal)"',
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(
            any("dialog[MacroSecurityDialog]:CSV exclusion_reason drift" in e for e in errors),
            errors,
        )

    def test_csv_row_removed_fails(self) -> None:
        csv_text = self.contents[CSV].replace(
            "cui/uiconfig/ui/certdialog.ui,CertDialog,GtkDialog,"
            'native-exclusion,,"collects input, kept modal (router Classify: KeepModal)"\n',
            "",
            1,
        )
        self.assert_changed(CSV, csv_text)
        errors = self.failures(contents=self.with_content(CSV, csv_text))
        self.assertTrue(any("dialog[CertDialog]:no CSV policy row" in e for e in errors), errors)

    # -- Layer 2: live router classification -------------------------------
    def test_declared_classification_mismatch_fails(self) -> None:
        # Declaring a security dialog as 'input' contradicts the live router (returns 'security').
        registry = copy.deepcopy(self.registry)
        for dialog in registry["dialogs"]:
            if dialog["id"] == "DigitalSignaturesDialog":
                dialog["classification"] = "input"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("dialog[DigitalSignaturesDialog]:router reason drift" in e for e in errors)
            or any("dialog[DigitalSignaturesDialog]:CSV exclusion_reason drift" in e for e in errors),
            errors,
        )

    def test_classification_out_of_domain_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialogs"][0]["classification"] = "acknowledgment"
        errors = self.failures(registry=registry)
        self.assertTrue(any("classification" in e and "must be one of" in e for e in errors), errors)

    # -- Layer 3: modal footer ---------------------------------------------
    def test_footer_response_corrupted_fails(self) -> None:
        ui = self.contents[DIGSIG_UI].replace(
            '<action-widget response="-7">close</action-widget>',
            '<action-widget response="-5">close</action-widget>',
            1,
        )
        self.assert_changed(DIGSIG_UI, ui)
        errors = self.failures(contents=self.with_content(DIGSIG_UI, ui))
        self.assertTrue(any("dialog[DigitalSignaturesDialog]:footer drift" in e for e in errors), errors)

    def test_footer_widget_renamed_fails(self) -> None:
        ui = self.contents[DIGSIG_UI].replace(
            '<action-widget response="-11">help</action-widget>',
            '<action-widget response="-11">helpX</action-widget>',
            1,
        )
        self.assert_changed(DIGSIG_UI, ui)
        errors = self.failures(contents=self.with_content(DIGSIG_UI, ui))
        self.assertTrue(any("dialog[DigitalSignaturesDialog]:footer drift" in e for e in errors), errors)

    # -- Layer 4: source reachability --------------------------------------
    def test_generic_dialog_controller_bind_removed_fails(self) -> None:
        source = self.contents[MACROSEC_SRC].replace(
            'u"xmlsec/ui/macrosecuritydialog.ui"_ustr', 'u"xmlsec/ui/macrosecuritydialogX.ui"_ustr', 1
        )
        self.assert_changed(MACROSEC_SRC, source)
        errors = self.failures(contents=self.with_content(MACROSEC_SRC, source))
        self.assertTrue(any("dialog[MacroSecurityDialog]:modal_marker" in e for e in errors), errors)

    def test_run_call_removed_fails(self) -> None:
        source = self.contents[CHOOSER_SRC].replace(
            "return GenericDialogController::run();", "return 0;", 1
        )
        self.assert_changed(CHOOSER_SRC, source)
        errors = self.failures(contents=self.with_content(CHOOSER_SRC, source))
        self.assertTrue(any("dialog[SelectCertificateDialog]:modal_marker" in e for e in errors), errors)

    def test_marker_only_in_comment_fails(self) -> None:
        # A bind that survives only as a comment (dead code removed) must not satisfy the contract.
        source = self.contents[DIGSIG_SRC].replace(
            ': GenericDialogController(pParent, u"xmlsec/ui/digitalsignaturesdialog.ui"_ustr, u"DigitalSignaturesDialog"_ustr)',
            '// GenericDialogController(pParent, u"xmlsec/ui/digitalsignaturesdialog.ui"_ustr, u"DigitalSignaturesDialog"_ustr)',
            1,
        )
        self.assert_changed(DIGSIG_SRC, source)
        errors = self.failures(contents=self.with_content(DIGSIG_SRC, source))
        self.assertTrue(any("dialog[DigitalSignaturesDialog]:modal_marker" in e for e in errors), errors)

    # -- embedded tabbed pages ---------------------------------------------
    def test_embedded_page_root_renamed_fails(self) -> None:
        ui = self.contents[SECLEVEL_UI].replace('id="SecurityLevelPage"', 'id="SecurityLevelPageX"', 1)
        self.assert_changed(SECLEVEL_UI, ui)
        errors = self.failures(contents=self.with_content(SECLEVEL_UI, ui))
        self.assertTrue(
            any("dialog[MacroSecurityDialog]:embedded page root" in e for e in errors), errors
        )

    def test_embedded_page_source_bind_removed_fails(self) -> None:
        source = self.contents[MACROSEC_SRC].replace(
            'u"xmlsec/ui/securitytrustpage.ui"_ustr, u"SecurityTrustPage"_ustr',
            'u"xmlsec/ui/securitytrustpageX.ui"_ustr, u"SecurityTrustPage"_ustr',
            1,
        )
        self.assert_changed(MACROSEC_SRC, source)
        errors = self.failures(contents=self.with_content(MACROSEC_SRC, source))
        self.assertTrue(
            any("dialog[MacroSecurityDialog]:embedded_page[SecurityTrustPage] source bind" in e for e in errors),
            errors,
        )

    def test_dialog_ui_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DIGSIG_UI))
        self.assertTrue(any("dialog[DigitalSignaturesDialog]:ui:file missing" in e for e in errors), errors)

    def test_top_level_dialog_object_renamed_fails(self) -> None:
        ui = self.contents[DIGSIG_UI].replace(
            '<object class="GtkDialog" id="DigitalSignaturesDialog">',
            '<object class="GtkDialog" id="DigitalSignaturesDialogX">',
            1,
        )
        self.assert_changed(DIGSIG_UI, ui)
        errors = self.failures(contents=self.with_content(DIGSIG_UI, ui))
        self.assertTrue(
            any("dialog[DigitalSignaturesDialog]:top-level GtkDialog" in e for e in errors), errors
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

    def test_router_module_path_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["router_module"] = "bin/other.py"
        errors = self.failures(registry=registry)
        self.assertIn("registry:router_module:unexpected path", errors)

    def test_expected_count_mismatch_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialogs"] = registry["dialogs"][:4]
        errors = self.failures(registry=registry)
        self.assertTrue(any("expected_dialogs is 5 but 4" in e for e in errors), errors)

    def test_duplicate_dialog_id_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["dialogs"].append(copy.deepcopy(registry["dialogs"][0]))
        registry["expected_dialogs"] = len(registry["dialogs"])
        errors = self.failures(registry=registry)
        self.assertTrue(any("duplicate dialog id" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
