#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the PDF export tabbed dialog (WIN-SYS-002).

``qa/windows-ui-contract/pdf-export-dialog.json`` pins the PDF options dialog composition from
docs/design/08-dialogs.md 8.6. The dialog is a data-driven SfxTabDialogController whose Material
look is delivered entirely by shared vcl parts already in definition.xml, so the M-scope is
*pinning composition*, never re-drawing controls. This checker parses the real tree fail-closed:

* ``native_parts`` -- the ``tabitem``/Entire eight-state part (radius ``@corner-pill``), the
  ``tabheader``/``tabpane``/``tabbody`` strip+content parts, ``windowbackground``/BackgroundDialog,
  and ``frame``/Border that the tabbed dialog resolves through must exist in definition.xml with the
  exact fill/stroke/stroke-width/radius tokens, every declared metric (@height-tab, @space-tab-inline,
  @corner-pill, @corner-container) must carry its exact value, and every referenced palette role must
  resolve in *both* the light and dark palettes. A renamed part, dropped state, or token drift fails
  closed. definition.xml is read-only.
* ``notebook`` / ``footer`` -- pdfoptionsdialog.ui must carry the GtkNotebook ``tabcontrol`` at
  ``tab-pos=left`` and the footer action-widget order ok(-5) / cancel(-6) / help(-11), with the
  primary Export button (``E_xport``) marked has-default. A reorder or a lost default fails closed.
* ``tab_sequence`` / ``tab_pages`` -- impdialog.cxx must compose the tabs in the exact order
  general -> initialview -> userinterface -> links -> security -> digitalsignatures (verified by the
  ascending position of each ``AddTabPage(u"<id>"_ustr`` marker in comment-stripped source) with
  ``SetCurPageId`` on ``general``, and each tab must bind its Create class and its page .ui/root-id.
  Each page .ui must carry that root object id and its ordered GtkFrame group labels.
* ``modal_exclusions`` -- the input-collecting export dialogs (PdfOptionsDialog, WarnPDFDialog) must
  keep their native-exclusion (KeepModal) policy in dialog-notification-policy.csv (read-only).
* ``carveouts`` -- the tab-rail geometry, the security/signing per-field anatomy, and non-PDF export
  formats are build-dependent, so their ``status`` must stay ``specified`` and is never promoted.

It is source evidence only: ``runtime_verified`` is false throughout -- no native build, tab-rail
pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/pdf-export-dialog.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CSV_PATH = "qa/windows-ui-contract/dialog-notification-policy.csv"

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
    paths: set[str] = {DEFINITION_PATH, CSV_PATH}
    for key in ("impl_source", "dialog_ui"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    for page in registry.get("tab_pages", []) or []:
        if isinstance(page, dict) and isinstance(page.get("ui_source"), str):
            paths.add(page["ui_source"])
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


def _strip_xml_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


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
# definition.xml part validation
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


def _validate_tabitem(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    control = decl.get("control")
    part_name = decl.get("part")
    if not (isinstance(control, str) and isinstance(part_name, str)):
        errors.append("native_parts:tabitem:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"native_parts:tabitem:{control}/{part_name} missing in definition.xml")
        return
    for attr, expected in (decl.get("part_attrs") or {}).items():
        if part.get(attr) != expected:
            errors.append(
                f"native_parts:tabitem:part attr {attr} is {part.get(attr)!r}, expected {expected!r}"
            )
    states = decl.get("states")
    if not isinstance(states, list) or not states:
        errors.append("native_parts:tabitem:states non-empty array required")
        return
    for state_decl in states:
        role = state_decl.get("role", "?") if isinstance(state_decl, dict) else "?"
        if not isinstance(state_decl, dict):
            errors.append("native_parts:tabitem:state must be object")
            continue
        attrs = state_decl.get("attrs", {})
        if not isinstance(attrs, dict):
            errors.append(f"native_parts:tabitem:{role}:attrs must be object")
            continue
        state = _match_state(part, attrs)
        if state is None:
            errors.append(f"native_parts:tabitem:{role}:no <state> matching {attrs}")
            continue
        drawing = _first_drawing_child(state)
        if drawing is None:
            errors.append(f"native_parts:tabitem:{role}:state has no rect/line")
            continue
        expected_element = state_decl.get("element")
        if isinstance(expected_element, str) and drawing.tag != expected_element:
            errors.append(
                f"native_parts:tabitem:{role}:element is <{drawing.tag}>, expected <{expected_element}>"
            )
        _check_tokens(f"native_parts:tabitem:{role}", drawing, state_decl.get("tokens", {}), errors)


def _validate_simple_part(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    name = decl.get("name", "?")
    control = decl.get("control")
    part_name = decl.get("part")
    if not (isinstance(control, str) and isinstance(part_name, str)):
        errors.append(f"native_parts:{name}:control/part must be strings")
        return
    part = _find_part(root, control, part_name)
    if part is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} missing in definition.xml")
        return
    attrs = decl.get("attrs", {}) if isinstance(decl.get("attrs"), dict) else {}
    state = _match_state(part, attrs)
    if state is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} no <state> matching {attrs}")
        return
    drawing = _first_drawing_child(state)
    if drawing is None:
        errors.append(f"native_parts:{name}:{control}/{part_name} state has no rect/line")
        return
    expected_element = decl.get("element")
    if isinstance(expected_element, str) and drawing.tag != expected_element:
        errors.append(
            f"native_parts:{name}:element is <{drawing.tag}>, expected <{expected_element}>"
        )
    _check_tokens(f"native_parts:{name}", drawing, decl.get("tokens", {}), errors)


def _validate_native_parts(root: ET.Element, parts: Mapping[str, Any], errors: list[str]) -> None:
    tabitem = parts.get("tabitem")
    if isinstance(tabitem, dict):
        _validate_tabitem(root, tabitem, errors)
    else:
        errors.append("native_parts:tabitem:object required")

    simple = parts.get("simple_parts")
    if not isinstance(simple, list) or not simple:
        errors.append("native_parts:simple_parts:non-empty array required")
    else:
        for decl in simple:
            if isinstance(decl, dict):
                _validate_simple_part(root, decl, errors)
            else:
                errors.append("native_parts:simple_parts:entry must be object")

    for metric in parts.get("metrics", []) or []:
        if not isinstance(metric, dict):
            errors.append("native_parts:metric:object required")
            continue
        mname = metric.get("name")
        container = metric.get("container")
        tag = metric.get("tag")
        expected = metric.get("value")
        if not (isinstance(mname, str) and isinstance(container, str) and isinstance(tag, str)):
            errors.append("native_parts:metric:name/container/tag must be strings")
            continue
        actual = _named_value(root, container, tag, mname)
        if actual is None:
            errors.append(f"native_parts:metric:{mname} missing in definition.xml <{container}>")
        elif actual != expected:
            errors.append(
                f"native_parts:metric:{mname} is {actual!r}, expected {expected!r} (metric drift)"
            )

    for role in parts.get("palette_roles", []) or []:
        if not isinstance(role, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, role) is None:
                label = scheme or "light"
                errors.append(f"native_parts:palette:@{role} missing from the {label} palette")


# --------------------------------------------------------------------------------------------------
# pdfoptionsdialog.ui composition
# --------------------------------------------------------------------------------------------------
def _iter_objects(root: ET.Element) -> list[ET.Element]:
    return list(root.iter("object"))


def _object_by_id(root: ET.Element, cls: str, oid: str) -> ET.Element | None:
    for obj in _iter_objects(root):
        if obj.get("class") == cls and obj.get("id") == oid:
            return obj
    return None


def _direct_property(obj: ET.Element, name: str) -> ET.Element | None:
    for prop in obj.findall("property"):
        if prop.get("name") == name:
            return prop
    return None


def _validate_notebook(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    oid = decl.get("id")
    if not isinstance(oid, str):
        errors.append("notebook:id:string required")
        return
    notebook = _object_by_id(root, "GtkNotebook", oid)
    if notebook is None:
        errors.append(f"notebook:GtkNotebook id={oid!r} missing in pdfoptionsdialog.ui")
        return
    expected_pos = decl.get("tab_pos")
    if isinstance(expected_pos, str):
        prop = _direct_property(notebook, "tab-pos")
        actual = prop.text if prop is not None else None
        if actual != expected_pos:
            errors.append(
                f"notebook:tab-pos is {actual!r}, expected {expected_pos!r} (icon rail moved)"
            )


def _validate_footer(root: ET.Element, decl: Mapping[str, Any], errors: list[str]) -> None:
    action_holder = None
    for element in root.iter("action-widgets"):
        action_holder = element
        break
    expected = decl.get("action_widgets")
    if not isinstance(expected, list) or not expected:
        errors.append("footer:action_widgets:non-empty array required")
        return
    if action_holder is None:
        errors.append("footer:action-widgets block missing in pdfoptionsdialog.ui")
        return
    actual = [
        {"response": aw.get("response"), "id": (aw.text or "").strip()}
        for aw in action_holder.findall("action-widget")
    ]
    if len(actual) != len(expected):
        errors.append(
            f"footer:action_widgets length {len(actual)} != pinned {len(expected)} "
            "(a footer button was added or removed)"
        )
    for index, want in enumerate(expected):
        if index >= len(actual):
            break
        got = actual[index]
        if got.get("id") != want.get("id") or got.get("response") != want.get("response"):
            errors.append(
                f"footer:action_widgets[{index}] drift: pinned "
                f"{want.get('id')}({want.get('response')}) but found "
                f"{got.get('id')}({got.get('response')})"
            )

    primary = decl.get("primary")
    if not isinstance(primary, dict):
        errors.append("footer:primary:object required")
        return
    pid = primary.get("id")
    button = _object_by_id(root, "GtkButton", pid) if isinstance(pid, str) else None
    if button is None:
        errors.append(f"footer:primary:GtkButton id={pid!r} missing in pdfoptionsdialog.ui")
        return
    if primary.get("has_default") is True:
        prop = _direct_property(button, "has-default")
        if prop is None or prop.text != "True":
            errors.append("footer:primary:Export button must be has-default=True")
    expected_label = primary.get("label")
    if isinstance(expected_label, str):
        prop = _direct_property(button, "label")
        actual = prop.text if prop is not None else None
        if actual != expected_label:
            errors.append(
                f"footer:primary:label is {actual!r}, expected {expected_label!r} "
                "(primary action is not Export)"
            )


# --------------------------------------------------------------------------------------------------
# impdialog.cxx tab composition + page .ui bindings
# --------------------------------------------------------------------------------------------------
def _validate_tab_composition(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    impl_rel = registry.get("impl_source")
    impl_text = contents.get(impl_rel) if isinstance(impl_rel, str) else None
    if impl_text is None:
        errors.append("tab_sequence:impl_source file missing")
        code = ""
    else:
        code = _strip_comments(impl_text)

    sequence = registry.get("tab_sequence")
    if not isinstance(sequence, list) or not sequence:
        errors.append("tab_sequence:non-empty array required")
        sequence = []

    # Ordered AddTabPage markers -- ascending source position proves the tab order.
    last_index = -1
    last_id = None
    for tab_id in sequence:
        marker = f'AddTabPage(u"{tab_id}"_ustr'
        pos = code.find(marker)
        if pos < 0:
            errors.append(f"tab_sequence:{marker!r} missing from real code in impdialog.cxx")
            continue
        if pos < last_index:
            errors.append(
                f"tab_sequence:tab {tab_id!r} is out of order relative to {last_id!r} "
                "(AddTabPage composition reordered)"
            )
        last_index = pos
        last_id = tab_id

    cur_page = registry.get("cur_page")
    if isinstance(cur_page, str):
        marker = f'SetCurPageId(u"{cur_page}"_ustr)'
        if marker not in code:
            errors.append(f"tab_sequence:{marker!r} missing (default page changed)")

    pages = registry.get("tab_pages")
    if not isinstance(pages, list) or not pages:
        errors.append("tab_pages:non-empty array required")
        return

    page_ids = {p.get("id") for p in pages if isinstance(p, dict)}
    if page_ids != set(sequence):
        errors.append(
            f"tab_pages:id set {sorted(x for x in page_ids if x)} does not match "
            f"tab_sequence {sorted(sequence)}"
        )

    for page in pages:
        if not isinstance(page, dict):
            errors.append("tab_pages:entry must be object")
            continue
        pid = page.get("id")
        context = f"tab_pages[{pid}]"

        # The Create factory must be bound to THIS tab's AddTabPage call (it also appears at its
        # own method definition, so a bare presence check would false-pass a broken wiring).
        create_class = page.get("create_class")
        if not isinstance(create_class, str) or not create_class:
            errors.append(f"{context}:create_class:non-empty string required")
        else:
            marker = f'AddTabPage(u"{pid}"_ustr'
            mpos = code.find(marker)
            window = code[mpos:mpos + 300] if mpos >= 0 else ""
            if create_class not in window:
                errors.append(
                    f"{context}:create_class {create_class!r} not bound to its AddTabPage call "
                    "(the tab's Create factory wiring drifted)"
                )

        ui_ref = page.get("ui_ref")
        root_id = page.get("root_id")
        if isinstance(ui_ref, str) and isinstance(root_id, str):
            binding = f'u"{ui_ref}"_ustr, u"{root_id}"_ustr'
            if binding not in code:
                errors.append(
                    f"{context}:page binding {binding!r} missing from real code "
                    "(the SfxTabPage .ui/root-id binding drifted)"
                )
        else:
            errors.append(f"{context}:ui_ref/root_id must be strings")

        # The page .ui must carry the root object id and its ordered group-frame labels.
        ui_source = page.get("ui_source")
        page_text = contents.get(ui_source) if isinstance(ui_source, str) else None
        if page_text is None:
            errors.append(f"{context}:ui_source file missing: {ui_source}")
            continue
        page_xml = _strip_xml_comments(page_text)
        if isinstance(root_id, str) and f'id="{root_id}"' not in page_xml:
            errors.append(f"{context}:root object id=\"{root_id}\" missing in {ui_source}")
        group_frames = page.get("group_frames")
        if not isinstance(group_frames, list) or not group_frames:
            errors.append(f"{context}:group_frames:non-empty array required")
            continue
        for literal in group_frames:
            if not isinstance(literal, str) or not literal:
                errors.append(f"{context}:group_frames:entry must be a non-empty string")
                continue
            if literal not in page_xml:
                errors.append(
                    f"{context}:group frame {literal!r} missing in {ui_source} "
                    "(a page grouping was removed or renamed)"
                )


# --------------------------------------------------------------------------------------------------
# shared CSV cross-check + carve-outs
# --------------------------------------------------------------------------------------------------
def _validate_modal_exclusions(
    exclusions: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(exclusions, list) or not exclusions:
        errors.append("modal_exclusions:non-empty array required")
        return
    csv_text = contents.get(CSV_PATH)
    if csv_text is None:
        errors.append(f"modal_exclusions:file missing: {CSV_PATH}")
        return
    rows = list(csv.reader(io.StringIO(csv_text)))
    policy_by_locator: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        if len(row) >= 4:
            policy_by_locator[(row[0], row[1])] = row[3]
    for index, exclusion in enumerate(exclusions):
        if not isinstance(exclusion, dict):
            errors.append(f"modal_exclusions[{index}]:object required")
            continue
        ui_path = exclusion.get("ui_path")
        object_id = exclusion.get("object_id")
        expected = exclusion.get("expected_policy")
        if not (isinstance(ui_path, str) and isinstance(object_id, str) and isinstance(expected, str)):
            errors.append(f"modal_exclusions[{index}]:ui_path/object_id/expected_policy must be strings")
            continue
        actual = policy_by_locator.get((ui_path, object_id))
        if actual is None:
            errors.append(
                f"modal_exclusions:{ui_path}::{object_id} absent from {CSV_PATH} "
                "(the export dialog is no longer registered)"
            )
        elif actual != expected:
            errors.append(
                f"modal_exclusions:{ui_path}::{object_id} policy is {actual!r}, expected "
                f"{expected!r} (the input-collecting export dialog left KeepModal)"
            )


def _validate_carveouts(carveouts: Any, errors: list[str]) -> None:
    if not isinstance(carveouts, dict) or not carveouts:
        errors.append("carveouts:non-empty object required")
        return
    for name in ("tab_rail_geometry", "security_field_anatomy", "non_pdf_export"):
        block = carveouts.get(name)
        if not isinstance(block, dict):
            errors.append(f"carveouts:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"carveouts:{name}:status must stay 'specified' "
                "(build-dependent; not promoted to an implemented claim)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-pdf-export-dialog-composition":
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
    native_parts = registry.get("native_parts")
    if isinstance(native_parts, dict):
        if definition_root is not None:
            _validate_native_parts(definition_root, native_parts, errors)
    else:
        errors.append("registry:native_parts:object required")

    dialog_rel = registry.get("dialog_ui")
    dialog_root = _parse_xml(
        contents.get(dialog_rel) if isinstance(dialog_rel, str) else None, "dialog_ui", errors
    )
    if dialog_root is not None:
        notebook = registry.get("notebook")
        if isinstance(notebook, dict):
            _validate_notebook(dialog_root, notebook, errors)
        else:
            errors.append("registry:notebook:object required")
        footer = registry.get("footer")
        if isinstance(footer, dict):
            _validate_footer(dialog_root, footer, errors)
        else:
            errors.append("registry:footer:object required")

    _validate_tab_composition(registry, contents, errors)
    _validate_modal_exclusions(registry.get("modal_exclusions"), contents, errors)
    _validate_carveouts(registry.get("carveouts"), errors)

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
        print(f"PDF export dialog contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "PDF export dialog contract passed: pinned the "
        f"{len(registry['tab_sequence'])}-tab PDF options composition (notebook + Export-default "
        "footer), each tab's Create class + page .ui/root-id + group frames, the native "
        "tabitem/tabpane/tabbody/frame parts at @corner-pill/@corner-container, and the "
        "KeepModal export exclusions; tab-rail geometry / signing anatomy / non-PDF formats "
        "carved out spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
