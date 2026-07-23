#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Mutation regressions for the Find & Replace dialog closure contract (WIN-DLG-005).

Each test flips exactly one real anchor -- the modeless base-class marker, one of the four satellite
cross-checks, the router/CSV agreement, or the Replace-All one-shot flag -- and asserts the checker
fails closed, plus one clean-pass test.  All in-process, no build, no runtime.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-find-replace-dialog-contract.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_find_replace_dialog_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

HEADER_FILE = VALIDATOR.HEADER_FILE
SOURCE_FILE = VALIDATOR.SOURCE_FILE
UI_FILE = VALIDATOR.UI_FILE

BASE = VALIDATOR.load_context(REPOSITORY)


def make_context(
    *,
    registry=None,
    fieldset=None,
    integrations=None,
    producer_policy=None,
    csv_entries=None,
    contents=None,
    rerun_fieldset=None,
    rerun_foundation=None,
):
    return VALIDATOR.Context(
        registry if registry is not None else copy.deepcopy(BASE.registry),
        fieldset if fieldset is not None else copy.deepcopy(BASE.fieldset),
        integrations if integrations is not None else copy.deepcopy(BASE.integrations),
        producer_policy if producer_policy is not None else copy.deepcopy(BASE.producer_policy),
        csv_entries if csv_entries is not None else list(BASE.csv_entries),
        contents if contents is not None else dict(BASE.contents),
        BASE.router,
        rerun_fieldset if rerun_fieldset is not None else BASE.rerun_fieldset,
        rerun_foundation if rerun_foundation is not None else BASE.rerun_foundation,
    )


def _replace_csv_row(**changes):
    entries = []
    for entry in BASE.csv_entries:
        if entry.key.ui_path == UI_FILE and entry.key.object_id == "FindReplaceDialog":
            entries.append(dataclasses.replace(entry, **changes))
        else:
            entries.append(entry)
    return entries


class FindReplaceDialogContractTest(unittest.TestCase):
    def failures(self, context) -> list[str]:
        return VALIDATOR.check(context)

    # -- Clean pass ----------------------------------------------------------

    def test_production_contract_is_clean(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures(make_context()))

    # -- Registry schema -----------------------------------------------------

    def test_registry_inventory_id_is_pinned(self) -> None:
        registry = copy.deepcopy(BASE.registry)
        registry["inventory_id"] = "WIN-DLG-999"
        self.assertTrue(
            any("inventory_id:must be WIN-DLG-005" in e for e in self.failures(make_context(registry=registry)))
        )

    # -- Modeless base class (the one fact this row adds) --------------------

    def test_modeless_marker_must_exist_in_header(self) -> None:
        marker = BASE.registry["modeless_base_class"]["marker"]
        contents = dict(BASE.contents)
        contents[HEADER_FILE] = contents[HEADER_FILE].replace(
            marker,
            "class SVX_DLLPUBLIC SvxSearchDialog final : public GenericDialogController",
            1,
        )
        self.assertTrue(
            any("modeless-base" in e for e in self.failures(make_context(contents=contents)))
        )

    def test_registry_marker_must_pin_modeless_base(self) -> None:
        registry = copy.deepcopy(BASE.registry)
        registry["modeless_base_class"]["marker"] = (
            "class SVX_DLLPUBLIC SvxSearchDialog final : public GenericDialogController"
        )
        self.assertTrue(
            any(
                "must pin SfxModelessDialogController" in e
                for e in self.failures(make_context(registry=registry))
            )
        )

    # -- Satellite 1: fieldset reuse (WIN-INP-006) --------------------------

    def test_broken_fieldset_reuse_fails_closed(self) -> None:
        def boom() -> None:
            raise RuntimeError("fieldset contract broke")

        self.assertTrue(
            any("fieldset-reuse" in e for e in self.failures(make_context(rerun_fieldset=boom)))
        )

    # -- Satellite 2: regex-search-integrations cross-field equality --------

    def test_regex_integration_member_drift_fails_closed(self) -> None:
        integrations = copy.deepcopy(BASE.integrations)
        for entry in integrations["integrations"]:
            if entry.get("coverage_id") == "document.find-replace":
                entry["entry_member"] = "m_xDriftedMember"
        self.assertTrue(
            any(
                "regex-integration:drift" in e
                for e in self.failures(make_context(integrations=integrations))
            )
        )

    def test_regex_integration_status_must_be_source_integrated(self) -> None:
        integrations = copy.deepcopy(BASE.integrations)
        for entry in integrations["integrations"]:
            if entry.get("coverage_id") == "document.find-replace":
                entry["status"] = "planned"
        self.assertTrue(
            any(
                "status must be source-integrated" in e
                for e in self.failures(make_context(integrations=integrations))
            )
        )

    # -- Satellite 3: shared regex-builder foundation reuse -----------------

    def test_broken_foundation_reuse_fails_closed(self) -> None:
        def boom() -> None:
            raise RuntimeError("shared engine broke")

        self.assertTrue(
            any("foundation-reuse" in e for e in self.failures(make_context(rerun_foundation=boom)))
        )

    # -- Satellite 4: notification producer ---------------------------------

    def test_missing_notification_producer_fails_closed(self) -> None:
        policy = copy.deepcopy(BASE.producer_policy)
        policy["producers"] = [
            p for p in policy["producers"] if p.get("id") != "srchdlg-replace-all-outcome"
        ]
        self.assertTrue(
            any(
                "notification-producer:no" in e
                for e in self.failures(make_context(producer_policy=policy))
            )
        )

    def test_notification_producer_function_drift_fails_closed(self) -> None:
        policy = copy.deepcopy(BASE.producer_policy)
        for producer in policy["producers"]:
            if producer.get("id") == "srchdlg-replace-all-outcome":
                producer["function"] = "wrongFunction"
        self.assertTrue(
            any(
                "srchdlg-replace-all-outcome function" in e
                for e in self.failures(make_context(producer_policy=policy))
            )
        )

    # -- Router / CSV classification (native-exclusion, must stay modal) ----

    def test_csv_reason_drift_fails_closed(self) -> None:
        entries = _replace_csv_row(exclusion_reason="a different reason")
        self.assertTrue(
            any(
                "CSV exclusion_reason drift" in e
                for e in self.failures(make_context(csv_entries=entries))
            )
        )

    def test_csv_policy_flip_to_notification_fails_closed(self) -> None:
        entries = _replace_csv_row(policy=BASE.router.NOTIFICATION_POLICY)
        self.assertTrue(
            any("CSV policy is" in e for e in self.failures(make_context(csv_entries=entries)))
        )

    def test_missing_dialog_object_fails_closed(self) -> None:
        contents = dict(BASE.contents)
        contents[UI_FILE] = contents[UI_FILE].replace(
            'id="FindReplaceDialog"', 'id="RenamedReplaceDialog"', 1
        )
        self.assertTrue(
            any("not found in" in e for e in self.failures(make_context(contents=contents)))
        )

    # -- Replace-All one-shot flag ------------------------------------------

    def test_replace_all_arm_marker_exactly_once(self) -> None:
        arm = BASE.registry["replace_all_flag"]["arm_marker"]
        contents = dict(BASE.contents)
        contents[SOURCE_FILE] = contents[SOURCE_FILE].replace(arm, "", 1)
        self.assertTrue(
            any(
                "arm marker must appear exactly once" in e
                for e in self.failures(make_context(contents=contents))
            )
        )

    def test_replace_all_clear_marker_exactly_once(self) -> None:
        contents = dict(BASE.contents)
        # Remove the clear inside CommandHdl_Impl specifically (anchored to the dispatch that
        # precedes it), leaving the flag armed but never cleared in the Replace-All branch.
        contents[SOURCE_FILE] = contents[SOURCE_FILE].replace(
            "m_rBindings.ExecuteSynchron(FID_SEARCH_NOW, ppArgs);\n"
            "        g_bMaterialReplaceAllPending = false;",
            "m_rBindings.ExecuteSynchron(FID_SEARCH_NOW, ppArgs);",
            1,
        )
        self.assertTrue(
            any(
                "clear marker must appear exactly once" in e
                for e in self.failures(make_context(contents=contents))
            )
        )

    def test_commandhdl_signature_required(self) -> None:
        signature = BASE.registry["replace_all_flag"]["context_signature"]
        contents = dict(BASE.contents)
        contents[SOURCE_FILE] = contents[SOURCE_FILE].replace(
            signature,
            "IMPL_LINK(SvxSearchDialog, RenamedHdl_Impl, weld::Button&, rBtn, void)",
            1,
        )
        self.assertTrue(
            any(
                "CommandHdl_Impl body not found" in e
                for e in self.failures(make_context(contents=contents))
            )
        )


if __name__ == "__main__":
    unittest.main()
