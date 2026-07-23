#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material push-button composition (WIN-ACT-001).

``qa/windows-ui-contract/pushbutton-contract.json`` pins the three push-button variants that are
actually compiled in definition.xml today (tonal/plain, filled ``extra="action"``, text
``extra="flat"``) from docs/design/02-actions.md 1, and records the two open gaps (outlined
variant, default-button emphasis) as honest ``specified``, build-blocked carve-outs -- never as an
implemented claim. This checker parses the real tree fail-closed:

* ``compiled`` -- the ``pushbutton``/``Entire`` part must carry exactly the 13 pinned ``<state>``
  tuples (tonal x5, action x4, flat x4 -- two flat states intentionally empty) with their exact
  fill/stroke/stroke-width/radius tokens, the shared 4-line ``pushbutton``/``Focus`` ring
  (``@primary``, ``stroke-standard``, inset ``0.04-0.96``) every variant reuses, the D-020
  ``<style>`` default-slot pairing (``defaultActionButtonTextColor`` == ``actionButtonTextColor``,
  ``defaultButtonTextColor`` == ``buttonTextColor``) so the deferred default-emphasis decision
  cannot silently drift, every declared metric value, and every referenced palette role in *both*
  palettes. A renamed part, dropped/added/reordered state, or token drift fails closed.
  definition.xml is read-only.
* ``gallery_cardinality`` -- the ``pushbutton`` cell count in component-gallery-coverage.json
  (13 Entire + 1 Focus) must equal the compiled state count, so a partial/orphaned addition is
  caught by a cardinality mismatch.
* ``negative_guard`` (TEMPORARY) -- ``extra="outlined"`` must NOT appear in the ``<pushbutton>``
  block, and the ``ControlType::Pushbutton`` case of ``WidgetDefinitionPart::getStates``
  (vcl/source/gdi/WidgetDefinition.cxx) must still resolve ``sExtra`` only from ``mbIsAction`` /
  ``m_bFlatButton`` with no ``outlined`` token. This fails closed the instant outlined XML is added
  without the matching native signal, and MUST be inverted the day the real signal lands.
* ``target`` -- ``outlined`` and ``default_emphasis`` must stay ``status: "specified"``,
  ``runtime_verified: false``, and each carry a non-empty ``blocked_on`` citation, so neither can
  flip to an implemented claim without real source.
* ``design_anchors`` -- the owning design chapter (02-actions.md) must still carry the pinned
  future-work / D-020 anchor text, so registry and chapter cannot silently diverge.

It is source/composition evidence only: ``runtime_verified`` is false throughout -- no native build,
button pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/pushbutton-contract.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# definition.xml <state> attribute keys, matched as a complete exact signature (no partial alias).
STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected", "button-value", "extra",
)
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for key in ("native_signal_source", "gallery_registry", "design_source"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals."""

    out: list[str] = []
    i, n = 0, len(text)
    state = "code"
    quote = ""
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if c in ('"', "'"):
                state = "quote"
                quote = c
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        if state == "line":
            if c == "\n":
                state = "code"
                out.append(c)
            i += 1
            continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
            if c == "\n":
                out.append("\n")
            i += 1
            continue
        out.append(c)
        if c == "\\":
            if i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue
        if c == quote:
            state = "code"
        i += 1
    return "".join(out)


def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
        return None


# --------------------------------------------------------------------------------------------------
# definition.xml lookups
# --------------------------------------------------------------------------------------------------
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


def _check_tokens(context: str, drawing: ET.Element, tokens: Mapping[str, Any], errors: list[str]) -> None:
    for token_key, expected in tokens.items():
        actual = drawing.get(token_key)
        if actual != expected:
            errors.append(
                f"{context} token drift: {token_key} is {actual!r}, expected {expected!r}"
            )


def _validate_compiled(root: ET.Element, compiled: Mapping[str, Any], errors: list[str]) -> None:
    control = compiled.get("control")
    entire = compiled.get("entire_part")
    if not (isinstance(control, str) and isinstance(entire, str)):
        errors.append("compiled:control/entire_part must be strings")
        return
    part = _find_part(root, control, entire)
    if part is None:
        errors.append(f"compiled:{control}/{entire} missing in definition.xml")
        return

    states = compiled.get("states")
    if not isinstance(states, list) or not states:
        errors.append("compiled:states:non-empty array required")
        return

    # Exact cardinality: the compiled Entire part must carry exactly the pinned state count, so a
    # silently added/dropped state is caught even if every pinned state still matches.
    actual_states = part.findall("state")
    if len(actual_states) != len(states):
        errors.append(
            f"compiled:states:the {control}/{entire} part has {len(actual_states)} <state> "
            f"tuples but {len(states)} are pinned (a state was added or removed)"
        )

    for decl in states:
        if not isinstance(decl, dict):
            errors.append("compiled:states:entry must be object")
            continue
        role = decl.get("role", "?")
        attrs = decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"compiled:state:{role}:attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(f"compiled:state:{role}:no <state> matching {attrs}")
            continue
        drawing = _first_drawing_child(state)
        if decl.get("element") == "empty":
            if drawing is not None:
                errors.append(
                    f"compiled:state:{role}:pinned empty (no drawing) but found <{drawing.tag}> "
                    "(the text/flat idle/disabled state gained a container)"
                )
            continue
        if drawing is None:
            errors.append(f"compiled:state:{role}:state has no rect/line")
            continue
        expected_element = decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"compiled:state:{role}:element is <{drawing.tag}>, expected <{expected_element}>"
            )
        _check_tokens(f"compiled:state:{role}", drawing, decl.get("tokens", {}), errors)

    _validate_focus(root, control, compiled.get("focus_part"), errors)
    _validate_style_slots(root, compiled.get("style_slots"), errors)

    for metric in compiled.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("compiled:metric:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("compiled:metric:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"compiled:metric:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(
                f"compiled:metric:{mname} is {actual!r}, expected {expected!r} (metric drift)"
            )

    for role in compiled.get("palette_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"compiled:palette:@{role} missing from the {label} palette")


def _validate_focus(root: ET.Element, control: str, focus: Any, errors: list[str]) -> None:
    if not isinstance(focus, dict):
        errors.append("compiled:focus_part:object required")
        return
    part_name = focus.get("part")
    if not isinstance(part_name, str):
        errors.append("compiled:focus_part:part must be a string")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"compiled:focus_part:{control}/{part_name} missing in definition.xml")
        return
    state = part.find("state")
    if state is None:
        errors.append(f"compiled:focus_part:{control}/{part_name} has no <state>")
        return
    lines = [child for child in state if child.tag == "line"]
    pinned = focus.get("lines")
    if not isinstance(pinned, list) or not pinned:
        errors.append("compiled:focus_part:lines:non-empty array required")
        return
    if len(lines) != len(pinned):
        errors.append(
            f"compiled:focus_part:the ring has {len(lines)} lines but {len(pinned)} are pinned "
            "(the shared focus ring changed)"
        )
    stroke = focus.get("stroke")
    stroke_width = focus.get("stroke-width")
    for index, want in enumerate(pinned):
        if index >= len(lines):
            break
        line = lines[index]
        if not isinstance(want, dict):
            errors.append(f"compiled:focus_part:line[{index}]:object required")
            continue
        if line.get("stroke") != stroke:
            errors.append(
                f"compiled:focus_part:line[{index}] stroke is {line.get('stroke')!r}, "
                f"expected {stroke!r}"
            )
        if line.get("stroke-width") != stroke_width:
            errors.append(
                f"compiled:focus_part:line[{index}] stroke-width is {line.get('stroke-width')!r}, "
                f"expected {stroke_width!r}"
            )
        for coord in ("x1", "y1", "x2", "y2"):
            if line.get(coord) != want.get(coord):
                errors.append(
                    f"compiled:focus_part:line[{index}] {coord} is {line.get(coord)!r}, "
                    f"expected {want.get(coord)!r} (focus ring geometry drifted)"
                )


def _validate_style_slots(root: ET.Element, slots: Any, errors: list[str]) -> None:
    if not isinstance(slots, dict):
        errors.append("compiled:style_slots:object required")
        return
    style = root.find("style")
    if style is None:
        errors.append("compiled:style_slots:definition.xml has no <style> section")
        return

    def slot_value(name: str) -> str | None:
        element = style.find(name)
        return element.get("value") if element is not None else None

    pairs = slots.get("default_pairs")
    if not isinstance(pairs, list) or not pairs:
        errors.append("compiled:style_slots:default_pairs:non-empty array required")
    else:
        for pair in pairs:
            if not isinstance(pair, dict):
                errors.append("compiled:style_slots:pair must be object")
                continue
            default_name = pair.get("default")
            sibling_name = pair.get("sibling")
            expected = pair.get("value")
            if not (isinstance(default_name, str) and isinstance(sibling_name, str)):
                errors.append("compiled:style_slots:pair:default/sibling must be strings")
                continue
            default_value = slot_value(default_name)
            sibling_value = slot_value(sibling_name)
            if default_value is None:
                errors.append(f"compiled:style_slots:<{default_name}> missing in <style>")
            if sibling_value is None:
                errors.append(f"compiled:style_slots:<{sibling_name}> missing in <style>")
            if default_value != expected or sibling_value != expected:
                errors.append(
                    f"compiled:style_slots:D-020 pairing broken: {default_name}={default_value!r} / "
                    f"{sibling_name}={sibling_value!r}, both pinned {expected!r} "
                    "(default-emphasis deferral drifted -- needs a decision-log change)"
                )

    flat = slots.get("flat_slot")
    if isinstance(flat, dict):
        name = flat.get("slot")
        expected = flat.get("value")
        if isinstance(name, str):
            actual = slot_value(name)
            if actual != expected:
                errors.append(
                    f"compiled:style_slots:<{name}> is {actual!r}, expected {expected!r}"
                )
    else:
        errors.append("compiled:style_slots:flat_slot:object required")


# --------------------------------------------------------------------------------------------------
# gallery cardinality cross-check
# --------------------------------------------------------------------------------------------------
def _validate_gallery(registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]) -> None:
    block = registry.get("gallery_cardinality")
    if not isinstance(block, dict):
        errors.append("gallery_cardinality:object required")
        return
    rel = registry.get("gallery_registry")
    text = contents.get(rel) if isinstance(rel, str) else None
    if text is None:
        errors.append("gallery_cardinality:gallery_registry file missing")
        return
    try:
        gallery = json.loads(text)
    except json.JSONDecodeError as error:
        errors.append(f"gallery_cardinality:unparseable json:{error}")
        return
    cells = gallery.get("cells")
    if not isinstance(cells, list):
        errors.append("gallery_cardinality:component-gallery-coverage.json has no cells array")
        return
    control = block.get("control", "pushbutton")
    entire = sum(1 for c in cells if isinstance(c, dict) and c.get("control") == control and c.get("part") == "Entire")
    focus = sum(1 for c in cells if isinstance(c, dict) and c.get("control") == control and c.get("part") == "Focus")
    if entire != block.get("entire_cells"):
        errors.append(
            f"gallery_cardinality:{control}/Entire cells {entire} != pinned "
            f"{block.get('entire_cells')} (gallery/definition state count diverged)"
        )
    if focus != block.get("focus_cells"):
        errors.append(
            f"gallery_cardinality:{control}/Focus cells {focus} != pinned {block.get('focus_cells')}"
        )


# --------------------------------------------------------------------------------------------------
# negative guard (TEMPORARY)
# --------------------------------------------------------------------------------------------------
def _pushbutton_block(definition_text: str) -> str:
    match = re.search(r"<pushbutton>.*?</pushbutton>", definition_text, re.DOTALL)
    return match.group(0) if match else ""


def _pushbutton_case(code: str) -> str | None:
    """Return the brace-delimited body of the ``case ControlType::Pushbutton:`` block.

    The case opens with a ``{ ... }`` scope that itself contains an early ``break;``
    (``if (rValue.getType() != ControlType::Pushbutton) break;``), so a naive slice to the
    first ``break;`` would miss the mbIsAction/m_bFlatButton logic. Brace-match instead.
    """

    marker = "case ControlType::Pushbutton:"
    start = code.find(marker)
    if start < 0:
        return None
    brace = code.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for pos in range(brace, len(code)):
        c = code[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return code[start:pos + 1]
    return None


def _validate_negative_guard(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    guard = registry.get("negative_guard")
    if not isinstance(guard, dict):
        errors.append("negative_guard:object required")
        return

    forbidden_extra = guard.get("definition_forbidden_extra")
    definition_text = contents.get(DEFINITION_PATH)
    if isinstance(forbidden_extra, str) and definition_text is not None:
        block = _pushbutton_block(definition_text)
        if f'extra="{forbidden_extra}"' in block:
            errors.append(
                f"negative_guard:definition:extra=\"{forbidden_extra}\" appeared in the "
                "<pushbutton> block without a matching native signal (dead markup); if the "
                "native signal has landed, invert this guard per target.outlined.blocked_on"
            )

    native = guard.get("native_branch")
    if not isinstance(native, dict):
        errors.append("negative_guard:native_branch:object required")
        return
    rel = native.get("file")
    text = contents.get(rel) if isinstance(rel, str) else None
    if text is None:
        errors.append(f"negative_guard:native_branch:file missing: {rel}")
        return
    code = _strip_comments(text)
    case = _pushbutton_case(code)
    if case is None:
        errors.append(
            f"negative_guard:native_branch:{native.get('case_marker')!r} not found in {rel} "
            "(the ControlType::Pushbutton selector moved or was renamed)"
        )
        return
    for signal in native.get("required_signals", []) or []:
        if isinstance(signal, str) and signal not in case:
            errors.append(
                f"negative_guard:native_branch:{signal!r} missing from the Pushbutton case in {rel}"
            )
    for extra in native.get("required_extras", []) or []:
        if isinstance(extra, str) and extra not in case:
            errors.append(
                f"negative_guard:native_branch:{extra!r} missing from the Pushbutton case in {rel}"
            )
    forbidden = native.get("forbidden_token")
    if isinstance(forbidden, str) and forbidden in case:
        errors.append(
            f"negative_guard:native_branch:{forbidden!r} appeared in the Pushbutton case in {rel} "
            "(the outlined native signal may have landed -- invert this TEMPORARY guard and promote "
            "target.outlined to an implemented pin)"
        )


# --------------------------------------------------------------------------------------------------
# targets + design anchors
# --------------------------------------------------------------------------------------------------
def _validate_targets(registry: Mapping[str, Any], errors: list[str]) -> None:
    target = registry.get("target")
    if not isinstance(target, dict):
        errors.append("target:object required")
        return
    for name in ("outlined", "default_emphasis"):
        block = target.get(name)
        if not isinstance(block, dict):
            errors.append(f"target:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"target:{name}:status must stay 'specified' "
                "(build-blocked; not promoted to an implemented claim)"
            )
        if block.get("runtime_verified") is not False:
            errors.append(f"target:{name}:runtime_verified must be false")
        blocked_on = block.get("blocked_on")
        if not isinstance(blocked_on, list) or not blocked_on or not all(
            isinstance(item, str) and item.strip() for item in blocked_on
        ):
            errors.append(
                f"target:{name}:blocked_on:non-empty array of source citations required "
                "(status can never flip to implemented without real source)"
            )


def _validate_design_anchors(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    anchors = registry.get("design_anchors")
    rel = registry.get("design_source")
    text = contents.get(rel) if isinstance(rel, str) else None
    if not isinstance(anchors, list) or not anchors:
        errors.append("design_anchors:non-empty array required")
        return
    if text is None:
        errors.append(f"design_anchors:design_source file missing: {rel}")
        return
    for anchor in anchors:
        if isinstance(anchor, str) and anchor not in text:
            errors.append(
                f"design_anchors:{anchor!r} missing from {rel} "
                "(the design chapter and this registry diverged)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-pushbutton-composition":
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

    definition_root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    compiled = registry.get("compiled")
    if isinstance(compiled, dict):
        if definition_root is not None:
            _validate_compiled(definition_root, compiled, errors)
    else:
        errors.append("registry:compiled:object required")

    _validate_gallery(registry, contents, errors)
    _validate_negative_guard(registry, contents, errors)
    _validate_targets(registry, errors)
    _validate_design_anchors(registry, contents, errors)

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
        print(f"Push-button composition contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Push-button composition contract passed: pinned the 13 compiled pushbutton/Entire states "
        "(tonal/action/flat) + the shared 4-line Focus ring + the D-020 default-slot pairing, "
        "cross-checked the 13+1 gallery cells, held the TEMPORARY outlined negative guard "
        "(no extra=\"outlined\" XML, native branch still mbIsAction/m_bFlatButton only), and kept "
        "outlined/default-emphasis targets spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
