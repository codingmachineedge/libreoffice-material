#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Windows unsolicited-prompt contract."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-no-nag-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_no_nag_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class WindowsNoNagContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contents, self.present = VALIDATOR.load_snapshot(REPOSITORY)

    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)

    def test_every_forbidden_marker_has_a_working_mutation_guard(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for rule in VALIDATOR.FORBIDDEN_MARKERS:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] = mutated.get(rule.path, "") + "\n" + rule.marker
                violations = VALIDATOR.find_violations(mutated, self.present | {rule.path})
                self.assertIn(rule.rule_id, {item["rule"] for item in violations})

    def test_every_deleted_prompt_surface_has_a_working_mutation_guard(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for path in VALIDATOR.FORBIDDEN_FILES:
            with self.subTest(path=path):
                violations = VALIDATOR.find_violations(
                    self.contents, self.present | {path}
                )
                self.assertTrue(
                    any(
                        item["rule"] == "deleted-prompt-surface" and item["path"] == path
                        for item in violations
                    )
                )

    def test_every_required_safeguard_has_a_working_mutation_guard(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for rule in VALIDATOR.REQUIRED_MARKERS:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] = mutated[rule.path].replace(rule.marker, "")
                violations = VALIDATOR.find_violations(mutated, self.present)
                self.assertIn(rule.rule_id, {item["rule"] for item in violations})


if __name__ == "__main__":
    unittest.main()
