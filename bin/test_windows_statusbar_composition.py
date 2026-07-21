#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material status-bar composition contract (WIN-NAV-008).

Each mutation weakens one guarantee -- a drifted band token, a remapped faceColor
slot, a promoted spec-only field-hover, a broken zoom-slider part, comment-only
native wiring, an ungated (guard-detached) value-change call, or a dropped accessible
value-change path -- and asserts the checker fails closed on it. A green baseline
proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-statusbar-composition.py"
SPEC = importlib.util.spec_from_file_location("check_windows_statusbar_composition", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
STATUS = "vcl/source/window/status.cxx"
CONTROLLER = "framework/source/uielement/genericstatusbarcontroller.cxx"


class StatusBarCompositionContractTest(unittest.TestCase):
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

    # -- band: faceColor slot + tokens ------------------------------------
    def test_face_color_slot_remapped_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<faceColor value="@surface-container"/>',
            '<faceColor value="@surface"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("face-color-slot" in e for e in errors), errors)

    def test_band_metric_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<metric name="size-compact-control" value="28"/>',
            '<metric name="size-compact-control" value="32"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("band:metric:" in e and "metric drift" in e for e in errors), errors)

    def test_band_palette_color_removed_fails(self) -> None:
        # Drop @surface-container from the dark palette only.
        definition = self.contents[DEFINITION].replace(
            '<color name="surface-container" value="#211F26"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("band:palette:@surface-container missing from the dark" in e for e in errors),
            errors,
        )

    def test_top_rule_token_removed_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="outline-variant" value="#CAC4D0"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("top-rule:@outline-variant" in e for e in errors), errors)

    # -- field hover (spec-only grounding) --------------------------------
    def test_field_hover_promoted_to_runtime_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["field_hover"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("field_hover:status" in e for e in errors), errors)

    def test_field_hover_radius_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<radius name="corner-small" value="8"/>',
            '<radius name="corner-small" value="4"/>',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("field_hover:radius:corner-small" in e for e in errors), errors)

    # -- zoom slider parts ------------------------------------------------
    def test_slider_thumb_size_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="Button" width="@size-compact-control" height="@size-compact-control">',
            '<part value="Button" width="@size-compact-control" height="@size-standard-control">',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("zoom_slider" in e and "attribute height" in e for e in errors), errors)

    def test_slider_track_token_drift_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<part value="TrackHorzLeft">\n'
            '            <state enabled="true"><line stroke="@primary" stroke-width="@stroke-track"',
            '<part value="TrackHorzLeft">\n'
            '            <state enabled="true"><line stroke="@outline" stroke-width="@stroke-track"',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("zoom_slider:slider/TrackHorzLeft" in e and "token drift" in e for e in errors),
            errors,
        )

    def test_slider_part_renamed_fails(self) -> None:
        # Target the slider's multi-line TrackHorzRight (the scrollbar's is a
        # single-line rect part), so the rename hits the zoom slider specifically.
        definition = self.contents[DEFINITION].replace(
            '<part value="TrackHorzRight">\n'
            '            <state enabled="true"><line stroke="@outline-variant"',
            '<part value="Renamed">\n'
            '            <state enabled="true"><line stroke="@outline-variant"',
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("zoom_slider:slider/TrackHorzRight missing" in e for e in errors), errors
        )

    def test_slider_focus_state_dropped_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<state enabled="true" focused="true"><rect stroke="@on-surface" fill="@primary" '
            'stroke-width="@stroke-standard" radius="@corner-container"/></state>',
            "",
            1,
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(any("thumb-focus no <state> matching" in e for e in errors), errors)

    # -- band native wiring (status.cxx) ----------------------------------
    def test_band_comment_only_wiring_fails(self) -> None:
        source = self.contents[STATUS].replace(
            'if (const std::optional<Color> oBand = lcl_materialStatusColor("surface-container"))',
            '// if (const std::optional<Color> oBand = lcl_materialStatusColor("surface-container"))',
            1,
        )
        errors = self.failures(contents=self.with_content(STATUS, source))
        self.assertTrue(
            any('band:owner:marker missing in code (lcl_materialStatusColor("surface-container"))' in e
                for e in errors),
            errors,
        )

    def test_band_top_rule_wiring_removed_fails(self) -> None:
        source = self.contents[STATUS].replace(
            'lcl_materialStatusColor("outline-variant")', "std::nullopt", 1
        )
        errors = self.failures(contents=self.with_content(STATUS, source))
        self.assertTrue(
            any('lcl_materialStatusColor("outline-variant")' in e for e in errors), errors
        )

    def test_band_token_include_required(self) -> None:
        source = self.contents[STATUS].replace("#include <vcl/MaterialTokens.hxx>", "", 1)
        errors = self.failures(contents=self.with_content(STATUS, source))
        self.assertTrue(any("band:owner:missing #include" in e for e in errors), errors)

    # -- accessibility value-change path ----------------------------------
    def test_accessibility_guard_comment_only_fails(self) -> None:
        # Comment out the guarded call, leaving only the helper definition (one
        # occurrence): the checker requires the guard both defined AND invoked.
        source = self.contents[CONTROLLER].replace(
            "            if ( lcl_isMaterialFileWidgetTheme() )\n"
            "                m_xStatusbarItem->setAccessibleName( aStrValue );",
            "            // if ( lcl_isMaterialFileWidgetTheme() )\n"
            "            //     m_xStatusbarItem->setAccessibleName( aStrValue );",
            1,
        )
        errors = self.failures(contents=self.with_content(CONTROLLER, source))
        self.assertTrue(any("accessibility:guard" in e for e in errors), errors)

    def test_accessibility_guarded_call_detached_fails(self) -> None:
        # Keep the guard invocation (guard count stays 2) AND keep a real
        # setAccessibleName call (so the whole-file marker still resolves), but
        # detach the call from the guard by giving the guard an empty body. Only
        # the guarded_call binding can catch this -- proving it locks the NEW
        # owner-draw wiring, not merely that the tokens exist somewhere.
        source = self.contents[CONTROLLER].replace(
            "            if ( lcl_isMaterialFileWidgetTheme() )\n"
            "                m_xStatusbarItem->setAccessibleName( aStrValue );",
            "            if ( lcl_isMaterialFileWidgetTheme() )\n"
            "            {\n"
            "            }\n"
            "            m_xStatusbarItem->setAccessibleName( aStrValue );",
            1,
        )
        contents = self.with_content(CONTROLLER, source)
        errors = self.failures(contents=contents)
        # The guard-count and whole-file marker checks still pass...
        self.assertFalse(any("accessibility:guard " in e for e in errors), errors)
        self.assertFalse(
            any("accessibility:marker missing" in e for e in errors), errors
        )
        # ...but the guarded-call binding fails closed.
        self.assertTrue(any("accessibility:guarded-call" in e for e in errors), errors)

    def test_accessibility_repaint_retained(self) -> None:
        # Dropping the existing bare-repaint path must fail closed.
        source = self.contents[CONTROLLER].replace("m_xStatusbarItem->repaint();", "", 1)
        errors = self.failures(contents=self.with_content(CONTROLLER, source))
        self.assertTrue(any("must-retain marker dropped" in e for e in errors), errors)

    def test_accessibility_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["accessibility"]["source"] = "framework/source/does/not/exist.cxx"
        contents = dict(self.contents)
        contents.pop(CONTROLLER, None)
        errors = self.failures(registry=registry, contents=contents)
        self.assertTrue(any("accessibility:source" in e and "missing" in e for e in errors), errors)

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
        self.assertIn("registry:contract:unexpected value", errors)

    def test_theme_flag_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["theme_flag"] = "SOME_OTHER_FLAG"
        errors = self.failures(registry=registry)
        self.assertIn("registry:theme_flag:must be VCL_FILE_WIDGET_THEME", errors)


if __name__ == "__main__":
    unittest.main()
