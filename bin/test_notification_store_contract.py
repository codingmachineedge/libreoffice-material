#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the notification-store source contract."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-notification-store-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_notification_store_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class NotificationStoreContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contents, self.present = VALIDATOR.load_snapshot(REPOSITORY)

    def violation_ids(
        self, contents: dict[str, str], present: set[str] | None = None
    ) -> set[str]:
        return {
            item["rule"]
            for item in VALIDATOR.find_violations(
                contents, self.present if present is None else present
            )
        }

    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)

    def test_every_required_marker_has_a_working_mutation_guard(self) -> None:
        self.assertEqual(set(), self.violation_ids(self.contents))
        for rule in VALIDATOR.REQUIRED_MARKERS:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] = mutated[rule.path].replace(rule.marker, "")
                self.assertIn(rule.rule_id, self.violation_ids(mutated))

    def test_every_forbidden_marker_has_a_working_mutation_guard(self) -> None:
        self.assertEqual(set(), self.violation_ids(self.contents))
        for rule in VALIDATOR.FORBIDDEN_MARKERS:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] += "\n" + rule.marker
                self.assertIn(rule.rule_id, self.violation_ids(mutated))

    def test_every_required_file_has_a_working_mutation_guard(self) -> None:
        self.assertEqual(set(), self.violation_ids(self.contents))
        for path in VALIDATOR.REQUIRED_FILES:
            with self.subTest(path=path):
                present = set(self.present)
                present.remove(path)
                self.assertIn("required-file", self.violation_ids(self.contents, present))

    def test_rejects_reordered_deterministic_json(self) -> None:
        path = "sfx2/source/notification/NotificationJson.cxx"
        mutated = dict(self.contents)
        first = 'aWriter.put("id", rRecord.Id);'
        second = 'aWriter.put("source", rRecord.Source);'
        self.assertIn(first, mutated[path])
        self.assertIn(second, mutated[path])
        mutated[path] = mutated[path].replace(first, "TEMP", 1)
        mutated[path] = mutated[path].replace(second, first, 1)
        mutated[path] = mutated[path].replace("TEMP", second, 1)
        self.assertIn("deterministic-json-order", self.violation_ids(mutated))

    def test_rejects_ref_install_before_compare_and_swap(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        compare = "if (readHead(rRepositoryURL) != rExpected)"
        install = "osl::File::replace(aLock, aRef)"
        self.assertIn(compare, mutated[path])
        self.assertIn(install, mutated[path])
        mutated[path] = mutated[path].replace(compare, "CAS_MARKER", 1)
        mutated[path] = mutated[path].replace(install, compare, 1)
        mutated[path] = mutated[path].replace("CAS_MARKER", install, 1)
        ids = self.violation_ids(mutated)
        self.assertIn("lock-cas-install-order", ids)

    def test_rejects_display_text_outside_safe_privacy_branch(self) -> None:
        path = "sfx2/source/notification/NotificationStore.cxx"
        mutated = dict(self.contents)
        safe_assignment = "        aRecord.Title = rDraft.Title;"
        self.assertIn(safe_assignment, mutated[path])
        mutated[path] += "\n    aRecord.Title = rDraft.Title;\n"
        self.assertIn("metadata-text-isolation", self.violation_ids(mutated))

    def test_rejects_store_lifetime_outside_worker_order(self) -> None:
        path = "sfx2/source/notification/NotificationCenterService.cxx"
        mutated = dict(self.contents)
        destroy = "        pStore.reset();"
        process = "            process(*pStore, std::move(aRequest));"
        self.assertIn(destroy, mutated[path])
        self.assertIn(process, mutated[path])
        mutated[path] = mutated[path].replace(destroy, "        LIFETIME_MARKER", 1)
        mutated[path] = mutated[path].replace(process, destroy, 1)
        mutated[path] = mutated[path].replace("        LIFETIME_MARKER", process, 1)
        self.assertIn("worker-store-lifetime-order", self.violation_ids(mutated))

    def test_rejects_looped_bulk_store_dispatch(self) -> None:
        path = "sfx2/source/notification/NotificationCenterService.cxx"
        mutated = dict(self.contents)
        call = "rStore.remove(aRequest.Ids)"
        self.assertEqual(1, mutated[path].count(call))
        mutated[path] = mutated[path].replace(call, call + ", " + call, 1)
        self.assertIn("one-store-call-per-bulk-request", self.violation_ids(mutated))

    def test_rejects_incomplete_generated_configuration_adapter(self) -> None:
        path = "sfx2/source/notification/NotificationConfiguration.cxx"
        mutated = dict(self.contents)
        accessor = (
            "officecfg::Office::UI::NotificationCenter::Display::Animations::get()"
        )
        self.assertIn(accessor, mutated[path])
        mutated[path] = mutated[path].replace(accessor, "false", 1)
        self.assertIn(
            "complete-generated-configuration-adapter", self.violation_ids(mutated)
        )

    def test_rejects_post_mutation_compaction(self) -> None:
        path = "sfx2/source/notification/NotificationStore.cxx"
        mutated = dict(self.contents)
        compact = "Repository->compactSnapshot("
        commit = "Repository->commitSnapshot("
        self.assertEqual(1, mutated[path].count(compact))
        self.assertEqual(1, mutated[path].count(commit))
        mutated[path] = mutated[path].replace(compact, "ORDER_MARKER", 1)
        mutated[path] = mutated[path].replace(commit, compact, 1)
        mutated[path] = mutated[path].replace("ORDER_MARKER", commit, 1)
        self.assertIn("pre-mutation-compaction-order", self.violation_ids(mutated))

    def test_rejects_clearing_compaction_gate_before_prune(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        block = VALIDATOR._extract_braced_block(
            mutated[path], "OString LocalGitRepository::compactSnapshot("
        )
        prune = "pruneUnreachableLooseObjects("
        complete = "osl::File::remove(aPending)"
        self.assertIn(prune, block)
        self.assertIn(complete, block)
        changed = block.replace(prune, "ORDER_MARKER", 1)
        changed = changed.replace(complete, prune, 1)
        changed = changed.replace("ORDER_MARKER", complete, 1)
        mutated[path] = mutated[path].replace(block, changed, 1)
        self.assertIn("fail-closed-compaction-order", self.violation_ids(mutated))

    def test_rejects_pending_checkpoint_retry_bypass(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        retry = "if (bPending"
        self.assertIn(retry, mutated[path])
        mutated[path] = mutated[path].replace(retry, "if (false", 1)
        self.assertIn("fail-closed-compaction-order", self.violation_ids(mutated))

    def test_rejects_pending_checkpoint_snapshot_mismatch_omission(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        comparison = "if (aBlobBody != rJson)"
        self.assertIn(comparison, mutated[path])
        mutated[path] = mutated[path].replace(comparison, "if (false)", 1)
        self.assertIn("pending-checkpoint-reuse-shape", self.violation_ids(mutated))

    def test_rejects_read_only_permanent_guard(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        block = VALIDATOR._extract_braced_block(
            mutated[path], "class RepositoryGuard final"
        )
        lock_flags = "osl_File_OpenFlag_Read | osl_File_OpenFlag_Write"
        self.assertIn(lock_flags, block)
        changed = block.replace(lock_flags, "osl_File_OpenFlag_Read", 1)
        mutated[path] = mutated[path].replace(block, changed, 1)
        self.assertIn("permanent-operation-guard-shape", self.violation_ids(mutated))

    def test_rejects_guard_initialization_outside_process_lock(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        guard = VALIDATOR._extract_braced_block(
            mutated[path], "class RepositoryGuard final"
        )
        constructor = VALIDATOR._extract_braced_block(
            mutated[path], "LocalGitRepository::LocalGitRepository("
        )
        initialization = (
            '        ensureControlFile(pathURL(rRepositoryURL, { u"notification.guard" }), '
            "GuardContents);\n"
        )
        self.assertIn(initialization, guard)
        changed_guard = guard.replace(initialization, "", 1)
        changed_constructor = constructor.replace(
            "{\n",
            '{\n    ensureControlFile(pathURL(m_aRepositoryURL, { u"notification.guard" }), GuardContents);\n',
            1,
        )
        mutated[path] = mutated[path].replace(guard, changed_guard, 1)
        mutated[path] = mutated[path].replace(constructor, changed_constructor, 1)
        ids = self.violation_ids(mutated)
        self.assertIn("permanent-operation-guard-shape", ids)
        self.assertIn("guard-initialization-outside-lock", ids)

    def test_rejects_full_snapshot_history_traversal(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        block = VALIDATOR._extract_braced_block(
            mutated[path], "std::vector<GitSnapshot> LocalGitRepository::readHistory("
        )
        metadata = "readCommitMetadataUnlocked("
        self.assertIn(metadata, block)
        changed = block.replace(metadata, "readSnapshotUnlocked(", 1)
        mutated[path] = mutated[path].replace(block, changed, 1)
        self.assertIn("metadata-only-history-depth", self.violation_ids(mutated))

    def test_rejects_reserving_object_before_declared_type(self) -> None:
        path = "sfx2/source/notification/LocalGitRepository.cxx"
        mutated = dict(self.contents)
        block = VALIDATOR._extract_braced_block(
            mutated[path], "std::string inflateObject("
        )
        parse_header = "aInflated.find('\\0')"
        reserve = "aInflated.reserve(nExpectedSize)"
        self.assertIn(parse_header, block)
        self.assertIn(reserve, block)
        changed = block.replace(parse_header, "ORDER_MARKER", 1)
        changed = changed.replace(reserve, parse_header, 1)
        changed = changed.replace("ORDER_MARKER", reserve, 1)
        mutated[path] = mutated[path].replace(block, changed, 1)
        self.assertIn("declared-type-inflate-order", self.violation_ids(mutated))


if __name__ == "__main__":
    unittest.main()
