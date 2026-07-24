#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material appearance-options contract (Cluster E).

Each mutation weakens one guarantee -- a drifted schema type/default, a missing
enumeration, a widget id removed from the materialtheme frame, a lost weld binding, a
dropped FillItemSet commit, a missing header member, a broken restart apply path, a
Stage-3 live-apply symbol smuggled into the cui page, or a schema/ui/scheme-string
drift -- and asserts the checker fails closed. A green baseline proves the production
tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-material-appearance-options.py"
SPEC = importlib.util.spec_from_file_location("check_material_appearance_options", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class AppearanceOptionsContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)
        self.SCHEMA = self.registry["schema_source"]
        self.UI = self.registry["ui_source"]
        self.CONTROLLER = self.registry["controller_source"]
        self.HEADER = self.registry["controller_header"]

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- schema ------------------------------------------------------------
    def test_schema_type_drift_fails(self) -> None:
        source = self.contents[self.SCHEMA].replace(
            '<prop oor:name="MaterialAccent" oor:type="xs:short"',
            '<prop oor:name="MaterialAccent" oor:type="xs:int"',
            1,
        )
        errors = self.failures(contents=self.with_content(self.SCHEMA, source))
        self.assertTrue(
            any("properties:MaterialAccent:schema is not oor:type" in e for e in errors), errors
        )

    def test_schema_default_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["properties"][0]["default"] = "9"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("properties:MaterialAccent:schema default drifted" in e for e in errors), errors
        )

    def test_schema_enum_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["properties"][0]["enum_values"].append("9")
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("properties:MaterialAccent:schema enumeration '9' missing" in e for e in errors),
            errors,
        )

    def test_schema_prop_removed_fails(self) -> None:
        source = self.contents[self.SCHEMA].replace('oor:name="MaterialReducedMotion"', 'oor:name="Gone"', 1)
        errors = self.failures(contents=self.with_content(self.SCHEMA, source))
        self.assertTrue(
            any("properties:MaterialReducedMotion:not found" in e for e in errors), errors
        )

    # -- widgets -----------------------------------------------------------
    def test_widget_id_removed_fails(self) -> None:
        source = self.contents[self.UI].replace('id="materialaccent"', 'id="materialaccentZ"', 1)
        errors = self.failures(contents=self.with_content(self.UI, source))
        self.assertTrue(
            any("properties:MaterialAccent:widget id='materialaccent' not found" in e
                for e in errors),
            errors,
        )

    def test_frame_removed_fails(self) -> None:
        source = self.contents[self.UI].replace('id="materialtheme"', 'id="materialthemeZ"', 1)
        errors = self.failures(contents=self.with_content(self.UI, source))
        self.assertTrue(any("properties:frame id='materialtheme' not found" in e for e in errors), errors)

    # -- controller --------------------------------------------------------
    def test_weld_binding_removed_fails(self) -> None:
        source = self.contents[self.CONTROLLER].replace(
            'weld_check_button(u"materialreducedmotion"', 'weld_check_button(u"gone"', 1
        )
        errors = self.failures(contents=self.with_content(self.CONTROLLER, source))
        self.assertTrue(
            any("properties:MaterialReducedMotion:controller weld binding" in e for e in errors),
            errors,
        )

    def test_commit_removed_fails(self) -> None:
        source = self.contents[self.CONTROLLER].replace(
            "officecfg::Office::Common::Appearance::MaterialDensity::set(",
            "officecfg::Office::Common::Appearance::MaterialDensity::skip(",
            1,
        )
        errors = self.failures(contents=self.with_content(self.CONTROLLER, source))
        self.assertTrue(
            any("properties:MaterialDensity:controller never commits" in e for e in errors), errors
        )

    # -- header ------------------------------------------------------------
    def test_header_marker_missing_fails(self) -> None:
        source = self.contents[self.HEADER].replace("m_xMaterialAccent", "m_xRenamed")
        errors = self.failures(contents=self.with_content(self.HEADER, source))
        self.assertTrue(any("header:marker 'm_xMaterialAccent' missing" in e for e in errors), errors)

    # -- apply path --------------------------------------------------------
    def test_apply_marker_missing_fails(self) -> None:
        source = self.contents[self.CONTROLLER].replace("executeRestartDialog", "noop")
        errors = self.failures(contents=self.with_content(self.CONTROLLER, source))
        self.assertTrue(
            any("apply:required marker 'executeRestartDialog' missing" in e for e in errors),
            errors,
        )

    def test_forbidden_live_marker_present_fails(self) -> None:
        source = self.contents[self.CONTROLLER] + "\n// computeMaterialScheme leaked here\n"
        errors = self.failures(contents=self.with_content(self.CONTROLLER, source))
        self.assertTrue(
            any("apply:forbidden Stage-3 live-apply marker 'computeMaterialScheme'" in e
                for e in errors),
            errors,
        )

    # -- scheme string -----------------------------------------------------
    def test_scheme_order_length_mismatch_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["scheme_string"]["accent_order"].append("Cyan")
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("scheme_string:accent_order has 7 entries" in e for e in errors), errors
        )

    def test_scheme_default_value_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["scheme_string"]["default_accent_value"] = "1"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("scheme_string:default_accent_value must be '0'" in e for e in errors), errors
        )

    def test_scheme_accent_not_in_ui_fails(self) -> None:
        source = self.contents[self.UI].replace(">Violet</item>", ">Purple</item>", 1)
        errors = self.failures(contents=self.with_content(self.UI, source))
        self.assertTrue(
            any("scheme_string:accent 'Violet' is not an item" in e for e in errors), errors
        )

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_apply_stage_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["apply_stage"] = "live"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:apply_stage:must be 'restart'" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:contract:" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
