#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material elevation strategy (WIN-FND-003).

``qa/windows-ui-contract/elevation-strategy.json`` pins the one elevation channel
that is genuinely native today -- the outlined Border/Frame part -- and ledgers the
design's full elevation triad (borders / tonal surfaces / shadows, plus the
prototype scrim) against docs/design/01-foundations.md sections 2.1 and 4, honestly
separating what is compiled from what is prototype-only. It never mutates any anchor.

It asserts:

* **Border channel** -- the ``ControlType::Frame``/``Border`` part in the canonical
  definition.xml keeps its exact token quadruple (``@outline-variant`` stroke,
  ``@surface-container`` fill, ``@stroke-thin`` width, ``@corner-container`` radius),
  and the native draw path still insets the content region by 2px on every edge;
* **Tonal surfaces** -- the three surface roles (``@surface`` /
  ``@surface-container`` / ``@surface-container-low``) resolve in both light and dark
  palettes;
* **Scrim** -- the three ``--scrim`` rgba literals are byte-identical across
  01-foundations.md 2.1 and site/prototype.html;
* **Shadows** -- every one of the section-4 shadow-table rows is tagged
  prototype-only, matches the doc verbatim, and (for the surfaces the prototype
  actually renders) the same literal appears as a ``box-shadow`` in the prototype, so
  the doc is the single source of truth and no prototype value can silently drift
  from it. The section-4 table must carry exactly the declared number of rows so a
  future *native* shadow row cannot be slipped in un-ledgered;
* **Opacity/shadow are not latent natively** -- no drawable element in definition.xml
  carries an ``opacity``/``shadow``/``blur``/``elevation`` attribute (opacity is not
  even parseable in the widget-definition schema); the reader's ``shadowColor`` is
  bound to the legacy ``StyleSettings`` 3D-bevel slot, a distinct concept from this
  row's MD3 elevation shadow.

Source evidence only: ``runtime_verified`` is false throughout. Native shadow/scrim/
opacity rendering, any pixel/MATRIX capture, and the unassigned window-shell elevation
owner remain the separate build/runtime gates and are not claimed here.
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
REGISTRY_PATH = "qa/windows-ui-contract/elevation-strategy.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CHAPTER_PATH = "docs/design/01-foundations.md"
PROTOTYPE_PATH = "site/prototype.html"
DRAW_PATH = "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
READER_PATH = "vcl/source/gdi/WidgetDefinitionReader.cxx"
CONTRACT = "material-elevation-strategy"
THEME_FLAG = "VCL_FILE_WIDGET_THEME"

REQUIRED_SCHEMES = ("", "dark")
# Attribute names that would mean native shadow/opacity/elevation became a drawable
# dimension. None may appear on any element in definition.xml.
FORBIDDEN_DRAWABLE_ATTRS = frozenset({"opacity", "shadow", "blur", "elevation", "box-shadow"})


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _norm_space(value: str) -> str:
    """Remove every whitespace character so a CSS literal compares equal across the
    doc's ``, `` and the prototype's ``,`` separators."""

    return re.sub(r"\s+", "", value)


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in (DEFINITION_PATH, CHAPTER_PATH, PROTOTYPE_PATH, DRAW_PATH, READER_PATH):
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


def _frame_border_rect(root: ET.Element) -> ET.Element | None:
    frame = root.find("frame")
    if frame is None:
        return None
    for part in frame.findall("part"):
        if part.get("value") != "Border":
            continue
        for state in part.findall("state"):
            rect = state.find("rect")
            if rect is not None:
                return rect
    return None


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_border(
    root: ET.Element, border: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    rect = _frame_border_rect(root)
    if rect is None:
        errors.append("border:the ControlType::Frame/Border rect is missing from definition.xml")
    else:
        tokens = border.get("tokens")
        if not isinstance(tokens, dict):
            errors.append("border:tokens:object required")
        else:
            for attr, expected in tokens.items():
                actual = rect.get(attr)
                if actual != expected:
                    errors.append(
                        f"border:frame/Border token drift: {attr} is {actual!r}, "
                        f"expected {expected!r}"
                    )

    for role in border.get("surface_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"border:tonal:@{role} missing from the {label} palette")

    inset = border.get("inset")
    if isinstance(inset, dict):
        source_path = inset.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"border:inset:source {source_path!r} missing")
        else:
            code = _without_cpp_comments(source)
            for marker in inset.get("markers", []) or []:
                if isinstance(marker, str) and marker not in code:
                    errors.append(f"border:inset:marker missing in code ({marker!r})")


def _validate_scrim(
    scrim: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    chapter = contents.get(CHAPTER_PATH, "")
    prototype = contents.get(PROTOTYPE_PATH, "")
    literals = scrim.get("literals")
    if not isinstance(literals, dict) or not literals:
        errors.append("scrim:literals:non-empty object required")
        return
    for label, literal in literals.items():
        if not isinstance(literal, str):
            errors.append(f"scrim:{label}:literal must be a string")
            continue
        if literal not in chapter:
            errors.append(
                f"scrim:{label}:literal {literal!r} not found in {CHAPTER_PATH} 2.1"
            )
        if f"scrim:'{literal}'" not in prototype:
            errors.append(
                f"scrim:{label}:literal {literal!r} not found in the prototype scrim palette"
            )


def _section4_shadow_rows(chapter: str) -> list[tuple[str, str]]:
    """Return the (surface, shadow-literal) rows of the section-4 shadow table.

    The shadow cell may hold one backtick-wrapped literal, or two joined by `` / ``
    (the Impress/Draw canvas row: one value per app). Backticks are stripped; the
    header and separator rows have no backtick and are skipped.
    """

    lines = chapter.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("## 4."))
    except StopIteration:
        return []
    rows: list[tuple[str, str]] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        match = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if match and "`" in match.group(2):
            shadow = match.group(2).replace("`", "").strip()
            rows.append((match.group(1).strip(), shadow))
    return rows


def _validate_shadows(
    root: ET.Element, shadows: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    chapter = contents.get(CHAPTER_PATH, "")
    prototype = contents.get(PROTOTYPE_PATH, "")
    prototype_norm = _norm_space(prototype)

    doc_rows = _section4_shadow_rows(chapter)
    doc_map = {surface: shadow for surface, shadow in doc_rows}

    rows = shadows.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("shadows:rows:non-empty array required")
        return

    expected_count = shadows.get("doc_row_count")
    if isinstance(expected_count, int) and len(doc_rows) != expected_count:
        errors.append(
            f"shadows:doc_row_count:section 4 has {len(doc_rows)} shadow-table rows, "
            f"expected {expected_count} (a native shadow row must be ledgered, not slipped in)"
        )
    if len(rows) != len(doc_rows):
        errors.append(
            f"shadows:the ledger has {len(rows)} rows but section 4 has {len(doc_rows)} "
            "-- every doc shadow row must be ledgered"
        )

    for row in rows:
        if not isinstance(row, dict):
            errors.append("shadows:row:object required")
            continue
        surface = row.get("surface")
        shadow = row.get("shadow")
        if not isinstance(surface, str) or not isinstance(shadow, str):
            errors.append("shadows:row:surface and shadow must be strings")
            continue
        # Honest tag: every shadow row is prototype-only, never a native claim.
        if row.get("status") != "prototype-only":
            errors.append(f"shadows:{surface}:status must be 'prototype-only'")
        # The doc is the single source of truth: the row must match the doc verbatim.
        if surface not in doc_map:
            errors.append(f"shadows:{surface}:no matching surface row in section 4")
        elif doc_map[surface] != shadow:
            errors.append(
                f"shadows:{surface}:doc drift: section 4 says {doc_map[surface]!r}, "
                f"ledger says {shadow!r}"
            )
        # For the surfaces the prototype renders, the doc literal must appear as an
        # actual box-shadow -- the reconciliation guard that fails on prototype drift.
        # A `` / ``-joined cell (Impress/Draw) names one value per app: each segment
        # must appear; the internal comma of a layered shadow is never split.
        if row.get("prototype"):
            for segment in shadow.split(" / "):
                if _norm_space(segment) not in prototype_norm:
                    errors.append(
                        f"shadows:{surface}:the doc shadow {segment!r} is not present as a "
                        "box-shadow in the prototype (reconcile the prototype to the doc, "
                        "do not loosen this assertion)"
                    )


def _validate_opacity(
    root: ET.Element, opacity: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for element in root.iter():
        for attr in element.attrib:
            if attr in FORBIDDEN_DRAWABLE_ATTRS:
                errors.append(
                    f"opacity:definition.xml <{element.tag}> carries a forbidden drawable "
                    f"attribute {attr!r}; native shadow/opacity/elevation is not implemented"
                )
    # The legacy shadowColor is the StyleSettings 3D-bevel slot, not an MD3 elevation
    # shadow: prove the reader binds it there so this contract does not contradict the
    # existing check-material-theme.py assertion.
    marker = opacity.get("legacy_shadow_slot_marker")
    if isinstance(marker, str):
        reader = contents.get(READER_PATH)
        if reader is None:
            errors.append(f"opacity:legacy-shadow-slot:reader {READER_PATH} missing")
        elif marker not in _without_cpp_comments(reader):
            errors.append(
                f"opacity:legacy-shadow-slot:marker missing in reader ({marker!r})"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

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
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    root = _parse_definition(contents.get(DEFINITION_PATH, ""), errors)

    border = registry.get("border")
    if not isinstance(border, dict):
        errors.append("registry:border:object required")
        border = {}
    scrim = registry.get("scrim")
    if not isinstance(scrim, dict):
        errors.append("registry:scrim:object required")
        scrim = {}
    shadows = registry.get("shadows")
    if not isinstance(shadows, dict):
        errors.append("registry:shadows:object required")
        shadows = {}
    opacity = registry.get("opacity")
    if not isinstance(opacity, dict):
        errors.append("registry:opacity:object required")
        opacity = {}

    if root is not None:
        _validate_border(root, border, contents, errors)
        _validate_shadows(root, shadows, contents, errors)
        _validate_opacity(root, opacity, contents, errors)
    _validate_scrim(scrim, contents, errors)

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
        print(f"Material elevation strategy contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material elevation strategy contract passed: the native Border/Frame token "
        "quadruple and 2px inset, the three-surface tonal roles, the scrim literals, "
        "the prototype-only shadow ledger (reconciled to the doc), and the "
        "no-native-opacity guard are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
