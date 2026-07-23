#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the reduced-motion signal chain contract (WIN-FND-004).

Each mutation weakens one guarantee -- a removed declaration, a hardcoded delegation, a
dropped officecfg read, a flipped SPI backend, fewer than three System-case negations, a
schema type/default drift, a deleted consumer, or a smuggled motion token in the theme
definition -- and asserts the checker fails closed. The trip-wire case proves the
Material-motion SRC gate is kept visibly open. A green baseline proves the production
tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-reduced-motion-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_reduced_motion_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
SETTINGS_HXX = "include/vcl/settings.hxx"
SETTINGS_CXX = "vcl/source/app/settings.cxx"
SALFRAME_H = "vcl/inc/win/salframe.h"
SALFRAME_CXX = "vcl/win/window/salframe.cxx"
SCHEMA = "officecfg/registry/schema/org/openoffice/Office/Common.xcs"
VIEWSH = "sw/source/core/view/viewsh.cxx"


class ReducedMotionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

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

    # -- declarations ------------------------------------------------------
    def test_declaration_removed_fails(self) -> None:
        source = self.contents[SETTINGS_HXX].replace("IsAnimatedTextAllowed();", "", 1)
        errors = self.failures(contents=self.with_content(SETTINGS_HXX, source))
        self.assertTrue(any("declarations:marker missing" in e for e in errors), errors)

    # -- delegation --------------------------------------------------------
    def test_delegation_hardcoded_fails(self) -> None:
        source = self.contents[SETTINGS_CXX].replace(
            "return pDefWindow->ImplGetFrame()->GetUseReducedAnimation();", "return false;", 1
        )
        errors = self.failures(contents=self.with_content(SETTINGS_CXX, source))
        self.assertTrue(any("checkpoints:delegation:marker missing" in e for e in errors), errors)

    # -- officecfg reads ---------------------------------------------------
    def test_officecfg_read_removed_fails(self) -> None:
        source = self.contents[SETTINGS_CXX].replace(
            "officecfg::Office::Common::Accessibility::AllowAnimatedText::get()", "0", 1
        )
        errors = self.failures(contents=self.with_content(SETTINGS_CXX, source))
        self.assertTrue(any("checkpoints:officecfg-reads:marker missing" in e for e in errors), errors)

    # -- System-case negation count ---------------------------------------
    def test_system_case_negation_count_drops_fails(self) -> None:
        source = self.contents[SETTINGS_CXX].replace(
            "bIsAllowed = ! MiscSettings::GetUseReducedAnimation();", "bIsAllowed = true;", 1
        )
        errors = self.failures(contents=self.with_content(SETTINGS_CXX, source))
        self.assertTrue(any("repeated:system-case-negation" in e for e in errors), errors)

    # -- windows backend ---------------------------------------------------
    def test_windows_decl_removed_fails(self) -> None:
        source = self.contents[SALFRAME_H].replace(
            "GetUseReducedAnimation() const override;", "", 1
        )
        errors = self.failures(contents=self.with_content(SALFRAME_H, source))
        self.assertTrue(any("checkpoints:windows-decl:marker missing" in e for e in errors), errors)

    def test_windows_spi_negation_flipped_fails(self) -> None:
        source = self.contents[SALFRAME_CXX].replace(
            "return !bEnableAnimation;", "return bEnableAnimation;", 1
        )
        errors = self.failures(contents=self.with_content(SALFRAME_CXX, source))
        self.assertTrue(any("contiguous:windows-spi-backend" in e for e in errors), errors)

    # -- officecfg schema --------------------------------------------------
    def test_schema_type_drift_fails(self) -> None:
        source = self.contents[SCHEMA].replace(
            '<prop oor:name="AllowAnimatedGraphic" oor:type="xs:short"',
            '<prop oor:name="AllowAnimatedGraphic" oor:type="xs:int"',
            1,
        )
        errors = self.failures(contents=self.with_content(SCHEMA, source))
        self.assertTrue(any("schema:prop 'AllowAnimatedGraphic' is not oor:type" in e for e in errors), errors)

    def test_schema_default_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["schema"]["default"] = "1"
        errors = self.failures(registry=registry)
        self.assertTrue(any("schema:prop" in e and "default drifted" in e for e in errors), errors)

    # -- consumers ---------------------------------------------------------
    def test_consumer_call_site_removed_fails(self) -> None:
        source = self.contents[VIEWSH].replace(
            "MiscSettings::IsAnimatedGraphicAllowed()", "true", 1
        )
        errors = self.failures(contents=self.with_content(VIEWSH, source))
        self.assertTrue(
            any("consumers:IsAnimatedGraphicAllowed:no live call site" in e for e in errors), errors
        )

    # -- trip-wire ---------------------------------------------------------
    def test_motion_token_injected_fails(self) -> None:
        definition = self.contents[DEFINITION].replace("<metrics>", "<motion/><metrics>", 1)
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("trip_wire" in e and "motion element" in e for e in errors), errors)

    def test_motion_attribute_injected_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            "<metrics>", '<metrics duration="120">', 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("trip_wire" in e and "motion attribute" in e for e in errors), errors)

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
