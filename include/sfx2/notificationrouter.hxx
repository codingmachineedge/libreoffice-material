/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/dllapi.h>
#include <sfx2/notificationcenter.hxx>

#include <rtl/string.hxx>
#include <rtl/ustring.hxx>

namespace sfx2
{
/** Result of routing classification for a legacy prompt or message. */
enum class NotificationRoute
{
    Notification, ///< safe to emit as a bottom-right notification (transient/informational)
    KeepModal ///< must remain a modal dialog (input / confirm-destructive / credential / security)
};

/**
 * Thin producer facade over the asynchronous NotificationCenterService.
 *
 * Producers submit one NotificationDraft per event instead of opening a transient message box. The
 * facade is synchronous to call and fire-and-forget: it runs on the VCL main thread, forwards the
 * draft to SfxApplication::GetNotificationCenter().add(...), and installs a completion that refreshes
 * the visible stack from the returned immutable snapshot. The service and store enforce redaction
 * regardless of the privacy hint carried in the draft.
 */
class SFX2_DLLPUBLIC NotificationRouter final
{
public:
    /** Emit one notification. Non-blocking; returns immediately. Must run on the VCL main thread.
        Draft.Privacy defaults to MetadataOnly; callers opt into SafeDisplayText only for fixed,
        audited built-in strings. The service/store enforce redaction regardless of this call. */
    static void Notify(NotificationDraft aDraft);

    /** Convenience for the common built-in case: a fixed, translated, no-data string. Source must be
        an audited safe-display source (e.g. u8"libreoffice.core-ui") for the text to display; any
        other source is persisted MetadataOnly (redacted) by the store. */
    static void NotifyInfo(const OString& rSource, NotificationSeverity eSeverity,
                           const OUString& rTitle, const OUString& rBody = OUString());

    /** Policy classifier for the 597-dialog migration. KeepModal iff the prompt collects input,
        confirms a destructive/irreversible act, handles credentials, or enforces security.
        Everything purely informational routes to Notification. Pure; unit-tested. */
    static NotificationRoute Classify(bool bCollectsInput, bool bConfirmsDestructive,
                                      bool bCredential, bool bSecurity);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
