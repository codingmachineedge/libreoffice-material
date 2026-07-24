#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Material appearance-options page (Cluster E).

Stage 1 of the Material rewrite adds a Material section to Tools > Options >
Appearance over the existing theme-mode plumbing. This contract pins that composition,
source-only, so it cannot silently drift:

* **Schema** -- the officecfg ``Appearance`` group declares ``MaterialAccent`` (xs:short
  enum 0..5, default 0 = Violet), ``MaterialDensity`` (xs:short enum 0..1, default 0 =
  Comfortable), ``MaterialReducedMotion`` (xs:boolean, default false) and the optional
  ``MaterialSurfaceStyle`` (xs:short enum 0..1, default 0), each with the pinned type,
  default and enumeration values.
* **Widget ids** -- ``cui/uiconfig/ui/appearance.ui`` carries the ``materialtheme``
  GtkFrame and, inside it, the accent combo, the density radios and the reduced-motion
  checkbox named by the registry.
* **Controller** -- ``cui/source/options/appearance.cxx`` welds every UI id and commits
  every committed property through its officecfg accessor's ``::set(`` in ``FillItemSet``.
* **Apply path** -- the page applies Material appearance through the EXISTING restart
  dialog (``executeRestartDialog`` / ``RESTART_REASON_THEME_CHANGE``); the Stage-3 live
  token-cache re-key symbols must be ABSENT from the cui page.
* **Scheme string** -- the accent order matches the ``MaterialAccent`` enumeration and
  the appearance.ui combo items, so the schema, the UI and D's accent-key composition
  cannot diverge.

Density and reduced motion are stored-value-only and honest-inert this stage (the metric
/ motion plumbing is Stage 3). Source evidence only: ``runtime_verified`` is false.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/material-appearance-options.json"
CONTRACT = "material-appearance-options"


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _referenced_sources(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for key in ("schema_source", "ui_source", "controller_source", "controller_header"):
        value = registry.get(key)
        if isinstance(value, str):
            paths.add(value)
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in _referenced_sources(registry):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# integrity
# --------------------------------------------------------------------------------------------------
def _validate_integrity(registry: Mapping[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT:
        errors.append(f"registry:contract:must be {CONTRACT}")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")
    if registry.get("apply_stage") != "restart":
        errors.append(
            "registry:apply_stage:must be 'restart' (Stage 1 uses the existing restart path; "
            "live apply is Stage 3)"
        )


def _prop_block(source: str, name: str) -> str | None:
    match = re.search(
        r'<prop\s+oor:name="' + re.escape(name) + r'"(?:.*?)</prop>', source, flags=re.DOTALL
    )
    return match.group(0) if match else None


# --------------------------------------------------------------------------------------------------
# schema + widget + controller, per property
# --------------------------------------------------------------------------------------------------
def _validate_properties(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    schema = contents.get(registry.get("schema_source", ""))
    ui = contents.get(registry.get("ui_source", ""))
    controller = contents.get(registry.get("controller_source", ""))
    frame_id = registry.get("frame_id")

    if schema is None:
        errors.append("properties:schema_source missing")
    if ui is None:
        errors.append("properties:ui_source missing")
    if controller is None:
        errors.append("properties:controller_source missing")

    # Region of appearance.ui from the materialtheme frame onward, so widget ids are
    # verified to live INSIDE the frame, not merely somewhere in the file.
    frame_region = ""
    if ui is not None and isinstance(frame_id, str):
        if f'id="{frame_id}"' not in ui:
            errors.append(f"properties:frame id={frame_id!r} not found in appearance.ui")
        else:
            frame_region = ui[ui.index(f'id="{frame_id}"') :]

    props = registry.get("properties")
    if not isinstance(props, list) or not props:
        errors.append("registry:properties:non-empty array required")
        return

    for prop in props:
        if not isinstance(prop, dict):
            errors.append("properties:entry:object required")
            continue
        name = prop.get("name")
        if not isinstance(name, str):
            errors.append("properties:entry:name must be a string")
            continue

        # -- schema block --
        if schema is not None:
            block = _prop_block(schema, name)
            if block is None:
                errors.append(f"properties:{name}:not found in officecfg Appearance schema")
            else:
                prop_type = prop.get("type")
                default = prop.get("default")
                if isinstance(prop_type, str) and f'oor:type="{prop_type}"' not in block:
                    errors.append(f"properties:{name}:schema is not oor:type={prop_type!r}")
                if isinstance(default, str) and f"<value>{default}</value>" not in block:
                    errors.append(
                        f"properties:{name}:schema default drifted (expected "
                        f"<value>{default}</value>)"
                    )
                for value in prop.get("enum_values", []) or []:
                    if isinstance(value, str) and f'<enumeration oor:value="{value}"' not in block:
                        errors.append(
                            f"properties:{name}:schema enumeration {value!r} missing"
                        )

        if prop.get("schema_only"):
            # A stored-only key with no UI surface this stage: no widget/controller checks.
            continue

        # -- widget ids inside the frame --
        if frame_region:
            for ui_id in prop.get("ui_ids", []) or []:
                if isinstance(ui_id, str) and f'id="{ui_id}"' not in frame_region:
                    errors.append(
                        f"properties:{name}:widget id={ui_id!r} not found inside the "
                        f"{frame_id!r} frame"
                    )

        # -- controller weld bindings + officecfg commit --
        if controller is not None:
            for binding in prop.get("weld_bindings", []) or []:
                if isinstance(binding, str) and binding not in controller:
                    errors.append(
                        f"properties:{name}:controller weld binding {binding!r} missing"
                    )
            accessor = prop.get("officecfg_accessor")
            if isinstance(accessor, str):
                if accessor not in controller:
                    errors.append(
                        f"properties:{name}:controller never references {accessor!r}"
                    )
                elif prop.get("committed") and f"{accessor}::set(" not in controller:
                    errors.append(
                        f"properties:{name}:controller never commits {accessor}::set( "
                        "(FillItemSet must persist the value)"
                    )


# --------------------------------------------------------------------------------------------------
# header member markers
# --------------------------------------------------------------------------------------------------
def _validate_header(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    header = contents.get(registry.get("controller_header", ""))
    if header is None:
        errors.append("header:controller_header missing")
        return
    for marker in registry.get("header_markers", []) or []:
        if isinstance(marker, str) and marker not in header:
            errors.append(f"header:marker {marker!r} missing from appearance.hxx")


# --------------------------------------------------------------------------------------------------
# apply path (restart present, live re-key absent)
# --------------------------------------------------------------------------------------------------
def _validate_apply(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    controller = contents.get(registry.get("controller_source", ""))
    apply_block = registry.get("apply")
    if not isinstance(apply_block, dict):
        errors.append("registry:apply:object required")
        return
    if controller is None:
        errors.append("apply:controller_source missing")
        return
    for marker in apply_block.get("controller_markers", []) or []:
        if isinstance(marker, str) and marker not in controller:
            errors.append(f"apply:required marker {marker!r} missing from controller")
    for marker in apply_block.get("forbidden_live_markers", []) or []:
        if isinstance(marker, str) and marker in controller:
            errors.append(
                f"apply:forbidden Stage-3 live-apply marker {marker!r} present in the cui "
                "page -- Stage 1 must apply Material appearance via the restart path only"
            )


# --------------------------------------------------------------------------------------------------
# scheme string composition
# --------------------------------------------------------------------------------------------------
def _validate_scheme_string(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    scheme = registry.get("scheme_string")
    if not isinstance(scheme, dict):
        errors.append("registry:scheme_string:object required")
        return
    order = scheme.get("accent_order")
    if not isinstance(order, list) or not order:
        errors.append("scheme_string:accent_order:non-empty array required")
        return

    # Cross-check against the MaterialAccent enum count.
    accent_prop = next(
        (
            p
            for p in registry.get("properties", []) or []
            if isinstance(p, dict) and p.get("name") == scheme.get("accent_property")
        ),
        None,
    )
    if accent_prop is None:
        errors.append(
            f"scheme_string:accent_property {scheme.get('accent_property')!r} not among properties"
        )
    else:
        enum_values = accent_prop.get("enum_values", []) or []
        if len(order) != len(enum_values):
            errors.append(
                f"scheme_string:accent_order has {len(order)} entries but MaterialAccent "
                f"declares {len(enum_values)} enum values"
            )

    if scheme.get("default_accent_value") != "0":
        errors.append("scheme_string:default_accent_value must be '0' (Violet default)")
    if order and scheme.get("default_accent_name") != order[0]:
        errors.append(
            "scheme_string:default_accent_name must equal accent_order[0] (the default accent)"
        )

    # Each accent name must appear as a combo item inside the materialtheme frame.
    ui = contents.get(registry.get("ui_source", ""))
    frame_id = registry.get("frame_id")
    if ui is not None and isinstance(frame_id, str) and f'id="{frame_id}"' in ui:
        region = ui[ui.index(f'id="{frame_id}"') :]
        for name in order:
            if isinstance(name, str) and f">{name}</item>" not in region:
                errors.append(
                    f"scheme_string:accent {name!r} is not an item of the appearance.ui "
                    "accent combo (schema/ui/scheme-string drift)"
                )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    _validate_integrity(registry, errors)
    _validate_properties(registry, contents, errors)
    _validate_header(registry, contents, errors)
    _validate_apply(registry, contents, errors)
    _validate_scheme_string(registry, contents, errors)
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
        print(f"Material appearance-options contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material appearance-options contract passed: the officecfg Appearance schema "
        "(MaterialAccent/MaterialDensity/MaterialReducedMotion/MaterialSurfaceStyle), the "
        "materialtheme frame widget ids, the controller weld bindings + FillItemSet commit, "
        "the restart apply path (no Stage-3 live re-key), and the accent scheme-string "
        "composition are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
