#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for Material theme-resolution routing (WIN-FND-002).

``qa/windows-ui-contract/theme-resolution-routing.json`` pins the already-compiled
control-flow chain that resolves which theme (high contrast > dark > light) the
Material file-widget overlay applies, and how a live OS change re-resolves it
app-wide. docs/design/01-foundations.md section 3 ("Theme resolution order")
specifies the target precedence; this checker locks the real routing source
against drift. It pins six things and no more:

* **HC-first precedence** -- ``FileDefinitionWidgetDraw::updateSettings`` must
  short-circuit on ``GetHighContrastMode()``, set ``mbHighContrast``, restore the
  captured native baseline via ``updateNativeWidgetFrameworkSettings(nullptr)`` and
  ``return false`` (no Material HC paint), as one contiguous statement so a
  reordered or comment-only bypass fails closed;
* **native-fallback gate** -- ``usesNativeFallback()`` keys off ``mbHighContrast``
  alone and ``isNativeControlSupported`` dispatches to the native backend on it,
  never on a stale resolved definition;
* **dark platform signal** -- the Windows ``UseDarkMode()`` reads the AUTO/LIGHT/
  DARK app colour-mode layer and, on AUTO, the undocumented ``uxtheme.dll`` ordinal
  132 ``ShouldAppsUseDarkMode`` signal;
* **officecfg override layering** -- the generic settings pipeline applies the
  ``SAL_FORCE_HC`` env and ``Accessibility::HighContrast`` officecfg override, then
  captures the native baseline *before* invoking the Material bridge, in that order;
* **platform HC read + live refresh** -- the Windows frame reads
  ``SPI_GETHIGHCONTRAST``/``HCF_HIGHCONTRASTON`` and, on ``WM_SETTINGCHANGE``,
  triggers ``UpdateDarkMode`` and marks the theme changed;
* **app-wide cascade** -- ``ImplHandleSalSettings`` closes the loop on a
  ``SettingsChanged`` event via merge -> override -> set, in that order.

It is source evidence only: ``runtime_verified`` is false throughout. No native
build, rendered high-contrast/dark pixels, or live OS-toggle interaction is
claimed; the platform matrix (named Windows contrast themes, scale, RTL/CJK) and
the settings-cascade performance budget remain the separate build/runtime gates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/theme-resolution-routing.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CONTRACT = "material-theme-resolution-routing"
THEME_FLAG = "VCL_FILE_WIDGET_THEME"
OPT_IN_FLAG = "VCL_DRAW_WIDGETS_FROM_FILE"


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
    """Collapse every run of whitespace to a single space so a contiguous
    statement can be matched regardless of indentation or line wrapping."""

    return re.sub(r"\s+", " ", source).strip()


def _referenced_sources(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for checkpoint in registry.get("checkpoints", []) or []:
        if isinstance(checkpoint, dict) and isinstance(checkpoint.get("source"), str):
            paths.add(checkpoint["source"])
    for statement in registry.get("contiguous", []) or []:
        if isinstance(statement, dict) and isinstance(statement.get("source"), str):
            paths.add(statement["source"])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _referenced_sources(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_registry_integrity(registry: Mapping[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT:
        errors.append(f"registry:contract:must be {CONTRACT}")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("theme_flag") != THEME_FLAG:
        errors.append(f"registry:theme_flag:must be {THEME_FLAG}")
    if registry.get("opt_in_flag") != OPT_IN_FLAG:
        errors.append(f"registry:opt_in_flag:must be {OPT_IN_FLAG}")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")


def _validate_checkpoints(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    checkpoints = registry.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        errors.append("registry:checkpoints:non-empty array required")
        return
    seen: set[str] = set()
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            errors.append("checkpoints:entry:object required")
            continue
        cid = checkpoint.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append("checkpoints:entry:id must be a non-empty string")
            continue
        if cid in seen:
            errors.append(f"checkpoints:{cid}:duplicate id")
            continue
        seen.add(cid)
        source_path = checkpoint.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"checkpoints:{cid}:source {source_path!r} missing")
            continue
        code = _without_cpp_comments(source)
        markers = checkpoint.get("markers")
        if not isinstance(markers, list) or not markers:
            errors.append(f"checkpoints:{cid}:markers non-empty array required")
            continue
        for marker in markers:
            if not isinstance(marker, str):
                errors.append(f"checkpoints:{cid}:marker must be a string")
                continue
            if marker not in code:
                errors.append(
                    f"checkpoints:{cid}:marker missing in code ({marker!r}) "
                    f"[{source_path}] -- routing chain drifted or was commented out"
                )


def _validate_contiguous(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    # Contiguous statements prove ordering + adjacency, not merely that the tokens
    # exist somewhere: a reordered precedence short-circuit or a merge/set cascade
    # with the steps rearranged leaves every checkpoint marker intact but fails here.
    for statement in registry.get("contiguous", []) or []:
        if not isinstance(statement, dict):
            errors.append("contiguous:entry:object required")
            continue
        sid = statement.get("id", "?")
        source_path = statement.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"contiguous:{sid}:source {source_path!r} missing")
            continue
        expected = statement.get("statement")
        if not isinstance(expected, str) or not expected:
            errors.append(f"contiguous:{sid}:statement must be a non-empty string")
            continue
        collapsed = _collapse_ws(_without_cpp_comments(source))
        if _collapse_ws(expected) not in collapsed:
            errors.append(
                f"contiguous:{sid}:the ordered statement is not present as a contiguous "
                f"block ({expected!r} not found in {source_path}); a reordered or "
                "comment-only routing step fails closed"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    _validate_registry_integrity(registry, errors)
    _validate_checkpoints(registry, contents, errors)
    _validate_contiguous(registry, contents, errors)
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
        print(f"Material theme-resolution routing contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material theme-resolution routing contract passed: HC-first precedence "
        "short-circuit, the native-fallback gate, the AUTO/LIGHT/DARK + ordinal-132 "
        "dark signal, the officecfg HC override + native-baseline capture ordering, "
        "the SPI_GETHIGHCONTRAST/WM_SETTINGCHANGE platform reads, and the app-wide "
        "settings cascade are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
