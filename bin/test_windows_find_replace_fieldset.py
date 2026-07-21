#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Find & Replace field-set validator (WIN-INP-006)."""

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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-find-replace-fieldset.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/find-replace-fieldset.json"

SPEC = importlib.util.spec_from_file_location("check_windows_find_replace_fieldset", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class FindReplaceFieldsetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.tracked_files = sorted(
            {cls.registry["ui_file"], cls.registry["header_file"], cls.registry["source_file"]}
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

    def removed(self, rel: str, needle: str) -> dict[str, str]:
        """Remove every occurrence of ``needle`` so the anchor count drops to zero."""
        source = self.originals[rel]
        self.assertGreaterEqual(source.count(needle), 1, f"expected {needle!r} in {rel}")
        return {rel: source.replace(needle, "")}

    def replaced(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertGreaterEqual(source.count(old), 1, f"expected {old!r} in {rel}")
        return {rel: source.replace(old, new)}

    def duplicated_line(self, rel: str, anchor: str) -> dict[str, str]:
        """Append a second copy of the line carrying ``anchor`` (proves exactly-one anchors)."""
        source = self.originals[rel]
        for line in source.splitlines():
            if anchor in line:
                return {rel: source + "\n" + line + "\n"}
        self.fail(f"anchor {anchor!r} not found in {rel}")

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- .ui composition --------------------------------------------------------------------------
    def test_rejects_missing_regex_builder_button(self) -> None:
        files = self.replaced(
            self.registry["ui_file"],
            'class="GtkButton" id="searchterm_regex_builder"',
            'class="GtkButton" id="searchterm_regex_builder_gone"',
        )
        self.assert_fails("regex builder", files=files)

    def test_rejects_find_field_without_entry(self) -> None:
        # Break the find combo's has-entry declaration only (the replace combo keeps its own).
        ui = self.originals[self.registry["ui_file"]]
        marker = '<object class="GtkComboBoxText" id="searchterm">'
        head, _, tail = ui.partition(marker)
        tail = tail.replace(
            '<property name="has-entry">True</property>',
            '<property name="has-entry">False</property>',
            1,
        )
        self.assert_fails("has-entry=True", files={self.registry["ui_file"]: head + marker + tail})

    def test_rejects_missing_replace_field(self) -> None:
        files = self.replaced(
            self.registry["ui_file"],
            'class="GtkComboBoxText" id="replaceterm"',
            'class="GtkComboBoxText" id="replaceterm_gone"',
        )
        self.assert_fails("replace field", files=files)

    def test_rejects_missing_matchcase_checkbox(self) -> None:
        files = self.replaced(
            self.registry["ui_file"],
            'class="GtkCheckButton" id="matchcase"',
            'class="GtkCheckButton" id="matchcase_gone"',
        )
        self.assert_fails("match-case", files=files)

    def test_rejects_result_summary_without_notification_role(self) -> None:
        files = self.replaced(
            self.registry["ui_file"],
            '<property name="AtkObject::accessible-role">notification</property>',
            '<property name="AtkObject::accessible-role">tooltip</property>',
        )
        self.assert_fails("notification", files=files)

    def test_rejects_emphasis_removed_from_action_set(self) -> None:
        files = self.removed(
            self.registry["ui_file"],
            '<class name="suggested-action"/>',
        )
        self.assert_fails("emphasis", files=files)

    def test_rejects_emphasis_moved_off_the_default_action(self) -> None:
        # Move the filled emphasis from Find Next (search) onto Replace All: two-way divergence
        # from the contract (emphasis must sit on exactly the declared, keyboard-default action).
        ui = self.originals[self.registry["ui_file"]]
        moved = ui.replace(
            "                    <style>\n"
            '                      <class name="suggested-action"/>\n'
            "                    </style>\n",
            "",
        )
        moved = moved.replace(
            '<object class="GtkButton" id="replaceall">',
            '<object class="GtkButton" id="replaceall">\n'
            "                    <style>\n"
            '                      <class name="suggested-action"/>\n'
            "                    </style>",
        )
        self.assert_fails("emphasis", files={self.registry["ui_file"]: moved})

    def test_rejects_emphasized_action_not_default(self) -> None:
        ui = self.originals[self.registry["ui_file"]]
        # Drop has-default from the emphasized Find Next button.
        marker = '<object class="GtkButton" id="search">'
        head, _, tail = ui.partition(marker)
        tail = tail.replace(
            '<property name="has-default">True</property>',
            "",
            1,
        )
        self.assert_fails("Enter default", files={self.registry["ui_file"]: head + marker + tail})

    # -- header -----------------------------------------------------------------------------------
    def test_rejects_missing_sync_helper_declaration(self) -> None:
        files = self.removed(self.registry["header_file"], "SyncRegexControllerFromToggle")
        self.assert_fails("SyncRegexControllerFromToggle", files=files)

    def test_rejects_missing_controller_member(self) -> None:
        files = self.replaced(
            self.registry["header_file"],
            "m_xSearchRegexController",
            "mxRenamedRegexOwner",
        )
        self.assert_fails("m_xSearchRegexController", files=files)

    # -- source wiring ----------------------------------------------------------------------------
    def test_rejects_find_field_not_bound_to_shared_controller(self) -> None:
        files = self.replaced(
            self.registry["source_file"],
            "*m_xSearchLB, *m_xSearchRegexBuilder",
            "*m_xSearchLB",
        )
        self.assert_fails("*m_xSearchLB, *m_xSearchRegexBuilder", files=files)

    def test_rejects_match_case_binding_removed(self) -> None:
        files = self.replaced(
            self.registry["source_file"],
            "if (!m_xMatchCaseCB->get_active())",
            "if (false)",
        )
        self.assert_fails("if (!m_xMatchCaseCB->get_active())", files=files)

    def test_rejects_whole_words_descriptor_removed(self) -> None:
        # SetWordOnly appears on two descriptor-write paths; remove them all.
        files = self.removed(
            self.registry["source_file"],
            "m_pSearchItem->SetWordOnly(GetCheckBoxValue(*m_xWordBtn))",
        )
        self.assert_fails("SetWordOnly", files=files)

    def test_rejects_regexp_descriptor_removed(self) -> None:
        files = self.removed(self.registry["source_file"], "m_pSearchItem->SetRegExp(true)")
        self.assert_fails("SetRegExp(true)", files=files)

    def test_rejects_regexp_controller_sync_removed(self) -> None:
        files = self.replaced(
            self.registry["source_file"],
            "m_xRegExpBtn->set_active(rState.Mode ==",
            "m_xRegExpBtn->set_active(false && rState.Mode ==",
        )
        self.assert_fails("m_xRegExpBtn->set_active(rState.Mode ==", files=files)

    def test_rejects_duplicate_regexp_controller_sync(self) -> None:
        # A second sync path would mean a duplicated/forked matcher; the anchor must be unique.
        files = self.duplicated_line(
            self.registry["source_file"], "m_xRegExpBtn->set_active(rState.Mode =="
        )
        self.assert_fails("exactly 1", files=files)

    def test_rejects_loop_breaker_guard_removed(self) -> None:
        files = self.replaced(
            self.registry["source_file"],
            "if (aState.Mode != eMode)",
            "if (true)",
        )
        self.assert_fails("if (aState.Mode != eMode)", files=files)

    def test_rejects_missing_composition_marker(self) -> None:
        files = self.removed(
            self.registry["source_file"], "WIN-INP-006 Material Find & Replace field set"
        )
        self.assert_fails("WIN-INP-006 Material Find & Replace field set", files=files)

    def test_rejects_missing_result_summary_setter(self) -> None:
        files = self.removed(self.registry["source_file"], "void SvxSearchDialog::SetSearchLabel(")
        self.assert_fails("SetSearchLabel", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_missing_required_option(self) -> None:
        registry = self.registry_copy()
        registry["options"] = [o for o in registry["options"] if o["option"] != "whole-words"]
        self.assert_fails("missing", registry=registry)

    def test_rejects_emphasized_action_not_in_action_set(self) -> None:
        registry = self.registry_copy()
        registry["emphasized_action_id"] = "nonesuch"
        self.assert_fails("not an action id", registry=registry)

    def test_rejects_undocumented_live_preview_deferral(self) -> None:
        registry = self.registry_copy()
        registry["supplementary_live_preview"]["status"] = "present"
        self.assert_fails("status 'deferred'", registry=registry)

    def test_rejects_empty_live_preview_reason(self) -> None:
        registry = self.registry_copy()
        registry["supplementary_live_preview"]["reason"] = "  "
        self.assert_fails("non-empty reason", registry=registry)

    def test_rejects_wrong_inventory_id(self) -> None:
        registry = self.registry_copy()
        registry["inventory_id"] = "WIN-INP-005"
        self.assert_fails("WIN-INP-006", registry=registry)


if __name__ == "__main__":
    unittest.main()
