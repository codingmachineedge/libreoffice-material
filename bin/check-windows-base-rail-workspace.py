#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed guarded-material-source contract for the Base rail/workspace (WIN-BA-001).

``qa/windows-ui-contract/base-rail-workspace.json`` registers the four dbaccess
surfaces that gain their first real Material token consumption per
docs/design/12-base-math-shared.md 12.1: the navigation rail container fill
(@surface-container), the rail/workspace divider hairline (@outline-variant),
the selected rail entry (@primary-container / @on-primary-container) and the
shared OTitleWindow "kicker" variant (@on-surface-variant). This checker
cross-validates every declaration against the real tree:

* ``palette_tokens`` / ``metric_tokens`` / ``shape_tokens`` -- every colour role
  the rail consumes must exist in BOTH the default (light) and dark palettes of
  definition.xml; every metric and radius token must exist (with the exact radius
  value). A renamed role, a dropped scheme or a changed radius fails closed. The
  definition file is read only, never mutated.
* ``markers`` -- each guarded surface source, with C/C++ comments and raw strings
  stripped first, must carry the ``VCL_FILE_WIDGET_THEME`` activation guard, the
  high-contrast bypass, the ``vcl::MaterialTokens`` include + resolver, every
  declared token role as a quoted literal, and every anatomy code marker -- so
  comment-only wiring can never satisfy the contract. Declared header/.ui markers
  must survive too.
* ``kicker_call_site`` -- the "Database" rail head must be the OTitleWindow
  constructed with the Kicker variant, pinning that the default-Heading style is
  only overridden for the rail (the task/object-list headings stay Heading).

The registry establishes source-declared scope; it never claims a dbu build,
rail pixels or runtime interaction (``runtime_verified: false`` throughout).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/base-rail-workspace.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"


class ValidationError(RuntimeError):
    """Raised when the Material base rail/workspace contract is incomplete or weakened."""


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


def strip_xml_comments(source: str) -> str:
    return re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)


# --------------------------------------------------------------------------------------------------
# Registry loading
# --------------------------------------------------------------------------------------------------
def load_registry(registry_path: Path) -> dict[str, Any]:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")
    return data


def _load_contents(repo_root: Path, data: Mapping[str, Any]) -> dict[str, str]:
    paths: set[str] = {DEFINITION_PATH}
    for marker in data.get("markers", []):
        if isinstance(marker, dict):
            for key in ("source", "header", "ui"):
                value = marker.get(key)
                if isinstance(value, str):
                    paths.add(value)
    call_site = data.get("kicker_call_site")
    if isinstance(call_site, dict) and isinstance(call_site.get("source"), str):
        paths.add(call_site["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


# --------------------------------------------------------------------------------------------------
# definition.xml token existence + value fidelity
# --------------------------------------------------------------------------------------------------
def _parse_definition(text: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise ValidationError(f"definition.xml is not valid XML: {error}") from error


def validate_definition(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    root = _parse_definition(contents.get(DEFINITION_PATH, ""))

    palettes: dict[str, set[str]] = {}
    for palette in root.findall("palette"):
        scheme = palette.get("scheme", "")
        palettes[scheme] = {c.get("name") for c in palette.findall("color") if c.get("name")}
    for scheme in ("", "dark"):
        if scheme not in palettes:
            raise ValidationError(f"definition.xml is missing the {scheme!r} palette scheme")
    for role in data.get("palette_tokens", []):
        for scheme in ("", "dark"):
            if role not in palettes[scheme]:
                raise ValidationError(
                    f"definition.xml token drift: colour role {role!r} missing from "
                    f"scheme {scheme!r}"
                )

    metrics = root.find("metrics")
    metric_names = (
        {m.get("name") for m in metrics.findall("metric")} if metrics is not None else set()
    )
    for name in data.get("metric_tokens", []):
        if name not in metric_names:
            raise ValidationError(f"definition.xml token drift: metric {name!r} missing")

    shapes = root.find("shapes")
    radii = (
        {r.get("name"): r.get("value") for r in shapes.findall("radius")}
        if shapes is not None
        else {}
    )
    shape_tokens = data.get("shape_tokens", {})
    if isinstance(shape_tokens, dict):
        for name, expected in shape_tokens.items():
            actual = radii.get(name)
            if actual is None:
                raise ValidationError(f"definition.xml token drift: radius {name!r} missing")
            if actual != expected:
                raise ValidationError(
                    f"definition.xml token drift: radius {name!r} is {actual!r}, "
                    f"expected {expected!r}"
                )


# --------------------------------------------------------------------------------------------------
# Guarded source markers
# --------------------------------------------------------------------------------------------------
def _require(code: str, marker: str, context: str) -> None:
    if marker not in code:
        raise ValidationError(f"{context}: missing marker in code ({marker!r})")


def validate_guard(code: str, guard: Mapping[str, Any], context: str) -> None:
    _require(code, guard["env"], f"{context}:guard")
    _require(code, guard["value_marker"], f"{context}:guard")
    _require(code, guard["high_contrast_marker"], f"{context}:guard")
    _require(code, f"#include {guard['token_include']}", f"{context}:guard")
    for resolver in guard.get("resolver_markers", []):
        _require(code, resolver, f"{context}:guard")


def validate_markers(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    guard = data.get("guard")
    if not isinstance(guard, dict):
        raise ValidationError("registry guard block must be an object")

    markers = data.get("markers")
    if not isinstance(markers, list) or not markers:
        raise ValidationError("registry markers must be a non-empty array")
    if data.get("expected_markers") != len(markers):
        raise ValidationError("registry expected_markers count drift")

    seen: set[str] = set()
    for index, marker in enumerate(markers):
        if not isinstance(marker, dict):
            raise ValidationError(f"marker #{index} must be an object")
        marker_id = marker.get("id")
        if not isinstance(marker_id, str) or not marker_id:
            raise ValidationError(f"marker #{index} needs a non-empty id")
        if marker_id in seen:
            raise ValidationError(f"duplicate marker id: {marker_id}")
        seen.add(marker_id)
        context = f"marker[{marker_id}]"

        if marker.get("runtime_verified") is not False:
            raise ValidationError(f"{context}: runtime_verified must be false")

        source_path = marker.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            raise ValidationError(f"{context}: source {source_path} missing")
        code = strip_cpp_non_code(source)

        if marker.get("guarded", True):
            validate_guard(code, guard, context)

        for role in marker.get("tokens", []):
            if f'"{role}"' not in code:
                raise ValidationError(
                    f"{context}: token role {role!r} not consumed as a quoted literal in code"
                )

        for code_marker in marker.get("code_markers", []):
            _require(code, code_marker, context)

        header_path = marker.get("header")
        if isinstance(header_path, str):
            header = contents.get(header_path)
            if header is None:
                raise ValidationError(f"{context}: header {header_path} missing")
            header_code = strip_cpp_non_code(header)
            for header_marker in marker.get("header_markers", []):
                _require(header_code, header_marker, f"{context}:header")

        ui_path = marker.get("ui")
        if isinstance(ui_path, str):
            ui = contents.get(ui_path)
            if ui is None:
                raise ValidationError(f"{context}: ui {ui_path} missing")
            ui_code = strip_xml_comments(ui)
            for ui_marker in marker.get("ui_markers", []):
                _require(ui_code, ui_marker, f"{context}:ui")


def validate_kicker_call_site(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    call_site = data.get("kicker_call_site")
    if not isinstance(call_site, dict):
        raise ValidationError("registry kicker_call_site must be an object")
    source_path = call_site.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        raise ValidationError(f"kicker_call_site: source {source_path} missing")
    code = strip_cpp_non_code(source)
    for marker in call_site.get("markers", []):
        _require(code, marker, "kicker_call_site")


# --------------------------------------------------------------------------------------------------
def validate(repo_root: Path, registry_path: Path) -> dict[str, Any]:
    data = load_registry(registry_path)

    if data.get("schema_version") != 1:
        raise ValidationError("registry schema_version must be 1")
    if data.get("contract") != "material-base-rail-workspace":
        raise ValidationError("registry contract has an unexpected value")
    if data.get("platform") != "windows":
        raise ValidationError("registry platform must be windows")
    if data.get("definition_file") != DEFINITION_PATH:
        raise ValidationError("registry definition_file has an unexpected path")
    if data.get("runtime_verified") is not False:
        raise ValidationError("registry runtime_verified must be false")

    contents = _load_contents(repo_root, data)
    validate_definition(data, contents)
    validate_markers(data, contents)
    validate_kicker_call_site(data, contents)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = args.registry.resolve() if args.registry is not None else DEFAULT_REGISTRY
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Material base rail/workspace contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material base rail/workspace contract passed: "
        f"{len(data['markers'])} guarded dbaccess surfaces consume the rail palette "
        "(@surface-container fill, @outline-variant divider, @primary-container selection, "
        "@on-surface-variant kicker) behind the VCL_FILE_WIDGET_THEME guard, source-declared only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
