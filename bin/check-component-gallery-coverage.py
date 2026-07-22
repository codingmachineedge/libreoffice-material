#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Generate and validate the WIN-CONCEPT-003 component-gallery coverage ledger.

``WIN-CONCEPT-003`` (docs/WINDOWS_UI_INVENTORY.md) is the "Components gallery"
row: archive surface #11 "Components" from
``docs/design/00-windows-rewrite-contract.md``. It is a verification surface --
its purpose is to instantiate every Material component in every state so the
theme can be reviewed exhaustively. Its M-gate is spelled "SRC or test fixture":
a source-level artifact, not rendered pixels (pixels are the separate B/V gate).

This tool is that artifact. It is a fail-closed coverage contract that maps
every renderable Material part and every declared state in the canonical
``vcl/uiconfig/theme_definitions/material/definition.xml`` to exactly one
gallery cell, and pins the checked-in ledger to a fresh enumeration.

The cell list is GENERATED from the definition, never hand-maintained: silent
rot is the failure mode this guards. Enumeration reuses
``bin/check-material-theme.py``:

* ``check_material_theme.validate`` first runs the full Material theme contract
  over the definition, so a gallery can never be built over a broken theme, and
  yields the authoritative widget part/state counts;
* the walk here enumerates every widget control (every root child except the
  non-widget ``palette``/``shapes``/``metrics``/``style``/``settings``/
  ``typography`` sections), its parts, and its states, then cross-checks its
  totals against those authoritative counts so the two parsers can never
  silently diverge; and
* every ``check_material_theme.REQUIRED_PARTS`` control/part must resolve to at
  least one gallery cell.

Default mode validates that the checked-in ledger matches a fresh enumeration
exactly: a missing cell, an extra/phantom cell, a drifted state signature, count
drift, or any hand-edited metadata all fail closed. ``--regenerate`` rewrites the
ledger deterministically (stable sort, no timestamps).

This is source evidence only. It does not claim native implementation, a
successful build, dialog pixels, or any runtime interaction. The native fixture
``.ui`` and rendered pixels remain the separate B/V gate; the inventory owner is
unassigned and the ledger records only the proposed sfx2 dev/qa fixture home.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFINITION_REL = "vcl/uiconfig/theme_definitions/material/definition.xml"
DEFAULT_DEFINITION = REPOSITORY / DEFINITION_REL
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/component-gallery-coverage.json"
THEME_VALIDATOR_PATH = REPOSITORY / "bin/check-material-theme.py"

SCHEMA_VERSION = 1
CONTRACT = "windows-component-gallery-coverage"
INVENTORY_ROW = "WIN-CONCEPT-003"
SURFACE = "Components"
PLATFORM = "windows"
GENERATOR = "bin/check-component-gallery-coverage.py"

# Root children that declare tokens/geometry rather than renderable controls.
# This mirrors the exclusion set bin/check-material-theme.py uses when it counts
# widget parts, so the two walks enumerate the same set of controls.
NON_WIDGET_SECTIONS = frozenset(
    {"palette", "shapes", "metrics", "style", "settings", "typography"}
)

SOURCE_NOTE = (
    "Deterministic source-level gallery coverage ledger for WIN-CONCEPT-003. "
    "Regenerate with --regenerate. Every renderable Material part and declared "
    "state in the definition maps to exactly one gallery cell. Not a claim of "
    "native implementation, a successful build, dialog pixels, or any runtime "
    "evidence."
)

# The inventory owner for WIN-CONCEPT-003 is unassigned. This records the
# proposed native dev/qa fixture home without asserting the .ui exists yet; the
# closure ledger (WIN-SYS-016) will pick the file up once it is authored.
PROPOSED_FIXTURE = {
    "owner": "unassigned",
    "candidate_home": "sfx2/uiconfig/ui/componentgallery.ui",
    "note": (
        "Proposed sfx2 dev/qa fixture home for the Components gallery. The native "
        ".ui and rendered pixels are the separate B/V gate; this ledger is the "
        "source-level M-gate coverage contract only."
    ),
}


class ValidationError(RuntimeError):
    """Raised when the component-gallery coverage ledger is invalid."""


# --- Theme validator reuse -------------------------------------------------


def load_theme_validator(path: Path = THEME_VALIDATOR_PATH):
    """Import bin/check-material-theme.py as a module for parsing reuse."""

    spec = importlib.util.spec_from_file_location("check_material_theme", path)
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load theme validator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --- Enumeration -----------------------------------------------------------


def _canonical_state(state: ET.Element) -> dict[str, str]:
    """Return a state's attributes as a name-sorted mapping."""

    return {name: state.get(name, "") for name in sorted(state.attrib)}


def enumerate_gallery(
    root: ET.Element,
) -> tuple[list[dict[str, object]], list[dict[str, object]], int, int]:
    """Walk the definition tree into control and cell records.

    One gallery cell is produced per declared ``<state>``; a part with no
    declared state still yields one representative cell so every part is
    covered. Returns ``(controls, cells, part_total, state_total)``.
    """

    controls: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    part_total = 0
    state_total = 0

    for control in root:
        if not isinstance(control.tag, str) or control.tag in NON_WIDGET_SECTIONS:
            continue
        control_name = control.tag
        part_names: list[str] = []
        for part in control.findall("part"):
            part_total += 1
            part_name = part.get("value", "")
            part_names.append(part_name)
            states = part.findall("state")
            if not states:
                cells.append(
                    {
                        "cell_id": f"{control_name}/{part_name}/000",
                        "control": control_name,
                        "part": part_name,
                        "ordinal": 0,
                        "stateless": True,
                        "state": None,
                    }
                )
                continue
            for index, state in enumerate(states, start=1):
                state_total += 1
                cells.append(
                    {
                        "cell_id": f"{control_name}/{part_name}/{index:03d}",
                        "control": control_name,
                        "part": part_name,
                        "ordinal": index,
                        "stateless": False,
                        "state": _canonical_state(state),
                    }
                )
        controls.append({"control": control_name, "parts": part_names})

    return controls, cells, part_total, state_total


# --- Registry assembly -----------------------------------------------------


def build_registry(
    definition_path: Path, theme_module=None
) -> dict[str, object]:
    """Produce the full, deterministic ledger from the definition."""

    theme = theme_module if theme_module is not None else load_theme_validator()

    try:
        theme_result = theme.validate(definition_path)
    except (ET.ParseError, OSError, theme.ValidationError) as error:
        raise ValidationError(
            f"definition failed the Material theme contract: {error}"
        ) from error
    theme_part_count = theme_result[6]
    theme_state_count = theme_result[7]

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
    try:
        root = ET.parse(definition_path, parser=parser).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse {definition_path}: {error}") from error

    controls, cells, part_total, state_total = enumerate_gallery(root)

    # Cross-check the walk here against check-material-theme's authoritative
    # widget part/state counts; the two parsers must never silently diverge.
    if part_total != theme_part_count:
        raise ValidationError(
            f"enumerated {part_total} widget parts but the theme contract counts "
            f"{theme_part_count}"
        )
    if state_total != theme_state_count:
        raise ValidationError(
            f"enumerated {state_total} widget states but the theme contract counts "
            f"{theme_state_count}"
        )

    # Every required control/part named by the theme contract must be covered.
    covered_parts = {(cell["control"], cell["part"]) for cell in cells}
    for control_name, required_parts in sorted(theme.REQUIRED_PARTS.items()):
        for part_name in sorted(required_parts):
            if (control_name, part_name) not in covered_parts:
                raise ValidationError(
                    f"required control/part {control_name}/{part_name} has no "
                    f"gallery cell"
                )

    cells_sorted = sorted(cells, key=lambda cell: cell["cell_id"])
    cell_ids = [cell["cell_id"] for cell in cells_sorted]
    if len(cell_ids) != len(set(cell_ids)):
        duplicate = next(
            cell_id for cell_id in cell_ids if cell_ids.count(cell_id) > 1
        )
        raise ValidationError(f"duplicate gallery cell id: {duplicate}")

    counts = {
        "controls": len(controls),
        "parts": part_total,
        "states": state_total,
        "cells": len(cells_sorted),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "inventory_row": INVENTORY_ROW,
        "surface": SURFACE,
        "platform": PLATFORM,
        "generator": GENERATOR,
        "definition": DEFINITION_REL,
        "source_note": SOURCE_NOTE,
        "proposed_fixture": PROPOSED_FIXTURE,
        "counts": counts,
        "controls": controls,
        "cells": cells_sorted,
    }


# --- Registry file I/O -----------------------------------------------------


def serialize_registry(registry: Mapping[str, object]) -> str:
    """Serialize deterministically: stable order, 2-space indent, trailing LF."""

    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def write_registry(registry_path: Path, registry: Mapping[str, object]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialize_registry(registry))


def read_registry(registry_path: Path) -> dict[str, object]:
    try:
        text = registry_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(
            f"cannot read ledger {registry_path}: {error}"
        ) from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"ledger {registry_path} is not valid JSON: {error}"
        ) from error
    if not isinstance(data, dict):
        raise ValidationError(f"ledger {registry_path} must be a JSON object")
    return data


# --- Comparison ------------------------------------------------------------


def _format_keys(keys: Iterable[str], limit: int = 12) -> str:
    values = sorted(keys)
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; ... and {len(values) - limit} more"
    return "; ".join(shown) + suffix


def _index_by(
    records: object, key: str, section: str
) -> dict[str, Mapping[str, object]]:
    if not isinstance(records, list):
        raise ValidationError(f"ledger {section} section must be a list")
    index: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, dict) or key not in record:
            raise ValidationError(f"ledger {section} entry is malformed")
        identity = record[key]
        if not isinstance(identity, str):
            raise ValidationError(f"ledger {section} key must be a string")
        if identity in index:
            raise ValidationError(f"duplicate {section} entry in ledger: {identity}")
        index[identity] = record
    return index


def _diff_section(
    section: str, key: str, expected: object, actual: object
) -> list[str]:
    expected_index = _index_by(expected, key, section)
    actual_index = _index_by(actual, key, section)
    failures: list[str] = []

    missing = set(expected_index) - set(actual_index)
    stale = set(actual_index) - set(expected_index)
    if missing:
        failures.append(
            f"{len(missing)} {section} entr(y/ies) missing from ledger: "
            f"{_format_keys(missing)}"
        )
    if stale:
        failures.append(
            f"{len(stale)} {section} ledger entr(y/ies) with no matching source: "
            f"{_format_keys(stale)}"
        )
    for identity in sorted(set(expected_index) & set(actual_index)):
        if expected_index[identity] != actual_index[identity]:
            failures.append(
                f"{section} entry {identity!r} drifted from its generated mapping: "
                f"expected {expected_index[identity]!r}, found {actual_index[identity]!r}"
            )
    return failures


def compare_registry(
    expected: Mapping[str, object], actual: Mapping[str, object]
) -> None:
    """Fail closed with a focused diff when ``actual`` is not a fresh ledger."""

    failures: list[str] = []

    failures.extend(
        _diff_section("cell", "cell_id", expected.get("cells"), actual.get("cells"))
    )
    failures.extend(
        _diff_section(
            "control", "control", expected.get("controls"), actual.get("controls")
        )
    )

    for field in (
        "schema_version",
        "contract",
        "inventory_row",
        "surface",
        "platform",
        "generator",
        "definition",
        "source_note",
        "proposed_fixture",
        "counts",
    ):
        if expected.get(field) != actual.get(field):
            failures.append(
                f"ledger field {field!r} drifted: expected "
                f"{expected.get(field)!r}, found {actual.get(field)!r}"
            )

    if failures:
        raise ValidationError("\n".join(failures))


def validate(
    definition_path: Path, registry_path: Path, theme_module=None
) -> dict[str, object]:
    """Validate the checked-in ledger against a fresh enumeration."""

    expected = build_registry(definition_path, theme_module=theme_module)
    actual = read_registry(registry_path)
    compare_registry(expected, actual)
    return expected


# --- CLI -------------------------------------------------------------------


def _counts_text(counts: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--definition",
        type=Path,
        default=DEFAULT_DEFINITION,
        help="Material theme definition (default: the canonical definition.xml)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="coverage ledger JSON (default: component-gallery-coverage.json)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the ledger deterministically from a fresh enumeration",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    definition_path = args.definition.resolve()
    registry_path = args.registry.resolve()
    try:
        if args.regenerate:
            registry = build_registry(definition_path)
            write_registry(registry_path, registry)
        expected = validate(definition_path, registry_path)
    except ValidationError as error:
        print(
            f"Component gallery coverage contract failed:\n{error}",
            file=sys.stderr,
        )
        return 1

    counts = expected["counts"]
    assert isinstance(counts, dict)
    print(
        "Component gallery coverage contract passed: every Material part and "
        f"declared state maps to a gallery cell ({counts['cells']} cells)."
    )
    print(f"  counts: {_counts_text(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
