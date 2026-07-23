#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material dialog-anatomy validator."""

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
VALIDATOR_PATH = REPOSITORY / "bin/check-material-dialog-anatomy.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/dialog-anatomy-policy.json"

SPEC = importlib.util.spec_from_file_location("check_material_dialog_anatomy", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class MaterialDialogAnatomyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        helper = cls.registry["helper"]
        cls.tracked_files = sorted(
            {helper["ui_file"], helper["source"]}
            | {migration["file"] for migration in cls.registry["migrations"]}
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

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    def test_migration_count_is_within_the_declared_wave(self) -> None:
        self.assertGreaterEqual(len(self.registry["migrations"]), VALIDATOR.MIN_MIGRATIONS)
        self.assertLessEqual(len(self.registry["migrations"]), VALIDATOR.MAX_MIGRATIONS)

    # -- helper .ui composition -------------------------------------------------------------------
    def test_rejects_missing_destructive_role_class(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["ui_file"],
            '<style>\n                  <class name="destructive-action"/>\n                </style>\n',
            "",
        )
        self.assert_fails("destructive-action", files=files)

    def test_rejects_non_verb_destructive_label(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["ui_file"],
            'context="materialdestructiveconfirmdialog|destructive">_Delete',
            'context="materialdestructiveconfirmdialog|destructive">_OK',
        )
        self.assert_fails("must name a verb", files=files)

    def test_rejects_reordered_footer(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["ui_file"],
            '<action-widget response="-6">safe</action-widget>\n'
            '      <action-widget response="-5">destructive</action-widget>',
            '<action-widget response="-5">destructive</action-widget>\n'
            '      <action-widget response="-6">safe</action-widget>',
        )
        self.assert_fails("footer order", files=files)

    def test_rejects_wrong_safe_response_role(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["ui_file"],
            '<action-widget response="-6">safe</action-widget>',
            '<action-widget response="-5">safe</action-widget>',
        )
        self.assert_fails("action-widget 'safe'", files=files)

    def test_rejects_non_warning_message_type(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["ui_file"],
            '<property name="message-type">warning</property>',
            '<property name="message-type">info</property>',
        )
        self.assert_fails("message-type", files=files)

    # -- helper source behavior -------------------------------------------------------------------
    def test_rejects_destructive_enter_default(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["source"],
            "set_default_response(RET_CANCEL)",
            "set_default_response(RET_OK)",
        )
        self.assert_fails("NOT bind the Enter default to the destructive action", files=files)

    def test_rejects_missing_safe_default(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["source"],
            "xDialog->set_default_response(RET_CANCEL);",
            "",
        )
        self.assert_fails("bind the Enter default to the safe action", files=files)

    def test_rejects_focus_on_destructive(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["source"],
            "xSafe->grab_focus();",
            "xDestructive->grab_focus();",
        )
        self.assert_fails("initial focus on the safe action", files=files)

    def test_rejects_missing_secondary_text(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["source"],
            "xDialog->set_secondary_text(rParams.sSecondaryText);",
            "",
        )
        self.assert_fails("consequence (secondary) text", files=files)

    def test_rejects_missing_ret_ok_return(self) -> None:
        helper = self.registry["helper"]
        files = self.mutated(
            helper["source"],
            "return xDialog->run() == RET_OK;",
            "return xDialog->run() == RET_YES;",
        )
        self.assert_fails("returns destructive iff RET_OK", files=files)

    # -- migrated call sites ----------------------------------------------------------------------
    def test_rejects_call_site_without_helper_call(self) -> None:
        # sw glosbib has exactly one migration; drop its dispatch.
        target = "sw/source/ui/misc/glosbib.cxx"
        source = self.originals[target]
        self.assertIn("sfx2::ConfirmDestructiveAction(", source)
        mutated = source.replace("sfx2::ConfirmDestructiveAction(", "sfx2::LegacyBox(", 1)
        self.assert_fails("must dispatch", files={target: mutated})

    def test_rejects_call_site_without_header_include(self) -> None:
        target = "sd/source/ui/view/drviews4.cxx"
        files = self.mutated(
            target,
            "#include <sfx2/destructiveconfirmation.hxx>\n",
            "",
        )
        self.assert_fails("must include the helper header", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_too_few_migrations(self) -> None:
        registry = self.registry_copy()
        registry["migrations"] = registry["migrations"][:2]
        self.assert_fails("between 3 and 10 migrations", registry=registry)

    def test_rejects_equal_safe_and_destructive_responses(self) -> None:
        registry = self.registry_copy()
        registry["helper"]["safe_response"] = registry["helper"]["destructive_response"]
        self.assert_fails("responses must differ", registry=registry)

    def test_rejects_duplicate_migration_id(self) -> None:
        registry = self.registry_copy()
        registry["migrations"][1]["id"] = registry["migrations"][0]["id"]
        self.assert_fails("duplicate migration id", registry=registry)


if __name__ == "__main__":
    unittest.main()
