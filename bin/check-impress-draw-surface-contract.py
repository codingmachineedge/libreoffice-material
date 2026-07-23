#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material Impress/Draw shell surfaces.

``qa/windows-ui-contract/impress-draw-surfaces.json`` registers the Impress/Draw
shell surfaces from docs/design/11-impress-draw.md §11.1-§11.3 -- the tool rail, the
Fill/Line property panel, the status bar, the Position-and-Size and Shadow object
property panels (shared weld sidebars), the graphic/text object bars, the Impress
presentation-shell composition (slide panel / center canvas pane / Layouts panel)
and its status model, the guarded Draw canvas-grid dot color, and the guarded Draw
selection/marquee/guide overlay color -- and this checker cross-validates each
declaration against the real tree:

* ``definition_parts`` -- every declared (control, part) must exist in
  vcl/uiconfig/theme_definitions/material/definition.xml, its ``<part>`` sizing
  attributes must match, and every declared ``<state>`` must exist with the exact
  fill / stroke / radius / stroke-width tokens. A renamed part, dropped state, or
  changed token (token drift) fails closed.
* ``token_consumption`` -- the declared owner source must include the token
  accessor header and contain each marker in *code* (comments are stripped first),
  so comment-only wiring cannot satisfy the contract. An optional ``ordering`` block
  additionally pins that a guarded Material color branch is sequenced to LOSE to the
  resolved high-contrast check: the declared high-contrast marker must be present on
  the consuming function's path and the Material branch must be wired as the exact
  ``contiguous`` HC-losing statement (an ``else if`` of the high-contrast ``if``, or a
  high-contrast short-circuit that runs before the token resolution). This is a
  scoped heuristic, not full control-flow proof.
* ``status_model`` -- the status text resource must be defined with the expected
  copy, and the composing source must carry each code marker.
* ``disabled_policy`` -- the declared method body must set every listed control
  both ``set_visible(true)`` and ``set_sensitive(false)`` (visible-but-disabled,
  no layout jump). A missing control or missing method fails closed.

The registry establishes source-complete migration scope; it never claims a
native build or runtime evidence (``runtime_verified: false`` throughout).
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/impress-draw-surfaces.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

REQUIRED_SURFACE_IDS = {
    "draw.tool-rail", "draw.property-panel", "draw.status-bar",
    "impress.object-property-panel.possize", "impress.object-property-panel.shadow",
    "impress.object-bars", "impress.pane-composition", "impress.status-bar",
    "draw.canvas-grid", "draw.selection-overlay-guide-color",
}

# definition.xml <state> attribute keys, so declared attrs are validated as a
# complete, exact signature (no partial match that could alias two states).
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
    """Collapse every run of whitespace to a single space so a contiguous
    statement can be matched regardless of indentation or line wrapping."""
    return re.sub(r"\s+", " ", source).strip()


def _function_body(source: str, signature: str) -> str | None:
    start = source.find(signature)
    if start < 0:
        return None
    opening = source.find("{", start + len(signature))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    return None


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for surface in registry.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        for owner in surface.get("owner_sources", []):
            if isinstance(owner, str):
                paths.add(owner)
        status_model = surface.get("status_model")
        if isinstance(status_model, dict):
            for key in ("source", "resource_file"):
                value = status_model.get(key)
                if isinstance(value, str):
                    paths.add(value)
        for consumption in surface.get("token_consumption", []) or []:
            if isinstance(consumption, dict) and isinstance(consumption.get("source"), str):
                paths.add(consumption["source"])
        for policy in surface.get("disabled_policy", []) or []:
            if isinstance(policy, dict) and isinstance(policy.get("source"), str):
                paths.add(policy["source"])
        for owner_marker in surface.get("owner_markers", []) or []:
            if isinstance(owner_marker, dict) and isinstance(owner_marker.get("source"), str):
                paths.add(owner_marker["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _parse_definition(text: str, errors: list[str]) -> ET.Element | None:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"definition:xml:{error}")
        return None


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


def _validate_definition_part(
    context: str, root: ET.Element, declaration: Mapping[str, Any], errors: list[str]
) -> None:
    control = declaration.get("control")
    part_name = declaration.get("part")
    if not isinstance(control, str) or not isinstance(part_name, str):
        errors.append(f"{context}:definition-part:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"{context}:definition-part:{control}/{part_name} missing in definition.xml")
        return

    part_attrs = declaration.get("part_attrs")
    if isinstance(part_attrs, dict):
        for key, expected in part_attrs.items():
            if part.get(key) != expected:
                errors.append(
                    f"{context}:definition-part:{control}/{part_name} attribute {key} "
                    f"is {part.get(key)!r}, expected {expected!r}"
                )

    for state_decl in declaration.get("states", []):
        if not isinstance(state_decl, dict):
            errors.append(f"{context}:definition-part:{control}/{part_name} state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"{context}:definition-part:{control}/{part_name}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(
                f"{context}:definition-part:{control}/{part_name}:{role} no <state> matching {attrs}"
            )
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(
                f"{context}:definition-part:{control}/{part_name}:{role} state has no rect/line"
            )
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"{context}:definition-part:{control}/{part_name}:{role} element is "
                f"<{drawing.tag}>, expected <{expected_element}>"
            )
        tokens = state_decl.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append(f"{context}:definition-part:{control}/{part_name}:{role} tokens must be object")
            continue
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"{context}:definition-part:{control}/{part_name}:{role} token drift: "
                    f"{token_key} is {actual!r}, expected {expected!r}"
                )


def _validate_status_model(
    context: str, model: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = model.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:status-model:source {source_path} missing")
    resource = model.get("resource")
    resource_file = model.get("resource_file")
    resource_text = contents.get(resource_file) if isinstance(resource_file, str) else None
    if resource_text is None:
        errors.append(f"{context}:status-model:resource_file {resource_file} missing")
    elif isinstance(resource, str):
        define = re.search(
            rf'#define\s+{re.escape(resource)}\b.*?NC_\("{re.escape(resource)}",\s*"([^"]*)"',
            resource_text,
            re.DOTALL,
        )
        if define is None:
            errors.append(f"{context}:status-model:{resource} not defined in {resource_file}")
        else:
            wanted = model.get("resource_text_contains")
            if isinstance(wanted, str) and wanted not in define.group(1):
                errors.append(
                    f"{context}:status-model:{resource} copy {define.group(1)!r} lacks {wanted!r}"
                )
    if source is not None:
        code = _without_cpp_comments(source)
        for marker in model.get("markers", []):
            if isinstance(marker, str) and marker not in code:
                errors.append(f"{context}:status-model:marker missing in code ({marker})")


def _validate_token_ordering(
    context: str, source: str, ordering: Mapping[str, Any], errors: list[str]
) -> None:
    """Stronger-than-presence check that a guarded Material color branch is
    sequenced to LOSE to the resolved high-contrast check (chapter 11's rule that
    high contrast bypasses Material drawing entirely).

    The generic marker validator above only proves a marker exists *somewhere* in
    the comment-stripped file; it cannot prove branch ordering. This scopes to the
    consuming function body and requires (a) the high-contrast marker to be present
    on that path and (b) the Material branch to be wired as the exact declared
    ``contiguous`` statement -- for the overlay this is the ``else if`` bound to the
    high-contrast ``if``; for the grid this is the ``if (... GetHighContrastMode())
    return std::nullopt;`` short-circuit that runs before the token resolution. It
    remains a heuristic: it proves the HC-losing statement is written as declared
    inside the function, not full control-flow dominance -- a dedicated ordering
    mutation test guards it, and code review remains the backstop.
    """
    function = ordering.get("function")
    if not isinstance(function, str):
        errors.append(f"{context}:token-ordering:function must be a string")
        return
    body = _function_body(_without_cpp_comments(source), function + "(")
    if body is None:
        errors.append(f"{context}:token-ordering:function {function} not found")
        return
    collapsed = _collapse_ws(body)
    high_contrast = ordering.get("high_contrast_marker")
    if isinstance(high_contrast, str) and _collapse_ws(high_contrast) not in collapsed:
        errors.append(
            f"{context}:token-ordering:high-contrast marker missing in {function} ({high_contrast})"
        )
    contiguous = ordering.get("contiguous")
    if isinstance(contiguous, str) and _collapse_ws(contiguous) not in collapsed:
        errors.append(
            f"{context}:token-ordering:guard structure not contiguous in {function} "
            f"({contiguous}); the Material branch must be sequenced to lose to high contrast"
        )


def _validate_token_consumption(
    context: str, consumption: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = consumption.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:token-consumption:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    include = consumption.get("include")
    if isinstance(include, str) and f"#include {include}" not in code:
        errors.append(f"{context}:token-consumption:missing #include {include}")
    for marker in consumption.get("markers", []):
        if isinstance(marker, str) and marker not in code:
            errors.append(f"{context}:token-consumption:marker missing in code ({marker})")
    ordering = consumption.get("ordering")
    if isinstance(ordering, dict):
        _validate_token_ordering(context, source, ordering, errors)


def _validate_disabled_policy(
    context: str, policy: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = policy.get("source")
    method = policy.get("method")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:disabled-policy:source {source_path} missing")
        return
    if not isinstance(method, str):
        errors.append(f"{context}:disabled-policy:method must be a string")
        return
    body = _function_body(_without_cpp_comments(source), method + "(")
    if body is None:
        errors.append(f"{context}:disabled-policy:method {method} not found")
        return
    for control in policy.get("controls", []):
        if not isinstance(control, str):
            continue
        if f"{control}->set_visible(true)" not in body:
            errors.append(f"{context}:disabled-policy:{control} not kept visible (no layout jump)")
        if f"{control}->set_sensitive(false)" not in body:
            errors.append(f"{context}:disabled-policy:{control} not disabled")


def _validate_owner_markers(
    context: str, owner_marker: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = owner_marker.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:owner-marker:source {source_path} missing")
        return
    is_cpp = source_path.endswith((".cxx", ".hxx", ".c", ".h"))
    haystack = _without_cpp_comments(source) if is_cpp else source
    for marker in owner_marker.get("markers", []):
        if isinstance(marker, str) and marker not in haystack:
            errors.append(f"{context}:owner-marker:{marker} missing in {source_path}")


def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-impress-draw-surfaces":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")

    surfaces = registry.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("registry:surfaces:non-empty array required")
        surfaces = []
    if registry.get("expected_surfaces") != len(surfaces):
        errors.append("registry:expected_surfaces:count drift")

    root = _parse_definition(contents.get(DEFINITION_PATH, ""), errors)

    seen_ids: set[str] = set()
    for index, surface in enumerate(surfaces):
        context = f"surfaces[{index}]"
        if not isinstance(surface, dict):
            errors.append(f"{context}:object required")
            continue
        surface_id = surface.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"{context}:surface_id:non-empty string required")
            continue
        context = f"surface[{surface_id}]"
        if surface_id in seen_ids:
            errors.append(f"{context}:surface_id:duplicate")
        seen_ids.add(surface_id)

        if surface.get("status") != "source-declared":
            errors.append(f"{context}:status:must be source-declared")
        if not isinstance(surface.get("runtime_verified"), bool):
            errors.append(f"{context}:runtime_verified:boolean required")
        elif surface["runtime_verified"]:
            errors.append(f"{context}:runtime_verified:no runtime evidence exists; must be false")

        for owner in surface.get("owner_sources", []):
            if isinstance(owner, str) and owner not in contents:
                errors.append(f"{context}:owner_source:missing {owner}")

        for owner_marker in surface.get("owner_markers", []) or []:
            if isinstance(owner_marker, dict):
                _validate_owner_markers(context, owner_marker, contents, errors)

        if root is not None:
            for declaration in surface.get("definition_parts", []):
                if isinstance(declaration, dict):
                    _validate_definition_part(context, root, declaration, errors)

        status_model = surface.get("status_model")
        if isinstance(status_model, dict):
            _validate_status_model(context, status_model, contents, errors)

        for consumption in surface.get("token_consumption", []) or []:
            if isinstance(consumption, dict):
                _validate_token_consumption(context, consumption, contents, errors)

        for policy in surface.get("disabled_policy", []) or []:
            if isinstance(policy, dict):
                _validate_disabled_policy(context, policy, contents, errors)

    missing_required = REQUIRED_SURFACE_IDS - seen_ids
    if missing_required:
        errors.append(f"registry:surfaces:missing required {', '.join(sorted(missing_required))}")

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents)
    if errors:
        raise ValidationError("\n".join(errors))


def main() -> int:
    try:
        validate_repository()
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Impress/Draw surface contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository()
    print(
        "Impress/Draw surface contract passed: "
        f"{len(registry['surfaces'])} Draw shell surface(s) with definition-part token, "
        "status-model, token-consumption and no-selection-policy fidelity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
