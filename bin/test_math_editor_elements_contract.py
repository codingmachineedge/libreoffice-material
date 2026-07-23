#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Math editor/elements validator.

Every pinned fact in ``qa/windows-ui-contract/math-editor-elements.json`` is
mutation-tested: the production tree passes, and the multilineeditbox token set,
the editwindow/sidebarelements .ui bindings, the by-name builder wiring, the
single shared SmElementsControl class and the closed ordered category list all
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
VALIDATOR_PATH = REPOSITORY / "bin/check-math-editor-elements-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/math-editor-elements.json"

SPEC = importlib.util.spec_from_file_location("check_math_editor_elements_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class MathEditorElementsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        tracked: set[str] = {cls.registry["definition_file"]}
        for obj in cls.registry["ui_objects"]:
            tracked.add(obj["ui"])
        for marker in cls.registry["markers"]:
            tracked.add(marker["source"])
        tracked.add(cls.registry["shared_control_header"]["header"])
        tracked.add(cls.registry["category_list"]["source"])
        tracked.add(cls.registry["category_list"]["strings_file"])
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

    # -- multilineeditbox part ----------------------------------------------------------------
    def test_rejects_token_drift(self) -> None:
        registry = self.registry_copy()
        registry["definition_part"]["states"][1]["tokens"]["stroke"] = "@wrong"
        self.assert_fails("token drift: stroke is '@primary', expected '@wrong'", registry=registry)

    def test_rejects_unmatched_focused_state(self) -> None:
        # The focused-state signature must match exactly; a stricter declared
        # signature that no compiled <state> carries fails closed.
        registry = self.registry_copy()
        registry["definition_part"]["states"][1]["attrs"]["pressed"] = "true"
        self.assert_fails("multilineeditbox/Entire:focused: no <state> matching", registry=registry)

    # -- .ui objects --------------------------------------------------------------------------
    def test_rejects_scroll_policy_drift(self) -> None:
        files = self.mutated(
            "starmath/uiconfig/smath/ui/editwindow.ui",
            '<property name="vscrollbar-policy">always</property>',
            '<property name="vscrollbar-policy">never</property>',
        )
        self.assert_fails("property 'vscrollbar-policy' is 'never', expected 'always'", files=files)

    def test_rejects_missing_editview(self) -> None:
        files = self.mutated(
            "starmath/uiconfig/smath/ui/editwindow.ui",
            'id="editview"',
            'id="editviewX"',
        )
        self.assert_fails("object id 'editview' not found", files=files)

    def test_rejects_iconview_activation_drift(self) -> None:
        files = self.mutated(
            "starmath/uiconfig/smath/ui/sidebarelements_math.ui",
            '<property name="activate-on-single-click">True</property>',
            '<property name="activate-on-single-click">False</property>',
        )
        self.assert_fails(
            "property 'activate-on-single-click' is 'False', expected 'True'", files=files
        )

    def test_rejects_missing_deletemenu(self) -> None:
        files = self.mutated(
            "starmath/uiconfig/smath/ui/sidebarelements_math.ui",
            'id="deletemenu"',
            'id="deletemenuX"',
        )
        self.assert_fails("object id 'deletemenu' not found", files=files)

    # -- source markers -----------------------------------------------------------------------
    def test_rejects_scroll_binding_rename(self) -> None:
        files = self.mutated(
            "starmath/source/edit.cxx",
            'weld_scrolled_window(u"scrolledwindow"_ustr, true)',
            'weld_scrolled_window(u"otherwindow"_ustr, true)',
        )
        self.assert_fails("missing marker in code", files=files)

    def test_comment_only_view_binding_fails_closed(self) -> None:
        files = self.mutated(
            "starmath/source/edit.cxx",
            "mxTextControlWin.reset(new weld::CustomWeld(rBuilder, u\"editview\"_ustr",
            "// mxTextControlWin.reset(new weld::CustomWeld(rBuilder, u\"editview\"_ustr",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_panel_builder_id_rename(self) -> None:
        files = self.mutated(
            "starmath/source/SmElementsPanel.cxx",
            'weld_combo_box(u"categorylist"_ustr)',
            'weld_combo_box(u"otherlist"_ustr)',
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_shared_control_definition_rename(self) -> None:
        files = self.mutated(
            "starmath/source/ElementsDockingWindow.cxx",
            "const std::vector<TranslateId>& SmElementsControl::categories()",
            "const std::vector<TranslateId>& SmElementsControl::renamedCategories()",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_forked_shared_control_class(self) -> None:
        files = self.mutated(
            "starmath/inc/ElementsDockingWindow.hxx",
            "class SmElementsControl",
            "class RenamedControl",
        )
        self.assert_fails("shared_control_header: missing marker in code", files=files)

    # -- category list closure ----------------------------------------------------------------
    def test_rejects_category_reorder(self) -> None:
        registry = self.registry_copy()
        ids = registry["category_list"]["ordered_ids"]
        ids[1], ids[2] = ids[2], ids[1]
        self.assert_fails("missing or out of order in s_a5Categories", registry=registry)

    def test_rejects_extra_category_entry(self) -> None:
        files = self.mutated(
            "starmath/source/ElementsDockingWindow.cxx",
            "    RID_CATEGORY_USERDEFINED,",
            "    RID_CATEGORY_USERDEFINED,\n    RID_CATEGORY_SNUCK_IN,",
        )
        self.assert_fails("expected exactly 11 (closed list)", files=files)

    def test_rejects_category_not_translatable(self) -> None:
        files = self.mutated(
            "starmath/inc/strings.hrc",
            '#define RID_CATEGORY_RELATIONS              NC_("RID_CATEGORY_RELATIONS", "Relations" )',
            '#define RID_CATEGORY_RELATIONS "Relations"',
        )
        self.assert_fails("is not defined as an NC_() string", files=files)

    # -- registry integrity -------------------------------------------------------------------
    def test_rejects_expected_marker_count_drift(self) -> None:
        registry = self.registry_copy()
        registry["expected_markers"] = len(registry["markers"]) - 1
        self.assert_fails("expected_markers count drift", registry=registry)

    def test_rejects_top_level_runtime_verified_true(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        self.assert_fails("registry runtime_verified must be false", registry=registry)


if __name__ == "__main__":
    unittest.main()
