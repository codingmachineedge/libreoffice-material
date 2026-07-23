#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Generate and validate the WIN-CONCEPT-001 Features command-catalog ledger.

``WIN-CONCEPT-001`` (docs/WINDOWS_UI_INVENTORY.md) is the "Features command
catalog" row: the suite-level command inventory specified in
``docs/design/12-base-math-shared.md`` 12.3. Its M-gate is a source-level
artifact, not rendered pixels (the native ``.ui`` surface and the Run-command
UNO dispatch are the separate B/V gate). This tool is that artifact.

It is a fail-closed coverage contract that binds every row of the checked-in
catalog ``site/prototype-features.json`` (a mirror of the LibreOffice command
inventory, rows of the form ``[name, scope, category, uno-command]``) to a real
``.uno:`` command registration in the ten officecfg ``Office/UI/*Commands.xcu``
files, and pins the checked-in ledger to a fresh enumeration. It is the direct
analogue of ``bin/check-component-gallery-coverage.py`` (WIN-CONCEPT-003)
applied to officecfg instead of ``definition.xml``.

Resolution (per catalog row, ``base`` = the command with any ``?...`` parameter
suffix stripped) is dispatch-first, so the class records where the command's
real dispatch target is registered:

* ``exact-in-module``   -- a non-parameterized command registered verbatim in
  its own module's file, or a parameterized command whose exact node exists in
  its own module file with no separately-registered base;
* ``base-in-module``    -- a parameterized command whose base (dispatch target)
  is registered in its own module file (a parameter fan of a module command);
* ``base-cross-file``   -- a parameterized command whose base is registered only
  in another module's file (e.g. ``.uno:StyleApply`` / ``.uno:AutoCorrectDlg``
  dispatched from GenericCommands);
* ``exact-cross-file``  -- a command registered verbatim only in another file;
* ``unresolved``        -- the command binds to no registered node anywhere.

The contract fails closed if any row is ``unresolved``, so a dropped catalog
row, a renamed/removed officecfg node, or a parser that silently drops the
parameter-carrying / ``install:module`` / Popups nodes all surface here. The
officecfg walk deliberately collects the *whole* ``UserInterface`` subtree
(both ``Commands`` and ``Popups``) using ElementTree -- the node element tag is
the unqualified ``node`` while the identifying attribute is the namespaced
``{http://openoffice.org/2001/registry}name`` -- so the parameter-bearing and
``install:module`` (LibreLogo) nodes are never lost the way a naive
``oor:op="replace">``-terminated regex loses them.

The ledger also pins: the compound selection identity
``UNO command + U+241F + display name`` being unique across all rows (which is
what resolves the duplicate display names), the per-scope and per-category
counts over their closed value sets, the eleven scope -> module -> officecfg
file bindings, and the normative render cap, cross-checked against
``docs/design/12-base-math-shared.md`` 12.3 so the ledger constant and the
design constant can never drift apart.

Default mode validates that the checked-in ledger matches a fresh enumeration
exactly; ``--regenerate`` rewrites it deterministically (stable sort by the
identity key, no timestamps).

This is source evidence only. It does not claim a native Features surface, a
successful build, rendered pixels, Run-command dispatch, or any runtime
interaction. It proves the catalog is a faithful subset of the officecfg
registrations; it does not prove officecfg is complete versus the running
product, nor that the labels are localized, nor that the cap performs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
CATALOG_REL = "site/prototype-features.json"
UI_DIR_REL = "officecfg/registry/data/org/openoffice/Office/UI"
DESIGN_REL = "docs/design/12-base-math-shared.md"
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/features-command-catalog.json"

SCHEMA_VERSION = 1
CONTRACT = "windows-features-command-catalog"
INVENTORY_ROW = "WIN-CONCEPT-001"
SURFACE = "Features"
PLATFORM = "windows"
GENERATOR = "bin/check-features-command-catalog.py"

# The unit-separator SYMBOL that the prototype uses to build the compound
# selection identity (docs/design/12-base-math-shared.md 12.3 "Selection
# identity"): UNO command + U+241F + display name.
IDENTITY_SEPARATOR = "␟"
IDENTITY_SEPARATOR_LABEL = "U+241F"

# The normative render cap (docs/design/12-base-math-shared.md 12.3 "Capped
# list"): the list renders at most this many rows. Cross-checked against the
# design chapter so the ledger constant and the prose constant cannot drift.
RENDER_CAP = 400

# Module tag (catalog field 2) -> officecfg Office/UI file basename. The catalog
# scope labels ("Writer", "Draw & Impress", ...) map onto these module tags.
MODULE_FILES = {
    "basic": "BasicIDECommands",
    "biblio": "BibliographyCommands",
    "calc": "CalcCommands",
    "chart": "ChartCommands",
    "dbu": "DbuCommands",
    "math": "MathCommands",
    "report": "ReportCommands",
    "sd": "DrawImpressCommands",
    "shared": "GenericCommands",
    "writer": "WriterCommands",
}

# The eleven Features scopes (docs/design/12-base-math-shared.md 12.3) bound to
# their module tag and officecfg file. "All features" is the union of every
# scope and owns no single file.
SCOPE_BINDINGS = [
    {"scope": "All features", "module": None, "officecfg_file": None},
    {"scope": "Common", "module": "shared"},
    {"scope": "Writer", "module": "writer"},
    {"scope": "Calc", "module": "calc"},
    {"scope": "Draw & Impress", "module": "sd"},
    {"scope": "Charts", "module": "chart"},
    {"scope": "Math", "module": "math"},
    {"scope": "Base", "module": "dbu"},
    {"scope": "Reports", "module": "report"},
    {"scope": "Basic IDE", "module": "basic"},
    {"scope": "Bibliography", "module": "biblio"},
]

# The closed category value set (catalog field 3).
CATEGORIES = frozenset(
    {
        "Command",
        "Data",
        "Draw",
        "Edit",
        "File",
        "Format",
        "Insert",
        "Slides",
        "Tools",
        "View",
    }
)

RESOLUTION_CLASSES = (
    "exact-in-module",
    "base-in-module",
    "base-cross-file",
    "exact-cross-file",
)

OOR_NAME_ATTR = "{http://openoffice.org/2001/registry}name"

SOURCE_NOTE = (
    "Deterministic source-level command-catalog coverage ledger for "
    "WIN-CONCEPT-001. Regenerate with --regenerate. Every catalog row in "
    "site/prototype-features.json binds to a real .uno command registration in "
    "the officecfg Office/UI/*Commands.xcu files; 0 rows may be unresolved. It "
    "proves the catalog is a faithful subset of the officecfg registrations; it "
    "is not a claim of a native Features surface, a successful build, rendered "
    "pixels, Run-command dispatch, localization, or any runtime evidence."
)

# The inventory owner for WIN-CONCEPT-001 is unassigned. This records the
# proposed native home without asserting the .ui or the dispatch exists yet;
# they are the separate B/V gate.
PROPOSED_FIXTURE = {
    "owner": "unassigned",
    "candidate_module": "framework",
    "note": (
        "The native Features .ui surface and the Run-command UNO dispatch are "
        "the separate B/V gate; this ledger is the source-level M-gate coverage "
        "contract only."
    ),
}


class ValidationError(RuntimeError):
    """Raised when the Features command-catalog ledger is invalid."""


# --- Source loading --------------------------------------------------------


def _read_text(repo_root: Path, rel: str) -> str:
    try:
        return (repo_root / rel).read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {rel}: {error}") from error


def load_catalog(repo_root: Path) -> list[list[str]]:
    """Load and structurally validate the prototype command catalog."""

    text = _read_text(repo_root, CATALOG_REL)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"{CATALOG_REL} is not valid JSON: {error}") from error
    if not isinstance(data, list) or not data:
        raise ValidationError(f"{CATALOG_REL} must be a non-empty JSON array")
    rows: list[list[str]] = []
    for index, row in enumerate(data):
        if (
            not isinstance(row, list)
            or len(row) != 4
            or not all(isinstance(value, str) for value in row)
        ):
            raise ValidationError(
                f"{CATALOG_REL} row {index} must be [name, scope, category, command] strings"
            )
        rows.append(row)
    return rows


def collect_uno_nodes(repo_root: Path, basename: str) -> set[str]:
    """Return every ``.uno:...`` node name declared anywhere in one xcu file.

    The whole ``UserInterface`` subtree is walked (both ``Commands`` and
    ``Popups``); the node element tag is the unqualified ``node`` and the
    identifying attribute is the namespaced ``{registry}name``, so
    parameter-bearing and ``install:module`` nodes are collected intact.
    """

    rel = f"{UI_DIR_REL}/{basename}.xcu"
    path = repo_root / rel
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse {rel}: {error}") from error
    names = {
        node.get(OOR_NAME_ATTR, "")
        for node in root.iter("node")
        if node.get(OOR_NAME_ATTR, "").startswith(".uno:")
    }
    if not names:
        raise ValidationError(f"{rel} declared no .uno command nodes")
    return names


def load_module_sets(repo_root: Path) -> dict[str, set[str]]:
    """Map each officecfg file basename to its set of registered .uno nodes."""

    return {
        basename: collect_uno_nodes(repo_root, basename)
        for basename in sorted(set(MODULE_FILES.values()))
    }


# --- Resolution ------------------------------------------------------------


def _officecfg_rel(basename: str) -> str:
    return f"{UI_DIR_REL}/{basename}.xcu"


def resolve_command(
    scope: str, command: str, module_sets: Mapping[str, set[str]]
) -> tuple[str, str | None]:
    """Return ``(resolution_class, resolving_file)`` for one catalog command.

    Dispatch-first: the base (parameter-stripped) command is resolved before the
    verbatim parameterized node, so a parameter fan is attributed to the module
    that actually registers its dispatch target.
    """

    module = MODULE_FILES[scope]
    own = module_sets[module]
    others = [name for name in sorted(module_sets) if name != module]
    base = command.split("?", 1)[0]
    has_param = "?" in command

    if base in own:
        klass = "base-in-module" if has_param else "exact-in-module"
        return klass, _officecfg_rel(module)
    for other in others:
        if base in module_sets[other]:
            return "base-cross-file", _officecfg_rel(other)
    # The base handler is not separately registered anywhere; fall back to the
    # verbatim (parameterized) node, which is a real registration in its own
    # right.
    if command in own:
        return "exact-in-module", _officecfg_rel(module)
    for other in others:
        if command in module_sets[other]:
            return "exact-cross-file", _officecfg_rel(other)
    return "unresolved", None


# --- Registry assembly -----------------------------------------------------


def build_registry(repo_root: Path = REPOSITORY) -> dict[str, object]:
    """Produce the full, deterministic ledger from the checked-in sources."""

    repo_root = repo_root.resolve()
    rows = load_catalog(repo_root)
    module_sets = load_module_sets(repo_root)

    commands: list[dict[str, object]] = []
    identity_keys: set[str] = set()
    per_scope: dict[str, int] = {}
    per_category: dict[str, int] = {}
    class_counts: dict[str, int] = {klass: 0 for klass in RESOLUTION_CLASSES}
    unresolved: list[str] = []

    for name, scope, category, command in rows:
        if scope not in MODULE_FILES:
            raise ValidationError(
                f"catalog command {command!r} has unknown scope {scope!r}"
            )
        if category not in CATEGORIES:
            raise ValidationError(
                f"catalog command {command!r} has unknown category {category!r}"
            )
        if not command.startswith(".uno:"):
            raise ValidationError(
                f"catalog command {command!r} ({name!r}) is not a .uno command"
            )

        identity_key = f"{command}{IDENTITY_SEPARATOR}{name}"
        if identity_key in identity_keys:
            raise ValidationError(
                f"duplicate selection identity for command {command!r} name {name!r}"
            )
        identity_keys.add(identity_key)

        klass, resolving_file = resolve_command(scope, command, module_sets)
        if klass == "unresolved":
            unresolved.append(f"{scope}:{command}")
            continue
        class_counts[klass] = class_counts.get(klass, 0) + 1
        per_scope[scope] = per_scope.get(scope, 0) + 1
        per_category[category] = per_category.get(category, 0) + 1

        commands.append(
            {
                "identity_key": identity_key,
                "name": name,
                "scope": scope,
                "category": category,
                "command": command,
                "resolution_class": klass,
                "resolving_file": resolving_file,
            }
        )

    if unresolved:
        shown = "; ".join(sorted(unresolved)[:12])
        suffix = "" if len(unresolved) <= 12 else f"; ... and {len(unresolved) - 12} more"
        raise ValidationError(
            f"{len(unresolved)} catalog command(s) resolve to no officecfg node: "
            f"{shown}{suffix}"
        )

    commands_sorted = sorted(commands, key=lambda entry: entry["identity_key"])

    # Drop the resolution classes that never occur so the ledger records only
    # the classes actually present, but always keep a deterministic order.
    resolution_class_counts = {
        klass: class_counts[klass]
        for klass in RESOLUTION_CLASSES
        if class_counts.get(klass, 0)
    }

    counts = {
        "total": len(commands_sorted),
        "resolution_classes": resolution_class_counts,
        "unresolved": len(unresolved),
        "per_scope": {scope: per_scope[scope] for scope in sorted(per_scope)},
        "per_category": {cat: per_category[cat] for cat in sorted(per_category)},
    }

    scope_bindings = _resolved_scope_bindings()

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "inventory_row": INVENTORY_ROW,
        "surface": SURFACE,
        "platform": PLATFORM,
        "generator": GENERATOR,
        "catalog": CATALOG_REL,
        "design_reference": DESIGN_REL,
        "identity_separator": IDENTITY_SEPARATOR_LABEL,
        "render_cap": RENDER_CAP,
        "source_note": SOURCE_NOTE,
        "proposed_fixture": PROPOSED_FIXTURE,
        "scope_bindings": scope_bindings,
        "counts": counts,
        "commands": commands_sorted,
    }


def _resolved_scope_bindings() -> list[dict[str, object]]:
    bindings: list[dict[str, object]] = []
    for binding in SCOPE_BINDINGS:
        module = binding["module"]
        officecfg_file = (
            None if module is None else _officecfg_rel(MODULE_FILES[module])
        )
        bindings.append(
            {
                "scope": binding["scope"],
                "module": module,
                "officecfg_file": officecfg_file,
            }
        )
    return bindings


# --- Design-reference cross-check ------------------------------------------


def validate_design_reference(repo_root: Path, render_cap: int) -> None:
    """Assert docs/design/12-base-math-shared.md 12.3 pins the same render cap.

    The design chapter is the normative home of the Features surface; binding
    the ledger's ``render_cap`` to the prose constant means neither can drift
    silently. The subsection this checker adds owns a machine-readable anchor.
    """

    text = _read_text(repo_root, DESIGN_REL)
    if "Source binding (normative)" not in text:
        raise ValidationError(
            f"{DESIGN_REL} 12.3 is missing the 'Source binding (normative)' subsection"
        )
    match = re.search(r"render cap at \*\*(\d+)\*\* rows", text)
    if match is None:
        raise ValidationError(
            f"{DESIGN_REL} 12.3 is missing the machine-readable render-cap anchor "
            "('render cap at **N** rows')"
        )
    doc_cap = int(match.group(1))
    if doc_cap != render_cap:
        raise ValidationError(
            f"render cap drift: ledger pins {render_cap} but {DESIGN_REL} 12.3 "
            f"states {doc_cap}"
        )


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


def _index_by(records: object, key: str, section: str) -> dict[str, Mapping[str, object]]:
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


def _diff_section(section: str, key: str, expected: object, actual: object) -> list[str]:
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
        _diff_section(
            "command", "identity_key", expected.get("commands"), actual.get("commands")
        )
    )

    for field in (
        "schema_version",
        "contract",
        "inventory_row",
        "surface",
        "platform",
        "generator",
        "catalog",
        "design_reference",
        "identity_separator",
        "render_cap",
        "source_note",
        "proposed_fixture",
        "scope_bindings",
        "counts",
    ):
        if expected.get(field) != actual.get(field):
            failures.append(
                f"ledger field {field!r} drifted: expected "
                f"{expected.get(field)!r}, found {actual.get(field)!r}"
            )

    if failures:
        raise ValidationError("\n".join(failures))


def validate(repo_root: Path, registry_path: Path) -> dict[str, object]:
    """Validate the checked-in ledger against a fresh enumeration."""

    expected = build_registry(repo_root)
    actual = read_registry(registry_path)
    compare_registry(expected, actual)
    validate_design_reference(repo_root, int(expected["render_cap"]))  # type: ignore[arg-type]
    return expected


# --- CLI -------------------------------------------------------------------


def _counts_text(counts: Mapping[str, object]) -> str:
    classes = counts.get("resolution_classes", {})
    assert isinstance(classes, dict)
    return ", ".join(f"{key}={classes[key]}" for key in sorted(classes))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPOSITORY,
        help="repository root to read sources from (default: script repository)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="coverage ledger JSON (default: features-command-catalog.json)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the ledger deterministically from a fresh enumeration",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = args.registry.resolve()
    try:
        if args.regenerate:
            registry = build_registry(repo_root)
            write_registry(registry_path, registry)
        expected = validate(repo_root, registry_path)
    except ValidationError as error:
        print(
            f"Features command-catalog contract failed:\n{error}",
            file=sys.stderr,
        )
        return 1

    counts = expected["counts"]
    assert isinstance(counts, dict)
    print(
        "Features command-catalog contract passed: "
        f"{counts['total']} catalog commands bound to officecfg registrations "
        f"({counts['unresolved']} unresolved)."
    )
    print(f"  resolution: {_counts_text(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
