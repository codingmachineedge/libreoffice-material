#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material standalone icon-button family (WIN-ACT-003).

``qa/windows-ui-contract/icon-button-contract.json`` pins the four real, standalone icon-only
close/dismiss/reset buttons across the sfx2 feedback + property-chip surfaces, each locked to the
exact shared native part it rides today per docs/design/02-actions.md 3.1 (a native standalone
icon-button part does not exist in definition.xml). This checker parses the real tree fail-closed:

* ``consumers`` -- each of the four registered ``.ui`` objects must stay icon-only (no sibling
  label) at its exact ui_path+object_id, keep its ``window-close-symbolic`` glyph on the pinned
  channel (a GtkToolButton ``icon-name`` attribute for Class A, a named GtkImage child for
  Class B), and keep a non-empty translatable ``tooltip-text`` at its pinned context (the sole
  accessible-name channel design 3.3 requires). Class-A consumers must keep their GtkToolbar host
  with the ``small-button`` style class and stay built via ``weld_toolbar(...)``; Class-B consumers
  must stay built via ``weld_button(...)``. Where a consumer additionally sets an explicit
  accessible name, that call must remain. Comments/raw strings are stripped before every C++
  assertion.
* ``shared_parts`` -- the ``pushbutton``/``Entire`` part must keep exactly its ``extra=action`` /
  ``extra=flat`` state set (no undeclared icon-only state may silently appear, or the Class-B
  fallback classification goes stale), and the ``toolbar``/``Button`` part must stay resolvable.
  definition.xml is read-only.
* closed-world scan -- an independent ``.ui`` walk (git ls-files, falling back to a filesystem
  walk) finds every icon-only ``GtkButton`` / ``GtkToolButton`` whose glyph is the shared
  ``window-close-symbolic``; the discovered set must equal the four pinned consumers plus the one
  excluded candidate (deck.ui btn_close, a sidebar-deck close). A new unclassified window-close
  icon button fails closed; a pinned/excluded entry the scanner no longer sees fails closed.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, icon-button
pixels, or runtime interaction are claimed. It does not add the missing native icon-button part;
it only proves which existing shared part each real consumer falls back to today.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/icon-button-contract.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

ICON_BUTTON_CLASSES = ("GtkButton", "GtkToolButton")
IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git", ".worktrees", "autom4te.cache", "build", "external", "extras",
        "helpcontent2", "icon-themes", "instdir", "solver", "translations", "workdir",
    }
)


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# IO / source hygiene
# --------------------------------------------------------------------------------------------------
CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def _strip_cpp(source: str) -> str:
    source = CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for consumer in registry.get("consumers", []) or []:
        if isinstance(consumer, dict):
            for key in ("ui_path", "impl_source"):
                value = consumer.get(key)
                if isinstance(value, str):
                    paths.add(value)
    for excluded in registry.get("excluded_candidates", []) or []:
        if isinstance(excluded, dict) and isinstance(excluded.get("ui_path"), str):
            paths.add(excluded["ui_path"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


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
# .ui object helpers
# --------------------------------------------------------------------------------------------------
def _object_by_id(root: ET.Element, oid: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("id") == oid:
            return obj
    return None


def _direct_properties(obj: ET.Element) -> dict[str, ET.Element]:
    return {p.get("name"): p for p in obj.findall("property")}


def _has_label(obj: ET.Element) -> bool:
    prop = _direct_properties(obj).get("label")
    return prop is not None and bool((prop.text or "").strip())


def _image_child_icon(obj: ET.Element, image_id: str) -> str | None:
    for image in obj.iter("object"):
        if image.get("class") == "GtkImage" and image.get("id") == image_id:
            icon = _direct_properties(image).get("icon-name")
            return (icon.text or "").strip() if icon is not None else None
    return None


def _effective_close_icon(obj: ET.Element, close_glyph: str) -> bool:
    """True if ``obj`` is an icon-only button whose effective glyph is ``close_glyph``."""

    if obj.get("class") not in ICON_BUTTON_CLASSES:
        return False
    if _has_label(obj):
        return False
    props = _direct_properties(obj)
    direct = props.get("icon-name")
    if direct is not None and (direct.text or "").strip() == close_glyph:
        return True
    for image in obj.iter("object"):
        if image.get("class") == "GtkImage":
            icon = _direct_properties(image).get("icon-name")
            if icon is not None and (icon.text or "").strip() == close_glyph:
                return True
    return False


# --------------------------------------------------------------------------------------------------
# consumer validation
# --------------------------------------------------------------------------------------------------
def _validate_consumer(
    consumer: Mapping[str, Any], close_glyph: str, contents: Mapping[str, str], errors: list[str]
) -> None:
    cid = consumer.get("id", "?")
    context = f"consumers[{cid}]"
    ui_path = consumer.get("ui_path")
    object_id = consumer.get("object_id")
    widget_class = consumer.get("widget_class")
    if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(widget_class, str)):
        errors.append(f"{context}:ui_path/object_id/widget_class must be strings")
        return

    root = _parse_xml(contents.get(ui_path), context, errors)
    if root is None:
        return
    obj = _object_by_id(root, object_id)
    if obj is None:
        errors.append(f"{context}:object id={object_id!r} missing in {ui_path}")
        return
    if obj.get("class") != widget_class:
        errors.append(
            f"{context}:object {object_id!r} class is {obj.get('class')!r}, expected {widget_class!r}"
        )
    if _has_label(obj):
        errors.append(f"{context}:object {object_id!r} gained a label (no longer icon-only)")

    # Icon channel.
    icon = consumer.get("icon")
    if not isinstance(icon, dict):
        errors.append(f"{context}:icon:object required")
    else:
        kind = icon.get("kind")
        name = icon.get("name")
        if kind == "toolbutton-attr":
            actual = _direct_properties(obj).get("icon-name")
            actual_text = (actual.text or "").strip() if actual is not None else None
            if actual_text != name:
                errors.append(
                    f"{context}:icon:toolbutton icon-name is {actual_text!r}, expected {name!r}"
                )
        elif kind == "image-child":
            image_id = icon.get("id")
            if not isinstance(image_id, str):
                errors.append(f"{context}:icon:image-child requires an id")
            else:
                actual_text = _image_child_icon(obj, image_id)
                if actual_text != name:
                    errors.append(
                        f"{context}:icon:GtkImage {image_id!r} icon-name is {actual_text!r}, "
                        f"expected {name!r}"
                    )
        else:
            errors.append(f"{context}:icon:kind must be 'toolbutton-attr' or 'image-child'")

    # Accessible-name channel: a non-empty translatable tooltip-text at the pinned context.
    tooltip = _direct_properties(obj).get("tooltip-text")
    expected_context = consumer.get("tooltip_context")
    if tooltip is None or not (tooltip.text or "").strip():
        errors.append(
            f"{context}:tooltip-text missing/empty on {object_id!r} "
            "(the sole accessible-name channel per design 3.3)"
        )
    elif isinstance(expected_context, str) and tooltip.get("context") != expected_context:
        errors.append(
            f"{context}:tooltip-text context is {tooltip.get('context')!r}, expected "
            f"{expected_context!r}"
        )

    # Class-A toolbar hosting + small-button style class.
    host_class = consumer.get("host_class")
    if host_class == "A-toolbar":
        toolbar_id = consumer.get("toolbar_id")
        style_class = consumer.get("style_class")
        toolbar = _object_by_id(root, toolbar_id) if isinstance(toolbar_id, str) else None
        if toolbar is None or toolbar.get("class") != "GtkToolbar":
            errors.append(f"{context}:Class-A GtkToolbar id={toolbar_id!r} missing in {ui_path}")
        else:
            if _object_by_id(toolbar, object_id) is None:
                errors.append(
                    f"{context}:{object_id!r} is no longer hosted inside GtkToolbar {toolbar_id!r} "
                    "(Class-A toolbar hosting lost)"
                )
            classes = {c.get("name") for c in toolbar.iter("class")}
            if isinstance(style_class, str) and style_class not in classes:
                errors.append(
                    f"{context}:GtkToolbar {toolbar_id!r} lost the {style_class!r} style class"
                )

    # weld binding + explicit accessible name in the owning .cxx.
    impl_rel = consumer.get("impl_source")
    weld = consumer.get("weld_binding")
    impl_text = contents.get(impl_rel) if isinstance(impl_rel, str) else None
    if impl_text is None:
        errors.append(f"{context}:impl_source file missing: {impl_rel}")
        return
    code = _strip_cpp(impl_text)
    if isinstance(weld, str) and weld not in code:
        errors.append(
            f"{context}:weld binding {weld!r} missing from real code in {impl_rel} "
            "(host build path drifted -- Class A must stay weld_toolbar, Class B weld_button)"
        )
    if consumer.get("accessible_name_source") == "explicit+tooltip":
        marker = consumer.get("accessible_name_marker")
        if isinstance(marker, str) and marker not in code:
            errors.append(
                f"{context}:explicit set_accessible_name marker {marker!r} missing from {impl_rel}"
            )


# --------------------------------------------------------------------------------------------------
# shared native parts (definition.xml)
# --------------------------------------------------------------------------------------------------
def _validate_shared_parts(root: ET.Element, shared: Any, errors: list[str]) -> None:
    if not isinstance(shared, dict):
        errors.append("shared_parts:object required")
        return

    push = shared.get("pushbutton")
    if isinstance(push, dict):
        control = root.find(push.get("control", "pushbutton"))
        part = None
        if control is not None:
            for candidate in control.findall("part"):
                if candidate.get("value") == push.get("part", "Entire"):
                    part = candidate
                    break
        if part is None:
            errors.append("shared_parts:pushbutton:Entire part missing in definition.xml")
        else:
            found_extras = sorted(
                {s.get("extra") for s in part.findall("state") if s.get("extra") is not None}
            )
            allowed = sorted(push.get("allowed_extras", []) or [])
            if found_extras != allowed:
                errors.append(
                    f"shared_parts:pushbutton:extra values are {found_extras}, expected {allowed} "
                    "(a dedicated icon-only state appeared/vanished -- Class-B fallback stale)"
                )
    else:
        errors.append("shared_parts:pushbutton:object required")

    tb = shared.get("toolbar_button")
    if isinstance(tb, dict):
        control = root.find(tb.get("control", "toolbar"))
        part = None
        if control is not None:
            for candidate in control.findall("part"):
                if candidate.get("value") == tb.get("part", "Button"):
                    part = candidate
                    break
        if part is None:
            errors.append("shared_parts:toolbar_button:toolbar/Button part missing in definition.xml")
        elif part.find("state") is None:
            errors.append("shared_parts:toolbar_button:toolbar/Button has no <state>")
    else:
        errors.append("shared_parts:toolbar_button:object required")


# --------------------------------------------------------------------------------------------------
# closed-world scan
# --------------------------------------------------------------------------------------------------
def _tracked_ui_files(repo_root: Path) -> list[Path]:
    """Independent .ui enumeration: git ls-files, falling back to a filtered filesystem walk."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--", "*.ui"],
            capture_output=True, text=True, check=True,
        )
        rels = [r for r in result.stdout.split("\0") if r.strip()]
        if rels:
            return [repo_root / r for r in rels]
    except (OSError, subprocess.CalledProcessError):
        pass
    walked: list[Path] = []
    for source in repo_root.rglob("*.ui"):
        rel = source.relative_to(repo_root)
        if any(part in IGNORED_DIRECTORY_NAMES for part in rel.parts):
            continue
        walked.append(source)
    return walked


def _discover_close_icon_buttons(
    repo_root: Path, close_glyph: str, errors: list[str]
) -> set[tuple[str, str]]:
    discovered: set[tuple[str, str]] = set()
    for source in _tracked_ui_files(repo_root):
        try:
            rel = source.relative_to(repo_root).as_posix()
        except ValueError:
            continue
        try:
            root = ET.parse(source).getroot()
        except (ET.ParseError, OSError):
            continue
        for obj in root.iter("object"):
            oid = obj.get("id")
            if oid and _effective_close_icon(obj, close_glyph):
                discovered.add((rel, oid))
    return discovered


def _validate_closed_world(
    registry: Mapping[str, Any], repo_root: Path, errors: list[str]
) -> None:
    close_glyph = registry.get("close_glyph")
    if not isinstance(close_glyph, str) or not close_glyph:
        errors.append("registry:close_glyph:non-empty string required")
        return

    classified: dict[tuple[str, str], str] = {}
    for consumer in registry.get("consumers", []) or []:
        if isinstance(consumer, dict):
            key = (consumer.get("ui_path"), consumer.get("object_id"))
            if isinstance(key[0], str) and isinstance(key[1], str):
                classified[key] = f"consumer[{consumer.get('id')}]"
    for excluded in registry.get("excluded_candidates", []) or []:
        if isinstance(excluded, dict):
            key = (excluded.get("ui_path"), excluded.get("object_id"))
            if isinstance(key[0], str) and isinstance(key[1], str):
                classified[key] = f"excluded[{excluded.get('category')}]"

    discovered = _discover_close_icon_buttons(repo_root, close_glyph, errors)

    for key in sorted(discovered - set(classified)):
        errors.append(
            f"closed_world:unclassified {close_glyph} icon button {key[0]}#{key[1]} "
            "(register it as a consumer or an excluded candidate)"
        )
    for key in sorted(set(classified) - discovered):
        errors.append(
            f"closed_world:{classified[key]} {key[0]}#{key[1]} no longer matches the scanner "
            "(the icon button lost its window-close glyph, gained a label, or was removed)"
        )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(
    registry: Mapping[str, Any], contents: Mapping[str, str], repo_root: Path = REPOSITORY
) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-icon-button-composition":
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

    close_glyph = registry.get("close_glyph")
    consumers = registry.get("consumers")
    if not isinstance(consumers, list) or not consumers:
        errors.append("registry:consumers:non-empty array required")
    elif isinstance(close_glyph, str):
        for consumer in consumers:
            if isinstance(consumer, dict):
                _validate_consumer(consumer, close_glyph, contents, errors)
            else:
                errors.append("consumers:entry must be object")

    definition_root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    if definition_root is not None:
        _validate_shared_parts(definition_root, registry.get("shared_parts"), errors)

    _validate_closed_world(registry, repo_root, errors)

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents, repo_root)
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
        print(f"Icon-button composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Icon-button composition contract passed: pinned "
        f"{len(registry['consumers'])} standalone window-close icon buttons (2 Class-A toolbar, "
        "2 Class-B plain-button) to their shared native parts + tooltip accessible-name channel, "
        "and the closed-world scan classified every window-close icon-only button; "
        "runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
