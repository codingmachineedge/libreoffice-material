#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for default-on Material activation (Windows).

The Material widget treatment ships in every MSI but is dormant: upstream keeps
it behind two environment variables that no product code sets --
``vcl/source/gdi/salgdilayout.cxx`` enables ``FileDefinitionWidgetDraw`` only
when ``VCL_DRAW_WIDGETS_FROM_FILE`` is set, and the theme-name guards select the
shared theme only when ``VCL_FILE_WIDGET_THEME`` == ``material``. The Material
assets themselves DO ship (``vcl/Package_theme_definitions.mk`` installs
``material/definition.xml``).

This fork defaults both variables ON at the very top of ``soffice_main()``
(``desktop/source/app/sofficemain.cxx``), under ``#ifdef _WIN32``, before any
consumer in the process reads them. ``qa/windows-ui-contract/material-default-activation.json``
pins that wiring; this checker cross-validates every anchor against real,
comment-stripped source and fails closed on drift:

* ``activation`` -- inside ``soffice_main()``, and BEFORE the first pre-existing
  statement (``sal_detail_initialize(sal::detail::InitializeSoffice``), the code
  must (a) be guarded by ``#ifdef _WIN32``; (b) honour the ``LIBREOFFICE_MATERIAL_THEME``
  opt-out token with its case-insensitive values; (c) respect an already-set
  theme via ``getenv("VCL_FILE_WIDGET_THEME")``; and (d) carry both ``_putenv_s``
  calls with the exact values ``"material"`` and ``"1"``. A moved block, a dropped
  guard, a dropped opt-out, a dropped override-respect, or a drifted ``_putenv_s``
  value fails closed.
* ``asset_cross_checks`` -- ``salgdilayout.cxx`` must still gate on
  ``VCL_DRAW_WIDGETS_FROM_FILE`` and ``Package_theme_definitions.mk`` must still
  ship ``material/definition.xml`` -- so activation cannot outlive its assets.
* ``carveout`` -- first real visual verification is build-dependent, so its
  ``status`` stays ``specified`` and is never promoted.

It is source + wiring evidence only: ``runtime_verified`` is false throughout --
no native build, theme pixels, or runtime observation of the activated theme is
claimed. The mutation suite in bin/test_material_default_activation.py exercises
every branch.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/material-default-activation.json"


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
    paths: set[str] = set()

    activation = registry.get("activation")
    if isinstance(activation, dict) and isinstance(activation.get("file"), str):
        paths.add(activation["file"])

    crosschecks = registry.get("asset_cross_checks")
    if isinstance(crosschecks, dict):
        for key in ("gate", "assets"):
            block = crosschecks.get(key)
            if isinstance(block, dict) and isinstance(block.get("file"), str):
                paths.add(block["file"])

    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Source helpers
# --------------------------------------------------------------------------------------------------
def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments, preserving string/char literals."""

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
        # quote
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


def _extract_function_body(code: str, signature: str) -> str | None:
    """Return the brace-delimited body of the function named by ``signature``.

    ``signature`` is matched literally (e.g. ``"soffice_main()"``). The returned
    text is the code between the function's opening and matching closing brace.
    """

    start = code.find(signature)
    if start < 0:
        return None
    opening = code.find("{", start + len(signature))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[opening + 1 : index]
    return None


# --------------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------------
def _validate_activation(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = block.get("file")
    if not isinstance(file_path, str):
        errors.append("activation:file must be a string")
        return
    text = contents.get(file_path)
    if text is None:
        errors.append(f"activation:{file_path}:file missing")
        return
    code = _strip_comments(text)

    signature = block.get("function_anchor")
    if not isinstance(signature, str):
        errors.append("activation:function_anchor must be a string")
        return
    body = _extract_function_body(code, signature)
    if body is None:
        errors.append(
            f"activation:{file_path}:function {signature!r} not found "
            "(the default-on block must live inside soffice_main)"
        )
        return

    first_anchor = block.get("first_statement_anchor")
    if not isinstance(first_anchor, str) or not first_anchor:
        errors.append("activation:first_statement_anchor must be a non-empty string")
        return
    first_at = body.find(first_anchor)
    if first_at < 0:
        errors.append(
            f"activation:{file_path}:first-statement anchor {first_anchor!r} not found "
            "(cannot prove the block precedes the pre-existing body)"
        )
        return

    # Everything below must appear in the region BEFORE the first pre-existing
    # statement; ``pre`` is exactly that region.
    pre = body[:first_at]

    # (a) the block is guarded by #ifdef _WIN32.
    guard = block.get("guard")
    if not isinstance(guard, str) or not guard:
        errors.append("activation:guard must be a non-empty string")
    elif guard not in pre:
        errors.append(
            f"activation:{file_path}:guard {guard!r} missing before the first statement "
            "(the default-on block must be Windows-guarded and precede the body)"
        )

    # (b) opt-out token + its case-insensitive values.
    opt_out_var = block.get("opt_out_var")
    if not isinstance(opt_out_var, str) or not opt_out_var:
        errors.append("activation:opt_out_var must be a non-empty string")
    elif opt_out_var not in pre:
        errors.append(
            f"activation:{file_path}:opt-out token {opt_out_var!r} missing "
            "(LIBREOFFICE_MATERIAL_THEME=off must fully disable the default)"
        )
    ci_marker = block.get("opt_out_case_insensitive_marker")
    if isinstance(ci_marker, str) and ci_marker and ci_marker not in pre:
        errors.append(
            f"activation:{file_path}:case-insensitive opt-out marker {ci_marker!r} missing "
            "(the opt-out comparison must be case-insensitive)"
        )
    values = block.get("opt_out_values")
    if not isinstance(values, list) or not values:
        errors.append("activation:opt_out_values must be a non-empty array")
    else:
        for value in values:
            if not isinstance(value, str):
                errors.append("activation:opt_out_values entries must be strings")
                continue
            if f'"{value}"' not in pre:
                errors.append(
                    f"activation:{file_path}:opt-out value {value!r} not compared "
                    "(a documented opt-out value was dropped)"
                )

    # (c) an already-set theme is respected.
    respect = block.get("respect_existing_check")
    if not isinstance(respect, str) or not respect:
        errors.append("activation:respect_existing_check must be a non-empty string")
    elif respect not in pre:
        errors.append(
            f"activation:{file_path}:respect-existing check {respect!r} missing "
            "(a user-set VCL_FILE_WIDGET_THEME must never be overridden)"
        )

    # (d) both _putenv_s calls with exact values, before the first statement.
    calls = block.get("putenv_calls")
    if not isinstance(calls, list) or not calls:
        errors.append("activation:putenv_calls must be a non-empty array")
    else:
        for call in calls:
            if not isinstance(call, dict):
                errors.append("activation:putenv_calls entry must be an object")
                continue
            var = call.get("var")
            value = call.get("value")
            if not (isinstance(var, str) and isinstance(value, str)):
                errors.append("activation:putenv_calls var/value must be strings")
                continue
            pattern = re.compile(
                r'_putenv_s\(\s*"' + re.escape(var) + r'"\s*,\s*"' + re.escape(value) + r'"\s*\)'
            )
            if not pattern.search(pre):
                errors.append(
                    f"activation:{file_path}:_putenv_s({var!r}, {value!r}) missing before the "
                    "first statement (the exact env default drifted, moved, or was removed)"
                )


def _validate_gate(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = block.get("file")
    anchor = block.get("anchor")
    if not (isinstance(file_path, str) and isinstance(anchor, str)):
        errors.append("asset_cross_checks:gate:file/anchor must be strings")
        return
    text = contents.get(file_path)
    if text is None:
        errors.append(f"asset_cross_checks:gate:{file_path}:file missing")
        return
    if anchor not in _strip_comments(text):
        errors.append(
            f"asset_cross_checks:gate:{file_path}:anchor {anchor!r} missing "
            "(FileDefinitionWidgetDraw no longer gates on VCL_DRAW_WIDGETS_FROM_FILE; "
            "the default-on wiring would target a dead switch)"
        )


def _validate_assets(
    block: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    file_path = block.get("file")
    anchor = block.get("anchor")
    if not (isinstance(file_path, str) and isinstance(anchor, str)):
        errors.append("asset_cross_checks:assets:file/anchor must be strings")
        return
    text = contents.get(file_path)
    if text is None:
        errors.append(f"asset_cross_checks:assets:{file_path}:file missing")
        return
    if anchor not in text:
        errors.append(
            f"asset_cross_checks:assets:{file_path}:anchor {anchor!r} missing "
            "(the Material theme definition no longer ships; activation would outlive "
            "its assets)"
        )


def _validate_carveout(carveout: Any, errors: list[str]) -> None:
    if not isinstance(carveout, dict) or not carveout:
        errors.append("carveout:non-empty object required")
        return
    block = carveout.get("first_visual_verification")
    if not isinstance(block, dict):
        errors.append("carveout:first_visual_verification:object required")
        return
    if block.get("status") != "specified":
        errors.append(
            "carveout:first_visual_verification:status must stay 'specified' "
            "(build-dependent; not promoted to an implemented/runtime claim)"
        )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "material-default-activation":
        errors.append("registry:contract:must be material-default-activation")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    activation = registry.get("activation")
    if isinstance(activation, dict):
        _validate_activation(activation, contents, errors)
    else:
        errors.append("registry:activation:object required")

    crosschecks = registry.get("asset_cross_checks")
    if isinstance(crosschecks, dict):
        gate = crosschecks.get("gate")
        if isinstance(gate, dict):
            _validate_gate(gate, contents, errors)
        else:
            errors.append("registry:asset_cross_checks:gate:object required")
        assets = crosschecks.get("assets")
        if isinstance(assets, dict):
            _validate_assets(assets, contents, errors)
        else:
            errors.append("registry:asset_cross_checks:assets:object required")
    else:
        errors.append("registry:asset_cross_checks:object required")

    _validate_carveout(registry.get("carveout"), errors)

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
        print(f"Material default-activation contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material default-activation contract passed: soffice_main() defaults "
        "VCL_FILE_WIDGET_THEME=material and VCL_DRAW_WIDGETS_FROM_FILE=1 under #ifdef _WIN32 "
        "before the first pre-existing statement, with the LIBREOFFICE_MATERIAL_THEME opt-out "
        "and user-override-wins semantics, and the salgdilayout gate + material/definition.xml "
        "assets still present -- source+wiring evidence only, runtime_verified false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
