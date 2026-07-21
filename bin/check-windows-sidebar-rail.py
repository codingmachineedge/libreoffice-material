#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the native Material sidebar rail (WIN-NAV-005).

The rail is the vertical deck-switcher on the sidebar's outer edge. Design
05 s5.1 / 05 s5.7 / 06 s6.7 are explicit that it is *sidebar-framework* chrome --
"No dedicated native rail part exists; buttons consume icon-button/toolbar
tokens ... belong to the sidebar framework" -- so its Material metrics and state
palette live in the sfx2 sidebar ``Theme`` and are consumed by ``TabBar`` /
``SidebarController``, NOT as a VCL widget-definition part. (This diverges from
the row plan's mention of definition.xml; the design chapter wins.)

The registry ``qa/windows-ui-contract/sidebar-rail.json`` pins the design
ground truth: a 48px rail on ``@surface-container``; 38x38px corner-small
buttons carrying 22px icons stacked at a 4px gap below 10px top padding; and the
idle/hover/active-deck/focus/disabled state palette (design 05 s5.2). This
checker enforces that the sfx2 sidebar framework carries that contract as real,
guarded native wiring:

* ``Theme`` declares one enum slot per rail metric and per rail state colour,
  registers each in both property-name maps, classifies each in
  ``GetPropertyType`` and *sets* each in ``UpdateTheme`` -- the metrics to their
  literal density-invariant values and the colours from the Material-mapped
  ``StyleSettings`` getter that resolves to the named design token;
* ``TabBar`` consumes the 48px rail-width metric in ``GetDefaultWidth`` and the
  button/gap/padding metrics when laying the rail buttons out, all behind the
  ``VCL_DRAW_WIDGETS_FROM_FILE`` Material guard so non-Material paths are
  untouched, and keeps the rail fill on ``@surface-container``; and
* ``SidebarController`` keeps the click-active-to-collapse behaviour
  (``OpenThenToggleDeck`` closing the visible deck).

Every source assertion runs against a comment/raw-string-stripped copy of the
file, so commented-out wiring fails closed. It is source evidence only: no
native build, rail pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/sidebar-rail.json"

# Every state colour a rail button can show, keyed by the design 05 s5.2 token,
# so the registry's human-readable state table must stay consistent with the
# Theme colour slots it is drawn from.
STATE_TOKENS_FROM_COLORS = ("fill", "icon", "ring")


class ValidationError(RuntimeError):
    """Raised when the Material sidebar-rail contract is incomplete or weakened."""


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
_SLOT_NAME = re.compile(r"^(?:Color|Int)_[A-Za-z0-9]+$")
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
        "tabbar_source",
        "controller_source",
        "rail_fill",
        "metrics",
        "colors",
        "states",
        "tabbar_width_marker",
        "tabbar_geometry_markers",
        "tabbar_background_marker",
        "collapse_function",
        "collapse_markers",
    )
    missing = [key for key in required_top if key not in data]
    if missing:
        raise ValidationError("registry is missing keys: " + ", ".join(missing))

    rail_fill = data["rail_fill"]
    if not isinstance(rail_fill, dict):
        raise ValidationError("registry rail_fill must be an object")
    for field, pattern in (
        ("slot", _SLOT_NAME),
        ("token", _TOKEN_NAME),
        ("getter", _GETTER_NAME),
    ):
        value = rail_fill.get(field)
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            raise ValidationError(f"registry rail_fill.{field} is malformed: {value!r}")

    metrics = data["metrics"]
    if not isinstance(metrics, list) or not metrics:
        raise ValidationError("registry metrics must be a non-empty array")
    seen_slots: set[str] = {rail_fill["slot"]}
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            raise ValidationError(f"metric #{index} must be an object")
        slot = metric.get("slot")
        if not isinstance(slot, str) or _SLOT_NAME.fullmatch(slot) is None or not slot.startswith("Int_"):
            raise ValidationError(f"metric #{index} has a malformed Int_ slot: {slot!r}")
        if slot in seen_slots:
            raise ValidationError(f"duplicate slot: {slot}")
        seen_slots.add(slot)
        value = metric.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValidationError(f"metric {slot} must have a positive integer value")

    colors = data["colors"]
    if not isinstance(colors, list) or not colors:
        raise ValidationError("registry colors must be a non-empty array")
    color_tokens: dict[str, str] = {}
    for index, color in enumerate(colors):
        if not isinstance(color, dict):
            raise ValidationError(f"color #{index} must be an object")
        slot = color.get("slot")
        if (
            not isinstance(slot, str)
            or _SLOT_NAME.fullmatch(slot) is None
            or not slot.startswith("Color_")
        ):
            raise ValidationError(f"color #{index} has a malformed Color_ slot: {slot!r}")
        if slot in seen_slots:
            raise ValidationError(f"duplicate slot: {slot}")
        seen_slots.add(slot)
        token = color.get("token")
        getter = color.get("getter")
        if not isinstance(token, str) or _TOKEN_NAME.fullmatch(token) is None:
            raise ValidationError(f"color {slot} has a malformed token: {token!r}")
        if not isinstance(getter, str) or _GETTER_NAME.fullmatch(getter) is None:
            raise ValidationError(f"color {slot} has a malformed getter: {getter!r}")
        color_tokens[token] = slot

    states = data["states"]
    if not isinstance(states, list) or not states:
        raise ValidationError("registry states must be a non-empty array")
    for index, state in enumerate(states):
        if not isinstance(state, dict) or not isinstance(state.get("name"), str):
            raise ValidationError(f"state #{index} must be a named object")
        for key in STATE_TOKENS_FROM_COLORS:
            token = state.get(key)
            if token is None or token in ("transparent", "none"):
                continue
            if not isinstance(token, str) or _TOKEN_NAME.fullmatch(token) is None:
                raise ValidationError(
                    f"state {state['name']}.{key} is a malformed token: {token!r}"
                )
            if token not in color_tokens:
                raise ValidationError(
                    f"state {state['name']}.{key} references token @{token} that no rail "
                    "colour slot provides"
                )

    for key in ("collapse_markers", "tabbar_geometry_markers"):
        markers = data[key]
        if not isinstance(markers, list) or not all(
            isinstance(item, str) and item for item in markers
        ):
            raise ValidationError(f"registry {key} must be a non-empty array of strings")

    return data


# --------------------------------------------------------------------------------------------------
# Theme header: every rail slot must be a declared enum member.
# --------------------------------------------------------------------------------------------------
def validate_theme_header(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["theme_header"]))
    slots = [metric["slot"] for metric in data["metrics"]] + [
        color["slot"] for color in data["colors"]
    ]
    for slot in slots:
        if re.search(rf"\b{re.escape(slot)}\s*,", source) is None:
            raise ValidationError(
                f"{data['theme_header']} must declare the rail Theme enum slot {slot}"
            )


# --------------------------------------------------------------------------------------------------
# Theme source: registration, classification, and value/getter wiring.
# --------------------------------------------------------------------------------------------------
def validate_theme_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["theme_source"]))

    def require(pattern: str, description: str) -> None:
        if re.search(pattern, source) is None:
            raise ValidationError(f"{data['theme_source']} must {description}")

    all_slots = (
        [metric["slot"] for metric in data["metrics"]]
        + [color["slot"] for color in data["colors"]]
    )
    for slot in all_slots:
        # Registered in both directions of the property-name maps.
        require(
            rf'maPropertyNameToIdMap\[u"{re.escape(slot)}"_ustr\]\s*=\s*{re.escape(slot)}\s*;',
            f"register the name->id map entry for {slot}",
        )
        require(
            rf'maPropertyIdToNameMap\[{re.escape(slot)}\]\s*=\s*"{re.escape(slot)}"\s*;',
            f"register the id->name map entry for {slot}",
        )
        # Classified in GetPropertyType.
        require(
            rf"case\s+{re.escape(slot)}\s*:",
            f"classify {slot} in GetPropertyType",
        )

    # Metrics are set to their literal density-invariant values in UpdateTheme.
    for metric in data["metrics"]:
        slot = metric["slot"]
        value = metric["value"]
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,"
            rf"\s*Any\(\s*sal_Int32\(\s*{value}\s*\)\s*\)\s*\)\s*;",
            f"set {slot} to the density-invariant literal {value} in UpdateTheme",
        )

    # Colours are set from the Material-mapped StyleSettings getter for their token.
    for color in data["colors"]:
        slot = color["slot"]
        getter = color["getter"]
        require(
            rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(slot)}\]\s*,"
            rf"\s*Any\(\s*sal_Int32\(\s*rStyle\.{re.escape(getter)}\(\)\.GetRGBColor\(\)\s*\)\s*\)\s*\)\s*;",
            f"set {slot} from rStyle.{getter}() in UpdateTheme",
        )

    # The 48px rail fill stays on @surface-container via the dialog colour.
    rail_fill = data["rail_fill"]
    require(
        rf"rStyle\.{re.escape(rail_fill['getter'])}\(\)",
        f"source the rail fill base colour from rStyle.{rail_fill['getter']}()",
    )
    require(
        rf"setPropertyValue\s*\(\s*maPropertyIdToNameMap\[{re.escape(rail_fill['slot'])}\]\s*,",
        f"set the rail fill slot {rail_fill['slot']} in UpdateTheme",
    )


# --------------------------------------------------------------------------------------------------
# TabBar: guarded consumption of the rail metrics and the rail fill.
# --------------------------------------------------------------------------------------------------
def validate_tabbar_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["tabbar_source"]))

    def require(marker: str, description: str) -> None:
        if marker not in source:
            raise ValidationError(f"{data['tabbar_source']} must {description}: missing {marker!r}")

    # The Material guard: env gate + helper that fences the rail treatment.
    require(data["guard_env"], "gate the rail treatment on the Material draw path")
    if re.search(rf"\b{re.escape(data['guard_helper'])}\s*\(", source) is None:
        raise ValidationError(
            f"{data['tabbar_source']} must define/use the Material guard helper "
            f"{data['guard_helper']}()"
        )

    # 48px rail width consumed inside GetDefaultWidth, behind the guard.
    match = re.search(
        r"TabBar::GetDefaultWidth\s*\(\s*\)\s*\{.*?\n\}", source, flags=re.DOTALL
    )
    if match is None:
        raise ValidationError(
            f"{data['tabbar_source']} must define TabBar::GetDefaultWidth()"
        )
    default_width_body = match.group(0)
    if data["tabbar_width_marker"] not in default_width_body:
        raise ValidationError(
            f"{data['tabbar_source']} GetDefaultWidth must return the rail-width metric "
            f"({data['tabbar_width_marker']})"
        )
    if re.search(rf"{re.escape(data['guard_helper'])}\s*\(\s*\)", default_width_body) is None:
        raise ValidationError(
            f"{data['tabbar_source']} GetDefaultWidth must guard the rail width on "
            f"{data['guard_helper']}()"
        )

    # Button footprint, gap and top padding are consumed from the metric slots.
    for marker in data["tabbar_geometry_markers"]:
        require(marker, "apply the rail button geometry from the Material metrics")

    # The rail fill stays on @surface-container (Color_TabBarBackground).
    require(data["tabbar_background_marker"], "keep the rail fill on the tab-bar background slot")


# --------------------------------------------------------------------------------------------------
# SidebarController: click-active-to-collapse must survive.
# --------------------------------------------------------------------------------------------------
def validate_controller_source(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["controller_source"]))
    function = data["collapse_function"]
    match = re.search(
        rf"SidebarController::{re.escape(function)}\s*\(.*?\n\}}", source, flags=re.DOTALL
    )
    if match is None:
        raise ValidationError(
            f"{data['controller_source']} must define SidebarController::{function}() "
            "(click-active-to-collapse)"
        )
    body = match.group(0)
    for marker in data["collapse_markers"]:
        if marker not in body:
            raise ValidationError(
                f"{data['controller_source']} {function} must keep the collapse marker "
                f"{marker!r} so clicking the active deck collapses the sidebar to the rail"
            )


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_theme_header(repo_root, data)
    validate_theme_source(repo_root, data)
    validate_tabbar_source(repo_root, data)
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
        print(f"Material sidebar rail contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Material sidebar rail contract passed: sfx2 sidebar Theme declares "
        f"{len(data['metrics'])} rail metrics and {len(data['colors'])} rail state colours, "
        "TabBar consumes the 48px rail width and 38px button geometry behind the "
        "VCL_DRAW_WIDGETS_FROM_FILE guard, and SidebarController keeps "
        "click-active-to-collapse."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
