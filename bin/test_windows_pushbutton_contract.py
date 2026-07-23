#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the push-button composition contract (WIN-ACT-001).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree and
asserts the checker fails closed, while the pristine production tree passes. The real repository
is never mutated: every mutation is applied to the ``contents`` map ``load_repository`` returns
or to a deep copy of the registry.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-pushbutton-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_pushbutton_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
NATIVE = "vcl/source/gdi/WidgetDefinition.cxx"
GALLERY = "qa/windows-ui-contract/component-gallery-coverage.json"
DESIGN = "docs/design/02-actions.md"


class PushButtonContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(self, *, registry: dict | None = None, contents: dict[str, str] | None = None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
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

    # -- compiled states (definition.xml) --------------------------------------
    def test_state_token_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<rect stroke="@primary-action-hover" fill="@primary-action-hover" stroke-width="@stroke-thin" radius="@corner-pill"/>',
            '<rect stroke="@primary-action-hover" fill="@surface" stroke-width="@stroke-thin" radius="@corner-pill"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("compiled:state:action-rollover" in e and "token drift" in e for e in errors), errors)

    def test_state_removed_fails(self) -> None:
        contents = self.replace_once(DEFINITION, '<state enabled="false" extra="flat"/>', "")
        errors = self.failures(contents=contents)
        self.assertTrue(any("compiled:states" in e and "was added or removed" in e for e in errors), errors)

    def test_flat_empty_state_gains_container_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="true" extra="flat"/>',
            '<state enabled="true" extra="flat"><rect stroke="@primary" fill="@primary" stroke-width="@stroke-none" radius="@corner-pill"/></state>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("compiled:state:flat-enabled" in e and "pinned empty" in e for e in errors), errors)

    def test_focus_ring_geometry_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["compiled"]["focus_part"]["lines"][0]["x1"] = "0.10"
        errors = self.failures(registry=registry)
        self.assertTrue(any("compiled:focus_part:line[0] x1" in e for e in errors), errors)

    def test_style_slot_d020_pairing_broken_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<defaultActionButtonTextColor value="@on-primary"/>',
            '<defaultActionButtonTextColor value="@primary"/>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("D-020 pairing broken" in e for e in errors), errors)

    def test_metric_drift_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION, '<radius name="corner-pill" value="20"/>', '<radius name="corner-pill" value="21"/>'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("compiled:metric:corner-pill" in e and "metric drift" in e for e in errors), errors)

    def test_palette_role_missing_fails(self) -> None:
        registry = self.registry_copy()
        registry["compiled"]["palette_roles"].append("no-such-role")
        errors = self.failures(registry=registry)
        self.assertTrue(any("compiled:palette:@no-such-role" in e for e in errors), errors)

    # -- gallery cardinality ---------------------------------------------------
    def test_gallery_cardinality_mismatch_fails(self) -> None:
        registry = self.registry_copy()
        registry["gallery_cardinality"]["entire_cells"] = 12
        errors = self.failures(registry=registry)
        self.assertTrue(any("gallery_cardinality:pushbutton/Entire cells" in e for e in errors), errors)

    # -- TEMPORARY negative guard ----------------------------------------------
    def test_outlined_xml_added_fails(self) -> None:
        contents = self.replace_once(
            DEFINITION,
            '<state enabled="false" extra="flat"/>',
            '<state enabled="false" extra="flat"/>\n            '
            '<state enabled="true" extra="outlined"><rect stroke="@outline" fill="@surface" stroke-width="@stroke-thin" radius="@corner-pill"/></state>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any('negative_guard:definition:extra="outlined"' in e for e in errors), errors)

    def test_native_signal_removed_fails(self) -> None:
        contents = self.replace_once(
            NATIVE, "if (rPushButtonValue.mbIsAction)", "if (rPushButtonValue.mbActionFlag)"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("negative_guard:native_branch" in e and "rPushButtonValue.mbIsAction" in e for e in errors),
            errors,
        )

    def test_native_outlined_token_added_fails(self) -> None:
        contents = self.replace_once(
            NATIVE,
            'else if (rPushButtonValue.m_bFlatButton)\n                    sExtra = "flat";',
            'else if (rPushButtonValue.m_bFlatButton)\n                    sExtra = "flat";\n'
            '                else\n                    sExtra = "outlined";',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("negative_guard:native_branch" in e and "outlined" in e for e in errors), errors)

    def test_pushbutton_case_missing_fails(self) -> None:
        contents = self.replace_once(NATIVE, "case ControlType::Pushbutton:", "case ControlType::PushbuttonX:")
        errors = self.failures(contents=contents)
        self.assertTrue(any("negative_guard:native_branch" in e and "not found" in e for e in errors), errors)

    # -- honest carve-outs -----------------------------------------------------
    def test_target_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["target"]["outlined"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("target:outlined:status must stay 'specified'" in e for e in errors), errors)

    def test_target_blocked_on_emptied_fails(self) -> None:
        registry = self.registry_copy()
        registry["target"]["default_emphasis"]["blocked_on"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("target:default_emphasis:blocked_on" in e for e in errors), errors)

    # -- design cross-tie ------------------------------------------------------
    def test_design_anchor_missing_fails(self) -> None:
        contents = self.replace_once(
            DESIGN, "The outlined variant has no native", "The outlined variant HAS a native"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("design_anchors:" in e and "missing from" in e for e in errors), errors)

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

    def test_definition_file_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["definition_file"] = "vcl/uiconfig/theme_definitions/other.xml"
        errors = self.failures(registry=registry)
        self.assertIn("registry:definition_file:unexpected path", errors)


if __name__ == "__main__":
    unittest.main()
