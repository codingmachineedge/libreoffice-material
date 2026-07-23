#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the migration & profile-compatibility contract (WIN-SYS-010).

Each mutation perturbs one guarantee against an in-memory copy of the tree and
asserts the checker fails closed; a positive control proves the pristine tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-material-migration-compat-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_material_migration_compat_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CSV = VALIDATOR.POLICY_CSV_PATH
MIGRATION = "desktop/source/migration/migration.cxx"
CHECK_EXT = "desktop/source/app/check_ext_deps.cxx"
APP = "desktop/source/app/app.cxx"
SETUP = "officecfg/registry/schema/org/openoffice/Setup.xcs"
PS1 = "bin/Run-Windows-Headless-Smoke.ps1"
MIGRATE_FN = "void Migration::migrateSettingsIfNecessary()"


class MigrationCompatContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(self, *, registry=None, contents=None) -> list[str]:
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

    def mutate(self, path: str, old: str, new: str, count: int = 1) -> dict[str, str]:
        text = self.contents[path]
        replaced = text.replace(old, new) if count < 0 else text.replace(old, new, count)
        self.assertNotEqual(text, replaced, f"mutation anchor not found in {path}: {old!r}")
        return self.with_content(path, replaced)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- silent-migration positive path -----------------------------------
    def test_migration_completed_guard_dropped_fails(self) -> None:
        contents = self.mutate(
            MIGRATION, 'u"MigrationCompleted"_ustr', 'u"MigrationDoneX"_ustr', count=-1
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any('"MigrationCompleted"' in e and "missing required marker" in e for e in errors),
            errors,
        )

    def test_disable_usermigration_escape_removed_fails(self) -> None:
        contents = self.mutate(
            MIGRATION, "SAL_DISABLE_USERMIGRATION", "SAL_ALLOW_USERMIGRATION"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("SAL_DISABLE_USERMIGRATION" in e and "missing required marker" in e for e in errors),
            errors,
        )

    def test_migrated4_stamp_removed_fails(self) -> None:
        contents = self.mutate(MIGRATION, "/MIGRATED4", "/MIGRATED5X")
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("/MIGRATED4" in e and "missing required marker" in e for e in errors), errors
        )

    # -- forbidden-nag blocklist (paired with the positive path) ----------
    def test_migration_nag_introduced_fails(self) -> None:
        contents = self.mutate(
            MIGRATION, MIGRATE_FN, MIGRATE_FN + "\nvoid nag_stub() { AppendInfoBar(); }\n"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("forbidden nag marker" in e and "AppendInfoBar" in e for e in errors), errors
        )

    def test_forbidden_token_in_comment_is_tolerated(self) -> None:
        # A forbidden token that survives only in a comment must NOT trip the blocklist:
        # proves the checker anchors on comment-stripped code.
        contents = self.mutate(
            MIGRATION, MIGRATE_FN, MIGRATE_FN + "\n// weld::MessageDialog only in a comment\n"
        )
        errors = self.failures(contents=contents)
        self.assertFalse(any("forbidden nag marker" in e for e in errors), errors)

    # -- retained compatibility decision + ordering -----------------------
    def test_compat_decision_removed_fails(self) -> None:
        contents = self.mutate(
            CHECK_EXT, "LastCompatibilityCheckID", "LastCompatibilityCheckXID", count=-1
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("missing compat marker" in e and "LastCompatibilityCheckID" in e for e in errors),
            errors,
        )

    def test_compat_gate_removed_from_app_fails(self) -> None:
        contents = self.mutate(
            APP, "bool bAbort = CheckExtensionDependencies();", "bool bAbort = false;"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("CheckExtensionDependencies();" in e and "compatibility gate" in e for e in errors),
            errors,
        )

    def test_ordering_swapped_fails(self) -> None:
        # Migration must not precede the compat check: swapping the pinned order in the
        # registry must fail against the real (correctly ordered) app.cxx.
        registry = copy.deepcopy(self.registry)
        ordering = registry["compat_decisions"]["ordering"]
        ordering["first"], ordering["then"] = ordering["then"], ordering["first"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("ordering drift" in e for e in errors), errors)

    def test_compat_policy_rerouted_fails(self) -> None:
        contents = self.mutate(
            CSV,
            "updaterequireddialog.ui,UpdateRequiredDialog,GtkDialog,native-exclusion",
            "updaterequireddialog.ui,UpdateRequiredDialog,GtkDialog,bottom-right-notification-form",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("was rerouted" in e for e in errors), errors)

    def test_compat_policy_row_removed_fails(self) -> None:
        text = self.contents[CSV]
        lines = [ln for ln in text.splitlines(keepends=True) if "MigrationWarnDialog" not in ln]
        contents = self.with_content(CSV, "".join(lines))
        self.assertNotEqual(text, contents[CSV])
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("MigrationWarnDialog" in e and "missing from" in e for e in errors), errors
        )

    # -- profile-compat config schema -------------------------------------
    def test_schema_prop_dropped_fails(self) -> None:
        contents = self.mutate(
            SETUP, '<prop oor:name="MigrationCompleted"', '<prop oor:name="MigrationCompletedX"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("missing schema prop" in e for e in errors), errors)

    # -- delegated legacy no-nag seed reference (WIN-SYS-008) -------------
    def test_legacy_seed_anchor_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["legacy_seed_reference"]["references"][0]["anchor"] = "no-such-anchor"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing anchor" in e for e in errors), errors)

    def test_legacy_seed_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(PS1))
        self.assertTrue(
            any("Run-Windows-Headless-Smoke.ps1" in e and "file missing" in e for e in errors),
            errors,
        )

    # -- registry integrity -----------------------------------------------
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

    def test_migration_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(MIGRATION))
        self.assertTrue(any("migration_invariants" in e and "file missing" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
