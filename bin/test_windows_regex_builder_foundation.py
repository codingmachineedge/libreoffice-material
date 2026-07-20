#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the shared Windows regex-builder foundation."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-regex-builder-foundation.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_regex_builder_foundation", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class WindowsRegexBuilderFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contents = VALIDATOR.load_contents(REPOSITORY)

    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)

    def test_every_required_marker_is_guarded(self) -> None:
        self.assertEqual([], VALIDATOR.violations(self.contents))
        for rule in VALIDATOR.REQUIRED:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] = mutated[rule.path].replace(rule.marker, "")
                failures = VALIDATOR.violations(mutated)
                self.assertTrue(any(item.startswith(rule.rule_id + ":") for item in failures))

    def test_every_forbidden_marker_is_guarded(self) -> None:
        self.assertEqual([], VALIDATOR.violations(self.contents))
        for rule in VALIDATOR.FORBIDDEN:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[rule.path] += "\n" + rule.marker
                failures = VALIDATOR.violations(mutated)
                self.assertTrue(any(item.startswith(rule.rule_id + ":") for item in failures))

    def test_popover_root_and_advanced_sections_are_structural(self) -> None:
        mutated = dict(self.contents)
        mutated[VALIDATOR.UI_PATH] = mutated[VALIDATOR.UI_PATH].replace(
            'class="GtkPopover" id="RegexBuilderPopover"',
            'class="GtkBox" id="RegexBuilderPopover"',
            1,
        )
        self.assertTrue(
            any(item.startswith("popover-root:") for item in VALIDATOR.violations(mutated))
        )

    def test_cppunit_recipe_markers_are_mutation_guarded(self) -> None:
        recipe_path = "sfx2/CppunitTest_sfx2_regexsearch.mk"
        recipe_rules = [rule for rule in VALIDATOR.REQUIRED if rule.path == recipe_path]
        self.assertGreaterEqual(len(recipe_rules), 5)
        for rule in recipe_rules:
            with self.subTest(rule=rule.rule_id):
                mutated = dict(self.contents)
                mutated[recipe_path] = mutated[recipe_path].replace(rule.marker, "", 1)
                self.assertTrue(
                    any(
                        item.startswith(rule.rule_id + ":")
                        for item in VALIDATOR.violations(mutated)
                    )
                )

    def test_every_runtime_resource_definition_and_use_is_mutation_guarded(self) -> None:
        for resource in VALIDATOR.REQUIRED_REGEX_RESOURCES:
            with self.subTest(resource=resource, mutation="definition"):
                mutated = dict(self.contents)
                mutated[VALIDATOR.RESOURCE_PATH] = mutated[VALIDATOR.RESOURCE_PATH].replace(
                    f"#define {resource}", f"#define REMOVED_{resource}", 1
                )
                self.assertTrue(
                    any(
                        item.startswith("regex-resource-definition:") and resource in item
                        for item in VALIDATOR.violations(mutated)
                    )
                )

            with self.subTest(resource=resource, mutation="use"):
                mutated = dict(self.contents)
                mutated[VALIDATOR.SOURCE_PATH] = mutated[VALIDATOR.SOURCE_PATH].replace(
                    resource, f"REMOVED_{resource}"
                )
                self.assertTrue(
                    any(
                        item.startswith("regex-resource-use:") and resource in item
                        for item in VALIDATOR.violations(mutated)
                    )
                )

    def test_responsive_work_area_contract_is_structural(self) -> None:
        mutated = dict(self.contents)
        mutated[VALIDATOR.UI_PATH] = mutated[VALIDATOR.UI_PATH].replace(
            '<property name="constrain-to">window</property>',
            '<property name="constrain-to">none</property>',
            1,
        )
        self.assertTrue(
            any(item.startswith("popover-constrain:") for item in VALIDATOR.violations(mutated))
        )

        mutated = dict(self.contents)
        mutated[VALIDATOR.UI_PATH] = mutated[VALIDATOR.UI_PATH].replace(
            '<property name="border-width">12</property>',
            '<property name="width-request">820</property>\n'
            '        <property name="border-width">12</property>',
            1,
        )
        self.assertTrue(
            any(item.startswith("responsive-size:") for item in VALIDATOR.violations(mutated))
        )

    def test_entry_and_combobox_callback_routes_are_exactly_once(self) -> None:
        mutated = dict(self.contents)
        mutated[VALIDATOR.SOURCE_PATH] = mutated[VALIDATOR.SOURCE_PATH].replace(
            "NotifyOwnerChanged();\n    m_aChangedHdl.Call(*this);",
            "NotifyOwnerChanged();\n    m_aChangedHdl.Call(*this);\n    m_aChangedHdl.Call(*this);",
            1,
        )
        self.assertTrue(
            any(item.startswith("single-notify-route:") for item in VALIDATOR.violations(mutated))
        )

        for route_id, owner_call in (
            ("entry", "m_aOwnerEntryChangedHdl.Call(rEntry);"),
            ("combobox", "m_aOwnerComboChangedHdl.Call(rComboBox);"),
        ):
            with self.subTest(route=route_id):
                mutated = dict(self.contents)
                mutated[VALIDATOR.SOURCE_PATH] = mutated[VALIDATOR.SOURCE_PATH].replace(
                    owner_call, owner_call + "\n    " + owner_call, 1
                )
                self.assertTrue(
                    any(
                        item.startswith(f"single-notify-{route_id}:")
                        for item in VALIDATOR.violations(mutated)
                    )
                )

        mutated = dict(self.contents)
        mutated[VALIDATOR.SOURCE_PATH] = mutated[VALIDATOR.SOURCE_PATH].replace(
            "SetSearchText(m_aState.Pattern);\n    UpdateSearchValidity();\n    NotifyStateChanged();",
            "SetSearchText(m_aState.Pattern);\n    UpdateSearchValidity();\n    NotifyStateChanged();\n"
            "    NotifyStateChanged();",
            1,
        )
        self.assertTrue(
            any(item.startswith("single-notify-set-state:") for item in VALIDATOR.violations(mutated))
        )


if __name__ == "__main__":
    unittest.main()
