#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Impress slide-show settings contract (WIN-IM-003).

Each test breaks exactly one composition or wiring guarantee against an in-memory copy of the tree
and asserts the checker fails closed, while the pristine production tree passes. The real
repository is never mutated: every mutation is applied to the ``contents`` map ``load_repository``
returns or to a deep copy of the registry.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-impress-slideshow-settings-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_impress_slideshow_settings_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

DIALOG = "sd/uiconfig/simpress/ui/presentationdialog.ui"
IMPL = "sd/source/ui/dlg/present.cxx"
HEADER = "sd/source/ui/inc/present.hxx"
CSV = "qa/windows-ui-contract/dialog-notification-policy.csv"


class ImpressSlideshowSettingsContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
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

    def without_content(self, path: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents.pop(path, None)
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

    # -- frame group composition (presentationdialog.ui) -----------------------
    def test_frame_group_reorder_fails(self) -> None:
        registry = self.registry_copy()
        groups = registry["frame_groups"]
        groups[0], groups[1] = groups[1], groups[0]
        errors = self.failures(registry=registry)
        self.assertTrue(any("frame_groups" in e and "id drift" in e for e in errors), errors)

    def test_frame_group_relabel_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            'context="presentationdialog|label1">Range</property>',
            'context="presentationdialog|label1">Ranges</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("frame_groups" in e and "label drift" in e for e in errors), errors)

    def test_frame_renamed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<object class="GtkFrame" id="frameremote">',
            '<object class="GtkFrame" id="frameremoteX">',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("frame_groups" in e and "id drift" in e for e in errors), errors)

    def test_frame_count_mismatch_fails(self) -> None:
        registry = self.registry_copy()
        registry["frame_groups"].append({"id": "frameSpurious", "label": "Spurious"})
        errors = self.failures(registry=registry)
        self.assertTrue(any("frame_groups:GtkFrame count" in e for e in errors), errors)

    # -- footer (presentationdialog.ui) ----------------------------------------
    def test_footer_response_drift_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<action-widget response="-5">ok</action-widget>',
            '<action-widget response="-99">ok</action-widget>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:action_widgets" in e and "drift" in e for e in errors), errors)

    def test_footer_default_removed_fails(self) -> None:
        contents = self.replace_once(
            DIALOG,
            '<property name="has-default">True</property>',
            '<property name="has-default">False</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary" in e and "has-default" in e for e in errors), errors)

    def test_footer_primary_label_drift_fails(self) -> None:
        contents = self.replace_once(DIALOG, ">_OK</property>", ">O_K</property>")
        errors = self.failures(contents=contents)
        self.assertTrue(any("footer:primary:label" in e for e in errors), errors)

    def test_dialog_ui_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(DIALOG))
        self.assertTrue(any("dialog_ui:file missing" in e for e in errors), errors)

    # -- present.cxx wiring markers --------------------------------------------
    def test_wiring_pattern_removed_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            "m_xLbDias->set_sensitive( m_xRbtAtDia->get_active() );",
            "m_xLbDias->set_sensitive( true );",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("wiring_markers:range-radio-enable" in e and "wiring drifted" in e for e in errors),
            errors,
        )

    def test_wiring_pattern_commented_out_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            "m_xCbxAlwaysOnTop->set_active(false);",
            "// m_xCbxAlwaysOnTop->set_active(false);",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any(
                "wiring_markers:windowed-alwaysontop-forced-off" in e and "wiring drifted" in e
                for e in errors
            ),
            errors,
        )

    def test_wiring_method_renamed_fails(self) -> None:
        contents = self.replace_once(
            IMPL,
            "IMPL_LINK_NOARG(SdStartPresentationDlg, ChangeRangeHdl, weld::Toggleable&, void)",
            "IMPL_LINK_NOARG(SdStartPresentationDlg, ChangeRangeHdlX, weld::Toggleable&, void)",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("wiring_markers:range-radio-enable" in e and "not found" in e for e in errors),
            errors,
        )

    def test_impl_source_missing_fails(self) -> None:
        errors = self.failures(contents=self.without_content(IMPL))
        self.assertTrue(any("wiring_markers:impl_source file missing" in e for e in errors), errors)

    # -- present.hxx header markers --------------------------------------------
    def test_header_marker_removed_fails(self) -> None:
        contents = self.replace_once(HEADER, "void ChangePause();", "void ChangePauseX();")
        errors = self.failures(contents=contents)
        self.assertTrue(any("header_markers" in e and "ChangePause" in e for e in errors), errors)

    # -- shared CSV modal exclusion (read-only) --------------------------------
    def test_modal_exclusion_policy_desync_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            "sd/uiconfig/simpress/ui/presentationdialog.ui,PresentationDialog,GtkDialog,native-exclusion",
            "sd/uiconfig/simpress/ui/presentationdialog.ui,PresentationDialog,GtkDialog,route-notification",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("modal_exclusion" in e and "PresentationDialog" in e and "policy is" in e for e in errors),
            errors,
        )

    def test_modal_exclusion_row_removed_fails(self) -> None:
        contents = self.replace_once(
            CSV,
            'sd/uiconfig/simpress/ui/presentationdialog.ui,PresentationDialog,GtkDialog,'
            'native-exclusion,,"collects input, kept modal (router Classify: KeepModal)"\n',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("modal_exclusion" in e and "PresentationDialog" in e and "absent" in e for e in errors),
            errors,
        )

    # -- honest carve-outs -----------------------------------------------------
    def test_carveout_status_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["carveouts"]["playback_engine"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("carveouts:playback_engine:status must stay 'specified'" in e for e in errors), errors
        )

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

    def test_inventory_row_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["inventory_row"] = "WIN-IM-999"
        errors = self.failures(registry=registry)
        self.assertIn("registry:inventory_row:must be WIN-IM-003", errors)


if __name__ == "__main__":
    unittest.main()
