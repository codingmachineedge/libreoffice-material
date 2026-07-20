#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Regression tests for the centralized Windows dialog-placement validator."""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-dialog-placement.py"
DIALOG_SOURCE_PATH = REPOSITORY / "vcl/source/window/dialog.cxx"
EVENT_SOURCE_PATH = REPOSITORY / "vcl/source/window/event.cxx"
HEADER_PATH = REPOSITORY / "include/vcl/toolkit/dialog.hxx"

SPEC = importlib.util.spec_from_file_location(
    "check_windows_dialog_placement", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class WindowsDialogPlacementValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dialog_source = DIALOG_SOURCE_PATH.read_text(encoding="utf-8")
        cls.event_source = EVENT_SOURCE_PATH.read_text(encoding="utf-8")
        cls.header = HEADER_PATH.read_text(encoding="utf-8")

    def validate_sources(
        self,
        *,
        dialog_source: str | None = None,
        event_source: str | None = None,
        header: str | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dialog_source_path = root / "dialog.cxx"
            event_source_path = root / "event.cxx"
            header_path = root / "dialog.hxx"
            dialog_source_path.write_text(
                self.dialog_source if dialog_source is None else dialog_source,
                encoding="utf-8",
            )
            event_source_path.write_text(
                self.event_source if event_source is None else event_source,
                encoding="utf-8",
            )
            header_path.write_text(
                self.header if header is None else header, encoding="utf-8"
            )
            VALIDATOR.validate(dialog_source_path, event_source_path, header_path)

    def assert_validation_fails(self, message: str, **sources: str) -> None:
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            self.validate_sources(**sources)

    def replace_once(self, source: str, old: str, new: str) -> str:
        self.assertEqual(source.count(old), 1, f"expected one copy of {old!r}")
        return source.replace(old, new, 1)

    def test_production_source_passes(self) -> None:
        self.validate_sources()

    def test_rejects_non_windows_helper(self) -> None:
        mutated = self.replace_once(
            self.dialog_source,
            "#if defined(_WIN32)\nnamespace\n{",
            "#if defined(__linux__)\nnamespace\n{",
        )
        self.assert_validation_fails(
            "Windows dialog placement helper must be inside an _WIN32 guard",
            dialog_source=mutated,
        )

    def test_rejects_non_windows_final_hook(self) -> None:
        marker = (
            "#if defined(_WIN32)\n"
            "    // Run after the complete virtual StateChanged chain:"
        )
        mutated = self.replace_once(
            self.event_source,
            marker,
            "#if defined(__linux__)\n"
            "    // Run after the complete virtual StateChanged chain:",
        )
        self.assert_validation_fails(
            "Windows final-InitShow dialog hook must be inside an _WIN32 guard",
            event_source=mutated,
        )

    def test_rejects_missing_lok_guard(self) -> None:
        mutated = self.replace_once(
            self.dialog_source,
            "    // LibreOfficeKit owns dialog geometry and transports it to a remote client.\n"
            "    if (comphelper::LibreOfficeKit::isActive())\n"
            "        return;",
            "    // LibreOfficeKit guard accidentally removed.\n"
            "    if (false)\n"
            "        return;",
        )
        self.assert_validation_fails(
            "Windows dialog placement helper is missing: "
            "comphelper::LibreOfficeKit::isActive()",
            dialog_source=mutated,
        )

    def test_rejects_placement_before_final_init_dispatch(self) -> None:
        hook = (
            "#if defined(_WIN32)\n"
            "    // Run after the complete virtual StateChanged chain: derived dialogs can perform a final\n"
            "    // layout after Dialog::StateChanged returns.\n"
            "    if (Dialog* pDialog = dynamic_cast<Dialog*>(this))\n"
            "        pDialog->ImplPositionAsWindowsNotification();\n"
            "#endif"
        )
        without_hook = self.replace_once(self.event_source, hook, "")
        dispatch = "    CompatStateChanged( StateChangedType::InitShow );"
        mutated = self.replace_once(
            without_hook, dispatch, hook + "\n\n" + dispatch
        )
        self.assert_validation_fails(
            "Windows dialog placement must run after the complete virtual InitShow dispatch",
            event_source=mutated,
        )

    def test_rejects_missing_owner_intersection(self) -> None:
        mutated = self.replace_once(
            self.dialog_source,
            "GetWindowExtentsAbsolute().GetIntersection(aWorkArea)",
            "GetWindowExtentsAbsolute()",
        )
        self.assert_validation_fails(
            "Windows dialog placement helper is missing: "
            "GetWindowExtentsAbsolute().GetIntersection(aWorkArea)",
            dialog_source=mutated,
        )

    def test_rejects_unbounded_material_inset(self) -> None:
        mutated = self.replace_once(
            self.dialog_source,
            "std::min(kMaterialNotificationInset, nHorizontalRoom)",
            "kMaterialNotificationInset",
        )
        self.assert_validation_fails(
            "Windows dialog placement helper is missing: "
            "std::min(kMaterialNotificationInset, nHorizontalRoom)",
            dialog_source=mutated,
        )

    def test_rejects_missing_work_area_clamp(self) -> None:
        mutated = self.replace_once(
            self.dialog_source,
            "std::clamp(nDesired, nWorkAreaStart, nLastVisibleStart)",
            "nDesired",
        )
        self.assert_validation_fails(
            "Windows dialog clamping helper is missing: "
            "std::clamp(nDesired, nWorkAreaStart, nLastVisibleStart)",
            dialog_source=mutated,
        )

    def test_rejects_client_origin_without_decoration_offset(self) -> None:
        self.assertEqual(self.dialog_source.count("aDecorationOffset"), 3)
        mutated = self.dialog_source.replace("aDecorationOffset", "aRetiredOffset")
        self.assert_validation_fails(
            "Windows dialog placement helper is missing: aDecorationOffset",
            dialog_source=mutated,
        )

    def test_rejects_duplicate_hook(self) -> None:
        mutated = self.event_source.replace(
            "        pDialog->ImplPositionAsWindowsNotification();",
            "        pDialog->ImplPositionAsWindowsNotification();\n"
            "        pDialog->ImplPositionAsWindowsNotification();",
            1,
        )
        self.assert_validation_fails(
            "Windows final-InitShow dialog hook must be called exactly once",
            event_source=mutated,
        )

    def test_rejects_missing_dialog_method_declaration(self) -> None:
        mutated = self.replace_once(
            self.header,
            "    SAL_DLLPRIVATE void    ImplPositionAsWindowsNotification();\n",
            "",
        )
        self.assert_validation_fails(
            "Dialog notification-placement method must be declared exactly once",
            header=mutated,
        )


if __name__ == "__main__":
    unittest.main()
