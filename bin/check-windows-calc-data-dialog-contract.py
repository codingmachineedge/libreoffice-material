#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed contract for the Calc Data-menu dialog family (WIN-CA-005).

``qa/windows-ui-contract/calc-data-dialogs.json`` carries two validated sections
for the Calc "filters, sort, data, pivot, charts, conditional formatting" family.

Part A -- ``pinned_dialogs`` (composition-PINNING of the six top-level GtkDialog
shells that anchor the Data-menu core: Sort, Subtotals, Standard Filter, Advanced
Filter, Pivot Filter, Conditional Format Manager). For each dialog the checker
parses the real ``.ui`` with ElementTree and fails closed on:

* a missing/renamed root ``GtkDialog`` id;
* a reordered / added / removed action-widget (the exact ordered
  ``(response, id)`` footer sequence is pinned);
* a footer-role drift -- the default-response button must still carry
  ``has-default`` and the secondary-response button must still be packed
  ``secondary`` (hyphen/underscore property spellings are normalized);

and greps the declared ``controller_source`` (comments stripped) for the exact
weld controller base-class token plus the ``_ustr`` ``.ui`` load-path and dialog-id
string literals. The six controller bases are pinned PER-DIALOG on purpose:
``ScPivotFilterDlg`` genuinely uses ``GenericDialogController`` while the others
use ``SfxTabDialogController`` or ``ScAnyRefDlgController`` -- a real, verified
difference, never normalized away. The pin covers only the outer shell/footer and
the controller binding, never the content inside the tab pages.

Part B -- ``surface_ledger`` (a generated, byte-for-byte-diffed enumeration of the
row's other in-scope surfaces so the boundary is honest instead of silent). It
classifies each in-scope ``.ui`` as ``standard-anatomy`` (inherits chapter-8.1
modal anatomy once compiled) or ``custom-paint-guard-required`` (its owning source
subclasses ``weld::CustomWidgetController`` / ``EditBrowseBox`` or holds a
``weld::CustomWeld`` preview member -- the guard-bound previews a future build-bound
slice must convert). Scope: an explicit maintained set of sc data-family ``.ui``
files, plus a full git walk of ``chart2/uiconfig/ui`` (so a NEW chart2 ``.ui``
fails the diff until it is classified). Every ``custom-paint`` classification's
evidence token is verified present in its owning source, so the ledger is grounded
in real source, not asserted. Default mode diffs the checked-in ledger against a
fresh enumeration (added/removed/reclassified file or hand-edit fails closed);
``--regenerate`` rewrites ONLY the ledger section (the hand-authored
``pinned_dialogs`` are preserved).

The ledger is additive per-surface evidence; it does NOT reassign ownership and
does NOT claim to be a full closure (WIN-SYS-016's ui-registry.json remains the
owner-level authority that every sc/ and chart2/ ``.ui`` is enumerated). This row
does NOT duplicate the two ``sc/source/ui/view/tabvwshf.cxx`` destructive-sheet
migrations already tracked by dialog-anatomy-policy.json.

It is source evidence only: ``runtime_verified`` is false throughout -- no native
build, dialog pixels, FLOW, A11Y, LOC, PERF or COMPAT is claimed, and a footer
pin cannot detect runtime code that hides/relabels an action-widget after
construction (a specified-only limitation).
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/calc-data-dialogs.json"

CHART2_UI_GLOB = "chart2/uiconfig/ui/*.ui"

# Explicit maintained sc data-family scope (the row's filter/sort/pivot/subtotal/
# conditional-format/data surfaces beyond the six pinned dialogs). Enumerated
# explicitly because sc/uiconfig/scalc/ui has no clean data-only directory
# boundary; the full owner-level closure of every sc/ .ui is WIN-SYS-016's job.
SC_SCOPE: tuple[str, ...] = (
    "sc/uiconfig/scalc/ui/sortcriteriapage.ui",
    "sc/uiconfig/scalc/ui/sortkey.ui",
    "sc/uiconfig/scalc/ui/sortoptionspage.ui",
    "sc/uiconfig/scalc/ui/sortwarning.ui",
    "sc/uiconfig/scalc/ui/subtotalgrppage.ui",
    "sc/uiconfig/scalc/ui/subtotaloptionspage.ui",
    "sc/uiconfig/scalc/ui/filterdropdown.ui",
    "sc/uiconfig/scalc/ui/filterlist.ui",
    "sc/uiconfig/scalc/ui/filtersubdropdown.ui",
    "sc/uiconfig/scalc/ui/datafielddialog.ui",
    "sc/uiconfig/scalc/ui/datafieldoptionsdialog.ui",
    "sc/uiconfig/scalc/ui/pivotcalcfielddialog.ui",
    "sc/uiconfig/scalc/ui/pivotfielddialog.ui",
    "sc/uiconfig/scalc/ui/pivottablelayoutdialog.ui",
    "sc/uiconfig/scalc/ui/selectsource.ui",
    "sc/uiconfig/scalc/ui/condformatmanager.ui",
    "sc/uiconfig/scalc/ui/conditionaleasydialog.ui",
    "sc/uiconfig/scalc/ui/conditionalentry.ui",
    "sc/uiconfig/scalc/ui/conditionaliconset.ui",
    "sc/uiconfig/scalc/ui/databaroptions.ui",
    "sc/uiconfig/scalc/ui/consolidatedialog.ui",
    "sc/uiconfig/scalc/ui/definedatabaserangedialog.ui",
    "sc/uiconfig/scalc/ui/multipleoperationsdialog.ui",
    "sc/uiconfig/scalc/ui/validationdialog.ui",
    "sc/uiconfig/scalc/ui/validationcriteriapage.ui",
    "sc/uiconfig/scalc/ui/validationhelptabpage.ui",
    "sc/uiconfig/scalc/ui/textimportcsv.ui",
    "sc/uiconfig/scalc/ui/textimportoptions.ui",
)

# ui_file -> (evidence source, evidence token). A classification of
# custom-paint-guard-required is only emitted if the token is genuinely present
# (comment-stripped) in the named owning source. Everything in scope but not here
# is standard-anatomy.
CUSTOM_PAINT: Mapping[str, dict[str, str]] = {
    "sc/uiconfig/scalc/ui/conditionalentry.ui": {
        "source": "sc/source/ui/inc/condformatdlgentry.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> mxWdPreview;",
    },
    "sc/uiconfig/scalc/ui/textimportcsv.ui": {
        "source": "sc/source/ui/inc/csvcontrol.hxx",
        "token": "class SAL_DLLPUBLIC_RTTI ScCsvControl : public weld::CustomWidgetController",
    },
    "chart2/uiconfig/ui/chartdatadialog.ui": {
        "source": "chart2/source/controller/dialogs/DataBrowser.hxx",
        "token": "class DataBrowser : public ::svt::EditBrowseBox",
    },
    "chart2/uiconfig/ui/tp_ChartType.ui": {
        "source": "chart2/source/controller/dialogs/tp_ChartType.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xSubTypeListWin;",
    },
    "chart2/uiconfig/ui/tp_3D_SceneIllumination.ui": {
        "source": "chart2/source/controller/dialogs/tp_3D_SceneIllumination.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xPreviewWnd;",
    },
    "chart2/uiconfig/ui/tp_axisLabel.ui": {
        "source": "chart2/source/controller/dialogs/tp_AxisLabel.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xCtrlDialWin;",
    },
    "chart2/uiconfig/ui/titlerotationtabpage.ui": {
        "source": "chart2/source/controller/dialogs/tp_TitleRotation.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xCtrlDialWin;",
    },
    "chart2/uiconfig/ui/tp_PolarOptions.ui": {
        "source": "chart2/source/controller/dialogs/tp_PolarOptions.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xAngleDialWin;",
    },
    "chart2/uiconfig/ui/tp_DataLabel.ui": {
        "source": "chart2/source/controller/dialogs/res_DataLabel.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xDC_DialWin;",
    },
    "chart2/uiconfig/ui/dlg_DataLabel.ui": {
        "source": "chart2/source/controller/dialogs/res_DataLabel.hxx",
        "token": "std::unique_ptr<weld::CustomWeld> m_xDC_DialWin;",
    },
}

STANDARD = "standard-anatomy"
CUSTOM = "custom-paint-guard-required"

LEDGER_SOURCE_NOTE = (
    "Generated per-surface classification of the Calc data/chart family beyond the six "
    "pinned dialogs. Each entry is standard-anatomy (inherits chapter-8.1 modal anatomy "
    "once compiled) or custom-paint-guard-required (owning source subclasses "
    "weld::CustomWidgetController/EditBrowseBox or holds a weld::CustomWeld preview member). "
    "Regenerate with --regenerate. Additive per-surface evidence, not an ownership "
    "reassignment and not a full closure; WIN-SYS-016 ui-registry.json remains the "
    "owner-level authority. Source composition only -- never dialog pixels, FLOW, A11Y, "
    "LOC, PERF or COMPAT."
)


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
    return re.sub(r"\s+", " ", source).strip()


def _norm_prop_name(name: str | None) -> str:
    return (name or "").replace("_", "-")


# --------------------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------------------
def _pinned_paths(registry: Mapping[str, Any]) -> set[str]:
    paths: set[str] = set()
    for dialog in registry.get("pinned_dialogs", []) or []:
        if not isinstance(dialog, dict):
            continue
        for key in ("ui_file", "controller_source"):
            value = dialog.get(key)
            if isinstance(value, str):
                paths.add(value)
    return paths


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    paths = _pinned_paths(registry)
    for evidence in CUSTOM_PAINT.values():
        paths.add(evidence["source"])
    contents: dict[str, str] = {}
    for relative in paths:
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# Part A -- pinned dialog shells
# --------------------------------------------------------------------------------------------------
def _find_dialog(root: ET.Element, dialog_id: str) -> ET.Element | None:
    for obj in root.iter("object"):
        if obj.get("class") == "GtkDialog" and obj.get("id") == dialog_id:
            return obj
    return None


def _actual_action_widgets(dialog: ET.Element) -> list[dict[str, str]]:
    holder = dialog.find("action-widgets")
    result: list[dict[str, str]] = []
    if holder is None:
        return result
    for widget in holder.findall("action-widget"):
        result.append(
            {"response": widget.get("response", ""), "id": (widget.text or "").strip()}
        )
    return result


def _button_roles(root: ET.Element) -> dict[str, dict[str, bool]]:
    """Map every GtkButton id -> {has_default, secondary}.

    ``has-default`` lives on the button object; ``secondary`` lives on the sibling
    ``<packing>`` within the same ``<child>``. Property names may use hyphens or
    underscores, so both are normalized.
    """
    roles: dict[str, dict[str, bool]] = {}
    for child in root.iter("child"):
        obj = child.find("object")
        if obj is None or obj.get("class") != "GtkButton":
            continue
        button_id = obj.get("id")
        if not button_id:
            continue
        has_default = any(
            _norm_prop_name(p.get("name")) == "has-default" and (p.text or "").strip() == "True"
            for p in obj.findall("property")
        )
        packing = child.find("packing")
        secondary = packing is not None and any(
            _norm_prop_name(p.get("name")) == "secondary" and (p.text or "").strip() == "True"
            for p in packing.findall("property")
        )
        roles[button_id] = {"has_default": has_default, "secondary": secondary}
    return roles


def _validate_pinned_dialog(
    dialog: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    ui_file = dialog.get("ui_file")
    dialog_id = dialog.get("dialog_id")
    context = f"pinned[{dialog_id or ui_file}]"
    if not isinstance(ui_file, str) or not isinstance(dialog_id, str):
        errors.append(f"{context}:ui_file/dialog_id must be strings")
        return
    text = contents.get(ui_file)
    if text is None:
        errors.append(f"{context}:ui file {ui_file} missing")
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        errors.append(f"{context}:unparseable xml:{error}")
        return

    dialog_obj = _find_dialog(root, dialog_id)
    if dialog_obj is None:
        errors.append(f"{context}:root GtkDialog id {dialog_id!r} missing/renamed in {ui_file}")
        return

    # Exact ordered action-widget footer.
    actual = _actual_action_widgets(dialog_obj)
    expected = dialog.get("action_widgets")
    if not isinstance(expected, list) or not expected:
        errors.append(f"{context}:action_widgets:non-empty array required")
    else:
        exp_seq = [
            (str(w.get("response")), str(w.get("id"))) for w in expected if isinstance(w, dict)
        ]
        act_seq = [(w["response"], w["id"]) for w in actual]
        if act_seq != exp_seq:
            errors.append(
                f"{context}:action-widget footer drift: pinned {exp_seq} but found {act_seq} "
                "(reordered/added/removed action-widget)"
            )

    # Footer roles: default button is has-default, secondary button is packed secondary.
    roles = _button_roles(root)
    id_for_response = {w["response"]: w["id"] for w in actual}
    default_response = dialog.get("footer_default_response")
    if isinstance(default_response, str):
        button_id = id_for_response.get(default_response)
        if button_id is None:
            errors.append(f"{context}:footer_default_response {default_response} has no action-widget")
        elif not roles.get(button_id, {}).get("has_default"):
            errors.append(
                f"{context}:footer default drift: button {button_id!r} "
                f"(response {default_response}) is not marked has-default"
            )
    secondary_response = dialog.get("footer_secondary_response")
    if isinstance(secondary_response, str):
        button_id = id_for_response.get(secondary_response)
        if button_id is None:
            errors.append(f"{context}:footer_secondary_response {secondary_response} has no action-widget")
        elif not roles.get(button_id, {}).get("secondary"):
            errors.append(
                f"{context}:footer secondary drift: button {button_id!r} "
                f"(response {secondary_response}) is not packed secondary"
            )

    # Controller binding: base class + .ui load-path + dialog-id literals.
    controller_source = dialog.get("controller_source")
    controller_base = dialog.get("controller_base")
    load_literal = dialog.get("ui_load_path_literal")
    source = contents.get(controller_source) if isinstance(controller_source, str) else None
    if source is None:
        errors.append(f"{context}:controller_source {controller_source} missing")
        return
    code = _without_cpp_comments(source)
    if isinstance(controller_base, str) and controller_base not in code:
        errors.append(
            f"{context}:controller base {controller_base!r} not bound in {controller_source} "
            "(per-dialog base must not drift)"
        )
    if isinstance(load_literal, str) and load_literal not in code:
        errors.append(
            f"{context}:.ui load-path literal {load_literal!r} missing in {controller_source}"
        )
    if f'"{dialog_id}"' not in code:
        errors.append(f"{context}:dialog-id literal \"{dialog_id}\" missing in {controller_source}")


# --------------------------------------------------------------------------------------------------
# Part B -- generated surface ledger
# --------------------------------------------------------------------------------------------------
def git_ui_paths(repo_root: Path, glob: str) -> list[str]:
    command = [
        "git", "-C", str(repo_root), "ls-files", "-z",
        "--cached", "--others", "--exclude-standard", "--", glob,
    ]
    try:
        completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as error:
        raise ValidationError(f"cannot run git to discover .ui files: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"git .ui discovery failed: {detail}")
    seen: set[str] = set()
    paths: list[str] = []
    for raw in completed.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw:
            continue
        if not (repo_root / PurePosixPath(raw)).is_file():
            continue
        posix = PurePosixPath(raw).as_posix()
        if posix not in seen:
            seen.add(posix)
            paths.append(posix)
    return sorted(paths)


def _classify(ui_file: str, repo_root: Path, contents: Mapping[str, str]) -> dict[str, Any]:
    evidence = CUSTOM_PAINT.get(ui_file)
    if evidence is None:
        return {"ui_file": ui_file, "classification": STANDARD, "evidence": None}
    source_path = evidence["source"]
    token = evidence["token"]
    source = contents.get(source_path)
    if source is None:
        disk = repo_root / source_path
        source = disk.read_text(encoding="utf-8") if disk.is_file() else None
    if source is None or _collapse_ws(token) not in _collapse_ws(_without_cpp_comments(source)):
        raise ValidationError(
            f"custom-paint evidence for {ui_file} not found: token {token!r} absent from "
            f"{source_path} (reclassify or fix the evidence)"
        )
    return {
        "ui_file": ui_file,
        "classification": CUSTOM,
        "evidence": {"source": source_path, "token": token},
    }


def build_surface_ledger(
    repo_root: Path, contents: Mapping[str, str], pinned_ui: set[str]
) -> dict[str, Any]:
    ui_files: list[str] = []
    for path in SC_SCOPE:
        if path in pinned_ui:
            continue
        if not (repo_root / path).is_file():
            raise ValidationError(f"scoped sc data-family file missing: {path}")
        ui_files.append(path)
    for path in git_ui_paths(repo_root, CHART2_UI_GLOB):
        if path in pinned_ui:
            continue
        ui_files.append(path)

    entries = [_classify(path, repo_root, contents) for path in sorted(set(ui_files))]
    custom = sum(1 for e in entries if e["classification"] == CUSTOM)
    return {
        "source_note": LEDGER_SOURCE_NOTE,
        "counts": {
            "total": len(entries),
            "standard_anatomy": len(entries) - custom,
            "custom_paint": custom,
        },
        "entries": entries,
    }


def _validate_surface_ledger(
    registry: Mapping[str, Any], built: Mapping[str, Any], errors: list[str]
) -> None:
    checked_in = registry.get("surface_ledger")
    if not isinstance(checked_in, dict):
        errors.append("registry:surface_ledger:object required")
        return
    if checked_in.get("source_note") != built["source_note"]:
        errors.append("surface_ledger:source_note drifted from the generator")
    if checked_in.get("counts") != built["counts"]:
        errors.append(
            f"surface_ledger:counts drift: checked-in {checked_in.get('counts')!r} "
            f"vs generated {built['counts']!r}"
        )
    expected = {e["ui_file"]: e for e in built["entries"]}
    actual_list = checked_in.get("entries")
    if not isinstance(actual_list, list):
        errors.append("surface_ledger:entries must be a list")
        return
    actual = {}
    for entry in actual_list:
        if not isinstance(entry, dict) or "ui_file" not in entry:
            errors.append("surface_ledger:entry malformed")
            continue
        actual[entry["ui_file"]] = entry
    missing = set(expected) - set(actual)
    stale = set(actual) - set(expected)
    if missing:
        errors.append(
            f"surface_ledger:{len(missing)} in-scope surface(s) missing from ledger: "
            + ", ".join(sorted(missing)[:12])
        )
    if stale:
        errors.append(
            f"surface_ledger:{len(stale)} ledger entr(y/ies) with no in-scope source: "
            + ", ".join(sorted(stale)[:12])
        )
    for ui_file in sorted(set(expected) & set(actual)):
        if expected[ui_file] != actual[ui_file]:
            errors.append(
                f"surface_ledger:{ui_file} drifted from generated classification: "
                f"expected {expected[ui_file]!r}, found {actual[ui_file]!r}"
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
    if registry.get("contract") != "material-calc-data-dialogs":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    dialogs = registry.get("pinned_dialogs")
    if not isinstance(dialogs, list) or not dialogs:
        errors.append("registry:pinned_dialogs:non-empty array required")
        dialogs = []
    pinned_ui: set[str] = set()
    for dialog in dialogs:
        if isinstance(dialog, dict) and isinstance(dialog.get("ui_file"), str):
            pinned_ui.add(dialog["ui_file"])
        _validate_pinned_dialog(dialog if isinstance(dialog, dict) else {}, contents, errors)

    try:
        built = build_surface_ledger(repo_root, contents, pinned_ui)
    except ValidationError as error:
        errors.append(f"surface_ledger:generation failed: {error}")
    else:
        _validate_surface_ledger(registry, built, errors)
        # Belt and braces: no pinned dialog may also appear in the ledger.
        ledger_files = {
            e.get("ui_file")
            for e in (registry.get("surface_ledger", {}) or {}).get("entries", [])
            if isinstance(e, dict)
        }
        overlap = pinned_ui & ledger_files
        if overlap:
            errors.append(f"surface_ledger:pinned dialog double-listed: {', '.join(sorted(overlap))}")

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents, repo_root)
    if errors:
        raise ValidationError("\n".join(errors))


def regenerate(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    pinned_ui = {
        d["ui_file"]
        for d in registry.get("pinned_dialogs", [])
        if isinstance(d, dict) and isinstance(d.get("ui_file"), str)
    }
    built = build_surface_ledger(repo_root, contents, pinned_ui)
    updated = copy.deepcopy(registry)
    updated["surface_ledger"] = built
    path = repo_root / REGISTRY_PATH
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(updated, indent=2, ensure_ascii=False) + "\n")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite only the surface_ledger section deterministically",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    try:
        if args.regenerate:
            regenerate(repo_root)
        validate_repository(repo_root)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Calc data-dialog contract failed:\n{error}", file=sys.stderr)
        return 1
    registry, _ = load_repository(repo_root)
    ledger = registry.get("surface_ledger", {})
    counts = ledger.get("counts", {}) if isinstance(ledger, dict) else {}
    print(
        "Calc data-dialog contract passed: "
        f"{len(registry.get('pinned_dialogs', []))} pinned Data-menu dialog shells (footer + "
        f"per-dialog controller) and a {counts.get('total', 0)}-surface ledger "
        f"({counts.get('custom_paint', 0)} custom-paint-guard-required, "
        f"{counts.get('standard_anatomy', 0)} standard-anatomy)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
