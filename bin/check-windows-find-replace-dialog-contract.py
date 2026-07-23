#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed Find & Replace dialog closure contract (WIN-DLG-005).

``qa/windows-ui-contract/find-replace-dialog.json`` is a row-identity artifact that ties the four
already-real satellite contracts covering the Find & Replace surface into one WIN-DLG-005 pin and
adds the one fact none of them currently record: the dialog's genuinely-modeless C++ base class.

All evidence is static source/XML/JSON/CSV reads -- no native build, no runtime, no pixels
(``runtime_verified`` is false throughout). The checker validates, fail-closed:

1. include/svx/srchdlg.hxx contains
   ``class SVX_DLLPUBLIC SvxSearchDialog final : public SfxModelessDialogController`` verbatim, so the
   dialog can never silently become an application-modal blocking window and break live
   find-as-you-type / Find All over the real document (04-inputs.md 5-6, 08-dialogs.md 8.5).
2. find-replace-fieldset.json's own validate() (WIN-INP-006) is re-run in-process -- real reuse, not
   a re-implementation -- so a broken fieldset also fails this row.
3. regex-search-integrations.json's ``document.find-replace`` entry is ``source-integrated`` and its
   ui_file/header_file/source_file/entry_id/entry_member/builder_member/controller_member are
   byte-identical to find-replace-fieldset.json's find_field equivalents -- catches the two
   independently-maintained registries drifting apart on the same real symbols.
4. bin/check-windows-regex-builder-foundation.py's validate_repository() is re-run in-process (py3.9
   sys.modules-before-exec_module order) -- a broken shared ICU/popover engine also fails this row.
5. notification-producer-policy.json carries the ``srchdlg-replace-all-outcome`` producer pointing at
   svx/source/dialog/srchdlg.cxx::lcl_NotifyMaterialReplaceOutcome (read-only; only this producer is
   asserted, since the notifications cluster owns and appends to that file).
6. classify_route/_scan_dialog_signals (imported the way check-windows-security-prompt-modality.py
   imports them) still classify findreplacedialog.ui's FindReplaceDialog as ``native-exclusion``, and
   the router's computed (policy, reason) equals the checked-in dialog-notification-policy.csv row --
   a regression guard against an accidental future reclassification to the notification form.
7. the ``g_bMaterialReplaceAllPending`` one-shot flag is armed exactly once and cleared exactly once
   inside CommandHdl_Impl's Replace-All branch, pinning the code's own documented no-leak invariant.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable


REPOSITORY = Path(__file__).resolve().parents[1]

REGISTRY_PATH = "qa/windows-ui-contract/find-replace-dialog.json"
FIELDSET_REGISTRY = "qa/windows-ui-contract/find-replace-fieldset.json"
INTEGRATIONS_REGISTRY = "qa/windows-ui-contract/regex-search-integrations.json"
PRODUCER_POLICY = "qa/windows-ui-contract/notification-producer-policy.json"
POLICY_CSV = "qa/windows-ui-contract/dialog-notification-policy.csv"

HEADER_FILE = "include/svx/srchdlg.hxx"
SOURCE_FILE = "svx/source/dialog/srchdlg.cxx"
UI_FILE = "svx/uiconfig/ui/findreplacedialog.ui"

FIELDSET_MODULE = "bin/check-windows-find-replace-fieldset.py"
FOUNDATION_MODULE = "bin/check-windows-regex-builder-foundation.py"
ROUTER_MODULE = "bin/check-windows-dialog-notification-contract.py"


class ValidationError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------------
# Module import (py3.9 sys.modules-before-exec_module pitfall).
#
# The three reused checkers all use ``from __future__ import annotations`` plus frozen/ordered
# dataclasses; under the py 3.9 launcher each must be registered in sys.modules *before* exec_module or
# the dataclass machinery cannot resolve the module.  We import the pure helpers only and never trigger
# any git-based discovery path.
# --------------------------------------------------------------------------------------------------
def _load_module(repo_root: Path, relative: str, module_name: str):
    module_path = repo_root / relative
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # MUST precede exec_module (py3.9 dataclass pitfall)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------------------------------
def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def _without_cpp_comments(source: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)


def _function_body(source: str, signature: str) -> str | None:
    start = source.find(signature)
    if start < 0:
        return None
    opening = source.find("{", start + len(signature))
    if opening < 0:
        return None
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    return None


def _tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _resolve_path(data: Any, dotted: str) -> Any:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


# --------------------------------------------------------------------------------------------------
# Context: everything the checks read, so the mutation suite can flip any single anchor in-memory.
# --------------------------------------------------------------------------------------------------
class Context:
    def __init__(
        self,
        registry: dict[str, Any],
        fieldset: dict[str, Any],
        integrations: dict[str, Any],
        producer_policy: dict[str, Any],
        csv_entries: list[Any],
        contents: dict[str, str],
        router: Any,
        rerun_fieldset: Callable[[], None],
        rerun_foundation: Callable[[], None],
    ) -> None:
        self.registry = registry
        self.fieldset = fieldset
        self.integrations = integrations
        self.producer_policy = producer_policy
        self.csv_entries = csv_entries
        self.contents = contents
        self.router = router
        self.rerun_fieldset = rerun_fieldset
        self.rerun_foundation = rerun_foundation


def load_context(repo_root: Path = REPOSITORY) -> Context:
    repo_root = repo_root.resolve()
    router = _load_module(repo_root, ROUTER_MODULE, "check_windows_dialog_notification_contract")
    fieldset_mod = _load_module(repo_root, FIELDSET_MODULE, "check_windows_find_replace_fieldset")
    foundation_mod = _load_module(
        repo_root, FOUNDATION_MODULE, "check_windows_regex_builder_foundation"
    )

    registry = _read_json(repo_root / REGISTRY_PATH)
    fieldset = _read_json(repo_root / FIELDSET_REGISTRY)
    integrations = _read_json(repo_root / INTEGRATIONS_REGISTRY)
    producer_policy = _read_json(repo_root / PRODUCER_POLICY)
    csv_entries = router.read_registry(repo_root / POLICY_CSV)

    contents: dict[str, str] = {}
    for relative in (HEADER_FILE, SOURCE_FILE, UI_FILE):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")

    def rerun_fieldset() -> None:
        fieldset_mod.validate(repo_root, repo_root / FIELDSET_REGISTRY)

    def rerun_foundation() -> None:
        foundation_mod.validate_repository(repo_root)

    return Context(
        registry,
        fieldset,
        integrations,
        producer_policy,
        csv_entries,
        contents,
        router,
        rerun_fieldset,
        rerun_foundation,
    )


# --------------------------------------------------------------------------------------------------
# Individual checks.
# --------------------------------------------------------------------------------------------------
def _check_registry_schema(registry: dict[str, Any], errors: list[str]) -> None:
    if registry.get("schema_version") != 1:
        errors.append("registry:schema_version:must be 1")
    if registry.get("contract") != "windows-native-find-replace-dialog-closure":
        errors.append("registry:contract:unexpected value")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("inventory_id") != "WIN-DLG-005":
        errors.append("registry:inventory_id:must be WIN-DLG-005")


def _check_modeless_base_class(context: Context, errors: list[str]) -> None:
    block = context.registry.get("modeless_base_class")
    if not isinstance(block, dict):
        errors.append("registry:modeless_base_class:object required")
        return
    marker = block.get("marker")
    if not isinstance(marker, str) or not marker.strip():
        errors.append("registry:modeless_base_class:marker non-empty text required")
        return
    if "SfxModelessDialogController" not in marker:
        errors.append(
            "registry:modeless_base_class:marker must pin SfxModelessDialogController "
            "(a modeless base class); GenericDialogController would be application-modal"
        )
    header = context.contents.get(HEADER_FILE)
    if header is None:
        errors.append(f"modeless-base:missing {HEADER_FILE}")
        return
    if marker not in _without_cpp_comments(header):
        errors.append(
            f"modeless-base:marker not found verbatim in {HEADER_FILE}: {marker!r} "
            "(the dialog must stay modeless so find-as-you-type keeps the canvas live)"
        )


def _check_fieldset_reuse(context: Context, errors: list[str]) -> None:
    try:
        context.rerun_fieldset()
    except Exception as error:  # noqa: BLE001 - any failure of the reused contract fails this row
        errors.append(f"fieldset-reuse:WIN-INP-006 find-replace-fieldset contract failed: {error}")


def _check_foundation_reuse(context: Context, errors: list[str]) -> None:
    try:
        context.rerun_foundation()
    except Exception as error:  # noqa: BLE001 - any failure of the shared engine fails this row
        errors.append(
            f"foundation-reuse:regex-builder-foundation contract failed: {error}"
        )


def _check_regex_integration_cross_field(context: Context, errors: list[str]) -> None:
    satellites = context.registry.get("satellite_contracts")
    if not isinstance(satellites, dict):
        errors.append("registry:satellite_contracts:object required")
        return
    spec = satellites.get("regex_integration")
    if not isinstance(spec, dict):
        errors.append("registry:satellite_contracts.regex_integration:object required")
        return
    coverage_id = spec.get("coverage_id")
    mapping = spec.get("cross_field_equality")
    if not isinstance(coverage_id, str) or not coverage_id:
        errors.append("registry:regex_integration.coverage_id:non-empty text required")
        return
    if not isinstance(mapping, dict) or not mapping:
        errors.append("registry:regex_integration.cross_field_equality:non-empty object required")
        return

    entry = next(
        (
            item
            for item in context.integrations.get("integrations", [])
            if isinstance(item, dict) and item.get("coverage_id") == coverage_id
        ),
        None,
    )
    if entry is None:
        errors.append(
            f"regex-integration:no {coverage_id!r} entry in {INTEGRATIONS_REGISTRY}"
        )
        return
    if entry.get("status") != "source-integrated":
        errors.append(
            f"regex-integration:{coverage_id} status must be source-integrated"
        )

    for integration_key, fieldset_path in mapping.items():
        integration_value = entry.get(integration_key)
        fieldset_value = _resolve_path(context.fieldset, str(fieldset_path))
        if integration_value is None:
            errors.append(
                f"regex-integration:missing {coverage_id}.{integration_key} in the integration entry"
            )
            continue
        if fieldset_value is None:
            errors.append(
                f"regex-integration:missing fieldset path {fieldset_path!r} in {FIELDSET_REGISTRY}"
            )
            continue
        if integration_value != fieldset_value:
            errors.append(
                f"regex-integration:drift on {integration_key}: integrations has "
                f"{integration_value!r} but fieldset {fieldset_path} is {fieldset_value!r}"
            )


def _check_notification_producer(context: Context, errors: list[str]) -> None:
    satellites = context.registry.get("satellite_contracts")
    spec = satellites.get("notification_producer") if isinstance(satellites, dict) else None
    if not isinstance(spec, dict):
        errors.append("registry:satellite_contracts.notification_producer:object required")
        return
    producer_id = spec.get("producer_id")
    if not isinstance(producer_id, str) or not producer_id:
        errors.append("registry:notification_producer.producer_id:non-empty text required")
        return

    producers = context.producer_policy.get("producers")
    if not isinstance(producers, list):
        errors.append(f"notification-producer:{PRODUCER_POLICY} producers array required")
        return
    producer = next(
        (
            item
            for item in producers
            if isinstance(item, dict) and item.get("id") == producer_id
        ),
        None,
    )
    if producer is None:
        errors.append(
            f"notification-producer:no {producer_id!r} producer in {PRODUCER_POLICY}"
        )
        return
    for key, registry_key in (
        ("file", "producer_file"),
        ("function", "producer_function"),
        ("router_call", "producer_router_call"),
    ):
        expected = spec.get(registry_key)
        if expected is not None and producer.get(key) != expected:
            errors.append(
                f"notification-producer:{producer_id} {key} is {producer.get(key)!r}, "
                f"expected {expected!r}"
            )


def _top_level_dialog(root: ET.Element, dialog_id: str, dialog_classes) -> ET.Element | None:
    for child in root:
        if _tag(child.tag) != "object":
            continue
        if child.get("id") == dialog_id and child.get("class") in dialog_classes:
            return child
    return None


def _check_router_classification(context: Context, errors: list[str]) -> None:
    router = context.router
    exclusion_policy = router.EXCLUSION_POLICY
    dialog_id = context.registry.get("dialog_id")
    if not isinstance(dialog_id, str) or not dialog_id:
        errors.append("registry:dialog_id:non-empty text required")
        return

    ui_text = context.contents.get(UI_FILE)
    if ui_text is None:
        errors.append(f"router:missing {UI_FILE}")
        return
    try:
        ui_root = ET.fromstring(ui_text)
    except ET.ParseError as error:
        errors.append(f"router:cannot parse {UI_FILE}: {error}")
        return

    dialog_object = _top_level_dialog(ui_root, dialog_id, router.DIALOG_CLASSES)
    if dialog_object is None:
        errors.append(f"router:top-level dialog {dialog_id!r} not found in {UI_FILE}")
        return
    widget_class = dialog_object.get("class", "")
    signals = router._scan_dialog_signals(dialog_object)
    policy, reason = router.classify_route(UI_FILE, dialog_id, widget_class, signals)

    if policy != exclusion_policy:
        errors.append(
            f"router:classify_route returned policy {policy!r}, must be {exclusion_policy!r} "
            "(Find & Replace must never route to the notification form / stay modal)"
        )

    row = next(
        (
            entry
            for entry in context.csv_entries
            if entry.key.ui_path == UI_FILE and entry.key.object_id == dialog_id
        ),
        None,
    )
    if row is None:
        errors.append(f"router:no CSV policy row for {UI_FILE}#{dialog_id}")
        return
    if row.policy != exclusion_policy:
        errors.append(
            f"router:CSV policy is {row.policy!r}, must be {exclusion_policy!r}"
        )
    if row.exclusion_reason != reason:
        errors.append(
            f"router:CSV exclusion_reason drift: CSV has {row.exclusion_reason!r}, but "
            f"classify_route computes {reason!r}"
        )


def _check_replace_all_flag(context: Context, errors: list[str]) -> None:
    spec = context.registry.get("replace_all_flag")
    if not isinstance(spec, dict):
        errors.append("registry:replace_all_flag:object required")
        return
    signature = spec.get("context_signature")
    arm = spec.get("arm_marker")
    clear = spec.get("clear_marker")
    for name, value in (("context_signature", signature), ("arm_marker", arm), ("clear_marker", clear)):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"registry:replace_all_flag.{name}:non-empty text required")
            return

    source = context.contents.get(SOURCE_FILE)
    if source is None:
        errors.append(f"replace-all-flag:missing {SOURCE_FILE}")
        return
    body = _function_body(_without_cpp_comments(source), signature)
    if body is None:
        errors.append(f"replace-all-flag:CommandHdl_Impl body not found via {signature!r}")
        return
    if body.count(arm) != 1:
        errors.append(
            f"replace-all-flag:arm marker must appear exactly once in CommandHdl_Impl: {arm!r}"
        )
    if body.count(clear) != 1:
        errors.append(
            f"replace-all-flag:clear marker must appear exactly once in CommandHdl_Impl: {clear!r}"
        )


def check(context: Context) -> list[str]:
    errors: list[str] = []
    _check_registry_schema(context.registry, errors)
    _check_modeless_base_class(context, errors)
    _check_fieldset_reuse(context, errors)
    _check_regex_integration_cross_field(context, errors)
    _check_foundation_reuse(context, errors)
    _check_notification_producer(context, errors)
    _check_router_classification(context, errors)
    _check_replace_all_flag(context, errors)
    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    context = load_context(repo_root)
    errors = check(context)
    if errors:
        raise ValidationError("\n".join(errors))


def main() -> int:
    try:
        validate_repository()
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"Find & Replace dialog closure contract failed (WIN-DLG-005):\n{error}", file=sys.stderr)
        return 1
    print(
        "Find & Replace dialog closure contract passed (WIN-DLG-005): SvxSearchDialog stays modeless "
        "(SfxModelessDialogController), the WIN-INP-006 fieldset and shared regex-builder foundation "
        "re-validate in-process, the document.find-replace integration and fieldset registries agree "
        "field-for-field, the srchdlg-replace-all-outcome producer is registered, the dialog stays "
        "native-exclusion (router + CSV agree), and the Replace-All one-shot flag is armed/cleared "
        "exactly once. Source/registry-consistency evidence only; runtime_verified is false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
