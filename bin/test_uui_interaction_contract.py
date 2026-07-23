#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the WIN-SYS-011 uui interaction validator.

The checker (bin/check-uui-interaction-contract.py) pins the modality of the ten
uui authentication / conflict / generic-error dialogs. Each test proves the
contract fails closed for one documented mutation while the production sources +
registry pass:

* three-way lock -- flipping a credential dialog's shared-CSV row to the
  notification form, or drifting its CSV reason, fails;
* credential precedence -- removing a credential dialog's ``visibility=False``
  password field, or mis-partitioning the credential set, fails;
* modal call sites -- removing (or commenting out) the informational-error
  predicate, an error-seam marker, a conflict ``->run()`` site, or the modal
  presentation fails;
* honesty -- promoting the routing carve-out to ``wired``, setting
  ``runtime_verified`` true, or changing the status fails; and
* completeness -- dropping a registered uui root, or registering a phantom root
  absent from the exhaustive CSV, fails.

All writes go to a tempfile tree; the checked-in sources and registry are read
only. The shared notification checker module is imported from the real
repository (it is not mutated).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPOSITORY / "bin/check-uui-interaction-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/uui-interaction-policy.json"

SPEC = importlib.util.spec_from_file_location("check_uui_interaction_contract", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {CHECKER_PATH}")
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class UuiInteractionContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        seam = cls.registry["error_seam"]
        cls.tracked_files = sorted(
            {cls.registry["notification_policy_csv"]}
            | {dialog["ui_path"] for dialog in cls.registry["dialogs"]}
            | {site["file"] for site in cls.registry["conflict_sites"]}
            | {seam["file"], seam["modal_presentation"]["file"]}
        )
        cls.originals = {rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files}

    # -- scaffolding ------------------------------------------------------------------------------
    def run_validate(self, *, files: dict[str, str] | None = None, registry: dict | None = None) -> None:
        files = files or {}
        registry_data = registry if registry is not None else self.registry
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in self.tracked_files:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(files.get(rel, self.originals[rel]), encoding="utf-8")
            registry_path = root / "uui-interaction-policy.json"
            registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
            CHECKER.validate(root, registry_path)

    def assert_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(CHECKER.ValidationError, re.escape(message)):
            self.run_validate(**kwargs)

    def mutated(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        CHECKER.validate(REPOSITORY, REGISTRY_PATH)

    def test_ten_dialogs_four_credential(self) -> None:
        self.assertEqual(len(self.registry["dialogs"]), 10)
        self.assertEqual(
            sorted(self.registry["credential_dialogs"]),
            ["LoginDialog", "MasterPasswordDialog", "PasswordDialog", "SetMasterPasswordDialog"],
        )

    # -- three-way registry <-> classifier <-> CSV lock -------------------------------------------
    def test_rejects_credential_dialog_routed_in_csv(self) -> None:
        # Flip LoginDialog's shared-CSV row from native-exclusion to the
        # bottom-right notification form (a well-formed but wrong policy).
        files = self.mutated(
            self.registry["notification_policy_csv"],
            'uui/uiconfig/ui/logindialog.ui,LoginDialog,GtkDialog,native-exclusion,,'
            '"collects credentials, kept modal (router Classify: KeepModal)"',
            "uui/uiconfig/ui/logindialog.ui,LoginDialog,GtkDialog,bottom-right-notification-form,default,",
        )
        self.assert_fails("CSV policy is 'bottom-right-notification-form', not native-exclusion", files=files)

    def test_rejects_csv_reason_drift(self) -> None:
        files = self.mutated(
            self.registry["notification_policy_csv"],
            'uui/uiconfig/ui/logindialog.ui,LoginDialog,GtkDialog,native-exclusion,,'
            '"collects credentials, kept modal (router Classify: KeepModal)"',
            'uui/uiconfig/ui/logindialog.ui,LoginDialog,GtkDialog,native-exclusion,,'
            '"some other reason, kept modal (router Classify: KeepModal)"',
        )
        self.assert_fails("disagrees with the classifier", files=files)

    # -- credential precedence ---------------------------------------------------------------------
    def test_rejects_missing_password_field_in_credential_dialog(self) -> None:
        # Make MasterPasswordDialog's sole password entry visible: the credential
        # dialog then carries no visibility=False password GtkEntry.
        files = self.mutated(
            "uui/uiconfig/ui/masterpassworddlg.ui",
            '<property name="visibility">False</property>',
            '<property name="visibility">True</property>',
        )
        self.assert_fails("has no visibility=False password GtkEntry", files=files)

    def test_rejects_non_password_dialog_marked_credential(self) -> None:
        registry = self.registry_copy()
        registry["credential_dialogs"].append("FilterSelectDialog")
        self.assert_fails("has no visibility=False password GtkEntry", registry=registry)

    def test_rejects_password_dialog_dropped_from_credential_set(self) -> None:
        registry = self.registry_copy()
        registry["credential_dialogs"].remove("PasswordDialog")
        self.assert_fails("carries a password GtkEntry", registry=registry)

    # -- reason-key drift --------------------------------------------------------------------------
    def test_rejects_reason_key_drift(self) -> None:
        registry = self.registry_copy()
        for dialog in registry["dialogs"]:
            if dialog["object_id"] == "AuthFallbackDlg":
                dialog["expected_reason_key"] = "credential"
        self.assert_fails("reason drifted", registry=registry)

    # -- modal conflict / error seam call sites ---------------------------------------------------
    def test_rejects_removed_error_seam_predicate(self) -> None:
        files = self.mutated(
            "uui/source/iahndl.cxx",
            "UUIInteractionHelper::isInformationalErrorMessageRequest(",
            "UUIInteractionHelper::isRemovedPredicate(",
        )
        self.assert_fails("UUIInteractionHelper::isInformationalErrorMessageRequest(", files=files)

    def test_rejects_commented_out_error_seam_predicate(self) -> None:
        files = self.mutated(
            "uui/source/iahndl.cxx",
            "UUIInteractionHelper::isInformationalErrorMessageRequest(",
            "// UUIInteractionHelper::isInformationalErrorMessageRequest(",
        )
        self.assert_fails("UUIInteractionHelper::isInformationalErrorMessageRequest(", files=files)

    def test_rejects_removed_seam_marker(self) -> None:
        files = self.mutated(
            "uui/source/iahndl.cxx",
            "rContinuations.getLength() != 1",
            "rContinuations.getLength() != 99",
        )
        self.assert_fails("rContinuations.getLength() != 1", files=files)

    def test_rejects_removed_conflict_run_site(self) -> None:
        files = self.mutated(
            "uui/source/nameclashdlg.cxx",
            "xErrorBox->run();",
            "(void)xErrorBox;",
        )
        self.assert_fails("xErrorBox->run();", files=files)

    def test_rejects_removed_modal_presentation(self) -> None:
        files = self.mutated(
            "uui/source/iahndl-errorhandler.cxx",
            "return static_cast<DialogMask>(xBox->run());",
            "return DialogMask::ButtonsOk;",
        )
        self.assert_fails("return static_cast<DialogMask>(xBox->run());", files=files)

    # -- honesty -----------------------------------------------------------------------------------
    def test_rejects_routing_carveout_promoted_to_wired(self) -> None:
        registry = self.registry_copy()
        registry["routing_carveout"]["status"] = "wired"
        self.assert_fails("seam-only-not-wired", registry=registry)

    def test_rejects_runtime_verified_true(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        self.assert_fails("runtime_verified must be false", registry=registry)

    def test_rejects_status_not_source_declared(self) -> None:
        registry = self.registry_copy()
        registry["status"] = "implemented"
        self.assert_fails("status must be 'source-declared'", registry=registry)

    # -- completeness against the exhaustive CSV ---------------------------------------------------
    def test_rejects_dropped_uui_dialog(self) -> None:
        registry = self.registry_copy()
        registry["dialogs"] = [d for d in registry["dialogs"] if d["object_id"] != "SimpleNameClashDialog"]
        self.assert_fails("present in the shared CSV but not registered here", registry=registry)

    def test_rejects_phantom_uui_dialog(self) -> None:
        registry = self.registry_copy()
        registry["dialogs"].append(
            {
                "ui_path": "uui/uiconfig/ui/logindialog.ui",
                "object_id": "PhantomDialog",
                "widget_class": "GtkDialog",
                "expected_policy": "native-exclusion",
                "expected_reason_key": "input",
            }
        )
        self.assert_fails("no matching shared-CSV root", registry=registry)


if __name__ == "__main__":
    unittest.main()
