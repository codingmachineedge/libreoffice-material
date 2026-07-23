#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for Writer's format tab-dialogs (WIN-WR-003).

``qa/windows-ui-contract/writer-format-dialogs.json`` pins the DIALOG-notebook
composition of Writer's four highest-traffic ``SfxTabDialogController``
left-icon-rail format dialogs -- Character (chardlg.cxx / characterproperties.ui),
Paragraph (pardlg.cxx / paradialog.ui), Table Properties (tabledlg.cxx /
tableproperties.ui) and Picture/Frame (frmdlg.cxx, one .cxx driving
FrameDialog/PictureDialog/ObjectDialog via a runtime ``m_sDlgType`` string). None
carry a Material paint override, so the whole Material look is delivered by the
SHARED native left-icon-tab parts plus the weld/SfxTabDialogController framework.

This checker parses the real tree fail-closed:

* ``definition_parts`` / ``tab_style`` / ``tab_settings`` / ``metrics`` /
  ``palette_colors`` -- the shared native left-icon-tab part contract (the 8-state
  ``tabitem``, ``tabheader``/``tabpane``/``tabbody``, ``windowbackground``, the
  footer ``pushbutton`` states, ``frame``/Border, plus the tab colour routing,
  layout switches, metrics and both-palette roles) is validated ONCE. A renamed
  part, dropped state or token drift fails closed. definition.xml is read only.
* ``dialogs`` -- for each dialog: the owning .cxx must carry the controller bind
  and the pinned ``icon_prefix_marker`` (preserving the real RID_M vs RID_L
  divergence, never normalized); every ``ui_variant`` .ui must be a modal
  ``GtkDialog`` whose ``tabcontrol`` ``GtkNotebook`` is a left icon rail with the
  exact reset/ok/cancel/help footer; and every pinned ``AddTabPage`` page must
  exist as real (comment-stripped) source. NO page-order is asserted (the
  pardlg/frmdlg page sets are heavily runtime-conditional). A page with
  ``applies_when`` additionally requires its ``m_sDlgType == "..."`` guard in
  source; a ``ui_variant`` with ``applies_when`` requires the same guard.
* ``shared_pages`` -- the reused svx/cui Border / Area / Transparency pages are
  validated ONCE (each .ui root object exists and the .cxx bind marker is real)
  and cross-referenced by id from each dialog's pages, never duplicated.
* ``carveouts`` -- Mail Merge, References and Page Layout stay ``status:
  specified`` (out of this slice), never promoted to an implemented claim.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, tab-rail pixels or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/writer-format-dialogs.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

REQUIRED_DIALOG_IDS = {"character", "paragraph", "table", "picture-frame"}
VALID_ICON_PREFIXES = {"RID_M", "RID_L"}

STATE_ATTR_KEYS = (
    "enabled", "focused", "pressed", "rollover", "default", "selected",
    "button-value", "extra",
)
REQUIRED_SCHEMES = ("", "dark")


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _registry_paths(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = {DEFINITION_PATH}
    for dialog in registry.get("dialogs", []) or []:
        if not isinstance(dialog, dict):
            continue
        if isinstance(dialog.get("source"), str):
            paths.add(dialog["source"])
        for variant in dialog.get("ui_variants", []) or []:
            if isinstance(variant, dict) and isinstance(variant.get("ui_file"), str):
                paths.add(variant["ui_file"])
    for page in registry.get("shared_pages", []) or []:
        if not isinstance(page, dict):
            continue
        for key in ("bind_source", "page_ui"):
            if isinstance(page.get(key), str):
                paths.add(page[key])
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _registry_paths(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# C/C++ comment stripping (anchor on real code, never a comment)
# --------------------------------------------------------------------------------------------------
def _strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    state = "code"  # code | line | block | quote
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
        # state == "quote"
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


# --------------------------------------------------------------------------------------------------
# definition.xml lookups (shared native part cross-checks)
# --------------------------------------------------------------------------------------------------
def _parse_xml(text: str | None, label: str, errors: list[str]) -> ET.Element | None:
    if text is None:
        errors.append(f"{label}:file missing")
        return None
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{label}:unparseable xml:{error}")
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


def _child_value(root: ET.Element, container: str, name: str) -> str | None:
    holder = root.find(container)
    if holder is None:
        return None
    element = holder.find(name)
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


def _validate_part(root: ET.Element, declaration: Mapping[str, Any], errors: list[str]) -> None:
    control = declaration.get("control")
    part_name = declaration.get("part")
    if not isinstance(control, str) or not isinstance(part_name, str):
        errors.append("definition_parts:entry:control/part must be strings")
        return
    label = f"definition_parts:{control}/{part_name}"
    if root.find(control) is None:
        errors.append(f"{label}:<{control}> missing in definition.xml")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"{label}:part missing in definition.xml")
        return
    part_attrs = declaration.get("part_attrs")
    if isinstance(part_attrs, dict):
        for attr_key, expected in part_attrs.items():
            actual = part.get(attr_key)
            if actual != expected:
                errors.append(
                    f"{label}:part attribute drift: {attr_key} is {actual!r}, expected {expected!r}"
                )
    states = declaration.get("states")
    if not isinstance(states, list) or not states:
        errors.append(f"{label}:states non-empty array required")
        return
    for state_decl in states:
        if not isinstance(state_decl, dict):
            errors.append(f"{label}:state must be object")
            continue
        role = state_decl.get("role", "?")
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"{label}:{role} attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(f"{label}:{role} no <state> matching {attrs}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"{label}:{role} state has no rect/line")
            continue
        expected_element = state_decl.get("element", "rect")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(f"{label}:{role} element is <{drawing.tag}>, expected <{expected_element}>")
        tokens = state_decl.get("tokens", {})
        if not isinstance(tokens, dict):
            errors.append(f"{label}:{role} tokens must be object")
            continue
        for token_key, expected in tokens.items():
            actual = drawing.get(token_key)
            if actual != expected:
                errors.append(
                    f"{label}:{role} token drift: {token_key} is {actual!r}, expected {expected!r}"
                )


def _validate_definition(root: ET.Element, registry: Mapping[str, Any], errors: list[str]) -> None:
    parts = registry.get("definition_parts")
    if not isinstance(parts, list) or not parts:
        errors.append("registry:definition_parts:non-empty array required")
    else:
        for declaration in parts:
            if isinstance(declaration, dict):
                _validate_part(root, declaration, errors)
            else:
                errors.append("definition_parts:entry:object required")

    tab_style = registry.get("tab_style")
    if not isinstance(tab_style, dict) or not tab_style:
        errors.append("registry:tab_style:non-empty object required")
    else:
        for name, expected in tab_style.items():
            actual = _child_value(root, "style", name)
            if actual is None:
                errors.append(f"tab_style:{name} missing in definition.xml <style>")
            elif actual != expected:
                errors.append(f"tab_style:{name} is {actual!r}, expected {expected!r} (drift)")

    tab_settings = registry.get("tab_settings")
    if not isinstance(tab_settings, dict) or not tab_settings:
        errors.append("registry:tab_settings:non-empty object required")
    else:
        for name, expected in tab_settings.items():
            actual = _child_value(root, "settings", name)
            if actual is None:
                errors.append(f"tab_settings:{name} missing in definition.xml <settings>")
            elif actual != expected:
                errors.append(f"tab_settings:{name} is {actual!r}, expected {expected!r} (drift)")

    for metric in registry.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("metrics:entry:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("metrics:entry:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"metrics:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(f"metrics:{mname} is {actual!r}, expected {expected!r} (metric drift)")

    for role in registry.get("palette_colors", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                where = scheme or "light"
                errors.append(f"palette:@{role} missing from the {where} palette")


# --------------------------------------------------------------------------------------------------
# .ui composition (plain GtkBuilder, no namespace)
# --------------------------------------------------------------------------------------------------
def _find_object(root: ET.Element, object_id: str) -> ET.Element | None:
    for node in root.iter("object"):
        if node.get("id") == object_id:
            return node
    return None


def _ui_footer(root: ET.Element) -> list[dict[str, str]]:
    footer: list[dict[str, str]] = []
    for action_widgets in root.iter("action-widgets"):
        for widget in action_widgets.findall("action-widget"):
            footer.append(
                {"response": (widget.get("response") or ""), "widget": (widget.text or "").strip()}
            )
    return footer


def _ui_secondary_widgets(root: ET.Element) -> set[str]:
    secondary: set[str] = set()
    for child in root.iter("child"):
        obj = child.find("object")
        packing = child.find("packing")
        if obj is None or packing is None:
            continue
        widget_id = obj.get("id")
        if not widget_id:
            continue
        for prop in packing.findall("property"):
            if prop.get("name") == "secondary" and (prop.text or "").strip().lower() == "true":
                secondary.add(widget_id)
    return secondary


def _validate_variant_composition(
    context: str, root: ET.Element, variant: Mapping[str, Any], errors: list[str]
) -> None:
    dialog_id = variant.get("dialog_object")
    dialog = _find_object(root, dialog_id) if isinstance(dialog_id, str) else None
    if dialog is None:
        errors.append(f"{context}:root object {dialog_id!r} missing")
        return
    if dialog.get("class") != "GtkDialog":
        errors.append(f"{context}:{dialog_id} is not a GtkDialog")

    modal = None
    for prop in dialog.findall("property"):
        if prop.get("name") == "modal":
            modal = (prop.text or "").strip().lower() == "true"
    if variant.get("modal") is True and modal is not True:
        errors.append(f"{context}:dialog must declare modal=True")

    notebook_decl = variant.get("notebook")
    if not isinstance(notebook_decl, dict):
        errors.append(f"{context}:notebook object required")
    else:
        notebook = _find_object(root, notebook_decl.get("id"))
        if notebook is None or notebook.get("class") != "GtkNotebook":
            errors.append(f"{context}:notebook {notebook_decl.get('id')!r} GtkNotebook missing")
        else:
            props = {p.get("name"): (p.text or "").strip() for p in notebook.findall("property")}
            if props.get("tab-pos") != notebook_decl.get("tab_pos"):
                errors.append(
                    f"{context}:notebook tab-pos is {props.get('tab-pos')!r}, expected "
                    f"{notebook_decl.get('tab_pos')!r} (the left icon rail must be preserved)"
                )
            # group-name: JSON null means the attribute must be absent.
            if props.get("group-name") != notebook_decl.get("group_name"):
                errors.append(
                    f"{context}:notebook group-name is {props.get('group-name')!r}, expected "
                    f"{notebook_decl.get('group_name')!r}"
                )

    expected_footer = variant.get("footer")
    if not isinstance(expected_footer, list) or not expected_footer:
        errors.append(f"{context}:footer non-empty array required")
        return
    actual_footer = _ui_footer(root)
    secondary = _ui_secondary_widgets(root)
    if len(actual_footer) != len(expected_footer):
        errors.append(
            f"{context}:footer length {len(actual_footer)} != pinned {len(expected_footer)} "
            "(an action-widget was added or removed)"
        )
    for index, want in enumerate(expected_footer):
        if index >= len(actual_footer):
            break
        got = actual_footer[index]
        if got.get("response") != want.get("response") or got.get("widget") != want.get("widget"):
            errors.append(
                f"{context}:footer[{index}] drift: pinned {want.get('widget')}({want.get('response')}) "
                f"but found {got.get('widget')}({got.get('response')})"
            )
            continue
        want_secondary = bool(want.get("secondary"))
        got_secondary = want.get("widget") in secondary
        if want_secondary != got_secondary:
            errors.append(
                f"{context}:footer[{index}] {want.get('widget')} secondary flag is "
                f"{got_secondary}, expected {want_secondary}"
            )


# --------------------------------------------------------------------------------------------------
# Dialog / page validation
# --------------------------------------------------------------------------------------------------
def _validate_dialogs(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    stripped: dict[str, str | None] = {}

    def code(rel: str | None) -> str | None:
        if not isinstance(rel, str):
            return None
        if rel not in stripped:
            text = contents.get(rel)
            stripped[rel] = _strip_comments(text) if text is not None else None
        return stripped[rel]

    shared_ids = {
        p.get("id")
        for p in registry.get("shared_pages", []) or []
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    }

    dialogs = registry.get("dialogs")
    if not isinstance(dialogs, list) or not dialogs:
        errors.append("registry:dialogs:non-empty array required")
        return
    seen: set[str] = set()
    for dialog in dialogs:
        if not isinstance(dialog, dict):
            errors.append("dialogs:entry:object required")
            continue
        did = dialog.get("id")
        if not isinstance(did, str) or not did:
            errors.append("dialogs:entry:id:non-empty string required")
            continue
        where = f"dialogs[{did}]"
        if did in seen:
            errors.append(f"{where}:duplicate id")
        seen.add(did)

        source_path = dialog.get("source")
        source_code = code(source_path)
        if source_code is None:
            errors.append(f"{where}:source {source_path} missing")
            continue

        bind = dialog.get("controller_bind")
        if isinstance(bind, str) and bind not in source_code:
            errors.append(f"{where}:controller bind missing in code ({bind})")

        icon_prefix = dialog.get("icon_prefix")
        if icon_prefix not in VALID_ICON_PREFIXES:
            errors.append(f"{where}:icon_prefix must be one of {sorted(VALID_ICON_PREFIXES)}")
        prefix_marker = dialog.get("icon_prefix_marker")
        if isinstance(prefix_marker, str):
            if prefix_marker not in source_code:
                errors.append(
                    f"{where}:icon_prefix_marker missing in code ({prefix_marker}) -- the real "
                    "RID_M vs RID_L divergence must be preserved, never normalized"
                )
        else:
            errors.append(f"{where}:icon_prefix_marker string required")

        variants = dialog.get("ui_variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{where}:ui_variants:non-empty array required")
        else:
            for variant in variants:
                if not isinstance(variant, dict):
                    errors.append(f"{where}:ui_variant:object required")
                    continue
                ui_file = variant.get("ui_file")
                vlabel = f"{where}:variant[{ui_file}]"
                ui_root = _parse_xml(
                    contents.get(ui_file) if isinstance(ui_file, str) else None, vlabel, errors
                )
                if ui_root is not None:
                    _validate_variant_composition(vlabel, ui_root, variant, errors)
                applies = variant.get("applies_when")
                if isinstance(applies, str):
                    guard = f'm_sDlgType == "{applies}"'
                    if guard not in source_code:
                        errors.append(
                            f"{vlabel}:applies_when guard missing in code ({guard})"
                        )

        pages = dialog.get("tab_pages")
        if not isinstance(pages, list) or not pages:
            errors.append(f"{where}:tab_pages:non-empty array required")
            continue
        page_ids: set[str] = set()
        for page in pages:
            if not isinstance(page, dict):
                errors.append(f"{where}:page:object required")
                continue
            pid = page.get("id")
            if not isinstance(pid, str) or not pid:
                errors.append(f"{where}:page:id:non-empty string required")
                continue
            plabel = f"{where}:page[{pid}]"
            if pid in page_ids:
                errors.append(f"{plabel}:duplicate page id")
            page_ids.add(pid)
            marker = page.get("add_marker")
            if isinstance(marker, str):
                if marker not in source_code:
                    errors.append(f"{plabel}:AddTabPage marker missing in code ({marker})")
            else:
                errors.append(f"{plabel}:add_marker string required")
            applies = page.get("applies_when")
            if isinstance(applies, str):
                guard = f'm_sDlgType == "{applies}"'
                if guard not in source_code:
                    errors.append(f"{plabel}:applies_when guard missing in code ({guard})")
            shared = page.get("shared_page")
            if shared is not None and shared not in shared_ids:
                errors.append(f"{plabel}:shared_page {shared!r} not declared in shared_pages")

    missing = REQUIRED_DIALOG_IDS - seen
    if missing:
        errors.append(f"registry:dialogs:missing required {', '.join(sorted(missing))}")


def _validate_shared_pages(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    pages = registry.get("shared_pages")
    if not isinstance(pages, list) or not pages:
        errors.append("registry:shared_pages:non-empty array required")
        return
    seen: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            errors.append("shared_pages:entry:object required")
            continue
        pid = page.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append("shared_pages:entry:id:non-empty string required")
            continue
        where = f"shared_pages[{pid}]"
        if pid in seen:
            errors.append(f"{where}:duplicate id")
        seen.add(pid)
        bind_source = page.get("bind_source")
        bind_text = contents.get(bind_source) if isinstance(bind_source, str) else None
        bind_marker = page.get("bind_marker")
        if bind_text is None:
            errors.append(f"{where}:bind_source {bind_source} missing")
        elif isinstance(bind_marker, str) and bind_marker not in _strip_comments(bind_text):
            errors.append(f"{where}:bind marker missing in code ({bind_marker})")
        page_ui = page.get("page_ui")
        root_id = page.get("page_root_id")
        page_root = _parse_xml(
            contents.get(page_ui) if isinstance(page_ui, str) else None, f"{where}:page_ui", errors
        )
        if page_root is not None:
            if not isinstance(root_id, str) or _find_object(page_root, root_id) is None:
                errors.append(f"{where}:page root object {root_id!r} missing in {page_ui}")


def _validate_carveouts(registry: Mapping[str, Any], errors: list[str]) -> None:
    carveouts = registry.get("carveouts")
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("registry:carveouts:non-empty object required")
        return
    for name, block in carveouts.items():
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' (out-of-slice surfaces must never "
                "be promoted to an implemented claim)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-writer-format-dialogs-composition":
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

    root = _parse_xml(contents.get(DEFINITION_PATH), "definition", errors)
    if root is not None:
        _validate_definition(root, registry, errors)

    _validate_dialogs(registry, contents, errors)
    _validate_shared_pages(registry, contents, errors)
    _validate_carveouts(registry, errors)
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
        print(f"Writer format dialogs composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    dialogs = registry.get("dialogs", [])
    shared = registry.get("shared_pages", [])
    print(
        "Writer format dialogs composition contract passed: "
        f"{len(dialogs)} left-icon-rail tab-dialogs (Character/Paragraph/Table/Picture-Frame) over "
        "the shared native tabitem/tabheader/tabpane/tabbody/pushbutton/frame parts, "
        f"{len(shared)} shared svx/cui pages validated once, the RID_M/RID_L icon-prefix divergence "
        "preserved, and Mail Merge/References/Page Layout carved out spec-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
