/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * This file incorporates work covered by the following license notice:
 *
 *   Licensed to the Apache Software Foundation (ASF) under one or more
 *   contributor license agreements. See the NOTICE file distributed
 *   with this work for additional information regarding copyright
 *   ownership. The ASF licenses this file to you under the Apache
 *   License, Version 2.0 (the "License"); you may not use this file
 *   except in compliance with the License. You may obtain a copy of
 *   the License at http://www.apache.org/licenses/LICENSE-2.0 .
 */

#include <sfx2/sidebar/Theme.hxx>
#include <sfx2/app.hxx>
#include <tools/color.hxx>

#include <vcl/svapp.hxx>
#include <vcl/settings.hxx>
#include <comphelper/diagnose_ex.hxx>

#include <cstdlib>

using namespace css;
using namespace css::uno;

namespace sfx2::sidebar {

namespace {

/** WIN-CON-007: the Material deck treatment (deck/title/panel on @surface, the
    14px deck content inset, and the title/heading text colours) only applies
    when the file-definition Material widget theme is the active VCL draw path --
    the same VCL_DRAW_WIDGETS_FROM_FILE gate the rail (WIN-NAV-005) keys on. Every
    other theme keeps the measured native deck colours and zero content padding,
    so no non-Material sidebar geometry, colour, keyboard, a11y or RTL behaviour
    changes off the Material path. */
bool IsMaterialDeck()
{
    static const bool bMaterial = (std::getenv("VCL_DRAW_WIDGETS_FROM_FILE") != nullptr);
    return bMaterial;
}

} // anonymous namespace

Theme& Theme::GetCurrentTheme()
{
    OSL_ASSERT(SfxGetpApp());
    return SfxGetpApp()->GetSidebarTheme();
}

Theme::Theme()
    : mbIsHighContrastMode(Application::GetSettings().GetStyleSettings().GetHighContrastMode()),
      mbIsHighContrastModeSetManually(false)
{
    SetupPropertyMaps();
}

Theme::~Theme()
{
}

Color Theme::GetColor (const ThemeItem eItem)
{
    const PropertyType eType (GetPropertyType(eItem));
    OSL_ASSERT(eType==PT_Color);
    const sal_Int32 nIndex (GetIndex(eItem, eType));
    const Theme& rTheme (GetCurrentTheme());
    if (eType == PT_Color)
        return rTheme.maColors[nIndex];
    else
        return COL_WHITE;
}

sal_Int32 Theme::GetInteger (const ThemeItem eItem)
{
    const PropertyType eType (GetPropertyType(eItem));
    OSL_ASSERT(eType==PT_Integer);
    const sal_Int32 nIndex (GetIndex(eItem, eType));
    const Theme& rTheme (GetCurrentTheme());
    return rTheme.maIntegers[nIndex];
}

bool Theme::IsHighContrastMode()
{
    const Theme& rTheme (GetCurrentTheme());
    return rTheme.mbIsHighContrastMode;
}

void Theme::HandleDataChange()
{
    Theme& rTheme (GetCurrentTheme());

    if ( ! rTheme.mbIsHighContrastModeSetManually)
    {
        // Do not modify mbIsHighContrastMode when it was manually set.
        GetCurrentTheme().mbIsHighContrastMode = Application::GetSettings().GetStyleSettings().GetHighContrastMode();
        rTheme.maRawValues[Bool_IsHighContrastModeActive] <<= GetCurrentTheme().mbIsHighContrastMode;
    }

    GetCurrentTheme().UpdateTheme();
}

void Theme::InitializeTheme()
{
    setPropertyValue(
        maPropertyIdToNameMap[Bool_UseSystemColors],
        Any(false));
}

void Theme::UpdateTheme()
{
    try
    {
        const StyleSettings& rStyle (Application::GetSettings().GetStyleSettings());

        Color aBaseBackgroundColor (rStyle.GetDialogColor());
        // UX says this should be a little brighter, but that looks off when compared to the other windows.
        //aBaseBackgroundColor.IncreaseLuminance(7);
        Color aSecondColor (aBaseBackgroundColor);
        aSecondColor.DecreaseLuminance(15);

        // WIN-CON-007: on the Material draw path the properties deck, its title
        // bar, and the panels all sit on @surface (design 06 s6.7 / site
        // prototype writerBody()), one tonal step brighter than the
        // @surface-container rail so the deck/rail hairline reads. The rail keeps
        // @surface-container via Color_TabBarBackground below. Off the Material
        // path every deck slot keeps its measured native value (dialog colour /
        // luminance-stepped title bar), so no non-Material sidebar changes.
        const bool bMaterialDeck (IsMaterialDeck());
        const Color aDeckSurfaceColor (bMaterialDeck ? rStyle.GetWindowColor() : aBaseBackgroundColor);
        const Color aPanelTitleColor (bMaterialDeck ? rStyle.GetWindowColor() : aSecondColor);

        setPropertyValue(
            maPropertyIdToNameMap[Color_DeckBackground],
            Any(sal_Int32(aDeckSurfaceColor.GetRGBColor())));

        setPropertyValue(
            maPropertyIdToNameMap[Color_DeckTitleBarBackground],
            Any(sal_Int32(aDeckSurfaceColor.GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckSeparatorHeight],
            Any(sal_Int32(1)));
        setPropertyValue(
            maPropertyIdToNameMap[Color_PanelBackground],
            Any(sal_Int32(aDeckSurfaceColor.GetRGBColor())));

        setPropertyValue(
            maPropertyIdToNameMap[Color_PanelTitleBarBackground],
            Any(sal_Int32(aPanelTitleColor.GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabBarBackground],
            Any(sal_Int32(aBaseBackgroundColor.GetRGBColor())));

        // WIN-CON-007: the deck title text uses the `title` type role in
        // @on-surface; 11px uppercase section headings use @on-surface-variant
        // (design 06 s6.7). Both are sourced from the Material-mapped
        // StyleSettings getter that resolves to the named token, so the deck
        // follows whatever widget theme is active. Color_PanelSectionHeadingText
        // is the pinned source of truth for the panel-heading treatment: the
        // panel title bar is a weld::Expander, which exposes no font-colour API,
        // so the 11px uppercase heading is drawn by the later native
        // panel-heading paint row that reads this slot -- the absence of a getter
        // consumer today is deliberate, not a wiring gap.
        setPropertyValue(
            maPropertyIdToNameMap[Color_DeckTitleText],
            Any(sal_Int32(rStyle.GetWindowTextColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_PanelSectionHeadingText],
            Any(sal_Int32(rStyle.GetGroupTextColor().GetRGBColor())));

        // WIN-CON-007: the deck content inset is 14px on the Material path (design
        // 06 s6.7 / site prototype) and the measured native zero otherwise. These
        // existing Int_Deck*Padding slots are consumed unconditionally by
        // Deck::GetContentArea, so the value itself is guarded here to keep the
        // non-Material deck geometry untouched.
        const sal_Int32 nDeckContentPadding (bMaterialDeck ? 14 : 0);
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckLeftPadding],
            Any(sal_Int32(nDeckContentPadding)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckTopPadding],
            Any(sal_Int32(nDeckContentPadding)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckRightPadding],
            Any(sal_Int32(nDeckContentPadding)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckBottomPadding],
            Any(sal_Int32(nDeckContentPadding)));

        // WIN-CON-007: density-invariant Material deck metrics. Like the rail
        // metrics these are pinned literals set unconditionally; each consumer
        // (Deck scrollbar, DeckTitleBar title font, SidebarController overlay)
        // applies them behind its own Material guard.
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckScrollbarThickness],
            Any(sal_Int32(12)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckTitleScalePercent],
            Any(sal_Int32(120)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_PanelSectionHeadingHeight],
            Any(sal_Int32(11)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_DeckOverlayMinWidth],
            Any(sal_Int32(600)));

        // Material sidebar rail state palette (WIN-NAV-005). Each slot is
        // sourced from the Material-mapped StyleSettings getter that resolves to
        // the design token named in design 05 s5.2, so the rail follows whatever
        // widget theme is active instead of hard-coding a Material literal.
        // These six colour slots (and the Int_TabItemIconSize metric set below)
        // are intentionally set-only for now: they are the pinned source of
        // truth the sidebar-rail contract locks in, to be read via
        // Theme::GetColor / Theme::GetInteger by the bespoke rail-button paint
        // row. The absence of a getter consumer today is deliberate, not a
        // wiring gap.
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabItemActiveBackground],
            Any(sal_Int32(rStyle.GetActiveTabColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabItemActiveText],
            Any(sal_Int32(rStyle.GetHighlightTextColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabItemText],
            Any(sal_Int32(rStyle.GetGroupTextColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabItemFocusRing],
            Any(sal_Int32(rStyle.GetAccentColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabItemDisabledText],
            Any(sal_Int32(rStyle.GetDeactiveTextColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_TabBarSeparator],
            Any(sal_Int32(rStyle.GetMenuBorderColor().GetRGBColor())));

        // Material sidebar rail metrics (WIN-NAV-005), density-invariant.
        setPropertyValue(
            maPropertyIdToNameMap[Int_TabBarRailWidth],
            Any(sal_Int32(48)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_TabItemButtonSize],
            Any(sal_Int32(38)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_TabItemIconSize],
            Any(sal_Int32(22)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_TabItemGap],
            Any(sal_Int32(4)));
        setPropertyValue(
            maPropertyIdToNameMap[Int_TabBarTopPadding],
            Any(sal_Int32(10)));

        setPropertyValue(
            maPropertyIdToNameMap[Color_Highlight],
            Any(sal_Int32(rStyle.GetHighlightColor().GetRGBColor())));
        setPropertyValue(
            maPropertyIdToNameMap[Color_HighlightText],
            Any(sal_Int32(rStyle.GetHighlightTextColor().GetRGBColor())));
    }
    catch(beans::UnknownPropertyException const &)
    {
        DBG_UNHANDLED_EXCEPTION("sfx", "unknown property");
        OSL_ASSERT(false);
    }
}

void Theme::disposing(std::unique_lock<std::mutex>&)
{
    SolarMutexGuard aGuard;

    ChangeListeners aListeners;
    aListeners.swap(maChangeListeners);

    const lang::EventObject aEvent (getXWeak());

    for (const auto& rContainer : aListeners)
    {
        for (const auto& rxListener : rContainer.second)
        {
            try
            {
                rxListener->disposing(aEvent);
            }
            catch(const Exception&)
            {
            }
        }
    }
}

Reference<beans::XPropertySet> Theme::GetPropertySet()
{
    if (SfxGetpApp())
        return Reference<beans::XPropertySet>(&GetCurrentTheme());
    else
        return Reference<beans::XPropertySet>();
}

Reference<beans::XPropertySetInfo> SAL_CALL Theme::getPropertySetInfo()
{
    return Reference<beans::XPropertySetInfo>(this);
}

void SAL_CALL Theme::setPropertyValue (
    const OUString& rsPropertyName,
    const css::uno::Any& rValue)
{
    SolarMutexGuard aGuard;

    PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
    if (iId == maPropertyNameToIdMap.end())
        throw beans::UnknownPropertyException(rsPropertyName);

    const PropertyType eType (GetPropertyType(iId->second));
    if (eType == PT_Invalid)
        throw beans::UnknownPropertyException(rsPropertyName);

    const ThemeItem eItem (iId->second);

    if (rValue == maRawValues[eItem])
    {
        // Value is not different from the one in the property
        // set => nothing to do.
        return;
    }

    const Any aOldValue (maRawValues[eItem]);

    const beans::PropertyChangeEvent aEvent(
        getXWeak(),
        rsPropertyName,
        false,
        eItem,
        aOldValue,
        rValue);

    if (DoVetoableListenersVeto(GetVetoableListeners(AnyItem_, false), aEvent))
        return;
    if (DoVetoableListenersVeto(GetVetoableListeners(eItem, false), aEvent))
        return;

    maRawValues[eItem] = rValue;
    ProcessNewValue(rValue, eItem, eType);

    BroadcastPropertyChange(GetChangeListeners(AnyItem_, false), aEvent);
    BroadcastPropertyChange(GetChangeListeners(eItem, false), aEvent);
}

Any SAL_CALL Theme::getPropertyValue (
    const OUString& rsPropertyName)
{
    SolarMutexGuard aGuard;

    PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
    if (iId == maPropertyNameToIdMap.end())
        throw beans::UnknownPropertyException(rsPropertyName);

    const PropertyType eType (GetPropertyType(iId->second));
    if (eType == PT_Invalid)
        throw beans::UnknownPropertyException(rsPropertyName);

    const ThemeItem eItem (iId->second);

    return maRawValues[eItem];
}

void SAL_CALL Theme::addPropertyChangeListener(
    const OUString& rsPropertyName,
    const css::uno::Reference<css::beans::XPropertyChangeListener>& rxListener)
{
    SolarMutexGuard aGuard;

    ThemeItem eItem (AnyItem_);
    if (rsPropertyName.getLength() > 0)
    {
        PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
        if (iId == maPropertyNameToIdMap.end())
            throw beans::UnknownPropertyException(rsPropertyName);

        const PropertyType eType (GetPropertyType(iId->second));
        if (eType == PT_Invalid)
            throw beans::UnknownPropertyException(rsPropertyName);

        eItem = iId->second;
    }
    ChangeListenerContainer* pListeners = GetChangeListeners(eItem, true);
    if (pListeners != nullptr)
        pListeners->push_back(rxListener);
}

void SAL_CALL Theme::removePropertyChangeListener(
    const OUString& rsPropertyName,
    const css::uno::Reference<css::beans::XPropertyChangeListener>& rxListener)
{
    SolarMutexGuard aGuard;

    ThemeItem eItem (AnyItem_);
    if (rsPropertyName.getLength() > 0)
    {
        PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
        if (iId == maPropertyNameToIdMap.end())
            throw beans::UnknownPropertyException(rsPropertyName);

        const PropertyType eType (GetPropertyType(iId->second));
        if (eType == PT_Invalid)
            throw beans::UnknownPropertyException(rsPropertyName);

        eItem = iId->second;
    }
    ChangeListenerContainer* pContainer = GetChangeListeners(eItem, false);
    if (pContainer != nullptr)
    {
        ChangeListenerContainer::iterator iListener (::std::find(pContainer->begin(), pContainer->end(), rxListener));
        if (iListener != pContainer->end())
        {
            pContainer->erase(iListener);

            // Remove the listener container when empty.
            if (pContainer->empty())
                maChangeListeners.erase(eItem);
        }
    }
}

void SAL_CALL Theme::addVetoableChangeListener(
    const OUString& rsPropertyName,
    const css::uno::Reference<css::beans::XVetoableChangeListener>& rxListener)
{
    SolarMutexGuard aGuard;

    ThemeItem eItem (AnyItem_);
    if (rsPropertyName.getLength() > 0)
    {
        PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
        if (iId == maPropertyNameToIdMap.end())
            throw beans::UnknownPropertyException(rsPropertyName);

        const PropertyType eType (GetPropertyType(iId->second));
        if (eType == PT_Invalid)
            throw beans::UnknownPropertyException(rsPropertyName);

        eItem = iId->second;
    }
    VetoableListenerContainer* pListeners = GetVetoableListeners(eItem, true);
    if (pListeners != nullptr)
        pListeners->push_back(rxListener);
}

void SAL_CALL Theme::removeVetoableChangeListener(
    const OUString& rsPropertyName,
    const css::uno::Reference<css::beans::XVetoableChangeListener>& rxListener)
{
    SolarMutexGuard aGuard;

    ThemeItem eItem (AnyItem_);
    if (rsPropertyName.getLength() > 0)
    {
        PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
        if (iId == maPropertyNameToIdMap.end())
            throw beans::UnknownPropertyException(rsPropertyName);

        const PropertyType eType (GetPropertyType(iId->second));
        if (eType == PT_Invalid)
            throw beans::UnknownPropertyException(rsPropertyName);

        eItem = iId->second;
    }
    VetoableListenerContainer* pContainer = GetVetoableListeners(eItem, false);
    if (pContainer != nullptr)
    {
        VetoableListenerContainer::iterator iListener (::std::find(pContainer->begin(), pContainer->end(), rxListener));
        if (iListener != pContainer->end())
        {
            pContainer->erase(iListener);
            // Remove container when empty.
            if (pContainer->empty())
                maVetoableListeners.erase(eItem);
        }
    }
}

css::uno::Sequence<css::beans::Property> SAL_CALL Theme::getProperties()
{
    SolarMutexGuard aGuard;

    ::std::vector<beans::Property> aProperties;

    sal_Int32 const nEnd(End_);
    for (sal_Int32 nItem(Begin_); nItem!=nEnd; ++nItem)
    {
        const ThemeItem eItem (static_cast<ThemeItem>(nItem));
        const PropertyType eType (GetPropertyType(eItem));
        if (eType == PT_Invalid)
            continue;

        const beans::Property aProperty(
            maPropertyIdToNameMap[eItem],
            eItem,
            GetCppuType(eType),
            0);
        aProperties.push_back(aProperty);
    }

    return css::uno::Sequence<css::beans::Property>(
        aProperties.data(),
        aProperties.size());
}

beans::Property SAL_CALL Theme::getPropertyByName (const OUString& rsPropertyName)
{
    SolarMutexGuard aGuard;

    PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
    if (iId == maPropertyNameToIdMap.end())
        throw beans::UnknownPropertyException(rsPropertyName);

    const PropertyType eType (GetPropertyType(iId->second));
    if (eType == PT_Invalid)
        throw beans::UnknownPropertyException(rsPropertyName);

    const ThemeItem eItem (iId->second);

    return beans::Property(
        rsPropertyName,
        eItem,
        GetCppuType(eType),
        0);
}

sal_Bool SAL_CALL Theme::hasPropertyByName (const OUString& rsPropertyName)
{
    SolarMutexGuard aGuard;

    PropertyNameToIdMap::const_iterator iId (maPropertyNameToIdMap.find(rsPropertyName));
    if (iId == maPropertyNameToIdMap.end())
        return false;

    const PropertyType eType (GetPropertyType(iId->second));
    if (eType == PT_Invalid)
        return false;

    return true;
}

void Theme::SetupPropertyMaps()
{
    maPropertyIdToNameMap.resize(Post_Bool_);
    maColors.resize(Color_Int_ - Pre_Color_ - 1);
    maIntegers.resize(Int_Bool_ - Color_Int_ - 1);
    maBooleans.resize(Post_Bool_ - Int_Bool_ - 1);

    maPropertyNameToIdMap[u"Color_Highlight"_ustr]=Color_Highlight;
    maPropertyIdToNameMap[Color_Highlight]="Color_Highlight";

    maPropertyNameToIdMap[u"Color_HighlightText"_ustr]=Color_HighlightText;
    maPropertyIdToNameMap[Color_HighlightText]="Color_HighlightText";


    maPropertyNameToIdMap[u"Color_DeckBackground"_ustr]=Color_DeckBackground;
    maPropertyIdToNameMap[Color_DeckBackground]="Color_DeckBackground";

    maPropertyNameToIdMap[u"Color_DeckTitleBarBackground"_ustr]=Color_DeckTitleBarBackground;
    maPropertyIdToNameMap[Color_DeckTitleBarBackground]="Color_DeckTitleBarBackground";

    maPropertyNameToIdMap[u"Color_PanelBackground"_ustr]=Color_PanelBackground;
    maPropertyIdToNameMap[Color_PanelBackground]="Color_PanelBackground";

    maPropertyNameToIdMap[u"Color_PanelTitleBarBackground"_ustr]=Color_PanelTitleBarBackground;
    maPropertyIdToNameMap[Color_PanelTitleBarBackground]="Color_PanelTitleBarBackground";

    maPropertyNameToIdMap[u"Color_TabBarBackground"_ustr]=Color_TabBarBackground;
    maPropertyIdToNameMap[Color_TabBarBackground]="Color_TabBarBackground";

    maPropertyNameToIdMap[u"Color_TabItemActiveBackground"_ustr]=Color_TabItemActiveBackground;
    maPropertyIdToNameMap[Color_TabItemActiveBackground]="Color_TabItemActiveBackground";

    maPropertyNameToIdMap[u"Color_TabItemActiveText"_ustr]=Color_TabItemActiveText;
    maPropertyIdToNameMap[Color_TabItemActiveText]="Color_TabItemActiveText";

    maPropertyNameToIdMap[u"Color_TabItemText"_ustr]=Color_TabItemText;
    maPropertyIdToNameMap[Color_TabItemText]="Color_TabItemText";

    maPropertyNameToIdMap[u"Color_TabItemFocusRing"_ustr]=Color_TabItemFocusRing;
    maPropertyIdToNameMap[Color_TabItemFocusRing]="Color_TabItemFocusRing";

    maPropertyNameToIdMap[u"Color_TabItemDisabledText"_ustr]=Color_TabItemDisabledText;
    maPropertyIdToNameMap[Color_TabItemDisabledText]="Color_TabItemDisabledText";

    maPropertyNameToIdMap[u"Color_TabBarSeparator"_ustr]=Color_TabBarSeparator;
    maPropertyIdToNameMap[Color_TabBarSeparator]="Color_TabBarSeparator";

    maPropertyNameToIdMap[u"Color_DeckTitleText"_ustr]=Color_DeckTitleText;
    maPropertyIdToNameMap[Color_DeckTitleText]="Color_DeckTitleText";

    maPropertyNameToIdMap[u"Color_PanelSectionHeadingText"_ustr]=Color_PanelSectionHeadingText;
    maPropertyIdToNameMap[Color_PanelSectionHeadingText]="Color_PanelSectionHeadingText";


    maPropertyNameToIdMap[u"Int_DeckBorderSize"_ustr]=Int_DeckBorderSize;
    maPropertyIdToNameMap[Int_DeckBorderSize]="Int_DeckBorderSize";

    maPropertyNameToIdMap[u"Int_DeckSeparatorHeight"_ustr]=Int_DeckSeparatorHeight;
    maPropertyIdToNameMap[Int_DeckSeparatorHeight]="Int_DeckSeparatorHeight";

    maPropertyNameToIdMap[u"Int_DeckLeftPadding"_ustr]=Int_DeckLeftPadding;
    maPropertyIdToNameMap[Int_DeckLeftPadding]="Int_DeckLeftPadding";

    maPropertyNameToIdMap[u"Int_DeckTopPadding"_ustr]=Int_DeckTopPadding;
    maPropertyIdToNameMap[Int_DeckTopPadding]="Int_DeckTopPadding";

    maPropertyNameToIdMap[u"Int_DeckRightPadding"_ustr]=Int_DeckRightPadding;
    maPropertyIdToNameMap[Int_DeckRightPadding]="Int_DeckRightPadding";

    maPropertyNameToIdMap[u"Int_DeckBottomPadding"_ustr]=Int_DeckBottomPadding;
    maPropertyIdToNameMap[Int_DeckBottomPadding]="Int_DeckBottomPadding";

    maPropertyNameToIdMap[u"Int_TabBarRailWidth"_ustr]=Int_TabBarRailWidth;
    maPropertyIdToNameMap[Int_TabBarRailWidth]="Int_TabBarRailWidth";

    maPropertyNameToIdMap[u"Int_TabItemButtonSize"_ustr]=Int_TabItemButtonSize;
    maPropertyIdToNameMap[Int_TabItemButtonSize]="Int_TabItemButtonSize";

    maPropertyNameToIdMap[u"Int_TabItemIconSize"_ustr]=Int_TabItemIconSize;
    maPropertyIdToNameMap[Int_TabItemIconSize]="Int_TabItemIconSize";

    maPropertyNameToIdMap[u"Int_TabItemGap"_ustr]=Int_TabItemGap;
    maPropertyIdToNameMap[Int_TabItemGap]="Int_TabItemGap";

    maPropertyNameToIdMap[u"Int_TabBarTopPadding"_ustr]=Int_TabBarTopPadding;
    maPropertyIdToNameMap[Int_TabBarTopPadding]="Int_TabBarTopPadding";

    maPropertyNameToIdMap[u"Int_DeckScrollbarThickness"_ustr]=Int_DeckScrollbarThickness;
    maPropertyIdToNameMap[Int_DeckScrollbarThickness]="Int_DeckScrollbarThickness";

    maPropertyNameToIdMap[u"Int_DeckTitleScalePercent"_ustr]=Int_DeckTitleScalePercent;
    maPropertyIdToNameMap[Int_DeckTitleScalePercent]="Int_DeckTitleScalePercent";

    maPropertyNameToIdMap[u"Int_PanelSectionHeadingHeight"_ustr]=Int_PanelSectionHeadingHeight;
    maPropertyIdToNameMap[Int_PanelSectionHeadingHeight]="Int_PanelSectionHeadingHeight";

    maPropertyNameToIdMap[u"Int_DeckOverlayMinWidth"_ustr]=Int_DeckOverlayMinWidth;
    maPropertyIdToNameMap[Int_DeckOverlayMinWidth]="Int_DeckOverlayMinWidth";


    maPropertyNameToIdMap[u"Bool_UseSystemColors"_ustr]=Bool_UseSystemColors;
    maPropertyIdToNameMap[Bool_UseSystemColors]="Bool_UseSystemColors";

    maPropertyNameToIdMap[u"Bool_IsHighContrastModeActive"_ustr]=Bool_IsHighContrastModeActive;
    maPropertyIdToNameMap[Bool_IsHighContrastModeActive]="Bool_IsHighContrastModeActive";

    maRawValues.resize(maPropertyIdToNameMap.size());
}

Theme::PropertyType Theme::GetPropertyType (const ThemeItem eItem)
{
    switch(eItem)
    {
        case Color_Highlight:
        case Color_HighlightText:
        case Color_DeckBackground:
        case Color_DeckTitleBarBackground:
        case Color_PanelBackground:
        case Color_PanelTitleBarBackground:
        case Color_TabBarBackground:
        case Color_TabItemActiveBackground:
        case Color_TabItemActiveText:
        case Color_TabItemText:
        case Color_TabItemFocusRing:
        case Color_TabItemDisabledText:
        case Color_TabBarSeparator:
        case Color_DeckTitleText:
        case Color_PanelSectionHeadingText:
            return PT_Color;

        case Int_DeckBorderSize:
        case Int_DeckSeparatorHeight:
        case Int_DeckLeftPadding:
        case Int_DeckTopPadding:
        case Int_DeckRightPadding:
        case Int_DeckBottomPadding:
        case Int_TabBarRailWidth:
        case Int_TabItemButtonSize:
        case Int_TabItemIconSize:
        case Int_TabItemGap:
        case Int_TabBarTopPadding:
        case Int_DeckScrollbarThickness:
        case Int_DeckTitleScalePercent:
        case Int_PanelSectionHeadingHeight:
        case Int_DeckOverlayMinWidth:
            return PT_Integer;

        case Bool_UseSystemColors:
        case Bool_IsHighContrastModeActive:
            return PT_Boolean;

        default:
            return PT_Invalid;
    }
}

css::uno::Type const & Theme::GetCppuType (const PropertyType eType)
{
    switch(eType)
    {
        case PT_Color:
            return cppu::UnoType<sal_uInt32>::get();

        case PT_Integer:
            return cppu::UnoType<sal_Int32>::get();

        case PT_Boolean:
            return cppu::UnoType<sal_Bool>::get();

        case PT_Invalid:
        default:
            return cppu::UnoType<void>::get();
    }
}

sal_Int32 Theme::GetIndex (const ThemeItem eItem, const PropertyType eType)
{
    switch(eType)
    {
        case PT_Color:
            return eItem - Pre_Color_-1;
        case PT_Integer:
            return eItem - Color_Int_-1;
        case PT_Boolean:
            return eItem - Int_Bool_-1;
        default:
            OSL_ASSERT(false);
            return 0;
    }
}

Theme::VetoableListenerContainer* Theme::GetVetoableListeners (
    const ThemeItem eItem,
    const bool bCreate)
{
    VetoableListeners::iterator iContainer (maVetoableListeners.find(eItem));
    if (iContainer != maVetoableListeners.end())
        return &iContainer->second;
    else if (bCreate)
    {
        maVetoableListeners[eItem] = VetoableListenerContainer();
        return &maVetoableListeners[eItem];
    }
    else
        return nullptr;
}

Theme::ChangeListenerContainer* Theme::GetChangeListeners (
    const ThemeItem eItem,
    const bool bCreate)
{
    ChangeListeners::iterator iContainer (maChangeListeners.find(eItem));
    if (iContainer != maChangeListeners.end())
        return &iContainer->second;
    else if (bCreate)
    {
        maChangeListeners[eItem] = ChangeListenerContainer();
        return &maChangeListeners[eItem];
    }
    else
        return nullptr;
}

bool Theme::DoVetoableListenersVeto (
    const VetoableListenerContainer* pListeners,
    const beans::PropertyChangeEvent& rEvent)
{
    if (pListeners == nullptr)
        return false;

    VetoableListenerContainer aListeners (*pListeners);
    try
    {
        for (const auto& rxListener : aListeners)
        {
            rxListener->vetoableChange(rEvent);
        }
    }
    catch(const beans::PropertyVetoException&)
    {
        return true;
    }
    catch(const Exception&)
    {
        // Ignore any other errors (such as disposed listeners).
    }
    return false;
}

void Theme::BroadcastPropertyChange (
    const ChangeListenerContainer* pListeners,
    const beans::PropertyChangeEvent& rEvent)
{
    if (pListeners == nullptr)
        return;

    const ChangeListenerContainer aListeners (*pListeners);
    try
    {
        for (const auto& rxListener : aListeners)
        {
            rxListener->propertyChange(rEvent);
        }
    }
    catch(const Exception&)
    {
        // Ignore any errors (such as disposed listeners).
    }
}

void Theme::ProcessNewValue (
    const Any& rValue,
    const ThemeItem eItem,
    const PropertyType eType)
{
    const sal_Int32 nIndex (GetIndex (eItem, eType));
    switch (eType)
    {
        case PT_Color:
        {
            Color nColorValue;
            if (rValue >>= nColorValue)
                maColors[nIndex] = nColorValue;
            break;
        }
        case PT_Integer:
        {
            sal_Int32 nValue (0);
            if (rValue >>= nValue)
            {
                maIntegers[nIndex] = nValue;
            }
            break;
        }
        case PT_Boolean:
        {
            bool bValue (false);
            if (rValue >>= bValue)
            {
                maBooleans[nIndex] = bValue;
                if (eItem == Bool_IsHighContrastModeActive)
                {
                    mbIsHighContrastModeSetManually = true;
                    mbIsHighContrastMode = maBooleans[nIndex];
                    HandleDataChange();
                }
                else if (eItem == Bool_UseSystemColors)
                {
                    HandleDataChange();
                }
            }
            break;
        }
        case PT_Invalid:
            OSL_ASSERT(eType != PT_Invalid);
            throw RuntimeException();
    }
}

} // end of namespace sfx2::sidebar

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
