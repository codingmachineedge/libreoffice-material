#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate semantic tokens and required VCL Material widget coverage."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


TOKEN_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
TOKEN_REFERENCE = re.compile(r"^@([a-z][a-z0-9-]*)$")
RADIUS_VALUE = re.compile(r"^(?:0|[1-9][0-9]*)$")
METRIC_VALUE = re.compile(r"^(?:0|[1-9][0-9]*)$")
REQUIRED_SCHEMES = {"light", "dark"}
# The bounded accent scheme set (Stage-1 appearance foundation). Each recolors
# only the primary* family + visited-link over the default light/dark neutrals;
# the composed active-scheme key is "<accent>" / "<accent>-dark" (Violet is the
# unnamed default "light"/"dark", never listed here so it can never be replaced).
ACCENT_SCHEMES = {
    "blue", "blue-dark", "teal", "teal-dark", "green", "green-dark",
    "amber", "amber-dark", "rose", "rose-dark",
}
ALLOWED_SCHEMES = REQUIRED_SCHEMES | ACCENT_SCHEMES
# Roles an accent scheme is permitted to recolor. Every other role must stay
# byte-identical to the accent's base neutrals (light for "<accent>", dark for
# "<accent>-dark").
PRIMARY_FAMILY_ROLES = {
    "primary", "on-primary", "primary-container", "on-primary-container",
    "primary-hover", "primary-pressed", "primary-action-hover",
    "primary-action-pressed", "visited-link",
}
NEUTRAL_ROLES = {
    "surface", "surface-container", "surface-container-low", "on-surface",
    "on-surface-variant", "outline", "outline-variant", "disabled-container",
    "inverse-surface", "inverse-on-surface", "warning-container",
    "on-warning-container", "error-container", "on-error-container",
}
# The unnamed default (light) and scheme="dark" palettes are FROZEN: adding
# accent schemes must never drift them, so genuine captures stay byte-stable.
EXPECTED_DEFAULT_LIGHT = {
    "primary": "#6750A4", "on-primary": "#FFFFFF", "primary-container": "#E8DEF8",
    "on-primary-container": "#1D192B", "primary-hover": "#D0BCFF",
    "primary-pressed": "#CCC2DC", "primary-action-hover": "#7965AF",
    "primary-action-pressed": "#5B3F91", "surface": "#FFFBFE",
    "surface-container": "#F3EDF7", "surface-container-low": "#F7F2FA",
    "on-surface": "#1D1B20", "on-surface-variant": "#49454F", "outline": "#79747E",
    "outline-variant": "#CAC4D0", "disabled-container": "#E6E0E9",
    "inverse-surface": "#313033", "inverse-on-surface": "#F4EFF4",
    "warning-container": "#FFDDB3", "on-warning-container": "#2A1800",
    "error-container": "#F9DEDC", "on-error-container": "#410E0B",
    "visited-link": "#7D5260",
}
EXPECTED_DEFAULT_DARK = {
    "primary": "#D0BCFF", "on-primary": "#381E72", "primary-container": "#4F378B",
    "on-primary-container": "#EADDFF", "primary-hover": "#4F378B",
    "primary-pressed": "#625B71", "primary-action-hover": "#C4AEFF",
    "primary-action-pressed": "#B69DF8", "surface": "#141218",
    "surface-container": "#211F26", "surface-container-low": "#1D1B20",
    "on-surface": "#E6E0E9", "on-surface-variant": "#CAC4D0", "outline": "#938F99",
    "outline-variant": "#49454F", "disabled-container": "#36343B",
    "inverse-surface": "#E6E0E9", "inverse-on-surface": "#322F35",
    "warning-container": "#5F4100", "on-warning-container": "#FFDDB3",
    "error-container": "#8C1D18", "on-error-container": "#F9DEDC",
    "visited-link": "#EFB8C8",
}
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
REQUIRED_METRICS = {
    "stroke-none": 0,
    "stroke-thin": 1,
    "stroke-standard": 2,
    "stroke-track": 4,
    "space-list-entry": 12,
    "space-tab-inline": 12,
    "height-floating-title": 14,
    "size-menu-indicator": 18,
    "height-window-title": 18,
    "size-list-preview": 18,
    "size-tree-node": 20,
    "size-selection-control": 24,
    "size-compact-control": 28,
    "size-standard-control": 36,
    "height-tab": 40,
}
REQUIRED_METRIC_USAGE = {
    "stroke-none": 96,
    "stroke-thin": 49,
    "stroke-standard": 155,
    "stroke-track": 8,
    "space-list-entry": 1,
    "space-tab-inline": 1,
    "height-floating-title": 1,
    "size-menu-indicator": 6,
    "height-window-title": 1,
    "size-list-preview": 2,
    "size-tree-node": 2,
    "size-selection-control": 4,
    "size-compact-control": 12,
    "size-standard-control": 8,
    "height-tab": 1,
}
REQUIRED_SETTING_METRICS = {
    "listBoxEntryMargin": "space-list-entry",
    "titleHeight": "height-window-title",
    "floatTitleHeight": "height-floating-title",
    "listBoxPreviewDefaultLogicWidth": "size-list-preview",
    "listBoxPreviewDefaultLogicHeight": "size-list-preview",
}
REQUIRED_PART_METRICS = {
    ("radiobutton", "Entire", "width"): "size-selection-control",
    ("radiobutton", "Entire", "height"): "size-selection-control",
    ("checkbox", "Entire", "width"): "size-selection-control",
    ("checkbox", "Entire", "height"): "size-selection-control",
    ("combobox", "ButtonDown", "width"): "size-standard-control",
    ("combobox", "ButtonDown", "height"): "size-standard-control",
    ("editbox", "Entire", "height"): "size-standard-control",
    ("editboxnoborder", "Entire", "height"): "size-standard-control",
    ("listbox", "ButtonDown", "width"): "size-standard-control",
    ("listbox", "ButtonDown", "height"): "size-standard-control",
    ("spinbox", "ButtonDown", "width"): "size-standard-control",
    ("spinbox", "ButtonDown", "height"): "size-compact-control",
    ("spinbox", "ButtonUp", "width"): "size-standard-control",
    ("spinbox", "ButtonUp", "height"): "size-compact-control",
    ("spinbuttons", "ButtonUp", "width"): "size-compact-control",
    ("spinbuttons", "ButtonUp", "height"): "size-compact-control",
    ("spinbuttons", "ButtonDown", "width"): "size-compact-control",
    ("spinbuttons", "ButtonDown", "height"): "size-compact-control",
    ("spinbuttons", "ButtonLeft", "width"): "size-compact-control",
    ("spinbuttons", "ButtonLeft", "height"): "size-compact-control",
    ("spinbuttons", "ButtonRight", "width"): "size-compact-control",
    ("spinbuttons", "ButtonRight", "height"): "size-compact-control",
    ("slider", "Button", "width"): "size-compact-control",
    ("slider", "Button", "height"): "size-compact-control",
    ("tabitem", "Entire", "height"): "height-tab",
    ("tabitem", "Entire", "margin-width"): "space-tab-inline",
    ("listnode", "Entire", "width"): "size-tree-node",
    ("listnode", "Entire", "height"): "size-tree-node",
    ("menupopup", "MenuItemCheckMark", "width"): "size-menu-indicator",
    ("menupopup", "MenuItemCheckMark", "height"): "size-menu-indicator",
    ("menupopup", "MenuItemRadioMark", "width"): "size-menu-indicator",
    ("menupopup", "MenuItemRadioMark", "height"): "size-menu-indicator",
    ("menupopup", "SubmenuArrow", "width"): "size-menu-indicator",
    ("menupopup", "SubmenuArrow", "height"): "size-menu-indicator",
}
STROKE_METRICS = {
    "stroke-none",
    "stroke-thin",
    "stroke-standard",
    "stroke-track",
}
METRIC_PART_ATTRIBUTES = ("width", "height", "margin-width", "margin-height")
METRIC_GEOMETRY_SHA256 = (
    "b14802df66934f83303c7da311fb8b421c5d58d119e418edb345dd68e20504fa"
)
NORMALIZED_COORDINATE_SHA256 = (
    "8345cd2865759bc8a73f9a7845af2b5d420ea4812c75bcdfe3ba038a13c402e8"
)

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
    "disableColor": "on-surface-variant",
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
    "progress": {"Entire", "TrackHorzArea"},
    "levelbar": {"Entire", "TrackHorzArea"},
    "tabitem": {"Entire", "MenuItem"},
    "tabheader": {"Entire"},
    "tabpane": {"Entire"},
    "tabbody": {"Entire"},
    "windowbackground": {"Entire", "BackgroundWindow", "BackgroundDialog"},
    "frame": {"Border"},
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
    "listnet": {"Entire"},
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


def validate_indicator_states(root: ET.Element) -> None:
    expected_parts = {
        ("progress", "TrackHorzArea"): (
            ({"enabled": "true"}, "enabled", "outline-variant"),
            ({"enabled": "false"}, "disabled", "disabled-container"),
        ),
        ("progress", "Entire"): (
            ({"enabled": "true"}, "enabled", "primary"),
            ({"enabled": "false"}, "disabled", "outline-variant"),
        ),
        ("levelbar", "TrackHorzArea"): (
            ({"enabled": "true"}, "enabled", "outline-variant"),
            ({"enabled": "false"}, "disabled", "disabled-container"),
        ),
        ("levelbar", "Entire"): (
            ({"enabled": "true", "extra": "critical"}, "critical", "error-container"),
            ({"enabled": "true", "extra": "low"}, "low", "warning-container"),
            ({"enabled": "true", "extra": "medium"}, "medium", "primary-hover"),
            ({"enabled": "true", "extra": "high"}, "high", "primary"),
            ({"enabled": "false"}, "disabled", "outline-variant"),
        ),
    }

    for (control_name, part_name), expected_states in expected_parts.items():
        label = f"{control_name}/{part_name}"
        part = find_part(root, control_name, part_name)
        states = part.findall("state")
        if len(states) != len(expected_states):
            fail(
                f"{label} must define exactly {len(expected_states)} states, "
                f"found {len(states)}"
            )

        expected_by_attributes = {
            tuple(sorted(attributes.items())): (state_name, color_name)
            for attributes, state_name, color_name in expected_states
        }
        seen: set[tuple[tuple[str, str], ...]] = set()
        for state in states:
            attributes = tuple(sorted(state.attrib.items()))
            expected = expected_by_attributes.get(attributes)
            if expected is None:
                fail(f"{label} has unexpected state attributes {dict(attributes)!r}")
            if attributes in seen:
                fail(f"{label} duplicates its {expected[0]} state")
            seen.add(attributes)

            state_name, color_name = expected
            actions = list(state)
            if (
                len(actions) != 1
                or actions[0].tag != "rect"
                or (state.text or "").strip()
                or (actions[0].tail or "").strip()
            ):
                fail(f"{label} {state_name} state must contain exactly one rectangle")
            expected_rectangle = {
                "stroke": f"@{color_name}",
                "fill": f"@{color_name}",
                "stroke-width": "@stroke-none",
                "radius": "@corner-indicator",
            }
            if (
                actions[0].attrib != expected_rectangle
                or list(actions[0])
                or (actions[0].text or "").strip()
            ):
                fail(f"{label} {state_name} rectangle has the wrong Material anatomy")


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
    missing_schemes = sorted(ALLOWED_SCHEMES - palettes.keys())
    if missing_schemes:
        fail(f"missing palette schemes: {', '.join(missing_schemes)}")
    unexpected_schemes = sorted(palettes.keys() - ALLOWED_SCHEMES)
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


def validate_scheme_stability(
    palettes: dict[str, dict[str, tuple[int, int, int]]]
) -> None:
    """The default (light) + scheme="dark" palettes are frozen byte-identical, and
    every accent scheme recolors only the primary* family + visited-link, keeping
    its base neutrals unchanged. This fails closed if the default drifts or an
    accent silently retints a neutral role."""

    for scheme_name, expected in (
        ("light", EXPECTED_DEFAULT_LIGHT),
        ("dark", EXPECTED_DEFAULT_DARK),
    ):
        tokens = palettes.get(scheme_name)
        if tokens is None:
            fail(f"{scheme_name} palette missing")
        actual_names = set(tokens)
        expected_names = set(expected)
        if actual_names != expected_names:
            extra = sorted(actual_names - expected_names)
            missing = sorted(expected_names - actual_names)
            details = []
            if missing:
                details.append(f"missing {', '.join(missing)}")
            if extra:
                details.append(f"unexpected {', '.join(extra)}")
            fail(f"frozen {scheme_name} palette role set drifted: {'; '.join(details)}")
        for role, hex_value in expected.items():
            expected_rgb = parse_color(hex_value)
            if tokens[role] != expected_rgb:
                fail(
                    f"frozen {scheme_name} palette role {role!r} must stay "
                    f"{hex_value} (default scheme is byte-frozen so genuine "
                    f"captures never drift), found {format_color(tokens[role])}"
                )

    for scheme_name, tokens in palettes.items():
        if scheme_name not in ACCENT_SCHEMES:
            continue
        base_name = "dark" if scheme_name.endswith("-dark") else "light"
        base_tokens = palettes[base_name]
        recolored = {
            role
            for role in tokens
            if base_tokens.get(role) != tokens.get(role)
        }
        illegal = sorted(recolored - PRIMARY_FAMILY_ROLES)
        if illegal:
            fail(
                f"accent scheme {scheme_name!r} recolors non-primary role(s) "
                f"{', '.join(illegal)}: only the primary* family + visited-link "
                f"may differ from the {base_name} neutrals"
            )
        for role in NEUTRAL_ROLES:
            if tokens.get(role) != base_tokens.get(role):
                fail(
                    f"accent scheme {scheme_name!r} neutral role {role!r} must be "
                    f"byte-identical to the {base_name} palette"
                )


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


def read_metrics(root: ET.Element) -> dict[str, int]:
    sections = root.findall("metrics")
    if len(sections) != 1:
        fail(f"expected exactly one <metrics> section, found {len(sections)}")
    metrics_element = sections[0]
    if metrics_element.attrib:
        fail("metrics section must not have attributes")
    if (metrics_element.text or "").strip():
        fail("metrics section must not contain text")

    metrics: dict[str, int] = {}
    for element in metrics_element:
        if not isinstance(element.tag, str):
            fail("metrics section must not contain processing instructions")
        if element.tag != "metric":
            fail(f"metrics has unknown element <{element.tag}>")
        if list(element) or (element.text or "").strip():
            fail(f"metric token {element.get('name', '')!r} must not have content")
        if (element.tail or "").strip():
            fail("metrics section must not contain text")

        unknown_attributes = sorted(set(element.attrib) - {"name", "value"})
        if unknown_attributes:
            fail("metric token has unknown attributes: " + ", ".join(unknown_attributes))
        if set(element.attrib) != {"name", "value"}:
            fail("metric tokens require exactly name and value attributes")

        name = element.get("name", "")
        if not TOKEN_NAME.fullmatch(name):
            fail(f"invalid metric token name {name!r}")
        if name not in REQUIRED_METRICS:
            fail(f"unknown metric token {name!r}")
        if name in metrics:
            fail(f"duplicate metric token {name!r}")

        value_text = element.get("value", "")
        if not METRIC_VALUE.fullmatch(value_text):
            fail(f"invalid metric value {value_text!r} for {name!r}")
        value = int(value_text)
        if value > 2_147_483_647:
            fail(f"metric value for {name!r} exceeds sal_Int32")
        expected = REQUIRED_METRICS[name]
        if value != expected:
            fail(f"metric token {name!r} must be {expected}, found {value}")
        metrics[name] = value

    if not metrics:
        fail("metrics section is empty")
    missing = sorted(REQUIRED_METRICS.keys() - metrics.keys())
    if missing:
        fail(f"missing metric tokens: {', '.join(missing)}")

    metric_elements = set(metrics_element.iter())
    for element in root.iter():
        if (
            isinstance(element.tag, str)
            and element.tag in {"metrics", "metric"}
            and element not in metric_elements
        ):
            fail(f"<{element.tag}> must appear only in the root <metrics> section")
    return metrics


def _element_paths(root: ET.Element) -> dict[ET.Element, str]:
    paths = {root: "widgets[0]"}

    def visit(parent: ET.Element) -> None:
        seen: dict[str, int] = {}
        for child in parent:
            if not isinstance(child.tag, str):
                continue
            index = seen.get(child.tag, 0)
            seen[child.tag] = index + 1
            paths[child] = f"{paths[parent]}/{child.tag}[{index}]"
            visit(child)

    visit(root)
    return paths


def _metric_reference(
    element: ET.Element,
    attribute: str,
    label: str,
    metrics: dict[str, int],
) -> tuple[str, int]:
    value = element.get(attribute)
    if value is None:
        fail(f"{label} must reference a metric token")
    match = TOKEN_REFERENCE.fullmatch(value)
    if match is None:
        fail(f"{label} must reference a metric token")
    name = match.group(1)
    if name not in metrics:
        fail(f"{label} references unknown metric token {name!r}")
    return name, metrics[name]


def validate_metric_usage(
    root: ET.Element, metrics: dict[str, int]
) -> tuple[Counter[str], str]:
    paths = _element_paths(root)
    references: Counter[str] = Counter()
    geometry_rows: list[str] = []
    consumed: set[tuple[ET.Element, str]] = set()

    settings = root.find("settings")
    if settings is None:
        fail("missing settings section")
    for setting_name, expected_name in REQUIRED_SETTING_METRICS.items():
        elements = settings.findall(setting_name)
        if len(elements) != 1:
            fail(
                f"expected exactly one settings/{setting_name}, found {len(elements)}"
            )
        element = elements[0]
        if set(element.attrib) != {"value"}:
            fail(f"settings/{setting_name} requires exactly one value attribute")
        if list(element) or (element.text or "").strip():
            fail(f"settings/{setting_name} must not have content")
        name, value = _metric_reference(
            element, "value", f"settings/{setting_name}/@value", metrics
        )
        if name != expected_name:
            fail(f"settings/{setting_name}/@value must reference @{expected_name}")
        references[name] += 1
        consumed.add((element, "value"))
        geometry_rows.append(f"{paths[element]}@value={value}")

    actual_part_slots: set[tuple[str, str, str]] = set()
    for control in root:
        if not isinstance(control.tag, str):
            continue
        for part in control.findall("part"):
            part_name = part.get("value", "")
            for attribute in METRIC_PART_ATTRIBUTES:
                if attribute not in part.attrib:
                    continue
                slot = (control.tag, part_name, attribute)
                label = f"{control.tag}/{part_name}/@{attribute}"
                if slot in actual_part_slots:
                    fail(f"duplicate Material metric slot {label}")
                actual_part_slots.add(slot)
                expected_name = REQUIRED_PART_METRICS.get(slot)
                if expected_name is None:
                    fail(f"unexpected Material metric slot {label}")
                name, value = _metric_reference(part, attribute, label, metrics)
                if name != expected_name:
                    fail(f"{label} must reference @{expected_name}")
                references[name] += 1
                consumed.add((part, attribute))
                geometry_rows.append(f"{paths[part]}@{attribute}={value}")

    missing_part_slots = sorted(REQUIRED_PART_METRICS.keys() - actual_part_slots)
    if missing_part_slots:
        control, part, attribute = missing_part_slots[0]
        fail(f"missing Material metric slot {control}/{part}/@{attribute}")

    for element in root.iter():
        if element.tag not in {"rect", "line"}:
            continue
        label = f"{element.tag}/@stroke-width"
        name, value = _metric_reference(element, "stroke-width", label, metrics)
        if name not in STROKE_METRICS:
            fail(f"{label} must reference a stroke metric token")
        references[name] += 1
        consumed.add((element, "stroke-width"))
        geometry_rows.append(f"{paths[element]}@stroke-width={value}")

    coordinate_count = 0
    coordinate_patterns: set[tuple[float, float, float, float]] = set()
    coordinate_rows: list[str] = []
    allowed_non_metric_references: set[tuple[ET.Element, str]] = set()
    style = root.find("style")
    if style is not None:
        allowed_non_metric_references.update((element, "value") for element in style)
    for element in root.iter():
        if element.tag == "rect":
            allowed_non_metric_references.update(
                (element, attribute)
                for attribute in ("stroke", "fill")
                if attribute in element.attrib
            )
        elif element.tag == "line" and "stroke" in element.attrib:
            allowed_non_metric_references.add((element, "stroke"))
        if element.tag == "rect" and "radius" in element.attrib:
            allowed_non_metric_references.add((element, "radius"))

    coordinate_attributes = ("x1", "y1", "x2", "y2")
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        if element.tag in {"rect", "line"}:
            present = {
                attribute
                for attribute in coordinate_attributes
                if attribute in element.attrib
            }
            if element.tag == "line" or present:
                missing = set(coordinate_attributes) - present
                if missing:
                    fail(
                        f"{element.tag} coordinate set is incomplete: "
                        f"missing {', '.join(sorted(missing))}"
                    )
                coordinates: dict[str, float] = {}
                for attribute in coordinate_attributes:
                    value = element.get(attribute, "")
                    if value.startswith("@"):
                        fail(
                            f"{element.tag}/@{attribute} must remain a normalized "
                            "numeric coordinate"
                        )
                    try:
                        coordinate = float(value)
                    except ValueError:
                        fail(
                            f"{element.tag}/@{attribute} must be a normalized "
                            "numeric coordinate"
                        )
                    if not math.isfinite(coordinate) or not 0.0 <= coordinate <= 1.0:
                        fail(
                            f"{element.tag}/@{attribute} must be between 0 and 1"
                        )
                    coordinates[attribute] = coordinate
                    coordinate_rows.append(
                        f"{paths[element]}@{attribute}={value}"
                    )
                if element.tag == "rect" and (
                    coordinates["x1"] > coordinates["x2"]
                    or coordinates["y1"] > coordinates["y2"]
                ):
                    fail(
                        "rect normalized coordinates must be ordered x1 <= x2 and y1 <= y2"
                    )
                coordinate_count += 4
                coordinate_patterns.add(
                    tuple(coordinates[name] for name in coordinate_attributes)
                )
        for attribute, value in element.attrib.items():
            slot = (element, attribute)
            if (
                value.startswith("@")
                and slot not in consumed
                and slot not in allowed_non_metric_references
            ):
                match = TOKEN_REFERENCE.fullmatch(value)
                if match is not None and match.group(1) in metrics:
                    fail(f"{element.tag}/@{attribute} must not reference a metric token")
                fail(f"{element.tag}/@{attribute} must not reference a token")

    if coordinate_count != 684:
        fail(f"expected 684 normalized coordinate scalars, found {coordinate_count}")
    if len(coordinate_patterns) != 45:
        fail(
            "expected 45 normalized coordinate patterns, "
            f"found {len(coordinate_patterns)}"
        )
    coordinate_digest = hashlib.sha256(
        "\n".join(sorted(coordinate_rows)).encode("utf-8")
    ).hexdigest()
    if coordinate_digest != NORMALIZED_COORDINATE_SHA256:
        fail(
            "normalized coordinate geometry changed: "
            f"expected {NORMALIZED_COORDINATE_SHA256}, found {coordinate_digest}"
        )

    unused = sorted(metrics.keys() - references.keys())
    if unused:
        fail(f"unused metric tokens: {', '.join(unused)}")
    expected_usage = Counter(REQUIRED_METRIC_USAGE)
    if references != expected_usage:
        fail(
            "metric reference counts changed: "
            f"expected {dict(sorted(expected_usage.items()))}, "
            f"found {dict(sorted(references.items()))}"
        )
    expected_geometry_rows = sum(REQUIRED_METRIC_USAGE.values())
    if len(geometry_rows) != expected_geometry_rows:
        fail(
            f"expected {expected_geometry_rows} resolved metric geometry rows, "
            f"found {len(geometry_rows)}"
        )

    geometry_digest = hashlib.sha256(
        "\n".join(sorted(geometry_rows)).encode("utf-8")
    ).hexdigest()
    if geometry_digest != METRIC_GEOMETRY_SHA256:
        fail(
            "resolved Material metric geometry changed: "
            f"expected {METRIC_GEOMETRY_SHA256}, found {geometry_digest}"
        )
    return references, geometry_digest


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


CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\('
    r'.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    source = CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def validate_native_typography_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = strip_cpp_non_code(source)
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
    source = strip_cpp_non_code(source)

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
    source = strip_cpp_non_code(source)
    required = (
        r"bool\s+readShapeTokens\s*\(",
        r"bool\s+readRadiusReference\s*\(",
        r'aPaletteWalker\.name\(\)\s*==\s*"shapes"',
        r'rWalker\.attribute\(\s*"radius"_ostr\s*\)',
        r"if\s*\(\s*bHasRx\s*\|\|\s*bHasRy\s*\)",
        r"nRx\s*=\s*nRy\s*=\s*nRadius",
        r"readDefinition\s*\([^;]*aRadiusTokens\s*[,)]",
    )
    for pattern in required:
        if re.search(pattern, source) is None:
            fail(f"native shape source is missing pattern {pattern!r}")


def validate_native_metric_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = strip_cpp_non_code(source)
    required = (
        r"bool\s+readMetricTokens\s*\(",
        r"bool\s+readMetricReference\s*\(",
        r"bool\s+readMetricSetting\s*\(",
        r"bool\s+readLiteralSetting\s*\(",
        r"bool\s+readLegacyRadius\s*\(",
        r"bool\s+readDrawingCoordinate\s*\(",
        r'aPaletteWalker\.name\(\)\s*==\s*"metrics"',
        r"if\s*\(\s*!\s*readMetricTokens\s*\(\s*aPaletteWalker\s*,\s*"
        r"aTokens\s*\)\s*\)\s*m_bValid\s*=\s*false",
        r"readMetricReference\s*\(\s*sStrokeWidth\s*,\s*rMetricTokens\s*,",
        r"readMetricReference\s*\(\s*sWidth\s*,\s*rMetricTokens\s*,",
        r"readMetricReference\s*\(\s*sHeight\s*,\s*rMetricTokens\s*,",
        r"readMetricReference\s*\(\s*sMarginHeight\s*,\s*rMetricTokens\s*,",
        r"readMetricReference\s*\(\s*sMarginWidth\s*,\s*rMetricTokens\s*,",
        r"readLegacyRadius\s*\(\s*sRx\s*,\s*nRx\s*\)",
        r"readLegacyRadius\s*\(\s*sRy\s*,\s*nRy\s*\)",
        r"readMetricSetting\s*\(\s*aWalker\.attribute\(\s*"
        r'"value"_ostr\s*\)\s*,\s*aMetricTokens\s*,',
        r"readLiteralSetting\s*\(\s*aWalker\.attribute\(\s*"
        r'"value"_ostr\s*\)\s*,',
        r'readDrawingCoordinate\s*\(\s*rWalker\.attribute\(\s*"x1"_ostr\s*\)',
        r'readDrawingCoordinate\s*\(\s*rWalker\.attribute\(\s*"y1"_ostr\s*\)',
        r'readDrawingCoordinate\s*\(\s*rWalker\.attribute\(\s*"x2"_ostr\s*\)',
        r'readDrawingCoordinate\s*\(\s*rWalker\.attribute\(\s*"y2"_ostr\s*\)',
        r"readPart\s*\([^;]*rRadiusTokens\s*,\s*rMetricTokens\s*\)",
        r"readDrawingDefinition\s*\([^;]*rRadiusTokens\s*,\s*rMetricTokens\s*\)",
        r"readDefinition\s*\([^;]*aRadiusTokens\s*,\s*aMetricTokens\s*\)",
    )
    for setting_name, member_name in (
        ("listBoxEntryMargin", "msListBoxEntryMargin"),
        ("titleHeight", "msTitleHeight"),
        ("floatTitleHeight", "msFloatTitleHeight"),
        ("listBoxPreviewDefaultLogicWidth", "msListBoxPreviewDefaultLogicWidth"),
        ("listBoxPreviewDefaultLogicHeight", "msListBoxPreviewDefaultLogicHeight"),
    ):
        required += (
            rf'\{{\s*"{setting_name}"\s*,\s*'
            rf"&rWidgetDefinition\.mpSettings->{member_name}\s*\}}",
        )
    for pattern in required:
        if re.search(pattern, source) is None:
            fail(f"native metric source is missing pattern {pattern!r}")

    direct_conversion = re.search(
        r"\b(sStrokeWidth|sWidth|sHeight|sMarginHeight|sMarginWidth)\s*"
        r"\.\s*toInt32\s*\(",
        source,
    )
    if direct_conversion is not None:
        fail(
            "native metric source contains direct consumer conversion "
            f"{direct_conversion.group(1)!r}"
        )


def validate_native_indicator_source(paths: tuple[Path, ...]) -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    source = strip_cpp_non_code(source)
    required = (
        r"tools::Long\s+getLevelBarStateValue\s*\(",
        r"nFullWidth\s*/\s*4\s*\+\s*\(\s*nFullWidth\s*%\s*4\s*!=\s*0\s*\)",
        r"nFullWidth\s*-\s*nFullWidth\s*/\s*4",
        r"case\s+ControlType::LevelBar\s*:",
        r'nPercent\s*<\s*2500[^;]*sExtra\s*=\s*"critical"',
        r'nPercent\s*<\s*5000[^;]*sExtra\s*=\s*"low"',
        r'nPercent\s*<\s*7500[^;]*sExtra\s*=\s*"medium"',
        r'sExtra\s*=\s*"high"',
        r"ePart\s*!=\s*ControlPart::Entire",
        r"pWidgetDefinition\s*->\s*getDefinition\s*\(\s*"
        r"eType\s*,\s*ControlPart::TrackHorzArea\s*\)",
        r"bOK\s*=\s*!\s*pTrack\s*\|\|\s*resolveDefinition\s*\(\s*"
        r"eType\s*,\s*ControlPart::TrackHorzArea",
        r"std::max\s*\(\s*nWidth\s*,\s*tools::Long\s*\(\s*0\s*\)\s*\)",
        r"if\s*\(\s*nProgressWidth\s*==\s*0\s*\)\s*break",
        r"getLevelBarStateValue\s*\(\s*rValue\.getNumericVal\s*\(\s*\)\s*,\s*"
        r"rControlRegion\.GetWidth\s*\(\s*\)\s*\)",
        r"testProgressAndLevelIndicatorTracks",
        r"ControlType::Progress\s*,\s*ControlPart::TrackHorzArea",
        r"ControlType::LevelBar\s*,\s*ControlPart::TrackHorzArea",
        r"ImplControlValue\s*\(\s*tools::Long\s*\(\s*0\s*\)\s*\)",
    )
    for pattern in required:
        if re.search(pattern, source, flags=re.DOTALL) is None:
            fail(f"native indicator source is missing pattern {pattern!r}")


def validate_native_container_source(
    renderer_paths: tuple[Path, ...], reader_paths: tuple[Path, ...]
) -> None:
    renderer = strip_cpp_non_code(
        "\n".join(path.read_text(encoding="utf-8") for path in renderer_paths)
    )
    reader = strip_cpp_non_code(
        "\n".join(path.read_text(encoding="utf-8") for path in reader_paths)
    )
    # The frame's native region case is the only source this milestone adds to
    # the renderer, so it is asserted as a single unit: the Border-guard, the
    # full-bleed bounding region, and the 2px content inset must co-occur. That
    # inset is the native content-region inset D-017 required before the frame
    # could leave fallback; anchoring it here fails the check if the region case
    # is removed even though the pre-existing drawNativeControl Frame dispatch
    # remains.
    frame_region_case = (
        r"case\s+ControlType::Frame\s*:.*?"
        r"getDefinition\s*\(\s*eType\s*,\s*ControlPart::Border\s*\).*?"
        r"rNativeBoundingRegion\s*=\s*rBoundingControlRegion\s*;\s*"
        r"rNativeContentRegion\s*=\s*rBoundingControlRegion\s*;\s*"
        r"rNativeContentRegion\s*\.\s*AdjustLeft\s*\(\s*2\s*\)\s*;\s*"
        r"rNativeContentRegion\s*\.\s*AdjustTop\s*\(\s*2\s*\)\s*;\s*"
        r"rNativeContentRegion\s*\.\s*AdjustRight\s*\(\s*-\s*2\s*\)\s*;\s*"
        r"rNativeContentRegion\s*\.\s*AdjustBottom\s*\(\s*-\s*2\s*\)\s*;"
    )
    if re.search(frame_region_case, renderer, flags=re.DOTALL) is None:
        fail("native container renderer is missing the inset Frame region case")
    # Dependency assertions on the support chain these controls rely on. The
    # reader mappings and the ListNet draw dispatch are shared/upstream scaffolding
    # rather than code this milestone added, but the Material frame and net-less
    # tree break silently if any of them is later removed, so they are checked.
    if re.search(r"case\s+ControlType::ListNet\s*:", renderer, flags=re.DOTALL) is None:
        fail("native container renderer is missing the ListNet draw dispatch")
    for pattern in (
        r'\{\s*"frame"\s*,\s*ControlType::Frame\s*\}',
        r'\{\s*"listnet"\s*,\s*ControlType::ListNet\s*\}',
        r'o3tl::equalsIgnoreAsciiCase\s*\(\s*sPart\s*,\s*"Border"\s*\)',
    ):
        if re.search(pattern, reader, flags=re.DOTALL) is None:
            fail(f"native container reader source is missing pattern {pattern!r}")


def validate(path: Path) -> tuple[int, int, int, int, int, int, int, int]:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
    root = ET.parse(path, parser=parser).getroot()
    if root.tag != "widgets":
        fail("root element must be <widgets>")

    palettes, palette_elements = read_palettes(root)
    token_names = set(palettes["light"])
    typography = read_typography(root)
    shapes = read_shapes(root)
    metrics = read_metrics(root)

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
    validate_metric_usage(root, metrics)

    for control_name, required_parts in REQUIRED_PARTS.items():
        control = root.find(control_name)
        if control is None:
            fail(f"missing control {control_name}")
        actual_parts = {part.get("value", "") for part in control.findall("part")}
        missing_parts = sorted(required_parts - actual_parts)
        if missing_parts:
            fail(f"{control_name} missing parts: {', '.join(missing_parts)}")

    validate_indicator_states(root)

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

    # Runs after the per-scheme contrast pass so a default-neutral edit still
    # surfaces its concrete contrast/feedback failure first; this then fails
    # closed on any surviving default drift or illegal accent neutral retint.
    validate_scheme_stability(palettes)

    part_count = sum(
        len(control.findall("part"))
        for control in root
        if control.tag
        not in {"palette", "shapes", "metrics", "style", "settings", "typography"}
    )
    state_count = sum(1 for _ in root.iter("state"))
    return (
        len(palettes),
        len(token_names),
        len(typography),
        len(shapes),
        len(metrics),
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
            metric_count,
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
        validate_native_metric_source(
            (
                repository / "vcl/inc/widgetdraw/WidgetDefinitionReader.hxx",
                repository / "vcl/source/gdi/WidgetDefinitionReader.cxx",
            )
        )
        validate_native_indicator_source(
            (
                args.renderer,
                args.typography_source,
                repository
                / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx",
            )
        )
        validate_native_container_source(
            (args.renderer,),
            (repository / "vcl/source/gdi/WidgetDefinitionReader.cxx",),
        )
    except (ET.ParseError, OSError, ValidationError) as error:
        print(f"{args.definition}: {error}", file=sys.stderr)
        return 1
    print(
        f"Material theme OK: {scheme_count} schemes, {token_count} color tokens each, "
        f"{typography_count} typography roles, {shape_count} shape tokens, "
        f"{metric_count} metric tokens, "
        f"{style_count} style slots, "
        f"{part_count} parts, {state_count} states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
