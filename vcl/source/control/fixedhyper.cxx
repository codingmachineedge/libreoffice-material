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

#include <accessibility/vclxaccessiblefixedhyperlink.hxx>

#include <vcl/event.hxx>
#include <vcl/toolkit/fixedhyper.hxx>
#include <vcl/MaterialTokens.hxx>
#include <vcl/outdev.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/vclevent.hxx>
#include <vcl/weld/MessageDialog.hxx>
#include <vcl/ptrstyle.hxx>
#include <comphelper/anytostring.hxx>
#include <comphelper/processfactory.hxx>
#include <cppuhelper/exc_hlp.hxx>

#include <com/sun/star/system/XSystemShellExecute.hpp>
#include <com/sun/star/system/SystemShellExecuteFlags.hpp>
#include <com/sun/star/system/SystemShellExecute.hpp>

#include <cstdlib>
#include <optional>
#include <string_view>

using namespace css;

namespace
{
// Cached, per-scheme Material token table (see vcl::MaterialTokens): definition.xml
// is immutable at runtime, so it is parsed at most once per scheme. Only reached
// after the getenv gate in FixedHyperlink::ImplUseMaterialLink(), so the platform
// theme never parses it. The focus-ring color/radius flow through the named token
// table rather than any raw @primary hex or literal corner-focus pixel here.
const vcl::MaterialTokens* lcl_materialTokens()
{
    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    static std::optional<vcl::MaterialTokens> spLightTokens;
    static std::optional<vcl::MaterialTokens> spDarkTokens;
    std::optional<vcl::MaterialTokens>& rCache = bDark ? spDarkTokens : spLightTokens;
    if (!rCache)
        rCache = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    return rCache->isValid() ? &*rCache : nullptr;
}
}

FixedHyperlink::FixedHyperlink(vcl::Window* pParent, WinBits nWinStyle)
    : FixedText(pParent, nWinStyle, WindowType::LINK_BUTTON)
    , m_nTextLen(0)
    , m_aOldPointer(PointerStyle::Arrow)
    , m_bVisited(false)
    , m_bForcedNoTabStop(false)
{
    Initialize();
}

bool FixedHyperlink::ImplUseMaterialLink() const
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return false;

    // Resolved high contrast bypasses Material drawing entirely and restores the
    // native StyleSettings baseline, so the platform focus rectangle and platform
    // link colors apply there -- never force the Material corner-focus ring.
    return !Application::GetSettings().GetStyleSettings().GetHighContrastMode();
}

void FixedHyperlink::ImplUpdateLinkStyle()
{
    // Material may have gone inactive at runtime (e.g. high contrast toggled on)
    // while this link still held the forced disabled-link styling. Revert every
    // property the disabled branch forced -- non-focusable (WB_NOTABSTOP), no
    // underline, deactiveTextColor -- back to the platform baseline before the
    // early return below, so a link disabled under Material and then re-enabled
    // after the switch cannot stay keyboard-unreachable and underline-less. Runs
    // only after the disabled branch forced state (m_bForcedNoTabStop), so a
    // pure platform build never enters here.
    if (!ImplUseMaterialLink() && m_bForcedNoTabStop)
    {
        SetStyle(GetStyle() & ~WB_NOTABSTOP);
        m_bForcedNoTabStop = false;
        vcl::Font aRevertFont = GetControlFont();
        aRevertFont.SetUnderline(LINESTYLE_SINGLE);
        SetControlFont(aRevertFont);
        SetControlForeground(Application::GetSettings().GetStyleSettings().GetLinkColor());
        Invalidate();
    }

    // Default theme and resolved high contrast keep the inherited FixedText link
    // styling (single underline + platform link color, platform focus rectangle)
    // untouched: no non-Material rendering path is changed here.
    if (!ImplUseMaterialLink())
        return;

    const StyleSettings& rStyleSettings = GetSettings().GetStyleSettings();
    vcl::Font aFont = GetControlFont();

    if (IsEnabled())
    {
        // Enabled: a single underline that persists through hover with no color
        // tint; @primary while unvisited, @visited-link once visited.
        aFont.SetUnderline(LINESTYLE_SINGLE);
        SetControlFont(aFont);
        SetControlForeground(m_bVisited ? rStyleSettings.GetVisitedLinkColor()
                                        : rStyleSettings.GetLinkColor());
        if (m_bForcedNoTabStop)
        {
            // Restore the focusability we removed while disabled; never touch the
            // caller's own tab-stop intent that we did not change.
            SetStyle(GetStyle() & ~WB_NOTABSTOP);
            m_bForcedNoTabStop = false;
        }
    }
    else
    {
        // Disabled: deactiveTextColor (@outline) plain text -- no underline and
        // not focusable (dropped from tab traversal).
        aFont.SetUnderline(LINESTYLE_NONE);
        SetControlFont(aFont);
        SetControlForeground(rStyleSettings.GetDeactiveTextColor());
        if (!(GetStyle() & WB_NOTABSTOP))
        {
            SetStyle(GetStyle() | WB_NOTABSTOP);
            m_bForcedNoTabStop = true;
        }
    }

    Invalidate();
}

void FixedHyperlink::Initialize()
{
    // saves the old pointer
    m_aOldPointer = GetPointer();
    // changes the font
    vcl::Font aFont = GetControlFont( );
    // to underline
    aFont.SetUnderline( LINESTYLE_SINGLE );
    SetControlFont( aFont );
    // changes the color to link color
    SetControlForeground( Application::GetSettings().GetStyleSettings().GetLinkColor() );
    // calculates text len
    m_nTextLen = GetOutDev()->GetCtrlTextWidth( GetText() );

    SetClickHdl(LINK(this, FixedHyperlink, HandleClick));

    // Apply the Material enabled/visited/disabled link contract; a no-op under
    // the platform theme, so the legacy underline + link color set above stays.
    ImplUpdateLinkStyle();
}

bool FixedHyperlink::ImplIsOverText(Point aPosition) const
{
    Size aSize = GetOutputSizePixel();

    bool bIsOver = false;

    if (GetStyle() & WB_RIGHT)
    {
        return aPosition.X() > (aSize.Width() - m_nTextLen);
    }
    else if (GetStyle() & WB_CENTER)
    {
        bIsOver = aPosition.X() > (aSize.Width() / 2 - m_nTextLen / 2) &&
                  aPosition.X() < (aSize.Width() / 2 + m_nTextLen / 2);
    }
    else
    {
        bIsOver = aPosition.X() < m_nTextLen;
    }

    return bIsOver;
}

rtl::Reference<comphelper::OAccessible> FixedHyperlink::CreateAccessible()
{
    return new VCLXAccessibleFixedHyperlink(this);
}

void FixedHyperlink::MouseMove( const MouseEvent& rMEvt )
{
    // changes the pointer if the control is enabled and the mouse is over the text.
    if ( !rMEvt.IsLeaveWindow() && IsEnabled() && ImplIsOverText(GetPointerPosPixel()) )
        SetPointer( PointerStyle::RefHand );
    else
        SetPointer( m_aOldPointer );
}

void FixedHyperlink::MouseButtonUp( const MouseEvent& )
{
    // calls the link if the control is enabled and the mouse is over the text.
    if ( IsEnabled() && ImplIsOverText(GetPointerPosPixel()) )
    {
        // Activating the link visits it (exposed via IsVisited(); Material
        // repaints in @visited-link).
        SetVisited(true);
        ImplCallEventListenersAndHandler( VclEventId::ButtonClick, [this] () { m_aClickHdl.Call(*this); } );
    }
}

void FixedHyperlink::RequestHelp( const HelpEvent& rHEvt )
{
    if ( IsEnabled() && ImplIsOverText(GetPointerPosPixel()) )
        FixedText::RequestHelp( rHEvt );
}

tools::Rectangle FixedHyperlink::ImplGetFocusRect() const
{
    Size aSize = GetSizePixel();
    tools::Rectangle aFocusRect(Point(1, 1), Size(m_nTextLen + 4, aSize.Height() - 2));
    if (GetStyle() & WB_RIGHT)
        aFocusRect.Move(aSize.Width() - aFocusRect.getOpenWidth(), 0);
    else if (GetStyle() & WB_CENTER)
        aFocusRect.Move((aSize.Width() - aFocusRect.getOpenWidth()) / 2, 0);
    return aFocusRect;
}

void FixedHyperlink::ImplDrawFocusRing(vcl::RenderContext& rRenderContext)
{
    const vcl::MaterialTokens* pTokens = lcl_materialTokens();
    if (!pTokens)
        return;
    const std::optional<Color> oPrimary = pTokens->findColor("primary");
    const std::optional<sal_Int32> oRadius = pTokens->findRadius("corner-focus");
    if (!oPrimary || !oRadius)
        return;

    const tools::Rectangle aRing = ImplGetFocusRect();
    rRenderContext.Push(vcl::PushFlags::LINECOLOR | vcl::PushFlags::FILLCOLOR);
    rRenderContext.SetFillColor();
    rRenderContext.SetLineColor(*oPrimary);
    rRenderContext.DrawRect(aRing, *oRadius, *oRadius);
    rRenderContext.Pop();
}

void FixedHyperlink::Paint(vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect)
{
    FixedText::Paint(rRenderContext, rRect);

    // Material keyboard-focus affordance: the @primary corner-focus ring drawn
    // over the label. Gated on the Material theme being active and not high
    // contrast, so the platform focus rectangle is used everywhere else.
    if (HasFocus() && IsEnabled() && ImplUseMaterialLink())
        ImplDrawFocusRing(rRenderContext);
}

void FixedHyperlink::StateChanged(StateChangedType nType)
{
    FixedText::StateChanged(nType);

    // Re-apply the enabled/disabled Material link contract on an enable flip
    // (disabled -> @outline plain non-underlined non-focusable, and back).
    if (nType == StateChangedType::Enable)
        ImplUpdateLinkStyle();
}

void FixedHyperlink::DataChanged(const DataChangedEvent& rDCEvt)
{
    FixedText::DataChanged(rDCEvt);

    // A settings/theme change (e.g. dark/light or a high-contrast toggle)
    // re-resolves the Material link colors and focus suppression.
    if (rDCEvt.GetType() == DataChangedEventType::SETTINGS
        && (rDCEvt.GetFlags() & AllSettingsFlags::STYLE))
        ImplUpdateLinkStyle();
}

void FixedHyperlink::GetFocus()
{
    const tools::Rectangle aFocusRect = ImplGetFocusRect();
    Invalidate(aFocusRect);

    // Material keyboard focus: the @primary corner-focus ring is laid by
    // Paint(); suppress the platform focus rectangle. Under the platform theme
    // and in resolved high contrast this branch is skipped and the inherited
    // ShowFocus platform rectangle applies unchanged.
    if (ImplUseMaterialLink() && IsEnabled())
        return;

    ShowFocus(aFocusRect);
}

void FixedHyperlink::LoseFocus()
{
    SetTextColor( GetControlForeground() );
    Invalidate(tools::Rectangle(Point(), GetSizePixel()));
    HideFocus();
}

void FixedHyperlink::SetVisited(bool bVisited)
{
    if (m_bVisited == bVisited)
        return;
    m_bVisited = bVisited;
    // Repaints the link in @visited-link under Material; inert otherwise.
    ImplUpdateLinkStyle();
}

void FixedHyperlink::KeyInput( const KeyEvent& rKEvt )
{
    switch ( rKEvt.GetKeyCode().GetCode() )
    {
        case KEY_SPACE:
        case KEY_RETURN:
            // Keyboard activation visits the link, exactly as a pointer click.
            SetVisited(true);
            m_aClickHdl.Call( *this );
            break;

        default:
            FixedText::KeyInput( rKEvt );
    }
}

void FixedHyperlink::SetURL( const OUString& rNewURL )
{
    m_sURL = rNewURL;
    SetQuickHelpText( m_sURL );
}


void FixedHyperlink::SetText(const OUString& rNewDescription)
{
    FixedText::SetText(rNewDescription);
    m_nTextLen = GetOutDev()->GetCtrlTextWidth(GetText());
}

bool FixedHyperlink::set_property(const OUString &rKey, const OUString &rValue)
{
    if (rKey == "uri")
        SetURL(rValue);
    else
        return FixedText::set_property(rKey, rValue);
    return true;
}

IMPL_LINK(FixedHyperlink, HandleClick, FixedHyperlink&, rHyperlink, void)
{
    if ( rHyperlink.m_sURL.isEmpty() ) // Nothing to do, when the URL is empty
        return;

    try
    {
        uno::Reference< system::XSystemShellExecute > xSystemShellExecute(
            system::SystemShellExecute::create(comphelper::getProcessComponentContext()));
        //throws css::lang::IllegalArgumentException, css::system::SystemShellExecuteException
        xSystemShellExecute->execute( rHyperlink.m_sURL, OUString(), system::SystemShellExecuteFlags::URIS_ONLY );
    }
    catch ( const uno::Exception& )
    {
        uno::Any exc(cppu::getCaughtException());
        OUString msg(comphelper::anyToString(exc));
        SolarMutexGuard g;
        std::shared_ptr<weld::MessageDialog> xErrorBox(
            Application::CreateMessageDialog(GetFrameWeld(), VclMessageType::Error, VclButtonsType::Ok, msg));
        xErrorBox->set_title(rHyperlink.GetText());
        xErrorBox->runAsync(xErrorBox, [](sal_Int32){});
    }
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
