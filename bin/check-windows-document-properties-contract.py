#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material Document Properties dialog (WIN-SYS-003).

``qa/windows-ui-contract/document-properties.json`` pins the DIALOG-notebook
composition of the sfx2 ``SfxDocumentInfoDialog`` (documentpropertiesdialog.ui +
dinfdlg.cxx). This is a deliberately distinct scope from calc-sheet-tabs, which
pins the Calc sheet-strip ``tabitem``: dinfdlg.cxx carries no Material paint
override (contrast ``ScTabControl::Paint``), so the entire Material look is
delivered by the shared vcl parts plus the weld/``SfxTabDialogController``
framework. The M-scope of this row is therefore *pinning composition*, never
re-drawing controls. This checker parses the real tree fail-closed and
cross-validates every declaration:

* ``definition_parts`` -- the native left-icon-tab parts the notebook resolves
  through (the full 8-state ``tabitem``/Entire, ``tabheader``/``tabpane``/
  ``tabbody``, ``windowbackground``/BackgroundDialog, the footer ``pushbutton``
  states, and ``frame``/Border) must exist in
  vcl/uiconfig/theme_definitions/material/definition.xml with the exact
  fill / stroke / stroke-width / radius tokens per ``<state>``. A renamed part,
  dropped state or token drift fails closed. The definition file is read only.
* ``tab_style`` / ``tab_settings`` -- the tab colour routing
  (activeTabColor / inactiveTabColor / tabTextColor / tabRolloverTextColor /
  tabHighlightTextColor) and the tab layout switches (noActiveTabTextRaise,
  centeredTabs) must carry the pinned values.
* ``metrics`` -- corner-pill / corner-container / height-tab / space-tab-inline
  must carry their exact values, and every referenced palette role must resolve
  in *both* the light and dark palettes.
* ``dialog_composition`` -- documentpropertiesdialog.ui must be a modal
  ``GtkDialog`` whose ``tabcontrol`` ``GtkNotebook`` is a left icon rail
  (tab-pos=left, group-name=icons) and whose footer action-widget order and
  help-secondary flag match the pinned sequence exactly.
* ``tab_pages`` -- the ordered ``AddTabPage`` page set (with the RID_L 32px
  icon-rail identity and each ``SfxTabPage`` .ui root) must exist as real
  (comment-stripped) source, and every pinned page .ui must declare its root
  object id. Conditional pages (cmisprops, security) are marked optional.
* ``carveouts`` -- honest guards: STR_SFX_QUERY_WRONG_TYPE stays a
  non-destructive query (present in source, never promoted to a destructive
  confirmation) and the deferred surfaces stay ``status: specified``.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, tab-rail pixels or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/document-properties.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# definition.xml <state> attribute keys, so a declared attrs signature is validated
# as a complete, exact match (no partial match that could alias two states).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)

# The palettes whose colour roles must all resolve (light = no scheme attribute).
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _registry_paths(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = {DEFINITION_PATH}
    composition = registry.get("dialog_composition")
    if isinstance(composition, dict) and isinstance(composition.get("ui_file"), str):
        paths.add(composition["ui_file"])
    source = registry.get("tab_page_source")
    if isinstance(source, dict) and isinstance(source.get("file"), str):
        paths.add(source["file"])
    icon = registry.get("icon_rail_source")
    if isinstance(icon, dict) and isinstance(icon.get("file"), str):
        paths.add(icon["file"])
    for page in registry.get("tab_pages", []) or []:
        if not isinstance(page, dict):
            continue
        for key in ("add_source", "bind_source", "page_ui"):
            value = page.get(key)
            if isinstance(value, str):
                paths.add(value)
    carveouts = registry.get("carveouts")
    if isinstance(carveouts, dict):
        for block in carveouts.values():
            if isinstance(block, dict) and isinstance(block.get("source"), str):
                paths.add(block["source"])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _registry_paths(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# C/C++ comment stripping (anchor on real code, never a comment)
# --------------------------------------------------------------------------------------------------
def _strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    state = "code"  # code | line | block | quote
    quote = ""
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if c in ('"', "'"):
                state = "quote"
                quote = c
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        if state == "line":
            if c == "\n":
                state = "code"
                out.append(c)
            i += 1
            continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
            if c == "\n":
                out.append("\n")
            i += 1
            continue
        # state == "quote"
        out.append(c)
        if c == "\\":
            if i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue
        if c == quote:
            state = "code"
        i += 1
    return "".join(out)


# --------------------------------------------------------------------------------------------------
# definition.xml lookups (native part cross-checks)
# --------------------------------------------------------------------------------------------------
def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


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


def _child_value(root: ET.Element, container: str, name: str) -> str | None:
    holder = root.find(container)
    if holder is None:
        return None
    element = holder.find(name)
    if element is None:
        return None
    return element.get("value")


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


def _validate_part(
    root: ET.Element, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    control = declaration.get("control")
    part_name = declaration.get("part")
    if not isinstance(control, str) or not isinstance(part_name, str):
        errors.append("definition_parts:entry:control/part must be strings")
        return
    label = f"definition_parts:{control}/{part_name}"
    if root.find(control) is None:
        errors.append(f"{label}:<{control}> missing in definition.xml")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"{label}:part missing in definition.xml")
        return

    part_attrs = declaration.get("part_attrs")
    if isinstance(part_attrs, dict):
        for attr_key, expected in part_attrs.items():
            actual = part.get(attr_key)
            if actual != expected:
                errors.append(
                    f"{label}:part attribute drift: {attr_key} is {actual!r}, expected {expected!r}"
                )

    states = declaration.get("states")
    if not isinstance(states, list) or not states:
        errors.append(f"{label}:states non-empty array required")
        return
    for state_decl in states:
        if not isinstance(state_decl, dict):
            errors.append(f"{label}:state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"{label}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(f"{label}:{role} no <state> matching {attrs}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"{label}:{role} state has no rect/line")
            continue
        expected_element = state_decl.get("element", "rect")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"{label}:{role} element is <{drawing.tag}>, expected <{expected_element}>"
            )
        tokens = state_decl.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append(f"{label}:{role} tokens must be object")
            continue
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"{label}:{role} token drift: {token_key} is {actual!r}, expected {expected!r}"
                )


def _validate_definition(root: ET.Element, registry: Mapping[str, Any], errors: list[str]) -> None:
    parts = registry.get("definition_parts")
    if not isinstance(parts, list) or not parts:
        errors.append("registry:definition_parts:non-empty array required")
    else:
        for declaration in parts:
            if isinstance(declaration, dict):
                _validate_part(root, declaration, errors)
            else:
                errors.append("definition_parts:entry:object required")

    tab_style = registry.get("tab_style")
    if not isinstance(tab_style, dict) or not tab_style:
        errors.append("registry:tab_style:non-empty object required")
    else:
        for name, expected in tab_style.items():
            actual = _child_value(root, "style", name)
            if actual is None:
                errors.append(f"tab_style:{name} missing in definition.xml <style>")
            elif actual != expected:
                errors.append(f"tab_style:{name} is {actual!r}, expected {expected!r} (drift)")

    tab_settings = registry.get("tab_settings")
    if not isinstance(tab_settings, dict) or not tab_settings:
        errors.append("registry:tab_settings:non-empty object required")
    else:
        for name, expected in tab_settings.items():
            actual = _child_value(root, "settings", name)
            if actual is None:
                errors.append(f"tab_settings:{name} missing in definition.xml <settings>")
            elif actual != expected:
                errors.append(f"tab_settings:{name} is {actual!r}, expected {expected!r} (drift)")

    for metric in registry.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("metrics:entry:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("metrics:entry:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"metrics:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(f"metrics:{mname} is {actual!r}, expected {expected!r} (metric drift)")

    for role in registry.get("palette_colors", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                where = scheme or "light"
                errors.append(f"palette:@{role} missing from the {where} palette")


# --------------------------------------------------------------------------------------------------
# documentpropertiesdialog.ui composition (no namespace: plain GtkBuilder)
# --------------------------------------------------------------------------------------------------
def _find_object(root: ET.Element, object_id: str) -> ET.Element | None:
    for node in root.iter("object"):
        if node.get("id") == object_id:
            return node
    return None


def _ui_footer(root: ET.Element) -> list[dict[str, str]]:
    footer: list[dict[str, str]] = []
    for action_widgets in root.iter("action-widgets"):
        for widget in action_widgets.findall("action-widget"):
            footer.append(
                {"response": (widget.get("response") or ""), "widget": (widget.text or "").strip()}
            )
    return footer


def _ui_secondary_widgets(root: ET.Element) -> set[str]:
    """Widget ids whose enclosing <child> packing marks secondary=True."""

    secondary: set[str] = set()
    for child in root.iter("child"):
        obj = child.find("object")
        packing = child.find("packing")
        if obj is None or packing is None:
            continue
        widget_id = obj.get("id")
        if not widget_id:
            continue
        for prop in packing.findall("property"):
            if prop.get("name") == "secondary" and (prop.text or "").strip().lower() == "true":
                secondary.add(widget_id)
    return secondary


def _validate_dialog_composition(
    root: ET.Element, composition: Mapping[str, Any], errors: list[str]
) -> None:
    dialog_id = composition.get("dialog_object")
    dialog = _find_object(root, dialog_id) if isinstance(dialog_id, str) else None
    if dialog is None:
        errors.append(f"dialog_composition:root object {dialog_id!r} missing")
        return
    if dialog.get("class") != "GtkDialog":
        errors.append(f"dialog_composition:{dialog_id} is not a GtkDialog")

    modal = None
    for prop in dialog.findall("property"):
        if prop.get("name") == "modal":
            modal = (prop.text or "").strip().lower() == "true"
    if composition.get("modal") is True and modal is not True:
        errors.append("dialog_composition:dialog must declare modal=True")

    notebook_decl = composition.get("notebook")
    if not isinstance(notebook_decl, dict):
        errors.append("dialog_composition:notebook object required")
    else:
        notebook = _find_object(root, notebook_decl.get("id"))
        if notebook is None or notebook.get("class") != "GtkNotebook":
            errors.append(
                f"dialog_composition:notebook {notebook_decl.get('id')!r} GtkNotebook missing"
            )
        else:
            props = {
                p.get("name"): (p.text or "").strip()
                for p in notebook.findall("property")
            }
            if props.get("tab-pos") != notebook_decl.get("tab_pos"):
                errors.append(
                    "dialog_composition:notebook tab-pos is "
                    f"{props.get('tab-pos')!r}, expected {notebook_decl.get('tab_pos')!r} "
                    "(the left icon rail must be preserved)"
                )
            if props.get("group-name") != notebook_decl.get("group_name"):
                errors.append(
                    "dialog_composition:notebook group-name is "
                    f"{props.get('group-name')!r}, expected {notebook_decl.get('group_name')!r}"
                )

    expected_footer = composition.get("footer")
    if not isinstance(expected_footer, list) or not expected_footer:
        errors.append("dialog_composition:footer non-empty array required")
        return
    actual_footer = _ui_footer(root)
    secondary = _ui_secondary_widgets(root)
    if len(actual_footer) != len(expected_footer):
        errors.append(
            f"dialog_composition:footer length {len(actual_footer)} != pinned "
            f"{len(expected_footer)} (an action-widget was added or removed)"
        )
    for index, want in enumerate(expected_footer):
        if index >= len(actual_footer):
            break
        got = actual_footer[index]
        if got.get("response") != want.get("response") or got.get("widget") != want.get("widget"):
            errors.append(
                f"dialog_composition:footer[{index}] drift: pinned "
                f"{want.get('widget')}({want.get('response')}) but found "
                f"{got.get('widget')}({got.get('response')})"
            )
            continue
        want_secondary = bool(want.get("secondary"))
        got_secondary = want.get("widget") in secondary
        if want_secondary != got_secondary:
            errors.append(
                f"dialog_composition:footer[{index}] {want.get('widget')} secondary flag is "
                f"{got_secondary}, expected {want_secondary}"
            )


# --------------------------------------------------------------------------------------------------
# Programmatic page set (dinfdlg.cxx / securitypage.cxx / documentfontsdialog.cxx)
# --------------------------------------------------------------------------------------------------
def _require(code: str | None, marker: str, where: str, errors: list[str]) -> None:
    if code is None:
        errors.append(f"{where}:source file missing")
        return
    if marker not in code:
        errors.append(f"{where}:missing real code marker {marker!r}")


def _validate_tab_pages(registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]) -> None:
    stripped: dict[str, str] = {}

    def code(rel: str | None) -> str | None:
        if not isinstance(rel, str):
            return None
        if rel not in stripped:
            text = contents.get(rel)
            stripped[rel] = _strip_comments(text) if text is not None else None
        return stripped[rel]

    source = registry.get("tab_page_source")
    if not isinstance(source, dict):
        errors.append("registry:tab_page_source:object required")
    else:
        controller_bind = source.get("controller_bind")
        if isinstance(controller_bind, str):
            _require(code(source.get("file")), controller_bind,
                     "tab_page_source:controller_bind", errors)
        else:
            errors.append("tab_page_source:controller_bind string required")

    icon = registry.get("icon_rail_source")
    if not isinstance(icon, dict):
        errors.append("registry:icon_rail_source:object required")
    else:
        marker = icon.get("marker")
        if isinstance(marker, str):
            _require(code(icon.get("file")), marker, "icon_rail_source", errors)
        else:
            errors.append("icon_rail_source:marker string required")

    pages = registry.get("tab_pages")
    if not isinstance(pages, list) or not pages:
        errors.append("registry:tab_pages:non-empty array required")
        return
    seen: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            errors.append("tab_pages:entry:object required")
            continue
        page_id = page.get("id")
        if not isinstance(page_id, str) or not page_id:
            errors.append("tab_pages:entry:id string required")
            continue
        where = f"tab_pages[{page_id}]"
        if page_id in seen:
            errors.append(f"{where}:duplicate page id")
        seen.add(page_id)

        for field in ("add_marker", "icon_marker"):
            marker = page.get(field)
            if isinstance(marker, str):
                _require(code(page.get("add_source")), marker, f"{where}:{field}", errors)
            else:
                errors.append(f"{where}:{field} string required")

        bind_marker = page.get("bind_marker")
        if isinstance(bind_marker, str):
            _require(code(page.get("bind_source")), bind_marker, f"{where}:bind_marker", errors)
        else:
            errors.append(f"{where}:bind_marker string required")

        # The page .ui must exist and declare its pinned root object id.
        page_ui = page.get("page_ui")
        root_id = page.get("page_root_id")
        page_text = contents.get(page_ui) if isinstance(page_ui, str) else None
        page_root = _parse_xml(page_text, f"{where}:page_ui", errors)
        if page_root is not None:
            if not isinstance(root_id, str) or _find_object(page_root, root_id) is None:
                errors.append(f"{where}:page root object {root_id!r} missing in {page_ui}")


# --------------------------------------------------------------------------------------------------
# Carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_carveouts(registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]) -> None:
    carveouts = registry.get("carveouts")
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("registry:carveouts:non-empty object required")
        return
    for name, block in carveouts.items():
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' "
                "(deferred/non-destructive carve-outs must never be promoted to an implemented claim)"
            )
        marker = block.get("marker")
        if isinstance(marker, str):
            text = contents.get(block.get("source"))
            code = _strip_comments(text) if text is not None else None
            _require(code, marker, f"carveouts:{name}", errors)


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-document-properties-composition":
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

    root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    if root is not None:
        _validate_definition(root, registry, errors)

    composition = registry.get("dialog_composition")
    if isinstance(composition, dict):
        ui_file = composition.get("ui_file")
        ui_root = _parse_xml(
            contents.get(ui_file) if isinstance(ui_file, str) else None,
            "dialog_composition:ui", errors,
        )
        if ui_root is not None:
            _validate_dialog_composition(ui_root, composition, errors)
    else:
        errors.append("registry:dialog_composition:object required")

    _validate_tab_pages(registry, contents, errors)
    _validate_carveouts(registry, contents, errors)
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
        print(f"Document Properties composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    pages = registry.get("tab_pages", [])
    optional = sum(1 for p in pages if isinstance(p, dict) and p.get("optional"))
    print(
        "Document Properties composition contract passed: "
        f"the modal SfxDocumentInfoDialog with its left icon-rail tabcontrol notebook, "
        f"{len(pages)} pinned page(s) ({optional} conditional) over the RID_L 32px rail, the "
        "8-state tabitem / tabheader / tabpane / tabbody / pushbutton / frame parts and the tab "
        "style+settings block, with STR_SFX_QUERY_WRONG_TYPE carved out non-destructive."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
