#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for Writer's sidebar decks (WIN-WR-004).

``qa/windows-ui-contract/writer-sidebar-decks.json`` pins the two real,
non-experimental Writer-owned sidebar decks that ``SwPanelFactory`` routes to
production panel classes: the WriterPageDeck 'Styles' panel (``PageStylesPanel``
over pagestylespanel.ui) and the NavigatorDeck panel (``SwNavigationPI`` over
navigatorpanel.ui). It is a pure source-composition + control-flow pin -- it
asserts NO new definition.xml part/state, because the widgets involved (combobox,
ColorListBox/menu-button, toolbar, treeview) are stock weld controls already
covered by generic control theming outside this row's scope.

For each surface this checker cross-validates, fail-closed:

* ``widget_bindings`` -- every declared ``{id, gtk_class, weld_accessor}`` must
  resolve to a real ``<object class=gtk_class id=id>`` in the panel's .ui, and the
  panel's .cxx must bind it via ``weld_accessor(u"id"_ustr)`` in real
  (comment-stripped) code. A renamed/removed widget id, wrong class, or dropped
  weld call fails closed.
* ``factory_routing`` -- SwPanelFactory.cxx must still route the
  ``rsResourceURL.endsWith("<suffix>")`` branch to the real ``<create_call>``.
* ``visibility_switch`` -- the panel's mutually-exclusive visibility state machine
  is extracted by brace-matched per-branch bodies: every declared ``shown``
  control must carry ``->show()`` and every ``hidden`` control ``->hide()`` in its
  branch, plus any pinned ``side_effects`` (tree ShowTree/HideTree,
  SetGlobalMode(bool)) and method-level side effects (TriggerDeckLayouting). The
  GRADIENT branch's two-visible case (colour + gradient) is modelled as a set. The
  ToggleTree LOK early-return branch is an out-of-scope carve-out (its marker is
  only checked to exist, never pinned as a mode branch).

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, deck pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/writer-sidebar-decks.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

REQUIRED_SURFACE_IDS = {"writer.sidebar.page-styles", "writer.sidebar.navigator"}


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _function_body(source: str, signature: str) -> str | None:
    start = source.find(signature)
    if start < 0:
        return None
    opening = source.find("{", start + len(signature))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    return None


def _branch_body(body: str, anchor: str) -> str | None:
    """Brace-matched block that follows the first occurrence of ``anchor``."""
    start = body.find(anchor)
    if start < 0:
        return None
    opening = body.find("{", start + len(anchor))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(body)):
        if body[index] == "{":
            depth += 1
        elif body[index] == "}":
            depth -= 1
            if depth == 0:
                return body[opening + 1 : index]
    return None


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for surface in registry.get("surfaces", []) or []:
        if not isinstance(surface, dict):
            continue
        for key in ("ui_file", "widget_source"):
            if isinstance(surface.get(key), str):
                paths.add(surface[key])
        for owner in surface.get("owner_sources", []) or []:
            if isinstance(owner, str):
                paths.add(owner)
        routing = surface.get("factory_routing")
        if isinstance(routing, dict) and isinstance(routing.get("source"), str):
            paths.add(routing["source"])
        switch = surface.get("visibility_switch")
        if isinstance(switch, dict) and isinstance(switch.get("source"), str):
            paths.add(switch["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# .ui widget lookups
# --------------------------------------------------------------------------------------------------
def _parse_ui(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


def _object_class(root: ET.Element, object_id: str) -> str | None:
    for node in root.iter("object"):
        if node.get("id") == object_id:
            return node.get("class")
    return None


def _validate_widget_bindings(
    context: str, surface: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    ui_file = surface.get("ui_file")
    ui_root = _parse_ui(
        contents.get(ui_file) if isinstance(ui_file, str) else None, f"{context}:ui", errors
    )
    widget_source = surface.get("widget_source")
    src = contents.get(widget_source) if isinstance(widget_source, str) else None
    code = _without_cpp_comments(src) if src is not None else None
    if code is None:
        errors.append(f"{context}:widget_source {widget_source} missing")

    bindings = surface.get("widget_bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append(f"{context}:widget_bindings:non-empty array required")
        return
    seen: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            errors.append(f"{context}:widget_binding:object required")
            continue
        wid = binding.get("id")
        gtk_class = binding.get("gtk_class")
        accessor = binding.get("weld_accessor")
        if not (isinstance(wid, str) and isinstance(gtk_class, str) and isinstance(accessor, str)):
            errors.append(f"{context}:widget_binding:id/gtk_class/weld_accessor strings required")
            continue
        if wid in seen:
            errors.append(f"{context}:widget_binding:{wid}:duplicate id")
        seen.add(wid)
        if ui_root is not None:
            actual_class = _object_class(ui_root, wid)
            if actual_class is None:
                errors.append(f"{context}:widget_binding:{wid} missing from {ui_file}")
            elif actual_class != gtk_class:
                errors.append(
                    f"{context}:widget_binding:{wid} class is {actual_class!r}, expected {gtk_class!r}"
                )
        if code is not None:
            weld_call = f'{accessor}(u"{wid}"_ustr)'
            if weld_call not in code:
                errors.append(
                    f"{context}:widget_binding:{wid} not bound in code ({weld_call})"
                )


def _validate_factory_routing(
    context: str, routing: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(routing, dict):
        errors.append(f"{context}:factory_routing:object required")
        return
    source_path = routing.get("source")
    src = contents.get(source_path) if isinstance(source_path, str) else None
    if src is None:
        errors.append(f"{context}:factory_routing:source {source_path} missing")
        return
    code = _without_cpp_comments(src)
    suffix = routing.get("resource_suffix")
    create_call = routing.get("create_call")
    if isinstance(suffix, str):
        guard = f'rsResourceURL.endsWith("{suffix}")'
        if guard not in code:
            errors.append(f"{context}:factory_routing:dispatch missing in code ({guard})")
    else:
        errors.append(f"{context}:factory_routing:resource_suffix string required")
    if isinstance(create_call, str):
        if create_call not in code:
            errors.append(f"{context}:factory_routing:create call missing in code ({create_call})")
    else:
        errors.append(f"{context}:factory_routing:create_call string required")


def _validate_visibility_switch(
    context: str, switch: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(switch, dict):
        errors.append(f"{context}:visibility_switch:object required")
        return
    source_path = switch.get("source")
    src = contents.get(source_path) if isinstance(source_path, str) else None
    if src is None:
        errors.append(f"{context}:visibility_switch:source {source_path} missing")
        return
    code = _without_cpp_comments(src)
    signature = switch.get("function_signature")
    if not isinstance(signature, str):
        errors.append(f"{context}:visibility_switch:function_signature string required")
        return
    body = _function_body(code, signature)
    if body is None:
        errors.append(f"{context}:visibility_switch:function {signature} not found")
        return

    for effect in switch.get("method_side_effects", []) or []:
        if isinstance(effect, str) and effect not in body:
            errors.append(f"{context}:visibility_switch:method side-effect missing in code ({effect})")

    # The optional LOK carve-out marker must exist (a real branch), never be pinned as a mode.
    lok = switch.get("lok_carveout")
    if isinstance(lok, dict):
        marker = lok.get("marker")
        if isinstance(marker, str) and marker not in body:
            errors.append(f"{context}:visibility_switch:lok_carveout marker missing in code ({marker})")

    branches = switch.get("branches")
    if not isinstance(branches, list) or not branches:
        errors.append(f"{context}:visibility_switch:branches:non-empty array required")
        return
    seen: set[str] = set()
    for branch in branches:
        if not isinstance(branch, dict):
            errors.append(f"{context}:visibility_switch:branch:object required")
            continue
        name = branch.get("name")
        anchor = branch.get("anchor")
        if not isinstance(name, str) or not isinstance(anchor, str):
            errors.append(f"{context}:visibility_switch:branch:name/anchor strings required")
            continue
        if name in seen:
            errors.append(f"{context}:visibility_switch:branch:{name}:duplicate")
        seen.add(name)
        blabel = f"{context}:visibility_switch[{name}]"
        branch_body = _branch_body(body, anchor)
        if branch_body is None:
            errors.append(f"{blabel}:branch body not found (anchor {anchor!r})")
            continue
        for control in branch.get("shown", []) or []:
            if isinstance(control, str) and f"{control}->show()" not in branch_body:
                errors.append(f"{blabel}:{control} not shown (missing {control}->show())")
        for control in branch.get("hidden", []) or []:
            if isinstance(control, str) and f"{control}->hide()" not in branch_body:
                errors.append(f"{blabel}:{control} not hidden (missing {control}->hide())")
        for effect in branch.get("side_effects", []) or []:
            if isinstance(effect, str) and effect not in branch_body:
                errors.append(f"{blabel}:side-effect missing in branch ({effect})")


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-writer-sidebar-decks":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("theme_flag") != "VCL_FILE_WIDGET_THEME":
        errors.append("registry:theme_flag:must be VCL_FILE_WIDGET_THEME")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    surfaces = registry.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("registry:surfaces:non-empty array required")
        surfaces = []
    if registry.get("expected_surfaces") != len(surfaces):
        errors.append("registry:expected_surfaces:count drift")

    seen_ids: set[str] = set()
    for index, surface in enumerate(surfaces):
        context = f"surfaces[{index}]"
        if not isinstance(surface, dict):
            errors.append(f"{context}:object required")
            continue
        surface_id = surface.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"{context}:surface_id:non-empty string required")
            continue
        context = f"surface[{surface_id}]"
        if surface_id in seen_ids:
            errors.append(f"{context}:surface_id:duplicate")
        seen_ids.add(surface_id)

        if surface.get("status") != "source-declared":
            errors.append(f"{context}:status:must be source-declared")
        if not isinstance(surface.get("runtime_verified"), bool):
            errors.append(f"{context}:runtime_verified:boolean required")
        elif surface["runtime_verified"]:
            errors.append(f"{context}:runtime_verified:no runtime evidence exists; must be false")

        for owner in surface.get("owner_sources", []) or []:
            if isinstance(owner, str) and owner not in contents:
                errors.append(f"{context}:owner_source:missing {owner}")

        _validate_widget_bindings(context, surface, contents, errors)
        _validate_factory_routing(context, surface.get("factory_routing"), contents, errors)
        _validate_visibility_switch(context, surface.get("visibility_switch"), contents, errors)

    missing_required = REQUIRED_SURFACE_IDS - seen_ids
    if missing_required:
        errors.append(f"registry:surfaces:missing required {', '.join(sorted(missing_required))}")

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents)
    if errors:
        raise ValidationError("\n".join(errors))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    try:
        validate_repository(repo_root)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Writer sidebar decks contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Writer sidebar decks contract passed: "
        f"{len(registry['surfaces'])} Writer-owned deck panel(s) with .ui widget bindings, "
        "SwPanelFactory routing, and the PageStyles fill-switch + Navigator content/global "
        "visibility state machines intact (GRADIENT two-visible modelled as a set; LOK "
        "early-return carved out)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
