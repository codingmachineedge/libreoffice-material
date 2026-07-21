#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the Material warning/error banner (infobar) severity contract.

The registry ``qa/windows-ui-contract/infobar-severity-policy.json`` describes the single infobar
strip surface and the contract of docs/design/07-feedback.md 7.6:

* every ``InfobarType`` severity resolves a Material container/on-container pair from semantic
  ``StyleSettings`` feedback slots (INFO -> the primary-container highlight roles, WARNING ->
  warning-container, DANGER -> error-container) or from the single shared ``NotificationTheme``
  resolved-green accent (SUCCESS) -- never from an infobar-local ``basegfx::BColor`` hex literal;
* the high-contrast bypass restores the captured native baseline (light + dialog-text);
* the persistent strip paints the ``corner-container`` (12px) radius in code, with a square
  high-contrast fallback (an ``InterimItemWindow`` strip has no themed part);
* a polite live announcement (``AccessibleRole::NOTIFICATION`` in the ``.ui`` plus a refreshed
  accessible name that names the severity in words) reaches assistive tech without stealing focus;
* ``infobar.ui`` carries the 7.6 padding / gap / leading-icon geometry.

Source markers are matched against comment-stripped C++ so comment-only wiring cannot satisfy the
contract. It is source evidence only: no native build, banner pixels, or runtime announcement are
claimed.
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
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/infobar-severity-policy.json"

SEVERITY_TYPES = ("INFO", "SUCCESS", "WARNING", "DANGER")

CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\('
    r'.*?\)(?P=delimiter)"',
    re.DOTALL,
)


class ValidationError(RuntimeError):
    """Raised when the infobar severity contract is incomplete or weakened."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def strip_cpp_non_code(source: str) -> str:
    """Drop raw strings and comments so markers must appear in real code."""

    source = CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


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

    required = (
        "source",
        "header",
        "ui_file",
        "container_id",
        "color_resolver",
        "forbidden_color_literal_regex",
        "severities",
        "high_contrast_markers",
        "announcement",
        "corner_container",
        "ui_geometry",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ValidationError("registry is missing keys: " + ", ".join(missing))

    severities = data["severities"]
    if not isinstance(severities, list):
        raise ValidationError("registry 'severities' must be an array")
    seen = []
    for index, entry in enumerate(severities):
        if not isinstance(entry, dict):
            raise ValidationError(f"severity #{index} must be an object")
        for field in ("type", "case_label", "background_marker", "foreground_marker"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"severity #{index} has empty required field {field!r}")
        seen.append(entry["type"])
    if tuple(seen) != SEVERITY_TYPES:
        raise ValidationError(
            "registry must map exactly the four InfobarType severities in order "
            f"{SEVERITY_TYPES}, found {tuple(seen)}"
        )

    try:
        int(data["corner_container"]["radius"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError("corner_container.radius must be an integer") from error
    return data


# --------------------------------------------------------------------------------------------------
# Source: color routing + high-contrast bypass
# --------------------------------------------------------------------------------------------------
def validate_source_routing(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["source"]))

    if data["color_resolver"] not in source:
        raise ValidationError(
            f"{data['source']} must define the severity color resolver {data['color_resolver']!r}"
        )

    forbidden = re.compile(data["forbidden_color_literal_regex"])
    hit = forbidden.search(source)
    if hit is not None:
        raise ValidationError(
            "infobar severity colors must not use raw color literals; found "
            f"{hit.group(0)!r} in {data['source']} (INFO/SUCCESS must route through Material roles)"
        )

    for entry in data["severities"]:
        label = entry["type"]
        for field in ("case_label", "background_marker", "foreground_marker"):
            marker = entry[field]
            if marker not in source:
                raise ValidationError(
                    f"{label} severity must wire {field} {marker!r} in {data['source']}"
                )

    for marker in data["high_contrast_markers"]:
        if marker not in source:
            raise ValidationError(
                f"{data['source']} must keep the high-contrast bypass marker {marker!r}"
            )


# --------------------------------------------------------------------------------------------------
# Source: corner-container radius painted in code
# --------------------------------------------------------------------------------------------------
def validate_corner_container(repo_root: Path, data: dict) -> None:
    source = strip_cpp_non_code(_read(repo_root / data["source"]))
    corner = data["corner_container"]
    for key in ("paint_signature", "draw_marker", "radius_marker"):
        marker = corner[key]
        if marker not in source:
            raise ValidationError(
                f"{data['source']} must paint the corner-container radius in code: missing "
                f"{key} {marker!r}"
            )
    radius = str(int(corner["radius"]))
    if radius not in corner["radius_marker"]:
        raise ValidationError(
            f"corner_container.radius_marker must resolve the {radius}px corner-container radius"
        )


# --------------------------------------------------------------------------------------------------
# Announcement: source markers + AccessibleRole::NOTIFICATION in the .ui
# --------------------------------------------------------------------------------------------------
def _find_object_by_id(root: ET.Element, obj_id: str) -> ET.Element:
    for obj in root.iter():
        if _tag(obj.tag) == "object" and obj.get("id") == obj_id:
            return obj
    raise ValidationError(f"infobar .ui has no object with id {obj_id!r}")


def _accessible_role(obj: ET.Element) -> str | None:
    """Return the AccessibleRole declared on this object's own accessible internal-child."""

    for child in obj:
        if _tag(child.tag) != "child" or child.get("internal-child") != "accessible":
            continue
        for atk in child:
            if _tag(atk.tag) != "object" or atk.get("class") != "AtkObject":
                continue
            for prop in atk:
                if (
                    _tag(prop.tag) == "property"
                    and prop.get("name") == "AtkObject::accessible-role"
                ):
                    return (prop.text or "").strip()
    return None


def validate_announcement(repo_root: Path, data: dict) -> None:
    announcement = data["announcement"]
    source = strip_cpp_non_code(_read(repo_root / data["source"]))
    for marker in announcement["source_markers"]:
        if marker not in source:
            raise ValidationError(
                f"{data['source']} must build the polite live announcement: missing {marker!r}"
            )

    ui_path = repo_root / data["ui_file"]
    try:
        root = ET.parse(ui_path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse infobar .ui {data['ui_file']}: {error}") from error

    container = _find_object_by_id(root, data["container_id"])
    role = _accessible_role(container)
    if role != announcement["accessible_role"]:
        raise ValidationError(
            f"infobar strip {data['container_id']!r} must declare accessible-role "
            f"{announcement['accessible_role']!r} (a polite live region), found {role!r}"
        )


# --------------------------------------------------------------------------------------------------
# .ui reference geometry (7.6)
# --------------------------------------------------------------------------------------------------
def _object_properties(obj: ET.Element) -> dict[str, str]:
    props: dict[str, str] = {}
    for child in obj:
        if _tag(child.tag) == "property" and child.get("name"):
            props[child.get("name")] = (child.text or "").strip()
    return props


def validate_ui_geometry(repo_root: Path, data: dict) -> None:
    ui_path = repo_root / data["ui_file"]
    try:
        root = ET.parse(ui_path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse infobar .ui {data['ui_file']}: {error}") from error

    geometry = data["ui_geometry"]

    grids = [
        obj
        for obj in root.iter()
        if _tag(obj.tag) == "object" and obj.get("class") == geometry["grid_class"]
    ]
    if len(grids) != 1:
        raise ValidationError(
            f"infobar .ui must contain exactly one {geometry['grid_class']}, found {len(grids)}"
        )
    grid_props = _object_properties(grids[0])
    for name, expected in geometry["grid_margins"].items():
        actual = grid_props.get(name)
        if actual != expected:
            raise ValidationError(
                f"infobar grid property {name!r} must be {expected!r} (7.6 padding/gap), "
                f"found {actual!r}"
            )

    box = _find_object_by_id(root, geometry["leading_box_id"])
    box_spacing = _object_properties(box).get("spacing")
    if box_spacing != geometry["leading_box_spacing"]:
        raise ValidationError(
            f"leading box {geometry['leading_box_id']!r} spacing must be "
            f"{geometry['leading_box_spacing']!r} (12px icon-text gap), found {box_spacing!r}"
        )

    image = _find_object_by_id(root, geometry["image_id"])
    image_size = _object_properties(image).get("pixel-size")
    if image_size != geometry["image_pixel_size"]:
        raise ValidationError(
            f"leading icon {geometry['image_id']!r} pixel-size must be "
            f"{geometry['image_pixel_size']!r} (20px leading icon), found {image_size!r}"
        )


# --------------------------------------------------------------------------------------------------
# Header wiring
# --------------------------------------------------------------------------------------------------
def validate_header(repo_root: Path, data: dict) -> None:
    header = strip_cpp_non_code(_read(repo_root / data["header"]))
    for marker in ("virtual void Paint(", "void UpdateAccessibleAnnouncement("):
        if marker not in header:
            raise ValidationError(f"{data['header']} must declare {marker!r}")


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_source_routing(repo_root, data)
    validate_corner_container(repo_root, data)
    validate_announcement(repo_root, data)
    validate_ui_geometry(repo_root, data)
    validate_header(repo_root, data)
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
        validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Material infobar contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Material infobar contract passed: four InfobarType severities route through Material "
        "container/on-container roles (no infobar-local hex), the corner-container radius is "
        "painted in code with a high-contrast bypass, a polite live announcement names the "
        "severity, and infobar.ui carries the 7.6 padding/gap/icon geometry (source evidence "
        "only; no banner pixels or runtime announcement claimed)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
