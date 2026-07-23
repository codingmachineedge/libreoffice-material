#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Read-only upstream-symbol pin for the Calc sheet-tab strip base (WIN-CA-004).

``qa/windows-ui-contract/calc-sheet-tabs-upstream-pin.json`` pins the stock
svtools ``TabBar`` / ``TabDrawer`` base symbols that ``ScTabControl`` delegates
its whole sheet-tab-strip geometry to. The Material accent-strip overlay that
ScTabControl adds is pinned separately (and guarded) by
``qa/windows-ui-contract/calc-sheet-tabs.json``; THIS contract only proves that
the base it overlays is the shared, unforked svtools geometry, and records the
four application subclasses that share it.

Why this row does NOT advance the M gate: the pinned symbols are stock upstream
LibreOffice code with no ``VCL_FILE_WIDGET_THEME`` / Material guard. Per the
inventory legend, existing non-Material-guarded source never satisfies the M
gate, so the registry carries ``advances_m_gate: false`` and this checker fails
closed if that flag is ever flipped true without the pin becoming a guarded
Material branch. It is a verification-only pin, deliberately kept read-only:

* ``upstream_files`` -- ``include/svtools/tabbar.hxx`` and
  ``svtools/source/control/tabbar.cxx`` must both be present and are declared
  read-only / never-mutated (matching the "definition file is read only, never
  mutated" convention already used for definition.xml). This checker never
  writes to svtools.
* ``symbols`` -- every declared base symbol substring (whitespace-normalized,
  comments stripped first, so commented-out or renamed code fails closed) must
  be present verbatim in its file. A rename, signature change, or removal of any
  of ``TabBar::Paint`` / ``TabDrawer`` / ``drawTab`` / ``AddTabClick`` /
  ``ImplPrePaint`` / ``GetPageRect`` / ``GetPageArea`` fails closed, because that
  would break the base_call premise of calc-sheet-tabs.json.
* ``subclasses`` -- the four ``TabBar`` subclasses (Calc / Basic IDE /
  Impress / Draw) must each still declare their shared base, so the
  shared-ownership fact cannot silently rot into a stale claim.

Source evidence only: ``runtime_verified`` is false and ``advances_m_gate`` is
false throughout -- no native build, tab pixels, or runtime interaction are
claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/calc-sheet-tabs-upstream-pin.json"

REQUIRED_UPSTREAM = {
    "include/svtools/tabbar.hxx",
    "svtools/source/control/tabbar.cxx",
}


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _collapse_ws(source: str) -> str:
    """Collapse every run of whitespace to a single space so a declared symbol
    matches regardless of the multi-space alignment svtools headers use."""
    return re.sub(r"\s+", " ", source).strip()


def _referenced_files(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for entry in registry.get("upstream_files", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            paths.add(entry["file"])
    for entry in registry.get("symbols", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            paths.add(entry["file"])
    for entry in registry.get("subclasses", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            paths.add(entry["file"])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _referenced_files(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _collapsed_code(contents: Mapping[str, str], path: str, cache: dict[str, str]) -> str | None:
    if path in cache:
        return cache[path]
    source = contents.get(path)
    if source is None:
        return None
    collapsed = _collapse_ws(_without_cpp_comments(source))
    cache[path] = collapsed
    return collapsed


def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-calc-sheet-tabs-upstream-pin":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")
    # An upstream, non-Material-guarded pin never satisfies the M gate. This flag
    # is fail-closed: flipping it true would require the pin to first become a
    # guarded Material branch (a genuine build-verifiable change, out of scope).
    if registry.get("advances_m_gate") is not False:
        errors.append(
            "registry:advances_m_gate:must be false (a stock, non-Material-guarded upstream "
            "symbol pin never satisfies the M gate per the inventory legend)"
        )

    upstream = registry.get("upstream_files")
    if not isinstance(upstream, list) or not upstream:
        errors.append("registry:upstream_files:non-empty array required")
        upstream = []
    seen_upstream: set[str] = set()
    for index, entry in enumerate(upstream):
        context = f"upstream_files[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{context}:object required")
            continue
        file_path = entry.get("file")
        if not isinstance(file_path, str) or not file_path:
            errors.append(f"{context}:file:non-empty string required")
            continue
        seen_upstream.add(file_path)
        if entry.get("read_only") is not True:
            errors.append(f"{context}:read_only:must be true (this row never mutates svtools)")
        if entry.get("never_mutated") is not True:
            errors.append(f"{context}:never_mutated:must be true")
        if file_path not in contents:
            errors.append(f"{context}:file missing on disk ({file_path})")
    missing_upstream = REQUIRED_UPSTREAM - seen_upstream
    if missing_upstream:
        errors.append(
            f"registry:upstream_files:missing required {', '.join(sorted(missing_upstream))}"
        )

    cache: dict[str, str] = {}

    def check_symbols(section: str) -> None:
        entries = registry.get(section)
        if not isinstance(entries, list) or not entries:
            errors.append(f"registry:{section}:non-empty array required")
            return
        for index, entry in enumerate(entries):
            context = f"{section}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{context}:object required")
                continue
            file_path = entry.get("file")
            symbol = entry.get("symbol")
            if not isinstance(file_path, str) or not file_path:
                errors.append(f"{context}:file:non-empty string required")
                continue
            if not isinstance(symbol, str) or not symbol:
                errors.append(f"{context}:symbol:non-empty string required")
                continue
            code = _collapsed_code(contents, file_path, cache)
            if code is None:
                errors.append(f"{context}:file missing on disk ({file_path})")
                continue
            if _collapse_ws(symbol) not in code:
                errors.append(
                    f"{context}:symbol absent from {file_path} (rename/removal/drift): {symbol!r}"
                )

    check_symbols("symbols")
    check_symbols("subclasses")

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
        print(f"Calc sheet-tabs upstream pin failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Calc sheet-tabs upstream pin passed: "
        f"{len(registry['symbols'])} svtools TabBar/TabDrawer base symbol(s) and "
        f"{len(registry['subclasses'])} shared subclass(es) pinned read-only "
        "(advances_m_gate=false; no guarded Material branch claimed here)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
