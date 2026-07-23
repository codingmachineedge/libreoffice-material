#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the WIN-CONCEPT-001 Features-catalog validator.

The checker (bin/check-features-command-catalog.py) binds every row of
site/prototype-features.json to a real .uno registration in the officecfg
Office/UI/*Commands.xcu files and pins the checked-in ledger to a fresh
enumeration. Each test proves the contract fails closed for one documented
mutation while the production sources + ledger pass:

* row coverage -- a dropped or phantom catalog row fails through
  ``compare_registry``;
* identity uniqueness -- the two "Accent 1" rows keep distinct compound keys,
  and a duplicated catalog row fails ``build_registry`` closed;
* dispatch resolution -- removing the shared ``.uno:StyleApply`` node reclassifies
  the 13 base-cross-file calc rows (drift caught), and removing a LibreLogo node
  leaves its catalog row unresolved (build aborts);
* parse robustness -- the 9 ``install:module`` LibreLogo writer rows are counted
  (WriterCommands = 551 nodes), so a naive drop of them would fail the coverage;
* count pins -- the ``shared`` scope equals the GenericCommands node count, and
  hand-edited counts / scope bindings fail closed;
* render cap -- the ledger cap is cross-checked against
  docs/design/12-base-math-shared.md 12.3, and a drifted or missing anchor fails;
* closed value sets -- an unknown category or scope fails ``build_registry``; and
* determinism -- ``--regenerate`` produces byte-identical output across runs.

All writes go to a tempfile tree; the checked-in inputs and ledger are read only
and are asserted untouched by the regenerate test.
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
CHECKER_PATH = REPOSITORY / "bin/check-features-command-catalog.py"
REGISTRY = REPOSITORY / "qa/windows-ui-contract/features-command-catalog.json"

SPEC = importlib.util.spec_from_file_location("check_features_command_catalog", CHECKER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {CHECKER_PATH}")
CHECKER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)

CATALOG_REL = CHECKER.CATALOG_REL
DESIGN_REL = CHECKER.DESIGN_REL
UI_DIR_REL = CHECKER.UI_DIR_REL
REGISTRY_REL = "qa/windows-ui-contract/features-command-catalog.json"
OFFICECFG_RELS = [
    f"{UI_DIR_REL}/{basename}.xcu"
    for basename in sorted(set(CHECKER.MODULE_FILES.values()))
]
SOURCE_RELS = [CATALOG_REL, DESIGN_REL, *OFFICECFG_RELS]


class FeaturesCommandCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fresh = CHECKER.build_registry(REPOSITORY)
        cls.originals = {rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in SOURCE_RELS}
        cls.ledger = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.catalog = json.loads(cls.originals[CATALOG_REL])

    # -- scaffolding ------------------------------------------------------------------------------
    def materialize(
        self,
        root: Path,
        *,
        catalog: list | None = None,
        overrides: dict[str, str] | None = None,
        ledger: dict | None = None,
    ) -> None:
        overrides = overrides or {}
        for rel in SOURCE_RELS:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel == CATALOG_REL and catalog is not None:
                text = json.dumps(catalog, ensure_ascii=False)
            else:
                text = overrides.get(rel, self.originals[rel])
            target.write_text(text, encoding="utf-8")
        registry_target = root / REGISTRY_REL
        registry_target.parent.mkdir(parents=True, exist_ok=True)
        registry_data = self.ledger if ledger is None else ledger
        registry_target.write_text(json.dumps(registry_data, ensure_ascii=False), encoding="utf-8")

    def build_from(self, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.materialize(root, **kwargs)
            return CHECKER.build_registry(root)

    def validate_from(self, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.materialize(root, **kwargs)
            return CHECKER.validate(root, root / REGISTRY_REL)

    def assert_build_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(CHECKER.ValidationError, re.escape(message)):
            self.build_from(**kwargs)

    def assert_validate_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(CHECKER.ValidationError, re.escape(message)):
            self.validate_from(**kwargs)

    def one_override(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def catalog_copy(self) -> list:
        return copy.deepcopy(self.catalog)

    def ledger_copy(self) -> dict:
        return copy.deepcopy(self.ledger)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        expected = CHECKER.validate(REPOSITORY, REGISTRY)
        self.assertEqual(expected["inventory_row"], "WIN-CONCEPT-001")
        self.assertEqual(expected["counts"]["total"], 2433)
        self.assertEqual(expected["counts"]["unresolved"], 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CHECKER.main([]), 0)

    def test_checked_in_ledger_is_a_fresh_enumeration(self) -> None:
        self.assertEqual(
            REGISTRY.read_text(encoding="utf-8"),
            CHECKER.serialize_registry(self.fresh),
        )

    def test_resolution_class_counts_are_pinned(self) -> None:
        classes = self.fresh["counts"]["resolution_classes"]
        self.assertEqual(classes["exact-in-module"], 2366)
        self.assertEqual(classes["base-in-module"], 53)
        self.assertEqual(classes["base-cross-file"], 14)
        self.assertNotIn("exact-cross-file", classes)

    # -- M1 row coverage --------------------------------------------------------------------------
    def test_basic_dialog_row_binds_to_basicide(self) -> None:
        key = f".uno:NewDialog{CHECKER.IDENTITY_SEPARATOR}BASIC Dialog"
        entry = next(c for c in self.fresh["commands"] if c["identity_key"] == key)
        self.assertEqual(entry["resolution_class"], "exact-in-module")
        self.assertTrue(entry["resolving_file"].endswith("BasicIDECommands.xcu"))

    def test_rejects_dropped_catalog_row(self) -> None:
        catalog = self.catalog_copy()
        del catalog[0]
        self.assert_validate_fails("no matching source", catalog=catalog)

    def test_rejects_phantom_catalog_row(self) -> None:
        catalog = self.catalog_copy()
        catalog.append(["ZZZ Phantom Feature", "basic", "Command", ".uno:NewDialog"])
        self.assert_validate_fails("missing from ledger", catalog=catalog)

    # -- M2 identity uniqueness -------------------------------------------------------------------
    def test_accent1_collision_keeps_distinct_identity_keys(self) -> None:
        # Two rows share the display name "Accent 1" but different UNO commands;
        # the compound key must keep them distinct.
        keys = [c["identity_key"] for c in self.fresh["commands"] if c["name"] == "Accent 1"]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        self.assertIn(f".uno:Accent1CellStyles{CHECKER.IDENTITY_SEPARATOR}Accent 1", keys)

    def test_rejects_duplicated_identity(self) -> None:
        catalog = self.catalog_copy()
        catalog.append(list(catalog[0]))  # exact duplicate row -> duplicate identity
        self.assert_build_fails("duplicate selection identity", catalog=catalog)

    # -- M3 dispatch resolution -------------------------------------------------------------------
    def test_styleapply_backs_the_cross_file_calc_rows(self) -> None:
        cross = [c for c in self.fresh["commands"] if c["resolution_class"] == "base-cross-file"]
        styleapply = [c for c in cross if c["command"].startswith(".uno:StyleApply?")]
        self.assertEqual(len(styleapply), 13)
        for entry in styleapply:
            self.assertTrue(entry["resolving_file"].endswith("GenericCommands.xcu"))

    def test_removing_styleapply_node_reclassifies_and_fails_closed(self) -> None:
        # Removing the shared base node reclassifies the 13 calc rows to their
        # verbatim CalcCommands nodes -> the fresh build drifts from the ledger.
        overrides = self.one_override(
            f"{UI_DIR_REL}/GenericCommands.xcu",
            'oor:name=".uno:StyleApply"',
            'oor:name=".uno:StyleApplyXREMOVED"',
        )
        self.assert_validate_fails("drifted from its generated mapping", overrides=overrides)

    def test_removing_librelogo_node_leaves_row_unresolved(self) -> None:
        overrides = self.one_override(
            f"{UI_DIR_REL}/WriterCommands.xcu",
            'oor:name=".uno:LibreLogo-clearscreen"',
            'oor:name=".uno:LibreLogo-clearscreenXREMOVED"',
        )
        self.assert_build_fails("resolve to no officecfg node", overrides=overrides)

    # -- M4 parse robustness ----------------------------------------------------------------------
    def test_librelogo_nodes_are_collected(self) -> None:
        # The install:module LibreLogo nodes carry a script TargetURL and no Label;
        # a naive oor:op="replace">-terminated parser drops them (542 vs 551).
        nodes = CHECKER.collect_uno_nodes(REPOSITORY, "WriterCommands")
        self.assertEqual(len(nodes), 551)
        self.assertIn(".uno:LibreLogo-goforward", nodes)
        # All 9 LibreLogo catalog rows resolve (exact-in-module in WriterCommands).
        logo = [c for c in self.fresh["commands"] if "LibreLogo" in c["command"]]
        self.assertEqual(len(logo), 9)
        for entry in logo:
            self.assertEqual(entry["resolution_class"], "exact-in-module")

    # -- M5 count pins ----------------------------------------------------------------------------
    def test_shared_scope_equals_generic_node_count(self) -> None:
        generic = CHECKER.collect_uno_nodes(REPOSITORY, "GenericCommands")
        self.assertEqual(len(generic), 995)
        self.assertEqual(self.fresh["counts"]["per_scope"]["shared"], 995)

    def test_rejects_tampered_counts(self) -> None:
        ledger = self.ledger_copy()
        ledger["counts"]["total"] = ledger["counts"]["total"] + 1
        self.assert_validate_fails("ledger field 'counts' drifted", ledger=ledger)

    def test_rejects_drifted_command_entry(self) -> None:
        ledger = self.ledger_copy()
        ledger["commands"][0]["resolution_class"] = "base-cross-file"
        self.assert_validate_fails("drifted from its generated mapping", ledger=ledger)

    # -- M6 scope -> file binding -----------------------------------------------------------------
    def test_rejects_tampered_scope_binding(self) -> None:
        ledger = self.ledger_copy()
        ledger["scope_bindings"][1]["officecfg_file"] = "officecfg/wrong.xcu"
        self.assert_validate_fails("ledger field 'scope_bindings' drifted", ledger=ledger)

    # -- M7 render cap ----------------------------------------------------------------------------
    def test_rejects_render_cap_drift_in_design(self) -> None:
        overrides = self.one_override(
            DESIGN_REL, "render cap at **400** rows", "render cap at **399** rows"
        )
        self.assert_validate_fails("render cap drift", overrides=overrides)

    def test_rejects_missing_source_binding_subsection(self) -> None:
        overrides = self.one_override(
            DESIGN_REL, "### Source binding (normative)", "### Source binding removed"
        )
        self.assert_validate_fails("missing the 'Source binding (normative)' subsection", overrides=overrides)

    # -- M8 closed value sets ---------------------------------------------------------------------
    def test_rejects_unknown_category(self) -> None:
        catalog = self.catalog_copy()
        catalog[0][2] = "Bogus"
        self.assert_build_fails("unknown category", catalog=catalog)

    def test_rejects_unknown_scope(self) -> None:
        catalog = self.catalog_copy()
        catalog[0][1] = "nosuchmodule"
        self.assert_build_fails("unknown scope", catalog=catalog)

    def test_rejects_non_uno_command(self) -> None:
        catalog = self.catalog_copy()
        catalog[0][3] = "PlainString"
        self.assert_build_fails("is not a .uno command", catalog=catalog)

    # -- determinism ------------------------------------------------------------------------------
    def test_regenerate_is_byte_deterministic(self) -> None:
        before = REGISTRY.read_bytes()
        outputs = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(2):
                target = root / f"ledger-{index}.json"
                argv = ["--regenerate", "--registry", str(target)]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(CHECKER.main(argv), 0)
                outputs.append(target.read_bytes())
        self.assertEqual(outputs[0], outputs[1], "--regenerate must be deterministic")
        self.assertEqual(
            REGISTRY.read_bytes(), before, "regenerate test must not touch the checked-in ledger"
        )


if __name__ == "__main__":
    unittest.main()
