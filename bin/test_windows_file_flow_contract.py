#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Windows file-flow contract (WIN-SYS-001).

Each test breaks exactly one guarantee against an in-memory copy of the tree and asserts the
checker fails closed, while the pristine production tree passes. The real repository is never
mutated: every mutation is applied to the ``contents`` map ``load_repository`` returns.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-file-flow-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_file_flow_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

WIN32 = "fpicker/source/win32/VistaFilePickerImpl.cxx"
HELPER = "sfx2/source/dialog/filedlghelper.cxx"
CSV = VALIDATOR.CSV_PATH


class WindowsFileFlowContractTest(unittest.TestCase):
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

    def replace_all(self, path: str, old: str, new: str) -> dict[str, str]:
        source = self.contents[path]
        self.assertGreaterEqual(source.count(old), 1, f"expected {old!r} in {path}")
        return self.with_content(path, source.replace(old, new))

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    def box(self, registry: dict, bid: str) -> dict:
        return next(b for b in registry["message_boxes"] if b["id"] == bid)

    # -- baseline --------------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- platform-delegation anchors (win32) -----------------------------------
    def test_overwrite_prompt_removed_fails(self) -> None:
        # FOS_OVERWRITEPROMPT appears for both open and save -- both must be gone to break it.
        contents = self.replace_all(
            WIN32, "FOS_FILEMUSTEXIST | FOS_OVERWRITEPROMPT", "FOS_FILEMUSTEXIST"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("platform_delegation" in e and "FOS_OVERWRITEPROMPT" in e for e in errors), errors)

    def test_open_dialog_clsid_renamed_fails(self) -> None:
        contents = self.replace_once(
            WIN32,
            "TDialogImpl<IFileOpenDialog, CLSID_FileOpenDialog>",
            "TDialogImpl<IFileOpenDialog, CLSID_FileOpenDialogX>",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("CLSID_FileOpenDialog" in e for e in errors), errors)

    def test_save_dialog_clsid_renamed_fails(self) -> None:
        contents = self.replace_once(
            WIN32,
            "TDialogImpl<IFileSaveDialog, CLSID_FileSaveDialog>",
            "TDialogImpl<IFileSaveDialog, CLSID_FileSaveDialogX>",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("CLSID_FileSaveDialog" in e for e in errors), errors)

    def test_customize_interface_renamed_fails(self) -> None:
        contents = self.replace_once(
            WIN32,
            "QueryInterface<IFileDialogCustomize>()",
            "QueryInterface<IFileDialogCustomizeX>()",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("IFileDialogCustomize" in e for e in errors), errors)

    def test_commented_out_delegation_anchor_fails(self) -> None:
        # An anchor surviving only inside a // comment must not satisfy the contract.
        contents = self.replace_all(
            WIN32,
            "impl_sta_InitDialog(rRequest, FOS_FILEMUSTEXIST | FOS_OVERWRITEPROMPT);",
            "// impl_sta_InitDialog(rRequest, FOS_FILEMUSTEXIST | FOS_OVERWRITEPROMPT);",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("FOS_OVERWRITEPROMPT" in e for e in errors), errors)

    def test_delegation_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(WIN32))
        self.assertTrue(any("platform_delegation:file missing" in e for e in errors), errors)

    # -- picker-selection seam -------------------------------------------------
    def test_office_file_picker_service_renamed_fails(self) -> None:
        contents = self.replace_once(
            HELPER,
            "com.sun.star.ui.dialogs.OfficeFilePicker",
            "com.sun.star.ui.dialogs.OfficeFilePickerX",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("picker_seam" in e and "OfficeFilePicker" in e for e in errors), errors)

    # -- call-site message boxes -----------------------------------------------
    def test_scripting_signature_resid_removed_fails(self) -> None:
        contents = self.replace_once(
            HELPER,
            "SfxResId(RID_SVXSTR_XMLSEC_QUERY_LOSINGSCRIPTINGSIGNATURE)",
            "SfxResId(RID_SVXSTR_XMLSEC_QUERY_REMOVED)",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("losing-scripting-signature" in e and "resid" in e for e in errors), errors
        )

    def test_gpg_failure_resid_removed_fails(self) -> None:
        contents = self.replace_once(
            HELPER,
            "SfxResId(RID_SVXSTR_GPG_ENCRYPT_FAILURE)",
            "SfxResId(RID_SVXSTR_GPG_ENCRYPT_REMOVED)",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("gpg-encrypt-failure" in e and "resid" in e for e in errors), errors)

    def test_password_length_resid_removed_fails(self) -> None:
        contents = self.replace_once(
            HELPER, "SfxResId(STR_PASSWORD_LEN)", "SfxResId(STR_PASSWORD_REMOVED)"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("password-length" in e and "resid" in e for e in errors), errors)

    def test_password_secondary_resid_removed_fails(self) -> None:
        contents = self.replace_once(
            HELPER, "SfxResId(STR_PASSWORD_WARNING)", "SfxResId(STR_PASSWORD_WARNING_REMOVED)"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("password-length" in e and "secondary_resid" in e for e in errors), errors
        )

    def test_commented_out_resid_fails(self) -> None:
        contents = self.replace_once(
            HELPER,
            "SfxResId(RID_SVXSTR_GPG_ENCRYPT_FAILURE)));",
            "/* SfxResId(RID_SVXSTR_GPG_ENCRYPT_FAILURE) */ nullptr));",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("gpg-encrypt-failure" in e and "resid" in e for e in errors), errors)

    def test_message_type_unbound_fails(self) -> None:
        # Change the scripting box's VclMessageType away from the pinned Question.
        contents = self.replace_once(
            HELPER,
            "VclMessageType::Question, VclButtonsType::YesNo",
            "VclMessageType::Information, VclButtonsType::YesNo",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("losing-scripting-signature" in e and "message_type" in e for e in errors), errors
        )

    def test_buttons_widened_not_accepted_as_prefix(self) -> None:
        # Ok -> OkCancel must NOT satisfy the whole-token binding for the GPG box.
        contents = self.replace_once(
            HELPER,
            "VclMessageType::Warning, VclButtonsType::Ok",
            "VclMessageType::Warning, VclButtonsType::OkCancel",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("gpg-encrypt-failure" in e and "buttons" in e for e in errors), errors)

    # -- honesty guards on the message boxes -----------------------------------
    def test_box_routed_to_notification_fails(self) -> None:
        registry = self.registry_copy()
        self.box(registry, "gpg-encrypt-failure")["routes_to_notification"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("gpg-encrypt-failure" in e and "routes_to_notification" in e for e in errors), errors
        )

    def test_box_non_modal_fails(self) -> None:
        registry = self.registry_copy()
        self.box(registry, "password-length")["modal"] = False
        errors = self.failures(registry=registry)
        self.assertTrue(any("password-length" in e and "modal" in e for e in errors), errors)

    def test_box_classification_outside_taxonomy_fails(self) -> None:
        registry = self.registry_copy()
        self.box(registry, "losing-scripting-signature")["classification"] = "marketing"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("losing-scripting-signature" in e and "classification" in e for e in errors), errors
        )

    def test_duplicate_message_box_id_fails(self) -> None:
        registry = self.registry_copy()
        registry["message_boxes"][1]["id"] = registry["message_boxes"][0]["id"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("duplicate id" in e for e in errors), errors)

    def test_empty_message_boxes_fails(self) -> None:
        registry = self.registry_copy()
        registry["message_boxes"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("message_boxes:non-empty array required" in e for e in errors), errors)

    # -- cross-reference into the shared CSV (read-only) -----------------------
    def test_cross_reference_policy_desync_fails(self) -> None:
        # A referenced .ui root that lost its native-exclusion policy fails closed.
        contents = self.replace_once(
            CSV,
            "sfx2/uiconfig/ui/querysavedialog.ui,QuerySaveDialog,GtkMessageDialog,native-exclusion",
            "sfx2/uiconfig/ui/querysavedialog.ui,QuerySaveDialog,GtkMessageDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("cross_references" in e and "QuerySaveDialog" in e and "policy is" in e for e in errors),
            errors,
        )

    def test_cross_reference_row_removed_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "fpicker/uiconfig/ui/remotefilesdialog.ui,RemoteFilesDialog,GtkDialog,native-exclusion,,"
            '"collects input, kept modal (router Classify: KeepModal)"\n',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("cross_references" in e and "RemoteFilesDialog" in e and "absent" in e for e in errors),
            errors,
        )

    def test_cross_reference_csv_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(CSV))
        self.assertTrue(any("cross_references:file missing" in e for e in errors), errors)

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

    def test_schema_version_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["schema_version"] = 2
        errors = self.failures(registry=registry)
        self.assertIn("registry:schema_version:must be 1", errors)

    def test_allowed_classifications_missing_canonical_fails(self) -> None:
        registry = self.registry_copy()
        registry["allowed_classifications"] = ["decision", "input", "acknowledgment"]
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("allowed_classifications:missing canonical" in e for e in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
