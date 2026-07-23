#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material Writer ruler colour chain (WIN-WR-002).

``qa/windows-ui-contract/writer-ruler-token-contract.json`` pins the StyleSettings
colour-slot chain that paints Writer's ruler under the Material file-widget theme.
Writer's ruler is ``SwCommentRuler`` (a compiled ``SvxRuler`` subclass) whose
``Paint()`` delegates to the shared ``Ruler::ImplDraw`` in
svtools/source/control/ruler.cxx, plus ``SwCommentRuler``'s own
``DrawCommentControl``. Every colour those functions read from StyleSettings is
populated from definition.xml's ``<style>`` slots by
``FileDefinitionWidgetDraw::updateSettings`` when the Material theme is selected.

This checker parses the real tree fail-closed:

* ``style_slots`` -- each declared ``<style>`` slot in definition.xml must carry
  its exact Material token (windowColor -> @surface, dialogColor ->
  @surface-container, ...). A slot drift fails closed. The definition file is
  read only, never mutated.
* ``palette_colors`` -- every palette role the slots resolve to must exist in
  *both* the light and dark palettes.
* ``bridge`` -- FileDefinitionWidgetDraw.cxx must still contain the
  ``updateSettings`` function marker and every ``aStyleSet.Set*Color(...)``
  assignment that copies a definition slot into the live StyleSettings. A dropped
  or renamed assignment breaks the chain the ruler reads and fails closed
  (comments are stripped first, so comment-only wiring cannot satisfy it).
* ``paint_paths`` -- swruler.cxx (the Writer Comments toggle + the
  ``SvxRuler::Paint`` delegation) and ruler.cxx (the shared page-track / margin /
  border / indent painting) must each still contain every pinned
  ``rStyleSettings.Get*Color()`` call-site marker; a renamed, removed, or
  reworded call fails closed (comments stripped).
* ``carveout`` -- the ``ThemeColors::IsThemeEnabled()`` office-theme-colors
  branch is an honest carve-out: its ``status`` must stay ``specified`` (never
  claimed as Material-covered) and its branch marker must remain present in
  source so the carve-out reflects real code.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, ruler pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/writer-ruler-token-contract.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# The palettes whose color roles must all resolve (light = no scheme attribute).
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    bridge = registry.get("bridge")
    if isinstance(bridge, dict) and isinstance(bridge.get("source"), str):
        paths.add(bridge["source"])
    for path_entry in registry.get("paint_paths", []) or []:
        if isinstance(path_entry, dict) and isinstance(path_entry.get("source"), str):
            paths.add(path_entry["source"])
    carveout = registry.get("carveout")
    if isinstance(carveout, dict) and isinstance(carveout.get("source"), str):
        paths.add(carveout["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# definition.xml lookups
# --------------------------------------------------------------------------------------------------
def _parse_definition(text: str | None, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append("definition:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"definition:unparseable xml:{error}")
        return None


def _palette_color(root: ET.Element, scheme: str, name: str) -> str | None:
    for palette in root.findall("palette"):
        if (palette.get("scheme") or "") != scheme:
            continue
        for color in palette.findall("color"):
            if color.get("name") == name:
                return color.get("value")
    return None


def _style_slot_value(root: ET.Element, slot: str) -> str | None:
    style = root.find("style")
    if style is None:
        return None
    element = style.find(slot)
    return element.get("value") if element is not None else None


def _validate_style_slots(root: ET.Element, slots: Any, errors: list[str]) -> None:
    if not isinstance(slots, list) or not slots:
        errors.append("style_slots:non-empty array required")
        return
    for entry in slots:
        if not isinstance(entry, dict):
            errors.append("style_slots:entry:object required")
            continue
        slot = entry.get("slot")
        token = entry.get("token")
        if not isinstance(slot, str) or not isinstance(token, str):
            errors.append("style_slots:entry:slot/token strings required")
            continue
        actual = _style_slot_value(root, slot)
        if actual is None:
            errors.append(f"style_slots:{slot} missing from definition.xml <style>")
        elif actual != token:
            errors.append(
                f"style_slots:{slot} is {actual!r}, expected {token!r} (token drift)"
            )


def _validate_palette(root: ET.Element, roles: Any, errors: list[str]) -> None:
    if not isinstance(roles, list) or not roles:
        errors.append("palette_colors:non-empty array required")
        return
    for role in roles:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# Source-marker validators
# --------------------------------------------------------------------------------------------------
def _validate_bridge(bridge: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(bridge, dict):
        errors.append("registry:bridge:object required")
        return
    source_path = bridge.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"bridge:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    marker = bridge.get("function_marker")
    if isinstance(marker, str) and marker not in code:
        errors.append(f"bridge:function marker missing in code ({marker})")
    assignments = bridge.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        errors.append("bridge:assignments:non-empty array required")
        return
    for assignment in assignments:
        if isinstance(assignment, str) and assignment not in code:
            errors.append(f"bridge:assignment missing in code ({assignment})")


def _validate_paint_paths(paths: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(paths, list) or not paths:
        errors.append("registry:paint_paths:non-empty array required")
        return
    seen: set[str] = set()
    for entry in paths:
        if not isinstance(entry, dict):
            errors.append("paint_paths:entry:object required")
            continue
        pid = entry.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append("paint_paths:entry:id:non-empty string required")
            continue
        if pid in seen:
            errors.append(f"paint_paths:{pid}:duplicate id")
        seen.add(pid)
        source_path = entry.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"paint_paths:{pid}:source {source_path} missing")
            continue
        code = _without_cpp_comments(source)
        delegation = entry.get("delegation_marker")
        if isinstance(delegation, str) and delegation not in code:
            errors.append(f"paint_paths:{pid}:delegation marker missing in code ({delegation})")
        markers = entry.get("markers")
        if not isinstance(markers, list) or not markers:
            errors.append(f"paint_paths:{pid}:markers:non-empty array required")
            continue
        for marker in markers:
            if isinstance(marker, str) and marker not in code:
                errors.append(f"paint_paths:{pid}:marker missing in code ({marker})")


def _validate_carveout(carveout: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(carveout, dict):
        errors.append("registry:carveout:object required")
        return
    if carveout.get("status") != "specified":
        errors.append(
            "carveout:status:must stay 'specified' (the ThemeColors office-theme-colors "
            "branch is a user opt-in; it is never claimed as Material-token-covered)"
        )
    source_path = carveout.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"carveout:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    branch_marker = carveout.get("branch_marker")
    if isinstance(branch_marker, str) and branch_marker not in code:
        errors.append(
            f"carveout:branch marker missing in code ({branch_marker}) -- the carve-out must "
            "reflect a real source branch"
        )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-writer-ruler-token-contract":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("theme_flag") != "VCL_FILE_WIDGET_THEME":
        errors.append("registry:theme_flag:must be VCL_FILE_WIDGET_THEME")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    root = _parse_definition(contents.get(DEFINITION_PATH), errors)
    if root is not None:
        _validate_style_slots(root, registry.get("style_slots"), errors)
        _validate_palette(root, registry.get("palette_colors"), errors)

    _validate_bridge(registry.get("bridge"), contents, errors)
    _validate_paint_paths(registry.get("paint_paths"), contents, errors)
    _validate_carveout(registry.get("carveout"), contents, errors)

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
        print(f"Writer ruler token contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Writer ruler token contract passed: definition.xml <style> ruler colour slots, "
        "the FileDefinitionWidgetDraw::updateSettings bridge assignments, and the "
        "SwCommentRuler + shared Ruler::ImplDraw StyleSettings call sites are intact, with "
        "the ThemeColors office-theme-colors branch carved out spec-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
