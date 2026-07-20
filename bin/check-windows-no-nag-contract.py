#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail closed when unsolicited Windows startup/promotion prompts return.

The contract deliberately distinguishes promotional/onboarding interruption
from recovery, security, compatibility, and explicit user-invoked actions.
It is a source validator, not runtime proof.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MarkerRule:
    rule_id: str
    path: str
    marker: str
    rationale: str


FORBIDDEN_FILES = {
    "cui/source/dialogs/fileextcheckdlg.cxx": "automatic file-association prompt",
    "cui/source/inc/fileextcheckdlg.hxx": "automatic file-association prompt",
    "cui/uiconfig/ui/fileextcheckdialog.ui": "automatic file-association prompt",
    "cui/source/dialogs/welcomedlg.cxx": "automatic welcome prompt",
    "cui/source/inc/welcomedlg.hxx": "automatic welcome prompt",
    "cui/uiconfig/ui/welcomedialog.ui": "automatic welcome prompt",
    "cui/source/dialogs/whatsnewtabpage.cxx": "automatic What's New prompt",
    "cui/source/inc/whatsnewtabpage.hxx": "automatic What's New prompt",
    "cui/uiconfig/ui/whatsnewtabpage.ui": "automatic What's New prompt",
}


FORBIDDEN_MARKERS = (
    MarkerRule(
        "file-association-startup",
        "desktop/source/app/app.cxx",
        "CheckFileExtRegistration(",
        "file associations remain an explicit Options action",
    ),
    MarkerRule(
        "file-association-api",
        "include/vcl/fileregistration.hxx",
        "CheckFileExtRegistration(",
        "the startup-only prompt API must not return",
    ),
    MarkerRule(
        "file-association-implementation",
        "vcl/win/app/fileregistration.cxx",
        "CheckFileExtRegistration(",
        "the startup-only prompt implementation must not return",
    ),
    MarkerRule(
        "crash-report-modal-handler",
        "desktop/source/app/app.cxx",
        "handleCrashReport(",
        "crash dumps and recovery remain, but startup solicitation does not",
    ),
    MarkerRule(
        "crash-report-modal-service",
        "desktop/source/app/app.cxx",
        "com.sun.star.comp.svx.CrashReportUI",
        "the crash-report modal must never be launched automatically",
    ),
    MarkerRule(
        "crash-report-option-code",
        "cui/source/options/optgdlg.cxx",
        "Office::Common::Misc::CrashReport",
        "an option must not claim to control a removed automatic sender",
    ),
    MarkerRule(
        "crash-report-option-member",
        "cui/source/options/optgdlg.hxx",
        "m_xCrashReport",
        "the dead crash-report opt-in control must stay removed",
    ),
    MarkerRule(
        "crash-report-option-ui",
        "cui/uiconfig/ui/optgeneralpage.ui",
        'id="crashreport"',
        "Options must not advertise an unreachable crash-report action",
    ),
    MarkerRule(
        "crash-report-option-schema",
        "officecfg/registry/schema/org/openoffice/Office/Common.xcs",
        '<prop oor:name="CrashReport"',
        "a removed startup sender must not retain a misleading preference",
    ),
    MarkerRule(
        "welcome-factory",
        "include/sfx2/sfxdlg.hxx",
        "CreateWelcomeDialog",
        "the explicit release-notes command replaces automatic welcome UI",
    ),
    MarkerRule(
        "welcome-factory-implementation",
        "cui/source/factory/dlgfact.cxx",
        "CreateWelcomeDialog",
        "dead automatic welcome UI must stay removed",
    ),
    MarkerRule(
        "fileext-factory",
        "include/vcl/abstdlg.hxx",
        "CreateFileExtCheckDialog",
        "dead automatic file-association UI must stay removed",
    ),
    MarkerRule(
        "tip-scheduler-api",
        "include/sfx2/app.hxx",
        "IsTipOfTheDayDue",
        "Tip of the Day is manual-only",
    ),
    MarkerRule(
        "tip-scheduler-view",
        "sfx2/source/view/viewfrm.cxx",
        "IsTipOfTheDayDue",
        "document creation must not schedule tips",
    ),
    MarkerRule(
        "tip-scheduler-impress",
        "sd/source/ui/app/sdmod1.cxx",
        "IsTipOfTheDayDue",
        "Impress must not schedule a deferred tip",
    ),
    MarkerRule(
        "tip-auto-dispatch",
        "sfx2/source/view/viewfrm.cxx",
        "SID_TIPOFTHEDAY",
        "only the explicit Help command may dispatch the tip dialog",
    ),
    MarkerRule(
        "promo-donation-handler",
        "include/sfx2/viewfrm.hxx",
        "DonationHandler",
        "recurring donation infobars are forbidden",
    ),
    MarkerRule(
        "promo-involvement-handler",
        "include/sfx2/viewfrm.hxx",
        "GetInvolvedHandler",
        "recurring involvement infobars are forbidden",
    ),
    MarkerRule(
        "promo-whatsnew-handler",
        "include/sfx2/viewfrm.hxx",
        "WhatsNewHandler",
        "automatic What's New infobars are forbidden",
    ),
    MarkerRule(
        "promo-donation-schedule",
        "sfx2/source/view/viewfrm.cxx",
        "LastTimeDonateShown",
        "recurring donation scheduling is forbidden",
    ),
    MarkerRule(
        "promo-involvement-schedule",
        "sfx2/source/view/viewfrm.cxx",
        "LastTimeGetInvolvedShown",
        "recurring involvement scheduling is forbidden",
    ),
    MarkerRule(
        "welcome-auto-state",
        "sfx2/source/view/viewfrm.cxx",
        "wantsWhatsNew",
        "release notes remain explicit, never automatic",
    ),
    MarkerRule(
        "show-tip-setting",
        "officecfg/registry/schema/org/openoffice/Office/Common.xcs",
        '<prop oor:name="ShowTipOfTheDay"',
        "a removed automatic feature must not retain an enabling preference",
    ),
    MarkerRule(
        "fileext-check-setting",
        "officecfg/registry/schema/org/openoffice/Office/Common.xcs",
        '<prop oor:name="PerformFileExtCheck"',
        "a removed automatic feature must not retain an enabling preference",
    ),
    MarkerRule(
        "donation-setting",
        "officecfg/registry/schema/org/openoffice/Office/Common.xcs",
        '<prop oor:name="ShowDonation"',
        "recurring donation solicitation must not be configurable back on",
    ),
    MarkerRule(
        "welcome-setting",
        "officecfg/registry/schema/org/openoffice/Setup.xcs",
        '<prop oor:name="WhatsNew"',
        "automatic What's New state must stay removed",
    ),
    MarkerRule(
        "welcome-dialog-setting",
        "officecfg/registry/schema/org/openoffice/Setup.xcs",
        '<prop oor:name="WhatsNewDialog"',
        "automatic welcome-dialog state must stay removed",
    ),
    MarkerRule(
        "donation-timestamp-setting",
        "officecfg/registry/schema/org/openoffice/Setup.xcs",
        '<prop oor:name="LastTimeDonateShown"',
        "recurring donation scheduling state must stay removed",
    ),
    MarkerRule(
        "involvement-timestamp-setting",
        "officecfg/registry/schema/org/openoffice/Setup.xcs",
        '<prop oor:name="LastTimeGetInvolvedShown"',
        "recurring involvement scheduling state must stay removed",
    ),
    MarkerRule(
        "donation-infobar-setting",
        "officecfg/registry/schema/org/openoffice/Office/UI/Infobar.xcs",
        '<prop oor:name="Donate"',
        "promotional infobars must not be re-enabled by configuration",
    ),
    MarkerRule(
        "involvement-infobar-setting",
        "officecfg/registry/schema/org/openoffice/Office/UI/Infobar.xcs",
        '<prop oor:name="GetInvolved"',
        "promotional infobars must not be re-enabled by configuration",
    ),
    MarkerRule(
        "whatsnew-infobar-setting",
        "officecfg/registry/schema/org/openoffice/Office/UI/Infobar.xcs",
        '<prop oor:name="WhatsNew"',
        "promotional infobars must not be re-enabled by configuration",
    ),
    MarkerRule(
        "tip-startup-checkbox",
        "cui/uiconfig/ui/optgeneralpage.ui",
        'id="cbShowTipOfTheDay"',
        "manual tips need no startup checkbox",
    ),
    MarkerRule(
        "fileext-startup-checkbox",
        "cui/uiconfig/ui/optgeneralpage.ui",
        'id="cbPerformFileExtCheck"',
        "manual association control needs no startup checkbox",
    ),
    MarkerRule(
        "tip-dialog-checkbox",
        "cui/uiconfig/ui/tipofthedaydialog.ui",
        'id="cbShowTip"',
        "the manual tip dialog cannot opt users back into startup prompts",
    ),
)


REQUIRED_MARKERS = (
    MarkerRule(
        "first-run-initialization",
        "desktop/source/app/app.cxx",
        "CheckFirstRun(",
        "first-run initialization is not promotional UI",
    ),
    MarkerRule(
        "safe-mode-startup",
        "desktop/source/app/app.cxx",
        "handleSafeMode();",
        "explicit Safe Mode must remain actionable",
    ),
    MarkerRule(
        "extension-compatibility",
        "desktop/source/app/app.cxx",
        "CheckExtensionDependencies();",
        "incompatible extensions remain a required compatibility warning",
    ),
    MarkerRule(
        "document-recovery-command",
        "desktop/source/app/app.cxx",
        "vnd.sun.star.autorecovery:/doAutoRecovery",
        "document recovery must remain intact",
    ),
    MarkerRule(
        "auto-recovery-service",
        "desktop/source/app/app.cxx",
        "css::frame::theAutoRecovery::get",
        "the recovery service must remain intact",
    ),
    MarkerRule(
        "manual-file-association",
        "vcl/win/app/fileregistration.cxx",
        "void LaunchRegistrationUI()",
        "the explicit Windows association action must remain",
    ),
    MarkerRule(
        "manual-file-association-options",
        "cui/source/options/optgdlg.cxx",
        "vcl::fileregistration::LaunchRegistrationUI();",
        "Options must retain the explicit association action",
    ),
    MarkerRule(
        "manual-tip-command",
        "sfx2/source/appl/appserv.cxx",
        "case SID_TIPOFTHEDAY:",
        "Help > Tip of the Day remains user-invoked",
    ),
    MarkerRule(
        "manual-whatsnew-command",
        "sfx2/source/appl/appserv.cxx",
        "case SID_WHATSNEW:",
        "Help > What's New remains user-invoked",
    ),
    MarkerRule(
        "manual-feedback-command",
        "sfx2/source/appl/appserv.cxx",
        "case SID_SEND_FEEDBACK:",
        "Help > Send Feedback remains user-invoked",
    ),
    MarkerRule(
        "promotional-infobars-disabled",
        "sfx2/source/dialog/infobar.cxx",
        'if (sId == u"donate" || sId == u"getinvolved" || sId == u"whatsnew")\n'
        "        return false;",
        "legacy profiles cannot restore promotional infobars",
    ),
    MarkerRule(
        "autocorrect-explanation-disabled",
        "sfx2/source/dialog/infobar.cxx",
        'if (sId == u"autocorr_leadtrail")\n        return false;',
        "autocorrection remains functional without an unsolicited explanation",
    ),
    MarkerRule(
        "readonly-warning",
        "sfx2/source/view/viewfrm.cxx",
        'AppendInfoBar(u"readonly"_ustr',
        "read-only state must remain visible",
    ),
    MarkerRule(
        "macro-warning",
        "sfx2/source/view/viewfrm.cxx",
        'AppendInfoBar(u"macro"_ustr',
        "macro security must remain visible",
    ),
    MarkerRule(
        "hidden-metadata-warning",
        "sfx2/source/view/viewfrm.cxx",
        'AppendInfoBar(u"securitywarn"_ustr',
        "hidden metadata security must remain visible",
    ),
    MarkerRule(
        "password-migration-warning",
        "sfx2/source/view/viewfrm.cxx",
        'AppendInfoBar(u"oldmasterpassword"_ustr',
        "credential migration must remain visible",
    ),
)


class ValidationError(RuntimeError):
    pass


def referenced_paths() -> set[str]:
    return {
        *(rule.path for rule in FORBIDDEN_MARKERS),
        *(rule.path for rule in REQUIRED_MARKERS),
        *FORBIDDEN_FILES,
    }


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


def find_violations(
    contents: Mapping[str, str], present: set[str]
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path, rationale in sorted(FORBIDDEN_FILES.items()):
        if path in present:
            violations.append(
                {
                    "rule": "deleted-prompt-surface",
                    "path": path,
                    "detail": rationale,
                }
            )
    for rule in FORBIDDEN_MARKERS:
        if rule.marker in contents.get(rule.path, ""):
            violations.append(
                {
                    "rule": rule.rule_id,
                    "path": rule.path,
                    "detail": rule.rationale,
                }
            )
    for rule in REQUIRED_MARKERS:
        if rule.marker not in contents.get(rule.path, ""):
            violations.append(
                {
                    "rule": rule.rule_id,
                    "path": rule.path,
                    "detail": f"required safeguard missing: {rule.rationale}",
                }
            )
    return violations


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    contents, present = load_snapshot(repo_root)
    violations = find_violations(contents, present)
    if violations:
        lines = [
            f"{item['rule']}: {item['path']}: {item['detail']}"
            for item in violations
        ]
        raise ValidationError("\n".join(lines))


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
        print(f"Windows no-nag contract failed:\n{error}", file=sys.stderr)
        return 1
    summary = {
        "forbidden_files": len(FORBIDDEN_FILES),
        "forbidden_markers": len(FORBIDDEN_MARKERS),
        "required_safeguards": len(REQUIRED_MARKERS),
    }
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            "Windows no-nag contract passed: "
            f"{summary['forbidden_files']} removed prompt surfaces, "
            f"{summary['forbidden_markers']} forbidden startup/promotion markers, "
            f"{summary['required_safeguards']} retained safeguards/manual actions"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
