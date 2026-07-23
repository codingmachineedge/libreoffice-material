#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the icon-button composition contract (WIN-ACT-003).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree (or a
deep copy of the registry) and asserts the checker fails closed, while the pristine production tree
passes. The real repository is never mutated. The closed-world scan reads the real .ui tree, so its
failure modes are exercised through registry mutation (drop a consumer -> unclassified; add a
phantom classification -> stale).
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-icon-button-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_icon_button_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
INFOBAR_UI = "sfx2/uiconfig/ui/infobar.ui"
INFOBAR_CXX = "sfx2/source/dialog/infobar.cxx"
CARD_UI = "sfx2/uiconfig/ui/notificationcard.ui"
CARD_CXX = "sfx2/source/notification/NotificationCard.cxx"
MANAGER_UI = "sfx2/uiconfig/ui/notificationmanager.ui"
MANAGER_CXX = "sfx2/source/notification/NotificationManagerController.cxx"
PROPCHIP_UI = "sfx2/uiconfig/ui/propertychip.ui"


class IconButtonContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(self, *, registry: dict | None = None, contents: dict[str, str] | None = None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
            REPOSITORY,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def replace_once(self, path: str, old: str, new: str) -> dict[str, str]:
        source = self.contents[path]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {path}")
        return self.with_content(path, source.replace(old, new, 1))

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- baseline --------------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- icon-only / label -----------------------------------------------------
    def test_consumer_gains_label_fails(self) -> None:
        contents = self.replace_once(
            CARD_UI,
            '<object class="GtkButton" id="dismiss_button">',
            '<object class="GtkButton" id="dismiss_button">\n                <property name="label">Close</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("notificationcard-dismiss" in e and "gained a label" in e for e in errors), errors)

    # -- icon channel ----------------------------------------------------------
    def test_class_a_icon_drift_fails(self) -> None:
        contents = self.replace_once(
            INFOBAR_UI,
            '<property name="icon-name">window-close-symbolic</property>',
            '<property name="icon-name">edit-clear-symbolic</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("infobar-close" in e and "icon-name" in e for e in errors), errors)

    def test_class_b_image_icon_drift_fails(self) -> None:
        contents = self.replace_once(
            MANAGER_UI,
            '<property name="icon-name">window-close-symbolic</property>',
            '<property name="icon-name">edit-clear-symbolic</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("notificationmanager-close" in e and "close_image" in e for e in errors), errors)

    # -- accessible-name channel -----------------------------------------------
    def test_tooltip_removed_fails(self) -> None:
        contents = self.replace_once(
            PROPCHIP_UI,
            '<property name="tooltip-text" translatable="yes" context="propertychip|remove">Reset this property to inherit from parent style</property>',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("propertychip-remove" in e and "tooltip-text missing" in e for e in errors), errors)

    def test_tooltip_context_drift_fails(self) -> None:
        contents = self.replace_once(
            INFOBAR_UI, 'context="infobar|close|tooltip_text"', 'context="infobar|close|tooltip_textX"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("infobar-close" in e and "tooltip-text context" in e for e in errors), errors)

    def test_explicit_accessible_name_removed_fails(self) -> None:
        contents = self.replace_once(
            CARD_CXX, "m_xDismiss->set_accessible_name(", "m_xDismiss->set_accessible_nameGONE("
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("notificationcard-dismiss" in e and "set_accessible_name" in e for e in errors), errors
        )

    # -- Class-A toolbar hosting -----------------------------------------------
    def test_small_button_style_removed_fails(self) -> None:
        contents = self.replace_once(INFOBAR_UI, '<class name="small-button"/>', '<class name="plain-button"/>')
        errors = self.failures(contents=contents)
        self.assertTrue(any("infobar-close" in e and "small-button" in e for e in errors), errors)

    def test_class_a_weld_toolbar_to_button_fails(self) -> None:
        contents = self.replace_once(
            INFOBAR_CXX, 'weld_toolbar(u"closebar"_ustr)', 'weld_button(u"closebar"_ustr)'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("infobar-close" in e and "weld binding" in e for e in errors), errors)

    def test_class_b_weld_button_drift_fails(self) -> None:
        contents = self.replace_once(
            MANAGER_CXX, 'weld_button(u"close_button"_ustr)', 'weld_toolbar(u"close_button"_ustr)'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("notificationmanager-close" in e and "weld binding" in e for e in errors), errors)

    # -- shared native parts ---------------------------------------------------
    def test_pushbutton_extra_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="false" extra="flat"/>',
            '<state enabled="false" extra="flat"/>\n            '
            '<state enabled="true" extra="icon"><rect stroke="@outline" fill="@surface" stroke-width="@stroke-thin" radius="@corner-pill"/></state>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("shared_parts:pushbutton:extra values" in e for e in errors), errors)

    def test_toolbar_button_part_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["shared_parts"]["toolbar_button"]["part"] = "ButtonX"
        errors = self.failures(registry=registry)
        self.assertTrue(any("shared_parts:toolbar_button" in e and "missing" in e for e in errors), errors)

    # -- closed-world scan -----------------------------------------------------
    def test_unclassified_candidate_fails(self) -> None:
        registry = self.registry_copy()
        registry["consumers"] = [c for c in registry["consumers"] if c["id"] != "infobar-close"]
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("closed_world:unclassified" in e and "infobar.ui#close" in e for e in errors), errors
        )

    def test_stale_classification_fails(self) -> None:
        registry = self.registry_copy()
        registry["excluded_candidates"].append(
            {"ui_path": "sfx2/uiconfig/ui/ghost.ui", "object_id": "phantom", "category": "x", "reason": "y"}
        )
        errors = self.failures(registry=registry)
        self.assertTrue(any("closed_world:" in e and "no longer matches the scanner" in e for e in errors), errors)

    # -- registry integrity ----------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)


if __name__ == "__main__":
    unittest.main()
