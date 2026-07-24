#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material notebookbar composition contract (WIN-NAV-004).

Each mutation weakens one guarantee and asserts the checker fails closed on it. The
group_area section covers a dropped @surface palette role, a missing token include, a
comment-only guard, a detached (guard-decoupled) @surface override, a dropped legacy
accent Merge() call, a stripped Material marker, or a role/registry drift. The tab_row
section adds the NEW structural markers: a dropped @primary/@outline-variant palette
role, a role drift, a missing token include, a stripped VCL_FILE_WIDGET_THEME or
GetHighContrastMode marker (high-contrast must always win), an un-invoked guard, and --
the load-bearing ones -- an underline paint detached from the guard or a removed hairline
paint. A green baseline proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-notebookbar-composition.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_notebookbar_composition", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DEFINITION = VALIDATOR.DEFINITION_PATH
NOTEBOOKBAR = "vcl/source/control/notebookbar.cxx"
TABCONTROL = "sfx2/source/notebookbar/NotebookbarTabControl.cxx"


class NotebookbarCompositionContractTest(unittest.TestCase):
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

    # -- palette (@surface role) ------------------------------------------
    def test_surface_role_removed_from_dark_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="surface" value="#141218"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("group_area:palette:@surface missing from the dark" in e for e in errors),
            errors,
        )

    def test_role_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["group_area"]["role"] = "surface-container"
        errors = self.failures(registry=registry)
        self.assertTrue(any("group_area:role" in e for e in errors), errors)

    # -- native wiring (notebookbar.cxx) ----------------------------------
    def test_token_include_required(self) -> None:
        source = self.contents[NOTEBOOKBAR].replace(
            "#include <vcl/MaterialTokens.hxx>", "", 1
        )
        errors = self.failures(contents=self.with_content(NOTEBOOKBAR, source))
        self.assertTrue(any("group_area:owner:missing #include" in e for e in errors), errors)

    def test_marker_stripped_fails(self) -> None:
        # Re-point the theme gate away from the documented flag: the comment-stripped
        # source then no longer carries the VCL_FILE_WIDGET_THEME marker.
        source = self.contents[NOTEBOOKBAR].replace(
            'std::getenv("VCL_FILE_WIDGET_THEME")',
            'std::getenv("SOME_OTHER_FLAG")',
            1,
        )
        errors = self.failures(contents=self.with_content(NOTEBOOKBAR, source))
        self.assertTrue(
            any("marker missing in code (VCL_FILE_WIDGET_THEME)" in e for e in errors),
            errors,
        )

    def test_guard_comment_only_fails(self) -> None:
        # Comment out the guarded override, leaving only the helper definition (one
        # occurrence): the checker requires the guard both defined AND invoked.
        source = self.contents[NOTEBOOKBAR].replace(
            "    if (const std::optional<Color> oSurface = lcl_materialNotebookbarColor(\"surface\"))\n"
            "        aColor = *oSurface;",
            "    // if (const std::optional<Color> oSurface = lcl_materialNotebookbarColor(\"surface\"))\n"
            "    //     aColor = *oSurface;",
            1,
        )
        errors = self.failures(contents=self.with_content(NOTEBOOKBAR, source))
        self.assertTrue(any("group_area:owner:guard" in e for e in errors), errors)

    def test_guarded_call_detached_fails(self) -> None:
        # Keep the guard invocation (guard count stays 2) AND keep a real *oSurface
        # override (so the whole-file marker still resolves), but detach the override
        # from the guard by giving the guard an empty body. Only the guarded_call
        # binding can catch this -- proving it locks the NEW group-area wiring, not
        # merely that the tokens exist somewhere.
        source = self.contents[NOTEBOOKBAR].replace(
            "    if (const std::optional<Color> oSurface = lcl_materialNotebookbarColor(\"surface\"))\n"
            "        aColor = *oSurface;",
            "    if (const std::optional<Color> oSurface = lcl_materialNotebookbarColor(\"surface\"))\n"
            "    {\n"
            "    }\n"
            "    aColor = *oSurface;",
            1,
        )
        contents = self.with_content(NOTEBOOKBAR, source)
        errors = self.failures(contents=contents)
        # The guard-count and whole-file marker checks still pass...
        self.assertFalse(any("group_area:owner:guard " in e for e in errors), errors)
        self.assertFalse(
            any("group_area:owner:marker missing" in e for e in errors), errors
        )
        # ...but the guarded-call binding fails closed.
        self.assertTrue(any("group_area:owner:guarded-call" in e for e in errors), errors)

    def test_accent_merge_dropped_fails(self) -> None:
        # Dropping any legacy per-module accent Merge() call must fail closed -- the
        # native/default-theme path must stay byte-for-byte untouched.
        source = self.contents[NOTEBOOKBAR].replace(
            "aColor.Merge(Color(0x1a, 0x85, 0xd1), cTrans)", "", 1
        )
        errors = self.failures(contents=self.with_content(NOTEBOOKBAR, source))
        self.assertTrue(any("must-retain accent Merge() dropped" in e for e in errors), errors)

    def test_owner_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["group_area"]["owner"]["source"] = "vcl/source/does/not/exist.cxx"
        contents = dict(self.contents)
        contents.pop(NOTEBOOKBAR, None)
        errors = self.failures(registry=registry, contents=contents)
        self.assertTrue(any("group_area:owner:source" in e and "missing" in e for e in errors), errors)

    # -- tab-row palette (@primary / @outline-variant) --------------------
    def test_tab_primary_removed_from_dark_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="primary" value="#D0BCFF"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any("tab_row:palette:@primary missing from the dark" in e for e in errors),
            errors,
        )

    def test_tab_outline_variant_removed_from_light_fails(self) -> None:
        definition = self.contents[DEFINITION].replace(
            '<color name="outline-variant" value="#CAC4D0"/>', "", 1
        )
        errors = self.failures(contents=self.with_content(DEFINITION, definition))
        self.assertTrue(
            any(
                "tab_row:palette:@outline-variant missing from the light" in e
                for e in errors
            ),
            errors,
        )

    def test_tab_role_primary_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["tab_row"]["role_primary"] = "secondary"
        errors = self.failures(registry=registry)
        self.assertTrue(any("tab_row:role_primary" in e for e in errors), errors)

    def test_tab_role_rule_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["tab_row"]["role_rule"] = "outline"
        errors = self.failures(registry=registry)
        self.assertTrue(any("tab_row:role_rule" in e for e in errors), errors)

    # -- tab-row native wiring (NotebookbarTabControl.cxx) ----------------
    def test_tab_token_include_required(self) -> None:
        source = self.contents[TABCONTROL].replace(
            "#include <vcl/MaterialTokens.hxx>", "", 1
        )
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        self.assertTrue(any("tab_row:owner:missing #include" in e for e in errors), errors)

    def test_tab_hc_marker_stripped_fails(self) -> None:
        # High-contrast must ALWAYS win: strip the GetHighContrastMode short-circuit and
        # the tab-row overlay would run in HC mode -- fail closed.
        source = self.contents[TABCONTROL].replace("GetHighContrastMode", "GetSomeOtherMode")
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        self.assertTrue(any("tab_row:owner:hc-marker missing" in e for e in errors), errors)

    def test_tab_theme_marker_stripped_fails(self) -> None:
        # Re-point the theme gate away from the documented flag: the comment-stripped
        # source then no longer carries the VCL_FILE_WIDGET_THEME marker.
        source = self.contents[TABCONTROL].replace(
            'std::getenv("VCL_FILE_WIDGET_THEME")',
            'std::getenv("SOME_OTHER_FLAG")',
            1,
        )
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        self.assertTrue(
            any(
                "tab_row:owner:marker missing in code (VCL_FILE_WIDGET_THEME)" in e
                for e in errors
            ),
            errors,
        )

    def test_tab_guard_not_invoked_fails(self) -> None:
        # Drop both guard invocations, leaving only the helper definition (one
        # occurrence): the checker requires the guard both defined AND invoked.
        source = self.contents[TABCONTROL].replace(
            '    const std::optional<Color> oRule = lcl_materialTabControlColor("outline-variant");\n'
            '    const std::optional<Color> oPrimary = lcl_materialTabControlColor("primary");',
            "    const std::optional<Color> oRule = std::nullopt;\n"
            "    const std::optional<Color> oPrimary = std::nullopt;",
            1,
        )
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        self.assertTrue(any("tab_row:owner:guard" in e for e in errors), errors)

    def test_tab_underline_paint_detached_fails(self) -> None:
        # Keep the guard resolution, markers and guard-count intact, but detach the
        # underline DrawRect from the guard by filling with a raw literal instead of the
        # guard-dereferenced *oPrimary. Only the paint binding can catch this -- proving
        # it locks the NEW underline paint, not merely that the token exists somewhere.
        source = self.contents[TABCONTROL].replace(
            "rRenderContext.SetFillColor(*oPrimary);",
            "rRenderContext.SetFillColor(COL_BLACK);",
            1,
        )
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        # The guard-count and whole-file marker checks still pass...
        self.assertFalse(any("tab_row:owner:guard " in e for e in errors), errors)
        self.assertFalse(any("tab_row:owner:marker missing" in e for e in errors), errors)
        # ...but the underline paint binding fails closed.
        self.assertTrue(any("tab_row:owner:paint:underline" in e for e in errors), errors)

    def test_tab_hairline_paint_removed_fails(self) -> None:
        # Alter the hairline DrawLine so the guard-bound statement no longer matches: the
        # @outline-variant tab-row hairline paint must fail closed.
        source = self.contents[TABCONTROL].replace(
            "rRenderContext.DrawLine(Point(0, nBaseline), Point(nWidth - 1, nBaseline));",
            "rRenderContext.DrawLine(Point(0, 0), Point(0, 0));",
            1,
        )
        errors = self.failures(contents=self.with_content(TABCONTROL, source))
        self.assertTrue(any("tab_row:owner:paint:hairline" in e for e in errors), errors)

    def test_tab_owner_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["tab_row"]["owner"]["source"] = "sfx2/source/does/not/exist.cxx"
        contents = dict(self.contents)
        contents.pop(TABCONTROL, None)
        errors = self.failures(registry=registry, contents=contents)
        self.assertTrue(
            any("tab_row:owner:source" in e and "missing" in e for e in errors), errors
        )

    def test_tab_row_section_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["tab_row"]
        errors = self.failures(registry=registry)
        self.assertIn("registry:tab_row:object required", errors)

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
