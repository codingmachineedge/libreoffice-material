#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material elevation strategy contract (WIN-FND-003).

Each mutation weakens one guarantee -- a drifted Border/Frame token, a dropped tonal
role, a removed 2px inset, a scrim literal drift, a shadow row that no longer matches
the doc or the prototype, a promoted (non prototype-only) shadow, a smuggled native
shadow row, or an injected native opacity attribute -- and asserts the checker fails
closed. The prototype-drift case is the reconciliation guard: it must stay fail-closed,
never loosened. A green baseline proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-elevation-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_elevation_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
CHAPTER = VALIDATOR.CHAPTER_PATH
PROTOTYPE = VALIDATOR.PROTOTYPE_PATH
DRAW = VALIDATOR.DRAW_PATH
READER = VALIDATOR.READER_PATH

FRAME_RECT = (
    '<rect stroke="@outline-variant" fill="@surface-container" '
    'stroke-width="@stroke-thin" radius="@corner-container"/>'
)


class ElevationContractTest(unittest.TestCase):
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

    # -- border channel ----------------------------------------------------
    def test_border_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            FRAME_RECT,
            FRAME_RECT.replace('fill="@surface-container"', 'fill="@surface"'),
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("border:frame/Border token drift" in e for e in errors), errors)

    def test_border_surface_role_unresolved_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["border"]["surface_roles"].append("not-a-real-surface")
        errors = self.failures(registry=registry)
        self.assertTrue(any("border:tonal:@not-a-real-surface" in e for e in errors), errors)

    def test_border_inset_removed_fails(self) -> None:
        source = self.contents[DRAW].replace(
            "rNativeContentRegion.AdjustBottom(-2);", "", 1
        )
        errors = self.failures(contents=self.with_content(DRAW, source))
        self.assertTrue(any("border:inset:marker missing" in e for e in errors), errors)

    # -- scrim -------------------------------------------------------------
    def test_scrim_prototype_drift_fails(self) -> None:
        prototype = self.contents[PROTOTYPE].replace(
            "scrim:'rgba(0,0,0,.6)'", "scrim:'rgba(0,0,0,.5)'", 1
        )
        errors = self.failures(contents=self.with_content(PROTOTYPE, prototype))
        self.assertTrue(any("scrim:dark" in e for e in errors), errors)

    # -- shadows -----------------------------------------------------------
    def test_shadow_doc_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["shadows"]["rows"][1]["shadow"] = "0 24px 64px rgba(0,0,0,.9)"
        errors = self.failures(registry=registry)
        self.assertTrue(any("shadows:Modal dialogs:doc drift" in e for e in errors), errors)

    def test_shadow_prototype_drift_fails(self) -> None:
        # The reconciliation guard: reintroduce the historical prototype drift
        # (modal .44) and the doc literal .4 is no longer found in the prototype.
        prototype = self.contents[PROTOTYPE].replace(
            "box-shadow:0 24px 64px rgba(0,0,0,.4)",
            "box-shadow:0 24px 64px rgba(0,0,0,.44)",
            1,
        )
        errors = self.failures(contents=self.with_content(PROTOTYPE, prototype))
        self.assertTrue(
            any("shadows:Modal dialogs" in e and "not present as a box-shadow" in e for e in errors),
            errors,
        )

    def test_shadow_status_not_prototype_only_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["shadows"]["rows"][0]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("status must be 'prototype-only'" in e for e in errors), errors
        )

    def test_smuggled_native_shadow_row_fails(self) -> None:
        # Append an eighth shadow row to the section-4 table; doc_row_count (7)
        # and the ledger length both fail closed on the un-ledgered addition.
        chapter = self.contents[CHAPTER].replace(
            "| Impress/Draw canvas | `0 8px 30px rgba(0,0,0,.16)` / `0 8px 30px rgba(0,0,0,.14)` |",
            "| Impress/Draw canvas | `0 8px 30px rgba(0,0,0,.16)` / `0 8px 30px rgba(0,0,0,.14)` |\n"
            "| Sidebar panel | `0 2px 8px rgba(0,0,0,.12)` |",
            1,
        )
        errors = self.failures(contents=self.with_content(CHAPTER, chapter))
        self.assertTrue(any("shadows:doc_row_count" in e for e in errors), errors)

    # -- opacity / legacy shadow slot -------------------------------------
    def test_native_opacity_attribute_injected_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            FRAME_RECT,
            FRAME_RECT.replace(
                'radius="@corner-container"/>', 'radius="@corner-container" opacity="0.5"/>'
            ),
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("opacity" in e and "forbidden drawable attribute" in e for e in errors), errors
        )

    def test_legacy_shadow_slot_marker_removed_fails(self) -> None:
        reader = self.contents[READER].replace(
            '{ "shadowColor", &rWidgetDefinition.mpStyle->maShadowColor }',
            '{ "shadowColorX", &rWidgetDefinition.mpStyle->maShadowColor }',
            1,
        )
        errors = self.failures(contents=self.with_content(READER, reader))
        self.assertTrue(any("opacity:legacy-shadow-slot:marker missing" in e for e in errors), errors)

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
