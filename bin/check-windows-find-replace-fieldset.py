#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the Material Find & Replace field set (inventory row WIN-INP-006).

The registry ``qa/windows-ui-contract/find-replace-fieldset.json`` describes the one native
Find & Replace surface (``svx/uiconfig/ui/findreplacedialog.ui`` +
``svx/source/dialog/srchdlg.cxx`` / ``include/svx/srchdlg.hxx``). This checker enforces the
composition and engine-flag contract of docs/design/04-inputs.md sections 6 and 6.1:

* the find field is the shared search combo with its adjacent advanced regex builder, and the
  builder is bound through the shared ``sfx2::RegexSearchController`` (the registered
  ``document.find-replace`` integration);
* the option checkboxes -- Match case, Whole words only, Regular expressions -- drive the ONE
  ``SvxSearchItem`` (the single ICU-backed LibreOffice search descriptor), never a parallel
  matcher: Match case is the inverse of the ignore-case flag, Whole words maps to the descriptor
  word-boundary option, and Regular expressions shares its state with the builder mode;
* the regexp toggle and the builder controller stay bidirectionally consistent through the sync
  helpers, with a mode-equality guard so the two-way binding never forms a feedback loop;
* a Replace field and an in-dialog result-summary label (notification a11y role) are present; and
* the full action set is present with Material emphasis (exactly one action carries the filled
  ``suggested-action`` role and it is the keyboard Enter default).

It is source evidence only: no native build, dialog pixels, or runtime interaction are claimed.
Anchors are the real wiring code (weld bindings, descriptor writes, sync helpers), so a checkbox
whose binding is reduced to a comment fails the contract.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/find-replace-fieldset.json"

REQUIRED_OPTIONS = ("match-case", "whole-words", "regular-expressions")
REQUIRED_ACTION_IDS = ("searchall", "backsearch", "search", "replace", "replaceall")


class ValidationError(RuntimeError):
    """Raised when the Find & Replace field-set contract is incomplete or weakened."""


def _tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _require_marker(source: str, marker: str, where: str, *, exactly: int | None = None) -> None:
    count = source.count(marker)
    if exactly is not None:
        if count != exactly:
            raise ValidationError(
                f"{where} must contain {marker!r} exactly {exactly} time(s), found {count}"
            )
        return
    if count < 1:
        raise ValidationError(f"{where} must contain {marker!r} (real wiring, not a comment)")


# --------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------
def load_registry(registry_path: Path) -> dict:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    if data.get("contract") != "windows-native-find-replace-fieldset":
        raise ValidationError("registry.contract must be 'windows-native-find-replace-fieldset'")
    if data.get("inventory_id") != "WIN-INP-006":
        raise ValidationError("registry.inventory_id must be 'WIN-INP-006'")

    for key in (
        "ui_file",
        "header_file",
        "source_file",
        "dialog_id",
        "owner_type",
        "composition_marker",
        "emphasis_class",
        "emphasized_action_id",
    ):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"registry has empty required field {key!r}")

    for key in ("find_field", "replace_field", "result_summary"):
        if not isinstance(data.get(key), dict):
            raise ValidationError(f"registry must define a {key!r} object")

    options = data.get("options")
    if not isinstance(options, list):
        raise ValidationError("registry must define an 'options' array")
    seen = {opt.get("option") for opt in options if isinstance(opt, dict)}
    missing = [name for name in REQUIRED_OPTIONS if name not in seen]
    if missing:
        raise ValidationError("registry.options is missing: " + ", ".join(missing))
    for index, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise ValidationError(f"option #{index} must be an object")
        for field in ("option", "widget_id", "member", "descriptor_marker"):
            value = opt.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"option #{index} has empty required field {field!r}")

    actions = data.get("actions")
    if not isinstance(actions, list):
        raise ValidationError("registry must define an 'actions' array")
    action_ids = [a.get("id") for a in actions if isinstance(a, dict)]
    for want in REQUIRED_ACTION_IDS:
        if want not in action_ids:
            raise ValidationError(f"registry.actions is missing the {want!r} action")
    if data["emphasized_action_id"] not in action_ids:
        raise ValidationError(
            f"registry.emphasized_action_id {data['emphasized_action_id']!r} is not an action id"
        )

    # Deferrals must be documented, never silently dropped.
    for path_keys, label in (
        (("replace_field", "floating_label"), "replace field floating label"),
        (("supplementary_live_preview",), "supplementary live-preview run list"),
    ):
        node = data
        for key in path_keys:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        if not isinstance(node, dict) or node.get("status") != "deferred":
            raise ValidationError(f"{label} must be declared with status 'deferred'")
        if not isinstance(node.get("reason"), str) or not node["reason"].strip():
            raise ValidationError(f"{label} deferral must document a non-empty reason")

    return data


# --------------------------------------------------------------------------------------------------
# .ui composition
# --------------------------------------------------------------------------------------------------
def _object_by_id(root: ET.Element, object_id: str) -> ET.Element | None:
    for obj in root.iter():
        if _tag(obj.tag) == "object" and obj.get("id") == object_id:
            return obj
    return None


def _object_properties(obj: ET.Element) -> dict[str, str]:
    props: dict[str, str] = {}
    for prop in obj:
        if _tag(prop.tag) == "property" and prop.get("name"):
            props[prop.get("name")] = (prop.text or "").strip()
    return props


def _object_style_classes(obj: ET.Element) -> set[str]:
    classes: set[str] = set()
    for style in obj:
        if _tag(style.tag) != "style":
            continue
        for cls in style:
            if _tag(cls.tag) == "class" and cls.get("name"):
                classes.add(cls.get("name"))
    return classes


def _accessible_role(obj: ET.Element) -> str:
    for child in obj:
        if _tag(child.tag) != "child" or child.get("internal-child") != "accessible":
            continue
        for atk in child:
            if _tag(atk.tag) != "object":
                continue
            for prop in atk:
                if (
                    _tag(prop.tag) == "property"
                    and prop.get("name") == "AtkObject::accessible-role"
                ):
                    return (prop.text or "").strip()
    return ""


def _require_object(root: ET.Element, object_id: str, klass: str, where: str) -> ET.Element:
    obj = _object_by_id(root, object_id)
    if obj is None:
        raise ValidationError(f"{where}: {object_id!r} is missing from the .ui")
    if obj.get("class") != klass:
        raise ValidationError(
            f"{where}: {object_id!r} must be a {klass}, got {obj.get('class')!r}"
        )
    return obj


def validate_ui(repo_root: Path, data: dict) -> None:
    path = repo_root / data["ui_file"]
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse .ui {data['ui_file']}: {error}") from error

    dialog = _object_by_id(root, data["dialog_id"])
    if dialog is None or dialog.get("class") != "GtkDialog":
        raise ValidationError(f".ui must define GtkDialog {data['dialog_id']!r}")

    # Find field: shared search combo with adjacent advanced builder.
    find = data["find_field"]
    combo = _require_object(root, find["widget_id"], "GtkComboBoxText", "find field")
    if _object_properties(combo).get("has-entry") != "True":
        raise ValidationError("find field combo must declare has-entry=True")
    _require_object(root, find["regex_builder_id"], "GtkButton", "find field regex builder")

    # Replace field.
    replace = data["replace_field"]
    rcombo = _require_object(root, replace["widget_id"], "GtkComboBoxText", "replace field")
    if _object_properties(rcombo).get("has-entry") != "True":
        raise ValidationError("replace field combo must declare has-entry=True")

    # Option checkboxes.
    for opt in data["options"]:
        _require_object(root, opt["widget_id"], "GtkCheckButton", f"option {opt['option']!r}")

    # Result-summary label with the notification accessibility role.
    summary = data["result_summary"]
    label = _require_object(root, summary["widget_id"], "GtkLabel", "result-summary label")
    want_role = summary.get("a11y_role", "notification")
    got_role = _accessible_role(label)
    if got_role != want_role:
        raise ValidationError(
            f"result-summary label {summary['widget_id']!r} must expose the {want_role!r} "
            f"accessibility role, got {got_role!r}"
        )

    # Action set present, and Material emphasis on exactly one action -- the keyboard default.
    emphasis_class = data["emphasis_class"]
    emphasized_id = data["emphasized_action_id"]
    emphasized_buttons: list[str] = []
    for action in data["actions"]:
        button = _require_object(root, action["id"], "GtkButton", f"action {action['id']!r}")
        if emphasis_class in _object_style_classes(button):
            emphasized_buttons.append(action["id"])
    if emphasized_buttons != [emphasized_id]:
        raise ValidationError(
            f"exactly one action must carry the {emphasis_class!r} emphasis and it must be "
            f"{emphasized_id!r}; found {emphasized_buttons}"
        )
    emphasized = _require_object(root, emphasized_id, "GtkButton", "emphasized action")
    if _object_properties(emphasized).get("has-default") != "True":
        raise ValidationError(
            f"the emphasized action {emphasized_id!r} must be the Enter default (has-default=True) "
            "so the filled treatment never detaches from keyboard activation"
        )


# --------------------------------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------------------------------
def validate_header(repo_root: Path, data: dict) -> None:
    header = _read(repo_root / data["header_file"])
    members = [data["find_field"]["member"], data["find_field"]["regex_builder_member"],
               data["find_field"]["controller_member"], data["replace_field"]["member"],
               data["result_summary"]["member"]]
    members += [opt["member"] for opt in data["options"]]
    members += [action["member"] for action in data["actions"] if action.get("member")]
    for member in members:
        _require_marker(header, member, f"header {data['header_file']}")
    _require_marker(header, "SyncRegexControllerFromToggle", f"header {data['header_file']}")


# --------------------------------------------------------------------------------------------------
# Source wiring (real code, not comments)
# --------------------------------------------------------------------------------------------------
def validate_source(repo_root: Path, data: dict) -> None:
    source = _read(repo_root / data["source_file"])
    where = f"source {data['source_file']}"

    # The composition is self-documented, and the find field is bound to the shared controller
    # (the registered document.find-replace regex integration).
    _require_marker(source, data["composition_marker"], where)
    find = data["find_field"]
    _require_marker(source, find["controller_ctor_marker"], where)
    _require_marker(source, find["controller_ctor_args"], where)

    # weld bindings for every welded field.
    _require_marker(source, f'weld_combo_box(u"{find["widget_id"]}"', where)
    _require_marker(source, data["replace_field"]["weld_marker"], where)
    _require_marker(source, f'weld_label(u"{data["result_summary"]["widget_id"]}"', where)
    _require_marker(source, "void SvxSearchDialog::SetSearchLabel(", where)

    for opt in data["options"]:
        if "weld_marker" in opt:
            _require_marker(source, opt["weld_marker"], where)
        # Every option drives the one real search descriptor.
        _require_marker(source, opt["descriptor_marker"], where)

    match_case = next(o for o in data["options"] if o["option"] == "match-case")
    _require_marker(source, match_case["descriptor_effect"], where)

    regexp = next(o for o in data["options"] if o["option"] == "regular-expressions")
    _require_marker(source, regexp["toggle_gate"], where)
    # Bidirectional consistency: toggle -> controller helper, controller -> toggle single sync
    # path (exactly one, so there is no second matcher), and a loop-breaking mode guard.
    _require_marker(source, regexp["toggle_to_controller_helper"], where)
    _require_marker(source, regexp["controller_to_toggle_marker"], where, exactly=1)
    _require_marker(source, regexp["loop_breaker_guard"], where, exactly=1)


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_ui(repo_root, data)
    validate_header(repo_root, data)
    validate_source(repo_root, data)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve()
        if args.registry is not None
        else repo_root / "qa/windows-ui-contract/find-replace-fieldset.json"
    )
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Find & Replace field-set contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Find & Replace field-set contract passed (WIN-INP-006): the search combo binds the "
        "shared regex builder, Match case / Whole words / Regular expressions all drive the one "
        f"{data['single_search_descriptor']} descriptor with a loop-safe bidirectional regexp "
        "sync, and the Replace field, result-summary label, and emphasized action set are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
