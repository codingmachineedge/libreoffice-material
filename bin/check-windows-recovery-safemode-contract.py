#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the recovery / Safe-Mode surfaces (WIN-SYS-009).

``qa/windows-ui-contract/recovery-safemode.json`` pins the composition of the seven
real upstream recovery / crash / Safe-Mode ``.ui`` surfaces plus their two weld
consumers, so the row's core constraint -- these safeguards must remain INTACT,
never removed or rerouted -- is enforced fail-closed. The surfaces are weld
GtkDialogs whose Material look is delivered entirely by shared vcl parts already in
definition.xml, so the M-scope is *pinning composition*, never re-drawing controls.
This checker parses the real tree fail-closed and cross-validates every declaration:

* ``dialogs`` -- each ``.ui`` root exists with its pinned widget class; its
  ``<action-widget>`` order + response ids match exactly (a removed, added,
  reordered, or re-responded action widget fails closed); every ``required_widget``
  exists with its pinned class and any pinned property (e.g. ``radio_restore``
  active, the safe action's ``has-default``); and the ``safe_default`` invariant
  holds -- the safe action keeps ``has-default`` while each forbidden (destructive)
  action must never carry it (Recover Selected stays default over Discard All,
  Cancel stays default over Restart). Hyphen and underscore property spellings are
  normalized before comparison.
* ``weld_bindings`` -- svx/source/dialog/docrecovery.cxx and SafeModeDialog.cxx
  still bind the preserved widgets. Each ``weld_<kind>(u"id"_ustr)`` is matched from
  comment-stripped source with the ``u`` prefix / ``_ustr`` suffix tolerated, so a
  dropped binding (dead safeguard widget) fails closed.
* ``grounding_parts`` -- the native parts the dialogs resolve through
  (windowbackground/BackgroundDialog, pushbutton Entire+Focus, radiobutton,
  checkbox, progress TrackHorzArea+Entire, frame/Border) must exist in
  definition.xml, and every declared palette role must resolve in *both* the light
  and dark palettes. The definition file is read only, never mutated.
* ``policy_crosscheck`` -- the seven recovery/safemode/crash rows in the shared
  dialog-notification-policy.csv must stay ``native-exclusion`` (router Classify:
  KeepModal). Read-only reconciliation, anchored on ui_path + object_id (never a
  line number); a row rerouted to the bottom-right notification form or removed
  fails closed.
* ``retained_safeguards`` -- the no-nag retained-safeguard markers (handleSafeMode,
  the autorecovery command, the auto-recovery service) must still exist as real
  (comment-stripped) code, reconciled with check-windows-no-nag-contract.py.
* ``carveouts`` -- the Discard-All -> ConfirmDestructiveAction conversion and the
  Material dialog anatomy are build-dependent, so their ``status`` must stay
  ``specified`` and is never promoted to an implemented claim.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, dialog pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/recovery-safemode.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
POLICY_CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

NATIVE_EXCLUSION = "native-exclusion"
REQUIRED_SCHEMES = ("", "dark")
TRUE_VALUES = frozenset({"true", "1", "yes"})


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
    paths: set[str] = {DEFINITION_PATH, POLICY_CSV_PATH}
    for dialog in registry.get("dialogs", []) or []:
        if isinstance(dialog, dict) and isinstance(dialog.get("ui_file"), str):
            paths.add(dialog["ui_file"])
    for binding in registry.get("weld_bindings", []) or []:
        if isinstance(binding, dict) and isinstance(binding.get("file"), str):
            paths.add(binding["file"])
    for safeguard in registry.get("retained_safeguards", []) or []:
        if isinstance(safeguard, dict) and isinstance(safeguard.get("file"), str):
            paths.add(safeguard["file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# C++ comment stripping (preserves string literals; anchors bind to real code).
# --------------------------------------------------------------------------------------------------
def _strip_comments(text: str) -> str:
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
        # quote
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
# XML helpers
# --------------------------------------------------------------------------------------------------
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


def _index_ui(root: ET.Element) -> dict[str, tuple[str, dict[str, str]]]:
    """id -> (widget_class, {normalized-property-name: value}) for every ``<object>``.

    Property names are normalized (``_`` -> ``-``) so the checker tolerates the .ui
    files' mixed hyphen/underscore spellings.
    """

    objects: dict[str, tuple[str, dict[str, str]]] = {}
    for obj in root.iter():
        if _local(obj.tag) != "object":
            continue
        oid = (obj.get("id") or "").strip()
        if not oid:
            continue
        props: dict[str, str] = {}
        for prop in obj:
            if _local(prop.tag) == "property":
                name = (prop.get("name") or "").replace("_", "-")
                props[name] = (prop.text or "").strip()
        objects[oid] = (obj.get("class", ""), props)
    return objects


def _action_widgets(root: ET.Element) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for node in root.iter():
        if _local(node.tag) == "action-widget":
            result.append(((node.get("response") or "").strip(), (node.text or "").strip()))
    return result


def _is_true(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUE_VALUES


def _find_part(root: ET.Element, control: str, part: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part:
            return candidate
    return None


def _palette_color(root: ET.Element, scheme: str, name: str) -> str | None:
    for palette in root.findall("palette"):
        if (palette.get("scheme") or "") != scheme:
            continue
        for color in palette.findall("color"):
            if color.get("name") == name:
                return color.get("value")
    return None


# --------------------------------------------------------------------------------------------------
# Per-section validation
# --------------------------------------------------------------------------------------------------
def _validate_dialog(
    dialog: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    did = dialog.get("id", "?")
    ui_file = dialog.get("ui_file")
    dialog_id = dialog.get("dialog_id")
    widget_class = dialog.get("widget_class")
    if not (isinstance(ui_file, str) and isinstance(dialog_id, str) and isinstance(widget_class, str)):
        errors.append(f"dialogs:{did}:ui_file/dialog_id/widget_class must be strings")
        return
    root = _parse_xml(contents.get(ui_file), f"dialogs:{did}", errors)
    if root is None:
        return
    objects = _index_ui(root)

    if dialog_id not in objects:
        errors.append(f"dialogs:{did}:root object {dialog_id!r} missing from {ui_file}")
    elif objects[dialog_id][0] != widget_class:
        errors.append(
            f"dialogs:{did}:root {dialog_id} class is {objects[dialog_id][0]!r}, "
            f"expected {widget_class!r} (widget-class drift)"
        )

    action_widgets = dialog.get("action_widgets")
    if action_widgets is not None:
        if not isinstance(action_widgets, list):
            errors.append(f"dialogs:{did}:action_widgets must be an array")
        else:
            expected = [
                ((aw.get("response") or "").strip(), (aw.get("id") or "").strip())
                for aw in action_widgets
                if isinstance(aw, dict)
            ]
            actual = _action_widgets(root)
            if actual != expected:
                errors.append(
                    f"dialogs:{did}:action-widget drift: pinned {expected} but found {actual} "
                    "(a footer action was added, removed, reordered, or re-responded)"
                )

    for widget in dialog.get("required_widgets", []) or []:
        if not isinstance(widget, dict):
            errors.append(f"dialogs:{did}:required_widget must be an object")
            continue
        wid = widget.get("id")
        if not isinstance(wid, str):
            errors.append(f"dialogs:{did}:required_widget id must be a string")
            continue
        if wid not in objects:
            errors.append(f"dialogs:{did}:missing widget {wid!r} in {ui_file}")
            continue
        cls, props = objects[wid]
        want_class = widget.get("class")
        if isinstance(want_class, str) and cls != want_class:
            errors.append(
                f"dialogs:{did}:widget {wid} class is {cls!r}, expected {want_class!r}"
            )
        for pkey, pval in (widget.get("properties") or {}).items():
            norm = str(pkey).replace("_", "-")
            actual = props.get(norm)
            if actual is None or actual.strip().lower() != str(pval).strip().lower():
                errors.append(
                    f"dialogs:{did}:widget {wid} property {norm} is {actual!r}, "
                    f"expected {pval!r} (composition drift)"
                )
        for pkey in widget.get("absent_or_false") or []:
            norm = str(pkey).replace("_", "-")
            if _is_true(props.get(norm)):
                errors.append(
                    f"dialogs:{did}:widget {wid} must not set {norm}=True "
                    "(non-default action carries a default flag)"
                )

    safe_default = dialog.get("safe_default")
    if isinstance(safe_default, dict):
        default_action = safe_default.get("default_action")
        if not isinstance(default_action, str):
            errors.append(f"dialogs:{did}:safe_default.default_action must be a string")
        elif default_action not in objects:
            errors.append(f"dialogs:{did}:safe_default action {default_action!r} not found")
        elif not _is_true(objects[default_action][1].get("has-default")):
            errors.append(
                f"dialogs:{did}:safe default lost -- {default_action} no longer has has-default "
                "(the safe action must stay the Enter default)"
            )
        for forbidden in safe_default.get("forbidden_default_actions", []) or []:
            if forbidden in objects and _is_true(objects[forbidden][1].get("has-default")):
                errors.append(
                    f"dialogs:{did}:destructive action {forbidden} became the default "
                    "(the destructive action must never carry has-default)"
                )


def _weld_present(code: str, method: str, widget: str) -> bool:
    pattern = re.compile(
        re.escape(method) + r"\(\s*u?\"" + re.escape(widget) + r"\"(?:_ustr)?\s*\)"
    )
    return pattern.search(code) is not None


def _validate_weld_bindings(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for group in registry.get("weld_bindings", []) or []:
        if not isinstance(group, dict):
            errors.append("weld_bindings:entry must be an object")
            continue
        file_path = group.get("file")
        if not isinstance(file_path, str):
            errors.append("weld_bindings:file must be a string")
            continue
        text = contents.get(file_path)
        if text is None:
            errors.append(f"weld_bindings:{file_path}:file missing")
            continue
        code = _strip_comments(text)
        for binding in group.get("bindings", []) or []:
            if not isinstance(binding, dict):
                errors.append(f"weld_bindings:{file_path}:binding must be an object")
                continue
            method = binding.get("method")
            widget = binding.get("widget")
            if not (isinstance(method, str) and isinstance(widget, str)):
                errors.append(f"weld_bindings:{file_path}:method/widget must be strings")
                continue
            if not _weld_present(code, method, widget):
                errors.append(
                    f"weld_bindings:{file_path}:missing binding {method}(\"{widget}\") "
                    "(a preserved recovery widget is no longer bound in source)"
                )


def _validate_grounding(root: ET.Element | None, block: Mapping[str, Any], errors: list[str]) -> None:
    if root is None:
        return
    for entry in block.get("control_parts", []) or []:
        if not isinstance(entry, dict):
            errors.append("grounding_parts:control_part must be an object")
            continue
        control = entry.get("control")
        part = entry.get("part")
        if not (isinstance(control, str) and isinstance(part, str)):
            errors.append("grounding_parts:control/part must be strings")
            continue
        if _find_part(root, control, part) is None:
            errors.append(
                f"grounding_parts:{control}/{part} missing in definition.xml "
                "(the native part the recovery dialogs resolve through was renamed or removed)"
            )
    for role in block.get("palette_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"grounding_parts:palette:@{role} missing from the {label} palette")


def _read_policy_rows(text: str | None, errors: list[str]) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    if text is None:
        errors.append(f"policy_crosscheck:{POLICY_CSV_PATH}:file missing")
        return rows
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        ui_path = (row.get("ui_path") or "").strip()
        object_id = (row.get("object_id") or "").strip()
        rows[(ui_path, object_id)] = (row.get("policy") or "").strip()
    return rows


def _validate_policy_crosscheck(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    rows = _read_policy_rows(contents.get(POLICY_CSV_PATH), errors)
    for entry in registry.get("policy_crosscheck", []) or []:
        if not isinstance(entry, dict):
            errors.append("policy_crosscheck:entry must be an object")
            continue
        ui_file = entry.get("ui_file")
        dialog_id = entry.get("dialog_id")
        expected = entry.get("expected_policy", NATIVE_EXCLUSION)
        if not (isinstance(ui_file, str) and isinstance(dialog_id, str)):
            errors.append("policy_crosscheck:ui_file/dialog_id must be strings")
            continue
        policy = rows.get((ui_file, dialog_id))
        if policy is None:
            errors.append(
                f"policy_crosscheck:{ui_file}#{dialog_id} missing from {POLICY_CSV_PATH} "
                "(a preserved recovery safeguard row was removed)"
            )
        elif policy != expected:
            errors.append(
                f"policy_crosscheck:{ui_file}#{dialog_id} policy is {policy!r}, expected "
                f"{expected!r} (a modal recovery safeguard was rerouted)"
            )


def _validate_retained_safeguards(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for safeguard in registry.get("retained_safeguards", []) or []:
        if not isinstance(safeguard, dict):
            errors.append("retained_safeguards:entry must be an object")
            continue
        file_path = safeguard.get("file")
        marker = safeguard.get("marker")
        if not (isinstance(file_path, str) and isinstance(marker, str)):
            errors.append("retained_safeguards:file/marker must be strings")
            continue
        text = contents.get(file_path)
        if text is None:
            errors.append(f"retained_safeguards:{file_path}:file missing")
            continue
        if marker not in _strip_comments(text):
            errors.append(
                f"retained_safeguards:{file_path}:missing marker {marker!r} "
                "(a preserved recovery/Safe-Mode safeguard was removed)"
            )


def _validate_carveouts(registry: Mapping[str, Any], errors: list[str]) -> None:
    carveouts = registry.get("carveouts")
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("registry:carveouts:object required")
        return
    for name, block in carveouts.items():
        if not isinstance(block, dict) or block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' "
                "(the ConfirmDestructiveAction conversion / Material anatomy are "
                "build-dependent and must not be promoted to an implemented claim)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-recovery-safemode-composition":
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

    dialogs = registry.get("dialogs")
    if not isinstance(dialogs, list) or not dialogs:
        errors.append("registry:dialogs:non-empty array required")
    else:
        seen: set[str] = set()
        for dialog in dialogs:
            if not isinstance(dialog, dict):
                errors.append("registry:dialogs:entry must be an object")
                continue
            did = dialog.get("id")
            if isinstance(did, str):
                if did in seen:
                    errors.append(f"registry:dialogs:duplicate id {did!r}")
                seen.add(did)
            _validate_dialog(dialog, contents, errors)

    _validate_weld_bindings(registry, contents, errors)

    grounding = registry.get("grounding_parts")
    if isinstance(grounding, dict):
        root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
        _validate_grounding(root, grounding, errors)
    else:
        errors.append("registry:grounding_parts:object required")

    _validate_policy_crosscheck(registry, contents, errors)
    _validate_retained_safeguards(registry, contents, errors)
    _validate_carveouts(registry, errors)

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
        print(f"Recovery/Safe-Mode composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Recovery/Safe-Mode composition contract passed: "
        f"{len(registry['dialogs'])} pinned recovery/crash/Safe-Mode dialog(s), their weld "
        "bindings, native-part grounding in both palettes, the seven KeepModal policy rows "
        "and the no-nag retained safeguards, with the ConfirmDestructiveAction conversion and "
        "Material anatomy carved out spec-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
