#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the notebookbar .ui conformance contract.

A green baseline proves the production tree currently passes and that the
checked-in contract is byte-identical to a fresh derivation (regenerate is
idempotent). Each other test weakens exactly one guarantee -- via synthetic
``.ui`` snippets for the derive/classify/acceptance layer, and via mutated
copies of the real contract for the drift/header/regression layer -- and asserts
the checker rejects it. This is the fail-closed proof for the family markers:
stripped divider, reintroduced legacy padding, removed collapse machinery,
deleted or family-mismatched conformance marker, surface added/removed from the
owned set, status regression versus baseline, and header/runtime drift.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-notebookbar-ui-conformance.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/notebookbar-ui-conformance.json"

SPEC = importlib.util.spec_from_file_location(
    "check_windows_notebookbar_ui_conformance", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
V = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = V
SPEC.loader.exec_module(V)


def make_ui(inner: str, marker_family: str | None) -> str:
    marker = (
        f"  <!-- material-notebookbar-ui-conformance family={marker_family} wave=1 cluster=2 -->\n"
        if marker_family
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<interface domain="x">\n'
        '  <requires lib="LibreOffice" version="1.0"/>\n'
        f"{marker}"
        f"{inner}"
        "</interface>\n"
    )


# A group grid with grid spacing, a caption + a divider, plus collapse machinery.
TABBED_INNER = (
    '  <object class="sfxlo-PriorityHBox" id="tab">\n'
    '    <object class="GtkGrid" id="gdHomeFont">\n'
    '      <property name="row-spacing">3</property>\n'
    '      <property name="column-spacing">3</property>\n'
    '      <child><object class="sfxlo-NotebookbarToolBox" id="tb">\n'
    '        <property name="icon_size">3</property></object></child>\n'
    '      <child><object class="GtkSeparator"/></child>\n'
    "    </object>\n"
    "  </object>\n"
)

# A GtkBox spacing strip, a divider, no gd grid, no PriorityHBox.
GROUPS_INNER = (
    '  <object class="sfxlo-ContextVBox" id="ctx">\n'
    '    <object class="GtkBox" id="strip">\n'
    '      <property name="spacing">3</property>\n'
    '      <child><object class="GtkSeparator"/></child>\n'
    "    </object>\n"
    "  </object>\n"
)

# A legacy strip: separators with child-packing padding, priority machinery, no spacing.
LEGACY_INNER = (
    '  <object class="sfxlo-PriorityMergedHBox" id="pm">\n'
    '    <object class="sfxlo-PriorityHBox" id="ph">\n'
    '      <child><object class="GtkSeparator"/>\n'
    '        <packing><property name="padding">5</property></packing></child>\n'
    "    </object>\n"
    "  </object>\n"
)


class DeriveClassifyAcceptanceTest(unittest.TestCase):
    def derive(self, inner: str, marker_family: str | None):
        text = make_ui(inner, marker_family)
        markers = V.derive_markers(text, "synthetic.ui")
        family = V.classify_family(markers)
        status = V.acceptance_status(family, markers)
        return markers, family, status

    # -- tabbed ------------------------------------------------------------
    def test_tabbed_ok_is_rewritten(self) -> None:
        m, fam, status = self.derive(TABBED_INNER, "tabbed")
        self.assertEqual(fam, V.FAMILY_TABBED)
        self.assertEqual(status, V.STATUS_REWRITTEN)
        self.assertEqual(m["legacy_padding_count"], 0)
        self.assertEqual(m["group_grid_count"], 1)
        self.assertGreater(m["separator_count"], 0)

    def test_tabbed_with_legacy_padding_is_not_rewritten(self) -> None:
        inner = TABBED_INNER.replace(
            "<child><object class=\"GtkSeparator\"/></child>",
            '<child><object class="GtkSeparator"/>'
            '<packing><property name="padding">5</property></packing></child>',
        )
        m, fam, status = self.derive(inner, "tabbed")
        self.assertEqual(fam, V.FAMILY_TABBED)
        self.assertEqual(m["legacy_padding_count"], 1)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)

    def test_tabbed_marker_family_mismatch_is_not_rewritten(self) -> None:
        _, fam, status = self.derive(TABBED_INNER, "groups")
        self.assertEqual(fam, V.FAMILY_TABBED)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)

    def test_tabbed_missing_marker_is_not_rewritten(self) -> None:
        _, fam, status = self.derive(TABBED_INNER, None)
        self.assertEqual(fam, V.FAMILY_TABBED)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)

    def test_tabbed_without_divider_is_not_rewritten(self) -> None:
        inner = TABBED_INNER.replace('<child><object class="GtkSeparator"/></child>', "")
        m, fam, status = self.derive(inner, "tabbed")
        self.assertEqual(m["separator_count"], 0)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)

    # -- groups ------------------------------------------------------------
    def test_groups_ok_is_rewritten(self) -> None:
        m, fam, status = self.derive(GROUPS_INNER, "groups")
        self.assertEqual(fam, V.FAMILY_GROUPS)
        self.assertEqual(status, V.STATUS_REWRITTEN)
        self.assertEqual(m["box_spacing_decls"], 1)
        self.assertEqual(m["group_grid_count"], 0)

    def test_groups_with_padding_is_not_rewritten(self) -> None:
        inner = GROUPS_INNER.replace(
            '<child><object class="GtkSeparator"/></child>',
            '<child><object class="GtkSeparator"/>'
            '<packing><property name="padding">5</property></packing></child>',
        )
        _, fam, status = self.derive(inner, "groups")
        self.assertEqual(fam, V.FAMILY_GROUPS)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)

    # -- legacy ------------------------------------------------------------
    def test_legacy_is_in_progress(self) -> None:
        m, fam, status = self.derive(LEGACY_INNER, "grouped-compact-single")
        self.assertEqual(fam, V.FAMILY_LEGACY)
        self.assertEqual(status, V.STATUS_IN_PROGRESS)
        self.assertEqual(m["legacy_padding_count"], 1)
        self.assertIn("sfxlo-PriorityHBox", m["collapse_machinery"])

    def test_legacy_missing_marker_is_pending(self) -> None:
        _, fam, status = self.derive(LEGACY_INNER, None)
        self.assertEqual(fam, V.FAMILY_LEGACY)
        self.assertEqual(status, V.STATUS_PENDING)

    def test_legacy_without_machinery_is_pending(self) -> None:
        inner = (
            '  <object class="GtkBox" id="b">\n'
            '    <child><object class="GtkSeparator"/>\n'
            '      <packing><property name="padding">5</property></packing></child>\n'
            "  </object>\n"
        )
        _, fam, status = self.derive(inner, "grouped-compact-single")
        self.assertEqual(fam, V.FAMILY_LEGACY)
        self.assertEqual(status, V.STATUS_PENDING)

    def test_malformed_xml_raises(self) -> None:
        with self.assertRaises(V.ValidationError):
            V.derive_markers("<interface><object></interface>", "bad.ui")


class LiveBaselineTest(unittest.TestCase):
    def test_production_contract_passes(self) -> None:
        V.validate_contract(REPOSITORY, REGISTRY_PATH)

    def test_checked_in_matches_fresh_derivation(self) -> None:
        fresh = V.serialize_registry(V.build_registry(REPOSITORY))
        on_disk = REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertEqual(fresh, on_disk, "contract drifted from tree; run --regenerate")

    def test_coverage_counts(self) -> None:
        cov = V.build_registry(REPOSITORY)["coverage"]
        self.assertEqual(cov["total"], 21)
        self.assertEqual(cov["rewritten_material"], 7)
        self.assertEqual(cov["in_progress"], 14)
        self.assertEqual(cov["pending"], 0)
        self.assertEqual(cov["by_family"][V.FAMILY_TABBED]["total"], 4)
        self.assertEqual(cov["by_family"][V.FAMILY_TABBED][V.STATUS_REWRITTEN], 4)
        self.assertEqual(cov["by_family"][V.FAMILY_GROUPS]["total"], 3)
        self.assertEqual(cov["by_family"][V.FAMILY_LEGACY][V.STATUS_REWRITTEN], 0)

    def test_no_crlf_in_contract(self) -> None:
        self.assertNotIn("\r", REGISTRY_PATH.read_text(encoding="utf-8"))


class DriftAndHeaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.expected = V.build_registry(REPOSITORY)
        self.actual = copy.deepcopy(self.expected)

    def diff(self) -> list[str]:
        failures: list[str] = []
        V._diff_surfaces(self.expected.get("surfaces"), self.actual.get("surfaces"), failures)
        return failures

    def headers(self) -> list[str]:
        failures: list[str] = []
        V._header_failures(self.expected, self.actual, failures)
        return failures

    def test_baseline_clean(self) -> None:
        self.assertEqual([], self.diff())
        self.assertEqual([], self.headers())

    def test_missing_surface_fails(self) -> None:
        self.actual["surfaces"] = self.actual["surfaces"][1:]
        self.assertTrue(any("missing from contract" in e for e in self.diff()))

    def test_stale_surface_fails(self) -> None:
        ghost = copy.deepcopy(self.actual["surfaces"][0])
        ghost["surface"] = "sw/uiconfig/swriter/ui/notebookbar_ghost.ui"
        self.actual["surfaces"].append(ghost)
        self.assertTrue(any("no matching owned file" in e for e in self.diff()))

    def test_marker_drift_fails(self) -> None:
        self.actual["surfaces"][0]["markers"]["separator_count"] += 1
        self.assertTrue(any("drifted from its derived structure" in e for e in self.diff()))

    def test_runtime_verified_true_fails(self) -> None:
        self.actual["runtime_verified"] = True
        self.assertTrue(any("runtime_verified" in e for e in self.headers()))

    def test_contract_field_drift_fails(self) -> None:
        self.actual["contract"] = "something-else"
        self.assertTrue(any("field 'contract' drifted" in e for e in self.headers()))

    def test_coverage_drift_fails(self) -> None:
        self.actual["coverage"]["rewritten_material"] = 99
        self.assertTrue(any("field 'coverage' drifted" in e for e in self.headers()))


class AcceptanceAndRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.expected = V.build_registry(REPOSITORY)

    def acceptance(self, expected) -> list[str]:
        failures: list[str] = []
        V._acceptance_failures(expected, failures)
        return failures

    def test_acceptance_baseline_clean(self) -> None:
        self.assertEqual([], self.acceptance(self.expected))

    def test_acceptance_missing_marker_fails(self) -> None:
        exp = copy.deepcopy(self.expected)
        exp["surfaces"][0]["markers"]["conformance_marker"] = False
        self.assertTrue(any("conformance marker comment missing" in e for e in self.acceptance(exp)))

    def test_acceptance_rewritten_with_padding_fails(self) -> None:
        exp = copy.deepcopy(self.expected)
        row = next(s for s in exp["surfaces"] if s["rewrite_status"] == V.STATUS_REWRITTEN)
        row["markers"]["legacy_padding_count"] = 3
        self.assertTrue(any("legacy child-packing padding" in e for e in self.acceptance(exp)))

    def test_acceptance_marker_family_mismatch_fails(self) -> None:
        exp = copy.deepcopy(self.expected)
        exp["surfaces"][0]["markers"]["marker_family"] = "wrong"
        self.assertTrue(any("marker family" in e for e in self.acceptance(exp)))

    def test_regression_status_downgrade_fails(self) -> None:
        baseline = copy.deepcopy(self.expected)
        # In the "now" tree, drop one rewritten surface to in-progress.
        now = copy.deepcopy(self.expected)
        row = next(s for s in now["surfaces"] if s["rewrite_status"] == V.STATUS_REWRITTEN)
        row["rewrite_status"] = V.STATUS_IN_PROGRESS
        failures: list[str] = []
        V._regression_failures(baseline, now, failures)
        self.assertTrue(any("regressed" in e for e in failures))

    def test_regression_marker_removed_fails(self) -> None:
        baseline = copy.deepcopy(self.expected)
        now = copy.deepcopy(self.expected)
        now["surfaces"][0]["markers"]["conformance_marker"] = False
        failures: list[str] = []
        V._regression_failures(baseline, now, failures)
        self.assertTrue(any("marker was removed" in e for e in failures))

    def test_regression_no_baseline_is_clean(self) -> None:
        failures: list[str] = []
        V._regression_failures(None, self.expected, failures)
        self.assertEqual([], failures)


class MalformedContractTest(unittest.TestCase):
    def test_duplicate_surface_rejected(self) -> None:
        row = {"surface": "a"}
        with self.assertRaises(V.ValidationError):
            V._surface_index([row, {"surface": "a"}])

    def test_non_list_rejected(self) -> None:
        with self.assertRaises(V.ValidationError):
            V._surface_index({"surface": "a"})


if __name__ == "__main__":
    unittest.main()
