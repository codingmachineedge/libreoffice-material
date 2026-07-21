/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationStackController.hxx"
#include "NotificationCard.hxx"
#include "NotificationOverlayWindow.hxx"
#include "NotificationPresenter.hxx"
#include "NotificationViewModel.hxx"

#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>

#include <vcl/weld/Box.hxx>
#include <vcl/weld/Button.hxx>
#include <vcl/weld/Label.hxx>

#include <algorithm>

namespace sfx2
{
NotificationStackController::NotificationStackController(NotificationPresenter& rPresenter,
                                                        vcl::Window* pOwner)
    : m_rPresenter(rPresenter)
    , m_aAutoDismiss("sfx2::NotificationStackController auto-dismiss")
{
    m_aAutoDismiss.SetInvokeHandler(LINK(this, NotificationStackController, AutoDismissHdl));
    Create(pOwner);
}

NotificationStackController::~NotificationStackController()
{
    m_aAutoDismiss.Stop();
    m_aCards.clear();
    if (m_xOverlay)
        m_xOverlay.disposeAndClear();
}

void NotificationStackController::Create(vcl::Window* pOwner)
{
    if (!pOwner)
        return;

    // The stack lets Tab escape back to the document, so it never steals focus while typing.
    m_xOverlay = VclPtr<NotificationOverlayWindow>::Create(
        pOwner, u"sfx/ui/notificationstack.ui"_ustr, u"NotificationStack"_ustr,
        /*bAllowCycleFocusOut*/ true);

    weld::Builder& rBuilder = m_xOverlay->GetBuilder();
    m_xCardBox = rBuilder.weld_box(u"stack_cards"_ustr);
    m_xOverflow = rBuilder.weld_button(u"overflow_button"_ustr);
    m_xManagerButton = rBuilder.weld_button(u"manager_button"_ustr);
    m_xBadge = rBuilder.weld_label(u"manager_badge"_ustr);
    m_xLive = rBuilder.weld_label(u"live_region"_ustr);

    m_xOverflow->connect_clicked(LINK(this, NotificationStackController, OverflowHdl));
    m_xManagerButton->connect_clicked(LINK(this, NotificationStackController, ManagerButtonHdl));
    m_xOverlay->SetLayoutHdl(LINK(this, NotificationStackController, LayoutHdl));
}

void NotificationStackController::Reanchor(vcl::Window* pOwner)
{
    m_aAutoDismiss.Stop();
    m_aCards.clear();
    m_xCardBox.reset();
    m_xOverflow.reset();
    m_xManagerButton.reset();
    m_xBadge.reset();
    m_xLive.reset();
    if (m_xOverlay)
        m_xOverlay.disposeAndClear();
    Create(pOwner);
    Rebuild();
}

void NotificationStackController::SetSnapshot(const NotificationCenterSnapshotRef& xSnapshot)
{
    m_xSnapshot = xSnapshot;
    Rebuild();
}

void NotificationStackController::Rebuild()
{
    if (!m_xOverlay || !m_xCardBox || !m_xSnapshot)
        return;

    const NotificationPreferences& rPrefs = m_xSnapshot->Preferences;

    // Cards clear their welded widgets on destruction, removing them from the box.
    m_aCards.clear();

    const std::vector<NotificationDisplayRow> aRows
        = NotificationViewModel::VisibleCards(*m_xSnapshot, rPrefs);
    const sal_uInt32 nHidden = NotificationViewModel::HiddenCardCount(*m_xSnapshot, rPrefs);

    // When notifications are disabled, suppress the auto-shown cards but keep the manager reachable.
    const bool bShowCards = rPrefs.Enabled;

    if (bShowCards)
    {
        // Newest is nearest the bottom: append oldest-first into the vertical box.
        for (auto it = aRows.rbegin(); it != aRows.rend(); ++it)
        {
            auto xCard = std::make_unique<NotificationCard>(m_xCardBox.get(), *it, rPrefs);
            xCard->SetDetailsHdl(LINK(this, NotificationStackController, CardDetailsHdl));
            xCard->SetDismissHdl(LINK(this, NotificationStackController, CardDismissHdl));
            m_aCards.push_back(std::move(xCard));
        }
    }

    if (nHidden > 0 && bShowCards)
    {
        m_xOverflow->set_label(
            SfxResId(STR_NOTIF_OVERFLOW).replaceFirst(u"%1"_ustr, OUString::number(nHidden)));
        m_xOverflow->set_visible(true);
    }
    else
        m_xOverflow->set_visible(false);

    const NotificationCounts aCounts = NotificationViewModel::Counts(*m_xSnapshot);
    m_xManagerButton->set_accessible_name(SfxResId(STR_NOTIF_OPEN_MANAGER)
                                              .replaceFirst(u"%1"_ustr,
                                                            OUString::number(aCounts.Unread)));
    if (aCounts.Unread > 0 && rPrefs.Enabled)
    {
        m_xBadge->set_label(OUString::number(aCounts.Unread));
        m_xBadge->set_visible(true);
    }
    else
        m_xBadge->set_visible(false);

    m_xOverlay->RepositionBottomRight(rPrefs.HorizontalInset, rPrefs.VerticalInset, rPrefs.Width);

    // Announce the new generation once through the polite live region (reinforcement only).
    if (m_xSnapshot->Generation != m_nLastAnnouncedGeneration && !aRows.empty())
    {
        m_nLastAnnouncedGeneration = m_xSnapshot->Generation;
        m_xLive->set_label(
            SfxResId(STR_NOTIF_ANNOUNCE_NEW).replaceFirst(u"%1"_ustr, aRows.front().SourceLabel));
    }

    ScheduleAutoDismiss(rPrefs, static_cast<sal_uInt32>(aRows.size()));
}

void NotificationStackController::ScheduleAutoDismiss(const NotificationPreferences& rPreferences,
                                                      sal_uInt32 nVisible)
{
    m_aAutoDismiss.Stop();
    // Never auto-dismiss when disabled or when the timeout is off; decision-required prompts never
    // reach the stack this checkpoint (they keep modal semantics).
    if (!rPreferences.Enabled || rPreferences.TimeoutSeconds <= 0 || nVisible == 0)
        return;
    m_aAutoDismiss.SetTimeout(static_cast<sal_uInt64>(rPreferences.TimeoutSeconds) * 1000);
    m_aAutoDismiss.Start();
}

IMPL_LINK_NOARG(NotificationStackController, AutoDismissHdl, Timer*, void)
{
    if (!m_xSnapshot)
        return;
    const std::vector<NotificationDisplayRow> aRows
        = NotificationViewModel::VisibleCards(*m_xSnapshot, m_xSnapshot->Preferences);
    if (aRows.empty())
        return;
    // Archive the oldest visible card (top of the stack); still in Inbox because VisibleCards only
    // returns unarchived, undeleted Inbox rows from the current snapshot.
    const OString aOldest = aRows.back().Id;
    m_rPresenter.GetService().archive({ aOldest }, m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationStackController, OverflowHdl, weld::Button&, void)
{
    m_rPresenter.OpenManager();
}

IMPL_LINK_NOARG(NotificationStackController, ManagerButtonHdl, weld::Button&, void)
{
    m_rPresenter.ToggleManager();
}

IMPL_LINK_NOARG(NotificationStackController, LayoutHdl, NotificationOverlayWindow&, void) {}

IMPL_LINK(NotificationStackController, CardDetailsHdl, const OString&, rId, void)
{
    m_rPresenter.OpenManager(rId);
}

IMPL_LINK(NotificationStackController, CardDismissHdl, const OString&, rId, void)
{
    // Dismiss = the prototype's card close = archive (one-way, recoverable). One service request.
    m_rPresenter.GetService().archive({ rId }, m_rPresenter.MakeRefreshCompletion());
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
