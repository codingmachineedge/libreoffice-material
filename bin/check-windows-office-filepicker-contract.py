#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the in-suite Office file picker (WIN-DLG-003).

``qa/windows-ui-contract/office-file-picker-composition.json`` pins the in-suite OfficeFilePicker
Save-As / Open fallback sheet (fpicker/source/office/iodlg.cxx + explorerfiledialog.ui) from
docs/design/08-dialogs.md 8.3 / 8.3.1. The .ui controls are plain stock widgets with no
definition.xml part, so the M-scope is *binding the design regions to real widget ids + weld_*
bindings*, never re-drawing an OS picker. WIN-SYS-001 already closes the OS delegation seam; this
row pins only the fallback picker's own composition. This checker parses the real tree fail-closed:

* ``regions`` -- each documented region (breadcrumb-row=current_path, file-name-field=file_name,
  file-type-dropdown=file_type, password-checkbox=password, footer open/cancel) must exist in
  explorerfiledialog.ui at its exact object id + class, and its ``weld_*`` binding literal must be
  real (comment-stripped) code in iodlg.cxx. The 'Breadcrumb row' is pinned to current_path, never
  breadcrumb.ui.
* ``save_mode_label_swap`` -- the PickerFlags::SaveAs branch and its STR_EXPLORERFILE_SAVE /
  STR_EXPLORERFILE_BUTTONSAVE resources and the confirm-button relabel must be real code.
* ``message_boxes`` -- the picker's own overwrite-confirmation box: STR_SVT_ALREADYEXISTOVERWRITE
  present, VclMessageType::Question / VclButtonsType::YesNo bound to that call site, the
  ``run() != RET_YES`` -> ``return`` safe-default control flow present, classification inside the
  router taxonomy, and (honesty) modal + not routed to the notification stack.
* ``breadcrumb_guard`` -- iodlg.cxx must NOT reference ``breadcrumb`` (breadcrumb.ui belongs to the
  remote picker); a reference would make the current_path pin stale and fails closed.
* ``picker_seam`` + ``cross_references`` -- the OfficeFilePicker service literal must still be real
  code in filedlghelper.cxx, and explorerfiledialog.ui / foldernamedialog.ui must keep their
  native-exclusion (KeepModal) policy in dialog-notification-policy.csv (read-only; never
  re-registered).

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, Save-As
sheet pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/office-file-picker-composition.json"
CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

CANONICAL_CLASSIFICATIONS = ("decision", "security", "credential", "input", "acknowledgment")
# How far either side of the resid literal the message-type/buttons enums may sit while still
# binding to that call site. The overwrite box assigns aMsg = FpsResId(resid), runs a
# replaceFirst("$filename$", ...) block, then calls CreateMessageDialog(..., VclMessageType::Question,
# VclButtonsType::YesNo, aMsg) a few lines below -- so the enums sit a few hundred chars after the resid.
ENUM_BINDING_WINDOW = 600


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO / source hygiene
# --------------------------------------------------------------------------------------------------
CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


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


def _strip_cpp(text: str) -> str:
    return _strip_comments(CPP_RAW_STRING.sub("", text))


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {CSV_PATH}
    for key in ("picker_ui", "impl_source"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    for block_key in ("save_mode_label_swap", "breadcrumb_guard", "picker_seam"):
        block = registry.get(block_key)
        if isinstance(block, dict) and isinstance(block.get("file"), str):
            paths.add(block["file"])
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
        cache[rel] = _strip_cpp(contents[rel])
    return cache[rel]


def _has_whole_token(haystack: str, token: str) -> bool:
    start = 0
    while True:
        idx = haystack.find(token, start)
        if idx < 0:
            return False
        after = haystack[idx + len(token): idx + len(token) + 1]
        if not (after.isalnum() or after == "_"):
            return True
        start = idx + 1


def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


def _object_by_id(root: ET.Element, cls: str, oid: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == oid and obj.get("class") == cls:
            return obj
    return None


# --------------------------------------------------------------------------------------------------
# regions
# --------------------------------------------------------------------------------------------------
def _validate_regions(
    registry: Mapping[str, Any], contents: Mapping[str, str], cache: dict[str, str], errors: list[str]
) -> None:
    regions = registry.get("regions")
    if not isinstance(regions, list) or not regions:
        errors.append("regions:non-empty array required")
        return
    picker_rel = registry.get("picker_ui")
    picker_root = _parse_xml(contents.get(picker_rel) if isinstance(picker_rel, str) else None, "picker_ui", errors)
    impl_rel = registry.get("impl_source")
    impl_code = _stripped(contents, impl_rel, cache) if isinstance(impl_rel, str) else None
    if impl_code is None:
        errors.append("regions:impl_source file missing")

    for region in regions:
        if not isinstance(region, dict):
            errors.append("regions:entry must be object")
            continue
        name = region.get("region", "?")
        oid = region.get("object_id")
        cls = region.get("class")
        if picker_root is not None and isinstance(oid, str) and isinstance(cls, str):
            if _object_by_id(picker_root, cls, oid) is None:
                errors.append(f"regions:{name}:{cls} id={oid!r} missing in explorerfiledialog.ui")
        binding = region.get("binding")
        if isinstance(binding, str) and impl_code is not None and binding not in impl_code:
            errors.append(
                f"regions:{name}:weld binding {binding!r} missing from real code in iodlg.cxx "
                "(the region's control binding drifted)"
            )


def _validate_anchor_block(
    name: str, block: Any, contents: Mapping[str, str], cache: dict[str, str], errors: list[str]
) -> None:
    if not isinstance(block, dict):
        errors.append(f"{name}:object required")
        return
    rel = block.get("file")
    code = _stripped(contents, rel, cache) if isinstance(rel, str) else None
    if code is None:
        errors.append(f"{name}:file missing: {rel}")
        return
    for index, anchor in enumerate(block.get("anchors", []) or []):
        if not isinstance(anchor, dict):
            errors.append(f"{name}:anchor[{index}]:object required")
            continue
        literal = anchor.get("literal")
        if not isinstance(literal, str) or not literal:
            errors.append(f"{name}:anchor[{index}]:literal:non-empty string required")
            continue
        if literal not in code:
            errors.append(f"{name}:anchor:{literal!r} missing from real code in {rel} (save-mode swap drifted)")


def _validate_message_box(
    box: Any, allowed: Sequence[str], contents: Mapping[str, str], cache: dict[str, str], errors: list[str]
) -> None:
    if not isinstance(box, dict):
        errors.append("message_boxes:entry:object required")
        return
    bid = box.get("id")
    context = f"message_box[{bid}]" if isinstance(bid, str) and bid else "message_box[?]"
    rel = box.get("file")
    code = _stripped(contents, rel, cache) if isinstance(rel, str) else None
    if code is None:
        errors.append(f"{context}:file missing: {rel}")
        return

    resid = box.get("resid")
    if not isinstance(resid, str) or not resid:
        errors.append(f"{context}:resid:non-empty string required")
        return
    resid_index = code.find(resid)
    if resid_index < 0:
        errors.append(f"{context}:resid:{resid!r} missing from real code in {rel} (overwrite box removed/renamed)")
        return

    # Enums may sit on either side of the resid (aMsg = FpsResId(...); then CreateMessageDialog(...)).
    window = code[max(0, resid_index - ENUM_BINDING_WINDOW): resid_index + ENUM_BINDING_WINDOW]
    for field, prefix in (("message_type", "VclMessageType::"), ("buttons", "VclButtonsType::")):
        value = box.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{context}:{field}:non-empty string required")
            continue
        if not _has_whole_token(window, f"{prefix}{value}"):
            errors.append(
                f"{context}:{field}:{prefix}{value!r} not bound to the {resid} call site in {rel} "
                "(message-box shape drifted)"
            )

    safe = box.get("safe_default")
    if isinstance(safe, dict):
        guard = safe.get("guard_literal")
        abort = safe.get("abort_literal")
        if isinstance(guard, str):
            gpos = code.find(guard, resid_index)
            if gpos < 0:
                errors.append(
                    f"{context}:safe_default:{guard!r} missing after the resid in {rel} "
                    "(the destructive overwrite no longer requires an explicit Yes)"
                )
            elif isinstance(abort, str) and abort not in code[gpos: gpos + 200]:
                errors.append(
                    f"{context}:safe_default:{abort!r} not found after {guard!r} in {rel} "
                    "(the write no longer aborts unless Yes)"
                )
    else:
        errors.append(f"{context}:safe_default:object required")

    if box.get("classification") not in allowed:
        errors.append(f"{context}:classification:{box.get('classification')!r} not in allowed taxonomy {list(allowed)}")
    if box.get("modal") is not True:
        errors.append(f"{context}:modal:must be true (an overwrite decision stays modal)")
    if box.get("routes_to_notification") is not False:
        errors.append(f"{context}:routes_to_notification:must be false (a decision box is never bottom-right routed)")


def _validate_breadcrumb_guard(block: Any, contents: Mapping[str, str], cache: dict[str, str], errors: list[str]) -> None:
    if not isinstance(block, dict):
        errors.append("breadcrumb_guard:object required")
        return
    rel = block.get("file")
    code = _stripped(contents, rel, cache) if isinstance(rel, str) else None
    if code is None:
        errors.append(f"breadcrumb_guard:file missing: {rel}")
        return
    forbidden = block.get("forbidden_literal")
    if isinstance(forbidden, str) and forbidden.lower() in code.lower():
        errors.append(
            f"breadcrumb_guard:{forbidden!r} appeared in {rel} "
            "(breadcrumb.ui belongs to the remote picker; the 'Breadcrumb row = current_path' pin is stale)"
        )


def _validate_picker_seam(block: Any, contents: Mapping[str, str], cache: dict[str, str], errors: list[str]) -> None:
    if not isinstance(block, dict):
        errors.append("picker_seam:object required")
        return
    rel = block.get("file")
    code = _stripped(contents, rel, cache) if isinstance(rel, str) else None
    if code is None:
        errors.append(f"picker_seam:file missing: {rel}")
        return
    literal = block.get("literal")
    if isinstance(literal, str) and literal not in code:
        errors.append(
            f"picker_seam:{literal!r} missing from real code in {rel} "
            "(the upstream OfficeFilePicker routing boundary drifted)"
        )


def _validate_cross_references(references: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(references, list) or not references:
        errors.append("cross_references:non-empty array required")
        return
    csv_text = contents.get(CSV_PATH)
    if csv_text is None:
        errors.append(f"cross_references:file missing: {CSV_PATH}")
        return
    rows = list(csv.reader(io.StringIO(csv_text)))
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
            errors.append(f"cross_references:{ui_path}::{object_id} absent from {CSV_PATH} (no longer registered)")
        elif actual != expected:
            errors.append(
                f"cross_references:{ui_path}::{object_id} policy is {actual!r}, expected {expected!r} "
                "(a referenced picker root lost its native-exclusion classification)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-office-file-picker-composition":
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
                errors.append(f"registry:allowed_classifications:missing canonical taxonomy value {expected!r}")

    cache: dict[str, str] = {}
    _validate_regions(registry, contents, cache, errors)
    _validate_anchor_block("save_mode_label_swap", registry.get("save_mode_label_swap"), contents, cache, errors)

    boxes = registry.get("message_boxes")
    if not isinstance(boxes, list) or not boxes:
        errors.append("registry:message_boxes:non-empty array required")
    else:
        for box in boxes:
            _validate_message_box(box, allowed, contents, cache, errors)

    _validate_breadcrumb_guard(registry.get("breadcrumb_guard"), contents, cache, errors)
    _validate_picker_seam(registry.get("picker_seam"), contents, cache, errors)
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
        print(f"Office file-picker contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Office file-picker contract passed: pinned "
        f"{len(registry['regions'])} Save-As regions to their widget ids + weld bindings (Breadcrumb "
        "row = current_path, not breadcrumb.ui), the save-mode label swap, the modal Question/YesNo "
        "overwrite box with its safe-default control flow, the breadcrumb guard, and the "
        "OfficeFilePicker seam + KeepModal cross-references; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
