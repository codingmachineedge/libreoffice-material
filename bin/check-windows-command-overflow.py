#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed presence contract for adaptive command overflow (WIN-SHL-002).

``qa/windows-ui-contract/command-overflow.json`` pins the REAL, pre-existing,
non-Material toolbar-overflow reachability/order mechanism the design chapters rely on
(docs/design/01-foundations.md 7; docs/design/05-navigation.md 1.3/4.3): a clipped
toolbar item stays ``mbVisible=true`` (overflow is not silent removal), both the native
custom-menu builder and the framework floating overflow toolbar walk items in original
declared order, and arrow-key highlight cycling folds the ``>>`` menu button into the
sequence. Each marker is a regular expression matched against *comment-stripped* source
across two ``vcl`` files and one ``framework`` file, so commenting the wiring out -- or
replacing it with a descriptive comment -- fails the contract.

HONESTY BOUND (enforced, not merely documented): ``satisfies_material_gate`` must be
``false``. None of this code is Material-specific -- it carries no VCL_FILE_WIDGET_THEME
guard and definition.xml has no overflow token -- so, exactly like the WIN-NAV-002
context-menu *presence* markers, it must never be reported as advancing the row's ``M``
(Material-specific) gate. Flipping that flag to ``true`` fails this checker closed.

It is source evidence only: ``runtime_verified`` is false throughout -- no Windows build,
toolbar pixels, or runtime resize/keyboard interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/command-overflow.json"


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _strip_comments(source: str) -> str:
    """Remove C/C++ block and line comments, preserving newlines so that markers can
    never be satisfied by commented-out or comment-only wiring."""
    without_block = re.sub(
        r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S
    )
    return "\n".join(re.sub(r"//.*$", "", line) for line in without_block.split("\n"))


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for marker in registry.get("code_markers", []) or []:
        if not isinstance(marker, dict):
            continue
        rel = marker.get("file")
        if not isinstance(rel, str) or rel in contents:
            continue
        path = repo_root / rel
        if path.is_file():
            contents[rel] = path.read_text(encoding="utf-8")
    return registry, contents


def _validate_markers(
    markers: object, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(markers, list) or not markers:
        errors.append("code_markers:non-empty array required")
        return
    stripped: dict[str, str] = {}
    seen: set[str] = set()
    for index, marker in enumerate(markers):
        if not isinstance(marker, dict):
            errors.append(f"code_markers:#{index}:object required")
            continue
        marker_id = marker.get("id")
        rel = marker.get("file")
        pattern = marker.get("pattern")
        if not isinstance(marker_id, str) or not marker_id.strip():
            errors.append(f"code_markers:#{index}:id required")
            continue
        if marker_id in seen:
            errors.append(f"code_markers:duplicate id {marker_id!r}")
            continue
        seen.add(marker_id)
        if not isinstance(rel, str) or not isinstance(pattern, str):
            errors.append(f"code_markers:{marker_id}:file and pattern required")
            continue
        source = contents.get(rel)
        if source is None:
            errors.append(f"code_markers:{marker_id}:source {rel} missing")
            continue
        if rel not in stripped:
            stripped[rel] = _strip_comments(source)
        try:
            found = re.search(pattern, stripped[rel], flags=re.S) is not None
        except re.error as error:
            errors.append(f"code_markers:{marker_id}:bad pattern ({error})")
            continue
        if not found:
            errors.append(
                f"code_markers:{marker_id}:presence marker not found in real code of {rel} "
                f"({marker.get('why', pattern)})"
            )


def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-command-overflow":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    # Honesty invariant: presence markers over pre-existing upstream source must never be
    # reported as satisfying the Material (M) gate.
    gate = registry.get("satisfies_material_gate")
    if not isinstance(gate, bool):
        errors.append("registry:satisfies_material_gate:boolean required")
    elif gate:
        errors.append(
            "registry:satisfies_material_gate:must stay false -- this pins pre-existing "
            "upstream overflow code (no VCL_FILE_WIDGET_THEME guard, no definition.xml "
            "token); existing upstream source does not satisfy M"
        )

    _validate_markers(registry.get("code_markers"), contents, errors)

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
        registry, contents = load_repository(repo_root)
        errors = violations(registry, contents)
        if errors:
            raise ValidationError("\n".join(errors))
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Windows command-overflow contract failed:\n{error}", file=sys.stderr)
        return 1
    count = len(registry.get("code_markers", []) or [])
    print(
        f"Windows command-overflow contract passed: {count} presence markers pin the real "
        "clipped-stays-visible / declared-order custom-menu / arrow-key menu-button / "
        "framework overflow-toolbar wiring. Presence-only, not Material-gated "
        "(satisfies_material_gate=false); no build or runtime interaction claimed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
