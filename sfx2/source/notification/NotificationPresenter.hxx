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

#include <rtl/string.hxx>

#include <memory>

namespace vcl
{
class Window;
}

namespace sfx2
{
class NotificationStackController;
class NotificationManagerController;

/**
 * App-owned, main-thread coordinator between the async notification service and the visible surfaces.
 *
 * Data flow is snapshot-pull: every service request the presenter or router issues carries a
 * completion that hands the returned immutable snapshot to AdoptSnapshot. There is no push channel and
 * no polling loop. The presenter owns the stack controller always and the manager controller lazily,
 * re-anchors overlays on frame activation, and tolerates cancelled/late completions through an
 * alive-token guard (see the service shutdown contract).
 */
class NotificationPresenter final
{
public:
    NotificationPresenter();
    ~NotificationPresenter();

    NotificationPresenter(const NotificationPresenter&) = delete;
    NotificationPresenter& operator=(const NotificationPresenter&) = delete;

    /** Completion that adopts the returned snapshot on the VCL main thread, no-op if the presenter
        has been destroyed (cancelled/late completions are safe). */
    NotificationCenterService::Completion MakeRefreshCompletion();

    /** Generation-guarded adoption of a returned immutable snapshot. Drops stale/out-of-order
        generations and pushes the adopted snapshot into the live controllers. */
    void AdoptSnapshot(NotificationCenterSnapshotRef xState);

    /** The application notification service; controllers submit requests through it. */
    NotificationCenterService& GetService();

    /** The retained snapshot (may be null before the first adoption). */
    const NotificationCenterSnapshotRef& GetSnapshot() const { return m_xSnapshot; }

    /** Owner top-level window the overlays anchor to, or nullptr when none exists yet. */
    static vcl::Window* ResolveOwnerWindow();

    /** Show the manager overlay, optionally focused on one record. */
    void OpenManager(const OString& rFocusId = OString());
    /** Toggle the manager overlay open/closed. */
    void ToggleManager();
    /** Close the manager overlay. */
    void CloseManager();

    /** Re-anchor / recreate the overlays against the current owner window (frame activation). */
    void Reanchor();

private:
    std::shared_ptr<int> m_xAlive;
    sal_uInt64 m_nLastGeneration = 0;
    NotificationCenterSnapshotRef m_xSnapshot;
    std::unique_ptr<NotificationStackController> m_xStack;
    std::unique_ptr<NotificationManagerController> m_xManager;

    void EnsureStack();
    void EnsureManager();
    void PushSnapshotToControllers();
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
