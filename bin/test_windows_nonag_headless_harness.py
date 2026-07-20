#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Windows no-nag headless harness contract."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-nonag-headless-harness.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_nonag_headless_harness", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class WindowsNoNagHeadlessHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contents, self.present = VALIDATOR.load_snapshot(REPOSITORY)

    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)

    def test_every_required_marker_has_a_working_mutation_guard(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for rule in VALIDATOR.REQUIRED_MARKERS:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] = mutated[rule.path].replace(rule.marker, "", 1)
                violations = VALIDATOR.find_violations(mutated, self.present)
                self.assertIn(rule.rule_id, {item["rule"] for item in violations})

    def test_dedicated_entrypoint_rejects_every_suppressive_argument(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for argument in VALIDATOR.SUPPRESSIVE_ARGUMENTS:
            with self.subTest(argument=argument):
                mutated = dict(self.contents)
                mutated[VALIDATOR.ENTRYPOINT] += f"\n# mutation {argument}\n"
                violations = VALIDATOR.find_violations(mutated, self.present)
                self.assertIn(
                    f"dedicated-suppressive-{argument[2:]}",
                    {item["rule"] for item in violations},
                )

    def test_no_nag_launch_block_rejects_every_suppressive_argument(self) -> None:
        baseline = VALIDATOR.find_violations(self.contents, self.present)
        self.assertEqual([], baseline)
        for argument in VALIDATOR.SUPPRESSIVE_ARGUMENTS:
            with self.subTest(argument=argument):
                mutated = dict(self.contents)
                mutated[VALIDATOR.ENGINE] = mutated[VALIDATOR.ENGINE].replace(
                    VALIDATOR.SEGMENT_START,
                    f"{VALIDATOR.SEGMENT_START}\n    '{argument}',",
                    1,
                )
                violations = VALIDATOR.find_violations(mutated, self.present)
                self.assertIn(
                    f"no-nag-suppressive-{argument[2:]}",
                    {item["rule"] for item in violations},
                )


if __name__ == "__main__":
    unittest.main()
