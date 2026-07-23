#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the version-history seeded-state ledger (WIN-CONCEPT-002).

Each mutation weakens one guarantee -- an extra or dangling seeded entry, a second
current version, stripped restore gating, a restore control wired to a destructive
dispatch, a malformed commit hash or word-delta, a falsely-backed concept affordance,
or a drifted ledger entry -- and asserts the checker fails closed. Regeneration is
idempotent. A green baseline proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-version-history-seeded-state.py"
SPEC = importlib.util.spec_from_file_location("check_version_history_seeded_state", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class VersionHistorySeededStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.proto = VALIDATOR.DEFAULT_PROTOTYPE.read_text(encoding="utf-8")
        self.versdlg = VALIDATOR.DEFAULT_VERSDLG.read_text(encoding="utf-8")
        self.registry = VALIDATOR.read_registry(VALIDATOR.DEFAULT_REGISTRY)

    def build(self, *, proto: str | None = None, versdlg: str | None = None) -> dict:
        return VALIDATOR.build_registry(
            self.proto if proto is None else proto,
            self.versdlg if versdlg is None else versdlg,
        )

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate(
            VALIDATOR.DEFAULT_PROTOTYPE, VALIDATOR.DEFAULT_VERSDLG, VALIDATOR.DEFAULT_REGISTRY
        )

    def test_checked_in_matches_fresh(self) -> None:
        VALIDATOR.compare_registry(self.build(), self.registry)

    def test_regenerate_idempotent(self) -> None:
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(
            VALIDATOR.serialize_registry(first), VALIDATOR.serialize_registry(second)
        )

    # -- fixture coherence -------------------------------------------------
    def test_thirteenth_entry_fails(self) -> None:
        proto = self.proto.replace(
            "var HISTORY=[\n",
            "var HISTORY=[\n {id:12,time:'x',group:'Today',action:'x',icon:'edit',"
            "hash:'abcdef0',author:'x',added:0,removed:0,file:'x.odt',docIx:0},\n",
            1,
        )
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    def test_dangling_docix_fails(self) -> None:
        proto = self.proto.replace("docIx:5,current:true", "docIx:99,current:true", 1)
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    def test_second_current_fails(self) -> None:
        proto = self.proto.replace("hash:'7b1d0c8'", "hash:'7b1d0c8',current:true", 1)
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    def test_malformed_hash_fails(self) -> None:
        proto = self.proto.replace("hash:'e9c4f2a'", "hash:'zzzzzzz'", 1)
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    def test_non_integer_word_delta_fails(self) -> None:
        proto = self.proto.replace("added:11", "added:'many'", 1)
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    # -- render gating -----------------------------------------------------
    def test_restore_gating_stripped_fails(self) -> None:
        proto = self.proto.replace("var restoreBtn = hdoc ?", "var restoreBtn = true ?", 1)
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    def test_restore_destructive_dispatch_fails(self) -> None:
        proto = self.proto.replace(
            'title="Restore this version"', 'title="Restore this version" data-act="restore"', 1
        )
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(proto=proto)

    # -- provenance --------------------------------------------------------
    def test_upstream_backing_removed_fails(self) -> None:
        versdlg = self.versdlg.replace("SID_DOCUMENT_COMPARE", "SID_SOMETHING_ELSE")
        with self.assertRaises(VALIDATOR.ValidationError):
            self.build(versdlg=versdlg)

    def test_falsely_backing_branch_fails(self) -> None:
        # Hand-edit the checked-in ledger to claim Branch has upstream backing; the
        # generated provenance never does, so the comparison fails closed.
        actual = copy.deepcopy(self.registry)
        actual["provenance"]["backed"].append(
            {"affordance": "branch", "upstream": "SID_FAKE", "source": VALIDATOR.VERSDLG_REL}
        )
        actual["provenance"]["concept_only"].remove("branch")
        with self.assertRaises(VALIDATOR.ValidationError):
            VALIDATOR.compare_registry(self.build(), actual)

    # -- ledger drift ------------------------------------------------------
    def test_entry_hand_edit_drift_fails(self) -> None:
        actual = copy.deepcopy(self.registry)
        actual["entries"][0]["author"] = "Someone Else"
        with self.assertRaises(VALIDATOR.ValidationError):
            VALIDATOR.compare_registry(self.build(), actual)

    def test_runtime_verified_flag_is_false(self) -> None:
        self.assertIs(self.build()["runtime_verified"], False)


if __name__ == "__main__":
    unittest.main()
