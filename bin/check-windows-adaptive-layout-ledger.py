#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed adaptive-layout enumeration ledger for WIN-FND-006.

``qa/windows-ui-contract/adaptive-layout-ledger.json`` enumerates every native
anchor of the compact/medium/expanded adaptive-layout model
(``docs/design/01-foundations.md`` S7). Today exactly one anchor exists:
WIN-CON-007's Material-guarded below-medium overlay predicate
(``Int_DeckOverlayMinWidth`` = 600 consumed by ``ShouldDeckOverlayCanvas``),
which the sidebar-panels contract already locks. This ledger:

* pins that one real anchor by **cross-referencing** the sidebar-panels contract
  that owns it (guard, consuming function, threshold slot + value, consumer
  marker) -- it never re-asserts the source regexes that
  ``check-windows-sidebar-panels.py`` owns, so the two contracts cannot silently
  diverge;
* carries an explicit ``target-no-native-anchor`` placeholder for every other
  surface S7 names (toolbar overflow, notebookbar, status-bar pane dropping,
  dialog near-full-width) so none is silently unenumerated;
* runs a negative-space guard that scans ``sfx2/source`` and
  ``framework/source/uielement`` (comment-stripped) for any OTHER width-driven
  breakpoint slot and fails closed if one appears that the ledger does not
  enumerate (catching a silent duplicate claim as much as silent drift); and
* cross-checks the S7 design prose still names the three window classes.

It is source/text evidence only (``runtime_verified`` false) and moves no gate:
the single populated anchor is owned and locked by WIN-CON-007, not this row.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/adaptive-layout-ledger.json"
SIBLING_REGISTRY = "qa/windows-ui-contract/sidebar-panels.json"
CONTRACT_NAME = "windows-adaptive-layout-ledger"

INVENTORY_ID_PATTERN = re.compile(r"^WIN-[A-Z0-9]+-[0-9]+$")
NATIVE = "native-anchor"
TARGET = "target-no-native-anchor"
REQUIRED_TARGET_ROWS = ("WIN-SHL-002", "WIN-NAV-004", "WIN-NAV-008")

_CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


class ValidationError(RuntimeError):
    pass


def strip_cpp_non_code(source: str) -> str:
    source = _CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


# --------------------------------------------------------------------------------------------------
# Repository reads (kept separate so violations() is pure and mutation-testable).
# --------------------------------------------------------------------------------------------------
def scan_breakpoint_slots(repo_root: Path, registry: Mapping[str, Any]) -> list[str]:
    """Return the sorted set of width-driven breakpoint slot names in the scan scope."""

    pattern_text = registry.get("breakpoint_slot_pattern")
    if not isinstance(pattern_text, str):
        return []
    pattern = re.compile(pattern_text)
    scope = registry.get("source_scan_scope")
    if not isinstance(scope, list):
        return []
    found: set[str] = set()
    for rel in scope:
        if not isinstance(rel, str):
            continue
        base = repo_root / rel
        if not base.is_dir():
            continue
        for suffix in ("*.cxx", "*.hxx"):
            for path in base.rglob(suffix):
                try:
                    text = strip_cpp_non_code(path.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                for match in pattern.finditer(text):
                    found.add(match.group(0))
    return sorted(found)


def load_design_text(repo_root: Path, registry: Mapping[str, Any]) -> str | None:
    rel = registry.get("design_ref")
    if not isinstance(rel, str):
        return None
    path = repo_root / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_repository(
    repo_root: Path = REPOSITORY, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str], str | None]:
    registry = _read_json(registry_path)
    sibling_path = repo_root / SIBLING_REGISTRY
    sibling = _read_json(sibling_path) if sibling_path.is_file() else None
    scanned = scan_breakpoint_slots(repo_root, registry)
    design_text = load_design_text(repo_root, registry)
    return registry, sibling, scanned, design_text


# --------------------------------------------------------------------------------------------------
# Validation (pure)
# --------------------------------------------------------------------------------------------------
def _validate_meta(registry: Mapping[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT_NAME:
        errors.append(f"registry:contract:must be {CONTRACT_NAME!r}")
    if registry.get("inventory_row") != "WIN-FND-006":
        errors.append("registry:inventory_row:must be WIN-FND-006")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")


def _validate_cross_reference(
    entry: Mapping[str, Any], sibling: Mapping[str, Any] | None, errors: list[str]
) -> None:
    """Confirm the real anchor agrees with the sibling contract that already locks it."""

    locked_by = entry.get("locked_by")
    if locked_by != SIBLING_REGISTRY:
        errors.append(
            f"anchors:{entry.get('inventory_row')}:locked_by must be {SIBLING_REGISTRY!r}"
        )
        return
    if sibling is None:
        errors.append(f"cross_reference:{SIBLING_REGISTRY} missing; cannot cross-check the anchor")
        return

    slot = entry.get("threshold_slot")
    value = entry.get("threshold_value")
    metrics = sibling.get("metrics")
    match = None
    if isinstance(metrics, list):
        for metric in metrics:
            if isinstance(metric, dict) and metric.get("slot") == slot:
                match = metric
                break
    if match is None:
        errors.append(
            f"cross_reference:{slot} is not a metric locked by {SIBLING_REGISTRY} "
            "(the ledger must cross-reference an existing locked anchor, not invent one)"
        )
    elif match.get("value") != value:
        errors.append(
            f"cross_reference:{slot} value {value!r} disagrees with the sibling contract "
            f"({match.get('value')!r}); the two contracts must not diverge"
        )

    for entry_key, sibling_key in (
        ("consuming_function", "overlay_function"),
        ("consumer_marker", "overlay_threshold_marker"),
        ("guard_env", "guard_env"),
        ("guard_helper", "guard_helper"),
    ):
        if entry.get(entry_key) != sibling.get(sibling_key):
            errors.append(
                f"cross_reference:{entry_key} {entry.get(entry_key)!r} disagrees with the sibling "
                f"contract {sibling_key} {sibling.get(sibling_key)!r}"
            )


def _validate_anchors(
    registry: Mapping[str, Any], sibling: Mapping[str, Any] | None, errors: list[str]
) -> set[str]:
    """Validate anchor structure; return the set of enumerated native breakpoint slots."""

    anchors = registry.get("anchors")
    enumerated: set[str] = set()
    if not isinstance(anchors, list) or not anchors:
        errors.append("registry:anchors:non-empty array required")
        return enumerated

    seen_rows: set[str] = set()
    target_rows: set[str] = set()
    native_count = 0
    for index, entry in enumerate(anchors):
        if not isinstance(entry, dict):
            errors.append(f"anchors[{index}]:object required")
            continue
        row = entry.get("inventory_row")
        if not isinstance(row, str) or INVENTORY_ID_PATTERN.fullmatch(row) is None:
            errors.append(f"anchors[{index}]:inventory_row malformed: {row!r}")
        if not isinstance(entry.get("surface"), str) or not entry["surface"]:
            errors.append(f"anchors[{index}]:surface non-empty string required")
        if not isinstance(entry.get("design_ref"), str):
            errors.append(f"anchors[{index}]:design_ref string required")
        status = entry.get("status")
        if status not in (NATIVE, TARGET):
            errors.append(
                f"anchors[{index}]:status must be {NATIVE!r} or {TARGET!r} (got {status!r})"
            )
            continue
        if isinstance(row, str):
            key = f"{row}|{entry.get('surface')}"
            if key in seen_rows:
                errors.append(f"anchors:duplicate entry {key}")
            seen_rows.add(key)
        if status == NATIVE:
            native_count += 1
            slot = entry.get("threshold_slot")
            if not isinstance(slot, str) or not slot:
                errors.append(f"anchors:{row}:native-anchor requires a threshold_slot")
            else:
                enumerated.add(slot)
            if not isinstance(entry.get("threshold_value"), int) or isinstance(
                entry.get("threshold_value"), bool
            ):
                errors.append(f"anchors:{row}:native-anchor requires an integer threshold_value")
            _validate_cross_reference(entry, sibling, errors)
        elif status == TARGET and isinstance(row, str):
            target_rows.add(row)

    if native_count == 0:
        errors.append("anchors:at least one native-anchor entry is required")
    for required in REQUIRED_TARGET_ROWS:
        if required not in target_rows:
            errors.append(
                f"anchors:missing the target-no-native-anchor placeholder for {required} "
                "(every S7 surface must stay enumerated)"
            )
    return enumerated


def _validate_negative_space(
    enumerated: set[str], scanned: Sequence[str], errors: list[str]
) -> None:
    scanned_set = set(scanned)
    unenumerated = sorted(scanned_set - enumerated)
    missing = sorted(enumerated - scanned_set)
    if unenumerated:
        errors.append(
            "negative_space: width-driven breakpoint slot(s) found in the scan scope that the "
            f"ledger does not enumerate: {unenumerated} (a new adaptive-layout anchor must be added "
            "to the ledger)"
        )
    if missing:
        errors.append(
            "negative_space: enumerated native anchor(s) no longer present in the scan scope: "
            f"{missing} (the anchor drifted or was removed)"
        )


def _validate_design_prose(
    registry: Mapping[str, Any], design_text: str | None, errors: list[str]
) -> None:
    anchor = registry.get("design_anchor")
    markers = registry.get("design_class_markers")
    if design_text is None:
        errors.append("design_ref: the S7 design chapter is missing; cannot cross-reference the model")
        return
    if not isinstance(anchor, str) or anchor not in design_text:
        errors.append(f"design_ref: the adaptive-layout section anchor {anchor!r} is gone")
    if not isinstance(markers, list) or not markers:
        errors.append("registry:design_class_markers:non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and marker not in design_text:
            errors.append(
                f"design_ref: S7 no longer names the window-class behaviour {marker!r}"
            )


def violations(
    registry: Mapping[str, Any],
    sibling: Mapping[str, Any] | None,
    scanned: Sequence[str],
    design_text: str | None,
) -> list[str]:
    errors: list[str] = []
    _validate_meta(registry, errors)
    enumerated = _validate_anchors(registry, sibling, errors)
    _validate_negative_space(enumerated, scanned, errors)
    _validate_design_prose(registry, design_text, errors)
    return errors


def validate(repo_root: Path = REPOSITORY, registry_path: Path = DEFAULT_REGISTRY) -> None:
    registry, sibling, scanned, design_text = load_repository(repo_root, registry_path)
    errors = violations(registry, sibling, scanned, design_text)
    if errors:
        raise ValidationError("\n".join(errors))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = args.registry.resolve()
    try:
        validate(repo_root, registry_path)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Adaptive-layout ledger failed:\n{error}", file=sys.stderr)
        return 1
    registry, _, scanned, _ = load_repository(repo_root, registry_path)
    anchors = registry.get("anchors", [])
    native = sum(1 for a in anchors if isinstance(a, dict) and a.get("status") == NATIVE)
    print(
        f"Adaptive-layout ledger passed: {native} native anchor(s) cross-referenced from the "
        "sidebar-panels contract, every other S7 surface enumerated as target-no-native-anchor, "
        f"and no unenumerated width-driven breakpoint in the scan scope ({len(scanned)} found)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
