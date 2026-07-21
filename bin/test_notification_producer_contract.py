#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the notification-producer validator.

Each test proves the contract rejects an unreal or mislabeled producer while the production
registry passes. The checker must NOT fail on the unrouted legacy-dialog backlog (it never scans
for it), only on the registered producers and the shared router seam.
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
VALIDATOR_PATH = REPOSITORY / "bin/check-notification-producer-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/notification-producer-policy.json"

SPEC = importlib.util.spec_from_file_location("check_notification_producer_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class NotificationProducerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        router = cls.registry["router"]
        cls.tracked_files = sorted(
            {router["header"], router["source"], cls.registry["approved_source_registry"]}
            | {producer["file"] for producer in cls.registry["producers"]}
        )
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

    # -- scaffolding ------------------------------------------------------------------------------
    def run_validate(
        self,
        *,
        files: dict[str, str] | None = None,
        registry: dict | None = None,
    ) -> None:
        files = files or {}
        registry_data = registry if registry is not None else self.registry
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in self.tracked_files:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(files.get(rel, self.originals[rel]), encoding="utf-8")
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
            VALIDATOR.validate(root, registry_path)

    def assert_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            self.run_validate(**kwargs)

    def mutated(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    def producer(self, pid: str) -> dict:
        return next(p for p in self.registry["producers"] if p["id"] == pid)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    def test_required_producers_are_all_registered(self) -> None:
        ids = {p["id"] for p in self.registry["producers"]}
        for pid in self.registry["required_producers"]:
            self.assertIn(pid, ids)

    # -- unreal call sites ------------------------------------------------------------------------
    def test_rejects_missing_router_call(self) -> None:
        confirmation = self.producer("srchdlg-replace-all-outcome")
        files = self.mutated(
            confirmation["file"],
            "sfx2::NotificationRouter::NotifyConfirmation(",
            "sfx2::NotificationRouter::NotifyDisabled(",
        )
        self.assert_fails("sfx2::NotificationRouter::NotifyConfirmation(", files=files)

    def test_rejects_commented_out_router_call(self) -> None:
        # A call that only survives inside a comment must not satisfy the contract.
        confirmation = self.producer("srchdlg-replace-all-outcome")
        files = self.mutated(
            confirmation["file"],
            'sfx2::NotificationRouter::NotifyConfirmation("libreoffice.core-ui"_ostr, rOutcome, !bNoMatch);',
            "// sfx2::NotificationRouter::NotifyConfirmation removed for this build",
        )
        self.assert_fails("sfx2::NotificationRouter::NotifyConfirmation(", files=files)

    def test_rejects_unreal_enclosing_function(self) -> None:
        registry = self.registry_copy()
        registry["producers"][0]["function"] = "SfxViewShell::NoSuchExecPrintFunction"
        self.assert_fails("SfxViewShell::NoSuchExecPrintFunction", registry=registry)

    def test_rejects_missing_source_literal(self) -> None:
        # Drop the audited source literal at the printer-busy call site.
        files = self.mutated(
            "sfx2/source/view/viewprn.cxx",
            '"libreoffice.core-ui"_ostr, sfx2::NotificationSeverity::Warning',
            "aRuntimeSource, sfx2::NotificationSeverity::Warning",
        )
        self.assert_fails('"libreoffice.core-ui"_ostr', files=files)

    # -- mislabeled severity / source -------------------------------------------------------------
    def test_rejects_notifyinfo_severity_mismatch(self) -> None:
        # Registry claims Information, but the printer-busy site spells Warning.
        registry = self.registry_copy()
        self.producer_in(registry, "viewprn-printer-busy")["severity"] = ["Information"]
        self.assert_fails("NotificationSeverity::Information", registry=registry)

    def test_rejects_confirmation_non_confirmation_severity(self) -> None:
        registry = self.registry_copy()
        self.producer_in(registry, "srchdlg-replace-all-outcome")["severity"] = ["Warning"]
        self.assert_fails("non-confirmation", registry=registry)

    def test_rejects_source_outside_allowlist(self) -> None:
        registry = self.registry_copy()
        self.producer_in(registry, "srchdlg-replace-all-outcome")["source"] = "evil.source"
        self.assert_fails("not in approved_display_sources", registry=registry)

    def test_rejects_allowlist_drift_from_compiled_source(self) -> None:
        registry = self.registry_copy()
        registry["approved_display_sources"] = ["libreoffice.core-ui"]
        self.assert_fails("drift from the compiled allowlist", registry=registry)

    def test_rejects_informational_only_cleared(self) -> None:
        registry = self.registry_copy()
        self.producer_in(registry, "srchdlg-replace-all-outcome")["informational_only"] = False
        self.assert_fails("informational_only=true", registry=registry)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_missing_required_producer(self) -> None:
        registry = self.registry_copy()
        registry["producers"] = [
            p for p in registry["producers"] if p["id"] != "viewprn-printer-busy"
        ]
        self.assert_fails("required_producers", registry=registry)

    def test_rejects_duplicate_producer_id(self) -> None:
        registry = self.registry_copy()
        registry["producers"][1]["id"] = registry["producers"][0]["id"]
        self.assert_fails("duplicate producer id", registry=registry)

    def test_rejects_unknown_router_call(self) -> None:
        registry = self.registry_copy()
        self.producer_in(registry, "newhelp-no-search-text")["router_call"] = "NotifyModal"
        self.assert_fails("unknown router_call", registry=registry)

    # -- shared router seam -----------------------------------------------------------------------
    def test_rejects_router_header_without_confirmation(self) -> None:
        files = self.mutated(
            self.registry["router"]["header"],
            "static void NotifyConfirmation(",
            "static void ConfirmationRemoved(",
        )
        self.assert_fails("router header", files=files)

    def test_rejects_router_source_confirmation_not_mapping_success(self) -> None:
        files = self.mutated(
            self.registry["router"]["source"],
            "NotificationSeverity::Success",
            "NotificationSeverity::Warning",
        )
        self.assert_fails("NotificationSeverity::Success", files=files)

    def test_rejects_classify_informational_branch_removed(self) -> None:
        files = self.mutated(
            self.registry["router"]["source"],
            "return NotificationRoute::Notification;",
            "return NotificationRoute::KeepModal;",
        )
        self.assert_fails("return NotificationRoute::Notification;", files=files)

    # helper ------------------------------------------------------------------------------------
    @staticmethod
    def producer_in(registry: dict, pid: str) -> dict:
        return next(p for p in registry["producers"] if p["id"] == pid)


if __name__ == "__main__":
    unittest.main()
