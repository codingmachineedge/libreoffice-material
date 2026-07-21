/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationOverlayWindow.hxx"

#include <vcl/weld/Container.hxx>
#include <vcl/window.hxx>

#include <algorithm>

namespace sfx2
{
NotificationOverlayWindow::NotificationOverlayWindow(vcl::Window* pParent, const OUString& rUIFile,
                                                     const OUString& rId, bool bAllowCycleFocusOut)
    : InterimItemWindow(pParent, rUIFile, rId, bAllowCycleFocusOut)
{
    InitControlBase(m_xContainer.get());
}

NotificationOverlayWindow::~NotificationOverlayWindow() { disposeOnce(); }

void NotificationOverlayWindow::dispose()
{
    m_aLayoutHdl = Link<NotificationOverlayWindow&, void>();
    InterimItemWindow::dispose();
}

void NotificationOverlayWindow::Resize()
{
    InterimItemWindow::Resize();
    m_aLayoutHdl.Call(*this);
}

void NotificationOverlayWindow::RepositionBottomRight(sal_Int32 nHInset, sal_Int32 nVInset,
                                                      sal_Int32 nDesiredWidth)
{
    vcl::Window* pParent = GetParent();
    if (!pParent)
        return;

    const Size aParent(pParent->GetOutputSizePixel());
    const Size aOptimal(GetOptimalSize());

    tools::Long nWidth = nDesiredWidth > 0 ? nDesiredWidth : aOptimal.Width();
    const tools::Long nWidthBudget = aParent.Width() - 2 * nHInset;
    if (nWidthBudget > 0)
        nWidth = std::min<tools::Long>(nWidth, nWidthBudget);
    nWidth = std::max<tools::Long>(nWidth, 1);

    tools::Long nHeight = std::max<tools::Long>(aOptimal.Height(), 1);
    const tools::Long nHeightBudget = aParent.Height() - 2 * nVInset;
    if (nHeightBudget > 0)
        nHeight = std::min<tools::Long>(nHeight, nHeightBudget);

    tools::Long nX = aParent.Width() - nWidth - nHInset;
    tools::Long nY = aParent.Height() - nHeight - nVInset;
    nX = std::max<tools::Long>(nX, 0);
    nY = std::max<tools::Long>(nY, 0);

    SetPosSizePixel(Point(nX, nY), Size(nWidth, nHeight));
    Show();
    // Raise above siblings without grabbing top-level focus.
    SetZOrder(nullptr, ZOrderFlags::First);
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
