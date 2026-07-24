#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material density model contract (WIN-FND-005).

Each mutation weakens one guarantee -- a drifted native metric, a smuggled density
attribute on the metrics section, a target-table row that no longer matches the doc or
is no longer tagged 'specified', lost design honesty language, a calc-chrome carve-out
that drifted from the master table, the stored density selector disappearing from the
tree, or a drifted selectable-stage marker -- and asserts the checker fails closed. A
green baseline proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-density-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_density_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CHAPTER = VALIDATOR.CHAPTER_PATH
DESIGN = VALIDATOR.MATERIAL_DESIGN_PATH
CALC = VALIDATOR.CALC_CHROME_PATH
READER_TEST = VALIDATOR.READER_TEST_PATH


class DensityContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
            REPOSITORY,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- native metrics ----------------------------------------------------
    def test_native_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<metric name="size-standard-control" value="36"/>',
            '<metric name="size-standard-control" value="99"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("native_metrics:size-standard-control" in e and "metric drift" in e for e in errors),
            errors,
        )

    def test_metrics_section_attribute_injected_fails(self) -> None:
        definition = self.contents[DEFINITION].replace("<metrics>", '<metrics scale="2">', 1)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("<metrics> must carry zero attributes" in e for e in errors), errors
        )

    def test_ledger_dropping_a_metric_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["native_metrics"]["height-tab"]
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("native_metrics:height-tab present in definition.xml but not ledgered" in e
                for e in errors),
            errors,
        )

    # -- target table ------------------------------------------------------
    def test_target_table_doc_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["target_table"][0]["compact"] = "99px"
        errors = self.failures(registry=registry)
        self.assertTrue(any("target_table:--ctrl:doc drift" in e for e in errors), errors)

    def test_target_table_status_not_specified_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["target_table"][0]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("target_table:--ctrl:status must be 'specified'" in e for e in errors), errors
        )

    def test_target_table_doc_row_removed_fails(self) -> None:
        chapter = self.contents[CHAPTER].replace(
            "| `--fs` | `13px` | `14px` | Base font size |", "", 1
        )
        errors = self.failures(contents=self.with_content(CHAPTER, chapter))
        self.assertTrue(any("target_table:--fs:no matching row" in e for e in errors), errors)

    # -- design honesty ----------------------------------------------------
    def test_design_honesty_marker_missing_fails(self) -> None:
        design = self.contents[DESIGN].replace("## Desktop density", "## Desktop layout", 1)
        errors = self.failures(contents=self.with_content(DESIGN, design))
        self.assertTrue(any("design_honesty:marker missing" in e for e in errors), errors)

    # -- calc-chrome carve-out consistency --------------------------------
    def test_carveout_drift_fails(self) -> None:
        calc = json.loads(self.contents[CALC])
        calc["density"]["metrics"][0]["compact"] = "99"
        errors = self.failures(contents=self.with_content(CALC, json.dumps(calc)))
        self.assertTrue(any("carveout:--tb:compact" in e and "drifted" in e for e in errors), errors)

    def test_carveout_status_promoted_fails(self) -> None:
        calc = json.loads(self.contents[CALC])
        calc["density"]["status"] = "implemented"
        errors = self.failures(contents=self.with_content(CALC, json.dumps(calc)))
        self.assertTrue(
            any("carveout:calc-chrome density status must stay 'specified'" in e for e in errors),
            errors,
        )

    # -- reader-test corroboration ----------------------------------------
    def test_reader_test_fixture_dropped_fails(self) -> None:
        source = self.contents[READER_TEST].replace(
            "definitionMetricsSectionAttribute.xml", "definitionRenamedFixture.xml", 1
        )
        errors = self.failures(contents=self.with_content(READER_TEST, source))
        self.assertTrue(any("reader_test:" in e for e in errors), errors)

    # -- selector-presence guard (git-grep is monkeypatched) --------------
    def test_selector_missing_fails(self) -> None:
        # git grep returns 1 (found nothing): the stored density selector regressed.
        original = VALIDATOR._git_grep
        try:
            VALIDATOR._git_grep = (  # type: ignore[assignment]
                lambda repo, pattern, globs: (1, [], "")
            )
            errors: list[str] = []
            VALIDATOR._validate_selector_presence(self.registry, REPOSITORY, errors)
        finally:
            VALIDATOR._git_grep = original  # type: ignore[assignment]
        self.assertTrue(
            any("selector_presence:" in e and "is missing" in e for e in errors), errors
        )

    def test_selector_wrong_file_fails(self) -> None:
        # git grep finds a match, but not in the expected file.
        original = VALIDATOR._git_grep
        try:
            VALIDATOR._git_grep = (  # type: ignore[assignment]
                lambda repo, pattern, globs: (0, ["sc/uiconfig/scalc/ui/other.ui"], "")
            )
            errors: list[str] = []
            VALIDATOR._validate_selector_presence(self.registry, REPOSITORY, errors)
        finally:
            VALIDATOR._git_grep = original  # type: ignore[assignment]
        self.assertTrue(
            any("selector_presence:" in e and "among the matches" in e for e in errors), errors
        )

    def test_selector_git_unavailable_fails_closed(self) -> None:
        original = VALIDATOR._git_grep
        try:
            VALIDATOR._git_grep = (  # type: ignore[assignment]
                lambda repo, pattern, globs: (-1, [], "git not found")
            )
            errors: list[str] = []
            VALIDATOR._validate_selector_presence(self.registry, REPOSITORY, errors)
        finally:
            VALIDATOR._git_grep = original  # type: ignore[assignment]
        self.assertTrue(
            any("selector_presence:could not run git grep" in e for e in errors), errors
        )

    def test_selectable_stage_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["selectable_stage"] = "live"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:selectable_stage:" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:contract:" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
