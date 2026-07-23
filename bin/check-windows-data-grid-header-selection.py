#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the data-grid header/selection colour pipe (WIN-CON-003).

``qa/windows-ui-contract/data-grid-header-selection.json`` pins the REAL,
already-compiled header/selection colour pipe consumed by the two "grids target"
surfaces (dbaccess/Base and Calc), and -- just as importantly -- records exactly
where each surface STOPS SHORT of that pipe, correcting the design chapter's
over-claim rather than repeating it.

What is genuinely wired (positive pins):

* the definition.xml ``<listheader>`` Button/Arrow part and the ``<style>``
  highlight/alternating-row/deactive/face slots exist with the exact tokens, in
  both palettes;
* ``vcl/source/gdi/FileDefinitionWidgetDraw.cxx`` unconditionally pushes those
  ``<style>`` colours into the live StyleSettings (Face/ButtonText/Shadow/
  Highlight/HighlightText) plus a presence-guarded SetAlternatingRowColor -- real,
  generic, cross-platform infrastructure (not vcl/win-specific);
* dbaccess/Base's grid header IS a vcl HeaderBar (``BrowserHeader: public
  HeaderBar``) whose Button/Arrow paint calls the native ListHeader part
  (headbar.cxx), and ``DbGridControl`` extends the ``EditBrowseBox`` stack
  (gridctrl.hxx); BrowseBox's own selection paint reads
  ``GetHighlightColor()``/``GetHighlightTextColor()`` directly (brwbox2.cxx);
* Calc's idle header face/text/rule line read the same StyleSettings slots
  (hdrcont.cxx) -- a narrower, legitimate positive pin.

What is NOT yet on that pipe (NEGATIVE markers): Calc's SELECTED-header fill and
active-cell cursor ring still resolve through ``svtools::ColorConfig``'s
``CALCCELLFOCUS`` item (Tools>Options>Application Colors), a separate pipe the
Material definition.xml/StyleSettings mechanism never touches. Those surfaces
carry ``status: not_yet_material`` and the checker asserts their
``not_material_markers`` (the CALCCELLFOCUS calls) stay PRESENT and their
``absent_markers`` (``GetHighlightColor(`` / ``GetAccentColor(``) stay ABSENT.

FAIL-CLOSED DUAL-UPDATE DISCIPLINE: if a future pass closes the gap -- rewiring
the Calc selected-header fill or active-cell cursor onto the Material StyleSettings
pipe -- the CALCCELLFOCUS marker vanishes and/or the absent marker appears, so
this checker fails closed until the surface's ``status`` is flipped to
``compiled`` (and positive markers added) in the SAME change. Code and ledger can
never silently disagree in either direction; the registry status field MUST be
updated in the same change as any such fix.

Every source assertion runs against a comment-stripped, whitespace-normalized copy,
so commented-out or reformatted wiring fails closed. It is source evidence only:
``runtime_verified`` is false throughout -- no native build, grid pixels, or
runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/data-grid-header-selection.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

REQUIRED_SCHEMES = ("", "dark")
ALLOWED_SURFACE_STATUS = {"compiled", "not_yet_material"}
REQUIRED_SURFACE_IDS = {
    "dbaccess-header",
    "dbaccess-selection",
    "calc-header-idle",
    "calc-header-selected-fill",
    "calc-active-cell-ring",
}

STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)


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
    pipe = registry.get("style_pipe")
    if isinstance(pipe, dict) and isinstance(pipe.get("source"), str):
        paths.add(pipe["source"])
    for surface in registry.get("surfaces", []) or []:
        if not isinstance(surface, dict):
            continue
        for entry in surface.get("sources", []) or []:
            if isinstance(entry, dict) and isinstance(entry.get("source"), str):
                paths.add(entry["source"])
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


def _find_part(root: ET.Element, control: str, part: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part:
            return candidate
    return None


def _state_signature(state: ET.Element) -> dict[str, str]:
    return {key: state.get(key, "any") for key in STATE_ATTR_KEYS}


def _match_state(part: ET.Element, attrs: Mapping[str, str]) -> ET.Element | None:
    wanted = {key: attrs.get(key, "any") for key in STATE_ATTR_KEYS}
    for state in part.findall("state"):
        if _state_signature(state) == wanted:
            return state
    return None


def _first_drawing_child(state: ET.Element) -> ET.Element | None:
    for child in state:
        if child.tag in ("rect", "line"):
            return child
    return None


def _validate_part(
    context: str, root: ET.Element, control: str, declaration: Any, errors: list[str]
) -> None:
    if not isinstance(declaration, dict):
        errors.append(f"{context}:object required")
        return
    part_name = declaration.get("part")
    if not isinstance(part_name, str):
        errors.append(f"{context}:part must be a string")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"{context}:{control}/{part_name} missing in definition.xml")
        return
    states = declaration.get("states")
    if not isinstance(states, list) or not states:
        errors.append(f"{context}:{control}/{part_name}:states non-empty array required")
        return
    for state_decl in states:
        if not isinstance(state_decl, dict):
            errors.append(f"{context}:{control}/{part_name}:state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"{context}:{control}/{part_name}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(f"{context}:{control}/{part_name}:{role} no <state> matching {attrs}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"{context}:{control}/{part_name}:{role} state has no rect/line")
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"{context}:{control}/{part_name}:{role} element is <{drawing.tag}>, "
                f"expected <{expected_element}>"
            )
        tokens = state_decl.get("tokens", {})
        if isinstance(tokens, dict):
            for token_key, expected in tokens.items():
                actual = drawing.get(token_key)
                if actual != expected:
                    errors.append(
                        f"{context}:{control}/{part_name}:{role} token drift: {token_key} is "
                        f"{actual!r}, expected {expected!r}"
                    )


def _validate_listheader(root: ET.Element, block: Any, errors: list[str]) -> None:
    if not isinstance(block, dict):
        errors.append("registry:listheader_part:object required")
        return
    control = block.get("control")
    if not isinstance(control, str):
        errors.append("listheader_part:control:must be a string")
        return
    if root.find(control) is None:
        errors.append(f"listheader_part:control:<{control}> missing in definition.xml")
        return
    _validate_part("listheader_part:button", root, control, block.get("button"), errors)
    _validate_part("listheader_part:arrow", root, control, block.get("arrow"), errors)


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
def _validate_style_pipe(pipe: Any, contents: Mapping[str, str], errors: list[str]) -> None:
    if not isinstance(pipe, dict):
        errors.append("registry:style_pipe:object required")
        return
    source_path = pipe.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"style_pipe:source {source_path} missing")
        return
    code = _normalized_code(source)
    unconditional = pipe.get("unconditional_markers")
    if not isinstance(unconditional, list) or not unconditional:
        errors.append("style_pipe:unconditional_markers:non-empty array required")
    else:
        for marker in unconditional:
            if isinstance(marker, str) and _collapse_ws(marker) not in code:
                errors.append(f"style_pipe:unconditional marker missing ({marker})")
    for marker in pipe.get("guarded_markers", []) or []:
        if isinstance(marker, str) and _collapse_ws(marker) not in code:
            errors.append(f"style_pipe:guarded marker missing ({marker})")


def _validate_surface(surface: Any, contents: Mapping[str, str], errors: list[str]) -> str | None:
    if not isinstance(surface, dict):
        errors.append("surfaces:object required")
        return None
    surface_id = surface.get("surface_id")
    if not isinstance(surface_id, str) or not surface_id:
        errors.append("surfaces:surface_id:non-empty string required")
        return None
    context = f"surface[{surface_id}]"
    status = surface.get("status")
    if status not in ALLOWED_SURFACE_STATUS:
        errors.append(f"{context}:status:must be one of {sorted(ALLOWED_SURFACE_STATUS)}")
    sources = surface.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{context}:sources:non-empty array required")
        return surface_id

    for entry in sources:
        if not isinstance(entry, dict):
            errors.append(f"{context}:source entry must be object")
            continue
        source_path = entry.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"{context}:source {source_path} missing")
            continue
        code = _normalized_code(source)

        if status == "compiled":
            markers = entry.get("markers")
            if not isinstance(markers, list) or not markers:
                errors.append(f"{context}:{source_path}:compiled surface needs markers")
            else:
                for marker in markers:
                    if isinstance(marker, str) and _collapse_ws(marker) not in code:
                        errors.append(f"{context}:{source_path}:positive marker missing ({marker})")

        elif status == "not_yet_material":
            # The NEGATIVE proof: the not-Material call sites must stay present. If they
            # disappear (rewired onto the Material StyleSettings pipe), this fails closed
            # until the registry status is flipped to 'compiled' in the SAME change.
            negatives = entry.get("not_material_markers")
            if not isinstance(negatives, list) or not negatives:
                errors.append(
                    f"{context}:{source_path}:not_yet_material surface needs not_material_markers"
                )
            else:
                for marker in negatives:
                    if isinstance(marker, str) and _collapse_ws(marker) not in code:
                        errors.append(
                            f"{context}:{source_path}:not_material_marker gone ({marker}); the "
                            "surface appears rewired onto the Material pipe -- flip status to "
                            "'compiled' in the SAME change"
                        )
            for marker in entry.get("absent_markers", []) or []:
                if isinstance(marker, str) and _collapse_ws(marker) in code:
                    errors.append(
                        f"{context}:{source_path}:absent_marker now PRESENT ({marker}); the "
                        "surface appears rewired onto the Material pipe -- flip status to "
                        "'compiled' in the SAME change"
                    )
    return surface_id


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-data-grid-header-selection":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("status") != "partial":
        errors.append("registry:status:must be 'partial' (dbaccess compiled; Calc selection not)")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    root = _parse_definition(contents.get(DEFINITION_PATH), errors)
    if root is not None:
        _validate_listheader(root, registry.get("listheader_part"), errors)
        _validate_style_slots(root, registry.get("style_slots"), errors)

    _validate_style_pipe(registry.get("style_pipe"), contents, errors)

    surfaces = registry.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("registry:surfaces:non-empty array required")
        surfaces = []
    seen_ids: set[str] = set()
    for surface in surfaces:
        surface_id = _validate_surface(surface, contents, errors)
        if surface_id is not None:
            if surface_id in seen_ids:
                errors.append(f"surface[{surface_id}]:duplicate surface_id")
            seen_ids.add(surface_id)
    missing = REQUIRED_SURFACE_IDS - seen_ids
    if missing:
        errors.append(f"registry:surfaces:missing required {', '.join(sorted(missing))}")

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
        print(f"Data-grid header/selection contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    surfaces = registry.get("surfaces", [])
    compiled = sum(1 for s in surfaces if isinstance(s, dict) and s.get("status") == "compiled")
    pending = sum(
        1 for s in surfaces if isinstance(s, dict) and s.get("status") == "not_yet_material"
    )
    print(
        "Data-grid header/selection contract passed: definition.xml <listheader> Button/Arrow "
        "and <style> highlight/alt-row/face slots, the FileDefinitionWidgetDraw StyleSettings "
        f"pipe, and {compiled} compiled + {pending} not-yet-material surface(s) are intact "
        "(Calc selected-header fill + active-cell ring still on the CALCCELLFOCUS ColorConfig "
        "pipe, pinned as negative markers)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
