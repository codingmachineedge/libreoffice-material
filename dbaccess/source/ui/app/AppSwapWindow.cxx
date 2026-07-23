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

#include "AppSwapWindow.hxx"
#include <helpids.h>
#include "AppView.hxx"
#include <sfx2/thumbnailviewitem.hxx>
#include <vcl/event.hxx>
#include <vcl/mnemonic.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/MaterialTokens.hxx>
#include <tools/color.hxx>
#include "AppController.hxx"

#include <cstdlib>
#include <optional>
#include <string_view>

using namespace ::dbaui;

namespace
{
// Guarded Material Base navigation-rail treatment (docs/design/12-base-math-shared.md
// 12.1). The env + high-contrast guard idiom mirrors sc/source/ui/app/inputwin.cxx's
// formula-bar resolver and sfx2/source/control/startcentercard.cxx: only while the
// documented Material file-widget theme is active (and not forced high contrast) does
// the rail resolve a token; otherwise the generic StyleSettings path is left intact.
bool lcl_isMaterialBaseActive()
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return false;
    if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())
        return false;
    return true;
}

// The Base navigation rail fills @surface-container (12.1 "Database nav rail").
std::optional<Color> lcl_getMaterialRailFill()
{
    if (!lcl_isMaterialBaseActive())
        return std::nullopt;
    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    const vcl::MaterialTokens aTokens
        = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    if (!aTokens.isValid())
        return std::nullopt;
    return aTokens.findColor("surface-container");
}
} // namespace

OApplicationSwapWindow::OApplicationSwapWindow(weld::Container* pParent,
                                               OAppBorderWindow& rBorderWindow)
    : OChildWindow(pParent, u"dbaccess/ui/appswapwindow.ui"_ustr, u"AppSwapWindow"_ustr)
    , m_xIconControl(
          new OApplicationIconControl(m_xBuilder->weld_scrolled_window(u"scroll"_ustr, true)))
    , m_xIconControlWin(new weld::CustomWeld(*m_xBuilder, u"valueset"_ustr, *m_xIconControl))
    , m_eLastType(E_NONE)
    , m_rBorderWin(rBorderWindow)
    , m_nChangeEvent(nullptr)
{
    // Material Base rail: @surface-container fill while the Material theme is active,
    // else the generic stacked background (non-Material paths untouched).
    if (const std::optional<Color> oRailFill = lcl_getMaterialRailFill())
        m_xContainer->set_background(*oRailFill);
    else
        m_xContainer->set_stack_background();

    m_xIconControl->SetHelpId(HID_APP_SWAP_ICONCONTROL);
    m_xIconControl->Fill();
    m_xIconControl->setItemStateHdl(LINK(this, OApplicationSwapWindow, OnContainerSelectHdl));
    m_xIconControl->setControlActionListener(&m_rBorderWin.getView()->getAppController());
}

void OApplicationSwapWindow::GrabFocus()
{
    if (m_xIconControl)
        m_xIconControl->GrabFocus();
}

bool OApplicationSwapWindow::HasChildPathFocus() const
{
    return m_xIconControl && m_xIconControl->HasFocus();
}

OApplicationSwapWindow::~OApplicationSwapWindow()
{
    if (m_nChangeEvent)
        Application::RemoveUserEvent(m_nChangeEvent);
}

void OApplicationSwapWindow::clearSelection()
{
    m_xIconControl->deselectItems();
    onContainerSelected(E_NONE);
}

void OApplicationSwapWindow::createIconAutoMnemonics(MnemonicGenerator& rMnemonics)
{
    m_xIconControl->createIconAutoMnemonics(rMnemonics);
}

bool OApplicationSwapWindow::interceptKeyInput(const KeyEvent& _rEvent)
{
    const vcl::KeyCode& rKeyCode = _rEvent.GetKeyCode();
    if (rKeyCode.GetModifier() == KEY_MOD2)
        return m_xIconControl->DoKeyShortCut(_rEvent);
    // not handled
    return false;
}

ElementType OApplicationSwapWindow::getElementType() const
{
    return m_xIconControl->GetSelectedItem();
}

bool OApplicationSwapWindow::onContainerSelected(ElementType _eType)
{
    if (m_eLastType == _eType)
        return true;

    if (m_rBorderWin.getView()->getAppController().onContainerSelect(_eType))
    {
        if (_eType != E_NONE)
            m_eLastType = _eType;
        return true;
    }

    if (!m_nChangeEvent)
        m_nChangeEvent
            = Application::PostUserEvent(LINK(this, OApplicationSwapWindow, ChangeToLastSelected));
    return false;
}

IMPL_LINK(OApplicationSwapWindow, OnContainerSelectHdl, const ThumbnailViewItem*, pEntry, void)
{
    if (pEntry->mbSelected)
    {
        ElementType eType = static_cast<ElementType>(pEntry->mnId - 1);
        onContainerSelected(eType); // i87582
    }
}

IMPL_LINK_NOARG(OApplicationSwapWindow, ChangeToLastSelected, void*, void)
{
    m_nChangeEvent = nullptr;
    selectContainer(m_eLastType);
}

void OApplicationSwapWindow::selectContainer(ElementType eType)
{
    m_xIconControl->deselectItems();
    m_xIconControl->SelectItem(eType + 1); // will trigger onContainerSelected
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
