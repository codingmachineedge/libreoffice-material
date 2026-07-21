#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material Calc formula bar (ScInputWindow).

``qa/windows-ui-contract/calc-formula-bar.json`` registers the Calc formula-bar
surface (WIN-CA-002) from docs/design/10-writer-calc.md 10.3 (formula bar row)
and 10.4 (RTL order swap). The formula row is a ToolBox composing the Name Box
(ScPosWnd combobox), the fx Function-Wizard / Sum items and the formula-input
window (ScTextWnd editbox). This checker cross-validates what ``ScInputWindow`` /
``ScTextWnd`` own natively and additively against the real tree:

* ``definition_parts`` -- the combobox / editbox / toolbar parts the Name Box,
  formula input and fx/Sum items consume their tokens from must exist in
  vcl/uiconfig/theme_definitions/material/definition.xml with the exact part
  sizing attributes and, per declared ``<state>``, the exact fill / stroke /
  radius / stroke-width tokens. A renamed part, dropped state or changed token
  (token drift) fails closed. The definition file is read only, never mutated.
* ``guarded_token_consumption`` -- the owner source must include the token
  accessor header and carry, in *code* (comments stripped first), the
  VCL_FILE_WIDGET_THEME activation guard, the high-contrast bypass guard, the
  ``vcl::MaterialTokens`` sourcing and every declared token lookup, so comment-only
  wiring cannot satisfy the contract.
* ``paint_layout`` -- the additive ``ScInputWindow::Paint`` override must call the
  base ``ToolBox::Paint`` (never replace it) and carry every layout marker, and
  the header must declare the override plus the Material members/helpers.
* ``field_token_centralization`` -- the centralized ``@surface`` field-fill and
  ``@on-surface`` text-fill accessors must each hold both the resolved token and
  the StyleSettings fallback, and every declared editbox fill site must funnel
  through the accessor (call-site floor), so the token role is consumed
  explicitly rather than via the generic slot alone and the lookup is not
  duplicated across the owner-drawn paints.
* ``rtl_order`` -- the 10.4 Name Box / formula-input order swap must be present as
  the real logical item order (Name Box leading, formula input trailing) plus the
  recorded RTL direction the additive row rule consumes, so the native-mirroring
  swap cannot silently regress.

The registry establishes source-complete migration scope; it never claims a
native build or runtime evidence (``runtime_verified: false`` throughout).
"""

from __future__ import annotations

import json
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/calc-formula-bar.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

REQUIRED_SURFACE_IDS = {"calc.formula-bar"}

# definition.xml <state> attribute keys, so declared attrs are validated as a
# complete, exact signature (no partial match that could alias two states).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)

# Registry block keys whose "source"/"header" file paths must be loaded.
_BLOCK_KEYS = (
    "guarded_token_consumption",
    "paint_layout",
    "field_token_centralization",
    "rtl_order",
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
        for key in _BLOCK_KEYS:
            block = surface.get(key)
            if isinstance(block, dict):
                for path_key in ("source", "header"):
                    value = block.get(path_key)
                    if isinstance(value, str):
                        paths.add(value)
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


def _validate_guarded_token_consumption(
    context: str, block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = block.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:token-consumption:source {source_path} missing")
        return
    code = _without_cpp_comments(source)
    include = block.get("include")
    if isinstance(include, str) and f"#include {include}" not in code:
        errors.append(f"{context}:token-consumption:missing #include {include}")
    for guard_key, label in (("env_guard", "activation"), ("high_contrast_guard", "high-contrast")):
        guard = block.get(guard_key)
        if isinstance(guard, str) and guard not in code:
            errors.append(f"{context}:token-consumption:missing {label} guard ({guard})")
    for marker in block.get("markers", []):
        if isinstance(marker, str) and marker not in code:
            errors.append(f"{context}:token-consumption:marker missing in code ({marker})")


def _validate_paint_layout(
    context: str, block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = block.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:paint-layout:source {source_path} missing")
    else:
        code = _without_cpp_comments(source)
        override = block.get("override_signature")
        base_call = block.get("base_call")
        if isinstance(override, str) and override not in code:
            errors.append(f"{context}:paint-layout:missing Paint override ({override})")
        # The override must call the base paint, never replace it.
        if isinstance(base_call, str) and base_call not in code:
            errors.append(f"{context}:paint-layout:override must call the base paint ({base_call})")
        for marker in block.get("markers", []):
            if isinstance(marker, str) and marker not in code:
                errors.append(f"{context}:paint-layout:marker missing in code ({marker})")

    header_path = block.get("header")
    header = contents.get(header_path) if isinstance(header_path, str) else None
    if header is None:
        errors.append(f"{context}:paint-layout:header {header_path} missing")
    else:
        header_code = _without_cpp_comments(header)
        for marker in block.get("header_markers", []):
            if isinstance(marker, str) and marker not in header_code:
                errors.append(f"{context}:paint-layout:header marker missing ({marker})")


def _validate_field_centralization(
    context: str, block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = block.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:field-centralization:source {source_path} missing")
        return
    code = _without_cpp_comments(source)

    for accessor in block.get("accessors", []):
        if not isinstance(accessor, dict):
            errors.append(f"{context}:field-centralization:accessor must be object")
            continue
        signature = accessor.get("signature")
        if not isinstance(signature, str):
            errors.append(f"{context}:field-centralization:accessor signature must be a string")
            continue
        body = _function_body(code, signature)
        if body is None:
            errors.append(f"{context}:field-centralization:accessor {signature!r} not found in code")
            continue
        for marker in accessor.get("must_contain", []):
            if isinstance(marker, str) and marker not in body:
                errors.append(
                    f"{context}:field-centralization:{signature!r} must contain {marker!r} "
                    "(token role and StyleSettings fallback)"
                )

    for site in block.get("call_sites", []):
        if not isinstance(site, dict):
            errors.append(f"{context}:field-centralization:call_site must be object")
            continue
        call = site.get("call")
        minimum = site.get("min")
        if not isinstance(call, str) or not isinstance(minimum, int):
            errors.append(f"{context}:field-centralization:call_site call/min invalid")
            continue
        seen = code.count(call)
        if seen < minimum:
            errors.append(
                f"{context}:field-centralization:call site {call!r} used {seen} time(s), "
                f"expected at least {minimum}; every editbox fill site must funnel through it"
            )


def _validate_rtl_order(
    context: str, block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    source_path = block.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{context}:rtl-order:source {source_path} missing")
        return
    code = _without_cpp_comments(source)

    for marker in block.get("markers", []):
        if isinstance(marker, str) and marker not in code:
            errors.append(f"{context}:rtl-order:order marker missing in code ({marker})")

    rule_fn = block.get("rule_function")
    if isinstance(rule_fn, str):
        body = _function_body(code, rule_fn)
        if body is None:
            errors.append(f"{context}:rtl-order:rule function {rule_fn!r} not found in code")
        else:
            for marker in block.get("rule_must_contain", []):
                if isinstance(marker, str) and marker not in body:
                    errors.append(
                        f"{context}:rtl-order:the additive row rule must consume {marker!r} "
                        "so the RTL direction is real, not comment-only"
                    )


def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-calc-formula-bar":
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

        if root is not None:
            declarations = surface.get("definition_parts", [])
            if not declarations:
                errors.append(f"{context}:definition_parts:non-empty array required")
            for declaration in declarations:
                if isinstance(declaration, dict):
                    _validate_definition_part(context, root, declaration, errors)

        token_block = surface.get("guarded_token_consumption")
        if isinstance(token_block, dict):
            _validate_guarded_token_consumption(context, token_block, contents, errors)
        else:
            errors.append(f"{context}:guarded_token_consumption:object required")

        paint_block = surface.get("paint_layout")
        if isinstance(paint_block, dict):
            _validate_paint_layout(context, paint_block, contents, errors)
        else:
            errors.append(f"{context}:paint_layout:object required")

        field_block = surface.get("field_token_centralization")
        if isinstance(field_block, dict):
            _validate_field_centralization(context, field_block, contents, errors)
        else:
            errors.append(f"{context}:field_token_centralization:object required")

        rtl_block = surface.get("rtl_order")
        if isinstance(rtl_block, dict):
            _validate_rtl_order(context, rtl_block, contents, errors)
        else:
            errors.append(f"{context}:rtl_order:object required")

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
        print(f"Calc formula-bar contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository()
    print(
        "Calc formula-bar contract passed: "
        f"{len(registry['surfaces'])} ScInputWindow surface(s) with combobox/editbox/toolbar "
        "token fidelity, guarded token consumption, additive Paint override, centralized "
        "@surface/@on-surface field-fill token consumption and the 10.4 RTL order swap"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
