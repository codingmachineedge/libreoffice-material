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

#pragma once

#if !defined(VCL_DLLIMPLEMENTATION) && !defined(TOOLKIT_DLLIMPLEMENTATION) && !defined(VCL_INTERNALS)
#error "don't use this in new code"
#endif

#include <config_options.h>
#include <vcl/dllapi.h>
#include <vcl/toolkit/fixed.hxx>

class UNLESS_MERGELIBS(VCL_DLLPUBLIC) FixedHyperlink final : public FixedText
{
private:
    tools::Long                m_nTextLen;
    PointerStyle        m_aOldPointer;
    Link<FixedHyperlink&,void> m_aClickHdl;
    OUString            m_sURL;
    bool                m_bVisited;
    bool                m_bForcedNoTabStop;

    /** initializes the font (link color and underline).

        Called by the Ctors.
    */
    void                Initialize();

    /** is position X position hitting text */
    SAL_DLLPRIVATE bool ImplIsOverText(Point rPosition) const;

    /** true only when the documented Material file-widget theme is the active
        rendering (VCL_FILE_WIDGET_THEME=material) and high contrast is not
        resolved. false under the platform theme and in resolved high contrast,
        so every non-Material link rendering path stays untouched. */
    SAL_DLLPRIVATE bool ImplUseMaterialLink() const;

    /** applies the Material link contract for the current enabled/visited state:
        an enabled link keeps a single underline in @primary (unvisited) or
        @visited-link (visited); a disabled link becomes @outline
        (deactiveTextColor) plain, non-underlined, non-focusable text. Inert
        under the platform theme. */
    SAL_DLLPRIVATE void ImplUpdateLinkStyle();

    /** shared focus-rectangle geometry so the platform and Material focus paths
        use identical, text-alignment/RTL-correct bounds. */
    SAL_DLLPRIVATE tools::Rectangle ImplGetFocusRect() const;

    /** draws the Material keyboard-focus affordance: a @primary outline at
        corner-focus radius, replacing the platform focus rectangle. */
    SAL_DLLPRIVATE void ImplDrawFocusRing(vcl::RenderContext& rRenderContext);

    DECL_DLLPRIVATE_LINK(HandleClick, FixedHyperlink&, void);

    /** overwrites Window::MouseMove().

        Changes the pointer only over the text.
    */
    virtual void        MouseMove( const MouseEvent& rMEvt ) override;

    /** overwrites Window::MouseButtonUp().

        Calls the set link if the mouse is over the text.
    */
    virtual void        MouseButtonUp( const MouseEvent& rMEvt ) override;

    /** overwrites Window::RequestHelp().

        Shows tooltip only if the mouse is over the text.
    */
    virtual void        RequestHelp( const HelpEvent& rHEvt ) override;

    /** overwrites FixedText::Paint().

        After the label, lays the Material @primary corner-focus ring while the
        link is focused (Material active, enabled, not high contrast).
    */
    virtual void        Paint( vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect ) override;

    /** overwrites FixedText::StateChanged().

        Re-applies the Material link style when the enabled state flips.
    */
    virtual void        StateChanged( StateChangedType nType ) override;

    /** overwrites FixedText::DataChanged().

        Re-resolves the Material link colors on a settings/theme change.
    */
    virtual void        DataChanged( const DataChangedEvent& rDCEvt ) override;

public:
    /** ctors

        With WinBits.
    */
    FixedHyperlink( vcl::Window* pParent, WinBits nWinStyle = 0 );

    virtual rtl::Reference<comphelper::OAccessible> CreateAccessible() override;

    /** overwrites Window::GetFocus().

        Changes the color of the text and shows a focus rectangle.
    */
    virtual void        GetFocus() override;

    /** overwrites Window::LoseFocus().

        Changes the color of the text and hides the focus rectangle.
    */
    virtual void        LoseFocus() override;

    /** overwrites Window::KeyInput().

        KEY_RETURN and KEY_SPACE calls the link handler.
    */
    virtual void        KeyInput( const KeyEvent& rKEvt ) override;

    virtual bool        set_property(const OUString &rKey, const OUString &rValue) override;


    /** sets m_aClickHdl with rLink.

        m_aClickHdl is called if the text is clicked.
    */
    void         SetClickHdl( const Link<FixedHyperlink&,void>& rLink ) { m_aClickHdl = rLink; }
    const Link<FixedHyperlink&,void>& GetClickHdl() const { return m_aClickHdl; }

    // ::FixedHyperbaseLink

    /** sets the URL of the hyperlink and uses it as tooltip. */
    void                SetURL(const OUString& rNewURL);

    /** returns the URL of the hyperlink.

        @return
            m_sURL
    */
    const OUString&     GetURL() const { return m_sURL;}

    /** marks the link visited (Material @visited-link) and exposes the visited
        state; activating either link surface -- the native widget or the
        weld::LinkButton wrapper -- records the visit through here. */
    void                SetVisited(bool bVisited);

    /** exposes whether the link has been activated (visited). */
    bool                IsVisited() const { return m_bVisited; }

    /** sets new text and recalculates the text length. */
    virtual void        SetText(const OUString& rNewDescription) override;
};

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
