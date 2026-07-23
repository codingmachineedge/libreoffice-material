#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material base rail/workspace validator.

Every marker in ``qa/windows-ui-contract/base-rail-workspace.json`` is
mutation-tested: the production tree passes, and each guarded surface, token
consumption, .ui anchor, kicker call site and registry invariant is proven to
fail closed when weakened (including comment-only wiring, which the checker
strips before matching).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-base-rail-workspace.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/base-rail-workspace.json"

SPEC = importlib.util.spec_from_file_location("check_windows_base_rail_workspace", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class BaseRailWorkspaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        tracked: set[str] = {cls.registry["definition_file"]}
        for marker in cls.registry["markers"]:
            for key in ("source", "header", "ui"):
                if isinstance(marker.get(key), str):
                    tracked.add(marker[key])
        tracked.add(cls.registry["kicker_call_site"]["source"])
        cls.tracked_files = sorted(tracked)
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

    # -- scaffolding --------------------------------------------------------------------------
    def run_validate(self, *, files: dict[str, str] | None = None, registry: dict | None = None) -> None:
        files = files or {}
        registry_data = registry if registry is not None else self.registry
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in self.tracked_files:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(files.get(rel, self.originals[rel]), encoding="utf-8")
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
            VALIDATOR.validate(root, registry_path)

    def assert_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            self.run_validate(**kwargs)

    def mutated(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    def _marker_index(self, marker_id: str) -> int:
        for index, marker in enumerate(self.registry["markers"]):
            if marker["id"] == marker_id:
                return index
        raise AssertionError(f"unknown marker id {marker_id}")

    # -- production ---------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- guard --------------------------------------------------------------------------------
    def test_rejects_removed_activation_guard(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppSwapWindow.cxx",
            'std::getenv("VCL_FILE_WIDGET_THEME")',
            'std::getenv("DISABLED_BASE_GUARD")',
        )
        self.assert_fails("missing marker in code ('VCL_FILE_WIDGET_THEME')", files=files)

    def test_rejects_removed_high_contrast_bypass(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppView.cxx",
            "GetHighContrastMode()",
            "false",
        )
        self.assert_fails("missing marker in code ('GetHighContrastMode()')", files=files)

    def test_comment_only_guard_fails_closed(self) -> None:
        # The checker strips C++ comments first, so commenting out the resolver
        # call must fail closed rather than satisfy the marker.
        files = self.mutated(
            "dbaccess/source/ui/app/AppIconControl.cxx",
            "vcl::MaterialTokens::fromThemeDefinition(bDark",
            "// vcl::MaterialTokens::fromThemeDefinition(bDark",
        )
        self.assert_fails("missing marker in code ('MaterialTokens::fromThemeDefinition')", files=files)

    # -- token consumption --------------------------------------------------------------------
    def test_rejects_dropped_surface_container_token(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppSwapWindow.cxx",
            'findColor("surface-container")',
            'findColor("surface-XXX")',
        )
        self.assert_fails(
            "token role 'surface-container' not consumed as a quoted literal in code", files=files
        )

    def test_rejects_dropped_on_primary_container_token(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppIconControl.cxx",
            'findColor("on-primary-container")',
            'findColor("on-primary-XXX")',
        )
        self.assert_fails(
            "token role 'on-primary-container' not consumed as a quoted literal in code",
            files=files,
        )

    # -- anatomy code markers -----------------------------------------------------------------
    def test_rejects_dropped_highlight_member(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppIconControl.cxx",
            "maHighlightColor = oSelection->aFill;",
            "// removed",
        )
        self.assert_fails("missing marker in code ('maHighlightColor')", files=files)

    def test_rejects_dropped_kicker_font_color(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppTitleWindow.cxx",
            "m_xTitle->set_font_color(*oKicker);",
            "// removed",
        )
        self.assert_fails("missing marker in code ('set_font_color(')", files=files)

    # -- .ui anchors --------------------------------------------------------------------------
    def test_rejects_renamed_panel_hairline(self) -> None:
        files = self.mutated(
            "dbaccess/uiconfig/ui/appborderwindow.ui",
            'id="panelhairline"',
            'id="panelXXX"',
        )
        self.assert_fails('missing marker in code (\'id="panelhairline"\')', files=files)

    def test_rejects_removed_title_label_id(self) -> None:
        files = self.mutated(
            "dbaccess/uiconfig/ui/titlewindow.ui",
            'id="title"',
            'id="titleXXX"',
        )
        self.assert_fails('missing marker in code (\'id="title"\')', files=files)

    # -- header markers -----------------------------------------------------------------------
    def test_rejects_removed_titlestyle_enum(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppTitleWindow.hxx",
            "enum class TitleStyle",
            "enum class RemovedStyle",
        )
        self.assert_fails("missing marker in code ('enum class TitleStyle')", files=files)

    # -- kicker call site ---------------------------------------------------------------------
    def test_rejects_rail_head_not_kicker(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/app/AppView.cxx",
            "OTitleWindow::TitleStyle::Kicker",
            "OTitleWindow::TitleStyle::Heading",
        )
        self.assert_fails("missing marker in code ('OTitleWindow::TitleStyle::Kicker')", files=files)

    # -- registry integrity -------------------------------------------------------------------
    def test_rejects_expected_marker_count_drift(self) -> None:
        registry = self.registry_copy()
        registry["expected_markers"] = len(registry["markers"]) - 1
        self.assert_fails("expected_markers count drift", registry=registry)

    def test_rejects_runtime_verified_true_marker(self) -> None:
        registry = self.registry_copy()
        registry["markers"][0]["runtime_verified"] = True
        self.assert_fails("runtime_verified must be false", registry=registry)

    def test_rejects_palette_token_drift(self) -> None:
        registry = self.registry_copy()
        registry["palette_tokens"].append("not-a-real-role")
        self.assert_fails("colour role 'not-a-real-role' missing from scheme", registry=registry)

    def test_rejects_shape_token_value_drift(self) -> None:
        registry = self.registry_copy()
        registry["shape_tokens"]["corner-container"] = "99"
        self.assert_fails("radius 'corner-container' is '12', expected '99'", registry=registry)

    def test_rejects_top_level_runtime_verified_true(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        self.assert_fails("registry runtime_verified must be false", registry=registry)


if __name__ == "__main__":
    unittest.main()
