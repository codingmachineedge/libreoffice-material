#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed .ui structural conformance gate for the module notebookbars.

``qa/windows-ui-contract/notebookbar-ui-conformance.json`` pins the Material
structural markers that are expressible in the notebookbar ``.ui`` XML itself,
across every module notebookbar surface owned by Writer/Calc/Draw/Impress
(``sw``/``sc``/``sd/sdraw``/``sd/simpress``). It is the counterpart to
``notebookbar-composition.json`` (WIN-NAV-004): that contract pins the guarded
*source* colour decisions (group-area @surface wash, tab-row underline/hairline)
and deliberately declares the ``.ui`` geometry out of its scope --
    "the 96px group height / 8px padding / command-chip .ui geometry ...
     remain .ui/build-bound work outside this contract".
This checker owns exactly that left-behind ``.ui`` layer.

STRUCTURAL FAMILIES (classified from the parsed XML, never from the filename):

* ``tabbed`` -- the ribbon ``notebookbar.ui`` of each module. Command groups are
  ``GtkGrid id="gd..."`` cells that already declare Material ``row-spacing`` +
  ``column-spacing``, carry a group-caption ``GtkLabel``, are divided by
  ``GtkSeparator`` rules, and drive the collapse machinery
  (``sfxlo-PriorityHBox`` / ``-PriorityMergedHBox`` / ``-DropdownBox`` /
  ``-NotebookbarToolBox`` / ``-NotebookbarTabControl``). This is the family the
  design ribbon chapter (docs/design/05-navigation.md section 4) describes.
* ``groups`` -- the ``notebookbar_groups.ui`` layout: a ``GtkBox``-``spacing``
  strip with no ``gd`` grids and no priority machinery, already zero-padding.
* ``grouped-compact-single`` -- the grouped-bar / compact / single-row legacy
  layouts. These still express inter-group spacing through legacy
  ``GtkSeparator`` child-packing ``padding`` and declare no grid/box spacing.

ACCEPTANCE ("rewritten-material" for the ``.ui`` layer):

* ``tabbed``   : group grids declare row+column spacing, dividers present, the
                 file carries ZERO legacy child-packing ``padding`` (the grid
                 spacing is the Material spacing), and the conformance marker is
                 present and self-declares ``family=tabbed``.
* ``groups``   : ``GtkBox`` spacing declared, dividers present, zero legacy
                 padding, conformance marker present self-declaring
                 ``family=groups``.
* ``grouped-compact-single`` : held at ``in-progress``. The legacy
                 separator-padding -> Material grid/box spacing conversion is
                 build-bound (a blind rewrite would alter the shared stock
                 layout with no local build to verify parity), so this family is
                 pinned as a regression net -- dividers present, collapse
                 machinery preserved, conformance marker present self-declaring
                 ``family=grouped-compact-single`` -- and its flip to
                 rewritten-material is tracked, not yet claimed.

The conformance marker is an inert XML comment
``<!-- material-notebookbar-ui-conformance family=<fam> wave=1 cluster=2 -->``
inserted after the ``<requires lib="LibreOffice" .../>`` line. Comments are
ignored by GtkBuilder/VclBuilder (these files already ship such comments), so
the stock render is byte-identical; the marker only makes each surface's
enrolment and self-declared family machine-checkable.

Default mode validates the checked-in contract against a fresh derivation from
the live ``.ui`` tree and fails closed on: a surface added/removed from the
owned set (file-set parity), any marker drift (a stripped divider, a
reintroduced legacy padding, a removed collapse-machinery class, a deleted or
family-mismatched marker), any status regression versus the committed baseline
(rewritten-material -> in-progress), and any coverage miscount. ``--regenerate``
rewrites the contract deterministically from the tree (pins migrate to assert
the new structure, they are never hand-weakened).

This is a source-level ``.ui`` structural ledger: ``runtime_verified`` is false
-- no native build, notebookbar pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/notebookbar-ui-conformance.json"
REGISTRY_REL = "qa/windows-ui-contract/notebookbar-ui-conformance.json"

SCHEMA_VERSION = 1
CONTRACT = "windows-notebookbar-ui-conformance"
PLATFORM = "windows"
GENERATOR = "bin/check-windows-notebookbar-ui-conformance.py"
DESIGN_REF = "docs/design/05-navigation.md#4"
CROSS_REFERENCE = "qa/windows-ui-contract/notebookbar-composition.json"

SOURCE_NOTE = (
    "Deterministic source-level .ui structural conformance ledger for the module "
    "notebookbars (sw/sc/sd). Regenerate with --regenerate. Counterpart to "
    "notebookbar-composition.json (source colour guards); this contract owns the .ui "
    "geometry layer that one explicitly excludes. Not a claim of native build or "
    "runtime evidence."
)

# The git pathspecs enumerating the owned surfaces -- one per module notebookbar
# directory. File-set parity is asserted against this fresh enumeration.
OWNED_PATHSPECS: Sequence[str] = (
    "sw/uiconfig/swriter/ui/notebookbar*.ui",
    "sc/uiconfig/scalc/ui/notebookbar*.ui",
    "sd/uiconfig/sdraw/ui/notebookbar*.ui",
    "sd/uiconfig/simpress/ui/notebookbar*.ui",
)

# The collapse / optical-grouping machinery classes whose presence multiset is
# pinned per surface so a future edit cannot silently strip the priority-collapse
# behaviour. Fixed order -> deterministic serialisation.
MACHINERY_CLASSES: Sequence[str] = (
    "sfxlo-NotebookbarTabControl",
    "sfxlo-ContextVBox",
    "sfxlo-PriorityHBox",
    "sfxlo-PriorityMergedHBox",
    "sfxlo-DropdownBox",
    "sfxlo-NotebookbarToolBox",
)

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in-progress"
STATUS_REWRITTEN = "rewritten-material"
STATUS_ORDINAL = {STATUS_PENDING: 0, STATUS_IN_PROGRESS: 1, STATUS_REWRITTEN: 2}

FAMILY_TABBED = "tabbed"
FAMILY_GROUPS = "groups"
FAMILY_LEGACY = "grouped-compact-single"

DEFERRED_NOTE = (
    "Legacy GtkSeparator child-packing 'padding' -> Material grid/box spacing "
    "conversion is build-bound (no local build to verify stock/collapse parity on "
    "this shared .ui); pinned as a regression net, flip to rewritten-material deferred."
)

MARKER_RE = re.compile(r"material-notebookbar-ui-conformance\s+family=(\S+)")


class ValidationError(RuntimeError):
    """Raised when the notebookbar .ui conformance contract is invalid."""


# --------------------------------------------------------------------------- #
# Surface enumeration                                                         #
# --------------------------------------------------------------------------- #
def owned_ui_paths(repo_root: Path) -> list[str]:
    """Return the sorted set of owned module notebookbar .ui surfaces via Git."""

    command = [
        "git",
        "-C",
        str(repo_root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        *OWNED_PATHSPECS,
    ]
    try:
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError as error:  # pragma: no cover - environment failure
        raise ValidationError(f"cannot run git to discover notebookbar .ui files: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"git notebookbar .ui discovery failed: {detail}")

    seen: set[str] = set()
    paths: list[str] = []
    for raw in completed.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw:
            continue
        posix = PurePosixPath(raw).as_posix()
        if not posix.rsplit("/", 1)[-1].startswith("notebookbar"):
            continue
        if not posix.endswith(".ui"):
            continue
        if not (repo_root / PurePosixPath(posix)).is_file():
            continue
        if posix not in seen:
            seen.add(posix)
            paths.append(posix)
    if not paths:
        raise ValidationError("no owned notebookbar .ui surfaces discovered")
    return sorted(paths)


# --------------------------------------------------------------------------- #
# Per-surface marker derivation                                               #
# --------------------------------------------------------------------------- #
def _iter_objects(root: ET.Element):
    for obj in root.iter("object"):
        yield obj


def derive_markers(text: str, surface: str) -> dict[str, object]:
    """Derive the structural markers for one .ui file from its XML + raw text."""

    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValidationError(f"{surface}: not well-formed XML: {error}") from error

    separator_count = 0
    group_grid_count = 0
    machinery: dict[str, int] = {}
    for obj in _iter_objects(root):
        cls = obj.get("class", "")
        if cls == "GtkSeparator":
            separator_count += 1
        elif cls == "GtkGrid" and (obj.get("id") or "").startswith("gd"):
            group_grid_count += 1
        if cls in MACHINERY_CLASSES:
            machinery[cls] = machinery.get(cls, 0) + 1

    row_spacing = 0
    column_spacing = 0
    box_spacing = 0
    legacy_padding = 0
    icon_size = 0
    for prop in root.iter("property"):
        name = prop.get("name")
        if name == "row-spacing":
            row_spacing += 1
        elif name == "column-spacing":
            column_spacing += 1
        elif name == "spacing":
            box_spacing += 1
        elif name == "padding":
            legacy_padding += 1
        elif name in ("icon_size", "icon-size"):
            icon_size += 1

    marker_match = MARKER_RE.search(text)
    conformance_marker = marker_match is not None
    marker_family = marker_match.group(1) if marker_match else None

    ordered_machinery = {cls: machinery[cls] for cls in MACHINERY_CLASSES if cls in machinery}

    return {
        "conformance_marker": conformance_marker,
        "marker_family": marker_family,
        "separator_count": separator_count,
        "group_grid_count": group_grid_count,
        "row_spacing_decls": row_spacing,
        "column_spacing_decls": column_spacing,
        "box_spacing_decls": box_spacing,
        "legacy_padding_count": legacy_padding,
        "icon_size_decls": icon_size,
        "collapse_machinery": ordered_machinery,
    }


def classify_family(markers: Mapping[str, object]) -> str:
    """Classify the structural family from derived markers (never the filename)."""

    if (
        int(markers["group_grid_count"]) > 0  # type: ignore[arg-type]
        and int(markers["row_spacing_decls"]) > 0  # type: ignore[arg-type]
        and int(markers["column_spacing_decls"]) > 0  # type: ignore[arg-type]
    ):
        return FAMILY_TABBED
    if (
        int(markers["box_spacing_decls"]) > 0  # type: ignore[arg-type]
        and int(markers["group_grid_count"]) == 0  # type: ignore[arg-type]
        and "sfxlo-PriorityHBox" not in markers["collapse_machinery"]  # type: ignore[operator]
    ):
        return FAMILY_GROUPS
    return FAMILY_LEGACY


def acceptance_status(family: str, markers: Mapping[str, object]) -> str:
    """Return the honest rewrite status for a surface given its markers."""

    marker_ok = bool(markers["conformance_marker"]) and markers["marker_family"] == family
    dividers = int(markers["separator_count"]) > 0  # type: ignore[arg-type]

    if family == FAMILY_TABBED:
        if (
            marker_ok
            and dividers
            and int(markers["row_spacing_decls"]) > 0  # type: ignore[arg-type]
            and int(markers["column_spacing_decls"]) > 0  # type: ignore[arg-type]
            and int(markers["legacy_padding_count"]) == 0  # type: ignore[arg-type]
        ):
            return STATUS_REWRITTEN
        return STATUS_IN_PROGRESS
    if family == FAMILY_GROUPS:
        if (
            marker_ok
            and dividers
            and int(markers["box_spacing_decls"]) > 0  # type: ignore[arg-type]
            and int(markers["legacy_padding_count"]) == 0  # type: ignore[arg-type]
        ):
            return STATUS_REWRITTEN
        return STATUS_IN_PROGRESS
    # grouped-compact-single: capped at in-progress (deep rewrite deferred).
    if marker_ok and dividers and markers["collapse_machinery"]:
        return STATUS_IN_PROGRESS
    return STATUS_PENDING


def spacing_kind(family: str) -> str:
    if family == FAMILY_TABBED:
        return "grid"
    if family == FAMILY_GROUPS:
        return "box"
    return "pending"


# --------------------------------------------------------------------------- #
# Registry assembly                                                           #
# --------------------------------------------------------------------------- #
def build_surface_row(repo_root: Path, surface: str) -> dict[str, object]:
    text = (repo_root / PurePosixPath(surface)).read_text(encoding="utf-8")
    markers = derive_markers(text, surface)
    family = classify_family(markers)
    status = acceptance_status(family, markers)
    module = "sd/sdraw" if surface.startswith("sd/uiconfig/sdraw/") else (
        "sd/simpress" if surface.startswith("sd/uiconfig/simpress/") else surface.split("/", 1)[0]
    )
    row: dict[str, object] = {
        "surface": surface,
        "module": module,
        "family": family,
        "rewrite_status": status,
        "spacing_declared": spacing_kind(family),
        "markers": {
            "conformance_marker": markers["conformance_marker"],
            "marker_family": markers["marker_family"],
            "separator_count": markers["separator_count"],
            "group_grid_count": markers["group_grid_count"],
            "row_spacing_decls": markers["row_spacing_decls"],
            "column_spacing_decls": markers["column_spacing_decls"],
            "box_spacing_decls": markers["box_spacing_decls"],
            "legacy_padding_count": markers["legacy_padding_count"],
            "icon_size_decls": markers["icon_size_decls"],
            "collapse_machinery": markers["collapse_machinery"],
        },
        "deferred": DEFERRED_NOTE if family == FAMILY_LEGACY else None,
    }
    return row


def compute_coverage(surfaces: Sequence[Mapping[str, object]]) -> dict[str, object]:
    total = len(surfaces)
    by_status = {STATUS_PENDING: 0, STATUS_IN_PROGRESS: 0, STATUS_REWRITTEN: 0}
    by_family: dict[str, dict[str, int]] = {}
    by_module: dict[str, dict[str, int]] = {}
    for row in surfaces:
        status = str(row["rewrite_status"])
        family = str(row["family"])
        module = str(row["module"])
        by_status[status] = by_status.get(status, 0) + 1
        by_family.setdefault(family, {"total": 0, STATUS_REWRITTEN: 0})
        by_family[family]["total"] += 1
        if status == STATUS_REWRITTEN:
            by_family[family][STATUS_REWRITTEN] += 1
        by_module.setdefault(module, {"total": 0, STATUS_REWRITTEN: 0})
        by_module[module]["total"] += 1
        if status == STATUS_REWRITTEN:
            by_module[module][STATUS_REWRITTEN] += 1
    rewritten = by_status[STATUS_REWRITTEN]
    coverage_pct = round(rewritten / total * 100, 2) if total else 0.0
    return {
        "total": total,
        "rewritten_material": rewritten,
        "in_progress": by_status[STATUS_IN_PROGRESS],
        "pending": by_status[STATUS_PENDING],
        "coverage_pct": coverage_pct,
        "by_family": {key: by_family[key] for key in sorted(by_family)},
        "by_module": {key: by_module[key] for key in sorted(by_module)},
    }


def build_registry(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    surfaces = [build_surface_row(repo_root, surface) for surface in owned_ui_paths(repo_root)]
    surfaces.sort(key=lambda row: str(row["surface"]))
    coverage = compute_coverage(surfaces)
    families = {
        FAMILY_TABBED: {
            "design_ref": DESIGN_REF,
            "required_markers": [
                "conformance_marker(family=tabbed)",
                "separator_count>0",
                "row_spacing_decls>0",
                "column_spacing_decls>0",
                "legacy_padding_count==0",
                "collapse_machinery preserved",
            ],
            "rewritten_status": STATUS_REWRITTEN,
            "note": (
                "Ribbon notebookbar.ui: gd-grid command groups already declare Material "
                "row/column spacing and are divided by GtkSeparator rules; the last legacy "
                "separator paddings were converted to equivalent margins so the file is "
                "padding-free. Group captions widen-and-scroll (design 4.6), never ellipsize."
            ),
        },
        FAMILY_GROUPS: {
            "design_ref": DESIGN_REF,
            "required_markers": [
                "conformance_marker(family=groups)",
                "separator_count>0",
                "box_spacing_decls>0",
                "legacy_padding_count==0",
            ],
            "rewritten_status": STATUS_REWRITTEN,
            "note": "notebookbar_groups.ui: GtkBox-spacing strip, zero legacy padding.",
        },
        FAMILY_LEGACY: {
            "design_ref": DESIGN_REF,
            "required_markers": [
                "conformance_marker(family=grouped-compact-single)",
                "separator_count>0",
                "collapse_machinery preserved",
            ],
            "rewritten_status": STATUS_IN_PROGRESS,
            "note": DEFERRED_NOTE,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "platform": PLATFORM,
        "generator": GENERATOR,
        "design_ref": DESIGN_REF,
        "cross_reference": CROSS_REFERENCE,
        "status": "source-declared",
        "runtime_verified": False,
        "source_note": SOURCE_NOTE,
        "rewrite_status_values": [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_REWRITTEN],
        "families": families,
        "coverage": coverage,
        "surfaces": surfaces,
    }


# --------------------------------------------------------------------------- #
# Registry file I/O                                                           #
# --------------------------------------------------------------------------- #
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
        raise ValidationError(f"cannot read contract {registry_path}: {error}") from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"contract {registry_path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError(f"contract {registry_path} must be a JSON object")
    return data


# --------------------------------------------------------------------------- #
# Comparison + acceptance                                                     #
# --------------------------------------------------------------------------- #
def _surface_index(surfaces: object) -> dict[str, Mapping[str, object]]:
    index: dict[str, Mapping[str, object]] = {}
    if not isinstance(surfaces, list):
        raise ValidationError("contract surfaces section must be a list")
    for surface in surfaces:
        if not isinstance(surface, dict) or "surface" not in surface:
            raise ValidationError("contract surface entry is malformed")
        key = surface["surface"]
        if not isinstance(key, str):
            raise ValidationError("contract surface key must be a string")
        if key in index:
            raise ValidationError(f"duplicate surface entry in contract: {key}")
        index[key] = surface
    return index


def _format_keys(keys: Iterable[str], limit: int = 12) -> str:
    values = sorted(keys)
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; ... and {len(values) - limit} more"
    return "; ".join(shown) + suffix


def _diff_surfaces(expected: object, actual: object, failures: list[str]) -> None:
    expected_index = _surface_index(expected)
    actual_index = _surface_index(actual)
    missing = set(expected_index) - set(actual_index)
    stale = set(actual_index) - set(expected_index)
    if missing:
        failures.append(
            f"{len(missing)} owned surface(s) missing from contract "
            f"(run --regenerate): {_format_keys(missing)}"
        )
    if stale:
        failures.append(
            f"{len(stale)} contract surface(s) with no matching owned file "
            f"(run --regenerate): {_format_keys(stale)}"
        )
    for key in sorted(set(expected_index) & set(actual_index)):
        if expected_index[key] != actual_index[key]:
            failures.append(
                f"surface {key!r} drifted from its derived structure "
                f"(run --regenerate): expected {expected_index[key]!r}, "
                f"found {actual_index[key]!r}"
            )


def _acceptance_failures(expected: Mapping[str, object], failures: list[str]) -> None:
    """Defence-in-depth semantic checks on the freshly derived surfaces."""

    for row in expected.get("surfaces", []):  # type: ignore[union-attr]
        surface = row["surface"]
        family = row["family"]
        markers = row["markers"]
        status = row["rewrite_status"]
        # Marker must exist and self-declare the derived family.
        if not markers["conformance_marker"]:
            failures.append(f"{surface}: conformance marker comment missing")
        elif markers["marker_family"] != family:
            failures.append(
                f"{surface}: marker family {markers['marker_family']!r} != derived "
                f"family {family!r}"
            )
        # Dividers present everywhere.
        if int(markers["separator_count"]) <= 0:
            failures.append(f"{surface}: no GtkSeparator group dividers present")
        # rewritten-material implies zero legacy padding + declared spacing.
        if status == STATUS_REWRITTEN:
            if int(markers["legacy_padding_count"]) != 0:
                failures.append(
                    f"{surface}: rewritten-material but carries "
                    f"{markers['legacy_padding_count']} legacy child-packing padding(s)"
                )
            if family == FAMILY_TABBED and not (
                int(markers["row_spacing_decls"]) > 0
                and int(markers["column_spacing_decls"]) > 0
            ):
                failures.append(f"{surface}: rewritten tabbed surface lost grid spacing")
            if family == FAMILY_GROUPS and int(markers["box_spacing_decls"]) <= 0:
                failures.append(f"{surface}: rewritten groups surface lost box spacing")
        # Legacy family must retain its collapse machinery pin.
        if family == FAMILY_LEGACY and not markers["collapse_machinery"]:
            failures.append(f"{surface}: legacy family lost all collapse machinery")


def _git_baseline(repo_root: Path, rel_path: str) -> dict[str, object] | None:
    command = ["git", "-C", str(repo_root), "show", f"HEAD:{rel_path}"]
    try:
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError:  # pragma: no cover - environment failure
        return None
    if completed.returncode != 0:
        return None  # no committed baseline yet (first commit)
    try:
        data = json.loads(completed.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _regression_failures(baseline: Mapping[str, object] | None, expected: Mapping[str, object], failures: list[str]) -> None:
    if not baseline:
        return
    try:
        base_index = _surface_index(baseline.get("surfaces"))
    except ValidationError:
        return
    now_index = _surface_index(expected.get("surfaces"))
    for key in sorted(set(base_index) & set(now_index)):
        base_status = str(base_index[key].get("rewrite_status", STATUS_PENDING))
        now_status = str(now_index[key].get("rewrite_status", STATUS_PENDING))
        base_ord = STATUS_ORDINAL.get(base_status, 0)
        now_ord = STATUS_ORDINAL.get(now_status, 0)
        if now_ord < base_ord:
            failures.append(
                f"{key}: rewrite status regressed {base_status} -> {now_status} "
                "(pins must never be weakened)"
            )
        base_marker = base_index[key].get("markers", {})
        now_marker = now_index[key].get("markers", {})
        if isinstance(base_marker, dict) and base_marker.get("conformance_marker") and not (
            isinstance(now_marker, dict) and now_marker.get("conformance_marker")
        ):
            failures.append(f"{key}: conformance marker was removed (pins must never be weakened)")


def _header_failures(expected: Mapping[str, object], actual: Mapping[str, object], failures: list[str]) -> None:
    for field in (
        "schema_version",
        "contract",
        "platform",
        "generator",
        "design_ref",
        "cross_reference",
        "status",
        "runtime_verified",
        "source_note",
        "rewrite_status_values",
        "families",
        "coverage",
    ):
        if expected.get(field) != actual.get(field):
            failures.append(
                f"contract field {field!r} drifted (run --regenerate): "
                f"expected {expected.get(field)!r}, found {actual.get(field)!r}"
            )
    if actual.get("runtime_verified") is not False:
        failures.append("contract runtime_verified: no runtime evidence exists; must be false")


def validate_contract(repo_root: Path, registry_path: Path) -> dict[str, object]:
    expected = build_registry(repo_root)
    actual = read_registry(registry_path)
    failures: list[str] = []
    _diff_surfaces(expected.get("surfaces"), actual.get("surfaces"), failures)
    _header_failures(expected, actual, failures)
    _acceptance_failures(expected, failures)
    baseline = _git_baseline(repo_root, REGISTRY_REL)
    _regression_failures(baseline, expected, failures)
    if failures:
        raise ValidationError("\n".join(failures))
    return expected


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the contract deterministically from a fresh derivation",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve() if args.registry is not None else repo_root / REGISTRY_REL
    )
    try:
        if args.regenerate:
            write_registry(registry_path, build_registry(repo_root))
        expected = validate_contract(repo_root, registry_path)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Notebookbar .ui conformance contract failed:\n{error}", file=sys.stderr)
        return 1

    coverage = expected["coverage"]
    assert isinstance(coverage, dict)
    print(
        "Notebookbar .ui conformance contract passed: "
        f"{coverage['coverage_pct']}% rewritten-material "
        f"({coverage['rewritten_material']}/{coverage['total']}) | "
        f"in-progress {coverage['in_progress']} | pending {coverage['pending']}"
    )
    for family in (FAMILY_TABBED, FAMILY_GROUPS, FAMILY_LEGACY):
        by_family = coverage["by_family"]
        assert isinstance(by_family, dict)
        stats = by_family.get(family)
        if stats:
            print(f"  {family}: {stats[STATUS_REWRITTEN]}/{stats['total']} rewritten-material")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
