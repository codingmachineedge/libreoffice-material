/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/notificationcenter.hxx>

#include <tools/link.hxx>
#include <vcl/timer.hxx>
#include <vcl/vclptr.hxx>

#include <memory>
#include <vector>

namespace vcl
{
class Window;
}
namespace weld
{
class Box;
class Button;
class Label;
}

namespace sfx2
{
class NotificationPresenter;
class NotificationOverlayWindow;
class NotificationCard;

/** Builds and maintains the bottom-right card stack, overflow control, and manager FAB from the
    retained snapshot and preferences. All card actions map to one service request each. */
class NotificationStackController final
{
public:
    NotificationStackController(NotificationPresenter& rPresenter, vcl::Window* pOwner);
    ~NotificationStackController();

    void SetSnapshot(const NotificationCenterSnapshotRef& xSnapshot);
    void Reanchor(vcl::Window* pOwner);

private:
    NotificationPresenter& m_rPresenter;
    VclPtr<NotificationOverlayWindow> m_xOverlay;
    std::unique_ptr<weld::Box> m_xCardBox;
    std::unique_ptr<weld::Button> m_xOverflow;
    std::unique_ptr<weld::Button> m_xManagerButton;
    std::unique_ptr<weld::Label> m_xBadge;
    std::unique_ptr<weld::Label> m_xLive;
    std::vector<std::unique_ptr<NotificationCard>> m_aCards;
    NotificationCenterSnapshotRef m_xSnapshot;
    sal_uInt64 m_nLastAnnouncedGeneration = 0;
    Timer m_aAutoDismiss;

    void Create(vcl::Window* pOwner);
    void Rebuild();
    void ScheduleAutoDismiss(const NotificationPreferences& rPreferences, sal_uInt32 nVisible);

    DECL_LINK(OverflowHdl, weld::Button&, void);
    DECL_LINK(ManagerButtonHdl, weld::Button&, void);
    DECL_LINK(AutoDismissHdl, Timer*, void);
    DECL_LINK(LayoutHdl, NotificationOverlayWindow&, void);
    DECL_LINK(CardDetailsHdl, const OString&, void);
    DECL_LINK(CardDismissHdl, const OString&, void);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
