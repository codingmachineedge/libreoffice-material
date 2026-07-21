#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the WIN-NAV-001 menu-composition validator.

Each test copies the real tracked files into a scratch tree, applies one surgical mutation that
weakens the menubar/drop-menu composition contract, and asserts the validator rejects it. Together
they prove the contract fails closed for the definition.xml token half, the settings/NWF guard
channel, and the real Menu::ImplCalcSize layout -- including that comment-only wiring is rejected.
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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-menu-composition.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/menu-composition.json"

SPEC = importlib.util.spec_from_file_location("check_windows_menu_composition", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class MenuCompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        files = {cls.registry["definition_xml"], VALIDATOR.SVDATA_HEADER}
        files.update(marker["file"] for marker in cls.registry["code_markers"])
        cls.tracked_files = sorted(files)
        cls.originals = {
            rel: (REPOSITORY / rel).read_text(encoding="utf-8") for rel in cls.tracked_files
        }

    # -- scaffolding ------------------------------------------------------------------------------
    def run_validate(
        self,
        *,
        files: dict[str, str] | None = None,
        registry: dict | None = None,
    ) -> None:
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

    def mutated(self, rel: str, old: str, new: str, *, count: int = 1) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), count, f"expected exactly {count} {old!r} in {rel}")
        return {rel: source.replace(old, new)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- definition.xml token half ----------------------------------------------------------------
    def test_rejects_missing_min_width_setting(self) -> None:
        files = self.mutated(
            self.registry["definition_xml"],
            '        <menuPopupMinWidth value="248"/>\n',
            "",
        )
        self.assert_fails("missing <menuPopupMinWidth>", files=files)

    def test_rejects_wrong_band_height_setting(self) -> None:
        files = self.mutated(
            self.registry["definition_xml"],
            '<menuBarHeight value="38"/>',
            '<menuBarHeight value="30"/>',
        )
        self.assert_fails("menu setting <menuBarHeight> must be 38", files=files)

    def test_rejects_wrong_indicator_metric(self) -> None:
        files = self.mutated(
            self.registry["definition_xml"],
            '<metric name="size-menu-indicator" value="18"/>',
            '<metric name="size-menu-indicator" value="16"/>',
        )
        self.assert_fails("size-menu-indicator", files=files)

    def test_rejects_enabled_disabled_submenu_arrow(self) -> None:
        # Milestone-10 dimmed disabled arrow: the enabled="false" state must stay @outline.
        files = self.mutated(
            self.registry["definition_xml"],
            '<state enabled="false"><line stroke="@outline" stroke-width="@stroke-standard" '
            'x1="0.4" y1="0.28" x2="0.62" y2="0.5"/><line stroke="@outline" '
            'stroke-width="@stroke-standard" x1="0.62" y1="0.5" x2="0.4" y2="0.72"/></state>',
            '<state enabled="false"><line stroke="@primary" stroke-width="@stroke-standard" '
            'x1="0.4" y1="0.28" x2="0.62" y2="0.5"/><line stroke="@primary" '
            'stroke-width="@stroke-standard" x1="0.62" y1="0.5" x2="0.4" y2="0.72"/></state>',
        )
        self.assert_fails("SubmenuArrow disabled indicator", files=files)

    def test_rejects_wrong_menubar_rollover_fill(self) -> None:
        files = self.mutated(
            self.registry["definition_xml"],
            '<state rollover="true"><rect stroke="@primary-container" fill="@primary-container" '
            'stroke-width="@stroke-none" radius="@corner-container"/></state>',
            '<state rollover="true"><rect stroke="@primary-container" fill="@surface" '
            'stroke-width="@stroke-none" radius="@corner-container"/></state>',
        )
        self.assert_fails("MenuItem state {'rollover': 'true'}", files=files)

    # -- NWF guard channel ------------------------------------------------------------------------
    def test_rejects_missing_nwf_field(self) -> None:
        files = self.mutated(
            VALIDATOR.SVDATA_HEADER,
            "int                     mnMenuPopupMinWidth = 0;"
            "        // Material drop-menu minimum width (0 = platform default)",
            "",
        )
        self.assert_fails("mnMenuPopupMinWidth", files=files)

    def test_rejects_missing_populate_from_setting(self) -> None:
        files = self.mutated(
            "vcl/source/gdi/FileDefinitionWidgetDraw.cxx",
            "rNWFData.mnMenuPopupMinWidth\n"
            "        = getSettingValueInteger(pSettings->msMenuPopupMinWidth, "
            "aBaseline.mnMenuPopupMinWidth);",
            "",
        )
        self.assert_fails("populate-minwidth", files=files)

    def test_rejects_missing_baseline_restore(self) -> None:
        # Removing the restore leaks the Material value into non-Material sessions: the guard must
        # stay reversible.
        files = self.mutated(
            "vcl/source/gdi/FileDefinitionWidgetDraw.cxx",
            "rNWFData.mnMenuBarHeight = aBaseline.mnMenuBarHeight;",
            "",
        )
        self.assert_fails("populate-baseline-restore", files=files)

    def test_rejects_missing_reader_setting_map_entry(self) -> None:
        files = self.mutated(
            "vcl/source/gdi/WidgetDefinitionReader.cxx",
            '        { "menuAccelColumnGap", '
            "&rWidgetDefinition.mpSettings->msMenuAccelColumnGap },\n",
            "",
        )
        self.assert_fails("reader-accelgap", files=files)

    # -- real layout half -------------------------------------------------------------------------
    def test_rejects_comment_only_min_width(self) -> None:
        # Commenting the layout out must fail: markers are matched against comment-stripped source.
        files = self.mutated(
            "vcl/source/window/menu.cxx",
            "aSz.setWidth( rMenuNWFData.mnMenuPopupMinWidth );",
            "// aSz.setWidth( rMenuNWFData.mnMenuPopupMinWidth );",
        )
        self.assert_fails("layout-minwidth", files=files)

    def test_rejects_missing_accel_gap_layout(self) -> None:
        files = self.mutated(
            "vcl/source/window/menu.cxx",
            "nAccWidth += (rMenuNWFData.mnMenuAccelColumnGap > 0)\n"
            "                                 ? rMenuNWFData.mnMenuAccelColumnGap\n"
            "                                 : nExtra;",
            "nAccWidth += nExtra;",
        )
        self.assert_fails("layout-accelgap", files=files)

    def test_rejects_missing_item_height_layout(self) -> None:
        files = self.mutated(
            "vcl/source/window/menu.cxx",
            "nMinMenuItemHeight = rMenuNWFData.mnMenuItemHeight;",
            "nMinMenuItemHeight = nMinMenuItemHeight;",
        )
        self.assert_fails("layout-itemheight", files=files)

    def test_rejects_disabled_arrow_state_plumbing_removed(self) -> None:
        # Drop the enabled guard on the submenu-arrow draw: the dimmed disabled arrow would never
        # render even though definition.xml declares it.
        files = self.mutated(
            "vcl/source/window/menu.cxx",
            "                        if (pData->bEnabled && m_pWindow->IsEnabled())\n"
            "                            nState |= ControlState::ENABLED;\n"
            "                        if (bHighlighted)\n"
            "                            nState |= ControlState::SELECTED;\n"
            "\n"
            "                        aTmpPos.setX( aOutSz.Width() - aTmpSz.Width()",
            "                        if (bHighlighted)\n"
            "                            nState |= ControlState::SELECTED;\n"
            "\n"
            "                        aTmpPos.setX( aOutSz.Width() - aTmpSz.Width()",
        )
        self.assert_fails("layout-disabled-arrow", files=files)

    def test_rejects_missing_accelerator_source(self) -> None:
        files = self.mutated(
            "framework/source/uielement/menubarmanager.cxx",
            "SetAcceleratorKeys(pMenu);",
            "/* accelerators removed */",
            count=2,
        )
        self.assert_fails("accel-source", files=files)

    def test_rejects_missing_padding_consumer(self) -> None:
        files = self.mutated(
            "vcl/source/window/menufloatingwindow.cxx",
            "ImplGetSVData()->maNWFData.mnMenuFormatBorderY;",
            "0;",
        )
        self.assert_fails("padding-consumer", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_missing_registry_key(self) -> None:
        registry = self.registry_copy()
        del registry["menu_settings"]
        self.assert_fails("missing required key 'menu_settings'", registry=registry)

    def test_rejects_duplicate_marker_id(self) -> None:
        registry = self.registry_copy()
        registry["code_markers"][1]["id"] = registry["code_markers"][0]["id"]
        self.assert_fails("duplicate code_marker id", registry=registry)


if __name__ == "__main__":
    unittest.main()
