#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed fidelity contract for the public Material token accessor.

``vcl::MaterialTokens`` (include/vcl/MaterialTokens.hxx,
vcl/source/gdi/MaterialTokens.cxx) is a queryable named-token table over the
Material widget definition's palette / shape / metric data. This checker proves
the accessor is a 1:1 mirror of
``vcl/uiconfig/theme_definitions/material/definition.xml`` with no drift and no
hard-coded hex duplication:

* The C++ publishes a token-name vocabulary (``gMaterialColorRoles``,
  ``gMaterialShapeTokens``, ``gMaterialMetricTokens``). Each list must equal the
  definition's ``<palette>`` / ``<shapes>`` / ``<metrics>`` names exactly -- no
  missing name, no undeclared extra name -- and the declared ``std::array`` size
  must match. Both palette schemes (light + dark) must carry the same names.
* No hex color literal may appear in the accessor's header or source: values are
  read from the file, never restated, so a palette literal cannot drift.
* The accessor must actually source its data through the existing
  WidgetDefinitionReader path (``readTokenTables`` reusing ``readColorPalette``),
  not an ad-hoc copy, and must be registered as a public VCL export that the
  build compiles.

A mismatch on any of these fails the contract; the mutation suite in
bin/test_material_token_accessor.py exercises every branch.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping


REPOSITORY = Path(__file__).resolve().parents[1]

DEFINITION = "vcl/uiconfig/theme_definitions/material/definition.xml"
HEADER = "include/vcl/MaterialTokens.hxx"
SOURCE = "vcl/source/gdi/MaterialTokens.cxx"
READER_HEADER = "vcl/inc/widgetdraw/WidgetDefinitionReader.hxx"
READER_SOURCE = "vcl/source/gdi/WidgetDefinitionReader.cxx"
MAKEFILE = "vcl/Library_vcl.mk"

FILES = (DEFINITION, HEADER, SOURCE, READER_HEADER, READER_SOURCE, MAKEFILE)

# The C++ array names, mapped to the definition.xml section they mirror.
VOCAB_ARRAYS = {
    "gMaterialColorRoles": "palette",
    "gMaterialShapeTokens": "shapes",
    "gMaterialMetricTokens": "metrics",
}

_ARRAY_RE = re.compile(
    r"std::array<\s*std::string_view\s*,\s*(\d+)\s*>\s+"
    r"(gMaterial\w+)\s*=\s*\{(.*?)\};",
    re.DOTALL,
)
_STRING_LITERAL_RE = re.compile(r'"([^"\\]*)"')
_HEX_LITERAL_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


class ValidationError(RuntimeError):
    pass


def load_repository(repo_root: Path = REPOSITORY) -> dict[str, str]:
    contents: dict[str, str] = {}
    for relative in FILES:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def _strip_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _parse_definition(text: str, errors: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"definition:xml:{error}")
        return result

    palettes: dict[str, list[str]] = {}
    for palette in root.findall("palette"):
        scheme = palette.get("scheme") or ""
        names = [child.get("name", "") for child in palette if child.tag == "color"]
        palettes[scheme] = names
    result["palettes"] = palettes

    shapes = root.find("shapes")
    result["shapes"] = (
        [child.get("name", "") for child in shapes if child.tag == "radius"]
        if shapes is not None
        else []
    )

    metrics = root.find("metrics")
    result["metrics"] = (
        [child.get("name", "") for child in metrics if child.tag == "metric"]
        if metrics is not None
        else []
    )
    return result


def _parse_arrays(source: str, errors: list[str]) -> dict[str, tuple[int, list[str]]]:
    arrays: dict[str, tuple[int, list[str]]] = {}
    for declared_n, name, body in _ARRAY_RE.findall(source):
        literals = _STRING_LITERAL_RE.findall(body)
        arrays[name] = (int(declared_n), literals)
    for name in VOCAB_ARRAYS:
        if name not in arrays:
            errors.append(f"accessor:vocabulary:{name} array not found")
    return arrays


def _compare_names(
    label: str,
    declared_n: int,
    accessor_names: list[str],
    definition_names: list[str],
    errors: list[str],
) -> None:
    accessor_set = set(accessor_names)
    definition_set = set(definition_names)
    if len(accessor_names) != len(accessor_set):
        duplicates = sorted(n for n in accessor_set if accessor_names.count(n) > 1)
        errors.append(f"accessor:{label}:duplicate name(s) {', '.join(duplicates)}")
    if declared_n != len(accessor_names):
        errors.append(
            f"accessor:{label}:declared std::array size {declared_n} "
            f"!= {len(accessor_names)} literals"
        )
    missing = sorted(definition_set - accessor_set)
    if missing:
        errors.append(f"accessor:{label}:missing definition name(s) {', '.join(missing)}")
    extra = sorted(accessor_set - definition_set)
    if extra:
        errors.append(f"accessor:{label}:undeclared name(s) not in definition {', '.join(extra)}")
    if declared_n != len(definition_names) and not missing and not extra:
        errors.append(
            f"accessor:{label}:size drift declared {declared_n} vs definition "
            f"{len(definition_names)}"
        )


def violations(contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    for relative in FILES:
        if relative not in contents:
            errors.append(f"file:missing {relative}")
    if errors:
        return errors

    definition = _parse_definition(contents[DEFINITION], errors)
    palettes = definition.get("palettes", {}) if definition else {}
    if not isinstance(palettes, dict) or "" not in palettes:
        errors.append("definition:palette:default (light) palette missing")
    if isinstance(palettes, dict) and "dark" not in palettes:
        errors.append("definition:palette:dark palette missing")
    # Every palette scheme (default light/dark + the bounded accent set) must
    # carry the identical token-name set, so the single C++ vocabulary mirrors
    # them all and MaterialTokens stays valid across every composed scheme.
    if isinstance(palettes, dict) and "" in palettes:
        light_names = set(palettes[""])
        for scheme, names in palettes.items():
            if set(names) != light_names:
                label = scheme or "light"
                errors.append(
                    f"definition:palette:scheme {label!r} token names differ from light"
                )

    header = contents[HEADER]
    source = contents[SOURCE]
    header_nc = _strip_cpp_comments(header)
    source_nc = _strip_cpp_comments(source)

    # Public export + registration.
    if "class VCL_DLLPUBLIC MaterialTokens" not in header_nc:
        errors.append("accessor:export:class VCL_DLLPUBLIC MaterialTokens missing")
    if not re.search(r"^\s*vcl/source/gdi/MaterialTokens\s*\\?\s*$", contents[MAKEFILE], re.M):
        errors.append("accessor:build:vcl/source/gdi/MaterialTokens not registered in Library_vcl.mk")

    # No hard-coded palette literal in the accessor.
    for relative, blob in ((HEADER, header), (SOURCE, source)):
        found = _HEX_LITERAL_RE.findall(blob)
        if found:
            errors.append(f"accessor:no-hex:{relative} restates hex literal(s) {', '.join(sorted(set(found)))}")

    # Vocabulary 1:1 with the definition.
    arrays = _parse_arrays(source_nc, errors)
    if isinstance(palettes, dict):
        light = palettes.get("", [])
    else:
        light = []
    section_names = {
        "palette": light,
        "shapes": definition.get("shapes", []) if definition else [],
        "metrics": definition.get("metrics", []) if definition else [],
    }
    for array_name, section in VOCAB_ARRAYS.items():
        if array_name not in arrays:
            continue
        declared_n, literals = arrays[array_name]
        _compare_names(array_name, declared_n, literals, section_names[section], errors)

    # The accessor must source data through the existing reader path.
    for marker, label in (
        ("#include <vcl/MaterialTokens.hxx>", "self-include"),
        ("#include <widgetdraw/WidgetDefinitionReader.hxx>", "reader-include"),
        ("WidgetDefinitionReader aReader(", "reader-construct"),
        (".readTokenTables(", "reader-call"),
        ("theme_definitions/material/", "theme-path"),
        ("definition.xml", "definition-file"),
    ):
        if marker not in source_nc:
            errors.append(f"accessor:reader-path:{label} marker missing ({marker})")

    # readTokenTables must exist and genuinely reuse readColorPalette (not a copy).
    reader_header_nc = _strip_cpp_comments(contents[READER_HEADER])
    reader_source_nc = _strip_cpp_comments(contents[READER_SOURCE])
    if "bool readTokenTables(" not in reader_header_nc:
        errors.append("reader:api:readTokenTables not declared in WidgetDefinitionReader.hxx")
    token_body = _function_body(reader_source_nc, "WidgetDefinitionReader::readTokenTables(")
    if token_body is None:
        errors.append("reader:api:readTokenTables not implemented in WidgetDefinitionReader.cxx")
    else:
        for marker, label in (
            ("readColorPalette(", "color-palette"),
            ("readShapeTokens(", "shape-tokens"),
            ("readMetricTokens(", "metric-tokens"),
        ):
            if marker not in token_body:
                errors.append(f"reader:reuse:readTokenTables must call {label} reader ({marker})")

    return errors


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


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    contents = load_repository(repo_root)
    errors = violations(contents)
    if errors:
        raise ValidationError("\n".join(errors))


def main() -> int:
    try:
        validate_repository()
    except (OSError, ValidationError) as error:
        print(f"Material token accessor contract failed:\n{error}", file=sys.stderr)
        return 1
    contents = load_repository()
    definition = _parse_definition(contents[DEFINITION], [])
    palettes = definition.get("palettes", {})
    n_colors = len(palettes.get("", [])) if isinstance(palettes, dict) else 0
    print(
        "Material token accessor passed: vcl::MaterialTokens mirrors "
        f"{n_colors} color roles, {len(definition.get('shapes', []))} shape tokens and "
        f"{len(definition.get('metrics', []))} metric tokens 1:1 from definition.xml "
        "with no hard-coded hex and reader-path sourcing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
