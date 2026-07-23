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

#include "AppTitleWindow.hxx"

#include <core_resource.hxx>

#include <vcl/font.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/weld/Label.hxx>
#include <vcl/MaterialTokens.hxx>
#include <tools/color.hxx>
#include <tools/fontenum.hxx>

#include <cstdlib>
#include <optional>
#include <string_view>

namespace
{
// Guarded Material Base rail-kicker treatment (docs/design/12-base-math-shared.md
// 12.1). Same env + high-contrast guard idiom as sc/source/ui/app/inputwin.cxx's
// formula-bar resolver: only while the documented Material file-widget theme is
// active (and not forced high contrast) does the kicker resolve its colour token.
bool lcl_isMaterialBaseActive()
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return false;
    if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())
        return false;
    return true;
}

// The rail kicker text is @on-surface-variant (12.1 "Rail kicker").
std::optional<Color> lcl_getMaterialKickerColor()
{
    if (!lcl_isMaterialBaseActive())
        return std::nullopt;
    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    const vcl::MaterialTokens aTokens
        = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    if (!aTokens.isValid())
        return std::nullopt;
    return aTokens.findColor("on-surface-variant");
}
} // namespace

namespace dbaui
{
OTitleWindow::OTitleWindow(weld::Container* pParent, TranslateId pTitleId, TitleStyle eStyle)
    : m_xBuilder(Application::CreateBuilder(pParent, u"dbaccess/ui/titlewindow.ui"_ustr))
    , m_xContainer(m_xBuilder->weld_container(u"TitleWindow"_ustr))
    , m_xTitleFrame(m_xBuilder->weld_container(u"titleparent"_ustr))
    , m_xTitle(m_xBuilder->weld_label(u"title"_ustr))
    , m_xChildContainer(m_xBuilder->weld_container(u"box"_ustr))
    , m_eStyle(eStyle)
{
    setTitle(pTitleId);

    m_xContainer->set_stack_background();
    m_xTitleFrame->set_title_background();
    m_xTitle->set_label_type(weld::LabelType::Title);

    if (m_eStyle == TitleStyle::Kicker)
    {
        // Material rail kicker (12.1 "Rail kicker"): @on-surface-variant, bold. The
        // uppercase transform and 0.06 em tracking are typographic refinements with
        // no weld hook, deferred to a build; this pins colour + weight + guard only.
        if (const std::optional<Color> oKicker = lcl_getMaterialKickerColor())
        {
            m_xTitle->set_font_color(*oKicker);
            vcl::Font aFont(Application::GetSettings().GetStyleSettings().GetLabelFont());
            aFont.SetWeight(WEIGHT_BOLD);
            m_xTitle->set_font(aFont);
        }
    }
}

OTitleWindow::~OTitleWindow() {}

weld::Container* OTitleWindow::getChildContainer() { return m_xChildContainer.get(); }

void OTitleWindow::setChildWindow(const std::shared_ptr<OChildWindow>& rChild)
{
    m_xChild = rChild;
}

void OTitleWindow::setTitle(TranslateId pTitleId)
{
    if (!pTitleId)
        return;
    m_xTitle->set_label(DBA_RES(pTitleId));
}

void OTitleWindow::GrabFocus()
{
    if (m_xChild)
        m_xChild->GrabFocus();
}

bool OTitleWindow::HasChildPathFocus() const { return m_xChild && m_xChild->HasChildPathFocus(); }

} // namespace dbaui
/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
