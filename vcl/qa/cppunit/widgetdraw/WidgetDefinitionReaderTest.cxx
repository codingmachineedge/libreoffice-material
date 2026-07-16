/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <string_view>

#include <cppunit/TestAssert.h>
#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/plugin/TestPlugIn.h>
#include <osl/file.hxx>
#include <unotest/bootstrapfixturebase.hxx>
#include <vcl/font.hxx>
#include <vcl/settings.hxx>

#include <widgetdraw/WidgetDefinitionReader.hxx>

namespace
{
constexpr OUStringLiteral gaDataUrl(u"/vcl/qa/cppunit/widgetdraw/data/");
constexpr OUStringLiteral gaMaterialThemeUrl(u"/vcl/uiconfig/theme_definitions/material/");

double linearColorComponent(sal_uInt8 nComponent)
{
    const double fComponent = static_cast<double>(nComponent) / 255.0;
    return fComponent <= 0.04045 ? fComponent / 12.92 : std::pow((fComponent + 0.055) / 1.055, 2.4);
}

double relativeLuminance(Color const& rColor)
{
    return 0.2126 * linearColorComponent(rColor.GetRed())
           + 0.7152 * linearColorComponent(rColor.GetGreen())
           + 0.0722 * linearColorComponent(rColor.GetBlue());
}

double contrastRatio(Color const& rFirst, Color const& rSecond)
{
    const double fFirst = relativeLuminance(rFirst);
    const double fSecond = relativeLuminance(rSecond);
    return (std::max(fFirst, fSecond) + 0.05) / (std::min(fFirst, fSecond) + 0.05);
}

class WidgetDefinitionReaderTest : public test::BootstrapFixtureBase
{
private:
    OUString getFullUrl(std::u16string_view sFileName)
    {
        return m_directories.getURLFromSrc(gaDataUrl) + sFileName;
    }

    OUString getMaterialThemeUrl(std::u16string_view sFileName)
    {
        return m_directories.getURLFromSrc(gaMaterialThemeUrl) + sFileName;
    }

public:
    void testRead();
    void testReadSettings();
    void testReadTypography();
    void testReadColorTokens();
    void testReadColorPalettes();
    void testReadShapeTokens();
    void testRejectInvalidDefinitions();
    void testReadMaterialTheme();

    CPPUNIT_TEST_SUITE(WidgetDefinitionReaderTest);
    CPPUNIT_TEST(testRead);
    CPPUNIT_TEST(testReadSettings);
    CPPUNIT_TEST(testReadTypography);
    CPPUNIT_TEST(testReadColorTokens);
    CPPUNIT_TEST(testReadColorPalettes);
    CPPUNIT_TEST(testReadShapeTokens);
    CPPUNIT_TEST(testRejectInvalidDefinitions);
    CPPUNIT_TEST(testReadMaterialTheme);
    CPPUNIT_TEST_SUITE_END();
};

void WidgetDefinitionReaderTest::testReadColorTokens()
{
    vcl::WidgetDefinition aDefinition;
    vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionColorTokens.xml"), getFullUrl(u""));
    CPPUNIT_ASSERT(aReader.read(aDefinition));
    CPPUNIT_ASSERT_EQUAL(u"abcdef"_ustr, aDefinition.mpStyle->maFaceColor.AsRGBHexString());

    auto pPushButton = aDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Entire);
    CPPUNIT_ASSERT(pPushButton);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0), pPushButton->mnWidth);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0), pPushButton->mnHeight);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0), pPushButton->mnMarginWidth);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0), pPushButton->mnMarginHeight);
    const auto aStates = pPushButton->getStates(ControlType::Pushbutton, ControlPart::Entire,
                                                ControlState::ENABLED, PushButtonValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aStates[0]->mpWidgetDrawActions.size());
    const auto& rRect
        = static_cast<const vcl::WidgetDrawActionRectangle&>(*aStates[0]->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"123456"_ustr, rRect.maStrokeColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"abcdef"_ustr, rRect.maFillColor.AsRGBHexString());
}

void WidgetDefinitionReaderTest::testReadShapeTokens()
{
    vcl::WidgetDefinition aDefinition;
    vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionShapeTokens.xml"), getFullUrl(u""));
    CPPUNIT_ASSERT(aReader.read(aDefinition));

    auto pPushButton = aDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Entire);
    CPPUNIT_ASSERT(pPushButton);
    const auto aStates = pPushButton->getStates(ControlType::Pushbutton, ControlPart::Entire,
                                                ControlState::ENABLED, PushButtonValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
    constexpr std::array<sal_Int32, 8> aExpectedRadii = { 3, 4, 6, 8, 10, 12, 18, 20 };
    CPPUNIT_ASSERT_EQUAL(aExpectedRadii.size(), aStates[0]->mpWidgetDrawActions.size());
    for (size_t i = 0; i < aExpectedRadii.size(); ++i)
    {
        CPPUNIT_ASSERT_EQUAL(vcl::WidgetDrawActionType::RECTANGLE,
                             aStates[0]->mpWidgetDrawActions[i]->maType);
        const auto& rRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
            *aStates[0]->mpWidgetDrawActions[i]);
        CPPUNIT_ASSERT_EQUAL(aExpectedRadii[i], rRect.mnRx);
        CPPUNIT_ASSERT_EQUAL(aExpectedRadii[i], rRect.mnRy);
    }
}

void WidgetDefinitionReaderTest::testReadColorPalettes()
{
    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionColorPalettes.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL(u"abcdef"_ustr, aDefinition.mpStyle->maFaceColor.AsRGBHexString());

        auto pSpinButton
            = aDefinition.getDefinition(ControlType::SpinButtons, ControlPart::ButtonUp);
        CPPUNIT_ASSERT(pSpinButton);
        const auto aStates = pSpinButton->getStates(ControlType::SpinButtons, ControlPart::ButtonUp,
                                                    ControlState::ENABLED, SpinbuttonValue());
        CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
        const auto& rRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
            *aStates[0]->mpWidgetDrawActions[0]);
        CPPUNIT_ASSERT_EQUAL(u"654321"_ustr, rRect.maFillColor.AsRGBHexString());
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionColorPalettes.xml"),
                                            getFullUrl(u""), "dark"_ostr);
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL(u"101010"_ustr, aDefinition.mpStyle->maFaceColor.AsRGBHexString());

        auto pSpinButton
            = aDefinition.getDefinition(ControlType::SpinButtons, ControlPart::ButtonUp);
        CPPUNIT_ASSERT(pSpinButton);
        const auto aStates = pSpinButton->getStates(ControlType::SpinButtons, ControlPart::ButtonUp,
                                                    ControlState::ENABLED, SpinbuttonValue());
        CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
        const auto& rRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
            *aStates[0]->mpWidgetDrawActions[0]);
        CPPUNIT_ASSERT_EQUAL(u"d0bcff"_ustr, rRect.maFillColor.AsRGBHexString());
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionColorPalettes.xml"),
                                            getFullUrl(u""), "unknown"_ostr);
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL(u"abcdef"_ustr, aDefinition.mpStyle->maFaceColor.AsRGBHexString());
    }
}

void WidgetDefinitionReaderTest::testRejectInvalidDefinitions()
{
    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionUnknownColorToken.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionDuplicateColorToken.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionUnknownPart.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionDuplicatePart.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionDuplicatePaletteScheme.xml"),
                                            getFullUrl(u""), "dark"_ostr);
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionInvalidUnselectedPalette.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionMismatchedPaletteTokens.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    constexpr std::array<std::u16string_view, 15> aInvalidTypographyDefinitions = {
        u"definitionDuplicateTypographyRole.xml",
        u"definitionDuplicateTypographySection.xml",
        u"definitionMissingTypographyRole.xml",
        u"definitionInvalidTypographyScale.xml",
        u"definitionInvalidTypographyWeight.xml",
        u"definitionUnknownTypographyRole.xml",
        u"definitionTypographyFamily.xml",
        u"definitionNestedTypography.xml",
        u"definitionMissingTypographyAttribute.xml",
        u"definitionTypographyText.xml",
        u"definitionTooLargeTypographyScale.xml",
        u"definitionTypographySectionAttribute.xml",
        u"definitionUnknownTypographyElement.xml",
        u"definitionTypographyRoleText.xml",
        u"definitionTypographyRoleProcessingInstruction.xml",
    };
    for (const auto aFileName : aInvalidTypographyDefinitions)
    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(aFileName), getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }

    constexpr std::array<std::u16string_view, 23> aInvalidShapeDefinitions = {
        u"definitionDuplicateShapesSection.xml",
        u"definitionDuplicateRadiusToken.xml",
        u"definitionEmptyShapes.xml",
        u"definitionShapesSectionAttribute.xml",
        u"definitionMissingRadiusName.xml",
        u"definitionMissingRadiusValue.xml",
        u"definitionExtraRadiusAttribute.xml",
        u"definitionInvalidRadiusName.xml",
        u"definitionInvalidRadiusValue.xml",
        u"definitionLeadingZeroRadiusValue.xml",
        u"definitionOverflowRadiusValue.xml",
        u"definitionAliasedRadiusValue.xml",
        u"definitionUnknownShapeElement.xml",
        u"definitionUnknownRadiusToken.xml",
        u"definitionEmptyRadiusReference.xml",
        u"definitionShapesText.xml",
        u"definitionShapesProcessingInstruction.xml",
        u"definitionRadiusTokenText.xml",
        u"definitionNestedRadiusToken.xml",
        u"definitionRadiusTokenProcessingInstruction.xml",
        u"definitionLiteralRadius.xml",
        u"definitionRadiusWithRx.xml",
        u"definitionRadiusWithRy.xml",
    };
    for (const auto aFileName : aInvalidShapeDefinitions)
    {
        const OUString aDefinitionUrl = getFullUrl(aFileName);
        osl::DirectoryItem aItem;
        CPPUNIT_ASSERT_EQUAL(osl::DirectoryItem::E_None,
                             osl::DirectoryItem::get(aDefinitionUrl, aItem));
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(aDefinitionUrl, getFullUrl(u""));
        CPPUNIT_ASSERT(!aReader.read(aDefinition));
    }
}

void WidgetDefinitionReaderTest::testReadTypography()
{
    vcl::WidgetDefinition aDefinition;
    vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionTypography.xml"), getFullUrl(u""));
    CPPUNIT_ASSERT(aReader.read(aDefinition));
    CPPUNIT_ASSERT(aDefinition.mpTypography);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(125), aDefinition.mpTypography->maBody.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maBody.meWeight
                   == vcl::WidgetDefinitionFontWeight::Normal);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(150), aDefinition.mpTypography->maLabel.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maLabel.meWeight
                   == vcl::WidgetDefinitionFontWeight::Bold);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(200), aDefinition.mpTypography->maTitle.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maTitle.meWeight
                   == vcl::WidgetDefinitionFontWeight::Medium);

    auto makeNativeFont = [](const OUString& rFamily, tools::Long nHeight)
    {
        vcl::Font aFont(rFamily, u"Native Style"_ustr, Size(7, nHeight));
        aFont.SetWeight(WEIGHT_LIGHT);
        aFont.SetPitch(PITCH_FIXED);
        aFont.SetCharSet(RTL_TEXTENCODING_UTF8);
        aFont.SetLanguage(LANGUAGE_JAPANESE);
        aFont.SetOrientation(Degree10(120));
        return aFont;
    };

    StyleSettings aNative;
    aNative.SetAppFont(makeNativeFont(u"Native App"_ustr, 24));
    aNative.SetHelpFont(makeNativeFont(u"Native Help"_ustr, 25));
    aNative.SetFieldFont(makeNativeFont(u"Native Field"_ustr, 26));
    aNative.SetMenuFont(makeNativeFont(u"Native Menu"_ustr, 27));
    aNative.SetToolFont(makeNativeFont(u"Native Tool"_ustr, 28));
    aNative.SetGroupFont(makeNativeFont(u"Native Group"_ustr, 29));
    aNative.SetLabelFont(makeNativeFont(u"Native Label"_ustr, 30));
    aNative.SetRadioCheckFont(makeNativeFont(u"Native Radio"_ustr, 31));
    aNative.SetPushButtonFont(makeNativeFont(u"Native Button"_ustr, 32));
    vcl::Font aNativeTabFont = makeNativeFont(u"Native Tab"_ustr, 33);
    aNativeTabFont.SetWeight(WEIGHT_BLACK);
    aNative.SetTabFont(aNativeTabFont);
    aNative.SetTitleFont(makeNativeFont(u"Native Title"_ustr, 35));
    aNative.SetFloatTitleFont(makeNativeFont(u"Native Float Title"_ustr, 36));

    auto applyRole = [](const vcl::Font& rNative, sal_Int32 nScale, FontWeight eWeight)
    {
        vcl::Font aFont(rNative);
        aFont.SetFontHeight((rNative.GetFontHeight() * nScale + 50) / 100);
        if (aFont.GetWeight() == WEIGHT_DONTKNOW || aFont.GetWeight() < eWeight)
            aFont.SetWeight(eWeight);
        return aFont;
    };

    StyleSettings aExpected(aNative);
    aExpected.SetAppFont(applyRole(aNative.GetAppFont(), 125, WEIGHT_NORMAL));
    aExpected.SetHelpFont(applyRole(aNative.GetHelpFont(), 125, WEIGHT_NORMAL));
    aExpected.SetFieldFont(applyRole(aNative.GetFieldFont(), 125, WEIGHT_NORMAL));
    aExpected.SetMenuFont(applyRole(aNative.GetMenuFont(), 150, WEIGHT_BOLD));
    aExpected.SetToolFont(applyRole(aNative.GetToolFont(), 150, WEIGHT_BOLD));
    aExpected.SetGroupFont(applyRole(aNative.GetGroupFont(), 150, WEIGHT_BOLD));
    aExpected.SetLabelFont(applyRole(aNative.GetLabelFont(), 150, WEIGHT_BOLD));
    aExpected.SetRadioCheckFont(applyRole(aNative.GetRadioCheckFont(), 150, WEIGHT_BOLD));
    aExpected.SetPushButtonFont(applyRole(aNative.GetPushButtonFont(), 150, WEIGHT_BOLD));
    aExpected.SetTabFont(applyRole(aNative.GetTabFont(), 150, WEIGHT_BOLD));
    aExpected.SetTitleFont(applyRole(aNative.GetTitleFont(), 200, WEIGHT_MEDIUM));
    aExpected.SetFloatTitleFont(applyRole(aNative.GetFloatTitleFont(), 200, WEIGHT_MEDIUM));

    StyleSettings aActual(aNative);
    aDefinition.mpTypography->apply(aActual, aNative);
    CPPUNIT_ASSERT(aExpected == aActual);
    CPPUNIT_ASSERT_EQUAL(u"Native App"_ustr, aActual.GetAppFont().GetFamilyName());
    CPPUNIT_ASSERT_EQUAL(u"Native Style"_ustr, aActual.GetAppFont().GetStyleName());
    CPPUNIT_ASSERT(aActual.GetAppFont().GetCharSet() == RTL_TEXTENCODING_UTF8);
    CPPUNIT_ASSERT(aActual.GetAppFont().GetLanguage() == LANGUAGE_JAPANESE);
    CPPUNIT_ASSERT(aActual.GetAppFont().GetPitch() == PITCH_FIXED);
    CPPUNIT_ASSERT(aActual.GetAppFont().GetOrientation() == Degree10(120));
    CPPUNIT_ASSERT_EQUAL(tools::Long(30), aActual.GetAppFont().GetFontHeight());
    CPPUNIT_ASSERT(aActual.GetAppFont().GetWeight() == WEIGHT_NORMAL);
    CPPUNIT_ASSERT_EQUAL(tools::Long(31), aActual.GetHelpFont().GetFontHeight());
    CPPUNIT_ASSERT_EQUAL(tools::Long(33), aActual.GetFieldFont().GetFontHeight());
    CPPUNIT_ASSERT_EQUAL(tools::Long(41), aActual.GetMenuFont().GetFontHeight());
    CPPUNIT_ASSERT(aActual.GetMenuFont().GetWeight() == WEIGHT_BOLD);
    CPPUNIT_ASSERT(aActual.GetTabFont().GetWeight() == WEIGHT_BLACK);
    CPPUNIT_ASSERT_EQUAL(u"Native Title"_ustr, aActual.GetTitleFont().GetFamilyName());
    CPPUNIT_ASSERT_EQUAL(tools::Long(70), aActual.GetTitleFont().GetFontHeight());
    CPPUNIT_ASSERT(aActual.GetTitleFont().GetWeight() == WEIGHT_MEDIUM);

    StyleSettings aAppliedTwice(aActual);
    aDefinition.mpTypography->apply(aAppliedTwice, aNative);
    CPPUNIT_ASSERT(aActual == aAppliedTwice);
}

void WidgetDefinitionReaderTest::testReadMaterialTheme()
{
    vcl::WidgetDefinition aDefinition;
    vcl::WidgetDefinitionReader aReader(getMaterialThemeUrl(u"definition.xml"),
                                        getMaterialThemeUrl(u""));
    CPPUNIT_ASSERT(aReader.read(aDefinition));

    CPPUNIT_ASSERT_EQUAL(u"fffbfe"_ustr, aDefinition.mpStyle->maWindowColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"1d1b20"_ustr, aDefinition.mpStyle->maWindowTextColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr, aDefinition.mpStyle->maHighlightColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"ffffff"_ustr,
                         aDefinition.mpStyle->maActionButtonTextColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"f4eff4"_ustr, aDefinition.mpStyle->maHelpTextColor.AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moAccentColor);
    CPPUNIT_ASSERT_EQUAL(u"6750a4"_ustr, aDefinition.mpStyle->moAccentColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moListBoxWindowBackgroundColor);
    CPPUNIT_ASSERT_EQUAL(u"fffbfe"_ustr,
                         aDefinition.mpStyle->moListBoxWindowBackgroundColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moListBoxWindowTextColor);
    CPPUNIT_ASSERT_EQUAL(u"1d1b20"_ustr,
                         aDefinition.mpStyle->moListBoxWindowTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moListBoxWindowHighlightColor);
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr,
                         aDefinition.mpStyle->moListBoxWindowHighlightColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moListBoxWindowHighlightTextColor);
    CPPUNIT_ASSERT_EQUAL(u"1d192b"_ustr,
                         aDefinition.mpStyle->moListBoxWindowHighlightTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moAlternatingRowColor);
    CPPUNIT_ASSERT_EQUAL(u"f7f2fa"_ustr,
                         aDefinition.mpStyle->moAlternatingRowColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moWarningColor);
    CPPUNIT_ASSERT_EQUAL(u"ffddb3"_ustr, aDefinition.mpStyle->moWarningColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moWarningTextColor);
    CPPUNIT_ASSERT_EQUAL(u"2a1800"_ustr, aDefinition.mpStyle->moWarningTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moErrorColor);
    CPPUNIT_ASSERT_EQUAL(u"f9dedc"_ustr, aDefinition.mpStyle->moErrorColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDefinition.mpStyle->moErrorTextColor);
    CPPUNIT_ASSERT_EQUAL(u"410e0b"_ustr, aDefinition.mpStyle->moErrorTextColor->AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL("12"_ostr, aDefinition.mpSettings->msListBoxEntryMargin);
    CPPUNIT_ASSERT(aDefinition.mpTypography);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(100), aDefinition.mpTypography->maBody.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maBody.meWeight
                   == vcl::WidgetDefinitionFontWeight::Preserve);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(100), aDefinition.mpTypography->maLabel.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maLabel.meWeight
                   == vcl::WidgetDefinitionFontWeight::Medium);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(120), aDefinition.mpTypography->maTitle.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maTitle.meWeight
                   == vcl::WidgetDefinitionFontWeight::SemiBold);

    auto makeMaterialNativeFont
        = [](const OUString& rFamily, tools::Long nHeight, FontWeight eWeight)
    {
        vcl::Font aFont(rFamily, u"Native Material Style"_ustr, Size(0, nHeight));
        aFont.SetWeight(eWeight);
        return aFont;
    };
    StyleSettings aNativeTypography;
    aNativeTypography.SetAppFont(
        makeMaterialNativeFont(u"Material Native Body"_ustr, 16, WEIGHT_BOLD));
    aNativeTypography.SetMenuFont(
        makeMaterialNativeFont(u"Material Native Label"_ustr, 17, WEIGHT_LIGHT));
    aNativeTypography.SetTabFont(
        makeMaterialNativeFont(u"Material Native Strong Label"_ustr, 18, WEIGHT_BLACK));
    aNativeTypography.SetTitleFont(
        makeMaterialNativeFont(u"Material Native Title"_ustr, 15, WEIGHT_LIGHT));
    aNativeTypography.SetFloatTitleFont(
        makeMaterialNativeFont(u"Material Native Strong Title"_ustr, 19, WEIGHT_BOLD));

    StyleSettings aAppliedTypography(aNativeTypography);
    aDefinition.mpTypography->apply(aAppliedTypography, aNativeTypography);
    CPPUNIT_ASSERT_EQUAL(u"Material Native Body"_ustr,
                         aAppliedTypography.GetAppFont().GetFamilyName());
    CPPUNIT_ASSERT_EQUAL(tools::Long(16), aAppliedTypography.GetAppFont().GetFontHeight());
    CPPUNIT_ASSERT(aAppliedTypography.GetAppFont().GetWeight() == WEIGHT_BOLD);
    CPPUNIT_ASSERT_EQUAL(tools::Long(17), aAppliedTypography.GetMenuFont().GetFontHeight());
    CPPUNIT_ASSERT(aAppliedTypography.GetMenuFont().GetWeight() == WEIGHT_MEDIUM);
    CPPUNIT_ASSERT(aAppliedTypography.GetTabFont().GetWeight() == WEIGHT_BLACK);
    CPPUNIT_ASSERT_EQUAL(u"Material Native Title"_ustr,
                         aAppliedTypography.GetTitleFont().GetFamilyName());
    CPPUNIT_ASSERT_EQUAL(tools::Long(18), aAppliedTypography.GetTitleFont().GetFontHeight());
    CPPUNIT_ASSERT(aAppliedTypography.GetTitleFont().GetWeight() == WEIGHT_SEMIBOLD);
    CPPUNIT_ASSERT_EQUAL(tools::Long(23), aAppliedTypography.GetFloatTitleFont().GetFontHeight());
    CPPUNIT_ASSERT(aAppliedTypography.GetFloatTitleFont().GetWeight() == WEIGHT_BOLD);
    CPPUNIT_ASSERT(
        contrastRatio(aDefinition.mpStyle->maWindowTextColor, aDefinition.mpStyle->maWindowColor)
        >= 4.5);
    CPPUNIT_ASSERT(
        contrastRatio(aDefinition.mpStyle->maFieldTextColor, aDefinition.mpStyle->maFieldColor)
        >= 4.5);
    CPPUNIT_ASSERT(
        contrastRatio(aDefinition.mpStyle->maMenuTextColor, aDefinition.mpStyle->maMenuColor)
        >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(aDefinition.mpStyle->maHighlightTextColor,
                                 aDefinition.mpStyle->maHighlightColor)
                   >= 4.5);
    CPPUNIT_ASSERT(
        contrastRatio(aDefinition.mpStyle->maHelpTextColor, aDefinition.mpStyle->maHelpColor)
        >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDefinition.mpStyle->moListBoxWindowTextColor,
                                 *aDefinition.mpStyle->moListBoxWindowBackgroundColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDefinition.mpStyle->moListBoxWindowHighlightTextColor,
                                 *aDefinition.mpStyle->moListBoxWindowHighlightColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDefinition.mpStyle->moWarningTextColor,
                                 *aDefinition.mpStyle->moWarningColor)
                   >= 4.5);
    CPPUNIT_ASSERT(
        contrastRatio(*aDefinition.mpStyle->moErrorTextColor, *aDefinition.mpStyle->moErrorColor)
        >= 4.5);

    auto pPushButton = aDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Entire);
    CPPUNIT_ASSERT(pPushButton);
    const auto aPushButtonStates = pPushButton->getStates(
        ControlType::Pushbutton, ControlPart::Entire, ControlState::ENABLED, PushButtonValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aPushButtonStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aPushButtonStates[0]->mpWidgetDrawActions.size());
    const auto& rButtonRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aPushButtonStates[0]->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(20), rButtonRect.mnRx);
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr, rButtonRect.maFillColor.AsRGBHexString());

    PushButtonValue aActionButtonValue;
    aActionButtonValue.mbIsAction = true;
    const auto aActionButtonStates = pPushButton->getStates(
        ControlType::Pushbutton, ControlPart::Entire, ControlState::ENABLED, aActionButtonValue);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aActionButtonStates.size());
    const auto& rActionButtonRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aActionButtonStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"6750a4"_ustr, rActionButtonRect.maFillColor.AsRGBHexString());
    CPPUNIT_ASSERT(
        contrastRatio(aDefinition.mpStyle->maActionButtonTextColor, rActionButtonRect.maFillColor)
        >= 4.5);

    PushButtonValue aFlatButtonValue;
    aFlatButtonValue.m_bFlatButton = true;
    const auto aFlatButtonStates = pPushButton->getStates(
        ControlType::Pushbutton, ControlPart::Entire, ControlState::ENABLED, aFlatButtonValue);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aFlatButtonStates.size());
    CPPUNIT_ASSERT(aFlatButtonStates.back()->mpWidgetDrawActions.empty());
    const auto aFlatButtonRolloverStates
        = pPushButton->getStates(ControlType::Pushbutton, ControlPart::Entire,
                                 ControlState::ENABLED | ControlState::ROLLOVER, aFlatButtonValue);
    CPPUNIT_ASSERT_EQUAL(size_t(4), aFlatButtonRolloverStates.size());
    const auto& rFlatButtonRolloverRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aFlatButtonRolloverStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr, rFlatButtonRolloverRect.maFillColor.AsRGBHexString());

    auto pPushButtonFocus = aDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Focus);
    CPPUNIT_ASSERT(pPushButtonFocus);
    const auto aPushButtonFocusStates = pPushButtonFocus->getStates(
        ControlType::Pushbutton, ControlPart::Focus, ControlState::FOCUSED, PushButtonValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aPushButtonFocusStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(4), aPushButtonFocusStates[0]->mpWidgetDrawActions.size());
    for (const auto& pAction : aPushButtonFocusStates[0]->mpWidgetDrawActions)
        CPPUNIT_ASSERT(pAction->maType == vcl::WidgetDrawActionType::LINE);

    auto pCheckbox = aDefinition.getDefinition(ControlType::Checkbox, ControlPart::Entire);
    CPPUNIT_ASSERT(pCheckbox);
    const auto aCheckedStates
        = pCheckbox->getStates(ControlType::Checkbox, ControlPart::Entire, ControlState::ENABLED,
                               ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aCheckedStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(3), aCheckedStates[0]->mpWidgetDrawActions.size());
    const auto aMixedStates
        = pCheckbox->getStates(ControlType::Checkbox, ControlPart::Entire, ControlState::ENABLED,
                               ImplControlValue(ButtonValue::Mixed));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aMixedStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(2), aMixedStates[0]->mpWidgetDrawActions.size());
    const auto aDisabledCheckedStates
        = pCheckbox->getStates(ControlType::Checkbox, ControlPart::Entire, ControlState::NONE,
                               ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDisabledCheckedStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(3), aDisabledCheckedStates[0]->mpWidgetDrawActions.size());

    auto pRadio = aDefinition.getDefinition(ControlType::Radiobutton, ControlPart::Entire);
    CPPUNIT_ASSERT(pRadio);
    const auto aSelectedRadioStates
        = pRadio->getStates(ControlType::Radiobutton, ControlPart::Entire, ControlState::ENABLED,
                            ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aSelectedRadioStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(2), aSelectedRadioStates[0]->mpWidgetDrawActions.size());
    const auto& rRadioDot = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aSelectedRadioStates[0]->mpWidgetDrawActions[1]);
    CPPUNIT_ASSERT_DOUBLES_EQUAL(0.33, rRadioDot.mfX1, 0.001);
    CPPUNIT_ASSERT_DOUBLES_EQUAL(0.67, rRadioDot.mfX2, 0.001);
    const auto aDisabledSelectedRadioStates
        = pRadio->getStates(ControlType::Radiobutton, ControlPart::Entire, ControlState::NONE,
                            ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDisabledSelectedRadioStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(2), aDisabledSelectedRadioStates[0]->mpWidgetDrawActions.size());

    auto pComboButton = aDefinition.getDefinition(ControlType::Combobox, ControlPart::ButtonDown);
    CPPUNIT_ASSERT(pComboButton);
    const auto aComboButtonStates = pComboButton->getStates(
        ControlType::Combobox, ControlPart::ButtonDown, ControlState::ENABLED, ImplControlValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aComboButtonStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(3), aComboButtonStates[0]->mpWidgetDrawActions.size());

    for (ControlPart ePart : { ControlPart::ButtonUp, ControlPart::ButtonDown,
                               ControlPart::ButtonLeft, ControlPart::ButtonRight })
    {
        auto pSpinButton = aDefinition.getDefinition(ControlType::SpinButtons, ePart);
        CPPUNIT_ASSERT(pSpinButton);
        CPPUNIT_ASSERT_EQUAL(sal_Int32(28), pSpinButton->mnWidth);
        CPPUNIT_ASSERT_EQUAL(sal_Int32(28), pSpinButton->mnHeight);

        for (ControlState eState :
             { ControlState::ENABLED, ControlState::ENABLED | ControlState::ROLLOVER,
               ControlState::ENABLED | ControlState::PRESSED, ControlState::NONE })
        {
            const auto aSpinButtonStates = pSpinButton->getStates(ControlType::SpinButtons, ePart,
                                                                  eState, SpinbuttonValue());
            CPPUNIT_ASSERT(!aSpinButtonStates.empty());
            CPPUNIT_ASSERT(!aSpinButtonStates.back()->mpWidgetDrawActions.empty());
        }
    }

    CPPUNIT_ASSERT(aDefinition.getDefinition(ControlType::EditboxNoBorder, ControlPart::Entire));
    CPPUNIT_ASSERT(aDefinition.getDefinition(ControlType::MultilineEditbox, ControlPart::Entire));
    CPPUNIT_ASSERT(aDefinition.getDefinition(ControlType::Listbox, ControlPart::ListboxWindow));

    auto pScrollbarEntire = aDefinition.getDefinition(ControlType::Scrollbar, ControlPart::Entire);
    CPPUNIT_ASSERT(pScrollbarEntire);
    const auto aScrollbarEntireStates = pScrollbarEntire->getStates(
        ControlType::Scrollbar, ControlPart::Entire, ControlState::ENABLED, ImplControlValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aScrollbarEntireStates.size());
    CPPUNIT_ASSERT(aScrollbarEntireStates[0]->mpWidgetDrawActions.empty());

    auto pDisabledSliderTrack
        = aDefinition.getDefinition(ControlType::Slider, ControlPart::TrackHorzLeft);
    CPPUNIT_ASSERT(pDisabledSliderTrack);
    const auto aDisabledSliderTrackStates = pDisabledSliderTrack->getStates(
        ControlType::Slider, ControlPart::TrackHorzLeft, ControlState::NONE, SliderValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDisabledSliderTrackStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDisabledSliderTrackStates[0]->mpWidgetDrawActions.size());

    auto pToolbarEntire = aDefinition.getDefinition(ControlType::Toolbar, ControlPart::Entire);
    CPPUNIT_ASSERT(pToolbarEntire);
    auto pToolbarButton = aDefinition.getDefinition(ControlType::Toolbar, ControlPart::Button);
    CPPUNIT_ASSERT(pToolbarButton);
    const auto aCheckedToolbarButtonStates
        = pToolbarButton->getStates(ControlType::Toolbar, ControlPart::Button,
                                    ControlState::ENABLED, ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(2), aCheckedToolbarButtonStates.size());
    const auto& rCheckedToolbarButtonRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aCheckedToolbarButtonStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr, rCheckedToolbarButtonRect.maFillColor.AsRGBHexString());
    const auto aCheckedPressedToolbarButtonStates = pToolbarButton->getStates(
        ControlType::Toolbar, ControlPart::Button, ControlState::ENABLED | ControlState::PRESSED,
        ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(4), aCheckedPressedToolbarButtonStates.size());
    const auto& rCheckedPressedToolbarButtonRect
        = static_cast<const vcl::WidgetDrawActionRectangle&>(
            *aCheckedPressedToolbarButtonStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"ccc2dc"_ustr,
                         rCheckedPressedToolbarButtonRect.maFillColor.AsRGBHexString());

    auto pListNode = aDefinition.getDefinition(ControlType::ListNode, ControlPart::Entire);
    CPPUNIT_ASSERT(pListNode);
    const auto aExpandedListNodeStates
        = pListNode->getStates(ControlType::ListNode, ControlPart::Entire, ControlState::ENABLED,
                               ImplControlValue(ButtonValue::On));
    CPPUNIT_ASSERT_EQUAL(size_t(2), aExpandedListNodeStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(2), aExpandedListNodeStates.back()->mpWidgetDrawActions.size());

    auto pTab = aDefinition.getDefinition(ControlType::TabItem, ControlPart::Entire);
    CPPUNIT_ASSERT(pTab);
    const TabitemValue aTabValue(tools::Rectangle(), TabBarPosition::Top);
    const auto aSelectedTabStates
        = pTab->getStates(ControlType::TabItem, ControlPart::Entire,
                          ControlState::ENABLED | ControlState::SELECTED, aTabValue);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aSelectedTabStates.size());
    const auto aSelectedRolloverTabStates = pTab->getStates(
        ControlType::TabItem, ControlPart::Entire,
        ControlState::ENABLED | ControlState::SELECTED | ControlState::ROLLOVER, aTabValue);
    CPPUNIT_ASSERT_EQUAL(size_t(4), aSelectedRolloverTabStates.size());
    const auto& rSelectedRolloverTabRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aSelectedRolloverTabStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"d0bcff"_ustr, rSelectedRolloverTabRect.maFillColor.AsRGBHexString());
    auto pTabMenuItem = aDefinition.getDefinition(ControlType::TabItem, ControlPart::MenuItem);
    CPPUNIT_ASSERT(pTabMenuItem);
    const auto aSelectedFocusedMenuItemStates = pTabMenuItem->getStates(
        ControlType::TabItem, ControlPart::MenuItem,
        ControlState::ENABLED | ControlState::SELECTED | ControlState::FOCUSED, aTabValue);
    CPPUNIT_ASSERT_EQUAL(size_t(4), aSelectedFocusedMenuItemStates.size());
    const auto& rSelectedFocusedMenuItemRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aSelectedFocusedMenuItemStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"e8def8"_ustr, rSelectedFocusedMenuItemRect.maFillColor.AsRGBHexString());

    auto pListHeaderButton
        = aDefinition.getDefinition(ControlType::ListHeader, ControlPart::Button);
    CPPUNIT_ASSERT(pListHeaderButton);
    auto pListHeaderArrow = aDefinition.getDefinition(ControlType::ListHeader, ControlPart::Arrow);
    CPPUNIT_ASSERT(pListHeaderArrow);
    const auto aDownArrowStates
        = pListHeaderArrow->getStates(ControlType::ListHeader, ControlPart::Arrow,
                                      ControlState::ENABLED, ImplControlValue(tools::Long(1)));
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDownArrowStates.size());
    CPPUNIT_ASSERT_EQUAL(size_t(2), aDownArrowStates[0]->mpWidgetDrawActions.size());

    vcl::WidgetDefinition aDarkDefinition;
    vcl::WidgetDefinitionReader aDarkReader(getMaterialThemeUrl(u"definition.xml"),
                                            getMaterialThemeUrl(u""), "dark"_ostr);
    CPPUNIT_ASSERT(aDarkReader.read(aDarkDefinition));
    CPPUNIT_ASSERT_EQUAL(u"141218"_ustr, aDarkDefinition.mpStyle->maWindowColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"e6e0e9"_ustr,
                         aDarkDefinition.mpStyle->maWindowTextColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"381e72"_ustr,
                         aDarkDefinition.mpStyle->maActionButtonTextColor.AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moAccentColor);
    CPPUNIT_ASSERT_EQUAL(u"d0bcff"_ustr, aDarkDefinition.mpStyle->moAccentColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moListBoxWindowBackgroundColor);
    CPPUNIT_ASSERT_EQUAL(u"141218"_ustr,
                         aDarkDefinition.mpStyle->moListBoxWindowBackgroundColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moListBoxWindowTextColor);
    CPPUNIT_ASSERT_EQUAL(u"e6e0e9"_ustr,
                         aDarkDefinition.mpStyle->moListBoxWindowTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moListBoxWindowHighlightColor);
    CPPUNIT_ASSERT_EQUAL(u"4f378b"_ustr,
                         aDarkDefinition.mpStyle->moListBoxWindowHighlightColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moListBoxWindowHighlightTextColor);
    CPPUNIT_ASSERT_EQUAL(
        u"eaddff"_ustr,
        aDarkDefinition.mpStyle->moListBoxWindowHighlightTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moAlternatingRowColor);
    CPPUNIT_ASSERT_EQUAL(u"1d1b20"_ustr,
                         aDarkDefinition.mpStyle->moAlternatingRowColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moWarningColor);
    CPPUNIT_ASSERT_EQUAL(u"5f4100"_ustr, aDarkDefinition.mpStyle->moWarningColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moWarningTextColor);
    CPPUNIT_ASSERT_EQUAL(u"ffddb3"_ustr,
                         aDarkDefinition.mpStyle->moWarningTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moErrorColor);
    CPPUNIT_ASSERT_EQUAL(u"8c1d18"_ustr, aDarkDefinition.mpStyle->moErrorColor->AsRGBHexString());
    CPPUNIT_ASSERT(aDarkDefinition.mpStyle->moErrorTextColor);
    CPPUNIT_ASSERT_EQUAL(u"f9dedc"_ustr,
                         aDarkDefinition.mpStyle->moErrorTextColor->AsRGBHexString());
    CPPUNIT_ASSERT(contrastRatio(aDarkDefinition.mpStyle->maWindowTextColor,
                                 aDarkDefinition.mpStyle->maWindowColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDarkDefinition.mpStyle->moListBoxWindowTextColor,
                                 *aDarkDefinition.mpStyle->moListBoxWindowBackgroundColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDarkDefinition.mpStyle->moListBoxWindowHighlightTextColor,
                                 *aDarkDefinition.mpStyle->moListBoxWindowHighlightColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDarkDefinition.mpStyle->moWarningTextColor,
                                 *aDarkDefinition.mpStyle->moWarningColor)
                   >= 4.5);
    CPPUNIT_ASSERT(contrastRatio(*aDarkDefinition.mpStyle->moErrorTextColor,
                                 *aDarkDefinition.mpStyle->moErrorColor)
                   >= 4.5);
    CPPUNIT_ASSERT(aDarkDefinition.mpTypography);
    CPPUNIT_ASSERT_EQUAL(aDefinition.mpTypography->maBody.mnScalePercent,
                         aDarkDefinition.mpTypography->maBody.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maBody.meWeight
                   == aDarkDefinition.mpTypography->maBody.meWeight);
    CPPUNIT_ASSERT_EQUAL(aDefinition.mpTypography->maLabel.mnScalePercent,
                         aDarkDefinition.mpTypography->maLabel.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maLabel.meWeight
                   == aDarkDefinition.mpTypography->maLabel.meWeight);
    CPPUNIT_ASSERT_EQUAL(aDefinition.mpTypography->maTitle.mnScalePercent,
                         aDarkDefinition.mpTypography->maTitle.mnScalePercent);
    CPPUNIT_ASSERT(aDefinition.mpTypography->maTitle.meWeight
                   == aDarkDefinition.mpTypography->maTitle.meWeight);

    auto pDarkPushButton
        = aDarkDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Entire);
    CPPUNIT_ASSERT(pDarkPushButton);
    const auto aDarkActionButtonStates = pDarkPushButton->getStates(
        ControlType::Pushbutton, ControlPart::Entire, ControlState::ENABLED, aActionButtonValue);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aDarkActionButtonStates.size());
    const auto& rDarkActionButtonRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aDarkActionButtonStates.back()->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"d0bcff"_ustr, rDarkActionButtonRect.maFillColor.AsRGBHexString());
    CPPUNIT_ASSERT(contrastRatio(aDarkDefinition.mpStyle->maActionButtonTextColor,
                                 rDarkActionButtonRect.maFillColor)
                   >= 4.5);

    auto pDarkSpinButton
        = aDarkDefinition.getDefinition(ControlType::SpinButtons, ControlPart::ButtonUp);
    CPPUNIT_ASSERT(pDarkSpinButton);
    const auto aDarkSpinButtonStates = pDarkSpinButton->getStates(
        ControlType::SpinButtons, ControlPart::ButtonUp, ControlState::ENABLED, SpinbuttonValue());
    CPPUNIT_ASSERT_EQUAL(size_t(1), aDarkSpinButtonStates.size());
    const auto& rDarkSpinButtonRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
        *aDarkSpinButtonStates[0]->mpWidgetDrawActions[0]);
    CPPUNIT_ASSERT_EQUAL(u"4f378b"_ustr, rDarkSpinButtonRect.maFillColor.AsRGBHexString());
}

void WidgetDefinitionReaderTest::testReadSettings()
{
    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionSettings1.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL(""_ostr, aDefinition.mpSettings->msCenteredTabs);
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionSettings2.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL("true"_ostr, aDefinition.mpSettings->msCenteredTabs);
    }

    {
        vcl::WidgetDefinition aDefinition;
        vcl::WidgetDefinitionReader aReader(getFullUrl(u"definitionSettings3.xml"),
                                            getFullUrl(u""));
        CPPUNIT_ASSERT(aReader.read(aDefinition));
        CPPUNIT_ASSERT_EQUAL("true"_ostr, aDefinition.mpSettings->msNoActiveTabTextRaise);
        CPPUNIT_ASSERT_EQUAL("false"_ostr, aDefinition.mpSettings->msCenteredTabs);
        CPPUNIT_ASSERT_EQUAL("0"_ostr, aDefinition.mpSettings->msListBoxEntryMargin);
        CPPUNIT_ASSERT_EQUAL("10"_ostr, aDefinition.mpSettings->msDefaultFontSize);
        CPPUNIT_ASSERT_EQUAL("16"_ostr, aDefinition.mpSettings->msTitleHeight);
        CPPUNIT_ASSERT_EQUAL("12"_ostr, aDefinition.mpSettings->msFloatTitleHeight);
        CPPUNIT_ASSERT_EQUAL("15"_ostr, aDefinition.mpSettings->msListBoxPreviewDefaultLogicWidth);
        CPPUNIT_ASSERT_EQUAL("7"_ostr, aDefinition.mpSettings->msListBoxPreviewDefaultLogicHeight);
    }
}

void WidgetDefinitionReaderTest::testRead()
{
    vcl::WidgetDefinition aDefinition;

    vcl::WidgetDefinitionReader aReader(getFullUrl(u"definition1.xml"), getFullUrl(u""));
    CPPUNIT_ASSERT(aReader.read(aDefinition));

    CPPUNIT_ASSERT_EQUAL(u"123456"_ustr, aDefinition.mpStyle->maFaceColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"234567"_ustr, aDefinition.mpStyle->maCheckedColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"345678"_ustr, aDefinition.mpStyle->maLightColor.AsRGBHexString());

    CPPUNIT_ASSERT_EQUAL(u"ffffff"_ustr, aDefinition.mpStyle->maVisitedLinkColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"ffffff"_ustr, aDefinition.mpStyle->maToolTextColor.AsRGBHexString());
    CPPUNIT_ASSERT_EQUAL(u"ffffff"_ustr, aDefinition.mpStyle->maWindowTextColor.AsRGBHexString());
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moAccentColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moListBoxWindowBackgroundColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moListBoxWindowTextColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moListBoxWindowHighlightColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moListBoxWindowHighlightTextColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moAlternatingRowColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moWarningColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moWarningTextColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moErrorColor);
    CPPUNIT_ASSERT(!aDefinition.mpStyle->moErrorTextColor);

    // Pushbutton
    {
        ControlState eState
            = ControlState::DEFAULT | ControlState::ENABLED | ControlState::ROLLOVER;
        std::vector<std::shared_ptr<vcl::WidgetDefinitionState>> aStates
            = aDefinition.getDefinition(ControlType::Pushbutton, ControlPart::Entire)
                  ->getStates(ControlType::Pushbutton, ControlPart::Entire, eState,
                              PushButtonValue());

        CPPUNIT_ASSERT_EQUAL(size_t(2), aStates.size());

        CPPUNIT_ASSERT_EQUAL(size_t(2), aStates[0]->mpWidgetDrawActions.size());
        CPPUNIT_ASSERT_EQUAL(vcl::WidgetDrawActionType::RECTANGLE,
                             aStates[0]->mpWidgetDrawActions[0]->maType);
        CPPUNIT_ASSERT_EQUAL(vcl::WidgetDrawActionType::LINE,
                             aStates[0]->mpWidgetDrawActions[1]->maType);
        const auto& rRect = static_cast<const vcl::WidgetDrawActionRectangle&>(
            *aStates[0]->mpWidgetDrawActions[0]);
        CPPUNIT_ASSERT_EQUAL(sal_Int32(5), rRect.mnRx);
        CPPUNIT_ASSERT_EQUAL(sal_Int32(5), rRect.mnRy);
    }

    // Radiobutton
    {
        std::vector<std::shared_ptr<vcl::WidgetDefinitionState>> aStates
            = aDefinition.getDefinition(ControlType::Radiobutton, ControlPart::Entire)
                  ->getStates(ControlType::Radiobutton, ControlPart::Entire, ControlState::NONE,
                              ImplControlValue(ButtonValue::On));
        CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
        CPPUNIT_ASSERT_EQUAL(size_t(2), aStates[0]->mpWidgetDrawActions.size());
    }

    {
        std::vector<std::shared_ptr<vcl::WidgetDefinitionState>> aStates
            = aDefinition.getDefinition(ControlType::Radiobutton, ControlPart::Entire)
                  ->getStates(ControlType::Radiobutton, ControlPart::Entire, ControlState::NONE,
                              ImplControlValue(ButtonValue::Off));
        CPPUNIT_ASSERT_EQUAL(size_t(1), aStates.size());
        CPPUNIT_ASSERT_EQUAL(size_t(1), aStates[0]->mpWidgetDrawActions.size());
    }
}

} // namespace

CPPUNIT_TEST_SUITE_REGISTRATION(WidgetDefinitionReaderTest);

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
