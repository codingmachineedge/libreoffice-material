#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Impress Slide Show Settings dialog (WIN-IM-003).

``qa/windows-ui-contract/impress-slideshow-settings.json`` pins the only genuinely native,
.ui-backed, build-free-checkable surface inside WIN-IM-003's scope: the Slide Show Settings
dialog (``SdStartPresentationDlg``, built from ``sd/uiconfig/simpress/ui/presentationdialog.ui``).
The dialog's Material look is delivered entirely by the shared generic weld-dialog parts already
in definition.xml, so the M-scope here is *pinning composition and wiring*, never re-drawing
controls. This checker parses the real tree fail-closed:

* ``frame_groups`` -- the five ``GtkFrame`` group boxes in ``presentationdialog.ui`` must appear
  in the pinned document order (Range / Presentation Mode / Presentation Options / Display /
  Remote control), each carrying its pinned object id and bold group-label text. A reorder,
  renamed frame, or relabelled group fails closed.
* ``footer`` -- the ``action-widgets`` order ok(-5) / cancel(-6) / help(-11) must match exactly and
  the primary OK button must stay ``has-default``. A reordered footer or a lost default fails closed.
* ``wiring_markers`` -- each of the eight enable/disable + role-binding chains in present.cxx must
  exist as real (comment-stripped) code *inside its named method body* (ChangeRangeHdl,
  ClickWindowPresentationHdl, ChangePause, InitMonitorSettings, GetDisplayName, the constructor, and
  run()). A partial revert that leaves the method defined but strips its wiring fails closed here.
* ``header_markers`` -- present.hxx must still declare the class and the handler/method members the
  wiring depends on (comment-stripped), so a rename of the dialog surface fails closed.
* ``modal_exclusion`` -- the input-collecting dialog must keep its native-exclusion (KeepModal)
  classification in dialog-notification-policy.csv (read-only). A drift to route-notification fails.
* ``carveouts`` -- the Custom Slide Show dialogs, the full-screen/OpenGL playback engine, and real
  multi-monitor placement are build-dependent, so their ``status`` must stay ``specified``.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, dialog
pixels, monitor placement, or runtime interaction are claimed. The registry-closure OVERRIDES
mapping recorded in ``registry_closure_override`` is a coordination hand-off; this checker does not
apply or assert it (bin/check-windows-ui-registry-closure.py is not in this slice's owned files).
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
REGISTRY_PATH = "qa/windows-ui-contract/impress-slideshow-settings.json"
CONTRACT_NAME = "material-impress-slideshow-settings-composition"
INVENTORY_ROW = "WIN-IM-003"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO / source helpers
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = set()
    for key in ("dialog_ui", "impl_source", "header_source", "csv_policy"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals and line count."""

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


def _function_body(source: str, signature: str) -> str | None:
    """Return the brace-balanced body that follows ``signature`` (the first { after it)."""

    start = source.find(signature)
    if start < 0:
        return None
    opening = source.find("{", start + len(signature))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    return None


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
# presentationdialog.ui composition
# --------------------------------------------------------------------------------------------------
def _iter_objects(root: ET.Element) -> list[ET.Element]:
    return list(root.iter("object"))


def _object_by_id(root: ET.Element, cls: str, oid: str) -> ET.Element | None:
    for obj in _iter_objects(root):
        if obj.get("class") == cls and obj.get("id") == oid:
            return obj
    return None


def _direct_property(obj: ET.Element, name: str) -> ET.Element | None:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return prop
    return None


def _frame_label(frame_obj: ET.Element) -> str | None:
    """Return the bold group-label text of a GtkFrame's ``<child type="label">``."""

    for child in frame_obj.findall("child"):
        if child.get("type") != "label":
            continue
        label_obj = child.find("object")
        if label_obj is None:
            continue
        prop = _direct_property(label_obj, "label")
        if prop is not None:
            return (prop.text or "").strip()
    return None


def _validate_frame_groups(root: ET.Element, groups: Any, errors: list[str]) -> None:
    if not isinstance(groups, list) or not groups:
        errors.append("frame_groups:non-empty array required")
        return
    frames = [obj for obj in _iter_objects(root) if obj.get("class") == "GtkFrame"]
    if len(frames) != len(groups):
        errors.append(
            f"frame_groups:GtkFrame count {len(frames)} != pinned {len(groups)} "
            "(a group box was added or removed)"
        )
    for index, want in enumerate(groups):
        if not isinstance(want, dict):
            errors.append(f"frame_groups[{index}]:object required")
            continue
        want_id = want.get("id")
        want_label = want.get("label")
        if not (isinstance(want_id, str) and isinstance(want_label, str)):
            errors.append(f"frame_groups[{index}]:id/label must be strings")
            continue
        if index >= len(frames):
            errors.append(
                f"frame_groups[{index}]:pinned {want_id!r} ({want_label!r}) has no frame at that "
                "position (group order truncated)"
            )
            continue
        frame = frames[index]
        got_id = frame.get("id")
        if got_id != want_id:
            errors.append(
                f"frame_groups[{index}]:frame id drift: pinned {want_id!r} but found {got_id!r} "
                "(group order changed)"
            )
        got_label = _frame_label(frame)
        if got_label != want_label:
            errors.append(
                f"frame_groups[{index}]:group label drift for {want_id!r}: pinned {want_label!r} "
                f"but found {got_label!r}"
            )


def _validate_footer(root: ET.Element, footer: Any, errors: list[str]) -> None:
    if not isinstance(footer, dict):
        errors.append("footer:object required")
        return
    expected = footer.get("action_widgets")
    if not isinstance(expected, list) or not expected:
        errors.append("footer:action_widgets:non-empty array required")
        return
    action_holder = None
    for element in root.iter("action-widgets"):
        action_holder = element
        break
    if action_holder is None:
        errors.append("footer:action-widgets block missing in presentationdialog.ui")
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
                f"footer:action_widgets[{index}] drift: pinned "
                f"{want.get('id')}({want.get('response')}) but found "
                f"{got.get('id')}({got.get('response')})"
            )

    primary = footer.get("primary")
    if not isinstance(primary, dict):
        errors.append("footer:primary:object required")
        return
    pid = primary.get("id")
    button = _object_by_id(root, "GtkButton", pid) if isinstance(pid, str) else None
    if button is None:
        errors.append(f"footer:primary:GtkButton id={pid!r} missing in presentationdialog.ui")
        return
    if primary.get("has_default") is True:
        prop = _direct_property(button, "has-default")
        if prop is None or prop.text != "True":
            errors.append("footer:primary:OK button must be has-default=True")
    expected_label = primary.get("label")
    if isinstance(expected_label, str):
        prop = _direct_property(button, "label")
        actual_label = prop.text if prop is not None else None
        if actual_label != expected_label:
            errors.append(
                f"footer:primary:label is {actual_label!r}, expected {expected_label!r} "
                "(primary action is not OK)"
            )


# --------------------------------------------------------------------------------------------------
# present.cxx wiring markers + present.hxx header markers
# --------------------------------------------------------------------------------------------------
def _validate_wiring_markers(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    markers = registry.get("wiring_markers")
    if not isinstance(markers, list) or not markers:
        errors.append("wiring_markers:non-empty array required")
        return
    impl_rel = registry.get("impl_source")
    impl_text = contents.get(impl_rel) if isinstance(impl_rel, str) else None
    if impl_text is None:
        errors.append("wiring_markers:impl_source file missing")
        return
    code = _strip_comments(impl_text)

    seen_ids: set[str] = set()
    for index, marker in enumerate(markers):
        if not isinstance(marker, dict):
            errors.append(f"wiring_markers[{index}]:object required")
            continue
        mid = marker.get("id")
        signature = marker.get("method_signature")
        patterns = marker.get("patterns")
        if not (isinstance(mid, str) and mid):
            errors.append(f"wiring_markers[{index}]:id:non-empty string required")
            continue
        if mid in seen_ids:
            errors.append(f"wiring_markers:{mid}:duplicate id")
        seen_ids.add(mid)
        if not isinstance(signature, str) or not signature:
            errors.append(f"wiring_markers:{mid}:method_signature:non-empty string required")
            continue
        if not isinstance(patterns, list) or not patterns:
            errors.append(f"wiring_markers:{mid}:patterns:non-empty array required")
            continue
        body = _function_body(code, signature)
        if body is None:
            errors.append(
                f"wiring_markers:{mid}:method {signature!r} not found as real code in present.cxx"
            )
            continue
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                errors.append(f"wiring_markers:{mid}:pattern must be a non-empty string")
                continue
            if pattern not in body:
                errors.append(
                    f"wiring_markers:{mid}:wiring drifted -- {pattern!r} missing from the "
                    f"{signature.split('(')[0].strip()} body in present.cxx"
                )


def _validate_header_markers(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    markers = registry.get("header_markers")
    if not isinstance(markers, list) or not markers:
        errors.append("header_markers:non-empty array required")
        return
    header_rel = registry.get("header_source")
    header_text = contents.get(header_rel) if isinstance(header_rel, str) else None
    if header_text is None:
        errors.append("header_markers:header_source file missing")
        return
    code = _strip_comments(header_text)
    for marker in markers:
        if not isinstance(marker, str) or not marker:
            errors.append("header_markers:entry must be a non-empty string")
            continue
        if marker not in code:
            errors.append(
                f"header_markers:{marker!r} missing from present.hxx "
                "(the dialog surface was renamed or restructured)"
            )


# --------------------------------------------------------------------------------------------------
# shared CSV cross-check + carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_modal_exclusion(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    decl = registry.get("modal_exclusion")
    if not isinstance(decl, dict):
        errors.append("modal_exclusion:object required")
        return
    ui_path = decl.get("ui_path")
    object_id = decl.get("object_id")
    expected = decl.get("expected_policy")
    if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(expected, str)):
        errors.append("modal_exclusion:ui_path/object_id/expected_policy must be strings")
        return
    csv_rel = registry.get("csv_policy")
    csv_text = contents.get(csv_rel) if isinstance(csv_rel, str) else None
    if csv_text is None:
        errors.append("modal_exclusion:csv_policy file missing")
        return
    rows = list(csv.reader(io.StringIO(csv_text)))
    policy_by_locator: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        if len(row) >= 4:
            policy_by_locator[(row[0], row[1])] = row[3]
    actual = policy_by_locator.get((ui_path, object_id))
    if actual is None:
        errors.append(
            f"modal_exclusion:{ui_path}::{object_id} absent from dialog-notification-policy.csv "
            "(the dialog is no longer registered as an exclusion)"
        )
    elif actual != expected:
        errors.append(
            f"modal_exclusion:{ui_path}::{object_id} policy is {actual!r}, expected {expected!r} "
            "(the input-collecting slide-show dialog left KeepModal)"
        )


def _validate_carveouts(carveouts: Any, errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("carveouts:non-empty object required")
        return
    for name in ("custom_slide_show_dialogs", "playback_engine", "multimonitor_placement"):
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
    if registry.get("contract") != CONTRACT_NAME:
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("inventory_row") != INVENTORY_ROW:
        errors.append("registry:inventory_row:must be WIN-IM-003")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    dialog_rel = registry.get("dialog_ui")
    dialog_root = _parse_xml(
        contents.get(dialog_rel) if isinstance(dialog_rel, str) else None, "dialog_ui", errors
    )
    if dialog_root is not None:
        _validate_frame_groups(dialog_root, registry.get("frame_groups"), errors)
        _validate_footer(dialog_root, registry.get("footer"), errors)

    _validate_wiring_markers(registry, contents, errors)
    _validate_header_markers(registry, contents, errors)
    _validate_modal_exclusion(registry, contents, errors)
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
        print(f"Impress slide-show settings contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Impress slide-show settings contract passed: pinned the "
        f"{len(registry['frame_groups'])} GtkFrame groups (Range/Presentation Mode/Presentation "
        "Options/Display/Remote control) + ok/cancel/help footer of presentationdialog.ui, the "
        f"{len(registry['wiring_markers'])} method-anchored enable/disable + role-binding chains in "
        "present.cxx, the KeepModal exclusion, and the custom-show / playback / multi-monitor "
        "carve-outs spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
