#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Regression tests for the Material theme source validator."""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY / "bin/check-material-theme.py"
DEFINITION_PATH = (
    REPOSITORY / "vcl/uiconfig/theme_definitions/material/definition.xml"
)
RENDERER_PATH = REPOSITORY / "vcl/source/gdi/FileDefinitionWidgetDraw.cxx"
TYPOGRAPHY_SOURCE_PATH = REPOSITORY / "vcl/source/gdi/WidgetDefinition.cxx"
READER_HEADER_PATH = REPOSITORY / "vcl/inc/widgetdraw/WidgetDefinitionReader.hxx"
READER_SOURCE_PATH = REPOSITORY / "vcl/source/gdi/WidgetDefinitionReader.cxx"

SPEC = importlib.util.spec_from_file_location("check_material_theme", VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class MaterialThemeValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = DEFINITION_PATH.read_text(encoding="utf-8")

    def replace_once(self, old: str, new: str) -> str:
        self.assertEqual(
            self.definition.count(old),
            1,
            f"production definition no longer has one copy of {old!r}",
        )
        return self.definition.replace(old, new, 1)

    def assert_definition_fails(self, definition: str, message: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "definition.xml"
            path.write_text(definition, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError, re.escape(message)
            ):
                VALIDATOR.validate(path)

    def validate_definition(self, definition: str) -> tuple[int, ...]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "definition.xml"
            path.write_text(definition, encoding="utf-8")
            return VALIDATOR.validate(path)

    def test_canonical_theme_and_native_sources_pass(self) -> None:
        self.assertEqual(
            VALIDATOR.validate(DEFINITION_PATH), (2, 23, 3, 8, 72, 74, 190)
        )
        VALIDATOR.validate_native_typography_source(
            (RENDERER_PATH, TYPOGRAPHY_SOURCE_PATH)
        )
        VALIDATOR.validate_native_style_source(
            (
                REPOSITORY / "vcl/inc/widgetdraw/WidgetDefinition.hxx",
                REPOSITORY / "vcl/source/gdi/WidgetDefinitionReader.cxx",
                RENDERER_PATH,
                REPOSITORY / "include/vcl/settings.hxx",
                REPOSITORY / "vcl/source/app/settings.cxx",
                REPOSITORY
                / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx",
            )
        )
        VALIDATOR.validate_native_shape_source(
            (READER_HEADER_PATH, READER_SOURCE_PATH)
        )

    def test_style_structure_and_semantic_mapping_are_strict(self) -> None:
        face = '        <faceColor value="@surface-container"/>'
        missing_section = self.replace_once(
            "    <style>", "    <ignoredStyle>"
        ).replace("    </style>", "    </ignoredStyle>", 1)
        cases = {
            "missing section": (
                missing_section,
                "expected exactly one <style> section, found 0",
            ),
            "duplicate section": (
                self.replace_once(
                    "    </style>", "    </style>\n\n    <style/>"
                ),
                "expected exactly one <style> section, found 2",
            ),
            "section attribute": (
                self.replace_once("    <style>", '    <style mode="material">'),
                "style section must not have attributes",
            ),
            "section text": (
                self.replace_once("    <style>", "    <style>invalid"),
                "style section must not contain text",
            ),
            "unknown element": (
                self.replace_once(face, '        <mysteryColor value="@surface"/>'),
                "style has unknown element <mysteryColor>",
            ),
            "missing value": (
                self.replace_once(face, "        <faceColor/>"),
                "style <faceColor> requires exactly one value attribute",
            ),
            "extra attribute": (
                self.replace_once(
                    face,
                    '        <faceColor value="@surface-container" mode="fixed"/>',
                ),
                "style <faceColor> requires exactly one value attribute",
            ),
            "child text": (
                self.replace_once(
                    face,
                    '        <faceColor value="@surface-container">invalid</faceColor>',
                ),
                "style <faceColor> must not have content",
            ),
            "nested element": (
                self.replace_once(
                    face,
                    '        <faceColor value="@surface-container"><color/></faceColor>',
                ),
                "style <faceColor> must not have content",
            ),
            "nested processing instruction": (
                self.replace_once(
                    face,
                    '        <faceColor value="@surface-container">'
                    "<?material style?></faceColor>",
                ),
                "style <faceColor> must not have content",
            ),
            "direct processing instruction": (
                self.replace_once(
                    "    <style>", "    <style>\n        <?material style?>"
                ),
                "style has unknown element <",
            ),
            "child tail": (
                self.replace_once(face, face + "invalid"),
                "style section must not contain text",
            ),
            "duplicate element": (
                self.replace_once(face, f"{face}\n{face}"),
                "duplicate style element <faceColor>",
            ),
            "missing element": (
                self.replace_once(face, ""),
                "missing required style elements: faceColor",
            ),
            "wrong mapping": (
                self.replace_once(
                    face, '        <faceColor value="@surface"/>'
                ),
                "style <faceColor> must reference @surface-container",
            ),
            "literal value": (
                self.replace_once(face, '        <faceColor value="#FFFBFE"/>'),
                "style <faceColor> must reference @surface-container",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_shape_structure_is_strict(self) -> None:
        radius = '        <radius name="corner-checkbox" value="3"/>'
        missing_section = self.replace_once(
            "    <shapes>", "    <ignoredShapes>"
        ).replace("    </shapes>", "    </ignoredShapes>", 1)
        cases = {
            "missing section": (
                missing_section,
                "expected exactly one <shapes> section, found 0",
            ),
            "duplicate section": (
                self.replace_once("    </shapes>", "    </shapes>\n\n    <shapes/>"),
                "expected exactly one <shapes> section, found 2",
            ),
            "section attribute": (
                self.replace_once("    <shapes>", '    <shapes mode="material">'),
                "shapes section must not have attributes",
            ),
            "section text": (
                self.replace_once("    <shapes>", "    <shapes>invalid"),
                "shapes section must not contain text",
            ),
            "processing instruction": (
                self.replace_once(
                    "    <shapes>", "    <shapes>\n        <?material shapes?>"
                ),
                "shapes section must not contain processing instructions",
            ),
            "unknown element": (
                self.replace_once(radius, "        <curve/>"),
                "shapes has unknown element <curve>",
            ),
            "missing name": (
                self.replace_once(radius, '        <radius value="3"/>'),
                "shape radii require exactly name and value attributes",
            ),
            "missing value": (
                self.replace_once(
                    radius, '        <radius name="corner-checkbox"/>'
                ),
                "shape radii require exactly name and value attributes",
            ),
            "extra attribute": (
                self.replace_once(
                    radius,
                    '        <radius name="corner-checkbox" value="3" mode="fixed"/>',
                ),
                "shape radius has unknown attributes: mode",
            ),
            "invalid uppercase name": (
                self.replace_once(radius, radius.replace("corner", "Corner", 1)),
                "invalid shape token name 'Corner-checkbox'",
            ),
            "invalid underscore name": (
                self.replace_once(radius, radius.replace("corner-", "corner_", 1)),
                "invalid shape token name 'corner_checkbox'",
            ),
            "unknown name": (
                self.replace_once(
                    radius, radius.replace("corner-checkbox", "corner-mystery")
                ),
                "unknown shape token 'corner-mystery'",
            ),
            "duplicate token": (
                self.replace_once(radius, f"{radius}\n{radius}"),
                "duplicate shape token 'corner-checkbox'",
            ),
            "missing token": (
                self.replace_once(radius, ""),
                "missing shape tokens: corner-checkbox",
            ),
            "radius text": (
                self.replace_once(
                    radius,
                    '        <radius name="corner-checkbox" value="3">'
                    "invalid</radius>",
                ),
                "shape radius 'corner-checkbox' must not have content",
            ),
            "nested element": (
                self.replace_once(
                    radius,
                    '        <radius name="corner-checkbox" value="3">'
                    "<extra/></radius>",
                ),
                "shape radius 'corner-checkbox' must not have content",
            ),
            "nested processing instruction": (
                self.replace_once(
                    radius,
                    '        <radius name="corner-checkbox" value="3">'
                    "<?material radius?></radius>",
                ),
                "shape radius 'corner-checkbox' must not have content",
            ),
            "radius tail": (
                self.replace_once(radius, radius + "invalid"),
                "shapes section must not contain text",
            ),
            "misplaced radius": (
                self.replace_once(
                    "    <settings>",
                    "    <settings>\n"
                    '        <radius name="outside" value="1"/>',
                ),
                "<radius> must appear only in the root <shapes> section",
            ),
            "nested shapes": (
                self.replace_once("    <settings>", "    <settings><shapes/>"),
                "<shapes> must appear only in the root <shapes> section",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_shape_values_are_bounded_and_canonical(self) -> None:
        radius = '        <radius name="corner-checkbox" value="3"/>'
        invalid_values = ("round", "+3", "-1", "3.0", " 3", "03")
        for value in invalid_values:
            with self.subTest(value=value):
                definition = self.replace_once(
                    radius, radius.replace('value="3"', f'value="{value}"')
                )
                self.assert_definition_fails(
                    definition,
                    f"invalid shape radius {value!r} for 'corner-checkbox'",
                )

        above_limit = self.replace_once(
            radius, radius.replace('value="3"', 'value="65"')
        )
        self.assert_definition_fails(
            above_limit,
            "shape radius for 'corner-checkbox' must be between 0 and 64",
        )

        wrong_value = self.replace_once(
            radius, radius.replace('value="3"', 'value="4"')
        )
        self.assert_definition_fails(
            wrong_value,
            "shape token 'corner-checkbox' must be radius 3, found 4",
        )

    def test_shape_references_are_strict_and_complete(self) -> None:
        rounded = (
            '                <rect stroke="@primary-container" '
            'fill="@primary-container" stroke-width="1" '
            'radius="@corner-pill"/>'
        )
        cases = {
            "literal radius": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', "20")
                ),
                "rect/@radius must reference a shape token",
            ),
            "empty radius": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', "")
                ),
                "rect/@radius must reference a shape token",
            ),
            "double marker": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', '@@corner-pill')
                ),
                "rect/@radius must reference a shape token",
            ),
            "uppercase reference": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', '@Corner-pill')
                ),
                "rect/@radius must reference a shape token",
            ),
            "reference whitespace": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', '@corner-pill ')
                ),
                "rect/@radius must reference a shape token",
            ),
            "unknown shape reference": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', '@corner-mystery')
                ),
                "rect/@radius references unknown shape token 'corner-mystery'",
            ),
            "color token as radius": (
                self.replace_once(
                    rounded, rounded.replace('@corner-pill', '@primary')
                ),
                "rect/@radius references unknown shape token 'primary'",
            ),
            "legacy rx": (
                self.replace_once(
                    rounded, rounded.replace('radius="@corner-pill"', 'rx="20"')
                ),
                "rect must not use legacy rx or ry in Material definition",
            ),
            "legacy ry": (
                self.replace_once(
                    rounded, rounded.replace('radius="@corner-pill"', 'ry="20"')
                ),
                "rect must not use legacy rx or ry in Material definition",
            ),
            "legacy pair": (
                self.replace_once(
                    rounded,
                    rounded.replace(
                        'radius="@corner-pill"', 'rx="20" ry="20"'
                    ),
                ),
                "rect must not use legacy rx or ry in Material definition",
            ),
            "mixed singular and legacy": (
                self.replace_once(
                    rounded,
                    rounded.replace(
                        'radius="@corner-pill"',
                        'radius="@corner-pill" rx="20"',
                    ),
                ),
                "rect must not use legacy rx or ry in Material definition",
            ),
            "radius on non-rect": (
                self.replace_once(rounded, rounded.replace("<rect", "<line")),
                "line/@radius is only valid on <rect>",
            ),
            "shape token as color": (
                self.replace_once(
                    rounded,
                    rounded.replace(
                        'stroke="@primary-container"', 'stroke="@corner-pill"'
                    ),
                ),
                "rect/@stroke references unknown token 'corner-pill'",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

        self.assertEqual(self.definition.count("@corner-focus"), 2)
        unused = self.definition.replace("@corner-focus", "@corner-small")
        self.assert_definition_fails(unused, "unused shape tokens: corner-focus")

    def test_canonical_shape_usage_preserves_geometry_and_order_independence(
        self,
    ) -> None:
        root = ET.parse(DEFINITION_PATH).getroot()
        rects = list(root.iter("rect"))
        rounded = [element for element in rects if "radius" in element.attrib]
        square = [element for element in rects if "radius" not in element.attrib]
        self.assertEqual(len(rects), 157)
        self.assertEqual(len(rounded), 146)
        self.assertEqual(len(square), 11)
        self.assertFalse(
            any("rx" in element.attrib or "ry" in element.attrib for element in root.iter())
        )
        self.assertEqual(
            Counter(element.get("radius", "")[1:] for element in rounded),
            Counter(
                {
                    "corner-checkbox": 12,
                    "corner-indicator": 10,
                    "corner-focus": 2,
                    "corner-small": 19,
                    "corner-control": 26,
                    "corner-container": 51,
                    "corner-toolbar": 8,
                    "corner-pill": 18,
                }
            ),
        )

        start = self.definition.index("    <shapes>")
        end = self.definition.index("    </shapes>", start) + len("    </shapes>")
        section = self.definition[start:end]
        moved = self.definition[:start] + self.definition[end:]
        moved = moved.replace("</widgets>", f"{section}\n\n</widgets>", 1)
        self.assertEqual(
            self.validate_definition(moved), (2, 23, 3, 8, 72, 74, 190)
        )

    def test_feedback_tokens_are_scheme_specific_and_exact(self) -> None:
        expected = {
            ("light", "warning-container"): "#FFDDB3",
            ("light", "on-warning-container"): "#2A1800",
            ("light", "error-container"): "#F9DEDC",
            ("light", "on-error-container"): "#410E0B",
            ("dark", "warning-container"): "#5F4100",
            ("dark", "on-warning-container"): "#FFDDB3",
            ("dark", "error-container"): "#8C1D18",
            ("dark", "on-error-container"): "#F9DEDC",
        }
        for (scheme, name), color in expected.items():
            with self.subTest(scheme=scheme, token=name):
                line = f'        <color name="{name}" value="{color}"/>'
                definition = self.replace_once(
                    line, f'        <color name="{name}" value="#000000"/>'
                )
                self.assert_definition_fails(
                    definition,
                    f"{scheme} palette token {name!r} must be {color}, "
                    "found #000000",
                )

        light = '        <color name="warning-container" value="#FFDDB3"/>'
        dark = '        <color name="warning-container" value="#5F4100"/>'
        definition = self.definition.replace(light, "", 1).replace(dark, "", 1)
        self.assert_definition_fails(
            definition,
            "light palette is missing required feedback token 'warning-container'",
        )

    def test_list_selection_warning_and_error_contrast_is_enforced(self) -> None:
        cases = {
            "list": (
                self.replace_once(
                    '        <color name="on-surface" value="#1D1B20"/>',
                    '        <color name="on-surface" value="#FFFBFE"/>',
                ),
                "light listBoxWindowTextColor/listBoxWindowBackgroundColor "
                "contrast is only 1.00:1",
                None,
            ),
            "selection": (
                self.replace_once(
                    '        <color name="on-primary-container" value="#1D192B"/>',
                    '        <color name="on-primary-container" value="#E8DEF8"/>',
                ),
                "light listBoxWindowHighlightTextColor/"
                "listBoxWindowHighlightColor contrast is only 1.00:1",
                None,
            ),
            "warning": (
                self.replace_once(
                    '        <color name="on-warning-container" value="#2A1800"/>',
                    '        <color name="on-warning-container" value="#FFDDB3"/>',
                ),
                "light warningTextColor/warningColor contrast is only 1.00:1",
                ("on-warning-container", "#FFDDB3"),
            ),
            "error": (
                self.replace_once(
                    '        <color name="on-error-container" value="#410E0B"/>',
                    '        <color name="on-error-container" value="#F9DEDC"/>',
                ),
                "light errorTextColor/errorColor contrast is only 1.00:1",
                ("on-error-container", "#F9DEDC"),
            ),
        }
        for name, (definition, message, feedback_override) in cases.items():
            with self.subTest(name=name):
                feedback_colors = {
                    scheme: dict(colors)
                    for scheme, colors in VALIDATOR.REQUIRED_FEEDBACK_COLORS.items()
                }
                if feedback_override is not None:
                    token, color = feedback_override
                    feedback_colors["light"][token] = color
                with mock.patch.object(
                    VALIDATOR, "REQUIRED_FEEDBACK_COLORS", feedback_colors
                ):
                    self.assert_definition_fails(definition, message)

    def test_typography_structure_is_strict(self) -> None:
        body = '        <role name="body" scale="100" weight="preserve"/>'
        label = '        <role name="label" scale="100" weight="medium"/>'
        cases = {
            "duplicate role": (
                self.replace_once(body, f"{body}\n{body}"),
                "duplicate typography role 'body'",
            ),
            "duplicate section": (
                self.replace_once(
                    "    </typography>", "    </typography>\n\n    <typography/>"
                ),
                "expected exactly one <typography> section, found 2",
            ),
            "missing role": (
                self.replace_once(label, ""),
                "missing typography roles: label",
            ),
            "font family": (
                self.replace_once(body, body[:-2] + ' family="Inter"/>'),
                "typography role has unknown attributes: family",
            ),
            "unknown role": (
                self.replace_once('name="body"', 'name="caption"'),
                "unknown typography role 'caption'",
            ),
            "unknown element": (
                self.replace_once(body, "        <font/>"),
                "typography has unknown element <font>",
            ),
            "nested element": (
                self.replace_once(body, body[:-2] + "><font/></role>"),
                "typography role 'body' must not have content",
            ),
            "section text": (
                self.replace_once("    <typography>", "    <typography>invalid"),
                "typography section must not contain text",
            ),
            "role text": (
                self.replace_once(body, body[:-2] + ">invalid</role>"),
                "typography role 'body' must not have content",
            ),
            "role processing instruction": (
                self.replace_once(
                    body, body[:-2] + "><?material role?></role>"
                ),
                "typography role 'body' must not have content",
            ),
            "processing instruction": (
                self.replace_once(
                    "    <typography>",
                    "    <typography>\n        <?material typography?>",
                ),
                "typography has unknown element",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_typography_values_are_bounded_and_canonical(self) -> None:
        cases = {
            "below minimum": (
                self.replace_once('name="body" scale="100"', 'name="body" scale="099"'),
                "typography scale for 'body' must be between 100 and 200",
            ),
            "above maximum": (
                self.replace_once('name="body" scale="100"', 'name="body" scale="201"'),
                "typography scale for 'body' must be between 100 and 200",
            ),
            "bad weight": (
                self.replace_once('weight="preserve"', 'weight="heavy"'),
                "invalid typography weight 'heavy' for 'body'",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_palette_rejects_text_and_processing_instructions(self) -> None:
        color = '        <color name="primary" value="#6750A4"/>'
        cases = {
            "direct text": (
                self.replace_once("    <palette>", "    <palette>invalid"),
                "palette 'light' must not contain text",
            ),
            "color tail": (
                self.replace_once(color, color + "invalid"),
                "palette 'light' must not contain text",
            ),
            "processing instruction": (
                self.replace_once(
                    "    <palette>", "    <palette>\n        <?material palette?>"
                ),
                "palette 'light' has unknown element",
            ),
            "color extra attribute": (
                self.replace_once(
                    color,
                    '        <color name="primary" value="#6750A4" mode="fixed"/>',
                ),
                "palette 'light' <color> requires exactly name and value attributes",
            ),
            "nested color element": (
                self.replace_once(
                    color,
                    '        <color name="primary" value="#6750A4"><extra/></color>',
                ),
                "palette 'light' color 'primary' must not have content",
            ),
            "nested color processing instruction": (
                self.replace_once(
                    color,
                    '        <color name="primary" value="#6750A4">'
                    "<?material color?></color>",
                ),
                "palette 'light' color 'primary' must not have content",
            ),
            "root processing instruction": (
                self.replace_once("<widgets>", "<widgets>\n    <?material root?>"),
                "Material definition must not contain processing instructions",
            ),
            "settings processing instruction": (
                self.replace_once(
                    "    <settings>",
                    "    <settings>\n        <?material settings?>",
                ),
                "Material definition must not contain processing instructions",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_settings_section_is_unique_and_cannot_set_a_default_font(self) -> None:
        duplicate = self.replace_once(
            "    </settings>", "    </settings>\n\n    <settings/>"
        )
        self.assert_definition_fails(
            duplicate, "expected exactly one <settings> section, found 2"
        )

        default_font = self.replace_once(
            "    <settings>",
            '    <settings>\n        <defaultFontSize value="10"/>',
        )
        self.assert_definition_fails(
            default_font,
            "Material typography must not replace the native font with defaultFontSize",
        )

    def test_required_native_source_patterns_cannot_hide_in_comments(self) -> None:
        comments = "\n".join(
            (
                "// mpTypography->apply(aStyleSet, aNativeStyleSet);",
                "// moNativeStyle;",
                "// applyLegacyMinimumFontHeight(aStyleSet, aNativeStyleSet, 10);",
                "// WidgetDefinitionTypography::apply() {}",
                "// rTarget.SetAppFont();",
                "// rTarget.SetTitleFont();",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            renderer = Path(directory) / "renderer.cxx"
            typography = Path(directory) / "typography.cxx"
            renderer.write_text(comments, encoding="utf-8")
            typography.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native typography source is missing pattern",
            ):
                VALIDATOR.validate_native_typography_source((renderer, typography))

    def test_required_native_style_patterns_cannot_hide_in_comments(self) -> None:
        comments = "\n".join(
            (
                "// std::optional<Color> moAccentColor;",
                '// { "accentColor", &rWidgetDefinition.mpStyle->moAccentColor },',
                "// if (pDefinitionStyle->moAccentColor)",
                "//     aStyleSet.SetAccentColor(*pDefinitionStyle->moAccentColor);",
                "// StyleSettings::SetWarningTextColor(const Color&);",
                "// StyleSettings::SetErrorColor(const Color&);",
                "// StyleSettings::SetErrorTextColor(const Color&);",
                "// pGraphics->UpdateSettings(aSettings);",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "style-source.cxx"
            source.write_text(comments, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native style source is missing pattern",
            ):
                VALIDATOR.validate_native_style_source((source,))

    def test_required_native_shape_patterns_cannot_hide_in_comments(self) -> None:
        comments = "\n".join(
            (
                "// bool readShapeTokens();",
                "// bool readRadiusReference();",
                '// aPaletteWalker.name() == "shapes";',
                '// rWalker.attribute("radius"_ostr);',
                "// if (bHasRx || bHasRy) {}",
                "// nRx = nRy = nRadius;",
                "// readDefinition(aWalker, rWidgetDefinition, eType, aRadiusTokens);",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "shape-source.cxx"
            source.write_text(comments, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native shape source is missing pattern",
            ):
                VALIDATOR.validate_native_shape_source((source,))

    def test_native_source_guard_rejects_fixed_identity_setters(self) -> None:
        valid_source = "\n".join(
            (
                "mpTypography->apply(aStyleSet, aNativeStyleSet);",
                "moNativeStyle;",
                "applyLegacyMinimumFontHeight(aStyleSet, aNativeStyleSet, 10);",
                "WidgetDefinitionTypography::apply() {}",
                "rTarget.SetAppFont();",
                "rTarget.SetTitleFont();",
            )
        )
        forbidden_overrides = (
            ".SetIconFont(",
            ".SetFamilyName(",
            ".SetFamily(",
            ".SetStyleName(",
            ".SetCharSet(",
            ".SetLanguage(",
            ".SetPitch(",
            ".SetOrientation(",
            ".SetFontWidth(",
        )
        for forbidden in forbidden_overrides:
            with self.subTest(forbidden=forbidden):
                with tempfile.TemporaryDirectory() as directory:
                    renderer = Path(directory) / "renderer.cxx"
                    typography = Path(directory) / "typography.cxx"
                    renderer.write_text(
                        valid_source + f"\nrTarget{forbidden}value);\n",
                        encoding="utf-8",
                    )
                    typography.write_text("", encoding="utf-8")
                    with self.assertRaisesRegex(
                        VALIDATOR.ValidationError,
                        re.escape(
                            "native typography source contains forbidden override "
                            f"{forbidden!r}"
                        ),
                    ):
                        VALIDATOR.validate_native_typography_source(
                            (renderer, typography)
                        )


if __name__ == "__main__":
    unittest.main()
