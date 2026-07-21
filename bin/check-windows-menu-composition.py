#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the WIN-NAV-001 menubar + drop-menu composition contract.

The registry ``qa/windows-ui-contract/menu-composition.json`` pins two halves of the design-05
navigation menu surface and asserts that they are wired to each other in real code, not merely
declared:

* the Material *token* half in ``vcl/uiconfig/theme_definitions/material/definition.xml`` -- the
  ``menubar``/``menupopup`` parts and states (band ``@surface-container``; drop menu ``@surface`` +
  ``@outline-variant`` hairline; ``@corner-container``/``@corner-small`` radii; the check/radio marks
  and the submenu arrow at ``size-menu-indicator``; the ``@outline-variant`` separator; and the
  milestone-10 ``enabled="false"`` ``@outline`` disabled-submenu-arrow state) plus the five menu
  composition ``<settings>`` (band/row heights, drop-menu minimum width, inner border, accelerator
  gap); and

* the *layout* half in the real cross-platform menu code -- the ``settings -> WidgetDefinition ->
  ImplSVNWFData -> Menu::ImplCalcSize`` channel that carries those metrics into the actual popup and
  band geometry, guarded so it is populated only while the Material file-definition theme is live and
  reverted to the captured platform baseline on teardown (so non-Material rendering, mnemonics, RTL
  submenu keys and accessibility are untouched).

Every native marker is matched against comment-stripped source, so commenting the wiring out -- or
replacing it with a descriptive comment -- fails the contract. It is source evidence only: no native
build, menu pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/menu-composition.json"

SVDATA_HEADER = "vcl/inc/svdata.hxx"


class ValidationError(RuntimeError):
    """Raised when the menu-composition contract is incomplete or weakened."""


# --------------------------------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------------------------------
def _tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def _strip_comments(source: str) -> str:
    """Remove C/C++ block and line comments, preserving newlines so that markers can never be
    satisfied by commented-out or comment-only wiring."""

    without_block = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
    kept_lines = []
    for line in without_block.split("\n"):
        kept_lines.append(re.sub(r"//.*$", "", line))
    return "\n".join(kept_lines)


# --------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------
def load_registry(registry_path: Path) -> dict:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    for key in (
        "definition_xml",
        "indicator_metric",
        "menu_settings",
        "menubar_part_states",
        "menupopup_part_states",
        "menupopup_indicators",
        "menupopup_separator",
        "nwf_fields",
        "code_markers",
    ):
        if key not in data:
            raise ValidationError(f"registry is missing required key {key!r}")

    if not isinstance(data["menu_settings"], dict) or not data["menu_settings"]:
        raise ValidationError("registry menu_settings must be a non-empty object")
    if not isinstance(data["nwf_fields"], list) or not data["nwf_fields"]:
        raise ValidationError("registry nwf_fields must be a non-empty array")
    if not isinstance(data["code_markers"], list) or not data["code_markers"]:
        raise ValidationError("registry code_markers must be a non-empty array")

    seen: set[str] = set()
    for index, marker in enumerate(data["code_markers"]):
        if not isinstance(marker, dict):
            raise ValidationError(f"code_marker #{index} must be an object")
        for field in ("id", "file", "pattern"):
            value = marker.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"code_marker #{index} has empty required field {field!r}")
        if marker["id"] in seen:
            raise ValidationError(f"duplicate code_marker id: {marker['id']}")
        seen.add(marker["id"])
    return data


# --------------------------------------------------------------------------------------------------
# definition.xml token half
# --------------------------------------------------------------------------------------------------
def _widgets_root(repo_root: Path, rel: str) -> ET.Element:
    path = repo_root / rel
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse definition.xml {rel}: {error}") from error
    if _tag(root.tag) != "widgets":
        raise ValidationError(f"{rel} root element must be <widgets>, got <{_tag(root.tag)}>")
    return root


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _tag(child.tag) == name:
            return child
    return None


def _find_part(widget: ET.Element, part_value: str) -> ET.Element:
    for part in widget:
        if _tag(part.tag) == "part" and part.get("value") == part_value:
            return part
    raise ValidationError(f"<{_tag(widget.tag)}> is missing <part value=\"{part_value}\">")


def _state_matching(part: ET.Element, wanted: dict) -> ET.Element:
    """Return the <state> element whose attributes exactly equal ``wanted``."""

    for state in part:
        if _tag(state.tag) != "state":
            continue
        if dict(state.attrib) == {k: str(v) for k, v in wanted.items()}:
            return state
    raise ValidationError(
        f"part <{part.get('value')}> is missing a <state> with attributes {wanted!r}"
    )


def _drawing_child(state: ET.Element, element: str | None = None) -> ET.Element:
    for child in state:
        if element is None and _tag(child.tag) in ("rect", "line"):
            return child
        if element is not None and _tag(child.tag) == element:
            return child
    raise ValidationError(
        f"state {dict(state.attrib)!r} is missing its {element or 'rect/line'} drawing element"
    )


def _require_attr(element: ET.Element, attr: str, expected: str, context: str) -> None:
    got = element.get(attr)
    if got != expected:
        raise ValidationError(
            f"{context}: <{_tag(element.tag)}> {attr} must be {expected!r}, got {got!r}"
        )


def validate_metric(root: ET.Element, spec: dict) -> None:
    metrics = _child(root, "metrics")
    if metrics is None:
        raise ValidationError("definition.xml has no <metrics> section")
    for metric in metrics:
        if _tag(metric.tag) == "metric" and metric.get("name") == spec["name"]:
            if metric.get("value") != str(spec["value"]):
                raise ValidationError(
                    f"metric {spec['name']!r} must be {spec['value']}, got {metric.get('value')!r}"
                )
            return
    raise ValidationError(f"definition.xml is missing the <metric name=\"{spec['name']}\">")


def validate_settings(root: ET.Element, settings: dict) -> None:
    section = _child(root, "settings")
    if section is None:
        raise ValidationError("definition.xml has no <settings> section")
    present = {_tag(child.tag): child.get("value") for child in section}
    for name, expected in settings.items():
        if name not in present:
            raise ValidationError(f"definition.xml <settings> is missing <{name}>")
        if present[name] != str(expected):
            raise ValidationError(
                f"menu setting <{name}> must be {expected}, got {present[name]!r}"
            )


def validate_part_states(widget: ET.Element, part_states: dict) -> None:
    widget_name = _tag(widget.tag)
    for part_value, specs in part_states.items():
        part = _find_part(widget, part_value)
        for spec in specs:
            state = _state_matching(part, spec.get("state", {}))
            drawing = _drawing_child(state)
            context = f"{widget_name}/{part_value} state {spec.get('state', {})!r}"
            for attr_key, xml_attr in (
                ("fill", "fill"),
                ("stroke", "stroke"),
                ("stroke_width", "stroke-width"),
                ("radius", "radius"),
            ):
                if attr_key in spec:
                    _require_attr(drawing, xml_attr, spec[attr_key], context)


def validate_indicators(widget: ET.Element, indicators: dict) -> None:
    for part_value, spec in indicators.items():
        part = _find_part(widget, part_value)
        if part.get("width") != spec["size_metric"] or part.get("height") != spec["size_metric"]:
            raise ValidationError(
                f"menupopup/{part_value} must be sized at {spec['size_metric']} square"
            )
        element = spec.get("element")
        enabled = _state_matching(part, spec.get("enabled_state", {}))
        _require_attr(
            _drawing_child(enabled, element),
            "stroke",
            spec["enabled_stroke"],
            f"menupopup/{part_value} enabled indicator",
        )
        disabled = _state_matching(part, spec.get("disabled_state", {}))
        _require_attr(
            _drawing_child(disabled, element),
            "stroke",
            spec["disabled_stroke"],
            f"menupopup/{part_value} disabled indicator",
        )


def validate_separator(widget: ET.Element, spec: dict) -> None:
    part = _find_part(widget, spec["part"])
    state = _state_matching(part, {})
    line = _drawing_child(state, "line")
    _require_attr(line, "stroke", spec["stroke"], "menupopup/Separator")
    _require_attr(line, "stroke-width", spec["stroke_width"], "menupopup/Separator")


def validate_definition(repo_root: Path, data: dict) -> None:
    root = _widgets_root(repo_root, data["definition_xml"])
    validate_metric(root, data["indicator_metric"])
    validate_settings(root, data["menu_settings"])

    menubar = _child(root, "menubar")
    if menubar is None:
        raise ValidationError("definition.xml has no <menubar> widget")
    validate_part_states(menubar, data["menubar_part_states"])

    menupopup = _child(root, "menupopup")
    if menupopup is None:
        raise ValidationError("definition.xml has no <menupopup> widget")
    validate_part_states(menupopup, data["menupopup_part_states"])
    validate_indicators(menupopup, data["menupopup_indicators"])
    validate_separator(menupopup, data["menupopup_separator"])


# --------------------------------------------------------------------------------------------------
# native layout half
# --------------------------------------------------------------------------------------------------
def validate_nwf_fields(repo_root: Path, fields: Sequence[str]) -> None:
    source = _strip_comments(_read(repo_root / SVDATA_HEADER))
    for field in fields:
        if not re.search(rf"\b{re.escape(field)}\b", source):
            raise ValidationError(
                f"{SVDATA_HEADER} must declare the NWF channel field {field!r}"
            )


def validate_code_markers(repo_root: Path, markers: Sequence[dict]) -> None:
    cache: dict[str, str] = {}
    for marker in markers:
        rel = marker["file"]
        if rel not in cache:
            cache[rel] = _strip_comments(_read(repo_root / rel))
        if not re.search(marker["pattern"], cache[rel], flags=re.S):
            raise ValidationError(
                f"{rel}: contract marker {marker['id']!r} not found in real code "
                f"({marker.get('why', marker['pattern'])})"
            )


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_definition(repo_root, data)
    validate_nwf_fields(repo_root, data["nwf_fields"])
    validate_code_markers(repo_root, data["code_markers"])
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
        args.registry.resolve()
        if args.registry is not None
        else repo_root / "qa/windows-ui-contract/menu-composition.json"
    )
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Windows menu-composition contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Windows menu-composition contract passed: definition.xml declares the menubar/menupopup "
        f"parts, {len(data['menu_settings'])} composition settings and the disabled-arrow @outline "
        f"state, and {len(data['code_markers'])} real code markers carry them through the "
        "settings -> NWF -> ImplCalcSize layout channel."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
