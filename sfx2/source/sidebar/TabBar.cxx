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

#include <sfx2/sidebar/TabBar.hxx>
#include <sidebar/DeckDescriptor.hxx>
#include <sfx2/sidebar/Theme.hxx>
#include <sidebar/Tools.hxx>
#include <sfx2/sidebar/FocusManager.hxx>
#include <sfx2/sidebar/SidebarController.hxx>

#include <comphelper/lok.hxx>
#include <comphelper/processfactory.hxx>
#include <o3tl/safeint.hxx>
#include <cstdlib>
#include <utility>
#include <vcl/commandevent.hxx>
#include <vcl/commandinfoprovider.hxx>
#include <vcl/event.hxx>
#include <vcl/svapp.hxx>
#include <vcl/weld/Box.hxx>
#include <vcl/weld/Menu.hxx>
#include <vcl/weld/MenuButton.hxx>
#include <vcl/weld/Toolbar.hxx>
#include <svtools/acceleratorexecute.hxx>
#include <osl/diagnose.h>

#include "uiobject.hxx"

using namespace css;
using namespace css::uno;

static int gDefaultWidth;

namespace sfx2::sidebar {

namespace {

/** WIN-NAV-005: the Material sidebar rail treatment (48px rail width, 38x38px
    corner-small buttons stacked at a 4px gap below 10px top padding) only
    applies when the file-definition Material widget theme is the active VCL
    draw path. Every other theme keeps the measured native rail untouched, so no
    keyboard, mouse, a11y or RTL behaviour of the shared TabBar changes off the
    Material path. The rail width and button geometry are density-invariant and
    unaffected by high contrast; the @primary focus ring is drawn by the shared
    toolbar Focus part, which honours the VCL high-contrast bypass. */
bool IsMaterialRail()
{
    // The VCL_DRAW_WIDGETS_FROM_FILE environment variable is treated as
    // authoritative here: it is the same gate VCL keys the file-definition
    // widget-draw backend on (SalGraphics::initWidgetDrawBackends in
    // vcl/source/gdi/salgdilayout.cxx), so when it is set the Material rail
    // geometry lines up with the intended draw path. VCL additionally drops the
    // backend if the Material definition file fails to load; that degenerate
    // configuration (env set but definition unloadable) is not supported and is
    // intentionally not consulted here, since VCL exposes no process-global
    // "backend active" signal to the sfx2 sidebar -- isActive() is per
    // SalGraphics instance, not a static predicate.
    static const bool bMaterial = (std::getenv("VCL_DRAW_WIDGETS_FROM_FILE") != nullptr);
    return bMaterial;
}

} // anonymous namespace

TabBar::TabBar(vcl::Window* pParentWindow,
               const Reference<frame::XFrame>& rxFrame,
               std::function<void (const OUString&)> aDeckActivationFunctor,
               PopupMenuSignalConnectFunction aPopupMenuSignalConnectFunction,
               SidebarController& rParentSidebarController
              )
    : InterimItemWindow(pParentWindow, u"sfx/ui/tabbar.ui"_ustr, u"TabBar"_ustr)
    , mxFrame(rxFrame)
    , mxAuxBuilder(Application::CreateBuilder(m_xContainer.get(), u"sfx/ui/tabbarcontents.ui"_ustr))
    , mxTempToplevel(mxAuxBuilder->weld_box(u"toplevel"_ustr))
    , mxContents(mxAuxBuilder->weld_widget(u"TabBarContents"_ustr))
    , mxMeasureBox(mxAuxBuilder->weld_widget(u"measure"_ustr))
    , maDeckActivationFunctor(std::move(aDeckActivationFunctor))
    , mrParentSidebarController(rParentSidebarController)
{
    set_id(u"TabBar"_ustr); // for uitest

    InitControlBase(mxMenuButton.get());

    mxTempToplevel->move(mxContents.get(), m_xContainer.get());

    // For Gtk4 defer menu_button until after the contents have been
    // transferred to its final home (where the old parent is a GtkWindow to
    // support loading the accelerators in the menu for Gtk3)
    mxMenuButton = mxAuxBuilder->weld_menu_button(u"menubutton"_ustr);
    mxMainMenu = mxAuxBuilder->weld_menu(u"mainmenu"_ustr);
    mxSubMenu = mxAuxBuilder->weld_menu(u"submenu"_ustr);
    aPopupMenuSignalConnectFunction(*mxMainMenu, *mxSubMenu);

    UpdateMenus();

    gDefaultWidth = m_xContainer->get_preferred_size().Width();

    // we have this widget just so we can measure best width for static TabBar::GetDefaultWidth
    mxMeasureBox->hide();

    SetBackground(Wallpaper(Theme::GetColor(Theme::Color_TabBarBackground)));

#if OSL_DEBUG_LEVEL >= 2
    SetText(OUString("TabBar"));
#endif
}

TabBar::~TabBar()
{
    disposeOnce();
}

void TabBar::dispose()
{
    maItems.clear();
    mxMeasureBox.reset();
    mxSubMenu.reset();
    mxMainMenu.reset();
    mxMenuButton.reset();
    m_xContainer->move(mxContents.get(), mxTempToplevel.get());
    mxContents.reset();
    mxTempToplevel.reset();
    mxAuxBuilder.reset();
    InterimItemWindow::dispose();
}

sal_Int32 TabBar::GetDefaultWidth()
{
    // WIN-NAV-005: the Material rail is a fixed 48px deck-switcher column
    // (design 05 s5.1) rather than the width measured from native toolbar
    // chrome. SidebarController uses this value to lay out the rail/deck split
    // and the collapsed-to-rail state, so honouring the Material metric here is
    // what makes the whole rail 48px wide.
    if (IsMaterialRail())
        return Theme::GetInteger(Theme::Int_TabBarRailWidth);

    if (!gDefaultWidth)
    {
        std::unique_ptr<weld::Builder> xBuilder(Application::CreateBuilder(nullptr, u"sfx/ui/tabbarcontents.ui"_ustr));
        std::unique_ptr<weld::Widget> xContainer(xBuilder->weld_widget(u"TabBarContents"_ustr));
        gDefaultWidth = xContainer->get_preferred_size().Width();
    }
    return gDefaultWidth;
}

void TabBar::SetDecks(const ResourceManager::DeckContextDescriptorContainer& rDecks)
{
    // invisible with LOK, so keep empty to avoid invalidations
    if (comphelper::LibreOfficeKit::isActive())
        return;

    // Remove the current buttons.
    maItems.clear();
    for (auto const& deck : rDecks)
    {
        std::shared_ptr<DeckDescriptor> xDescriptor = mrParentSidebarController.GetResourceManager()->GetDeckDescriptor(deck.msId);
        if (xDescriptor == nullptr)
        {
            OSL_ASSERT(xDescriptor!=nullptr);
            continue;
        }

        maItems.emplace_back(std::make_unique<Item>(*this));
        auto& xItem(maItems.back());
        xItem->msDeckId = xDescriptor->msId;
        CreateTabItem(*xItem->mxButton, *xDescriptor);
        xItem->mxButton->connect_clicked(LINK(xItem.get(), TabBar::Item, HandleClick));
        xItem->maDeckActivationFunctor = maDeckActivationFunctor;
        xItem->mbIsHidden = !xDescriptor->mbIsEnabled;

        xItem->mxButton->set_visible(deck.mbIsEnabled);
    }

    // WIN-NAV-005: on the Material path give every rail button the fixed
    // 38x38px corner-small footprint (design 05 s5.1), stacked with a 4px gap
    // below 10px top padding. The rest/hover/active/focus/disabled fills and
    // icon colours come from the shared Material toolbar Button part the rail
    // buttons already render through, so only the geometry is applied here.
    if (IsMaterialRail())
    {
        const sal_Int32 nButtonSize = Theme::GetInteger(Theme::Int_TabItemButtonSize);
        const sal_Int32 nGap = Theme::GetInteger(Theme::Int_TabItemGap);
        const sal_Int32 nTopPadding = Theme::GetInteger(Theme::Int_TabBarTopPadding);
        // The 10px top padding belongs above the first *visible* rail button
        // (design 05 s5.1). maItems can lead with decks hidden by the
        // set_visible(deck.mbIsEnabled) call above, and a hidden button gets no
        // allocation, so anchoring the padding on maItems[0] would strand it on
        // an invisible button and leave the first visible button with only the
        // 4px inter-button gap. Track the first visible item instead.
        bool bFirstVisible = true;
        for (auto const& item : maItems)
        {
            const bool bVisible = item->mxButton->get_visible();
            item->mxButton->set_size_request(nButtonSize, nButtonSize);
            item->mxButton->set_margin_top(bFirstVisible && bVisible ? nTopPadding : nGap);
            if (bVisible)
                bFirstVisible = false;
        }
    }

    UpdateButtonIcons();
    UpdateMenus();
}

void TabBar::UpdateButtonIcons()
{
    for (auto const& item : maItems)
    {
        std::shared_ptr<DeckDescriptor> xDeckDescriptor = mrParentSidebarController.GetResourceManager()->GetDeckDescriptor(item->msDeckId);
        if (!xDeckDescriptor)
            continue;
        item->mxButton->set_item_image(u"toggle"_ustr, GetItemImage(*xDeckDescriptor));
    }
}

void TabBar::HighlightDeck(std::u16string_view rsDeckId)
{
    for (auto const& item : maItems)
        item->mxButton->set_item_active(u"toggle"_ustr, item->msDeckId == rsDeckId);
    UpdateMenus();
}

void TabBar::RemoveDeckHighlight()
{
    for (auto const& item : maItems)
        item->mxButton->set_item_active(u"toggle"_ustr, false);
    UpdateMenus();
}

void TabBar::DataChanged(const DataChangedEvent& rDataChangedEvent)
{
    SetBackground(Theme::GetColor(Theme::Color_TabBarBackground));
    UpdateButtonIcons();
    UpdateMenus();

    InterimItemWindow::DataChanged(rDataChangedEvent);
}

bool TabBar::EventNotify(NotifyEvent& rEvent)
{
    NotifyEventType nType = rEvent.GetType();
    if(NotifyEventType::KEYINPUT == nType)
    {
        return InterimItemWindow::EventNotify(rEvent);
    }
    else if(NotifyEventType::COMMAND == nType)
    {
        const CommandEvent& rCommandEvent = *rEvent.GetCommandEvent();
        if(rCommandEvent.GetCommand() == CommandEventId::Wheel)
        {
            const CommandWheelData* pData = rCommandEvent.GetWheelData();
            if(!pData->GetModifier() && (pData->GetMode() == CommandWheelMode::SCROLL))
            {
                auto pItem = std::find_if(maItems.begin(), maItems.end(),
                    [] (const auto& item) { return item->mxButton->get_item_active("toggle"); });
                if(pItem == maItems.end())
                    return true;
                if(pData->GetNotchDelta()<0)
                {
                    if(pItem+1 == maItems.end())
                        return true;
                    ++pItem;
                }
                else
                {
                    if(pItem == maItems.begin())
                        return true;
                    --pItem;
                }
                try
                {
                    (*pItem)->maDeckActivationFunctor((*pItem)->msDeckId);
                    GrabFocusToDocument();
                }
                catch(const css::uno::Exception&) {};
                return true;
            }
        }
    }
    return false;
}

void TabBar::CreateTabItem(weld::Toolbar& rItem, const DeckDescriptor& rDeckDescriptor)
{
    rItem.set_accessible_description(rDeckDescriptor.msHelpText);
    const OUString sCommand = ".uno:SidebarDeck." + rDeckDescriptor.msId;
    OUString sShortcut = vcl::CommandInfoProvider::GetCommandShortcut(sCommand, mxFrame);
    if (!sShortcut.isEmpty())
        sShortcut = u" (" + sShortcut + u")";
    rItem.set_item_accessible_name(u"toggle"_ustr, rDeckDescriptor.msTitle);
    rItem.set_item_tooltip_text(u"toggle"_ustr, rDeckDescriptor.msHelpText + sShortcut);
}

css::uno::Reference<css::graphic::XGraphic> TabBar::GetItemImage(const DeckDescriptor& rDeckDescriptor) const
{
    return Tools::GetImage(
        rDeckDescriptor.msIconURL,
        rDeckDescriptor.msHighContrastIconURL,
        mxFrame);
}

TabBar::Item::Item(TabBar& rTabBar)
    : mrTabBar(rTabBar)
    , mxBuilder(Application::CreateBuilder(rTabBar.GetContainer(), u"sfx/ui/tabbutton.ui"_ustr))
    , mxButton(mxBuilder->weld_toolbar(u"button"_ustr))
    , mbIsHidden(false)
{
}

TabBar::Item::~Item()
{
    mrTabBar.GetContainer()->move(mxButton.get(), nullptr);
}

IMPL_LINK_NOARG(TabBar::Item, HandleClick, const OUString&, void)
{
    // tdf#143146 copy the functor and arg before calling
    // GrabFocusToDocument which may destroy this object
    DeckActivationFunctor aDeckActivationFunctor = maDeckActivationFunctor;
    auto sDeckId = msDeckId;

    mrTabBar.GrabFocusToDocument();
    try
    {
        aDeckActivationFunctor(sDeckId);
    }
    catch(const css::uno::Exception&)
    {} // workaround for #i123198#
}

OUString const & TabBar::GetDeckIdForIndex (const sal_Int32 nIndex) const
{
    if (nIndex<0 || o3tl::make_unsigned(nIndex)>=maItems.size())
        throw RuntimeException();
    return maItems[nIndex]->msDeckId;
}

void TabBar::ToggleHideFlag (const sal_Int32 nIndex)
{
    if (nIndex<0 || o3tl::make_unsigned(nIndex) >= maItems.size())
        throw RuntimeException();

    maItems[nIndex]->mbIsHidden = ! maItems[nIndex]->mbIsHidden;

    std::shared_ptr<DeckDescriptor> xDeckDescriptor = mrParentSidebarController.GetResourceManager()->GetDeckDescriptor(maItems[nIndex]->msDeckId);
    if (xDeckDescriptor)
    {
        xDeckDescriptor->mbIsEnabled = ! maItems[nIndex]->mbIsHidden;

        Context aContext;
        aContext.msApplication = mrParentSidebarController.GetCurrentContext().msApplication;
        // leave aContext.msContext on default 'any' ... this func is used only for decks
        // and we don't have context-sensitive decks anyway

        xDeckDescriptor->maContextList.ToggleVisibilityForContext(
            aContext, xDeckDescriptor->mbIsEnabled );
    }
    UpdateMenus();
}

void TabBar::UpdateFocusManager(FocusManager& rFocusManager)
{
    std::vector<weld::Widget*> aButtons;
    aButtons.reserve(maItems.size()+1);
    aButtons.push_back(mxMenuButton.get());
    for (auto const& item : maItems)
    {
        aButtons.push_back(item->mxButton.get());
    }
    rFocusManager.SetButtons(aButtons);
}

void TabBar::UpdateMenus()
{
    if (Application::GetToolkitName() == u"gtk4"_ustr)
    {
        SAL_WARN("sfx", "Skipping update of sidebar menus to avoid crash due to gtk4 menu brokenness.");
        return;
    }

    for (int i = mxMainMenu->n_children() - 1; i >= 0; --i)
    {
        OUString sIdent = mxMainMenu->get_id(i);
        if (sIdent.startsWith("select"))
            mxMainMenu->remove(sIdent);
    }
    for (int i = mxSubMenu->n_children() - 1; i >= 0; --i)
    {
        OUString sIdent = mxSubMenu->get_id(i);
        if (sIdent.indexOf("customize") != -1)
            mxSubMenu->remove(sIdent);
    }

    // Add one entry for every tool panel element to individually make
    // them visible or hide them.
    sal_Int32 nIndex (0);
    for (auto const& rItem : maItems)
    {
        std::shared_ptr<DeckDescriptor> xDeckDescriptor
            = mrParentSidebarController.GetResourceManager()->GetDeckDescriptor(rItem->msDeckId);

        if (!xDeckDescriptor)
            continue;

        const OUString sDisplayName = xDeckDescriptor->msTitle;
        OUString sIdent("select" + OUString::number(nIndex));
        const bool bCurrentDeck = rItem->mxButton->get_item_active(u"toggle"_ustr);
        const bool bActive = !rItem->mbIsHidden;
        const bool bEnabled = rItem->mxButton->get_visible();
        mxMainMenu->insert(nIndex, sIdent, sDisplayName, nullptr, nullptr, nullptr, TRISTATE_FALSE);
        mxMainMenu->set_active(sIdent, bCurrentDeck);
        mxMainMenu->set_sensitive(sIdent, bEnabled && bActive);

        if (!comphelper::LibreOfficeKit::isActive())
        {
            if (bCurrentDeck)
            {
                // Don't allow the currently visible deck to be disabled.
                OUString sSubIdent("nocustomize" + OUString::number(nIndex));
                mxSubMenu->insert(nIndex, sSubIdent, sDisplayName, nullptr, nullptr, nullptr,
                                  TRISTATE_FALSE);
                mxSubMenu->set_active(sSubIdent, true);
            }
            else
            {
                OUString sSubIdent("customize" + OUString::number(nIndex));
                mxSubMenu->insert(nIndex, sSubIdent, sDisplayName, nullptr, nullptr, nullptr,
                                  TRISTATE_TRUE);
                mxSubMenu->set_active(sSubIdent, bEnabled && bActive);
            }
        }

        ++nIndex;
    }

    bool bHideLock = true;
    bool bHideUnLock = true;
    // LOK doesn't support docked/undocked; Sidebar is floating but rendered docked in browser.
    if (!comphelper::LibreOfficeKit::isActive())
    {
        // Add entry for docking or un-docking the tool panel.
        if (!mrParentSidebarController.IsDocked())
            bHideLock = false;
        else
            bHideUnLock = false;
    }
    mxMainMenu->set_visible(u"locktaskpanel"_ustr, !bHideLock);
    mxMainMenu->set_visible(u"unlocktaskpanel"_ustr, !bHideUnLock);

    // No Restore or Customize options for LoKit.
    mxMainMenu->set_visible(u"customization"_ustr, !comphelper::LibreOfficeKit::isActive());
}

void TabBar::EnableMenuButton(const bool bEnable)
{
    mxMenuButton->set_sensitive(bEnable);
}

FactoryFunction TabBar::GetUITestFactory() const
{
    return TabBarUIObject::create;
}

} // end of namespace sfx2::sidebar

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
