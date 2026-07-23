#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for Writer's review/collaboration surfaces (WIN-WR-005).

``qa/windows-ui-contract/writer-review-composition.json`` pins the composition of
Writer's three real, already-registered review surfaces:

* ``toolbar`` -- the Track Changes toolbar (changes.xml), registered as
  ``private:resource/toolbar/changes`` / UIName 'Track Changes' in
  WriterWindowState.xcu. Its ordered ``toolbaritem``/``toolbarseparator``
  composition must match exactly (a reorder/add/remove fails closed) and its
  ``design_core`` review commands must be present and visible.
* ``decks[writer.review.comments]`` -- the Comments sidebar deck: the Sidebar.xcu
  CommentsDeck/CommentsPanel Id/DeckId/ImplementationURL chain, the SwPanelFactory
  ``/CommentsPanel`` dispatch to ``CommentsPanel::Create``, and every weld id the
  CommentsPanel.cxx binds over commentspanel.ui + the per-thread Comment widget
  over commentwidget.ui (each weld marker in real code AND the id present in the
  matching .ui).
* ``decks[writer.review.manage-changes]`` -- the Manage Changes sidebar deck: the
  Sidebar.xcu SwManageChangesDeck/SwManageChangesPanel chain, the
  ``/ManageChangesPanel`` dispatch to SwRedlineAcceptPanel, its
  managechangessidebar.ui content-area weld, and the ``shared_mount`` proving
  Writer constructs ``SwRedlineAcceptDlg`` which mounts the SHARED svx control
  ``new SvxAcceptChgCtr(pContentArea)`` (not a Writer-private widget).

Every C++ source assertion runs against a comment-stripped copy; every .xcu
assertion runs against an XML-comment-stripped copy, so commented-out wiring
cannot satisfy the contract. It reuses the already-validated generic native
toolbar Button part (WIN-CA-001) and invents no new tokens. It is source evidence
only: ``runtime_verified`` is false throughout -- no native build, toolbar/deck
pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/writer-review-composition.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

TOOLBAR_NS = "{http://openoffice.org/2001/toolbar}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"

REQUIRED_DECK_IDS = {"writer.review.comments", "writer.review.manage-changes"}


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _without_xml_comments(source: str) -> str:
    return re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = set()
    toolbar = registry.get("toolbar")
    if isinstance(toolbar, dict):
        if isinstance(toolbar.get("file"), str):
            paths.add(toolbar["file"])
        reg = toolbar.get("registration")
        if isinstance(reg, dict) and isinstance(reg.get("source"), str):
            paths.add(reg["source"])
    for deck in registry.get("decks", []) or []:
        if not isinstance(deck, dict):
            continue
        reg = deck.get("registration")
        if isinstance(reg, dict) and isinstance(reg.get("source"), str):
            paths.add(reg["source"])
        factory = deck.get("factory")
        if isinstance(factory, dict) and isinstance(factory.get("source"), str):
            paths.add(factory["source"])
        for panel in deck.get("panels", []) or []:
            if not isinstance(panel, dict):
                continue
            for key in ("source", "ui_file"):
                if isinstance(panel.get(key), str):
                    paths.add(panel[key])
        mount = deck.get("shared_mount")
        if isinstance(mount, dict) and isinstance(mount.get("source"), str):
            paths.add(mount["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Toolbar composition
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


def _actual_toolbar_sequence(root: ET.Element) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    for child in root:
        tag = child.tag.split("}")[-1]
        if tag == "toolbaritem":
            visible = child.get(f"{TOOLBAR_NS}visible") != "false"
            sequence.append({"command": child.get(f"{XLINK_NS}href"), "visible": visible})
        elif tag == "toolbarseparator":
            sequence.append({"separator": True})
    return sequence


def _entry_repr(entry: Mapping[str, Any]) -> str:
    if entry.get("separator"):
        return "<separator>"
    return f"{entry.get('command')}(visible={entry.get('visible')})"


def _validate_toolbar(
    toolbar: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = toolbar.get("file")
    root = _parse_xml(
        contents.get(file_path) if isinstance(file_path, str) else None, "toolbar", errors
    )
    expected = toolbar.get("sequence")
    if not isinstance(expected, list) or not expected:
        errors.append("toolbar:sequence:non-empty array required")
    elif root is not None:
        actual = _actual_toolbar_sequence(root)
        if len(actual) != len(expected):
            errors.append(
                f"toolbar:sequence:length {len(actual)} != pinned {len(expected)} "
                "(a toolbar item or separator was added or removed)"
            )
        for index, want in enumerate(expected):
            if index >= len(actual):
                break
            got = actual[index]
            want_sep = bool(want.get("separator")) if isinstance(want, dict) else False
            got_sep = bool(got.get("separator"))
            if want_sep or got_sep:
                if want_sep != got_sep:
                    errors.append(
                        f"toolbar:sequence[{index}]:composition drift: pinned "
                        f"{_entry_repr(want)} but found {_entry_repr(got)}"
                    )
                continue
            if got.get("command") != want.get("command"):
                errors.append(
                    f"toolbar:sequence[{index}]:command drift: pinned {want.get('command')!r} "
                    f"but found {got.get('command')!r} (identity/order changed)"
                )
            elif bool(got.get("visible")) != bool(want.get("visible")):
                errors.append(
                    f"toolbar:sequence[{index}]:visibility drift for {want.get('command')}"
                )
        present = {e["command"] for e in actual if e.get("command")}
        visible = {e["command"] for e in actual if e.get("visible") and e.get("command")}
        core = toolbar.get("design_core")
        if not isinstance(core, list) or not core:
            errors.append("toolbar:design_core:non-empty array required")
        else:
            for command in core:
                if command not in present:
                    errors.append(f"toolbar:design_core:{command} absent from the toolbar")
                elif command not in visible:
                    errors.append(f"toolbar:design_core:{command} present but hidden")

    registration = toolbar.get("registration")
    if not isinstance(registration, dict):
        errors.append("toolbar:registration:object required")
        return
    source_path = registration.get("source")
    text = contents.get(source_path) if isinstance(source_path, str) else None
    if text is None:
        errors.append(f"toolbar:registration:source {source_path} missing")
        return
    xcu = _without_xml_comments(text)
    for marker in registration.get("markers", []) or []:
        if isinstance(marker, str) and marker not in xcu:
            errors.append(f"toolbar:registration:marker missing in {source_path} ({marker})")


# --------------------------------------------------------------------------------------------------
# Deck composition
# --------------------------------------------------------------------------------------------------
def _ui_ids(text: str | None) -> set[str]:
    if text is None:
        return set()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return set()
    return {node.get("id") for node in root.iter("object") if node.get("id")}


def _validate_deck(
    deck: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    sid = deck.get("surface_id")
    context = f"deck[{sid}]"

    if deck.get("status") != "source-declared":
        errors.append(f"{context}:status:must be source-declared")
    if not isinstance(deck.get("runtime_verified"), bool):
        errors.append(f"{context}:runtime_verified:boolean required")
    elif deck["runtime_verified"]:
        errors.append(f"{context}:runtime_verified:no runtime evidence exists; must be false")

    registration = deck.get("registration")
    if isinstance(registration, dict):
        source_path = registration.get("source")
        text = contents.get(source_path) if isinstance(source_path, str) else None
        if text is None:
            errors.append(f"{context}:registration:source {source_path} missing")
        else:
            xcu = _without_xml_comments(text)
            for marker in registration.get("markers", []) or []:
                if isinstance(marker, str) and marker not in xcu:
                    errors.append(f"{context}:registration:marker missing ({marker})")
    else:
        errors.append(f"{context}:registration:object required")

    factory = deck.get("factory")
    if isinstance(factory, dict):
        source_path = factory.get("source")
        text = contents.get(source_path) if isinstance(source_path, str) else None
        if text is None:
            errors.append(f"{context}:factory:source {source_path} missing")
        else:
            code = _without_cpp_comments(text)
            suffix = factory.get("resource_suffix")
            if isinstance(suffix, str):
                guard = f'rsResourceURL.endsWith("{suffix}")'
                if guard not in code:
                    errors.append(f"{context}:factory:dispatch missing ({guard})")
            else:
                errors.append(f"{context}:factory:resource_suffix string required")
            create_call = factory.get("create_call")
            if isinstance(create_call, str):
                if create_call not in code:
                    errors.append(f"{context}:factory:create call missing ({create_call})")
            else:
                errors.append(f"{context}:factory:create_call string required")
    else:
        errors.append(f"{context}:factory:object required")

    panels = deck.get("panels")
    if not isinstance(panels, list) or not panels:
        errors.append(f"{context}:panels:non-empty array required")
    else:
        for panel in panels:
            if not isinstance(panel, dict):
                errors.append(f"{context}:panel:object required")
                continue
            pname = panel.get("name", "?")
            plabel = f"{context}:panel[{pname}]"
            source_path = panel.get("source")
            src = contents.get(source_path) if isinstance(source_path, str) else None
            code = _without_cpp_comments(src) if src is not None else None
            if code is None:
                errors.append(f"{plabel}:source {source_path} missing")
            ui_ids = _ui_ids(contents.get(panel.get("ui_file")) if isinstance(panel.get("ui_file"), str) else None)
            ui_load = panel.get("ui_load")
            if isinstance(ui_load, str) and code is not None and ui_load not in code:
                errors.append(f"{plabel}:ui load marker missing in code ({ui_load})")
            for widget in panel.get("widgets", []) or []:
                if not isinstance(widget, dict):
                    errors.append(f"{plabel}:widget:object required")
                    continue
                wid = widget.get("id")
                marker = widget.get("weld_marker")
                if isinstance(marker, str) and code is not None and marker not in code:
                    errors.append(f"{plabel}:widget {wid}:weld marker missing in code ({marker})")
                if isinstance(wid, str) and panel.get("ui_file") and wid not in ui_ids:
                    errors.append(f"{plabel}:widget {wid}:id missing from {panel.get('ui_file')}")

    mount = deck.get("shared_mount")
    if isinstance(mount, dict):
        source_path = mount.get("source")
        src = contents.get(source_path) if isinstance(source_path, str) else None
        if src is None:
            errors.append(f"{context}:shared_mount:source {source_path} missing")
        else:
            code = _without_cpp_comments(src)
            for marker in mount.get("markers", []) or []:
                if isinstance(marker, str) and marker not in code:
                    errors.append(f"{context}:shared_mount:marker missing in code ({marker})")


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-writer-review-composition":
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

    toolbar = registry.get("toolbar")
    if isinstance(toolbar, dict):
        _validate_toolbar(toolbar, contents, errors)
    else:
        errors.append("registry:toolbar:object required")

    decks = registry.get("decks")
    if not isinstance(decks, list) or not decks:
        errors.append("registry:decks:non-empty array required")
        decks = []
    seen: set[str] = set()
    for index, deck in enumerate(decks):
        if not isinstance(deck, dict):
            errors.append(f"decks[{index}]:object required")
            continue
        sid = deck.get("surface_id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"decks[{index}]:surface_id:non-empty string required")
            continue
        if sid in seen:
            errors.append(f"deck[{sid}]:surface_id:duplicate")
        seen.add(sid)
        _validate_deck(deck, contents, errors)

    missing = REQUIRED_DECK_IDS - seen
    if missing:
        errors.append(f"registry:decks:missing required {', '.join(sorted(missing))}")

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
        print(f"Writer review composition contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    decks = registry.get("decks", [])
    print(
        "Writer review composition contract passed: the Track Changes toolbar sequence + "
        "WriterWindowState registration, and "
        f"{len(decks)} sidebar deck(s) (Comments + Manage Changes) with their Sidebar.xcu "
        "chains, SwPanelFactory dispatch, .ui-cross-checked weld bindings, and the shared "
        "SvxAcceptChgCtr mount are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
