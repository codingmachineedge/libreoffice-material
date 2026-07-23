#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed composition-pinning contract for the Base Add Table/Query tree (WIN-BA-002).

``qa/windows-ui-contract/base-addtable-tree.json`` grounds the single concrete
WIN-BA-002 claim chapter 12.1 makes -- that Base's relation and query designers
use the net-less Material tree (``listnode`` disclosure at ``@size-tree-node`` and
the empty ``listnet``/``Entire`` state that suppresses connector nets) -- against
the real native wiring:

* ``definition_parts`` -- the ``listnode``/``listnet`` parts the tree resolves
  through must exist in definition.xml with the declared sizing attributes and
  states. Read only, never mutated.
* ``tree_view`` / ``contrast_view`` -- the Add Table/Query dialog's ``tablelist``
  GtkTreeView must bind the hierarchical GtkTreeStore model and carry no
  ``show-expanders`` override (disclosure stays governed by the native part),
  while the flat ``querylist`` binds the GtkListStore with ``show-expanders`` off
  -- so the two are never conflated.
* ``markers`` -- the ``.ui``-to-native wiring (adtabdlg.cxx), the plain
  ``OTableTreeListBox : TreeListBox`` subclass, the stock ``weld::TreeView``
  wrapper with no custom cell renderer, and the single shared ``OJoinController``
  construction path that both ``OQueryController`` and ``ORelationController``
  derive -- all asserted against comment-stripped source so commented-out or
  owner-draw wiring fails closed.

The ``carve_out`` block records, explicitly, that this proves ONLY the Add
Table/Query tree wiring: it makes no claim about the Table Design grid, the Query
Design join-graph canvas, SQL View, Form Design or Report Design. Source-declared
only: no build, no rendered tree, no runtime evidence (``runtime_verified: false``).
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
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/base-addtable-tree.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

ALLOWED_CARVE_OUT_STATUS = {"out-of-scope"}


class ValidationError(RuntimeError):
    """Raised when the Add Table/Query tree contract is incomplete or weakened."""


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
    tree_view = data.get("tree_view")
    if isinstance(tree_view, dict) and isinstance(tree_view.get("ui"), str):
        paths.add(tree_view["ui"])
    for marker in data.get("markers", []):
        if isinstance(marker, dict) and isinstance(marker.get("source"), str):
            paths.add(marker["source"])
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
# definition.xml native parts
# --------------------------------------------------------------------------------------------------
def _find_part(root: ET.Element, control: str, part_value: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part_value:
            return candidate
    return None


def validate_definition(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    root = _parse_xml(contents.get(DEFINITION_PATH, ""), "definition.xml")

    parts = data.get("definition_parts", {})
    if not isinstance(parts, dict):
        raise ValidationError("registry definition_parts must be an object")

    listnode = parts.get("listnode", {})
    node = _find_part(root, listnode.get("control", "listnode"), listnode.get("part", "Entire"))
    if node is None:
        raise ValidationError("definition.xml is missing the listnode/Entire part")
    for attr, expected in listnode.get("part_attrs", {}).items():
        if node.get(attr) != expected:
            raise ValidationError(
                f"definition.xml listnode/Entire {attr} is {node.get(attr)!r}, expected {expected!r}"
            )
    if listnode.get("require_enabled_state"):
        if not any(
            s.get("enabled") == "true" and s.get("button-value") is None
            for s in node.findall("state")
        ):
            raise ValidationError(
                "definition.xml listnode/Entire is missing its base enabled=true disclosure state"
            )

    listnet = parts.get("listnet", {})
    net = _find_part(root, listnet.get("control", "listnet"), listnet.get("part", "Entire"))
    if net is None:
        raise ValidationError("definition.xml is missing the listnet/Entire part")
    if listnet.get("require_empty_enabled_state"):
        empty_states = [
            s for s in net.findall("state") if s.get("enabled") == "true" and len(list(s)) == 0
        ]
        if not empty_states:
            raise ValidationError(
                "definition.xml listnet/Entire is missing the empty enabled=true state that "
                "suppresses connector nets"
            )

    metrics = root.find("metrics")
    metric_names = (
        {m.get("name") for m in metrics.findall("metric")} if metrics is not None else set()
    )
    for name in data.get("metric_tokens", []):
        if name not in metric_names:
            raise ValidationError(f"definition.xml token drift: metric {name!r} missing")


# --------------------------------------------------------------------------------------------------
# tablesjoindialog.ui tree-view wiring
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


def validate_tree_view(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    tree_view = data.get("tree_view")
    if not isinstance(tree_view, dict):
        raise ValidationError("registry tree_view must be an object")
    ui_path = tree_view.get("ui")
    ui_text = contents.get(ui_path) if isinstance(ui_path, str) else None
    if ui_text is None:
        raise ValidationError(f"tree_view: ui {ui_path} missing")
    root = _parse_xml(ui_text, ui_path)
    objects = _objects_by_id(root)

    def check_view(spec: Mapping[str, Any], label: str) -> None:
        view_id = spec.get("id")
        obj = objects.get(view_id)
        if obj is None:
            raise ValidationError(f"{label}: GtkTreeView id={view_id!r} not found in {ui_path}")
        if obj.get("class") != "GtkTreeView":
            raise ValidationError(f"{label}: id={view_id!r} is not a GtkTreeView")
        props = _direct_properties(obj)
        model = spec.get("model")
        if props.get("model") != model:
            raise ValidationError(
                f"{label}: id={view_id!r} model is {props.get('model')!r}, expected {model!r}"
            )
        model_obj = objects.get(model)
        expected_class = spec.get("model_store_class")
        if expected_class is not None:
            if model_obj is None or model_obj.get("class") != expected_class:
                actual = model_obj.get("class") if model_obj is not None else None
                raise ValidationError(
                    f"{label}: model {model!r} store class is {actual!r}, expected "
                    f"{expected_class!r}"
                )
        for forbidden in spec.get("forbidden_props", []):
            if forbidden in props:
                raise ValidationError(
                    f"{label}: id={view_id!r} must NOT carry the {forbidden!r} property "
                    "(disclosure must stay governed by the native listnode part)"
                )
        if spec.get("require_show_expanders_false"):
            value = props.get("show-expanders", "").strip().lower()
            if value not in ("false", "0"):
                raise ValidationError(
                    f"{label}: id={view_id!r} must set show-expanders=False (flat list), "
                    f"found {props.get('show-expanders')!r}"
                )

    check_view(tree_view, "tree_view")

    contrast = data.get("contrast_view")
    if isinstance(contrast, dict):
        check_view(contrast, "contrast_view")


# --------------------------------------------------------------------------------------------------
# source markers
# --------------------------------------------------------------------------------------------------
def validate_markers(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
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

        source_path = marker.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            raise ValidationError(f"{context}: source {source_path} missing")
        code = strip_cpp_non_code(source)

        for code_marker in marker.get("code_markers", []):
            if code_marker not in code:
                raise ValidationError(f"{context}: missing marker in code ({code_marker!r})")

        for forbidden in marker.get("forbidden_markers", []):
            if forbidden in code:
                raise ValidationError(
                    f"{context}: forbidden owner-draw/custom-render marker present ({forbidden!r}); "
                    f"{marker.get('forbidden_note', 'the stock native tree part must govern')}"
                )


def validate_carve_out(data: Mapping[str, Any]) -> None:
    carve_out = data.get("carve_out")
    if not isinstance(carve_out, dict):
        raise ValidationError("registry carve_out must be an object")
    status = carve_out.get("status")
    if status not in ALLOWED_CARVE_OUT_STATUS:
        raise ValidationError(
            f"carve_out status {status!r} must stay one of {sorted(ALLOWED_CARVE_OUT_STATUS)} "
            "(this pin never claims to cover the carved-out designers)"
        )
    surfaces = carve_out.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ValidationError("carve_out must list the surfaces it explicitly does NOT cover")


# --------------------------------------------------------------------------------------------------
def validate(repo_root: Path, registry_path: Path) -> dict[str, Any]:
    data = load_registry(registry_path)

    if data.get("schema_version") != 1:
        raise ValidationError("registry schema_version must be 1")
    if data.get("contract") != "material-base-addtable-tree":
        raise ValidationError("registry contract has an unexpected value")
    if data.get("platform") != "windows":
        raise ValidationError("registry platform must be windows")
    if data.get("definition_file") != DEFINITION_PATH:
        raise ValidationError("registry definition_file has an unexpected path")
    if data.get("runtime_verified") is not False:
        raise ValidationError("registry runtime_verified must be false")

    contents = _load_contents(repo_root, data)
    validate_definition(data, contents)
    validate_tree_view(data, contents)
    validate_markers(data, contents)
    validate_carve_out(data)
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
        print(f"Base Add Table/Query tree contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Base Add Table/Query tree contract passed: the hierarchical tablelist tree wires the "
        f"GtkTreeStore model through OTableTreeListBox/TreeListBox and the shared OJoinController "
        f"path ({len(data['markers'])} markers) onto the net-less listnode/listnet definition "
        "parts; Table/Query/Form/Report designers explicitly carved out, source-declared only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
