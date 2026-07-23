#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed composition-pinning contract for Math placeholder/error/insertion (WIN-MA-002).

``qa/windows-ui-contract/math-editor.json`` pins the three upstream StarMath
behavioural primitives chapter 12.2 declares normative -- placeholder marks
(``<?>``), error text+position pairing with a non-destructive clear path, and
symbol-insertion focus-return -- plus the native ``multilineeditbox`` part the
editor maps to, plus the F4/Shift+F4 (mark) and F3/Shift+F3 (error) accelerator,
command and menu bindings:

* ``definition_part`` -- the compiled ``multilineeditbox``/``Entire`` 3-state token
  set, read only.
* ``behavior_markers`` -- each upstream code marker/literal, asserted against
  comment/raw-string-stripped source so commented-out wiring fails closed.
* ``command_bindings`` -- the F4/F3 accelerator nodes resolve to
  ``.uno:NextMark/.uno:PrevMark/.uno:NextError/.uno:PrevError``, and those commands
  exist as command nodes and menu items.
* ``material_carve_outs`` -- the three Material differentiators stay
  ``status:"specified"`` (build-bound); the checker fails closed if any is promoted
  to an implemented/runtime claim.

GATE CONTRACT: this is a D-gate source pin only. Existing upstream UI source never
satisfies the M gate, so the contract asserts ``advances_m: false`` -- it proves the
substrate the Material design builds on is present and unregressed, nothing more.
``runtime_verified: false`` throughout: no build, no pixels, no interaction.
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
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/math-editor.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

STATE_ATTR_KEYS = ("enabled", "focused", "pressed", "rollover", "default", "selected", "button-value")
ALLOWED_CARVE_OUT_STATUS = {"specified"}
# How far after an accelerator key node the resolved command may appear.
_BINDING_WINDOW = 400


class ValidationError(RuntimeError):
    """Raised when the Math editor behavioural contract is incomplete or weakened."""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def strip_cpp_non_code(source: str) -> str:
    raw = re.compile(
        r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
        re.DOTALL,
    )
    source = raw.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def load_registry(registry_path: Path) -> dict[str, Any]:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")
    return data


def _load_contents(repo_root: Path, data: Mapping[str, Any]) -> dict[str, str]:
    paths: set[str] = {DEFINITION_PATH}
    for marker in data.get("behavior_markers", []):
        if isinstance(marker, dict) and isinstance(marker.get("source"), str):
            paths.add(marker["source"])
    bindings = data.get("command_bindings", {})
    if isinstance(bindings, dict):
        for block in ("accelerators", "commands", "menu"):
            entry = bindings.get(block)
            if isinstance(entry, dict) and isinstance(entry.get("file"), str):
                paths.add(entry["file"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


# --------------------------------------------------------------------------------------------------
# definition.xml multilineeditbox part
# --------------------------------------------------------------------------------------------------
def _find_part(root: ET.Element, control: str, part_value: str) -> ET.Element | None:
    control_element = root.find(control)
    if control_element is None:
        return None
    for candidate in control_element.findall("part"):
        if candidate.get("value") == part_value:
            return candidate
    return None


def _match_state(part: ET.Element, attrs: Mapping[str, str]) -> ET.Element | None:
    wanted = {key: attrs.get(key, "any") for key in STATE_ATTR_KEYS}
    for state in part.findall("state"):
        signature = {key: state.get(key, "any") for key in STATE_ATTR_KEYS}
        if signature == wanted:
            return state
    return None


def validate_definition_part(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    try:
        root = ET.fromstring(contents.get(DEFINITION_PATH, ""))
    except ET.ParseError as error:
        raise ValidationError(f"definition.xml is not valid XML: {error}") from error
    part_decl = data.get("definition_part")
    if not isinstance(part_decl, dict):
        raise ValidationError("registry definition_part must be an object")
    part = _find_part(root, part_decl.get("control"), part_decl.get("part"))
    if part is None:
        raise ValidationError(
            f"definition.xml is missing {part_decl.get('control')}/{part_decl.get('part')}"
        )
    for state_decl in part_decl.get("states", []):
        role = state_decl.get("role", "?")
        state = _match_state(part, state_decl.get("attrs", {}))
        if state is None:
            raise ValidationError(
                f"definition.xml multilineeditbox/Entire:{role}: no <state> matching "
                f"{state_decl.get('attrs')}"
            )
        rect = next((child for child in state if child.tag in ("rect", "line")), None)
        if rect is None:
            raise ValidationError(f"definition.xml multilineeditbox/Entire:{role} has no rect/line")
        for token_key, expected in state_decl.get("tokens", {}).items():
            if rect.get(token_key) != expected:
                raise ValidationError(
                    f"definition.xml multilineeditbox/Entire:{role} token drift: {token_key} is "
                    f"{rect.get(token_key)!r}, expected {expected!r}"
                )


# --------------------------------------------------------------------------------------------------
# behavioural source markers
# --------------------------------------------------------------------------------------------------
def validate_behavior_markers(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    markers = data.get("behavior_markers")
    if not isinstance(markers, list) or not markers:
        raise ValidationError("registry behavior_markers must be a non-empty array")
    if data.get("expected_behavior_markers") != len(markers):
        raise ValidationError("registry expected_behavior_markers count drift")

    seen: set[str] = set()
    for index, marker in enumerate(markers):
        marker_id = marker.get("id")
        if not isinstance(marker_id, str) or not marker_id:
            raise ValidationError(f"behavior marker #{index} needs a non-empty id")
        if marker_id in seen:
            raise ValidationError(f"duplicate behavior marker id: {marker_id}")
        seen.add(marker_id)
        context = f"behavior_marker[{marker_id}]"
        source_path = marker.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            raise ValidationError(f"{context}: source {source_path} missing")
        code = strip_cpp_non_code(source)
        for code_marker in marker.get("code_markers", []):
            if code_marker not in code:
                raise ValidationError(f"{context}: missing marker in code ({code_marker!r})")


# --------------------------------------------------------------------------------------------------
# command / accelerator / menu bindings
# --------------------------------------------------------------------------------------------------
def _accelerator_binds(text: str, key: str, command: str) -> bool:
    for match in re.finditer(rf'oor:name="{re.escape(key)}"', text):
        window = text[match.start():match.start() + _BINDING_WINDOW]
        if f">{command}</value>" in window:
            return True
    return False


def validate_command_bindings(data: Mapping[str, Any], contents: Mapping[str, str]) -> None:
    bindings = data.get("command_bindings")
    if not isinstance(bindings, dict):
        raise ValidationError("registry command_bindings must be an object")

    accelerators = bindings.get("accelerators", {})
    accel_text = contents.get(accelerators.get("file"))
    if accel_text is None:
        raise ValidationError(f"command_bindings: accelerators file {accelerators.get('file')} missing")
    for binding in accelerators.get("bindings", []):
        key = binding.get("key")
        command = binding.get("command")
        if not _accelerator_binds(accel_text, key, command):
            raise ValidationError(
                f"command_bindings: accelerator {key!r} does not resolve to {command!r}"
            )

    commands = bindings.get("commands", {})
    command_text = contents.get(commands.get("file"))
    if command_text is None:
        raise ValidationError(f"command_bindings: commands file {commands.get('file')} missing")
    for node in commands.get("nodes", []):
        if f'oor:name="{node}"' not in command_text:
            raise ValidationError(f"command_bindings: command node {node!r} missing")

    menu = bindings.get("menu", {})
    menu_text = contents.get(menu.get("file"))
    if menu_text is None:
        raise ValidationError(f"command_bindings: menu file {menu.get('file')} missing")
    for item in menu.get("items", []):
        if f'menu:id="{item}"' not in menu_text:
            raise ValidationError(f"command_bindings: menu item {item!r} missing")


# --------------------------------------------------------------------------------------------------
# honest carve-outs (anti-promotion guard)
# --------------------------------------------------------------------------------------------------
def validate_carve_outs(data: Mapping[str, Any]) -> None:
    carve_outs = data.get("material_carve_outs")
    if not isinstance(carve_outs, list) or not carve_outs:
        raise ValidationError("registry material_carve_outs must be a non-empty array")
    seen: set[str] = set()
    for index, carve in enumerate(carve_outs):
        carve_id = carve.get("id")
        if not isinstance(carve_id, str) or not carve_id:
            raise ValidationError(f"carve_out #{index} needs a non-empty id")
        if carve_id in seen:
            raise ValidationError(f"duplicate carve_out id: {carve_id}")
        seen.add(carve_id)
        status = carve.get("status")
        if status not in ALLOWED_CARVE_OUT_STATUS:
            raise ValidationError(
                f"carve_out {carve_id!r} status {status!r} must stay "
                f"{sorted(ALLOWED_CARVE_OUT_STATUS)} (a source pin never promotes a Material "
                "differentiator to implemented/runtime)"
            )
        if not isinstance(carve.get("description"), str) or not carve["description"]:
            raise ValidationError(f"carve_out {carve_id!r} needs a description")


# --------------------------------------------------------------------------------------------------
def validate(repo_root: Path, registry_path: Path) -> dict[str, Any]:
    data = load_registry(registry_path)

    if data.get("schema_version") != 1:
        raise ValidationError("registry schema_version must be 1")
    if data.get("contract") != "material-math-editor":
        raise ValidationError("registry contract has an unexpected value")
    if data.get("platform") != "windows":
        raise ValidationError("registry platform must be windows")
    if data.get("definition_file") != DEFINITION_PATH:
        raise ValidationError("registry definition_file has an unexpected path")
    if data.get("runtime_verified") is not False:
        raise ValidationError("registry runtime_verified must be false")
    # Gate contract: a source pin over existing upstream code never satisfies M.
    if data.get("advances_m") is not False:
        raise ValidationError(
            "registry advances_m must be false: existing upstream source never satisfies the M gate"
        )
    if data.get("gate") != "D":
        raise ValidationError("registry gate must be 'D' (source-pin scope)")

    contents = _load_contents(repo_root, data)
    validate_definition_part(data, contents)
    validate_behavior_markers(data, contents)
    validate_command_bindings(data, contents)
    validate_carve_outs(data)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = args.registry.resolve() if args.registry is not None else DEFAULT_REGISTRY
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Math editor behavioural contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Math editor behavioural contract passed: "
        f"{len(data['behavior_markers'])} upstream primitives (placeholder <?> nav, error "
        "text+position pairing, non-destructive clear, insertion focus-return, panel emission), "
        "F4/F3 accelerator+command+menu bindings, and the multilineeditbox part -- D-gate source "
        "pin only, does NOT advance M; the 3 Material differentiators stay specified/build-bound."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
