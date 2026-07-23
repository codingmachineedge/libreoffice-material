#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed composition-pinning contract for the Math editor + Elements panel (WIN-MA-001).

``qa/windows-ui-contract/math-editor-elements.json`` pins the real StarMath tree
behind the inventory's 'shared multiline primitive compiled' claim and design
12.2, for the command-editor strip and the Elements panel only:

* ``definition_part`` -- the compiled ``multilineeditbox``/``Entire`` 3-state token
  set (enabled/focused/disabled) must be present with the exact fill / stroke /
  stroke-width / radius tokens. Read only, never mutated. This pins that the
  shared primitive is unchanged; it does NOT claim Math's editor paints from it
  (WeldEditView sources its own field colour -- see the registry caveat).
* ``ui_objects`` -- editwindow.ui's scrolledwindow/editview and
  sidebarelements_math.ui's categorylist/elements/deletemenu must exist with the
  declared classes and the exact scroll-policy / IconView activation properties
  that SmEditWindow / SmElementsPanel bind by name.
* ``markers`` -- the by-name builder bindings (comment-stripped source) in
  edit.cxx and SmElementsPanel.cxx, and the single shared SmElementsControl
  definition in ElementsDockingWindow.cxx.
* ``shared_control_header`` -- the one SmElementsControl class + its ``categories()``
  and IconView/Menu ctor, so the sidebar panel and the control never fork.
* ``category_list`` -- the closed, ordered 11-entry ``RID_CATEGORY_*`` list driving
  the category combo, pinned by symbol identity + order (locale-safe) and each id
  defined as an ``NC_()`` string.

Source-composition evidence only: no build, no rendered editor/panel, no runtime
interaction is claimed (``runtime_verified: false`` throughout).
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
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/math-editor-elements.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

STATE_ATTR_KEYS = ("enabled", "focused", "pressed", "rollover", "default", "selected", "button-value")


class ValidationError(RuntimeError):
    """Raised when the Math editor/elements contract is incomplete or weakened."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def strip_cpp_non_code(source: str) -> str:
    raw = re.compile(
        r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
        re.DOTALL,
    )
    source = raw.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


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
    for obj in data.get("ui_objects", []):
        if isinstance(obj, dict) and isinstance(obj.get("ui"), str):
            paths.add(obj["ui"])
    for marker in data.get("markers", []):
        if isinstance(marker, dict) and isinstance(marker.get("source"), str):
            paths.add(marker["source"])
    header = data.get("shared_control_header", {})
    if isinstance(header, dict) and isinstance(header.get("header"), str):
        paths.add(header["header"])
    category = data.get("category_list", {})
    if isinstance(category, dict):
        for key in ("source", "strings_file"):
            if isinstance(category.get(key), str):
                paths.add(category[key])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def _parse_xml(text: str, label: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise ValidationError(f"{label} is not valid XML: {error}") from error


# --------------------------------------------------------------------------------------------------
# definition.xml multilineeditbox part
# --------------------------------------------------------------------------------------------------
def _find_part(root: ET.Element, control: str, part_value: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part_value:
            return candidate
    return None


def _state_signature(state: ET.Element) -> dict[str, str]:
    return {key: state.get(key, "any") for key in STATE_ATTR_KEYS}


def _match_state(part: ET.Element, attrs: Mapping[str, str]) -> ET.Element | None:
    wanted = {key: attrs.get(key, "any") for key in STATE_ATTR_KEYS}
    for state in part.findall("state"):
        if _state_signature(state) == wanted:
            return state
    return None


def validate_definition_part(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    root = _parse_xml(contents.get(DEFINITION_PATH, ""), "definition.xml")
    part_decl = data.get("definition_part")
    if not isinstance(part_decl, dict):
        raise ValidationError("registry definition_part must be an object")
    control = part_decl.get("control")
    part_name = part_decl.get("part")
    part = _find_part(root, control, part_name)
    if part is None:
        raise ValidationError(f"definition.xml is missing {control}/{part_name}")
    for state_decl in part_decl.get("states", []):
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        state = _match_state(part, attrs)
        if state is None:
            raise ValidationError(
                f"definition.xml {control}/{part_name}:{role}: no <state> matching {attrs}"
            )
        rect = next((child for child in state if child.tag in ("rect", "line")), None)
        if rect is None:
            raise ValidationError(
                f"definition.xml {control}/{part_name}:{role} state has no rect/line"
            )
        for token_key, expected in state_decl.get("tokens", {}).items():
            actual = rect.get(token_key)
            if actual != expected:
                raise ValidationError(
                    f"definition.xml {control}/{part_name}:{role} token drift: {token_key} is "
                    f"{actual!r}, expected {expected!r}"
                )


# --------------------------------------------------------------------------------------------------
# .ui objects
# --------------------------------------------------------------------------------------------------
def _objects_by_id(root: ET.Element) -> dict[str, ET.Element]:
    result: dict[str, ET.Element] = {}
    for obj in root.iter("object"):
        obj_id = obj.get("id")
        if obj_id:
            result[obj_id] = obj
    return result


def _direct_properties(obj: ET.Element) -> dict[str, str]:
    return {
        prop.get("name"): (prop.text or "")
        for prop in obj.findall("property")
        if prop.get("name")
    }


def validate_ui_objects(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    cache: dict[str, dict[str, ET.Element]] = {}
    for decl in data.get("ui_objects", []):
        if not isinstance(decl, dict):
            raise ValidationError("ui_objects entry must be an object")
        ui_path = decl.get("ui")
        obj_id = decl.get("object_id")
        context = f"ui_object[{obj_id}]"
        if ui_path not in cache:
            ui_text = contents.get(ui_path)
            if ui_text is None:
                raise ValidationError(f"{context}: ui {ui_path} missing")
            cache[ui_path] = _objects_by_id(_parse_xml(ui_text, ui_path))
        objects = cache[ui_path]
        obj = objects.get(obj_id)
        if obj is None:
            raise ValidationError(f"{context}: object id {obj_id!r} not found in {ui_path}")
        expected_class = decl.get("object_class")
        if expected_class is not None and obj.get("class") != expected_class:
            raise ValidationError(
                f"{context}: class is {obj.get('class')!r}, expected {expected_class!r}"
            )
        props = _direct_properties(obj)
        for name, expected in decl.get("props", {}).items():
            if props.get(name) != expected:
                raise ValidationError(
                    f"{context}: property {name!r} is {props.get(name)!r}, expected {expected!r}"
                )


# --------------------------------------------------------------------------------------------------
# source + header markers
# --------------------------------------------------------------------------------------------------
def validate_markers(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    markers = data.get("markers")
    if not isinstance(markers, list) or not markers:
        raise ValidationError("registry markers must be a non-empty array")
    if data.get("expected_markers") != len(markers):
        raise ValidationError("registry expected_markers count drift")

    seen: set[str] = set()
    for index, marker in enumerate(markers):
        marker_id = marker.get("id")
        if not isinstance(marker_id, str) or not marker_id:
            raise ValidationError(f"marker #{index} needs a non-empty id")
        if marker_id in seen:
            raise ValidationError(f"duplicate marker id: {marker_id}")
        seen.add(marker_id)
        context = f"marker[{marker_id}]"
        source_path = marker.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            raise ValidationError(f"{context}: source {source_path} missing")
        code = strip_cpp_non_code(source)
        for code_marker in marker.get("code_markers", []):
            if code_marker not in code:
                raise ValidationError(f"{context}: missing marker in code ({code_marker!r})")


def validate_shared_control_header(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    header_decl = data.get("shared_control_header")
    if not isinstance(header_decl, dict):
        raise ValidationError("registry shared_control_header must be an object")
    header_path = header_decl.get("header")
    header = contents.get(header_path) if isinstance(header_path, str) else None
    if header is None:
        raise ValidationError(f"shared_control_header: header {header_path} missing")
    code = strip_cpp_non_code(header)
    for marker in header_decl.get("markers", []):
        if marker not in code:
            raise ValidationError(
                f"shared_control_header: missing marker in code ({marker!r})"
            )


# --------------------------------------------------------------------------------------------------
# category list closure
# --------------------------------------------------------------------------------------------------
def validate_category_list(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    category = data.get("category_list")
    if not isinstance(category, dict):
        raise ValidationError("registry category_list must be an object")
    source_path = category.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        raise ValidationError(f"category_list: source {source_path} missing")
    code = strip_cpp_non_code(source)

    vector_open = category.get("vector_open")
    vector_close = category.get("vector_close", "};")
    start = code.find(vector_open)
    if start < 0:
        raise ValidationError(f"category_list: vector opener {vector_open!r} not found")
    end = code.find(vector_close, start + len(vector_open))
    if end < 0:
        raise ValidationError("category_list: vector is not closed")
    block = code[start + len(vector_open):end]

    ordered_ids = category.get("ordered_ids", [])
    cursor = 0
    for category_id in ordered_ids:
        position = block.find(category_id, cursor)
        if position < 0:
            raise ValidationError(
                f"category_list: {category_id!r} missing or out of order in s_a5Categories"
            )
        cursor = position + len(category_id)

    # No extra RID_CATEGORY_* entries may sneak in (closed list).
    found = re.findall(r"RID_CATEGORY_[A-Z_]+", block)
    if len(found) != len(ordered_ids):
        raise ValidationError(
            f"category_list: s_a5Categories holds {len(found)} RID_CATEGORY_* entries, "
            f"expected exactly {len(ordered_ids)} (closed list)"
        )

    strings_path = category.get("strings_file")
    strings = contents.get(strings_path) if isinstance(strings_path, str) else None
    if strings is None:
        raise ValidationError(f"category_list: strings_file {strings_path} missing")
    for category_id in ordered_ids:
        if not re.search(
            rf"#define\s+{re.escape(category_id)}\s+NC_\(", strings
        ):
            raise ValidationError(
                f"category_list: {category_id!r} is not defined as an NC_() string in {strings_path}"
            )


# --------------------------------------------------------------------------------------------------
def validate(repo_root: Path, registry_path: Path) -> dict[str, Any]:
    data = load_registry(registry_path)

    if data.get("schema_version") != 1:
        raise ValidationError("registry schema_version must be 1")
    if data.get("contract") != "material-math-editor-elements":
        raise ValidationError("registry contract has an unexpected value")
    if data.get("platform") != "windows":
        raise ValidationError("registry platform must be windows")
    if data.get("definition_file") != DEFINITION_PATH:
        raise ValidationError("registry definition_file has an unexpected path")
    if data.get("runtime_verified") is not False:
        raise ValidationError("registry runtime_verified must be false")

    contents = _load_contents(repo_root, data)
    validate_definition_part(data, contents)
    validate_ui_objects(data, contents)
    validate_markers(data, contents)
    validate_shared_control_header(data, contents)
    validate_category_list(data, contents)
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
        print(f"Math editor/elements contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Math editor/elements contract passed: multilineeditbox 3-state token fidelity, "
        "editwindow/sidebarelements .ui bindings, SmEditWindow/SmElementsPanel by-name wiring "
        f"and the closed {len(data['category_list']['ordered_ids'])}-entry RID_CATEGORY_* list, "
        "source-composition evidence only (Math editor does not paint from the tokens)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
