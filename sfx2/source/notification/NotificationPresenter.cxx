/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationPresenter.hxx"
#include "NotificationManagerController.hxx"
#include "NotificationStackController.hxx"

#include <sfx2/app.hxx>
#include <sfx2/viewfrm.hxx>

#include <vcl/svapp.hxx>
#include <vcl/window.hxx>

#include <utility>

namespace sfx2
{
NotificationPresenter::NotificationPresenter()
    : m_xAlive(std::make_shared<int>(0))
{
    assert(Application::IsMainThread());
    EnsureStack();
    // Seed initial state; the completion adopts the returned authoritative snapshot.
    GetService().requestSnapshot(MakeRefreshCompletion());
}

NotificationPresenter::~NotificationPresenter()
{
    // Destroy the overlays (via the controllers) while VCL is alive. m_xAlive then expires, so any
    // completion the service still drains during its own shutdown is a guarded no-op.
    m_xManager.reset();
    m_xStack.reset();
}

NotificationCenterService& NotificationPresenter::GetService()
{
    return SfxGetpApp()->GetNotificationCenter();
}

vcl::Window* NotificationPresenter::ResolveOwnerWindow()
{
    if (SfxViewFrame* pFrame = SfxViewFrame::Current())
    {
        vcl::Window& rWindow = pFrame->GetWindow();
        if (vcl::Window* pTop = rWindow.GetWindow(GetWindowType::Frame))
            return pTop;
        return &rWindow;
    }
    // No document frame: anchor to the backing / Start Center top-level when present.
    return Application::GetFirstTopLevelWindow();
}

NotificationCenterService::Completion NotificationPresenter::MakeRefreshCompletion()
{
    std::weak_ptr<int> xWeak = m_xAlive;
    return [this, xWeak](NotificationCenterResult aResult) {
        // Delivered on the VCL main thread. A cancelled or late completion whose presenter has been
        // destroyed is a safe no-op; a later requestSnapshot reconciles.
        if (xWeak.expired())
            return;
        AdoptSnapshot(aResult.State);
    };
}

void NotificationPresenter::AdoptSnapshot(NotificationCenterSnapshotRef xState)
{
    // Generation guard: drop null, stale, or out-of-order snapshots. Any request's returned snapshot
    // is authoritative, so reordering is harmless.
    if (!xState || xState->Generation <= m_nLastGeneration)
        return;
    m_nLastGeneration = xState->Generation;
    m_xSnapshot = std::move(xState);
    PushSnapshotToControllers();
}

void NotificationPresenter::PushSnapshotToControllers()
{
    if (m_xStack)
        m_xStack->SetSnapshot(m_xSnapshot);
    if (m_xManager)
        m_xManager->SetSnapshot(m_xSnapshot);
}

void NotificationPresenter::EnsureStack()
{
    if (!m_xStack)
        m_xStack = std::make_unique<NotificationStackController>(*this, ResolveOwnerWindow());
}

void NotificationPresenter::EnsureManager()
{
    if (!m_xManager)
    {
        m_xManager = std::make_unique<NotificationManagerController>(*this, ResolveOwnerWindow());
        if (m_xSnapshot)
            m_xManager->SetSnapshot(m_xSnapshot);
    }
}

void NotificationPresenter::OpenManager(const OString& rFocusId)
{
    EnsureManager();
    if (m_xManager)
        m_xManager->Show(rFocusId);
}

void NotificationPresenter::ToggleManager()
{
    EnsureManager();
    if (!m_xManager)
        return;
    if (m_xManager->IsVisible())
        m_xManager->Hide();
    else
        m_xManager->Show(OString());
}

void NotificationPresenter::CloseManager()
{
    if (m_xManager)
        m_xManager->Hide();
}

void NotificationPresenter::Reanchor()
{
    vcl::Window* pOwner = ResolveOwnerWindow();
    if (m_xStack)
        m_xStack->Reanchor(pOwner);
    if (m_xManager)
        m_xManager->Reanchor(pOwner);
    PushSnapshotToControllers();
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
