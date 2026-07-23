#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Base Add Table/Query tree validator.

Every pinned wiring fact in ``qa/windows-ui-contract/base-addtable-tree.json`` is
mutation-tested: the production tree passes, and each definition-part attribute,
the hierarchical model binding, the absence of a ``show-expanders`` override, the
flat-contrast list, the ``.ui``-to-native wiring, the plain TreeListBox wrapper,
the shared controller path and the carve-out invariant all fail closed when
weakened (including comment-only wiring and an injected owner-draw override).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-base-addtable-tree-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/base-addtable-tree.json"

SPEC = importlib.util.spec_from_file_location(
    "check_windows_base_addtable_tree_contract", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class BaseAddTableTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        tracked: set[str] = {cls.registry["definition_file"], cls.registry["tree_view"]["ui"]}
        for marker in cls.registry["markers"]:
            tracked.add(marker["source"])
        cls.tracked_files = sorted(tracked)
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

    def run_validate(self, *, files: dict[str, str] | None = None, registry: dict | None = None) -> None:
        files = files or {}
        registry_data = registry if registry is not None else self.registry
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in self.tracked_files:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(files.get(rel, self.originals[rel]), encoding="utf-8")
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
            VALIDATOR.validate(root, registry_path)

    def assert_fails(self, message: str, **kwargs) -> None:
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            self.run_validate(**kwargs)

    def mutated(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- production ---------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- definition parts ---------------------------------------------------------------------
    def test_rejects_listnode_size_attr_drift(self) -> None:
        registry = self.registry_copy()
        registry["definition_parts"]["listnode"]["part_attrs"]["width"] = "@size-wrong"
        self.assert_fails("listnode/Entire width", registry=registry)

    def test_rejects_listnet_empty_state_removed(self) -> None:
        files = self.mutated(
            self.registry["definition_file"],
            '<listnet><part value="Entire"><state enabled="true"/></part></listnet>',
            '<listnet><part value="Entire"><state enabled="true"><rect/></state></part></listnet>',
        )
        self.assert_fails("listnet/Entire is missing the empty enabled=true state", files=files)

    def test_rejects_missing_metric_token(self) -> None:
        registry = self.registry_copy()
        registry["metric_tokens"].append("size-not-real")
        self.assert_fails("metric 'size-not-real' missing", registry=registry)

    # -- tree-view wiring ---------------------------------------------------------------------
    def test_rejects_tablelist_model_drift(self) -> None:
        files = self.mutated(
            self.registry["tree_view"]["ui"],
            '<property name="model">liststore2</property>',
            '<property name="model">liststoreX</property>',
        )
        self.assert_fails("model is 'liststoreX', expected 'liststore2'", files=files)

    def test_rejects_show_expanders_added_to_tablelist(self) -> None:
        # Injecting a show-expanders override on the hierarchical tree would suppress
        # disclosure at the .ui level instead of leaving it to the native part.
        files = self.mutated(
            self.registry["tree_view"]["ui"],
            '<property name="model">liststore2</property>',
            '<property name="model">liststore2</property>\n'
            '                    <property name="show-expanders">False</property>',
        )
        self.assert_fails("must NOT carry the 'show-expanders' property", files=files)

    def test_rejects_hierarchical_store_downgraded(self) -> None:
        files = self.mutated(
            self.registry["tree_view"]["ui"],
            '<object class="GtkTreeStore" id="liststore2">',
            '<object class="GtkListStore" id="liststore2">',
        )
        self.assert_fails("store class is 'GtkListStore', expected 'GtkTreeStore'", files=files)

    def test_rejects_contrast_list_expanders_enabled(self) -> None:
        files = self.mutated(
            self.registry["tree_view"]["ui"],
            '<property name="show-expanders">False</property>',
            '<property name="show-expanders">True</property>',
        )
        self.assert_fails("must set show-expanders=False", files=files)

    # -- source wiring ------------------------------------------------------------------------
    def test_rejects_missing_dialog_binding(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/dlg/adtabdlg.cxx",
            "dbaccess/ui/tablesjoindialog.ui",
            "dbaccess/ui/somewhereelse.ui",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_injected_owner_draw(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/inc/dbtreelistbox.hxx",
            "weld::TreeView& GetWidget() { return *m_xTreeView; }",
            "weld::TreeView& GetWidget() { m_xTreeView->connect_custom_render(); return *m_xTreeView; }",
        )
        self.assert_fails("forbidden owner-draw/custom-render marker present", files=files)

    def test_comment_only_shared_path_fails_closed(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/querydesign/JoinController.cxx",
            "m_xAddTableDialog = std::make_shared<OAddTableDlg>",
            "// m_xAddTableDialog = std::make_shared<OAddTableDlg>",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_query_designer_not_deriving_join(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/inc/querycontroller.hxx",
            "class OQueryController  :public OJoinController",
            "class OQueryController  :public OSomethingElse",
        )
        self.assert_fails("missing marker in code", files=files)

    def test_rejects_relation_designer_not_deriving_join(self) -> None:
        files = self.mutated(
            "dbaccess/source/ui/inc/RelationController.hxx",
            "class ORelationController : public OJoinController",
            "class ORelationController : public OSomethingElse",
        )
        self.assert_fails("missing marker in code", files=files)

    # -- registry integrity -------------------------------------------------------------------
    def test_rejects_expected_marker_count_drift(self) -> None:
        registry = self.registry_copy()
        registry["expected_markers"] = len(registry["markers"]) - 1
        self.assert_fails("expected_markers count drift", registry=registry)

    def test_rejects_carve_out_status_flip(self) -> None:
        registry = self.registry_copy()
        registry["carve_out"]["status"] = "covered"
        self.assert_fails("carve_out status 'covered' must stay", registry=registry)

    def test_rejects_top_level_runtime_verified_true(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        self.assert_fails("registry runtime_verified must be false", registry=registry)


if __name__ == "__main__":
    unittest.main()
