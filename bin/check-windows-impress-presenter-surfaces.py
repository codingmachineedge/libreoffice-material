#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the Impress presenter / animation / transition surfaces
(WIN-IM-004).

``qa/windows-ui-contract/impress-presenter-surfaces.json`` composition-pins the real,
already-shipping upstream surfaces this row owns, as purely static source/XML assertions (no
build, no pixels, no UNO tree). It enforces, fail-closed:

* ``component`` -- ``sd/source/console/presenter.component`` must register the presenter console as
  the CppComponent ``org.libreoffice.comp.PresenterScreenProtocolHandler`` (constructor
  ``sd_PresenterProtocolHandler_get_implementation``) implementing
  ``com.sun.star.frame.ProtocolHandler``. A renamed implementation, constructor, or dropped service
  fails closed. This corrects the stale inventory note that assigned the presenter to ``sdext``.
* ``console_absence`` -- across ``sd/source/console/*.cxx`` and ``*.hxx`` (comment / raw-string
  stripped) there must be ZERO references to ``VCL_FILE_WIDGET_THEME`` /
  ``VCL_DRAW_WIDGETS_FROM_FILE`` / ``MaterialTokens``, because the console renders through its own
  PresenterTheme bitmap/sprite pipeline outside the VCL widget-draw path. If a future change adds
  such a guard without updating the documented architecture divergence, the drift is surfaced here
  rather than silently satisfied. A vanished console directory (fewer than ``min_cxx_files``) fails
  closed too, so the absence marker can never vacuously pass.
* ``panels`` -- the animation deck (``customanimationspanel.ui`` ``effect_list`` GtkTreeView) and the
  transition deck (``slidetransitionspanel.ui`` ``transitions_icons`` GtkIconView, item-width 55)
  are genuine PanelLayout-hosted sidebar decks: each panel's ``PanelLayout(...)`` constructor
  call-site literal must exist as real (comment-stripped) code and bind the ``.ui`` root object id,
  and the ``.ui`` (comment-stripped) must carry that root id plus the pinned content widget class +
  id. A GtkTreeView<->GtkIconView swap fails closed.
* ``divergences`` -- the transition-gallery IconView-vs-design-grid mismatch, the presenter-console
  token-family-without-implemented-control gap, and the pre-existing prototype-features.json catalog
  gap are flagged, not reconciled: their ``status`` must stay ``specified`` and is never promoted.

It is source evidence only: ``runtime_verified`` is false throughout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/impress-presenter-surfaces.json"
CONTRACT_NAME = "material-impress-presenter-surfaces"
INVENTORY_ROW = "WIN-IM-004"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# C++ comment / raw-string stripping (mirrors check-windows-sidebar-panels.py) so a commented-out
# or raw-string-embedded marker can never silently satisfy or break an assertion.
# --------------------------------------------------------------------------------------------------
_CPP_RAW_STRING = re.compile(
    r'(?:u8|u|U|L)?R"(?P<delimiter>[^ ()\\\t\r\n]{0,16})\(.*?\)(?P=delimiter)"',
    re.DOTALL,
)


def strip_cpp_non_code(source: str) -> str:
    source = _CPP_RAW_STRING.sub("", source)
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _strip_xml_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


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

    component = registry.get("component")
    if isinstance(component, dict) and isinstance(component.get("file"), str):
        paths.add(component["file"])

    for panel in registry.get("panels", []) or []:
        if not isinstance(panel, dict):
            continue
        for key in ("impl_source", "ui_source"):
            value = panel.get(key)
            if isinstance(value, str):
                paths.add(value)

    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")

    # Enumerate the presenter console sources so the absence marker runs against the real tree and a
    # vanished directory fails closed. Loaded into contents so mutation tests can exercise it.
    console = registry.get("console_absence")
    if isinstance(console, dict) and isinstance(console.get("dir"), str):
        console_dir = repo_root / console["dir"]
        if console_dir.is_dir():
            for source in sorted(console_dir.glob("*.cxx")) + sorted(console_dir.glob("*.hxx")):
                rel = source.relative_to(repo_root).as_posix()
                contents[rel] = source.read_text(encoding="utf-8")

    return registry, contents


# --------------------------------------------------------------------------------------------------
# presenter.component registration
# --------------------------------------------------------------------------------------------------
def _validate_component(
    component: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(component, dict):
        errors.append("component:object required")
        return
    file_rel = component.get("file")
    text = contents.get(file_rel) if isinstance(file_rel, str) else None
    if text is None:
        errors.append("component:file missing (presenter.component)")
        return
    xml = _strip_xml_comments(text)
    implementation = component.get("implementation")
    constructor = component.get("constructor")
    service = component.get("service")
    if not (isinstance(implementation, str) and isinstance(constructor, str) and isinstance(service, str)):
        errors.append("component:implementation/constructor/service must be strings")
        return
    if f'name="{implementation}"' not in xml:
        errors.append(
            f"component:implementation name={implementation!r} missing in presenter.component "
            "(presenter console CppComponent no longer registered)"
        )
    if f'constructor="{constructor}"' not in xml:
        errors.append(
            f"component:constructor={constructor!r} missing in presenter.component "
            "(protocol-handler factory wiring drifted)"
        )
    if f'<service name="{service}"' not in xml:
        errors.append(
            f"component:service={service!r} missing in presenter.component "
            "(presenter console no longer implements the ProtocolHandler service)"
        )


# --------------------------------------------------------------------------------------------------
# console absence marker
# --------------------------------------------------------------------------------------------------
def _validate_console_absence(
    console: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(console, dict):
        errors.append("console_absence:object required")
        return
    console_dir = console.get("dir")
    forbidden = console.get("forbidden_markers")
    min_cxx = console.get("min_cxx_files")
    if not isinstance(console_dir, str) or not console_dir:
        errors.append("console_absence:dir:non-empty string required")
        return
    if not isinstance(forbidden, list) or not forbidden:
        errors.append("console_absence:forbidden_markers:non-empty array required")
        return
    if isinstance(min_cxx, bool) or not isinstance(min_cxx, int) or min_cxx < 1:
        errors.append("console_absence:min_cxx_files:positive integer required")
        return

    prefix = console_dir.rstrip("/") + "/"
    cxx_files = [rel for rel in contents if rel.startswith(prefix) and rel.endswith(".cxx")]
    if len(cxx_files) < min_cxx:
        errors.append(
            f"console_absence:only {len(cxx_files)} .cxx file(s) discovered under {console_dir} "
            f"(expected >= {min_cxx}); the console tree moved and the absence marker cannot be "
            "asserted -- fail closed"
        )
        return

    scanned = [
        rel for rel in contents
        if rel.startswith(prefix) and (rel.endswith(".cxx") or rel.endswith(".hxx"))
    ]
    for rel in sorted(scanned):
        code = strip_cpp_non_code(contents[rel])
        for marker in forbidden:
            if isinstance(marker, str) and marker in code:
                errors.append(
                    f"console_absence:{rel} now references {marker!r} -- the presenter console gained "
                    "a VCL widget-theme hook that this row's architecture-divergence note does not "
                    "document (update the divergence note and author archive-backed design first)"
                )


# --------------------------------------------------------------------------------------------------
# animation / transition PanelLayout decks
# --------------------------------------------------------------------------------------------------
def _validate_panels(
    panels: Any, contents: Mapping[str, str], errors: list[str]
) -> None:
    if not isinstance(panels, list) or not panels:
        errors.append("panels:non-empty array required")
        return
    seen_ids: set[str] = set()
    for index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            errors.append(f"panels[{index}]:object required")
            continue
        pid = panel.get("id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"panels[{index}]:id:non-empty string required")
            continue
        context = f"panels[{pid}]"
        if pid in seen_ids:
            errors.append(f"{context}:id:duplicate")
        seen_ids.add(pid)

        impl_rel = panel.get("impl_source")
        call = panel.get("panel_layout_call")
        ui_rel = panel.get("ui_source")
        root_id = panel.get("root_object_id")
        widget = panel.get("content_widget")

        # PanelLayout constructor call-site binds the .cxx to its .ui root object id.
        impl_text = contents.get(impl_rel) if isinstance(impl_rel, str) else None
        if impl_text is None:
            errors.append(f"{context}:impl_source file missing: {impl_rel}")
        elif not isinstance(call, str) or not call:
            errors.append(f"{context}:panel_layout_call:non-empty string required")
        elif call not in strip_cpp_non_code(impl_text):
            errors.append(
                f"{context}:PanelLayout call site missing from real code in {impl_rel} "
                "(the sidebar deck host binding drifted)"
            )

        # The .ui must carry the root id and the pinned content widget class + id.
        ui_text = contents.get(ui_rel) if isinstance(ui_rel, str) else None
        if ui_text is None:
            errors.append(f"{context}:ui_source file missing: {ui_rel}")
            continue
        ui_xml = _strip_xml_comments(ui_text)
        if not isinstance(root_id, str) or not root_id:
            errors.append(f"{context}:root_object_id:non-empty string required")
        elif f'id="{root_id}"' not in ui_xml:
            errors.append(f"{context}:root object id=\"{root_id}\" missing in {ui_rel}")

        if not isinstance(widget, dict):
            errors.append(f"{context}:content_widget:object required")
            continue
        wclass = widget.get("class")
        wid = widget.get("id")
        if not (isinstance(wclass, str) and isinstance(wid, str)):
            errors.append(f"{context}:content_widget:class/id must be strings")
            continue
        anchor = f'<object class="{wclass}" id="{wid}">'
        if anchor not in ui_xml:
            errors.append(
                f"{context}:content widget {anchor!r} missing in {ui_rel} "
                "(GtkTreeView<->GtkIconView class swap or renamed content surface)"
            )
        item_width = widget.get("item_width")
        if isinstance(item_width, str):
            if f'<property name="item-width">{item_width}</property>' not in ui_xml:
                errors.append(
                    f"{context}:content widget {wid} item-width {item_width!r} drift in {ui_rel}"
                )


# --------------------------------------------------------------------------------------------------
# honest divergence flags (never promoted)
# --------------------------------------------------------------------------------------------------
def _validate_divergences(divergences: Any, errors: list[str]) -> None:
    if not isinstance(divergences, dict) or not divergences:
        errors.append("divergences:non-empty object required")
        return
    for name in ("transition_gallery", "presenter_console_chrome", "catalog_gap"):
        block = divergences.get(name)
        if not isinstance(block, dict):
            errors.append(f"divergences:{name}:object required")
            continue
        if block.get("status") != "specified":
            errors.append(
                f"divergences:{name}:status must stay 'specified' "
                "(flagged honestly as an open divergence / documented gap; never promoted to an "
                "implemented claim)"
            )


# --------------------------------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------------------------------
def violations(registry: Mapping[str, Any], contents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != CONTRACT_NAME:
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("inventory_row") != INVENTORY_ROW:
        errors.append("registry:inventory_row:must be WIN-IM-004")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    _validate_component(registry.get("component"), contents, errors)
    _validate_console_absence(registry.get("console_absence"), contents, errors)
    _validate_panels(registry.get("panels"), contents, errors)
    _validate_divergences(registry.get("divergences"), errors)

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
        print(f"Impress presenter surfaces contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    print(
        "Impress presenter surfaces contract passed: pinned the presenter console CppComponent "
        "registration, the zero-VCL-widget-theme-hook absence across sd/source/console, the "
        f"{len(registry['panels'])} PanelLayout content surfaces (effect_list GtkTreeView + "
        "transitions_icons GtkIconView), and the transition-grid / presenter-chrome / catalog-gap "
        "divergences spec-only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
