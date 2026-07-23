#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed render/display-scale neutrality contract for WIN-SYS-014.

``qa/windows-ui-contract/render-scale-matrix.json`` pins the render-method and
display-scaling NEUTRALITY invariants the Material file-widget path was designed
around, plus the upstream preconditions the accepted software Start Center
(E-SC) evidence depends on. This is a *regression / precondition guard*, not a
Material implementation of the GPU/RDP/fractional-scale/multi-monitor matrix:

* ``render_agnostic`` -- the Material draw path
  ``vcl/source/gdi/FileDefinitionWidgetDraw.cxx`` contains none of the
  render-method-*selection* identifiers (``renderMethodToUse``,
  ``isVCLSkiaEnabled``, ``SAL_SKIA``, ``RenderVulkan``, ``RenderMetal``,
  ``SkiaHelper::``), so accelerated-vs-software is a build-verification (pixel
  parity) concern, never a source divergence. Absence assertion.
* ``dpi_awareness_pinned`` -- ``DeclareDPIAware.manifest`` is
  ``<dpiAware>true</dpiAware>`` (system-DPI-aware, NOT per-monitor: no
  ``PerMonitor`` / ``dpiAwareness`` token), the scaling model the px token
  geometry assumes.
* ``dpi_manifest_wired`` -- ``com_MSC_class.mk`` really applies that manifest to
  every ``Executable`` via ``mt.exe ... -updateresource``.
* ``win_skia_default`` -- ``Common.xcu`` ``UseSkia`` is ``true`` on ``wnt`` (GPU
  is the Windows default; raster is the fallback).
* ``skia_settings_surface`` -- ``Common.xcs`` declares ``UseSkia`` /
  ``ForceSkia`` / ``ForceSkiaRaster`` boolean props whose schema defaults are all
  ``false`` (raster is never the schema default).
* ``raster_fallback_exists`` -- ``SkiaHelper.cxx`` ``initRenderMethodToUse``
  returns ``RenderRaster`` for bitmap-rendering, for Windows/macOS safe-mode
  (``_WIN32`` guard), and for ``ForceSkiaRaster::get()`` -- the software-raster
  fallback the accepted evidence runs under, still a caller-selected fallback.

A ``matrix`` carve-out records the entire build-bound remainder as
``status:specified`` and is never promoted. It is source/text evidence only:
``runtime_verified`` is false throughout -- no build, pixels, or runtime
interaction are claimed, and no checklist gate (M included) is moved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/render-scale-matrix.json"
CONTRACT_NAME = "material-render-scale-neutrality"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# C++ comment / raw-string stripping so commented-out code cannot satisfy or trip a marker.
# --------------------------------------------------------------------------------------------------
_CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    source = _CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _pin_files(registry: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    pins = registry.get("pins")
    if isinstance(pins, dict):
        for pin in pins.values():
            if isinstance(pin, dict) and isinstance(pin.get("file"), str):
                files.append(pin["file"])
    return files


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _pin_files(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Per-pin validators. Each is driven by the registry so a drifted registry value
# is exercised against the real (correct) tree.
# --------------------------------------------------------------------------------------------------
def _pin(registry: Mapping[str, Any], name: str, errors: list[str]) -> Mapping[str, Any] | None:
    pins = registry.get("pins")
    if not isinstance(pins, dict):
        errors.append("registry:pins:object required")
        return None
    pin = pins.get(name)
    if not isinstance(pin, dict):
        errors.append(f"pins:{name}:object required")
        return None
    return pin


def _source(pin: Mapping[str, Any], contents: Mapping[str, str], name: str, errors: list[str]) -> str | None:
    rel = pin.get("file")
    if not isinstance(rel, str):
        errors.append(f"pins:{name}:file must be a string")
        return None
    text = contents.get(rel)
    if text is None:
        errors.append(f"pins:{name}:{rel} missing")
        return None
    return text


def _validate_render_agnostic(registry, contents, errors) -> None:
    pin = _pin(registry, "render_agnostic", errors)
    if pin is None:
        return
    text = _source(pin, contents, "render_agnostic", errors)
    if text is None:
        return
    stripped = strip_cpp_non_code(text)
    tokens = pin.get("forbidden_tokens")
    if not isinstance(tokens, list) or not tokens:
        errors.append("pins:render_agnostic:forbidden_tokens non-empty array required")
        return
    for token in tokens:
        if isinstance(token, str) and token in stripped:
            errors.append(
                f"pins:render_agnostic:{pin['file']} contains render-method-selection token "
                f"{token!r} (the Material draw path must stay render-agnostic)"
            )


def _validate_dpi_awareness(registry, contents, errors) -> None:
    pin = _pin(registry, "dpi_awareness_pinned", errors)
    if pin is None:
        return
    text = _source(pin, contents, "dpi_awareness_pinned", errors)
    if text is None:
        return
    literal = pin.get("required_literal")
    if not isinstance(literal, str) or literal not in text:
        errors.append(
            f"pins:dpi_awareness_pinned:{pin['file']} must contain the system-DPI-aware literal "
            f"{literal!r}"
        )
    for token in pin.get("forbidden_tokens", []) or []:
        if isinstance(token, str) and token in text:
            errors.append(
                f"pins:dpi_awareness_pinned:{pin['file']} contains per-monitor token {token!r} "
                "(the pinned model is system-DPI-aware, not per-monitor)"
            )


def _validate_dpi_manifest_wired(registry, contents, errors) -> None:
    pin = _pin(registry, "dpi_manifest_wired", errors)
    if pin is None:
        return
    text = _source(pin, contents, "dpi_manifest_wired", errors)
    if text is None:
        return
    markers = pin.get("line_markers")
    if not isinstance(markers, list) or not markers or not all(isinstance(m, str) for m in markers):
        errors.append("pins:dpi_manifest_wired:line_markers non-empty string array required")
        return
    # All markers must co-occur on a single logical line (the Executable mt.exe
    # -updateresource invocation), so removing that line fails closed.
    pattern = "[^\n]*".join(re.escape(m) for m in markers)
    if re.search(pattern, text) is None:
        errors.append(
            f"pins:dpi_manifest_wired:{pin['file']} must apply DeclareDPIAware.manifest to Executable "
            f"targets via mt.exe -updateresource (missing one of {markers})"
        )


_XCU_PROP = "officecfg xcu prop block"


def _prop_block(text: str, prop: str) -> str | None:
    match = re.search(
        rf'<prop\b[^>]*oor:name="{re.escape(prop)}"[^>]*>.*?</prop>', text, flags=re.DOTALL
    )
    return match.group(0) if match else None


def _validate_win_skia_default(registry, contents, errors) -> None:
    pin = _pin(registry, "win_skia_default", errors)
    if pin is None:
        return
    text = _source(pin, contents, "win_skia_default", errors)
    if text is None:
        return
    prop = pin.get("prop")
    required = pin.get("required_value")
    if not isinstance(prop, str) or not isinstance(required, str):
        errors.append("pins:win_skia_default:prop/required_value must be strings")
        return
    block = _prop_block(text, prop)
    if block is None:
        errors.append(f"pins:win_skia_default:{pin['file']} has no <prop oor:name=\"{prop}\"> block")
        return
    if required not in block:
        errors.append(
            f"pins:win_skia_default:{pin['file']} {prop} must carry {required!r} "
            "(GPU/Skia is the Windows default)"
        )


def _validate_skia_settings_surface(registry, contents, errors) -> None:
    pin = _pin(registry, "skia_settings_surface", errors)
    if pin is None:
        return
    text = _source(pin, contents, "skia_settings_surface", errors)
    if text is None:
        return
    props = pin.get("props")
    if not isinstance(props, list) or not props:
        errors.append("pins:skia_settings_surface:props non-empty array required")
        return
    for entry in props:
        if not isinstance(entry, dict):
            errors.append("pins:skia_settings_surface:prop must be an object")
            continue
        name = entry.get("name")
        default = entry.get("default")
        if not isinstance(name, str) or not isinstance(default, str):
            errors.append("pins:skia_settings_surface:prop name/default must be strings")
            continue
        block = _prop_block(text, name)
        if block is None:
            errors.append(
                f"pins:skia_settings_surface:{pin['file']} has no boolean prop {name!r}"
            )
            continue
        if 'oor:type="xs:boolean"' not in block:
            errors.append(
                f"pins:skia_settings_surface:{pin['file']} {name} must be an xs:boolean prop"
            )
        if f"<value>{default}</value>" not in block:
            errors.append(
                f"pins:skia_settings_surface:{pin['file']} {name} schema default must be "
                f"<value>{default}</value>"
            )


def _function_body(text: str, function: str) -> str | None:
    match = re.search(rf"\b{re.escape(function)}\s*\([^)]*\)\s*\{{.*?\n\}}", text, flags=re.DOTALL)
    return match.group(0) if match else None


def _validate_raster_fallback(registry, contents, errors) -> None:
    pin = _pin(registry, "raster_fallback_exists", errors)
    if pin is None:
        return
    text = _source(pin, contents, "raster_fallback_exists", errors)
    if text is None:
        return
    stripped = strip_cpp_non_code(text)
    function = pin.get("function")
    if not isinstance(function, str):
        errors.append("pins:raster_fallback_exists:function must be a string")
        return
    body = _function_body(stripped, function)
    if body is None:
        errors.append(
            f"pins:raster_fallback_exists:{pin['file']} must define {function}()"
        )
        return
    raster_return = pin.get("raster_return")
    if not isinstance(raster_return, str) or raster_return not in body:
        errors.append(
            f"pins:raster_fallback_exists:{function} must return {raster_return!r} for the fallback conditions"
        )
    win_guard = pin.get("win_guard_token")
    if not isinstance(win_guard, str) or win_guard not in body:
        errors.append(
            f"pins:raster_fallback_exists:{function} must guard the safe-mode raster branch on {win_guard!r}"
        )
    conditions = pin.get("raster_conditions")
    if not isinstance(conditions, list) or not conditions:
        errors.append("pins:raster_fallback_exists:raster_conditions non-empty array required")
        return
    for condition in conditions:
        if isinstance(condition, str) and condition not in body:
            errors.append(
                f"pins:raster_fallback_exists:{function} must degrade to raster for {condition!r}"
            )


# --------------------------------------------------------------------------------------------------
# matrix carve-out and registry meta.
# --------------------------------------------------------------------------------------------------
def _validate_matrix(registry: Mapping[str, Any], errors: list[str]) -> None:
    matrix = registry.get("matrix")
    if not isinstance(matrix, dict):
        errors.append("registry:matrix:object required")
        return
    if matrix.get("status") != "specified":
        errors.append(
            "matrix:status:must stay 'specified' (the GPU/RDP/fractional-scale/multi-monitor "
            "matrix is build-bound and must never be promoted to an implemented claim)"
        )
    if matrix.get("runtime_verified") is not False:
        errors.append("matrix:runtime_verified:must be false (no runtime evidence exists)")
    build_bound = matrix.get("build_bound")
    if not isinstance(build_bound, list) or not build_bound:
        errors.append("matrix:build_bound:non-empty array of the build-bound remainder required")


def _validate_meta(registry: Mapping[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT_NAME:
        errors.append(f"registry:contract:must be {CONTRACT_NAME!r}")
    if registry.get("inventory_row") != "WIN-SYS-014":
        errors.append("registry:inventory_row:must be WIN-SYS-014")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")


# --------------------------------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    _validate_meta(registry, errors)
    _validate_render_agnostic(registry, contents, errors)
    _validate_dpi_awareness(registry, contents, errors)
    _validate_dpi_manifest_wired(registry, contents, errors)
    _validate_win_skia_default(registry, contents, errors)
    _validate_skia_settings_surface(registry, contents, errors)
    _validate_raster_fallback(registry, contents, errors)
    _validate_matrix(registry, errors)
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
        print(f"Render/scale neutrality contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Render/scale neutrality contract passed: the Material draw path stays render-agnostic, "
        "the system-DPI-aware manifest is pinned and wired to every Executable, Skia is the "
        "Windows default with a software-raster fallback that is never the default, and the full "
        "GPU/RDP/fractional-scale/multi-monitor matrix stays build-bound (specified, runtime_verified:false)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
