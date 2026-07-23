#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material template-manager dialogs (WIN-SYS-004).

``qa/windows-ui-contract/template-manager.json`` pins the composition of the three upstream
template-manager dialog roots -- ``TemplateDialog`` (sfx2/uiconfig/ui/templatedlg.ui),
``SaveAsTemplateDialog`` (saveastemplatedlg.ui) and ``TemplatesCategoryDialog``
(templatecategorydlg.ui) -- from docs/design/08-dialogs.md 8.1. Their Material treatment is
delivered entirely by shared vcl parts consumed through the ``VCL_FILE_WIDGET_THEME`` builder, so
the M-scope of this row is *pinning composition* -- footer action-widget order + response codes,
the has-default primary, and the required control set -- and grounding it in the native part
contract, never re-drawing controls. This checker parses the real tree fail-closed:

* ``dialog_parts`` -- the native ``windowbackground``/``pushbutton``/``checkbox``/``combobox``/
  ``frame``/``listbox`` parts every template dialog control resolves through must exist in
  vcl/uiconfig/theme_definitions/material/definition.xml with the exact
  fill / stroke / stroke-width / radius tokens per state, every declared metric must carry its
  exact value, and every palette role the states reference must resolve in *both* the light and
  dark palettes. A renamed part, dropped state, or token drift fails closed. The definition file is
  read only, never mutated.
* ``dialogs`` -- each ``.ui`` root's ``<action-widgets>`` order + response codes must match the
  pinned footer exactly, the pinned primary must carry ``has-default``, every ``required_widget``
  must be present by id + class, and any runtime-set primary label (the OK button label
  ``SfxTemplateManagerDlg``/``SfxSaveAsTemplateDialog`` set in the ``.cxx``, not the ``.ui``) must
  still be referenced in the owning source. A reordered/dropped button, flipped response, removed
  default, renamed widget, or dropped label fails closed.
* ``regex_search`` -- the already-source-integrated Template Manager search field and its adjacent
  regex builder (owned by regex-search-integrations.json) must remain present and adjacent in the
  ``.ui``; this contract pins the adjacency so a re-composition cannot silently drop it, and never
  re-registers the field.
* ``carveouts`` -- pixel geometry, the thumbnail/list card anatomy, density and RTL are
  build-dependent and must stay ``status: specified``, never promoted to an implemented claim.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, dialog
pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/template-manager.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CONTRACT_NAME = "material-template-manager-composition"

# definition.xml <state> attribute keys, so a declared attrs signature is validated as a complete,
# exact match (no partial match that could alias two states).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)

# The palettes whose color roles must all resolve (light = no scheme attribute).
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {registry.get("definition_file", DEFINITION_PATH)}
    for dialog in registry.get("dialogs", []) or []:
        if not isinstance(dialog, dict):
            continue
        if isinstance(dialog.get("ui_file"), str):
            paths.add(dialog["ui_file"])
        label = dialog.get("primary_label")
        if isinstance(label, dict) and isinstance(label.get("source"), str):
            paths.add(label["source"])
    regex = registry.get("regex_search")
    if isinstance(regex, dict) and isinstance(regex.get("ui_file"), str):
        paths.add(regex["ui_file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals.

    Anchoring on the result guarantees the contract binds to real code, never to a marker that
    merely appears in a comment.
    """

    out: list[str] = []
    i, n = 0, len(text)
    state = "code"
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
# definition.xml part cross-checks
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
    root: ET.Element, name: str, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    control = declaration.get("control")
    part_name = declaration.get("part")
    if not isinstance(control, str) or not isinstance(part_name, str):
        errors.append(f"dialog_parts:{name}:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"dialog_parts:{name}:{control}/{part_name} missing in definition.xml")
        return
    states = declaration.get("states")
    if not isinstance(states, list) or not states:
        errors.append(f"dialog_parts:{name}:{control}/{part_name}:states non-empty array required")
        return
    for state_decl in states:
        if not isinstance(state_decl, dict):
            errors.append(f"dialog_parts:{name}:{control}/{part_name}:state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"dialog_parts:{name}:{control}/{part_name}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(
                f"dialog_parts:{name}:{control}/{part_name}:{role} no <state> matching {attrs}"
            )
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(
                f"dialog_parts:{name}:{control}/{part_name}:{role} state has no rect/line"
            )
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"dialog_parts:{name}:{control}/{part_name}:{role} element is <{drawing.tag}>, "
                f"expected <{expected_element}>"
            )
        tokens = state_decl.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append(f"dialog_parts:{name}:{control}/{part_name}:{role} tokens must be object")
            continue
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"dialog_parts:{name}:{control}/{part_name}:{role} token drift: {token_key} is "
                    f"{actual!r}, expected {expected!r}"
                )


def _validate_dialog_parts(root: ET.Element, parts: Mapping[str, Any], errors: list[str]) -> None:
    declared = parts.get("parts")
    if not isinstance(declared, dict) or not declared:
        errors.append("dialog_parts:parts:non-empty object required")
    else:
        for name, declaration in declared.items():
            if isinstance(declaration, dict):
                _validate_part(root, name, declaration, errors)
            else:
                errors.append(f"dialog_parts:{name}:object required")

    for metric in parts.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("dialog_parts:metric:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("dialog_parts:metric:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"dialog_parts:metric:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(
                f"dialog_parts:metric:{mname} is {actual!r}, expected {expected!r} (metric drift)"
            )

    palette = parts.get("palette_colors")
    if not isinstance(palette, list) or not palette:
        errors.append("dialog_parts:palette_colors:non-empty array required")
    else:
        for role in palette:
            if not isinstance(role, str):
                continue
            for scheme in REQUIRED_SCHEMES:
                if _palette_color(root, scheme, role) is None:
                    label = scheme or "light"
                    errors.append(f"dialog_parts:palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# .ui composition
# --------------------------------------------------------------------------------------------------
def _find_object(root: ET.Element, object_id: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == object_id:
            return obj
    return None


def _object_by_id_class(root: ET.Element, object_id: str, cls: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == object_id and obj.get("class") == cls:
            return obj
    return None


def _bool_property(obj: ET.Element, name: str) -> bool:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return (prop.text or "").strip().lower() == "true"
    return False


def _action_widgets(dialog: ET.Element) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for widgets in dialog.iter("action-widgets"):
        for aw in widgets.findall("action-widget"):
            result.append(((aw.text or "").strip(), aw.get("response", "")))
    return result


def _direct_child_object_ids(obj: ET.Element) -> list[str]:
    ids: list[str] = []
    for child in obj.findall("child"):
        inner = child.find("object")
        if inner is not None and inner.get("id"):
            ids.append(inner.get("id"))
    return ids


def _validate_dialog(context: str, root: ET.Element, dialog: Mapping[str, Any], errors: list[str]) -> None:
    dialog_id = dialog.get("id")
    obj = _find_object(root, dialog_id) if isinstance(dialog_id, str) else None
    if obj is None:
        errors.append(f"{context}:root object {dialog_id!r} missing from .ui")
        return

    expected = dialog.get("action_widgets")
    if not isinstance(expected, list) or not expected:
        errors.append(f"{context}:action_widgets:non-empty array required")
    else:
        actual = _action_widgets(obj)
        want = [(str(e.get("id")), str(e.get("response"))) for e in expected if isinstance(e, dict)]
        if actual != want:
            errors.append(
                f"{context}:action_widgets:footer composition drift: pinned {want} but found {actual}"
            )

    primary = dialog.get("primary")
    if isinstance(primary, str):
        button = _find_object(root, primary)
        if button is None:
            errors.append(f"{context}:primary:{primary} missing from .ui")
        elif not _bool_property(button, "has-default"):
            errors.append(
                f"{context}:primary:{primary} must carry has-default "
                "(the primary is the Enter default)"
            )

    for widget in dialog.get("required_widgets", []) or []:
        if not isinstance(widget, dict):
            errors.append(f"{context}:required_widget:object required")
            continue
        wid = widget.get("id")
        wcls = widget.get("class")
        if not (isinstance(wid, str) and isinstance(wcls, str)):
            errors.append(f"{context}:required_widget:id/class must be strings")
            continue
        if _object_by_id_class(root, wid, wcls) is None:
            errors.append(f"{context}:required_widget:{wid} ({wcls}) missing from .ui")


def _validate_primary_label(context: str, source_text: str | None, label: Mapping[str, Any], errors: list[str]) -> None:
    marker = label.get("marker")
    if not isinstance(marker, str) or not marker:
        errors.append(f"{context}:primary_label:marker must be a non-empty string")
        return
    if source_text is None:
        errors.append(f"{context}:primary_label:source file missing")
        return
    if marker not in _strip_comments(source_text):
        errors.append(
            f"{context}:primary_label:runtime-set label marker {marker!r} absent from source "
            "(the .cxx must still set the primary label)"
        )


def _validate_regex_search(root: ET.Element, regex: Mapping[str, Any], errors: list[str]) -> None:
    if regex.get("status") != "implemented-elsewhere":
        errors.append("regex_search:status:must stay 'implemented-elsewhere' (owned elsewhere, never re-added)")
    field = regex.get("field")
    builder = regex.get("builder")
    if not (isinstance(field, str) and isinstance(builder, str)):
        errors.append("regex_search:field/builder must be strings")
        return
    if _find_object(root, field) is None:
        errors.append(f"regex_search:field:{field} missing from .ui")
    if _find_object(root, builder) is None:
        errors.append(f"regex_search:builder:{builder} missing from .ui")
    # The builder must sit immediately after the field within a shared parent (the adjacency the
    # RegexSearchController pin depends on).
    adjacent = False
    for obj in root.iter("object"):
        ids = _direct_child_object_ids(obj)
        if field in ids and builder in ids and ids.index(builder) == ids.index(field) + 1:
            adjacent = True
            break
    if not adjacent:
        errors.append(
            f"regex_search:adjacency:{builder} must immediately follow {field} in the .ui "
            "(regex builder adjacency broken)"
        )


def _validate_carveouts(carveouts: Mapping[str, Any], errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("registry:carveouts:non-empty object required")
        return
    for name, block in carveouts.items():
        if not isinstance(block, dict) or block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status:must stay 'specified' "
                "(pixel geometry / thumbnail card / density / RTL are build-dependent "
                "and must not be promoted to an implemented claim)"
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
    definition_path = registry.get("definition_file")
    if definition_path != DEFINITION_PATH:
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

    dialog_parts = registry.get("dialog_parts")
    if isinstance(dialog_parts, dict):
        if root is not None:
            _validate_dialog_parts(root, dialog_parts, errors)
    else:
        errors.append("registry:dialog_parts:object required")

    dialogs = registry.get("dialogs")
    if not isinstance(dialogs, list) or not dialogs:
        errors.append("registry:dialogs:non-empty array required")
        dialogs = []
    seen_ids: set[str] = set()
    for index, dialog in enumerate(dialogs):
        if not isinstance(dialog, dict):
            errors.append(f"dialogs[{index}]:object required")
            continue
        dialog_id = dialog.get("id")
        context = f"dialog[{dialog_id}]" if isinstance(dialog_id, str) else f"dialogs[{index}]"
        if isinstance(dialog_id, str):
            if dialog_id in seen_ids:
                errors.append(f"{context}:id:duplicate")
            seen_ids.add(dialog_id)
        ui_file = dialog.get("ui_file")
        ui_root = _parse_xml(contents.get(ui_file) if isinstance(ui_file, str) else None, context, errors)
        if ui_root is not None:
            _validate_dialog(context, ui_root, dialog, errors)
        label = dialog.get("primary_label")
        if isinstance(label, dict):
            source = label.get("source")
            _validate_primary_label(
                context, contents.get(source) if isinstance(source, str) else None, label, errors
            )

    regex = registry.get("regex_search")
    if isinstance(regex, dict):
        ui_file = regex.get("ui_file")
        regex_root = _parse_xml(contents.get(ui_file) if isinstance(ui_file, str) else None, "regex_search", errors)
        if regex_root is not None:
            _validate_regex_search(regex_root, regex, errors)
    else:
        errors.append("registry:regex_search:object required")

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
        print(f"Template manager composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Template manager composition contract passed: "
        f"{len(registry['dialogs'])} pinned dialog root(s), the native "
        "windowbackground/pushbutton/checkbox/combobox/frame/listbox parts in both palettes, the "
        "regex-search adjacency preserved, with pixel geometry/thumbnail card/density/RTL carved "
        "out spec-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
