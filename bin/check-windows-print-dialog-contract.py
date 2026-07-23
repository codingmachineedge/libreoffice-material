#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Print dialog composition (WIN-DLG-004).

``qa/windows-ui-contract/print-dialog.json`` pins the Print dialog composition from
docs/design/08-dialogs.md 8.4. The dialog is a GtkNotebook-hosted GenericDialogController whose
Material look is delivered entirely by shared vcl parts already in definition.xml, so the M-scope
is *pinning composition*, never re-drawing controls. This checker parses the real tree fail-closed
(check-pdf-export-dialog-contract.py pattern):

* ``footer`` -- the action-widgets help(-11)/ok(-5)/cancel(-6) order with the primary Print button
  (``_Print``, has-default). A reorder or a lost default fails closed.
* ``structure`` -- the tabcontrol GtkNotebook, previewbox GtkCheckButton, the Range radio trio in
  order inside GtkFrame frPrintRange, the Printer field (printersbox + setup) inside frPrinterName,
  the Copies field (copycount bound to adjustment2 lower=1/upper=16384), and the real FOUR-button
  preview pager (btnFirst/backward/forward/btnLast) plus the pageedit entry and the totalnumpages
  ``/ %n`` label -- correcting the design's simplified two-button pager prose against real source.
* ``native_parts`` -- the pushbutton ``extra="action"`` states, radiobutton/Entire at
  ``@corner-control``, combobox / checkbox / spinbox / tabpane / tabbody parts, the spinbuttons
  part's existence, every declared metric value, and every referenced palette role in *both*
  palettes must resolve in definition.xml (read-only). A renamed part, dropped state, or token
  drift fails closed.
* ``modal_exclusions`` -- PrintDialog must keep its native-exclusion (KeepModal) policy in
  dialog-notification-policy.csv (read-only cross-check).
* ``carveouts`` -- the runtime-injected app tabs, preview-thumbnail rendering, prototype geometry,
  and adaptive stacking are build-dependent, so their ``status`` must stay ``specified``.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, print-dialog
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
REGISTRY_PATH = "qa/windows-ui-contract/print-dialog.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected", "button-value", "extra",
)
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


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH, CSV_PATH}
    dialog = registry.get("dialog_ui")
    if isinstance(dialog, str):
        paths.add(dialog)
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
# definition.xml part validation
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


def _validate_state_part(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    name = decl.get("name", "?")
    control = decl.get("control")
    part_name = decl.get("part")
    if not (isinstance(control, str) and isinstance(part_name, str)):
        errors.append(f"native_parts:{name}:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} missing in definition.xml")
        return
    for state_decl in decl.get("states", []) or []:
        role = state_decl.get("role", "?") if isinstance(state_decl, dict) else "?"
        if not isinstance(state_decl, dict):
            errors.append(f"native_parts:{name}:state must be object")
            continue
        state = _match_state(part, state_decl.get("attrs", {}))
        if state is None:
            errors.append(f"native_parts:{name}:{role}:no <state> matching {state_decl.get('attrs')}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"native_parts:{name}:{role}:state has no rect/line")
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"native_parts:{name}:{role}:element is <{drawing.tag}>, expected <{expected_element}>"
            )
        _check_tokens(f"native_parts:{name}:{role}", drawing, state_decl.get("tokens", {}), errors)


def _validate_simple_part(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    name = decl.get("name", "?")
    control = decl.get("control")
    part_name = decl.get("part")
    if not (isinstance(control, str) and isinstance(part_name, str)):
        errors.append(f"native_parts:{name}:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} missing in definition.xml")
        return
    state = _match_state(part, decl.get("attrs", {}) if isinstance(decl.get("attrs"), dict) else {})
    if state is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} no <state> matching {decl.get('attrs')}")
        return
    drawing = _first_drawing_child(state)
    if drawing is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} state has no rect/line")
        return
    expected_element = decl.get("element")
    if isinstance(expected_element, str) and drawing.tag != expected_element:
        errors.append(f"native_parts:{name}:element is <{drawing.tag}>, expected <{expected_element}>")
    _check_tokens(f"native_parts:{name}", drawing, decl.get("tokens", {}), errors)


def _validate_native_parts(root: ET.Element, parts: Mapping[str, Any], errors: list[str]) -> None:
    for decl in parts.get("state_parts", []) or []:
        if isinstance(decl, dict):
            _validate_state_part(root, decl, errors)
        else:
            errors.append("native_parts:state_parts:entry must be object")

    for decl in parts.get("simple_parts", []) or []:
        if isinstance(decl, dict):
            _validate_simple_part(root, decl, errors)
        else:
            errors.append("native_parts:simple_parts:entry must be object")

    for decl in parts.get("present_parts", []) or []:
        if not isinstance(decl, dict):
            errors.append("native_parts:present_parts:entry must be object")
            continue
        name = decl.get("name", "?")
        control = decl.get("control")
        part_name = decl.get("part")
        if not (isinstance(control, str) and isinstance(part_name, str)):
            errors.append(f"native_parts:{name}:control/part must be strings")
            continue
        if _find_part(root, control, part_name) is None:
            errors.append(f"native_parts:{name}:{control}/{part_name} missing in definition.xml")

    for metric in parts.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("native_parts:metric:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("native_parts:metric:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"native_parts:metric:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(f"native_parts:metric:{mname} is {actual!r}, expected {expected!r} (metric drift)")

    for role in parts.get("palette_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"native_parts:palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# printdialog.ui composition
# --------------------------------------------------------------------------------------------------
def _object_by_id(root: ET.Element, cls: str | None, oid: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == oid and (cls is None or obj.get("class") == cls):
            return obj
    return None


def _direct_property(obj: ET.Element, name: str) -> ET.Element | None:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return prop
    return None


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
        errors.append("footer:action-widgets block missing in printdialog.ui")
        return
    actual = [
        {"response": aw.get("response"), "id": (aw.text or "").strip()}
        for aw in action_holder.findall("action-widget")
    ]
    if len(actual) != len(expected):
        errors.append(
            f"footer:action_widgets length {len(actual)} != pinned {len(expected)} "
            "(a footer button was added or removed)"
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
    if not isinstance(primary, dict):
        errors.append("footer:primary:object required")
        return
    button = _object_by_id(root, "GtkButton", primary.get("id")) if isinstance(primary.get("id"), str) else None
    if button is None:
        errors.append(f"footer:primary:GtkButton id={primary.get('id')!r} missing in printdialog.ui")
        return
    if primary.get("has_default") is True:
        prop = _direct_property(button, "has-default")
        if prop is None or (prop.text or "").strip() != "True":
            errors.append("footer:primary:Print button must be has-default=True")
    expected_label = primary.get("label")
    if isinstance(expected_label, str):
        prop = _direct_property(button, "label")
        actual = (prop.text or "").strip() if prop is not None else None
        if actual != expected_label:
            errors.append(
                f"footer:primary:label is {actual!r}, expected {expected_label!r} (primary action is not Print)"
            )


def _descendant_ids_in_order(container: ET.Element, cls: str) -> list[str]:
    return [obj.get("id") for obj in container.iter("object") if obj.get("class") == cls and obj.get("id")]


def _validate_widget(root: ET.Element, context: str, decl: Any, errors: list[str]) -> None:
    if not isinstance(decl, dict):
        errors.append(f"{context}:object required")
        return
    oid = decl.get("id")
    cls = decl.get("class")
    obj = _object_by_id(root, cls if isinstance(cls, str) else None, oid) if isinstance(oid, str) else None
    if obj is None:
        errors.append(f"{context}:{cls} id={oid!r} missing in printdialog.ui")
        return
    expected_text = decl.get("text")
    if isinstance(expected_text, str):
        prop = _direct_property(obj, "label")
        actual = (prop.text or "").strip() if prop is not None else None
        if actual != expected_text:
            errors.append(f"{context}:label is {actual!r}, expected {expected_text!r}")


def _validate_ordered_group(
    root: ET.Element, context: str, frame_id: str, cls: str, expected_ids: Sequence[str], errors: list[str]
) -> None:
    frame = _object_by_id(root, None, frame_id)
    if frame is None:
        errors.append(f"{context}:frame id={frame_id!r} missing in printdialog.ui")
        return
    actual = _descendant_ids_in_order(frame, cls)
    for oid in expected_ids:
        if oid not in actual:
            errors.append(f"{context}:{cls} {oid!r} missing inside {frame_id!r}")
    positions = [actual.index(oid) for oid in expected_ids if oid in actual]
    if positions != sorted(positions):
        errors.append(f"{context}:{cls} order drift inside {frame_id!r}: pinned {list(expected_ids)}, found {actual}")


def _validate_structure(root: ET.Element, structure: Mapping[str, Any], errors: list[str]) -> None:
    _validate_widget(root, "structure:notebook", structure.get("notebook"), errors)
    _validate_widget(root, "structure:previewbox", structure.get("previewbox"), errors)

    range_group = structure.get("range_group")
    if isinstance(range_group, dict):
        _validate_ordered_group(
            root, "structure:range_group", range_group.get("frame_id"), "GtkRadioButton",
            range_group.get("radios", []), errors,
        )
    else:
        errors.append("structure:range_group:object required")

    printer = structure.get("printer_group")
    if isinstance(printer, dict):
        frame = _object_by_id(root, None, printer.get("frame_id"))
        if frame is None:
            errors.append(f"structure:printer_group:frame id={printer.get('frame_id')!r} missing")
        else:
            for key in ("combo", "setup"):
                sub = printer.get(key)
                if isinstance(sub, dict) and isinstance(sub.get("id"), str):
                    if _object_by_id(frame, sub.get("class"), sub["id"]) is None:
                        errors.append(
                            f"structure:printer_group:{key} {sub.get('class')} id={sub['id']!r} "
                            f"missing inside {printer.get('frame_id')!r}"
                        )
                else:
                    errors.append(f"structure:printer_group:{key}:object with id required")
    else:
        errors.append("structure:printer_group:object required")

    copies = structure.get("copies")
    if isinstance(copies, dict):
        spin = copies.get("spin")
        adjustment = copies.get("adjustment")
        _validate_widget(root, "structure:copies:spin", spin, errors)
        if isinstance(spin, dict) and isinstance(adjustment, dict):
            spin_obj = _object_by_id(root, spin.get("class"), spin.get("id"))
            adj_id = adjustment.get("id")
            if spin_obj is not None:
                prop = _direct_property(spin_obj, "adjustment")
                bound = (prop.text or "").strip() if prop is not None else None
                if bound != adj_id:
                    errors.append(
                        f"structure:copies:spin adjustment is {bound!r}, expected {adj_id!r}"
                    )
            adj_obj = _object_by_id(root, "GtkAdjustment", adj_id) if isinstance(adj_id, str) else None
            if adj_obj is None:
                errors.append(f"structure:copies:GtkAdjustment id={adj_id!r} missing")
            else:
                for bound_key in ("lower", "upper"):
                    prop = _direct_property(adj_obj, bound_key)
                    actual = (prop.text or "").strip() if prop is not None else None
                    if actual != adjustment.get(bound_key):
                        errors.append(
                            f"structure:copies:adjustment {bound_key} is {actual!r}, "
                            f"expected {adjustment.get(bound_key)!r}"
                        )
    else:
        errors.append("structure:copies:object required")

    pager = structure.get("pager")
    if isinstance(pager, dict):
        buttons = pager.get("page_buttons")
        if isinstance(buttons, list) and buttons:
            actual = _descendant_ids_in_order(root, "GtkButton")
            present = [b for b in buttons if b in actual]
            missing = [b for b in buttons if b not in actual]
            for oid in missing:
                errors.append(f"structure:pager:GtkButton {oid!r} missing in printdialog.ui")
            positions = [actual.index(b) for b in present]
            if positions != sorted(positions):
                errors.append(
                    f"structure:pager:page-button order drift: pinned {buttons}, found order {present}"
                )
        else:
            errors.append("structure:pager:page_buttons:non-empty array required")
        _validate_widget(root, "structure:pager:page_entry", pager.get("page_entry"), errors)
        _validate_widget(root, "structure:pager:total_label", pager.get("total_label"), errors)
    else:
        errors.append("structure:pager:object required")


# --------------------------------------------------------------------------------------------------
# modal exclusions + carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_modal_exclusions(exclusions: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(exclusions, list) or not exclusions:
        errors.append("modal_exclusions:non-empty array required")
        return
    csv_text = contents.get(CSV_PATH)
    if csv_text is None:
        errors.append(f"modal_exclusions:file missing: {CSV_PATH}")
        return
    rows = list(csv.reader(io.StringIO(csv_text)))
    policy_by_locator: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        if len(row) >= 4:
            policy_by_locator[(row[0], row[1])] = row[3]
    for index, exclusion in enumerate(exclusions):
        if not isinstance(exclusion, dict):
            errors.append(f"modal_exclusions[{index}]:object required")
            continue
        ui_path = exclusion.get("ui_path")
        object_id = exclusion.get("object_id")
        expected = exclusion.get("expected_policy")
        if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(expected, str)):
            errors.append(f"modal_exclusions[{index}]:ui_path/object_id/expected_policy must be strings")
            continue
        actual = policy_by_locator.get((ui_path, object_id))
        if actual is None:
            errors.append(
                f"modal_exclusions:{ui_path}::{object_id} absent from {CSV_PATH} "
                "(the Print dialog is no longer registered)"
            )
        elif actual != expected:
            errors.append(
                f"modal_exclusions:{ui_path}::{object_id} policy is {actual!r}, expected {expected!r} "
                "(the input-collecting Print dialog left KeepModal)"
            )


def _validate_carveouts(carveouts: Any, errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("carveouts:non-empty object required")
        return
    for name in ("runtime_injected_tabs", "preview_thumbnail_rendering", "prototype_geometry", "adaptive_stacking"):
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
    if registry.get("contract") != "material-print-dialog-composition":
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
    native_parts = registry.get("native_parts")
    if isinstance(native_parts, dict):
        if definition_root is not None:
            _validate_native_parts(definition_root, native_parts, errors)
    else:
        errors.append("registry:native_parts:object required")

    dialog_rel = registry.get("dialog_ui")
    dialog_root = _parse_xml(
        contents.get(dialog_rel) if isinstance(dialog_rel, str) else None, "dialog_ui", errors
    )
    if dialog_root is not None:
        footer = registry.get("footer")
        if isinstance(footer, dict):
            _validate_footer(dialog_root, footer, errors)
        else:
            errors.append("registry:footer:object required")
        structure = registry.get("structure")
        if isinstance(structure, dict):
            _validate_structure(dialog_root, structure, errors)
        else:
            errors.append("registry:structure:object required")

    _validate_modal_exclusions(registry.get("modal_exclusions"), contents, errors)
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
        print(f"Print dialog contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Print dialog contract passed: pinned the Print-default footer, the tabcontrol notebook, "
        "the Range radio trio, the Printer field, the Copies spin (adjustment2 1..16384), the real "
        "four-button preview pager + '/ %n' label, and the native pushbutton/radiobutton/combobox/"
        "checkbox/spinbox/tab parts, with the KeepModal exclusion and runtime-tab / preview / "
        "geometry / stacking carve-outs spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
