#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Office file-picker contract (WIN-DLG-003).

Each test breaks exactly one composition guarantee against an in-memory copy of the tree (or a
deep copy of the registry) and asserts the checker fails closed, while the pristine production tree
passes. The real repository is never mutated.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-office-filepicker-contract.py"
SPEC = importlib.util.spec_from_file_location("check_windows_office_filepicker_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

CSV = VALIDATOR.CSV_PATH
PICKER_UI = "fpicker/uiconfig/ui/explorerfiledialog.ui"
IMPL = "fpicker/source/office/iodlg.cxx"
FILEDLGHELPER = "sfx2/source/dialog/filedlghelper.cxx"


class OfficeFilePickerContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(self, *, registry: dict | None = None, contents: dict[str, str] | None = None) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def replace_once(self, path: str, old: str, new: str) -> dict[str, str]:
        source = self.contents[path]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {path}")
        return self.with_content(path, source.replace(old, new, 1))

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- baseline --------------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- regions ---------------------------------------------------------------
    def test_region_widget_missing_fails(self) -> None:
        contents = self.replace_once(
            PICKER_UI, '<object class="GtkComboBoxText" id="current_path">', '<object class="GtkComboBoxText" id="current_pathX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("regions:breadcrumb-row" in e and "missing" in e for e in errors), errors)

    def test_region_binding_drift_fails(self) -> None:
        contents = self.replace_once(
            IMPL, 'weld_combo_box(u"file_type"_ustr)', 'weld_combo_box(u"file_typeX"_ustr)'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("regions:file-type-dropdown" in e and "weld binding" in e for e in errors), errors)

    # -- save-mode label swap --------------------------------------------------
    def test_save_mode_anchor_missing_fails(self) -> None:
        contents = self.replace_once(IMPL, "STR_EXPLORERFILE_BUTTONSAVE", "STR_EXPLORERFILE_BUTTONSTORE")
        errors = self.failures(contents=contents)
        self.assertTrue(any("save_mode_label_swap:anchor" in e for e in errors), errors)

    # -- overwrite message box -------------------------------------------------
    def test_overwrite_resid_missing_fails(self) -> None:
        contents = self.replace_once(IMPL, "STR_SVT_ALREADYEXISTOVERWRITE", "STR_SVT_OVERWRITE_RENAMED")
        errors = self.failures(contents=contents)
        self.assertTrue(any("message_box[overwrite-confirm]:resid" in e for e in errors), errors)

    def test_overwrite_buttons_drift_fails(self) -> None:
        contents = self.replace_once(IMPL, "VclButtonsType::YesNo", "VclButtonsType::OkCancel")
        errors = self.failures(contents=contents)
        self.assertTrue(any("message_box[overwrite-confirm]:buttons" in e for e in errors), errors)

    def test_overwrite_safe_default_removed_fails(self) -> None:
        contents = self.replace_once(IMPL, "run() != RET_YES", "run() == RET_YES")
        errors = self.failures(contents=contents)
        self.assertTrue(any("message_box[overwrite-confirm]:safe_default" in e for e in errors), errors)

    def test_overwrite_classification_invalid_fails(self) -> None:
        registry = self.registry_copy()
        registry["message_boxes"][0]["classification"] = "banana"
        errors = self.failures(registry=registry)
        self.assertTrue(any("message_box[overwrite-confirm]:classification" in e for e in errors), errors)

    def test_overwrite_routes_to_notification_fails(self) -> None:
        registry = self.registry_copy()
        registry["message_boxes"][0]["routes_to_notification"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("message_box[overwrite-confirm]:routes_to_notification" in e for e in errors), errors)

    # -- breadcrumb guard (the false-pin tripwire) -----------------------------
    def test_breadcrumb_reference_fails(self) -> None:
        contents = self.replace_once(
            IMPL, 'm_aIniKey = "FileDialog"', 'm_aIniKey = "FileDialog_breadcrumb"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("breadcrumb_guard" in e for e in errors), errors)

    # -- picker seam + cross-references ----------------------------------------
    def test_picker_seam_literal_missing_fails(self) -> None:
        contents = self.replace_once(
            FILEDLGHELPER, '"com.sun.star.ui.dialogs.OfficeFilePicker"', '"com.sun.star.ui.dialogs.RenamedPicker"'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("picker_seam" in e and "OfficeFilePicker" in e for e in errors), errors)

    def test_cross_reference_policy_desync_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "fpicker/uiconfig/ui/explorerfiledialog.ui,ExplorerFileDialog,GtkDialog,native-exclusion",
            "fpicker/uiconfig/ui/explorerfiledialog.ui,ExplorerFileDialog,GtkDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("cross_references" in e and "ExplorerFileDialog" in e and "policy is" in e for e in errors), errors)

    # -- registry integrity ----------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)


if __name__ == "__main__":
    unittest.main()
