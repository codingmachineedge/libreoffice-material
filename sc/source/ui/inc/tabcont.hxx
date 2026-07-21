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

#include <types.hxx>
#include <svtools/tabbar.hxx>
#include <vcl/transfer.hxx>
#include <tools/color.hxx>
#include <map>

class ScViewData;

//  initial size
#define SC_TABBAR_DEFWIDTH      270

class ScTabControl : public TabBar, public DropTargetHelper, public DragSourceHelper
{
private:
    ScViewData&     rViewData;
    sal_uInt16      nMouseClickPageId;      /// Last page ID after mouse button down/up
    sal_uInt16      nSelPageIdByMouse;      /// Selected page ID, if selected with mouse
    bool            bErrorShown;

    /// User sheet-tab colours held out of the TabBar base full-tab fill while the
    /// Material file-widget theme is active, so they can be drawn as an accent
    /// strip under the label (docs/design/05-navigation.md 6.4) instead of a
    /// full fill that would compete with the selection treatment.
    std::map<sal_uInt16, Color> maMaterialTabColors;

    void            DoDrag();

    sal_uInt16      GetMaxId() const;
    SCTAB           GetPrivatDropPos(const Point& rPos );

    /// True only when VCL_FILE_WIDGET_THEME=material is the documented active
    /// theme and high contrast is not resolved (native baseline bypass).
    bool            IsMaterialSheetTabActive() const;
    /// Route a document tab colour: under the Material theme record it for the
    /// accent-strip overlay and leave the base tab neutral; otherwise apply the
    /// existing full-fill path unchanged.
    void            SetMaterialAwareTabBgColor( sal_uInt16 nPageId, const Color& rColor );
    /// Draw the Material strip top rule and the per-tab colour accent strips on
    /// top of the base paint; never consults the selection state.
    void            PaintMaterialSheetTabOverlay( vcl::RenderContext& rRenderContext );

    DECL_LINK(ShowPageList, const CommandEvent&, void);

protected:
    virtual void    Paint( vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect ) override;
    virtual void    Select() override;
    virtual void    Command( const CommandEvent& rCEvt ) override;
    virtual void    MouseButtonDown( const MouseEvent& rMEvt ) override;
    virtual void    MouseButtonUp( const MouseEvent& rMEvt ) override;

    virtual sal_Int8 AcceptDrop( const AcceptDropEvent& rEvt ) override;
    virtual sal_Int8 ExecuteDrop( const ExecuteDropEvent& rEvt ) override;

    virtual void    StartDrag( sal_Int8 nAction, const Point& rPosPixel ) override;

    virtual bool    StartRenaming() override;
    virtual TabBarAllowRenamingReturnCode    AllowRenaming() override;
    virtual void    EndRenaming() override;
    virtual void    Mirror() override;

    virtual void    AddTabClick() override;

public:
                    ScTabControl( vcl::Window* pParent, ScViewData& rData );
    virtual void    dispose() override;
                    virtual ~ScTabControl() override;

    using TabBar::StartDrag;

    void            UpdateInputContext();
    void            UpdateStatus();

    void            SetSheetLayoutRTL( bool bSheetRTL );
    void            SwitchToPageId( sal_uInt16 nId );
};

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
