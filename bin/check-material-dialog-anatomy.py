#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the shared Material destructive-confirmation dialog anatomy.

The registry ``qa/windows-ui-contract/dialog-anatomy-policy.json`` names one shared weld-level
helper plus every real ``weld::MessageDialog`` destructive confirmation migrated onto it. This
checker enforces the composition and behavior contract of docs/design/08-dialogs.md 8.1:

* the helper ``.ui`` composes the modal footer in the shared order
  ``Help | spacer | safe secondary | destructive primary``;
* the destructive primary carries the ``destructive-action`` role (Material ``@error-container``)
  and a verb-named label -- never a bare "OK";
* the helper source binds the SAFE action as both the initial focus and the Enter default, so
  Enter/Space activation can never destroy data, and never binds the default to the destructive
  action; and
* every registered migration includes the helper header and dispatches through the shared entry
  point instead of an ad-hoc message box.

It is source evidence only: no native build, dialog pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/dialog-anatomy-policy.json"

# GTK response codes as written in .ui action-widgets, mapped to the VCL RET_* names the C++ helper
# and callers use (see vcl/source/window/builder.cxx and include/vcl/vclenum.hxx).
RET_TO_GTK = {
    "RET_OK": -5,
    "RET_CANCEL": -6,
    "RET_CLOSE": -7,
    "RET_YES": -8,
    "RET_NO": -9,
    "RET_HELP": -11,
}
HELP_RESPONSE = "RET_HELP"

# Labels that are not verbs: a destructive primary must never degrade to one of these.
NON_VERB_LABELS = frozenset({"ok", "yes", "no", "cancel", "close", "apply", "help", "retry"})

MIN_MIGRATIONS = 3
MAX_MIGRATIONS = 10


class ValidationError(RuntimeError):
    """Raised when the destructive-confirmation anatomy contract is incomplete or weakened."""


def _tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def _clean_label(raw: str) -> str:
    """Strip mnemonic markers and surrounding punctuation from a button label."""

    return raw.replace("_", "").replace("&", "").replace("~", "").strip().strip("._ ").lower()


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

    helper = data.get("helper")
    if not isinstance(helper, dict):
        raise ValidationError("registry must define a 'helper' object")
    required_helper = (
        "ui_file",
        "dialog_id",
        "message_type",
        "source",
        "header",
        "entry_point",
        "safe_response",
        "destructive_response",
        "footer_order",
        "destructive_role_class",
    )
    missing = [key for key in required_helper if key not in helper]
    if missing:
        raise ValidationError("helper is missing keys: " + ", ".join(missing))

    for key in ("safe_response", "destructive_response"):
        if helper[key] not in RET_TO_GTK:
            raise ValidationError(f"helper.{key} must be a known RET_* name, got {helper[key]!r}")
    if helper["safe_response"] == helper["destructive_response"]:
        raise ValidationError("helper safe and destructive responses must differ")

    footer = helper["footer_order"]
    if footer != ["help", "safe", "destructive"]:
        raise ValidationError(
            "helper.footer_order must be [help, safe, destructive] "
            "(Help | spacer | safe secondary | destructive primary)"
        )

    migrations = data.get("migrations")
    if not isinstance(migrations, list):
        raise ValidationError("registry must define a 'migrations' array")
    if not (MIN_MIGRATIONS <= len(migrations) <= MAX_MIGRATIONS):
        raise ValidationError(
            f"registry must list between {MIN_MIGRATIONS} and {MAX_MIGRATIONS} migrations, "
            f"found {len(migrations)}"
        )
    seen_ids: set[str] = set()
    for index, migration in enumerate(migrations):
        if not isinstance(migration, dict):
            raise ValidationError(f"migration #{index} must be an object")
        for field in ("id", "file", "act", "verb"):
            value = migration.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"migration #{index} has empty required field {field!r}")
        if migration["id"] in seen_ids:
            raise ValidationError(f"duplicate migration id: {migration['id']}")
        seen_ids.add(migration["id"])
    return data


# --------------------------------------------------------------------------------------------------
# Helper .ui composition
# --------------------------------------------------------------------------------------------------
def _find_dialog(root: ET.Element, dialog_id: str) -> ET.Element:
    for obj in root.iter():
        if _tag(obj.tag) == "object" and obj.get("id") == dialog_id:
            return obj
    raise ValidationError(f"helper .ui has no object with id {dialog_id!r}")


def _object_style_classes(obj: ET.Element) -> set[str]:
    classes: set[str] = set()
    for style in obj:
        if _tag(style.tag) != "style":
            continue
        for cls in style:
            if _tag(cls.tag) == "class" and cls.get("name"):
                classes.add(cls.get("name"))
    return classes


def _button_by_id(root: ET.Element, button_id: str) -> ET.Element:
    for obj in root.iter():
        if (
            _tag(obj.tag) == "object"
            and obj.get("class") == "GtkButton"
            and obj.get("id") == button_id
        ):
            return obj
    raise ValidationError(f"helper .ui has no GtkButton with id {button_id!r}")


def _button_label(button: ET.Element) -> str:
    for prop in button:
        if _tag(prop.tag) == "property" and prop.get("name") == "label":
            return prop.text or ""
    return ""


def validate_helper_ui(repo_root: Path, helper: dict) -> None:
    path = repo_root / helper["ui_file"]
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse helper .ui {helper['ui_file']}: {error}") from error

    dialog = _find_dialog(root, helper["dialog_id"])
    if dialog.get("class") != "GtkMessageDialog":
        raise ValidationError(
            f"helper dialog {helper['dialog_id']} must be a GtkMessageDialog, "
            f"got {dialog.get('class')!r}"
        )

    message_type = ""
    for prop in dialog.iter():
        if _tag(prop.tag) == "property" and prop.get("name") == "message-type":
            message_type = (prop.text or "").strip().lower()
            break
    if message_type != helper["message_type"]:
        raise ValidationError(
            f"helper dialog message-type must be {helper['message_type']!r}, got {message_type!r}"
        )

    # Footer order and response roles come from <action-widgets>.
    action_widgets = []
    for widgets in dialog.iter():
        if _tag(widgets.tag) != "action-widgets":
            continue
        for aw in widgets:
            if _tag(aw.tag) == "action-widget":
                action_widgets.append(((aw.text or "").strip(), aw.get("response", "")))
    ordered_ids = [name for name, _ in action_widgets]
    if ordered_ids != helper["footer_order"]:
        raise ValidationError(
            "helper footer order must be "
            f"{helper['footer_order']} (Help | spacer | safe secondary | destructive primary), "
            f"got {ordered_ids}"
        )

    expected_response = {
        "help": HELP_RESPONSE,
        "safe": helper["safe_response"],
        "destructive": helper["destructive_response"],
    }
    responses = dict(action_widgets)
    for name, ret_name in expected_response.items():
        want = str(RET_TO_GTK[ret_name])
        got = responses.get(name)
        if got != want:
            raise ValidationError(
                f"helper action-widget {name!r} must use response {want} ({ret_name}), got {got!r}"
            )

    # The destructive primary carries the error-container role and a verb-named label.
    destructive = _button_by_id(root, "destructive")
    if helper["destructive_role_class"] not in _object_style_classes(destructive):
        raise ValidationError(
            "helper destructive button must carry the "
            f"{helper['destructive_role_class']!r} style class (Material @error-container)"
        )
    destructive_label = _clean_label(_button_label(destructive))
    if not destructive_label:
        raise ValidationError("helper destructive button must declare a default label")
    if destructive_label in NON_VERB_LABELS:
        raise ValidationError(
            f"helper destructive button label must name a verb, not {destructive_label!r}"
        )

    # The safe secondary must carry a real label and must NOT be styled destructive.
    safe = _button_by_id(root, "safe")
    if not _clean_label(_button_label(safe)):
        raise ValidationError("helper safe button must declare a label")
    if helper["destructive_role_class"] in _object_style_classes(safe):
        raise ValidationError("helper safe button must not carry the destructive-action role")


# --------------------------------------------------------------------------------------------------
# Helper source behavior
# --------------------------------------------------------------------------------------------------
def validate_helper_source(repo_root: Path, helper: dict) -> None:
    source = _read(repo_root / helper["source"])

    required = {
        "loads the helper .ui": helper["ui_file"].split("/")[-1].replace(".ui", ""),
        "welds the helper dialog id": helper["dialog_id"],
        "sets the object (primary) text": "set_primary_text(",
        "sets the consequence (secondary) text": "set_secondary_text(",
        "welds the destructive button": 'weld_button(u"destructive"',
        "sets the destructive verb label": "->set_label(",
        "welds the safe button": 'weld_button(u"safe"',
        "returns destructive iff RET_OK": "== RET_OK",
    }
    for description, marker in required.items():
        if marker not in source:
            raise ValidationError(f"helper source must ({description}): missing {marker!r}")

    destructive_default = f"set_default_response({helper['destructive_response']})"
    if destructive_default in source:
        raise ValidationError(
            "helper source must NOT bind the Enter default to the destructive action: "
            f"found {destructive_default!r}"
        )
    safe_default = f"set_default_response({helper['safe_response']})"
    if safe_default not in source:
        raise ValidationError(
            f"helper source must bind the Enter default to the safe action: missing {safe_default!r}"
        )

    if "xSafe->grab_focus()" not in source:
        raise ValidationError(
            "helper source must place the initial focus on the safe action: missing "
            "xSafe->grab_focus()"
        )
    if "xDestructive->grab_focus()" in source:
        raise ValidationError(
            "helper source must NOT place the initial focus on the destructive action"
        )


# --------------------------------------------------------------------------------------------------
# Migrated call sites
# --------------------------------------------------------------------------------------------------
def validate_migrations(repo_root: Path, data: dict) -> None:
    helper = data["helper"]
    header = helper["header"]
    entry_point = helper["entry_point"]

    # C++ sources spell the header without the leading "include/" search-root prefix.
    include_spelling = header[len("include/") :] if header.startswith("include/") else header

    calls_per_file: dict[str, int] = {}
    for migration in data["migrations"]:
        calls_per_file[migration["file"]] = calls_per_file.get(migration["file"], 0) + 1

    for file_path, expected_calls in sorted(calls_per_file.items()):
        source = _read(repo_root / file_path)
        if f"<{include_spelling}>" not in source:
            raise ValidationError(
                f"migrated call site {file_path} must include the helper header "
                f"<{include_spelling}>"
            )
        qualified = f"sfx2::{entry_point}("
        found = source.count(qualified)
        if found < expected_calls:
            raise ValidationError(
                f"migrated call site {file_path} must dispatch {expected_calls} confirmation(s) "
                f"through {qualified}, found {found}"
            )


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_helper_ui(repo_root, data["helper"])
    validate_helper_source(repo_root, data["helper"])
    validate_migrations(repo_root, data)
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
        else repo_root / "qa/windows-ui-contract/dialog-anatomy-policy.json"
    )
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Material dialog anatomy contract failed:\n{error}", file=sys.stderr)
        return 1

    migrations = data["migrations"]
    print(
        "Material dialog anatomy contract passed: shared destructive-confirmation helper "
        f"composes Help | spacer | safe | destructive, binds the safe action as focus + Enter "
        f"default, and covers {len(migrations)} migrated confirmation(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
