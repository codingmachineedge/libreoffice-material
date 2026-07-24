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

#include <chrono>
#include <cstdlib>
#include <optional>
#include <string_view>
#include <vcl/builderfactory.hxx>
#include <vcl/commandevent.hxx>
#include <vcl/layout.hxx>
#include <vcl/MaterialTokens.hxx>
#include <vcl/notebookbar/notebookbar.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/tabpage.hxx>
#include <sfx2/viewfrm.hxx>
#include <notebookbar/NotebookbarTabControl.hxx>
#include <com/sun/star/ui/theModuleUIConfigurationManagerSupplier.hpp>
#include <com/sun/star/ui/ItemType.hpp>
#include <com/sun/star/frame/XModuleManager.hpp>
#include <com/sun/star/frame/ModuleManager.hpp>
#include <com/sun/star/frame/XFrame.hpp>
#include <com/sun/star/uno/Reference.h>
#include <com/sun/star/awt/PopupMenuDirection.hpp>
#include <com/sun/star/awt/XVclWindowPeer.hpp>
#include <com/sun/star/frame/XPopupMenuController.hpp>
#include <comphelper/processfactory.hxx>
#include <comphelper/propertyvalue.hxx>
#include <sidebar/SidebarToolBox.hxx>
#include <toolkit/awt/vclxmenu.hxx>
#include <cppuhelper/implbase.hxx>

#define ICON_SIZE 25
constexpr OUString TOOLBAR_STR = u"private:resource/toolbar/notebookbarshortcuts"_ustr;

using namespace css::uno;
using namespace css::ui;
using namespace css::frame;

namespace
{
// Resolve a Material semantic color token for the notebookbar tab-row band, but only
// when the Material file-widget theme is the active, documented activation
// (VCL_FILE_WIDGET_THEME=material -- the same gate used in
// vcl/source/control/notebookbar.cxx (group-area @surface wash) and
// vcl/source/window/status.cxx; see docs/design/05-navigation.md section 4, tab-row
// band). System forced colors take precedence over the Material treatment for
// accessibility, so high-contrast mode ALWAYS wins and returns nothing here. Under the
// default/native theme this also returns nothing, so NotebookbarTabControl::Paint()
// overlays no Material treatment and the stock tab drawing stays byte-for-byte
// unchanged -- keyboard, mouse, a11y and RTL behavior are untouched. Values flow
// exclusively through vcl::MaterialTokens, the single named-token view over
// definition.xml, so the @primary active-tab underline and @outline-variant tab-row
// hairline can never drift from the definition they mirror (no raw hex literal here).
// The per-scheme token table is parsed at most once because definition.xml is immutable
// at runtime, keeping the paint path cheap; the cheap getenv gate short-circuits before
// any parse under the native theme.
std::optional<Color> lcl_materialTabControlColor(std::string_view rRole)
{
    // System forced colors take precedence over the Material treatment for
    // accessibility; never override the HC-aware colors.
    if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())
        return std::nullopt;

    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return std::nullopt;

    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    static std::optional<vcl::MaterialTokens> spLightTokens;
    static std::optional<vcl::MaterialTokens> spDarkTokens;
    std::optional<vcl::MaterialTokens>& rCache = bDark ? spDarkTokens : spLightTokens;
    if (!rCache)
        rCache = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    if (!rCache->isValid())
        return std::nullopt;
    return rCache->findColor(rRole);
}
}

class ChangedUIEventListener : public ::cppu::WeakImplHelper<XUIConfigurationListener>
{
    VclPtr<NotebookbarTabControl> m_pParent;

public:
    explicit ChangedUIEventListener(NotebookbarTabControl *p)
    : m_pParent(p)
    {
        try
        {
            if (SfxViewFrame* pViewFrm = SfxViewFrame::Current())
            {
                const Reference<XComponentContext>& xContext = comphelper::getProcessComponentContext();
                const Reference<XModuleManager> xModuleManager  = ModuleManager::create( xContext );
                Reference<XFrame> xFrame = pViewFrm->GetFrame().GetFrameInterface();
                OUString aModuleName = xModuleManager->identify( xFrame );

                Reference<XUIConfigurationManager> m_xConfigManager;
                Reference<XModuleUIConfigurationManagerSupplier > xModuleCfgMgrSupplier(
                    theModuleUIConfigurationManagerSupplier::get( xContext ) );
                m_xConfigManager.set( xModuleCfgMgrSupplier->getUIConfigurationManager( aModuleName ) );
                css::uno::Reference< css::ui::XUIConfiguration > xConfig( m_xConfigManager, css::uno::UNO_QUERY_THROW );
                xConfig->addConfigurationListener( this );
            }
        }
        catch( const css::uno::RuntimeException& ) {}
    }

    // XUIConfigurationListener
    virtual void SAL_CALL elementInserted( const ConfigurationEvent& rEvent ) override
    {
        if( rEvent.ResourceURL == TOOLBAR_STR )
        {
            m_pParent->m_bInvalidate = true;
            m_pParent->StateChanged(StateChangedType::UpdateMode);
        }
    }

    virtual void SAL_CALL elementRemoved( const ConfigurationEvent& rEvent ) override
    {
        elementInserted( rEvent );
    }

    virtual void SAL_CALL elementReplaced( const ConfigurationEvent& rEvent ) override
    {
        elementInserted( rEvent );
    }

    virtual void SAL_CALL disposing(const ::css::lang::EventObject&) override
    {
        try
        {
            if (SfxViewFrame* pViewFrm = SfxViewFrame::Current())
            {
                const Reference<XComponentContext>& xContext = comphelper::getProcessComponentContext();
                const Reference<XModuleManager> xModuleManager  = ModuleManager::create( xContext );
                Reference<XFrame> xFrame = pViewFrm->GetFrame().GetFrameInterface();
                OUString aModuleName = xModuleManager->identify( xFrame );

                Reference<XUIConfigurationManager> m_xConfigManager;
                Reference<XModuleUIConfigurationManagerSupplier > xModuleCfgMgrSupplier(
                    theModuleUIConfigurationManagerSupplier::get( xContext ) );
                m_xConfigManager.set( xModuleCfgMgrSupplier->getUIConfigurationManager( aModuleName ) );
                css::uno::Reference< css::ui::XUIConfiguration > xConfig( m_xConfigManager, css::uno::UNO_QUERY_THROW );
                xConfig->removeConfigurationListener( this );
            }
        }
        catch( const css::uno::RuntimeException& ) {}

        m_pParent.reset();
    }
};

namespace {

class ShortcutsToolBox : public sfx2::sidebar::SidebarToolBox
{
public:
    ShortcutsToolBox( Window* pParent )
    : sfx2::sidebar::SidebarToolBox( pParent )
    {
        mbUseDefaultButtonSize = false;
        mbSideBar = false;
        SetToolboxButtonSize(ToolBoxButtonSize::Small);
    }

    virtual void KeyInput( const KeyEvent& rKEvt ) override
    {
        if ( rKEvt.GetKeyCode().IsMod1() )
        {
            sal_uInt16 nCode( rKEvt.GetKeyCode().GetCode() );
            if ( nCode == KEY_RIGHT || nCode == KEY_LEFT )
            {
                GetParent()->KeyInput( rKEvt );
                return;
            }
        }
        return sfx2::sidebar::SidebarToolBox::KeyInput( rKEvt );
    }
};

}

NotebookbarTabControl::NotebookbarTabControl( Window* pParent )
: NotebookbarTabControlBase( pParent )
, m_bInitialized( false )
, m_bInvalidate( true )
{
}

NotebookbarTabControl::~NotebookbarTabControl()
{
}

void NotebookbarTabControl::Paint( vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect )
{
    // Draw the stock/native tab pane, header and tab items first; the Material band
    // treatment below is a pure overlay that never alters that geometry or hit-testing.
    NotebookbarTabControlBase::Paint( rRenderContext, rRect );

    // Material file-widget theme: overlay the tab-row band treatment -- a full-width
    // @outline-variant hairline along the bottom of the 38px tab row (the rule that
    // separates the tab row from the grouped command strip carrying the landed
    // @surface group-area wash) plus a 2px @primary underline beneath the active tab
    // (docs/design/05-navigation.md section 4). Both colors resolve through
    // vcl::MaterialTokens; high-contrast mode and the native/default theme both return
    // nullopt from the guard helper, so no Material code path runs and the stock tab
    // drawing above is the final pixel result (HC precedence on every branch).
    const std::optional<Color> oRule = lcl_materialTabControlColor("outline-variant");
    const std::optional<Color> oPrimary = lcl_materialTabControlColor("primary");
    if (!oRule && !oPrimary)
        return;

    const tools::Rectangle aTab = GetTabBounds( GetCurPageId() );
    if (aTab.IsEmpty())
        return;

    const tools::Long nWidth = GetOutputSizePixel().Width();
    const tools::Long nBaseline = aTab.Bottom();

    // @outline-variant tab-row band hairline (full width, 1px)
    if (oRule)
    {
        rRenderContext.SetLineColor(*oRule);
        rRenderContext.DrawLine(Point(0, nBaseline), Point(nWidth - 1, nBaseline));
    }

    // 2px @primary active-tab underline, drawn over the hairline segment so the active
    // tab reads as selected
    if (oPrimary)
    {
        rRenderContext.SetLineColor();
        rRenderContext.SetFillColor(*oPrimary);
        rRenderContext.DrawRect(tools::Rectangle(aTab.Left(), nBaseline - 1, aTab.Right(), nBaseline));
    }
}

void NotebookbarTabControl::ArrowStops( sal_uInt16 nCode )
{
    ToolBox* pToolBox( GetToolBox() );
    Control* pOpenMenu( GetOpenMenu() );

    if ( nCode == KEY_LEFT )
    {
        if ( HasFocus() )
        {
            if ( pToolBox )
                pToolBox->GrabFocus();
            else if ( pOpenMenu )
                pOpenMenu->GrabFocus();
        }
        else if ( pToolBox && pToolBox->HasFocus() )
        {
            if ( pOpenMenu )
                pOpenMenu->GrabFocus();
            else
                GrabFocus();
        }
        else if ( pOpenMenu && pOpenMenu->HasFocus() )
        {
            GrabFocus();
        }
    }
    else if ( nCode == KEY_RIGHT )
    {
        if ( HasFocus() )
        {
            if ( pOpenMenu )
                pOpenMenu->GrabFocus();
            else if ( pToolBox )
                pToolBox->GrabFocus();
        }
        else if ( pToolBox && pToolBox->HasFocus() )
        {
            GrabFocus();
        }
        else if ( pOpenMenu && pOpenMenu->HasFocus() )
        {
            if ( pToolBox )
                pToolBox->GrabFocus();
            else
                GrabFocus();
        }
    }
}

void NotebookbarTabControl::KeyInput( const KeyEvent& rKEvt )
{
    if ( rKEvt.GetKeyCode().IsMod1() )
    {
        sal_uInt16 nCode( rKEvt.GetKeyCode().GetCode() );
        if ( nCode == KEY_RIGHT || nCode == KEY_LEFT )
        {
            ArrowStops( nCode );
            return;
        }
    }
    return NotebookbarTabControlBase::KeyInput( rKEvt );
}

void NotebookbarTabControl::Command( const CommandEvent& rCEvt )
{
    if ( rCEvt.GetCommand() == CommandEventId::Wheel )
    {
        const CommandWheelData* pData = rCEvt.GetWheelData();
        if ( pData && !pData->GetModifier()
             && pData->GetMode() == CommandWheelMode::SCROLL
             && pData->GetDelta() != 0 )
        {
            // Debounce: require at least 100 ms between tab switches so that
            // casual scrolling does not rapidly cycle through tabs.
            auto now = std::chrono::steady_clock::now();
            static constexpr auto debounceMs = std::chrono::milliseconds(100);
            if ( now - m_lastTabSwitch >= debounceMs )
            {
                m_lastTabSwitch = now;
                ImplActivateTabPage( pData->GetDelta() < 0 );
            }
            return;
        }
    }
    NotebookbarTabControlBase::Command( rCEvt );
}

bool NotebookbarTabControl::EventNotify( NotifyEvent& rNEvt )
{
    if ( rNEvt.GetType() == NotifyEventType::KEYINPUT )
    {
        const vcl::KeyCode& rKey = rNEvt.GetKeyEvent()->GetKeyCode();
        sal_uInt16 nCode = rKey.GetCode();
        if ( rKey.IsMod1() && ( nCode == KEY_RIGHT || nCode == KEY_LEFT ) )
        {
            ArrowStops( nCode );
            return true;
        }
    }
    return NotebookbarTabControlBase::EventNotify( rNEvt );
}

void NotebookbarTabControl::StateChanged(StateChangedType nStateChange)
{
    SfxViewFrame* pViewFrm = SfxViewFrame::Current();
    if (!m_bInitialized && pViewFrm)
    {
        VclPtr<ShortcutsToolBox> pShortcuts = VclPtr<ShortcutsToolBox>::Create( this );
        pShortcuts->Show();

        SetToolBox(pShortcuts.get());
        SetIconClickHdl( LINK( this, NotebookbarTabControl, OpenNotebookbarPopupMenu ) );

        m_pListener = new ChangedUIEventListener( this );

        m_bInitialized = true;
    }
    if (m_bInitialized && m_bInvalidate && pViewFrm)
    {
        ToolBox* pToolBox = GetToolBox();
        if( !pToolBox )
            return;

        pToolBox->Clear();

        const Reference<XComponentContext>& xContext = comphelper::getProcessComponentContext();
        const Reference<XModuleManager> xModuleManager  = ModuleManager::create( xContext );
        m_xFrame = pViewFrm->GetFrame().GetFrameInterface();
        OUString aModuleName = xModuleManager->identify( m_xFrame );

        FillShortcutsToolBox( xContext, m_xFrame, aModuleName, pToolBox );

        Size aSize( pToolBox->GetOptimalSize() );
        Point aPos( ICON_SIZE + 10, 0 );
        pToolBox->SetPosSizePixel( aPos, aSize );
        ImplPlaceTabs( GetSizePixel().getWidth() );

        m_bInvalidate = false;
    }
    NotebookbarTabControlBase::StateChanged( nStateChange );
}

void NotebookbarTabControl::FillShortcutsToolBox(Reference<XComponentContext> const & xContext,
                                          const Reference<XFrame>& xFrame,
                                          const OUString& aModuleName,
                                          ToolBox* pShortcuts
)
{
    Reference<css::container::XIndexAccess> xIndex;

    try
    {
        Reference<XUIConfigurationManager> m_xConfigManager;
        Reference<XModuleUIConfigurationManagerSupplier > xModuleCfgMgrSupplier(
            theModuleUIConfigurationManagerSupplier::get( xContext ) );
        m_xConfigManager.set( xModuleCfgMgrSupplier->getUIConfigurationManager( aModuleName ) );
        xIndex = m_xConfigManager->getSettings( TOOLBAR_STR, false );
    }
    catch( const Exception& ) {}

    if ( !xIndex.is() )
        return;

    Sequence< css::beans::PropertyValue > aPropSequence;
    for ( sal_Int32 i = 0; i < xIndex->getCount(); ++i )
    {
        try
        {
            if ( xIndex->getByIndex( i ) >>= aPropSequence )
            {
                OUString aCommandURL;
                sal_uInt16 nType = ItemType::DEFAULT;
                bool bVisible = true;

                for (const auto& aProp : aPropSequence)
                {
                    if ( aProp.Name == "CommandURL" )
                        aProp.Value >>= aCommandURL;
                    else if ( aProp.Name == "Type" )
                        aProp.Value >>= nType;
                    else if ( aProp.Name == "IsVisible" )
                        aProp.Value >>= bVisible;
                }
                if ( bVisible && ( nType == ItemType::DEFAULT ) )
                    pShortcuts->InsertItem( aCommandURL, xFrame, ToolBoxItemBits::ICON_ONLY, Size( ICON_SIZE, ICON_SIZE ) );
            }
        }
        catch ( const Exception& )
        {
            break;
        }
    }
}

IMPL_LINK(NotebookbarTabControl, OpenNotebookbarPopupMenu, NotebookBar*, pNotebookbar, void)
{
    if (!pNotebookbar || !m_xFrame.is())
        return;

    Sequence<Any> aArgs {
        Any(comphelper::makePropertyValue(u"Value"_ustr, u"notebookbar"_ustr)),
        Any(comphelper::makePropertyValue(u"Frame"_ustr, m_xFrame)) };

    const Reference<XComponentContext>& xContext = comphelper::getProcessComponentContext();
    Reference<XPopupMenuController> xPopupController(
        xContext->getServiceManager()->createInstanceWithArgumentsAndContext(
        u"com.sun.star.comp.framework.ResourceMenuController"_ustr, aArgs, xContext), UNO_QUERY);

    rtl::Reference<VCLXPopupMenu> xPopupMenu = new VCLXPopupMenu();

    if (!xPopupController.is() || !xPopupMenu.is())
        return;

    xPopupController->setPopupMenu(xPopupMenu);
    Control* pOpenMenuButton = GetOpenMenu();
    assert(pOpenMenuButton);
    Point aPos(pOpenMenuButton->GetSizePixel().getWidth(), pOpenMenuButton->GetSizePixel().getHeight());
    xPopupMenu->execute(pOpenMenuButton->GetComponentInterface(),
                        css::awt::Rectangle(aPos.X(), aPos.Y(), 1, 1),
                        css::awt::PopupMenuDirection::EXECUTE_DOWN);

    Reference<css::lang::XComponent> xComponent(xPopupController, UNO_QUERY);
    if (xComponent.is())
        xComponent->dispose();
}

Size NotebookbarTabControl::calculateRequisition() const
{
    Size aSize = NotebookbarTabControlBase::calculateRequisition();

    for (int i = 0; i < GetPageCount(); i++)
    {
        vcl::Window* pChild = GetTabPage(TabControl::GetPageId(i));

        if (pChild)
        {
            Size aChildSize = VclContainer::getLayoutRequisition(*pChild);

            if (aChildSize.getWidth() < aSize.getWidth())
                aSize.setWidth( aChildSize.Width() );
        }
    }

    if (aSize.Width() < 400)
        aSize.setWidth( 400 );

    return aSize;
}

VCL_BUILDER_FACTORY( NotebookbarTabControl )

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
