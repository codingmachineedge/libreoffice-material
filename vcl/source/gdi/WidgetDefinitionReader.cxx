/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#include <frozen/bits/defines.h>
#include <frozen/bits/elsa_std.h>
#include <frozen/unordered_map.h>

#include <algorithm>
#include <initializer_list>
#include <limits>
#include <map>
#include <optional>
#include <unordered_map>
#include <utility>

#include <widgetdraw/WidgetDefinitionReader.hxx>

#include <sal/config.h>
#include <sal/log.hxx>
#include <osl/file.hxx>
#include <tools/stream.hxx>
#include <o3tl/string_view.hxx>
#include <o3tl/numeric.hxx>

namespace vcl
{
namespace
{
bool lcl_fileExists(OUString const& sFilename)
{
    osl::File aFile(sFilename);
    osl::FileBase::RC eRC = aFile.open(osl_File_OpenFlag_Read);
    return osl::FileBase::E_None == eRC;
}

bool readSetting(OString const& rInputString, OString& rOutputString)
{
    if (!rInputString.isEmpty())
        rOutputString = rInputString;
    return true;
}

OString getValueOrAny(OString const& rInputString)
{
    if (rInputString.isEmpty())
        return "any"_ostr;
    return rInputString;
}

bool haveSameColorTokenNames(std::map<OString, Color> const& rFirst,
                             std::map<OString, Color> const& rSecond)
{
    if (rFirst.size() != rSecond.size())
        return false;

    auto aFirst = rFirst.begin();
    auto aSecond = rSecond.begin();
    while (aFirst != rFirst.end())
    {
        if (aFirst->first != aSecond->first)
            return false;
        ++aFirst;
        ++aSecond;
    }
    return true;
}

bool haveOnlyAttributes(tools::XmlWalker const& rWalker,
                        std::initializer_list<std::string_view> aAllowed)
{
    for (const OString& rAttribute : rWalker.attributeNames())
    {
        const std::string_view aAttribute(rAttribute.getStr(), rAttribute.getLength());
        if (std::find(aAllowed.begin(), aAllowed.end(), aAttribute) == aAllowed.end())
        {
            SAL_WARN("vcl.gdi", "Unsupported file-widget attribute: " << rAttribute);
            return false;
        }
    }
    return true;
}

std::optional<WidgetDefinitionFontWeight> xmlStringToTypographyWeight(std::string_view rWeight)
{
    if (rWeight == "preserve")
        return WidgetDefinitionFontWeight::Preserve;
    if (rWeight == "normal")
        return WidgetDefinitionFontWeight::Normal;
    if (rWeight == "medium")
        return WidgetDefinitionFontWeight::Medium;
    if (rWeight == "semibold")
        return WidgetDefinitionFontWeight::SemiBold;
    if (rWeight == "bold")
        return WidgetDefinitionFontWeight::Bold;
    return std::nullopt;
}

std::optional<sal_Int32> readTypographyScale(OString const& rScale)
{
    if (rScale.getLength() != 3)
        return std::nullopt;
    for (sal_Int32 i = 0; i < rScale.getLength(); ++i)
    {
        if (rScale[i] < '0' || rScale[i] > '9')
            return std::nullopt;
    }

    const sal_Int32 nScale = rScale.toInt32();
    if (nScale < 100 || nScale > 200)
        return std::nullopt;
    return nScale;
}

bool hasUnexpectedChildContent(tools::XmlWalker& rWalker)
{
    bool bHasContent = false;
    rWalker.children();
    while (rWalker.isValid())
    {
        if (!rWalker.isBlank() && !rWalker.isComment())
            bHasContent = true;
        rWalker.next();
    }
    rWalker.parent();
    return bHasContent;
}

bool isTokenName(OString const& rName)
{
    if (rName.isEmpty() || rName[0] < 'a' || rName[0] > 'z')
        return false;
    for (sal_Int32 i = 1; i < rName.getLength(); ++i)
    {
        const char c = rName[i];
        if ((c < 'a' || c > 'z') && (c < '0' || c > '9') && c != '-')
            return false;
    }
    return true;
}

std::optional<sal_Int32> readNonNegativeInteger(OString const& rValue)
{
    if (rValue.isEmpty() || (rValue.getLength() > 1 && rValue[0] == '0'))
        return std::nullopt;

    sal_Int64 nValue = 0;
    for (sal_Int32 i = 0; i < rValue.getLength(); ++i)
    {
        const char c = rValue[i];
        if (c < '0' || c > '9')
            return std::nullopt;
        nValue = nValue * 10 + (c - '0');
        if (nValue > std::numeric_limits<sal_Int32>::max())
            return std::nullopt;
    }
    return static_cast<sal_Int32>(nValue);
}

bool readShapeTokens(tools::XmlWalker& rWalker, std::map<OString, sal_Int32>& rRadiusTokens)
{
    bool bValid = true;
    if (!rWalker.attributeNames().empty())
    {
        SAL_WARN("vcl.gdi", "File-widget shapes section must not have attributes");
        bValid = false;
    }

    rWalker.children();
    while (rWalker.isValid())
    {
        if (!rWalker.isElement())
        {
            if (!rWalker.isBlank() && !rWalker.isComment())
            {
                SAL_WARN("vcl.gdi", "Unexpected content in file-widget shapes section");
                bValid = false;
            }
            rWalker.next();
            continue;
        }
        if (rWalker.name() != "radius")
        {
            SAL_WARN("vcl.gdi", "Unsupported file-widget shape element: " << rWalker.name());
            bValid = false;
            rWalker.next();
            continue;
        }

        const auto aAttributes = rWalker.attributeNames();
        if (aAttributes.size() != 2 || !haveOnlyAttributes(rWalker, { "name", "value" }))
        {
            SAL_WARN("vcl.gdi", "File-widget radius tokens require name and value");
            bValid = false;
        }

        const OString aName = rWalker.attribute("name"_ostr);
        const OString aValue = rWalker.attribute("value"_ostr);
        const auto nValue = readNonNegativeInteger(aValue);
        if (!isTokenName(aName) || !nValue)
        {
            SAL_WARN("vcl.gdi", "Invalid file-widget radius token: " << aName);
            bValid = false;
        }
        else if (!rRadiusTokens.emplace(aName, *nValue).second)
        {
            SAL_WARN("vcl.gdi", "Duplicate file-widget radius token: " << aName);
            bValid = false;
        }

        if (hasUnexpectedChildContent(rWalker))
        {
            SAL_WARN("vcl.gdi", "File-widget radius tokens must not have content");
            bValid = false;
        }
        rWalker.next();
    }
    rWalker.parent();

    if (rRadiusTokens.empty())
    {
        SAL_WARN("vcl.gdi", "Empty file-widget shapes section");
        bValid = false;
    }
    return bValid;
}

bool readMetricTokens(tools::XmlWalker& rWalker, std::map<OString, sal_Int32>& rMetricTokens)
{
    bool bValid = true;
    if (!rWalker.attributeNames().empty())
    {
        SAL_WARN("vcl.gdi", "File-widget metrics section must not have attributes");
        bValid = false;
    }

    rWalker.children();
    while (rWalker.isValid())
    {
        if (!rWalker.isElement())
        {
            if (!rWalker.isBlank() && !rWalker.isComment())
            {
                SAL_WARN("vcl.gdi", "Unexpected content in file-widget metrics section");
                bValid = false;
            }
            rWalker.next();
            continue;
        }
        if (rWalker.name() != "metric")
        {
            SAL_WARN("vcl.gdi", "Unsupported file-widget metric element: " << rWalker.name());
            bValid = false;
            rWalker.next();
            continue;
        }

        const auto aAttributes = rWalker.attributeNames();
        if (aAttributes.size() != 2 || !haveOnlyAttributes(rWalker, { "name", "value" }))
        {
            SAL_WARN("vcl.gdi", "File-widget metric tokens require name and value");
            bValid = false;
        }

        const OString aName = rWalker.attribute("name"_ostr);
        const OString aValue = rWalker.attribute("value"_ostr);
        const auto nValue = readNonNegativeInteger(aValue);
        if (!isTokenName(aName) || !nValue)
        {
            SAL_WARN("vcl.gdi", "Invalid file-widget metric token: " << aName);
            bValid = false;
        }
        else if (!rMetricTokens.emplace(aName, *nValue).second)
        {
            SAL_WARN("vcl.gdi", "Duplicate file-widget metric token: " << aName);
            bValid = false;
        }

        if (hasUnexpectedChildContent(rWalker))
        {
            SAL_WARN("vcl.gdi", "File-widget metric tokens must not have content");
            bValid = false;
        }
        rWalker.next();
    }
    rWalker.parent();

    if (rMetricTokens.empty())
    {
        SAL_WARN("vcl.gdi", "Empty file-widget metrics section");
        bValid = false;
    }
    return bValid;
}

bool readRadiusReference(OString const& rValue, const std::map<OString, sal_Int32>& rRadiusTokens,
                         sal_Int32& rRadius)
{
    if (!rValue.startsWith("@"))
    {
        SAL_WARN("vcl.gdi", "File-widget radius must reference a shape token: " << rValue);
        return false;
    }

    const auto aToken = rRadiusTokens.find(rValue.copy(1));
    if (aToken == rRadiusTokens.end())
    {
        SAL_WARN("vcl.gdi", "Unknown file-widget radius token: " << rValue);
        return false;
    }
    rRadius = aToken->second;
    return true;
}

bool readMetricReference(OString const& rValue, const std::map<OString, sal_Int32>& rMetricTokens,
                         sal_Int32& rMetric)
{
    if (!rValue.startsWith("@"))
    {
        rMetric = rValue.toInt32();
        return true;
    }

    const auto aToken = rMetricTokens.find(rValue.copy(1));
    if (aToken == rMetricTokens.end())
    {
        SAL_WARN("vcl.gdi", "Unknown file-widget metric token: " << rValue);
        return false;
    }
    rMetric = aToken->second;
    return true;
}

bool readMetricSetting(OString const& rValue, const std::map<OString, sal_Int32>& rMetricTokens,
                       OString& rSetting)
{
    if (!rValue.startsWith("@"))
        return readSetting(rValue, rSetting);

    sal_Int32 nMetric = 0;
    if (!readMetricReference(rValue, rMetricTokens, nMetric))
        return false;
    rSetting = OString::number(nMetric);
    return true;
}

bool readLiteralSetting(OString const& rValue, OString& rSetting)
{
    if (rValue.startsWith("@"))
    {
        SAL_WARN("vcl.gdi", "File-widget setting does not accept token references: " << rValue);
        return false;
    }
    return readSetting(rValue, rSetting);
}

bool readLegacyRadius(OString const& rValue, sal_Int32& rRadius)
{
    if (rValue.startsWith("@"))
    {
        SAL_WARN("vcl.gdi", "Legacy file-widget radius axes do not accept tokens: " << rValue);
        return false;
    }
    rRadius = rValue.toInt32();
    return true;
}

bool readDrawingCoordinate(OString const& rValue, float fDefault, float& rCoordinate)
{
    if (rValue.isEmpty())
    {
        rCoordinate = fDefault;
        return true;
    }
    if (rValue.startsWith("@"))
    {
        SAL_WARN("vcl.gdi", "File-widget drawing coordinates cannot reference tokens: " << rValue);
        return false;
    }
    rCoordinate = rValue.toFloat();
    return true;
}

bool readTypography(tools::XmlWalker& rWalker, WidgetDefinitionTypography& rTypography)
{
    bool bValid = true;
    if (!rWalker.attributeNames().empty())
    {
        SAL_WARN("vcl.gdi", "File-widget typography section must not have attributes");
        bValid = false;
    }

    bool bHasBody = false;
    bool bHasLabel = false;
    bool bHasTitle = false;

    rWalker.children();
    while (rWalker.isValid())
    {
        if (!rWalker.isElement())
        {
            if (!rWalker.isBlank() && !rWalker.isComment())
            {
                SAL_WARN("vcl.gdi", "Unexpected content in file-widget typography section");
                bValid = false;
            }
            rWalker.next();
            continue;
        }
        if (rWalker.name() != "role")
        {
            SAL_WARN("vcl.gdi", "Unsupported file-widget typography element: " << rWalker.name());
            bValid = false;
            rWalker.next();
            continue;
        }

        const auto aAttributes = rWalker.attributeNames();
        if (aAttributes.size() != 3 || !haveOnlyAttributes(rWalker, { "name", "scale", "weight" }))
        {
            SAL_WARN("vcl.gdi", "File-widget typography roles require name, scale, and weight");
            bValid = false;
        }

        const OString aName = rWalker.attribute("name"_ostr);
        WidgetDefinitionTypographyRole* pRole = nullptr;
        bool* pSeen = nullptr;
        if (aName == "body")
        {
            pRole = &rTypography.maBody;
            pSeen = &bHasBody;
        }
        else if (aName == "label")
        {
            pRole = &rTypography.maLabel;
            pSeen = &bHasLabel;
        }
        else if (aName == "title")
        {
            pRole = &rTypography.maTitle;
            pSeen = &bHasTitle;
        }
        else
        {
            SAL_WARN("vcl.gdi", "Unknown file-widget typography role: " << aName);
            bValid = false;
        }

        if (pSeen && *pSeen)
        {
            SAL_WARN("vcl.gdi", "Duplicate file-widget typography role: " << aName);
            bValid = false;
            pRole = nullptr;
        }
        if (pSeen)
            *pSeen = true;

        const OString aScale = rWalker.attribute("scale"_ostr);
        const auto nScale = readTypographyScale(aScale);
        if (!nScale)
        {
            SAL_WARN("vcl.gdi", "Invalid file-widget typography scale: " << aScale);
            bValid = false;
        }

        const OString aWeight = rWalker.attribute("weight"_ostr);
        const auto eWeight = xmlStringToTypographyWeight(aWeight);
        if (!eWeight)
        {
            SAL_WARN("vcl.gdi", "Invalid file-widget typography weight: " << aWeight);
            bValid = false;
        }

        if (pRole && nScale && eWeight)
        {
            pRole->mnScalePercent = *nScale;
            pRole->meWeight = *eWeight;
        }

        if (hasUnexpectedChildContent(rWalker))
        {
            SAL_WARN("vcl.gdi", "File-widget typography roles must not have content");
            bValid = false;
        }
        rWalker.next();
    }
    rWalker.parent();

    if (!bHasBody || !bHasLabel || !bHasTitle)
    {
        SAL_WARN("vcl.gdi", "File-widget typography requires body, label, and title roles");
        bValid = false;
    }
    return bValid;
}

std::optional<ControlPart> xmlStringToControlPart(std::string_view sPart)
{
    if (o3tl::equalsIgnoreAsciiCase(sPart, "NONE"))
        return ControlPart::NONE;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Entire"))
        return ControlPart::Entire;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ListboxWindow"))
        return ControlPart::ListboxWindow;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Button"))
        return ControlPart::Button;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ButtonUp"))
        return ControlPart::ButtonUp;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ButtonDown"))
        return ControlPart::ButtonDown;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ButtonLeft"))
        return ControlPart::ButtonLeft;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ButtonRight"))
        return ControlPart::ButtonRight;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "AllButtons"))
        return ControlPart::AllButtons;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "SeparatorHorz"))
        return ControlPart::SeparatorHorz;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "SeparatorVert"))
        return ControlPart::SeparatorVert;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackHorzLeft"))
        return ControlPart::TrackHorzLeft;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackVertUpper"))
        return ControlPart::TrackVertUpper;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackHorzRight"))
        return ControlPart::TrackHorzRight;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackVertLower"))
        return ControlPart::TrackVertLower;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackHorzArea"))
        return ControlPart::TrackHorzArea;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TrackVertArea"))
        return ControlPart::TrackVertArea;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Arrow"))
        return ControlPart::Arrow;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ThumbHorz"))
        return ControlPart::ThumbHorz;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "ThumbVert"))
        return ControlPart::ThumbVert;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "MenuItem"))
        return ControlPart::MenuItem;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "MenuItemCheckMark"))
        return ControlPart::MenuItemCheckMark;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "MenuItemRadioMark"))
        return ControlPart::MenuItemRadioMark;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Separator"))
        return ControlPart::Separator;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "SubmenuArrow"))
        return ControlPart::SubmenuArrow;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "SubEdit"))
        return ControlPart::SubEdit;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "DrawBackgroundHorz"))
        return ControlPart::DrawBackgroundHorz;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "DrawBackgroundVert"))
        return ControlPart::DrawBackgroundVert;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "TabsDrawRtl"))
        return ControlPart::TabsDrawRtl;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "HasBackgroundTexture"))
        return ControlPart::HasBackgroundTexture;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "HasThreeButtons"))
        return ControlPart::HasThreeButtons;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "BackgroundWindow"))
        return ControlPart::BackgroundWindow;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "BackgroundDialog"))
        return ControlPart::BackgroundDialog;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Border"))
        return ControlPart::Border;
    else if (o3tl::equalsIgnoreAsciiCase(sPart, "Focus"))
        return ControlPart::Focus;
    return std::nullopt;
}

bool getControlTypeForXmlString(std::string_view rString, ControlType& reType)
{
    static constexpr auto aPartMap = frozen::make_unordered_map<std::string_view, ControlType>({
        { "pushbutton", ControlType::Pushbutton },
        { "radiobutton", ControlType::Radiobutton },
        { "checkbox", ControlType::Checkbox },
        { "combobox", ControlType::Combobox },
        { "editbox", ControlType::Editbox },
        { "editboxnoborder", ControlType::EditboxNoBorder },
        { "multilineeditbox", ControlType::MultilineEditbox },
        { "listbox", ControlType::Listbox },
        { "scrollbar", ControlType::Scrollbar },
        { "spinbox", ControlType::Spinbox },
        { "spinbuttons", ControlType::SpinButtons },
        { "slider", ControlType::Slider },
        { "fixedline", ControlType::Fixedline },
        { "progress", ControlType::Progress },
        { "levelbar", ControlType::LevelBar },
        { "tabitem", ControlType::TabItem },
        { "tabheader", ControlType::TabHeader },
        { "tabpane", ControlType::TabPane },
        { "tabbody", ControlType::TabBody },
        { "frame", ControlType::Frame },
        { "windowbackground", ControlType::WindowBackground },
        { "toolbar", ControlType::Toolbar },
        { "listnode", ControlType::ListNode },
        { "listnet", ControlType::ListNet },
        { "listheader", ControlType::ListHeader },
        { "menubar", ControlType::Menubar },
        { "menupopup", ControlType::MenuPopup },
        { "tooltip", ControlType::Tooltip },
    });

    auto const aIterator = aPartMap.find(rString);
    if (aIterator != aPartMap.end())
    {
        reType = aIterator->second;
        return true;
    }
    return false;
}

} // end anonymous namespace

WidgetDefinitionReader::WidgetDefinitionReader(OUString aDefinitionFile, OUString aResourcePath,
                                               OString aScheme)
    : m_rDefinitionFile(std::move(aDefinitionFile))
    , m_rResourcePath(std::move(aResourcePath))
    , m_aScheme(std::move(aScheme))
    , m_bValid(true)
{
}

bool WidgetDefinitionReader::readColor(OString const& rValue, Color& rColor) const
{
    if (!rValue.startsWith("@"))
    {
        if (color::createFromString(rValue, rColor))
            return true;
        SAL_WARN("vcl.gdi", "Invalid file-widget color value: " << rValue);
        return false;
    }

    auto const aToken = m_aColorTokens.find(rValue.copy(1));
    if (aToken == m_aColorTokens.end())
    {
        SAL_WARN("vcl.gdi", "Unknown file-widget color token: " << rValue);
        return false;
    }

    rColor = aToken->second;
    return true;
}

bool WidgetDefinitionReader::readColorPalette(tools::XmlWalker& rWalker,
                                              std::map<OString, Color>& rColorTokens) const
{
    bool bValid = true;
    rWalker.children();
    while (rWalker.isValid())
    {
        if (!rWalker.isElement())
        {
            if (!rWalker.isBlank() && !rWalker.isComment())
            {
                SAL_WARN("vcl.gdi", "Unexpected content in file-widget color palette");
                bValid = false;
            }
            rWalker.next();
            continue;
        }
        if (rWalker.name() == "color")
        {
            OString const sName = rWalker.attribute("name"_ostr);
            OString const sValue = rWalker.attribute("value"_ostr);
            Color aColor;
            if (sName.isEmpty() || sValue.startsWith("@")
                || !color::createFromString(sValue, aColor))
            {
                SAL_WARN("vcl.gdi", "Invalid file-widget color token: " << sName);
                bValid = false;
            }
            else if (!rColorTokens.emplace(sName, aColor).second)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget color token: " << sName);
                bValid = false;
            }
        }
        else
        {
            SAL_WARN("vcl.gdi", "Unknown file-widget palette entry: " << rWalker.name());
            bValid = false;
        }
        rWalker.next();
    }
    rWalker.parent();

    if (rColorTokens.empty())
    {
        SAL_WARN("vcl.gdi", "Empty file-widget color palette");
        bValid = false;
    }
    return bValid;
}

void WidgetDefinitionReader::readDrawingDefinition(
    tools::XmlWalker& rWalker, const std::shared_ptr<WidgetDefinitionState>& rpState,
    const std::map<OString, sal_Int32>& rRadiusTokens,
    const std::map<OString, sal_Int32>& rMetricTokens)
{
    rWalker.children();
    while (rWalker.isValid())
    {
        if (rWalker.name() == "metrics" || rWalker.name() == "metric")
        {
            SAL_WARN("vcl.gdi", "Misplaced file-widget metric element: " << rWalker.name());
            m_bValid = false;
        }
        else if (rWalker.name() == "rect")
        {
            Color aStrokeColor;
            if (!readColor(rWalker.attribute("stroke"_ostr), aStrokeColor))
                m_bValid = false;
            Color aFillColor;
            if (!readColor(rWalker.attribute("fill"_ostr), aFillColor))
                m_bValid = false;
            OString sStrokeWidth = rWalker.attribute("stroke-width"_ostr);
            sal_Int32 nStrokeWidth = -1;
            if (!sStrokeWidth.isEmpty()
                && !readMetricReference(sStrokeWidth, rMetricTokens, nStrokeWidth))
            {
                m_bValid = false;
            }

            sal_Int32 nRx = -1;
            sal_Int32 nRy = -1;
            const auto aAttributes = rWalker.attributeNames();
            const bool bHasRadius = std::find(aAttributes.begin(), aAttributes.end(), "radius"_ostr)
                                    != aAttributes.end();
            const bool bHasRx
                = std::find(aAttributes.begin(), aAttributes.end(), "rx"_ostr) != aAttributes.end();
            const bool bHasRy
                = std::find(aAttributes.begin(), aAttributes.end(), "ry"_ostr) != aAttributes.end();
            if (bHasRadius)
            {
                if (bHasRx || bHasRy)
                {
                    SAL_WARN("vcl.gdi", "File-widget radius cannot be combined with rx or ry");
                    m_bValid = false;
                }
                sal_Int32 nRadius = -1;
                if (readRadiusReference(rWalker.attribute("radius"_ostr), rRadiusTokens, nRadius))
                    nRx = nRy = nRadius;
                else
                    m_bValid = false;
            }
            else
            {
                OString sRx = rWalker.attribute("rx"_ostr);
                if (!sRx.isEmpty() && !readLegacyRadius(sRx, nRx))
                    m_bValid = false;

                OString sRy = rWalker.attribute("ry"_ostr);
                if (!sRy.isEmpty() && !readLegacyRadius(sRy, nRy))
                    m_bValid = false;
            }

            float fX1 = 0.0;
            float fY1 = 0.0;
            float fX2 = 1.0;
            float fY2 = 1.0;
            if (!readDrawingCoordinate(rWalker.attribute("x1"_ostr), 0.0, fX1)
                || !readDrawingCoordinate(rWalker.attribute("y1"_ostr), 0.0, fY1)
                || !readDrawingCoordinate(rWalker.attribute("x2"_ostr), 1.0, fX2)
                || !readDrawingCoordinate(rWalker.attribute("y2"_ostr), 1.0, fY2))
            {
                m_bValid = false;
            }

            rpState->addDrawRectangle(aStrokeColor, nStrokeWidth, aFillColor, fX1, fY1, fX2, fY2,
                                      nRx, nRy);
        }
        else if (rWalker.name() == "line")
        {
            Color aStrokeColor;
            if (!readColor(rWalker.attribute("stroke"_ostr), aStrokeColor))
                m_bValid = false;

            OString sStrokeWidth = rWalker.attribute("stroke-width"_ostr);
            sal_Int32 nStrokeWidth = -1;
            if (!sStrokeWidth.isEmpty()
                && !readMetricReference(sStrokeWidth, rMetricTokens, nStrokeWidth))
            {
                m_bValid = false;
            }

            float fX1 = -1.0;
            float fY1 = -1.0;
            float fX2 = -1.0;
            float fY2 = -1.0;
            if (!readDrawingCoordinate(rWalker.attribute("x1"_ostr), -1.0, fX1)
                || !readDrawingCoordinate(rWalker.attribute("y1"_ostr), -1.0, fY1)
                || !readDrawingCoordinate(rWalker.attribute("x2"_ostr), -1.0, fX2)
                || !readDrawingCoordinate(rWalker.attribute("y2"_ostr), -1.0, fY2))
            {
                m_bValid = false;
            }

            rpState->addDrawLine(aStrokeColor, nStrokeWidth, fX1, fY1, fX2, fY2);
        }
        else if (rWalker.name() == "image")
        {
            OString sSource = rWalker.attribute("source"_ostr);
            rpState->addDrawImage(m_rResourcePath
                                  + OStringToOUString(sSource, RTL_TEXTENCODING_UTF8));
        }
        else if (rWalker.name() == "external")
        {
            OString sSource = rWalker.attribute("source"_ostr);
            rpState->addDrawExternal(m_rResourcePath
                                     + OStringToOUString(sSource, RTL_TEXTENCODING_UTF8));
        }
        rWalker.next();
    }
    rWalker.parent();
}

void WidgetDefinitionReader::readDefinition(tools::XmlWalker& rWalker,
                                            WidgetDefinition& rWidgetDefinition, ControlType eType,
                                            const std::map<OString, sal_Int32>& rRadiusTokens,
                                            const std::map<OString, sal_Int32>& rMetricTokens)
{
    rWalker.children();
    while (rWalker.isValid())
    {
        if (rWalker.name() == "metrics" || rWalker.name() == "metric")
        {
            SAL_WARN("vcl.gdi", "Misplaced file-widget metric element: " << rWalker.name());
            m_bValid = false;
        }
        else if (rWalker.name() == "part")
        {
            OString sPart = rWalker.attribute("value"_ostr);
            auto const oPart = xmlStringToControlPart(sPart);
            if (!oPart)
            {
                SAL_WARN("vcl.gdi", "Unknown file-widget control part: " << sPart);
                m_bValid = false;
                rWalker.next();
                continue;
            }
            ControlPart const ePart = *oPart;

            std::shared_ptr<WidgetDefinitionPart> pPart = std::make_shared<WidgetDefinitionPart>();

            OString sWidth = rWalker.attribute("width"_ostr);
            if (!sWidth.isEmpty())
            {
                if (!readMetricReference(sWidth, rMetricTokens, pPart->mnWidth))
                    m_bValid = false;
            }

            OString sHeight = rWalker.attribute("height"_ostr);
            if (!sHeight.isEmpty())
            {
                if (!readMetricReference(sHeight, rMetricTokens, pPart->mnHeight))
                    m_bValid = false;
            }

            OString sMarginHeight = rWalker.attribute("margin-height"_ostr);
            if (!sMarginHeight.isEmpty())
            {
                if (!readMetricReference(sMarginHeight, rMetricTokens, pPart->mnMarginHeight))
                    m_bValid = false;
            }

            OString sMarginWidth = rWalker.attribute("margin-width"_ostr);
            if (!sMarginWidth.isEmpty())
            {
                if (!readMetricReference(sMarginWidth, rMetricTokens, pPart->mnMarginWidth))
                    m_bValid = false;
            }

            OString sOrientation = rWalker.attribute("orientation"_ostr);
            if (!sOrientation.isEmpty())
            {
                pPart->msOrientation = sOrientation;
            }

            if (!rWidgetDefinition.maDefinitions.emplace(ControlTypeAndPart(eType, ePart), pPart)
                     .second)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget control part: " << sPart);
                m_bValid = false;
            }
            readPart(rWalker, pPart, rRadiusTokens, rMetricTokens);
        }
        rWalker.next();
    }
    rWalker.parent();
}

void WidgetDefinitionReader::readPart(tools::XmlWalker& rWalker,
                                      const std::shared_ptr<WidgetDefinitionPart>& rpPart,
                                      const std::map<OString, sal_Int32>& rRadiusTokens,
                                      const std::map<OString, sal_Int32>& rMetricTokens)
{
    rWalker.children();
    while (rWalker.isValid())
    {
        if (rWalker.name() == "metrics" || rWalker.name() == "metric")
        {
            SAL_WARN("vcl.gdi", "Misplaced file-widget metric element: " << rWalker.name());
            m_bValid = false;
        }
        else if (rWalker.name() == "state")
        {
            OString sEnabled = getValueOrAny(rWalker.attribute("enabled"_ostr));
            OString sFocused = getValueOrAny(rWalker.attribute("focused"_ostr));
            OString sPressed = getValueOrAny(rWalker.attribute("pressed"_ostr));
            OString sRollover = getValueOrAny(rWalker.attribute("rollover"_ostr));
            OString sDefault = getValueOrAny(rWalker.attribute("default"_ostr));
            OString sSelected = getValueOrAny(rWalker.attribute("selected"_ostr));
            OString sButtonValue = getValueOrAny(rWalker.attribute("button-value"_ostr));
            OString sExtra = getValueOrAny(rWalker.attribute("extra"_ostr));

            std::shared_ptr<WidgetDefinitionState> pState = std::make_shared<WidgetDefinitionState>(
                sEnabled, sFocused, sPressed, sRollover, sDefault, sSelected, sButtonValue, sExtra);

            rpPart->maStates.push_back(pState);
            readDrawingDefinition(rWalker, pState, rRadiusTokens, rMetricTokens);
        }
        rWalker.next();
    }
    rWalker.parent();
}

bool WidgetDefinitionReader::readTokenTables(
    std::map<OString, std::map<OString, Color>>& rColorPalettes,
    std::map<OString, sal_Int32>& rRadiusTokens, std::map<OString, sal_Int32>& rMetricTokens) const
{
    rColorPalettes.clear();
    rRadiusTokens.clear();
    rMetricTokens.clear();

    if (!lcl_fileExists(m_rDefinitionFile))
        return false;

    // Reuse the exact palette/shape/metric reading path read()'s first pass drives,
    // so this query cannot diverge from the tokens the renderer resolves. Aggregate
    // validity locally; reader member state is left untouched.
    bool bValid = true;
    bool bHasShapes = false;
    bool bHasMetrics = false;

    SvFileStream aTokenStream(m_rDefinitionFile, StreamMode::READ);
    tools::XmlWalker aTokenWalker;
    if (!aTokenWalker.open(&aTokenStream) || aTokenWalker.name() != "widgets")
        return false;

    aTokenWalker.children();
    while (aTokenWalker.isValid())
    {
        if (aTokenWalker.name() == "palette")
        {
            OString const aScheme = aTokenWalker.attribute("scheme"_ostr);
            std::map<OString, Color> aColorTokens;
            if (!readColorPalette(aTokenWalker, aColorTokens))
                bValid = false;
            if (!rColorPalettes.emplace(aScheme, std::move(aColorTokens)).second)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget color palette scheme: " << aScheme);
                bValid = false;
            }
        }
        else if (aTokenWalker.name() == "shapes")
        {
            std::map<OString, sal_Int32> aShapeTokens;
            if (!readShapeTokens(aTokenWalker, aShapeTokens))
                bValid = false;
            if (bHasShapes)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget shapes section");
                bValid = false;
            }
            else
                rRadiusTokens = std::move(aShapeTokens);
            bHasShapes = true;
        }
        else if (aTokenWalker.name() == "metrics")
        {
            std::map<OString, sal_Int32> aTokens;
            if (!readMetricTokens(aTokenWalker, aTokens))
                bValid = false;
            if (bHasMetrics)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget metrics section");
                bValid = false;
            }
            else
                rMetricTokens = std::move(aTokens);
            bHasMetrics = true;
        }
        aTokenWalker.next();
    }
    aTokenWalker.parent();

    if (rColorPalettes.empty() || !bHasShapes || !bHasMetrics)
        bValid = false;

    // Every palette scheme must expose the same set of token names, mirroring the
    // invariant read() enforces before selecting the active scheme.
    if (!rColorPalettes.empty())
    {
        auto const& rReferencePalette = rColorPalettes.begin()->second;
        for (auto const& [rScheme, rColorTokens] : rColorPalettes)
        {
            if (!haveSameColorTokenNames(rReferencePalette, rColorTokens))
            {
                SAL_WARN("vcl.gdi",
                         "Mismatched file-widget color token set for palette scheme: " << rScheme);
                bValid = false;
            }
        }
    }

    return bValid;
}

bool WidgetDefinitionReader::read(WidgetDefinition& rWidgetDefinition)
{
    if (!lcl_fileExists(m_rDefinitionFile))
        return false;

    m_aColorTokens.clear();
    m_bValid = true;
    rWidgetDefinition.maDefinitions.clear();
    rWidgetDefinition.mpTypography.reset();

    // Resolve every semantic token section in a dedicated pass so definitions
    // may place them anywhere under the root without making token use
    // order-dependent. All color profiles are validated even though only one
    // is selected for this read.
    std::map<OString, std::map<OString, Color>> aColorPalettes;
    std::map<OString, sal_Int32> aRadiusTokens;
    std::map<OString, sal_Int32> aMetricTokens;
    bool bHasShapes = false;
    bool bHasMetrics = false;
    {
        SvFileStream aPaletteStream(m_rDefinitionFile, StreamMode::READ);
        tools::XmlWalker aPaletteWalker;
        if (!aPaletteWalker.open(&aPaletteStream) || aPaletteWalker.name() != "widgets")
            return false;

        aPaletteWalker.children();
        while (aPaletteWalker.isValid())
        {
            if (aPaletteWalker.name() == "palette")
            {
                OString const aScheme = aPaletteWalker.attribute("scheme"_ostr);
                std::map<OString, Color> aColorTokens;
                if (!readColorPalette(aPaletteWalker, aColorTokens))
                    m_bValid = false;
                if (!aColorPalettes.emplace(aScheme, std::move(aColorTokens)).second)
                {
                    SAL_WARN("vcl.gdi", "Duplicate file-widget color palette scheme: " << aScheme);
                    m_bValid = false;
                }
            }
            else if (aPaletteWalker.name() == "shapes")
            {
                std::map<OString, sal_Int32> aShapeTokens;
                if (!readShapeTokens(aPaletteWalker, aShapeTokens))
                    m_bValid = false;
                if (bHasShapes)
                {
                    SAL_WARN("vcl.gdi", "Duplicate file-widget shapes section");
                    m_bValid = false;
                }
                else
                    aRadiusTokens = std::move(aShapeTokens);
                bHasShapes = true;
            }
            else if (aPaletteWalker.name() == "metrics")
            {
                std::map<OString, sal_Int32> aTokens;
                if (!readMetricTokens(aPaletteWalker, aTokens))
                    m_bValid = false;
                if (bHasMetrics)
                {
                    SAL_WARN("vcl.gdi", "Duplicate file-widget metrics section");
                    m_bValid = false;
                }
                else
                    aMetricTokens = std::move(aTokens);
                bHasMetrics = true;
            }
            aPaletteWalker.next();
        }
        aPaletteWalker.parent();
    }

    if (!aColorPalettes.empty())
    {
        auto const& rReferencePalette = aColorPalettes.begin()->second;
        for (auto const& [rScheme, rColorTokens] : aColorPalettes)
        {
            if (!haveSameColorTokenNames(rReferencePalette, rColorTokens))
            {
                SAL_WARN("vcl.gdi",
                         "Mismatched file-widget color token set for palette scheme: " << rScheme);
                m_bValid = false;
            }
        }

        auto aSelectedPalette = aColorPalettes.find(m_aScheme);
        if (aSelectedPalette == aColorPalettes.end() && !m_aScheme.isEmpty())
            aSelectedPalette = aColorPalettes.find(OString());
        if (aSelectedPalette == aColorPalettes.end())
        {
            SAL_WARN("vcl.gdi", "No file-widget color palette for scheme: " << m_aScheme);
            m_bValid = false;
        }
        else
            m_aColorTokens = aSelectedPalette->second;
    }

    if (!m_bValid)
        return false;

    rWidgetDefinition.mpStyle = std::make_shared<WidgetDefinitionStyle>();

    std::unordered_map<std::string_view, Color*> aStyleColorMap = {
        { "faceColor", &rWidgetDefinition.mpStyle->maFaceColor },
        { "checkedColor", &rWidgetDefinition.mpStyle->maCheckedColor },
        { "lightColor", &rWidgetDefinition.mpStyle->maLightColor },
        { "lightBorderColor", &rWidgetDefinition.mpStyle->maLightBorderColor },
        { "shadowColor", &rWidgetDefinition.mpStyle->maShadowColor },
        { "darkShadowColor", &rWidgetDefinition.mpStyle->maDarkShadowColor },
        { "defaultButtonTextColor", &rWidgetDefinition.mpStyle->maDefaultButtonTextColor },
        { "buttonTextColor", &rWidgetDefinition.mpStyle->maButtonTextColor },
        { "defaultActionButtonTextColor",
          &rWidgetDefinition.mpStyle->maDefaultActionButtonTextColor },
        { "actionButtonTextColor", &rWidgetDefinition.mpStyle->maActionButtonTextColor },
        { "flatButtonTextColor", &rWidgetDefinition.mpStyle->maFlatButtonTextColor },
        { "defaultButtonRolloverTextColor",
          &rWidgetDefinition.mpStyle->maDefaultButtonRolloverTextColor },
        { "buttonRolloverTextColor", &rWidgetDefinition.mpStyle->maButtonRolloverTextColor },
        { "defaultActionButtonRolloverTextColor",
          &rWidgetDefinition.mpStyle->maDefaultActionButtonRolloverTextColor },
        { "actionButtonRolloverTextColor",
          &rWidgetDefinition.mpStyle->maActionButtonRolloverTextColor },
        { "flatButtonRolloverTextColor",
          &rWidgetDefinition.mpStyle->maFlatButtonRolloverTextColor },
        { "defaultButtonPressedRolloverTextColor",
          &rWidgetDefinition.mpStyle->maDefaultButtonPressedRolloverTextColor },
        { "buttonPressedRolloverTextColor",
          &rWidgetDefinition.mpStyle->maButtonPressedRolloverTextColor },
        { "defaultActionButtonPressedRolloverTextColor",
          &rWidgetDefinition.mpStyle->maDefaultActionButtonPressedRolloverTextColor },
        { "actionButtonPressedRolloverTextColor",
          &rWidgetDefinition.mpStyle->maActionButtonPressedRolloverTextColor },
        { "flatButtonPressedRolloverTextColor",
          &rWidgetDefinition.mpStyle->maFlatButtonPressedRolloverTextColor },
        { "radioCheckTextColor", &rWidgetDefinition.mpStyle->maRadioCheckTextColor },
        { "groupTextColor", &rWidgetDefinition.mpStyle->maGroupTextColor },
        { "labelTextColor", &rWidgetDefinition.mpStyle->maLabelTextColor },
        { "windowColor", &rWidgetDefinition.mpStyle->maWindowColor },
        { "windowTextColor", &rWidgetDefinition.mpStyle->maWindowTextColor },
        { "dialogColor", &rWidgetDefinition.mpStyle->maDialogColor },
        { "dialogTextColor", &rWidgetDefinition.mpStyle->maDialogTextColor },
        { "workspaceColor", &rWidgetDefinition.mpStyle->maWorkspaceColor },
        { "monoColor", &rWidgetDefinition.mpStyle->maMonoColor },
        { "fieldColor", &rWidgetDefinition.mpStyle->maFieldColor },
        { "fieldTextColor", &rWidgetDefinition.mpStyle->maFieldTextColor },
        { "fieldRolloverTextColor", &rWidgetDefinition.mpStyle->maFieldRolloverTextColor },
        { "activeColor", &rWidgetDefinition.mpStyle->maActiveColor },
        { "activeTextColor", &rWidgetDefinition.mpStyle->maActiveTextColor },
        { "activeBorderColor", &rWidgetDefinition.mpStyle->maActiveBorderColor },
        { "deactiveColor", &rWidgetDefinition.mpStyle->maDeactiveColor },
        { "deactiveTextColor", &rWidgetDefinition.mpStyle->maDeactiveTextColor },
        { "deactiveBorderColor", &rWidgetDefinition.mpStyle->maDeactiveBorderColor },
        { "menuColor", &rWidgetDefinition.mpStyle->maMenuColor },
        { "menuBarColor", &rWidgetDefinition.mpStyle->maMenuBarColor },
        { "menuBarRolloverColor", &rWidgetDefinition.mpStyle->maMenuBarRolloverColor },
        { "menuBorderColor", &rWidgetDefinition.mpStyle->maMenuBorderColor },
        { "menuTextColor", &rWidgetDefinition.mpStyle->maMenuTextColor },
        { "menuBarTextColor", &rWidgetDefinition.mpStyle->maMenuBarTextColor },
        { "menuBarRolloverTextColor", &rWidgetDefinition.mpStyle->maMenuBarRolloverTextColor },
        { "menuBarHighlightTextColor", &rWidgetDefinition.mpStyle->maMenuBarHighlightTextColor },
        { "menuHighlightColor", &rWidgetDefinition.mpStyle->maMenuHighlightColor },
        { "menuHighlightTextColor", &rWidgetDefinition.mpStyle->maMenuHighlightTextColor },
        { "highlightColor", &rWidgetDefinition.mpStyle->maHighlightColor },
        { "highlightTextColor", &rWidgetDefinition.mpStyle->maHighlightTextColor },
        { "activeTabColor", &rWidgetDefinition.mpStyle->maActiveTabColor },
        { "inactiveTabColor", &rWidgetDefinition.mpStyle->maInactiveTabColor },
        { "tabTextColor", &rWidgetDefinition.mpStyle->maTabTextColor },
        { "tabRolloverTextColor", &rWidgetDefinition.mpStyle->maTabRolloverTextColor },
        { "tabHighlightTextColor", &rWidgetDefinition.mpStyle->maTabHighlightTextColor },
        { "disableColor", &rWidgetDefinition.mpStyle->maDisableColor },
        { "helpColor", &rWidgetDefinition.mpStyle->maHelpColor },
        { "helpTextColor", &rWidgetDefinition.mpStyle->maHelpTextColor },
        { "linkColor", &rWidgetDefinition.mpStyle->maLinkColor },
        { "visitedLinkColor", &rWidgetDefinition.mpStyle->maVisitedLinkColor },
        { "toolTextColor", &rWidgetDefinition.mpStyle->maToolTextColor },
    };

    std::unordered_map<std::string_view, std::optional<Color>*> aOptionalStyleColorMap = {
        { "accentColor", &rWidgetDefinition.mpStyle->moAccentColor },
        { "listBoxWindowBackgroundColor",
          &rWidgetDefinition.mpStyle->moListBoxWindowBackgroundColor },
        { "listBoxWindowTextColor", &rWidgetDefinition.mpStyle->moListBoxWindowTextColor },
        { "listBoxWindowHighlightColor",
          &rWidgetDefinition.mpStyle->moListBoxWindowHighlightColor },
        { "listBoxWindowHighlightTextColor",
          &rWidgetDefinition.mpStyle->moListBoxWindowHighlightTextColor },
        { "alternatingRowColor", &rWidgetDefinition.mpStyle->moAlternatingRowColor },
        { "warningColor", &rWidgetDefinition.mpStyle->moWarningColor },
        { "warningTextColor", &rWidgetDefinition.mpStyle->moWarningTextColor },
        { "errorColor", &rWidgetDefinition.mpStyle->moErrorColor },
        { "errorTextColor", &rWidgetDefinition.mpStyle->moErrorTextColor },
    };

    rWidgetDefinition.mpSettings = std::make_shared<WidgetDefinitionSettings>();

    std::unordered_map<std::string_view, OString*> aSettingMap = {
        { "noActiveTabTextRaise", &rWidgetDefinition.mpSettings->msNoActiveTabTextRaise },
        { "centeredTabs", &rWidgetDefinition.mpSettings->msCenteredTabs },
        { "defaultFontSize", &rWidgetDefinition.mpSettings->msDefaultFontSize },
    };

    std::unordered_map<std::string_view, OString*> aMetricSettingMap = {
        { "listBoxEntryMargin", &rWidgetDefinition.mpSettings->msListBoxEntryMargin },
        { "titleHeight", &rWidgetDefinition.mpSettings->msTitleHeight },
        { "floatTitleHeight", &rWidgetDefinition.mpSettings->msFloatTitleHeight },
        { "listBoxPreviewDefaultLogicWidth",
          &rWidgetDefinition.mpSettings->msListBoxPreviewDefaultLogicWidth },
        { "listBoxPreviewDefaultLogicHeight",
          &rWidgetDefinition.mpSettings->msListBoxPreviewDefaultLogicHeight },
        { "menuBarHeight", &rWidgetDefinition.mpSettings->msMenuBarHeight },
        { "menuItemHeight", &rWidgetDefinition.mpSettings->msMenuItemHeight },
        { "menuPopupMinWidth", &rWidgetDefinition.mpSettings->msMenuPopupMinWidth },
        { "menuAccelColumnGap", &rWidgetDefinition.mpSettings->msMenuAccelColumnGap },
        { "menuInnerBorder", &rWidgetDefinition.mpSettings->msMenuInnerBorder },
    };

    SvFileStream aFileStream(m_rDefinitionFile, StreamMode::READ);

    tools::XmlWalker aWalker;
    if (!aWalker.open(&aFileStream))
        return false;

    if (aWalker.name() != "widgets")
        return false;

    bool bHasTypography = false;
    aWalker.children();
    while (aWalker.isValid())
    {
        ControlType eType;
        if (aWalker.name() == "palette")
        {
            // Parsed in the order-independent first pass.
        }
        else if (aWalker.name() == "shapes")
        {
            // Parsed in the order-independent first pass.
        }
        else if (aWalker.name() == "metrics")
        {
            // Parsed in the order-independent first pass.
        }
        else if (aWalker.name() == "metric")
        {
            SAL_WARN("vcl.gdi", "Misplaced file-widget metric element");
            m_bValid = false;
        }
        else if (aWalker.name() == "style")
        {
            aWalker.children();
            while (aWalker.isValid())
            {
                if (aWalker.name() == "metrics" || aWalker.name() == "metric")
                {
                    SAL_WARN("vcl.gdi", "Misplaced file-widget metric element: " << aWalker.name());
                    m_bValid = false;
                }
                else
                {
                    auto aOptional = aOptionalStyleColorMap.find(aWalker.name());
                    if (aOptional != aOptionalStyleColorMap.end())
                    {
                        Color aColor;
                        if (readColor(aWalker.attribute("value"_ostr), aColor))
                            *aOptional->second = aColor;
                        else
                            m_bValid = false;
                    }
                    else
                    {
                        auto aColor = aStyleColorMap.find(aWalker.name());
                        if (aColor != aStyleColorMap.end()
                            && !readColor(aWalker.attribute("value"_ostr), *aColor->second))
                        {
                            m_bValid = false;
                        }
                    }
                }
                aWalker.next();
            }
            aWalker.parent();
        }
        else if (aWalker.name() == "settings")
        {
            aWalker.children();
            while (aWalker.isValid())
            {
                if (aWalker.name() == "metrics" || aWalker.name() == "metric")
                {
                    SAL_WARN("vcl.gdi", "Misplaced file-widget metric element: " << aWalker.name());
                    m_bValid = false;
                }
                else
                {
                    auto aMetric = aMetricSettingMap.find(aWalker.name());
                    if (aMetric != aMetricSettingMap.end())
                    {
                        if (!readMetricSetting(aWalker.attribute("value"_ostr), aMetricTokens,
                                               *aMetric->second))
                        {
                            m_bValid = false;
                        }
                    }
                    else
                    {
                        auto aSetting = aSettingMap.find(aWalker.name());
                        if (aSetting != aSettingMap.end()
                            && !readLiteralSetting(aWalker.attribute("value"_ostr),
                                                   *aSetting->second))
                        {
                            m_bValid = false;
                        }
                    }
                }
                aWalker.next();
            }
            aWalker.parent();
        }
        else if (aWalker.name() == "typography")
        {
            auto pTypography = std::make_shared<WidgetDefinitionTypography>();
            if (!readTypography(aWalker, *pTypography))
                m_bValid = false;
            if (bHasTypography)
            {
                SAL_WARN("vcl.gdi", "Duplicate file-widget typography section");
                m_bValid = false;
            }
            else
                rWidgetDefinition.mpTypography = std::move(pTypography);
            bHasTypography = true;
        }
        else if (getControlTypeForXmlString(aWalker.name(), eType))
        {
            readDefinition(aWalker, rWidgetDefinition, eType, aRadiusTokens, aMetricTokens);
        }
        aWalker.next();
    }
    aWalker.parent();

    return m_bValid;
}

} // end vcl namespace

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
