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
#include <cmath>
#include <string_view>

#include <cppunit/TestAssert.h>
#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/plugin/TestPlugIn.h>
#include <unotest/bootstrapfixturebase.hxx>

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
    void testReadColorTokens();
    void testRejectInvalidDefinitions();
    void testReadMaterialTheme();

    CPPUNIT_TEST_SUITE(WidgetDefinitionReaderTest);
    CPPUNIT_TEST(testRead);
    CPPUNIT_TEST(testReadSettings);
    CPPUNIT_TEST(testReadColorTokens);
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
    CPPUNIT_ASSERT_EQUAL("12"_ostr, aDefinition.mpSettings->msListBoxEntryMargin);
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
