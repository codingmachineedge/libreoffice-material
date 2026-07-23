#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material window/floating title bars (WIN-NAV-007).

``qa/windows-ui-contract/titlebar-composition.json`` pins exactly what the row's
compiled-but-unverified gates already claim -- and, crucially, an ABSENCE fact that keeps
the row honest. This checker cross-validates all of it against the real tree:

* ``metrics`` -- definition.xml must carry ``height-window-title`` = 18 and
  ``height-floating-title`` = 14 with the exact values (metric drift fails closed);
* ``settings`` -- the ``<settings>`` block must map ``titleHeight`` ->
  ``@height-window-title`` and ``floatTitleHeight`` -> ``@height-floating-title``;
* ``style_slots`` -- the six frame-activation ``<style>`` slots must resolve to the
  design-05 section 7.1 tokens (active* -> ``@primary`` / ``@on-primary``; deactive* ->
  ``@disabled-container`` / ``@outline`` / ``@outline-variant``), and every referenced
  palette role must exist in *both* the light and dark palettes;
* ``owner`` -- FileDefinitionWidgetDraw.cxx must carry the generic StyleSettings push
  markers in *code* (comments stripped), proving the metrics/colours are wired into
  ``StyleSettings`` -- shared cross-control, cross-platform plumbing, not a title-bar
  render; and
* ``consumption`` -- the honest half. ``status`` must stay ``"not-wired"`` and the
  declared markers (``GetActiveColor``/``GetDeactiveColor``/... in brdwin.cxx and the DWM
  caption/border/text-colour attributes in salframe.cxx) must stay **absent** from
  comment-stripped code. These absence markers are intentionally fragile: the day a
  future commit genuinely wires an active/inactive visual distinction (a real,
  build-verifiable improvement) this checker fails closed and demands a coordinated
  registry + inventory-row update, rather than letting the row drift silently to a
  claimed pass.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build,
title-bar pixels, or runtime active/inactive capture are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/titlebar-composition.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# The palettes whose colour roles must all resolve (light = no scheme attribute).
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
    owner = registry.get("owner")
    if isinstance(owner, dict) and isinstance(owner.get("source"), str):
        paths.add(owner["source"])
    consumption = registry.get("consumption")
    if isinstance(consumption, dict):
        for entry in consumption.get("absent_markers", []) or []:
            if isinstance(entry, dict) and isinstance(entry.get("source"), str):
                paths.add(entry["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# definition.xml lookups
# --------------------------------------------------------------------------------------------------
def _parse_definition(text: str, errors: list[str]) -> ET.Element | None:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"definition:xml:{error}")
        return None


def _palette_color(root: ET.Element, scheme: str, name: str) -> str | None:
    for palette in root.findall("palette"):
        if (palette.get("scheme") or "") != scheme:
            continue
        for color in palette.findall("color"):
            if color.get("name") == name:
                return color.get("value")
    return None


def _named_value(root: ET.Element, container: str, tag: str, name: str) -> str | None:
    holder = root.find(container)
    if holder is None:
        return None
    for element in holder.findall(tag):
        if element.get("name") == name:
            return element.get("value")
    return None


def _metric_value(root: ET.Element, name: str) -> str | None:
    return _named_value(root, "metrics", "metric", name)


def _setting_value(root: ET.Element, name: str) -> str | None:
    section = root.find("settings")
    if section is None:
        return None
    element = section.find(name)
    return element.get("value") if element is not None else None


def _style_slot_value(root: ET.Element, slot: str) -> str | None:
    style = root.find("style")
    if style is None:
        return None
    element = style.find(slot)
    return element.get("value") if element is not None else None


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_metrics(root: ET.Element, metrics: Sequence[Any], errors: list[str]) -> None:
    for metric in metrics or []:
        if not isinstance(metric, dict):
            continue
        name = metric.get("name")
        expected = metric.get("value")
        actual = _metric_value(root, name) if isinstance(name, str) else None
        if actual is None:
            errors.append(f"metrics:{name} missing in definition.xml <metrics>")
        elif actual != expected:
            errors.append(f"metrics:{name} is {actual!r}, expected {expected!r} (metric drift)")


def _validate_settings(root: ET.Element, settings: Sequence[Any], errors: list[str]) -> None:
    for setting in settings or []:
        if not isinstance(setting, dict):
            continue
        name = setting.get("name")
        expected = setting.get("value")
        actual = _setting_value(root, name) if isinstance(name, str) else None
        if actual is None:
            errors.append(f"settings:<{name}> missing in definition.xml <settings>")
        elif actual != expected:
            errors.append(f"settings:<{name}> is {actual!r}, expected {expected!r}")


def _validate_style_slots(root: ET.Element, slots: Sequence[Any], errors: list[str]) -> None:
    for slot_decl in slots or []:
        if not isinstance(slot_decl, dict):
            continue
        slot = slot_decl.get("slot")
        token = slot_decl.get("token")
        actual = _style_slot_value(root, slot) if isinstance(slot, str) else None
        if actual != token:
            errors.append(
                f"style_slots:<style><{slot}> is {actual!r}, expected {token!r} "
                "(frame-activation slot drift; docs/design/05-navigation.md 7.1)"
            )


def _validate_palette(root: ET.Element, roles: Sequence[Any], errors: list[str]) -> None:
    for role in roles or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"palette:@{role} missing from the {label} palette")


def _validate_owner(
    owner: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = owner.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"owner:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    for marker in owner.get("markers", []) or []:
        if isinstance(marker, str) and marker not in code:
            errors.append(f"owner:marker missing in code ({marker})")


def _validate_consumption(
    consumption: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    # Honest guard: the frame-activation slots are pushed into StyleSettings but nothing
    # consumes them for an active/inactive distinction. This fact must NOT be promoted to
    # a claimed wiring.
    if consumption.get("status") != "not-wired":
        errors.append(
            "consumption:status:must stay 'not-wired' (nothing consumes the active/deactive "
            "slots for a visual distinction -- brdwin.cxx and the DWM chrome are unwired; "
            "see docs/design/05-navigation.md 7.1/7.7)"
        )
    entries = consumption.get("absent_markers")
    if not isinstance(entries, list) or not entries:
        errors.append("consumption:absent_markers:non-empty array required")
        return
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("consumption:absent_markers:object required")
            continue
        source_path = entry.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"consumption:absent-guard:source {source_path} missing")
            continue
        code = _without_cpp_comments(source)
        for marker in entry.get("markers", []) or []:
            if isinstance(marker, str) and marker in code:
                errors.append(
                    f"consumption:absent-guard:{source_path} now contains {marker!r} in code "
                    "-- the active/inactive title-bar path is being wired; promote "
                    "consumption.status and update the inventory row in the same change"
                )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-titlebar-composition":
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

    root = _parse_definition(contents.get(DEFINITION_PATH, ""), errors)

    owner = registry.get("owner")
    if not isinstance(owner, dict):
        errors.append("registry:owner:object required")
        owner = {}
    consumption = registry.get("consumption")
    if not isinstance(consumption, dict):
        errors.append("registry:consumption:object required")
        consumption = {}

    if root is not None:
        _validate_metrics(root, registry.get("metrics", []), errors)
        _validate_settings(root, registry.get("settings", []), errors)
        _validate_style_slots(root, registry.get("style_slots", []), errors)
        _validate_palette(root, registry.get("palette_colors", []), errors)

    _validate_owner(owner, contents, errors)
    _validate_consumption(consumption, contents, errors)

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
        print(f"Material title-bar composition contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material title-bar composition contract passed: the 18/14 title metrics, the "
        "titleHeight/floatTitleHeight settings and the six frame-activation style slots are "
        "wired generically into StyleSettings by FileDefinitionWidgetDraw.cxx, and the "
        "active/inactive consumption path stays honestly not-wired (brdwin.cxx and the DWM "
        "caption chrome carry none of the absence markers)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
