#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Validate the centralized Windows notification-form dialog placement hook."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


class ValidationError(RuntimeError):
    """Raised when the Windows dialog-placement contract is weakened."""


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_DIALOG_SOURCE = REPOSITORY / "vcl/source/window/dialog.cxx"
DEFAULT_EVENT_SOURCE = REPOSITORY / "vcl/source/window/event.cxx"
DEFAULT_HEADER = REPOSITORY / "include/vcl/toolkit/dialog.hxx"
HELPER_SIGNATURE = "void lclPositionDialogAsWindowsNotification(Dialog& rDialog)"
LOW_LEVEL_CALL = "lclPositionDialogAsWindowsNotification(*this);"
FINAL_INIT_HOOK = "pDialog->ImplPositionAsWindowsNotification();"
METHOD_DECLARATION = "SAL_DLLPRIVATE void    ImplPositionAsWindowsNotification();"


def _extract_braced_block(source: str, marker: str) -> str:
    start = source.find(marker)
    if start < 0:
        raise ValidationError(f"required source marker is missing: {marker}")
    brace = source.find("{", start + len(marker))
    if brace < 0:
        raise ValidationError(f"required source block has no opening brace: {marker}")

    depth = 0
    for position in range(brace, len(source)):
        character = source[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    raise ValidationError(f"required source block is unterminated: {marker}")


def _is_inside_windows_guard(source: str, position: int) -> bool:
    stack: list[bool] = []
    offset = 0
    for line in source.splitlines(keepends=True):
        if offset > position:
            break
        directive = line.strip()
        if directive.startswith("#if"):
            stack.append(bool(re.search(r"\b_WIN32\b", directive)))
        elif directive.startswith("#endif"):
            if stack:
                stack.pop()
        offset += len(line)
    return any(stack)


def _require_markers(block: str, markers: tuple[str, ...], contract: str) -> None:
    missing = [marker for marker in markers if marker not in block]
    if missing:
        raise ValidationError(f"{contract} is missing: " + ", ".join(missing))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error


def validate(dialog_source_path: Path, event_source_path: Path, header_path: Path) -> None:
    dialog_source = _read(dialog_source_path)
    event_source = _read(event_source_path)
    header = _read(header_path)

    if dialog_source.count(HELPER_SIGNATURE) != 1:
        raise ValidationError("Windows dialog placement helper must be defined exactly once")
    if dialog_source.count(LOW_LEVEL_CALL) != 1:
        raise ValidationError("Windows dialog placement implementation must be called exactly once")
    if event_source.count(FINAL_INIT_HOOK) != 1:
        raise ValidationError("Windows final-InitShow dialog hook must be called exactly once")
    if header.count(METHOD_DECLARATION) != 1:
        raise ValidationError("Dialog notification-placement method must be declared exactly once")

    helper_position = dialog_source.index(HELPER_SIGNATURE)
    low_level_call_position = dialog_source.index(LOW_LEVEL_CALL)
    final_hook_position = event_source.index(FINAL_INIT_HOOK)
    if not _is_inside_windows_guard(dialog_source, helper_position):
        raise ValidationError("Windows dialog placement helper must be inside an _WIN32 guard")
    if not _is_inside_windows_guard(dialog_source, low_level_call_position):
        raise ValidationError("Windows dialog placement implementation must be inside an _WIN32 guard")
    if not _is_inside_windows_guard(event_source, final_hook_position):
        raise ValidationError("Windows final-InitShow dialog hook must be inside an _WIN32 guard")

    helper = _extract_braced_block(dialog_source, HELPER_SIGNATURE)
    _require_markers(
        helper,
        (
            "comphelper::LibreOfficeKit::isActive()",
            "GetDesktopRectPixel()",
            "GetParent()",
            "GetWindowExtentsAbsolute().GetIntersection(aWorkArea)",
            "aDialogExtent(rDialog.GetWindowExtentsAbsolute())",
            "std::max<tools::Long>(0, aAnchorSize.Width() - aDialogSize.Width())",
            "std::max<tools::Long>(0, aAnchorSize.Height() - aDialogSize.Height())",
            "std::min(kMaterialNotificationInset, nHorizontalRoom)",
            "std::min(kMaterialNotificationInset, nVerticalRoom)",
            "lclClampDialogCoordinate(",
            "OutputToAbsoluteScreenPixel(Point())",
            "aDecorationOffset",
            "SetPosPixel(",
        ),
        "Windows dialog placement helper",
    )

    lok_guard = helper.index("comphelper::LibreOfficeKit::isActive()")
    work_area = helper.index("GetDesktopRectPixel()")
    if lok_guard > work_area:
        raise ValidationError("LibreOfficeKit guard must run before dialog geometry is changed")

    if "constexpr tools::Long kMaterialNotificationInset = 16;" not in dialog_source:
        raise ValidationError("Windows dialog placement must retain the 16-pixel Material inset")

    clamp = _extract_braced_block(
        dialog_source,
        "tools::Long lclClampDialogCoordinate(tools::Long nDesired, "
        "tools::Long nWorkAreaStart,",
    )
    _require_markers(
        clamp,
        (
            "std::max(nWorkAreaStart, nWorkAreaEnd - nDialogExtent + 1)",
            "std::clamp(nDesired, nWorkAreaStart, nLastVisibleStart)",
        ),
        "Windows dialog clamping helper",
    )

    placement_method = _extract_braced_block(
        dialog_source, "void Dialog::ImplPositionAsWindowsNotification()"
    )
    if LOW_LEVEL_CALL not in placement_method:
        raise ValidationError("Dialog placement method must call the Windows implementation")

    state_changed = _extract_braced_block(dialog_source, "void Dialog::StateChanged(")
    init_show = _extract_braced_block(
        state_changed, "if (nType == StateChangedType::InitShow)"
    )
    if "DoInitialLayout();" not in init_show:
        raise ValidationError("Dialog InitShow must retain DoInitialLayout()")
    if LOW_LEVEL_CALL in state_changed or FINAL_INIT_HOOK in state_changed:
        raise ValidationError("Dialog placement must not run before derived InitShow layout completes")

    init_dispatch = _extract_braced_block(event_source, "void Window::ImplCallInitShow()")
    _require_markers(
        init_dispatch,
        (
            "CompatStateChanged( StateChangedType::InitShow );",
            "mpWindowImpl->mbInInitShow    = false;",
            "dynamic_cast<Dialog*>(this)",
            FINAL_INIT_HOOK,
        ),
        "final InitShow dispatch",
    )
    state_dispatch_position = init_dispatch.index(
        "CompatStateChanged( StateChangedType::InitShow );"
    )
    init_complete_position = init_dispatch.index("mpWindowImpl->mbInInitShow    = false;")
    placement_position = init_dispatch.index(FINAL_INIT_HOOK)
    if not state_dispatch_position < init_complete_position < placement_position:
        raise ValidationError(
            "Windows dialog placement must run after the complete virtual InitShow dispatch"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialog-source", type=Path, default=DEFAULT_DIALOG_SOURCE)
    parser.add_argument("--event-source", type=Path, default=DEFAULT_EVENT_SOURCE)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    args = parser.parse_args()

    try:
        validate(args.dialog_source, args.event_source, args.header)
    except ValidationError as error:
        print(f"Windows dialog placement validation failed: {error}", file=sys.stderr)
        return 1

    print(
        "Windows dialog placement validation passed: centralized final-InitShow hook, "
        "Windows/LibreOfficeKit guards, owner/work-area anchoring, Material inset, "
        "and decorated-extent clamping are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
