#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material sidebar-rail validator."""

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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-sidebar-rail.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/sidebar-rail.json"

SPEC = importlib.util.spec_from_file_location("check_windows_sidebar_rail", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class SidebarRailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.tracked_files = [
            cls.registry["theme_header"],
            cls.registry["theme_source"],
            cls.registry["tabbar_source"],
            cls.registry["controller_source"],
        ]
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

    # -- Theme header -----------------------------------------------------------------------------
    def test_rejects_missing_enum_slot(self) -> None:
        files = self.mutated(
            self.registry["theme_header"],
            "        Color_TabItemFocusRing,\n",
            "",
        )
        self.assert_fails("must declare the rail Theme enum slot Color_TabItemFocusRing", files=files)

    def test_rejects_missing_metric_enum_slot(self) -> None:
        files = self.mutated(
            self.registry["theme_header"],
            "        Int_TabBarRailWidth,\n",
            "",
        )
        self.assert_fails("must declare the rail Theme enum slot Int_TabBarRailWidth", files=files)

    # -- Theme source: registration / classification / values ------------------------------------
    def test_rejects_missing_property_classification(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "        case Int_TabItemIconSize:\n",
            "",
        )
        self.assert_fails("classify Int_TabItemIconSize in GetPropertyType", files=files)

    def test_rejects_missing_name_map_registration(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            '    maPropertyNameToIdMap[u"Int_TabItemGap"_ustr]=Int_TabItemGap;\n',
            "",
        )
        self.assert_fails("register the name->id map entry for Int_TabItemGap", files=files)

    def test_rejects_wrong_metric_literal(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "maPropertyIdToNameMap[Int_TabBarRailWidth],\n            Any(sal_Int32(48)));",
            "maPropertyIdToNameMap[Int_TabBarRailWidth],\n            Any(sal_Int32(50)));",
        )
        self.assert_fails(
            "set Int_TabBarRailWidth to the density-invariant literal 48 in UpdateTheme",
            files=files,
        )

    def test_rejects_wrong_color_getter(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "rStyle.GetActiveTabColor().GetRGBColor()",
            "rStyle.GetFaceColor().GetRGBColor()",
        )
        self.assert_fails(
            "set Color_TabItemActiveBackground from rStyle.GetActiveTabColor() in UpdateTheme",
            files=files,
        )

    # -- TabBar: guarded consumption --------------------------------------------------------------
    def test_rejects_commented_out_rail_width(self) -> None:
        # Comment-only wiring must fail: the checker strips C++ comments first.
        files = self.mutated(
            self.registry["tabbar_source"],
            "        return Theme::GetInteger(Theme::Int_TabBarRailWidth);\n",
            "        return 0; //Theme::GetInteger(Theme::Int_TabBarRailWidth);\n",
        )
        self.assert_fails("GetDefaultWidth must return the rail-width metric", files=files)

    def test_rejects_removed_material_guard_env(self) -> None:
        files = self.mutated(
            self.registry["tabbar_source"],
            '"VCL_DRAW_WIDGETS_FROM_FILE"',
            '"DISABLED_RAIL_GUARD"',
        )
        self.assert_fails("gate the rail treatment on the Material draw path", files=files)

    def test_rejects_missing_button_geometry(self) -> None:
        files = self.mutated(
            self.registry["tabbar_source"],
            "            item->mxButton->set_size_request(nButtonSize, nButtonSize);\n",
            "",
        )
        self.assert_fails("apply the rail button geometry from the Material metrics", files=files)

    # -- SidebarController: click-active-to-collapse ---------------------------------------------
    def test_rejects_removed_collapse_on_active(self) -> None:
        files = self.mutated(
            self.registry["controller_source"],
            "            // tdf#67627 Clicking a second time on a Deck icon will close the Deck\n"
            "            RequestCloseDeck();\n"
            "            return;\n",
            "            return;\n",
        )
        self.assert_fails("must keep the collapse marker", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_duplicate_slot(self) -> None:
        registry = self.registry_copy()
        registry["metrics"][1]["slot"] = registry["metrics"][0]["slot"]
        self.assert_fails("duplicate slot", registry=registry)

    def test_registry_value_drives_source_assertion(self) -> None:
        registry = self.registry_copy()
        registry["metrics"][0]["value"] = 999
        self.assert_fails(
            "set Int_TabBarRailWidth to the density-invariant literal 999", registry=registry
        )

    def test_rejects_state_token_without_backing_color_slot(self) -> None:
        registry = self.registry_copy()
        registry["states"][1]["fill"] = "tertiary-container"
        self.assert_fails("no rail colour slot provides", registry=registry)


if __name__ == "__main__":
    unittest.main()
