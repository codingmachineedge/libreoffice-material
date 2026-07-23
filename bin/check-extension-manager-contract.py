#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material extension-manager dialogs (WIN-SYS-005).

``qa/windows-ui-contract/extension-manager.json`` pins the composition of the nine upstream
extension-manager + dependency dialog roots in desktop/uiconfig/ui/ (ExtensionManagerDialog,
Dependencies, UpdateDialog, UpdateInstallDialog, UpdateRequiredDialog, InstallForAllDialog,
LicenseDialog, ShowLicenseDialog, and the extension menu). They are data-driven GtkDialog /
GtkMessageDialog / GtkMenu XML assembled from shared vcl/weld primitives that already carry the
Material treatment behind ``VCL_FILE_WIDGET_THEME``, so the M-scope of this row is *pinning
composition* -- modal footer action-widget order + response codes, command button-box
identity/order/secondary/default flags, and the informational-vs-decision shape of each root -- and
grounding it in the native part contract, never re-drawing controls. This checker parses the real
tree fail-closed:

* ``dialog_parts`` -- the native ``windowbackground``/``pushbutton``/``checkbox``/``editbox``/
  ``progress``/``frame``/``listnode`` parts every extension dialog control resolves through must
  exist in vcl/uiconfig/theme_definitions/material/definition.xml with the exact tokens per state,
  every declared metric must carry its exact value, and every palette role must resolve in *both*
  the light and dark palettes. The definition file is read only, never mutated.
* ``dialogs`` -- each ``.ui`` root's ``<action-widgets>`` order + response codes must match the
  pinned footer exactly, the pinned primary must carry ``has-default``, and every declared command
  button must be present with its pinned label / secondary flag / default flag. A reordered or
  dropped button, a flipped response, a changed secondary flag, or an informational root gaining a
  second decision button fails closed.
* ``menus`` -- the extension context menu root must remain a ``GtkMenu``.
* ``modal_policy`` -- a READ-ONLY reconciliation against dialog-notification-policy.csv: every
  declared root must keep ``policy = native-exclusion`` (KeepModal). A root demoted to the transient
  bottom-right notification stack (a consent/data-loss guard) fails closed. The CSV is never
  rewritten -- it is owned by check-windows-dialog-notification-contract.py.
* ``regex_search`` -- the already-source-integrated Extension Manager search field and its adjacent
  regex builder (owned by regex-search-integrations.json) must remain present and adjacent; pinned,
  never re-registered.
* ``carveouts`` -- pixel geometry, the custom-drawn list-item Paint, density and RTL are
  build-dependent and must stay ``status: specified``.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, dialog
pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/extension-manager.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
POLICY_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"
CONTRACT_NAME = "material-extension-manager-composition"

STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)
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
    paths.add(registry.get("policy_file", POLICY_PATH))
    for dialog in registry.get("dialogs", []) or []:
        if isinstance(dialog, dict) and isinstance(dialog.get("ui_file"), str):
            paths.add(dialog["ui_file"])
    for menu in registry.get("menus", []) or []:
        if isinstance(menu, dict) and isinstance(menu.get("ui_file"), str):
            paths.add(menu["ui_file"])
    regex = registry.get("regex_search")
    if isinstance(regex, dict) and isinstance(regex.get("ui_file"), str):
        paths.add(regex["ui_file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _clean_label(raw: str) -> str:
    return raw.replace("_", "").replace("&", "").replace("~", "").strip().strip("._ ").lower()


# --------------------------------------------------------------------------------------------------
# definition.xml part cross-checks (shared shape with the template-manager contract)
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


def _bool_property(obj: ET.Element, name: str) -> bool:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return (prop.text or "").strip().lower() == "true"
    return False


def _label_property(obj: ET.Element) -> str:
    for prop in obj.findall("property"):
        if prop.get("name") == "label":
            return prop.text or ""
    return ""


def _action_widgets(dialog: ET.Element) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for widgets in dialog.iter("action-widgets"):
        for aw in widgets.findall("action-widget"):
            result.append(((aw.text or "").strip(), aw.get("response", "")))
    return result


def _child_wrapper_of(root: ET.Element, object_id: str) -> ET.Element | None:
    for child in root.iter("child"):
        inner = child.find("object")
        if inner is not None and inner.get("id") == object_id:
            return child
    return None


def _packing_bool(child: ET.Element, name: str) -> bool:
    packing = child.find("packing")
    if packing is None:
        return False
    for prop in packing.findall("property"):
        if prop.get("name") == name:
            return (prop.text or "").strip().lower() == "true"
    return False


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
                f"{context}:primary:{primary} must carry has-default (the primary is the Enter default)"
            )

    for spec in dialog.get("buttons", []) or []:
        if not isinstance(spec, dict):
            errors.append(f"{context}:button:object required")
            continue
        bid = spec.get("id")
        if not isinstance(bid, str):
            errors.append(f"{context}:button:id must be a string")
            continue
        button = _find_object(root, bid)
        if button is None:
            errors.append(f"{context}:button:{bid} missing from .ui")
            continue
        expected_label = spec.get("label")
        if isinstance(expected_label, str):
            if _clean_label(_label_property(button)) != _clean_label(expected_label):
                errors.append(
                    f"{context}:button:{bid} label drift: pinned {expected_label!r} but found "
                    f"{_label_property(button)!r}"
                )
        if "secondary" in spec:
            wrapper = _child_wrapper_of(root, bid)
            actual_secondary = _packing_bool(wrapper, "secondary") if wrapper is not None else False
            if actual_secondary != bool(spec.get("secondary")):
                errors.append(
                    f"{context}:button:{bid} secondary flag drift: pinned {bool(spec.get('secondary'))} "
                    f"but found {actual_secondary}"
                )
        if spec.get("has_default") and not _bool_property(button, "has-default"):
            errors.append(f"{context}:button:{bid} must carry has-default")


def _validate_menu(context: str, root: ET.Element, menu: Mapping[str, Any], errors: list[str]) -> None:
    menu_id = menu.get("id")
    expected_class = menu.get("class", "GtkMenu")
    obj = _find_object(root, menu_id) if isinstance(menu_id, str) else None
    if obj is None:
        errors.append(f"{context}:menu object {menu_id!r} missing from .ui")
    elif obj.get("class") != expected_class:
        errors.append(
            f"{context}:menu {menu_id} class is {obj.get('class')!r}, expected {expected_class!r}"
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


# --------------------------------------------------------------------------------------------------
# dialog-notification-policy.csv reconciliation (read only)
# --------------------------------------------------------------------------------------------------
def _validate_modal_policy(
    policy_text: str | None, policy: Mapping[str, Any], errors: list[str]
) -> None:
    if policy_text is None:
        errors.append("modal_policy:policy file missing")
        return
    required_policy = policy.get("required_policy", "native-exclusion")
    index: dict[tuple[str, str], str] = {}
    reader = csv.DictReader(io.StringIO(policy_text))
    for row in reader:
        key = ((row.get("ui_path") or "").strip(), (row.get("object_id") or "").strip())
        index[key] = (row.get("policy") or "").strip()
    for root in policy.get("roots", []) or []:
        if not isinstance(root, dict):
            errors.append("modal_policy:root:object required")
            continue
        ui_path = root.get("ui_path")
        object_id = root.get("object_id")
        if not (isinstance(ui_path, str) and isinstance(object_id, str)):
            errors.append("modal_policy:root:ui_path/object_id must be strings")
            continue
        actual = index.get((ui_path, object_id))
        if actual is None:
            errors.append(
                f"modal_policy:{object_id}:no row in dialog-notification-policy.csv for {ui_path}"
            )
        elif actual != required_policy:
            errors.append(
                f"modal_policy:{object_id}:policy is {actual!r}, must stay {required_policy!r} "
                "(KeepModal; a consent/decision dialog must not be routed to the notification stack)"
            )


def _validate_carveouts(carveouts: Mapping[str, Any], errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("registry:carveouts:non-empty object required")
        return
    for name, block in carveouts.items():
        if not isinstance(block, dict) or block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status:must stay 'specified' "
                "(pixel geometry / list-item Paint / density / RTL are build-dependent "
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

    for index, menu in enumerate(registry.get("menus", []) or []):
        if not isinstance(menu, dict):
            errors.append(f"menus[{index}]:object required")
            continue
        menu_id = menu.get("id")
        context = f"menu[{menu_id}]" if isinstance(menu_id, str) else f"menus[{index}]"
        ui_file = menu.get("ui_file")
        menu_root = _parse_xml(contents.get(ui_file) if isinstance(ui_file, str) else None, context, errors)
        if menu_root is not None:
            _validate_menu(context, menu_root, menu, errors)

    modal_policy = registry.get("modal_policy")
    if isinstance(modal_policy, dict):
        policy_file = registry.get("policy_file", POLICY_PATH)
        _validate_modal_policy(contents.get(policy_file), modal_policy, errors)
    else:
        errors.append("registry:modal_policy:object required")

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
        print(f"Extension manager composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Extension manager composition contract passed: "
        f"{len(registry['dialogs'])} pinned dialog root(s) + the extension menu, the native "
        "windowbackground/pushbutton/checkbox/editbox/progress/frame/listnode parts in both "
        "palettes, every declared root kept native-exclusion (KeepModal) in the notification "
        "policy, the regex-search adjacency preserved, with pixels/list-item Paint/density/RTL "
        "carved out spec-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
