#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the WIN-SYS-014 render/scale neutrality contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-render-scale-matrix.py"
SPEC = importlib.util.spec_from_file_location("check_windows_render_scale_matrix", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


FDWD = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
MANIFEST = "solenv/gbuild/platform/DeclareDPIAware.manifest"
MSC = "solenv/gbuild/platform/com_MSC_class.mk"
XCU = "officecfg/registry/data/org/openoffice/Office/Common.xcu"
XCS = "officecfg/registry/schema/org/openoffice/Office/Common.xcs"
SKIA = "vcl/skia/SkiaHelper.cxx"


class RenderScaleMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(self, *, registry=None, contents=None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def without_content(self, path: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents.pop(path, None)
        return contents

    def replace_in_prop_block(self, path: str, prop: str, old: str, new: str) -> dict[str, str]:
        text = self.contents[path]
        block = VALIDATOR._prop_block(text, prop)
        self.assertIsNotNone(block, f"no {prop} block in {path}")
        self.assertIn(old, block, f"{old!r} not in {prop} block")
        return self.with_content(path, text.replace(block, block.replace(old, new, 1), 1))

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- render_agnostic ---------------------------------------------------
    def test_render_method_selection_token_fails(self) -> None:
        text = self.contents[FDWD] + "\nvoid material_probe() { (void)renderMethodToUse(); }\n"
        errors = self.failures(contents=self.with_content(FDWD, text))
        self.assertTrue(any("render_agnostic" in e and "renderMethodToUse" in e for e in errors), errors)

    def test_commented_render_token_is_ignored(self) -> None:
        # The comment strip means a render-method token in a comment must NOT trip.
        text = self.contents[FDWD] + "\n// renderMethodToUse SkiaHelper:: RenderVulkan in a comment\n"
        errors = self.failures(contents=self.with_content(FDWD, text))
        self.assertEqual([], errors, errors)

    def test_render_agnostic_file_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(FDWD))
        self.assertTrue(any("render_agnostic" in e and "missing" in e for e in errors), errors)

    # -- dpi_awareness_pinned ---------------------------------------------
    def test_per_monitor_manifest_fails(self) -> None:
        text = self.contents[MANIFEST].replace(
            "<dpiAware>true</dpiAware>", "<dpiAwareness>PerMonitorV2</dpiAwareness>", 1
        )
        self.assertNotEqual(text, self.contents[MANIFEST])
        errors = self.failures(contents=self.with_content(MANIFEST, text))
        self.assertTrue(any("dpi_awareness_pinned" in e for e in errors), errors)

    # -- dpi_manifest_wired -----------------------------------------------
    def test_manifest_not_wired_to_executable_fails(self) -> None:
        text = self.contents[MSC].replace("DeclareDPIAware.manifest", "Missing.manifest")
        self.assertNotEqual(text, self.contents[MSC])
        errors = self.failures(contents=self.with_content(MSC, text))
        self.assertTrue(any("dpi_manifest_wired" in e for e in errors), errors)

    # -- win_skia_default --------------------------------------------------
    def test_windows_skia_default_off_fails(self) -> None:
        contents = self.replace_in_prop_block(
            XCU,
            "UseSkia",
            '<value install:module="wnt">true</value>',
            '<value install:module="wnt">false</value>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("win_skia_default" in e for e in errors), errors)

    # -- skia_settings_surface --------------------------------------------
    def test_force_skia_raster_default_on_fails(self) -> None:
        contents = self.replace_in_prop_block(
            XCS, "ForceSkiaRaster", "<value>false</value>", "<value>true</value>"
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("skia_settings_surface" in e and "ForceSkiaRaster" in e for e in errors), errors)

    # -- raster_fallback_exists -------------------------------------------
    def test_removed_force_raster_fallback_fails(self) -> None:
        text = self.contents[SKIA].replace(
            "if (officecfg::Office::Common::VCL::ForceSkiaRaster::get())", "if (false)", 1
        )
        self.assertNotEqual(text, self.contents[SKIA])
        errors = self.failures(contents=self.with_content(SKIA, text))
        self.assertTrue(any("raster_fallback_exists" in e for e in errors), errors)

    def test_removed_win_safe_mode_guard_fails(self) -> None:
        text = self.contents[SKIA].replace(
            "#if defined(MACOSX) || defined(_WIN32)", "#if defined(MACOSX)", 1
        )
        self.assertNotEqual(text, self.contents[SKIA])
        errors = self.failures(contents=self.with_content(SKIA, text))
        self.assertTrue(any("raster_fallback_exists" in e and "_WIN32" in e for e in errors), errors)

    # -- matrix carve-out + meta ------------------------------------------
    def test_matrix_promotion_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["matrix"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("matrix:status:must stay 'specified'" in e for e in errors), errors)

    def test_matrix_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["matrix"]["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("matrix:runtime_verified" in e for e in errors), errors)

    def test_matrix_build_bound_emptied_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["matrix"]["build_bound"] = []
        errors = self.failures(registry=registry)
        self.assertTrue(any("matrix:build_bound" in e for e in errors), errors)

    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:contract" in e for e in errors), errors)

    def test_registry_value_drives_win_skia_assertion(self) -> None:
        # A registry that pins the wrong wnt value must be caught against the real xcu.
        registry = copy.deepcopy(self.registry)
        registry["pins"]["win_skia_default"]["required_value"] = (
            '<value install:module="wnt">false</value>'
        )
        errors = self.failures(registry=registry)
        self.assertTrue(any("win_skia_default" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
