#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material default-activation contract (Windows).

Each mutation perturbs one guarantee against an in-memory copy of the tree and
asserts the checker fails closed; a positive control proves the pristine tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import re
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-material-default-activation.py"
SPEC = importlib.util.spec_from_file_location(
    "check_material_default_activation", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

SOURCE = "desktop/source/app/sofficemain.cxx"
GATE = "vcl/source/gdi/salgdilayout.cxx"
MK = "vcl/Package_theme_definitions.mk"

# The whole default-on block: from its Windows guard through the matching #endif.
BLOCK_RE = re.compile(r"#ifdef _WIN32\n    // Fork default:.*?\n#endif\n", re.DOTALL)
FIRST_STATEMENT = "sal_detail_initialize(sal::detail::InitializeSoffice, nullptr);\n"


class MaterialDefaultActivationTest(unittest.TestCase):
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

    def mutate(self, path: str, old: str, new: str, count: int = 1) -> dict[str, str]:
        text = self.contents[path]
        replaced = text.replace(old, new) if count < 0 else text.replace(old, new, count)
        self.assertNotEqual(text, replaced, f"mutation anchor not found in {path}: {old!r}")
        return self.with_content(path, replaced)

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- the activation block ---------------------------------------------
    def test_removed_block_fails(self) -> None:
        src = self.contents[SOURCE]
        mutated = BLOCK_RE.sub("", src, count=1)
        self.assertNotEqual(src, mutated, "block anchor not found")
        errors = self.failures(contents=self.with_content(SOURCE, mutated))
        self.assertTrue(errors)
        self.assertTrue(any("_putenv_s" in e for e in errors), errors)

    def test_block_moved_after_first_statement_fails(self) -> None:
        src = self.contents[SOURCE]
        match = BLOCK_RE.search(src)
        self.assertIsNotNone(match, "block anchor not found")
        block = match.group(0)
        without = src[: match.start()] + src[match.end() :]
        moved = without.replace(FIRST_STATEMENT, FIRST_STATEMENT + block, 1)
        self.assertNotEqual(without, moved, "first-statement anchor not found")
        errors = self.failures(contents=self.with_content(SOURCE, moved))
        self.assertTrue(
            any("before the first statement" in e for e in errors), errors
        )

    def test_win32_guard_removed_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                SOURCE, "#ifdef _WIN32\n    // Fork default", "#if 1\n    // Fork default"
            )
        )
        self.assertTrue(any("guard" in e for e in errors), errors)

    def test_opt_out_token_removed_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                SOURCE, "LIBREOFFICE_MATERIAL_THEME", "SOME_OTHER_TOKEN", -1
            )
        )
        self.assertTrue(any("opt-out token" in e for e in errors), errors)

    def test_opt_out_value_drift_fails(self) -> None:
        errors = self.failures(contents=self.mutate(SOURCE, '"off"', '"disabled"'))
        self.assertTrue(any("not compared" in e for e in errors), errors)

    def test_case_insensitive_marker_removed_fails(self) -> None:
        errors = self.failures(contents=self.mutate(SOURCE, "_stricmp", "strcmp", -1))
        self.assertTrue(any("case-insensitive" in e for e in errors), errors)

    def test_respect_existing_removed_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                SOURCE,
                'getenv("VCL_FILE_WIDGET_THEME")',
                'getenv("VCL_SOMETHING_ELSE")',
                -1,
            )
        )
        self.assertTrue(any("respect-existing" in e for e in errors), errors)

    def test_theme_putenv_value_drift_fails(self) -> None:
        # Target the code call, not the "material" mention in the block comment
        # (the checker strips comments, so a comment-only edit would be invisible).
        errors = self.failures(
            contents=self.mutate(
                SOURCE,
                '_putenv_s("VCL_FILE_WIDGET_THEME", "material")',
                '_putenv_s("VCL_FILE_WIDGET_THEME", "materiel")',
            )
        )
        self.assertTrue(
            any("VCL_FILE_WIDGET_THEME" in e and "_putenv_s" in e for e in errors), errors
        )

    def test_draw_putenv_value_drift_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                SOURCE,
                '_putenv_s("VCL_DRAW_WIDGETS_FROM_FILE", "1")',
                '_putenv_s("VCL_DRAW_WIDGETS_FROM_FILE", "2")',
                -1,
            )
        )
        self.assertTrue(
            any("VCL_DRAW_WIDGETS_FROM_FILE" in e and "_putenv_s" in e for e in errors),
            errors,
        )

    def test_missing_source_file_fails_closed(self) -> None:
        errors = self.failures(contents=self.without_content(SOURCE))
        self.assertTrue(any("file missing" in e for e in errors), errors)

    # -- asset cross-checks ------------------------------------------------
    def test_salgdilayout_gate_drift_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                GATE,
                'getenv("VCL_DRAW_WIDGETS_FROM_FILE")',
                'getenv("VCL_DEAD_SWITCH")',
            )
        )
        self.assertTrue(any("asset_cross_checks:gate" in e for e in errors), errors)

    def test_package_mk_drift_fails(self) -> None:
        errors = self.failures(
            contents=self.mutate(
                MK, "material/definition.xml", "material/definition-renamed.xml"
            )
        )
        self.assertTrue(any("asset_cross_checks:assets" in e for e in errors), errors)

    def test_gate_file_missing_fails_closed(self) -> None:
        errors = self.failures(contents=self.without_content(GATE))
        self.assertTrue(any("asset_cross_checks:gate" in e for e in errors), errors)

    # -- registry invariants ----------------------------------------------
    def test_runtime_verified_true_rejected(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified" in e for e in errors), errors)

    def test_wrong_contract_slug_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:contract" in e for e in errors), errors)

    def test_wrong_schema_version_fails(self) -> None:
        registry = self.registry_copy()
        registry["schema_version"] = 2
        errors = self.failures(registry=registry)
        self.assertTrue(any("schema_version" in e for e in errors), errors)

    def test_wrong_status_fails(self) -> None:
        registry = self.registry_copy()
        registry["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("registry:status" in e for e in errors), errors)

    def test_carveout_status_promoted_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveout"]["first_visual_verification"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(any("carveout" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
