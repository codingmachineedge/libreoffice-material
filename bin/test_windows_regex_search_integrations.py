#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for native regex-search field integrations."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-regex-search-integrations.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_regex_search_integrations", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class WindowsRegexSearchIntegrationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.coverage, self.contents = VALIDATOR.load_repository(REPOSITORY)
        self.entry = self.registry["integrations"][0]

    def failures(
        self,
        *,
        registry: dict | None = None,
        coverage: dict | None = None,
        contents: dict[str, str] | None = None,
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.coverage if coverage is None else coverage,
            self.contents if contents is None else contents,
        )

    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    def test_shipping_inventory_link_is_required(self) -> None:
        coverage = copy.deepcopy(self.coverage)
        for item in coverage["shipping_fields"]:
            if item["coverage_id"] == self.entry["coverage_id"]:
                item["widget_id"] = "different-entry"
                break
        self.assertTrue(
            any(
                error.endswith("registry locator or policy mismatch")
                for error in self.failures(coverage=coverage)
            )
        )

    def test_adjacent_builder_button_is_structural(self) -> None:
        contents = dict(self.contents)
        ui_file = self.entry["ui_file"]
        contents[ui_file] = contents[ui_file].replace(
            f'id="{self.entry["builder_button_id"]}"', 'id="removed-regex-builder"', 1
        )
        self.assertTrue(any(":ui-button:" in error for error in self.failures(contents=contents)))

    def test_accessible_name_description_and_tooltip_are_required(self) -> None:
        ui_file = self.entry["ui_file"]
        for marker, replacement, failure in (
            (
                '<property name="tooltip-text" translatable="yes" '
                'context="gotosheetdialog|entry-mask_regex_builder|tooltip_text">',
                '<property name="removed-tooltip" translatable="yes" '
                'context="gotosheetdialog|entry-mask_regex_builder|tooltip_text">',
                ":ui-accessibility:tooltip missing",
            ),
            (
                '<property name="AtkObject::accessible-name" translatable="yes" '
                'context="gotosheetdialog|entry-mask_regex_builder-atkobject">',
                '<property name="removed-accessible-name" translatable="yes" '
                'context="gotosheetdialog|entry-mask_regex_builder-atkobject">',
                ":ui-accessibility:AtkObject::accessible-name missing",
            ),
            (
                '<property name="AtkObject::accessible-description" translatable="yes" '
                'context="gotosheetdialog|extended_tip|entry-mask_regex_builder">',
                '<property name="removed-accessible-description" translatable="yes" '
                'context="gotosheetdialog|extended_tip|entry-mask_regex_builder">',
                ":ui-accessibility:AtkObject::accessible-description missing",
            ),
        ):
            with self.subTest(marker=marker):
                contents = dict(self.contents)
                contents[ui_file] = contents[ui_file].replace(marker, replacement, 1)
                self.assertTrue(
                    any(error.endswith(failure) for error in self.failures(contents=contents))
                )

        contents = dict(self.contents)
        contents[ui_file] = contents[ui_file].replace(
            '<property name="AtkObject::accessible-name" translatable="yes" '
            'context="gotosheetdialog|entry-mask_regex_builder-atkobject">',
            '<property name="AtkObject::accessible-name" translatable="no" '
            'context="gotosheetdialog|entry-mask_regex_builder-atkobject">',
            1,
        )
        self.assertTrue(
            any(
                error.endswith(
                    ":ui-accessibility:AtkObject::accessible-name must be translated"
                )
                for error in self.failures(contents=contents)
            )
        )

    def test_controller_must_own_the_existing_changed_handler(self) -> None:
        contents = dict(self.contents)
        source_file = self.entry["source_file"]
        contents[source_file] = contents[source_file].replace(
            f"LINK(this, {self.entry['owner_type']}, {self.entry['owner_changed_handler']})",
            "Link<weld::TextWidget&, void>()",
            1,
        )
        self.assertTrue(
            any(
                ":source-wiring:missing LINK(" in error
                for error in self.failures(contents=contents)
            )
        )

        contents = dict(self.contents)
        contents[source_file] += (
            f"\n// forbidden bypass\n{self.entry['entry_member']}->connect_changed("
            "Link<weld::TextWidget&, void>());\n"
        )
        self.assertTrue(
            any(
                error.endswith("direct changed handler bypasses controller")
                for error in self.failures(contents=contents)
            )
        )

    def test_literal_case_sensitive_compatibility_is_guarded(self) -> None:
        source_file = self.entry["source_file"]
        for marker in (
            "aState.Mode = sfx2::RegexSearchMode::Literal;",
            "aState.Flags.CaseInsensitive = false;",
        ):
            with self.subTest(marker=marker):
                contents = dict(self.contents)
                contents[source_file] = contents[source_file].replace(marker, "", 1)
                self.assertTrue(
                    any(
                        ":literal-default:missing" in error
                        for error in self.failures(contents=contents)
                    )
                )

    def test_compiled_matcher_and_search_options_are_exactly_once(self) -> None:
        source_file = self.entry["source_file"]
        for marker, failure in (
            ("std::make_unique<utl::TextSearch>", "handler-compiled-matcher"),
            (f"{self.entry['controller_member']}->GetSearchOptions()", "handler-search-options"),
            ("xSearch->searchForward", "handler-matching"),
        ):
            with self.subTest(marker=marker):
                contents = dict(self.contents)
                contents[source_file] = contents[source_file].replace(marker, "removed", 1)
                self.assertTrue(
                    any(failure in error for error in self.failures(contents=contents))
                )

    def test_matcher_compilation_cannot_move_inside_the_item_loop(self) -> None:
        contents = dict(self.contents)
        source_file = self.entry["source_file"]
        source = contents[source_file]
        build = (
            "    if (bValid && !bEmpty)\n"
            "        xSearch = std::make_unique<utl::TextSearch>("
            "m_xRegexSearchController->GetSearchOptions());\n\n"
        )
        self.assertIn(build, source)
        source = source.replace(build, "", 1)
        source = source.replace(
            "    for (const OUString& rSheetName : maCacheSheetsNames)\n    {\n",
            "    for (const OUString& rSheetName : maCacheSheetsNames)\n"
            "    {\n"
            "        if (bValid && !bEmpty)\n"
            "            xSearch = std::make_unique<utl::TextSearch>("
            "m_xRegexSearchController->GetSearchOptions());\n",
            1,
        )
        contents[source_file] = source
        self.assertTrue(
            any(
                ":compiled-once:matcher must be built before the loop" in error
                for error in self.failures(contents=contents)
            )
        )

    def test_invalid_regex_remains_fail_closed(self) -> None:
        source_file = self.entry["source_file"]
        for marker, replacement, failure in (
            (
                "sfx2::RegexSearchService::Validate(rState)",
                "removedValidation(rState)",
                ":handler-validation:expected exactly 1",
            ),
            (
                "bEmpty || (xSearch && xSearch->searchForward",
                "bEmpty || removedFailClosedRoute",
                ":handler:empty/invalid fail-closed route missing",
            ),
        ):
            with self.subTest(marker=marker):
                contents = dict(self.contents)
                contents[source_file] = contents[source_file].replace(marker, replacement, 1)
                self.assertTrue(
                    any(
                        error.endswith(failure)
                        for error in self.failures(contents=contents)
                    )
                )

    def test_legacy_substring_matching_cannot_return(self) -> None:
        contents = dict(self.contents)
        source_file = self.entry["source_file"]
        contents[source_file] = contents[source_file].replace(
            "    m_xLb->clear();",
            "    const sal_Int32 nLegacy = rState.Pattern.indexOf(rState.Pattern);\n"
            "    (void)nLegacy;\n    m_xLb->clear();",
            1,
        )
        self.assertTrue(
            any(
                error.endswith("legacy substring matcher remains")
                for error in self.failures(contents=contents)
            )
        )


if __name__ == "__main__":
    unittest.main()
