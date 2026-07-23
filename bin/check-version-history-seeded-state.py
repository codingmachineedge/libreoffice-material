#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Generate and validate the WIN-CONCEPT-002 version-history seeded-state ledger.

``WIN-CONCEPT-002`` (docs/WINDOWS_UI_INVENTORY.md) is the "Version history"
prototype-only design concept. Its named gate is "seeded-state/restore/compare
checks". This tool is that artifact: a fail-closed, deterministically regenerable
coverage ledger over the seeded ``HISTORY``/``DOCS`` fixture in site/prototype.html,
plus a provenance map binding each detail-pane affordance to real upstream reality in
sfx2/source/dialog/versdlg.cxx.

It proves exactly three honest things and no more:

1. the seeded fixture is internally coherent (12 entries, one current, every doc
   snapshot index in range, six docs, hash/word-delta shapes);
2. the ``historyBody`` render source gates restore on a real document snapshot and the
   current pill on the current flag, and never wires the restore control to a silent
   destructive dispatch; and
3. exactly two affordances have real upstream backing -- Compare-with-current maps to
   ``SID_DOCUMENT_COMPARE`` and view-comment to ``SfxViewVersionDialog_Impl`` -- while
   Branch / Export / restore-as-replace / whole-project-scope / auto-commit /
   word-delta / commit-hash are recorded as concept-only.

This is prototype-internal seeded-fixture coverage plus an upstream-provenance ledger:
it is explicitly weaker than a bind-to-real-upstream-data ledger and is **not** a claim
that a native auto-commit version engine, restore-as-replace, or any runtime behaviour
exists. ``runtime_verified`` is false throughout; the native timeline surface, the
destructive-restore flow, and all pixel/interaction evidence are the separate build
gates.

Default mode validates the checked-in ledger against a fresh enumeration; any missing,
extra, or drifted entry fails closed. ``--regenerate`` rewrites it deterministically
(stable sort by id, no timestamps).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
PROTOTYPE_REL = "site/prototype.html"
VERSDLG_REL = "sfx2/source/dialog/versdlg.cxx"
DEFAULT_PROTOTYPE = REPOSITORY / PROTOTYPE_REL
DEFAULT_VERSDLG = REPOSITORY / VERSDLG_REL
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/version-history-seeded-state.json"

SCHEMA_VERSION = 1
CONTRACT = "windows-version-history-seeded-state"
INVENTORY_ROW = "WIN-CONCEPT-002"
SURFACE = "Version history"
PLATFORM = "windows"
GENERATOR = "bin/check-version-history-seeded-state.py"
DESIGN_REFERENCE = "docs/design/12-base-math-shared.md"

ENTRY_FIELDS = ("id", "time", "group", "action", "icon", "hash", "author", "added", "removed", "file")
HASH_PATTERN = re.compile(r"^[0-9a-f]{7}$")

SOURCE_NOTE = (
    "Deterministic source-level seeded-state coverage ledger for WIN-CONCEPT-002. "
    "Regenerate with --regenerate. Source of truth is the inline seeded HISTORY/DOCS "
    "fixture in site/prototype.html plus a provenance map to real upstream versdlg.cxx "
    "SIDs. This is prototype-internal coverage + concept-vs-reality provenance, NOT a "
    "claim that a native auto-commit version engine, restore-as-replace, or any runtime "
    "evidence exists."
)

# Render-gating markers the historyBody() source must carry. Each must be present; the
# restore control must be gated on a real document snapshot and must never carry a
# destructive dispatch.
GATING_MARKERS = {
    "restore_gated_on_snapshot": "var restoreBtn = hdoc ?",
    "current_gated_on_current_flag": "var currentBtn = hs.current ?",
    "snapshot_gated_on_docIx": "var hdoc=(hs.docIx!=null)?DOCS[hs.docIx]:null;",
    "compare_present": "Compare with current",
    "selection_dispatch": 'data-act="set:histSel:',
}
RESTORE_LINE_MARKER = "var restoreBtn = hdoc ?"
RESTORE_LABEL = "Restore this version"
DESTRUCTIVE_TOKEN = "data-act"

# Provenance: concept affordances that DO have real upstream backing, and those that do
# not. The backed markers must resolve in versdlg.cxx.
PROVENANCE_BACKED = (
    {
        "affordance": "compare-with-current",
        "upstream": "SID_DOCUMENT_COMPARE",
        "source": VERSDLG_REL,
        "markers": ["SID_DOCUMENT_COMPARE"],
    },
    {
        "affordance": "view-comment",
        "upstream": "SfxViewVersionDialog_Impl",
        "source": VERSDLG_REL,
        "markers": ["SfxViewVersionDialog_Impl"],
    },
)
PROVENANCE_CONCEPT_ONLY = (
    "branch",
    "export",
    "restore-as-replace",
    "whole-project-scope",
    "auto-commit",
    "word-delta",
    "commit-hash",
)

PROPOSED_FIXTURE = {
    "owner": "unassigned",
    "candidate_home": "sfx2 document model",
    "note": (
        "Candidate native owner for a Version-history timeline surface. The native .ui, "
        "the auto-commit engine, and rendered pixels are the separate build gates; this "
        "ledger is the source-level seeded-state coverage contract only."
    ),
}


class ValidationError(RuntimeError):
    """Raised when the version-history seeded-state ledger is invalid."""


# --- Quote-aware extraction ------------------------------------------------


def _balanced_region(text: str, open_index: int, open_char: str, close_char: str) -> str:
    """Return the balanced ``open_char``..``close_char`` region starting at
    ``open_index``, respecting single/double-quoted JS strings (so commas, colons,
    and nested different-quote characters inside strings never mis-split)."""

    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[open_index : index + 1]
    raise ValidationError(f"unbalanced {open_char!r} region starting at index {open_index}")


def _split_top_level(body: str, separator: str = ",") -> list[str]:
    """Split ``body`` on ``separator`` at bracket depth 0, respecting quotes."""

    parts: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    current: list[str] = []
    for char in body:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
        elif char in "[{(":
            depth += 1
            current.append(char)
        elif char in ")}]":
            depth -= 1
            current.append(char)
        elif char == separator and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _parse_value(raw: str) -> object:
    value = raw.strip()
    if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except ValueError as error:
        raise ValidationError(f"un-parseable seeded value {raw!r}") from error


def _parse_object(object_text: str) -> dict[str, object]:
    inner = object_text.strip()
    if not (inner.startswith("{") and inner.endswith("}")):
        raise ValidationError(f"expected a brace object, got {object_text!r}")
    record: dict[str, object] = {}
    for field in _split_top_level(inner[1:-1]):
        field = field.strip()
        if not field:
            continue
        key, _, raw = field.partition(":")
        key = key.strip()
        if not key or not _:
            raise ValidationError(f"malformed seeded field {field!r}")
        record[key] = _parse_value(raw)
    return record


# --- Enumeration -----------------------------------------------------------


def enumerate_history(prototype_text: str) -> list[dict[str, object]]:
    match = re.search(r"\bvar\s+HISTORY\s*=\s*\[", prototype_text)
    if match is None:
        raise ValidationError("var HISTORY=[ declaration not found in the prototype")
    array = _balanced_region(prototype_text, match.end() - 1, "[", "]")
    objects = [chunk for chunk in _split_top_level(array[1:-1]) if chunk.strip()]
    entries = [_normalize_entry(_parse_object(obj)) for obj in objects]
    return sorted(entries, key=lambda entry: entry["id"])


def _normalize_entry(raw: Mapping[str, object]) -> dict[str, object]:
    entry: dict[str, object] = {}
    for field in ENTRY_FIELDS:
        if field not in raw:
            raise ValidationError(f"seeded entry missing required field {field!r}: {raw!r}")
        entry[field] = raw[field]
    entry["docIx"] = raw.get("docIx")
    entry["current"] = bool(raw.get("current", False))
    return entry


def count_docs(prototype_text: str) -> int:
    docs_match = re.search(r"\bvar\s+DOCS\s*=", prototype_text)
    hist_match = re.search(r"\bvar\s+HISTORY\s*=", prototype_text)
    if docs_match is None or hist_match is None:
        raise ValidationError("var DOCS / var HISTORY declarations not found")
    block = prototype_text[docs_match.start() : hist_match.start()]
    return len(re.findall(r"\{\s*title\s*:", block))


# --- Source-contract validation --------------------------------------------


def validate_fixture(entries: Sequence[Mapping[str, object]], docs_count: int) -> None:
    if len(entries) != 12:
        raise ValidationError(f"expected 12 seeded history entries, found {len(entries)}")
    if docs_count != 6:
        raise ValidationError(f"expected 6 seeded DOCS records, found {docs_count}")

    ids = [entry["id"] for entry in entries]
    if sorted(ids) != list(range(12)):
        raise ValidationError(f"seeded entry ids must be exactly 0..11, found {sorted(ids)}")

    current = [entry["id"] for entry in entries if entry["current"]]
    if len(current) != 1:
        raise ValidationError(f"exactly one entry must be current, found {len(current)}: {current}")

    for entry in entries:
        docix = entry["docIx"]
        if docix is not None:
            if not isinstance(docix, int) or not 0 <= docix < docs_count:
                raise ValidationError(
                    f"entry {entry['id']}: docIx {docix!r} out of range [0, {docs_count})"
                )
        for delta in ("added", "removed"):
            value = entry[delta]
            if not isinstance(value, int) or value < 0:
                raise ValidationError(f"entry {entry['id']}: {delta} must be a non-negative integer")
        if not (isinstance(entry["hash"], str) and HASH_PATTERN.match(entry["hash"])):
            raise ValidationError(f"entry {entry['id']}: hash {entry['hash']!r} is not a 7-hex id")


def validate_gating(prototype_text: str) -> None:
    for key, marker in GATING_MARKERS.items():
        if marker not in prototype_text:
            raise ValidationError(f"render gating marker missing ({key}: {marker!r})")
    # The restore control must not carry a destructive dispatch: its single-line
    # definition must name the Restore label but contain no data-act binding.
    line = _line_containing(prototype_text, RESTORE_LINE_MARKER)
    if RESTORE_LABEL not in line:
        raise ValidationError("restore control line does not render the Restore label")
    if DESTRUCTIVE_TOKEN in line:
        raise ValidationError(
            "restore control is wired to a destructive dispatch (data-act); the prototype "
            "restore must stay a non-committing affordance"
        )


def _line_containing(text: str, marker: str) -> str:
    index = text.find(marker)
    if index == -1:
        raise ValidationError(f"marker {marker!r} not found")
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start : end if end != -1 else len(text)]


def validate_provenance(versdlg_text: str) -> None:
    for backed in PROVENANCE_BACKED:
        for marker in backed["markers"]:
            if marker not in versdlg_text:
                raise ValidationError(
                    f"provenance:{backed['affordance']}:upstream marker {marker!r} missing "
                    f"from {VERSDLG_REL}"
                )


# --- Registry assembly -----------------------------------------------------


def build_registry(prototype_text: str, versdlg_text: str) -> dict[str, object]:
    entries = enumerate_history(prototype_text)
    docs_count = count_docs(prototype_text)
    validate_fixture(entries, docs_count)
    validate_gating(prototype_text)
    validate_provenance(versdlg_text)

    counts = {
        "entries": len(entries),
        "current": sum(1 for entry in entries if entry["current"]),
        "docs": docs_count,
        "with_snapshot": sum(1 for entry in entries if entry["docIx"] is not None),
        "groups": len({entry["group"] for entry in entries}),
    }

    provenance = {
        "backed": [
            {"affordance": item["affordance"], "upstream": item["upstream"], "source": item["source"]}
            for item in PROVENANCE_BACKED
        ],
        "concept_only": list(PROVENANCE_CONCEPT_ONLY),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "inventory_row": INVENTORY_ROW,
        "surface": SURFACE,
        "platform": PLATFORM,
        "generator": GENERATOR,
        "prototype": PROTOTYPE_REL,
        "design_reference": DESIGN_REFERENCE,
        "runtime_verified": False,
        "source_note": SOURCE_NOTE,
        "proposed_fixture": PROPOSED_FIXTURE,
        "counts": counts,
        "gating": dict(GATING_MARKERS),
        "provenance": provenance,
        "entries": entries,
    }


# --- Registry file I/O -----------------------------------------------------


def serialize_registry(registry: Mapping[str, object]) -> str:
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def write_registry(registry_path: Path, registry: Mapping[str, object]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialize_registry(registry))


def read_registry(registry_path: Path) -> dict[str, object]:
    try:
        text = registry_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read ledger {registry_path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"ledger {registry_path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError(f"ledger {registry_path} must be a JSON object")
    return data


# --- Comparison ------------------------------------------------------------


def _format_keys(keys: Iterable[str], limit: int = 12) -> str:
    values = sorted(keys)
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; ... and {len(values) - limit} more"
    return "; ".join(shown) + suffix


def _index_entries(records: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(records, list):
        raise ValidationError("ledger entries section must be a list")
    index: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, dict) or "id" not in record:
            raise ValidationError("ledger entry is malformed")
        key = str(record["id"])
        if key in index:
            raise ValidationError(f"duplicate entry in ledger: id {key}")
        index[key] = record
    return index


def compare_registry(expected: Mapping[str, object], actual: Mapping[str, object]) -> None:
    failures: list[str] = []

    expected_index = _index_entries(expected.get("entries"))
    actual_index = _index_entries(actual.get("entries"))
    missing = set(expected_index) - set(actual_index)
    stale = set(actual_index) - set(expected_index)
    if missing:
        failures.append(f"{len(missing)} entr(y/ies) missing from ledger: {_format_keys(missing)}")
    if stale:
        failures.append(
            f"{len(stale)} ledger entr(y/ies) with no matching seeded entry: {_format_keys(stale)}"
        )
    for key in sorted(set(expected_index) & set(actual_index)):
        if expected_index[key] != actual_index[key]:
            failures.append(
                f"entry {key} drifted from its generated mapping: "
                f"expected {expected_index[key]!r}, found {actual_index[key]!r}"
            )

    for field in (
        "schema_version",
        "contract",
        "inventory_row",
        "surface",
        "platform",
        "generator",
        "prototype",
        "design_reference",
        "runtime_verified",
        "source_note",
        "proposed_fixture",
        "counts",
        "gating",
        "provenance",
    ):
        if expected.get(field) != actual.get(field):
            failures.append(
                f"ledger field {field!r} drifted: expected {expected.get(field)!r}, "
                f"found {actual.get(field)!r}"
            )

    if failures:
        raise ValidationError("\n".join(failures))


def validate(prototype_path: Path, versdlg_path: Path, registry_path: Path) -> dict[str, object]:
    expected = build_registry(
        prototype_path.read_text(encoding="utf-8"),
        versdlg_path.read_text(encoding="utf-8"),
    )
    actual = read_registry(registry_path)
    compare_registry(expected, actual)
    return expected


# --- CLI -------------------------------------------------------------------


def _counts_text(counts: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prototype", type=Path, default=DEFAULT_PROTOTYPE)
    parser.add_argument("--versdlg", type=Path, default=DEFAULT_VERSDLG)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the ledger deterministically from a fresh enumeration",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    prototype_path = args.prototype.resolve()
    versdlg_path = args.versdlg.resolve()
    registry_path = args.registry.resolve()
    try:
        if args.regenerate:
            registry = build_registry(
                prototype_path.read_text(encoding="utf-8"),
                versdlg_path.read_text(encoding="utf-8"),
            )
            write_registry(registry_path, registry)
        expected = validate(prototype_path, versdlg_path, registry_path)
    except (OSError, ValidationError) as error:
        print(f"Version-history seeded-state ledger failed:\n{error}", file=sys.stderr)
        return 1

    counts = expected["counts"]
    assert isinstance(counts, dict)
    print(
        "Version-history seeded-state ledger passed: the seeded fixture is coherent, the "
        "restore/current/compare gating is intact, and the concept-vs-upstream provenance "
        f"map holds ({counts['entries']} entries, {counts['docs']} docs)."
    )
    print(f"  counts: {_counts_text(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
