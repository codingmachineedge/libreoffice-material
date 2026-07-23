#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the reduced-motion signal chain (WIN-FND-004).

docs/design/01-foundations.md section 5 states that any future native Material motion
role must, under a platform reduced-motion preference, resolve to zero duration -- and
that "the native mapping ... is identical" to the reduced-motion behaviour LibreOffice
already ships. That pre-existing, compiled chain is this contract's subject. It does
**not** claim any Material-specific motion exists (marker ``trip_wire`` keeps that gate
visibly open); it pins the prerequisite signal path a Material motion implementation is
obliged to route through, so it cannot silently regress before a Material consumer
exists.

The chain, end to end:

* ``MiscSettings::GetUseReducedAnimation`` / ``IsAnimated{Others,Graphic,Text}Allowed``
  are declared in include/vcl/settings.hxx;
* in vcl/source/app/settings.cxx, ``GetUseReducedAnimation`` delegates to the platform
  frame (never a hardcoded value), and each ``IsAnimated*Allowed`` reads its officecfg
  ``Accessibility::AllowAnimated*`` key and, on the "System" case, negates
  ``GetUseReducedAnimation()``;
* on Windows the frame backend reads ``SPI_GETCLIENTAREAANIMATION`` and returns its
  negation (declared in vcl/inc/win/salframe.h);
* the three officecfg properties keep ``xs:short`` type and default value ``0``
  ("System");
* each ``IsAnimated*Allowed`` function has at least one real (non-comment) consumer;
* and the Material theme definition still carries **zero** motion/duration/easing token
  elements -- the trip-wire that keeps this row's Material-motion (SRC) gate open.

Source evidence only: ``runtime_verified`` is false throughout. No native Material
motion, build, motion-capture pair, or interaction timing is claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/reduced-motion-contract.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CONTRACT = "material-reduced-motion"
# Token names that would mean a native Material motion family has appeared. None may
# occur as an element tag or attribute name in the theme definition.
FORBIDDEN_MOTION_TOKENS = frozenset({"motion", "duration", "easing", "transition", "animation"})


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


def _referenced_sources(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = {DEFINITION_PATH}
    declarations = registry.get("declarations")
    if isinstance(declarations, dict) and isinstance(declarations.get("source"), str):
        paths.add(declarations["source"])
    schema = registry.get("schema")
    if isinstance(schema, dict) and isinstance(schema.get("source"), str):
        paths.add(schema["source"])
    for section in ("checkpoints", "contiguous", "repeated", "consumers"):
        for entry in registry.get(section, []) or []:
            if isinstance(entry, dict) and isinstance(entry.get("source"), str):
                paths.add(entry["source"])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _referenced_sources(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_integrity(registry: Mapping[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT:
        errors.append(f"registry:contract:must be {CONTRACT}")
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


def _markers_in(code: str, markers: Any, label: str, errors: list[str]) -> None:
    if not isinstance(markers, list) or not markers:
        errors.append(f"{label}:markers non-empty array required")
        return
    for marker in markers:
        if isinstance(marker, str) and marker not in code:
            errors.append(f"{label}:marker missing in code ({marker!r})")


def _validate_declarations(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    declarations = registry.get("declarations")
    if not isinstance(declarations, dict):
        errors.append("registry:declarations:object required")
        return
    source_path = declarations.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"declarations:source {source_path!r} missing")
        return
    _markers_in(_without_cpp_comments(source), declarations.get("markers"), "declarations", errors)


def _validate_checkpoints(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for checkpoint in registry.get("checkpoints", []) or []:
        if not isinstance(checkpoint, dict):
            errors.append("checkpoints:entry:object required")
            continue
        cid = checkpoint.get("id", "?")
        source_path = checkpoint.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"checkpoints:{cid}:source {source_path!r} missing")
            continue
        _markers_in(_without_cpp_comments(source), checkpoint.get("markers"), f"checkpoints:{cid}", errors)


def _validate_contiguous(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for statement in registry.get("contiguous", []) or []:
        if not isinstance(statement, dict):
            errors.append("contiguous:entry:object required")
            continue
        sid = statement.get("id", "?")
        source_path = statement.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"contiguous:{sid}:source {source_path!r} missing")
            continue
        expected = statement.get("statement")
        if not isinstance(expected, str) or not expected:
            errors.append(f"contiguous:{sid}:statement must be a non-empty string")
            continue
        if _collapse_ws(expected) not in _collapse_ws(_without_cpp_comments(source)):
            errors.append(
                f"contiguous:{sid}:the ordered statement is not present as a contiguous "
                f"block ({expected!r} not found in {source_path})"
            )


def _validate_repeated(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    # A marker that must appear at least ``min_count`` times, e.g. the System-case
    # negation of GetUseReducedAnimation() -- once per Allow* function.
    for entry in registry.get("repeated", []) or []:
        if not isinstance(entry, dict):
            errors.append("repeated:entry:object required")
            continue
        rid = entry.get("id", "?")
        source_path = entry.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"repeated:{rid}:source {source_path!r} missing")
            continue
        marker = entry.get("marker")
        min_count = entry.get("min_count")
        if not isinstance(marker, str) or not isinstance(min_count, int):
            errors.append(f"repeated:{rid}:marker string and min_count int required")
            continue
        actual = _without_cpp_comments(source).count(marker)
        if actual < min_count:
            errors.append(
                f"repeated:{rid}:marker {marker!r} appears {actual} time(s) in "
                f"{source_path}, expected at least {min_count}"
            )


def _validate_schema(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    schema = registry.get("schema")
    if not isinstance(schema, dict):
        errors.append("registry:schema:object required")
        return
    source_path = schema.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"schema:source {source_path!r} missing")
        return
    prop_type = schema.get("type")
    default = schema.get("default")
    for prop in schema.get("props", []) or []:
        if not isinstance(prop, str):
            continue
        match = re.search(
            r'<prop\s+oor:name="' + re.escape(prop) + r'"(.*?)</prop>', source, flags=re.DOTALL
        )
        if not match:
            errors.append(f"schema:prop {prop!r} not found in {source_path}")
            continue
        block = match.group(0)
        if isinstance(prop_type, str) and f'oor:type="{prop_type}"' not in block:
            errors.append(f"schema:prop {prop!r} is not oor:type={prop_type!r}")
        if isinstance(default, str) and f"<value>{default}</value>" not in block:
            errors.append(
                f"schema:prop {prop!r} default drifted (expected <value>{default}</value>)"
            )


def _validate_consumers(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    for consumer in registry.get("consumers", []) or []:
        if not isinstance(consumer, dict):
            errors.append("consumers:entry:object required")
            continue
        function = consumer.get("function", "?")
        source_path = consumer.get("source")
        source = contents.get(source_path) if isinstance(source_path, str) else None
        if source is None:
            errors.append(f"consumers:{function}:source {source_path!r} missing")
            continue
        marker = consumer.get("marker")
        if not isinstance(marker, str):
            errors.append(f"consumers:{function}:marker must be a string")
            continue
        if marker not in _without_cpp_comments(source):
            errors.append(
                f"consumers:{function}:no live call site ({marker!r}) in {source_path}"
            )


def _validate_trip_wire(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    # The SRC-gate trip-wire: the theme definition must still carry zero Material
    # motion tokens. When native motion tokens are finally implemented, this fires and
    # must be updated in the same change -- it must never be silently loosened.
    try:
        root = ET.fromstring(contents.get(DEFINITION_PATH, ""))
    except ET.ParseError as error:
        errors.append(f"trip_wire:definition xml parse error: {error}")
        return
    for element in root.iter():
        tag = element.tag if isinstance(element.tag, str) else ""
        if tag.lower() in FORBIDDEN_MOTION_TOKENS:
            errors.append(
                f"trip_wire:definition.xml now declares a <{tag}> motion element -- the "
                "Material-motion SRC gate is no longer empty; update this contract"
            )
        for attr in element.attrib:
            if attr.lower() in FORBIDDEN_MOTION_TOKENS:
                errors.append(
                    f"trip_wire:definition.xml <{tag}> carries a motion attribute "
                    f"{attr!r} -- update this contract, do not loosen the trip-wire"
                )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    _validate_integrity(registry, errors)
    _validate_declarations(registry, contents, errors)
    _validate_checkpoints(registry, contents, errors)
    _validate_contiguous(registry, contents, errors)
    _validate_repeated(registry, contents, errors)
    _validate_schema(registry, contents, errors)
    _validate_consumers(registry, contents, errors)
    _validate_trip_wire(registry, contents, errors)
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
        print(f"Reduced-motion signal chain contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Reduced-motion signal chain contract passed: the MiscSettings declarations, "
        "the officecfg-gated System-case negation, the Windows SPI_GETCLIENTAREAANIMATION "
        "backend, the xs:short/default-0 schema, live consumers, and the zero-motion-token "
        "trip-wire are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
