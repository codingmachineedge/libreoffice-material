/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationViewModel.hxx"

#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>

#include <algorithm>
#include <ctime>

namespace sfx2
{
namespace
{
/** Friendly, non-sensitive label for a producer source slug. The store already forbids paths in
    Source, so an unmapped slug is safe to surface verbatim. */
OUString lclSourceLabel(const OString& rSource)
{
    if (rSource == "libreoffice.core-ui"_ostr)
        return SfxResId(STR_NOTIF_SOURCE_CORE);
    if (rSource.isEmpty())
        return SfxResId(STR_NOTIF_SOURCE_CORE);
    return OStringToOUString(rSource, RTL_TEXTENCODING_UTF8);
}

/** Compact, localized relative-time label derived from a record's creation instant. CreatedAt is
    epoch seconds (the store timestamps records with currentEpochSeconds), so compute the delta in
    seconds directly. */
OUString lclRelativeTime(sal_Int64 nCreatedAtSeconds)
{
    sal_Int64 nDeltaSeconds = static_cast<sal_Int64>(std::time(nullptr)) - nCreatedAtSeconds;
    if (nDeltaSeconds < 0)
        nDeltaSeconds = 0;

    if (nDeltaSeconds < 60)
        return SfxResId(STR_NOTIF_TIME_NOW);
    if (nDeltaSeconds < 3600)
        return SfxResId(STR_NOTIF_TIME_MIN)
            .replaceFirst(u"%1"_ustr, OUString::number(nDeltaSeconds / 60));
    if (nDeltaSeconds < 86400)
        return SfxResId(STR_NOTIF_TIME_HOUR)
            .replaceFirst(u"%1"_ustr, OUString::number(nDeltaSeconds / 3600));
    return SfxResId(STR_NOTIF_TIME_DAY)
        .replaceFirst(u"%1"_ustr, OUString::number(nDeltaSeconds / 86400));
}

/** Records that back the Inbox card stack and the Inbox tab (undeleted, unarchived). */
bool lclIsInboxCard(const NotificationRecord& rRecord)
{
    return rRecord.Folder == NotificationFolder::Inbox;
}

bool lclMatchesView(const NotificationRecord& rRecord, NotificationView eView)
{
    switch (eView)
    {
        case NotificationView::Inbox:
            return rRecord.Folder == NotificationFolder::Inbox;
        case NotificationView::Unread:
            return rRecord.Folder == NotificationFolder::Inbox && !rRecord.Read;
        case NotificationView::Archived:
            return rRecord.Folder == NotificationFolder::Archived;
        case NotificationView::Deleted:
            return rRecord.Folder == NotificationFolder::Deleted;
        case NotificationView::All:
            return true;
    }
    return false;
}

bool lclNewerFirst(const NotificationRecord& rLeft, const NotificationRecord& rRight)
{
    if (rLeft.CreatedAt != rRight.CreatedAt)
        return rLeft.CreatedAt > rRight.CreatedAt;
    // Stable tie-break so equal timestamps keep a deterministic order.
    return rLeft.Id > rRight.Id;
}
} // namespace

sal_Int32 NotificationViewModel::ClampVisible(sal_Int32 nMaxVisible)
{
    return std::clamp<sal_Int32>(nMaxVisible, 1, 10);
}

OUString NotificationViewModel::SourceLabel(const OString& rSource) { return lclSourceLabel(rSource); }

std::vector<OString>
NotificationViewModel::DistinctSources(const NotificationCenterSnapshot& rSnapshot)
{
    // std::set keeps the producer slugs sorted and de-duplicated for a stable menu order.
    std::set<OString> aSeen;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (!rRecord.Source.isEmpty())
            aSeen.insert(rRecord.Source);
    }
    return std::vector<OString>(aSeen.begin(), aSeen.end());
}

NotificationDisplayRow NotificationViewModel::MakeRow(const NotificationRecord& rRecord)
{
    NotificationDisplayRow aRow;
    aRow.Id = rRecord.Id;
    aRow.Severity = rRecord.Severity;
    aRow.Folder = rRecord.Folder;
    aRow.Unread = !rRecord.Read;
    aRow.Pinned = rRecord.Pinned;
    aRow.SourceLabel = lclSourceLabel(rRecord.Source);
    aRow.RelativeTime = lclRelativeTime(rRecord.CreatedAt);

    // INV-5: text is renderable only when the record is an audited safe-display record and its title
    // is non-empty. Everything else renders a generic label with no body; the UI never reconstructs
    // redacted text.
    aRow.Redacted = rRecord.Privacy != NotificationPrivacy::SafeDisplayText || rRecord.Title.isEmpty();
    if (aRow.Redacted)
    {
        aRow.DisplayTitle
            = SfxResId(STR_NOTIF_REDACTED_TITLE).replaceFirst(u"%1"_ustr, aRow.SourceLabel);
        aRow.DisplayBody.clear();
    }
    else
    {
        aRow.DisplayTitle = rRecord.Title;
        aRow.DisplayBody = rRecord.Body;
    }

    // ShortCommit is display-only; NotificationRecord carries no per-record commit, so it stays empty
    // and is never round-tripped into a draft or commit.
    aRow.ShortCommit.clear();
    return aRow;
}

std::vector<NotificationDisplayRow>
NotificationViewModel::VisibleCards(const NotificationCenterSnapshot& rSnapshot,
                                    const NotificationPreferences& rPreferences)
{
    std::vector<NotificationRecord> aInbox;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (lclIsInboxCard(rRecord))
            aInbox.push_back(rRecord);
    }
    std::sort(aInbox.begin(), aInbox.end(), lclNewerFirst);

    const size_t nMax = static_cast<size_t>(ClampVisible(rPreferences.MaxVisible));
    std::vector<NotificationDisplayRow> aRows;
    for (size_t i = 0; i < aInbox.size() && i < nMax; ++i)
        aRows.push_back(MakeRow(aInbox[i]));
    return aRows;
}

sal_uInt32 NotificationViewModel::HiddenCardCount(const NotificationCenterSnapshot& rSnapshot,
                                                  const NotificationPreferences& rPreferences)
{
    sal_uInt32 nInbox = 0;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (lclIsInboxCard(rRecord))
            ++nInbox;
    }
    const sal_uInt32 nVisible = static_cast<sal_uInt32>(ClampVisible(rPreferences.MaxVisible));
    return nInbox > nVisible ? nInbox - nVisible : 0;
}

std::vector<NotificationDisplayRow>
NotificationViewModel::RowsForView(const NotificationCenterSnapshot& rSnapshot, NotificationView eView,
                                   std::optional<NotificationSeverity> oSeverityFilter,
                                   const OString& rSourceFilter, NotificationSortOrder eSort)
{
    std::vector<NotificationRecord> aFiltered;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (!lclMatchesView(rRecord, eView))
            continue;
        if (oSeverityFilter && rRecord.Severity != *oSeverityFilter)
            continue;
        if (!rSourceFilter.isEmpty() && rRecord.Source != rSourceFilter)
            continue;
        aFiltered.push_back(rRecord);
    }

    std::sort(aFiltered.begin(), aFiltered.end(),
              [eSort](const NotificationRecord& rLeft, const NotificationRecord& rRight) {
                  switch (eSort)
                  {
                      case NotificationSortOrder::Oldest:
                          if (rLeft.CreatedAt != rRight.CreatedAt)
                              return rLeft.CreatedAt < rRight.CreatedAt;
                          return rLeft.Id < rRight.Id;
                      case NotificationSortOrder::Source:
                      {
                          const sal_Int32 nCompare = rLeft.Source.compareTo(rRight.Source);
                          if (nCompare != 0)
                              return nCompare < 0;
                          return lclNewerFirst(rLeft, rRight);
                      }
                      case NotificationSortOrder::Newest:
                          break;
                  }
                  return lclNewerFirst(rLeft, rRight);
              });

    std::vector<NotificationDisplayRow> aRows;
    aRows.reserve(aFiltered.size());
    for (const NotificationRecord& rRecord : aFiltered)
        aRows.push_back(MakeRow(rRecord));
    return aRows;
}

NotificationCounts NotificationViewModel::Counts(const NotificationCenterSnapshot& rSnapshot)
{
    NotificationCounts aCounts;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        switch (rRecord.Folder)
        {
            case NotificationFolder::Inbox:
                ++aCounts.Inbox;
                if (!rRecord.Read)
                    ++aCounts.Unread;
                break;
            case NotificationFolder::Archived:
                ++aCounts.Archived;
                break;
            case NotificationFolder::Deleted:
                ++aCounts.Deleted;
                break;
        }
    }
    return aCounts;
}

OString NotificationViewModel::LatestUndoableCommit(const NotificationCenterSnapshot& rSnapshot)
{
    OString aCommitId;
    sal_Int64 nNewest = 0;
    bool bFound = false;
    for (const NotificationHistoryEntry& rEntry : rSnapshot.History)
    {
        // A maintenance compaction checkpoint is not undoable, and the None/Unknown sentinels are not
        // real user actions.
        if (rEntry.Action == NotificationAction::Maintenance
            || rEntry.Action == NotificationAction::None
            || rEntry.Action == NotificationAction::Unknown)
            continue;
        if (rEntry.CommitId.isEmpty())
            continue;
        if (!bFound || rEntry.Timestamp > nNewest)
        {
            bFound = true;
            nNewest = rEntry.Timestamp;
            aCommitId = rEntry.CommitId;
        }
    }
    return aCommitId;
}

std::set<OString>
NotificationViewModel::ReconcileSelection(const std::set<OString>& rSelection,
                                          const NotificationCenterSnapshot& rSnapshot)
{
    std::set<OString> aPresent;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (rSelection.count(rRecord.Id))
            aPresent.insert(rRecord.Id);
    }
    return aPresent;
}

std::vector<OString>
NotificationViewModel::SelectionVector(const std::set<OString>& rSelection,
                                       const NotificationCenterSnapshot& rSnapshot)
{
    // INV-6: exactly one vector, built once in stable snapshot order, handed to one service method.
    std::vector<OString> aIds;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (rSelection.count(rRecord.Id))
            aIds.push_back(rRecord.Id);
    }
    return aIds;
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
