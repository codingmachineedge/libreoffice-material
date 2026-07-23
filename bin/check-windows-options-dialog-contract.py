#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Options dialog composition (WIN-DLG-002).

``qa/windows-ui-contract/options-dialog-composition.json`` pins the Options dialog composition from
docs/design/08-dialogs.md 8.2. The dialog is a TREE master-detail shell whose Material look is
delivered entirely by shared vcl tree parts already in definition.xml, so the M-scope is *pinning
composition*, never re-drawing controls. This checker parses the real tree fail-closed:

* ``dialog_composition`` -- the modal GtkDialog OptionsDialog, the GtkTreeView ``pages`` bound to
  GtkTreeStore ``liststore1`` (2 columns) with headers-visible=False and enable-tree-lines=True, and
  the searchEntry/searchEntry_regex_builder pair. A renamed tree, dropped model binding, or a lost
  header/tree-line flag fails closed.
* ``footer`` -- the action-widgets help(-11)/revert(101)/ok(-5)/cancel(-6) order with the primary OK
  button (has-default). The documented Apply drift is pinned explicitly: the ``apply`` GtkButton must
  exist AND must NOT appear in the action-widget id set (it has no response code).
* ``node_groups`` -- the 12 ordered top-level option groups, each an AddGroup(...) call site in
  treeopt.cxx keyed to its SID_*_RES resource array (declared in treeopt.hrc), verified present in
  ascending source position (comment-stripped) with its exact module-guard signature. A reorder,
  dropped group, or changed guard fails closed.
* ``tree_parts`` -- the shared listnode/listnet/windowbackground/frame parts + metrics + both-palette
  roles the tree resolves through must exist in definition.xml (read-only).
* ``modal_exclusion`` -- OptionsDialog must keep its native-exclusion (KeepModal) policy in
  dialog-notification-policy.csv (read-only).
* ``carveouts`` -- leaf-page enumeration, tree row-selection fill, density/adaptive width, and the
  field-grid/floating-label treatment are build-dependent, so their ``status`` must stay
  ``specified``.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, options-
dialog pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/options-dialog-composition.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected", "button-value", "extra",
)
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO / source hygiene
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals."""

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


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH, CSV_PATH}
    for key in ("dialog_ui", "hrc_source", "impl_source"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
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
# definition.xml tree parts
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


def _check_tokens(context: str, drawing: ET.Element, tokens: Mapping[str, Any], errors: list[str]) -> None:
    for token_key, expected in tokens.items():
        actual = drawing.get(token_key)
        if actual != expected:
            errors.append(f"{context} token drift: {token_key} is {actual!r}, expected {expected!r}")


def _validate_tree_parts(root: ET.Element, parts: Mapping[str, Any], errors: list[str]) -> None:
    for decl in parts.get("state_parts", []) or []:
        if not isinstance(decl, dict):
            errors.append("tree_parts:state_parts:entry must be object")
            continue
        name = decl.get("name", "?")
        part = _find_part(root, decl.get("control"), decl.get("part")) if isinstance(decl.get("control"), str) else None
        if part is None:
            errors.append(f"tree_parts:{name}:{decl.get('control')}/{decl.get('part')} missing in definition.xml")
            continue
        for state_decl in decl.get("states", []) or []:
            role = state_decl.get("role", "?") if isinstance(state_decl, dict) else "?"
            state = _match_state(part, state_decl.get("attrs", {})) if isinstance(state_decl, dict) else None
            if state is None:
                errors.append(f"tree_parts:{name}:{role}:no <state> matching {state_decl.get('attrs')}")
                continue
            drawing = _first_drawing_child(state)
            if drawing is None:
                errors.append(f"tree_parts:{name}:{role}:state has no rect/line")
                continue
            expected_element = state_decl.get("element")
            if isinstance(expected_element, str) and drawing.tag != expected_element:
                errors.append(f"tree_parts:{name}:{role}:element is <{drawing.tag}>, expected <{expected_element}>")
            _check_tokens(f"tree_parts:{name}:{role}", drawing, state_decl.get("tokens", {}), errors)

    for decl in parts.get("simple_parts", []) or []:
        if not isinstance(decl, dict):
            errors.append("tree_parts:simple_parts:entry must be object")
            continue
        name = decl.get("name", "?")
        part = _find_part(root, decl.get("control"), decl.get("part")) if isinstance(decl.get("control"), str) else None
        if part is None:
            errors.append(f"tree_parts:{name}:{decl.get('control')}/{decl.get('part')} missing in definition.xml")
            continue
        state = _match_state(part, decl.get("attrs", {}) if isinstance(decl.get("attrs"), dict) else {})
        if state is None:
            errors.append(f"tree_parts:{name}:no <state> matching {decl.get('attrs')}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"tree_parts:{name}:state has no rect/line")
            continue
        _check_tokens(f"tree_parts:{name}", drawing, decl.get("tokens", {}), errors)

    for decl in parts.get("present_parts", []) or []:
        if not isinstance(decl, dict):
            errors.append("tree_parts:present_parts:entry must be object")
            continue
        name = decl.get("name", "?")
        if _find_part(root, decl.get("control"), decl.get("part")) is None:
            errors.append(f"tree_parts:{name}:{decl.get('control')}/{decl.get('part')} missing in definition.xml")

    for metric in parts.get("metrics", []) or []:
        if not isinstance(metric, dict):
            continue
        actual = _named_value(root, metric.get("container"), metric.get("tag"), metric.get("name"))
        if actual is None:
            errors.append(f"tree_parts:metric:{metric.get('name')} missing in definition.xml")
        elif actual != metric.get("value"):
            errors.append(
                f"tree_parts:metric:{metric.get('name')} is {actual!r}, expected {metric.get('value')!r}"
            )

    for role in parts.get("palette_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"tree_parts:palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# optionsdialog.ui composition
# --------------------------------------------------------------------------------------------------
def _object_by_id(root: ET.Element, cls: str | None, oid: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == oid and (cls is None or obj.get("class") == cls):
            return obj
    return None


def _direct_property(obj: ET.Element, name: str) -> str | None:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return (prop.text or "").strip()
    return None


def _validate_dialog_composition(root: ET.Element, comp: Mapping[str, Any], errors: list[str]) -> None:
    dialog = comp.get("dialog")
    if isinstance(dialog, dict):
        obj = _object_by_id(root, "GtkDialog", dialog.get("id")) if isinstance(dialog.get("id"), str) else None
        if obj is None:
            errors.append(f"dialog_composition:GtkDialog id={dialog.get('id')!r} missing")
        elif dialog.get("modal") is True and _direct_property(obj, "modal") != "True":
            errors.append("dialog_composition:OptionsDialog must be modal=True")
    else:
        errors.append("dialog_composition:dialog:object required")

    tree = comp.get("tree")
    if isinstance(tree, dict):
        obj = _object_by_id(root, tree.get("class"), tree.get("id")) if isinstance(tree.get("id"), str) else None
        if obj is None:
            errors.append(f"dialog_composition:tree {tree.get('class')} id={tree.get('id')!r} missing")
        else:
            if _direct_property(obj, "model") != tree.get("model"):
                errors.append(
                    f"dialog_composition:tree model is {_direct_property(obj, 'model')!r}, "
                    f"expected {tree.get('model')!r}"
                )
            if tree.get("headers_visible") is False and _direct_property(obj, "headers-visible") != "False":
                errors.append("dialog_composition:tree headers-visible must be False")
            if tree.get("enable_tree_lines") is True and _direct_property(obj, "enable-tree-lines") != "True":
                errors.append("dialog_composition:tree enable-tree-lines must be True")
    else:
        errors.append("dialog_composition:tree:object required")

    liststore = comp.get("liststore")
    if isinstance(liststore, dict):
        obj = _object_by_id(root, liststore.get("class"), liststore.get("id")) if isinstance(liststore.get("id"), str) else None
        if obj is None:
            errors.append(f"dialog_composition:liststore {liststore.get('class')} id={liststore.get('id')!r} missing")
        else:
            columns_holder = obj.find("columns")
            count = len(columns_holder.findall("column")) if columns_holder is not None else 0
            if count != liststore.get("columns"):
                errors.append(
                    f"dialog_composition:liststore has {count} columns, expected {liststore.get('columns')}"
                )
    else:
        errors.append("dialog_composition:liststore:object required")

    search = comp.get("search_field")
    if isinstance(search, dict):
        for key in ("entry", "regex_builder"):
            oid = search.get(key)
            if isinstance(oid, str) and _object_by_id(root, None, oid) is None:
                errors.append(f"dialog_composition:search_field:{key} id={oid!r} missing (regex-search seam drifted)")
    else:
        errors.append("dialog_composition:search_field:object required")


def _validate_footer(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    action_holder = None
    for element in root.iter("action-widgets"):
        action_holder = element
        break
    expected = decl.get("action_widgets")
    if not isinstance(expected, list) or not expected:
        errors.append("footer:action_widgets:non-empty array required")
        return
    if action_holder is None:
        errors.append("footer:action-widgets block missing in optionsdialog.ui")
        return
    actual = [
        {"response": aw.get("response"), "id": (aw.text or "").strip()}
        for aw in action_holder.findall("action-widget")
    ]
    actual_ids = {a["id"] for a in actual}
    if len(actual) != len(expected):
        errors.append(
            f"footer:action_widgets length {len(actual)} != pinned {len(expected)} "
            "(a footer action-widget was added or removed)"
        )
    for index, want in enumerate(expected):
        if index >= len(actual):
            break
        got = actual[index]
        if got.get("id") != want.get("id") or got.get("response") != want.get("response"):
            errors.append(
                f"footer:action_widgets[{index}] drift: pinned {want.get('id')}({want.get('response')}) "
                f"but found {got.get('id')}({got.get('response')})"
            )

    primary = decl.get("primary")
    if isinstance(primary, dict) and primary.get("has_default") is True:
        button = _object_by_id(root, "GtkButton", primary.get("id")) if isinstance(primary.get("id"), str) else None
        if button is None:
            errors.append(f"footer:primary:GtkButton id={primary.get('id')!r} missing")
        elif _direct_property(button, "has-default") != "True":
            errors.append("footer:primary:OK button must be has-default=True")

    # Documented Apply drift: apply must exist as a button AND must NOT be an action-widget.
    drift = decl.get("apply_drift")
    if isinstance(drift, dict):
        apply_id = drift.get("button_id")
        if isinstance(apply_id, str):
            if _object_by_id(root, "GtkButton", apply_id) is None:
                errors.append(f"footer:apply_drift:GtkButton id={apply_id!r} missing (the Apply button vanished)")
            if drift.get("must_not_be_action_widget") is True and apply_id in actual_ids:
                errors.append(
                    f"footer:apply_drift:{apply_id!r} is now an action-widget "
                    "(the documented Apply drift changed -- re-record the carve-out)"
                )


# --------------------------------------------------------------------------------------------------
# node groups (treeopt.hrc + treeopt.cxx)
# --------------------------------------------------------------------------------------------------
def _find_marker(code: str, marker: str) -> int:
    """First occurrence of ``marker`` whose trailing char is a token boundary.

    The AddGroup argument markers end in an identifier (e.g. ``SID_SC_EDITOPTIONS``), so a bare
    substring find would false-match a renamed ``SID_SC_EDITOPTIONS_V2``. Require the char after
    the match to not continue the identifier.
    """

    start = 0
    while True:
        idx = code.find(marker, start)
        if idx < 0:
            return -1
        after = code[idx + len(marker): idx + len(marker) + 1]
        if not (after.isalnum() or after == "_"):
            return idx
        start = idx + 1


def _validate_node_groups(registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]) -> None:
    groups = registry.get("node_groups")
    if not isinstance(groups, list) or not groups:
        errors.append("node_groups:non-empty array required")
        return

    hrc_rel = registry.get("hrc_source")
    hrc_text = contents.get(hrc_rel) if isinstance(hrc_rel, str) else None
    impl_rel = registry.get("impl_source")
    impl_text = contents.get(impl_rel) if isinstance(impl_rel, str) else None
    if impl_text is None:
        errors.append("node_groups:impl_source file missing")
        code = ""
    else:
        code = _strip_comments(impl_text)

    last_index = -1
    last_name = None
    for group in groups:
        if not isinstance(group, dict):
            errors.append("node_groups:entry must be object")
            continue
        name = group.get("name", "?")

        res_array = group.get("res_array")
        if isinstance(res_array, str):
            if hrc_text is None:
                errors.append("node_groups:hrc_source file missing")
            elif f"{res_array}[]" not in hrc_text:
                errors.append(f"node_groups:{name}:resource array {res_array}[] missing in treeopt.hrc")

        marker = group.get("marker")
        if not isinstance(marker, str) or not marker:
            errors.append(f"node_groups:{name}:marker:non-empty string required")
            continue
        pos = _find_marker(code, marker)
        if pos < 0:
            errors.append(
                f"node_groups:{name}:AddGroup marker {marker!r} missing from real code in treeopt.cxx "
                "(group call site removed, guard changed, or SID renamed)"
            )
            continue
        if pos < last_index:
            errors.append(
                f"node_groups:{name}:AddGroup out of order relative to {last_name!r} "
                "(the top-level group sequence was reordered)"
            )
        last_index = pos
        last_name = name


# --------------------------------------------------------------------------------------------------
# modal exclusion + carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_modal_exclusion(exclusion: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(exclusion, dict):
        errors.append("modal_exclusion:object required")
        return
    csv_text = contents.get(CSV_PATH)
    if csv_text is None:
        errors.append(f"modal_exclusion:file missing: {CSV_PATH}")
        return
    rows = list(csv.reader(io.StringIO(csv_text)))
    policy_by_locator: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        if len(row) >= 4:
            policy_by_locator[(row[0], row[1])] = row[3]
    ui_path = exclusion.get("ui_path")
    object_id = exclusion.get("object_id")
    expected = exclusion.get("expected_policy")
    if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(expected, str)):
        errors.append("modal_exclusion:ui_path/object_id/expected_policy must be strings")
        return
    actual = policy_by_locator.get((ui_path, object_id))
    if actual is None:
        errors.append(f"modal_exclusion:{ui_path}::{object_id} absent from {CSV_PATH} (no longer registered)")
    elif actual != expected:
        errors.append(
            f"modal_exclusion:{ui_path}::{object_id} policy is {actual!r}, expected {expected!r} "
            "(the input-collecting Options dialog left KeepModal)"
        )


def _validate_carveouts(carveouts: Any, errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("carveouts:non-empty object required")
        return
    for name in ("leaf_page_enumeration_deferred", "tree_row_selection_fill", "density_adaptive_width", "field_grid_floating_label"):
        block = carveouts.get(name)
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' "
                "(build-dependent; not promoted to an implemented claim)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-options-dialog-composition":
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

    definition_root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    tree_parts = registry.get("tree_parts")
    if isinstance(tree_parts, dict):
        if definition_root is not None:
            _validate_tree_parts(definition_root, tree_parts, errors)
    else:
        errors.append("registry:tree_parts:object required")

    dialog_rel = registry.get("dialog_ui")
    dialog_root = _parse_xml(
        contents.get(dialog_rel) if isinstance(dialog_rel, str) else None, "dialog_ui", errors
    )
    if dialog_root is not None:
        comp = registry.get("dialog_composition")
        if isinstance(comp, dict):
            _validate_dialog_composition(dialog_root, comp, errors)
        else:
            errors.append("registry:dialog_composition:object required")
        footer = registry.get("footer")
        if isinstance(footer, dict):
            _validate_footer(dialog_root, footer, errors)
        else:
            errors.append("registry:footer:object required")

    _validate_node_groups(registry, contents, errors)
    _validate_modal_exclusion(registry.get("modal_exclusion"), contents, errors)
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
        print(f"Options dialog contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Options dialog contract passed: pinned the modal tree shell (pages/liststore1, no headers, "
        "tree-lines) + the regex-search pair, the help/revert/ok/cancel footer with the recorded "
        f"Apply drift, the {len(registry['node_groups'])} ordered AddGroup option groups with module "
        "guards, and the shared listnode/listnet/windowbackground/frame tree parts; KeepModal + "
        "leaf/selection/density/field-grid carve-outs spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
