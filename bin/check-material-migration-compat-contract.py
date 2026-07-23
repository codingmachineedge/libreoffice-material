#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for migration & profile compatibility (WIN-SYS-010).

``qa/windows-ui-contract/migration-compat.json`` pins the invariants of the real
upstream migration / profile-compatibility flow. Settings migration is a silent
headless backend and the retained compat dialogs are shared dialogs whose Material
treatment already comes from definition.xml parts pinned elsewhere, so the M-scope
is *pinning flow invariants + policy classification*, never new guarded source. This
checker cross-validates, fail-closed against real (comment-stripped) source:

* ``migration_invariants`` -- the SILENT positive path in migration.cxx
  (migrateSettingsIfNecessary -> doMigration -> setMigrationCompleted, the
  MigrationCompleted idempotency guard, the SAL_DISABLE_USERMIGRATION escape, the
  MIGRATED4 stamp) must all be present, PAIRED with a forbidden-nag blocklist: no
  weld/MessageDialog/infobar/UpdateRequiredDialog token may appear in the migration
  path. A dropped guard or an introduced migration prompt fails closed.
* ``compat_decisions`` -- the retained compatibility DECISIONS stay modal:
  CheckExtensionDependencies / UpdateRequiredDialog gated by LastCompatibilityCheckID
  in check_ext_deps.cxx; app.cxx orders the compat check BEFORE settings migration
  (compat gates migration); and the three compat dialog roots stay
  ``native-exclusion`` (router Classify: KeepModal) in the shared policy CSV, anchored
  on ui_path + object_id (never a line number). A reorder, a deleted gate, or a
  rerouted policy row fails closed.
* ``config_schema`` -- the profile-compat schema props in Setup.xcs
  (MigrationCompleted, LastCompatibilityCheckID, the Migration/SupportedVersions
  group) must remain, checked against XML-comment-stripped text.
* ``legacy_seed_reference`` -- the E-NONAG-LEGACY dependency is a single delegated
  reference to the WIN-SYS-008 harness: each referenced file + one anchor must exist.
  It is NEVER re-seeded or re-validated here.

It is source + policy evidence only: ``runtime_verified`` is false throughout -- no
native build, dialog pixels, runtime migration observation, or exact-build
legacy-profile capture is claimed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/migration-compat.json"
POLICY_CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

NATIVE_EXCLUSION = "native-exclusion"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {POLICY_CSV_PATH}

    migration = registry.get("migration_invariants")
    if isinstance(migration, dict) and isinstance(migration.get("file"), str):
        paths.add(migration["file"])

    compat = registry.get("compat_decisions")
    if isinstance(compat, dict):
        if isinstance(compat.get("check_file"), str):
            paths.add(compat["check_file"])
        ordering = compat.get("ordering")
        if isinstance(ordering, dict) and isinstance(ordering.get("file"), str):
            paths.add(ordering["file"])

    schema = registry.get("config_schema")
    if isinstance(schema, dict) and isinstance(schema.get("file"), str):
        paths.add(schema["file"])

    legacy = registry.get("legacy_seed_reference")
    if isinstance(legacy, dict):
        for ref in legacy.get("references", []) or []:
            if isinstance(ref, dict) and isinstance(ref.get("file"), str):
                paths.add(ref["file"])

    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Source helpers
# --------------------------------------------------------------------------------------------------
def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments, preserving string/char literals."""

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
        # quote
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


def _strip_xml_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


# --------------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------------
def _validate_migration_invariants(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = block.get("file")
    if not isinstance(file_path, str):
        errors.append("migration_invariants:file must be a string")
        return
    text = contents.get(file_path)
    if text is None:
        errors.append(f"migration_invariants:{file_path}:file missing")
        return
    code = _strip_comments(text)

    required = block.get("required_markers")
    if not isinstance(required, list) or not required:
        errors.append("migration_invariants:required_markers non-empty array required")
    else:
        for marker in required:
            if not isinstance(marker, str) or marker not in code:
                errors.append(
                    f"migration_invariants:{file_path}:missing required marker {marker!r} "
                    "(the silent-migration positive path was broken)"
                )

    forbidden = block.get("forbidden_markers")
    if not isinstance(forbidden, list) or not forbidden:
        errors.append("migration_invariants:forbidden_markers non-empty array required")
    else:
        for marker in forbidden:
            if isinstance(marker, str) and marker in code:
                errors.append(
                    f"migration_invariants:{file_path}:forbidden nag marker {marker!r} present "
                    "(settings migration must remain silent -- no dialog/infobar in the path)"
                )


def _read_policy_rows(text: str | None, errors: list[str]) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    if text is None:
        errors.append(f"compat_decisions:{POLICY_CSV_PATH}:file missing")
        return rows
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        ui_path = (row.get("ui_path") or "").strip()
        object_id = (row.get("object_id") or "").strip()
        rows[(ui_path, object_id)] = (row.get("policy") or "").strip()
    return rows


def _validate_compat_decisions(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    check_file = block.get("check_file")
    if not isinstance(check_file, str):
        errors.append("compat_decisions:check_file must be a string")
    else:
        text = contents.get(check_file)
        if text is None:
            errors.append(f"compat_decisions:{check_file}:file missing")
        else:
            code = _strip_comments(text)
            for marker in block.get("check_markers", []) or []:
                if not isinstance(marker, str) or marker not in code:
                    errors.append(
                        f"compat_decisions:{check_file}:missing compat marker {marker!r} "
                        "(the retained compatibility decision was removed)"
                    )

    ordering = block.get("ordering")
    if not isinstance(ordering, dict):
        errors.append("compat_decisions:ordering object required")
    else:
        order_file = ordering.get("file")
        first = ordering.get("first")
        then = ordering.get("then")
        if not (isinstance(order_file, str) and isinstance(first, str) and isinstance(then, str)):
            errors.append("compat_decisions:ordering file/first/then must be strings")
        else:
            text = contents.get(order_file)
            if text is None:
                errors.append(f"compat_decisions:{order_file}:file missing")
            else:
                code = _strip_comments(text)
                first_at = code.find(first)
                then_at = code.find(then)
                if first_at < 0:
                    errors.append(
                        f"compat_decisions:{order_file}:missing {first!r} "
                        "(the compatibility gate was removed)"
                    )
                if then_at < 0:
                    errors.append(
                        f"compat_decisions:{order_file}:missing {then!r} "
                        "(the settings-migration call was removed)"
                    )
                if first_at >= 0 and then_at >= 0 and first_at >= then_at:
                    errors.append(
                        f"compat_decisions:{order_file}:ordering drift -- {first!r} must precede "
                        f"{then!r} (the compat check must gate settings migration)"
                    )

    rows = _read_policy_rows(contents.get(POLICY_CSV_PATH), errors)
    for entry in block.get("dialogs", []) or []:
        if not isinstance(entry, dict):
            errors.append("compat_decisions:dialog entry must be an object")
            continue
        ui_file = entry.get("ui_file")
        dialog_id = entry.get("dialog_id")
        expected = entry.get("expected_policy", NATIVE_EXCLUSION)
        if not (isinstance(ui_file, str) and isinstance(dialog_id, str)):
            errors.append("compat_decisions:dialog ui_file/dialog_id must be strings")
            continue
        policy = rows.get((ui_file, dialog_id))
        if policy is None:
            errors.append(
                f"compat_decisions:{ui_file}#{dialog_id} missing from {POLICY_CSV_PATH} "
                "(a retained compatibility dialog row was removed)"
            )
        elif policy != expected:
            errors.append(
                f"compat_decisions:{ui_file}#{dialog_id} policy is {policy!r}, expected "
                f"{expected!r} (a modal compatibility decision was rerouted)"
            )


def _validate_config_schema(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = block.get("file")
    if not isinstance(file_path, str):
        errors.append("config_schema:file must be a string")
        return
    text = contents.get(file_path)
    if text is None:
        errors.append(f"config_schema:{file_path}:file missing")
        return
    stripped = _strip_xml_comments(text)
    for marker in block.get("markers", []) or []:
        if not isinstance(marker, str) or marker not in stripped:
            errors.append(
                f"config_schema:{file_path}:missing schema prop {marker!r} "
                "(the profile-compat schema changed)"
            )


def _validate_legacy_seed_reference(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    references = block.get("references")
    if not isinstance(references, list) or not references:
        errors.append("legacy_seed_reference:references non-empty array required")
        return
    for ref in references:
        if not isinstance(ref, dict):
            errors.append("legacy_seed_reference:reference must be an object")
            continue
        file_path = ref.get("file")
        anchor = ref.get("anchor")
        if not (isinstance(file_path, str) and isinstance(anchor, str)):
            errors.append("legacy_seed_reference:file/anchor must be strings")
            continue
        text = contents.get(file_path)
        if text is None:
            errors.append(
                f"legacy_seed_reference:{file_path}:file missing "
                "(the delegated WIN-SYS-008 no-nag harness reference is broken)"
            )
        elif anchor not in text:
            errors.append(
                f"legacy_seed_reference:{file_path}:missing anchor {anchor!r} "
                "(the delegated WIN-SYS-008 no-nag harness reference is broken)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-migration-compat":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    migration = registry.get("migration_invariants")
    if isinstance(migration, dict):
        _validate_migration_invariants(migration, contents, errors)
    else:
        errors.append("registry:migration_invariants:object required")

    compat = registry.get("compat_decisions")
    if isinstance(compat, dict):
        _validate_compat_decisions(compat, contents, errors)
    else:
        errors.append("registry:compat_decisions:object required")

    schema = registry.get("config_schema")
    if isinstance(schema, dict):
        _validate_config_schema(schema, contents, errors)
    else:
        errors.append("registry:config_schema:object required")

    legacy = registry.get("legacy_seed_reference")
    if isinstance(legacy, dict):
        _validate_legacy_seed_reference(legacy, contents, errors)
    else:
        errors.append("registry:legacy_seed_reference:object required")

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
        print(f"Migration/profile-compatibility contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Migration/profile-compatibility contract passed: silent-migration positive path + "
        "forbidden-nag blocklist, the compat-check-gates-migration ordering, the three retained "
        "compat decisions kept native-exclusion, the Setup.xcs profile-compat schema, and the "
        "delegated WIN-SYS-008 legacy no-nag seed reference -- source+policy evidence only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
