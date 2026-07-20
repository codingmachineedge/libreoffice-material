#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Regression tests for the exhaustive Windows dialog policy contract."""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-dialog-notification-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/dialog-notification-policy.csv"

SPEC = importlib.util.spec_from_file_location(
    "check_windows_dialog_notification_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def entry(
    key: object,
    *,
    policy: str = VALIDATOR.NOTIFICATION_POLICY,
    profile: str = VALIDATOR.DEFAULT_NOTIFICATION_PROFILE,
    reason: str = "",
) -> object:
    return VALIDATOR.ContractEntry(key, policy, profile, reason)


class WindowsDialogNotificationContractTest(unittest.TestCase):
    def write_registry(self, rows: list[dict[str, str]]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "registry.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=VALIDATOR.CSV_FIELDS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    @staticmethod
    def row(**overrides: str) -> dict[str, str]:
        values = {
            "ui_path": "module/uiconfig/ui/example.ui",
            "object_id": "ExampleDialog",
            "widget_class": "GtkDialog",
            "policy": VALIDATOR.NOTIFICATION_POLICY,
            "notification_profile": "default",
            "exclusion_reason": "",
        }
        values.update(overrides)
        return values

    def test_production_contract_covers_every_dialog_root(self) -> None:
        report = VALIDATOR.validate_contract(REPOSITORY, REGISTRY_PATH)
        self.assertEqual(597, report.total)
        self.assertEqual(
            {"GtkDialog": 521, "GtkMessageDialog": 75, "GtkAssistant": 1},
            dict(report.classes),
        )
        self.assertEqual(
            {VALIDATOR.NOTIFICATION_POLICY: 597}, dict(report.policies)
        )
        self.assertEqual({"default": 597}, dict(report.profiles))

    def test_discovery_selects_only_top_level_dialog_classes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dialog = root / "dialog.ui"
            message = root / "message.ui"
            ignored = root / "ignored.ui"
            dialog.write_text(
                '<interface><object class="GtkDialog" id="Dialog"/></interface>',
                encoding="utf-8",
            )
            message.write_text(
                '<interface><object class="GtkMessageDialog" id="Message"/></interface>',
                encoding="utf-8",
            )
            ignored.write_text(
                '<interface><object class="GtkWindow" id="Window">'
                '<child><object class="GtkDialog" id="Nested"/></child>'
                '</object></interface>',
                encoding="utf-8",
            )
            discovered = VALIDATOR.discover_dialogs(
                root, [dialog, message, ignored]
            )
        self.assertEqual(
            [
                VALIDATOR.DialogKey("dialog.ui", "Dialog", "GtkDialog"),
                VALIDATOR.DialogKey(
                    "message.ui", "Message", "GtkMessageDialog"
                ),
            ],
            discovered,
        )

    def test_worktree_deletion_is_absent_during_registry_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            deleted = root / "deleted.ui"
            deleted.write_text(
                '<interface><object class="GtkDialog" id="Deleted"/></interface>',
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(root), "add", "--", "deleted.ui"], check=True
            )
            deleted.unlink()
            self.assertEqual([], VALIDATOR.repository_ui_paths(root))

    def test_rejects_source_addition_missing_from_registry(self) -> None:
        key = VALIDATOR.DialogKey("module/uiconfig/ui/new.ui", "New", "GtkDialog")
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "source dialog.*missing from policy registry"
        ):
            VALIDATOR.compare_contract([key], [])

    def test_rejects_registry_omission_or_deleted_source(self) -> None:
        key = VALIDATOR.DialogKey("module/uiconfig/ui/old.ui", "Old", "GtkDialog")
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "registry entry.*without matching source dialog"
        ):
            VALIDATOR.compare_contract([], [entry(key)])

    def test_widget_class_change_is_contract_drift(self) -> None:
        old = VALIDATOR.DialogKey(
            "module/uiconfig/ui/example.ui", "Example", "GtkDialog"
        )
        new = VALIDATOR.DialogKey(
            "module/uiconfig/ui/example.ui", "Example", "GtkMessageDialog"
        )
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "missing from policy registry"
        ):
            VALIDATOR.compare_contract([new], [entry(old)])

    def test_rejects_duplicate_registry_locator(self) -> None:
        rows = [self.row(), self.row(widget_class="GtkMessageDialog")]
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "duplicate registry dialog locator"
        ):
            VALIDATOR.read_registry(self.write_registry(rows))

    def test_notification_policy_requires_explicit_profile(self) -> None:
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError,
            "notification policy requires a slug-like notification_profile",
        ):
            VALIDATOR.read_registry(
                self.write_registry([self.row(notification_profile="")])
            )

    def test_exclusion_requires_reason_and_forbids_profile(self) -> None:
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "native exclusion requires an exclusion_reason"
        ):
            VALIDATOR.read_registry(
                self.write_registry(
                    [
                        self.row(
                            policy=VALIDATOR.EXCLUSION_POLICY,
                            notification_profile="",
                        )
                    ]
                )
            )
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError,
            "native exclusion cannot have a notification_profile",
        ):
            VALIDATOR.read_registry(
                self.write_registry(
                    [
                        self.row(
                            policy=VALIDATOR.EXCLUSION_POLICY,
                            exclusion_reason="Platform picker owned by Windows",
                        )
                    ]
                )
            )

    def test_rejects_unknown_or_implicit_policy(self) -> None:
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "unsupported explicit policy"
        ):
            VALIDATOR.read_registry(self.write_registry([self.row(policy="")]))

    def test_update_defaults_new_dialog_and_preserves_reviewed_exclusion(self) -> None:
        existing_key = VALIDATOR.DialogKey(
            "module/uiconfig/ui/existing.ui", "Existing", "GtkAssistant"
        )
        new_key = VALIDATOR.DialogKey(
            "module/uiconfig/ui/new.ui", "New", "GtkDialog"
        )
        existing = entry(
            existing_key,
            policy=VALIDATOR.EXCLUSION_POLICY,
            profile="",
            reason="Native shell owns this flow",
        )
        merged = VALIDATOR.merge_entries([new_key, existing_key], [existing])
        by_key = {item.key: item for item in merged}
        self.assertEqual(VALIDATOR.EXCLUSION_POLICY, by_key[existing_key].policy)
        self.assertEqual(
            VALIDATOR.NOTIFICATION_POLICY, by_key[new_key].policy
        )
        self.assertEqual("default", by_key[new_key].notification_profile)

    def test_registry_must_be_deterministically_sorted(self) -> None:
        rows = [
            self.row(ui_path="z/uiconfig/ui/z.ui", object_id="Z"),
            self.row(ui_path="a/uiconfig/ui/a.ui", object_id="A"),
        ]
        with self.assertRaisesRegex(
            VALIDATOR.ValidationError, "registry rows must be sorted"
        ):
            VALIDATOR.read_registry(self.write_registry(rows))


if __name__ == "__main__":
    unittest.main()
