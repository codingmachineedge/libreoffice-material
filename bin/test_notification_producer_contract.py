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
            | {
                marker["file"]
                for producer in cls.registry["producers"]
                for marker in producer.get("wiring_markers", [])
            }
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

    def mutated_all(self, rel: str, old: str, new: str) -> dict[str, str]:
        # Some wiring anchors (the consumption call) appear at more than one site; a reachability
        # marker only fails once every occurrence is gone, so this replaces them all.
        source = self.originals[rel]
        self.assertGreaterEqual(source.count(old), 1, f"expected {old!r} in {rel}")
        return {rel: source.replace(old, new)}

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

    # -- reachability wiring markers --------------------------------------------------------------
    def test_srchdlg_producer_declares_wiring_markers(self) -> None:
        # Guards the reachability contract itself: the transient confirmation producer must keep its
        # wiring_markers so the arming/consumption/guard sites stay bound.
        producer = self.producer("srchdlg-replace-all-outcome")
        patterns = {marker["pattern"] for marker in producer.get("wiring_markers", [])}
        self.assertIn("g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());", patterns)
        self.assertIn("lcl_NotifyMaterialReplaceOutcome(sStr);", patterns)
        self.assertIn('std::getenv("VCL_FILE_WIDGET_THEME")', patterns)

    def test_rejects_missing_arming_wiring_marker(self) -> None:
        # Partial revert removing ONLY the Replace-All arming assignment. The producer function still
        # exists, so every existence check passes; only the wiring marker catches the dead code.
        files = self.mutated(
            "svx/source/dialog/srchdlg.cxx",
            "g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());",
            "g_bMaterialReplaceAllPending = false;",
        )
        self.assert_fails(
            "g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());", files=files
        )

    def test_rejects_missing_consumption_wiring_marker(self) -> None:
        # Remove every SetSearchLabel consumption call. The producer function definition survives
        # (so the existing function/router-call/source-literal checks still pass), leaving it dead.
        files = self.mutated_all(
            "svx/source/dialog/srchdlg.cxx",
            "lcl_NotifyMaterialReplaceOutcome(sStr);",
            "(void)sStr;",
        )
        self.assert_fails("lcl_NotifyMaterialReplaceOutcome(sStr);", files=files)

    def test_rejects_missing_guard_wiring_marker(self) -> None:
        files = self.mutated(
            "svx/source/dialog/srchdlg.cxx",
            'std::getenv("VCL_FILE_WIDGET_THEME")',
            'std::getenv("VCL_MATERIAL")',
        )
        self.assert_fails('std::getenv("VCL_FILE_WIDGET_THEME")', files=files)

    def test_rejects_commented_out_wiring_marker(self) -> None:
        # The arming site surviving only inside a comment must not satisfy the reachability marker.
        files = self.mutated(
            "svx/source/dialog/srchdlg.cxx",
            "g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());",
            "// g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());",
        )
        self.assert_fails(
            "g_bMaterialReplaceAllPending = (&rBtn == m_xReplaceAllBtn.get());", files=files
        )

    def test_rejects_tampered_wiring_pattern(self) -> None:
        # A wiring pattern that no longer matches real source (e.g. anchored to the wrong button)
        # fails closed rather than silently binding nothing.
        registry = self.registry_copy()
        markers = self.producer_in(registry, "srchdlg-replace-all-outcome")["wiring_markers"]
        markers[0]["pattern"] = "g_bMaterialReplaceAllPending = (&rBtn == m_xNoSuchButton.get());"
        self.assert_fails(
            "g_bMaterialReplaceAllPending = (&rBtn == m_xNoSuchButton.get());", registry=registry
        )

    def test_wiring_markers_absent_still_passes(self) -> None:
        # The field is optional: dropping it entirely from a producer keeps the contract valid, the
        # same way the Batch-A viewprn/newhelp producers carry none.
        registry = self.registry_copy()
        del self.producer_in(registry, "srchdlg-replace-all-outcome")["wiring_markers"]
        self.run_validate(registry=registry)

    def test_batch_a_producers_carry_no_wiring_markers(self) -> None:
        # The two Batch-A producers must keep passing without the optional field.
        for pid in ("viewprn-printer-busy", "newhelp-no-search-text"):
            self.assertNotIn("wiring_markers", self.producer(pid))

    def test_rejects_malformed_wiring_marker_missing_pattern(self) -> None:
        registry = self.registry_copy()
        markers = self.producer_in(registry, "srchdlg-replace-all-outcome")["wiring_markers"]
        del markers[0]["pattern"]
        self.assert_fails("has empty required field 'pattern'", registry=registry)

    def test_rejects_empty_wiring_markers_list(self) -> None:
        # Present-but-empty is malformed: an empty list would enforce nothing while looking wired.
        registry = self.registry_copy()
        self.producer_in(registry, "srchdlg-replace-all-outcome")["wiring_markers"] = []
        self.assert_fails("must be a non-empty array when present", registry=registry)

    # helper ------------------------------------------------------------------------------------
    @staticmethod
    def producer_in(registry: dict, pid: str) -> dict:
        return next(p for p in registry["producers"] if p["id"] == pid)


if __name__ == "__main__":
    unittest.main()
