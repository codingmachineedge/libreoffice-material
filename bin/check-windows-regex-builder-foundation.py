#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Guard the shared ICU regex engine and adjacent anchored builder foundation."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


REPOSITORY = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    path: str
    marker: str


REQUIRED = (
    Rule("literal-mode", "include/sfx2/RegexSearchController.hxx", "Literal,"),
    Rule(
        "regex-mode",
        "include/sfx2/RegexSearchController.hxx",
        "RegularExpression",
    ),
    Rule(
        "case-insensitive-flag",
        "include/sfx2/RegexSearchController.hxx",
        "bool CaseInsensitive = true;",
    ),
    Rule(
        "global-flag",
        "include/sfx2/RegexSearchController.hxx",
        "bool Global = true;",
    ),
    Rule(
        "multiline-flag",
        "include/sfx2/RegexSearchController.hxx",
        "bool Multiline = false;",
    ),
    Rule(
        "dotall-flag",
        "include/sfx2/RegexSearchController.hxx",
        "bool DotMatchesNewline = false;",
    ),
    Rule(
        "icu-validation",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "icu::RegexPattern::compile",
    ),
    Rule(
        "libreoffice-search-engine",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "utl::TextSearch aSearch(CreateSearchOptions(rState));",
    ),
    Rule(
        "unicode-search-options",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "i18nutil::SearchOptions2 RegexSearchService::CreateSearchOptions",
    ),
    Rule(
        "preview-only-bounded-engine",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "RegexSearchEvaluation RegexSearchService::EvaluatePreview",
    ),
    Rule(
        "preview-pattern-bound",
        "include/sfx2/RegexSearchController.hxx",
        "PreviewMaxPatternCodeUnits = 1024",
    ),
    Rule(
        "entry-validation-pattern-bound",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_aState.Pattern.getLength() > RegexSearchService::PreviewMaxPatternCodeUnits",
    ),
    Rule(
        "preview-text-bound",
        "include/sfx2/RegexSearchController.hxx",
        "PreviewMaxTextCodeUnits = 16384",
    ),
    Rule(
        "preview-match-bound",
        "include/sfx2/RegexSearchController.hxx",
        "PreviewMaxMatches = 256",
    ),
    Rule(
        "preview-processing-bound",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "setTimeLimit(PreviewProcessingStepLimit",
    ),
    Rule(
        "preview-stack-bound",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "setStackLimit(PreviewStackLimitBytes",
    ),
    Rule(
        "preview-wall-clock-bound",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "setMatchCallback(lclRegexPreviewMatchCallback",
    ),
    Rule(
        "preview-timeout-status-probe",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "if (bFindReturnedFalse && !U_FAILURE(nStatus) && xMatcher)",
    ),
    Rule(
        "preview-debounce",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "SetTimeout(RegexPreviewDebounceMilliseconds)",
    ),
    Rule(
        "preview-close-cancellation",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_aPreviewTimer.Stop();",
    ),
    Rule(
        "preview-legacy-word-bounds",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "lclExpandLegacyWordBounds",
    ),
    Rule(
        "validation-legacy-word-bounds",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "const OUString aExpandedPattern = lclExpandLegacyWordBounds(aEffectivePattern);",
    ),
    Rule(
        "zero-width-progress",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "lclAdvancePastEmptyMatch",
    ),
    Rule(
        "popover-weld",
        "sfx2/source/dialog/RegexSearchController.cxx",
        'weld_popover(u"RegexBuilderPopover"_ustr)',
    ),
    Rule(
        "adjacent-anchor",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "popup_at_rect(&rAnchor, tools::Rectangle(Point(0, 0), aAnchorSize))",
    ),
    Rule(
        "responsive-popover-size",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "UpdateResponsiveSize",
    ),
    Rule(
        "backend-independent-close",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "Keep close bookkeeping and preview cancellation backend-independent.",
    ),
    Rule(
        "scrollable-build-page",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<object class="GtkScrolledWindow" id="build_page">',
    ),
    Rule(
        "scrollable-test-page",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<object class="GtkScrolledWindow" id="test_page">',
    ),
    Rule(
        "backend-window-constraint-request",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<property name="constrain-to">window</property>',
    ),
    Rule(
        "qt-work-area-clamp",
        "vcl/qt5/QtInstancePopover.cxx",
        "pScreen->availableGeometry()",
    ),
    Rule(
        "apply-semantics",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "BuilderApplyHdl",
    ),
    Rule(
        "cancel-semantics",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "CancelClickedHdl",
    ),
    Rule(
        "click-away-semantics",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "BuilderClosedHdl",
    ),
    Rule(
        "owner-entry-handler-forwarding",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_aOwnerEntryChangedHdl.Call(rEntry);",
    ),
    Rule(
        "editable-combobox-overload",
        "include/sfx2/RegexSearchController.hxx",
        "weld::Widget* pParent, weld::ComboBox& rComboBox",
    ),
    Rule(
        "editable-combobox-precondition",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "assert(m_pComboBox->has_entry());",
    ),
    Rule(
        "editable-combobox-read",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pComboBox->get_active_text()",
    ),
    Rule(
        "editable-combobox-write",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pComboBox->set_entry_text(rText);",
    ),
    Rule(
        "editable-combobox-validation",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pComboBox->set_entry_message_type(eType);",
    ),
    Rule(
        "owner-button-handler-forwarding",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_aOwnerBuilderClickedHdl.Call(rButton);",
    ),
    Rule(
        "owner-entry-handler-restoration",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pEntry->connect_changed(m_aOwnerEntryChangedHdl);",
    ),
    Rule(
        "owner-combobox-handler-forwarding",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_aOwnerComboChangedHdl.Call(rComboBox);",
    ),
    Rule(
        "owner-combobox-handler-restoration",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pComboBox->connect_changed(m_aOwnerComboChangedHdl);",
    ),
    Rule(
        "owner-button-handler-restoration",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pBuilderButton->connect_clicked(m_aOwnerBuilderClickedHdl);",
    ),
    Rule(
        "programmatic-change-guard",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "if (m_bProgrammaticTextUpdate)",
    ),
    Rule(
        "single-owner-consumer-route",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "void RegexSearchController::NotifyStateChanged()",
    ),
    Rule(
        "engine-build-wiring",
        "sfx2/Library_sfx.mk",
        "sfx2/source/dialog/RegexSearchController",
    ),
    Rule(
        "ui-build-wiring",
        "sfx2/UIConfig_sfx.mk",
        "sfx2/uiconfig/ui/regexbuilder",
    ),
    Rule(
        "native-test-wiring",
        "sfx2/Module_sfx2.mk",
        "CppunitTest_sfx2_regexsearch",
    ),
    Rule(
        "cppunit-recipe",
        "sfx2/CppunitTest_sfx2_regexsearch.mk",
        "gb_CppunitTest_CppunitTest,sfx2_regexsearch",
    ),
    Rule(
        "cppunit-test-object",
        "sfx2/CppunitTest_sfx2_regexsearch.mk",
        "sfx2/qa/cppunit/regexsearch",
    ),
    Rule(
        "cppunit-library-wiring",
        "sfx2/CppunitTest_sfx2_regexsearch.mk",
        "gb_CppunitTest_use_libraries,sfx2_regexsearch",
    ),
    Rule(
        "cppunit-service-registry",
        "sfx2/CppunitTest_sfx2_regexsearch.mk",
        "gb_CppunitTest_use_rdb,sfx2_regexsearch,services",
    ),
    Rule(
        "cppunit-configuration",
        "sfx2/CppunitTest_sfx2_regexsearch.mk",
        "gb_CppunitTest_use_configuration,sfx2_regexsearch",
    ),
    Rule(
        "invalid-pattern-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testInvalidExpressionReportsIcuError",
    ),
    Rule(
        "global-behavior-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testGlobalFlagControlsFirstVersusAllMatches",
    ),
    Rule(
        "zero-width-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testZeroWidthMatchAndPreviewLimitTerminate",
    ),
    Rule(
        "preview-bounds-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testLivePreviewHasExactTextAndMatchBounds",
    ),
    Rule(
        "preview-pattern-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testLivePreviewNeverTruncatesAnOversizedPattern",
    ),
    Rule(
        "preview-semantics-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testLivePreviewEmulatesLibreOfficeWordBounds",
    ),
    Rule(
        "consumer-search-separation-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testConsumerEvaluateDoesNotUseLivePreviewMatchCap",
    ),
    Rule(
        "pathological-preview-budget-test",
        "sfx2/qa/cppunit/regexsearch.cxx",
        "testPathologicalLivePreviewStopsAtBudget",
    ),
)

FORBIDDEN = (
    Rule("no-std-regex", "sfx2/source/dialog/RegexSearchController.cxx", "std::regex"),
    Rule(
        "no-modal-controller",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "GenericDialogController",
    ),
    Rule("no-dialog-root", "sfx2/uiconfig/ui/regexbuilder.ui", "GtkDialog"),
    Rule("no-dialog-actions", "sfx2/uiconfig/ui/regexbuilder.ui", "<action-widgets>"),
    Rule(
        "no-unbounded-live-preview",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "RegexSearchService::Evaluate(m_aState, 1000)",
    ),
    Rule(
        "no-fixed-popover-width",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<property name="width-request">820</property>',
    ),
    Rule(
        "no-fixed-popover-height",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<property name="height-request">640</property>',
    ),
    Rule(
        "no-unconstrained-popover",
        "sfx2/uiconfig/ui/regexbuilder.ui",
        '<property name="constrain-to">none</property>',
    ),
    Rule(
        "no-owner-entry-handler-loss",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pEntry->connect_changed(Link<weld::TextWidget&, void>());",
    ),
    Rule(
        "no-owner-button-handler-loss",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "m_pBuilderButton->connect_clicked(Link<weld::Button&, void>());",
    ),
    Rule(
        "no-combobox-entry-coercion",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "static_cast<weld::Entry",
    ),
    Rule(
        "no-combobox-entry-reinterpretation",
        "sfx2/source/dialog/RegexSearchController.cxx",
        "reinterpret_cast<weld::Entry",
    ),
)

RESOURCE_PATH = "include/sfx2/strings.hrc"
SOURCE_PATH = "sfx2/source/dialog/RegexSearchController.cxx"
REQUIRED_REGEX_RESOURCES = (
    "STR_REGEX_BUILDER_ACCESSIBLE_NAME",
    "STR_REGEX_BUILDER_ACCESSIBLE_DESCRIPTION",
    "STR_REGEX_BUILDER_TOOLTIP",
    "STR_REGEX_BUILDER_ENTER_PATTERN",
    "STR_REGEX_BUILDER_VALID",
    "STR_REGEX_BUILDER_INVALID",
    "STR_REGEX_BUILDER_INVALID_AT",
    "STR_REGEX_BUILDER_MATCH_NONE",
    "STR_REGEX_BUILDER_MATCH_ONE",
    "STR_REGEX_BUILDER_MATCH_FIRST",
    "STR_REGEX_BUILDER_MATCH_COUNT",
    "STR_REGEX_BUILDER_MATCH_TRUNCATED",
    "STR_REGEX_BUILDER_MATCHES_UNAVAILABLE",
    "STR_REGEX_BUILDER_PREVIEW_PENDING",
    "STR_REGEX_BUILDER_PREVIEW_BUDGET",
    "STR_REGEX_BUILDER_INPUT_TRUNCATED",
    "STR_REGEX_BUILDER_PREVIEW_SKIPPED",
)

UI_PATH = "sfx2/uiconfig/ui/regexbuilder.ui"
UI_IDS = {
    "RegexBuilderPopover",
    "pattern",
    "regexmode",
    "caseinsensitive",
    "global",
    "multiline",
    "dotall",
    "testtext",
    "validity",
    "matchsummary",
    "apply",
    "cancel",
    "build_page",
    "test_page",
    "reference_page",
    "examples_page",
}


class ValidationError(RuntimeError):
    pass


def function_body(source: str, signature: str) -> str | None:
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


def paths() -> set[str]:
    return {
        *(rule.path for rule in REQUIRED),
        *(rule.path for rule in FORBIDDEN),
        UI_PATH,
        RESOURCE_PATH,
        SOURCE_PATH,
    }


def load_contents(repo_root: Path = REPOSITORY) -> dict[str, str]:
    contents: dict[str, str] = {}
    for relative in paths():
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def violations(contents: Mapping[str, str]) -> list[str]:
    failures: list[str] = []
    for relative in sorted(paths()):
        if relative not in contents:
            failures.append(f"missing-file:{relative}")
    for rule in REQUIRED:
        if rule.marker not in contents.get(rule.path, ""):
            failures.append(f"{rule.rule_id}:{rule.path}:required marker missing")
    for rule in FORBIDDEN:
        if rule.marker in contents.get(rule.path, ""):
            failures.append(f"{rule.rule_id}:{rule.path}:forbidden marker present")

    resource_text = contents.get(RESOURCE_PATH, "")
    source_text = contents.get(SOURCE_PATH, "")
    for resource in REQUIRED_REGEX_RESOURCES:
        if re.search(rf"^#define\s+{re.escape(resource)}\b", resource_text, re.MULTILINE) is None:
            failures.append(
                f"regex-resource-definition:{RESOURCE_PATH}:{resource} definition missing"
            )
        if re.search(rf"\b{re.escape(resource)}\b", source_text) is None:
            failures.append(f"regex-resource-use:{SOURCE_PATH}:{resource} use missing")

    notify_body = function_body(
        source_text, "void RegexSearchController::NotifyStateChanged()"
    )
    if notify_body is None or notify_body.count("NotifyOwnerChanged();") != 1 or notify_body.count(
        "m_aChangedHdl.Call(*this);"
    ) != 1:
        failures.append(
            f"single-notify-route:{SOURCE_PATH}:must call one owner and one consumer callback"
        )

    for route_id, signature in (
        ("set-state", "void RegexSearchController::SetState"),
        ("builder-apply", "IMPL_LINK(RegexSearchController, BuilderApplyHdl"),
    ):
        body = function_body(source_text, signature)
        if body is None or body.count("SetSearchText(m_aState.Pattern);") != 1 or body.count(
            "NotifyStateChanged();"
        ) != 1:
            failures.append(
                f"single-notify-{route_id}:{SOURCE_PATH}:programmatic route must notify exactly once"
            )

    for route_id, signature, owner_call in (
        (
            "entry",
            "IMPL_LINK(RegexSearchController, EntryChangedHdl",
            "m_aOwnerEntryChangedHdl.Call(rEntry);",
        ),
        (
            "combobox",
            "IMPL_LINK(RegexSearchController, ComboChangedHdl",
            "m_aOwnerComboChangedHdl.Call(rComboBox);",
        ),
    ):
        body = function_body(source_text, signature)
        if (
            body is None
            or body.count("if (m_bProgrammaticTextUpdate)") != 1
            or body.count(owner_call) != 1
            or body.count("m_aChangedHdl.Call(*this);") != 1
        ):
            failures.append(
                f"single-notify-{route_id}:{SOURCE_PATH}:user route must notify exactly once"
            )

    ui_text = contents.get(UI_PATH)
    if ui_text is not None:
        try:
            root = ET.fromstring(ui_text)
        except ET.ParseError as error:
            failures.append(f"ui-xml:{UI_PATH}:{error}")
        else:
            top_objects = [child for child in root if child.tag.rsplit("}", 1)[-1] == "object"]
            if len(top_objects) != 1:
                failures.append(f"popover-root:{UI_PATH}:expected one top-level object")
            elif (
                top_objects[0].get("class") != "GtkPopover"
                or top_objects[0].get("id") != "RegexBuilderPopover"
            ):
                failures.append(f"popover-root:{UI_PATH}:advanced builder must be one GtkPopover")
            ids = {element.get("id") for element in root.iter() if element.get("id")}
            missing_ids = sorted(UI_IDS - ids)
            if missing_ids:
                failures.append(f"ui-ids:{UI_PATH}:missing {', '.join(missing_ids)}")

            popover = top_objects[0] if top_objects else None
            if popover is not None:
                constrain = next(
                    (
                        child.text
                        for child in popover
                        if child.tag.rsplit("}", 1)[-1] == "property"
                        and child.get("name") == "constrain-to"
                    ),
                    None,
                )
                if constrain != "window":
                    failures.append(
                        f"popover-constrain:{UI_PATH}:popover must constrain to its window"
                    )

            builder_content = next(
                (
                    element
                    for element in root.iter()
                    if element.get("id") == "builder_content"
                ),
                None,
            )
            if builder_content is not None:
                fixed_properties = {
                    child.get("name")
                    for child in builder_content
                    if child.tag.rsplit("}", 1)[-1] == "property"
                    and child.get("name") in {"width-request", "height-request"}
                }
                if fixed_properties:
                    failures.append(
                        f"responsive-size:{UI_PATH}:builder_content has fixed "
                        + ", ".join(sorted(fixed_properties))
                    )
    return failures


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    failures = violations(load_contents(repo_root))
    if failures:
        raise ValidationError("\n".join(failures))


def main() -> int:
    try:
        validate_repository()
    except ValidationError as error:
        print(f"Windows regex-builder foundation failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Windows regex-builder foundation passed: ICU/LibreOffice engine, i/g/m/s flags, "
        "bounded/debounced preview, responsive anchored popover, Entry/editable-ComboBox "
        "owner-handler routing, complete resources, embedded advanced UI, and native test wiring"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
