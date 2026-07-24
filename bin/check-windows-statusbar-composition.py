#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material framework status bar (WIN-NAV-008).

``qa/windows-ui-contract/statusbar-composition.json`` pins the composition of the
native 28px Material status band from docs/design/05-navigation.md section 8 -- the
band fill / top rule, the interactive-field hover tokens, the zoom slider, and the
accessible-value-change rule -- and this checker cross-validates every declaration
against the real tree:

* ``band`` -- the ``faceColor`` style slot in definition.xml must still map to
  ``@surface-container`` (the band fill), the declared metric / palette tokens must
  exist with the exact values (in *both* the light and dark palettes for colors),
  and the owning source vcl/source/window/status.cxx must include the token accessor
  and carry each Material-guard marker in *code* (comments are stripped first, so
  comment-only wiring cannot satisfy the contract). ``band.height`` additionally
  pins that status.cxx *consumes* the fixed 28px ``size-compact-control`` band
  height (``CalcWindowSizePixel`` floored via ``lcl_materialStatusMetric`` ->
  ``MaterialTokens::findMetric``): the source marker must name the pinned metric and
  survive comment stripping, so a dropped or commented-out floor fails closed;
* ``field_hover`` -- the hover wash color and ``corner-small`` radius the spec
  depends on must exist in definition.xml. The hover slot is honestly ``specified``
  (spec-only, not a native part), so no part wiring is claimed for it;
* ``zoom_slider`` -- every declared ``slider`` part / state must exist in
  definition.xml with the exact sizing attributes and fill / stroke / radius /
  stroke-width tokens. A renamed part, dropped state, or token drift fails closed;
* ``accessibility`` -- the generic status controller must expose owner-drawn status
  updates as accessible value changes (guarded by the Material theme flag and routed
  through the item's *accessible name* -- ``SetAccessibleName`` fires
  ``StatusbarNameChanged`` without recomputing the item width or issuing a second
  synchronous paint, unlike ``SetItemText``) while *retaining* the existing
  ``repaint()`` path. The guard helper must appear both defined and invoked in code,
  and the value-change call must be bound *directly* to the guard as a contiguous
  ``if ( guard() ) call;`` statement (whitespace-normalized, comments stripped) sitting
  on the owner-draw path, so an empty guard body, an unguarded call, or comment-only
  wiring all fail closed.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, status-band pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/statusbar-composition.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# definition.xml <state> attribute keys, so a declared attrs signature is validated
# as a complete, exact match (no partial match that could alias two states).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)

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


def _collapse_ws(source: str) -> str:
    """Collapse every run of whitespace to a single space so a contiguous
    statement can be matched regardless of indentation or line wrapping."""
    return re.sub(r"\s+", " ", source).strip()


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    band = registry.get("band")
    if isinstance(band, dict) and isinstance(band.get("owner"), dict):
        source = band["owner"].get("source")
        if isinstance(source, str):
            paths.add(source)
    accessibility = registry.get("accessibility")
    if isinstance(accessibility, dict) and isinstance(accessibility.get("source"), str):
        paths.add(accessibility["source"])
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


def _radius_value(root: ET.Element, name: str) -> str | None:
    return _named_value(root, "shapes", "radius", name)


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


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_tokens(root: ET.Element, band: Mapping[str, Any], errors: list[str]) -> None:
    face = band.get("face_color_slot")
    if isinstance(face, dict):
        slot = face.get("slot")
        token = face.get("token")
        actual = _style_slot_value(root, slot) if isinstance(slot, str) else None
        if actual != token:
            errors.append(
                f"band:face-color-slot:<style><{slot}> is {actual!r}, expected {token!r} "
                "(the status band renders from the faceColor -> @surface-container slot)"
            )

    top_rule = band.get("top_rule")
    if isinstance(top_rule, dict):
        rule_token = top_rule.get("token")
        if isinstance(rule_token, str) and _palette_color(root, "", rule_token) is None:
            errors.append(f"band:top-rule:@{rule_token} missing from the light palette")
        stroke = top_rule.get("stroke_width")
        if isinstance(stroke, str) and _metric_value(root, stroke) is None:
            errors.append(f"band:top-rule:stroke-width metric {stroke!r} missing")

    for metric in band.get("metrics", []) or []:
        if not isinstance(metric, dict):
            continue
        name = metric.get("name")
        expected = metric.get("value")
        actual = _metric_value(root, name) if isinstance(name, str) else None
        if actual is None:
            errors.append(f"band:metric:{name} missing in definition.xml <metrics>")
        elif actual != expected:
            errors.append(f"band:metric:{name} is {actual!r}, expected {expected!r} (metric drift)")

    for role in band.get("palette_colors", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"band:palette:@{role} missing from the {label} palette")


def _validate_field_hover(root: ET.Element, hover: Mapping[str, Any], errors: list[str]) -> None:
    # Honest guard: field hover is spec-only, so it must NOT be promoted to a
    # runtime claim here. It only grounds the tokens the spec references.
    if hover.get("status") != "specified":
        errors.append(
            "field_hover:status:must stay 'specified' (the hover wash is spec-only, "
            "not a native part -- see docs/design/05-navigation.md 8.1/8.2)"
        )
    wash = hover.get("wash_color")
    if isinstance(wash, str) and _palette_color(root, "", wash) is None:
        errors.append(f"field_hover:wash-color:@{wash} missing from the light palette")
    radius = hover.get("radius")
    if isinstance(radius, dict):
        name = radius.get("name")
        expected = radius.get("value")
        actual = _radius_value(root, name) if isinstance(name, str) else None
        if actual is None:
            errors.append(f"field_hover:radius:{name} missing in definition.xml <shapes>")
        elif actual != expected:
            errors.append(f"field_hover:radius:{name} is {actual!r}, expected {expected!r}")


def _validate_zoom_slider(root: ET.Element, slider: Mapping[str, Any], errors: list[str]) -> None:
    control = slider.get("control")
    if not isinstance(control, str):
        errors.append("zoom_slider:control:must be a string")
        return
    parts = slider.get("parts")
    if not isinstance(parts, list) or not parts:
        errors.append("zoom_slider:parts:non-empty array required")
        return
    for declaration in parts:
        if not isinstance(declaration, dict):
            errors.append("zoom_slider:part:object required")
            continue
        part_name = declaration.get("part")
        if not isinstance(part_name, str):
            errors.append("zoom_slider:part:name must be a string")
            continue
        part = _find_part(root, control, part_name)
        if part is None:
            errors.append(f"zoom_slider:{control}/{part_name} missing in definition.xml")
            continue
        part_attrs = declaration.get("part_attrs")
        if isinstance(part_attrs, dict):
            for key, expected in part_attrs.items():
                if part.get(key) != expected:
                    errors.append(
                        f"zoom_slider:{control}/{part_name} attribute {key} is "
                        f"{part.get(key)!r}, expected {expected!r}"
                    )
        for state_decl in declaration.get("states", []) or []:
            if not isinstance(state_decl, dict):
                errors.append(f"zoom_slider:{control}/{part_name} state must be object")
                continue
            role = state_decl.get("role", "?")
            attrs = state_decl.get("attrs", {})
            if not isinstance(attrs, dict):
                errors.append(f"zoom_slider:{control}/{part_name}:{role} attrs must be object")
                continue
            state = _match_state(part, attrs)
            if state is None:
                errors.append(
                    f"zoom_slider:{control}/{part_name}:{role} no <state> matching {attrs}"
                )
                continue
            drawing = _first_drawing_child(state)
            if drawing is None:
                errors.append(f"zoom_slider:{control}/{part_name}:{role} state has no rect/line")
                continue
            expected_element = state_decl.get("element")
            if isinstance(expected_element, str) and drawing.tag != expected_element:
                errors.append(
                    f"zoom_slider:{control}/{part_name}:{role} element is <{drawing.tag}>, "
                    f"expected <{expected_element}>"
                )
            tokens = state_decl.get("tokens", {})
            if not isinstance(tokens, dict):
                errors.append(f"zoom_slider:{control}/{part_name}:{role} tokens must be object")
                continue
            for token_key, expected in tokens.items():
                actual = drawing.get(token_key)
                if actual != expected:
                    errors.append(
                        f"zoom_slider:{control}/{part_name}:{role} token drift: {token_key} is "
                        f"{actual!r}, expected {expected!r}"
                    )


def _validate_band_owner(
    band: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    owner = band.get("owner")
    if not isinstance(owner, dict):
        errors.append("band:owner:object required")
        return
    source_path = owner.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"band:owner:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    include = owner.get("include")
    if isinstance(include, str) and f"#include {include}" not in code:
        errors.append(f"band:owner:missing #include {include}")
    for marker in owner.get("markers", []) or []:
        if isinstance(marker, str) and marker not in code:
            errors.append(f"band:owner:marker missing in code ({marker})")


def _validate_band_height(
    band: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    """The 28px band height must be *consumed* by the owner source, not merely
    declared in definition.xml. status.cxx floors CalcWindowSizePixel() to the
    ``size-compact-control`` metric via ``lcl_materialStatusMetric``; this pins
    that consumption. The source marker must name the same metric the band height
    pins (a drift-lock), and it must survive comment stripping so commented-out
    wiring fails closed -- exactly like the band-fill / top-rule markers."""
    height = band.get("height")
    if not isinstance(height, dict):
        errors.append("band:height:object required")
        return
    metric = height.get("metric")
    marker = height.get("source_marker")
    if not isinstance(metric, str) or not isinstance(marker, str):
        errors.append("band:height:metric and source_marker must be strings")
        return
    if metric not in marker:
        errors.append(
            f"band:height:source_marker {marker!r} must reference the height metric {metric!r}"
        )
    owner = band.get("owner")
    source_path = owner.get("source") if isinstance(owner, dict) else None
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"band:height:owner source {source_path!r} missing")
        return
    code = _without_cpp_comments(source)
    if marker not in code:
        errors.append(
            f"band:height:owner must consume the fixed 28px band height "
            f"({marker} missing from code; comment-only wiring fails closed)"
        )


def _validate_accessibility(
    accessibility: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = accessibility.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"accessibility:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    for marker in accessibility.get("markers", []) or []:
        if isinstance(marker, str) and marker not in code:
            errors.append(f"accessibility:marker missing in code ({marker})")
    # The guard helper must be both defined AND invoked in code: a lone definition
    # (call site commented out) leaves exactly one occurrence, so require >= 2.
    guard = accessibility.get("guard_marker")
    if isinstance(guard, str) and code.count(guard) < 2:
        errors.append(
            f"accessibility:guard {guard!r} must be both defined and invoked in code "
            "(the accessible value-change call must not be comment-only)"
        )
    # Bind the guard to its effect: the accessible value-change call must be the body
    # of the guard, expressed as a contiguous `if ( guard() ) call;` statement. This
    # is stronger than the whole-file markers above (which only prove the tokens exist
    # *somewhere*): an empty guard body, a guard gating an unrelated statement, or an
    # ungated value-change call all leave the markers/guard-count intact but fail here.
    guarded_call = accessibility.get("guarded_call")
    if isinstance(guarded_call, dict):
        collapsed = _collapse_ws(code)
        call_guard = guarded_call.get("guard")
        call_expr = guarded_call.get("call")
        if isinstance(call_guard, str) and isinstance(call_expr, str):
            statement = _collapse_ws(f"if ( {call_guard}() ) {call_expr};")
            if statement not in collapsed:
                errors.append(
                    "accessibility:guarded-call:the accessible value-change call must be "
                    f"gated directly by the theme guard as a contiguous statement "
                    f"({statement!r} not found; an empty or unrelated guard body fails closed)"
                )
            else:
                # And that guarded statement must live on the owner-draw path, i.e.
                # after the non-owner-draw split, never on the plain-text branch.
                anchor = guarded_call.get("within_branch_after")
                if isinstance(anchor, str):
                    anchor_c = _collapse_ws(anchor)
                    anchor_idx = collapsed.find(anchor_c)
                    if anchor_idx == -1 or collapsed.find(statement) < anchor_idx:
                        errors.append(
                            "accessibility:guarded-call:the guarded value-change call must sit "
                            f"on the owner-draw path (after {anchor!r})"
                        )
    # The existing bare-repaint path must be retained (the a11y change is additive).
    for retained in accessibility.get("must_retain", []) or []:
        if isinstance(retained, str) and retained not in code:
            errors.append(f"accessibility:must-retain marker dropped ({retained})")


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-statusbar-composition":
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

    band = registry.get("band")
    if not isinstance(band, dict):
        errors.append("registry:band:object required")
        band = {}
    field_hover = registry.get("field_hover")
    if not isinstance(field_hover, dict):
        errors.append("registry:field_hover:object required")
        field_hover = {}
    zoom_slider = registry.get("zoom_slider")
    if not isinstance(zoom_slider, dict):
        errors.append("registry:zoom_slider:object required")
        zoom_slider = {}
    accessibility = registry.get("accessibility")
    if not isinstance(accessibility, dict):
        errors.append("registry:accessibility:object required")
        accessibility = {}

    if root is not None:
        _validate_tokens(root, band, errors)
        _validate_field_hover(root, field_hover, errors)
        _validate_zoom_slider(root, zoom_slider, errors)

    _validate_band_owner(band, contents, errors)
    _validate_band_height(band, contents, errors)
    _validate_accessibility(accessibility, contents, errors)

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
        print(f"Material status-bar composition contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material status-bar composition contract passed: faceColor -> @surface-container "
        "band slot, @outline-variant top rule, spec-grounded field-hover tokens, the "
        "zoom-slider part wiring, and the guarded accessible-value-change path are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
