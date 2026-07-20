#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Regression tests for the Start Center Donate-action validator."""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-startcenter-no-donate.py"
UI_PATH = REPOSITORY / "sfx2/uiconfig/ui/startcenter.ui"
HEADER_PATH = REPOSITORY / "sfx2/source/dialog/backingwindow.hxx"
SOURCE_PATH = REPOSITORY / "sfx2/source/dialog/backingwindow.cxx"
BITMAPS_PATH = REPOSITORY / "sfx2/inc/bitmaps.hlst"

SPEC = importlib.util.spec_from_file_location("check_startcenter_no_donate", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class StartCenterNoDonateValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui = UI_PATH.read_text(encoding="utf-8")
        cls.header = HEADER_PATH.read_text(encoding="utf-8")
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.bitmaps = BITMAPS_PATH.read_text(encoding="utf-8")

    def validate_sources(
        self,
        *,
        ui: str | None = None,
        header: str | None = None,
        source: str | None = None,
        bitmaps: str | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ui_path = root / "startcenter.ui"
            header_path = root / "backingwindow.hxx"
            source_path = root / "backingwindow.cxx"
            bitmaps_path = root / "bitmaps.hlst"
            ui_path.write_text(self.ui if ui is None else ui, encoding="utf-8")
            header_path.write_text(
                self.header if header is None else header, encoding="utf-8"
            )
            source_path.write_text(
                self.source if source is None else source, encoding="utf-8"
            )
            bitmaps_path.write_text(
                self.bitmaps if bitmaps is None else bitmaps, encoding="utf-8"
            )
            VALIDATOR.validate(ui_path, header_path, source_path, bitmaps_path)

    def assert_validation_fails(self, message: str, **sources: str) -> None:
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            self.validate_sources(**sources)

    def test_production_sources_pass(self) -> None:
        self.validate_sources()

    def test_rejects_retired_widget_id(self) -> None:
        mutated = self.ui.replace('id="extensions"', 'id="donate"', 1)
        self.assert_validation_fails(
            "non-canonical Start Center widget IDs remain: donate", ui=mutated
        )

    def test_rejects_periodic_donation_banner(self) -> None:
        mutated = self.ui.replace(
            '<object class="GtkBox" id="box2">',
            '<object class="GtkBox" id="box2">\n'
            '  <child><object class="GtkGrid" id="gdDonation"/></child>',
            1,
        )
        self.assert_validation_fails(
            "non-canonical Start Center widget IDs remain: gdDonation", ui=mutated
        )

    def test_rejects_legacy_brand_surface(self) -> None:
        mutated = self.ui.replace(
            '<object class="GtkBox" id="buttons_box">',
            '<object class="GtkBox" id="buttons_box">\n'
            '  <child><object class="GtkDrawingArea" id="daBrand"/></child>',
            1,
        )
        self.assert_validation_fails(
            "non-canonical Start Center widget IDs remain: daBrand", ui=mutated
        )

    def test_rejects_retired_native_member(self) -> None:
        mutated = self.header.replace(
            "std::unique_ptr<weld::Button> mxExtensionsButton;",
            "std::unique_ptr<weld::Button> mxExtensionsButton;\n"
            "    std::unique_ptr<weld::Button> mxDonateButton;",
            1,
        )
        self.assert_validation_fails(
            "retired Start Center Donate wiring remains: mxDonateButton",
            header=mutated,
        )

    def test_rejects_donation_route_for_extensions(self) -> None:
        mutated = self.source.replace(
            "Menus::ExtensionsURL::get()", "Menus::DonationURL::get()", 1
        )
        self.assert_validation_fails(
            "ExtensionsClickHdl must use ExtensionsURL exactly once", source=mutated
        )

    def test_rejects_retired_bitmap_constant(self) -> None:
        mutated = self.bitmaps + (
            '\ninline constexpr OUString BMP_DONATE = u"res/donate.png"_ustr;\n'
        )
        self.assert_validation_fails(
            "retired Start Center Donate wiring remains: BMP_DONATE",
            bitmaps=mutated,
        )

    def test_rejects_layout_gap(self) -> None:
        marker = '<object class="GtkBox" id="small_buttons_box">'
        before, buttons = self.ui.split(marker, 1)
        mutated = before + marker + buttons.replace(
            '<property name="position">1</property>',
            '<property name="position">2</property>',
            1,
        )
        self.assert_validation_fails(
            "small_buttons_box positions must be contiguous after Donate removal; "
            "found ['0', '2']",
            ui=mutated,
        )


if __name__ == "__main__":
    unittest.main()
