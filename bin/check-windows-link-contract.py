#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the Material link interaction contract (inventory row WIN-ACT-005).

Both link surfaces are the one native ``FixedHyperlink`` widget: the weld
``weld::LinkButton`` wrapper (``SalInstanceLinkButton`` in
vcl/source/app/salvtables.cxx) drives the same control. The registry
``qa/windows-ui-contract/link-contract.json`` names those surfaces plus the
Material token side. This checker enforces the interaction contract specified in
docs/design/02-actions.md 5:

* a Material keyboard-focus affordance -- a ``@primary`` outline at
  ``corner-focus`` radius, laid by ``Paint()`` over the label and *replacing* the
  platform focus rectangle -- driven from the named Material token table
  (``findColor("primary")`` / ``findRadius("corner-focus")``), never a raw hex or
  a literal pixel radius;
* that affordance is gated on the Material file-widget theme being the active
  rendering (``VCL_FILE_WIDGET_THEME=material``) AND high contrast NOT being
  resolved, so under the platform theme and in forced-color mode the inherited
  platform focus rectangle applies unchanged;
* hover keeps the underline with no color tint (``MouseMove`` only changes the
  pointer -- it never recolors the text);
* a disabled link renders ``deactiveTextColor`` (``@outline``) as plain,
  non-underlined, non-focusable text (``LINESTYLE_NONE`` + ``WB_NOTABSTOP``);
* an enabled link keeps a single underline in ``@primary`` (unvisited) or
  ``@visited-link`` (visited) and stays focusable; and
* the visited state is recorded on activation and exposed (``SetVisited`` /
  ``IsVisited``) across BOTH surfaces -- the native widget's pointer/keyboard
  activation and the weld wrapper's click.

Comments are stripped before every source assertion, so comment-only wiring
fails. It is source evidence only: no native build, link pixels, or runtime
interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/link-contract.json"


class ValidationError(RuntimeError):
    """Raised when the Material link interaction contract is incomplete or weakened."""


# --------------------------------------------------------------------------------------------------
# Source hygiene
# --------------------------------------------------------------------------------------------------
CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\('
    r".*?\)(?P=delimiter)\"",
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    """Drop raw strings and comments so comment-only wiring can never satisfy a marker."""

    source = CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def _function_body(source: str, signature: re.Pattern[str], label: str) -> str:
    """Return the brace-delimited body that follows the first match of ``signature``."""

    match = signature.search(source)
    if match is None:
        raise ValidationError(f"{label} is missing")
    index = source.find("{", match.end())
    if index == -1:
        raise ValidationError(f"{label} has no body")
    depth = 0
    for position in range(index, len(source)):
        char = source[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[index : position + 1]
    raise ValidationError(f"{label} body is unbalanced")


def _require(source: str, pattern: str, description: str, *, where: str) -> None:
    if re.search(pattern, source) is None:
        raise ValidationError(f"{where} must {description}: missing /{pattern}/")


def _forbid(source: str, pattern: str, description: str, *, where: str) -> None:
    if re.search(pattern, source) is not None:
        raise ValidationError(f"{where} must {description}: found /{pattern}/")


# --------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------
def load_registry(registry_path: Path) -> dict:
    text = _read(registry_path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    if not isinstance(data.get("definition"), str) or not data["definition"].strip():
        raise ValidationError("registry must name a 'definition' file")

    focus = data.get("focus_ring")
    if not isinstance(focus, dict):
        raise ValidationError("registry must define a 'focus_ring' object")
    for key in ("color_role", "radius_token"):
        if not isinstance(focus.get(key), str) or not focus[key].strip():
            raise ValidationError(f"focus_ring.{key} must be a non-empty string")
    if not isinstance(focus.get("radius_value"), int):
        raise ValidationError("focus_ring.radius_value must be an integer")

    slots = data.get("style_slots")
    if not isinstance(slots, dict):
        raise ValidationError("registry must define a 'style_slots' object")
    for slot in ("linkColor", "visitedLinkColor", "deactiveTextColor"):
        if not isinstance(slots.get(slot), str) or not slots[slot].strip():
            raise ValidationError(f"style_slots.{slot} must name a semantic token")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, dict):
        raise ValidationError("registry must define a 'surfaces' object")
    for key in ("native_source", "native_header", "weld_source"):
        if not isinstance(surfaces.get(key), str) or not surfaces[key].strip():
            raise ValidationError(f"surfaces.{key} must name a source file")
    return data


# --------------------------------------------------------------------------------------------------
# Token side (definition.xml)
# --------------------------------------------------------------------------------------------------
def validate_definition(repo_root: Path, data: dict) -> None:
    path = repo_root / data["definition"]
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse definition {data['definition']}: {error}") from error

    style = root.find("style")
    if style is None:
        raise ValidationError("definition.xml has no <style> section")
    for slot, token in data["style_slots"].items():
        element = style.find(slot)
        if element is None:
            raise ValidationError(f"definition.xml <style> is missing <{slot}>")
        want = f"@{token}"
        if element.get("value") != want:
            raise ValidationError(
                f"definition.xml <style>/<{slot}> must be {want!r}, got {element.get('value')!r}"
            )

    shapes = root.find("shapes")
    if shapes is None:
        raise ValidationError("definition.xml has no <shapes> section")
    token = data["focus_ring"]["radius_token"]
    want_value = str(data["focus_ring"]["radius_value"])
    for radius in shapes.findall("radius"):
        if radius.get("name") == token:
            if radius.get("value") != want_value:
                raise ValidationError(
                    f"definition.xml shape {token!r} must be radius {want_value}, "
                    f"got {radius.get('value')!r}"
                )
            break
    else:
        raise ValidationError(f"definition.xml <shapes> is missing radius {token!r}")


# --------------------------------------------------------------------------------------------------
# Native surface (fixedhyper.cxx)
# --------------------------------------------------------------------------------------------------
def validate_native_source(repo_root: Path, data: dict) -> None:
    where = data["surfaces"]["native_source"]
    source = strip_cpp_non_code(_read(repo_root / where))
    color_role = data["focus_ring"]["color_role"]
    radius_token = data["focus_ring"]["radius_token"]

    # (1) Material-active gate + high-contrast bypass. The ring/style path is only
    #     reachable when the documented file-widget theme is active AND high contrast
    #     is not resolved -- so forced-color mode never gets the Material ring.
    _require(
        source,
        r"bool\s+FixedHyperlink::ImplUseMaterialLink\s*\(\s*\)\s*const",
        "define ImplUseMaterialLink()",
        where=where,
    )
    _require(
        source,
        r'std::getenv\s*\(\s*"VCL_FILE_WIDGET_THEME"\s*\)',
        "gate on the VCL_FILE_WIDGET_THEME env activation",
        where=where,
    )
    _require(
        source,
        r'std::string_view\s*\(\s*pThemeName\s*\)\s*!=\s*"material"',
        "reject any theme name other than material",
        where=where,
    )
    _require(
        source,
        r"return\s*!\s*Application::GetSettings\(\)\.GetStyleSettings\(\)"
        r"\.GetHighContrastMode\s*\(\s*\)",
        "bypass Material link styling in resolved high contrast",
        where=where,
    )

    # (2) Focus ring is token-driven: @primary color + corner-focus radius from the
    #     Material token table, with no raw hex and no literal pixel radius. The
    #     markers are asserted against ImplDrawFocusRing's own brace-matched body --
    #     the function Paint() actually calls -- so a decoy that keeps the tokens in
    #     a dead helper while leaving the real ring empty cannot satisfy them.
    draw_ring = _function_body(
        source,
        re.compile(r"void\s+FixedHyperlink::ImplDrawFocusRing\s*\("),
        f"{where} ImplDrawFocusRing()",
    )
    where_ring = f"{where} ImplDrawFocusRing()"
    _require(
        draw_ring,
        rf'findColor\s*\(\s*"{re.escape(color_role)}"\s*\)',
        f"resolve the focus-ring color from the {color_role!r} token",
        where=where_ring,
    )
    _require(
        draw_ring,
        rf'findRadius\s*\(\s*"{re.escape(radius_token)}"\s*\)',
        f"resolve the focus-ring radius from the {radius_token!r} token",
        where=where_ring,
    )
    _require(
        draw_ring,
        r"SetLineColor\s*\(\s*\*oPrimary\s*\)",
        "stroke the focus ring in the resolved @primary color",
        where=where_ring,
    )
    _require(
        draw_ring,
        r"DrawRect\s*\(\s*aRing\s*,\s*\*oRadius\s*,\s*\*oRadius\s*\)",
        "draw a rounded focus ring using the token radius",
        where=where_ring,
    )
    _forbid(
        draw_ring,
        r"DrawRect\s*\([^;]*,\s*\d+\s*,\s*\d+\s*\)",
        "not hard-code a literal focus-ring corner radius",
        where=where_ring,
    )

    # (3) The ring is laid only while focused, enabled, and Material-active -- so it
    #     replaces (never doubles) the platform rectangle and is never forced in HC.
    _require(
        source,
        r"void\s+FixedHyperlink::Paint\s*\(",
        "override Paint()",
        where=where,
    )
    _require(
        source,
        r"FixedText::Paint\s*\(\s*rRenderContext\s*,\s*rRect\s*\)",
        "chain the inherited FixedText::Paint before the ring",
        where=where,
    )
    _require(
        source,
        r"HasFocus\s*\(\s*\)\s*&&\s*IsEnabled\s*\(\s*\)\s*&&\s*ImplUseMaterialLink\s*\(\s*\)"
        r"\s*\)\s*ImplDrawFocusRing\s*\(",
        "gate the ring on focus + enabled + Material-active",
        where=where,
    )

    # GetFocus suppresses the platform rectangle only on the Material-active path.
    getfocus = _function_body(
        source,
        re.compile(r"void\s+FixedHyperlink::GetFocus\s*\(\s*\)"),
        f"{where} GetFocus()",
    )
    _require(
        getfocus,
        r"if\s*\(\s*ImplUseMaterialLink\s*\(\s*\)\s*&&\s*IsEnabled\s*\(\s*\)\s*\)\s*return\s*;",
        "return before ShowFocus() when the Material ring applies",
        where=f"{where} GetFocus()",
    )
    _require(
        getfocus,
        r"ShowFocus\s*\(\s*aFocusRect\s*\)",
        "keep the platform ShowFocus() rectangle for the non-Material path",
        where=f"{where} GetFocus()",
    )

    # (4) Disabled + (5) enabled branches of ImplUpdateLinkStyle.
    update = _function_body(
        source,
        re.compile(r"void\s+FixedHyperlink::ImplUpdateLinkStyle\s*\(\s*\)"),
        f"{where} ImplUpdateLinkStyle()",
    )
    where_update = f"{where} ImplUpdateLinkStyle()"
    _require(
        update,
        r"if\s*\(\s*!\s*ImplUseMaterialLink\s*\(\s*\)\s*\)\s*return\s*;",
        "leave the platform link styling untouched when Material is inactive",
        where=where_update,
    )
    _require(update, r"LINESTYLE_SINGLE", "keep a single underline while enabled", where=where_update)
    _require(
        update,
        r"GetLinkColor\s*\(\s*\)",
        "use @primary (linkColor) for an unvisited enabled link",
        where=where_update,
    )
    _require(
        update,
        r"GetVisitedLinkColor\s*\(\s*\)",
        "use @visited-link (visitedLinkColor) for a visited link",
        where=where_update,
    )
    _require(
        update,
        r"GetStyle\s*\(\s*\)\s*&\s*~\s*WB_NOTABSTOP",
        "keep an enabled link focusable",
        where=where_update,
    )
    _require(
        update,
        r"LINESTYLE_NONE",
        "drop the underline for a disabled link",
        where=where_update,
    )
    _require(
        update,
        r"GetDeactiveTextColor\s*\(\s*\)",
        "render a disabled link in deactiveTextColor (@outline)",
        where=where_update,
    )
    _require(
        update,
        r"GetStyle\s*\(\s*\)\s*\|\s*WB_NOTABSTOP",
        "make a disabled link non-focusable",
        where=where_update,
    )

    # (6) Hover keeps the underline with no color tint: MouseMove only touches the
    #     pointer and never recolors the text.
    mousemove = _function_body(
        source,
        re.compile(r"void\s+FixedHyperlink::MouseMove\s*\("),
        f"{where} MouseMove()",
    )
    _require(mousemove, r"SetPointer\s*\(", "change only the pointer on hover", where=f"{where} MouseMove()")
    _forbid(
        mousemove,
        r"SetControlForeground\s*\(|SetTextColor\s*\(",
        "not tint the link text on hover",
        where=f"{where} MouseMove()",
    )

    # (7) Visited state is recorded on activation and exposed.
    _require(
        source,
        r"void\s+FixedHyperlink::SetVisited\s*\(\s*bool\s+bVisited\s*\)",
        "define SetVisited(bool)",
        where=where,
    )
    _require(
        source,
        r"m_bVisited\s*=\s*bVisited",
        "store the visited state",
        where=where,
    )
    visits = len(re.findall(r"SetVisited\s*\(\s*true\s*\)", source))
    if visits < 2:
        raise ValidationError(
            f"{where} must record a visit on both pointer and keyboard activation: "
            f"found {visits} SetVisited(true) call(s), need >= 2"
        )


# --------------------------------------------------------------------------------------------------
# Native header (fixedhyper.hxx)
# --------------------------------------------------------------------------------------------------
def validate_native_header(repo_root: Path, data: dict) -> None:
    where = data["surfaces"]["native_header"]
    source = strip_cpp_non_code(_read(repo_root / where))
    for pattern, description in (
        (r"bool\s+m_bVisited", "declare the m_bVisited member"),
        (r"void\s+SetVisited\s*\(\s*bool\s+bVisited\s*\)", "declare SetVisited(bool)"),
        (r"bool\s+IsVisited\s*\(\s*\)\s*const", "expose IsVisited()"),
        (r"bool\s+ImplUseMaterialLink\s*\(\s*\)\s*const", "declare the Material-active gate"),
        (r"void\s+ImplUpdateLinkStyle\s*\(\s*\)", "declare ImplUpdateLinkStyle()"),
        (r"void\s+ImplDrawFocusRing\s*\(", "declare ImplDrawFocusRing()"),
        (r"void\s+Paint\s*\(", "override Paint()"),
    ):
        _require(source, pattern, description, where=where)


# --------------------------------------------------------------------------------------------------
# Weld surface (salvtables.cxx)
# --------------------------------------------------------------------------------------------------
def validate_weld_source(repo_root: Path, data: dict) -> None:
    where = data["surfaces"]["weld_source"]
    source = strip_cpp_non_code(_read(repo_root / where))
    click = _function_body(
        source,
        re.compile(r"IMPL_LINK\s*\(\s*SalInstanceLinkButton\s*,\s*ClickHdl\s*,"),
        f"{where} SalInstanceLinkButton::ClickHdl",
    )
    _require(
        click,
        r"\.SetVisited\s*\(\s*true\s*\)",
        "record the visit on the underlying widget so the weld surface exposes it",
        where=f"{where} SalInstanceLinkButton::ClickHdl",
    )


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_definition(repo_root, data)
    validate_native_source(repo_root, data)
    validate_native_header(repo_root, data)
    validate_weld_source(repo_root, data)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve() if args.registry is not None else DEFAULT_REGISTRY
    )
    try:
        validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Material link contract failed:\n{error}", file=sys.stderr)
        return 1

    print(
        "Material link contract passed: native FixedHyperlink + weld::LinkButton draw a "
        "token-driven @primary corner-focus ring (Material-active, not high contrast), keep "
        "the underline with no hover tint, render disabled links as @outline plain "
        "non-underlined non-focusable text, and expose the visited state across both surfaces."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
