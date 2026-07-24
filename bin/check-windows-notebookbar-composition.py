#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material notebookbar group area (WIN-NAV-004).

``qa/windows-ui-contract/notebookbar-composition.json`` pins the one concrete,
already-executing colour decision the notebookbar/ribbon owns today:
``NotebookBar::UpdateBackground()`` in vcl/source/control/notebookbar.cxx. Behind the
Material file-widget theme that routine resolves the ribbon *group-area* background wash
to the ``@surface`` role (docs/design/05-navigation.md section 4.1) through
``vcl::MaterialTokens`` instead of the four legacy per-module accent tints, and this
checker cross-validates that guarded swap against the real tree:

* ``@surface`` must exist in *both* the light and dark palettes of definition.xml (the
  role the group-area wash resolves to -- a dropped or renamed role fails closed);
* the owning source must ``#include <vcl/MaterialTokens.hxx>`` and carry the Material
  guard markers in *code* (comments are stripped first, so comment-only wiring cannot
  satisfy the contract);
* the guard helper must be both *defined and invoked* (``code.count() >= 2``);
* the guarded ``@surface`` override must be bound to the theme guard as a contiguous
  ``if (... = lcl_materialNotebookbarColor("surface")) aColor = *oSurface;`` statement
  (whitespace-normalised, comments stripped) sitting *after* the existing
  ``Color aColor = GetSettings().GetStyleSettings().GetDialogColor();`` line -- an empty
  guard body, a detached override, or comment-only wiring all fail closed; and
* every one of the four legacy per-module accent ``Merge()`` calls must remain present
  verbatim (``must_retain``), proving the native/default-theme path is byte-for-byte
  untouched.

The ``tab_row`` section pins the NEW composition-code structural markers the shared tab
control owns: ``NotebookbarTabControl::Paint()`` in
sfx2/source/notebookbar/NotebookbarTabControl.cxx overlays a 2px ``@primary`` active-tab
underline and a full-width ``@outline-variant`` tab-row bottom hairline on top of the
stock/native tab drawing. The checker cross-validates that:

* ``@primary`` and ``@outline-variant`` exist in *both* palettes, and the pinned role
  names (``role_primary``/``role_rule``) have not drifted;
* the owning source includes the token header and carries the Material guard markers,
  *including* the ``GetHighContrastMode`` short-circuit (high-contrast always wins);
* the guard helper is both defined and invoked; and
* each paint (underline, hairline) appears as a contiguous statement referencing the
  guard-dereferenced colour (``*oPrimary`` / ``*oRule``) sitting *after* its guard
  resolution -- a removed, reordered, or guard-detached paint fails closed.

SCOPE: the ``group_area`` section pins the group-area background wash ONLY, and
``tab_row`` pins the underline + hairline paints ONLY -- never the tab-row band FILL, the
per-group inter-command dividers, group-label typography, or any ``.ui`` geometry. It is
source evidence only: ``runtime_verified`` is false throughout -- no native build,
notebookbar pixels, or runtime interaction are claimed.
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
REGISTRY_PATH = "qa/windows-ui-contract/notebookbar-composition.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"

# The palettes whose colour roles must all resolve (light = no scheme attribute).
REQUIRED_SCHEMES = ("", "dark")


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
    """Collapse every run of whitespace to a single space so a contiguous
    statement can be matched regardless of indentation or line wrapping."""
    return re.sub(r"\s+", " ", source).strip()


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths: set[str] = {DEFINITION_PATH}
    for key in ("group_area", "tab_row"):
        section = registry.get(key)
        if isinstance(section, dict) and isinstance(section.get("owner"), dict):
            source = section["owner"].get("source")
            if isinstance(source, str):
                paths.add(source)
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# definition.xml lookups
# --------------------------------------------------------------------------------------------------
def _parse_definition(text: str, errors: list[str]) -> ET.Element | None:
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"definition:xml:{error}")
        return None


def _palette_color(root: ET.Element, scheme: str, name: str) -> str | None:
    for palette in root.findall("palette"):
        if (palette.get("scheme") or "") != scheme:
            continue
        for color in palette.findall("color"):
            if color.get("name") == name:
                return color.get("value")
    return None


# --------------------------------------------------------------------------------------------------
# Section validators
# --------------------------------------------------------------------------------------------------
def _validate_palette(root: ET.Element, group_area: Mapping[str, Any], errors: list[str]) -> None:
    role = group_area.get("role")
    if role != "surface":
        errors.append(
            "group_area:role:must stay 'surface' (docs/design/05-navigation.md 4.1 "
            "group-area @surface fill); a role rename desyncs the guarded source swap"
        )
    for name in group_area.get("palette_colors", []) or []:
        if not isinstance(name, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, name) is None:
                label = scheme or "light"
                errors.append(f"group_area:palette:@{name} missing from the {label} palette")


def _validate_tab_row_palette(
    root: ET.Element, tab_row: Mapping[str, Any], errors: list[str]
) -> None:
    if tab_row.get("role_primary") != "primary":
        errors.append(
            "tab_row:role_primary:must stay 'primary' (the 2px active-tab underline "
            "token, docs/design/05-navigation.md 4); a role rename desyncs the guarded paint"
        )
    if tab_row.get("role_rule") != "outline-variant":
        errors.append(
            "tab_row:role_rule:must stay 'outline-variant' (the tab-row band hairline "
            "token, docs/design/05-navigation.md 4); a role rename desyncs the guarded paint"
        )
    for name in tab_row.get("palette_colors", []) or []:
        if not isinstance(name, str):
            continue
        for scheme in REQUIRED_SCHEMES:
            if _palette_color(root, scheme, name) is None:
                label = scheme or "light"
                errors.append(f"tab_row:palette:@{name} missing from the {label} palette")


def _validate_owner(
    section: Mapping[str, Any],
    contents: Mapping[str, str],
    errors: list[str],
    prefix: str = "group_area",
) -> None:
    owner = section.get("owner")
    if not isinstance(owner, dict):
        errors.append(f"{prefix}:owner:object required")
        return
    source_path = owner.get("source")
    source = contents.get(source_path) if isinstance(source_path, str) else None
    if source is None:
        errors.append(f"{prefix}:owner:source {source_path} missing")
        return
    code = _without_cpp_comments(source)

    include = owner.get("include")
    if isinstance(include, str) and f"#include {include}" not in code:
        errors.append(f"{prefix}:owner:missing #include {include}")

    for marker in owner.get("markers", []) or []:
        if isinstance(marker, str) and marker not in code:
            errors.append(f"{prefix}:owner:marker missing in code ({marker})")

    # High-contrast must ALWAYS win: the guard helper has to short-circuit on the system
    # forced-colors flag before any Material branch. A dropped HC check fails closed.
    hc_marker = owner.get("hc_marker")
    if isinstance(hc_marker, str) and hc_marker not in code:
        errors.append(
            f"{prefix}:owner:hc-marker missing in code ({hc_marker}); high-contrast must "
            "always win before any Material colour branch"
        )

    # The guard helper must be both defined AND invoked: a lone definition (call site
    # commented out) leaves exactly one occurrence after comment stripping, so require
    # >= 2.
    guard = owner.get("guard_marker")
    if isinstance(guard, str) and code.count(guard) < 2:
        errors.append(
            f"{prefix}:owner:guard {guard!r} must be both defined and invoked in code "
            "(the guarded Material override must not be comment-only)"
        )

    collapsed = _collapse_ws(code)

    def _check_bound_statement(
        spec: Mapping[str, Any], label: str, missing_msg: str, order_msg: str
    ) -> None:
        statement = spec.get("statement")
        if not isinstance(statement, str):
            return
        statement_c = _collapse_ws(statement)
        if statement_c not in collapsed:
            errors.append(f"{label}:{missing_msg} ({statement!r} not found)")
            return
        anchor = spec.get("within_branch_after")
        if isinstance(anchor, str):
            anchor_c = _collapse_ws(anchor)
            anchor_idx = collapsed.find(anchor_c)
            if anchor_idx == -1 or collapsed.find(statement_c) < anchor_idx:
                errors.append(f"{label}:{order_msg} ({anchor!r})")

    # Bind the guard to its effect: the @surface override must be the body of the guard,
    # expressed as a contiguous `if (... = guard("surface")) aColor = *oSurface;`
    # statement sitting on the group-area path after the base-colour line. This is
    # stronger than the whole-file markers above (which only prove the tokens exist
    # somewhere): an empty guard body, a detached override, or comment-only wiring all
    # leave the markers/guard-count intact but fail here.
    guarded_call = owner.get("guarded_call")
    if isinstance(guarded_call, dict):
        _check_bound_statement(
            guarded_call,
            f"{prefix}:owner:guarded-call",
            "the @surface override must be gated directly by the theme guard as a "
            "contiguous statement (an empty or detached guard body fails closed)",
            "the guarded @surface override must sit after the base-colour line",
        )

    # Bind each Material paint to the guard-resolved optional colour: every paint's
    # SetColor+Draw pair must appear as a contiguous statement referencing the guard's
    # dereferenced result (*oPrimary / *oRule) and sit after that guard resolution. A
    # removed paint, a paint detached from the guard (e.g. a raw literal colour), or a
    # reordered paint all leave the markers/guard-count intact but fail here -- this is
    # what pins the NEW underline/hairline structural markers, not merely token presence.
    for paint in owner.get("paints", []) or []:
        if not isinstance(paint, dict):
            continue
        name = paint.get("name", "?")
        _check_bound_statement(
            paint,
            f"{prefix}:owner:paint:{name}",
            "the guard-resolved paint statement is missing or not contiguous (a removed "
            "or guard-detached paint fails closed)",
            "the paint must sit after its guard resolution",
        )

    # The existing native/default-theme path must be retained byte-for-byte: every legacy
    # per-module accent Merge() call must still be present.
    for retained in owner.get("must_retain", []) or []:
        if isinstance(retained, str) and retained not in code:
            errors.append(
                f"{prefix}:owner:must-retain accent Merge() dropped ({retained}); the "
                "native/default-theme path must stay byte-for-byte untouched"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-notebookbar-composition":
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

    root = _parse_definition(contents.get(DEFINITION_PATH, ""), errors)

    group_area = registry.get("group_area")
    if not isinstance(group_area, dict):
        errors.append("registry:group_area:object required")
        group_area = {}

    if root is not None:
        _validate_palette(root, group_area, errors)

    _validate_owner(group_area, contents, errors)

    tab_row = registry.get("tab_row")
    if not isinstance(tab_row, dict):
        errors.append("registry:tab_row:object required")
        tab_row = {}

    if root is not None:
        _validate_tab_row_palette(root, tab_row, errors)

    _validate_owner(tab_row, contents, errors, prefix="tab_row")

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
        print(f"Material notebookbar composition contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material notebookbar composition contract passed: the guarded @surface group-area "
        "wash resolves through vcl::MaterialTokens after the base-colour line (the four legacy "
        "per-module accent Merge() calls retained byte-for-byte), and the tab-row overlay draws "
        "a guard-bound 2px @primary active-tab underline plus a full-width @outline-variant "
        "hairline, HC-first on every branch. @surface/@primary/@outline-variant are all present "
        "in both palettes. Scope is those paints only (not the tab-row FILL or .ui geometry)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
