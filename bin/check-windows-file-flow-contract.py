#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Windows Open/Save file flows (WIN-SYS-001).

``qa/windows-ui-contract/file-flow-policy.json`` pins the file-flow platform-delegation
boundary and the surrounding call-site message boxes from docs/design/08-dialogs.md 8.3.1.
On Windows the Open/Save picker is the OS-owned native IFileDialog and the overwrite prompt
is OS-owned via the ``FOS_OVERWRITEPROMPT`` flag, so the M-scope of this row is *pinning the
delegation seam*, never re-drawing an OS-rendered picker. This checker parses the real tree
fail-closed and cross-validates every declaration:

* ``platform_delegation`` -- the win32 boundary anchors (the OS overwrite-prompt flag, the OS
  COM open/save dialog creation, the OS custom-control interface) must all exist as real
  (comment-stripped) code in fpicker/source/win32/VistaFilePickerImpl.cxx. A dropped
  ``FOS_OVERWRITEPROMPT`` or a renamed CLSID anchor fails closed -- that would mean the OS
  overwrite confirmation or the OS picker had been replaced, which this row forbids silently.
* ``picker_seam`` -- the ``OfficeFilePicker`` service literal in filedlghelper.cxx that marks
  the native-vs-fallback picker-selection boundary must be real code.
* ``message_boxes`` -- each of the three save-flow call-site boxes must have its ``SfxResId``
  literal present as real code, with the declared ``VclMessageType`` / ``VclButtonsType`` enum
  bound to that call site (found within a window immediately preceding the resid). Every box's
  ``classification`` must be inside the allowed router taxonomy and, for honesty, every box
  must stay ``modal`` with ``routes_to_notification`` false -- none is a pure informational
  acknowledgement, so none may be marked as routed into the bottom-right notification stack.
* ``cross_references`` -- each already-registered .ui root (querysave / password / remotefiles)
  must still carry its expected native-exclusion policy in dialog-notification-policy.csv. This
  is a read-only cross-check by locator; the checker never appends to or re-registers the CSV,
  so the notification / registry-closure contracts cannot double-count these roots.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build,
file-picker pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/file-flow-policy.json"
CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

# The five router-taxonomy classifications a call-site message box may honestly carry.
CANONICAL_CLASSIFICATIONS = ("decision", "security", "credential", "input", "acknowledgment")

# How far back from a resid literal the message-type / buttons enum may sit while still
# binding to that call site (the Application::CreateMessageDialog(...) argument list is a few
# lines above the resid string).
ENUM_BINDING_WINDOW = 400


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


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals.

    Anchoring on the result guarantees the contract binds to real code, never to a call name or
    resid that merely survives inside a comment.
    """

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


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {CSV_PATH}
    delegation = registry.get("platform_delegation")
    if isinstance(delegation, dict) and isinstance(delegation.get("file"), str):
        paths.add(delegation["file"])
    seam = registry.get("picker_seam")
    if isinstance(seam, dict) and isinstance(seam.get("file"), str):
        paths.add(seam["file"])
    for box in registry.get("message_boxes", []) or []:
        if isinstance(box, dict) and isinstance(box.get("file"), str):
            paths.add(box["file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _stripped(contents: Mapping[str, str], rel: str, cache: dict[str, str]) -> str | None:
    if rel not in contents:
        return None
    if rel not in cache:
        cache[rel] = _strip_comments(contents[rel])
    return cache[rel]


def _has_whole_token(haystack: str, token: str) -> bool:
    """True if ``token`` occurs in ``haystack`` not immediately followed by an identifier char.

    Distinguishes an exact enum (``VclButtonsType::Ok,``) from a longer one that merely shares the
    prefix (``VclButtonsType::OkCancel``), so a widened button set is not silently accepted.
    """

    start = 0
    while True:
        idx = haystack.find(token, start)
        if idx < 0:
            return False
        after = haystack[idx + len(token):idx + len(token) + 1]
        if not (after.isalnum() or after == "_"):
            return True
        start = idx + 1


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_anchor_block(
    name: str,
    block: Any,
    contents: Mapping[str, str],
    cache: dict[str, str],
    errors: list[str],
) -> None:
    if not isinstance(block, dict):
        errors.append(f"{name}:object required")
        return
    rel = block.get("file")
    if not isinstance(rel, str) or not rel:
        errors.append(f"{name}:file:non-empty string required")
        return
    code = _stripped(contents, rel, cache)
    if code is None:
        errors.append(f"{name}:file missing: {rel}")
        return
    anchors = block.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        errors.append(f"{name}:anchors:non-empty array required")
        return
    for index, anchor in enumerate(anchors):
        if not isinstance(anchor, dict):
            errors.append(f"{name}:anchor[{index}]:object required")
            continue
        literal = anchor.get("literal")
        if not isinstance(literal, str) or not literal:
            errors.append(f"{name}:anchor[{index}]:literal:non-empty string required")
            continue
        if literal not in code:
            errors.append(
                f"{name}:anchor:{literal!r} missing from real code in {rel} "
                "(delegation/seam boundary drifted)"
            )


def _validate_message_box(
    box: Any,
    allowed: Sequence[str],
    contents: Mapping[str, str],
    cache: dict[str, str],
    errors: list[str],
) -> None:
    if not isinstance(box, dict):
        errors.append("message_boxes:entry:object required")
        return
    bid = box.get("id")
    context = f"message_box[{bid}]" if isinstance(bid, str) and bid else "message_box[?]"

    rel = box.get("file")
    if not isinstance(rel, str) or not rel:
        errors.append(f"{context}:file:non-empty string required")
        return
    code = _stripped(contents, rel, cache)
    if code is None:
        errors.append(f"{context}:file missing: {rel}")
        return

    resid = box.get("resid")
    if not isinstance(resid, str) or not resid:
        errors.append(f"{context}:resid:non-empty string required")
        return
    resid_index = code.find(resid)
    if resid_index < 0:
        errors.append(
            f"{context}:resid:{resid!r} missing from real code in {rel} "
            "(the call-site message box was removed or renamed)"
        )
        return

    secondary = box.get("secondary_resid")
    if secondary is not None:
        if not isinstance(secondary, str) or not secondary:
            errors.append(f"{context}:secondary_resid:must be a non-empty string when present")
        elif secondary not in code:
            errors.append(f"{context}:secondary_resid:{secondary!r} missing from real code in {rel}")

    # The message-type and buttons enums must bind to THIS call site: the
    # Application::CreateMessageDialog(...) argument list sits immediately above the resid.
    window = code[max(0, resid_index - ENUM_BINDING_WINDOW):resid_index]
    for field, prefix in (("message_type", "VclMessageType::"), ("buttons", "VclButtonsType::")):
        value = box.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{context}:{field}:non-empty string required")
            continue
        token = f"{prefix}{value}"
        if not _has_whole_token(window, token):
            errors.append(
                f"{context}:{field}:{token!r} not bound to the {resid} call site in {rel} "
                "(message-box shape drifted)"
            )

    classification = box.get("classification")
    if classification not in allowed:
        errors.append(
            f"{context}:classification:{classification!r} not in allowed taxonomy "
            f"{list(allowed)}"
        )

    # Honesty: every file-flow box is a decision / security / credential prompt -- it stays modal
    # and is never routed into the bottom-right notification stack.
    if box.get("modal") is not True:
        errors.append(f"{context}:modal:must be true (file-flow prompts stay modal)")
    if box.get("routes_to_notification") is not False:
        errors.append(
            f"{context}:routes_to_notification:must be false "
            "(no file-flow box is a bottom-right-routed acknowledgement)"
        )


def _parse_csv_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def _validate_cross_references(
    references: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(references, list) or not references:
        errors.append("cross_references:non-empty array required")
        return
    csv_text = contents.get(CSV_PATH)
    if csv_text is None:
        errors.append(f"cross_references:file missing: {CSV_PATH}")
        return
    rows = _parse_csv_rows(csv_text)
    # Map (ui_path, object_id) -> policy from the CSV (skip the header row).
    policy_by_locator: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        if len(row) >= 4:
            policy_by_locator[(row[0], row[1])] = row[3]

    for index, ref in enumerate(references):
        if not isinstance(ref, dict):
            errors.append(f"cross_references[{index}]:object required")
            continue
        ui_path = ref.get("ui_path")
        object_id = ref.get("object_id")
        expected = ref.get("expected_policy")
        if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(expected, str)):
            errors.append(f"cross_references[{index}]:ui_path/object_id/expected_policy must be strings")
            continue
        actual = policy_by_locator.get((ui_path, object_id))
        if actual is None:
            errors.append(
                f"cross_references:{ui_path}::{object_id} absent from {CSV_PATH} "
                "(the cross-referenced .ui root is no longer registered)"
            )
        elif actual != expected:
            errors.append(
                f"cross_references:{ui_path}::{object_id} policy is {actual!r}, expected "
                f"{expected!r} (a referenced root lost its native-exclusion classification)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-windows-file-flow-delegation":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    allowed = registry.get("allowed_classifications")
    if not isinstance(allowed, list) or not allowed:
        errors.append("registry:allowed_classifications:non-empty array required")
        allowed = []
    else:
        for expected in CANONICAL_CLASSIFICATIONS:
            if expected not in allowed:
                errors.append(
                    f"registry:allowed_classifications:missing canonical taxonomy value {expected!r}"
                )

    cache: dict[str, str] = {}

    _validate_anchor_block(
        "platform_delegation", registry.get("platform_delegation"), contents, cache, errors
    )
    _validate_anchor_block("picker_seam", registry.get("picker_seam"), contents, cache, errors)

    boxes = registry.get("message_boxes")
    if not isinstance(boxes, list) or not boxes:
        errors.append("registry:message_boxes:non-empty array required")
    else:
        seen: set[str] = set()
        for box in boxes:
            if isinstance(box, dict) and isinstance(box.get("id"), str):
                if box["id"] in seen:
                    errors.append(f"message_boxes:duplicate id {box['id']!r}")
                seen.add(box["id"])
            _validate_message_box(box, allowed, contents, cache, errors)

    _validate_cross_references(registry.get("cross_references"), contents, errors)

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
        print(f"Windows file-flow contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Windows file-flow contract passed: pinned the win32 platform-delegation boundary "
        f"({len(registry['platform_delegation']['anchors'])} anchors), the OfficeFilePicker "
        f"selection seam, {len(registry['message_boxes'])} modal call-site message boxes, and "
        f"{len(registry['cross_references'])} read-only native-exclusion cross-references; "
        "runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
