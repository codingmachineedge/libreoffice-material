#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed Help/About & legacy-dialog family contract (WIN-SYS-015).

``qa/windows-ui-contract/help-about-family.json`` is a composition-PINNING
contract (calc-chrome idiom) over the existing upstream cui Help/About and
legacy/optional ``.ui`` files. It claims no native build, dialog pixels, or
Material redraw -- ``runtime_verified`` is false throughout. Four evidence layers:

* ``anatomy_pinned`` -- the real cui ``.ui`` trees are parsed fail-closed and the
  informational Help/About anatomy is pinned: the modal ``GtkDialog`` root, the
  single-dismiss action-widget (About = ``btnClose`` response ``-7``; Tip =
  ``btnOk`` response ``-5``), and the named link/nav widgets with their classes.
  ``AboutDialog`` declares ``modal=True`` in its ``.ui``; ``TipOfTheDayDialog``
  declares no ``.ui`` modal property, so its modal claim is keyed off the CSV
  KeepModal row instead of a ``.ui`` property.
* ``notification_policy`` -- the shared ``dialog-notification-policy.csv`` keeps
  the About/Tip rows ``native-exclusion`` (KeepModal); a flip fails closed.
* ``no_destructive_role`` -- the family never appears as a destructive migration
  in ``dialog-anatomy-policy.json`` (these are informational, not destructive).
* ``family`` -- ``ui-registry.json`` maps every WIN-SYS-015 UI-file surface to
  ``inventory_id == WIN-SYS-015`` / ``mapped_by == override``; a drift back to the
  unassigned bucket fails closed (the registry progress this row measures).
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
REGISTRY_PATH = "qa/windows-ui-contract/help-about-family.json"
POLICY_REGISTRY = "qa/windows-ui-contract/dialog-notification-policy.csv"
ANATOMY_REGISTRY = "qa/windows-ui-contract/dialog-anatomy-policy.json"
UI_REGISTRY = "qa/windows-ui-contract/ui-registry.json"
INVENTORY_ID = "WIN-SYS-015"

CSV_FIELDS = (
    "ui_path",
    "object_id",
    "widget_class",
    "policy",
    "notification_profile",
    "exclusion_reason",
)
EXCLUSION_POLICY = "native-exclusion"


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
    paths: set[str] = {POLICY_REGISTRY, ANATOMY_REGISTRY, UI_REGISTRY}
    for entry in registry.get("anatomy_pinned", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("ui_file"), str):
            paths.add(entry["ui_file"])
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
# .ui helpers (plain GtkBuilder, no namespace)
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


def _top_level_object(root: ET.Element, object_id: str, widget_class: str) -> ET.Element | None:
    for child in root:
        if child.tag != "object":
            continue
        if child.get("id") == object_id and child.get("class") == widget_class:
            return child
    return None


def _find_object(root: ET.Element, object_id: str) -> ET.Element | None:
    for node in root.iter("object"):
        if node.get("id") == object_id:
            return node
    return None


def _object_bool_property(obj: ET.Element, prop_name: str) -> bool:
    for prop in obj.findall("property"):
        if prop.get("name") == prop_name:
            return (prop.text or "").strip().lower() == "true"
    return False


def _ui_footer(root: ET.Element) -> list[dict[str, str]]:
    footer: list[dict[str, str]] = []
    for action_widgets in root.iter("action-widgets"):
        for widget in action_widgets.findall("action-widget"):
            footer.append(
                {"response": (widget.get("response") or ""), "widget": (widget.text or "").strip()}
            )
    return footer


# --------------------------------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------------------------------
def _csv_locator_map(text: str | None, errors: list[str]) -> dict[tuple[str, str], dict[str, str]]:
    if text is None:
        errors.append(f"policy_registry:{POLICY_REGISTRY} missing")
        return {}
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        errors.append("policy_registry:header drift from the shared CSV schema")
        return {}
    mapping: dict[tuple[str, str], dict[str, str]] = {}
    for row in reader:
        mapping[(row.get("ui_path") or "", row.get("object_id") or "")] = row
    return mapping


# --------------------------------------------------------------------------------------------------
# Layer validators
# --------------------------------------------------------------------------------------------------
def _validate_anatomy(
    registry: Mapping[str, Any], contents: Mapping[str, str],
    csv_map: Mapping[tuple[str, str], dict[str, str]], errors: list[str],
) -> None:
    entries = registry.get("anatomy_pinned")
    if not isinstance(entries, list) or not entries:
        errors.append("anatomy_pinned:non-empty array required")
        return
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("anatomy_pinned:entry:object required")
            continue
        entry_id = entry.get("id")
        where = f"anatomy_pinned[{entry_id}]"
        ui_file = entry.get("ui_file")
        object_id = entry.get("object_id")
        widget_class = entry.get("widget_class")
        if not isinstance(ui_file, str) or not isinstance(object_id, str) or not isinstance(widget_class, str):
            errors.append(f"{where}:ui_file/object_id/widget_class strings required")
            continue

        root = _parse_xml(contents.get(ui_file), f"{where}:ui", errors)
        if root is None:
            continue

        dialog = _top_level_object(root, object_id, widget_class)
        if dialog is None:
            errors.append(f"{where}:top-level {widget_class} {object_id!r} missing in {ui_file}")
            continue

        # Modal claim: from the .ui property, or (Tip of the Day) keyed off the CSV KeepModal row.
        modal_source = entry.get("modal_source")
        if modal_source == "ui":
            if not _object_bool_property(dialog, "modal"):
                errors.append(f"{where}:.ui must declare modal=True (modal_source=ui)")
        elif modal_source == "csv":
            row = csv_map.get((ui_file, object_id))
            if row is None:
                errors.append(f"{where}:modal_source=csv but no CSV policy row for {ui_file}#{object_id}")
            elif row.get("policy") != EXCLUSION_POLICY:
                errors.append(
                    f"{where}:modal_source=csv but CSV policy is {row.get('policy')!r}, "
                    f"must be {EXCLUSION_POLICY!r} (KeepModal keeps the dialog modal)"
                )
        else:
            errors.append(f"{where}:modal_source must be 'ui' or 'csv'")

        # Single-dismiss footer.
        expected_footer = entry.get("footer")
        if not isinstance(expected_footer, list) or len(expected_footer) != 1:
            errors.append(f"{where}:footer must be a single-dismiss array")
        else:
            actual_footer = _ui_footer(root)
            if actual_footer != [
                {"response": e.get("response"), "widget": e.get("widget")}
                for e in expected_footer if isinstance(e, dict)
            ]:
                errors.append(
                    f"{where}:footer drift: pinned "
                    f"{[(e.get('widget'), e.get('response')) for e in expected_footer]} "
                    f"but found {[(e['widget'], e['response']) for e in actual_footer]}"
                )

        # Named link / nav / dismiss widgets present with the pinned class.
        widgets = entry.get("widgets")
        if not isinstance(widgets, list) or not widgets:
            errors.append(f"{where}:widgets non-empty array required")
            continue
        for index, widget in enumerate(widgets):
            if not isinstance(widget, dict):
                errors.append(f"{where}:widget #{index} object required")
                continue
            wid = widget.get("id")
            wclass = widget.get("widget_class")
            if not isinstance(wid, str) or not isinstance(wclass, str):
                errors.append(f"{where}:widget #{index} id/widget_class strings required")
                continue
            obj = _find_object(root, wid)
            if obj is None:
                errors.append(f"{where}:widget {wid!r} missing in {ui_file}")
            elif obj.get("class") != wclass:
                errors.append(
                    f"{where}:widget {wid!r} class is {obj.get('class')!r}, expected {wclass!r}"
                )


def _validate_notification_policy(
    registry: Mapping[str, Any], csv_map: Mapping[tuple[str, str], dict[str, str]],
    errors: list[str],
) -> None:
    block = registry.get("notification_policy")
    if not isinstance(block, dict):
        errors.append("notification_policy:object required")
        return
    if block.get("policy") != EXCLUSION_POLICY:
        errors.append(f"notification_policy:policy must be {EXCLUSION_POLICY!r}")
    rows = block.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("notification_policy:rows non-empty array required")
        return
    for index, entry in enumerate(rows):
        if not isinstance(entry, dict):
            errors.append(f"notification_policy:row #{index} object required")
            continue
        ui_path = entry.get("ui_path")
        object_id = entry.get("object_id")
        if not isinstance(ui_path, str) or not isinstance(object_id, str):
            errors.append(f"notification_policy:row #{index} ui_path/object_id strings required")
            continue
        row = csv_map.get((ui_path, object_id))
        if row is None:
            errors.append(f"notification_policy:{ui_path}#{object_id}:no CSV policy row")
        elif row.get("policy") != EXCLUSION_POLICY:
            errors.append(
                f"notification_policy:{ui_path}#{object_id}:CSV policy is {row.get('policy')!r}, "
                f"must be {EXCLUSION_POLICY!r} (Help/About dialogs stay modal, never routed)"
            )


def _validate_no_destructive_role(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    block = registry.get("no_destructive_role")
    if not isinstance(block, dict):
        errors.append("no_destructive_role:object required")
        return
    tokens = block.get("forbidden_tokens")
    if not isinstance(tokens, list) or not tokens:
        errors.append("no_destructive_role:forbidden_tokens non-empty array required")
        return
    anatomy_text = contents.get(ANATOMY_REGISTRY)
    if anatomy_text is None:
        errors.append(f"no_destructive_role:{ANATOMY_REGISTRY} missing")
        return
    try:
        anatomy = json.loads(anatomy_text)
    except json.JSONDecodeError as error:
        errors.append(f"no_destructive_role:{ANATOMY_REGISTRY} not valid JSON: {error}")
        return
    migrations_text = json.dumps(anatomy.get("migrations", []), ensure_ascii=False)
    for token in tokens:
        if isinstance(token, str) and token in migrations_text:
            errors.append(
                f"no_destructive_role:Help/About surface token {token!r} appears in the "
                f"{ANATOMY_REGISTRY} destructive migrations (must never be a destructive dialog)"
            )


def _validate_family(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    family = registry.get("family")
    if not isinstance(family, list) or not family:
        errors.append("family:non-empty array required")
        return
    expected = registry.get("expected_family")
    if isinstance(expected, int) and expected != len(family):
        errors.append(f"family:expected_family is {expected} but {len(family)} declared")

    ui_registry_text = contents.get(UI_REGISTRY)
    if ui_registry_text is None:
        errors.append(f"family:{UI_REGISTRY} missing")
        return
    try:
        ui_registry = json.loads(ui_registry_text)
    except json.JSONDecodeError as error:
        errors.append(f"family:{UI_REGISTRY} not valid JSON: {error}")
        return
    surfaces = ui_registry.get("surfaces")
    if not isinstance(surfaces, list):
        errors.append(f"family:{UI_REGISTRY} surfaces section must be a list")
        return
    index: dict[str, Mapping[str, Any]] = {}
    for surface in surfaces:
        if isinstance(surface, dict) and isinstance(surface.get("surface"), str):
            index[surface["surface"]] = surface

    seen: set[str] = set()
    for entry in family:
        if not isinstance(entry, dict) or not isinstance(entry.get("surface"), str):
            errors.append("family:entry:surface string required")
            continue
        key = entry["surface"]
        if key in seen:
            errors.append(f"family:{key}:duplicate family surface")
        seen.add(key)
        mapped = index.get(key)
        if mapped is None:
            errors.append(f"family:{key}:not found among ui-registry surfaces")
            continue
        if mapped.get("inventory_id") != INVENTORY_ID:
            errors.append(
                f"family:{key}:inventory_id is {mapped.get('inventory_id')!r}, "
                f"must be {INVENTORY_ID!r} (assigned out of the unassigned baseline)"
            )
        if mapped.get("mapped_by") != "override":
            errors.append(
                f"family:{key}:mapped_by is {mapped.get('mapped_by')!r}, must be 'override'"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-help-about-family":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")
    if registry.get("policy_registry") != POLICY_REGISTRY:
        errors.append("registry:policy_registry:unexpected path")
    if registry.get("ui_registry") != UI_REGISTRY:
        errors.append("registry:ui_registry:unexpected path")
    if registry.get("inventory_id") != INVENTORY_ID:
        errors.append(f"registry:inventory_id:must be {INVENTORY_ID}")

    csv_map = _csv_locator_map(contents.get(POLICY_REGISTRY), errors)
    _validate_anatomy(registry, contents, csv_map, errors)
    _validate_notification_policy(registry, csv_map, errors)
    _validate_no_destructive_role(registry, contents, errors)
    _validate_family(registry, contents, errors)

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
        print(f"Help/About family contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    family = registry.get("family", [])
    anatomy = registry.get("anatomy_pinned", [])
    print(
        "Help/About family contract passed: "
        f"{len(anatomy)} informational dialog(s) anatomy-pinned, and "
        f"{len(family)} WIN-SYS-015 surface(s) confirmed override-assigned in the closure registry "
        "(Help/About family moved out of the unassigned baseline; KeepModal preserved)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
