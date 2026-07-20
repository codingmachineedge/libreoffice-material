#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate complete native dialog coverage for the Windows notification UI.

The checked-in registry is deliberately exhaustive. Every top-level
GtkDialog, GtkMessageDialog, or GtkAssistant object in a tracked or untracked
non-ignored ``.ui`` file must have one explicit policy row. New dialogs,
removed dialogs, widget-class changes, duplicate rows, and implicit policies
all fail validation.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    REPOSITORY
    / "qa/windows-ui-contract/dialog-notification-policy.csv"
)

DIALOG_CLASSES = frozenset({"GtkDialog", "GtkMessageDialog", "GtkAssistant"})
NOTIFICATION_POLICY = "bottom-right-notification-form"
EXCLUSION_POLICY = "native-exclusion"
ALLOWED_POLICIES = frozenset({NOTIFICATION_POLICY, EXCLUSION_POLICY})
DEFAULT_NOTIFICATION_PROFILE = "default"
PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

CSV_FIELDS = (
    "ui_path",
    "object_id",
    "widget_class",
    "policy",
    "notification_profile",
    "exclusion_reason",
)


class ValidationError(RuntimeError):
    """Raised when the dialog coverage contract is incomplete or invalid."""


@dataclass(frozen=True, order=True)
class DialogKey:
    """Stable identity and native class of one top-level dialog object."""

    ui_path: str
    object_id: str
    widget_class: str

    @property
    def locator(self) -> tuple[str, str]:
        return (self.ui_path, self.object_id)

    def display(self) -> str:
        anchor = self.object_id or "<anonymous-root>"
        return f"{self.ui_path}#{anchor} ({self.widget_class})"


@dataclass(frozen=True)
class ContractEntry:
    """The explicit Windows presentation policy for a discovered dialog."""

    key: DialogKey
    policy: str
    notification_profile: str
    exclusion_reason: str


@dataclass(frozen=True)
class ValidationReport:
    total: int
    classes: Counter[str]
    policies: Counter[str]
    profiles: Counter[str]


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _format_items(items: Iterable[DialogKey], limit: int = 12) -> str:
    values = [item.display() for item in sorted(items)]
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; ... and {len(values) - limit} more"
    return "; ".join(shown) + suffix


def repository_ui_paths(repo_root: Path) -> list[Path]:
    """Return tracked plus untracked, non-ignored UI files from Git."""

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
        "*.ui",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise ValidationError(f"cannot run git to discover .ui files: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"git .ui discovery failed: {detail}")

    paths: list[Path] = []
    for raw_path in completed.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if raw_path:
            path = repo_root / PurePosixPath(raw_path)
            # ``git ls-files --cached`` intentionally reports tracked files that
            # are deleted in the working tree. Treat those as absent so --update
            # can remove their stale policy rows; compare_contract still fails
            # closed until the registry is regenerated.
            if path.is_file():
                paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(repo_root).as_posix())


def discover_dialogs(
    repo_root: Path, candidate_paths: Sequence[Path] | None = None
) -> list[DialogKey]:
    """Discover every top-level native dialog object in the candidate UI files."""

    repo_root = repo_root.resolve()
    paths = repository_ui_paths(repo_root) if candidate_paths is None else candidate_paths
    dialogs: list[DialogKey] = []
    locators: dict[tuple[str, str], DialogKey] = {}

    for candidate in paths:
        path = candidate if candidate.is_absolute() else repo_root / candidate
        try:
            relative_path = path.resolve().relative_to(repo_root).as_posix()
        except ValueError as error:
            raise ValidationError(f"UI path escapes repository: {path}") from error
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as error:
            raise ValidationError(f"cannot parse {relative_path}: {error}") from error

        for child in root:
            if _tag_name(child.tag) != "object":
                continue
            widget_class = child.get("class", "")
            if widget_class not in DIALOG_CLASSES:
                continue
            object_id = child.get("id", "").strip()
            key = DialogKey(relative_path, object_id, widget_class)
            if key.locator in locators:
                prior = locators[key.locator]
                raise ValidationError(
                    "duplicate discovered dialog locator: "
                    f"{key.ui_path}#{key.object_id} ({prior.widget_class}, {widget_class})"
                )
            locators[key.locator] = key
            dialogs.append(key)
    return sorted(dialogs)


def _validate_registry_path(value: str, row_number: int) -> str:
    if value != value.strip() or "\\" in value:
        raise ValidationError(
            f"registry row {row_number} ui_path must be normalized POSIX text: {value!r}"
        )
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or value.startswith("./")
        or ":" in value
        or ".." in path.parts
        or path.suffix != ".ui"
        or path.as_posix() != value
    ):
        raise ValidationError(
            f"registry row {row_number} has invalid repository UI path: {value!r}"
        )
    return value


def _entry_from_row(row: dict[str, str | None], row_number: int) -> ContractEntry:
    missing_values = [field for field in CSV_FIELDS if row.get(field) is None]
    if missing_values:
        raise ValidationError(
            f"registry row {row_number} is missing columns: {', '.join(missing_values)}"
        )
    values = {field: (row[field] or "") for field in CSV_FIELDS}
    for field, value in values.items():
        if value != value.strip():
            raise ValidationError(
                f"registry row {row_number} field {field} has surrounding whitespace"
            )

    ui_path = _validate_registry_path(values["ui_path"], row_number)
    object_id = values["object_id"]
    widget_class = values["widget_class"]
    policy = values["policy"]
    profile = values["notification_profile"]
    reason = values["exclusion_reason"]

    if widget_class not in DIALOG_CLASSES:
        raise ValidationError(
            f"registry row {row_number} has unsupported widget_class: {widget_class!r}"
        )
    if policy not in ALLOWED_POLICIES:
        raise ValidationError(
            f"registry row {row_number} has unsupported explicit policy: {policy!r}"
        )
    if policy == NOTIFICATION_POLICY:
        if not profile or PROFILE_PATTERN.fullmatch(profile) is None:
            raise ValidationError(
                f"registry row {row_number} notification policy requires a slug-like "
                "notification_profile"
            )
        if reason:
            raise ValidationError(
                f"registry row {row_number} notification policy cannot have an "
                "exclusion_reason"
            )
    else:
        if profile:
            raise ValidationError(
                f"registry row {row_number} native exclusion cannot have a "
                "notification_profile"
            )
        if not reason:
            raise ValidationError(
                f"registry row {row_number} native exclusion requires an "
                "exclusion_reason"
            )

    return ContractEntry(
        key=DialogKey(ui_path, object_id, widget_class),
        policy=policy,
        notification_profile=profile,
        exclusion_reason=reason,
    )


def read_registry(registry_path: Path) -> list[ContractEntry]:
    try:
        stream = registry_path.open("r", encoding="utf-8", newline="")
    except OSError as error:
        raise ValidationError(f"cannot read registry {registry_path}: {error}") from error
    with stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValidationError(
                "registry header must be exactly: " + ",".join(CSV_FIELDS)
            )
        entries: list[ContractEntry] = []
        locators: dict[tuple[str, str], int] = {}
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValidationError(
                    f"registry row {row_number} has unexpected extra columns"
                )
            entry = _entry_from_row(row, row_number)
            if entry.key.locator in locators:
                raise ValidationError(
                    "duplicate registry dialog locator at rows "
                    f"{locators[entry.key.locator]} and {row_number}: "
                    f"{entry.key.ui_path}#{entry.key.object_id}"
                )
            locators[entry.key.locator] = row_number
            entries.append(entry)

    sorted_entries = sorted(entries, key=lambda entry: entry.key)
    if entries != sorted_entries:
        raise ValidationError(
            "registry rows must be sorted by ui_path, object_id, and widget_class"
        )
    return entries


def compare_contract(
    discovered: Sequence[DialogKey], entries: Sequence[ContractEntry]
) -> None:
    discovered_set = set(discovered)
    registry_set = {entry.key for entry in entries}
    missing = discovered_set - registry_set
    stale = registry_set - discovered_set
    failures: list[str] = []
    if missing:
        failures.append(
            f"{len(missing)} source dialog(s) missing from policy registry: "
            + _format_items(missing)
        )
    if stale:
        failures.append(
            f"{len(stale)} registry entry/entries without matching source dialog: "
            + _format_items(stale)
        )
    if failures:
        raise ValidationError("\n".join(failures))


def validate_contract(repo_root: Path, registry_path: Path) -> ValidationReport:
    discovered = discover_dialogs(repo_root)
    entries = read_registry(registry_path)
    compare_contract(discovered, entries)
    return ValidationReport(
        total=len(discovered),
        classes=Counter(key.widget_class for key in discovered),
        policies=Counter(entry.policy for entry in entries),
        profiles=Counter(
            entry.notification_profile
            for entry in entries
            if entry.notification_profile
        ),
    )


def merge_entries(
    discovered: Sequence[DialogKey], existing: Sequence[ContractEntry]
) -> list[ContractEntry]:
    """Preserve reviewed rows and explicitly default newly discovered dialogs."""

    prior = {entry.key: entry for entry in existing}
    return [
        prior.get(
            key,
            ContractEntry(
                key=key,
                policy=NOTIFICATION_POLICY,
                notification_profile=DEFAULT_NOTIFICATION_PROFILE,
                exclusion_reason="",
            ),
        )
        for key in sorted(discovered)
    ]


def write_registry(registry_path: Path, entries: Sequence[ContractEntry]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "ui_path": entry.key.ui_path,
                    "object_id": entry.key.object_id,
                    "widget_class": entry.key.widget_class,
                    "policy": entry.policy,
                    "notification_profile": entry.notification_profile,
                    "exclusion_reason": entry.exclusion_reason,
                }
            )


def _counter_text(counter: Counter[str]) -> str:
    return ", ".join(f"{key}={counter[key]}" for key in sorted(counter))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPOSITORY,
        help="repository root to scan (default: script repository)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="policy CSV (default: qa/windows-ui-contract/dialog-notification-policy.csv)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="regenerate coverage, preserving exact existing policies and defaulting new rows",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve()
        if args.registry is not None
        else repo_root / "qa/windows-ui-contract/dialog-notification-policy.csv"
    )
    try:
        if args.update:
            discovered = discover_dialogs(repo_root)
            existing = read_registry(registry_path) if registry_path.exists() else []
            write_registry(registry_path, merge_entries(discovered, existing))
        report = validate_contract(repo_root, registry_path)
    except ValidationError as error:
        print(f"Windows dialog notification contract failed:\n{error}", file=sys.stderr)
        return 1

    print(f"Windows dialog notification contract passed: {report.total} dialog roots")
    print(f"  classes: {_counter_text(report.classes)}")
    print(f"  policies: {_counter_text(report.policies)}")
    print(f"  profiles: {_counter_text(report.profiles) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
