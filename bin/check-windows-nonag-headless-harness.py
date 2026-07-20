#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail closed when the Windows fresh/legacy no-nag proof is weakened.

This is a source validator for the evidence harness. It does not launch
LibreOffice and does not turn a source-only pass into runtime evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
ENTRYPOINT = "bin/Run-Windows-NoNag-Headless-Smoke.ps1"
ENGINE = "bin/Run-Windows-Headless-Smoke.ps1"
EVIDENCE_VALIDATOR = "bin/Validate-Windows-Headless-Evidence.ps1"
WORKFLOW = ".github/workflows/windows-ui-contract.yml"
SEGMENT_START = "# BEGIN NO-NAG APPLICATION ARGUMENTS"
SEGMENT_END = "# END NO-NAG APPLICATION ARGUMENTS"
LEGACY_SEED_START = "# BEGIN LEGACY NO-NAG REGISTRY SEED"
LEGACY_SEED_END = "# END LEGACY NO-NAG REGISTRY SEED"
OOR_NAMESPACE = "http://openoffice.org/2001/registry"
OOR = f"{{{OOR_NAMESPACE}}}"
SUPPRESSIVE_ARGUMENTS = (
    "--nologo",
    "--norestore",
    "--headless",
    "--invisible",
    "--nodefault",
)

LEGACY_REGISTRY_EXPECTATIONS = {
    ("/org.openoffice.Office.Common/Misc", "FirstRun"): ("boolean", "true"),
    ("/org.openoffice.Office.Common/Misc", "CrashReport"): ("boolean", "true"),
    ("/org.openoffice.Office.Common/Misc", "ShowTipOfTheDay"): (
        "boolean",
        "true",
    ),
    ("/org.openoffice.Office.Common/Misc", "LastTipOfTheDayShown"): (
        "int",
        "-1",
    ),
    ("/org.openoffice.Office.Common/Misc", "PerformFileExtCheck"): (
        "boolean",
        "true",
    ),
    ("/org.openoffice.Office.Common/Misc", "ShowDonation"): ("boolean", "true"),
    ("/org.openoffice.Setup/Product", "ooSetupLastVersion"): ("string", "1.0"),
    ("/org.openoffice.Setup/Product", "WhatsNew"): ("boolean", "true"),
    ("/org.openoffice.Setup/Product", "WhatsNewDialog"): ("boolean", "true"),
    ("/org.openoffice.Setup/Product", "LastTimeGetInvolvedShown"): ("long", "1"),
    ("/org.openoffice.Setup/Product", "LastTimeDonateShown"): ("long", "1"),
    ("/org.openoffice.Office.UI.Infobar/Enabled", "Donate"): ("boolean", "true"),
    ("/org.openoffice.Office.UI.Infobar/Enabled", "GetInvolved"): (
        "boolean",
        "true",
    ),
    ("/org.openoffice.Office.UI.Infobar/Enabled", "WhatsNew"): (
        "boolean",
        "true",
    ),
    ("/org.openoffice.Office.UI.Infobar/Enabled", "AutoCorrLeadTrail"): (
        "boolean",
        "true",
    ),
}


@dataclass(frozen=True)
class MarkerRule:
    rule_id: str
    path: str
    marker: str
    rationale: str


REQUIRED_MARKERS = (
    MarkerRule(
        "dedicated-profile-modes",
        ENTRYPOINT,
        "[ValidateSet('Fresh', 'Legacy')]",
        "the dedicated entrypoint must expose only fresh and legacy profiles",
    ),
    MarkerRule(
        "dedicated-policy-forwarding",
        ENTRYPOINT,
        "StartupProfile = $ProfileMode",
        "the selected profile must reach the shared ownership/capture engine",
    ),
    MarkerRule(
        "dedicated-entrypoint-binding",
        ENTRYPOINT,
        "EvidenceEntrypointPath = $PSCommandPath",
        "evidence must hash the command the operator actually invoked",
    ),
    MarkerRule(
        "minimum-observation-parameter",
        ENGINE,
        "[ValidateRange(15, 120)]",
        "the no-nag observation cannot be shortened below fifteen seconds",
    ),
    MarkerRule(
        "no-nag-argument-start",
        ENGINE,
        SEGMENT_START,
        "the no-nag launch argument block must be independently auditable",
    ),
    MarkerRule(
        "no-nag-argument-end",
        ENGINE,
        SEGMENT_END,
        "the no-nag launch argument block must be independently auditable",
    ),
    MarkerRule(
        "blank-writer-launch",
        ENGINE,
        "\"-env:UserInstallation=$profileUri\", '--writer', '--quickstart=no'",
        "blank Writer must exercise document-startup prompt paths",
    ),
    MarkerRule(
        "runtime-suppressive-argument-guard",
        ENGINE,
        "Assert-NoNagLaunchArguments -Arguments $applicationArguments",
        "runtime launch construction must reject prompt-suppressive arguments",
    ),
    MarkerRule(
        "batch-percent-escape",
        ENGINE,
        "Argument.Replace('%', '%%')",
        "encoded profile URIs must survive Windows batch parameter expansion",
    ),
    MarkerRule(
        "batch-launcher-percent-rejection",
        ENGINE,
        "OutputRoot cannot contain a percent sign",
        "cmd.exe must not expand the private wrapper path before launch",
    ),
    MarkerRule(
        "batch-launcher-delayed-expansion-disabled",
        ENGINE,
        "cmd.exe /d /v:off /c call",
        "the outer cmd parser must preserve exclamation marks in the wrapper path",
    ),
    MarkerRule(
        "evidence-suppressive-argument-prefix-guard",
        EVIDENCE_VALIDATOR,
        '"$forbiddenArgument="',
        "accepted evidence must reject value-bearing prompt-suppressive switches",
    ),
    MarkerRule(
        "fresh-profile-empty",
        ENGINE,
        "Fresh no-nag profile was not empty immediately before launch.",
        "fresh proof must not pre-seed first-run suppression",
    ),
    MarkerRule(
        "legacy-first-run",
        ENGINE,
        '<prop oor:name="FirstRun" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must request the historical first-run path",
    ),
    MarkerRule(
        "legacy-crash-report",
        ENGINE,
        '<prop oor:name="CrashReport" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the historical crash-report trigger",
    ),
    MarkerRule(
        "legacy-tip",
        ENGINE,
        '<prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the historical tip trigger",
    ),
    MarkerRule(
        "legacy-association",
        ENGINE,
        '<prop oor:name="PerformFileExtCheck" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the historical association trigger",
    ),
    MarkerRule(
        "legacy-donation",
        ENGINE,
        '<prop oor:name="ShowDonation" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the historical donation trigger",
    ),
    MarkerRule(
        "legacy-old-version",
        ENGINE,
        '<prop oor:name="ooSetupLastVersion" oor:op="fuse"><value>1.0</value></prop>',
        "legacy proof must exercise the historical upgraded-profile path",
    ),
    MarkerRule(
        "legacy-whats-new",
        ENGINE,
        '<prop oor:name="WhatsNewDialog" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the historical What's New dialog trigger",
    ),
    MarkerRule(
        "legacy-promotions",
        ENGINE,
        '<prop oor:name="LastTimeGetInvolvedShown" oor:op="fuse"><value>1</value></prop>',
        "legacy proof must seed recurring promotion timestamps",
    ),
    MarkerRule(
        "legacy-autocorrect-explanation",
        ENGINE,
        '<prop oor:name="AutoCorrLeadTrail" oor:op="fuse"><value>true</value></prop>',
        "legacy proof must seed the removed AutoCorrect explanation",
    ),
    MarkerRule(
        "legacy-safe-crash-seed",
        ENGINE,
        "$applicationArguments += '-env:CrashDumpEnable=false'",
        "the legacy crash trigger must not create a dump or contact a service",
    ),
    MarkerRule(
        "legacy-safe-crash-seed-public-evidence",
        ENGINE,
        "$publicApplicationArguments += '-env:CrashDumpEnable=false'",
        "the sanitized evidence arguments must record the crash-dump bootstrap value",
    ),
    MarkerRule(
        "legacy-no-truthy-crash-environment",
        ENGINE,
        "'set \"CRASH_DUMP_ENABLE=\"'",
        "the legacy harness must not mistake a nonempty environment value for false",
    ),
    MarkerRule(
        "legacy-crash-bootstrap-evidence",
        EVIDENCE_VALIDATOR,
        "'No-nag evidence must clear any inherited truthy crash-dump override.'",
        "accepted evidence must prove the truthy process override remained absent",
    ),
    MarkerRule(
        "exact-build-binding",
        ENGINE,
        "if ($embeddedBuildId -ne $sourceLower)",
        "runtime payload and exact source commit must agree",
    ),
    MarkerRule(
        "dedicated-listener-ancestry",
        ENGINE,
        "$dedicatedListenerIdentity = Get-ValidatedLoopbackListenerIdentity",
        "the MCP listener PID must be bound to the dedicated driver ancestry",
    ),
    MarkerRule(
        "dedicated-listener-failure-cleanup",
        ENGINE,
        "[bool](Stop-RecordedProcessIdentity",
        "an orphaned validated listener must be stopped by exact PID/creation identity",
    ),
    MarkerRule(
        "window-inventory",
        ENGINE,
        "Record-WindowEnumeration -Enumeration $lastWindows",
        "every startup enumeration must be retained",
    ),
    MarkerRule(
        "bounded-window-polling",
        ENGINE,
        "while ($observationStopwatch.Elapsed.TotalSeconds -lt $ObservationSeconds)",
        "stable no-nag observation must poll at a bounded cadence",
    ),
    MarkerRule(
        "monotonic-observation-duration",
        ENGINE,
        "$script:ObservationElapsedMilliseconds = [long]$observationStopwatch.ElapsedMilliseconds",
        "the retained proof must bind the monotonic observation duration",
    ),
    MarkerRule(
        "single-owned-writer",
        ENGINE,
        "expected exactly one total and payload-owned top-level window",
        "each observation must reject prompts owned by helper processes too",
    ),
    MarkerRule(
        "exact-writer-thread-dpi",
        ENGINE,
        "-ExpectedWidth $results.window.width",
        "stable observations must retain full window identity and geometry",
    ),
    MarkerRule(
        "a11y-deny-check",
        ENGINE,
        "Assert-NoNagA11yReport -Report $a11y",
        "former nags must be absent from the complete accessibility tree",
    ),
    MarkerRule(
        "former-nag-tip",
        ENGINE,
        "'Tip of the Day'",
        "Tip text must remain in the former-nag denylist",
    ),
    MarkerRule(
        "former-nag-welcome",
        ENGINE,
        "'Welcome to'",
        "Welcome text must remain in the former-nag denylist",
    ),
    MarkerRule(
        "former-nag-whats-new-infobar",
        ENGINE,
        "'You are running version'",
        "the historical What's New infobar body must remain denied",
    ),
    MarkerRule(
        "former-nag-first-time-body",
        ENGINE,
        "'Please take a moment to personalize your settings'",
        "the historical first-run body must remain denied",
    ),
    MarkerRule(
        "former-nag-association",
        ENGINE,
        "'Default file formats not registered'",
        "association solicitation text must remain denied",
    ),
    MarkerRule(
        "former-nag-autocorrect",
        ENGINE,
        "'Autocorrection has removed a leading or trailing character'",
        "the unsolicited AutoCorrect explanation must remain denied",
    ),
    MarkerRule(
        "retained-recovery",
        ENGINE,
        "'Document Recovery'",
        "recovery prompts must be explicitly outside the former-nag denylist",
    ),
    MarkerRule(
        "retained-safe-mode",
        ENGINE,
        "'Troubleshoot Mode'",
        "Safe Mode must be explicitly outside the former-nag denylist",
    ),
    MarkerRule(
        "retained-macro-warning",
        ENGINE,
        "'Macros disabled'",
        "macro security must be explicitly outside the former-nag denylist",
    ),
    MarkerRule(
        "retained-extension-compatibility",
        ENGINE,
        "'Incompatible Extensions'",
        "extension compatibility warnings must remain outside the denylist",
    ),
    MarkerRule(
        "retained-hidden-information",
        ENGINE,
        "'Hidden Information'",
        "hidden-information security warnings must remain outside the denylist",
    ),
    MarkerRule(
        "retained-master-password",
        ENGINE,
        "'Master Password'",
        "credential safeguards must remain outside the denylist",
    ),
    MarkerRule(
        "retained-readonly-warning",
        ENGINE,
        "'read-only mode'",
        "read-only safety feedback must be explicitly outside the denylist",
    ),
    MarkerRule(
        "association-coverage-false",
        ENGINE,
        "automatic_file_association_runtime_covered = $false",
        "an extracted payload cannot claim the HKLM registry-gated branch",
    ),
    MarkerRule(
        "association-sandbox-boundary",
        ENGINE,
        "Use an MSI-installed disposable Windows Sandbox or VM for that proof.",
        "the missing association proof must name the safe acceptance environment",
    ),
    MarkerRule(
        "evidence-no-nag-entrypoint",
        EVIDENCE_VALIDATOR,
        "'bin/Run-Windows-NoNag-Headless-Smoke.ps1'",
        "candidate evidence must bind the dedicated entrypoint",
    ),
    MarkerRule(
        "evidence-fresh-empty",
        EVIDENCE_VALIDATOR,
        "Fresh no-nag profile must be empty immediately before launch.",
        "the evidence validator must enforce fresh-profile emptiness",
    ),
    MarkerRule(
        "evidence-poll-artifact",
        EVIDENCE_VALIDATOR,
        "no-nag window poll log SHA-256",
        "the evidence validator must bind the retained poll artifact",
    ),
    MarkerRule(
        "evidence-all-poll-window-inventory",
        EVIDENCE_VALIDATOR,
        "foreach ($poll in $windowPolls)",
        "accepted evidence must inspect startup and observation ownership inventories",
    ),
    MarkerRule(
        "evidence-poll-ownership-equivalence",
        EVIDENCE_VALIDATOR,
        "forged or missing payload-ownership marker",
        "accepted evidence must reject false-negative ownership flags",
    ),
    MarkerRule(
        "evidence-single-total-window",
        EVIDENCE_VALIDATOR,
        "exactly one total/owned window",
        "accepted observation evidence must reject helper-process prompt windows",
    ),
    MarkerRule(
        "evidence-a11y-deny-rescan",
        EVIDENCE_VALIDATOR,
        "a11y tree contains former nag text",
        "accepted evidence must independently rescan the retained accessibility tree",
    ),
    MarkerRule(
        "evidence-observation-duration",
        EVIDENCE_VALIDATOR,
        "monotonic observation duration is shorter",
        "accepted evidence must revalidate the observation duration",
    ),
    MarkerRule(
        "evidence-safety-denylist-disjoint",
        EVIDENCE_VALIDATOR,
        "Retained safety prompts must remain disjoint",
        "safety prompts cannot be silently added to the former-nag denylist",
    ),
    MarkerRule(
        "evidence-listener-cleanup",
        EVIDENCE_VALIDATOR,
        "cleanup.dedicated_driver_endpoint_closed",
        "passed evidence must prove the dedicated loopback endpoint closed",
    ),
    MarkerRule(
        "evidence-association-boundary",
        EVIDENCE_VALIDATOR,
        "Extracted-payload no-nag evidence cannot claim registry-gated association runtime coverage.",
        "the validator must reject an association overclaim",
    ),
    MarkerRule(
        "workflow-validator",
        WORKFLOW,
        "python3 bin/check-windows-nonag-headless-harness.py",
        "CI must run the no-nag harness source contract",
    ),
    MarkerRule(
        "workflow-mutations",
        WORKFLOW,
        "python3 bin/test_windows_nonag_headless_harness.py",
        "CI must run mutation coverage for the harness contract",
    ),
)


class ValidationError(RuntimeError):
    pass


def referenced_paths() -> set[str]:
    return {rule.path for rule in REQUIRED_MARKERS} | {ENTRYPOINT, ENGINE}


def load_snapshot(repo_root: Path) -> tuple[dict[str, str], set[str]]:
    contents: dict[str, str] = {}
    present: set[str] = set()
    for relative in sorted(referenced_paths()):
        path = repo_root / relative
        if path.exists():
            present.add(relative)
            if path.is_file():
                contents[relative] = path.read_text(encoding="utf-8")
    return contents, present


def _argument_segment(text: str) -> tuple[str | None, str | None]:
    start_count = text.count(SEGMENT_START)
    end_count = text.count(SEGMENT_END)
    if start_count != 1 or end_count != 1:
        return None, "no-nag launch argument segment must have one start and one end marker"
    start = text.index(SEGMENT_START) + len(SEGMENT_START)
    end = text.index(SEGMENT_END)
    if end <= start:
        return None, "no-nag launch argument segment markers are reversed"
    return text[start:end], None


def _legacy_seed_segment(text: str) -> tuple[str | None, str | None]:
    if text.count(LEGACY_SEED_START) != 1 or text.count(LEGACY_SEED_END) != 1:
        return None, "legacy registry seed must have one start and one end marker"
    start = text.index(LEGACY_SEED_START) + len(LEGACY_SEED_START)
    end = text.index(LEGACY_SEED_END)
    if end <= start:
        return None, "legacy registry seed markers are reversed"
    segment = text[start:end]
    xml_start = segment.find("<?xml")
    xml_end_marker = "</oor:items>"
    xml_end = segment.find(xml_end_marker)
    if xml_start < 0 or xml_end < xml_start:
        return None, "legacy registry seed does not contain one complete oor:items XML document"
    xml_end += len(xml_end_marker)
    if segment.find("<?xml", xml_start + 1) >= 0 or segment.find(
        xml_end_marker, xml_end
    ) >= 0:
        return None, "legacy registry seed contains multiple XML documents"
    return segment[xml_start:xml_end], None


def _legacy_registry_seed_violations(text: str) -> list[str]:
    xml_text, error = _legacy_seed_segment(text)
    if error:
        return [error]
    assert xml_text is not None
    for namespace_marker in (
        f'xmlns:oor="{OOR_NAMESPACE}"',
        'xmlns:xs="http://www.w3.org/2001/XMLSchema"',
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
    ):
        if namespace_marker not in xml_text:
            return [f"legacy registry seed is missing {namespace_marker}"]
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        return [f"legacy registry seed is invalid XML: {error}"]
    if root.tag != f"{OOR}items":
        return ["legacy registry seed root is not oor:items"]

    actual: dict[tuple[str, str], str] = {}
    violations: list[str] = []
    if root.attrib:
        violations.append("legacy registry seed root contains unexpected attributes")
    for item in root:
        if item.tag != "item":
            violations.append(f"unexpected legacy registry element {item.tag}")
            continue
        path = item.attrib.get(f"{OOR}path", "")
        if not path or set(item.attrib) != {f"{OOR}path"}:
            violations.append(
                "legacy registry item must contain only one nonblank oor:path"
            )
        for prop in item:
            if prop.tag != "prop":
                violations.append(f"unexpected element below {path}: {prop.tag}")
                continue
            name = prop.attrib.get(f"{OOR}name", "")
            operation = prop.attrib.get(f"{OOR}op", "")
            children = list(prop)
            values = [child for child in children if child.tag == "value"]
            if (
                not name
                or operation != "fuse"
                or set(prop.attrib) != {f"{OOR}name", f"{OOR}op"}
                or len(children) != 1
                or len(values) != 1
                or values[0].attrib
                or list(values[0])
            ):
                violations.append(
                    f"legacy registry property {path}/{name} must have only a name, oor:op=fuse, and one scalar value"
                )
                continue
            key = (path, name)
            if key in actual:
                violations.append(f"duplicate legacy registry property {path}/{name}")
                continue
            actual[key] = (values[0].text or "").strip()

    if set(actual) != set(LEGACY_REGISTRY_EXPECTATIONS):
        missing = sorted(set(LEGACY_REGISTRY_EXPECTATIONS) - set(actual))
        extra = sorted(set(actual) - set(LEGACY_REGISTRY_EXPECTATIONS))
        violations.append(f"legacy registry property set differs; missing={missing}, extra={extra}")
    for key, (value_type, expected_value) in LEGACY_REGISTRY_EXPECTATIONS.items():
        if key not in actual:
            continue
        value = actual[key]
        if value != expected_value:
            violations.append(
                f"legacy registry value {key[0]}/{key[1]} must be {expected_value!r}, found {value!r}"
            )
        if value_type == "boolean" and value not in {"true", "false"}:
            violations.append(f"legacy boolean {key[0]}/{key[1]} has invalid lexical value")
        elif value_type in {"int", "long"} and not re.fullmatch(r"[+-]?\d+", value):
            violations.append(f"legacy integer {key[0]}/{key[1]} has invalid lexical value")
        elif value_type == "string" and not value:
            violations.append(f"legacy string {key[0]}/{key[1]} is blank")
    return violations


def find_violations(
    contents: Mapping[str, str], present: set[str]
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for required_path in (ENTRYPOINT, ENGINE, EVIDENCE_VALIDATOR, WORKFLOW):
        if required_path not in present:
            violations.append(
                {
                    "rule": "required-file",
                    "path": required_path,
                    "detail": "required harness contract file is missing",
                }
            )
    for rule in REQUIRED_MARKERS:
        if rule.marker not in contents.get(rule.path, ""):
            violations.append(
                {
                    "rule": rule.rule_id,
                    "path": rule.path,
                    "detail": f"required harness safeguard missing: {rule.rationale}",
                }
            )

    entrypoint_text = contents.get(ENTRYPOINT, "")
    for argument in SUPPRESSIVE_ARGUMENTS:
        if argument in entrypoint_text:
            violations.append(
                {
                    "rule": f"dedicated-suppressive-{argument[2:]}",
                    "path": ENTRYPOINT,
                    "detail": f"dedicated no-nag entrypoint contains {argument}",
                }
            )

    segment, segment_error = _argument_segment(contents.get(ENGINE, ""))
    if segment_error:
        violations.append(
            {"rule": "argument-segment", "path": ENGINE, "detail": segment_error}
        )
    elif segment is not None:
        for argument in SUPPRESSIVE_ARGUMENTS:
            if argument in segment:
                violations.append(
                    {
                        "rule": f"no-nag-suppressive-{argument[2:]}",
                        "path": ENGINE,
                        "detail": f"no-nag launch block contains {argument}",
                    }
                )
    for detail in _legacy_registry_seed_violations(contents.get(ENGINE, "")):
        violations.append(
            {
                "rule": "legacy-registry-seed-schema",
                "path": ENGINE,
                "detail": detail,
            }
        )
    return violations


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    contents, present = load_snapshot(repo_root)
    violations = find_violations(contents, present)
    if violations:
        raise ValidationError(
            "\n".join(
                f"{item['rule']}: {item['path']}: {item['detail']}"
                for item in violations
            )
        )


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit the successful contract summary as JSON"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_arguments(sys.argv[1:] if argv is None else argv)
    try:
        validate_repository()
    except ValidationError as error:
        print(f"Windows no-nag headless harness contract failed:\n{error}", file=sys.stderr)
        return 1
    summary = {
        "required_markers": len(REQUIRED_MARKERS),
        "suppressive_arguments": len(SUPPRESSIVE_ARGUMENTS),
        "profile_modes": 2,
    }
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            "Windows no-nag headless harness contract passed: "
            f"{summary['profile_modes']} disposable profile modes, "
            f"{summary['required_markers']} required safeguards, "
            f"{summary['suppressive_arguments']} forbidden suppression arguments"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
