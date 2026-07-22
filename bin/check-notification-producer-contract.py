#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the native NotificationRouter *producer* inventory.

The registry ``qa/windows-ui-contract/notification-producer-policy.json`` names every audited
call site that emits a bottom-right notification instead of a transient modal message box
(docs/design/07-feedback.md 7.5). This checker enforces, fail-closed against real
(comment-stripped) source:

* each producer's enclosing function, its ``sfx2::NotificationRouter::<call>(`` call, and the
  ``"<source>"_ostr`` display source literal all exist as real code, not comments;
* the declared severity is honest -- an informational-notice producer (``NotifyInfo``) spells its
  ``NotificationSeverity::<Severity>`` at the call site; a confirmation producer
  (``NotifyConfirmation``) declares only Success/Information, the two outcomes the router maps;
* every producer is informational-only (it routes as a notification, never a modal prompt), and its
  display source is inside the compiled ``isApprovedSafeDisplaySource`` allowlist -- so a mislabeled
  entry that would be silently redacted at runtime fails here instead;
* when a producer declares the optional ``wiring_markers`` list, each anchored pattern -- the arming
  assignment, the consumption call, and the opt-in guard literal -- must exist as real code, so a
  partial revert that removes only the wiring (leaving the producer function still defined but dead,
  unreachable code) fails here instead of passing on the surviving definition; and
* the shared confirmation seam is real: the router header declares ``NotifyConfirmation``, the router
  source defines it forwarding through ``NotifyInfo`` with both Success and Information, and
  ``Classify`` keeps the informational case non-modal.

Scope: it validates ONLY the registered producers and the router seam. It deliberately does not try
to prove the whole legacy-dialog backlog has been routed (that lives in dialog-notification-policy.csv),
so it never fails on an unrouted dialog -- only on an unreal or mislabeled producer entry.

It is source evidence only: no native build, notification pixels, or runtime interaction are claimed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/notification-producer-policy.json"

# The four severities NotificationDraft accepts (include/sfx2/notificationcenter.hxx).
ALLOWED_SEVERITIES = frozenset({"Information", "Success", "Warning", "Error"})
# The two outcomes NotificationRouter::NotifyConfirmation maps (bSuccess ? Success : Information).
CONFIRMATION_SEVERITIES = frozenset({"Success", "Information"})
KNOWN_ROUTER_CALLS = frozenset({"NotifyInfo", "NotifyConfirmation"})


class ValidationError(RuntimeError):
    """Raised when the producer contract is incomplete, unreal, or mislabeled."""


# --------------------------------------------------------------------------------------------------
# IO / source helpers
# --------------------------------------------------------------------------------------------------
def _read(repo_root: Path, rel: str) -> str:
    path = repo_root / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {rel}: {error}") from error


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments while preserving string/char literals and line count.

    Anchoring on the result guarantees the contract binds to real code, never to a call name that
    merely appears in a comment or doc-string.
    """

    out: list[str] = []
    i, n = 0, len(text)
    state = "code"  # code | line | block | quote
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
def _validate_wiring_markers_shape(producer: dict) -> None:
    """Structurally validate a producer's optional ``wiring_markers`` list.

    The field is optional: a producer without it is valid (the Batch-A producers carry none). When
    present it must be a non-empty array of ``{file, pattern}`` objects (``note`` optional), so a
    malformed reachability declaration fails closed rather than silently enforcing nothing.
    """

    markers = producer.get("wiring_markers")
    if markers is None:
        return
    if not isinstance(markers, list) or not markers:
        raise ValidationError(
            f"producer {producer['id']} wiring_markers must be a non-empty array when present"
        )
    for index, marker in enumerate(markers):
        if not isinstance(marker, dict):
            raise ValidationError(
                f"producer {producer['id']} wiring_marker #{index} must be an object"
            )
        for field in ("file", "pattern"):
            value = marker.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(
                    f"producer {producer['id']} wiring_marker #{index} "
                    f"has empty required field {field!r}"
                )
        note = marker.get("note")
        if note is not None and (not isinstance(note, str) or not note.strip()):
            raise ValidationError(
                f"producer {producer['id']} wiring_marker #{index} "
                "note must be a non-empty string when present"
            )


def load_registry(registry_path: Path) -> dict:
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValidationError(f"cannot read registry {registry_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(f"registry is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValidationError("registry root must be a JSON object")

    for key in ("approved_display_sources", "approved_source_registry", "router",
                "confirmation_severities", "required_producers", "producers"):
        if key not in data:
            raise ValidationError(f"registry is missing required key {key!r}")

    if not isinstance(data["approved_display_sources"], list) or not data["approved_display_sources"]:
        raise ValidationError("approved_display_sources must be a non-empty array")
    if set(data["confirmation_severities"]) != CONFIRMATION_SEVERITIES:
        raise ValidationError(
            f"confirmation_severities must be {sorted(CONFIRMATION_SEVERITIES)}"
        )

    router = data["router"]
    if not isinstance(router, dict):
        raise ValidationError("router must be an object")
    for key in ("header", "source", "confirmation_entry_point"):
        if not isinstance(router.get(key), str) or not router[key].strip():
            raise ValidationError(f"router.{key} must be a non-empty string")

    producers = data["producers"]
    if not isinstance(producers, list):
        raise ValidationError("producers must be an array")
    required = data["required_producers"]
    if not isinstance(required, list) or not required:
        raise ValidationError("required_producers must be a non-empty array")
    if len(producers) < len(required):
        raise ValidationError(
            f"producers ({len(producers)}) cannot be fewer than required_producers ({len(required)})"
        )

    seen: set[str] = set()
    for index, producer in enumerate(producers):
        if not isinstance(producer, dict):
            raise ValidationError(f"producer #{index} must be an object")
        for field in ("id", "file", "function", "router_call", "source"):
            value = producer.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"producer #{index} has empty required field {field!r}")
        if producer["id"] in seen:
            raise ValidationError(f"duplicate producer id: {producer['id']}")
        seen.add(producer["id"])
        if not isinstance(producer.get("severity"), list) or not producer["severity"]:
            raise ValidationError(f"producer {producer['id']} must list at least one severity")
        if producer.get("informational_only") is not True:
            raise ValidationError(
                f"producer {producer['id']} must set informational_only=true "
                "(producers route as notifications, never modal prompts)"
            )
        _validate_wiring_markers_shape(producer)

    missing = [pid for pid in required if pid not in seen]
    if missing:
        raise ValidationError("required producer(s) not registered: " + ", ".join(missing))
    return data


# --------------------------------------------------------------------------------------------------
# Approved display-source allowlist (mirrors the compiled isApprovedSafeDisplaySource)
# --------------------------------------------------------------------------------------------------
def _cpp_approved_sources(repo_root: Path, rel: str) -> set[str]:
    code = _strip_comments(_read(repo_root, rel))
    match = re.search(r"isApprovedSafeDisplaySource\b.*?Approved\s*=\s*\{(.*?)\}", code, re.DOTALL)
    if not match:
        raise ValidationError(
            f"cannot locate the isApprovedSafeDisplaySource allowlist in {rel}"
        )
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def validate_display_source_allowlist(repo_root: Path, data: dict) -> None:
    policy_sources = set(data["approved_display_sources"])
    cpp_sources = _cpp_approved_sources(repo_root, data["approved_source_registry"])
    if policy_sources != cpp_sources:
        raise ValidationError(
            "approved_display_sources drift from the compiled allowlist: "
            f"policy={sorted(policy_sources)} vs source={sorted(cpp_sources)}"
        )


# --------------------------------------------------------------------------------------------------
# Shared confirmation seam (router header + source)
# --------------------------------------------------------------------------------------------------
def validate_router(repo_root: Path, data: dict) -> None:
    router = data["router"]
    entry = router["confirmation_entry_point"]

    header = _strip_comments(_read(repo_root, router["header"]))
    _require(header, f"{entry}(", f"router header {router['header']}")

    source = _strip_comments(_read(repo_root, router["source"]))
    _require(source, f"NotificationRouter::{entry}", f"router source {router['source']}")
    # The confirmation forwards through NotifyInfo and maps only Success / Information.
    _require(source, "NotifyInfo(", f"router source {router['source']}")
    for severity in sorted(CONFIRMATION_SEVERITIES):
        _require(source, f"NotificationSeverity::{severity}", f"router source {router['source']}")
    # Classify keeps the purely informational case non-modal (the producers' routing guarantee).
    _require(source, "return NotificationRoute::Notification;", f"router source {router['source']}")


# --------------------------------------------------------------------------------------------------
# Producer call sites
# --------------------------------------------------------------------------------------------------
def validate_producers(repo_root: Path, data: dict) -> None:
    approved = set(data["approved_display_sources"])
    stripped_cache: dict[str, str] = {}

    def stripped(rel: str) -> str:
        if rel not in stripped_cache:
            stripped_cache[rel] = _strip_comments(_read(repo_root, rel))
        return stripped_cache[rel]

    for producer in data["producers"]:
        where = f"producer {producer['id']} ({producer['file']})"
        code = stripped(producer["file"])

        # The enclosing function and the qualified router call must both be real code.
        _require(code, producer["function"], where)
        call = producer["router_call"]
        if call not in KNOWN_ROUTER_CALLS:
            raise ValidationError(f"{where} has unknown router_call {call!r}")
        _require(code, f"sfx2::NotificationRouter::{call}(", where)

        # The display source literal must be present and inside the SafeDisplayText allowlist.
        if producer["source"] not in approved:
            raise ValidationError(
                f"{where} display source {producer['source']!r} is not in approved_display_sources"
            )
        _require(code, f'"{producer["source"]}"_ostr', where)

        # Severity honesty.
        severities = producer["severity"]
        for severity in severities:
            if severity not in ALLOWED_SEVERITIES:
                raise ValidationError(f"{where} has unknown severity {severity!r}")
        if call == "NotifyInfo":
            # An informational-notice producer spells the exact severity enum at its call site.
            for severity in severities:
                _require(code, f"NotificationSeverity::{severity}", where)
        else:  # NotifyConfirmation
            extra = set(severities) - CONFIRMATION_SEVERITIES
            if extra:
                raise ValidationError(
                    f"{where} is a confirmation producer but declares non-confirmation "
                    f"severit(y/ies) {sorted(extra)}; only {sorted(CONFIRMATION_SEVERITIES)} are mapped"
                )

        # Reachability wiring. When a producer declares wiring_markers, each anchored pattern must
        # exist as real (comment-stripped) code. This closes the gap where a partial revert removes
        # only the arming, consumption, or guard site: the producer function itself still exists (so
        # the existence checks above keep passing) but is dead, unreachable code -- caught here.
        for index, marker in enumerate(producer.get("wiring_markers") or []):
            marker_where = f"{where} wiring_marker #{index}"
            note = marker.get("note")
            if note:
                marker_where += f" [{note}]"
            _require(stripped(marker["file"]), marker["pattern"], marker_where)


def validate(repo_root: Path, registry_path: Path) -> dict:
    data = load_registry(registry_path)
    validate_display_source_allowlist(repo_root, data)
    validate_router(repo_root, data)
    validate_producers(repo_root, data)
    return data


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--registry", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve()
        if args.registry is not None
        else repo_root / "qa/windows-ui-contract/notification-producer-policy.json"
    )
    try:
        data = validate(repo_root, registry_path)
    except ValidationError as error:
        print(f"Notification producer contract failed:\n{error}", file=sys.stderr)
        return 1

    producers = data["producers"]
    confirmations = sum(1 for p in producers if p["router_call"] == "NotifyConfirmation")
    print(
        "Notification producer contract passed: "
        f"{len(producers)} audited producer(s) "
        f"({confirmations} transient confirmation(s)) verified against real source, "
        "each SafeDisplayText under the compiled allowlist and informational-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
