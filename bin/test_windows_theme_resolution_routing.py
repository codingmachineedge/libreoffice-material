#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material theme-resolution routing contract (WIN-FND-002).

Each mutation weakens one guarantee -- a commented-out HC short-circuit, a reordered
precedence block, a native-fallback gate keyed off the wrong state, a dropped dark or
platform-HC signal, a broken WM_SETTINGCHANGE refresh, a rearranged app-wide cascade,
or a promoted honesty field -- and asserts the checker fails closed. A green baseline
proves the production tree currently passes.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-theme-resolution-routing.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_theme_resolution_routing", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

FDWD = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
LUNA = "vcl/win/gdi/salnativewidgets-luna.cxx"
SETTINGS = "vcl/source/window/settings.cxx"
SALGDI = "vcl/source/gdi/salgdilayout.cxx"
SALFRAME = "vcl/win/window/salframe.cxx"
WINPROC = "vcl/source/window/winproc.cxx"


class ThemeResolutionRoutingContractTest(unittest.TestCase):
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

    # -- hc-precedence checkpoint -----------------------------------------
    def test_hc_shortcircuit_commented_out_fails(self) -> None:
        source = self.contents[FDWD].replace(
            "        updateNativeWidgetFrameworkSettings(nullptr);\n        return false;\n    }",
            "        // updateNativeWidgetFrameworkSettings(nullptr);\n        return false;\n    }",
            1,
        )
        errors = self.failures(contents=self.with_content(FDWD, source))
        self.assertTrue(
            any("hc-precedence" in e or "hc-shortcircuit-order" in e for e in errors), errors
        )

    def test_hc_precedence_reordered_fails(self) -> None:
        # Keep every marker present but move the native-baseline restore *after*
        # the return so the short-circuit no longer restores before bailing.
        # The checkpoint markers still resolve; only the contiguous order fails.
        source = self.contents[FDWD].replace(
            "            m_pThemeState->mbHighContrast = true;\n        }\n"
            "        updateNativeWidgetFrameworkSettings(nullptr);\n        return false;",
            "            m_pThemeState->mbHighContrast = true;\n        }\n"
            "        return false;\n        updateNativeWidgetFrameworkSettings(nullptr);",
            1,
        )
        errors = self.failures(contents=self.with_content(FDWD, source))
        self.assertFalse(any("checkpoints:hc-precedence:" in e for e in errors), errors)
        self.assertTrue(any("hc-shortcircuit-order" in e for e in errors), errors)

    # -- native-fallback gate ---------------------------------------------
    def test_native_fallback_keyed_off_wrong_state_fails(self) -> None:
        source = self.contents[FDWD].replace(
            "    return m_pThemeState->mbHighContrast;\n}", "    return false;\n}", 1
        )
        errors = self.failures(contents=self.with_content(FDWD, source))
        self.assertTrue(any("native-fallback-gate" in e for e in errors), errors)

    # -- dark platform signal ---------------------------------------------
    def test_dark_ordinal_signal_dropped_fails(self) -> None:
        source = self.contents[LUNA].replace("MAKEINTRESOURCEA(132)", "MAKEINTRESOURCEA(999)", 1)
        errors = self.failures(contents=self.with_content(LUNA, source))
        self.assertTrue(any("dark-platform-signal" in e for e in errors), errors)

    # -- officecfg override layer -----------------------------------------
    def test_officecfg_hc_override_removed_fails(self) -> None:
        source = self.contents[SETTINGS].replace(
            "officecfg::Office::Common::Accessibility::HighContrast::get()", "0", 1
        )
        errors = self.failures(contents=self.with_content(SETTINGS, source))
        self.assertTrue(any("officecfg-override-layer" in e for e in errors), errors)

    def test_capture_before_update_reordered_fails(self) -> None:
        source = self.contents[SETTINGS].replace(
            "        pGraphics->CaptureFileDefinitionNativeSettings(rSettings);\n"
            "        pGraphics->UpdateFileDefinitionSettings(rSettings, ImplGetFrame()->GetUseDarkMode());",
            "        pGraphics->UpdateFileDefinitionSettings(rSettings, ImplGetFrame()->GetUseDarkMode());\n"
            "        pGraphics->CaptureFileDefinitionNativeSettings(rSettings);",
            1,
        )
        errors = self.failures(contents=self.with_content(SETTINGS, source))
        self.assertTrue(any("capture-before-update-order" in e for e in errors), errors)

    # -- opt-in gate -------------------------------------------------------
    def test_opt_in_gate_removed_fails(self) -> None:
        source = self.contents[SALGDI].replace(
            'getenv("VCL_DRAW_WIDGETS_FROM_FILE")', "false", 1
        )
        errors = self.failures(contents=self.with_content(SALGDI, source))
        self.assertTrue(any("opt-in-gate" in e for e in errors), errors)

    # -- platform HC read --------------------------------------------------
    def test_platform_hc_read_removed_fails(self) -> None:
        source = self.contents[SALFRAME].replace(
            "SystemParametersInfoW( SPI_GETHIGHCONTRAST, hc.cbSize, &hc, 0 )", "false", 1
        )
        errors = self.failures(contents=self.with_content(SALFRAME, source))
        self.assertTrue(any("platform-hc-read" in e for e in errors), errors)

    # -- live refresh ------------------------------------------------------
    def test_live_refresh_wm_settingchange_removed_fails(self) -> None:
        # `nMsg == WM_SETTINGCHANGE` is unique to ImplHandleSettingsChangeMsg
        # (the `case WM_SETTINGCHANGE:` label is a different literal), so removing
        # it drops the live-refresh trigger without collateral.
        source = self.contents[SALFRAME].replace(
            "nMsg == WM_SETTINGCHANGE", "nMsg == WM_NULL"
        )
        errors = self.failures(contents=self.with_content(SALFRAME, source))
        self.assertTrue(any("live-refresh" in e for e in errors), errors)

    # -- app-wide cascade --------------------------------------------------
    def test_app_cascade_reordered_fails(self) -> None:
        source = self.contents[WINPROC].replace(
            "        Application::MergeSystemSettings( aSettings );\n"
            "        pApp->OverrideSystemSettings( aSettings );\n"
            "        Application::SetSettings( aSettings );",
            "        Application::SetSettings( aSettings );\n"
            "        Application::MergeSystemSettings( aSettings );\n"
            "        pApp->OverrideSystemSettings( aSettings );",
            1,
        )
        errors = self.failures(contents=self.with_content(WINPROC, source))
        self.assertTrue(any("settings-cascade-order" in e for e in errors), errors)

    def test_source_missing_fails(self) -> None:
        contents = dict(self.contents)
        contents.pop(WINPROC, None)
        errors = self.failures(contents=contents)
        self.assertTrue(any("app-cascade" in e and "missing" in e for e in errors), errors)

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

    def test_theme_flag_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["theme_flag"] = "SOME_OTHER_FLAG"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:theme_flag:" in e for e in errors), errors)

    def test_opt_in_flag_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["opt_in_flag"] = "SOME_OTHER_FLAG"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:opt_in_flag:" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
