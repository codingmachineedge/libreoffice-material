#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material chart embedded-object editor (WIN-CH-001).

``qa/windows-ui-contract/chart-editor.json`` pins the chart in-place OLE-edit composition from
docs/design/12-base-math-shared.md. The chart editor's toolbar and menu bar are data-driven
uiconfig XML and its sidebar is a factory-routed set of PanelLayout decks, so the M-scope of this
row is *pinning composition* -- command identity + order, separator placement, per-button
visibility, factory routes, and sidebar panel ids -- and grounding the Material treatment in the
already-implemented native toolbar part contract, never re-drawing controls. This checker parses
the real tree fail-closed:

* ``chrome_parts`` -- the native ``toolbar`` band / separator / nine-state ``Button`` parts that
  every chart chrome control resolves through must exist in definition.xml with the exact
  fill / stroke / stroke-width / radius tokens (the Button at ``@corner-toolbar``), every declared
  metric must carry its value, and every palette role must resolve in *both* the light and dark
  palettes. A renamed part, dropped state, or token drift fails closed. definition.xml is read-only;
  no new Material chart source is claimed -- the treatment is grounded entirely in these shared parts.
* ``toolbars`` -- chart2/uiconfig/toolbar/toolbar.xml's *entire* ordered composition (toolbaritem
  command identity + visibility and every separator, in order) must match exactly, including the two
  ``visible="false"`` expert items pinned in ``preserved_commands``. ``design_core`` commands must be
  present and visible; ``preserved_commands`` must remain present at any visibility.
* ``menu`` -- chart2/uiconfig/menubar/menubar.xml's eight top-level ``menu:menu`` ids must match
  exactly and every ``design_core`` menu must be present.
* ``factory`` -- Chart2PanelFactory.cxx must declare the factory implementation name and each of the
  eight ``rsResourceURL.endsWith("/<Panel>")`` sidebar routes as real (comment-stripped) code.
* ``sidebar_panels`` -- each of the six sidebar ``.ui`` files must carry its pinned panel root id.
* ``carveouts`` -- the drawinglayer chart canvas, live preview, data-table grid, and 3D scene are
  build-dependent, so their ``status`` must stay ``specified`` and is never promoted.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, chart
pixels, OLE activation, or runtime interaction are claimed. Registry-closure assignment
(chart2/ -> WIN-CH-001) is already satisfied by the prefix rule in the closure checker; this
contract does not touch it.
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
REGISTRY_PATH = "qa/windows-ui-contract/chart-editor.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CONTRACT_NAME = "material-chart-editor-composition"
INVENTORY_ROW = "WIN-CH-001"

TOOLBAR_NS = "{http://openoffice.org/2001/toolbar}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"
MENU_NS = "{http://openoffice.org/2001/menu}"

# definition.xml <state> attribute keys, matched as a complete exact signature (no partial alias).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO / source helpers
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for toolbar in registry.get("toolbars", []) or []:
        if isinstance(toolbar, dict) and isinstance(toolbar.get("file"), str):
            paths.add(toolbar["file"])
    menu = registry.get("menu")
    if isinstance(menu, dict) and isinstance(menu.get("file"), str):
        paths.add(menu["file"])
    factory = registry.get("factory")
    if isinstance(factory, dict) and isinstance(factory.get("source"), str):
        paths.add(factory["source"])
    for panel in registry.get("sidebar_panels", []) or []:
        if isinstance(panel, dict) and isinstance(panel.get("file"), str):
            paths.add(panel["file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


# --------------------------------------------------------------------------------------------------
# definition.xml lookups (native toolbar parts)
# --------------------------------------------------------------------------------------------------
def _palette_color(root: ET.Element, scheme: str, name: str) -> str | None:
    for palette in root.findall("palette"):
        if (palette.get("scheme") or "") != scheme:
            continue
        for color in palette.findall("color"):
            if color.get("name") == name:
                return color.get("value")
    return None


def _named_value(root: ET.Element, container: str, tag: str, name: str) -> str | None:
    holder = root.find(container)
    if holder is None:
        return None
    for element in holder.findall(tag):
        if element.get("name") == name:
            return element.get("value")
    return None


def _find_part(root: ET.Element, control: str, part: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part:
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


def _first_drawing_child(state: ET.Element) -> ET.Element | None:
    for child in state:
        if child.tag in ("rect", "line"):
            return child
    return None


def _validate_simple_part(
    control: str, root: ET.Element, name: str, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    part_name = declaration.get("part")
    if not isinstance(part_name, str):
        errors.append(f"chrome_parts:{name}:part must be a string")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"chrome_parts:{name}:{control}/{part_name} missing in definition.xml")
        return
    state = _match_state(part, {})
    if state is None:
        errors.append(f"chrome_parts:{name}:{control}/{part_name} no default <state>")
        return
    drawing = _first_drawing_child(state)
    if drawing is None:
        errors.append(f"chrome_parts:{name}:{control}/{part_name} state has no rect/line")
        return
    expected_element = declaration.get("element")
    if isinstance(expected_element, str) and drawing.tag != expected_element:
        errors.append(
            f"chrome_parts:{name}:{control}/{part_name} element is <{drawing.tag}>, "
            f"expected <{expected_element}>"
        )
    tokens = declaration.get("tokens", {})
    if isinstance(tokens, dict):
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"chrome_parts:{name}:{control}/{part_name} token drift: {token_key} is "
                    f"{actual!r}, expected {expected!r}"
                )


def _validate_button_part(
    control: str, root: ET.Element, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    part_name = declaration.get("part")
    if not isinstance(part_name, str):
        errors.append("chrome_parts:button:part must be a string")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"chrome_parts:button:{control}/{part_name} missing in definition.xml")
        return
    states = declaration.get("states")
    if not isinstance(states, list) or not states:
        errors.append("chrome_parts:button:states non-empty array required")
        return
    for state_decl in states:
        if not isinstance(state_decl, dict):
            errors.append(f"chrome_parts:button:{control}/{part_name} state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"chrome_parts:button:{control}/{part_name}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(
                f"chrome_parts:button:{control}/{part_name}:{role} no <state> matching {attrs}"
            )
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"chrome_parts:button:{control}/{part_name}:{role} state has no rect/line")
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"chrome_parts:button:{control}/{part_name}:{role} element is <{drawing.tag}>, "
                f"expected <{expected_element}>"
            )
        tokens = state_decl.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append(f"chrome_parts:button:{control}/{part_name}:{role} tokens must be object")
            continue
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"chrome_parts:button:{control}/{part_name}:{role} token drift: {token_key} is "
                    f"{actual!r}, expected {expected!r}"
                )


def _validate_chrome_parts(root: ET.Element, parts: Mapping[str, Any], errors: list[str]) -> None:
    control = parts.get("control")
    if not isinstance(control, str):
        errors.append("chrome_parts:control:must be a string")
        return
    if root.find(control) is None:
        errors.append(f"chrome_parts:control:<{control}> missing in definition.xml")
        return

    for name in ("band", "entire", "separator"):
        declaration = parts.get(name)
        if isinstance(declaration, dict):
            _validate_simple_part(control, root, name, declaration, errors)
        else:
            errors.append(f"chrome_parts:{name}:object required")

    button = parts.get("button")
    if isinstance(button, dict):
        _validate_button_part(control, root, button, errors)
    else:
        errors.append("chrome_parts:button:object required")

    for metric in parts.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("chrome_parts:metric:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("chrome_parts:metric:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"chrome_parts:metric:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(
                f"chrome_parts:metric:{mname} is {actual!r}, expected {expected!r} (metric drift)"
            )

    for role in parts.get("palette_colors", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"chrome_parts:palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# uiconfig toolbar / menu parsing
# --------------------------------------------------------------------------------------------------
def _actual_toolbar_sequence(root: ET.Element) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    for child in root:
        tag = child.tag.split("}")[-1]
        if tag == "toolbaritem":
            visible = child.get(f"{TOOLBAR_NS}visible") != "false"
            sequence.append({"command": child.get(f"{XLINK_NS}href"), "visible": visible})
        elif tag == "toolbarseparator":
            sequence.append({"separator": True})
    return sequence


def _entry_repr(entry: Mapping[str, Any]) -> str:
    if entry.get("separator"):
        return "<separator>"
    return f"{entry.get('command')}(visible={entry.get('visible')})"


def _validate_toolbar(
    context: str, root: ET.Element, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    expected = declaration.get("sequence")
    if not isinstance(expected, list) or not expected:
        errors.append(f"{context}:sequence:non-empty array required")
        return
    actual = _actual_toolbar_sequence(root)

    if len(actual) != len(expected):
        errors.append(
            f"{context}:sequence:length {len(actual)} != pinned {len(expected)} "
            "(a toolbar item or separator was added or removed)"
        )
    for index, want in enumerate(expected):
        if index >= len(actual):
            break
        got = actual[index]
        want_sep = bool(want.get("separator")) if isinstance(want, dict) else False
        got_sep = bool(got.get("separator"))
        if want_sep or got_sep:
            if want_sep != got_sep:
                errors.append(
                    f"{context}:sequence[{index}]:composition drift: pinned "
                    f"{_entry_repr(want)} but found {_entry_repr(got)}"
                )
            continue
        if got.get("command") != want.get("command"):
            errors.append(
                f"{context}:sequence[{index}]:command drift: pinned {want.get('command')!r} "
                f"but found {got.get('command')!r} (identity/order changed)"
            )
        elif bool(got.get("visible")) != bool(want.get("visible")):
            errors.append(
                f"{context}:sequence[{index}]:visibility drift for {want.get('command')}: "
                f"pinned visible={want.get('visible')} but found visible={got.get('visible')}"
            )

    present = {e["command"] for e in actual if "command" in e and e["command"] is not None}
    visible = {e["command"] for e in actual if e.get("visible") and e.get("command")}

    core = declaration.get("design_core")
    if not isinstance(core, list) or not core:
        errors.append(f"{context}:design_core:non-empty array required")
    else:
        for command in core:
            if command not in present:
                errors.append(f"{context}:design_core:{command} absent from the toolbar")
            elif command not in visible:
                errors.append(
                    f"{context}:design_core:{command} present but hidden "
                    "(the design primary set must stay visible)"
                )

    preserved = declaration.get("preserved_commands")
    if not isinstance(preserved, list) or not preserved:
        errors.append(f"{context}:preserved_commands:non-empty array required")
    else:
        for command in preserved:
            if command not in present:
                errors.append(
                    f"{context}:preserved_commands:{command} removed "
                    "(expert commands must never be rebound or removed)"
                )


def _validate_menu(root: ET.Element, menu: Mapping[str, Any], errors: list[str]) -> None:
    actual = [c.get(f"{MENU_NS}id") for c in root if c.tag.endswith("}menu")]
    expected = menu.get("top_level")
    if not isinstance(expected, list) or not expected:
        errors.append("menu:top_level:non-empty array required")
    elif actual != expected:
        errors.append(
            f"menu:top_level:menu bar top-level sequence drift: pinned {expected} "
            f"but found {actual}"
        )
    core = menu.get("design_core")
    if isinstance(core, list):
        for menu_id in core:
            if menu_id not in actual:
                errors.append(f"menu:design_core:{menu_id} absent from the menu bar")


# --------------------------------------------------------------------------------------------------
# sidebar panel factory routes + panel .ui ids
# --------------------------------------------------------------------------------------------------
def _validate_factory(factory: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(factory, dict):
        errors.append("factory:object required")
        return
    source_rel = factory.get("source")
    source = contents.get(source_rel) if isinstance(source_rel, str) else None
    if source is None:
        errors.append(f"factory:source file missing: {source_rel}")
        return
    code = _without_cpp_comments(source)
    impl = factory.get("implementation_name")
    if not isinstance(impl, str) or not impl:
        errors.append("factory:implementation_name:non-empty string required")
    elif f'u"{impl}"_ustr' not in code:
        errors.append(
            f"factory:implementation_name {impl!r} missing in real code "
            "(chart sidebar panel factory registration drifted)"
        )
    routes = factory.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("factory:routes:non-empty array required")
        return
    seen: set[str] = set()
    for route in routes:
        if not isinstance(route, str) or not route:
            errors.append("factory:routes:entry must be a non-empty string")
            continue
        if route in seen:
            errors.append(f"factory:routes:{route} duplicate")
        seen.add(route)
        marker = f'rsResourceURL.endsWith("{route}")'
        if marker not in code:
            errors.append(
                f"factory:route {route!r} missing from real code in {source_rel} "
                "(a sidebar panel factory route was removed or renamed)"
            )


def _validate_sidebar_panels(panels: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(panels, list) or not panels:
        errors.append("sidebar_panels:non-empty array required")
        return
    seen: set[str] = set()
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            errors.append(f"sidebar_panels[{index}]:object required")
            continue
        file_rel = panel.get("file")
        root_id = panel.get("root_id")
        if not (isinstance(file_rel, str) and isinstance(root_id, str)):
            errors.append(f"sidebar_panels[{index}]:file/root_id must be strings")
            continue
        if root_id in seen:
            errors.append(f"sidebar_panels:{root_id} duplicate")
        seen.add(root_id)
        text = contents.get(file_rel)
        if text is None:
            errors.append(f"sidebar_panels:{file_rel} file missing")
            continue
        xml = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        if f'id="{root_id}"' not in xml:
            errors.append(
                f"sidebar_panels:{file_rel} no longer carries panel id \"{root_id}\" "
                "(the factory-routed panel root id drifted)"
            )


# --------------------------------------------------------------------------------------------------
# honest carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_carveouts(carveouts: Any, errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("carveouts:non-empty object required")
        return
    for name in ("chart_canvas", "live_preview", "data_table_grid", "scene_3d"):
        block = carveouts.get(name)
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' "
                "(custom-drawn / runtime chart surfaces are build-dependent; not promoted)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT_NAME:
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("inventory_row") != INVENTORY_ROW:
        errors.append("registry:inventory_row:must be WIN-CH-001")
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

    root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    chrome_parts = registry.get("chrome_parts")
    if isinstance(chrome_parts, dict):
        if root is not None:
            _validate_chrome_parts(root, chrome_parts, errors)
    else:
        errors.append("registry:chrome_parts:object required")

    toolbars = registry.get("toolbars")
    if not isinstance(toolbars, list) or not toolbars:
        errors.append("registry:toolbars:non-empty array required")
        toolbars = []
    seen_ids: set[str] = set()
    for index, toolbar in enumerate(toolbars):
        context = f"toolbars[{index}]"
        if not isinstance(toolbar, dict):
            errors.append(f"{context}:object required")
            continue
        toolbar_id = toolbar.get("id")
        if not isinstance(toolbar_id, str) or not toolbar_id:
            errors.append(f"{context}:id:non-empty string required")
            continue
        context = f"toolbar[{toolbar_id}]"
        if toolbar_id in seen_ids:
            errors.append(f"{context}:id:duplicate")
        seen_ids.add(toolbar_id)
        file_path = toolbar.get("file")
        if not isinstance(file_path, str):
            errors.append(f"{context}:file:string required")
            continue
        tb_root = _parse_xml(contents.get(file_path), context, errors)
        if tb_root is not None:
            _validate_toolbar(context, tb_root, toolbar, errors)

    menu = registry.get("menu")
    if isinstance(menu, dict):
        menu_file = menu.get("file")
        menu_root = _parse_xml(
            contents.get(menu_file) if isinstance(menu_file, str) else None, "menu", errors
        )
        if menu_root is not None:
            _validate_menu(menu_root, menu, errors)
    else:
        errors.append("registry:menu:object required")

    _validate_factory(registry.get("factory"), contents, errors)
    _validate_sidebar_panels(registry.get("sidebar_panels"), contents, errors)
    _validate_carveouts(registry.get("carveouts"), errors)

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
        print(f"Chart editor composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Chart editor composition contract passed: pinned the chart in-place toolbar + 8 top-level "
        f"menu composition, the {len(registry['factory']['routes'])} sidebar factory routes and "
        f"{len(registry['sidebar_panels'])} panel .ui ids, grounded in the native toolbar "
        "band/separator/nine-state Button parts at @corner-toolbar (light+dark), with the chart "
        "canvas / live-preview / data-table / 3D-scene carved out spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
