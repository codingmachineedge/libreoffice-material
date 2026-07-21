#!/usr/bin/env python3
# -*- tab-width: 4; indent-tabs-mode: nil; py-indent-offset: 4 -*-
#
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Capture a bounded, read-only accessibility tree from a running office.

Run this script with the Python executable from the same LibreOffice build as
the office process.  It connects over a caller-provided, run-scoped UNO pipe
and writes JSON that can accompany an off-screen desktop screenshot.  The
collector deliberately avoids accessible text, actions, focus changes, and
listeners so it does not mutate the application or record document contents.
"""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

try:
    import pyuno
    import uno
except ImportError as error:
    raise SystemExit(
        "pyuno is unavailable. Run this with the built LibreOffice "
        "instdir/program/python.exe."
    ) from error


# These are UNO constant names, not a compatibility promise. Unknown values
# remain visible by their numeric ID in the JSON output.
ACCESSIBLE_ROLES = (
    "UNKNOWN", "ALERT", "COLUMN_HEADER", "CANVAS", "CHECK_BOX",
    "CHECK_MENU_ITEM", "COLOR_CHOOSER", "COMBO_BOX", "DATE_EDITOR",
    "DESKTOP_ICON", "DESKTOP_PANE", "DIRECTORY_PANE", "DIALOG",
    "DOCUMENT", "EMBEDDED_OBJECT", "END_NOTE", "FILE_CHOOSER", "FILLER",
    "FONT_CHOOSER", "FOOTER", "FOOTNOTE", "FRAME", "GLASS_PANE",
    "GRAPHIC", "GROUP_BOX", "HEADER", "HEADING", "HYPER_LINK", "ICON",
    "INTERNAL_FRAME", "LABEL", "LAYERED_PANE", "LIST", "LIST_ITEM",
    "MENU", "MENU_BAR", "MENU_ITEM", "OPTION_PANE", "PAGE_TAB",
    "PAGE_TAB_LIST", "PANEL", "PARAGRAPH", "PASSWORD_TEXT", "POPUP_MENU",
    "PUSH_BUTTON", "PROGRESS_BAR", "RADIO_BUTTON", "RADIO_MENU_ITEM",
    "ROW_HEADER", "ROOT_PANE", "SCROLL_BAR", "SCROLL_PANE", "SHAPE",
    "SEPARATOR", "SLIDER", "SPIN_BOX", "SPLIT_PANE", "STATUS_BAR",
    "TABLE", "TABLE_CELL", "TEXT", "TEXT_FRAME", "TOGGLE_BUTTON",
    "TOOL_BAR", "TOOL_TIP", "TREE", "VIEW_PORT", "WINDOW",
    "BUTTON_DROPDOWN", "BUTTON_MENU", "CAPTION", "CHART", "EDIT_BAR",
    "FORM", "IMAGE_MAP", "NOTE", "PAGE", "RULER", "SECTION",
    "TREE_ITEM", "TREE_TABLE", "COMMENT", "COMMENT_END",
    "DOCUMENT_PRESENTATION", "DOCUMENT_SPREADSHEET", "DOCUMENT_TEXT",
    "STATIC", "NOTIFICATION", "BLOCK_QUOTE",
)

ACCESSIBLE_STATES = (
    "INVALID", "ACTIVE", "ARMED", "BUSY", "CHECKED", "DEFUNC", "EDITABLE",
    "ENABLED", "EXPANDABLE", "EXPANDED", "FOCUSABLE", "FOCUSED",
    "HORIZONTAL", "ICONIFIED", "INDETERMINATE", "MANAGES_DESCENDANTS",
    "MODAL", "MULTI_LINE", "MULTI_SELECTABLE", "OPAQUE", "PRESSED",
    "RESIZABLE", "SELECTABLE", "SELECTED", "SENSITIVE", "SHOWING",
    "SINGLE_LINE", "STALE", "TRANSIENT", "VERTICAL", "VISIBLE", "MOVEABLE",
    "DEFAULT", "OFFSCREEN", "COLLAPSE", "CHECKABLE",
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipe", required=True, help="Unique UNO pipe name for this run")
    parser.add_argument("--output", required=True, type=Path, help="JSON output path")
    parser.add_argument("--run-id", default="", help="Opaque run identifier recorded in output")
    parser.add_argument("--screenshot-sha256", default="", help="Related screenshot hash")
    parser.add_argument(
        "--progress-output",
        type=Path,
        help="Optional JSON progress record for diagnosing a blocked UNO call",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="UNO connection timeout in seconds")
    parser.add_argument("--max-nodes", type=int, default=5000)
    parser.add_argument("--max-children", type=int, default=500)
    parser.add_argument("--max-depth", type=int, default=32)
    parser.add_argument("--max-text", type=int, default=256)
    parser.add_argument(
        "--require-visible",
        action="store_true",
        help="Fail if no node reports SHOWING or VISIBLE",
    )
    parser.add_argument(
        "--terminate",
        action="store_true",
        help="Terminate the dedicated office instance only after a successful dump",
    )
    args = parser.parse_args()
    for name in ("timeout", "max_nodes", "max_children", "max_depth", "max_text"):
        if getattr(args, name) <= 0:
            parser.error("--{} must be greater than zero".format(name.replace("_", "-")))
    return args


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def limit_text(value, maximum):
    try:
        text = str(value)
    except Exception as error:  # A disposed UNO proxy can fail even during str().
        return "<unavailable: {}>".format(type(error).__name__)
    text = text.replace("\x00", "\\0")
    if len(text) > maximum:
        return text[:maximum] + "…"
    return text


def compact_error(error, maximum):
    return limit_text("{}: {}".format(type(error).__name__, error), maximum)


def constant_map(namespace, names):
    result = {}
    for name in names:
        try:
            result[int(uno.getConstantByName("{}.{}".format(namespace, name)))] = name
        except Exception:
            # A future office version may remove or rename a constant. Its
            # numeric value still remains represented in the resulting JSON.
            continue
    return result


def connect(pipe_name, timeout):
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    url = "uno:pipe,name={};urp;StarOffice.ComponentContext".format(pipe_name)
    deadline = time.monotonic() + timeout
    no_connect = pyuno.getClass("com.sun.star.connection.NoConnectException")
    while True:
        try:
            return resolver.resolve(url)
        except no_connect:
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out connecting to the run-scoped UNO pipe")
            time.sleep(0.2)


def optional_bounds(context, errors, max_text):
    try:
        bounds = context.getBounds()
        return {
            "x": int(bounds.X),
            "y": int(bounds.Y),
            "width": int(bounds.Width),
            "height": int(bounds.Height),
        }
    except AttributeError:
        # XAccessibleComponent is optional. Absence is represented as null,
        # not as a traversal failure.
        return None
    except Exception as error:
        errors.append("bounds: " + compact_error(error, max_text))
        return None


def collect_tree(root_accessible, limits, role_names, state_names, progress=None):
    nodes = []
    stack = [(root_accessible, [], 0)]
    partial = False
    visible_nodes = 0
    error_count = 0
    truncation_reasons = []

    while stack:
        if progress is not None and len(nodes) % 10 == 0:
            progress("collecting", node_count=len(nodes), current_path=stack[-1][1])
        if len(nodes) >= limits["max_nodes"]:
            partial = True
            truncation_reasons.append("max_nodes")
            break

        accessible, path, depth = stack.pop()
        node_errors = []
        try:
            context = accessible.getAccessibleContext()
        except Exception as error:
            nodes.append({
                "path": path,
                "role": {"id": None, "name": "UNAVAILABLE"},
                "name": "",
                "description": "",
                "state_mask": "0",
                "states": [],
                "child_count_reported": None,
                "children_visited": 0,
                "children_truncated": False,
                "bounds_parent_px": None,
                "errors": ["context: " + compact_error(error, limits["max_text"])],
            })
            error_count += 1
            partial = True
            continue

        def read(label, function, fallback):
            try:
                return function()
            except Exception as error:
                node_errors.append(label + ": " + compact_error(error, limits["max_text"]))
                return fallback

        role_id = read("role", lambda: int(context.getAccessibleRole()), -1)
        name = limit_text(read("name", context.getAccessibleName, ""), limits["max_text"])
        description = limit_text(
            read("description", context.getAccessibleDescription, ""), limits["max_text"]
        )
        state_mask = read("state", lambda: int(context.getAccessibleStateSet()), 0)
        states = [
            state_name
            for state_value, state_name in sorted(state_names.items())
            if state_value and state_mask & state_value == state_value
        ]
        if "SHOWING" in states or "VISIBLE" in states:
            visible_nodes += 1

        child_count = read("child_count", lambda: int(context.getAccessibleChildCount()), 0)
        child_count = max(child_count, 0)
        children_visited = min(child_count, limits["max_children"])
        children_truncated = child_count > children_visited
        if children_truncated:
            partial = True
            truncation_reasons.append("max_children")

        if depth >= limits["max_depth"] and children_visited:
            partial = True
            children_truncated = True
            children_visited = 0
            truncation_reasons.append("max_depth")

        bounds = optional_bounds(context, node_errors, limits["max_text"])
        if node_errors:
            error_count += len(node_errors)
            partial = True
        nodes.append({
            "path": path,
            "role": {"id": role_id, "name": role_names.get(role_id, "UNKNOWN")},
            "name": name,
            "description": description,
            "state_mask": str(state_mask),
            "states": states,
            "child_count_reported": child_count,
            "children_visited": children_visited,
            "children_truncated": children_truncated,
            "bounds_parent_px": bounds,
            "errors": node_errors,
        })

        children = []
        for child_index in range(children_visited):
            try:
                children.append((context.getAccessibleChild(child_index), path + [child_index], depth + 1))
            except Exception as error:
                node_errors.append(
                    "child[{}]: {}".format(
                        child_index, compact_error(error, limits["max_text"])
                    )
                )
                error_count += 1
                partial = True
        stack.extend(reversed(children))

    return {
        "nodes": nodes,
        "partial": partial,
        "visible_nodes": visible_nodes,
        "errors": error_count,
        "truncation_reasons": sorted(set(truncation_reasons)),
    }


def atomic_json_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
    os.replace(temporary, path)


def make_progress_writer(path, run_id):
    if path is None:
        return lambda _stage, **_details: None

    def write(stage, **details):
        atomic_json_write(
            path,
            {
                "schema_version": 1,
                "updated_at_utc": utc_now(),
                "run_id": run_id,
                "stage": stage,
                "details": details,
            },
        )

    return write


def optional_text(function, maximum):
    try:
        return limit_text(function(), maximum)
    except Exception as error:
        return "<unavailable: {}>".format(type(error).__name__)


def main():
    args = parse_arguments()
    progress = make_progress_writer(args.progress_output, args.run_id)
    limits = {
        "max_nodes": args.max_nodes,
        "max_children": args.max_children,
        "max_depth": args.max_depth,
        "max_text": args.max_text,
    }
    role_names = constant_map("com.sun.star.accessibility.AccessibleRole", ACCESSIBLE_ROLES)
    state_names = constant_map("com.sun.star.accessibility.AccessibleStateType", ACCESSIBLE_STATES)

    try:
        progress("connecting", pipe=args.pipe)
        context = connect(args.pipe, args.timeout)
        progress("connected")
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context
        )
        progress("desktop_resolved")
        frame = desktop.getCurrentFrame()
        if frame is None:
            raise RuntimeError("The office process has no current frame")
        progress("frame_resolved")
        window = frame.getContainerWindow()
        if window is None:
            raise RuntimeError("The current frame has no container window")
        progress("window_resolved")
        accessible = window.getProperty("XAccessible")
        if accessible is None:
            raise RuntimeError("The container window did not expose XAccessible")
        root_context = accessible.getAccessibleContext()
        if root_context is None:
            raise RuntimeError("The container accessibility object has no context")
        progress("accessibility_root_resolved")
        tree = collect_tree(accessible, limits, role_names, state_names, progress)
        progress("tree_collected", node_count=len(tree["nodes"]))
        report = {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "run_id": args.run_id,
            "screenshot_sha256": args.screenshot_sha256,
            "root": {
                "frame_name": optional_text(lambda: frame.getName(), args.max_text),
                "frame_title": optional_text(lambda: frame.getTitle(), args.max_text),
            },
            "limits": limits,
            "summary": {
                "node_count": len(tree["nodes"]),
                "partial": tree["partial"],
                "errors": tree["errors"],
                "visible_nodes": tree["visible_nodes"],
                "truncation_reasons": tree["truncation_reasons"],
            },
            "nodes": tree["nodes"],
        }
        atomic_json_write(args.output, report)
        progress("report_written", output=str(args.output))
        if args.require_visible and not tree["visible_nodes"]:
            raise RuntimeError("No accessible node reported SHOWING or VISIBLE")
        if args.terminate:
            try:
                terminated = desktop.terminate()
            except Exception as error:
                # LibreOffice can tear down the URP bridge before returning
                # from the successful terminate() RPC.  The process exit is
                # the authoritative result in that narrow race; preserve the
                # accessibility report instead of misclassifying it as a
                # failed no-nag run.
                if type(error).__name__ != "DisposedException":
                    raise
                terminated = True
            if not terminated:
                raise RuntimeError("The dedicated office process rejected normal termination")
        progress("complete", terminated=args.terminate)
        return 0
    except Exception as error:
        error_report = {
            "schema_version": 1,
            "captured_at_utc": utc_now(),
            "run_id": args.run_id,
            "fatal_error": compact_error(error, args.max_text),
        }
        atomic_json_write(args.output, error_report)
        progress("failed", error=error_report["fatal_error"])
        print(error_report["fatal_error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
