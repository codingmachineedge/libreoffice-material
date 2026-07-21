/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#include <sal/config.h>

#include <algorithm>
#include <cstdlib>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <string_view>
#include <utility>

#include <FileDefinitionWidgetDraw.hxx>
#include <widgetdraw/WidgetDefinitionReader.hxx>

#include <svdata.hxx>
#include <rtl/bootstrap.hxx>
#include <config_folders.h>
#include <osl/file.hxx>

#include <basegfx/range/b2drectangle.hxx>
#include <basegfx/polygon/b2dpolygontools.hxx>
#include <basegfx/tuple/b2dtuple.hxx>
#include <basegfx/matrix/b2dhommatrixtools.hxx>

#include <tools/stream.hxx>
#include <sal/log.hxx>
#include <vcl/bitmap.hxx>
#include <vcl/BitmapTools.hxx>
#include <vcl/gradient.hxx>
#include <toolbarvalue.hxx>

#include <comphelper/seqstream.hxx>
#include <comphelper/processfactory.hxx>
#include <comphelper/lok.hxx>
#include <comphelper/string.hxx>

#include <com/sun/star/graphic/SvgTools.hpp>
#include <basegfx/DrawCommands.hxx>
#include <o3tl/string_view.hxx>

using namespace css;

namespace vcl
{
struct FileDefinitionThemeState
{
    explicit FileDefinitionThemeState(OUString aRequestedTheme)
        : maRequestedTheme(std::move(aRequestedTheme))
    {
    }

    std::mutex maMutex;
    OUString maRequestedTheme;
    OUString maResolvedTheme;
    OString maColorScheme;
    std::shared_ptr<WidgetDefinition> mpDefinition;
    std::optional<StyleSettings> moNativeStyle;
    bool mbHighContrast = false;
};

namespace
{
OUString lcl_getThemeDefinitionPath()
{
    OUString sPath(u"$BRAND_BASE_DIR/" LIBO_SHARE_FOLDER "/theme_definitions/"_ustr);
    rtl::Bootstrap::expandMacros(sPath);
    return sPath;
}

bool lcl_directoryExists(OUString const& sDirectory)
{
    osl::DirectoryItem aDirectoryItem;
    osl::FileBase::RC eRes = osl::DirectoryItem::get(sDirectory, aDirectoryItem);
    return eRes == osl::FileBase::E_None;
}

bool lcl_fileExists(OUString const& sFilename)
{
    osl::File aFile(sFilename);
    osl::FileBase::RC eRC = aFile.open(osl_File_OpenFlag_Read);
    return osl::FileBase::E_None == eRC;
}

struct ComboBoxPartRegions
{
    tools::Rectangle maButton;
    tools::Rectangle maSubEdit;
};

ComboBoxPartRegions lcl_getComboBoxPartRegions(const tools::Rectangle& rControlRegion,
                                               const Size& rRequestedButtonSize, bool bRtl)
{
    // Native-control regions use device coordinates. Keep their physical RTL
    // placement identical to the composite drawn for ControlPart::Entire.
    const tools::Long nControlWidth = std::max<tools::Long>(rControlRegion.GetWidth(), 0);
    const tools::Long nControlHeight = std::max<tools::Long>(rControlRegion.GetHeight(), 0);
    const tools::Long nButtonWidth
        = std::clamp<tools::Long>(rRequestedButtonSize.Width(), 0, nControlWidth);
    const tools::Long nButtonHeight
        = std::clamp<tools::Long>(rRequestedButtonSize.Height(), 0, nControlHeight);
    const tools::Long nButtonX
        = bRtl ? rControlRegion.Left() : rControlRegion.Left() + nControlWidth - nButtonWidth;
    const tools::Long nButtonY = rControlRegion.Top() + (nControlHeight - nButtonHeight) / 2;

    const tools::Long nSubEditWidth = std::max<tools::Long>(nControlWidth - nButtonWidth - 1, 0);
    const tools::Long nSubEditHeight = std::max<tools::Long>(nControlHeight - 2, 0);
    const tools::Long nSubEditX
        = bRtl ? rControlRegion.Left() + nButtonWidth : rControlRegion.Left() + 1;

    return { tools::Rectangle(Point(nButtonX, nButtonY), Size(nButtonWidth, nButtonHeight)),
             tools::Rectangle(Point(nSubEditX, rControlRegion.Top() + 1),
                              Size(nSubEditWidth, nSubEditHeight)) };
}

bool lcl_isSpinButtonPart(ControlPart ePart)
{
    return ePart == ControlPart::ButtonUp || ePart == ControlPart::ButtonDown
           || ePart == ControlPart::ButtonLeft || ePart == ControlPart::ButtonRight;
}

std::shared_ptr<WidgetDefinition> getWidgetDefinition(OUString const& rDefinitionFile,
                                                      OUString const& rDefinitionResourcesPath,
                                                      OString const& rColorScheme)
{
    auto pWidgetDefinition = std::make_shared<WidgetDefinition>();
    WidgetDefinitionReader aReader(rDefinitionFile, rDefinitionResourcesPath, rColorScheme);
    if (aReader.read(*pWidgetDefinition))
        return pWidgetDefinition;
    return std::shared_ptr<WidgetDefinition>();
}

bool lcl_isSafeThemeName(std::string_view rThemeName)
{
    return !rThemeName.empty()
           && std::all_of(rThemeName.begin(), rThemeName.end(),
                          [](unsigned char c)
                          {
                              return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                                     || (c >= '0' && c <= '9') || c == '-' || c == '_';
                          });
}

OUString lcl_getRequestedThemeName()
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName)
        return u"online"_ustr;

    const std::string_view aThemeName(pThemeName);
    if (!lcl_isSafeThemeName(aThemeName))
    {
        SAL_WARN("vcl.gdi", "Ignoring unsafe VCL_FILE_WIDGET_THEME value");
        return u"online"_ustr;
    }

    return OUString::fromUtf8(aThemeName);
}

std::shared_ptr<WidgetDefinition> getWidgetDefinitionForTheme(std::u16string_view rThemeName,
                                                              OString const& rColorScheme)
{
    static std::mutex aDefinitionsMutex;
    static std::map<OUString, std::map<OString, std::shared_ptr<WidgetDefinition>>> aDefinitions;

    const OUString aThemeName(rThemeName);
    std::scoped_lock aGuard(aDefinitionsMutex);
    auto& rThemeDefinitions = aDefinitions[aThemeName];
    const auto aExisting = rThemeDefinitions.find(rColorScheme);
    if (aExisting != rThemeDefinitions.end())
        return aExisting->second;

    OUString sSharedDefinitionBasePath = lcl_getThemeDefinitionPath();
    OUString sThemeFolder = sSharedDefinitionBasePath + aThemeName + "/";
    OUString sThemeDefinitionFile = sThemeFolder + "definition.xml";
    std::shared_ptr<WidgetDefinition> pDefinition;
    if (lcl_directoryExists(sThemeFolder) && lcl_fileExists(sThemeDefinitionFile))
        pDefinition = getWidgetDefinition(sThemeDefinitionFile, sThemeFolder, rColorScheme);

    // A transient packaging or deployment failure must not poison the cache.
    if (pDefinition)
        rThemeDefinitions.emplace(rColorScheme, pDefinition);
    return pDefinition;
}

std::shared_ptr<WidgetDefinition> selectWidgetDefinition(OUString const& rRequestedTheme,
                                                         OString const& rColorScheme,
                                                         OUString& rResolvedTheme)
{
    std::shared_ptr<WidgetDefinition> pDefinition
        = getWidgetDefinitionForTheme(rRequestedTheme, rColorScheme);
    rResolvedTheme = rRequestedTheme;

    if (!pDefinition && rRequestedTheme != u"online")
    {
        pDefinition = getWidgetDefinitionForTheme(u"online", rColorScheme);
        rResolvedTheme = u"online"_ustr;
    }
#ifdef IOS
    if (!pDefinition)
    {
        pDefinition = getWidgetDefinitionForTheme(u"ios", rColorScheme);
        rResolvedTheme = u"ios"_ustr;
    }
#endif
    return pDefinition;
}

std::shared_ptr<FileDefinitionThemeState>
getFileDefinitionThemeState(OUString const& rRequestedTheme)
{
    static std::mutex aThemeStatesMutex;
    static std::map<OUString, std::shared_ptr<FileDefinitionThemeState>> aThemeStates;

    std::scoped_lock aGuard(aThemeStatesMutex);
    auto [aIterator, bInserted] = aThemeStates.try_emplace(rRequestedTheme, nullptr);
    if (bInserted)
        aIterator->second = std::make_shared<FileDefinitionThemeState>(rRequestedTheme);
    return aIterator->second;
}

int getSettingValueInteger(std::string_view rValue, int nDefault)
{
    if (rValue.empty())
        return nDefault;
    if (!comphelper::string::isdigitAsciiString(rValue))
        return nDefault;
    return o3tl::toInt32(rValue);
}

bool getSettingValueBool(std::string_view rValue, bool bDefault)
{
    if (rValue.empty())
        return bDefault;
    if (rValue == "true" || rValue == "false")
        return rValue == "true";
    return bDefault;
}

vcl::Font withMinimumFontHeight(const vcl::Font& rNative, tools::Long nMinimumHeight)
{
    vcl::Font aFont(rNative);
    if (nMinimumHeight > 0 && aFont.GetFontHeight() > 0 && aFont.GetFontHeight() < nMinimumHeight)
    {
        aFont.SetFontHeight(nMinimumHeight);
    }
    return aFont;
}

void applyLegacyMinimumFontHeight(StyleSettings& rTarget, const StyleSettings& rNative,
                                  tools::Long nMinimumHeight)
{
    rTarget.SetAppFont(withMinimumFontHeight(rNative.GetAppFont(), nMinimumHeight));
    rTarget.SetHelpFont(withMinimumFontHeight(rNative.GetHelpFont(), nMinimumHeight));
    rTarget.SetFieldFont(withMinimumFontHeight(rNative.GetFieldFont(), nMinimumHeight));
    rTarget.SetMenuFont(withMinimumFontHeight(rNative.GetMenuFont(), nMinimumHeight));
    rTarget.SetToolFont(withMinimumFontHeight(rNative.GetToolFont(), nMinimumHeight));
    rTarget.SetGroupFont(withMinimumFontHeight(rNative.GetGroupFont(), nMinimumHeight));
    rTarget.SetLabelFont(withMinimumFontHeight(rNative.GetLabelFont(), nMinimumHeight));
    rTarget.SetRadioCheckFont(withMinimumFontHeight(rNative.GetRadioCheckFont(), nMinimumHeight));
    rTarget.SetPushButtonFont(withMinimumFontHeight(rNative.GetPushButtonFont(), nMinimumHeight));
    rTarget.SetTabFont(withMinimumFontHeight(rNative.GetTabFont(), nMinimumHeight));
    rTarget.SetTitleFont(withMinimumFontHeight(rNative.GetTitleFont(), nMinimumHeight));
    rTarget.SetFloatTitleFont(withMinimumFontHeight(rNative.GetFloatTitleFont(), nMinimumHeight));
}

struct NativeWidgetFrameworkBaseline
{
    bool mbCaptured = false;
    bool mbNoFocusRects = false;
    bool mbNoFocusRectsForFlatButtons = false;
    bool mbNoActiveTabTextRaise = false;
    bool mbCenteredTabs = false;
    bool mbProgressNeedsErase = false;
    int mnStatusBarLowerRightOffset = 0;
    bool mbCanDrawWidgetAnySize = false;
    int mnListBoxEntryMargin = 0;
    int mnMenuFormatBorderX = 0;
    int mnMenuFormatBorderY = 0;
    int mnMenuBarHeight = 0;
    int mnMenuItemHeight = 0;
    int mnMenuPopupMinWidth = 0;
    int mnMenuAccelColumnGap = 0;
};

void updateNativeWidgetFrameworkSettings(const std::shared_ptr<WidgetDefinition>& pDefinition)
{
    static std::mutex aBaselineMutex;
    static NativeWidgetFrameworkBaseline aBaseline;
    std::scoped_lock aGuard(aBaselineMutex);

    ImplSVData* pSVData = ImplGetSVData();
    auto& rNWFData = pSVData->maNWFData;
    if (!pDefinition)
    {
        if (!aBaseline.mbCaptured)
            return;

        rNWFData.mbNoFocusRects = aBaseline.mbNoFocusRects;
        rNWFData.mbNoFocusRectsForFlatButtons = aBaseline.mbNoFocusRectsForFlatButtons;
        rNWFData.mbNoActiveTabTextRaise = aBaseline.mbNoActiveTabTextRaise;
        rNWFData.mbCenteredTabs = aBaseline.mbCenteredTabs;
        rNWFData.mbProgressNeedsErase = aBaseline.mbProgressNeedsErase;
        rNWFData.mnStatusBarLowerRightOffset = aBaseline.mnStatusBarLowerRightOffset;
        rNWFData.mbCanDrawWidgetAnySize = aBaseline.mbCanDrawWidgetAnySize;
        rNWFData.mnListBoxEntryMargin = aBaseline.mnListBoxEntryMargin;
        rNWFData.mnMenuFormatBorderX = aBaseline.mnMenuFormatBorderX;
        rNWFData.mnMenuFormatBorderY = aBaseline.mnMenuFormatBorderY;
        rNWFData.mnMenuBarHeight = aBaseline.mnMenuBarHeight;
        rNWFData.mnMenuItemHeight = aBaseline.mnMenuItemHeight;
        rNWFData.mnMenuPopupMinWidth = aBaseline.mnMenuPopupMinWidth;
        rNWFData.mnMenuAccelColumnGap = aBaseline.mnMenuAccelColumnGap;
        aBaseline.mbCaptured = false;
        return;
    }

    if (!aBaseline.mbCaptured)
    {
        aBaseline.mbNoFocusRects = rNWFData.mbNoFocusRects;
        aBaseline.mbNoFocusRectsForFlatButtons = rNWFData.mbNoFocusRectsForFlatButtons;
        aBaseline.mbNoActiveTabTextRaise = rNWFData.mbNoActiveTabTextRaise;
        aBaseline.mbCenteredTabs = rNWFData.mbCenteredTabs;
        aBaseline.mbProgressNeedsErase = rNWFData.mbProgressNeedsErase;
        aBaseline.mnStatusBarLowerRightOffset = rNWFData.mnStatusBarLowerRightOffset;
        aBaseline.mbCanDrawWidgetAnySize = rNWFData.mbCanDrawWidgetAnySize;
        aBaseline.mnListBoxEntryMargin = rNWFData.mnListBoxEntryMargin;
        aBaseline.mnMenuFormatBorderX = rNWFData.mnMenuFormatBorderX;
        aBaseline.mnMenuFormatBorderY = rNWFData.mnMenuFormatBorderY;
        aBaseline.mnMenuBarHeight = rNWFData.mnMenuBarHeight;
        aBaseline.mnMenuItemHeight = rNWFData.mnMenuItemHeight;
        aBaseline.mnMenuPopupMinWidth = rNWFData.mnMenuPopupMinWidth;
        aBaseline.mnMenuAccelColumnGap = rNWFData.mnMenuAccelColumnGap;
        aBaseline.mbCaptured = true;
    }

    auto const& pSettings = pDefinition->mpSettings;
    rNWFData.mbNoFocusRects = true;
    rNWFData.mbNoFocusRectsForFlatButtons = true;
    rNWFData.mbNoActiveTabTextRaise = getSettingValueBool(pSettings->msNoActiveTabTextRaise, true);
    rNWFData.mbCenteredTabs = getSettingValueBool(pSettings->msCenteredTabs, true);
    rNWFData.mbProgressNeedsErase = true;
    rNWFData.mnStatusBarLowerRightOffset = 10;
    rNWFData.mbCanDrawWidgetAnySize = true;
    rNWFData.mnListBoxEntryMargin
        = getSettingValueInteger(pSettings->msListBoxEntryMargin, aBaseline.mnListBoxEntryMargin);

    // Material menu composition metrics (docs/design/05-navigation.md 1.1/1.5): the drop-menu
    // inner border, the menubar band / command-row minimum heights, the drop-menu minimum width and
    // the accelerator-column gap. These feed the generic (cross-platform) Menu::ImplCalcSize layout
    // only while the Material file-definition theme is live; the baseline restore above returns the
    // platform values so non-Material rendering paths are never touched.
    rNWFData.mnMenuFormatBorderX
        = getSettingValueInteger(pSettings->msMenuInnerBorder, aBaseline.mnMenuFormatBorderX);
    rNWFData.mnMenuFormatBorderY
        = getSettingValueInteger(pSettings->msMenuInnerBorder, aBaseline.mnMenuFormatBorderY);
    rNWFData.mnMenuBarHeight
        = getSettingValueInteger(pSettings->msMenuBarHeight, aBaseline.mnMenuBarHeight);
    rNWFData.mnMenuItemHeight
        = getSettingValueInteger(pSettings->msMenuItemHeight, aBaseline.mnMenuItemHeight);
    rNWFData.mnMenuPopupMinWidth
        = getSettingValueInteger(pSettings->msMenuPopupMinWidth, aBaseline.mnMenuPopupMinWidth);
    rNWFData.mnMenuAccelColumnGap
        = getSettingValueInteger(pSettings->msMenuAccelColumnGap, aBaseline.mnMenuAccelColumnGap);
}

tools::Long getLevelBarStateValue(tools::Long nValue, tools::Long nFullWidth)
{
    if (nValue <= 0 || nFullWidth <= 0)
        return 0;

    const tools::Long nClampedValue = std::min(nValue, nFullWidth);
    const tools::Long nQuarter = nFullWidth / 4 + (nFullWidth % 4 != 0);
    const tools::Long nHalf = nFullWidth / 2 + (nFullWidth % 2 != 0);
    const tools::Long nThreeQuarters = nFullWidth - nFullWidth / 4;

    if (nClampedValue < nQuarter)
        return 0;
    if (nClampedValue < nHalf)
        return 2500;
    if (nClampedValue < nThreeQuarters)
        return 5000;
    return 7500;
}

} // end anonymous namespace

FileDefinitionWidgetDraw::FileDefinitionWidgetDraw(SalGraphics& rGraphics)
    : m_rGraphics(rGraphics)
    , m_bIsActive(false)
{
    const OUString aRequestedTheme = lcl_getRequestedThemeName();
    m_pThemeState = getFileDefinitionThemeState(aRequestedTheme);

    std::scoped_lock aGuard(m_pThemeState->maMutex);
    if (!m_pThemeState->mpDefinition)
    {
        m_pThemeState->mpDefinition
            = selectWidgetDefinition(aRequestedTheme, OString(), m_pThemeState->maResolvedTheme);
        m_pThemeState->maColorScheme.clear();
    }
    m_bIsActive = bool(m_pThemeState->mpDefinition);
}

std::shared_ptr<WidgetDefinition> FileDefinitionWidgetDraw::getWidgetDefinition() const
{
    std::scoped_lock aGuard(m_pThemeState->maMutex);
    return m_pThemeState->mpDefinition;
}

bool FileDefinitionWidgetDraw::usesNativeFallback() const
{
    std::scoped_lock aGuard(m_pThemeState->maMutex);
    return m_pThemeState->mbHighContrast;
}

bool FileDefinitionWidgetDraw::isNativeControlSupported(ControlType eType, ControlPart ePart)
{
    if (usesNativeFallback())
        return m_rGraphics.IsNativeControlSupportedNative(eType, ePart);

    const auto pWidgetDefinition = getWidgetDefinition();
    if (!pWidgetDefinition)
        return false;

    if (eType == ControlType::Generic || eType == ControlType::IntroProgress)
        return false;

    if ((eType == ControlType::Combobox || eType == ControlType::Listbox)
        && ePart == ControlPart::HasBackgroundTexture)
        return false;

    // ComboBox border drawing suppresses the child drop-down button because
    // native themes are expected to paint the composite in the Entire call.
    if (eType == ControlType::Combobox && ePart == ControlPart::Entire)
        return pWidgetDefinition->getDefinition(eType, ControlPart::Entire)
               && pWidgetDefinition->getDefinition(eType, ControlPart::ButtonDown);

    if (eType == ControlType::SpinButtons)
    {
        if (ePart == ControlPart::Entire || ePart == ControlPart::AllButtons)
        {
            return pWidgetDefinition->getDefinition(eType, ControlPart::ButtonUp)
                   && pWidgetDefinition->getDefinition(eType, ControlPart::ButtonDown)
                   && pWidgetDefinition->getDefinition(eType, ControlPart::ButtonLeft)
                   && pWidgetDefinition->getDefinition(eType, ControlPart::ButtonRight);
        }
        return false;
    }

    if (eType == ControlType::Spinbox && ePart == ControlPart::AllButtons)
        return false;

    if (eType == ControlType::Scrollbar
        && (ePart == ControlPart::DrawBackgroundHorz || ePart == ControlPart::DrawBackgroundVert))
        return false;

    if (eType == ControlType::Slider)
    {
        const bool bHasThumb = bool(pWidgetDefinition->getDefinition(eType, ControlPart::Button));
        if (ePart == ControlPart::TrackHorzArea)
            return bHasThumb && pWidgetDefinition->getDefinition(eType, ControlPart::TrackHorzLeft)
                   && pWidgetDefinition->getDefinition(eType, ControlPart::TrackHorzRight);
        if (ePart == ControlPart::TrackVertArea)
            return bHasThumb && pWidgetDefinition->getDefinition(eType, ControlPart::TrackVertUpper)
                   && pWidgetDefinition->getDefinition(eType, ControlPart::TrackVertLower);
        return false;
    }

    // A file theme must not claim a part it cannot draw. Several VCL callers
    // choose their generic fallback solely from this answer and do not retry
    // after drawNativeControl() returns false.
    return bool(pWidgetDefinition->getDefinition(eType, ePart));
}

bool FileDefinitionWidgetDraw::hitTestNativeControl(ControlType eType, ControlPart ePart,
                                                    const tools::Rectangle& rBoundingControlRegion,
                                                    const Point& rPos, bool& rIsInside)
{
    if (usesNativeFallback())
    {
        return m_rGraphics.HitTestNativeControlNative(eType, ePart, rBoundingControlRegion, rPos,
                                                      rIsInside);
    }
    return false;
}

void FileDefinitionWidgetDraw::drawPolyPolygon(SalGraphics& rGraphics,
                                               const basegfx::B2DHomMatrix& rObjectToDevice,
                                               const basegfx::B2DPolyPolygon& i_rPolyPolygon,
                                               double i_fTransparency)
{
    rGraphics.drawPolyPolygon(rObjectToDevice, i_rPolyPolygon, i_fTransparency);
}

void FileDefinitionWidgetDraw::drawPolyLine(
    SalGraphics& rGraphics, const basegfx::B2DHomMatrix& rObjectToDevice,
    const basegfx::B2DPolygon& i_rPolygon, double i_fTransparency, double i_fLineWidth,
    const std::vector<double>* i_pStroke, basegfx::B2DLineJoin i_eLineJoin,
    css::drawing::LineCap i_eLineCap, double i_fMiterMinimumAngle, bool bPixelSnapHairline)
{
    rGraphics.drawPolyLine(rObjectToDevice, i_rPolygon, i_fTransparency, i_fLineWidth, i_pStroke,
                           i_eLineJoin, i_eLineCap, i_fMiterMinimumAngle, bPixelSnapHairline);
}

void FileDefinitionWidgetDraw::drawBitmap(SalGraphics& rGraphics, const SalTwoRect& rPosAry,
                                          const SalBitmap& rSalBitmap)
{
    rGraphics.drawBitmap(rPosAry, rSalBitmap);
}

void FileDefinitionWidgetDraw::implDrawGradient(SalGraphics& rGraphics,
                                                const basegfx::B2DPolyPolygon& rPolyPolygon,
                                                const SalGradient& rGradient)
{
    rGraphics.implDrawGradient(rPolyPolygon, rGradient);
}

namespace
{
void drawFromDrawCommands(gfx::DrawRoot const& rDrawRoot, SalGraphics& rGraphics, tools::Long nX,
                          tools::Long nY, tools::Long nWidth, tools::Long nHeight)
{
    basegfx::B2DRectangle aSVGRect = rDrawRoot.maRectangle;

    basegfx::B2DRange aTargetSurface(nX, nY, nX + nWidth + 1, nY + nHeight + 1);

    for (std::shared_ptr<gfx::DrawBase> const& pDrawBase : rDrawRoot.maChildren)
    {
        switch (pDrawBase->getType())
        {
            case gfx::DrawCommandType::Rectangle:
            {
                auto const& rRectangle = static_cast<gfx::DrawRectangle const&>(*pDrawBase);

                basegfx::B2DRange aInputRectangle(rRectangle.maRectangle);

                double fDeltaX = aTargetSurface.getWidth() - aSVGRect.getWidth();
                double fDeltaY = aTargetSurface.getHeight() - aSVGRect.getHeight();

                basegfx::B2DRange aFinalRectangle(
                    aInputRectangle.getMinX(), aInputRectangle.getMinY(),
                    aInputRectangle.getMaxX() + fDeltaX, aInputRectangle.getMaxY() + fDeltaY);

                aFinalRectangle.translate(aTargetSurface.getMinX() - 0.5,
                                          aTargetSurface.getMinY() - 0.5);

                basegfx::B2DPolygon aB2DPolygon = basegfx::utils::createPolygonFromRect(
                    aFinalRectangle, rRectangle.mnRx / aFinalRectangle.getWidth() * 2.0,
                    rRectangle.mnRy / aFinalRectangle.getHeight() * 2.0);

                if (rRectangle.mpFillColor)
                {
                    rGraphics.SetLineColor();
                    rGraphics.SetFillColor(Color(*rRectangle.mpFillColor));
                    FileDefinitionWidgetDraw::drawPolyPolygon(rGraphics, basegfx::B2DHomMatrix(),
                                                              basegfx::B2DPolyPolygon(aB2DPolygon),
                                                              1.0 - rRectangle.mnOpacity);
                }
                else if (rRectangle.mpFillGradient)
                {
                    rGraphics.SetLineColor();
                    rGraphics.SetFillColor();
                    if (rRectangle.mpFillGradient->meType == gfx::GradientType::Linear)
                    {
                        auto* pLinearGradient = static_cast<gfx::LinearGradientInfo*>(
                            rRectangle.mpFillGradient.get());
                        SalGradient aGradient;
                        double x, y;

                        x = pLinearGradient->x1;
                        y = pLinearGradient->y1;

                        if (x > aSVGRect.getCenterX())
                            x = x + fDeltaX;
                        if (y > aSVGRect.getCenterY())
                            y = y + fDeltaY;

                        aGradient.maPoint1 = basegfx::B2DPoint(x + aTargetSurface.getMinX() - 0.5,
                                                               y + aTargetSurface.getMinY() - 0.5);

                        x = pLinearGradient->x2;
                        y = pLinearGradient->y2;

                        if (x > aSVGRect.getCenterX())
                            x = x + fDeltaX;
                        if (y > aSVGRect.getCenterY())
                            y = y + fDeltaY;

                        aGradient.maPoint2 = basegfx::B2DPoint(x + aTargetSurface.getMinX() - 0.5,
                                                               y + aTargetSurface.getMinY() - 0.5);

                        for (gfx::GradientStop const& rStop : pLinearGradient->maGradientStops)
                        {
                            Color aColor(rStop.maColor);
                            aColor.SetAlpha(255
                                            - (rStop.mfOpacity * (1.0f - rRectangle.mnOpacity)));
                            aGradient.maStops.emplace_back(aColor, rStop.mfOffset);
                        }
                        FileDefinitionWidgetDraw::implDrawGradient(
                            rGraphics, basegfx::B2DPolyPolygon(aB2DPolygon), aGradient);
                    }
                }
                if (rRectangle.mpStrokeColor)
                {
                    rGraphics.SetLineColor(Color(*rRectangle.mpStrokeColor));
                    rGraphics.SetFillColor();
                    FileDefinitionWidgetDraw::drawPolyLine(
                        rGraphics, basegfx::B2DHomMatrix(), aB2DPolygon, 1.0 - rRectangle.mnOpacity,
                        rRectangle.mnStrokeWidth,
                        nullptr, // MM01
                        basegfx::B2DLineJoin::Round, css::drawing::LineCap_ROUND, 0.0f, false);
                }
            }
            break;
            case gfx::DrawCommandType::Path:
            {
                auto const& rPath = static_cast<gfx::DrawPath const&>(*pDrawBase);

                double fDeltaX = aTargetSurface.getWidth() - aSVGRect.getWidth();
                double fDeltaY = aTargetSurface.getHeight() - aSVGRect.getHeight();

                basegfx::B2DPolyPolygon aPolyPolygon(rPath.maPolyPolygon);
                for (auto& rPolygon : aPolyPolygon)
                {
                    for (size_t i = 0; i < rPolygon.count(); ++i)
                    {
                        auto& rPoint = rPolygon.getB2DPoint(i);
                        double x = rPoint.getX();
                        double y = rPoint.getY();

                        if (x > aSVGRect.getCenterX())
                            x = x + fDeltaX;
                        if (y > aSVGRect.getCenterY())
                            y = y + fDeltaY;
                        rPolygon.setB2DPoint(i, basegfx::B2DPoint(x, y));
                    }
                }
                aPolyPolygon.translate(aTargetSurface.getMinX() - 0.5,
                                       aTargetSurface.getMinY() - 0.5);

                if (rPath.mpFillColor)
                {
                    rGraphics.SetLineColor();
                    rGraphics.SetFillColor(Color(*rPath.mpFillColor));
                    FileDefinitionWidgetDraw::drawPolyPolygon(rGraphics, basegfx::B2DHomMatrix(),
                                                              aPolyPolygon, 1.0 - rPath.mnOpacity);
                }
                if (rPath.mpStrokeColor)
                {
                    rGraphics.SetLineColor(Color(*rPath.mpStrokeColor));
                    rGraphics.SetFillColor();
                    for (auto const& rPolygon : std::as_const(aPolyPolygon))
                    {
                        FileDefinitionWidgetDraw::drawPolyLine(
                            rGraphics, basegfx::B2DHomMatrix(), rPolygon, 1.0 - rPath.mnOpacity,
                            rPath.mnStrokeWidth,
                            nullptr, // MM01
                            basegfx::B2DLineJoin::Round, css::drawing::LineCap_ROUND, 0.0f, false);
                    }
                }
            }
            break;

            default:
                break;
        }
    }
}

void munchDrawCommands(std::vector<std::shared_ptr<WidgetDrawAction>> const& rDrawActions,
                       SalGraphics& rGraphics, tools::Long nX, tools::Long nY, tools::Long nWidth,
                       tools::Long nHeight)
{
    for (std::shared_ptr<WidgetDrawAction> const& pDrawAction : rDrawActions)
    {
        switch (pDrawAction->maType)
        {
            case WidgetDrawActionType::RECTANGLE:
            {
                auto const& rWidgetDraw
                    = static_cast<WidgetDrawActionRectangle const&>(*pDrawAction);

                basegfx::B2DRectangle rRect(
                    nX + (nWidth * rWidgetDraw.mfX1), nY + (nHeight * rWidgetDraw.mfY1),
                    nX + (nWidth * rWidgetDraw.mfX2), nY + (nHeight * rWidgetDraw.mfY2));

                basegfx::B2DPolygon aB2DPolygon = basegfx::utils::createPolygonFromRect(
                    rRect, rWidgetDraw.mnRx / rRect.getWidth() * 2.0,
                    rWidgetDraw.mnRy / rRect.getHeight() * 2.0);

                rGraphics.SetLineColor();
                rGraphics.SetFillColor(rWidgetDraw.maFillColor);
                FileDefinitionWidgetDraw::drawPolyPolygon(
                    rGraphics, basegfx::B2DHomMatrix(), basegfx::B2DPolyPolygon(aB2DPolygon), 0.0f);
                rGraphics.SetLineColor(rWidgetDraw.maStrokeColor);
                rGraphics.SetFillColor();
                FileDefinitionWidgetDraw::drawPolyLine(
                    rGraphics, basegfx::B2DHomMatrix(), aB2DPolygon, 0.0f,
                    rWidgetDraw.mnStrokeWidth, nullptr, // MM01
                    basegfx::B2DLineJoin::Round, css::drawing::LineCap_ROUND, 0.0f, false);
            }
            break;
            case WidgetDrawActionType::LINE:
            {
                auto const& rWidgetDraw = static_cast<WidgetDrawActionLine const&>(*pDrawAction);
                Point aRectPoint(nX + 1, nY + 1);

                Size aRectSize(nWidth - 1, nHeight - 1);

                rGraphics.SetFillColor();
                rGraphics.SetLineColor(rWidgetDraw.maStrokeColor);

                basegfx::B2DPolygon aB2DPolygon{
                    { aRectPoint.X() + (aRectSize.Width() * rWidgetDraw.mfX1),
                      aRectPoint.Y() + (aRectSize.Height() * rWidgetDraw.mfY1) },
                    { aRectPoint.X() + (aRectSize.Width() * rWidgetDraw.mfX2),
                      aRectPoint.Y() + (aRectSize.Height() * rWidgetDraw.mfY2) },
                };

                FileDefinitionWidgetDraw::drawPolyLine(
                    rGraphics, basegfx::B2DHomMatrix(), aB2DPolygon, 0.0f,
                    rWidgetDraw.mnStrokeWidth, nullptr, // MM01
                    basegfx::B2DLineJoin::Round, css::drawing::LineCap_ROUND, 0.0f, false);
            }
            break;
            case WidgetDrawActionType::IMAGE:
            {
                double nScaleFactor = 1.0;
                if (comphelper::LibreOfficeKit::isActive())
                    nScaleFactor = comphelper::LibreOfficeKit::getDPIScale();

                auto const& rWidgetDraw = static_cast<WidgetDrawActionImage const&>(*pDrawAction);
                auto& rCacheImages = ImplGetSVData()->maGDIData.maThemeImageCache;
                OUString rCacheKey = rWidgetDraw.msSource + "@" + OUString::number(nScaleFactor);
                auto aIterator = rCacheImages.find(rCacheKey);

                Bitmap aBitmap;
                if (aIterator == rCacheImages.end())
                {
                    SvFileStream aFileStream(rWidgetDraw.msSource, StreamMode::READ);

                    vcl::bitmap::loadFromSvg(aFileStream, u""_ustr, aBitmap, nScaleFactor);
                    if (!aBitmap.IsEmpty())
                    {
                        rCacheImages.insert(std::make_pair(rCacheKey, aBitmap));
                    }
                }
                else
                {
                    aBitmap = aIterator->second;
                }

                tools::Long nImageWidth = aBitmap.GetSizePixel().Width();
                tools::Long nImageHeight = aBitmap.GetSizePixel().Height();
                SalTwoRect aTR(0, 0, nImageWidth, nImageHeight, nX, nY, nImageWidth / nScaleFactor,
                               nImageHeight / nScaleFactor);
                if (!aBitmap.IsEmpty())
                {
                    const std::shared_ptr<SalBitmap> pSalBitmap = aBitmap.ImplGetSalBitmap();
                    FileDefinitionWidgetDraw::drawBitmap(rGraphics, aTR, *pSalBitmap);
                }
            }
            break;
            case WidgetDrawActionType::EXTERNAL:
            {
                auto const& rWidgetDraw
                    = static_cast<WidgetDrawActionExternal const&>(*pDrawAction);

                auto& rCacheDrawCommands = ImplGetSVData()->maGDIData.maThemeDrawCommandsCache;

                auto aIterator = rCacheDrawCommands.find(rWidgetDraw.msSource);

                if (aIterator == rCacheDrawCommands.end())
                {
                    SvFileStream aFileStream(rWidgetDraw.msSource, StreamMode::READ);

                    const uno::Reference<uno::XComponentContext>& xContext(
                        comphelper::getProcessComponentContext());
                    const uno::Reference<graphic::XSvgParser> xSvgParser
                        = graphic::SvgTools::create(xContext);

                    std::size_t nSize = aFileStream.remainingSize();
                    std::vector<sal_Int8> aBuffer(nSize + 1);
                    aFileStream.ReadBytes(aBuffer.data(), nSize);
                    aBuffer[nSize] = 0;

                    uno::Sequence<sal_Int8> aData(aBuffer.data(), nSize + 1);
                    uno::Reference<io::XInputStream> aInputStream(
                        new comphelper::SequenceInputStream(aData));

                    uno::Any aAny = xSvgParser->getDrawCommands(aInputStream, u""_ustr);
                    if (aAny.has<sal_uInt64>())
                    {
                        auto* pDrawRoot = reinterpret_cast<gfx::DrawRoot*>(aAny.get<sal_uInt64>());
                        if (pDrawRoot)
                        {
                            rCacheDrawCommands.insert(
                                std::make_pair(rWidgetDraw.msSource, *pDrawRoot));
                            drawFromDrawCommands(*pDrawRoot, rGraphics, nX, nY, nWidth, nHeight);
                        }
                    }
                }
                else
                {
                    drawFromDrawCommands(aIterator->second, rGraphics, nX, nY, nWidth, nHeight);
                }
            }
            break;
        }
    }
}

} // end anonymous namespace

bool FileDefinitionWidgetDraw::resolveDefinition(ControlType eType, ControlPart ePart,
                                                 ControlState eState,
                                                 const ImplControlValue& rValue, tools::Long nX,
                                                 tools::Long nY, tools::Long nWidth,
                                                 tools::Long nHeight)
{
    bool bOK = false;
    const auto pWidgetDefinition = getWidgetDefinition();
    if (!pWidgetDefinition)
        return false;

    auto const pPart = pWidgetDefinition->getDefinition(eType, ePart);
    if (pPart)
    {
        auto const aStates = pPart->getStates(eType, ePart, eState, rValue);
        if (!aStates.empty())
        {
            // use last defined state
            auto const& pState = aStates.back();
            {
                munchDrawCommands(pState->mpWidgetDrawActions, m_rGraphics, nX, nY, nWidth,
                                  nHeight);
                bOK = true;
            }
        }
    }
    return bOK;
}

bool FileDefinitionWidgetDraw::drawNativeControl(ControlType eType, ControlPart ePart,
                                                 const tools::Rectangle& rControlRegion,
                                                 ControlState eState,
                                                 const ImplControlValue& rValue,
                                                 const OUString& rCaptions,
                                                 const Color& rBackgroundColor)
{
    if (usesNativeFallback())
    {
        return m_rGraphics.DrawNativeControlNative(eType, ePart, rControlRegion, eState, rValue,
                                                   rCaptions, rBackgroundColor);
    }

    const auto pWidgetDefinition = getWidgetDefinition();
    if (!pWidgetDefinition)
        return false;

    bool bOldAA = m_rGraphics.getAntiAlias();
    m_rGraphics.setAntiAlias(true);

    tools::Long nWidth = rControlRegion.GetWidth() - 1;
    tools::Long nHeight = rControlRegion.GetHeight() - 1;
    tools::Long nX = rControlRegion.Left();
    tools::Long nY = rControlRegion.Top();

    bool bOK = false;

    switch (eType)
    {
        case ControlType::Pushbutton:
        {
            /*bool bIsAction = false;
            const PushButtonValue* pPushButtonValue = static_cast<const PushButtonValue*>(&rValue);
            if (pPushButtonValue)
                bIsAction = pPushButtonValue->mbIsAction;*/

            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Radiobutton:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Checkbox:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Combobox:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
            if (bOK && ePart == ControlPart::Entire)
            {
                auto const pButton
                    = pWidgetDefinition->getDefinition(eType, ControlPart::ButtonDown);
                if (!pButton || pButton->mnWidth <= 0 || pButton->mnHeight <= 0)
                {
                    bOK = false;
                    break;
                }

                const bool bRtl = bool(m_rGraphics.GetLayout() & SalLayoutFlags::BiDiRtl);
                const ComboBoxPartRegions aRegions = lcl_getComboBoxPartRegions(
                    rControlRegion, Size(pButton->mnWidth, pButton->mnHeight), bRtl);
                bOK = resolveDefinition(eType, ControlPart::ButtonDown, eState, rValue,
                                        aRegions.maButton.Left(), aRegions.maButton.Top(),
                                        aRegions.maButton.GetWidth() - 1,
                                        aRegions.maButton.GetHeight() - 1);
            }
        }
        break;
        case ControlType::Editbox:
        case ControlType::EditboxNoBorder:
        case ControlType::MultilineEditbox:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Listbox:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Spinbox:
        {
            if (rValue.getType() == ControlType::SpinButtons)
            {
                const SpinbuttonValue* pSpinVal = static_cast<const SpinbuttonValue*>(&rValue);

                {
                    ControlPart eUpButtonPart = pSpinVal->mnUpperPart;
                    ControlState eUpButtonState = pSpinVal->mnUpperState;

                    tools::Long nUpperX = pSpinVal->maUpperRect.Left();
                    tools::Long nUpperY = pSpinVal->maUpperRect.Top();
                    tools::Long nUpperWidth = pSpinVal->maUpperRect.GetWidth() - 1;
                    tools::Long nUpperHeight = pSpinVal->maUpperRect.GetHeight() - 1;

                    bOK = resolveDefinition(eType, eUpButtonPart, eUpButtonState,
                                            ImplControlValue(), nUpperX, nUpperY, nUpperWidth,
                                            nUpperHeight);
                }

                if (bOK)
                {
                    ControlPart eDownButtonPart = pSpinVal->mnLowerPart;
                    ControlState eDownButtonState = pSpinVal->mnLowerState;

                    tools::Long nLowerX = pSpinVal->maLowerRect.Left();
                    tools::Long nLowerY = pSpinVal->maLowerRect.Top();
                    tools::Long nLowerWidth = pSpinVal->maLowerRect.GetWidth() - 1;
                    tools::Long nLowerHeight = pSpinVal->maLowerRect.GetHeight() - 1;

                    bOK = resolveDefinition(eType, eDownButtonPart, eDownButtonState,
                                            ImplControlValue(), nLowerX, nLowerY, nLowerWidth,
                                            nLowerHeight);
                }
            }
            else
            {
                bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
            }
        }
        break;
        case ControlType::SpinButtons:
        {
            if ((ePart != ControlPart::Entire && ePart != ControlPart::AllButtons)
                || rValue.getType() != ControlType::SpinButtons)
            {
                break;
            }

            const auto& rSpinValue = static_cast<const SpinbuttonValue&>(rValue);
            if (!lcl_isSpinButtonPart(rSpinValue.mnUpperPart)
                || !lcl_isSpinButtonPart(rSpinValue.mnLowerPart))
            {
                break;
            }

            const tools::Rectangle& rUpperRect = rSpinValue.maUpperRect;
            const tools::Rectangle& rLowerRect = rSpinValue.maLowerRect;
            if (rUpperRect.IsEmpty() || rLowerRect.IsEmpty())
                break;

            bOK = resolveDefinition(eType, rSpinValue.mnUpperPart, rSpinValue.mnUpperState,
                                    ImplControlValue(), rUpperRect.Left(), rUpperRect.Top(),
                                    rUpperRect.GetWidth() - 1, rUpperRect.GetHeight() - 1);
            if (bOK)
            {
                bOK = resolveDefinition(eType, rSpinValue.mnLowerPart, rSpinValue.mnLowerState,
                                        ImplControlValue(), rLowerRect.Left(), rLowerRect.Top(),
                                        rLowerRect.GetWidth() - 1, rLowerRect.GetHeight() - 1);
            }
        }
        break;
        case ControlType::TabItem:
        case ControlType::TabHeader:
        case ControlType::TabPane:
        case ControlType::TabBody:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Scrollbar:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Slider:
        {
            const SliderValue* pSliderValue = static_cast<const SliderValue*>(&rValue);
            tools::Long nThumbX = pSliderValue->maThumbRect.Left();
            tools::Long nThumbY = pSliderValue->maThumbRect.Top();
            tools::Long nThumbWidth = pSliderValue->maThumbRect.GetWidth() - 1;
            tools::Long nThumbHeight = pSliderValue->maThumbRect.GetHeight() - 1;

            if (ePart == ControlPart::TrackHorzArea)
            {
                tools::Long nCenterX = nThumbX + nThumbWidth / 2;

                bOK = resolveDefinition(eType, ControlPart::TrackHorzLeft, eState, rValue, nX, nY,
                                        nCenterX - nX, nHeight);
                if (bOK)
                    bOK = resolveDefinition(eType, ControlPart::TrackHorzRight, eState, rValue,
                                            nCenterX, nY, nX + nWidth - nCenterX, nHeight);
            }
            else if (ePart == ControlPart::TrackVertArea)
            {
                tools::Long nCenterY = nThumbY + nThumbHeight / 2;

                bOK = resolveDefinition(eType, ControlPart::TrackVertUpper, eState, rValue, nX, nY,
                                        nWidth, nCenterY - nY);
                if (bOK)
                    bOK = resolveDefinition(eType, ControlPart::TrackVertLower, eState, rValue, nX,
                                            nCenterY, nWidth, nY + nHeight - nCenterY);
            }

            if (bOK)
            {
                bOK = resolveDefinition(eType, ControlPart::Button,
                                        eState | pSliderValue->mnThumbState, rValue, nThumbX,
                                        nThumbY, nThumbWidth, nThumbHeight);
            }
        }
        break;
        case ControlType::Fixedline:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Toolbar:
        {
            if (ePart == ControlPart::ThumbHorz || ePart == ControlPart::ThumbVert)
            {
                if (rValue.getType() != ControlType::Toolbar)
                    break;
                auto const& rToolbarValue = static_cast<ToolbarValue const&>(rValue);
                if (rToolbarValue.maGripRect.IsEmpty())
                    break;
                bOK = resolveDefinition(
                    eType, ePart, eState, rValue, rToolbarValue.maGripRect.Left(),
                    rToolbarValue.maGripRect.Top(), rToolbarValue.maGripRect.GetWidth() - 1,
                    rToolbarValue.maGripRect.GetHeight() - 1);
            }
            else
            {
                bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
            }
        }
        break;
        case ControlType::Menubar:
        case ControlType::MenuPopup:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::Progress:
        case ControlType::LevelBar:
        {
            if (ePart != ControlPart::Entire)
            {
                bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
                break;
            }

            const tools::Long nDrawableWidth = std::max(nWidth, tools::Long(0));
            const auto pTrack = pWidgetDefinition->getDefinition(eType, ControlPart::TrackHorzArea);
            bOK = !pTrack
                  || resolveDefinition(eType, ControlPart::TrackHorzArea, eState, rValue, nX, nY,
                                       nDrawableWidth, nHeight);
            if (!bOK)
                break;

            const tools::Long nProgressWidth
                = std::clamp(rValue.getNumericVal(), tools::Long(0), nDrawableWidth);
            if (nProgressWidth == 0)
                break;

            if (eType == ControlType::LevelBar)
            {
                const ImplControlValue aLevelValue(
                    getLevelBarStateValue(rValue.getNumericVal(), rControlRegion.GetWidth()));
                bOK = resolveDefinition(eType, ePart, eState, aLevelValue, nX, nY, nProgressWidth,
                                        nHeight);
            }
            else
            {
                bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nProgressWidth,
                                        nHeight);
            }
        }
        break;
        case ControlType::IntroProgress:
            break;
        case ControlType::Tooltip:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::WindowBackground:
        case ControlType::Frame:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        case ControlType::ListNode:
        case ControlType::ListNet:
        case ControlType::ListHeader:
        {
            bOK = resolveDefinition(eType, ePart, eState, rValue, nX, nY, nWidth, nHeight);
        }
        break;
        default:
            break;
    }

    m_rGraphics.setAntiAlias(bOldAA);

    return bOK;
}

bool FileDefinitionWidgetDraw::getNativeControlRegion(
    ControlType eType, ControlPart ePart, const tools::Rectangle& rBoundingControlRegion,
    ControlState eState, const ImplControlValue& rValue, const OUString& rCaption,
    tools::Rectangle& rNativeBoundingRegion, tools::Rectangle& rNativeContentRegion)
{
    if (usesNativeFallback())
    {
        return m_rGraphics.GetNativeControlRegionNative(
            eType, ePart, rBoundingControlRegion, eState, rValue, rCaption, rNativeBoundingRegion,
            rNativeContentRegion);
    }

    const auto pWidgetDefinition = getWidgetDefinition();
    if (!pWidgetDefinition)
        return false;

    Point aLocation(rBoundingControlRegion.TopLeft());

    switch (eType)
    {
        case ControlType::Spinbox:
        {
            auto const pButtonUpPart
                = pWidgetDefinition->getDefinition(eType, ControlPart::ButtonUp);
            if (!pButtonUpPart)
                return false;
            Size aButtonSizeUp(pButtonUpPart->mnWidth, pButtonUpPart->mnHeight);

            auto const pButtonDownPart
                = pWidgetDefinition->getDefinition(eType, ControlPart::ButtonDown);
            if (!pButtonDownPart)
                return false;
            Size aButtonSizeDown(pButtonDownPart->mnWidth, pButtonDownPart->mnHeight);

            auto const pEntirePart = pWidgetDefinition->getDefinition(eType, ControlPart::Entire);
            if (!pEntirePart)
                return false;

            OString sOrientation = pEntirePart->msOrientation;

            if (sOrientation.isEmpty() || sOrientation == "stacked")
            {
                return false;
            }
            else if (sOrientation == "decrease-edit-increase")
            {
                if (ePart == ControlPart::ButtonUp)
                {
                    Point aPoint(aLocation.X() + rBoundingControlRegion.GetWidth()
                                     - aButtonSizeUp.Width(),
                                 aLocation.Y());
                    rNativeContentRegion = tools::Rectangle(aPoint, aButtonSizeUp);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::ButtonDown)
                {
                    rNativeContentRegion = tools::Rectangle(aLocation, aButtonSizeDown);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::SubEdit)
                {
                    Point aPoint(aLocation.X() + aButtonSizeDown.Width(), aLocation.Y());
                    Size aSize(rBoundingControlRegion.GetWidth()
                                   - (aButtonSizeDown.Width() + aButtonSizeUp.Width()),
                               std::max(aButtonSizeUp.Height(), aButtonSizeDown.Height()));
                    rNativeContentRegion = tools::Rectangle(aPoint, aSize);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::Entire)
                {
                    Size aSize(rBoundingControlRegion.GetWidth(),
                               std::max(aButtonSizeUp.Height(), aButtonSizeDown.Height()));
                    rNativeContentRegion = tools::Rectangle(aLocation, aSize);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
            }
            else if (sOrientation == "edit-decrease-increase")
            {
                if (ePart == ControlPart::ButtonUp)
                {
                    Point aPoint(aLocation.X() + rBoundingControlRegion.GetWidth()
                                     - aButtonSizeUp.Width(),
                                 aLocation.Y());
                    rNativeContentRegion = tools::Rectangle(aPoint, aButtonSizeUp);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::ButtonDown)
                {
                    Point aPoint(aLocation.X() + rBoundingControlRegion.GetWidth()
                                     - (aButtonSizeDown.Width() + aButtonSizeUp.Width()),
                                 aLocation.Y());
                    rNativeContentRegion = tools::Rectangle(aPoint, aButtonSizeDown);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::SubEdit)
                {
                    Size aSize(rBoundingControlRegion.GetWidth()
                                   - (aButtonSizeDown.Width() + aButtonSizeUp.Width()),
                               std::max(aButtonSizeUp.Height(), aButtonSizeDown.Height()));
                    rNativeContentRegion = tools::Rectangle(aLocation, aSize);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
                else if (ePart == ControlPart::Entire)
                {
                    Size aSize(rBoundingControlRegion.GetWidth(),
                               std::max(aButtonSizeUp.Height(), aButtonSizeDown.Height()));
                    rNativeContentRegion = tools::Rectangle(aLocation, aSize);
                    rNativeBoundingRegion = rNativeContentRegion;
                    return true;
                }
            }
        }
        break;
        case ControlType::Checkbox:
        case ControlType::Radiobutton:
        {
            auto const pPart = pWidgetDefinition->getDefinition(eType, ControlPart::Entire);
            if (!pPart)
                return false;

            Size aSize(pPart->mnWidth, pPart->mnHeight);
            rNativeContentRegion = tools::Rectangle(aLocation, aSize);
            rNativeBoundingRegion = rNativeContentRegion;
            return true;
        }
        case ControlType::TabItem:
        {
            auto const pPart = pWidgetDefinition->getDefinition(eType, ControlPart::Entire);
            if (!pPart)
                return false;

            tools::Long nWidth = std::max(rBoundingControlRegion.GetWidth() + pPart->mnMarginWidth,
                                          tools::Long(pPart->mnWidth));
            tools::Long nHeight
                = std::max(rBoundingControlRegion.GetHeight() + pPart->mnMarginHeight,
                           tools::Long(pPart->mnHeight));

            rNativeBoundingRegion = tools::Rectangle(aLocation, Size(nWidth, nHeight));
            rNativeContentRegion = rNativeBoundingRegion;
            return true;
        }
        case ControlType::Editbox:
        case ControlType::EditboxNoBorder:
        case ControlType::MultilineEditbox:
        {
            sal_Int32 nHeight = rBoundingControlRegion.GetHeight();

            auto const pPart = pWidgetDefinition->getDefinition(eType, ControlPart::Entire);
            if (!pPart)
                return false;
            nHeight = std::max(nHeight, pPart->mnHeight);

            Size aSize(rBoundingControlRegion.GetWidth(), nHeight);
            rNativeContentRegion = tools::Rectangle(aLocation, aSize);
            rNativeBoundingRegion = rNativeContentRegion;
            if (eType != ControlType::EditboxNoBorder)
                rNativeBoundingRegion.expand(2);
            return true;
        }
        break;
        case ControlType::Scrollbar:
        {
            if (ePart == ControlPart::ButtonUp || ePart == ControlPart::ButtonDown
                || ePart == ControlPart::ButtonLeft || ePart == ControlPart::ButtonRight)
            {
                rNativeContentRegion = tools::Rectangle(aLocation, Size(0, 0));
                rNativeBoundingRegion = rNativeContentRegion;
                return true;
            }
            else
            {
                rNativeBoundingRegion = rBoundingControlRegion;
                rNativeContentRegion = rNativeBoundingRegion;
                return true;
            }
        }
        break;
        case ControlType::Combobox:
        case ControlType::Listbox:
        {
            auto const pPart = pWidgetDefinition->getDefinition(eType, ControlPart::ButtonDown);
            if (!pPart || pPart->mnWidth <= 0 || pPart->mnHeight <= 0)
                return false;
            const bool bRtl = bool(m_rGraphics.GetLayout() & SalLayoutFlags::BiDiRtl);
            const ComboBoxPartRegions aRegions = lcl_getComboBoxPartRegions(
                rBoundingControlRegion, Size(pPart->mnWidth, pPart->mnHeight), bRtl);

            if (ePart == ControlPart::ButtonDown)
            {
                rNativeContentRegion = aRegions.maButton;
                rNativeBoundingRegion = rNativeContentRegion;
                return true;
            }
            else if (ePart == ControlPart::SubEdit)
            {
                rNativeContentRegion = aRegions.maSubEdit;
                rNativeBoundingRegion = rNativeContentRegion;
                return true;
            }
            else if (ePart == ControlPart::Entire)
            {
                Size aSize(rBoundingControlRegion.GetWidth(), pPart->mnHeight);
                rNativeContentRegion = tools::Rectangle(aLocation, aSize);
                rNativeBoundingRegion = rNativeContentRegion;
                rNativeBoundingRegion.expand(2);
                return true;
            }
        }
        break;
        case ControlType::MenuPopup:
        {
            if (ePart == ControlPart::MenuItemCheckMark || ePart == ControlPart::MenuItemRadioMark
                || ePart == ControlPart::SubmenuArrow)
            {
                auto const pPart = pWidgetDefinition->getDefinition(eType, ePart);
                if (!pPart || pPart->mnWidth <= 0 || pPart->mnHeight <= 0)
                    return false;

                rNativeContentRegion
                    = tools::Rectangle(aLocation, Size(pPart->mnWidth, pPart->mnHeight));
                rNativeBoundingRegion = rNativeContentRegion;
                return true;
            }
        }
        break;
        case ControlType::Slider:
            if (ePart == ControlPart::ThumbHorz || ePart == ControlPart::ThumbVert)
            {
                auto const pPart = pWidgetDefinition->getDefinition(eType, ControlPart::Button);
                if (!pPart)
                    return false;
                tools::Long const nWidth = pPart->mnWidth > 0 ? pPart->mnWidth : 28;
                tools::Long const nHeight = pPart->mnHeight > 0 ? pPart->mnHeight : 28;
                rNativeContentRegion = tools::Rectangle(aLocation, Size(nWidth, nHeight));
                rNativeBoundingRegion = rNativeContentRegion;
                return true;
            }
            break;
        case ControlType::Frame:
        {
            // The outlined Material frame decorates the given region in place:
            // the bounding region is drawn as-is, and the content region is
            // inset so grouped children sit inside the border instead of over
            // it. The 2px inset matches decoview's own DrawFrameStyle::Group
            // fallback so callers keep the same content geometry they expect
            // from the generic frame. decoview only issues the file-definition
            // Border draw when a native region is returned here.
            if (!pWidgetDefinition->getDefinition(eType, ControlPart::Border))
                return false;
            rNativeBoundingRegion = rBoundingControlRegion;
            rNativeContentRegion = rBoundingControlRegion;
            rNativeContentRegion.AdjustLeft(2);
            rNativeContentRegion.AdjustTop(2);
            rNativeContentRegion.AdjustRight(-2);
            rNativeContentRegion.AdjustBottom(-2);
            return true;
        }
        break;
        default:
            break;
    }

    return false;
}

bool FileDefinitionWidgetDraw::updateSettings(AllSettings& rSettings)
{
    return updateSettings(rSettings, MiscSettings::GetUseDarkMode());
}

void FileDefinitionWidgetDraw::restoreNativeSettings(AllSettings& rSettings) const
{
    std::scoped_lock aGuard(m_pThemeState->maMutex);
    if (m_pThemeState->moNativeStyle)
        rSettings.SetStyleSettings(*m_pThemeState->moNativeStyle);
}

void FileDefinitionWidgetDraw::captureNativeSettings(const AllSettings& rSettings)
{
    std::scoped_lock aGuard(m_pThemeState->maMutex);
    m_pThemeState->moNativeStyle = rSettings.GetStyleSettings();
}

bool FileDefinitionWidgetDraw::updateSettings(AllSettings& rSettings, bool bUseDarkMode)
{
    if (rSettings.GetStyleSettings().GetHighContrastMode())
    {
        {
            std::scoped_lock aGuard(m_pThemeState->maMutex);
            m_pThemeState->mbHighContrast = true;
        }
        updateNativeWidgetFrameworkSettings(nullptr);
        return false;
    }

    {
        std::scoped_lock aGuard(m_pThemeState->maMutex);
        // Window::ImplUpdateAllSettings normally captures the platform style
        // before this overlay runs. Keep direct graphics callers deterministic
        // too without exposing that capture hook outside VCL's private ABI.
        if (!m_pThemeState->moNativeStyle)
            m_pThemeState->moNativeStyle = rSettings.GetStyleSettings();
    }

    const OString aColorScheme = bUseDarkMode ? "dark"_ostr : OString();
    OUString aRequestedTheme;
    {
        std::scoped_lock aGuard(m_pThemeState->maMutex);
        aRequestedTheme = m_pThemeState->maRequestedTheme;
    }

    OUString aResolvedTheme;
    const auto pWidgetDefinition
        = selectWidgetDefinition(aRequestedTheme, aColorScheme, aResolvedTheme);
    {
        std::scoped_lock aGuard(m_pThemeState->maMutex);
        m_pThemeState->mpDefinition = pWidgetDefinition;
        m_pThemeState->maResolvedTheme = aResolvedTheme;
        m_pThemeState->maColorScheme = aColorScheme;
        m_pThemeState->mbHighContrast = false;
    }

    if (!pWidgetDefinition)
    {
        updateNativeWidgetFrameworkSettings(nullptr);
        return false;
    }

    updateNativeWidgetFrameworkSettings(pWidgetDefinition);
    StyleSettings aStyleSet = rSettings.GetStyleSettings();

    auto& pDefinitionStyle = pWidgetDefinition->mpStyle;

    aStyleSet.SetFaceColor(pDefinitionStyle->maFaceColor);
    aStyleSet.SetCheckedColor(pDefinitionStyle->maCheckedColor);
    aStyleSet.SetLightColor(pDefinitionStyle->maLightColor);
    aStyleSet.SetLightBorderColor(pDefinitionStyle->maLightBorderColor);
    aStyleSet.SetShadowColor(pDefinitionStyle->maShadowColor);
    aStyleSet.SetDarkShadowColor(pDefinitionStyle->maDarkShadowColor);
    if (pDefinitionStyle->moWarningColor)
        aStyleSet.SetWarningColor(*pDefinitionStyle->moWarningColor);
    if (pDefinitionStyle->moWarningTextColor)
        aStyleSet.SetWarningTextColor(*pDefinitionStyle->moWarningTextColor);
    if (pDefinitionStyle->moErrorColor)
        aStyleSet.SetErrorColor(*pDefinitionStyle->moErrorColor);
    if (pDefinitionStyle->moErrorTextColor)
        aStyleSet.SetErrorTextColor(*pDefinitionStyle->moErrorTextColor);
    aStyleSet.SetDefaultButtonTextColor(pDefinitionStyle->maDefaultButtonTextColor);
    aStyleSet.SetButtonTextColor(pDefinitionStyle->maButtonTextColor);
    aStyleSet.SetDefaultActionButtonTextColor(pDefinitionStyle->maDefaultActionButtonTextColor);
    aStyleSet.SetActionButtonTextColor(pDefinitionStyle->maActionButtonTextColor);
    aStyleSet.SetFlatButtonTextColor(pDefinitionStyle->maFlatButtonTextColor);
    aStyleSet.SetDefaultButtonRolloverTextColor(pDefinitionStyle->maDefaultButtonRolloverTextColor);
    aStyleSet.SetButtonRolloverTextColor(pDefinitionStyle->maButtonRolloverTextColor);
    aStyleSet.SetDefaultActionButtonRolloverTextColor(
        pDefinitionStyle->maDefaultActionButtonRolloverTextColor);
    aStyleSet.SetActionButtonRolloverTextColor(pDefinitionStyle->maActionButtonRolloverTextColor);
    aStyleSet.SetFlatButtonRolloverTextColor(pDefinitionStyle->maFlatButtonRolloverTextColor);
    aStyleSet.SetDefaultButtonPressedRolloverTextColor(
        pDefinitionStyle->maDefaultButtonPressedRolloverTextColor);
    aStyleSet.SetButtonPressedRolloverTextColor(pDefinitionStyle->maButtonPressedRolloverTextColor);
    aStyleSet.SetDefaultActionButtonPressedRolloverTextColor(
        pDefinitionStyle->maDefaultActionButtonPressedRolloverTextColor);
    aStyleSet.SetActionButtonPressedRolloverTextColor(
        pDefinitionStyle->maActionButtonPressedRolloverTextColor);
    aStyleSet.SetFlatButtonPressedRolloverTextColor(
        pDefinitionStyle->maFlatButtonPressedRolloverTextColor);
    aStyleSet.SetRadioCheckTextColor(pDefinitionStyle->maRadioCheckTextColor);
    aStyleSet.SetGroupTextColor(pDefinitionStyle->maGroupTextColor);
    aStyleSet.SetLabelTextColor(pDefinitionStyle->maLabelTextColor);
    aStyleSet.SetWindowColor(pDefinitionStyle->maWindowColor);
    aStyleSet.SetWindowTextColor(pDefinitionStyle->maWindowTextColor);
    aStyleSet.SetDialogColor(pDefinitionStyle->maDialogColor);
    aStyleSet.SetDialogTextColor(pDefinitionStyle->maDialogTextColor);
    aStyleSet.SetWorkspaceColor(pDefinitionStyle->maWorkspaceColor);
    aStyleSet.SetMonoColor(pDefinitionStyle->maMonoColor);
    aStyleSet.SetFieldColor(pDefinitionStyle->maFieldColor);
    aStyleSet.SetFieldTextColor(pDefinitionStyle->maFieldTextColor);
    aStyleSet.SetFieldRolloverTextColor(pDefinitionStyle->maFieldRolloverTextColor);
    aStyleSet.SetActiveColor(pDefinitionStyle->maActiveColor);
    aStyleSet.SetActiveTextColor(pDefinitionStyle->maActiveTextColor);
    aStyleSet.SetActiveBorderColor(pDefinitionStyle->maActiveBorderColor);
    aStyleSet.SetDeactiveColor(pDefinitionStyle->maDeactiveColor);
    aStyleSet.SetDeactiveTextColor(pDefinitionStyle->maDeactiveTextColor);
    aStyleSet.SetDeactiveBorderColor(pDefinitionStyle->maDeactiveBorderColor);
    if (pDefinitionStyle->moAccentColor)
        aStyleSet.SetAccentColor(*pDefinitionStyle->moAccentColor);
    aStyleSet.SetMenuColor(pDefinitionStyle->maMenuColor);
    aStyleSet.SetMenuBarColor(pDefinitionStyle->maMenuBarColor);
    aStyleSet.SetMenuBarRolloverColor(pDefinitionStyle->maMenuBarRolloverColor);
    aStyleSet.SetMenuBorderColor(pDefinitionStyle->maMenuBorderColor);
    aStyleSet.SetMenuTextColor(pDefinitionStyle->maMenuTextColor);
    aStyleSet.SetMenuBarTextColor(pDefinitionStyle->maMenuBarTextColor);
    aStyleSet.SetMenuBarRolloverTextColor(pDefinitionStyle->maMenuBarRolloverTextColor);
    aStyleSet.SetMenuBarHighlightTextColor(pDefinitionStyle->maMenuBarHighlightTextColor);
    aStyleSet.SetMenuHighlightColor(pDefinitionStyle->maMenuHighlightColor);
    aStyleSet.SetMenuHighlightTextColor(pDefinitionStyle->maMenuHighlightTextColor);
    if (pDefinitionStyle->moListBoxWindowBackgroundColor)
        aStyleSet.SetListBoxWindowBackgroundColor(
            *pDefinitionStyle->moListBoxWindowBackgroundColor);
    if (pDefinitionStyle->moListBoxWindowTextColor)
        aStyleSet.SetListBoxWindowTextColor(*pDefinitionStyle->moListBoxWindowTextColor);
    if (pDefinitionStyle->moListBoxWindowHighlightColor)
        aStyleSet.SetListBoxWindowHighlightColor(*pDefinitionStyle->moListBoxWindowHighlightColor);
    if (pDefinitionStyle->moListBoxWindowHighlightTextColor)
        aStyleSet.SetListBoxWindowHighlightTextColor(
            *pDefinitionStyle->moListBoxWindowHighlightTextColor);
    aStyleSet.SetHighlightColor(pDefinitionStyle->maHighlightColor);
    aStyleSet.SetHighlightTextColor(pDefinitionStyle->maHighlightTextColor);
    aStyleSet.SetActiveTabColor(pDefinitionStyle->maActiveTabColor);
    aStyleSet.SetInactiveTabColor(pDefinitionStyle->maInactiveTabColor);
    if (pDefinitionStyle->moAlternatingRowColor)
        aStyleSet.SetAlternatingRowColor(*pDefinitionStyle->moAlternatingRowColor);
    aStyleSet.SetTabTextColor(pDefinitionStyle->maTabTextColor);
    aStyleSet.SetTabRolloverTextColor(pDefinitionStyle->maTabRolloverTextColor);
    aStyleSet.SetTabHighlightTextColor(pDefinitionStyle->maTabHighlightTextColor);
    aStyleSet.SetDisableColor(pDefinitionStyle->maDisableColor);
    aStyleSet.SetHelpColor(pDefinitionStyle->maHelpColor);
    aStyleSet.SetHelpTextColor(pDefinitionStyle->maHelpTextColor);
    aStyleSet.SetLinkColor(pDefinitionStyle->maLinkColor);
    aStyleSet.SetVisitedLinkColor(pDefinitionStyle->maVisitedLinkColor);
    aStyleSet.SetToolTextColor(pDefinitionStyle->maToolTextColor);

    auto& pSettings = pWidgetDefinition->mpSettings;
    StyleSettings aNativeStyleSet = aStyleSet;
    {
        std::scoped_lock aGuard(m_pThemeState->maMutex);
        aNativeStyleSet = *m_pThemeState->moNativeStyle;
    }

    if (pWidgetDefinition->mpTypography)
        pWidgetDefinition->mpTypography->apply(aStyleSet, aNativeStyleSet);
    else if (!pSettings->msDefaultFontSize.isEmpty())
    {
        const int nMinimumFontHeight = getSettingValueInteger(pSettings->msDefaultFontSize, 0);
        applyLegacyMinimumFontHeight(aStyleSet, aNativeStyleSet, nMinimumFontHeight);
    }

    const sal_Int32 nTitleFontHeight = static_cast<sal_Int32>(std::clamp<tools::Long>(
        aStyleSet.GetTitleFont().GetFontHeight(), 0, std::numeric_limits<sal_Int32>::max()));
    const sal_Int32 nTitleHeight
        = getSettingValueInteger(pSettings->msTitleHeight, aStyleSet.GetTitleHeight());
    aStyleSet.SetTitleHeight(
        std::max({ nTitleHeight, aNativeStyleSet.GetTitleHeight(), nTitleFontHeight }));

    const sal_Int32 nFloatTitleFontHeight = static_cast<sal_Int32>(std::clamp<tools::Long>(
        aStyleSet.GetFloatTitleFont().GetFontHeight(), 0, std::numeric_limits<sal_Int32>::max()));
    const sal_Int32 nFloatTitleHeight
        = getSettingValueInteger(pSettings->msFloatTitleHeight, aStyleSet.GetFloatTitleHeight());
    aStyleSet.SetFloatTitleHeight(std::max(
        { nFloatTitleHeight, aNativeStyleSet.GetFloatTitleHeight(), nFloatTitleFontHeight }));

    int nLogicWidth = getSettingValueInteger(pSettings->msListBoxPreviewDefaultLogicWidth,
                                             15); // See vcl/source/app/settings.cxx
    int nLogicHeight = getSettingValueInteger(pSettings->msListBoxPreviewDefaultLogicHeight, 7);
    aStyleSet.SetListBoxPreviewDefaultLogicSize(Size(nLogicWidth, nLogicHeight));

    rSettings.SetStyleSettings(aStyleSet);

    return true;
}

} // end vcl namespace

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
