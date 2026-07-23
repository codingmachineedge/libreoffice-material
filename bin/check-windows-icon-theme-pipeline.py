#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed icon-theme pipeline contract for WIN-FND-007.

``qa/windows-ui-contract/icon-theme-pipeline.json`` pins the *current, real*
Windows icon-theme selection / package-naming / fallback contract and enumerates
``icon-themes/`` to record an honest ``material_theme_installed: false``. No
Material icon source or assets exist yet, so there is nothing to guard -- this
only pins what is real today so future drift fails closed:

* ``fallback`` -- ``IconThemeSelector.hxx`` hardcodes the ``colibre`` /
  ``colibre_dark`` fallback ids.
* ``windows_route`` -- on ``_WIN32``, ``GetIconThemeForDesktopEnvironment``
  routes to those fallback ids with no per-desktop routing.
* ``preferred_override_markers`` -- the generic ``mPreferredIconTheme`` path
  already lets any installed, correctly-named theme win on Windows with no new
  C++ wiring.
* ``no_material_in_selector`` -- the selector header/source contain no
  ``material`` substring today (the "not yet implemented" reality).
* ``package_naming`` -- the ``images_<id>[_dark][_svg].zip`` naming and
  ``_svg`` / ``_dark`` display-name stripping any future material package must
  satisfy to be discovered at all.
* ``installed_theme_dirs`` -- the literal 20-directory ``icon-themes/`` set, with
  a negative guard that no ``material*`` directory exists.
* ``iconography_prose`` -- the four qualitative native-iconography rules already
  stated in ``docs/design/01-foundations.md`` S8 and ``MATERIAL_DESIGN.md``.
* ``icon_size_linter`` -- a citation (not duplication) of the pre-existing
  ``bin/check-icon-sizes.py`` lc_/sc_ walk, honestly recorded as a script that
  exists but is not enforced by the Material CI gate.

Source/text evidence only: ``runtime_verified`` is false; no build, icon pixels,
RTL-mirroring, localization, or scaling evidence is claimed, and no gate moves.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/icon-theme-pipeline.json"
CONTRACT_NAME = "windows-icon-theme-pipeline"


class ValidationError(RuntimeError):
    pass


_CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    source = _CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _referenced_files(registry: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("selector_header", "selector_source", "info_source"):
        value = registry.get(key)
        if isinstance(value, str):
            files.append(value)
    prose = registry.get("iconography_prose")
    if isinstance(prose, dict):
        for rule in prose.get("rules", []) or []:
            if isinstance(rule, dict) and isinstance(rule.get("file"), str):
                files.append(rule["file"])
    linter = registry.get("icon_size_linter")
    if isinstance(linter, dict):
        for key in ("path", "ci_workflow"):
            if isinstance(linter.get(key), str):
                files.append(linter[key])
    # De-dup, keep order.
    seen: set[str] = set()
    ordered: list[str] = []
    for rel in files:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def enumerate_theme_dirs(repo_root: Path, registry: Mapping[str, Any]) -> list[str]:
    rel = registry.get("icon_themes_dir")
    if not isinstance(rel, str):
        return []
    base = repo_root / rel
    if not base.is_dir():
        return []
    return sorted(
        entry.name
        for entry in base.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )


def load_repository(
    repo_root: Path = REPOSITORY,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _referenced_files(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    theme_dirs = enumerate_theme_dirs(repo_root, registry)
    return registry, contents, theme_dirs


# --------------------------------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------------------------------
def _text(registry, contents, key, errors) -> tuple[str, str] | None:
    rel = registry.get(key)
    if not isinstance(rel, str):
        errors.append(f"registry:{key}:string required")
        return None
    text = contents.get(rel)
    if text is None:
        errors.append(f"{key}:{rel} missing")
        return None
    return rel, text


def _validate_fallback(registry, contents, errors) -> None:
    resolved = _text(registry, contents, "selector_header", errors)
    if resolved is None:
        return
    rel, text = resolved
    fallback = registry.get("fallback")
    if not isinstance(fallback, dict):
        errors.append("registry:fallback:object required")
        return
    markers = fallback.get("header_markers")
    if not isinstance(markers, list) or not markers:
        errors.append("fallback:header_markers:non-empty array required")
        return
    stripped = strip_cpp_non_code(text)
    for marker in markers:
        if isinstance(marker, str) and marker not in stripped:
            errors.append(f"fallback:{rel} must hardcode the Windows fallback id: missing {marker!r}")


def _validate_windows_route(registry, contents, errors) -> None:
    resolved = _text(registry, contents, "selector_source", errors)
    if resolved is None:
        return
    rel, text = resolved
    stripped = strip_cpp_non_code(text)
    route = registry.get("windows_route")
    if not isinstance(route, dict):
        errors.append("registry:windows_route:object required")
        return
    guard = route.get("guard")
    if not isinstance(guard, str) or guard not in stripped:
        errors.append(f"windows_route:{rel} must gate the Windows route on {guard!r}")
    markers = route.get("markers")
    if not isinstance(markers, list) or not markers:
        errors.append("windows_route:markers:non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and marker not in stripped:
            errors.append(
                f"windows_route:{rel} must route to the fallback ids on _WIN32: missing {marker!r}"
            )


def _validate_preferred_override(registry, contents, errors) -> None:
    resolved = _text(registry, contents, "selector_source", errors)
    if resolved is None:
        return
    rel, text = resolved
    stripped = strip_cpp_non_code(text)
    markers = registry.get("preferred_override_markers")
    if not isinstance(markers, list) or not markers:
        errors.append("registry:preferred_override_markers:non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and marker not in stripped:
            errors.append(
                f"preferred_override:{rel} must keep the generic mPreferredIconTheme override "
                f"path: missing {marker!r}"
            )


def _validate_no_material_in_selector(registry, contents, errors) -> None:
    if registry.get("no_material_in_selector") is not True:
        errors.append(
            "registry:no_material_in_selector:must be true (no Material icon routing exists yet)"
        )
        return
    for key in ("selector_header", "selector_source"):
        rel = registry.get(key)
        text = contents.get(rel) if isinstance(rel, str) else None
        if text is None:
            continue
        if "material" in text.lower():
            errors.append(
                f"no_material_in_selector:{rel} contains a 'material' substring; the ledger records "
                "material_theme_installed:false and no Material icon routing exists yet -- update the "
                "reviewed registry if that changes"
            )


def _validate_package_naming(registry, contents, errors) -> None:
    resolved = _text(registry, contents, "info_source", errors)
    if resolved is None:
        return
    rel, text = resolved
    stripped = strip_cpp_non_code(text)
    naming = registry.get("package_naming")
    if not isinstance(naming, dict):
        errors.append("registry:package_naming:object required")
        return
    markers = naming.get("markers")
    if not isinstance(markers, list) or not markers:
        errors.append("package_naming:markers:non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and marker not in stripped:
            errors.append(
                f"package_naming:{rel} must keep the images_<id>.zip / _svg / _dark contract: "
                f"missing {marker!r}"
            )


def _validate_theme_dirs(registry, theme_dirs, errors) -> None:
    declared = registry.get("installed_theme_dirs")
    if not isinstance(declared, list) or not declared:
        errors.append("registry:installed_theme_dirs:non-empty array required")
        return
    declared_sorted = sorted(str(d) for d in declared)
    prefix = registry.get("forbidden_theme_prefix")
    if not isinstance(prefix, str) or not prefix:
        errors.append("registry:forbidden_theme_prefix:non-empty string required")
        prefix = None

    if declared_sorted != sorted(theme_dirs):
        missing = sorted(set(declared_sorted) - set(theme_dirs))
        extra = sorted(set(theme_dirs) - set(declared_sorted))
        detail = []
        if missing:
            detail.append(f"declared-but-absent: {missing}")
        if extra:
            detail.append(f"present-but-unrecorded: {extra}")
        errors.append(
            "installed_theme_dirs: icon-themes/ enumeration drifted from the ledger ("
            + "; ".join(detail)
            + ")"
        )

    if prefix is not None:
        for name in theme_dirs:
            if name.lower().startswith(prefix.lower()):
                errors.append(
                    f"installed_theme_dirs: a {prefix!r}-prefixed icon theme directory {name!r} "
                    "exists; material_theme_installed:false is no longer honest -- a reviewed "
                    "registry update and gate re-evaluation is required"
                )
        for name in declared_sorted:
            if name.lower().startswith(prefix.lower()):
                errors.append(
                    f"installed_theme_dirs: the ledger records a {prefix!r}-prefixed directory "
                    f"{name!r} but material_theme_installed must stay false"
                )

    if registry.get("material_theme_installed") is not False:
        errors.append(
            "registry:material_theme_installed:must be false (no Material icon theme is installed)"
        )


def _validate_iconography_prose(registry, contents, errors) -> None:
    prose = registry.get("iconography_prose")
    if not isinstance(prose, dict):
        errors.append("registry:iconography_prose:object required")
        return
    rules = prose.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("iconography_prose:rules:non-empty array required")
        return
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"iconography_prose:rule[{index}]:object required")
            continue
        rel = rule.get("file")
        substring = rule.get("substring")
        label = rule.get("rule", "?")
        if not isinstance(rel, str) or not isinstance(substring, str):
            errors.append(f"iconography_prose:rule[{index}]:file/substring must be strings")
            continue
        text = contents.get(rel)
        if text is None:
            errors.append(f"iconography_prose:{rel} missing (rule: {label})")
            continue
        if substring not in text:
            errors.append(
                f"iconography_prose:{rel} no longer states the {label!r} rule: missing {substring!r}"
            )


def _validate_icon_size_linter(registry, contents, errors) -> None:
    linter = registry.get("icon_size_linter")
    if not isinstance(linter, dict):
        errors.append("registry:icon_size_linter:object required")
        return
    path = linter.get("path")
    if not isinstance(path, str):
        errors.append("icon_size_linter:path:string required")
        return
    if path not in contents:
        errors.append(f"icon_size_linter:{path} must exist (the cited pre-existing size linter)")
    ci_enforced = linter.get("ci_enforced")
    if not isinstance(ci_enforced, bool):
        errors.append("icon_size_linter:ci_enforced:boolean required")
        return
    workflow = linter.get("ci_workflow")
    workflow_text = contents.get(workflow) if isinstance(workflow, str) else None
    if workflow_text is not None:
        basename = path.rsplit("/", 1)[-1]
        referenced = basename in workflow_text
        if referenced != ci_enforced:
            errors.append(
                f"icon_size_linter:ci_enforced is {ci_enforced} but {basename} is "
                f"{'referenced' if referenced else 'not referenced'} in {workflow}; the honest "
                "caveat must match reality"
            )


def _validate_meta(registry, errors) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT_NAME:
        errors.append(f"registry:contract:must be {CONTRACT_NAME!r}")
    if registry.get("inventory_row") != "WIN-FND-007":
        errors.append("registry:inventory_row:must be WIN-FND-007")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")


# --------------------------------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------------------------------
def violations(
    registry: Mapping[str, Any], contents: Mapping[str, str], theme_dirs: Sequence[str]
) -> list[str]:
    errors: list[str] = []
    _validate_meta(registry, errors)
    _validate_fallback(registry, contents, errors)
    _validate_windows_route(registry, contents, errors)
    _validate_preferred_override(registry, contents, errors)
    _validate_no_material_in_selector(registry, contents, errors)
    _validate_package_naming(registry, contents, errors)
    _validate_theme_dirs(registry, list(theme_dirs), errors)
    _validate_iconography_prose(registry, contents, errors)
    _validate_icon_size_linter(registry, contents, errors)
    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents, theme_dirs = load_repository(repo_root)
    errors = violations(registry, contents, theme_dirs)
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
        print(f"Icon-theme pipeline contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _, theme_dirs = load_repository(repo_root)
    print(
        "Icon-theme pipeline contract passed: colibre/colibre_dark Windows fallback and the generic "
        "mPreferredIconTheme override are pinned, the images_<id>.zip/_svg/_dark naming contract holds, "
        f"{len(theme_dirs)} icon-themes/ directories are enumerated with no material* directory "
        "(material_theme_installed:false), and the four iconography prose rules are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
