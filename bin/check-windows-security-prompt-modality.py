#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed security-prompt modality contract (WIN-SYS-007).

``qa/windows-ui-contract/security-prompt-modality.json`` pins the five owned
certificate / digital-signature / macro-security dialog roots and proves the
HARD CONSTRAINT that each stays MODAL (``native-exclusion``) and is never routed
to the bottom-right notification stack. It does not reclassify or redraw anything
-- it binds four independent evidence layers per dialog, reusing the shared
NotificationRouter classifier as the single source of truth:

* CSV policy -- the shared ``dialog-notification-policy.csv`` row is present with
  ``policy == native-exclusion`` and its ``exclusion_reason`` matches the
  declared classification (so a flip to the notification form fails closed);
* live router -- ``classify_route`` (imported from
  bin/check-windows-dialog-notification-contract.py) scanned over the real
  ``.ui`` returns the native exclusion with the ``security`` reason for the four
  xmlsec roots and the ``input`` reason for cui's ``CertDialog``, pinning the
  router's own security-vs-input precedence;
* modal footer -- the ``.ui`` action-widget order matches the pinned footer;
* source reachability -- every declared ``modal_marker`` (the synchronous
  ``GenericDialogController`` bind and, where present, ``GenericDialogController::run()``)
  and every embedded page bind exists as real, comment-stripped source, and each
  embedded page ``.ui`` declares its pinned root object id.

``read_registry`` (also imported from the router module) additionally validates
the entire shared CSV as a well-formed registry on the disk-backed run. The
contract is source evidence only: ``runtime_verified`` is false throughout -- no
native build, dialog pixels, or Material redraw of any security control.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/security-prompt-modality.json"
POLICY_REGISTRY = "qa/windows-ui-contract/dialog-notification-policy.csv"
ROUTER_MODULE = "bin/check-windows-dialog-notification-contract.py"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# Import the shared NotificationRouter classifier as a module.
#
# The router module uses ``from __future__ import annotations`` plus frozen, ordered dataclasses;
# under the py 3.9 launcher it must be registered in sys.modules *before* exec_module or the
# dataclass machinery cannot resolve the module. We import only the pure helpers
# (read_registry, classify_route, _scan_dialog_signals, EXCLUSION_REASONS, EXCLUSION_POLICY,
# DIALOG_CLASSES, CSV_FIELDS) and never trigger the git-based discover_dialogs path.
# --------------------------------------------------------------------------------------------------
def _load_router_module(repo_root: Path = REPOSITORY):
    module_path = repo_root / ROUTER_MODULE
    spec = importlib.util.spec_from_file_location(
        "check_windows_dialog_notification_contract", module_path
    )
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load router module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # MUST precede exec_module (py3.9 dataclass pitfall)
    spec.loader.exec_module(module)
    return module


ROUTER = _load_router_module()
read_registry = ROUTER.read_registry
classify_route = ROUTER.classify_route
_scan_dialog_signals = ROUTER._scan_dialog_signals
EXCLUSION_REASONS = ROUTER.EXCLUSION_REASONS
EXCLUSION_POLICY = ROUTER.EXCLUSION_POLICY
DIALOG_CLASSES = ROUTER.DIALOG_CLASSES
CSV_FIELDS = ROUTER.CSV_FIELDS

ALLOWED_CLASSIFICATIONS = frozenset({"security", "input"})


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
    for dialog in registry.get("dialogs", []) or []:
        if not isinstance(dialog, dict):
            continue
        for key in ("ui_file", "source_file"):
            value = dialog.get(key)
            if isinstance(value, str):
                paths.add(value)
        for marker in dialog.get("modal_markers", []) or []:
            if isinstance(marker, dict) and isinstance(marker.get("file"), str):
                paths.add(marker["file"])
        for page in dialog.get("embedded_pages", []) or []:
            if isinstance(page, dict) and isinstance(page.get("ui_file"), str):
                paths.add(page["ui_file"])
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


def _top_level_dialog(root: ET.Element, object_id: str) -> ET.Element | None:
    for child in root:
        if child.tag != "object":
            continue
        if child.get("id") == object_id and child.get("class") in DIALOG_CLASSES:
            return child
    return None


def _object_present(root: ET.Element, object_id: str) -> bool:
    for node in root.iter("object"):
        if node.get("id") == object_id:
            return True
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
# CSV (parse the shared policy registry from text; the disk-backed run also fully validates it via
# the imported read_registry)
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
# Per-dialog validation
# --------------------------------------------------------------------------------------------------
def _require(code: str | None, marker: str, where: str, errors: list[str]) -> None:
    if code is None:
        errors.append(f"{where}:source file missing")
        return
    if marker not in code:
        errors.append(f"{where}:missing real code marker {marker!r}")


def _validate_dialog(
    dialog: Mapping[str, Any],
    contents: Mapping[str, str],
    csv_map: Mapping[tuple[str, str], dict[str, str]],
    stripped: dict[str, str | None],
    errors: list[str],
) -> None:
    dialog_id = dialog.get("id")
    where = f"dialog[{dialog_id}]"

    ui_file = dialog.get("ui_file")
    object_id = dialog.get("object_id")
    widget_class = dialog.get("widget_class")
    classification = dialog.get("classification")
    if not isinstance(ui_file, str) or not isinstance(object_id, str) or not isinstance(widget_class, str):
        errors.append(f"{where}:ui_file/object_id/widget_class strings required")
        return
    if classification not in ALLOWED_CLASSIFICATIONS:
        errors.append(
            f"{where}:classification {classification!r} must be one of {sorted(ALLOWED_CLASSIFICATIONS)}"
        )
        return
    expected_reason = EXCLUSION_REASONS[classification]

    # Layer 1: the shared CSV keeps this root a native-exclusion with the matching reason.
    row = csv_map.get((ui_file, object_id))
    if row is None:
        errors.append(f"{where}:no CSV policy row for {ui_file}#{object_id}")
    else:
        if row.get("policy") != EXCLUSION_POLICY:
            errors.append(
                f"{where}:CSV policy is {row.get('policy')!r}, must be {EXCLUSION_POLICY!r} "
                "(a security prompt must never route to the notification form)"
            )
        if row.get("widget_class") != widget_class:
            errors.append(
                f"{where}:CSV widget_class is {row.get('widget_class')!r}, expected {widget_class!r}"
            )
        if row.get("exclusion_reason") != expected_reason:
            errors.append(
                f"{where}:CSV exclusion_reason drift: is {row.get('exclusion_reason')!r}, "
                f"expected {expected_reason!r} for classification {classification!r}"
            )

    # Layer 2: the live router keeps it modal, scanning the real .ui.
    ui_root = _parse_xml(contents.get(ui_file), f"{where}:ui", errors)
    if ui_root is not None:
        dialog_object = _top_level_dialog(ui_root, object_id)
        if dialog_object is None:
            errors.append(f"{where}:top-level {widget_class} {object_id!r} missing in {ui_file}")
        else:
            signals = _scan_dialog_signals(dialog_object)
            policy, reason = classify_route(ui_file, object_id, widget_class, signals)
            if policy != EXCLUSION_POLICY:
                errors.append(
                    f"{where}:router classify_route returned policy {policy!r}, must be "
                    f"{EXCLUSION_POLICY!r} (KeepModal)"
                )
            if reason != expected_reason:
                errors.append(
                    f"{where}:router reason drift: classify_route gave {reason!r}, expected "
                    f"{expected_reason!r} for the declared {classification!r} precedence"
                )

        # Layer 3: the modal footer action-widget order matches the pin.
        expected_footer = dialog.get("footer")
        if not isinstance(expected_footer, list) or not expected_footer:
            errors.append(f"{where}:footer non-empty array required")
        else:
            actual_footer = _ui_footer(ui_root)
            if actual_footer != [
                {"response": entry.get("response"), "widget": entry.get("widget")}
                for entry in expected_footer
                if isinstance(entry, dict)
            ]:
                errors.append(
                    f"{where}:footer drift: pinned "
                    f"{[(e.get('widget'), e.get('response')) for e in expected_footer]} "
                    f"but found {[(e['widget'], e['response']) for e in actual_footer]}"
                )

    # Layer 4: source reachability -- every modal_marker is real, comment-stripped code.
    markers = dialog.get("modal_markers")
    if not isinstance(markers, list) or not markers:
        errors.append(f"{where}:modal_markers non-empty array required")
    else:
        for index, marker in enumerate(markers):
            if not isinstance(marker, dict):
                errors.append(f"{where}:modal_marker #{index} object required")
                continue
            file_path = marker.get("file")
            pattern = marker.get("pattern")
            if not isinstance(file_path, str) or not isinstance(pattern, str):
                errors.append(f"{where}:modal_marker #{index} file/pattern strings required")
                continue
            _require(stripped_code(file_path, contents, stripped), pattern,
                     f"{where}:modal_marker #{index}", errors)

    # Embedded tabbed page roots (macro-security level/trust, cert viewer general/details/page).
    for index, page in enumerate(dialog.get("embedded_pages", []) or []):
        if not isinstance(page, dict):
            errors.append(f"{where}:embedded_page #{index} object required")
            continue
        page_ui = page.get("ui_file")
        page_id = page.get("object_id")
        source_marker = page.get("source_marker")
        page_root = _parse_xml(contents.get(page_ui) if isinstance(page_ui, str) else None,
                               f"{where}:embedded_page[{page_id}]", errors)
        if page_root is not None:
            if not isinstance(page_id, str) or not _object_present(page_root, page_id):
                errors.append(f"{where}:embedded page root {page_id!r} missing in {page_ui}")
        if isinstance(source_marker, str):
            _require(stripped_code(dialog.get("source_file"), contents, stripped), source_marker,
                     f"{where}:embedded_page[{page_id}] source bind", errors)
        else:
            errors.append(f"{where}:embedded_page #{index} source_marker string required")


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
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-security-prompt-modality":
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
    if registry.get("router_module") != ROUTER_MODULE:
        errors.append("registry:router_module:unexpected path")

    dialogs = registry.get("dialogs")
    if not isinstance(dialogs, list) or not dialogs:
        errors.append("registry:dialogs:non-empty array required")
        return errors

    expected_count = registry.get("expected_dialogs")
    if isinstance(expected_count, int) and expected_count != len(dialogs):
        errors.append(
            f"registry:expected_dialogs is {expected_count} but {len(dialogs)} dialog(s) declared"
        )

    csv_map = _csv_locator_map(contents.get(POLICY_REGISTRY), errors)

    stripped: dict[str, str | None] = {}
    seen: set[str] = set()
    for dialog in dialogs:
        if not isinstance(dialog, dict):
            errors.append("dialogs:entry:object required")
            continue
        dialog_id = dialog.get("id")
        if not isinstance(dialog_id, str) or not dialog_id:
            errors.append("dialogs:entry:id string required")
            continue
        if dialog_id in seen:
            errors.append(f"dialogs:{dialog_id}:duplicate dialog id")
        seen.add(dialog_id)
        _validate_dialog(dialog, contents, csv_map, stripped, errors)

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents)
    # Genuine reuse of the imported read_registry: fully validate the shared CSV as a registry so a
    # structural corruption of the policy file fails this contract too (not only a per-row drift).
    try:
        read_registry(repo_root / POLICY_REGISTRY)
    except ROUTER.ValidationError as error:
        errors.append(f"policy_registry:shared CSV failed read_registry validation: {error}")
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
        print(f"Security-prompt modality contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    dialogs = registry.get("dialogs", [])
    security = sum(1 for d in dialogs if isinstance(d, dict) and d.get("classification") == "security")
    print(
        "Security-prompt modality contract passed: "
        f"{len(dialogs)} cert/signature/macro-security root(s) ({security} security, "
        f"{len(dialogs) - security} input) each pinned native-exclusion / KeepModal across the CSV "
        "policy, the live router classifier, the modal footer, and synchronous "
        "GenericDialogController source reachability."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
