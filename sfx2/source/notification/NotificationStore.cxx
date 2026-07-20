/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationcenter.hxx>

#include "LocalGitRepository.hxx"
#include "NotificationJson.hxx"

#include <rtl/strbuf.hxx>
#include <rtl/uuid.h>
#include <tools/urlobj.hxx>
#include <unotools/bootstrap.hxx>

#include <algorithm>
#include <array>
#include <chrono>
#include <map>
#include <mutex>
#include <set>
#include <string_view>

namespace sfx2
{
namespace
{
using notification_detail::GitFailure;
using notification_detail::GitRepositoryError;
using notification_detail::GitSnapshot;
using notification_detail::GitUndoTarget;
using notification_detail::LocalGitRepository;
using notification_detail::NotificationDataError;
using notification_detail::RecordMap;

constexpr sal_uInt32 MaximumReachableCommits = 128;
constexpr sal_uInt64 MaximumRepositoryBytes = 64 * 1024 * 1024;

sal_Int64 currentEpochSeconds()
{
    return std::chrono::duration_cast<std::chrono::seconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

OString createRecordId()
{
    std::array<sal_uInt8, 16> aUuid{};
    rtl_createUuid(aUuid.data(), nullptr, true);
    static constexpr char Hex[] = "0123456789abcdef";
    OStringBuffer aBuffer(32);
    for (sal_uInt8 nByte : aUuid)
    {
        aBuffer.append(Hex[nByte >> 4]);
        aBuffer.append(Hex[nByte & 0x0f]);
    }
    return aBuffer.makeStringAndClear();
}

OUString errorText(const std::exception& rError) { return OUString::fromUtf8(rError.what()); }

NotificationStoreHealth healthForFailure(GitFailure eFailure)
{
    switch (eFailure)
    {
        case GitFailure::Corrupt:
            return NotificationStoreHealth::Corrupt;
        case GitFailure::Unsupported:
            return NotificationStoreHealth::Unsupported;
        case GitFailure::Unavailable:
        case GitFailure::Conflict:
            return NotificationStoreHealth::Unavailable;
    }
    return NotificationStoreHealth::Unavailable;
}

bool matchesView(const NotificationRecord& rRecord, NotificationView eView)
{
    switch (eView)
    {
        case NotificationView::Inbox:
            return rRecord.Folder == NotificationFolder::Inbox;
        case NotificationView::Unread:
            return !rRecord.Read && rRecord.Folder != NotificationFolder::Deleted;
        case NotificationView::Archived:
            return rRecord.Folder == NotificationFolder::Archived;
        case NotificationView::Deleted:
            return rRecord.Folder == NotificationFolder::Deleted;
        case NotificationView::All:
            return true;
    }
    return false;
}

bool sameRecord(const RecordMap& rLeft, const RecordMap& rRight, const OString& rId)
{
    auto aLeft = rLeft.find(rId);
    auto aRight = rRight.find(rId);
    if (aLeft == rLeft.end() || aRight == rRight.end())
        return aLeft == rLeft.end() && aRight == rRight.end();
    return aLeft->second == aRight->second;
}

std::size_t estimatedRecordBytes(const NotificationRecord& rRecord)
{
    return 512 + 4 * static_cast<std::size_t>(rRecord.Title.getLength())
           + 4 * static_cast<std::size_t>(rRecord.Body.getLength());
}

std::size_t estimatedSnapshotBytes(const RecordMap& rRecords)
{
    std::size_t nBytes = 32;
    for (const auto& [rId, rRecord] : rRecords)
    {
        (void)rId;
        // Four bytes per UTF-16 code unit plus generous JSON escaping/property overhead.
        nBytes += estimatedRecordBytes(rRecord);
    }
    return nBytes;
}

sal_uInt32 purgeExpiredRecords(RecordMap& rRecords, const NotificationPreferences& rPreferences,
                               sal_Int64 nNow)
{
    const sal_Int64 nRetentionSeconds
        = static_cast<sal_Int64>(rPreferences.HistoryRetentionDays) * 24 * 60 * 60;
    const sal_Int64 nCutoff = nNow > nRetentionSeconds ? nNow - nRetentionSeconds : 0;
    sal_uInt32 nRemoved = 0;
    for (auto aIt = rRecords.begin(); aIt != rRecords.end();)
    {
        const NotificationRecord& rRecord = aIt->second;
        if (rRecord.Folder == NotificationFolder::Deleted && !rRecord.Pinned
            && rRecord.DeletedAt > 0 && rRecord.DeletedAt <= nCutoff)
        {
            aIt = rRecords.erase(aIt);
            ++nRemoved;
        }
        else
            ++aIt;
    }
    return nRemoved;
}

struct PruneCandidate
{
    OString Id;
    int Priority = 0;
    sal_Int64 Timestamp = 0;
};

bool enforceRecordLimits(RecordMap& rRecords, const NotificationPreferences& rPreferences,
                         const OString* pProtectedId, sal_uInt32& rRemoved)
{
    constexpr std::size_t SnapshotSafetyBudget
        = notification_detail::MaxSnapshotBytes - 1024 * 1024;
    std::size_t nEstimatedBytes = estimatedSnapshotBytes(rRecords);
    std::vector<PruneCandidate> aCandidates;
    for (const auto& [rId, rRecord] : rRecords)
    {
        if (rRecord.Pinned || (pProtectedId && rId == *pProtectedId))
            continue;
        int nPriority = 3;
        sal_Int64 nTimestamp = rRecord.CreatedAt;
        if (rRecord.Folder == NotificationFolder::Deleted)
        {
            nPriority = 0;
            nTimestamp = rRecord.DeletedAt;
        }
        else if (rRecord.Folder == NotificationFolder::Archived)
            nPriority = 1;
        else if (rRecord.Read)
            nPriority = 2;
        aCandidates.push_back({ rId, nPriority, nTimestamp });
    }
    std::sort(aCandidates.begin(), aCandidates.end(),
              [](const auto& rLeft, const auto& rRight)
              {
                  if (rLeft.Priority != rRight.Priority)
                      return rLeft.Priority < rRight.Priority;
                  if (rLeft.Timestamp != rRight.Timestamp)
                      return rLeft.Timestamp < rRight.Timestamp;
                  return rLeft.Id < rRight.Id;
              });

    auto aCandidate = aCandidates.begin();
    while ((rRecords.size() > static_cast<std::size_t>(rPreferences.HistoryLimit)
            || nEstimatedBytes > SnapshotSafetyBudget)
           && aCandidate != aCandidates.end())
    {
        auto aRecord = rRecords.find(aCandidate->Id);
        if (aRecord != rRecords.end())
        {
            nEstimatedBytes -= std::min(nEstimatedBytes, estimatedRecordBytes(aRecord->second));
            rRecords.erase(aRecord);
            ++rRemoved;
        }
        ++aCandidate;
    }
    return rRecords.size() <= static_cast<std::size_t>(rPreferences.HistoryLimit)
           && nEstimatedBytes <= SnapshotSafetyBudget;
}

sal_uInt32 deduplicateRecords(RecordMap& rRecords)
{
    std::map<std::string, OString> aWinners;
    std::set<OString> aRemove;
    for (const auto& [rId, rRecord] : rRecords)
    {
        if (rRecord.DedupeHash.isEmpty() || rRecord.Folder == NotificationFolder::Deleted)
            continue;
        std::string aKey(rRecord.Source);
        aKey.push_back('\0');
        aKey.append(rRecord.DedupeHash);
        auto [aWinner, bInserted] = aWinners.emplace(std::move(aKey), rId);
        if (bInserted)
            continue;
        const NotificationRecord& rExisting = rRecords.find(aWinner->second)->second;
        if (rExisting.Pinned && rRecord.Pinned)
            continue;
        if (rExisting.Pinned)
            aRemove.insert(rId);
        else if (rRecord.Pinned || rRecord.CreatedAt > rExisting.CreatedAt)
        {
            aRemove.insert(aWinner->second);
            aWinner->second = rId;
        }
        else
            aRemove.insert(rId);
    }
    for (const OString& rId : aRemove)
        rRecords.erase(rId);
    return static_cast<sal_uInt32>(aRemove.size());
}

NotificationMutationResult inputFailure(std::u16string_view rMessage)
{
    NotificationMutationResult aResult;
    aResult.Error = OUString(rMessage);
    return aResult;
}

constexpr std::string_view actionToken(NotificationAction eAction)
{
    switch (eAction)
    {
        case NotificationAction::Add:
            return "add";
        case NotificationAction::MarkRead:
            return "mark-read";
        case NotificationAction::MarkUnread:
            return "mark-unread";
        case NotificationAction::Archive:
            return "archive";
        case NotificationAction::Delete:
            return "delete";
        case NotificationAction::Restore:
            return "restore";
        case NotificationAction::Pin:
            return "pin";
        case NotificationAction::Unpin:
            return "unpin";
        case NotificationAction::Deduplicate:
            return "deduplicate";
        case NotificationAction::Purge:
            return "purge";
        case NotificationAction::EmptyTrash:
            return "empty-trash";
        case NotificationAction::Maintenance:
            return "maintenance";
        case NotificationAction::Undo:
            return "undo";
        case NotificationAction::None:
        case NotificationAction::Unknown:
            return "unknown";
    }
    return "unknown";
}

NotificationAction actionFromToken(std::string_view rToken)
{
    static constexpr std::array<std::pair<std::string_view, NotificationAction>, 13> Actions = {
        std::pair{ std::string_view("add"), NotificationAction::Add },
        std::pair{ std::string_view("mark-read"), NotificationAction::MarkRead },
        std::pair{ std::string_view("mark-unread"), NotificationAction::MarkUnread },
        std::pair{ std::string_view("archive"), NotificationAction::Archive },
        std::pair{ std::string_view("delete"), NotificationAction::Delete },
        std::pair{ std::string_view("restore"), NotificationAction::Restore },
        std::pair{ std::string_view("pin"), NotificationAction::Pin },
        std::pair{ std::string_view("unpin"), NotificationAction::Unpin },
        std::pair{ std::string_view("deduplicate"), NotificationAction::Deduplicate },
        std::pair{ std::string_view("purge"), NotificationAction::Purge },
        std::pair{ std::string_view("empty-trash"), NotificationAction::EmptyTrash },
        std::pair{ std::string_view("maintenance"), NotificationAction::Maintenance },
        std::pair{ std::string_view("undo"), NotificationAction::Undo },
    };
    auto aIt = std::find_if(Actions.begin(), Actions.end(),
                            [rToken](const auto& rEntry) { return rEntry.first == rToken; });
    return aIt == Actions.end() ? NotificationAction::Unknown : aIt->second;
}

NotificationMutationResult noCommitSuccess(NotificationAction eAction)
{
    NotificationMutationResult aResult;
    aResult.Success = true;
    aResult.Action = eAction;
    return aResult;
}
}

NotificationPreferences
normalizeNotificationPreferences(const NotificationPreferences& rPreferences)
{
    NotificationPreferences aResult = rPreferences;
    aResult.MaxVisible = std::clamp(aResult.MaxVisible, sal_Int32(1), sal_Int32(10));
    aResult.Width = std::clamp(aResult.Width, sal_Int32(320), sal_Int32(720));
    aResult.TimeoutSeconds = std::clamp(aResult.TimeoutSeconds, sal_Int32(0), sal_Int32(60));
    aResult.HorizontalInset = std::clamp(aResult.HorizontalInset, sal_Int32(0), sal_Int32(64));
    aResult.VerticalInset = std::clamp(aResult.VerticalInset, sal_Int32(0), sal_Int32(64));
    aResult.CornerRadius = std::clamp(aResult.CornerRadius, sal_Int32(0), sal_Int32(24));
    aResult.OpacityPercent = std::clamp(aResult.OpacityPercent, sal_Int32(70), sal_Int32(100));
    aResult.AccentColor = std::clamp(aResult.AccentColor, sal_Int32(-1), sal_Int32(0xffffff));
    aResult.HistoryRetentionDays
        = std::clamp(aResult.HistoryRetentionDays, sal_Int32(1), sal_Int32(365));
    aResult.HistoryLimit = std::clamp(aResult.HistoryLimit, sal_Int32(100), sal_Int32(5000));
    return aResult;
}

struct NotificationStore::Impl
{
    Impl(const OUString& rRepositoryURL, Clock aClock, IdProvider aIdProvider)
        : ClockProvider(aClock ? std::move(aClock) : Clock(currentEpochSeconds))
        , RecordIdProvider(aIdProvider ? std::move(aIdProvider) : IdProvider(createRecordId))
    {
        try
        {
            OUString aURL = rRepositoryURL.isEmpty() ? NotificationStore::profileRepositoryURL()
                                                     : rRepositoryURL;
            if (aURL.isEmpty())
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot locate the LibreOffice user profile");
            Repository = std::make_unique<LocalGitRepository>(aURL);
            refresh();
            Health = NotificationStoreHealth::Ready;
        }
        catch (const GitRepositoryError& rError)
        {
            setRepositoryFailure(rError);
        }
        catch (const NotificationDataError& rError)
        {
            Health = NotificationStoreHealth::Corrupt;
            LastError = errorText(rError);
        }
        catch (const std::exception& rError)
        {
            Health = NotificationStoreHealth::Unavailable;
            LastError = errorText(rError);
        }
    }

    void refresh()
    {
        GitSnapshot aSnapshot = Repository->currentSnapshot();
        if (aSnapshot.CommitId.isEmpty())
        {
            Records.clear();
            Head.clear();
            return;
        }
        RecordMap aRecords = notification_detail::parseRecords(aSnapshot.Json);
        Records.swap(aRecords);
        Head = aSnapshot.CommitId;
    }

    bool observe()
    {
        if (!Repository)
            return false;
        try
        {
            refresh();
            Health = NotificationStoreHealth::Ready;
            LastError.clear();
            return true;
        }
        catch (const GitRepositoryError& rError)
        {
            setRepositoryFailure(rError);
        }
        catch (const NotificationDataError& rError)
        {
            Health = NotificationStoreHealth::Corrupt;
            LastError = errorText(rError);
        }
        catch (const std::exception& rError)
        {
            Health = NotificationStoreHealth::Unavailable;
            LastError = errorText(rError);
        }
        return false;
    }

    void setRepositoryFailure(const GitRepositoryError& rError)
    {
        if (rError.Failure != GitFailure::Conflict)
            Health = healthForFailure(rError.Failure);
        LastError = errorText(rError);
    }

    sal_Int64 now() const { return std::max<sal_Int64>(1, ClockProvider()); }

    NotificationMutationResult commit(RecordMap&& rNext, NotificationAction eAction,
                                      sal_uInt32 nAffected, sal_Int64 nTimestamp)
    {
        NotificationMutationResult aResult;
        try
        {
            std::string aJson = notification_detail::serializeRecords(rNext);

            // Compact the retained pre-mutation state first. The user action is then a normal
            // child commit, so its returned ID always describes exactly the delta that undo will
            // invert. A durable pending marker makes any failed/crashed prune fail closed: the
            // next mutation must finish compaction before another history commit can be accepted.
            if (Repository->needsCompaction(MaximumReachableCommits, MaximumRepositoryBytes))
            {
                std::string aCurrentJson = notification_detail::serializeRecords(Records);
                Head = Repository->compactSnapshot(aCurrentJson, Head,
                                                   actionToken(NotificationAction::Maintenance), 0,
                                                   nTimestamp);
            }

            OString aCommit = Repository->commitSnapshot(aJson, Head, actionToken(eAction),
                                                         nAffected, nTimestamp);
            Records = std::move(rNext);
            Head = aCommit;
            LastError.clear();
            Health = NotificationStoreHealth::Ready;
            aResult.Success = true;
            aResult.CreatedCommit = true;
            aResult.Affected = nAffected;
            aResult.Action = eAction;
            aResult.CommitId = aCommit;
        }
        catch (const GitRepositoryError& rError)
        {
            // Compaction may have durably installed its checkpoint before a prune error. Refresh
            // that valid state, but preserve the error/health so writes remain fail closed until
            // an explicit refresh and successful compaction retry.
            try
            {
                refresh();
            }
            catch (...)
            {
            }
            aResult.Conflict = rError.Failure == GitFailure::Conflict;
            aResult.Error = errorText(rError);
            setRepositoryFailure(rError);
        }
        catch (const NotificationDataError& rError)
        {
            aResult.Error = errorText(rError);
        }
        catch (const std::exception& rError)
        {
            aResult.Error = errorText(rError);
            Health = NotificationStoreHealth::Unavailable;
            LastError = aResult.Error;
        }
        return aResult;
    }

    template <typename Validator, typename Mutator>
    NotificationMutationResult bulk(const std::vector<OString>& rIds, NotificationAction eAction,
                                    Validator aValidator, Mutator aMutator)
    {
        if (rIds.empty())
        {
            return noCommitSuccess(eAction);
        }
        if (rIds.size() > notification_detail::MaxRecordCount)
            return inputFailure(u"Too many notifications were selected.");
        std::set<OString> aUnique(rIds.begin(), rIds.end());
        if (aUnique.size() != rIds.size())
            return inputFailure(u"The notification selection contains duplicate IDs.");
        if (!std::all_of(rIds.begin(), rIds.end(), [](const OString& rId)
                         { return notification_detail::isValidRecordId(rId); }))
            return inputFailure(u"The notification selection contains an invalid ID.");

        try
        {
            refresh();
        }
        catch (const GitRepositoryError& rError)
        {
            setRepositoryFailure(rError);
            NotificationMutationResult aResult;
            aResult.Conflict = rError.Failure == GitFailure::Conflict;
            aResult.Error = errorText(rError);
            return aResult;
        }
        catch (const std::exception& rError)
        {
            Health = NotificationStoreHealth::Corrupt;
            LastError = errorText(rError);
            return inputFailure(LastError);
        }

        for (const OString& rId : rIds)
        {
            auto aIt = Records.find(rId);
            if (aIt == Records.end())
                return inputFailure(u"A selected notification no longer exists.");
            OUString aValidationError = aValidator(aIt->second);
            if (!aValidationError.isEmpty())
                return inputFailure(aValidationError);
        }

        RecordMap aNext = Records;
        sal_Int64 nNow = now();
        sal_uInt32 nAffected = 0;
        for (const OString& rId : rIds)
        {
            NotificationRecord& rRecord = aNext.find(rId)->second;
            if (aMutator(rRecord, nNow))
            {
                rRecord.UpdatedAt = std::max(rRecord.CreatedAt, nNow);
                ++nAffected;
            }
        }
        if (nAffected == 0)
        {
            return noCommitSuccess(eAction);
        }
        return commit(std::move(aNext), eAction, nAffected, nNow);
    }

    mutable std::mutex Mutex;
    std::unique_ptr<LocalGitRepository> Repository;
    RecordMap Records;
    OString Head;
    Clock ClockProvider;
    IdProvider RecordIdProvider;
    NotificationStoreHealth Health = NotificationStoreHealth::Unavailable;
    OUString LastError;
    NotificationPreferences Preferences;
};

NotificationStore::NotificationStore(const OUString& rRepositoryURL, Clock aClock,
                                     IdProvider aIdProvider)
    : m_pImpl(std::make_unique<Impl>(rRepositoryURL, std::move(aClock), std::move(aIdProvider)))
{
}

NotificationStore::~NotificationStore() = default;

OUString NotificationStore::profileRepositoryURL()
{
    OUString aUserData;
    utl::Bootstrap::PathStatus eStatus = utl::Bootstrap::locateUserData(aUserData);
    if (eStatus != utl::Bootstrap::PATH_EXISTS && eStatus != utl::Bootstrap::PATH_VALID)
        return OUString();
    INetURLObject aURL(aUserData);
    if (aURL.GetProtocol() != INetProtocol::File
        || !aURL.Append(u"notification-history.git", INetURLObject::EncodeMechanism::All))
        return OUString();
    return aURL.GetMainURL(INetURLObject::DecodeMechanism::NONE);
}

NotificationStoreHealth NotificationStore::health() const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    return m_pImpl->Health;
}

OUString NotificationStore::lastError() const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    return m_pImpl->LastError;
}

OString NotificationStore::headCommitId() const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    (void)m_pImpl->observe();
    return m_pImpl->Head;
}

bool NotificationStore::refresh()
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    return m_pImpl->observe();
}

std::vector<NotificationRecord> NotificationStore::query(NotificationView eView) const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    (void)m_pImpl->observe();
    std::vector<NotificationRecord> aResult;
    for (const auto& [rId, rRecord] : m_pImpl->Records)
    {
        (void)rId;
        if (matchesView(rRecord, eView))
            aResult.push_back(rRecord);
    }
    std::sort(aResult.begin(), aResult.end(),
              [](const auto& rLeft, const auto& rRight)
              {
                  return rLeft.CreatedAt != rRight.CreatedAt ? rLeft.CreatedAt > rRight.CreatedAt
                                                             : rLeft.Id < rRight.Id;
              });
    return aResult;
}

sal_uInt32 NotificationStore::count(NotificationView eView) const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    (void)m_pImpl->observe();
    return static_cast<sal_uInt32>(std::count_if(m_pImpl->Records.begin(), m_pImpl->Records.end(),
                                                 [eView](const auto& rEntry)
                                                 { return matchesView(rEntry.second, eView); }));
}

std::vector<NotificationRecord> NotificationStore::findByDedupeHash(const OString& rHash) const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    (void)m_pImpl->observe();
    std::vector<NotificationRecord> aResult;
    if (!notification_detail::isValidSha256(rHash) || rHash.isEmpty())
        return aResult;
    for (const auto& [rId, rRecord] : m_pImpl->Records)
    {
        (void)rId;
        if (rRecord.DedupeHash == rHash)
            aResult.push_back(rRecord);
    }
    std::sort(aResult.begin(), aResult.end(),
              [](const auto& rLeft, const auto& rRight)
              {
                  return rLeft.CreatedAt != rRight.CreatedAt ? rLeft.CreatedAt > rRight.CreatedAt
                                                             : rLeft.Id < rRight.Id;
              });
    return aResult;
}

std::vector<NotificationHistoryEntry> NotificationStore::history(sal_uInt32 nLimit) const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    std::vector<NotificationHistoryEntry> aResult;
    if (!m_pImpl->observe() || nLimit == 0)
        return aResult;
    nLimit = std::min<sal_uInt32>(nLimit, 1000);
    OString aCommit = m_pImpl->Head;
    try
    {
        for (const GitSnapshot& rSnapshot : m_pImpl->Repository->readHistory(aCommit, nLimit))
        {
            aResult.push_back({ rSnapshot.CommitId, rSnapshot.ParentId,
                                actionFromToken(rSnapshot.Action), rSnapshot.Affected,
                                rSnapshot.Timestamp });
        }
    }
    catch (const GitRepositoryError& rError)
    {
        m_pImpl->setRepositoryFailure(rError);
        aResult.clear();
    }
    catch (const std::exception& rError)
    {
        m_pImpl->Health = NotificationStoreHealth::Corrupt;
        m_pImpl->LastError = errorText(rError);
        aResult.clear();
    }
    return aResult;
}

NotificationCenterSnapshotRef NotificationStore::snapshot(sal_uInt64 nGeneration,
                                                           sal_uInt32 nHistoryLimit) const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    std::vector<NotificationRecord> aRecords;
    std::vector<NotificationHistoryEntry> aHistory;
    const bool bObserved = m_pImpl->observe();
    aRecords.reserve(m_pImpl->Records.size());
    for (const auto& [rId, rRecord] : m_pImpl->Records)
    {
        (void)rId;
        aRecords.push_back(rRecord);
    }
    std::sort(aRecords.begin(), aRecords.end(),
              [](const auto& rLeft, const auto& rRight)
              {
                  return rLeft.CreatedAt != rRight.CreatedAt ? rLeft.CreatedAt > rRight.CreatedAt
                                                             : rLeft.Id < rRight.Id;
              });

    nHistoryLimit = std::min<sal_uInt32>(nHistoryLimit, 1000);
    if (bObserved && nHistoryLimit != 0)
    {
        try
        {
            for (const GitSnapshot& rSnapshot :
                 m_pImpl->Repository->readHistory(m_pImpl->Head, nHistoryLimit))
            {
                aHistory.push_back({ rSnapshot.CommitId, rSnapshot.ParentId,
                                     actionFromToken(rSnapshot.Action), rSnapshot.Affected,
                                     rSnapshot.Timestamp });
            }
        }
        catch (const GitRepositoryError& rError)
        {
            m_pImpl->setRepositoryFailure(rError);
            aHistory.clear();
        }
        catch (const std::exception& rError)
        {
            m_pImpl->Health = NotificationStoreHealth::Corrupt;
            m_pImpl->LastError = errorText(rError);
            aHistory.clear();
        }
    }
    return std::make_shared<const NotificationCenterSnapshot>(
        nGeneration, m_pImpl->Health, m_pImpl->LastError, m_pImpl->Head, m_pImpl->Preferences,
        std::move(aRecords), std::move(aHistory));
}

NotificationPreferences NotificationStore::preferences() const
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    return m_pImpl->Preferences;
}

void NotificationStore::setPreferences(const NotificationPreferences& rPreferences)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    m_pImpl->Preferences = normalizeNotificationPreferences(rPreferences);
}

NotificationMutationResult NotificationStore::add(const NotificationDraft& rDraft,
                                                  OString* pRecordId)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->Repository)
        return inputFailure(u"Notification history is not available.");
    if (!notification_detail::isValidSource(rDraft.Source))
        return inputFailure(u"The notification source identifier is invalid.");
    if (!notification_detail::isValidSha256(rDraft.DedupeHash))
        return inputFailure(u"The notification dedupe hash is invalid.");
    if (rDraft.Privacy != NotificationPrivacy::MetadataOnly
        && rDraft.Privacy != NotificationPrivacy::SafeDisplayText)
        return inputFailure(u"The notification privacy class is invalid.");
    switch (rDraft.Severity)
    {
        case NotificationSeverity::Information:
        case NotificationSeverity::Success:
        case NotificationSeverity::Warning:
        case NotificationSeverity::Error:
            break;
        default:
            return inputFailure(u"The notification severity is invalid.");
    }
    if (rDraft.Title.getLength() > notification_detail::MaxTitleLength
        || rDraft.Body.getLength() > notification_detail::MaxBodyLength)
        return inputFailure(u"The notification display text is too long.");
    if (rDraft.Privacy == NotificationPrivacy::SafeDisplayText
        && (!notification_detail::isApprovedSafeDisplaySource(rDraft.Source)
            || !notification_detail::isSafeDisplayText(rDraft.Title)
            || !notification_detail::isSafeDisplayText(rDraft.Body)))
        return inputFailure(u"The notification display text may contain private data.");

    try
    {
        m_pImpl->refresh();
    }
    catch (const GitRepositoryError& rError)
    {
        m_pImpl->setRepositoryFailure(rError);
        NotificationMutationResult aResult;
        aResult.Conflict = rError.Failure == GitFailure::Conflict;
        aResult.Error = errorText(rError);
        return aResult;
    }
    catch (const std::exception& rError)
    {
        m_pImpl->Health = NotificationStoreHealth::Corrupt;
        m_pImpl->LastError = errorText(rError);
        return inputFailure(m_pImpl->LastError);
    }

    if (!rDraft.DedupeHash.isEmpty())
    {
        auto aDuplicate = std::find_if(m_pImpl->Records.begin(), m_pImpl->Records.end(),
                                       [&rDraft](const auto& rEntry)
                                       {
                                           const NotificationRecord& rRecord = rEntry.second;
                                           return rRecord.Folder != NotificationFolder::Deleted
                                                  && rRecord.Source == rDraft.Source
                                                  && rRecord.DedupeHash == rDraft.DedupeHash;
                                       });
        if (aDuplicate != m_pImpl->Records.end())
        {
            if (pRecordId)
                *pRecordId = aDuplicate->first;
            return noCommitSuccess(NotificationAction::Add);
        }
    }

    OString aId;
    for (unsigned int i = 0; i < 8; ++i)
    {
        aId = m_pImpl->RecordIdProvider();
        if (notification_detail::isValidRecordId(aId)
            && m_pImpl->Records.find(aId) == m_pImpl->Records.end())
            break;
        aId.clear();
    }
    if (aId.isEmpty())
        return inputFailure(u"A unique notification ID could not be generated.");

    sal_Int64 nNow = m_pImpl->now();
    NotificationRecord aRecord;
    aRecord.Id = aId;
    aRecord.Source = rDraft.Source;
    aRecord.Severity = rDraft.Severity;
    aRecord.Privacy = rDraft.Privacy;
    aRecord.Pinned = rDraft.Pinned;
    aRecord.CreatedAt = nNow;
    aRecord.UpdatedAt = nNow;
    aRecord.DedupeHash = rDraft.DedupeHash;
    if (rDraft.Privacy == NotificationPrivacy::SafeDisplayText)
    {
        aRecord.Title = rDraft.Title;
        aRecord.Body = rDraft.Body;
    }

    RecordMap aNext = m_pImpl->Records;
    aNext.emplace(aId, std::move(aRecord));
    sal_uInt32 nPruned = purgeExpiredRecords(aNext, m_pImpl->Preferences, nNow);
    if (!enforceRecordLimits(aNext, m_pImpl->Preferences, &aId, nPruned))
        return inputFailure(
            u"Notification history is full because all remaining records are pinned.");
    NotificationMutationResult aResult
        = m_pImpl->commit(std::move(aNext), NotificationAction::Add, nPruned + 1, nNow);
    if (aResult.Success && pRecordId)
        *pRecordId = aId;
    return aResult;
}

NotificationMutationResult NotificationStore::markRead(const std::vector<OString>& rIds, bool bRead)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready)
        return inputFailure(u"Notification history is not available.");
    return m_pImpl->bulk(
        rIds, bRead ? NotificationAction::MarkRead : NotificationAction::MarkUnread,
        [](const NotificationRecord&) { return OUString(); },
        [bRead](NotificationRecord& rRecord, sal_Int64)
        {
            if (rRecord.Read == bRead)
                return false;
            rRecord.Read = bRead;
            return true;
        });
}

NotificationMutationResult NotificationStore::setPinned(const std::vector<OString>& rIds,
                                                        bool bPinned)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready)
        return inputFailure(u"Notification history is not available.");
    return m_pImpl->bulk(
        rIds, bPinned ? NotificationAction::Pin : NotificationAction::Unpin,
        [](const NotificationRecord&) { return OUString(); },
        [bPinned](NotificationRecord& rRecord, sal_Int64)
        {
            if (rRecord.Pinned == bPinned)
                return false;
            rRecord.Pinned = bPinned;
            return true;
        });
}

NotificationMutationResult NotificationStore::archive(const std::vector<OString>& rIds)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready)
        return inputFailure(u"Notification history is not available.");
    return m_pImpl->bulk(
        rIds, NotificationAction::Archive,
        [](const NotificationRecord& rRecord)
        {
            return rRecord.Folder == NotificationFolder::Deleted
                       ? OUString(std::u16string_view(
                             u"A deleted notification must be restored before it can be archived."))
                       : OUString();
        },
        [](NotificationRecord& rRecord, sal_Int64)
        {
            if (rRecord.Folder == NotificationFolder::Archived)
                return false;
            rRecord.Folder = NotificationFolder::Archived;
            return true;
        });
}

NotificationMutationResult NotificationStore::remove(const std::vector<OString>& rIds)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready)
        return inputFailure(u"Notification history is not available.");
    return m_pImpl->bulk(
        rIds, NotificationAction::Delete, [](const NotificationRecord&) { return OUString(); },
        [](NotificationRecord& rRecord, sal_Int64 nNow)
        {
            if (rRecord.Folder == NotificationFolder::Deleted)
                return false;
            rRecord.PreviousFolder = rRecord.Folder;
            rRecord.Folder = NotificationFolder::Deleted;
            rRecord.DeletedAt = std::max<sal_Int64>({ 1, rRecord.CreatedAt, nNow });
            return true;
        });
}

NotificationMutationResult NotificationStore::restore(const std::vector<OString>& rIds)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready)
        return inputFailure(u"Notification history is not available.");
    return m_pImpl->bulk(
        rIds, NotificationAction::Restore, [](const NotificationRecord&) { return OUString(); },
        [](NotificationRecord& rRecord, sal_Int64)
        {
            if (rRecord.Folder != NotificationFolder::Deleted)
                return false;
            rRecord.Folder = rRecord.PreviousFolder;
            rRecord.DeletedAt = 0;
            return true;
        });
}

NotificationMutationResult NotificationStore::deduplicate()
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->observe())
        return inputFailure(u"Notification history is not available.");
    RecordMap aNext = m_pImpl->Records;
    sal_uInt32 nRemoved = deduplicateRecords(aNext);
    if (nRemoved == 0)
        return noCommitSuccess(NotificationAction::Deduplicate);
    return m_pImpl->commit(std::move(aNext), NotificationAction::Deduplicate, nRemoved,
                           m_pImpl->now());
}

NotificationMutationResult NotificationStore::purgeExpired()
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->observe())
        return inputFailure(u"Notification history is not available.");
    sal_Int64 nNow = m_pImpl->now();
    RecordMap aNext = m_pImpl->Records;
    sal_uInt32 nRemoved = purgeExpiredRecords(aNext, m_pImpl->Preferences, nNow);
    if (nRemoved == 0)
        return noCommitSuccess(NotificationAction::Purge);
    return m_pImpl->commit(std::move(aNext), NotificationAction::Purge, nRemoved, nNow);
}

NotificationMutationResult NotificationStore::emptyTrash()
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->observe())
        return inputFailure(u"Notification history is not available.");
    RecordMap aNext = m_pImpl->Records;
    sal_uInt32 nRemoved = 0;
    for (auto aIt = aNext.begin(); aIt != aNext.end();)
    {
        if (aIt->second.Folder == NotificationFolder::Deleted)
        {
            aIt = aNext.erase(aIt);
            ++nRemoved;
        }
        else
            ++aIt;
    }
    if (nRemoved == 0)
        return noCommitSuccess(NotificationAction::EmptyTrash);
    return m_pImpl->commit(std::move(aNext), NotificationAction::EmptyTrash, nRemoved,
                           m_pImpl->now());
}

NotificationMutationResult NotificationStore::maintain()
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->observe())
        return inputFailure(u"Notification history is not available.");
    sal_Int64 nNow = m_pImpl->now();
    RecordMap aNext = m_pImpl->Records;
    sal_uInt32 nRemoved = purgeExpiredRecords(aNext, m_pImpl->Preferences, nNow);
    if (!enforceRecordLimits(aNext, m_pImpl->Preferences, nullptr, nRemoved))
        return inputFailure(
            u"Notification history cannot meet its limit while all remaining records are pinned.");
    if (nRemoved == 0)
        return noCommitSuccess(NotificationAction::Maintenance);
    return m_pImpl->commit(std::move(aNext), NotificationAction::Maintenance, nRemoved, nNow);
}

NotificationMutationResult NotificationStore::undo(const OString& rCommitId)
{
    std::scoped_lock aGuard(m_pImpl->Mutex);
    if (m_pImpl->Health != NotificationStoreHealth::Ready || !m_pImpl->Repository)
        return inputFailure(u"Notification history is not available.");
    std::string_view aCommitId(rCommitId);
    if (aCommitId.size() != 40
        || !std::all_of(aCommitId.begin(), aCommitId.end(), [](unsigned char c)
                        { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }))
        return inputFailure(u"The notification history commit ID is invalid.");

    try
    {
        m_pImpl->refresh();
        GitUndoTarget aUndoTarget = m_pImpl->Repository->readUndoTarget(rCommitId, m_pImpl->Head);
        if (m_pImpl->Head.isEmpty() || !aUndoTarget.Found)
            return inputFailure(u"The selected commit is not in this notification history.");

        GitSnapshot& rTargetSnapshot = aUndoTarget.Target;
        if (!rTargetSnapshot.CheckpointFrom.isEmpty())
            return inputFailure(u"The selected commit is a compaction checkpoint; its earlier undo "
                                u"history has expired.");
        RecordMap aTarget = notification_detail::parseRecords(rTargetSnapshot.Json);
        RecordMap aParent;
        if (aUndoTarget.HasParent)
            aParent = notification_detail::parseRecords(aUndoTarget.Parent.Json);

        std::set<OString> aTouched;
        for (const auto& [rId, rRecord] : aTarget)
        {
            (void)rRecord;
            if (!sameRecord(aTarget, aParent, rId))
                aTouched.insert(rId);
        }
        for (const auto& [rId, rRecord] : aParent)
        {
            (void)rRecord;
            if (!sameRecord(aTarget, aParent, rId))
                aTouched.insert(rId);
        }
        if (aTouched.empty())
            return inputFailure(u"The selected commit has no notification changes to undo.");

        for (const OString& rId : aTouched)
        {
            if (!sameRecord(m_pImpl->Records, aTarget, rId))
            {
                NotificationMutationResult aResult
                    = inputFailure(u"A notification changed after the selected commit.");
                aResult.Conflict = true;
                return aResult;
            }
        }

        RecordMap aNext = m_pImpl->Records;
        for (const OString& rId : aTouched)
        {
            auto aParentRecord = aParent.find(rId);
            if (aParentRecord == aParent.end())
                aNext.erase(rId);
            else
                aNext[rId] = aParentRecord->second;
        }
        sal_Int64 nNow = m_pImpl->now();
        return m_pImpl->commit(std::move(aNext), NotificationAction::Undo,
                               static_cast<sal_uInt32>(aTouched.size()), nNow);
    }
    catch (const GitRepositoryError& rError)
    {
        m_pImpl->setRepositoryFailure(rError);
        NotificationMutationResult aResult;
        aResult.Conflict = rError.Failure == GitFailure::Conflict;
        aResult.Error = errorText(rError);
        return aResult;
    }
    catch (const NotificationDataError& rError)
    {
        m_pImpl->Health = NotificationStoreHealth::Corrupt;
        m_pImpl->LastError = errorText(rError);
        return inputFailure(m_pImpl->LastError);
    }
    catch (const std::exception& rError)
    {
        m_pImpl->Health = NotificationStoreHealth::Unavailable;
        m_pImpl->LastError = errorText(rError);
        return inputFailure(m_pImpl->LastError);
    }
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
