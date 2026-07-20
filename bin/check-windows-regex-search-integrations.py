#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate source-complete native integrations of the shared regex builder."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/regex-search-integrations.json"
COVERAGE_PATH = "qa/windows-ui-contract/search-field-coverage.json"
CONTROLLER_SOURCE = "sfx2/source/dialog/RegexSearchController.cxx"


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _required_text(entry: Mapping[str, Any], key: str, context: str, errors: list[str]) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}:{key}:non-empty text required")
        return ""
    return value


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


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _properties(element: ET.Element) -> dict[str, str]:
    return {
        child.get("name", ""): (child.text or "").strip()
        for child in element
        if child.tag.rsplit("}", 1)[-1] == "property"
    }


def _property_element(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == "property" and child.get("name") == name:
            return child
    return None


def _property_is_translated(element: ET.Element, name: str) -> bool:
    prop = _property_element(element, name)
    return (
        prop is not None
        and prop.get("translatable") == "yes"
        and bool(prop.get("context"))
    )


def _nearest_parent_object(
    element: ET.Element, parents: Mapping[ET.Element, ET.Element]
) -> ET.Element | None:
    parent = parents.get(element)
    while parent is not None:
        if parent.tag.rsplit("}", 1)[-1] == "object":
            return parent
        parent = parents.get(parent)
    return None


def _direct_object_children(element: ET.Element) -> list[ET.Element]:
    result: list[ET.Element] = []
    for child in element:
        if child.tag.rsplit("}", 1)[-1] != "child":
            continue
        result.extend(
            grandchild
            for grandchild in child
            if grandchild.tag.rsplit("}", 1)[-1] == "object"
        )
    return result


def _packing_properties(
    element: ET.Element, parents: Mapping[ET.Element, ET.Element]
) -> dict[str, str]:
    wrapper = parents.get(element)
    if wrapper is None or wrapper.tag.rsplit("}", 1)[-1] != "child":
        return {}
    for child in wrapper:
        if child.tag.rsplit("}", 1)[-1] == "packing":
            return _properties(child)
    return {}


def _accessible_object(element: ET.Element) -> ET.Element | None:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] != "child" or child.get("internal-child") != "accessible":
            continue
        for candidate in child:
            if candidate.tag.rsplit("}", 1)[-1] == "object":
                return candidate
    return None


def load_repository(
    repo_root: Path = REPOSITORY,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    coverage = _read_json(repo_root / COVERAGE_PATH)
    paths = {REGISTRY_PATH, COVERAGE_PATH, CONTROLLER_SOURCE}
    for raw_entry in registry.get("integrations", []):
        if not isinstance(raw_entry, dict):
            continue
        for key in ("ui_file", "header_file", "source_file"):
            value = raw_entry.get(key)
            if isinstance(value, str) and value:
                paths.add(value)
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, coverage, contents


def violations(
    registry: Mapping[str, Any],
    coverage: Mapping[str, Any],
    contents: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-native-regex-search-integrations":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")

    raw_integrations = registry.get("integrations")
    if not isinstance(raw_integrations, list):
        errors.append("registry:integrations:array required")
        raw_integrations = []
    if not raw_integrations:
        errors.append("registry:integrations:at least one source integration required")
    if registry.get("expected_integrations") != len(raw_integrations):
        errors.append("registry:expected_integrations:count drift")

    shipping = {
        item.get("coverage_id"): item
        for item in coverage.get("shipping_fields", [])
        if isinstance(item, dict) and isinstance(item.get("coverage_id"), str)
    }
    seen_ids: set[str] = set()
    seen_controls: set[tuple[str, str]] = set()

    controller_source = contents.get(CONTROLLER_SOURCE, "")
    for marker, label in (
        ("set_accessible_name(SfxResId(STR_REGEX_BUILDER_ACCESSIBLE_NAME))", "name"),
        (
            "set_accessible_description(\n"
            "        SfxResId(STR_REGEX_BUILDER_ACCESSIBLE_DESCRIPTION))",
            "description",
        ),
        ("set_tooltip_text(SfxResId(STR_REGEX_BUILDER_TOOLTIP))", "tooltip"),
    ):
        if marker not in controller_source:
            errors.append(f"shared-controller-accessibility:{label}:marker missing")

    required_keys = (
        "coverage_id",
        "surface",
        "status",
        "ui_file",
        "entry_id",
        "builder_button_id",
        "header_file",
        "source_file",
        "owner_type",
        "owner_changed_handler",
        "entry_member",
        "builder_member",
        "controller_member",
        "controller_parent",
        "matcher_strategy",
        "default_mode",
    )

    for index, raw_entry in enumerate(raw_integrations):
        context = f"integrations[{index}]"
        if not isinstance(raw_entry, dict):
            errors.append(f"{context}:object required")
            continue
        entry = raw_entry
        values = {key: _required_text(entry, key, context, errors) for key in required_keys}
        coverage_id = values["coverage_id"]
        ui_file = values["ui_file"]
        entry_id = values["entry_id"]
        button_id = values["builder_button_id"]
        header_file = values["header_file"]
        source_file = values["source_file"]
        owner_type = values["owner_type"]
        handler = values["owner_changed_handler"]
        entry_member = values["entry_member"]
        button_member = values["builder_member"]
        controller_member = values["controller_member"]

        if coverage_id in seen_ids:
            errors.append(f"{context}:coverage_id:duplicate {coverage_id}")
        seen_ids.add(coverage_id)
        control_key = (ui_file, entry_id)
        if control_key in seen_controls:
            errors.append(f"{context}:control:duplicate {ui_file}#{entry_id}")
        seen_controls.add(control_key)

        covered = shipping.get(coverage_id)
        if covered is None:
            errors.append(f"{context}:coverage-link:not a shipping search field")
        elif (
            covered.get("ui_file") != ui_file
            or covered.get("widget_id") != entry_id
            or covered.get("regex_builder") != "adjacent-advanced-builder"
        ):
            errors.append(f"{context}:coverage-link:registry locator or policy mismatch")

        if values["status"] != "source-integrated":
            errors.append(f"{context}:status:must be source-integrated")
        if values["matcher_strategy"] != "legacy-literal-or-compiled-once-utl-textsearch":
            errors.append(f"{context}:matcher_strategy:unsupported strategy")
        if values["default_mode"] != "literal-case-sensitive-indexof-compatible":
            errors.append(f"{context}:default_mode:compatibility mode required")
        if not isinstance(entry.get("runtime_verified"), bool):
            errors.append(f"{context}:runtime_verified:boolean required")

        ui_text = contents.get(ui_file)
        if ui_text is None:
            errors.append(f"{context}:ui-file:missing {ui_file}")
        else:
            try:
                root = ET.fromstring(ui_text)
            except ET.ParseError as error:
                errors.append(f"{context}:ui-xml:{error}")
            else:
                objects = {
                    element.get("id", ""): element
                    for element in root.iter()
                    if element.tag.rsplit("}", 1)[-1] == "object" and element.get("id")
                }
                entry_object = objects.get(entry_id)
                button_object = objects.get(button_id)
                if entry_object is None or entry_object.get("class") != "GtkEntry":
                    errors.append(f"{context}:ui-entry:GtkEntry {entry_id} missing")
                if button_object is None or button_object.get("class") != "GtkButton":
                    errors.append(f"{context}:ui-button:GtkButton {button_id} missing")
                if entry_object is not None and button_object is not None:
                    parents = {child: parent for parent in root.iter() for child in parent}
                    entry_parent = _nearest_parent_object(entry_object, parents)
                    button_parent = _nearest_parent_object(button_object, parents)
                    if entry_parent is None or entry_parent is not button_parent:
                        errors.append(f"{context}:ui-adjacency:entry and builder need one parent")
                    else:
                        parent_properties = _properties(entry_parent)
                        if (
                            entry_parent.get("class") != "GtkBox"
                            or parent_properties.get("orientation") != "horizontal"
                            or parent_properties.get("spacing") != "6"
                        ):
                            errors.append(
                                f"{context}:ui-parent:horizontal GtkBox with spacing 6 required"
                            )
                        children = _direct_object_children(entry_parent)
                        try:
                            entry_position = children.index(entry_object)
                            button_position = children.index(button_object)
                        except ValueError:
                            errors.append(
                                f"{context}:ui-adjacency:controls are not direct siblings"
                            )
                        else:
                            if button_position != entry_position + 1:
                                errors.append(f"{context}:ui-adjacency:builder must follow entry")

                        entry_packing = _packing_properties(entry_object, parents)
                        button_packing = _packing_properties(button_object, parents)
                        if entry_packing != {
                            "expand": "True",
                            "fill": "True",
                            "position": "0",
                        }:
                            errors.append(f"{context}:ui-packing:entry must fill position 0")
                        if button_packing != {
                            "expand": "False",
                            "fill": "True",
                            "position": "1",
                        }:
                            errors.append(f"{context}:ui-packing:builder must fit position 1")

                    entry_properties = _properties(entry_object)
                    if entry_properties.get("hexpand") != "True":
                        errors.append(f"{context}:ui-entry:hexpand must be True")
                    button_properties = _properties(button_object)
                    for name, expected in (
                        ("label", ".*"),
                        ("visible", "True"),
                        ("can-focus", "True"),
                        ("receives-default", "False"),
                    ):
                        if button_properties.get(name) != expected:
                            errors.append(f"{context}:ui-button:{name} must be {expected}")
                    if not button_properties.get("tooltip-text"):
                        errors.append(f"{context}:ui-accessibility:tooltip missing")
                    elif not _property_is_translated(button_object, "tooltip-text"):
                        errors.append(f"{context}:ui-accessibility:tooltip must be translated")
                    accessible_object = _accessible_object(button_object)
                    accessible = (
                        _properties(accessible_object) if accessible_object is not None else {}
                    )
                    for name in (
                        "AtkObject::accessible-name",
                        "AtkObject::accessible-description",
                    ):
                        if not accessible.get(name):
                            errors.append(f"{context}:ui-accessibility:{name} missing")
                        elif accessible_object is not None and not _property_is_translated(
                            accessible_object, name
                        ):
                            errors.append(
                                f"{context}:ui-accessibility:{name} must be translated"
                            )

        header = _without_cpp_comments(contents.get(header_file, ""))
        for marker, label in (
            ("class RegexSearchController;", "controller-forward-declaration"),
            (f"std::unique_ptr<weld::Button> {button_member};", "builder-member"),
            (
                f"std::unique_ptr<sfx2::RegexSearchController> {controller_member};",
                "controller-member",
            ),
        ):
            if marker not in header:
                errors.append(f"{context}:header:{label} missing")

        entry_member_at = header.find(f"std::unique_ptr<weld::Entry> {entry_member};")
        button_member_at = header.find(f"std::unique_ptr<weld::Button> {button_member};")
        controller_member_at = header.find(
            f"std::unique_ptr<sfx2::RegexSearchController> {controller_member};"
        )
        if (
            entry_member_at < 0
            or button_member_at < 0
            or controller_member_at < entry_member_at
            or controller_member_at < button_member_at
        ):
            errors.append(
                f"{context}:header:lifetime:controller must follow the entry and button"
            )

        source = _without_cpp_comments(contents.get(source_file, ""))
        source_markers = (
            "#include <sfx2/RegexSearchController.hxx>",
            "#include <unotools/textsearch.hxx>",
            f'weld_entry(u"{entry_id}"_ustr)',
            f'weld_button(u"{button_id}"_ustr)',
        )
        for marker in source_markers:
            if marker not in source:
                errors.append(f"{context}:source-wiring:missing {marker}")
        if f"{entry_member}->connect_changed" in source:
            errors.append(f"{context}:source-wiring:direct changed handler bypasses controller")

        constructor = _function_body(source, f"{owner_type}::{owner_type}(")
        if constructor is None:
            errors.append(f"{context}:constructor:not found")
        else:
            controller_wiring = re.compile(
                re.escape(controller_member)
                + r"\s*=\s*std::make_unique<sfx2::RegexSearchController>\s*\(\s*"
                + re.escape(values["controller_parent"])
                + r"\s*,\s*\*"
                + re.escape(entry_member)
                + r"\s*,\s*\*"
                + re.escape(button_member)
                + r"\s*,\s*LINK\s*\(\s*this\s*,\s*"
                + re.escape(owner_type)
                + r"\s*,\s*"
                + re.escape(handler)
                + r"\s*\)\s*\)\s*;"
            )
            if controller_wiring.search(constructor) is None:
                errors.append(f"{context}:source-wiring:controller constructor mismatch")
            for marker in (
                "aState.Mode = sfx2::RegexSearchMode::Literal;",
                "aState.Flags.CaseInsensitive = false;",
                f"{controller_member}->SetState(aState);",
            ):
                if marker not in constructor:
                    errors.append(f"{context}:literal-default:missing {marker}")

        body = _function_body(source, f"IMPL_LINK_NOARG({owner_type}, {handler}")
        if body is None:
            errors.append(f"{context}:handler:not found")
        else:
            normalized_body = " ".join(body.split())
            marker_counts = (
                (f"{controller_member}->GetState()", 1, "state"),
                ("sfx2::RegexSearchService::Validate(rState)", 1, "validation"),
                ("std::make_unique<utl::TextSearch>", 1, "compiled-matcher"),
                (f"{controller_member}->GetSearchOptions()", 1, "search-options"),
                ("xSearch->searchForward", 1, "matching"),
                ("rSheetName.indexOf(rState.Pattern)", 1, "legacy-literal"),
            )
            for marker, count, label in marker_counts:
                if body.count(marker) != count:
                    errors.append(f"{context}:handler-{label}:expected exactly {count}")
            compile_at = body.find("std::make_unique<utl::TextSearch>")
            loop_match = re.search(r"\bfor\s*\(", body)
            if compile_at < 0 or loop_match is None or compile_at > loop_match.start():
                errors.append(f"{context}:compiled-once:matcher must be built before the loop")
            if re.search(r"\bwhile\s*\(", body):
                errors.append(f"{context}:handler-zero-width:repeated matcher loop forbidden")
            compatibility_markers = (
                "const bool bValid = bEmpty || "
                "sfx2::RegexSearchService::Validate(rState).IsValid;",
                "const bool bLegacyCompatibleLiteral = rState.Mode == "
                "sfx2::RegexSearchMode::Literal && !rState.Flags.CaseInsensitive;",
                "if (bValid && !bEmpty && !bLegacyCompatibleLiteral)",
                "bEmpty || (bLegacyCompatibleLiteral && "
                "rSheetName.indexOf(rState.Pattern) >= 0) || "
                "(xSearch && xSearch->searchForward(rSheetName))",
            )
            for marker in compatibility_markers:
                if marker not in normalized_body:
                    errors.append(f"{context}:handler:compatibility route missing {marker}")
            if "bEmpty || (bLegacyCompatibleLiteral &&" not in normalized_body:
                errors.append(f"{context}:handler:empty/invalid fail-closed route missing")

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, coverage, contents = load_repository(repo_root)
    errors = violations(registry, coverage, contents)
    if errors:
        raise ValidationError("\n".join(errors))


def main() -> int:
    try:
        validate_repository()
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Windows regex-search integration contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _, _ = load_repository()
    print(
        "Windows regex-search integrations passed: "
        f"{len(registry['integrations'])} source-integrated field with adjacent accessible "
        "builder, controller-owned callback, exact legacy literal compatibility, and "
        "compiled-once regex/opt-in matching"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
