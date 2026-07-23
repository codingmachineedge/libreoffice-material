#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for Calc grid header/selection colour (WIN-CA-003).

``qa/windows-ui-contract/calc-grid-selection.json`` pins the real, already-wired
chain by which Calc's header highlight and active-cell selection consume the
compiled Material StyleSettings accent slot:

    definition.xml <style> accentColor=@primary (highlightColor / highlightTextColor
    / faceColor too) resolving in both palettes
      -> svtools/source/config/colorcfg.cxx ColorConfig::GetDefaultColor routing
         CALCCELLFOCUS and CALCDBFOCUS to StyleSettings::GetAccentColor()
      -> the sc/source/ui/view/{hdrcont,gridwin,gridwin4}.cxx paint call sites that
         read GetColorValue(CALCCELLFOCUS/CALCDBFOCUS), GetFaceColor(),
         GetButtonTextColor(), GetHighlightTextColor() and GetShadowColor().

Unlike the guarded-material-source pattern (status.cxx / inputwin.cxx / tabcont.cxx),
there is no VCL_FILE_WIDGET_THEME guard here -- this is stock upstream colour
plumbing that already happens to be Material-routed via the fork's colorcfg accent
special-cases, so the contract pins the UNCONDITIONAL existing wiring. Every C++
marker is matched against a comment-stripped, whitespace-normalized copy, so
commented-out or reformatted wiring fails closed.

Three things the row's other words imply but the source does NOT actually
Material-route are carved out honestly so none can be silently promoted:

* ``density`` (compact/comfortable defaults) -- no native code anywhere; status
  stays ``specified``;
* ``alignment`` (numeric-right/text-left) -- pre-existing stock ScPatternAttr
  behaviour, nothing theme-related to pin; status stays ``specified``;
* ``gridlines`` -- CALCGRID is consumed in gridwin4.cxx but is NOT special-cased
  in ColorConfig::GetDefaultColor, so it falls through to the fixed cAutoColors
  default (COL_GRAY3/COL_GRAY7), NOT a definition.xml token. Its status is
  ``divergent`` and the checker asserts the ``present_marker`` (CALCGRID consumed)
  is present AND the ``absent_marker`` (``case CALCGRID:``) is ABSENT from
  colorcfg.cxx. FAIL-CLOSED DUAL-UPDATE DISCIPLINE: if a future commit genuinely
  routes CALCGRID through a Material token by adding ``case CALCGRID:`` (a real,
  build-verifiable improvement), this absent-marker assertion fails closed and the
  registry's gridlines status MUST be updated in the SAME change, so code and
  ledger can never silently diverge in either direction.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, grid pixels, contrast, or runtime interaction are claimed, and the accent
routing is conditional on the user's Application-Colors value being COL_AUTO
(see the registry ``conditional_note``).
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
REGISTRY_PATH = "qa/windows-ui-contract/calc-grid-selection.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

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


def _collapse_ws(source: str) -> str:
    return re.sub(r"\s+", " ", source).strip()


def _normalized_code(source: str) -> str:
    return _collapse_ws(_without_cpp_comments(source))


def _collect_sources(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = {DEFINITION_PATH}
    bridge = registry.get("colorcfg_bridge")
    if isinstance(bridge, dict) and isinstance(bridge.get("source"), str):
        paths.add(bridge["source"])
    header = registry.get("header_highlight")
    if isinstance(header, dict) and isinstance(header.get("source"), str):
        paths.add(header["source"])
    cell = registry.get("cell_cursor")
    if isinstance(cell, dict):
        for entry in cell.get("sources", []) or []:
            if isinstance(entry, dict) and isinstance(entry.get("source"), str):
                paths.add(entry["source"])
    carveouts = registry.get("carveouts")
    if isinstance(carveouts, dict):
        gridlines = carveouts.get("gridlines")
        if isinstance(gridlines, dict):
            for key in ("colorcfg_source", "consumer_source"):
                if isinstance(gridlines.get(key), str):
                    paths.add(gridlines[key])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _collect_sources(registry):
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
    for index, entry in enumerate(slots):
        if not isinstance(entry, dict):
            errors.append(f"style_slots[{index}]:object required")
            continue
        slot = entry.get("slot")
        token = entry.get("token")
        if not isinstance(slot, str) or not isinstance(token, str) or not token.startswith("@"):
            errors.append(f"style_slots[{index}]:slot/token malformed (token must be @role)")
            continue
        actual = _style_slot_value(root, slot)
        if actual != token:
            errors.append(
                f"style_slots:{slot}:<style><{slot}> is {actual!r}, expected {token!r} (token drift)"
            )
        role = token[1:]
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"style_slots:{slot}:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# source markers
# --------------------------------------------------------------------------------------------------
def _markers_present(
    context: str, source_path: Any, markers: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:source {source_path} missing")
        return
    code = _normalized_code(source)
    if not isinstance(markers, list) or not markers:
        errors.append(f"{context}:markers:non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and _collapse_ws(marker) not in code:
            errors.append(f"{context}:marker missing in code ({marker})")


def _validate_carveouts(carveouts: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(carveouts, dict):
        errors.append("registry:carveouts:object required")
        return
    for name in ("density", "alignment"):
        block = carveouts.get(name)
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
        elif block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status:must stay 'specified' "
                f"({name} has no native Material consumption; must not be promoted)"
            )

    gridlines = carveouts.get("gridlines")
    if not isinstance(gridlines, dict):
        errors.append("carveouts:gridlines:object required")
        return
    if gridlines.get("status") != "divergent":
        errors.append(
            "carveouts:gridlines:status:must stay 'divergent' (CALCGRID falls through to the "
            "fixed cAutoColors default, not a Material token; must not be promoted without a "
            "coordinated code + status change)"
        )
    consumer_source = gridlines.get("consumer_source")
    present_marker = gridlines.get("present_marker")
    consumer = contents.get(consumer_source) if isinstance(consumer_source, str) else None
    if consumer is None:
        errors.append(f"carveouts:gridlines:consumer_source {consumer_source} missing")
    elif isinstance(present_marker, str) and _collapse_ws(present_marker) not in _normalized_code(
        consumer
    ):
        errors.append(
            f"carveouts:gridlines:present_marker missing (CALCGRID must still be consumed for "
            f"gridlines): {present_marker!r}"
        )
    colorcfg_source = gridlines.get("colorcfg_source")
    absent_marker = gridlines.get("absent_marker")
    colorcfg = contents.get(colorcfg_source) if isinstance(colorcfg_source, str) else None
    if colorcfg is None:
        errors.append(f"carveouts:gridlines:colorcfg_source {colorcfg_source} missing")
    elif isinstance(absent_marker, str) and _collapse_ws(absent_marker) in _normalized_code(colorcfg):
        # FAIL-CLOSED DUAL-UPDATE: a genuine 'case CALCGRID:' Material routing is a real
        # improvement, but it invalidates the 'divergent' status; require the same-change
        # status flip rather than let code and ledger silently disagree.
        errors.append(
            "carveouts:gridlines:absent_marker now PRESENT in colorcfg.cxx "
            f"({absent_marker!r}): CALCGRID appears to be special-cased/Material-routed now, so "
            "the gridlines status must be updated from 'divergent' in the SAME change"
        )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-calc-grid-selection-consumption":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    root = _parse_definition(contents.get(DEFINITION_PATH), errors)
    if root is not None:
        _validate_style_slots(root, registry.get("style_slots"), errors)

    bridge = registry.get("colorcfg_bridge")
    if isinstance(bridge, dict):
        _markers_present("colorcfg_bridge", bridge.get("source"), bridge.get("markers"), contents, errors)
    else:
        errors.append("registry:colorcfg_bridge:object required")

    header = registry.get("header_highlight")
    if isinstance(header, dict):
        _markers_present("header_highlight", header.get("source"), header.get("markers"), contents, errors)
    else:
        errors.append("registry:header_highlight:object required")

    cell = registry.get("cell_cursor")
    if isinstance(cell, dict):
        sources = cell.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append("cell_cursor:sources:non-empty array required")
        else:
            for index, entry in enumerate(sources):
                if not isinstance(entry, dict):
                    errors.append(f"cell_cursor:sources[{index}]:object required")
                    continue
                _markers_present(
                    f"cell_cursor[{entry.get('source')}]",
                    entry.get("source"),
                    entry.get("markers"),
                    contents,
                    errors,
                )
    else:
        errors.append("registry:cell_cursor:object required")

    _validate_carveouts(registry.get("carveouts"), contents, errors)

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
        print(f"Calc grid selection contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Calc grid selection contract passed: definition.xml accent/highlight/face slots resolve "
        "in both palettes, colorcfg.cxx routes CALCCELLFOCUS/CALCDBFOCUS to GetAccentColor(), the "
        "hdrcont/gridwin/gridwin4 paint sites consume them, and density/alignment/gridlines stay "
        "carved out (gridlines divergent, not Material-routed)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
