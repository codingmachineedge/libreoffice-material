#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the WIN-CONCEPT-003 component-gallery validator.

The checker (bin/check-component-gallery-coverage.py) generates a source-level
coverage ledger that maps every renderable Material part and declared state in the
canonical definition.xml to exactly one gallery cell, and pins the checked-in
ledger to that fresh enumeration. Each test here proves the contract fails closed
for one documented mutation while the production definition + ledger pass:

* ledger tampering -- a dropped cell, a phantom cell, a drifted state signature,
  and hand-edited counts / source_note / proposed_fixture / control-parts metadata
  each fail closed through ``compare_registry``;
* enumeration divergence -- when the checker's own walk and the reused
  ``check-material-theme`` walk disagree on the widget part/state totals the build
  aborts (checker lines 212-221), exercised both by a real definition.xml mutation
  (an extra nested ``<state>`` the recursive theme walk counts but the direct
  gallery walk does not) and by a stubbed theme module;
* the REQUIRED_PARTS guard -- any theme-required control/part that resolves to no
  gallery cell fails closed (checker lines 224-231); and
* determinism -- ``--regenerate`` produces byte-identical output across runs.

All writes go to a tempfile tree; the checked-in definition.xml and ledger are read
only and are asserted untouched by the regenerate test.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPOSITORY / "bin/check-component-gallery-coverage.py"
DEFINITION = REPOSITORY / "vcl/uiconfig/theme_definitions/material/definition.xml"
REGISTRY = REPOSITORY / "qa/windows-ui-contract/component-gallery-coverage.json"

SPEC = importlib.util.spec_from_file_location("check_component_gallery_coverage", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {CHECKER_PATH}")
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class _ThemeShim:
    """A stand-in theme module for driving the checker's cross-check branches.

    ``build_registry`` reads three attributes off the theme validator:
    ``validate`` (for the authoritative part/state counts), ``ValidationError``
    (for its except clause) and ``REQUIRED_PARTS`` (for the coverage guard). The
    real ``check-material-theme.validate`` re-derives REQUIRED_PARTS from its own
    module global, so it can never be made to pass while that global carries a
    bogus part. This shim delegates ``validate`` to the real, unpatched module --
    so the definition still passes the full theme contract -- while presenting an
    independently patched view of the counts and/or REQUIRED_PARTS to the checker.
    """

    def __init__(self, real, *, part_delta: int = 0, state_delta: int = 0, required=None) -> None:
        self._real = real
        self.ValidationError = real.ValidationError
        self.REQUIRED_PARTS = real.REQUIRED_PARTS if required is None else required
        self._part_delta = part_delta
        self._state_delta = state_delta

    def validate(self, path):
        result = list(self._real.validate(path))
        result[6] += self._part_delta
        result[7] += self._state_delta
        return tuple(result)


class ComponentGalleryCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The authoritative fresh enumeration of the production definition; every
        # ledger-tamper test mutates a deep copy of this and asserts rejection.
        cls.fresh = CHECKER.build_registry(DEFINITION)

    # -- scaffolding ------------------------------------------------------------------------------
    def real_theme(self):
        return CHECKER.load_theme_validator()

    def assert_ledger_rejected(self, message: str, mutate) -> None:
        """Write a tampered copy of the fresh ledger and assert the checker rejects it."""

        data = copy.deepcopy(self.fresh)
        mutate(data)
        self.assertNotEqual(data, self.fresh, "mutation must actually change the ledger")
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "ledger.json"
            registry_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(CHECKER.ValidationError, re.escape(message)):
                CHECKER.validate(DEFINITION, registry_path)

    def first_stateful_cell_id(self, data) -> str:
        return next(cell["cell_id"] for cell in data["cells"] if not cell["stateless"])

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        # The checked-in definition.xml + ledger must validate, and main() exit 0.
        expected = CHECKER.validate(DEFINITION, REGISTRY)
        self.assertEqual(expected["inventory_row"], "WIN-CONCEPT-003")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CHECKER.main([]), 0)

    def test_checked_in_ledger_is_a_fresh_enumeration(self) -> None:
        # Guards the whole suite: the on-disk ledger equals a fresh serialization.
        self.assertEqual(
            REGISTRY.read_text(encoding="utf-8"),
            CHECKER.serialize_registry(self.fresh),
        )

    # -- ledger tampering: cells ------------------------------------------------------------------
    def test_rejects_dropped_cell(self) -> None:
        def mutate(data):
            data["cells"] = data["cells"][1:]

        self.assert_ledger_rejected("cell entr(y/ies) missing from ledger", mutate)

    def test_rejects_phantom_cell(self) -> None:
        def mutate(data):
            data["cells"].append(
                {
                    "cell_id": "zzz-phantom/Entire/999",
                    "control": "zzz-phantom",
                    "part": "Entire",
                    "ordinal": 999,
                    "stateless": True,
                    "state": None,
                }
            )

        self.assert_ledger_rejected("ledger entr(y/ies) with no matching source", mutate)

    def test_rejects_drifted_state_signature(self) -> None:
        target = self.first_stateful_cell_id(self.fresh)

        def mutate(data):
            for cell in data["cells"]:
                if cell["cell_id"] == target:
                    cell["state"] = {"enabled": "tampered"}
                    return
            raise AssertionError("target cell vanished")

        self.assert_ledger_rejected(
            f"cell entry {target!r} drifted from its generated mapping", mutate
        )

    # -- ledger tampering: scalar / structured metadata -------------------------------------------
    def test_rejects_tampered_counts(self) -> None:
        def mutate(data):
            data["counts"]["cells"] = data["counts"]["cells"] + 1

        self.assert_ledger_rejected("ledger field 'counts' drifted", mutate)

    def test_rejects_tampered_source_note(self) -> None:
        def mutate(data):
            data["source_note"] = data["source_note"] + " tampered"

        self.assert_ledger_rejected("ledger field 'source_note' drifted", mutate)

    def test_rejects_tampered_proposed_fixture(self) -> None:
        def mutate(data):
            data["proposed_fixture"]["owner"] = "someone-else"

        self.assert_ledger_rejected("ledger field 'proposed_fixture' drifted", mutate)

    def test_rejects_tampered_controls_parts(self) -> None:
        def mutate(data):
            data["controls"][0]["parts"] = data["controls"][0]["parts"] + ["Phantom"]

        control_name = self.fresh["controls"][0]["control"]
        self.assert_ledger_rejected(
            f"control entry {control_name!r} drifted from its generated mapping", mutate
        )

    # -- enumeration divergence: real definition.xml mutation (checker lines 217-221) -------------
    def test_definition_mutation_diverges_state_count(self) -> None:
        # Nest an extra empty <state/> inside pushbutton/Entire's first state. The
        # theme walk (root.iter("state")) counts it; the gallery walk
        # (part.findall("state")) does not, so the two totals diverge and the build
        # aborts -- while the extra state is inert to the full theme contract, so
        # theme.validate still passes and we reach the checker's own cross-check.
        original = DEFINITION.read_text(encoding="utf-8")
        anchor = (
            '    <pushbutton>\n        <part value="Entire">\n'
            '            <state enabled="true">\n'
        )
        self.assertEqual(original.count(anchor), 1, "pushbutton anchor must be unique")
        injected = anchor.replace(
            '<state enabled="true">\n', '<state enabled="true"><state/>\n'
        )
        mutated = original.replace(anchor, injected, 1)
        with tempfile.TemporaryDirectory() as directory:
            definition_path = Path(directory) / "definition.xml"
            with definition_path.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(mutated)
            with self.assertRaisesRegex(
                CHECKER.ValidationError, "widget states but the theme contract counts"
            ):
                CHECKER.build_registry(definition_path)

    # -- enumeration divergence: stubbed theme walk (checker lines 212-221) -----------------------
    def test_rejects_theme_part_count_divergence(self) -> None:
        theme = _ThemeShim(self.real_theme(), part_delta=1)
        with self.assertRaisesRegex(
            CHECKER.ValidationError, "widget parts but the theme contract counts"
        ):
            CHECKER.build_registry(DEFINITION, theme_module=theme)

    def test_rejects_theme_state_count_divergence(self) -> None:
        theme = _ThemeShim(self.real_theme(), state_delta=-1)
        with self.assertRaisesRegex(
            CHECKER.ValidationError, "widget states but the theme contract counts"
        ):
            CHECKER.build_registry(DEFINITION, theme_module=theme)

    # -- REQUIRED_PARTS coverage guard (checker lines 224-231) ------------------------------------
    def test_rejects_required_part_without_gallery_cell(self) -> None:
        real = self.real_theme()
        required = {name: set(parts) for name, parts in real.REQUIRED_PARTS.items()}
        required["pushbutton"].add("PhantomPart")
        theme = _ThemeShim(real, required=required)
        with self.assertRaisesRegex(
            CHECKER.ValidationError,
            re.escape("required control/part pushbutton/PhantomPart has no gallery cell"),
        ):
            CHECKER.build_registry(DEFINITION, theme_module=theme)

    # -- determinism ------------------------------------------------------------------------------
    def test_regenerate_is_byte_deterministic(self) -> None:
        # Regenerate into two temp ledgers and assert byte-identical output, without
        # ever naming the checked-in ledger; assert that ledger is untouched too.
        before = REGISTRY.read_bytes()
        outputs = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(2):
                target = root / f"ledger-{index}.json"
                argv = [
                    "--regenerate",
                    "--definition",
                    str(DEFINITION),
                    "--registry",
                    str(target),
                ]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(CHECKER.main(argv), 0)
                outputs.append(target.read_bytes())
        self.assertEqual(outputs[0], outputs[1], "--regenerate must be deterministic")
        self.assertEqual(
            REGISTRY.read_bytes(), before, "regenerate test must not touch the checked-in ledger"
        )


if __name__ == "__main__":
    unittest.main()
