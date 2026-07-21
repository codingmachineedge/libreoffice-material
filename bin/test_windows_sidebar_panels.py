#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material sidebar deck & side panes validator."""

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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-sidebar-panels.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/sidebar-panels.json"

SPEC = importlib.util.spec_from_file_location("check_windows_sidebar_panels", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class SidebarPanelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.tracked_files = [
            cls.registry["theme_header"],
            cls.registry["theme_source"],
            cls.registry["deck_source"],
            cls.registry["deck_title_source"],
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

    def mutated_all(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertGreaterEqual(source.count(old), 1, f"expected {old!r} in {rel}")
        return {rel: source.replace(old, new)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- Theme header -----------------------------------------------------------------------------
    def test_rejects_missing_color_enum_slot(self) -> None:
        files = self.mutated(
            self.registry["theme_header"],
            "        Color_DeckTitleText,\n",
            "",
        )
        self.assert_fails("must declare the deck Theme enum slot Color_DeckTitleText", files=files)

    def test_rejects_missing_metric_enum_slot(self) -> None:
        files = self.mutated(
            self.registry["theme_header"],
            "        Int_DeckScrollbarThickness,\n",
            "",
        )
        self.assert_fails(
            "must declare the deck Theme enum slot Int_DeckScrollbarThickness", files=files
        )

    # -- Theme source: guard / registration / classification / values ----------------------------
    def test_rejects_removed_guard_helper(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "bool IsMaterialDeck()",
            "bool IsMaterialDeckX()",
        )
        self.assert_fails("must define the Material guard helper IsMaterialDeck()", files=files)

    def test_rejects_missing_property_classification(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "        case Int_DeckOverlayMinWidth:\n",
            "",
        )
        self.assert_fails("classify Int_DeckOverlayMinWidth in GetPropertyType", files=files)

    def test_rejects_missing_name_map_registration(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            '    maPropertyNameToIdMap[u"Int_DeckScrollbarThickness"_ustr]=Int_DeckScrollbarThickness;\n',
            "",
        )
        self.assert_fails(
            "register the name->id map entry for Int_DeckScrollbarThickness", files=files
        )

    def test_rejects_wrong_metric_literal(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "maPropertyIdToNameMap[Int_DeckScrollbarThickness],\n            Any(sal_Int32(12)));",
            "maPropertyIdToNameMap[Int_DeckScrollbarThickness],\n            Any(sal_Int32(13)));",
        )
        self.assert_fails(
            "set Int_DeckScrollbarThickness to the density-invariant literal 12 in UpdateTheme",
            files=files,
        )

    def test_rejects_wrong_color_getter(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "rStyle.GetWindowTextColor().GetRGBColor()",
            "rStyle.GetFaceColor().GetRGBColor()",
        )
        self.assert_fails(
            "set Color_DeckTitleText from rStyle.GetWindowTextColor() in UpdateTheme",
            files=files,
        )

    def test_rejects_unguarded_deck_surface(self) -> None:
        files = self.mutated_all(
            self.registry["theme_source"],
            "bMaterialDeck ? rStyle.GetWindowColor()",
            "true ? rStyle.GetWindowColor()",
        )
        self.assert_fails("must select the deck surface behind the Material guard", files=files)

    def test_rejects_missing_deck_surface_slot(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "        setPropertyValue(\n"
            "            maPropertyIdToNameMap[Color_DeckBackground],\n"
            "            Any(sal_Int32(aDeckSurfaceColor.GetRGBColor())));\n",
            "",
        )
        self.assert_fails("set the deck surface slot Color_DeckBackground in UpdateTheme", files=files)

    def test_rejects_unguarded_deck_padding(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "bMaterialDeck ? 14 : 0",
            "0",
        )
        self.assert_fails("must guard the deck content inset", files=files)

    def test_rejects_padding_slot_not_from_guarded_symbol(self) -> None:
        files = self.mutated(
            self.registry["theme_source"],
            "maPropertyIdToNameMap[Int_DeckLeftPadding],\n            Any(sal_Int32(nDeckContentPadding)));",
            "maPropertyIdToNameMap[Int_DeckLeftPadding],\n            Any(sal_Int32(14)));",
        )
        self.assert_fails(
            "set Int_DeckLeftPadding to the guarded deck inset nDeckContentPadding in UpdateTheme",
            files=files,
        )

    # -- Deck: guarded 12px scrollbar + retained fill --------------------------------------------
    def test_rejects_commented_out_scrollbar(self) -> None:
        # Comment-only wiring must fail: the checker strips C++ comments first.
        files = self.mutated(
            self.registry["deck_source"],
            "        mxVerticalScrollBar->set_scroll_thickness(Theme::GetInteger(Theme::Int_DeckScrollbarThickness));\n",
            "        //mxVerticalScrollBar->set_scroll_thickness(Theme::GetInteger(Theme::Int_DeckScrollbarThickness));\n",
        )
        self.assert_fails("must apply the 12px Material scrollbar", files=files)

    def test_rejects_removed_deck_fill(self) -> None:
        files = self.mutated(
            self.registry["deck_source"],
            "    m_xContainer->set_background(Theme::GetColor(Theme::Color_DeckBackground));\n",
            "",
        )
        self.assert_fails("must keep the deck fill on Color_DeckBackground", files=files)

    # -- DeckTitleBar: guarded title role --------------------------------------------------------
    def test_rejects_missing_title_semibold(self) -> None:
        files = self.mutated(
            self.registry["deck_title_source"],
            "    aFont.SetWeight(WEIGHT_SEMIBOLD);\n",
            "",
        )
        self.assert_fails("must apply the deck title role: missing 'WEIGHT_SEMIBOLD'", files=files)

    # -- SidebarController: collapse + overlay degrade -------------------------------------------
    def test_rejects_removed_collapse_on_active(self) -> None:
        files = self.mutated(
            self.registry["controller_source"],
            "            // tdf#67627 Clicking a second time on a Deck icon will close the Deck\n"
            "            RequestCloseDeck();\n"
            "            return;\n",
            "            return;\n",
        )
        self.assert_fails("must keep the collapse marker", files=files)

    def test_rejects_removed_overlay_predicate(self) -> None:
        files = self.mutated(
            self.registry["controller_source"],
            "bool ShouldDeckOverlayCanvas(sal_Int32 nWindowWidth)",
            "bool ShouldDeckOverlayCanvasX(sal_Int32 nWindowWidth)",
        )
        self.assert_fails(
            "must define the below-medium overlay predicate ShouldDeckOverlayCanvas()", files=files
        )

    def test_rejects_removed_overlay_threshold(self) -> None:
        files = self.mutated(
            self.registry["controller_source"],
            "nWindowWidth < Theme::GetInteger(Theme::Int_DeckOverlayMinWidth);",
            "nWindowWidth < 0;",
        )
        self.assert_fails("must read the overlay threshold", files=files)

    def test_rejects_unconsumed_overlay_predicate(self) -> None:
        files = self.mutated(
            self.registry["controller_source"],
            "        const bool bOverlayDegrade = ShouldDeckOverlayCanvas(nCanvasWidth);\n",
            "        const bool bOverlayDegrade = false;\n",
        )
        self.assert_fails("must consume the overlay predicate", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_duplicate_slot(self) -> None:
        registry = self.registry_copy()
        registry["metrics"][1]["slot"] = registry["metrics"][0]["slot"]
        self.assert_fails("duplicate slot", registry=registry)

    def test_registry_value_drives_source_assertion(self) -> None:
        registry = self.registry_copy()
        registry["metrics"][0]["value"] = 999
        self.assert_fails(
            "set Int_DeckScrollbarThickness to the density-invariant literal 999", registry=registry
        )

    def test_rejects_state_token_without_backing_color_slot(self) -> None:
        registry = self.registry_copy()
        registry["states"][0]["fill"] = "tertiary-container"
        self.assert_fails("no deck colour slot provides", registry=registry)


if __name__ == "__main__":
    unittest.main()
