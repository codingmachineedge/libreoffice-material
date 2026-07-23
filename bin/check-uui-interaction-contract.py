#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the uui authentication / conflict / generic-error modality lock.

``WIN-SYS-011`` (docs/WINDOWS_UI_INVENTORY.md) is the "authentication, conflicts
and generic error interaction" row over ``uui/source``. Its Material treatment
is delivered entirely by shared vcl parts (there is no per-dialog Material
``.ui`` to add), so the honest, build-free M-scope is to *pin modality* rather
than draw pixels. This checker enforces, fail-closed:

* **Modality (three-way registry <-> classifier <-> CSV lock).** For each of the
  ten registered uui ``.ui`` roots it re-runs the shared
  ``sfx2::NotificationRouter::Classify`` mirror -- ``classify_route`` imported
  from ``bin/check-windows-dialog-notification-contract.py`` -- on the *live*
  ``.ui`` and asserts the result is ``native-exclusion`` (kept modal) with the
  classifier's own reason. It then cross-checks the shared
  ``dialog-notification-policy.csv`` row for the same locator, so no future edit
  can flip a credential or conflict prompt to the bottom-right notification form
  without failing here.
* **Credential precedence.** The four true credential dialogs
  (login / password / master-password / set-master-password) must hit the
  ``credential`` precedence branch, each anchored on a real ``visibility=False``
  password ``GtkEntry`` -- and no other registered dialog may carry one, so a
  password field added to or removed from the wrong root fails closed.
* **Modal conflict/error call sites.** The conflict and error handlers stay
  modal: the real ``weld::MessageDialog ... ->run()`` markers in
  ``nameclashdlg.cxx``, ``iahndl-errorhandler.cxx`` and ``iahndl-locking.cxx``
  must exist as real (comment-stripped) code.
* **The generic-error routing seam, honestly unwired.** The
  ``isInformationalErrorMessageRequest`` predicate (a request is informational
  iff it has exactly one continuation that is Approve or Abort) and the modal
  ``executeErrorDialog`` presentation must exist, and the ``routing_carveout``
  status must stay ``seam-only-not-wired``. No uui NotificationRouter producer
  is wired today; promoting the carve-out without a real producer fails closed.

It is source evidence only: no native build, dialog pixels, or runtime
interaction are claimed, and ``runtime_verified`` stays ``false``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/uui-interaction-policy.json"
NOTIFICATION_CHECKER_PATH = (
    REPOSITORY / "bin/check-windows-dialog-notification-contract.py"
)


class ValidationError(RuntimeError):
    """Raised when the uui interaction modality lock is incomplete or invalid."""


# --------------------------------------------------------------------------------------------------
# Shared classifier reuse (py3.9 pitfall: the notification checker uses
# ``from __future__ import annotations`` + frozen dataclasses, so the module must
# be registered in sys.modules BEFORE exec_module or the frozen-dataclass
# machinery cannot resolve its own type. We only touch classify_route /
# _scan_dialog_signals / read_registry / EXCLUSION_REASONS / _tag_name -- never
# the git-based discover_dialogs path.)
# --------------------------------------------------------------------------------------------------
def load_notification_checker(path: Path = NOTIFICATION_CHECKER_PATH):
    spec = importlib.util.spec_from_file_location(
        "check_windows_dialog_notification_contract", path
    )
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load notification checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # register BEFORE exec_module (py3.9 pitfall)
    spec.loader.exec_module(module)
    for symbol in (
        "classify_route",
        "_scan_dialog_signals",
        "read_registry",
        "EXCLUSION_REASONS",
        "_tag_name",
        "EXCLUSION_POLICY",
    ):
        if not hasattr(module, symbol):
            raise ValidationError(
                f"notification checker is missing expected symbol {symbol!r}"
            )
    return module


# --------------------------------------------------------------------------------------------------
# Source helpers
# --------------------------------------------------------------------------------------------------
def _read(repo_root: Path, rel: str) -> str:
    try:
        return (repo_root / rel).read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {rel}: {error}") from error


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals.

    Anchoring on the result guarantees a marker binds to real code, never to a
    call name that merely appears in a comment.
    """

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
        # state == "quote"
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


def _require(code: str, marker: str, where: str) -> None:
    if marker not in code:
        raise ValidationError(f"{where} must contain real code marker {marker!r}")


# --------------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------------
def load_registry(registry_path: Path, ndc) -> dict:
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValidationError(f"cannot read registry {registry_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    for key in (
        "contract",
        "inventory_row",
        "status",
        "runtime_verified",
        "notification_policy_csv",
        "dialogs",
        "credential_dialogs",
        "conflict_sites",
        "error_seam",
        "routing_carveout",
    ):
        if key not in data:
            raise ValidationError(f"registry is missing required key {key!r}")

    # Honesty invariants -- these are the ones the mutation suite must be able to trip.
    if data["runtime_verified"] is not False:
        raise ValidationError("runtime_verified must be false (no runtime evidence is claimed)")
    if data["status"] != "source-declared":
        raise ValidationError("status must be 'source-declared'")

    dialogs = data["dialogs"]
    if not isinstance(dialogs, list) or not dialogs:
        raise ValidationError("dialogs must be a non-empty array")
    seen: set[tuple[str, str]] = set()
    for index, dialog in enumerate(dialogs):
        if not isinstance(dialog, dict):
            raise ValidationError(f"dialog #{index} must be an object")
        for field in ("ui_path", "object_id", "widget_class", "expected_policy", "expected_reason_key"):
            value = dialog.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"dialog #{index} has empty required field {field!r}")
        if dialog["expected_policy"] != ndc.EXCLUSION_POLICY:
            raise ValidationError(
                f"dialog {dialog['object_id']} expected_policy must be "
                f"{ndc.EXCLUSION_POLICY!r} (every uui interaction dialog stays modal)"
            )
        if dialog["expected_reason_key"] not in ndc.EXCLUSION_REASONS:
            raise ValidationError(
                f"dialog {dialog['object_id']} has unknown expected_reason_key "
                f"{dialog['expected_reason_key']!r}"
            )
        locator = (dialog["ui_path"], dialog["object_id"])
        if locator in seen:
            raise ValidationError(f"duplicate registered dialog locator: {locator}")
        seen.add(locator)

    credential = data["credential_dialogs"]
    if not isinstance(credential, list) or not credential:
        raise ValidationError("credential_dialogs must be a non-empty array")
    dialog_ids = {dialog["object_id"] for dialog in dialogs}
    for cid in credential:
        if cid not in dialog_ids:
            raise ValidationError(f"credential dialog {cid!r} is not a registered dialog")

    for site in data["conflict_sites"]:
        if not isinstance(site, dict) or not isinstance(site.get("file"), str) or not isinstance(
            site.get("marker"), str
        ):
            raise ValidationError("each conflict_site must have string file and marker")

    seam = data["error_seam"]
    if not isinstance(seam, dict):
        raise ValidationError("error_seam must be an object")
    for field in ("file", "predicate", "markers", "modal_presentation"):
        if field not in seam:
            raise ValidationError(f"error_seam is missing {field!r}")
    if not isinstance(seam["markers"], list) or not seam["markers"]:
        raise ValidationError("error_seam.markers must be a non-empty array")

    carveout = data["routing_carveout"]
    if not isinstance(carveout, dict) or "status" not in carveout:
        raise ValidationError("routing_carveout must be an object with a status")

    return data


# --------------------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------------------
def classify_dialog(repo_root: Path, ndc, dialog: dict):
    """Return ``((policy, reason), signals)`` for one top-level uui dialog."""

    ui_path = dialog["ui_path"]
    object_id = dialog["object_id"]
    widget_class = dialog["widget_class"]
    path = repo_root / ui_path
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValidationError(f"cannot parse {ui_path}: {error}") from error
    for child in root:
        if (
            ndc._tag_name(child.tag) == "object"
            and child.get("class") == widget_class
            and child.get("id", "").strip() == object_id
        ):
            signals = ndc._scan_dialog_signals(child)
            return ndc.classify_route(ui_path, object_id, widget_class, signals), signals
    raise ValidationError(
        f"{ui_path} has no top-level {widget_class} object #{object_id}"
    )


def validate(repo_root: Path, registry_path: Path) -> dict:
    repo_root = repo_root.resolve()
    ndc = load_notification_checker()
    data = load_registry(registry_path, ndc)

    # The live shared CSV, read through the notification checker's own validated
    # reader so a malformed or resorted CSV surfaces as a clear failure.
    csv_path = repo_root / data["notification_policy_csv"]
    csv_entries = ndc.read_registry(csv_path)
    csv_by_locator = {entry.key.locator: entry for entry in csv_entries}

    # Completeness lock against the exhaustive CSV: the registry must cover
    # exactly the uui dialog roots the shared contract knows about, so a uui
    # dialog dropped from (or added to) source -- which moves its CSV row --
    # fails here instead of silently escaping this row's modality guarantee.
    uui_csv_locators = {
        locator for locator in csv_by_locator if locator[0].startswith("uui/uiconfig/ui/")
    }
    registered_locators = {
        (dialog["ui_path"], dialog["object_id"]) for dialog in data["dialogs"]
    }
    missing_from_registry = uui_csv_locators - registered_locators
    stale_in_registry = registered_locators - uui_csv_locators
    if missing_from_registry:
        raise ValidationError(
            "uui dialog root(s) present in the shared CSV but not registered here: "
            + "; ".join(f"{path}#{oid}" for path, oid in sorted(missing_from_registry))
        )
    if stale_in_registry:
        raise ValidationError(
            "registered uui dialog(s) with no matching shared-CSV root: "
            + "; ".join(f"{path}#{oid}" for path, oid in sorted(stale_in_registry))
        )

    credential_reason = ndc.EXCLUSION_REASONS["credential"]
    credential_ids = set(data["credential_dialogs"])

    for dialog in data["dialogs"]:
        object_id = dialog["object_id"]
        (policy, reason), signals = classify_dialog(repo_root, ndc, dialog)
        expected_reason = ndc.EXCLUSION_REASONS[dialog["expected_reason_key"]]

        # (1) live classifier agrees with the registry
        if policy != ndc.EXCLUSION_POLICY:
            raise ValidationError(
                f"dialog {object_id} classifies as {policy!r}, not native-exclusion; "
                "a uui interaction dialog must stay modal"
            )
        if reason != expected_reason:
            raise ValidationError(
                f"dialog {object_id} reason drifted: registry expects "
                f"{expected_reason!r} but the classifier yields {reason!r}"
            )

        # (2) three-way cross-check against the live shared CSV row
        entry = csv_by_locator.get((dialog["ui_path"], object_id))
        if entry is None:
            raise ValidationError(
                f"dialog {object_id} has no row in {data['notification_policy_csv']}"
            )
        if entry.policy != ndc.EXCLUSION_POLICY:
            raise ValidationError(
                f"dialog {object_id} CSV policy is {entry.policy!r}, not native-exclusion"
            )
        if entry.exclusion_reason != reason:
            raise ValidationError(
                f"dialog {object_id} CSV reason {entry.exclusion_reason!r} disagrees with "
                f"the classifier {reason!r}"
            )

        # (3) credential precedence, proven from a real password field. The
        # password-field signal must partition exactly the credential set.
        is_credential = object_id in credential_ids
        if signals.has_password != is_credential:
            if is_credential:
                raise ValidationError(
                    f"credential dialog {object_id} has no visibility=False password GtkEntry"
                )
            raise ValidationError(
                f"non-credential dialog {object_id} carries a password GtkEntry; "
                "the credential set must be exactly the password-bearing dialogs"
            )
        if is_credential and reason != credential_reason:
            raise ValidationError(
                f"credential dialog {object_id} did not hit the credential precedence branch "
                f"(reason {reason!r})"
            )

    # (4) modal conflict/error call sites are real code
    for site in data["conflict_sites"]:
        code = _strip_comments(_read(repo_root, site["file"]))
        _require(code, site["marker"], f"conflict site {site['file']}")

    # (5) the informational-error routing seam is real...
    seam = data["error_seam"]
    seam_code = _strip_comments(_read(repo_root, seam["file"]))
    _require(seam_code, seam["predicate"], f"error seam {seam['file']}")
    for marker in seam["markers"]:
        _require(seam_code, marker, f"error seam {seam['file']}")
    modal = seam["modal_presentation"]
    modal_code = _strip_comments(_read(repo_root, modal["file"]))
    _require(modal_code, modal["marker"], f"error seam modal presentation {modal['file']}")

    # (6) ...but honestly unwired: no producer exists.
    carveout = data["routing_carveout"]
    if carveout["status"] != "seam-only-not-wired":
        raise ValidationError(
            "routing_carveout.status must stay 'seam-only-not-wired' -- no uui "
            f"NotificationRouter producer is wired (found {carveout['status']!r})"
        )

    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = args.registry.resolve()
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"uui interaction modality contract failed:\n{error}", file=sys.stderr)
        return 1

    dialogs = data["dialogs"]
    print(
        "uui interaction modality contract passed: "
        f"{len(dialogs)} uui interaction dialog(s) locked modal "
        f"({len(data['credential_dialogs'])} credential), "
        "informational-error seam present and seam-only-not-wired."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
