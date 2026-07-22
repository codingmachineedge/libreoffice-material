#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the native Material sidebar deck & side panes (WIN-CON-007).

Design 06 s6.7 is explicit that the deck, panel titles, section headings, the
12px scrollbar, the collapse-to-rail and the below-medium overlay are
*sidebar-framework* chrome -- "deck layout and the rail belong to the sidebar
framework ... restyled per surface later" -- so their Material metrics and
colour palette live in the sfx2 sidebar ``Theme`` and are consumed by ``Deck`` /
``DeckTitleBar`` / ``SidebarController``, NOT as VCL widget-definition parts.
(This diverges from the row plan's mention of definition.xml and of
DeckLayouter/Panel/PanelTitleBar/PanelFactory; the design chapter wins and the
audit found those files need no change -- see the registry ``note``.) This row
consumes, and does not fork, the NAV-005 rail primitive.

The registry ``qa/windows-ui-contract/sidebar-panels.json`` pins the design
ground truth:

* the properties deck, its title bar, and the panels sit on ``@surface``
  (re-sourced on the Material path from the existing ``Color_Deck*`` /
  ``Color_Panel*`` slots), one tonal step brighter than the ``@surface-container``
  rail so the deck/rail hairline reads;
* a 14px deck content inset (the existing ``Int_Deck*Padding`` slots, guarded to
  the Material value); the deck title in the ``title`` type role (@on-surface,
  120% scale, semibold); 11px uppercase section headings in @on-surface-variant
  (pinned; the panel title bar is a ``weld::Expander`` with no font API, so this
  colour/height is the source of truth for the later panel-heading paint row);
* the 12px Material deck scrollbar; and the collapse-to-rail plus below-medium
  overlay-degrade behaviours.

This checker enforces that the sfx2 sidebar framework carries that contract as
real, guarded native wiring:

* ``Theme`` declares one enum slot per new colour/metric, registers each in both
  property-name maps, classifies each in ``GetPropertyType`` and *sets* each in
  ``UpdateTheme`` -- the metrics to their literal density-invariant values, the
  colours from the Material-mapped ``StyleSettings`` getter that resolves to the
  named token, the deck surface behind the ``IsMaterialDeck`` guard, and the
  14px padding behind the same guard;
* ``Deck`` applies the 12px scrollbar behind the guard and keeps the deck fill
  on ``Color_DeckBackground``;
* ``DeckTitleBar`` applies the title role (colour + semibold + 120% scale) behind
  the guard; and
* ``SidebarController`` keeps click-active-to-collapse (``OpenThenToggleDeck``
  closing the visible deck) and consumes the overlay threshold through the
  guarded ``ShouldDeckOverlayCanvas`` predicate.

Every source assertion runs against a comment/raw-string-stripped copy of the
file, so commented-out wiring fails closed. It is source evidence only: no
native build, deck pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/sidebar-panels.json"

# The colour tokens a deck state can reference, keyed by the slot that provides
# them, so the registry's human-readable state table stays consistent with the
# Theme colour slots it is drawn from.
STATE_TOKEN_KEYS = ("fill", "text")


class ValidationError(RuntimeError):
    """Raised when the Material deck & side panes contract is incomplete or weakened."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


# --------------------------------------------------------------------------------------------------
# C++ comment / raw-string stripping so commented-out wiring can never satisfy a marker.
# --------------------------------------------------------------------------------------------------
_CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    source = _CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


# --------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------
_COLOR_SLOT = re.compile(r"^Color_[A-Za-z0-9]+$")
_INT_SLOT = re.compile(r"^Int_[A-Za-z0-9]+$")
_GETTER_NAME = re.compile(r"^Get[A-Za-z0-9]+$")
_TOKEN_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def load_registry(registry_path: Path) -> dict:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    required_top = (
        "guard_env",
        "guard_helper",
        "theme_header",
        "theme_source",
        "deck_source",
        "deck_title_source",
        "controller_source",
        "deck_surface",
        "deck_padding",
        "colors",
        "metrics",
        "states",
        "deck_fill_marker",
        "deck_scrollbar_marker",
        "deck_title_markers",
        "collapse_function",
        "collapse_markers",
        "overlay_function",
        "overlay_threshold_marker",
        "overlay_consume_marker",
    )
    missing = [key for key in required_top if key not in data]
    if missing:
        raise ValidationError("registry is missing keys: " + ", ".join(missing))

    seen_slots: set[str] = set()

    def claim_slot(slot: str, pattern: re.Pattern[str], where: str) -> None:
        if not isinstance(slot, str) or pattern.fullmatch(slot) is None:
            raise ValidationError(f"{where} has a malformed slot: {slot!r}")
        if slot in seen_slots:
            raise ValidationError(f"duplicate slot: {slot}")
        seen_slots.add(slot)

    # deck_surface: the re-sourced @surface fill slots.
    deck_surface = data["deck_surface"]
    if not isinstance(deck_surface, dict):
        raise ValidationError("registry deck_surface must be an object")
    for field, pattern in (("token", _TOKEN_NAME), ("getter", _GETTER_NAME)):
        value = deck_surface.get(field)
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise ValidationError(f"registry deck_surface.{field} is malformed: {value!r}")
    if not isinstance(deck_surface.get("guard_selector"), str) or not deck_surface["guard_selector"]:
        raise ValidationError("registry deck_surface.guard_selector must be a non-empty string")
    surface_slots = deck_surface.get("slots")
    if not isinstance(surface_slots, list) or not surface_slots:
        raise ValidationError("registry deck_surface.slots must be a non-empty array")
    for slot in surface_slots:
        claim_slot(slot, _COLOR_SLOT, "deck_surface.slots")

    # deck_padding: the guarded 14px inset slots.
    deck_padding = data["deck_padding"]
    if not isinstance(deck_padding, dict):
        raise ValidationError("registry deck_padding must be an object")
    padding_value = deck_padding.get("value")
    if not isinstance(padding_value, int) or isinstance(padding_value, bool) or padding_value <= 0:
        raise ValidationError("registry deck_padding.value must be a positive integer")
    for field in ("guard_selector", "value_symbol"):
        if not isinstance(deck_padding.get(field), str) or not deck_padding[field]:
            raise ValidationError(f"registry deck_padding.{field} must be a non-empty string")
    padding_slots = deck_padding.get("slots")
    if not isinstance(padding_slots, list) or not padding_slots:
        raise ValidationError("registry deck_padding.slots must be a non-empty array")
    for slot in padding_slots:
        claim_slot(slot, _INT_SLOT, "deck_padding.slots")

    # colours sourced from a Material-mapped getter.
    colors = data["colors"]
    if not isinstance(colors, list) or not colors:
        raise ValidationError("registry colors must be a non-empty array")
    color_tokens: dict[str, str] = {deck_surface["token"]: "deck_surface"}
    for index, color in enumerate(colors):
        if not isinstance(color, dict):
            raise ValidationError(f"color #{index} must be an object")
        claim_slot(color.get("slot"), _COLOR_SLOT, f"color #{index}")
        token = color.get("token")
        getter = color.get("getter")
        if not isinstance(token, str) or _TOKEN_NAME.fullmatch(token) is None:
            raise ValidationError(f"color {color.get('slot')} has a malformed token: {token!r}")
        if not isinstance(getter, str) or _GETTER_NAME.fullmatch(getter) is None:
            raise ValidationError(f"color {color.get('slot')} has a malformed getter: {getter!r}")
        color_tokens[token] = color["slot"]

    # density-invariant metric literals.
    metrics = data["metrics"]
    if not isinstance(metrics, list) or not metrics:
        raise ValidationError("registry metrics must be a non-empty array")
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            raise ValidationError(f"metric #{index} must be an object")
        claim_slot(metric.get("slot"), _INT_SLOT, f"metric #{index}")
        value = metric.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValidationError(f"metric {metric.get('slot')} must have a positive integer value")

    # states: any fill/text token must be provided by a colour slot or the surface.
    states = data["states"]
    if not isinstance(states, list) or not states:
        raise ValidationError("registry states must be a non-empty array")
    for index, state in enumerate(states):
        if not isinstance(state, dict) or not isinstance(state.get("name"), str):
            raise ValidationError(f"state #{index} must be a named object")
        for key in STATE_TOKEN_KEYS:
            token = state.get(key)
            if token is None:
                continue
            if not isinstance(token, str) or _TOKEN_NAME.fullmatch(token) is None:
                raise ValidationError(f"state {state['name']}.{key} is a malformed token: {token!r}")
            if token not in color_tokens:
                raise ValidationError(
                    f"state {state['name']}.{key} references token @{token} that no deck "
                    "colour slot provides"
                )

    for key in ("deck_title_markers", "collapse_markers"):
        markers = data[key]
        if not isinstance(markers, list) or not all(
            isinstance(item, str) and item for item in markers
        ):
            raise ValidationError(f"registry {key} must be a non-empty array of strings")

    return data


# --------------------------------------------------------------------------------------------------
# Theme header: every new slot must be a declared enum member.
# --------------------------------------------------------------------------------------------------
def _all_slots(data: dict) -> list[str]:
    return (
        list(data["deck_surface"]["slots"])
        + list(data["deck_padding"]["slots"])
        + [color["slot"] for color in data["colors"]]
        + [metric["slot"] for metric in data["metrics"]]
    )


def _new_slots(data: dict) -> list[str]:
    # deck_surface / deck_padding reuse pre-existing enum slots; only the colour
    # and metric slots are freshly declared by this row.
    return [color["slot"] for color in data["colors"]] + [
        metric["slot"] for metric in data["metrics"]
    ]


def validate_theme_header(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["theme_header"]))
    for slot in _new_slots(data):
        if re.search(rf"\b{re.escape(slot)}\s*,", source) is None:
            raise ValidationError(
                f"{data['theme_header']} must declare the deck Theme enum slot {slot}"
            )


# --------------------------------------------------------------------------------------------------
# Theme source: guard, registration, classification, and value/getter wiring.
# --------------------------------------------------------------------------------------------------
def validate_theme_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["theme_source"]))

    def require(pattern: str, description: str) -> None:
        if re.search(pattern, source) is None:
            raise ValidationError(f"{data['theme_source']} must {description}")

    # The Material guard helper must be defined and used.
    if re.search(rf"\bbool\s+{re.escape(data['guard_helper'])}\s*\(", source) is None:
        raise ValidationError(
            f"{data['theme_source']} must define the Material guard helper "
            f"{data['guard_helper']}()"
        )
    if data["guard_env"] not in source:
        raise ValidationError(
            f"{data['theme_source']} must gate the deck treatment on {data['guard_env']}"
        )

    # Every new slot registered in both directions of the property-name maps and
    # classified in GetPropertyType.
    for slot in _new_slots(data):
        require(
            rf'maPropertyNameToIdMap\[u"{re.escape(slot)}"_ustr\]\s*=\s*{re.escape(slot)}\s*;',
            f"register the name->id map entry for {slot}",
        )
        require(
            rf'maPropertyIdToNameMap\[{re.escape(slot)}\]\s*=\s*"{re.escape(slot)}"\s*;',
            f"register the id->name map entry for {slot}",
        )
        require(rf"case\s+{re.escape(slot)}\s*:", f"classify {slot} in GetPropertyType")

    # Metrics set to their literal density-invariant values in UpdateTheme.
    for metric in data["metrics"]:
        slot = metric["slot"]
        value = metric["value"]
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,"
            rf"\s*Any\(\s*sal_Int32\(\s*{value}\s*\)\s*\)\s*\)\s*;",
            f"set {slot} to the density-invariant literal {value} in UpdateTheme",
        )

    # Colours set from the Material-mapped StyleSettings getter for their token.
    for color in data["colors"]:
        slot = color["slot"]
        getter = color["getter"]
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,"
            rf"\s*Any\(\s*sal_Int32\(\s*rStyle\.{re.escape(getter)}\(\)\.GetRGBColor\(\)\s*\)\s*\)\s*\)\s*;",
            f"set {slot} from rStyle.{getter}() in UpdateTheme",
        )

    # The deck surface is re-sourced to @surface behind the guard; each fill slot
    # is written in UpdateTheme.
    deck_surface = data["deck_surface"]
    if deck_surface["guard_selector"] not in source:
        raise ValidationError(
            f"{data['theme_source']} must select the deck surface behind the Material guard "
            f"({deck_surface['guard_selector']!r})"
        )
    require(
        rf"rStyle\.{re.escape(deck_surface['getter'])}\(\)",
        f"source the deck surface from rStyle.{deck_surface['getter']}()",
    )
    for slot in deck_surface["slots"]:
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,",
            f"set the deck surface slot {slot} in UpdateTheme",
        )

    # The 14px deck content inset is guarded and written to each padding slot.
    deck_padding = data["deck_padding"]
    if deck_padding["guard_selector"] not in source:
        raise ValidationError(
            f"{data['theme_source']} must guard the deck content inset "
            f"({deck_padding['guard_selector']!r})"
        )
    for slot in deck_padding["slots"]:
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,"
            rf"\s*Any\(\s*sal_Int32\(\s*{re.escape(deck_padding['value_symbol'])}\s*\)\s*\)\s*\)\s*;",
            f"set {slot} to the guarded deck inset {deck_padding['value_symbol']} in UpdateTheme",
        )


# --------------------------------------------------------------------------------------------------
# Deck: guarded 12px scrollbar and the retained deck fill.
# --------------------------------------------------------------------------------------------------
def validate_deck_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["deck_source"]))

    if re.search(rf"\b{re.escape(data['guard_helper'])}\s*\(", source) is None:
        raise ValidationError(
            f"{data['deck_source']} must define/use the Material guard helper "
            f"{data['guard_helper']}()"
        )
    if data["deck_scrollbar_marker"] not in source:
        raise ValidationError(
            f"{data['deck_source']} must apply the 12px Material scrollbar: "
            f"missing {data['deck_scrollbar_marker']!r}"
        )
    if data["deck_fill_marker"] not in source:
        raise ValidationError(
            f"{data['deck_source']} must keep the deck fill on Color_DeckBackground: "
            f"missing {data['deck_fill_marker']!r}"
        )


# --------------------------------------------------------------------------------------------------
# DeckTitleBar: guarded title-role treatment.
# --------------------------------------------------------------------------------------------------
def validate_deck_title_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["deck_title_source"]))

    if re.search(rf"\b{re.escape(data['guard_helper'])}\s*\(", source) is None:
        raise ValidationError(
            f"{data['deck_title_source']} must define/use the Material guard helper "
            f"{data['guard_helper']}()"
        )
    for marker in data["deck_title_markers"]:
        if marker not in source:
            raise ValidationError(
                f"{data['deck_title_source']} must apply the deck title role: missing {marker!r}"
            )


# --------------------------------------------------------------------------------------------------
# SidebarController: click-active-to-collapse and the below-medium overlay degrade.
# --------------------------------------------------------------------------------------------------
def _function_body(source: str, function: str, path: str) -> str:
    match = re.search(
        rf"SidebarController::{re.escape(function)}\s*\(.*?\n\}}", source, flags=re.DOTALL
    )
    if match is None:
        raise ValidationError(f"{path} must define SidebarController::{function}()")
    return match.group(0)


def validate_controller_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["controller_source"]))
    path = data["controller_source"]

    if re.search(rf"\b{re.escape(data['guard_helper'])}\s*\(", source) is None:
        raise ValidationError(
            f"{path} must define/use the Material guard helper {data['guard_helper']}()"
        )

    # click-active-to-collapse (shared with NAV-005) must survive.
    collapse_body = _function_body(source, data["collapse_function"], path)
    for marker in data["collapse_markers"]:
        if marker not in collapse_body:
            raise ValidationError(
                f"{path} {data['collapse_function']} must keep the collapse marker {marker!r} so "
                "clicking the active deck collapses the sidebar to the rail"
            )

    # The overlay-degrade predicate must be defined, read the pinned threshold,
    # and be consumed inside the deck-open path.
    if re.search(rf"\bbool\s+{re.escape(data['overlay_function'])}\s*\(", source) is None:
        raise ValidationError(
            f"{path} must define the below-medium overlay predicate {data['overlay_function']}()"
        )
    if data["overlay_threshold_marker"] not in source:
        raise ValidationError(
            f"{path} {data['overlay_function']} must read the overlay threshold: "
            f"missing {data['overlay_threshold_marker']!r}"
        )
    if data["overlay_consume_marker"] not in collapse_body:
        raise ValidationError(
            f"{path} {data['collapse_function']} must consume the overlay predicate: "
            f"missing {data['overlay_consume_marker']!r}"
        )


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_theme_header(repo_root, data)
    validate_theme_source(repo_root, data)
    validate_deck_source(repo_root, data)
    validate_deck_title_source(repo_root, data)
    validate_controller_source(repo_root, data)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve() if args.registry is not None else DEFAULT_REGISTRY
    )
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Material sidebar deck & side panes contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Material sidebar deck & side panes contract passed: sfx2 sidebar Theme puts the deck "
        f"on @surface across {len(data['deck_surface']['slots'])} fill slots with a {data['deck_padding']['value']}px "
        f"guarded inset, declares {len(data['colors'])} title/heading colours and "
        f"{len(data['metrics'])} deck metrics, Deck applies the 12px scrollbar and DeckTitleBar the "
        "title role behind the VCL_DRAW_WIDGETS_FROM_FILE guard, and SidebarController keeps "
        "click-active-to-collapse plus the below-medium overlay degrade."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
