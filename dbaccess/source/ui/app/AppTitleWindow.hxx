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

#include <ChildWindow.hxx>

#include <unotools/resmgr.hxx>

namespace dbaui
{
    class OTitleWindow final
    {
    public:
        /** Shared-control style variant (docs/design/12-base-math-shared.md 12.1):
            the same OTitleWindow class heads the rail ("Database") and the task /
            object-list panes, but the rail instance is a Material "kicker" while the
            others are section "headings". Defaulting to Heading keeps every existing
            (non-rail) call site unchanged. */
        enum class TitleStyle
        {
            Heading, // 16 px/600 @on-surface section / task heading (default)
            Kicker,  // uppercase 11 px/700 @on-surface-variant rail kicker
        };

    private:
        std::unique_ptr<weld::Builder> m_xBuilder;
        std::unique_ptr<weld::Container> m_xContainer;
        std::unique_ptr<weld::Container> m_xTitleFrame;
        std::unique_ptr<weld::Label> m_xTitle;
        std::unique_ptr<weld::Container> m_xChildContainer;
        std::shared_ptr<OChildWindow> m_xChild;
        TitleStyle m_eStyle;

    public:
        OTitleWindow(weld::Container* pParent, TranslateId pTitleId,
                     TitleStyle eStyle = TitleStyle::Heading);
        ~OTitleWindow();

        void GrabFocus();

        bool HasChildPathFocus() const;

        /** gets the window which should be used as a child's parent */
        weld::Container* getChildContainer();

        /** sets the child window which should be displayed below the title. It will be destroyed at the end.
            @param  _pChild
                The child window.
        */
        void setChildWindow(const std::shared_ptr<OChildWindow>& rChild);

        /** gets the child window.

            @return
                The child window.
        */
        OChildWindow* getChildWindow() const { return m_xChild.get(); }

        /** sets the title text out of the resource
            @param  pTitleId
                The resource id of the title text.
        */
        void setTitle(TranslateId pTitleId);
    };
} // namespace dbaui

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
