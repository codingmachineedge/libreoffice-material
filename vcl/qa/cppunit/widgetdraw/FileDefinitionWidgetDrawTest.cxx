/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <array>
#include <cstddef>
#include <iterator>

#include <cppunit/TestAssert.h>
#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/plugin/TestPlugIn.h>
#include <test/bootstrapfixture.hxx>

#include <tools/color.hxx>
#include <tools/gen.hxx>
#include <vcl/settings.hxx>
#include <vcl/salnativewidgets.hxx>
#include <vcl/virdev.hxx>
#include <vcl/wall.hxx>

#include <salgdi.hxx>
#include <toolbarvalue.hxx>

namespace
{
constexpr tools::Long gnDeviceWidth = 160;
constexpr tools::Long gnDeviceHeight = 96;

void initializeDevice(VirtualDevice& rDevice)
{
    CPPUNIT_ASSERT(rDevice.SetOutputSizePixel(Size(gnDeviceWidth, gnDeviceHeight)));
    rDevice.SetBackground(Wallpaper(COL_WHITE));
    rDevice.Erase();
}

using StyleColorSetter = void (StyleSettings::*)(const Color&);

void assertStyleColorApplied(const StyleSettings& rActual, StyleColorSetter pSetter,
                             const Color& rExpected)
{
    StyleSettings aProbe(rActual);
    (aProbe.*pSetter)(rExpected);
    CPPUNIT_ASSERT(aProbe == rActual);
}

class FileDefinitionWidgetDrawTest : public test::BootstrapFixture
{
public:
    FileDefinitionWidgetDrawTest()
        : BootstrapFixture(true, false)
    {
    }
};

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testMaterialStyleSettingsColorClosure)
{
    ScopedVclPtrInstance<VirtualDevice> xDevice;
    initializeDevice(*xDevice);
    CPPUNIT_ASSERT(xDevice->IsNativeControlSupported(ControlType::Pushbutton, ControlPart::Entire));

    SalGraphics* pGraphics = xDevice->GetGraphics();
    CPPUNIT_ASSERT(pGraphics);

    AllSettings aSettings;
    StyleSettings aSeededStyle(aSettings.GetStyleSettings());
    const Color aSentinel(0x01, 0x02, 0x03);
    aSeededStyle.SetAccentColor(aSentinel);
    aSeededStyle.SetListBoxWindowBackgroundColor(aSentinel);
    aSeededStyle.SetListBoxWindowTextColor(aSentinel);
    aSeededStyle.SetListBoxWindowHighlightColor(aSentinel);
    aSeededStyle.SetListBoxWindowHighlightTextColor(aSentinel);
    aSeededStyle.SetAlternatingRowColor(aSentinel);
    aSeededStyle.SetWarningColor(aSentinel);
    aSeededStyle.SetWarningTextColor(aSentinel);
    aSeededStyle.SetErrorColor(aSentinel);
    aSeededStyle.SetErrorTextColor(aSentinel);
    aSettings.SetStyleSettings(aSeededStyle);

    CPPUNIT_ASSERT(pGraphics->UpdateSettings(aSettings));
    const StyleSettings& rMaterialStyle = aSettings.GetStyleSettings();
    const bool bDark = MiscSettings::GetUseDarkMode();
    const auto selectSchemeColor
        = [bDark](const Color& rLight, const Color& rDark) { return bDark ? rDark : rLight; };
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetAccentColor,
                            selectSchemeColor(Color(0x67, 0x50, 0xA4), Color(0xD0, 0xBC, 0xFF)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetListBoxWindowBackgroundColor,
                            selectSchemeColor(Color(0xFF, 0xFB, 0xFE), Color(0x14, 0x12, 0x18)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetListBoxWindowTextColor,
                            selectSchemeColor(Color(0x1D, 0x1B, 0x20), Color(0xE6, 0xE0, 0xE9)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetListBoxWindowHighlightColor,
                            selectSchemeColor(Color(0xE8, 0xDE, 0xF8), Color(0x4F, 0x37, 0x8B)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetListBoxWindowHighlightTextColor,
                            selectSchemeColor(Color(0x1D, 0x19, 0x2B), Color(0xEA, 0xDD, 0xFF)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetAlternatingRowColor,
                            selectSchemeColor(Color(0xF7, 0xF2, 0xFA), Color(0x1D, 0x1B, 0x20)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetWarningColor,
                            selectSchemeColor(Color(0xFF, 0xDD, 0xB3), Color(0x5F, 0x41, 0x00)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetWarningTextColor,
                            selectSchemeColor(Color(0x2A, 0x18, 0x00), Color(0xFF, 0xDD, 0xB3)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetErrorColor,
                            selectSchemeColor(Color(0xF9, 0xDE, 0xDC), Color(0x8C, 0x1D, 0x18)));
    assertStyleColorApplied(rMaterialStyle, &StyleSettings::SetErrorTextColor,
                            selectSchemeColor(Color(0x41, 0x0E, 0x0B), Color(0xF9, 0xDE, 0xDC)));

    const StyleSettings aFirstApplication(rMaterialStyle);
    CPPUNIT_ASSERT(pGraphics->UpdateSettings(aSettings));
    CPPUNIT_ASSERT(aFirstApplication == aSettings.GetStyleSettings());

    AllSettings aHighContrastSettings;
    StyleSettings aHighContrastStyle(aSeededStyle);
    aHighContrastStyle.SetHighContrastMode(true);
    aHighContrastSettings.SetStyleSettings(aHighContrastStyle);
    CPPUNIT_ASSERT(!pGraphics->UpdateSettings(aHighContrastSettings));
    CPPUNIT_ASSERT(aHighContrastStyle == aHighContrastSettings.GetStyleSettings());

    // FileDefinitionThemeState is shared, so leave it in the ordinary Material path.
    CPPUNIT_ASSERT(pGraphics->UpdateSettings(aSettings));
}

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testComboBoxLtrAndRtlGeometryAndPixels)
{
    constexpr tools::Long nControlX = 20;
    constexpr tools::Long nControlY = 10;
    constexpr tools::Long nControlWidth = 120;
    constexpr tools::Long nControlHeight = 40;
    constexpr tools::Long nButtonWidth = 36;
    constexpr tools::Long nButtonHeight = 36;

    const tools::Rectangle aControlRegion(Point(nControlX, nControlY),
                                          Size(nControlWidth, nControlHeight));
    const tools::Rectangle aExpectedButton(Point(nControlX + nControlWidth - nButtonWidth,
                                                 nControlY + (nControlHeight - nButtonHeight) / 2),
                                           Size(nButtonWidth, nButtonHeight));
    const tools::Rectangle aExpectedSubEdit(
        Point(nControlX + 1, nControlY + 1),
        Size(nControlWidth - nButtonWidth - 1, nControlHeight - 2));
    const ImplControlValue aValue;

    ScopedVclPtrInstance<VirtualDevice> xLtrDevice;
    initializeDevice(*xLtrDevice);

    CPPUNIT_ASSERT(
        xLtrDevice->IsNativeControlSupported(ControlType::Combobox, ControlPart::Entire));
    CPPUNIT_ASSERT(
        xLtrDevice->IsNativeControlSupported(ControlType::Combobox, ControlPart::ButtonDown));

    tools::Rectangle aBoundingRegion;
    tools::Rectangle aContentRegion;
    CPPUNIT_ASSERT(xLtrDevice->GetNativeControlRegion(
        ControlType::Combobox, ControlPart::ButtonDown, aControlRegion, ControlState::ENABLED,
        aValue, aBoundingRegion, aContentRegion));
    CPPUNIT_ASSERT_EQUAL(aExpectedButton, aBoundingRegion);
    CPPUNIT_ASSERT_EQUAL(aExpectedButton, aContentRegion);

    CPPUNIT_ASSERT(xLtrDevice->GetNativeControlRegion(ControlType::Combobox, ControlPart::SubEdit,
                                                      aControlRegion, ControlState::ENABLED, aValue,
                                                      aBoundingRegion, aContentRegion));
    CPPUNIT_ASSERT_EQUAL(aExpectedSubEdit, aBoundingRegion);
    CPPUNIT_ASSERT_EQUAL(aExpectedSubEdit, aContentRegion);

    CPPUNIT_ASSERT(xLtrDevice->DrawNativeControl(ControlType::Combobox, ControlPart::Entire,
                                                 aControlRegion, ControlState::ENABLED, aValue,
                                                 OUString()));

    const Color aLtrButtonColor
        = xLtrDevice->GetPixel(Point(aExpectedButton.Left() + 8, aExpectedButton.Center().Y()));
    const Color aLtrSurfaceColor
        = xLtrDevice->GetPixel(Point(nControlX + 8, aExpectedButton.Center().Y()));
    CPPUNIT_ASSERT(aLtrButtonColor != aLtrSurfaceColor);

    ScopedVclPtrInstance<VirtualDevice> xRtlDevice;
    initializeDevice(*xRtlDevice);
    xRtlDevice->EnableRTL();

    CPPUNIT_ASSERT(xRtlDevice->GetNativeControlRegion(
        ControlType::Combobox, ControlPart::ButtonDown, aControlRegion, ControlState::ENABLED,
        aValue, aBoundingRegion, aContentRegion));
    // Native regions are converted back to logical coordinates for callers.
    CPPUNIT_ASSERT_EQUAL(aExpectedButton, aBoundingRegion);
    CPPUNIT_ASSERT_EQUAL(aExpectedButton, aContentRegion);

    CPPUNIT_ASSERT(xRtlDevice->GetNativeControlRegion(ControlType::Combobox, ControlPart::SubEdit,
                                                      aControlRegion, ControlState::ENABLED, aValue,
                                                      aBoundingRegion, aContentRegion));
    CPPUNIT_ASSERT_EQUAL(aExpectedSubEdit, aBoundingRegion);
    CPPUNIT_ASSERT_EQUAL(aExpectedSubEdit, aContentRegion);

    CPPUNIT_ASSERT(xRtlDevice->DrawNativeControl(ControlType::Combobox, ControlPart::Entire,
                                                 aControlRegion, ControlState::ENABLED, aValue,
                                                 OUString()));

    // The control is centered horizontally, so mirroring keeps its outer bounds
    // fixed. Disable logical mirroring only for raw physical-pixel inspection.
    xRtlDevice->EnableRTL(false);
    const Point aRtlButtonSample(nControlX + 8, aExpectedButton.Center().Y());
    const Point aRtlSurfaceSample(aExpectedButton.Left() + 8, aExpectedButton.Center().Y());
    const Color aRtlButtonColor = xRtlDevice->GetPixel(aRtlButtonSample);
    const Color aRtlSurfaceColor = xRtlDevice->GetPixel(aRtlSurfaceSample);

    CPPUNIT_ASSERT_EQUAL(aLtrButtonColor, aRtlButtonColor);
    CPPUNIT_ASSERT_EQUAL(aLtrSurfaceColor, aRtlSurfaceColor);
    CPPUNIT_ASSERT(aRtlButtonColor != aRtlSurfaceColor);
}

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testToolbarGripUsesValueGeometry)
{
    ScopedVclPtrInstance<VirtualDevice> xDevice;
    initializeDevice(*xDevice);

    CPPUNIT_ASSERT(xDevice->IsNativeControlSupported(ControlType::Toolbar, ControlPart::ThumbVert));

    const tools::Rectangle aControlRegion(Point(10, 8), Size(100, 60));
    ToolbarValue aValue;
    aValue.maGripRect = tools::Rectangle(Point(31, 17), Size(12, 36));

    CPPUNIT_ASSERT(xDevice->DrawNativeControl(ControlType::Toolbar, ControlPart::ThumbVert,
                                              aControlRegion, ControlState::ENABLED, aValue,
                                              OUString()));

    CPPUNIT_ASSERT_EQUAL(COL_WHITE, xDevice->GetPixel(Point(20, 30)));
    CPPUNIT_ASSERT(xDevice->GetPixel(aValue.maGripRect.Center()) != COL_WHITE);
}

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testProgressAndLevelIndicatorTracks)
{
    ScopedVclPtrInstance<VirtualDevice> xDevice;
    initializeDevice(*xDevice);

    CPPUNIT_ASSERT(xDevice->IsNativeControlSupported(ControlType::Progress, ControlPart::Entire));
    CPPUNIT_ASSERT(
        xDevice->IsNativeControlSupported(ControlType::Progress, ControlPart::TrackHorzArea));
    CPPUNIT_ASSERT(xDevice->IsNativeControlSupported(ControlType::LevelBar, ControlPart::Entire));
    CPPUNIT_ASSERT(
        xDevice->IsNativeControlSupported(ControlType::LevelBar, ControlPart::TrackHorzArea));

    const tools::Rectangle aProgressRegion(Point(10, 4), Size(140, 12));
    CPPUNIT_ASSERT(xDevice->DrawNativeControl(ControlType::Progress, ControlPart::Entire,
                                              aProgressRegion, ControlState::ENABLED,
                                              ImplControlValue(tools::Long(45)), OUString()));
    const Color aProgressFill
        = xDevice->GetPixel(Point(aProgressRegion.Left() + 12, aProgressRegion.Center().Y()));
    const Color aProgressTrack
        = xDevice->GetPixel(Point(aProgressRegion.Right() - 12, aProgressRegion.Center().Y()));
    CPPUNIT_ASSERT(aProgressFill != COL_WHITE);
    CPPUNIT_ASSERT(aProgressTrack != COL_WHITE);
    CPPUNIT_ASSERT(aProgressFill != aProgressTrack);

    const tools::Rectangle aZeroRegion(Point(10, 20), Size(140, 12));
    CPPUNIT_ASSERT(xDevice->DrawNativeControl(ControlType::Progress, ControlPart::Entire,
                                              aZeroRegion, ControlState::ENABLED,
                                              ImplControlValue(tools::Long(0)), OUString()));
    const Color aZeroTrackLeft
        = xDevice->GetPixel(Point(aZeroRegion.Left() + 12, aZeroRegion.Center().Y()));
    const Color aZeroTrackRight
        = xDevice->GetPixel(Point(aZeroRegion.Right() - 12, aZeroRegion.Center().Y()));
    CPPUNIT_ASSERT(aZeroTrackLeft != COL_WHITE);
    CPPUNIT_ASSERT_EQUAL(aZeroTrackLeft, aZeroTrackRight);

    constexpr tools::Long aValues[] = { 24, 25, 49, 50, 74, 75 };
    std::array<Color, std::size(aValues)> aLevelColors;
    for (std::size_t i = 0; i < std::size(aValues); ++i)
    {
        const tools::Rectangle aLevelRegion(Point(10, 36 + tools::Long(i) * 10), Size(100, 8));
        CPPUNIT_ASSERT(xDevice->DrawNativeControl(ControlType::LevelBar, ControlPart::Entire,
                                                  aLevelRegion, ControlState::ENABLED,
                                                  ImplControlValue(aValues[i]), OUString()));
        aLevelColors[i]
            = xDevice->GetPixel(Point(aLevelRegion.Left() + 5, aLevelRegion.Center().Y()));
        const Color aTrack
            = xDevice->GetPixel(Point(aLevelRegion.Right() - 5, aLevelRegion.Center().Y()));
        CPPUNIT_ASSERT(aLevelColors[i] != COL_WHITE);
        CPPUNIT_ASSERT(aTrack != COL_WHITE);
        CPPUNIT_ASSERT(aLevelColors[i] != aTrack);
    }

    CPPUNIT_ASSERT(aLevelColors[0] != aLevelColors[1]);
    CPPUNIT_ASSERT_EQUAL(aLevelColors[1], aLevelColors[2]);
    CPPUNIT_ASSERT(aLevelColors[2] != aLevelColors[3]);
    CPPUNIT_ASSERT_EQUAL(aLevelColors[3], aLevelColors[4]);
    CPPUNIT_ASSERT(aLevelColors[4] != aLevelColors[5]);
}

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testStandaloneSpinButtonComposites)
{
    ScopedVclPtrInstance<VirtualDevice> xVerticalDevice;
    initializeDevice(*xVerticalDevice);

    CPPUNIT_ASSERT(
        xVerticalDevice->IsNativeControlSupported(ControlType::SpinButtons, ControlPart::Entire));
    CPPUNIT_ASSERT(xVerticalDevice->IsNativeControlSupported(ControlType::SpinButtons,
                                                             ControlPart::AllButtons));

    SpinbuttonValue aVerticalValue;
    aVerticalValue.maUpperRect = tools::Rectangle(Point(12, 8), Size(40, 40));
    aVerticalValue.maLowerRect = tools::Rectangle(Point(12, 52), Size(40, 40));
    aVerticalValue.mnUpperPart = ControlPart::ButtonUp;
    aVerticalValue.mnLowerPart = ControlPart::ButtonDown;
    aVerticalValue.mnUpperState = ControlState::ENABLED | ControlState::ROLLOVER;
    aVerticalValue.mnLowerState = ControlState::ENABLED | ControlState::PRESSED;

    CPPUNIT_ASSERT(xVerticalDevice->DrawNativeControl(
        ControlType::SpinButtons, ControlPart::Entire, tools::Rectangle(Point(8, 4), Size(52, 90)),
        ControlState::ENABLED, aVerticalValue, OUString()));

    const Color aUpApex = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maUpperRect.Left() + 20, aVerticalValue.maUpperRect.Top() + 16));
    const Color aUpOpposite = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maUpperRect.Left() + 20, aVerticalValue.maUpperRect.Top() + 23));
    const Color aDownApex = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maLowerRect.Left() + 20, aVerticalValue.maLowerRect.Top() + 23));
    const Color aDownOpposite = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maLowerRect.Left() + 20, aVerticalValue.maLowerRect.Top() + 16));
    CPPUNIT_ASSERT(aUpApex != aUpOpposite);
    CPPUNIT_ASSERT(aDownApex != aDownOpposite);

    const Color aRolloverFill = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maUpperRect.Left() + 5, aVerticalValue.maUpperRect.Center().Y()));
    const Color aPressedFill = xVerticalDevice->GetPixel(
        Point(aVerticalValue.maLowerRect.Left() + 5, aVerticalValue.maLowerRect.Center().Y()));
    CPPUNIT_ASSERT(aRolloverFill != COL_WHITE);
    CPPUNIT_ASSERT(aPressedFill != COL_WHITE);
    CPPUNIT_ASSERT(aRolloverFill != aPressedFill);
    CPPUNIT_ASSERT_EQUAL(COL_WHITE, xVerticalDevice->GetPixel(Point(70, 30)));

    ScopedVclPtrInstance<VirtualDevice> xHorizontalDevice;
    initializeDevice(*xHorizontalDevice);

    SpinbuttonValue aHorizontalValue;
    aHorizontalValue.maUpperRect = tools::Rectangle(Point(68, 20), Size(40, 40));
    aHorizontalValue.maLowerRect = tools::Rectangle(Point(112, 20), Size(40, 40));
    aHorizontalValue.mnUpperPart = ControlPart::ButtonRight;
    aHorizontalValue.mnLowerPart = ControlPart::ButtonLeft;
    aHorizontalValue.mnUpperState = ControlState::ENABLED | ControlState::ROLLOVER;
    aHorizontalValue.mnLowerState = ControlState::ENABLED | ControlState::PRESSED;

    CPPUNIT_ASSERT(
        xHorizontalDevice->DrawNativeControl(ControlType::SpinButtons, ControlPart::AllButtons,
                                             tools::Rectangle(Point(64, 16), Size(92, 48)),
                                             ControlState::ENABLED, aHorizontalValue, OUString()));

    const Color aRightApex = xHorizontalDevice->GetPixel(
        Point(aHorizontalValue.maUpperRect.Left() + 23, aHorizontalValue.maUpperRect.Top() + 20));
    const Color aRightOpposite = xHorizontalDevice->GetPixel(
        Point(aHorizontalValue.maUpperRect.Left() + 16, aHorizontalValue.maUpperRect.Top() + 20));
    const Color aLeftApex = xHorizontalDevice->GetPixel(
        Point(aHorizontalValue.maLowerRect.Left() + 16, aHorizontalValue.maLowerRect.Top() + 20));
    const Color aLeftOpposite = xHorizontalDevice->GetPixel(
        Point(aHorizontalValue.maLowerRect.Left() + 23, aHorizontalValue.maLowerRect.Top() + 20));
    CPPUNIT_ASSERT(aRightApex != aRightOpposite);
    CPPUNIT_ASSERT(aLeftApex != aLeftOpposite);

    CPPUNIT_ASSERT_EQUAL(aRolloverFill, xHorizontalDevice->GetPixel(
                                            Point(aHorizontalValue.maUpperRect.Left() + 5,
                                                  aHorizontalValue.maUpperRect.Center().Y())));
    CPPUNIT_ASSERT_EQUAL(aPressedFill, xHorizontalDevice->GetPixel(
                                           Point(aHorizontalValue.maLowerRect.Left() + 5,
                                                 aHorizontalValue.maLowerRect.Center().Y())));
    CPPUNIT_ASSERT_EQUAL(COL_WHITE, xHorizontalDevice->GetPixel(Point(20, 30)));
}

CPPUNIT_TEST_FIXTURE(FileDefinitionWidgetDrawTest, testNativeDrawingInvalidatesColorCache)
{
    ScopedVclPtrInstance<VirtualDevice> xDevice;
    initializeDevice(*xDevice);

    xDevice->SetLineColor(COL_BLUE);
    xDevice->SetFillColor(COL_RED);

    const tools::Rectangle aComboRegion(Point(20, 8), Size(120, 40));
    CPPUNIT_ASSERT(xDevice->DrawNativeControl(ControlType::Combobox, ControlPart::Entire,
                                              aComboRegion, ControlState::ENABLED,
                                              ImplControlValue(), OUString()));

    const tools::Rectangle aOrdinaryRectangle(Point(12, 62), Size(28, 22));
    xDevice->DrawRect(aOrdinaryRectangle);

    CPPUNIT_ASSERT_EQUAL(COL_RED, xDevice->GetPixel(aOrdinaryRectangle.Center()));
    CPPUNIT_ASSERT_EQUAL(COL_BLUE, xDevice->GetPixel(Point(aOrdinaryRectangle.Center().X(),
                                                           aOrdinaryRectangle.Top())));
}

} // namespace

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
