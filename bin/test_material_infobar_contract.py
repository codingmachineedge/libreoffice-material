#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material infobar severity validator."""

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
VALIDATOR_PATH = REPOSITORY / "bin/check-material-infobar-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/infobar-severity-policy.json"

SPEC = importlib.util.spec_from_file_location("check_material_infobar_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class MaterialInfobarContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.tracked_files = sorted(
            {cls.registry["source"], cls.registry["header"], cls.registry["ui_file"]}
        )
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

    # -- scaffolding ------------------------------------------------------------------------------
    def run_validate(
        self,
        *,
        files: dict[str, str] | None = None,
        registry: dict | None = None,
    ) -> None:
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

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    def test_registry_maps_all_four_severities(self) -> None:
        self.assertEqual(
            tuple(entry["type"] for entry in self.registry["severities"]),
            VALIDATOR.SEVERITY_TYPES,
        )

    # -- color routing ----------------------------------------------------------------------------
    def test_rejects_reintroduced_info_hex_literal(self) -> None:
        source = self.registry["source"]
        files = self.mutated(
            source,
            "rSettings.GetHighlightColor().getBColor()",
            "basegfx::BColor(0.0, 0.3, 0.5)",
        )
        self.assert_fails("must not use raw color literals", files=files)

    def test_rejects_reintroduced_color_object_literal(self) -> None:
        # Evasion guard: an infobar-local hardcode expressed as a Color(...) object literal (hex
        # or decimal r,g,b) rather than the basegfx::BColor float triple must still fail closed.
        source = self.registry["source"]
        for replacement in (
            "Color(0x004785).getBColor()",
            "Color(0x00, 0x47, 0x85).getBColor()",
            "Color(0, 71, 133).getBColor()",
        ):
            with self.subTest(replacement=replacement):
                files = self.mutated(
                    source,
                    "rSettings.GetHighlightColor().getBColor()",
                    replacement,
                )
                self.assert_fails("must not use raw color literals", files=files)

    def test_rejects_missing_warning_container_role(self) -> None:
        source = self.registry["source"]
        files = self.mutated(
            source,
            "rSettings.GetWarningColor().getBColor()",
            "rSettings.GetAccentColor().getBColor()",
        )
        self.assert_fails("WARNING severity must wire", files=files)

    def test_rejects_success_not_reusing_notification_green(self) -> None:
        source = self.registry["source"]
        files = self.mutated(
            source,
            "NotificationTheme::ResolveAccentColor(",
            "NotificationThemeX::ResolveAccentColor(",
        )
        self.assert_fails("SUCCESS severity must wire", files=files)

    def test_rejects_dropped_high_contrast_bypass(self) -> None:
        source = self.registry["source"]
        files = self.mutated(
            source,
            "rSettings.GetLightColor().getBColor()",
            "rSettings.GetWindowColor().getBColor()",
        )
        self.assert_fails("high-contrast bypass marker", files=files)

    # -- corner-container radius ------------------------------------------------------------------
    def test_rejects_missing_rounded_paint(self) -> None:
        source = self.registry["source"]
        files = self.mutated(
            source,
            "rRenderContext.DrawRect(aRect, nCornerContainerRadius, nCornerContainerRadius)",
            "rRenderContext.DrawRect(aRect)",
        )
        self.assert_fails("must paint the corner-container radius", files=files)

    def test_rejects_wrong_corner_radius(self) -> None:
        source = self.registry["source"]
        files = self.mutated(source, "? 0 : 12", "? 0 : 8")
        self.assert_fails("must paint the corner-container radius", files=files)

    # -- announcement -----------------------------------------------------------------------------
    def test_rejects_missing_announcement_call(self) -> None:
        source = self.registry["source"]
        files = self.mutated(source, "set_accessible_name(", "set_accessible_description(")
        self.assert_fails("must build the polite live announcement", files=files)

    def test_rejects_non_notification_accessible_role(self) -> None:
        ui_file = self.registry["ui_file"]
        files = self.mutated(ui_file, ">notification</property>", ">alert</property>")
        self.assert_fails("must declare accessible-role", files=files)

    # -- .ui reference geometry -------------------------------------------------------------------
    def test_rejects_wrong_grid_padding(self) -> None:
        ui_file = self.registry["ui_file"]
        files = self.mutated(
            ui_file,
            '<property name="margin-top">12</property>',
            '<property name="margin-top">8</property>',
        )
        self.assert_fails("grid property", files=files)

    def test_rejects_wrong_leading_icon_size(self) -> None:
        ui_file = self.registry["ui_file"]
        files = self.mutated(
            ui_file,
            '<property name="pixel-size">20</property>',
            '<property name="pixel-size">24</property>',
        )
        self.assert_fails("pixel-size", files=files)

    def test_rejects_wrong_icon_text_gap(self) -> None:
        ui_file = self.registry["ui_file"]
        files = self.mutated(
            ui_file,
            '<property name="spacing">12</property>',
            '<property name="spacing">6</property>',
        )
        self.assert_fails("icon-text gap", files=files)

    # -- header wiring ----------------------------------------------------------------------------
    def test_rejects_missing_paint_override_declaration(self) -> None:
        header = self.registry["header"]
        files = self.mutated(header, "virtual void Paint(", "virtual void PaintUnused(")
        self.assert_fails("must declare", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_incomplete_severity_map(self) -> None:
        registry = self.registry_copy()
        registry["severities"] = registry["severities"][:3]
        self.assert_fails("exactly the four InfobarType severities", registry=registry)


if __name__ == "__main__":
    unittest.main()
