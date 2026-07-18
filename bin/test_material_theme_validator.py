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

    def assert_indicator_fails(self, definition: str, message: str) -> None:
        root = ET.fromstring(definition)
        with self.assertRaisesRegex(VALIDATOR.ValidationError, re.escape(message)):
            VALIDATOR.validate_indicator_states(root)

    def test_canonical_theme_and_native_sources_pass(self) -> None:
        self.assertEqual(
            VALIDATOR.validate(DEFINITION_PATH), (2, 23, 3, 8, 15, 72, 79, 205)
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
        VALIDATOR.validate_native_metric_source(
            (READER_HEADER_PATH, READER_SOURCE_PATH)
        )
        VALIDATOR.validate_native_indicator_source(
            (
                RENDERER_PATH,
                TYPOGRAPHY_SOURCE_PATH,
                REPOSITORY
                / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx",
            )
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
            'fill="@primary-container" stroke-width="@stroke-thin" '
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
        self.assertEqual(len(rects), 170)
        self.assertEqual(len(rounded), 159)
        self.assertEqual(len(square), 11)
        self.assertFalse(
            any("rx" in element.attrib or "ry" in element.attrib for element in root.iter())
        )
        self.assertEqual(
            Counter(element.get("radius", "")[1:] for element in rounded),
            Counter(
                {
                    "corner-checkbox": 12,
                    "corner-indicator": 19,
                    "corner-focus": 2,
                    "corner-small": 19,
                    "corner-control": 26,
                    "corner-container": 53,
                    "corner-toolbar": 9,
                    "corner-pill": 19,
                }
            ),
        )

        start = self.definition.index("    <shapes>")
        end = self.definition.index("    </shapes>", start) + len("    </shapes>")
        section = self.definition[start:end]
        moved = self.definition[:start] + self.definition[end:]
        moved = moved.replace("</widgets>", f"{section}\n\n</widgets>", 1)
        self.assertEqual(
            self.validate_definition(moved), (2, 23, 3, 8, 15, 72, 79, 205)
        )

    def test_metric_structure_is_strict(self) -> None:
        metric = '        <metric name="stroke-none" value="0"/>'
        missing_section = self.replace_once(
            "    <metrics>", "    <ignoredMetrics>"
        ).replace("    </metrics>", "    </ignoredMetrics>", 1)
        section_start = self.definition.index("    <metrics>")
        section_end = self.definition.index("    </metrics>", section_start) + len(
            "    </metrics>"
        )
        section = self.definition[section_start:section_end]
        cases = {
            "missing section": (
                missing_section,
                "expected exactly one <metrics> section, found 0",
            ),
            "duplicate section": (
                self.replace_once(
                    "    </metrics>", "    </metrics>\n\n    <metrics/>"
                ),
                "expected exactly one <metrics> section, found 2",
            ),
            "empty section": (
                self.definition.replace(section, "    <metrics/>", 1),
                "metrics section is empty",
            ),
            "section attribute": (
                self.replace_once("    <metrics>", '    <metrics mode="material">'),
                "metrics section must not have attributes",
            ),
            "section text": (
                self.replace_once("    <metrics>", "    <metrics>invalid"),
                "metrics section must not contain text",
            ),
            "processing instruction": (
                self.replace_once(
                    "    <metrics>", "    <metrics>\n        <?material metrics?>"
                ),
                "metrics section must not contain processing instructions",
            ),
            "unknown element": (
                self.replace_once(metric, "        <measure/>"),
                "metrics has unknown element <measure>",
            ),
            "missing name": (
                self.replace_once(metric, '        <metric value="0"/>'),
                "metric tokens require exactly name and value attributes",
            ),
            "missing value": (
                self.replace_once(metric, '        <metric name="stroke-none"/>'),
                "metric tokens require exactly name and value attributes",
            ),
            "extra attribute": (
                self.replace_once(
                    metric,
                    '        <metric name="stroke-none" value="0" mode="fixed"/>',
                ),
                "metric token has unknown attributes: mode",
            ),
            "invalid uppercase name": (
                self.replace_once(metric, metric.replace("stroke", "Stroke", 1)),
                "invalid metric token name 'Stroke-none'",
            ),
            "invalid underscore name": (
                self.replace_once(metric, metric.replace("stroke-", "stroke_", 1)),
                "invalid metric token name 'stroke_none'",
            ),
            "unknown name": (
                self.replace_once(
                    metric, metric.replace("stroke-none", "stroke-mystery")
                ),
                "unknown metric token 'stroke-mystery'",
            ),
            "duplicate token": (
                self.replace_once(metric, f"{metric}\n{metric}"),
                "duplicate metric token 'stroke-none'",
            ),
            "missing token": (
                self.replace_once(metric, ""),
                "missing metric tokens: stroke-none",
            ),
            "token text": (
                self.replace_once(
                    metric,
                    '        <metric name="stroke-none" value="0">invalid</metric>',
                ),
                "metric token 'stroke-none' must not have content",
            ),
            "nested element": (
                self.replace_once(
                    metric,
                    '        <metric name="stroke-none" value="0"><extra/></metric>',
                ),
                "metric token 'stroke-none' must not have content",
            ),
            "nested processing instruction": (
                self.replace_once(
                    metric,
                    '        <metric name="stroke-none" value="0">'
                    "<?material metric?></metric>",
                ),
                "metric token 'stroke-none' must not have content",
            ),
            "token tail": (
                self.replace_once(metric, metric + "invalid"),
                "metrics section must not contain text",
            ),
            "misplaced metric": (
                self.replace_once(
                    "    <settings>",
                    "    <settings>\n"
                    '        <metric name="outside" value="1"/>',
                ),
                "<metric> must appear only in the root <metrics> section",
            ),
            "nested metrics": (
                self.replace_once("    <settings>", "    <settings><metrics/>"),
                "<metrics> must appear only in the root <metrics> section",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_metric_values_are_bounded_canonical_and_exact(self) -> None:
        metric = '        <metric name="stroke-thin" value="1"/>'
        invalid_values = ("", "thin", "+1", "-1", "1.0", " 1", "01", "@stroke-none")
        for value in invalid_values:
            with self.subTest(value=value):
                definition = self.replace_once(
                    metric, metric.replace('value="1"', f'value="{value}"')
                )
                self.assert_definition_fails(
                    definition,
                    f"invalid metric value {value!r} for 'stroke-thin'",
                )

        overflow = self.replace_once(
            metric, metric.replace('value="1"', 'value="2147483648"')
        )
        self.assert_definition_fails(
            overflow, "metric value for 'stroke-thin' exceeds sal_Int32"
        )

        wrong_value = self.replace_once(
            metric, metric.replace('value="1"', 'value="2"')
        )
        self.assert_definition_fails(
            wrong_value, "metric token 'stroke-thin' must be 1, found 2"
        )

    def test_metric_references_are_strict_complete_and_family_safe(self) -> None:
        rounded = (
            '                <rect stroke="@primary-container" '
            'fill="@primary-container" stroke-width="@stroke-thin" '
            'radius="@corner-pill"/>'
        )
        radio_part = (
            "    <radiobutton>\n"
            '        <part value="Entire" width="@size-selection-control" '
            'height="@size-selection-control">'
        )
        list_margin = '        <listBoxEntryMargin value="@space-list-entry"/>'
        menu_indicator = (
            '        <part value="MenuItemCheckMark" '
            'width="@size-menu-indicator" height="@size-menu-indicator">'
        )
        track_line = (
            '<line stroke="@primary" stroke-width="@stroke-track" '
            'x1="0" y1="0.5" x2="1" y2="0.5"/>'
        )
        cases = {
            "literal stroke": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "1")
                ),
                "rect/@stroke-width must reference a metric token",
            ),
            "empty stroke": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "")
                ),
                "rect/@stroke-width must reference a metric token",
            ),
            "double marker": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@@stroke-thin")
                ),
                "rect/@stroke-width must reference a metric token",
            ),
            "uppercase reference": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@Stroke-thin")
                ),
                "rect/@stroke-width must reference a metric token",
            ),
            "reference whitespace": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@stroke-thin ")
                ),
                "rect/@stroke-width must reference a metric token",
            ),
            "unknown metric": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@stroke-mystery")
                ),
                "rect/@stroke-width references unknown metric token 'stroke-mystery'",
            ),
            "color token as metric": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@primary")
                ),
                "rect/@stroke-width references unknown metric token 'primary'",
            ),
            "shape token as metric": (
                self.replace_once(
                    rounded, rounded.replace("@stroke-thin", "@corner-pill")
                ),
                "rect/@stroke-width references unknown metric token 'corner-pill'",
            ),
            "metric token as color": (
                self.replace_once(
                    rounded,
                    rounded.replace('stroke="@primary-container"', 'stroke="@stroke-thin"'),
                ),
                "rect/@stroke references unknown token 'stroke-thin'",
            ),
            "metric token as radius": (
                self.replace_once(
                    rounded, rounded.replace("@corner-pill", "@stroke-thin")
                ),
                "rect/@radius references unknown shape token 'stroke-thin'",
            ),
            "literal part metric": (
                self.replace_once(
                    radio_part,
                    radio_part.replace('width="@size-selection-control"', 'width="24"'),
                ),
                "radiobutton/Entire/@width must reference a metric token",
            ),
            "wrong part metric": (
                self.replace_once(
                    radio_part,
                    radio_part.replace("@size-selection-control", "@size-compact-control", 1),
                ),
                "radiobutton/Entire/@width must reference @size-selection-control",
            ),
            "literal setting metric": (
                self.replace_once(
                    list_margin, '        <listBoxEntryMargin value="12"/>'
                ),
                "settings/listBoxEntryMargin/@value must reference a metric token",
            ),
            "wrong setting metric": (
                self.replace_once(
                    list_margin,
                    '        <listBoxEntryMargin value="@space-tab-inline"/>',
                ),
                "settings/listBoxEntryMargin/@value must reference @space-list-entry",
            ),
            "missing part slot": (
                self.replace_once(
                    radio_part,
                    "    <radiobutton>\n"
                    '        <part value="Entire" height="@size-selection-control">',
                ),
                "missing Material metric slot radiobutton/Entire/@width",
            ),
            "unexpected part slot": (
                self.replace_once(
                    radio_part,
                    radio_part[:-1] + ' margin-height="@space-tab-inline">',
                ),
                "unexpected Material metric slot radiobutton/Entire/@margin-height",
            ),
            "equal-valued role misuse": (
                self.replace_once(
                    menu_indicator,
                    menu_indicator.replace("@size-menu-indicator", "@size-list-preview", 1),
                ),
                "menupopup/MenuItemCheckMark/@width must reference @size-menu-indicator",
            ),
            "unknown token in non-target attribute": (
                self.replace_once(
                    radio_part,
                    radio_part[:-1] + ' orientation="@metric-mystery">',
                ),
                "part/@orientation must not reference a token",
            ),
            "unknown token in extra drawing attribute": (
                self.replace_once(
                    rounded,
                    rounded[:-2] + ' metric-value="@metric-mystery"/>',
                ),
                "rect/@metric-value must not reference a token",
            ),
            "line cannot use fill token": (
                self.replace_once(
                    track_line,
                    track_line[:-2] + ' fill="@primary"/>',
                ),
                "line/@fill must not reference a token",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

        vertical_line = (
            '<line stroke="@primary" stroke-width="@stroke-track" '
            'x1="0.5" y1="0" x2="0.5" y2="1"/>'
        )
        swapped = self.replace_once(track_line, "COORDINATE-SWAP")
        swapped = swapped.replace(vertical_line, track_line, 1)
        swapped = swapped.replace("COORDINATE-SWAP", vertical_line, 1)
        self.assert_definition_fails(
            swapped,
            "normalized coordinate geometry changed",
        )

        coordinate_metric = self.definition.replace(
            'stroke-width="@stroke-standard" x1="0.04"',
            'stroke-width="@stroke-standard" x1="@size-standard-control"',
            1,
        )
        self.assertNotEqual(coordinate_metric, self.definition)
        self.assert_definition_fails(
            coordinate_metric,
            "line/@x1 must remain a normalized numeric coordinate",
        )

    def test_normalized_coordinates_are_numeric_complete_and_bounded(self) -> None:
        line = (
            '<line stroke="@primary" stroke-width="@stroke-track" '
            'x1="0" y1="0.5" x2="1" y2="0.5"/>'
        )
        rect = (
            '                <rect stroke="@on-surface-variant" fill="@surface" '
            'stroke-width="@stroke-standard" radius="@corner-control" '
            'x1="0.08" y1="0.08" x2="0.92" y2="0.92"/>'
        )
        cases = {
            "not numeric": (
                self.replace_once(line, line.replace('x1="0"', 'x1="invalid"')),
                "line/@x1 must be a normalized numeric coordinate",
            ),
            "above one": (
                self.replace_once(line, line.replace('x1="0"', 'x1="1.5"')),
                "line/@x1 must be between 0 and 1",
            ),
            "below zero": (
                self.replace_once(line, line.replace('x1="0"', 'x1="-0.1"')),
                "line/@x1 must be between 0 and 1",
            ),
            "incomplete": (
                self.replace_once(line, line.replace(' y2="0.5"', "")),
                "line coordinate set is incomplete: missing y2",
            ),
            "inverted rectangle": (
                self.replace_once(rect, rect.replace('x1="0.08"', 'x1="0.95"')),
                "rect normalized coordinates must be ordered x1 <= x2 and y1 <= y2",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_definition_fails(definition, message)

    def test_canonical_metric_usage_preserves_geometry_and_order_independence(
        self,
    ) -> None:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_pis=True))
        root = ET.parse(DEFINITION_PATH, parser=parser).getroot()
        metrics = VALIDATOR.read_metrics(root)
        references, digest = VALIDATOR.validate_metric_usage(root, metrics)
        self.assertEqual(references, Counter(VALIDATOR.REQUIRED_METRIC_USAGE))
        self.assertEqual(sum(references.values()), 346)
        self.assertEqual(digest, VALIDATOR.METRIC_GEOMETRY_SHA256)
        self.assertFalse(
            any(
                element.get(attribute, "").startswith("@")
                for element in root.iter()
                if element.tag in {"rect", "line"}
                for attribute in ("x1", "y1", "x2", "y2")
            )
        )

        start = self.definition.index("    <metrics>")
        end = self.definition.index("    </metrics>", start) + len("    </metrics>")
        section = self.definition[start:end]
        moved = self.definition[:start] + self.definition[end:]
        moved = moved.replace("</widgets>", f"{section}\n\n</widgets>", 1)
        self.assertEqual(
            self.validate_definition(moved), (2, 23, 3, 8, 15, 72, 79, 205)
        )

        swapped = self.definition.replace(
            'stroke-width="@stroke-thin"', 'stroke-width="@metric-swap"', 1
        )
        swapped = swapped.replace(
            'stroke-width="@stroke-standard"', 'stroke-width="@stroke-thin"', 1
        )
        swapped = swapped.replace(
            'stroke-width="@metric-swap"', 'stroke-width="@stroke-standard"', 1
        )
        self.assert_definition_fails(
            swapped, "resolved Material metric geometry changed"
        )

        equal_value_swap = self.definition.replace(
            'value="@size-list-preview"', 'value="@metric-swap"', 1
        )
        equal_value_swap = equal_value_swap.replace(
            'width="@size-menu-indicator"', 'width="@size-list-preview"', 1
        )
        equal_value_swap = equal_value_swap.replace(
            'value="@metric-swap"', 'value="@size-menu-indicator"', 1
        )
        self.assert_definition_fails(
            equal_value_swap,
            "settings/listBoxPreviewDefaultLogicWidth/@value must reference @size-list-preview",
        )

    def test_progress_and_level_indicator_anatomy_is_strict(self) -> None:
        VALIDATOR.validate_indicator_states(ET.fromstring(self.definition))

        progress_track_prefix = (
            "    <progress>\n"
            '        <part value="TrackHorzArea">\n'
            '            <state enabled="true"><rect stroke="@outline-variant" '
            'fill="@outline-variant" stroke-width="@stroke-none" '
            'radius="@corner-indicator"/></state>\n'
            '            <state enabled="false"><rect stroke="@disabled-container" '
            'fill="@disabled-container" stroke-width="@stroke-none" '
            'radius="@corner-indicator"/></state>\n'
            "        </part>\n"
        )
        level_track_prefix = progress_track_prefix.replace(
            "    <progress>", "    <levelbar>", 1
        )
        critical = (
            '            <state enabled="true" extra="critical"><rect '
            'stroke="@error-container" fill="@error-container" '
            'stroke-width="@stroke-none" '
            'radius="@corner-indicator"/></state>'
        )
        high = (
            '            <state enabled="true" extra="high"><rect '
            'stroke="@primary" fill="@primary" stroke-width="@stroke-none" '
            'radius="@corner-indicator"/></state>'
        )
        disabled_track = (
            '            <state enabled="false"><rect '
            'stroke="@disabled-container" fill="@disabled-container" '
            'stroke-width="@stroke-none" '
            'radius="@corner-indicator"/></state>'
        )

        cases = {
            "missing progress track": (
                self.definition.replace(progress_track_prefix, "    <progress>\n", 1),
                "missing progress/TrackHorzArea",
            ),
            "missing level track": (
                self.definition.replace(level_track_prefix, "    <levelbar>\n", 1),
                "missing levelbar/TrackHorzArea",
            ),
            "missing high band": (
                self.replace_once(high, ""),
                "levelbar/Entire must define exactly 5 states, found 4",
            ),
            "empty critical band": (
                self.replace_once(
                    critical,
                    '            <state enabled="true" extra="critical"/>',
                ),
                "levelbar/Entire critical state must contain exactly one rectangle",
            ),
            "unknown band": (
                self.replace_once('extra="critical"', 'extra="danger"'),
                "levelbar/Entire has unexpected state attributes",
            ),
            "wrong band anatomy": (
                self.replace_once(
                    critical, critical.replace('fill="@error-container"', 'fill="@primary"')
                ),
                "levelbar/Entire critical rectangle has the wrong Material anatomy",
            ),
            "empty disabled track": (
                self.definition.replace(
                    disabled_track, '            <state enabled="false"/>', 1
                ),
                "progress/TrackHorzArea disabled state must contain exactly one rectangle",
            ),
        }
        for name, (definition, message) in cases.items():
            with self.subTest(name=name):
                self.assert_indicator_fails(definition, message)

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

    def test_required_native_metric_patterns_cannot_hide_in_comments(self) -> None:
        comments = "\n".join(
            (
                "// bool readMetricTokens();",
                "// bool readMetricReference();",
                "// bool readMetricSetting();",
                "// bool readDrawingCoordinate();",
                '// aPaletteWalker.name() == "metrics";',
                "// readMetricReference(sStrokeWidth, rMetricTokens, nStrokeWidth);",
                "// readMetricReference(sWidth, rMetricTokens, nWidth);",
                "// readMetricReference(sHeight, rMetricTokens, nHeight);",
                "// readMetricReference(sMarginHeight, rMetricTokens, nMarginHeight);",
                "// readMetricReference(sMarginWidth, rMetricTokens, nMarginWidth);",
                '// readMetricSetting(aWalker.attribute("value"_ostr), aMetricTokens, value);',
                '// readDrawingCoordinate(rWalker.attribute("x1"_ostr), 0.0, x);',
                '// readDrawingCoordinate(rWalker.attribute("y1"_ostr), 0.0, y);',
                '// readDrawingCoordinate(rWalker.attribute("x2"_ostr), 1.0, x);',
                '// readDrawingCoordinate(rWalker.attribute("y2"_ostr), 1.0, y);',
                "// readDefinition(aWalker, definition, type, aRadiusTokens, aMetricTokens);",
                '// { "listBoxEntryMargin", &rWidgetDefinition.mpSettings->msListBoxEntryMargin },',
                '// { "titleHeight", &rWidgetDefinition.mpSettings->msTitleHeight },',
                '// { "floatTitleHeight", &rWidgetDefinition.mpSettings->msFloatTitleHeight },',
                '// { "listBoxPreviewDefaultLogicWidth", &rWidgetDefinition.mpSettings->msListBoxPreviewDefaultLogicWidth },',
                '// { "listBoxPreviewDefaultLogicHeight", &rWidgetDefinition.mpSettings->msListBoxPreviewDefaultLogicHeight },',
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "metric-source.cxx"
            source.write_text(comments, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native metric source is missing pattern",
            ):
                VALIDATOR.validate_native_metric_source((source,))

        reader_source = READER_SOURCE_PATH.read_text(encoding="utf-8")
        combined_source = (
            READER_HEADER_PATH.read_text(encoding="utf-8") + "\n" + reader_source
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "metric-source.cxx"
            source.write_text(
                'R"codex(' + combined_source + ')codex"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native metric source is missing pattern",
            ):
                VALIDATOR.validate_native_metric_source((source,))

        missing_call = reader_source.replace(
            "if (!readMetricTokens(aPaletteWalker, aTokens))",
            "if (aTokens.empty())",
            1,
        )
        self.assertNotEqual(missing_call, reader_source)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "metric-source.cxx"
            source.write_text(
                READER_HEADER_PATH.read_text(encoding="utf-8")
                + "\n"
                + missing_call,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native metric source is missing pattern",
            ):
                VALIDATOR.validate_native_metric_source((source,))

        missing_failure_propagation = reader_source.replace(
            "if (!readMetricTokens(aPaletteWalker, aTokens))\n"
            "                    m_bValid = false;",
            "readMetricTokens(aPaletteWalker, aTokens);",
            1,
        )
        self.assertNotEqual(missing_failure_propagation, reader_source)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "metric-source.cxx"
            source.write_text(
                READER_HEADER_PATH.read_text(encoding="utf-8")
                + "\n"
                + missing_failure_propagation,
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native metric source is missing pattern",
            ):
                VALIDATOR.validate_native_metric_source((source,))

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "metric-source.cxx"
            source.write_text(
                READER_HEADER_PATH.read_text(encoding="utf-8")
                + "\n"
                + READER_SOURCE_PATH.read_text(encoding="utf-8")
                + "\nsWidth.toInt32();\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native metric source contains direct consumer conversion 'sWidth'",
            ):
                VALIDATOR.validate_native_metric_source((source,))

    def test_required_native_indicator_patterns_cannot_hide_in_comments(self) -> None:
        comments = "\n".join(
            (
                "// tools::Long getLevelBarStateValue();",
                "// case ControlType::LevelBar:",
                '// sExtra = "critical"; sExtra = "low";',
                '// sExtra = "medium"; sExtra = "high";',
                "// ControlPart::TrackHorzArea;",
                "// if (nProgressWidth == 0) break;",
                "// testProgressAndLevelIndicatorTracks();",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "indicator-source.cxx"
            source.write_text(comments, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native indicator source is missing pattern",
            ):
                VALIDATOR.validate_native_indicator_source((source,))

        combined_source = "\n".join(
            (
                RENDERER_PATH.read_text(encoding="utf-8"),
                TYPOGRAPHY_SOURCE_PATH.read_text(encoding="utf-8"),
                (
                    REPOSITORY
                    / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx"
                ).read_text(encoding="utf-8"),
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "indicator-source.cxx"
            source.write_text(
                'R"codex(' + combined_source + ')codex"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native indicator source is missing pattern",
            ):
                VALIDATOR.validate_native_indicator_source((source,))

        renderer_source = RENDERER_PATH.read_text(encoding="utf-8")
        missing_legacy_compatibility = renderer_source.replace(
            "bOK = !pTrack", "bOK = pTrack &&", 1
        )
        self.assertNotEqual(missing_legacy_compatibility, renderer_source)
        with tempfile.TemporaryDirectory() as directory:
            renderer = Path(directory) / "renderer.cxx"
            renderer.write_text(missing_legacy_compatibility, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native indicator source is missing pattern",
            ):
                VALIDATOR.validate_native_indicator_source(
                    (
                        renderer,
                        TYPOGRAPHY_SOURCE_PATH,
                        REPOSITORY
                        / "vcl/qa/cppunit/widgetdraw/FileDefinitionWidgetDrawTest.cxx",
                    )
                )

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


    def test_container_frame_and_listnet_controls_are_required(self) -> None:
        root = ET.parse(DEFINITION_PATH).getroot()

        frame = root.find("frame")
        self.assertIsNotNone(frame, "definition is missing the <frame> control")
        frame_parts = {part.get("value") for part in frame.findall("part")}
        self.assertEqual(frame_parts, {"Border"})
        border = frame.find("part")
        rectangles = list(border.iter("rect"))
        self.assertEqual(len(rectangles), 1)
        self.assertEqual(
            rectangles[0].attrib,
            {
                "stroke": "@outline-variant",
                "fill": "@surface-container",
                "stroke-width": "@stroke-thin",
                "radius": "@corner-container",
            },
        )

        listnet = root.find("listnet")
        self.assertIsNotNone(listnet, "definition is missing the <listnet> control")
        listnet_parts = {part.get("value") for part in listnet.findall("part")}
        self.assertEqual(listnet_parts, {"Entire"})
        # The net-less Material tree relies on a supported-but-empty Entire
        # state: the renderer returns true and draws nothing so VCL suppresses
        # its own connector nets.
        entire = listnet.find("part")
        self.assertEqual(len(entire.findall("state")), 1)
        self.assertEqual(list(entire.find("state")), [])

        missing_border = self.replace_once(
            '<frame><part value="Border">', '<frame><part value="Entire">'
        )
        self.assert_definition_fails(missing_border, "frame missing parts: Border")

        without_listnet = self.replace_once(
            '    <listnet><part value="Entire"><state enabled="true"/></part></listnet>\n',
            "",
        )
        self.assert_definition_fails(without_listnet, "missing control listnet")

    def test_disabled_affordance_states_are_present_and_dimmed(self) -> None:
        root = ET.parse(DEFINITION_PATH).getroot()

        def part(control: str, value: str) -> ET.Element:
            element = root.find(control)
            self.assertIsNotNone(element, f"missing control {control}")
            for candidate in element.findall("part"):
                if candidate.get("value") == value:
                    return candidate
            self.fail(f"missing {control}/{value}")

        def state(part_element: ET.Element, **attributes: str) -> ET.Element:
            for candidate in part_element.findall("state"):
                if all(candidate.get(k) == v for k, v in attributes.items()) and all(
                    candidate.get(k) is None
                    for k in ("focused", "pressed", "rollover", "default")
                    if k not in attributes
                ):
                    return candidate
            self.fail(f"missing state {attributes!r}")

        # A disabled submenu-parent passes ControlState::NONE; the arrow must dim
        # rather than keep the enabled @on-surface-variant stroke.
        arrow = part("menupopup", "SubmenuArrow")
        self.assertEqual(len(arrow.findall("state")), 2)
        disabled_arrow = state(arrow, enabled="false")
        strokes = {line.get("stroke") for line in disabled_arrow.findall("line")}
        self.assertEqual(strokes, {"@outline"})

        # A disabled but checked toolbar button keeps a dimmed checked affordance
        # instead of collapsing to the plain disabled fill.
        toolbar_button = part("toolbar", "Button")
        disabled_checked = state(
            toolbar_button, enabled="false", **{"button-value": "true"}
        )
        rect = disabled_checked.find("rect")
        self.assertEqual(rect.get("stroke"), "@outline")
        self.assertEqual(rect.get("fill"), "@disabled-container")

        # A disabled tab control keeps the current page identifiable.
        for value in ("Entire", "MenuItem"):
            tab = part("tabitem", value)
            disabled_selected = state(tab, enabled="false", selected="true")
            rect = disabled_selected.find("rect")
            self.assertEqual(rect.get("stroke"), "@outline")
            self.assertEqual(rect.get("fill"), "@disabled-container")
            plain_disabled = state(tab, enabled="false")
            self.assertNotEqual(
                plain_disabled.find("rect").get("stroke"),
                disabled_selected.find("rect").get("stroke"),
                "disabled+selected tab must be distinct from plain disabled",
            )

    def test_required_native_container_patterns_cannot_hide_in_comments(self) -> None:
        commented_renderer = "\n".join(
            (
                "// case ControlType::Frame:",
                "// case ControlType::ListNet:",
                "// getDefinition(eType, ControlPart::Border)",
                "// rNativeBoundingRegion = rBoundingControlRegion;",
                "// rNativeContentRegion = rBoundingControlRegion;",
                "// rNativeContentRegion.AdjustLeft(2);",
                "// rNativeContentRegion.AdjustRight(-2);",
            )
        )
        real_reader = READER_SOURCE_PATH
        with tempfile.TemporaryDirectory() as directory:
            renderer = Path(directory) / "renderer.cxx"
            renderer.write_text(commented_renderer, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native container renderer is missing the inset Frame region case",
            ):
                VALIDATOR.validate_native_container_source(
                    (renderer,), (real_reader,)
                )

        commented_reader = "\n".join(
            (
                '// { "frame", ControlType::Frame },',
                '// { "listnet", ControlType::ListNet },',
                '// o3tl::equalsIgnoreAsciiCase(sPart, "Border")',
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            reader = Path(directory) / "reader.cxx"
            reader.write_text(commented_reader, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native container reader source is missing pattern",
            ):
                VALIDATOR.validate_native_container_source(
                    (RENDERER_PATH,), (reader,)
                )

        # The production sources must satisfy every required pattern.
        VALIDATOR.validate_native_container_source((RENDERER_PATH,), (real_reader,))

        # Dropping the frame's content inset must fail the check even though the
        # pre-existing drawNativeControl Frame dispatch still matches, so the
        # native content-region inset cannot silently regress.
        renderer_source = RENDERER_PATH.read_text(encoding="utf-8")
        without_inset = renderer_source.replace(
            "            rNativeContentRegion.AdjustLeft(2);\n", "", 1
        )
        self.assertNotEqual(without_inset, renderer_source)
        with tempfile.TemporaryDirectory() as directory:
            renderer = Path(directory) / "renderer.cxx"
            renderer.write_text(without_inset, encoding="utf-8")
            with self.assertRaisesRegex(
                VALIDATOR.ValidationError,
                "native container renderer is missing the inset Frame region case",
            ):
                VALIDATOR.validate_native_container_source(
                    (renderer,), (real_reader,)
                )


if __name__ == "__main__":
    unittest.main()
