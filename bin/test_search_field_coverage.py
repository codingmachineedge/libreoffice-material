#!/usr/bin/env python3
"""Tests for check_search_field_coverage.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "bin" / "check_search_field_coverage.py"
REGISTRY_PATH = REPO_ROOT / "qa" / "windows-ui-contract" / "search-field-coverage.json"
EXPECTED_SHIPPING_CONTROLS = {
    ("basctl/uiconfig/basicide/ui/objectbrowser.ui", "FilterBox"),
    ("cui/uiconfig/ui/aboutconfigdialog.ui", "searchEntry"),
    ("cui/uiconfig/ui/accelconfigpage.ui", "searchEntry"),
    ("cui/uiconfig/ui/additionsdialog.ui", "entrySearch"),
    ("cui/uiconfig/ui/fmsearchdialog.ui", "cmbSearchText"),
    ("cui/uiconfig/ui/menuassignpage.ui", "searchEntry"),
    ("cui/uiconfig/ui/optionsdialog.ui", "searchEntry"),
    ("cui/uiconfig/ui/specialcharacters.ui", "search"),
    ("desktop/uiconfig/ui/extensionmanager.ui", "search"),
    ("formula/uiconfig/ui/functionpage.ui", "search"),
    ("sc/uiconfig/scalc/ui/filterdropdown.ui", "search_edit"),
    ("sc/uiconfig/scalc/ui/functionpanel.ui", "search"),
    ("sc/uiconfig/scalc/ui/gotosheetdialog.ui", "entry-mask"),
    ("sfx2/uiconfig/ui/commandpopup.ui", "command_entry"),
    ("sfx2/uiconfig/ui/helpindexpage.ui", "termentry"),
    ("sfx2/uiconfig/ui/helpsearchpage.ui", "search"),
    ("sfx2/uiconfig/ui/searchdialog.ui", "searchterm"),
    ("sfx2/uiconfig/ui/templatedlg.ui", "search_filter"),
    ("svx/uiconfig/ui/findbox.ui", "find"),
    ("svx/uiconfig/ui/findreplacedialog.ui", "searchterm"),
    ("svx/uiconfig/ui/redlinefilterpage.ui", "commentedit"),
    ("svx/uiconfig/ui/sidebargallery.ui", "search"),
    ("sw/uiconfig/swriter/ui/findentrydialog.ui", "entry"),
    ("sw/uiconfig/swriter/ui/fldrefpage.ui", "filter"),
    ("sw/uiconfig/swriter/ui/sidebarquickfind.ui", "searchterm"),
    ("xmlsecurity/uiconfig/ui/selectcertificatedialog.ui", "searchbox"),
}

SPEC = importlib.util.spec_from_file_location("check_search_field_coverage", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError(f"Cannot import {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def _shipping(ui_file: str, widget_id: str, coverage_id: str = "test.shipping") -> dict[str, str]:
    return {
        "coverage_id": coverage_id,
        "surface": "Fixture shipping search",
        "ui_file": ui_file,
        "widget_id": widget_id,
        "query_scope": "fixture values",
        "regex_builder": "adjacent-advanced-builder",
    }


def _planned(ui_file: str, widget_id: str, coverage_id: str = "test.planned") -> dict[str, str]:
    return {
        "coverage_id": coverage_id,
        "surface": "Fixture planned search",
        "ui_file": ui_file,
        "widget_id": widget_id,
        "query_scope": "fixture values",
        "regex_builder": "adjacent-advanced-builder",
        "source_state": "not-yet-present",
        "planned_layout": "Anchor the builder beside the field.",
    }


def _exclusion(ui_file: str, widget_id: str, coverage_id: str = "test.exclusion") -> dict[str, str]:
    return {
        "coverage_id": coverage_id,
        "ui_file": ui_file,
        "widget_id": widget_id,
        "category": "categorical-filter",
        "reason": "Fixture control selects one fixed category and is not a text query.",
    }


def _registry(
    *,
    shipping: list[dict[str, str]] | None = None,
    planned: list[dict[str, str]] | None = None,
    excluded: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    shipping = shipping or []
    planned = planned or []
    excluded = excluded or []
    return {
        "schema_version": 1,
        "contract": "windows-native-text-query-coverage",
        "platform": "windows",
        "audit_date": "2026-07-20",
        "expected_counts": {
            "shipping_fields": len(shipping),
            "planned_fields": len(planned),
            "excluded_candidates": len(excluded),
        },
        "scanner_contract": {
            "widget_classes": sorted(validator.TEXT_WIDGET_CLASSES),
            "identifier_terms": sorted(validator.IDENTIFIER_TERMS),
            "semantic_properties": sorted(validator.SEMANTIC_PROPERTIES),
            "find_icon": validator.FIND_ICON,
        },
        "shipping_fields": shipping,
        "planned_fields": planned,
        "excluded_candidates": excluded,
    }


def _write_ui(root: Path, relative: str, body: str) -> None:
    target = root.joinpath(*relative.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<interface>\n"
        f"{body}\n"
        "</interface>\n",
        encoding="utf-8",
    )


class SearchFieldCoverageTests(unittest.TestCase):
    def test_repository_registry_is_valid_and_complete(self) -> None:
        errors, stats = validator.validate_registry(REPO_ROOT, REGISTRY_PATH)
        self.assertEqual([], errors)
        self.assertEqual(26, stats.shipping_fields)
        self.assertEqual(1, stats.planned_fields)
        self.assertEqual(16, stats.excluded_candidates)
        self.assertEqual(38, stats.discovered_candidates)

    def test_duplicate_control_coverage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ui_file = "module/uiconfig/ui/search.ui"
            _write_ui(root, ui_file, '  <object class="GtkEntry" id="search"/>')
            registry = _registry(
                shipping=[_shipping(ui_file, "search")],
                excluded=[_exclusion(ui_file, "search")],
            )

            errors, _ = validator.validate_registry_data(root, registry)

        self.assertTrue(
            any("duplicate control coverage" in error for error in errors), errors
        )

    def test_missing_shipping_widget_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ui_file = "module/uiconfig/ui/search.ui"
            _write_ui(root, ui_file, '  <object class="GtkEntry" id="different"/>')
            registry = _registry(shipping=[_shipping(ui_file, "missingSearch")])

            errors, _ = validator.validate_registry_data(root, registry)

        self.assertTrue(any("widget id does not exist" in error for error in errors), errors)

    def test_unclassified_identifier_candidate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_ui(
                root,
                "module/uiconfig/ui/newdialog.ui",
                '  <object class="GtkEntry" id="futureSearch"/>',
            )

            errors, _ = validator.validate_registry_data(root, _registry())

        self.assertTrue(
            any("unclassified search-control candidate" in error for error in errors),
            errors,
        )

    def test_unclassified_placeholder_candidate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_ui(
                root,
                "module/uiconfig/ui/newdialog.ui",
                """  <object class="GtkEntry" id="entry">
    <property name="placeholder-text">Search everything</property>
  </object>""",
            )

            errors, _ = validator.validate_registry_data(root, _registry())

        self.assertTrue(
            any("unclassified search-control candidate" in error for error in errors),
            errors,
        )

    def test_explicit_exclusion_classifies_ambiguous_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ui_file = "module/uiconfig/ui/filter.ui"
            _write_ui(
                root,
                ui_file,
                '  <object class="GtkComboBoxText" id="filter_mode"/>',
            )
            registry = _registry(excluded=[_exclusion(ui_file, "filter_mode")])

            errors, stats = validator.validate_registry_data(root, registry)

        self.assertEqual([], errors)
        self.assertEqual(1, stats.discovered_candidates)

    def test_stale_exclusion_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ui_file = "module/uiconfig/ui/category.ui"
            _write_ui(
                root,
                ui_file,
                '  <object class="GtkComboBoxText" id="category"/>',
            )
            registry = _registry(excluded=[_exclusion(ui_file, "category")])

            errors, _ = validator.validate_registry_data(root, registry)

        self.assertTrue(
            any("no longer matches the scanner" in error for error in errors), errors
        )

    def test_planned_widget_must_be_reclassified_when_added(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ui_file = "sfx2/uiconfig/ui/startcenter.ui"
            _write_ui(
                root,
                ui_file,
                '  <object class="GtkEntry" id="start_search"/>',
            )
            registry = _registry(planned=[_planned(ui_file, "start_search")])

            errors, _ = validator.validate_registry_data(root, registry)

        self.assertTrue(
            any("planned widget now exists" in error for error in errors), errors
        )

    def test_json_registry_has_no_duplicate_path_id_pairs(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        controls = [
            (entry["ui_file"], entry["widget_id"])
            for group in validator.ENTRY_GROUPS
            for entry in registry[group]
        ]
        self.assertEqual(len(controls), len(set(controls)))

    def test_registry_locks_the_audited_shipping_set_and_start_center_plan(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        actual_shipping = {
            (entry["ui_file"], entry["widget_id"])
            for entry in registry["shipping_fields"]
        }
        actual_planned = {
            (entry["ui_file"], entry["widget_id"])
            for entry in registry["planned_fields"]
        }

        self.assertSetEqual(EXPECTED_SHIPPING_CONTROLS, actual_shipping)
        self.assertSetEqual(
            {("sfx2/uiconfig/ui/startcenter.ui", "start_search")}, actual_planned
        )


if __name__ == "__main__":
    unittest.main()
