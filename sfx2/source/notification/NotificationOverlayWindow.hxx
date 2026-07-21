/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <vcl/InterimItemWindow.hxx>
#include <tools/link.hxx>

namespace sfx2
{
/**
 * Host vehicle for the notification stack and manager. A child overlay of the owning work area's
 * top-level window (never an OS top-level and never a FloatingWindow, which would auto-dismiss on
 * focus loss). Child-of-frame semantics keep it clipped with the owner and — for the stack — stop it
 * stealing top-level focus so typing continues in the document.
 */
class NotificationOverlayWindow final : public InterimItemWindow
{
public:
    NotificationOverlayWindow(vcl::Window* pParent, const OUString& rUIFile, const OUString& rId,
                              bool bAllowCycleFocusOut);
    virtual ~NotificationOverlayWindow() override;
    virtual void dispose() override;

    weld::Builder& GetBuilder() { return *m_xBuilder; }

    /** Anchor to the bottom-right of the parent client area, inset per preference, raised above
        siblings. Width is clamped to the parent width minus the insets; height follows the content
        optimal size clamped to the available height. */
    void RepositionBottomRight(sal_Int32 nHInset, sal_Int32 nVInset, sal_Int32 nDesiredWidth);

    virtual void Resize() override;
    void SetLayoutHdl(const Link<NotificationOverlayWindow&, void>& rLink) { m_aLayoutHdl = rLink; }

private:
    Link<NotificationOverlayWindow&, void> m_aLayoutHdl;
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
