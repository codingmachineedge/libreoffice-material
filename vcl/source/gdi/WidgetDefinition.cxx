/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#include <string_view>
#include <utility>
#include <widgetdraw/WidgetDefinition.hxx>

#include <sal/config.h>
#include <algorithm>
#include <limits>
#include <o3tl/safeint.hxx>
#include <unordered_map>
#include <vcl/font.hxx>
#include <vcl/settings.hxx>

namespace vcl
{
namespace
{
vcl::Font applyTypographyRole(const vcl::Font& rNative, const WidgetDefinitionTypographyRole& rRole)
{
    vcl::Font aFont(rNative);
    const tools::Long nNativeHeight = rNative.GetFontHeight();
    if (nNativeHeight > 0)
    {
        const sal_Int32 nScale = std::clamp<sal_Int32>(rRole.mnScalePercent, 100, 200);
        sal_Int64 nProduct;
        sal_Int64 nScaledHeight;
        if (o3tl::checked_multiply<sal_Int64>(nNativeHeight, nScale, nProduct))
            nScaledHeight = std::numeric_limits<tools::Long>::max();
        else
        {
            nScaledHeight = nProduct / 100;
            if (nProduct % 100 >= 50)
                ++nScaledHeight;
            nScaledHeight = std::max<sal_Int64>(nNativeHeight, nScaledHeight);
        }
        aFont.SetFontHeight(static_cast<tools::Long>(
            std::min<sal_Int64>(nScaledHeight, std::numeric_limits<tools::Long>::max())));
    }

    FontWeight eMinimumWeight = WEIGHT_DONTKNOW;
    switch (rRole.meWeight)
    {
        case WidgetDefinitionFontWeight::Preserve:
            break;
        case WidgetDefinitionFontWeight::Normal:
            eMinimumWeight = WEIGHT_NORMAL;
            break;
        case WidgetDefinitionFontWeight::Medium:
            eMinimumWeight = WEIGHT_MEDIUM;
            break;
        case WidgetDefinitionFontWeight::SemiBold:
            eMinimumWeight = WEIGHT_SEMIBOLD;
            break;
        case WidgetDefinitionFontWeight::Bold:
            eMinimumWeight = WEIGHT_BOLD;
            break;
    }
    if (eMinimumWeight != WEIGHT_DONTKNOW
        && (aFont.GetWeight() == WEIGHT_DONTKNOW || aFont.GetWeight() < eMinimumWeight))
    {
        aFont.SetWeight(eMinimumWeight);
    }
    return aFont;
}
}

void WidgetDefinitionTypography::apply(StyleSettings& rTarget, const StyleSettings& rNative) const
{
    rTarget.SetAppFont(applyTypographyRole(rNative.GetAppFont(), maBody));
    rTarget.SetHelpFont(applyTypographyRole(rNative.GetHelpFont(), maBody));
    rTarget.SetFieldFont(applyTypographyRole(rNative.GetFieldFont(), maBody));

    rTarget.SetMenuFont(applyTypographyRole(rNative.GetMenuFont(), maLabel));
    rTarget.SetToolFont(applyTypographyRole(rNative.GetToolFont(), maLabel));
    rTarget.SetGroupFont(applyTypographyRole(rNative.GetGroupFont(), maLabel));
    rTarget.SetLabelFont(applyTypographyRole(rNative.GetLabelFont(), maLabel));
    rTarget.SetRadioCheckFont(applyTypographyRole(rNative.GetRadioCheckFont(), maLabel));
    rTarget.SetPushButtonFont(applyTypographyRole(rNative.GetPushButtonFont(), maLabel));
    rTarget.SetTabFont(applyTypographyRole(rNative.GetTabFont(), maLabel));

    rTarget.SetTitleFont(applyTypographyRole(rNative.GetTitleFont(), maTitle));
    rTarget.SetFloatTitleFont(applyTypographyRole(rNative.GetFloatTitleFont(), maTitle));
}

std::shared_ptr<WidgetDefinitionPart> WidgetDefinition::getDefinition(ControlType eType,
                                                                      ControlPart ePart)
{
    auto aIterator = maDefinitions.find(ControlTypeAndPart(eType, ePart));

    if (aIterator != maDefinitions.end())
        return aIterator->second;
    return std::shared_ptr<WidgetDefinitionPart>();
}

namespace
{
// Single matching predicate shared by getStates() and the allocation-free
// getLastState() fast path, so the two can never diverge. The logic is
// byte-for-byte the body of the former getStates() loop.
bool lcl_stateMatches(const std::shared_ptr<WidgetDefinitionState>& state, ControlType eType,
                      ControlPart ePart, ControlState eState, ImplControlValue const& rValue)
{
    {
        bool bAdd = true;

        if (state->msEnabled != "any"
            && !((state->msEnabled == "true" && eState & ControlState::ENABLED)
                 || (state->msEnabled == "false" && !(eState & ControlState::ENABLED))))
            bAdd = false;
        if (state->msFocused != "any"
            && !((state->msFocused == "true" && eState & ControlState::FOCUSED)
                 || (state->msFocused == "false" && !(eState & ControlState::FOCUSED))))
            bAdd = false;
        if (state->msPressed != "any"
            && !((state->msPressed == "true" && eState & ControlState::PRESSED)
                 || (state->msPressed == "false" && !(eState & ControlState::PRESSED))))
            bAdd = false;
        if (state->msRollover != "any"
            && !((state->msRollover == "true" && eState & ControlState::ROLLOVER)
                 || (state->msRollover == "false" && !(eState & ControlState::ROLLOVER))))
            bAdd = false;
        if (state->msDefault != "any"
            && !((state->msDefault == "true" && eState & ControlState::DEFAULT)
                 || (state->msDefault == "false" && !(eState & ControlState::DEFAULT))))
            bAdd = false;
        if (state->msSelected != "any"
            && !((state->msSelected == "true" && eState & ControlState::SELECTED)
                 || (state->msSelected == "false" && !(eState & ControlState::SELECTED))))
            bAdd = false;

        ButtonValue eButtonValue = rValue.getTristateVal();

        if (state->msButtonValue != "any"
            && !((state->msButtonValue == "true" && eButtonValue == ButtonValue::On)
                 || (state->msButtonValue == "false" && eButtonValue == ButtonValue::Off)
                 || (state->msButtonValue == "mixed" && eButtonValue == ButtonValue::Mixed)))
        {
            bAdd = false;
        }

        std::string_view sExtra = "any";

        switch (eType)
        {
            case ControlType::TabItem:
            {
                if (rValue.getType() != ControlType::TabItem)
                    break;
                auto const& rTabItemValue = static_cast<TabitemValue const&>(rValue);

                if (rTabItemValue.isLeftAligned() && rTabItemValue.isRightAligned()
                    && rTabItemValue.isFirst() && rTabItemValue.isLast())
                    sExtra = "first_last";
                else if (rTabItemValue.isLeftAligned() || rTabItemValue.isFirst())
                    sExtra = "first";
                else if (rTabItemValue.isRightAligned() || rTabItemValue.isLast())
                    sExtra = "last";
                else
                    sExtra = "middle";
            }
            break;
            case ControlType::ListHeader:
            {
                if (ePart == ControlPart::Arrow)
                {
                    if (rValue.getNumericVal() == 1)
                        sExtra = "down";
                    else
                        sExtra = "up";
                }
            }
            break;
            case ControlType::Pushbutton:
            {
                if (rValue.getType() != ControlType::Pushbutton)
                    break;
                auto const& rPushButtonValue = static_cast<PushButtonValue const&>(rValue);
                if (rPushButtonValue.mbIsAction)
                    sExtra = "action";
                else if (rPushButtonValue.m_bFlatButton)
                    sExtra = "flat";
            }
            break;
            case ControlType::LevelBar:
            {
                const tools::Long nPercent = std::clamp<tools::Long>(
                    rValue.getNumericVal(), tools::Long(0), tools::Long(10000));
                if (nPercent < 2500)
                    sExtra = "critical";
                else if (nPercent < 5000)
                    sExtra = "low";
                else if (nPercent < 7500)
                    sExtra = "medium";
                else
                    sExtra = "high";
            }
            break;
            default:
                break;
        }

        if (state->msExtra != "any" && state->msExtra != sExtra)
        {
            bAdd = false;
        }

        return bAdd;
    }
}
}

std::vector<std::shared_ptr<WidgetDefinitionState>>
WidgetDefinitionPart::getStates(ControlType eType, ControlPart ePart, ControlState eState,
                                ImplControlValue const& rValue)
{
    std::vector<std::shared_ptr<WidgetDefinitionState>> aStatesToAdd;

    for (const auto& state : maStates)
    {
        if (lcl_stateMatches(state, eType, ePart, eState, rValue))
            aStatesToAdd.push_back(state);
    }

    return aStatesToAdd;
}

const std::shared_ptr<WidgetDefinitionState>&
WidgetDefinitionPart::getLastState(ControlType eType, ControlPart ePart, ControlState eState,
                                   ImplControlValue const& rValue)
{
    static const std::shared_ptr<WidgetDefinitionState> saNone;

    // The renderer only ever draws the last matching state, so scan backwards and
    // stop at the first hit: no vector allocation, no shared_ptr refcount traffic
    // and no comparisons past the winner. Identical result to getStates().back().
    for (auto aIterator = maStates.rbegin(); aIterator != maStates.rend(); ++aIterator)
    {
        if (lcl_stateMatches(*aIterator, eType, ePart, eState, rValue))
            return *aIterator;
    }
    return saNone;
}

WidgetDefinitionState::WidgetDefinitionState(OString sEnabled, OString sFocused, OString sPressed,
                                             OString sRollover, OString sDefault, OString sSelected,
                                             OString sButtonValue, OString sExtra)
    : msEnabled(std::move(sEnabled))
    , msFocused(std::move(sFocused))
    , msPressed(std::move(sPressed))
    , msRollover(std::move(sRollover))
    , msDefault(std::move(sDefault))
    , msSelected(std::move(sSelected))
    , msButtonValue(std::move(sButtonValue))
    , msExtra(std::move(sExtra))
{
}

void WidgetDefinitionState::addDrawRectangle(Color aStrokeColor, sal_Int32 nStrokeWidth,
                                             Color aFillColor, float fX1, float fY1, float fX2,
                                             float fY2, sal_Int32 nRx, sal_Int32 nRy)
{
    auto pCommand(std::make_shared<WidgetDrawActionRectangle>());
    pCommand->maStrokeColor = aStrokeColor;
    pCommand->maFillColor = aFillColor;
    pCommand->mnStrokeWidth = nStrokeWidth;
    pCommand->mnRx = nRx;
    pCommand->mnRy = nRy;
    pCommand->mfX1 = fX1;
    pCommand->mfY1 = fY1;
    pCommand->mfX2 = fX2;
    pCommand->mfY2 = fY2;
    mpWidgetDrawActions.push_back(std::move(pCommand));
}

void WidgetDefinitionState::addDrawLine(Color aStrokeColor, sal_Int32 nStrokeWidth, float fX1,
                                        float fY1, float fX2, float fY2)
{
    auto pCommand(std::make_shared<WidgetDrawActionLine>());
    pCommand->maStrokeColor = aStrokeColor;
    pCommand->mnStrokeWidth = nStrokeWidth;
    pCommand->mfX1 = fX1;
    pCommand->mfY1 = fY1;
    pCommand->mfX2 = fX2;
    pCommand->mfY2 = fY2;
    mpWidgetDrawActions.push_back(std::move(pCommand));
}

void WidgetDefinitionState::addDrawImage(OUString const& sSource)
{
    auto pCommand(std::make_shared<WidgetDrawActionImage>());
    pCommand->msSource = sSource;
    mpWidgetDrawActions.push_back(std::move(pCommand));
}

void WidgetDefinitionState::addDrawExternal(OUString const& sSource)
{
    auto pCommand(std::make_shared<WidgetDrawActionExternal>());
    pCommand->msSource = sSource;
    mpWidgetDrawActions.push_back(std::move(pCommand));
}

} // end vcl namespace

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
