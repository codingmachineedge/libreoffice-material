#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed mutation regressions for the Impress presenter surfaces contract (WIN-IM-004).

Each test breaks exactly one composition, wiring, or absence guarantee against an in-memory copy of
the tree and asserts the checker fails closed, while the pristine production tree passes. The real
repository is never mutated: every mutation is applied to the ``contents`` map ``load_repository``
returns or to a deep copy of the registry.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-impress-presenter-surfaces.py"
SPEC = importlib.util.spec_from_file_location(
    "check_windows_impress_presenter_surfaces", VALIDATOR_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)

COMPONENT = "sd/source/console/presenter.component"
CONSOLE_FILE = "sd/source/console/PresenterScreen.cxx"
ANIM_IMPL = "sd/source/ui/animations/CustomAnimationPane.cxx"
ANIM_UI = "sd/uiconfig/simpress/ui/customanimationspanel.ui"
TRANS_UI = "sd/uiconfig/simpress/ui/slidetransitionspanel.ui"


class ImpressPresenterSurfacesContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.contents = VALIDATOR.load_repository(REPOSITORY)

    # -- scaffolding -----------------------------------------------------------
    def failures(
        self, *, registry: dict | None = None, contents: dict[str, str] | None = None
    ) -> list[str]:
        return VALIDATOR.violations(
            self.registry if registry is None else registry,
            self.contents if contents is None else contents,
        )

    def with_content(self, path: str, text: str) -> dict[str, str]:
        contents = dict(self.contents)
        contents[path] = text
        return contents

    def replace_once(self, path: str, old: str, new: str) -> dict[str, str]:
        source = self.contents[path]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {path}")
        return self.with_content(path, source.replace(old, new, 1))

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- baseline --------------------------------------------------------------
    def test_production_contract(self) -> None:
        VALIDATOR.validate_repository(REPOSITORY)
        self.assertEqual([], self.failures())

    # -- presenter.component ---------------------------------------------------
    def test_component_implementation_renamed_fails(self) -> None:
        contents = self.replace_once(
            COMPONENT,
            'name="org.libreoffice.comp.PresenterScreenProtocolHandler"',
            'name="org.libreoffice.comp.PresenterScreenProtocolHandlerX"',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("component:implementation" in e for e in errors), errors)

    def test_component_service_removed_fails(self) -> None:
        contents = self.replace_once(
            COMPONENT,
            '<service name="com.sun.star.frame.ProtocolHandler"/>',
            "",
        )
        errors = self.failures(contents=contents)
        self.assertTrue(any("component:service" in e for e in errors), errors)

    def test_component_missing_fails(self) -> None:
        contents = dict(self.contents)
        contents.pop(COMPONENT, None)
        errors = self.failures(contents=contents)
        self.assertTrue(any("component:file missing" in e for e in errors), errors)

    # -- console absence marker ------------------------------------------------
    def test_console_gains_theme_hook_fails(self) -> None:
        source = self.contents[CONSOLE_FILE]
        contents = self.with_content(CONSOLE_FILE, source + "\nsal_Int32 x = VCL_FILE_WIDGET_THEME;\n")
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("console_absence" in e and "VCL_FILE_WIDGET_THEME" in e for e in errors), errors
        )

    def test_console_commented_theme_hook_passes(self) -> None:
        # A commented-out marker is stripped and must NOT satisfy or break the absence assertion.
        source = self.contents[CONSOLE_FILE]
        contents = self.with_content(CONSOLE_FILE, source + "\n// MaterialTokens placeholder\n")
        errors = self.failures(contents=contents)
        self.assertFalse(any("console_absence" in e for e in errors), errors)

    def test_console_directory_vanished_fails(self) -> None:
        registry = self.registry_copy()
        registry["console_absence"]["min_cxx_files"] = 9999
        errors = self.failures(registry=registry)
        self.assertTrue(any("console_absence:only" in e for e in errors), errors)

    # -- animation / transition PanelLayout decks ------------------------------
    def test_panel_layout_call_missing_fails(self) -> None:
        contents = self.replace_once(
            ANIM_IMPL,
            'PanelLayout(pParent, u"CustomAnimationsPanel"_ustr, u"modules/simpress/ui/customanimationspanel.ui"_ustr)',
            'PanelLayout(pParent, u"CustomAnimationsPanel"_ustr, u"modules/simpress/ui/customanimationspanelX.ui"_ustr)',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("panels[custom-animation]" in e and "PanelLayout call site missing" in e for e in errors),
            errors,
        )

    def test_content_widget_class_swap_fails(self) -> None:
        contents = self.replace_once(
            ANIM_UI,
            '<object class="GtkTreeView" id="effect_list">',
            '<object class="GtkIconView" id="effect_list">',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("panels[custom-animation]" in e and "content widget" in e for e in errors), errors
        )

    def test_root_object_id_renamed_fails(self) -> None:
        contents = self.replace_once(
            TRANS_UI, 'id="SlideTransitionsPanel">', 'id="SlideTransitionsPanelX">'
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("panels[slide-transition]" in e and "root object id" in e for e in errors), errors
        )

    def test_icon_view_item_width_drift_fails(self) -> None:
        contents = self.replace_once(
            TRANS_UI,
            '<property name="item-width">55</property>',
            '<property name="item-width">60</property>',
        )
        errors = self.failures(contents=contents)
        self.assertTrue(
            any("panels[slide-transition]" in e and "item-width" in e for e in errors), errors
        )

    # -- honest divergence flags -----------------------------------------------
    def test_divergence_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["divergences"]["transition_gallery"]["status"] = "implemented"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("divergences:transition_gallery:status must stay 'specified'" in e for e in errors),
            errors,
        )

    def test_catalog_gap_promotion_fails(self) -> None:
        registry = self.registry_copy()
        registry["divergences"]["catalog_gap"]["status"] = "resolved"
        errors = self.failures(registry=registry)
        self.assertTrue(
            any("divergences:catalog_gap:status must stay 'specified'" in e for e in errors), errors
        )

    # -- registry integrity ----------------------------------------------------
    def test_runtime_verified_true_fails(self) -> None:
        registry = self.registry_copy()
        registry["runtime_verified"] = True
        errors = self.failures(registry=registry)
        self.assertTrue(any("runtime_verified:no runtime evidence" in e for e in errors), errors)

    def test_contract_name_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["contract"] = "something-else"
        errors = self.failures(registry=registry)
        self.assertIn("registry:contract:unexpected value", errors)

    def test_inventory_row_drift_fails(self) -> None:
        registry = self.registry_copy()
        registry["inventory_row"] = "WIN-IM-000"
        errors = self.failures(registry=registry)
        self.assertIn("registry:inventory_row:must be WIN-IM-004", errors)


if __name__ == "__main__":
    unittest.main()
