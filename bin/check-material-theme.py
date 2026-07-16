#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate semantic tokens and required VCL Material widget coverage."""

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
RADIUS_VALUE = re.compile(r"^(?:0|[1-9][0-9]*)$")
REQUIRED_SCHEMES = {"light", "dark"}
ALLOWED_TYPOGRAPHY_WEIGHTS = {"preserve", "normal", "medium", "semibold", "bold"}
REQUIRED_TYPOGRAPHY = {
    "body": (100, "preserve"),
    "label": (100, "medium"),
    "title": (120, "semibold"),
}
REQUIRED_SHAPES = {
    "corner-checkbox": 3,
    "corner-indicator": 4,
    "corner-focus": 6,
    "corner-small": 8,
    "corner-control": 10,
    "corner-container": 12,
    "corner-toolbar": 18,
    "corner-pill": 20,
}

REQUIRED_FEEDBACK_COLORS = {
    "light": {
        "warning-container": "#FFDDB3",
        "on-warning-container": "#2A1800",
        "error-container": "#F9DEDC",
        "on-error-container": "#410E0B",
    },
    "dark": {
        "warning-container": "#5F4100",
        "on-warning-container": "#FFDDB3",
        "error-container": "#8C1D18",
        "on-error-container": "#F9DEDC",
    },
}

REQUIRED_STYLE = {
    "faceColor": "surface-container",
    "checkedColor": "primary-container",
    "lightColor": "surface",
    "lightBorderColor": "outline-variant",
    "shadowColor": "outline",
    "darkShadowColor": "on-surface",
    "defaultButtonTextColor": "on-primary-container",
    "buttonTextColor": "on-primary-container",
    "defaultActionButtonTextColor": "on-primary",
    "actionButtonTextColor": "on-primary",
    "flatButtonTextColor": "primary",
    "defaultButtonRolloverTextColor": "on-primary-container",
    "buttonRolloverTextColor": "on-primary-container",
    "defaultActionButtonRolloverTextColor": "on-primary",
    "actionButtonRolloverTextColor": "on-primary",
    "flatButtonRolloverTextColor": "on-primary-container",
    "defaultButtonPressedRolloverTextColor": "on-primary-container",
    "buttonPressedRolloverTextColor": "on-primary-container",
    "defaultActionButtonPressedRolloverTextColor": "on-primary",
    "actionButtonPressedRolloverTextColor": "on-primary",
    "flatButtonPressedRolloverTextColor": "on-primary-container",
    "radioCheckTextColor": "on-surface",
    "groupTextColor": "on-surface-variant",
    "labelTextColor": "on-surface",
    "windowColor": "surface",
    "windowTextColor": "on-surface",
    "dialogColor": "surface-container",
    "dialogTextColor": "on-surface",
    "workspaceColor": "surface-container-low",
    "monoColor": "on-surface",
    "fieldColor": "surface",
    "fieldTextColor": "on-surface",
    "fieldRolloverTextColor": "on-surface",
    "activeColor": "primary",
    "activeTextColor": "on-primary",
    "activeBorderColor": "primary",
    "deactiveColor": "disabled-container",
    "deactiveTextColor": "outline",
    "deactiveBorderColor": "outline-variant",
    "menuColor": "surface",
    "menuBarColor": "surface-container",
    "menuBarRolloverColor": "primary-container",
    "menuBorderColor": "outline-variant",
    "menuTextColor": "on-surface",
    "menuBarTextColor": "on-surface",
    "menuBarRolloverTextColor": "on-primary-container",
    "menuBarHighlightTextColor": "on-primary-container",
    "menuHighlightColor": "primary-container",
    "menuHighlightTextColor": "on-primary-container",
    "highlightColor": "primary-container",
    "highlightTextColor": "on-primary-container",
    "activeTabColor": "primary-container",
    "inactiveTabColor": "surface-container",
    "tabTextColor": "on-surface-variant",
    "tabRolloverTextColor": "on-surface",
    "tabHighlightTextColor": "on-primary-container",
    "disableColor": "disabled-container",
    "helpColor": "inverse-surface",
    "helpTextColor": "inverse-on-surface",
    "linkColor": "primary",
    "visitedLinkColor": "visited-link",
    "toolTextColor": "on-surface",
    "accentColor": "primary",
    "listBoxWindowBackgroundColor": "surface",
    "listBoxWindowTextColor": "on-surface",
    "listBoxWindowHighlightColor": "primary-container",
    "listBoxWindowHighlightTextColor": "on-primary-container",
    "alternatingRowColor": "surface-container-low",
    "warningColor": "warning-container",
    "warningTextColor": "on-warning-container",
    "errorColor": "error-container",
    "errorTextColor": "on-error-container",
}

STYLE_SOURCE_CLOSURE = {
    "accentColor": ("moAccentColor", "SetAccentColor"),
    "listBoxWindowBackgroundColor": (
        "moListBoxWindowBackgroundColor",
        "SetListBoxWindowBackgroundColor",
    ),
    "listBoxWindowTextColor": (
        "moListBoxWindowTextColor",
        "SetListBoxWindowTextColor",
    ),
    "listBoxWindowHighlightColor": (
        "moListBoxWindowHighlightColor",
        "SetListBoxWindowHighlightColor",
    ),
    "listBoxWindowHighlightTextColor": (
        "moListBoxWindowHighlightTextColor",
        "SetListBoxWindowHighlightTextColor",
    ),
    "alternatingRowColor": ("moAlternatingRowColor", "SetAlternatingRowColor"),
    "warningColor": ("moWarningColor", "SetWarningColor"),
    "warningTextColor": ("moWarningTextColor", "SetWarningTextColor"),
    "errorColor": ("moErrorColor", "SetErrorColor"),
    "errorTextColor": ("moErrorTextColor", "SetErrorTextColor"),
}

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
    "spinbuttons": {"ButtonDown", "ButtonUp", "ButtonLeft", "ButtonRight"},
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


def format_color(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{component:02X}" for component in color)


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


def validate_interaction_states(part: ET.Element, label: str) -> None:
    states = part.findall("state")
    expected = {
        "normal": lambda state: state.get("enabled") == "true"
        and state.get("rollover") is None
        and state.get("pressed") is None,
        "rollover": lambda state: state.get("enabled") == "true"
        and state.get("rollover") == "true"
        and state.get("pressed") is None,
        "pressed": lambda state: state.get("enabled") == "true"
        and state.get("pressed") == "true"
        and state.get("rollover") is None,
        "disabled": lambda state: state.get("enabled") == "false"
        and state.get("rollover") is None
        and state.get("pressed") is None,
    }
    for state_name, matches in expected.items():
        matching = [state for state in states if matches(state)]
        if not matching:
            fail(f"{label} missing {state_name} state")
        if any(len(state) == 0 for state in matching):
            fail(f"{label} {state_name} state has no drawing action")


def read_palettes(
    root: ET.Element,
) -> tuple[dict[str, dict[str, tuple[int, int, int]]], set[ET.Element]]:
    palettes: dict[str, dict[str, tuple[int, int, int]]] = {}
    palette_elements: set[ET.Element] = set()

    for palette in root.findall("palette"):
        unknown_attributes = sorted(set(palette.attrib) - {"scheme"})
        if unknown_attributes:
            fail(f"palette has unknown attributes: {', '.join(unknown_attributes)}")

        scheme_attribute = palette.get("scheme")
        scheme = "light" if scheme_attribute is None else scheme_attribute
        if not TOKEN_NAME.fullmatch(scheme):
            fail(f"invalid palette scheme {scheme!r}")
        if scheme in palettes:
            fail(f"duplicate palette scheme {scheme!r}")
        if (palette.text or "").strip():
            fail(f"palette {scheme!r} must not contain text")

        tokens: dict[str, tuple[int, int, int]] = {}
        for element in palette:
            if element.tag != "color":
                fail(f"palette {scheme!r} has unknown element <{element.tag}>")
            palette_elements.add(element)
            if set(element.attrib) != {"name", "value"}:
                fail(
                    f"palette {scheme!r} <color> requires exactly name and value attributes"
                )
            name = element.get("name", "")
            value = element.get("value", "")
            if not TOKEN_NAME.fullmatch(name):
                fail(f"invalid token name {name!r} in {scheme!r} palette")
            if name in tokens:
                fail(f"duplicate token {name!r} in {scheme!r} palette")
            tokens[name] = parse_color(value)
            if list(element) or (element.text or "").strip():
                fail(f"palette {scheme!r} color {name!r} must not have content")
            if (element.tail or "").strip():
                fail(f"palette {scheme!r} must not contain text")
        if not tokens:
            fail(f"palette {scheme!r} is empty")
        palettes[scheme] = tokens

    if not palettes:
        fail("missing semantic <palette>")
    missing_schemes = sorted(REQUIRED_SCHEMES - palettes.keys())
    if missing_schemes:
        fail(f"missing palette schemes: {', '.join(missing_schemes)}")
    unexpected_schemes = sorted(palettes.keys() - REQUIRED_SCHEMES)
    if unexpected_schemes:
        fail(f"unexpected palette schemes: {', '.join(unexpected_schemes)}")

    light_tokens = set(palettes["light"])
    for scheme, tokens in palettes.items():
        missing_tokens = sorted(light_tokens - tokens.keys())
        extra_tokens = sorted(tokens.keys() - light_tokens)
        if missing_tokens or extra_tokens:
            details = []
            if missing_tokens:
                details.append(f"missing {', '.join(missing_tokens)}")
            if extra_tokens:
                details.append(f"extra {', '.join(extra_tokens)}")
            fail(f"palette {scheme!r} token mismatch: {'; '.join(details)}")

    for scheme, expected_colors in REQUIRED_FEEDBACK_COLORS.items():
        for name, expected_text in expected_colors.items():
            actual = palettes[scheme].get(name)
            if actual is None:
                fail(
                    f"{scheme} palette is missing required feedback token {name!r}"
                )
            expected = parse_color(expected_text)
            if actual != expected:
                fail(
                    f"{scheme} palette token {name!r} must be {expected_text}, "
                    f"found {format_color(actual)}"
                )

    return palettes, palette_elements


def read_typography(root: ET.Element) -> dict[str, tuple[int, str]]:
    sections = root.findall("typography")
    if len(sections) != 1:
        fail(f"expected exactly one <typography> section, found {len(sections)}")
    typography = sections[0]
    if typography.attrib:
        fail("typography section must not have attributes")
    if (typography.text or "").strip():
        fail("typography section must not contain text")

    roles: dict[str, tuple[int, str]] = {}
    for element in typography:
        if element.tag != "role":
            fail(f"typography has unknown element <{element.tag}>")
        if list(element) or (element.text or "").strip():
            fail(f"typography role {element.get('name', '')!r} must not have content")
        if (element.tail or "").strip():
            fail("typography section must not contain text")
        unknown_attributes = sorted(set(element.attrib) - {"name", "scale", "weight"})
        if unknown_attributes:
            fail(
                "typography role has unknown attributes: "
                + ", ".join(unknown_attributes)
            )
        if set(element.attrib) != {"name", "scale", "weight"}:
            fail("typography roles require exactly name, scale, and weight")

        name = element.get("name", "")
        if name not in REQUIRED_TYPOGRAPHY:
            fail(f"unknown typography role {name!r}")
        if name in roles:
            fail(f"duplicate typography role {name!r}")

        scale_text = element.get("scale", "")
        if not re.fullmatch(r"[0-9]{3}", scale_text):
            fail(f"invalid typography scale {scale_text!r} for {name!r}")
        scale = int(scale_text)
        if not 100 <= scale <= 200:
            fail(f"typography scale for {name!r} must be between 100 and 200")

        weight = element.get("weight", "")
        if weight not in ALLOWED_TYPOGRAPHY_WEIGHTS:
            fail(f"invalid typography weight {weight!r} for {name!r}")
        roles[name] = (scale, weight)

    missing = sorted(REQUIRED_TYPOGRAPHY.keys() - roles.keys())
    if missing:
        fail(f"missing typography roles: {', '.join(missing)}")
    for name, expected in REQUIRED_TYPOGRAPHY.items():
        if roles[name] != expected:
            fail(
                f"typography role {name!r} must be scale={expected[0]} "
                f"weight={expected[1]!r}"
            )
    return roles


def read_shapes(root: ET.Element) -> dict[str, int]:
    sections = root.findall("shapes")
    if len(sections) != 1:
        fail(f"expected exactly one <shapes> section, found {len(sections)}")
    shapes = sections[0]
    if shapes.attrib:
        fail("shapes section must not have attributes")
    if (shapes.text or "").strip():
        fail("shapes section must not contain text")

    radii: dict[str, int] = {}
    for element in shapes:
        if not isinstance(element.tag, str):
            fail("shapes section must not contain processing instructions")
        if element.tag != "radius":
            fail(f"shapes has unknown element <{element.tag}>")
        if list(element) or (element.text or "").strip():
            fail(
                f"shape radius {element.get('name', '')!r} must not have content"
            )
        if (element.tail or "").strip():
            fail("shapes section must not contain text")

        unknown_attributes = sorted(set(element.attrib) - {"name", "value"})
        if unknown_attributes:
            fail(
                "shape radius has unknown attributes: "
                + ", ".join(unknown_attributes)
            )
        if set(element.attrib) != {"name", "value"}:
            fail("shape radii require exactly name and value attributes")

        name = element.get("name", "")
        if not TOKEN_NAME.fullmatch(name):
            fail(f"invalid shape token name {name!r}")
        if name not in REQUIRED_SHAPES:
            fail(f"unknown shape token {name!r}")
        if name in radii:
            fail(f"duplicate shape token {name!r}")

        value_text = element.get("value", "")
        if not RADIUS_VALUE.fullmatch(value_text):
            fail(f"invalid shape radius {value_text!r} for {name!r}")
        value = int(value_text)
        if not 0 <= value <= 64:
            fail(f"shape radius for {name!r} must be between 0 and 64")
        expected = REQUIRED_SHAPES[name]
        if value != expected:
            fail(f"shape token {name!r} must be radius {expected}, found {value}")
        radii[name] = value

    missing = sorted(REQUIRED_SHAPES.keys() - radii.keys())
    if missing:
        fail(f"missing shape tokens: {', '.join(missing)}")

    shape_elements = set(shapes.iter())
    for element in root.iter():
        if (
            isinstance(element.tag, str)
            and element.tag in {"shapes", "radius"}
            and element not in shape_elements
        ):
            fail(f"<{element.tag}> must appear only in the root <shapes> section")
    return radii


def read_style(root: ET.Element, token_names: set[str]) -> dict[str, str]:
    sections = root.findall("style")
    if len(sections) != 1:
        fail(f"expected exactly one <style> section, found {len(sections)}")
    style = sections[0]
    if style.attrib:
        fail("style section must not have attributes")
    if (style.text or "").strip():
        fail("style section must not contain text")

    references: dict[str, str] = {}
    for element in style:
        if element.tag not in REQUIRED_STYLE:
            fail(f"style has unknown element <{element.tag}>")
        name = element.tag
        if name in references:
            fail(f"duplicate style element <{name}>")
        if list(element) or (element.text or "").strip():
            fail(f"style <{name}> must not have content")
        if (element.tail or "").strip():
            fail("style section must not contain text")
        if set(element.attrib) != {"value"}:
            fail(f"style <{name}> requires exactly one value attribute")

        expected_token = REQUIRED_STYLE[name]
        value = element.get("value", "")
        expected_value = f"@{expected_token}"
        if value != expected_value:
            fail(f"style <{name}> must reference {expected_value}")
        if expected_token not in token_names:
            fail(f"style <{name}> references unknown token {expected_token!r}")
        references[name] = expected_token

    missing = sorted(REQUIRED_STYLE.keys() - references.keys())
    if missing:
        fail(f"missing required style elements: {', '.join(missing)}")
    return references


def validate_native_typography_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)
    for forbidden in (
        "Liberation Sans",
        "FAMILY_SWISS",
        ".SetIconFont(",
        ".SetFamilyName(",
        ".SetFamily(",
        ".SetStyleName(",
        ".SetCharSet(",
        ".SetLanguage(",
        ".SetPitch(",
        ".SetOrientation(",
        ".SetFontWidth(",
    ):
        if forbidden in source:
            fail(f"native typography source contains forbidden override {forbidden!r}")
    required = (
        r"mpTypography\s*->\s*apply\s*\(\s*aStyleSet\s*,\s*aNativeStyleSet\s*\)",
        r"moNativeStyle",
        r"applyLegacyMinimumFontHeight\s*\(\s*aStyleSet\s*,\s*aNativeStyleSet\s*,",
        r"WidgetDefinitionTypography::apply",
        r"rTarget\.SetAppFont",
        r"rTarget\.SetTitleFont",
    )
    for pattern in required:
        if re.search(pattern, source) is None:
            fail(f"native typography source is missing pattern {pattern!r}")


def validate_native_style_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)

    required: list[str] = []
    for xml_name, (member, setter) in STYLE_SOURCE_CLOSURE.items():
        required.extend(
            (
                rf"std::optional\s*<\s*Color\s*>\s+{member}",
                rf'\{{\s*"{xml_name}"\s*,\s*&rWidgetDefinition\.mpStyle->{member}\s*\}}',
                rf"if\s*\(\s*pDefinitionStyle->{member}\s*\)\s*"
                rf"aStyleSet\.{setter}\s*\(\s*\*pDefinitionStyle->{member}\s*\)",
            )
        )

    required.extend(
        (
            r"StyleSettings::SetWarningTextColor",
            r"StyleSettings::SetErrorColor",
            r"StyleSettings::SetErrorTextColor",
            r"pGraphics\s*->\s*UpdateSettings\s*\(",
        )
    )
    for pattern in required:
        if re.search(pattern, source) is None:
            fail(f"native style source is missing pattern {pattern!r}")


def validate_native_shape_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)
    required = (
        r"bool\s+readShapeTokens\s*\(",
        r"bool\s+readRadiusReference\s*\(",
        r'aPaletteWalker\.name\(\)\s*==\s*"shapes"',
        r'rWalker\.attribute\(\s*"radius"_ostr\s*\)',
        r"if\s*\(\s*bHasRx\s*\|\|\s*bHasRy\s*\)",
        r"nRx\s*=\s*nRy\s*=\s*nRadius",
        r"readDefinition\s*\([^;]*aRadiusTokens\s*\)",
    )
    for pattern in required:
        if re.search(pattern, source) is None:
            fail(f"native shape source is missing pattern {pattern!r}")


def validate(path: Path) -> tuple[int, int, int, int, int, int, int]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
    root = ET.parse(path, parser=parser).getroot()
    if root.tag != "widgets":
        fail("root element must be <widgets>")

    palettes, palette_elements = read_palettes(root)
    token_names = set(palettes["light"])
    typography = read_typography(root)
    shapes = read_shapes(root)

    settings_sections = root.findall("settings")
    if len(settings_sections) != 1:
        fail(f"expected exactly one <settings> section, found {len(settings_sections)}")
    settings = settings_sections[0]
    if settings.find("defaultFontSize") is not None:
        fail("Material typography must not replace the native font with defaultFontSize")

    style_references = read_style(root, token_names)
    references: set[str] = set(style_references.values())

    if any(not isinstance(element.tag, str) for element in root.iter()):
        fail("Material definition must not contain processing instructions")

    shape_references: set[str] = set()
    for element in root.iter():
        if "rx" in element.attrib or "ry" in element.attrib:
            fail(f"{element.tag} must not use legacy rx or ry in Material definition")

        radius = element.get("radius")
        if radius is not None:
            if element.tag != "rect":
                fail(f"{element.tag}/@radius is only valid on <rect>")
            match = TOKEN_REFERENCE.fullmatch(radius)
            if match is None:
                fail("rect/@radius must reference a shape token")
            name = match.group(1)
            if name not in shapes:
                fail(f"rect/@radius references unknown shape token {name!r}")
            shape_references.add(name)

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
            if name not in token_names:
                fail(f"{element.tag}/@{attribute} references unknown token {name!r}")
            references.add(name)

    unused = sorted(token_names - references)
    if unused:
        fail(f"unused semantic tokens: {', '.join(unused)}")
    unused_shapes = sorted(shapes.keys() - shape_references)
    if unused_shapes:
        fail(f"unused shape tokens: {', '.join(unused_shapes)}")

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

    for part_name in ("ButtonDown", "ButtonUp"):
        validate_interaction_states(
            find_part(root, "spinbox", part_name), f"spinbox/{part_name}"
        )
    for part_name in ("ButtonDown", "ButtonUp", "ButtonLeft", "ButtonRight"):
        validate_interaction_states(
            find_part(root, "spinbuttons", part_name), f"spinbuttons/{part_name}"
        )

    contrast_pairs = (
        ("listBoxWindowTextColor", "listBoxWindowBackgroundColor"),
        ("listBoxWindowHighlightTextColor", "listBoxWindowHighlightColor"),
        ("warningTextColor", "warningColor"),
        ("errorTextColor", "errorColor"),
        ("windowTextColor", "windowColor"),
        ("fieldTextColor", "fieldColor"),
        ("menuTextColor", "menuColor"),
        ("highlightTextColor", "highlightColor"),
        ("helpTextColor", "helpColor"),
    )
    for scheme, tokens in palettes.items():
        style_colors = {
            style_name: tokens[token_name]
            for style_name, token_name in style_references.items()
        }
        for foreground, background in contrast_pairs:
            ratio = contrast(style_colors[foreground], style_colors[background])
            if ratio < 4.5:
                fail(
                    f"{scheme} {foreground}/{background} contrast is only "
                    f"{ratio:.2f}:1"
                )
        for foreground, background in (
            ("on-primary", "primary"),
            ("on-primary-container", "primary-container"),
            ("on-primary-container", "primary-hover"),
            ("on-primary-container", "primary-pressed"),
            ("on-surface", "primary-hover"),
            ("on-surface", "primary-pressed"),
        ):
            ratio = contrast(tokens[foreground], tokens[background])
            if ratio < 4.5:
                fail(
                    f"{scheme} {foreground}/{background} contrast is only "
                    f"{ratio:.2f}:1"
                )
        disabled_ratio = contrast(tokens["outline"], tokens["disabled-container"])
        if disabled_ratio < 3.0:
            fail(
                f"{scheme} outline/disabled-container contrast is only "
                f"{disabled_ratio:.2f}:1"
            )

    part_count = sum(len(control.findall("part")) for control in root
                     if control.tag not in {"palette", "shapes", "style", "settings", "typography"})
    state_count = sum(1 for _ in root.iter("state"))
    return (
        len(palettes),
        len(token_names),
        len(typography),
        len(shapes),
        len(style_references),
        part_count,
        state_count,
    )


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "definition",
        nargs="?",
        type=Path,
        default=repository / "vcl/uiconfig/theme_definitions/material/definition.xml",
    )
    parser.add_argument(
        "--renderer",
        type=Path,
        default=repository / "vcl/source/gdi/FileDefinitionWidgetDraw.cxx",
    )
    parser.add_argument(
        "--typography-source",
        type=Path,
        default=repository / "vcl/source/gdi/WidgetDefinition.cxx",
    )
    args = parser.parse_args()
    try:
        (
            scheme_count,
            token_count,
            typography_count,
            shape_count,
            style_count,
            part_count,
            state_count,
        ) = validate(args.definition)
        validate_native_typography_source((args.renderer, args.typography_source))
        validate_native_style_source(
            (
                repository / "vcl/inc/widgetdraw/WidgetDefinition.hxx",
                repository / "vcl/source/gdi/WidgetDefinitionReader.cxx",
                args.renderer,
                repository / "include/vcl/settings.hxx",
                repository / "vcl/source/app/settings.cxx",
                repository
                / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx",
            )
        )
        validate_native_shape_source(
            (
                repository / "vcl/inc/widgetdraw/WidgetDefinitionReader.hxx",
                repository / "vcl/source/gdi/WidgetDefinitionReader.cxx",
            )
        )
    except (ET.ParseError, OSError, ValidationError) as error:
        print(f"{args.definition}: {error}", file=sys.stderr)
        return 1
    print(
        f"Material theme OK: {scheme_count} schemes, {token_count} tokens each, "
        f"{typography_count} typography roles, {shape_count} shape tokens, "
        f"{style_count} style slots, "
        f"{part_count} parts, {state_count} states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
