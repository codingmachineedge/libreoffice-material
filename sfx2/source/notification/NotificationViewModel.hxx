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

#include <optional>
#include <set>
#include <vector>

namespace sfx2
{
/** Sort order for the manager list folders. Mirrors the prototype's newest/oldest/source options. */
enum class NotificationSortOrder
{
    Newest,
    Oldest,
    Source
};

/** One display row derived from a NotificationRecord. This is the redaction chokepoint (INV-5): the
    view-model, not the widget layer, decides whether title/body text may be rendered. */
struct SFX2_DLLPUBLIC NotificationDisplayRow
{
    OString Id;
    NotificationSeverity Severity = NotificationSeverity::Information;
    NotificationFolder Folder = NotificationFolder::Inbox;
    bool Unread = false;
    bool Pinned = false;
    bool Redacted = false; ///< true when Privacy != SafeDisplayText or the title is empty
    OUString DisplayTitle; ///< safe text, or a generic localized label when Redacted
    OUString DisplayBody; ///< safe text, or empty when Redacted
    OUString SourceLabel; ///< friendly, non-sensitive label derived from Source
    OUString RelativeTime; ///< formatted from CreatedAt / UpdatedAt
    OString ShortCommit; ///< derived UI-only value; empty when not available
};

struct SFX2_DLLPUBLIC NotificationCounts
{
    sal_uInt32 Inbox = 0;
    sal_uInt32 Unread = 0;
    sal_uInt32 Archived = 0;
    sal_uInt32 Deleted = 0;
};

/** Pure transforms over an immutable snapshot. No VCL dependency; this is the headless-unit-testable
    core described in the notification-service checkpoint. */
class SFX2_DLLPUBLIC NotificationViewModel
{
public:
    /** Apply INV-5 redaction and derive one display row from a record. */
    static NotificationDisplayRow MakeRow(const NotificationRecord& rRecord);

    /** Friendly, non-sensitive label for a producer source slug. Kept in the view-model so source
        presentation stays with the redaction logic rather than leaking into the widget layer. */
    static OUString SourceLabel(const OString& rSource);

    /** Sorted, de-duplicated producer sources present in the snapshot; feeds the source filter menu. */
    static std::vector<OString> DistinctSources(const NotificationCenterSnapshot& rSnapshot);

    /** Bottom-right cards: Inbox folder, unarchived and undeleted, newest-first, capped at the
        schema-clamped MaxVisible (1..10). */
    static std::vector<NotificationDisplayRow> VisibleCards(const NotificationCenterSnapshot& rSnapshot,
                                                            const NotificationPreferences& rPreferences);

    /** Number of Inbox cards beyond the visible cap; feeds the "+%1 more" overflow control. */
    static sal_uInt32 HiddenCardCount(const NotificationCenterSnapshot& rSnapshot,
                                      const NotificationPreferences& rPreferences);

    /** Folder + severity/source filter + sort selection for the manager list. An empty severity
        filter matches every severity; an empty source filter matches every source. */
    static std::vector<NotificationDisplayRow>
    RowsForView(const NotificationCenterSnapshot& rSnapshot, NotificationView eView,
                std::optional<NotificationSeverity> oSeverityFilter, const OString& rSourceFilter,
                NotificationSortOrder eSort);

    /** Inbox/Unread/Archived/Deleted tallies for the tab suffixes. */
    static NotificationCounts Counts(const NotificationCenterSnapshot& rSnapshot);

    /** Newest history commit whose action is undoable (not a maintenance checkpoint); "" if none. */
    static OString LatestUndoableCommit(const NotificationCenterSnapshot& rSnapshot);

    /** Build exactly one ID vector from the selection, in snapshot order, dropping vanished ids.
        Guards INV-6 at the UI boundary: the manager never loops one request per row. */
    static std::vector<OString> SelectionVector(const std::set<OString>& rSelection,
                                                 const NotificationCenterSnapshot& rSnapshot);

    /** Reconcile a selection against the ids still present in the snapshot. */
    static std::set<OString> ReconcileSelection(const std::set<OString>& rSelection,
                                                const NotificationCenterSnapshot& rSnapshot);

    /** Clamp the visible-card count to the schema-permitted range. */
    static sal_Int32 ClampVisible(sal_Int32 nMaxVisible);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
