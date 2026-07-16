#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the semantic palette and required VCL Material widget coverage."""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


TOKEN_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
TOKEN_REFERENCE = re.compile(r"^@([a-z][a-z0-9-]*)$")

REQUIRED_PARTS = {
    "pushbutton": {"Entire", "Focus"},
    "radiobutton": {"Entire", "Focus"},
    "checkbox": {"Entire", "Focus"},
    "combobox": {"Entire", "SubEdit", "ButtonDown", "Focus"},
    "editbox": {"Entire"},
    "editboxnoborder": {"Entire"},
    "multilineeditbox": {"Entire"},
    "listbox": {"Entire", "ListboxWindow", "SubEdit", "ButtonDown", "Focus"},
    "spinbox": {"Entire", "SubEdit", "ButtonDown", "ButtonUp", "Focus"},
    "scrollbar": {
        "Entire",
        "ThumbHorz",
        "ThumbVert",
        "ButtonUp",
        "ButtonDown",
        "ButtonLeft",
        "ButtonRight",
        "TrackHorzLeft",
        "TrackHorzRight",
        "TrackVertUpper",
        "TrackVertLower",
    },
    "slider": {
        "Button",
        "TrackHorzLeft",
        "TrackHorzRight",
        "TrackVertUpper",
        "TrackVertLower",
    },
    "fixedline": {"SeparatorHorz", "SeparatorVert"},
    "progress": {"Entire"},
    "tabitem": {"Entire", "MenuItem"},
    "tabheader": {"Entire"},
    "tabpane": {"Entire"},
    "tabbody": {"Entire"},
    "windowbackground": {"Entire", "BackgroundWindow", "BackgroundDialog"},
    "toolbar": {
        "Entire",
        "DrawBackgroundHorz",
        "DrawBackgroundVert",
        "ThumbHorz",
        "ThumbVert",
        "SeparatorHorz",
        "SeparatorVert",
        "Button",
    },
    "listnode": {"Entire"},
    "listheader": {"Button", "Arrow"},
    "menubar": {"Entire", "MenuItem"},
    "menupopup": {
        "Entire",
        "MenuItem",
        "MenuItemCheckMark",
        "MenuItemRadioMark",
        "Separator",
        "SubmenuArrow",
    },
    "tooltip": {"Entire"},
}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def parse_color(value: str) -> tuple[int, int, int]:
    if not HEX_COLOR.fullmatch(value):
        fail(f"invalid RGB color {value!r}")
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def linear_component(component: int) -> float:
    value = component / 255.0
    return value / 12.92 if value <= 0.04045 else math.pow((value + 0.055) / 1.055, 2.4)


def luminance(color: tuple[int, int, int]) -> float:
    red, green, blue = (linear_component(component) for component in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def find_part(root: ET.Element, control_name: str, part_name: str) -> ET.Element:
    control = root.find(control_name)
    if control is None:
        fail(f"missing control {control_name}")
    for part in control.findall("part"):
        if part.get("value") == part_name:
            return part
    fail(f"missing {control_name}/{part_name}")


def has_state(part: ET.Element, **attributes: str) -> bool:
    return any(all(state.get(name) == value for name, value in attributes.items())
               for state in part.findall("state"))


def validate(path: Path) -> tuple[int, int, int]:
    root = ET.parse(path).getroot()
    if root.tag != "widgets":
        fail("root element must be <widgets>")

    palette = root.find("palette")
    if palette is None:
        fail("missing semantic <palette>")

    tokens: dict[str, tuple[int, int, int]] = {}
    palette_elements = set(palette.findall("color"))
    for element in palette_elements:
        name = element.get("name", "")
        value = element.get("value", "")
        if not TOKEN_NAME.fullmatch(name):
            fail(f"invalid token name {name!r}")
        if name in tokens:
            fail(f"duplicate token {name!r}")
        tokens[name] = parse_color(value)

    references: set[str] = set()
    style = root.find("style")
    if style is None:
        fail("missing <style>")

    style_colors: dict[str, tuple[int, int, int]] = {}
    for element in style:
        value = element.get("value", "")
        match = TOKEN_REFERENCE.fullmatch(value)
        if match is None:
            fail(f"style {element.tag} must reference a semantic token")
        name = match.group(1)
        if name not in tokens:
            fail(f"style {element.tag} references unknown token {name!r}")
        references.add(name)
        style_colors[element.tag] = tokens[name]

    for element in root.iter():
        if element in palette_elements:
            continue
        for attribute in ("stroke", "fill"):
            value = element.get(attribute)
            if value is None:
                continue
            match = TOKEN_REFERENCE.fullmatch(value)
            if match is None:
                fail(f"{element.tag}/@{attribute} must reference a semantic token")
            name = match.group(1)
            if name not in tokens:
                fail(f"{element.tag}/@{attribute} references unknown token {name!r}")
            references.add(name)

    unused = sorted(tokens.keys() - references)
    if unused:
        fail(f"unused semantic tokens: {', '.join(unused)}")

    for control_name, required_parts in REQUIRED_PARTS.items():
        control = root.find(control_name)
        if control is None:
            fail(f"missing control {control_name}")
        actual_parts = {part.get("value", "") for part in control.findall("part")}
        missing_parts = sorted(required_parts - actual_parts)
        if missing_parts:
            fail(f"{control_name} missing parts: {', '.join(missing_parts)}")

    checkbox = find_part(root, "checkbox", "Entire")
    for enabled in ("true", "false"):
        for value in ("false", "true", "mixed"):
            if not has_state(checkbox, enabled=enabled, **{"button-value": value}):
                fail(f"checkbox missing enabled={enabled}, button-value={value}")

    radio = find_part(root, "radiobutton", "Entire")
    for enabled in ("true", "false"):
        for value in ("false", "true"):
            if not has_state(radio, enabled=enabled, **{"button-value": value}):
                fail(f"radiobutton missing enabled={enabled}, button-value={value}")

    tab = find_part(root, "tabitem", "Entire")
    if not has_state(tab, enabled="true", selected="true", rollover="true"):
        fail("tabitem missing combined selected+rollover state")
    if not has_state(tab, enabled="true", selected="true", focused="true"):
        fail("tabitem missing combined selected+focused state")
    tab_menu_item = find_part(root, "tabitem", "MenuItem")
    if not has_state(tab_menu_item, enabled="true", selected="true", focused="true"):
        fail("tabitem/MenuItem missing combined selected+focused state")

    toolbar_button = find_part(root, "toolbar", "Button")
    if not has_state(toolbar_button, enabled="true", **{"button-value": "true"}):
        fail("toolbar button missing checked state")
    if not has_state(
        toolbar_button, enabled="true", pressed="true", **{"button-value": "true"}
    ):
        fail("toolbar button missing combined checked+pressed state")
    if not has_state(toolbar_button, enabled="true", focused="true"):
        fail("toolbar button missing focused state")

    slider_button = find_part(root, "slider", "Button")
    if not has_state(slider_button, enabled="true", focused="true"):
        fail("slider thumb missing focused state")
    for part_name in ("TrackHorzLeft", "TrackHorzRight", "TrackVertUpper", "TrackVertLower"):
        if not has_state(find_part(root, "slider", part_name), enabled="false"):
            fail(f"slider/{part_name} missing disabled state")

    contrast_pairs = (
        ("windowTextColor", "windowColor"),
        ("fieldTextColor", "fieldColor"),
        ("menuTextColor", "menuColor"),
        ("highlightTextColor", "highlightColor"),
        ("helpTextColor", "helpColor"),
    )
    for foreground, background in contrast_pairs:
        ratio = contrast(style_colors[foreground], style_colors[background])
        if ratio < 4.5:
            fail(f"{foreground}/{background} contrast is only {ratio:.2f}:1")
    if contrast(tokens["on-primary"], tokens["primary"]) < 4.5:
        fail("on-primary/primary contrast is below 4.5:1")

    part_count = sum(len(control.findall("part")) for control in root
                     if control.tag not in {"palette", "style", "settings"})
    state_count = sum(1 for _ in root.iter("state"))
    return len(tokens), part_count, state_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "definition",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "vcl/uiconfig/theme_definitions/material/definition.xml",
    )
    args = parser.parse_args()
    try:
        token_count, part_count, state_count = validate(args.definition)
    except (ET.ParseError, OSError, ValidationError) as error:
        print(f"{args.definition}: {error}", file=sys.stderr)
        return 1
    print(
        f"Material theme OK: {token_count} tokens, {part_count} parts, "
        f"{state_count} states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
