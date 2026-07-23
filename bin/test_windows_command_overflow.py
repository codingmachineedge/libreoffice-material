#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the command-overflow presence contract (WIN-SHL-002).

Every one of the eight presence markers gets a rejecting mutation, plus the honesty
invariant (``satisfies_material_gate`` must stay false) and registry integrity. A green
baseline proves the production tree currently passes. The function-anchored markers are
broken by renaming the *qualified* definition (``ToolBox::Method`` / ``ToolBarManager::
Method``) -- callers use the unqualified name, so the rename unambiguously removes only
the definition the marker pins.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-command-overflow.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_command_overflow", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

TB2 = "vcl/source/window/toolbox2.cxx"
TB = "vcl/source/window/toolbox.cxx"
TM = "framework/source/uielement/toolbarmanager.cxx"


class CommandOverflowContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def mutate(self, path: str, old: str, new: str, *, count: int = -1) -> dict[str, str]:
        source = self.contents[path]
        mutated = source.replace(old, new) if count < 0 else source.replace(old, new, count)
        self.assertNotEqual(source, mutated, f"mutation target not found in {path}: {old!r}")
        contents = dict(self.contents)
        contents[path] = mutated
        return contents

    def assert_marker_fails(self, marker_id: str, contents: dict[str, str]) -> None:
        errors = self.failures(contents=contents)
        self.assertTrue(
            any(f"code_markers:{marker_id}:" in e for e in errors),
            f"expected {marker_id} to fail closed; got {errors}",
        )

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- per-marker rejecting mutations -----------------------------------
    def test_isclipped_invariant_broken_fails(self) -> None:
        # Drop the "stays visible" half of the clipped predicate: overflow would then be
        # indistinguishable from removal.
        contents = self.mutate(
            TB2,
            "meType == ToolBoxItemType::BUTTON && mbVisible && maRect.IsEmpty()",
            "meType == ToolBoxItemType::BUTTON",
            count=1,
        )
        self.assert_marker_fails("impltoolitem-isclipped-keeps-visible", contents)

    def test_isitemclipped_renamed_fails(self) -> None:
        contents = self.mutate(
            TB2, "ToolBox::IsItemClipped(", "ToolBox::IsItemClipped_MUT(", count=1
        )
        self.assert_marker_fails("toolbox-isitemclipped-query", contents)

    def test_hasclippeditems_renamed_fails(self) -> None:
        contents = self.mutate(
            TB2, "ToolBox::ImplHasClippedItems()", "ToolBox::ImplHasClippedItems_MUT()", count=1
        )
        self.assert_marker_fails("toolbox-implhasclippeditems-gate", contents)

    def test_updatecustommenu_renamed_fails(self) -> None:
        contents = self.mutate(
            TB2,
            "ToolBox::UpdateCustomMenu(PopupMenu* pMenu)",
            "ToolBox::UpdateCustomMenu_MUT(PopupMenu* pMenu)",
            count=1,
        )
        self.assert_marker_fails("toolbox-updatecustommenu-declared-order", contents)

    def test_updatecustommenu_clipped_branch_broken_fails(self) -> None:
        # Even without renaming, dropping the clipped-item test breaks declared-order
        # insertion of the overflow group.
        contents = self.mutate(TB2, "if( rItem.IsClipped() )", "if( false )", count=1)
        self.assert_marker_fails("toolbox-updatecustommenu-declared-order", contents)

    def test_highlight_cycle_renamed_fails(self) -> None:
        contents = self.mutate(
            TB, "ToolBox::ImplChangeHighlightUpDn(", "ToolBox::ImplChangeHighlightUpDn_MUT(", count=1
        )
        self.assert_marker_fails("toolbox-highlight-menubutton-in-sequence", contents)

    def test_drawmenubutton_gate_renamed_fails(self) -> None:
        contents = self.mutate(
            TB, "ToolBox::ImplDrawMenuButton(", "ToolBox::ImplDrawMenuButton_MUT(", count=1
        )
        self.assert_marker_fails("toolbox-drawmenubutton-gated", contents)

    def test_menubutton_wiring_comment_only_fails(self) -> None:
        # Comment out the vcl-to-framework joint: comment-stripped code no longer carries
        # it, proving comment-only wiring cannot satisfy the contract.
        contents = self.mutate(
            TM,
            "m_pToolBar->SetMenuButtonHdl( LINK( pManager, ToolBarManager, MenuButton ) );",
            "// m_pToolBar->SetMenuButtonHdl( LINK( pManager, ToolBarManager, MenuButton ) );",
            count=1,
        )
        self.assert_marker_fails("toolbarmanager-menubutton-wiring", contents)

    def test_filloverflow_renamed_fails(self) -> None:
        contents = self.mutate(
            TM,
            "ToolBarManager::FillOverflowToolbar(",
            "ToolBarManager::FillOverflowToolbar_MUT(",
            count=1,
        )
        self.assert_marker_fails("toolbarmanager-filloverflow-declared-order", contents)

    # -- honesty invariant -------------------------------------------------
    def test_material_gate_flip_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["satisfies_material_gate"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("satisfies_material_gate:must stay false" in e for e in errors), errors
        )

    def test_material_gate_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        del registry["satisfies_material_gate"]
        errors = self.failures(registry=registry)
        self.assertTrue(any("satisfies_material_gate:boolean required" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
    def test_marker_source_missing_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["code_markers"][0]["file"] = "vcl/source/window/does-not-exist.cxx"
        contents = dict(self.contents)
        contents.pop(TB2, None)
        errors = self.failures(registry=registry, contents=contents)
        self.assertTrue(any(":source " in e and "missing" in e for e in errors), errors)

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


if __name__ == "__main__":
    unittest.main()
