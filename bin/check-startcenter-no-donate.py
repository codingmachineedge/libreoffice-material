#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Keep non-canonical Donate and legacy brand surfaces out of Start Center."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class ValidationError(RuntimeError):
    """Raised when the removed Start Center action is reintroduced."""


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_UI = REPOSITORY / "sfx2/uiconfig/ui/startcenter.ui"
DEFAULT_HEADER = REPOSITORY / "sfx2/source/dialog/backingwindow.hxx"
DEFAULT_SOURCE = REPOSITORY / "sfx2/source/dialog/backingwindow.cxx"
DEFAULT_BITMAPS = REPOSITORY / "sfx2/inc/bitmaps.hlst"

FORBIDDEN_NATIVE_MARKERS = (
    "mxDonateButton",
    "mxDonation",
    "ExtLinkClickHdl",
    'weld_button(u"donate"_ustr)',
    'u"daBrand"_ustr',
    "BrandImage",
    "initDonationBanner",
    "OnDonateLinkClick",
    "SID_DONATION",
    "BMP_DONATE",
    "STR_DONATE_BUTTON",
)

FORBIDDEN_WIDGET_IDS = {
    "donate",
    "donate_image",
    "gdDonation",
    "imgDonationLeft",
    "imgDonationRight",
    "lbDonateTitle",
    "lbDonateText",
    "btnDonateLink",
    "daBrand",
}


def _small_button_ids(root: ET.Element) -> tuple[list[str], list[str]]:
    boxes = root.findall(".//object[@id='small_buttons_box']")
    if len(boxes) != 1:
        raise ValidationError(
            "Start Center must contain exactly one small_buttons_box, "
            f"found {len(boxes)}"
        )

    ids: list[str] = []
    positions: list[str] = []
    for child in boxes[0].findall("./child"):
        widget = child.find("./object")
        if widget is None:
            continue
        widget_id = widget.get("id")
        if widget_id:
            ids.append(widget_id)
        position = child.find("./packing/property[@name='position']")
        positions.append(position.text.strip() if position is not None and position.text else "")
    return ids, positions


def _extensions_handler(source: str) -> str:
    marker = (
        "IMPL_STATIC_LINK_NOARG(BackingWindow, ExtensionsClickHdl, "
        "weld::Button&, void)"
    )
    start = source.find(marker)
    if start < 0:
        raise ValidationError("ExtensionsClickHdl implementation is missing")
    end = source.find("\nvoid BackingWindow::applyFilter", start)
    if end < 0:
        raise ValidationError("ExtensionsClickHdl implementation boundary is missing")
    return source[start:end]


def validate(
    ui_path: Path, header_path: Path, source_path: Path, bitmaps_path: Path
) -> None:
    try:
        root = ET.parse(ui_path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse {ui_path}: {error}") from error

    object_ids = {
        element.get("id") for element in root.findall(".//object") if element.get("id")
    }
    retired_ids = sorted(FORBIDDEN_WIDGET_IDS & object_ids)
    if retired_ids:
        raise ValidationError(
            "non-canonical Start Center widget IDs remain: " + ", ".join(retired_ids)
        )

    button_ids, positions = _small_button_ids(root)
    if button_ids != ["help", "extensions"]:
        raise ValidationError(
            "small_buttons_box must contain only help and extensions in that order; "
            f"found {button_ids}"
        )
    if positions != ["0", "1"]:
        raise ValidationError(
            "small_buttons_box positions must be contiguous after Donate removal; "
            f"found {positions}"
        )

    try:
        header = header_path.read_text(encoding="utf-8")
        source = source_path.read_text(encoding="utf-8")
        bitmaps = bitmaps_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read native Start Center source: {error}") from error

    native = header + "\n" + source + "\n" + bitmaps
    remaining_markers = [marker for marker in FORBIDDEN_NATIVE_MARKERS if marker in native]
    if remaining_markers:
        raise ValidationError(
            "retired Start Center Donate wiring remains: " + ", ".join(remaining_markers)
        )

    declaration = "DECL_STATIC_LINK(BackingWindow, ExtensionsClickHdl, weld::Button&, void);"
    if header.count(declaration) != 1:
        raise ValidationError("ExtensionsClickHdl declaration must appear exactly once")

    connection = (
        "mxExtensionsButton->connect_clicked("
        "LINK(this, BackingWindow, ExtensionsClickHdl));"
    )
    if source.count(connection) != 1:
        raise ValidationError("Extensions must connect exactly once to ExtensionsClickHdl")

    handler = _extensions_handler(source)
    if handler.count("Menus::ExtensionsURL::get()") != 1:
        raise ValidationError("ExtensionsClickHdl must use ExtensionsURL exactly once")
    if "DonationURL" in handler or "ShowDonation" in handler:
        raise ValidationError("ExtensionsClickHdl must not route through donation settings")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", type=Path, default=DEFAULT_UI)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bitmaps", type=Path, default=DEFAULT_BITMAPS)
    args = parser.parse_args()

    try:
        validate(args.ui, args.header, args.source, args.bitmaps)
    except ValidationError as error:
        print(f"Start Center validation failed: {error}", file=sys.stderr)
        return 1

    print(
        "Start Center validation passed: Donate and legacy brand surfaces absent; "
        "Help/Extensions footer and Extensions route intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
