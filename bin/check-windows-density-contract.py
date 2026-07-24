#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source ledger for the Material density model (WIN-FND-005).

WIN-FND-005 is honest only as a density-token *pinning + deferral* ledger: fixed
single-profile native metrics are compiled, but a *selectable* compact/comfortable
density is target-only. This contract proves that claim is internally consistent and
not silently regressing. It never implements a selector.

It asserts, source-only:

* **Native metrics** -- definition.xml's ``<metrics>`` still declares exactly the 15
  single-profile integer roles at their compiled values, and the ``<metrics>`` element
  still carries **zero** attributes (a density attribute is rejected by the compiled
  ``WidgetDefinitionReader``, corroborated by its ``definitionMetricsSectionAttribute``
  invalid-fixture test);
* **Target table** -- docs/design/01-foundations.md section 6's 7-row compact/
  comfortable table is present verbatim, every row tagged ``specified`` (target-only);
* **Design honesty** -- MATERIAL_DESIGN.md's "Desktop density" section still names both
  profiles and keeps its "implemented and verified separately" honesty language;
* **Carve-out consistency** -- qa/windows-ui-contract/calc-chrome.json's existing
  per-surface density carve-out (``--tb`` / ``--menu``) is byte-consistent with the
  master section-6 table, so the two cannot silently drift;
* **Selector presence** -- Stage 1 makes density selectable but *stored-value-only*
  (the compact/comfortable metric plumbing is still target-only). This guard was
  migrated from the earlier absence guard per the migrate-never-freeze-stock rule: a
  Git-tracked walk over ``.ui`` files and officecfg schemas must now **find** the
  MaterialDensity officecfg property and the density radio widgets in
  ``cui/uiconfig/ui/appearance.ui``, and their disappearance fails closed.

Source evidence only: ``runtime_verified`` is false throughout. It advances none of the
row's build/pixel/matrix/perf/compat gates; wiring the metric schema to comfortable/
compact and any rendered evidence are the separate build gates.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "qa/windows-ui-contract/density-contract.json"
DEFINITION_PATH = "vcl/uiconfig/theme_definitions/material/definition.xml"
CHAPTER_PATH = "docs/design/01-foundations.md"
MATERIAL_DESIGN_PATH = "MATERIAL_DESIGN.md"
CALC_CHROME_PATH = "qa/windows-ui-contract/calc-chrome.json"
READER_TEST_PATH = "vcl/qa/cppunit/widgetdraw/WidgetDefinitionReaderTest.cxx"
CONTRACT = "material-density-model"
THEME_FLAG = "VCL_FILE_WIDGET_THEME"

# The selector-presence guard (migrated from an absence guard): Stage 1 makes density
# a stored-value-only selection, so an officecfg property and a .ui widget whose
# name/id carries "density" must now BOTH exist. Their patterns/expected files live in
# the registry's ``selector_presence`` block; these are the fallback defaults.
UI_SELECTOR_PATTERN = r'id="[^"]*[Dd]ensity'
CFG_SELECTOR_PATTERN = r'oor:name="[^"]*[Dd]ensity'


class ValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: root must be an object")
    return value


def load_repository(repo_root: Path = REPOSITORY) -> tuple[dict[str, Any], dict[str, str]]:
    registry = _read_json(repo_root / REGISTRY_PATH)
    contents: dict[str, str] = {}
    for relative in (
        DEFINITION_PATH,
        CHAPTER_PATH,
        MATERIAL_DESIGN_PATH,
        CALC_CHROME_PATH,
        READER_TEST_PATH,
    ):
        path = repo_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return registry, contents


# --------------------------------------------------------------------------------------------------
# definition.xml native metrics
# --------------------------------------------------------------------------------------------------
def _validate_native_metrics(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    try:
        root = ET.fromstring(contents.get(DEFINITION_PATH, ""))
    except ET.ParseError as error:
        errors.append(f"native_metrics:definition xml parse error: {error}")
        return
    metrics_el = root.find("metrics")
    if metrics_el is None:
        errors.append("native_metrics:<metrics> section missing from definition.xml")
        return
    if len(metrics_el.attrib) != 0:
        errors.append(
            "native_metrics:<metrics> must carry zero attributes (a density attribute is "
            f"rejected by the reader); found {sorted(metrics_el.attrib)}"
        )
    actual = {}
    for metric in metrics_el.findall("metric"):
        name = metric.get("name")
        if isinstance(name, str):
            actual[name] = metric.get("value")

    expected = registry.get("native_metrics")
    if not isinstance(expected, dict) or not expected:
        errors.append("registry:native_metrics:non-empty object required")
        return
    if len(actual) != len(expected):
        errors.append(
            f"native_metrics:definition.xml declares {len(actual)} metric roles, "
            f"the ledger pins {len(expected)} (single-profile geometry drifted)"
        )
    for name, value in expected.items():
        if name not in actual:
            errors.append(f"native_metrics:{name} missing from definition.xml <metrics>")
        elif actual[name] != value:
            errors.append(
                f"native_metrics:{name} is {actual[name]!r}, expected {value!r} (metric drift)"
            )
    for name in actual:
        if name not in expected:
            errors.append(f"native_metrics:{name} present in definition.xml but not ledgered")


# --------------------------------------------------------------------------------------------------
# section-6 target table
# --------------------------------------------------------------------------------------------------
def _section6_rows(chapter: str) -> dict[str, tuple[str, str]]:
    """Return {variable: (compact, comfortable)} from the section-6 density table."""

    lines = chapter.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("## 6."))
    except StopIteration:
        return {}
    rows: dict[str, tuple[str, str]] = {}
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.replace("`", "").strip("|").split("|")]
        if len(cells) != 4:
            continue
        # Skip the header row and the markdown separator (`---`, `---:`), but keep
        # data rows whose variable name legitimately starts with `--` (e.g. --ctrl).
        if cells[0] == "Variable" or re.fullmatch(r"[-:]+", cells[0]):
            continue
        rows[cells[0]] = (cells[1], cells[2])
    return rows


def _validate_target_table(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    doc_rows = _section6_rows(contents.get(CHAPTER_PATH, ""))
    declared = registry.get("target_table")
    if not isinstance(declared, list) or not declared:
        errors.append("registry:target_table:non-empty array required")
        return
    if len(doc_rows) != len(declared):
        errors.append(
            f"target_table:section 6 has {len(doc_rows)} rows, the ledger pins "
            f"{len(declared)} -- every density row must be ledgered"
        )
    for row in declared:
        if not isinstance(row, dict):
            errors.append("target_table:row:object required")
            continue
        variable = row.get("variable")
        compact = row.get("compact")
        comfortable = row.get("comfortable")
        if not isinstance(variable, str):
            errors.append("target_table:row:variable must be a string")
            continue
        if row.get("status") != "specified":
            errors.append(f"target_table:{variable}:status must be 'specified' (target-only)")
        if variable not in doc_rows:
            errors.append(f"target_table:{variable}:no matching row in section 6")
            continue
        doc_compact, doc_comfortable = doc_rows[variable]
        if doc_compact != compact or doc_comfortable != comfortable:
            errors.append(
                f"target_table:{variable}:doc drift: section 6 says "
                f"({doc_compact!r}, {doc_comfortable!r}), ledger says ({compact!r}, {comfortable!r})"
            )


# --------------------------------------------------------------------------------------------------
# MATERIAL_DESIGN.md honesty
# --------------------------------------------------------------------------------------------------
def _validate_design_honesty(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    design = contents.get(MATERIAL_DESIGN_PATH, "")
    honesty = registry.get("design_honesty")
    if not isinstance(honesty, dict):
        errors.append("registry:design_honesty:object required")
        return
    for marker in honesty.get("markers", []) or []:
        if isinstance(marker, str) and marker not in design:
            errors.append(f"design_honesty:marker missing in MATERIAL_DESIGN.md ({marker!r})")


# --------------------------------------------------------------------------------------------------
# calc-chrome carve-out consistency
# --------------------------------------------------------------------------------------------------
def _validate_carveout_consistency(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    doc_rows = _section6_rows(contents.get(CHAPTER_PATH, ""))
    try:
        calc = json.loads(contents.get(CALC_CHROME_PATH, ""))
    except (json.JSONDecodeError, TypeError) as error:
        errors.append(f"carveout:cannot parse calc-chrome.json ({error})")
        return
    density = calc.get("density") if isinstance(calc, dict) else None
    if not isinstance(density, dict):
        errors.append("carveout:calc-chrome.json has no density block")
        return
    if density.get("status") != "specified":
        errors.append("carveout:calc-chrome density status must stay 'specified'")
    for metric in density.get("metrics", []) or []:
        if not isinstance(metric, dict):
            continue
        name = metric.get("name")
        if not isinstance(name, str):
            continue
        if name not in doc_rows:
            errors.append(f"carveout:{name} has no matching section-6 row to anchor to")
            continue
        doc_compact, doc_comfortable = doc_rows[name]
        # Section 6 carries a px suffix; the calc carve-out stores the bare integer.
        if metric.get("compact") != doc_compact.replace("px", ""):
            errors.append(
                f"carveout:{name}:compact {metric.get('compact')!r} drifted from section 6 "
                f"({doc_compact!r})"
            )
        if metric.get("comfortable") != doc_comfortable.replace("px", ""):
            errors.append(
                f"carveout:{name}:comfortable {metric.get('comfortable')!r} drifted from "
                f"section 6 ({doc_comfortable!r})"
            )


# --------------------------------------------------------------------------------------------------
# reader-test corroboration
# --------------------------------------------------------------------------------------------------
def _validate_reader_test(
    registry: Mapping[str, Any], contents: Mapping[str, str], errors: list[str]
) -> None:
    marker = registry.get("reader_test_fixture")
    if not isinstance(marker, str):
        return
    source = contents.get(READER_TEST_PATH)
    if source is None:
        errors.append(f"reader_test:{READER_TEST_PATH} missing")
    elif marker not in source:
        errors.append(
            f"reader_test:the invalid-metrics-attribute fixture {marker!r} is no longer "
            f"exercised by {READER_TEST_PATH}"
        )


# --------------------------------------------------------------------------------------------------
# selector-absence guard (Git-tracked walk)
# --------------------------------------------------------------------------------------------------
def _git_grep(repo_root: Path, pattern: str, globs: Sequence[str]) -> tuple[int, list[str], str]:
    command = ["git", "-C", str(repo_root), "grep", "-l", "-I", "-E", pattern, "--", *globs]
    try:
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except OSError as error:
        return -1, [], str(error)
    matches = [
        line for line in completed.stdout.decode("utf-8", errors="replace").splitlines() if line
    ]
    return completed.returncode, matches, completed.stderr.decode("utf-8", errors="replace").strip()


def _validate_selector_presence(
    registry: Mapping[str, Any], repo_root: Path, errors: list[str]
) -> None:
    presence = registry.get("selector_presence")
    if not isinstance(presence, dict):
        errors.append(
            "selector_presence:registry must carry a selector_presence object "
            "(density is now a stored-value-only selection, not absent)"
        )
        return

    checks = (
        (
            presence.get("ui_pattern", UI_SELECTOR_PATTERN),
            presence.get("ui_globs") or ["*.ui"],
            presence.get("ui_expected") or [],
            "the .ui density-selector widget",
        ),
        (
            presence.get("officecfg_pattern", CFG_SELECTOR_PATTERN),
            presence.get("officecfg_globs") or ["*.xcs", "*.xcu"],
            presence.get("officecfg_expected") or [],
            "the MaterialDensity officecfg property",
        ),
    )
    for pattern, globs, expected, label in checks:
        if not isinstance(pattern, str) or not pattern:
            errors.append(f"selector_presence:{label}:pattern must be a non-empty string")
            continue
        returncode, matches, stderr = _git_grep(repo_root, pattern, globs)
        if returncode == 1:
            errors.append(
                f"selector_presence:{label} is missing -- density is stored-value-only "
                "in Stage 1, so the selector must exist (did the stored selection regress?)"
            )
        elif returncode != 0:
            errors.append(
                f"selector_presence:could not run git grep for {label} "
                f"(returncode {returncode}: {stderr or 'unknown error'})"
            )
        else:
            for want in expected:
                if isinstance(want, str) and want not in matches:
                    errors.append(
                        f"selector_presence:{label}:expected {want!r} among the matches, "
                        f"found {sorted(matches)[:12]}"
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
    if registry.get("contract") != CONTRACT:
        errors.append(f"registry:contract:must be {CONTRACT}")
    if registry.get("platform") != "windows":
        errors.append("registry:platform:must be windows")
    if registry.get("definition_file") != DEFINITION_PATH:
        errors.append("registry:definition_file:unexpected path")
    if registry.get("theme_flag") != THEME_FLAG:
        errors.append(f"registry:theme_flag:must be {THEME_FLAG}")
    if registry.get("status") != "source-declared":
        errors.append("registry:status:must be source-declared")
    if not isinstance(registry.get("runtime_verified"), bool):
        errors.append("registry:runtime_verified:boolean required")
    elif registry["runtime_verified"]:
        errors.append("registry:runtime_verified:no runtime evidence exists; must be false")

    if registry.get("selectable_stage") != "stored-value-only":
        errors.append(
            "registry:selectable_stage:must be 'stored-value-only' "
            "(Stage 1 stores the density selection; metric plumbing is Stage 3)"
        )

    _validate_native_metrics(registry, contents, errors)
    _validate_target_table(registry, contents, errors)
    _validate_design_honesty(registry, contents, errors)
    _validate_carveout_consistency(registry, contents, errors)
    _validate_reader_test(registry, contents, errors)
    _validate_selector_presence(registry, repo_root, errors)

    return errors


def validate_repository(repo_root: Path = REPOSITORY) -> None:
    registry, contents = load_repository(repo_root)
    errors = violations(registry, contents, repo_root)
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
        print(f"Material density model contract failed:\n{error}", file=sys.stderr)
        return 1
    print(
        "Material density model contract passed: the 15 single-profile native metrics "
        "and their zero-attribute <metrics> element, the section-6 target table, the "
        "MATERIAL_DESIGN honesty language, the calc-chrome carve-out consistency, and "
        "the stored-value-only density-selector-presence guard are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
