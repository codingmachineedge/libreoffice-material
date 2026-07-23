#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Math editor behavioural validator.

Every pinned primitive in ``qa/windows-ui-contract/math-editor.json`` is
mutation-tested: the production tree passes, and the placeholder ``<?>`` marks,
the SID dispatch, the error text+position pairing and non-destructive clear
path, the insertion focus-return, the panel emission, the F4/F3 accelerator +
command + menu bindings, the multilineeditbox token set and the anti-promotion
carve-out / gate invariants all fail closed when weakened (including comment-only
wiring, which the checker strips before matching).
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
VALIDATOR_PATH = REPOSITORY / "bin/check-math-editor-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/math-editor.json"

SPEC = importlib.util.spec_from_file_location("check_math_editor_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class MathEditorContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        tracked: set[str] = {cls.registry["definition_file"]}
        for marker in cls.registry["behavior_markers"]:
            tracked.add(marker["source"])
        bindings = cls.registry["command_bindings"]
        for block in ("accelerators", "commands", "menu"):
            tracked.add(bindings[block]["file"])
        cls.tracked_files = sorted(tracked)
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

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

    # -- production ---------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- definition part ----------------------------------------------------------------------
    def test_rejects_token_drift(self) -> None:
        registry = self.registry_copy()
        registry["definition_part"]["states"][0]["tokens"]["fill"] = "@wrong"
        self.assert_fails("token drift: fill is '@surface', expected '@wrong'", registry=registry)

    # -- behavioural primitives ---------------------------------------------------------------
    def test_rejects_removed_placeholder_literal(self) -> None:
        files = self.mutated(
            "starmath/source/edit.cxx",
            'aText.indexOf("<?>", nPos)',
            'aText.indexOf("<!>", nPos)',
        )
        self.assert_fails("missing marker in code", files=files)

    def test_comment_only_dispatch_fails_closed(self) -> None:
        files = self.mutated(
            "starmath/source/view.cxx",
            "pWin->SelNextMark();",
            "// pWin->SelNextMark();",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_error_text_decoupled_from_position(self) -> None:
        files = self.mutated(
            "starmath/source/view.cxx",
            "SetStatusText( pErrorDesc->m_aText )",
            "SetStatusText( OUString() )",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_markerror_selection_removed(self) -> None:
        files = self.mutated(
            "starmath/source/edit.cxx",
            "pEditView->SetSelection(ESelection(nRow, nCol - 1, nRow, nCol));",
            "// removed",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_removed_clear_path(self) -> None:
        files = self.mutated(
            "starmath/source/view.cxx",
            "ShowError( nullptr )",
            "ShowError( pKept )",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_insertion_placeholder_landing_removed(self) -> None:
        files = self.mutated(
            "starmath/source/edit.cxx",
            'string = string.replaceFirst("<?>", selected);',
            "// removed",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_panel_emission_removed(self) -> None:
        files = self.mutated(
            "starmath/source/ElementsDockingWindow.cxx",
            "maSelectHdlLink.Call(GetElementSource(id))",
            "maSelectHdlLink.Call(OUString())",
        )
        self.assert_fails("missing marker in code", files=files)

    # -- command bindings ---------------------------------------------------------------------
    def test_rejects_rebound_f4_accelerator(self) -> None:
        files = self.mutated(
            "officecfg/registry/data/org/openoffice/Office/Accelerators.xcu",
            "<value xml:lang=\"en-US\">.uno:NextMark</value>",
            "<value xml:lang=\"en-US\">.uno:NothingMark</value>",
        )
        self.assert_fails("accelerator 'F4' does not resolve to '.uno:NextMark'", files=files)

    def test_rejects_missing_command_node(self) -> None:
        files = self.mutated(
            "officecfg/registry/data/org/openoffice/Office/UI/MathCommands.xcu",
            '<node oor:name=".uno:NextMark" oor:op="replace">',
            '<node oor:name=".uno:GoneMark" oor:op="replace">',
        )
        self.assert_fails("command node '.uno:NextMark' missing", files=files)

    def test_rejects_missing_menu_item(self) -> None:
        files = self.mutated(
            "starmath/uiconfig/smath/menubar/menubar.xml",
            '<menu:menuitem menu:id=".uno:NextMark"/>',
            '<menu:menuitem menu:id=".uno:GoneMark"/>',
        )
        self.assert_fails("menu item '.uno:NextMark' missing", files=files)

    # -- honesty invariants -------------------------------------------------------------------
    def test_rejects_carve_out_promotion(self) -> None:
        registry = self.registry_copy()
        registry["material_carve_outs"][0]["status"] = "implemented"
        self.assert_fails("status 'implemented' must stay", registry=registry)

    def test_rejects_advances_m_true(self) -> None:
        registry = self.registry_copy()
        registry["advances_m"] = True
        self.assert_fails("advances_m must be false", registry=registry)

    def test_rejects_top_level_runtime_verified_true(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        self.assert_fails("registry runtime_verified must be false", registry=registry)

    def test_rejects_behavior_marker_count_drift(self) -> None:
        registry = self.registry_copy()
        registry["expected_behavior_markers"] = len(registry["behavior_markers"]) - 1
        self.assert_fails("expected_behavior_markers count drift", registry=registry)

    def test_rejects_gate_not_d(self) -> None:
        registry = self.registry_copy()
        registry["gate"] = "M"
        self.assert_fails("registry gate must be 'D'", registry=registry)


if __name__ == "__main__":
    unittest.main()
