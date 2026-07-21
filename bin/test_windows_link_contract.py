#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed regression tests for the Material link-contract validator.

Every mutation removes or weakens one real code marker of the WIN-ACT-005 link
interaction contract and asserts the checker rejects it, so the contract can
never silently rot into comment-only wiring.
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
VALIDATOR_PATH = REPOSITORY / "bin/check-windows-link-contract.py"
REGISTRY_PATH = REPOSITORY / "qa/windows-ui-contract/link-contract.json"

SPEC = importlib.util.spec_from_file_location("check_windows_link_contract", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class WindowsLinkContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        surfaces = cls.registry["surfaces"]
        cls.tracked_files = sorted(
            {
                cls.registry["definition"],
                surfaces["native_source"],
                surfaces["native_header"],
                surfaces["weld_source"],
            }
        )
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

    def mutated(self, rel: str, old: str, new: str) -> dict[str, str]:
        source = self.originals[rel]
        self.assertEqual(source.count(old), 1, f"expected exactly one {old!r} in {rel}")
        return {rel: source.replace(old, new, 1)}

    def registry_copy(self) -> dict:
        return copy.deepcopy(self.registry)

    def native(self) -> str:
        return self.registry["surfaces"]["native_source"]

    def header(self) -> str:
        return self.registry["surfaces"]["native_header"]

    def weld(self) -> str:
        return self.registry["surfaces"]["weld_source"]

    # -- production -------------------------------------------------------------------------------
    def test_production_contract_passes(self) -> None:
        VALIDATOR.validate(REPOSITORY, REGISTRY_PATH)

    # -- Material-active gate + high-contrast bypass ----------------------------------------------
    def test_rejects_non_material_theme_gate_weakened(self) -> None:
        files = self.mutated(self.native(), '!= "material"', '!= "mtrial"')
        self.assert_fails("reject any theme name other than material", files=files)

    def test_rejects_missing_high_contrast_bypass(self) -> None:
        files = self.mutated(
            self.native(),
            "return !Application::GetSettings().GetStyleSettings().GetHighContrastMode();",
            "return Application::GetSettings().GetStyleSettings().GetHighContrastMode();",
        )
        self.assert_fails("bypass Material link styling in resolved high contrast", files=files)

    def test_rejects_comment_only_material_gate(self) -> None:
        # Commenting out the getenv gate must fail: comments are stripped first.
        files = self.mutated(
            self.native(),
            'std::getenv("VCL_FILE_WIDGET_THEME")',
            '/* std::getenv("VCL_FILE_WIDGET_THEME") */ nullptr',
        )
        self.assert_fails("gate on the VCL_FILE_WIDGET_THEME env activation", files=files)

    # -- token-driven focus ring ------------------------------------------------------------------
    def test_rejects_wrong_focus_ring_color_role(self) -> None:
        files = self.mutated(self.native(), 'findColor("primary")', 'findColor("secondary")')
        self.assert_fails("resolve the focus-ring color from the 'primary' token", files=files)

    def test_rejects_wrong_focus_ring_radius_token(self) -> None:
        files = self.mutated(
            self.native(), 'findRadius("corner-focus")', 'findRadius("corner-small")'
        )
        self.assert_fails(
            "resolve the focus-ring radius from the 'corner-focus' token", files=files
        )

    def test_rejects_non_rounded_focus_ring(self) -> None:
        files = self.mutated(
            self.native(),
            "rRenderContext.DrawRect(aRing, *oRadius, *oRadius);",
            "rRenderContext.DrawRect(aRing);",
        )
        self.assert_fails("draw a rounded focus ring using the token radius", files=files)

    def test_rejects_literal_focus_ring_radius(self) -> None:
        files = self.mutated(
            self.native(),
            "rRenderContext.DrawRect(aRing, *oRadius, *oRadius);",
            "rRenderContext.DrawRect(aRing, *oRadius, *oRadius);\n"
            "    rRenderContext.DrawRect(aRing, 6, 6);",
        )
        self.assert_fails("not hard-code a literal focus-ring corner radius", files=files)

    def test_rejects_empty_ring_body_with_decoy_markers(self) -> None:
        # Body-scoping guard (finding WIN-ACT-005 checker-robustness): the
        # token-driven ring markers are asserted against ImplDrawFocusRing's own
        # brace-matched body, not the flat source. Emptying the real function
        # Paint() calls while parking every marker in a never-called decoy must be
        # rejected -- before the markers were body-scoped this decoy passed while
        # painting nothing.
        native = self.native()
        source = self.originals[native]
        signature = re.compile(r"void\s+FixedHyperlink::ImplDrawFocusRing\s*\(")
        real_body = VALIDATOR._function_body(source, signature, "ring")
        decoy = (
            "\n\nvoid FixedHyperlink::ImplDrawFocusRingDecoy(vcl::RenderContext& rRenderContext)\n"
            "{\n"
            "    const std::optional<Color> oPrimary = lcl_materialTokens()->findColor(\"primary\");\n"
            "    const std::optional<sal_Int32> oRadius = lcl_materialTokens()->findRadius(\"corner-focus\");\n"
            "    rRenderContext.SetLineColor(*oPrimary);\n"
            "    rRenderContext.DrawRect(aRing, *oRadius, *oRadius);\n"
            "}\n"
        )
        mutated = source.replace(real_body, "{\n}", 1) + decoy
        self.assertNotEqual(mutated, source, "ring body mutation did not apply")
        self.assert_fails(
            "resolve the focus-ring color from the 'primary' token",
            files={native: mutated},
        )

    # -- ring gated on focus + enabled + Material -------------------------------------------------
    def test_rejects_ungated_focus_ring(self) -> None:
        files = self.mutated(
            self.native(),
            "if (HasFocus() && IsEnabled() && ImplUseMaterialLink())",
            "if (HasFocus())",
        )
        self.assert_fails("gate the ring on focus + enabled + Material-active", files=files)

    def test_rejects_getfocus_without_platform_suppression(self) -> None:
        files = self.mutated(
            self.native(),
            "if (ImplUseMaterialLink() && IsEnabled())",
            "if (false && IsEnabled())",
        )
        self.assert_fails("return before ShowFocus() when the Material ring applies", files=files)

    # -- disabled = @outline plain non-underlined non-focusable -----------------------------------
    def test_rejects_disabled_link_keeping_underline(self) -> None:
        files = self.mutated(
            self.native(),
            "aFont.SetUnderline(LINESTYLE_NONE);",
            "aFont.SetUnderline(LINESTYLE_SINGLE);",
        )
        self.assert_fails("drop the underline for a disabled link", files=files)

    def test_rejects_disabled_link_wrong_color(self) -> None:
        files = self.mutated(
            self.native(),
            "rStyleSettings.GetDeactiveTextColor()",
            "rStyleSettings.GetLinkColor()",
        )
        self.assert_fails("render a disabled link in deactiveTextColor (@outline)", files=files)

    def test_rejects_disabled_link_still_focusable(self) -> None:
        files = self.mutated(
            self.native(), "GetStyle() | WB_NOTABSTOP", "GetStyle()"
        )
        self.assert_fails("make a disabled link non-focusable", files=files)

    def test_rejects_enabled_link_not_refocusable(self) -> None:
        # Both the enabled branch and the Material-inactive revert clear
        # WB_NOTABSTOP; the checker only needs one clear in ImplUpdateLinkStyle,
        # so removing every clear proves it enforces re-focusability.
        native = self.native()
        source = self.originals[native]
        marker = "GetStyle() & ~WB_NOTABSTOP"
        self.assertGreaterEqual(source.count(marker), 1, f"expected {marker!r} in {native}")
        mutated = source.replace(marker, "GetStyle()")
        self.assert_fails("keep an enabled link focusable", files={native: mutated})

    # -- hover keeps underline, no color tint -----------------------------------------------------
    def test_rejects_hover_color_tint(self) -> None:
        files = self.mutated(
            self.native(),
            "SetPointer( PointerStyle::RefHand );",
            "SetPointer( PointerStyle::RefHand ); SetTextColor(COL_RED);",
        )
        self.assert_fails("not tint the link text on hover", files=files)

    # -- visited exposure across both surfaces ----------------------------------------------------
    def test_rejects_missing_visited_store(self) -> None:
        files = self.mutated(self.native(), "m_bVisited = bVisited", "m_bVisited = false")
        self.assert_fails("store the visited state", files=files)

    def test_rejects_single_activation_visit(self) -> None:
        files = self.mutated(
            self.native(),
            "            SetVisited(true);\n            m_aClickHdl.Call( *this );",
            "            m_aClickHdl.Call( *this );",
        )
        self.assert_fails("record a visit on both pointer and keyboard activation", files=files)

    def test_rejects_header_without_is_visited(self) -> None:
        files = self.mutated(
            self.header(),
            "    bool                IsVisited() const { return m_bVisited; }\n",
            "",
        )
        self.assert_fails("expose IsVisited()", files=files)

    def test_rejects_weld_without_visit(self) -> None:
        files = self.mutated(self.weld(), "rButton.SetVisited(true);\n", "")
        self.assert_fails(
            "record the visit on the underlying widget so the weld surface exposes it",
            files=files,
        )

    # -- token side (definition.xml) --------------------------------------------------------------
    def test_rejects_wrong_link_color_slot(self) -> None:
        files = self.mutated(
            self.registry["definition"],
            '<linkColor value="@primary"/>',
            '<linkColor value="@secondary"/>',
        )
        self.assert_fails("<style>/<linkColor> must be '@primary'", files=files)

    def test_rejects_wrong_corner_focus_radius(self) -> None:
        files = self.mutated(
            self.registry["definition"],
            '<radius name="corner-focus" value="6"/>',
            '<radius name="corner-focus" value="8"/>',
        )
        self.assert_fails("shape 'corner-focus' must be radius 6", files=files)

    # -- registry integrity -----------------------------------------------------------------------
    def test_rejects_missing_style_slots(self) -> None:
        registry = self.registry_copy()
        del registry["style_slots"]
        self.assert_fails("must define a 'style_slots' object", registry=registry)

    def test_rejects_non_integer_radius_value(self) -> None:
        registry = self.registry_copy()
        registry["focus_ring"]["radius_value"] = "6"
        self.assert_fails("focus_ring.radius_value must be an integer", registry=registry)

    def test_rejects_missing_weld_surface(self) -> None:
        registry = self.registry_copy()
        del registry["surfaces"]["weld_source"]
        self.assert_fails("surfaces.weld_source must name a source file", registry=registry)


if __name__ == "__main__":
    unittest.main()
