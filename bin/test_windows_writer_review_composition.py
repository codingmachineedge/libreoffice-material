#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Material Writer review-composition contract."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-writer-review-composition.py"
SPEC = importlib.util.spec_from_file_location("check_windows_writer_review_composition", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CHANGES = "sw/uiconfig/swriter/toolbar/changes.xml"
WWS = "officecfg/registry/data/org/openoffice/Office/UI/WriterWindowState.xcu"
SIDEBAR = "officecfg/registry/data/org/openoffice/Office/UI/Sidebar.xcu"
FACTORY = "sw/source/uibase/sidebar/SwPanelFactory.cxx"
COMMENTS = "sw/source/uibase/sidebar/CommentsPanel.cxx"
COMMENTS_UI = "sw/uiconfig/swriter/ui/commentspanel.ui"
REDLN = "sw/source/uibase/misc/redlndlg.cxx"


class WriterReviewCompositionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def assert_mutation_changed(self, path: str, text: str) -> None:
        self.assertNotEqual(self.contents[path], text, "mutation anchor did not match")

    def deck(self, registry: dict, sid: str) -> dict:
        return next(d for d in registry["decks"] if d["surface_id"] == sid)

    # -- baseline ----------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- Track Changes toolbar --------------------------------------------
    def test_toolbar_command_drift_fails(self) -> None:
        source = self.contents[CHANGES].replace(
            'xlink:href=".uno:AcceptTrackedChange"', 'xlink:href=".uno:AcceptTrackedChangeX"', 1
        )
        self.assert_mutation_changed(CHANGES, source)
        errors = self.failures(contents=self.with_content(CHANGES, source))
        self.assertTrue(any("toolbar:sequence" in e and "command drift" in e for e in errors), errors)

    def test_toolbar_separator_removed_fails(self) -> None:
        source = self.contents[CHANGES].replace(" <toolbar:toolbarseparator/>\n", "", 1)
        self.assert_mutation_changed(CHANGES, source)
        errors = self.failures(contents=self.with_content(CHANGES, source))
        self.assertTrue(
            any("composition drift" in e or "toolbar:sequence:length" in e for e in errors), errors
        )

    def test_toolbar_design_core_hidden_fails(self) -> None:
        source = self.contents[CHANGES].replace(
            '<toolbar:toolbaritem xlink:href=".uno:ShowTrackedChanges"/>',
            '<toolbar:toolbaritem xlink:href=".uno:ShowTrackedChanges" toolbar:visible="false"/>',
            1,
        )
        self.assert_mutation_changed(CHANGES, source)
        errors = self.failures(contents=self.with_content(CHANGES, source))
        self.assertTrue(any("design_core" in e and "present but hidden" in e for e in errors), errors)

    def test_toolbar_registration_marker_missing_fails(self) -> None:
        source = self.contents[WWS].replace(
            "private:resource/toolbar/changes", "private:resource/toolbar/tracked"
        )
        self.assert_mutation_changed(WWS, source)
        errors = self.failures(contents=self.with_content(WWS, source))
        self.assertTrue(any("toolbar:registration:marker missing" in e for e in errors), errors)

    # -- Comments deck -----------------------------------------------------
    def test_comments_registration_marker_missing_fails(self) -> None:
        source = self.contents[SIDEBAR].replace(
            "private:resource/toolpanel/SwPanelFactory/CommentsPanel",
            "private:resource/toolpanel/SwPanelFactory/Annotations",
        )
        self.assert_mutation_changed(SIDEBAR, source)
        errors = self.failures(contents=self.with_content(SIDEBAR, source))
        self.assertTrue(
            any("deck[writer.review.comments]:registration:marker missing" in e for e in errors), errors
        )

    def test_comments_factory_dispatch_missing_fails(self) -> None:
        source = self.contents[FACTORY].replace(
            'rsResourceURL.endsWith("/CommentsPanel")', 'rsResourceURL.endsWith("/CommentsPanelX")', 1
        )
        self.assert_mutation_changed(FACTORY, source)
        errors = self.failures(contents=self.with_content(FACTORY, source))
        self.assertTrue(
            any("deck[writer.review.comments]:factory:dispatch missing" in e for e in errors), errors
        )

    def test_comments_create_call_missing_fails(self) -> None:
        source = self.contents[FACTORY].replace(
            "sw::sidebar::CommentsPanel::Create", "sw::sidebar::CommentsPanelZ::Create", 1
        )
        self.assert_mutation_changed(FACTORY, source)
        errors = self.failures(contents=self.with_content(FACTORY, source))
        self.assertTrue(
            any("deck[writer.review.comments]:factory:create call missing" in e for e in errors), errors
        )

    def test_comments_weld_marker_missing_fails(self) -> None:
        source = self.contents[COMMENTS].replace(
            'weld_combo_box("filter_author")', 'weld_combo_box("filter_authorX")', 1
        )
        self.assert_mutation_changed(COMMENTS, source)
        errors = self.failures(contents=self.with_content(COMMENTS, source))
        self.assertTrue(any("weld marker missing in code" in e for e in errors), errors)

    def test_comment_widget_weld_marker_missing_fails(self) -> None:
        # weld_expander("expander") is bound in more than one place; remove them all
        # so the marker is truly absent (the contract only requires >= 1 occurrence).
        source = self.contents[COMMENTS].replace(
            'weld_expander("expander")', 'weld_expander("expanderX")'
        )
        self.assert_mutation_changed(COMMENTS, source)
        errors = self.failures(contents=self.with_content(COMMENTS, source))
        self.assertTrue(any("widget expander:weld marker missing" in e for e in errors), errors)

    def test_comments_ui_id_missing_fails(self) -> None:
        source = self.contents[COMMENTS_UI].replace('id="filter_author"', 'id="filter_authorX"', 1)
        self.assert_mutation_changed(COMMENTS_UI, source)
        errors = self.failures(contents=self.with_content(COMMENTS_UI, source))
        self.assertTrue(any("widget filter_author:id missing from" in e for e in errors), errors)

    def test_comments_ui_load_missing_fails(self) -> None:
        source = self.contents[COMMENTS].replace(
            "modules/swriter/ui/commentspanel.ui", "modules/swriter/ui/commentspanelX.ui", 1
        )
        self.assert_mutation_changed(COMMENTS, source)
        errors = self.failures(contents=self.with_content(COMMENTS, source))
        self.assertTrue(any("ui load marker missing" in e for e in errors), errors)

    # -- Manage Changes deck (shared svx mount) ---------------------------
    def test_manage_changes_shared_mount_missing_fails(self) -> None:
        # The whole point of the Manage Changes deck: it MOUNTS the shared svx control.
        source = self.contents[REDLN].replace(
            "new SvxAcceptChgCtr(pContentArea)", "new SomeOtherWriterWidget(pContentArea)", 1
        )
        self.assert_mutation_changed(REDLN, source)
        errors = self.failures(contents=self.with_content(REDLN, source))
        self.assertTrue(
            any("deck[writer.review.manage-changes]:shared_mount:marker missing" in e for e in errors),
            errors,
        )

    def test_manage_changes_factory_create_call_missing_fails(self) -> None:
        source = self.contents[FACTORY].replace(
            "std::make_unique<SwRedlineAcceptPanel>(pParent)",
            "std::make_unique<SomeOtherPanel>(pParent)",
            1,
        )
        self.assert_mutation_changed(FACTORY, source)
        errors = self.failures(contents=self.with_content(FACTORY, source))
        self.assertTrue(
            any("deck[writer.review.manage-changes]:factory:create call missing" in e for e in errors),
            errors,
        )

    def test_manage_changes_ui_load_missing_fails(self) -> None:
        source = self.contents[REDLN].replace(
            "modules/swriter/ui/managechangessidebar.ui",
            "modules/swriter/ui/managechangessidebarX.ui",
            1,
        )
        self.assert_mutation_changed(REDLN, source)
        errors = self.failures(contents=self.with_content(REDLN, source))
        self.assertTrue(any("ui load marker missing" in e for e in errors), errors)

    # -- registry integrity ------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_deck_runtime_verified_true_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.deck(registry, "writer.review.comments")["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)

    def test_missing_required_deck_fails(self) -> None:
        registry = copy.deepcopy(self.registry)
        self.deck(registry, "writer.review.manage-changes")["surface_id"] = "renamed"
        errors = self.failures(registry=registry)
        self.assertTrue(any("missing required writer.review.manage-changes" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
