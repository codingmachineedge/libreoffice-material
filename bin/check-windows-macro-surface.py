#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed macro-surface contract (WIN-SYS-006).

``qa/windows-ui-contract/macro-surface.json`` pins the macro manager / organizer /
IDE and macro-security surfaces in three parts, all verifiable build-free with py
static checks over comment-stripped source, XML, and the shared policy CSV.
``runtime_verified`` is false throughout: no native build, dialog pixels, or
Material redraw is claimed.

* ``shared_helper`` -- the exported ``sfx2::ConfirmDestructiveAction`` entry point
  and ``DestructiveConfirmation`` struct (the Material destructive-confirmation
  machinery basctl links against) still exist in the header.
* ``destructive_conversions`` -- the single shared basctl ``QueryDel()`` funnel,
  through which every Basic-IDE macro/dialog/library/module delete-or-overwrite
  confirmation flows, is dispatched through that helper: the include, the params
  build, the per-caller verb, and the shared consequence are present; the raw
  ``VclMessageType::Question`` / ``VclButtonsType::YesNo`` box is gone; each of the
  five call sites passes the correct verb (``Overwrite`` for the macro overwrite,
  ``Delete`` for the four deletions); and each ``RID_STR_QUERYDEL*`` primary
  wording -- including the library-``reference to`` distinction -- is preserved.
* ``security_prompt`` -- the macro-EXECUTION prompt keeps its safe default: in the
  ``.ui`` the ``cancel`` (``Disable Macros``) button carries ``has-default`` and the
  ``ok`` (``Enable Macros``) button does not, and in source the safe button takes
  the initial focus (``mxDisableBtn->grab_focus()``) while the unsafe button never
  does -- so keyboard activation can never silently run untrusted macros.
* ``modal_surface_ledger`` -- a read-only subset assertion that every row-owned
  macro/organizer/security dialog root stays ``native-exclusion`` (kept modal) in
  the shared ``dialog-notification-policy.csv``.
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
REGISTRY_PATH = "qa/windows-ui-contract/macro-surface.json"
POLICY_REGISTRY = "qa/windows-ui-contract/dialog-notification-policy.csv"

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
    paths: set[str] = {POLICY_REGISTRY}
    for key in ("helper_header",):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    helper = registry.get("shared_helper")
    if isinstance(helper, dict) and isinstance(helper.get("file"), str):
        paths.add(helper["file"])
    conversions = registry.get("destructive_conversions")
    if isinstance(conversions, dict):
        for key in ("funnel_file", "strings_file"):
            value = conversions.get(key)
            if isinstance(value, str):
                paths.add(value)
        for section in ("present_markers", "absent_markers", "preserved_strings"):
            for marker in conversions.get(section, []) or []:
                if isinstance(marker, dict) and isinstance(marker.get("file"), str):
                    paths.add(marker["file"])
    prompt = registry.get("security_prompt")
    if isinstance(prompt, dict):
        for key in ("ui_file", "source_file"):
            value = prompt.get(key)
            if isinstance(value, str):
                paths.add(value)
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


def stripped_code(
    rel: str | None, contents: Mapping[str, str], cache: dict[str, str | None]
) -> str | None:
    if not isinstance(rel, str):
        return None
    if rel not in cache:
        text = contents.get(rel)
        cache[rel] = _strip_comments(text) if text is not None else None
    return cache[rel]


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
# Marker helpers
# --------------------------------------------------------------------------------------------------
def _require_present(
    code: str | None, pattern: str, where: str, errors: list[str]
) -> None:
    if code is None:
        errors.append(f"{where}:source file missing")
        return
    if pattern not in code:
        errors.append(f"{where}:missing real code marker {pattern!r}")


def _require_absent(
    code: str | None, pattern: str, where: str, errors: list[str]
) -> None:
    if code is None:
        errors.append(f"{where}:source file missing")
        return
    if pattern in code:
        errors.append(f"{where}:forbidden marker still present {pattern!r}")


def _markers(section: object) -> list[dict[str, Any]]:
    return [m for m in (section or []) if isinstance(m, dict)]


# --------------------------------------------------------------------------------------------------
# Part validators
# --------------------------------------------------------------------------------------------------
def _validate_shared_helper(
    registry: Mapping[str, Any], stripped: dict[str, str | None],
    contents: Mapping[str, str], errors: list[str],
) -> None:
    helper = registry.get("shared_helper")
    if not isinstance(helper, dict):
        errors.append("shared_helper:object required")
        return
    file_path = helper.get("file")
    markers = _markers(helper.get("markers"))
    if not isinstance(file_path, str):
        errors.append("shared_helper:file string required")
        return
    if not markers:
        errors.append("shared_helper:markers non-empty array required")
    code = stripped_code(file_path, contents, stripped)
    for index, marker in enumerate(markers):
        pattern = marker.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"shared_helper:marker #{index} pattern string required")
            continue
        _require_present(code, pattern, f"shared_helper:marker #{index}", errors)


def _validate_conversions(
    registry: Mapping[str, Any], stripped: dict[str, str | None],
    contents: Mapping[str, str], errors: list[str],
) -> None:
    conversions = registry.get("destructive_conversions")
    if not isinstance(conversions, dict):
        errors.append("destructive_conversions:object required")
        return

    for index, marker in enumerate(_markers(conversions.get("present_markers"))):
        pattern = marker.get("pattern")
        code = stripped_code(marker.get("file"), contents, stripped)
        if not isinstance(pattern, str):
            errors.append(f"destructive_conversions:present_marker #{index} pattern required")
            continue
        _require_present(code, pattern, f"destructive_conversions:present_marker #{index}", errors)

    for index, marker in enumerate(_markers(conversions.get("absent_markers"))):
        pattern = marker.get("pattern")
        code = stripped_code(marker.get("file"), contents, stripped)
        if not isinstance(pattern, str):
            errors.append(f"destructive_conversions:absent_marker #{index} pattern required")
            continue
        _require_absent(code, pattern, f"destructive_conversions:absent_marker #{index}", errors)

    funnel = conversions.get("funnel_file")
    funnel_code = stripped_code(funnel, contents, stripped)
    verb_labels = conversions.get("verb_labels")
    if not isinstance(verb_labels, dict):
        errors.append("destructive_conversions:verb_labels object required")
        verb_labels = {}

    call_sites = conversions.get("call_sites")
    if not isinstance(call_sites, list) or not call_sites:
        errors.append("destructive_conversions:call_sites non-empty array required")
    else:
        seen_ids: set[str] = set()
        for index, site in enumerate(call_sites):
            if not isinstance(site, dict):
                errors.append(f"destructive_conversions:call_site #{index} object required")
                continue
            site_id = site.get("id")
            verb = site.get("verb")
            pattern = site.get("pattern")
            where = f"destructive_conversions:call_site[{site_id}]"
            if not isinstance(site_id, str) or not site_id:
                errors.append(f"destructive_conversions:call_site #{index} id required")
                continue
            if site_id in seen_ids:
                errors.append(f"{where}:duplicate call-site id")
            seen_ids.add(site_id)
            if not isinstance(pattern, str):
                errors.append(f"{where}:pattern string required")
                continue
            _require_present(funnel_code, pattern, where, errors)
            # The declared verb must map to a real label resource and that label token must
            # actually appear inside the pinned call-site expression (so the correct verb, and only
            # the correct verb, is passed per caller -- Overwrite for the macro overwrite, Delete
            # for the deletions).
            if verb not in verb_labels:
                errors.append(f"{where}:verb {verb!r} not declared in verb_labels")
            else:
                label = verb_labels[verb]
                if not isinstance(label, str) or label not in pattern:
                    errors.append(
                        f"{where}:call-site does not pass the {verb!r} verb label {label!r}"
                    )
                for other_verb, other_label in verb_labels.items():
                    if other_verb != verb and isinstance(other_label, str) and other_label in pattern:
                        errors.append(
                            f"{where}:call-site passes the wrong verb label {other_label!r} "
                            f"(expected {verb!r})"
                        )

    for index, marker in enumerate(_markers(conversions.get("preserved_strings"))):
        pattern = marker.get("pattern")
        code = stripped_code(marker.get("file"), contents, stripped)
        if not isinstance(pattern, str):
            errors.append(f"destructive_conversions:preserved_string #{index} pattern required")
            continue
        _require_present(code, pattern, f"destructive_conversions:preserved_string #{index}", errors)


def _validate_security_prompt(
    registry: Mapping[str, Any], stripped: dict[str, str | None],
    contents: Mapping[str, str], errors: list[str],
) -> None:
    prompt = registry.get("security_prompt")
    if not isinstance(prompt, dict):
        errors.append("security_prompt:object required")
        return

    ui_file = prompt.get("ui_file")
    object_id = prompt.get("object_id")
    widget_class = prompt.get("widget_class")
    if not isinstance(ui_file, str) or not isinstance(object_id, str) or not isinstance(widget_class, str):
        errors.append("security_prompt:ui_file/object_id/widget_class strings required")
        return

    ui_root = _parse_xml(contents.get(ui_file), "security_prompt:ui", errors)
    if ui_root is not None:
        dialog = _top_level_object(ui_root, object_id, widget_class)
        if dialog is None:
            errors.append(
                f"security_prompt:top-level {widget_class} {object_id!r} missing in {ui_file}"
            )

        expected_footer = prompt.get("footer")
        if not isinstance(expected_footer, list) or not expected_footer:
            errors.append("security_prompt:footer non-empty array required")
        else:
            actual_footer = _ui_footer(ui_root)
            if actual_footer != [
                {"response": e.get("response"), "widget": e.get("widget")}
                for e in expected_footer if isinstance(e, dict)
            ]:
                errors.append(
                    f"security_prompt:footer drift: pinned "
                    f"{[(e.get('widget'), e.get('response')) for e in expected_footer]} "
                    f"but found {[(e['widget'], e['response']) for e in actual_footer]}"
                )

        safe = prompt.get("safe_button")
        if isinstance(safe, dict) and isinstance(safe.get("id"), str):
            btn = _find_object(ui_root, safe["id"])
            if btn is None:
                errors.append(f"security_prompt:safe button {safe['id']!r} missing in {ui_file}")
            elif not _object_bool_property(btn, "has-default"):
                errors.append(
                    f"security_prompt:safe button {safe['id']!r} must carry has-default=True "
                    "(the Disable action is the GTK default)"
                )
        else:
            errors.append("security_prompt:safe_button.id string required")

        unsafe = prompt.get("unsafe_button")
        if isinstance(unsafe, dict) and isinstance(unsafe.get("id"), str):
            btn = _find_object(ui_root, unsafe["id"])
            if btn is None:
                errors.append(f"security_prompt:unsafe button {unsafe['id']!r} missing in {ui_file}")
            elif _object_bool_property(btn, "has-default"):
                errors.append(
                    f"security_prompt:unsafe button {unsafe['id']!r} must NOT carry has-default "
                    "(Enable Macros must never be the default action)"
                )
        else:
            errors.append("security_prompt:unsafe_button.id string required")

    code = stripped_code(prompt.get("source_file"), contents, stripped)
    for index, marker in enumerate(_markers(prompt.get("source_present_markers"))):
        pattern = marker.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"security_prompt:source_present_marker #{index} pattern required")
            continue
        _require_present(code, pattern, f"security_prompt:source_present_marker #{index}", errors)
    for index, marker in enumerate(_markers(prompt.get("source_absent_markers"))):
        pattern = marker.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"security_prompt:source_absent_marker #{index} pattern required")
            continue
        _require_absent(code, pattern, f"security_prompt:source_absent_marker #{index}", errors)


def _validate_modal_ledger(
    registry: Mapping[str, Any], csv_map: Mapping[tuple[str, str], dict[str, str]],
    errors: list[str],
) -> None:
    ledger = registry.get("modal_surface_ledger")
    if not isinstance(ledger, dict):
        errors.append("modal_surface_ledger:object required")
        return
    if ledger.get("policy") != EXCLUSION_POLICY:
        errors.append(
            f"modal_surface_ledger:policy must be {EXCLUSION_POLICY!r}"
        )
    roots = ledger.get("roots")
    if not isinstance(roots, list) or not roots:
        errors.append("modal_surface_ledger:roots non-empty array required")
        return
    seen: set[str] = set()
    for index, root in enumerate(roots):
        if not isinstance(root, dict):
            errors.append(f"modal_surface_ledger:root #{index} object required")
            continue
        ui_path = root.get("ui_path")
        object_id = root.get("object_id")
        if not isinstance(ui_path, str) or not isinstance(object_id, str):
            errors.append(f"modal_surface_ledger:root #{index} ui_path/object_id strings required")
            continue
        if ui_path in seen:
            errors.append(f"modal_surface_ledger:{ui_path}:duplicate root")
        seen.add(ui_path)
        row = csv_map.get((ui_path, object_id))
        if row is None:
            errors.append(
                f"modal_surface_ledger:{ui_path}#{object_id}:no CSV policy row "
                "(a macro/organizer/security root must stay registered and modal)"
            )
        elif row.get("policy") != EXCLUSION_POLICY:
            errors.append(
                f"modal_surface_ledger:{ui_path}#{object_id}:CSV policy is {row.get('policy')!r}, "
                f"must be {EXCLUSION_POLICY!r} (must never route to a notification form)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-macro-surface":
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

    stripped: dict[str, str | None] = {}
    _validate_shared_helper(registry, stripped, contents, errors)
    _validate_conversions(registry, stripped, contents, errors)
    _validate_security_prompt(registry, stripped, contents, errors)

    csv_map = _csv_locator_map(contents.get(POLICY_REGISTRY), errors)
    _validate_modal_ledger(registry, csv_map, errors)

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
        print(f"Macro-surface contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    conversions = registry.get("destructive_conversions", {})
    sites = conversions.get("call_sites", []) if isinstance(conversions, dict) else []
    roots = registry.get("modal_surface_ledger", {}).get("roots", [])
    print(
        "Macro-surface contract passed: "
        f"{len(sites)} basctl destructive confirmation(s) routed through "
        "sfx2::ConfirmDestructiveAction with per-caller verbs, the macro-execution prompt "
        f"safe-default pinned, and {len(roots)} macro/organizer/security root(s) kept "
        "native-exclusion in the shared CSV."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
