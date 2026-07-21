/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationrouter.hxx>

#include "NotificationPresenter.hxx"

#include <sfx2/app.hxx>

#include <vcl/svapp.hxx>

#include <utility>

namespace sfx2
{
void NotificationRouter::Notify(NotificationDraft aDraft)
{
    // Non-blocking, fire-and-forget on the VCL main thread.
    assert(Application::IsMainThread());
    SfxApplication* pApp = SfxGetpApp();
    if (!pApp)
        return;

    // Ensure the presenter exists so its refresh completion can adopt the returned snapshot, then
    // submit exactly one add request carrying that guarded completion.
    NotificationPresenter& rPresenter = pApp->GetNotificationPresenter();
    pApp->GetNotificationCenter().add(std::move(aDraft), rPresenter.MakeRefreshCompletion());
}

void NotificationRouter::NotifyInfo(const OString& rSource, NotificationSeverity eSeverity,
                                    const OUString& rTitle, const OUString& rBody)
{
    NotificationDraft aDraft;
    aDraft.Source = rSource;
    aDraft.Severity = eSeverity;
    // SafeDisplayText is honored only for audited built-in sources; the store redacts every other
    // source regardless of this hint.
    aDraft.Privacy = NotificationPrivacy::SafeDisplayText;
    aDraft.Title = rTitle;
    aDraft.Body = rBody;
    Notify(std::move(aDraft));
}

NotificationRoute NotificationRouter::Classify(bool bCollectsInput, bool bConfirmsDestructive,
                                               bool bCredential, bool bSecurity)
{
    // Prompts that collect input, confirm a destructive act, handle credentials, or enforce security
    // keep modal semantics; everything purely informational routes to a notification.
    if (bCollectsInput || bConfirmsDestructive || bCredential || bSecurity)
        return NotificationRoute::KeepModal;
    return NotificationRoute::Notification;
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
