/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/dllapi.h>

#include <rtl/string.hxx>
#include <rtl/ustring.hxx>
#include <sal/types.h>

#include <functional>
#include <memory>
#include <vector>

namespace sfx2
{
/** A notification has one persisted folder. Unread is deliberately an orthogonal state. */
enum class NotificationFolder
{
    Inbox,
    Archived,
    Deleted
};

enum class NotificationView
{
    Inbox,
    Unread,
    Archived,
    Deleted,
    All
};

enum class NotificationSeverity
{
    Information,
    Success,
    Warning,
    Error
};

/**
 * MetadataOnly is the default and never persists title or body text. SafeDisplayText is an audited
 * convention for built-in producers whose text is known not to contain document data, paths or
 * secrets. Source is caller-supplied, so its allowlist is defense in depth rather than an
 * authentication or extension security boundary.
 */
enum class NotificationPrivacy
{
    MetadataOnly,
    SafeDisplayText
};

enum class NotificationStoreHealth
{
    Ready,
    Unavailable,
    Corrupt,
    Unsupported
};

enum class NotificationAction
{
    None,
    Add,
    MarkRead,
    MarkUnread,
    Archive,
    Delete,
    Restore,
    Pin,
    Unpin,
    Deduplicate,
    Purge,
    EmptyTrash,
    Maintenance,
    Undo,
    Unknown
};

struct SFX2_DLLPUBLIC NotificationRecord
{
    OString Id;
    OString Source;
    NotificationSeverity Severity = NotificationSeverity::Information;
    NotificationFolder Folder = NotificationFolder::Inbox;
    NotificationFolder PreviousFolder = NotificationFolder::Inbox;
    NotificationPrivacy Privacy = NotificationPrivacy::MetadataOnly;
    bool Read = false;
    bool Pinned = false;
    sal_Int64 CreatedAt = 0;
    sal_Int64 UpdatedAt = 0;
    sal_Int64 DeletedAt = 0;
    OUString Title;
    OUString Body;
    /** Optional lowercase SHA-256 value. Raw paths and document identifiers must not be supplied. */
    OString DedupeHash;

    bool operator==(const NotificationRecord&) const = default;
};

struct SFX2_DLLPUBLIC NotificationDraft
{
    OString Source;
    NotificationSeverity Severity = NotificationSeverity::Information;
    NotificationPrivacy Privacy = NotificationPrivacy::MetadataOnly;
    OUString Title;
    OUString Body;
    OString DedupeHash;
    bool Pinned = false;
};

struct SFX2_DLLPUBLIC NotificationMutationResult
{
    bool Success = false;
    bool Conflict = false;
    bool CreatedCommit = false;
    sal_uInt32 Affected = 0;
    NotificationAction Action = NotificationAction::None;
    OString CommitId;
    OUString Error;
};

struct SFX2_DLLPUBLIC NotificationHistoryEntry
{
    OString CommitId;
    OString ParentId;
    NotificationAction Action = NotificationAction::Unknown;
    sal_uInt32 Affected = 0;
    sal_Int64 Timestamp = 0;
};

struct SFX2_DLLPUBLIC NotificationPreferences
{
    bool Enabled = true;
    sal_Int32 MaxVisible = 3;
    sal_Int32 Width = 420;
    sal_Int32 TimeoutSeconds = 8;
    sal_Int32 HorizontalInset = 16;
    sal_Int32 VerticalInset = 16;
    sal_Int32 CornerRadius = 12;
    sal_Int32 OpacityPercent = 100;
    /** -1 selects the current theme accent; otherwise this is an RGB value. */
    sal_Int32 AccentColor = -1;
    sal_Int32 HistoryRetentionDays = 30;
    sal_Int32 HistoryLimit = 2000;
    bool UseThemeColors = true;
    bool Animations = true;

    bool operator==(const NotificationPreferences&) const = default;
};

SFX2_DLLPUBLIC NotificationPreferences
normalizeNotificationPreferences(const NotificationPreferences& rPreferences);

struct NotificationCenterSnapshot;
using NotificationCenterSnapshotRef = std::shared_ptr<const NotificationCenterSnapshot>;

/**
 * Persistent, local-only notification history. The repository URL is injectable for tests. An
 * empty URL selects <UserInstallation>/user/notification-history.git.
 *
 * The history repository has no remote, hooks or executable actions. It is local but not encrypted.
 * Mutating methods perform compression and durable file synchronization synchronously. Refresh,
 * query and history methods can synchronously read and decompress history. These calls must not run
 * on the UI thread; UI integrations must use NotificationCenterService, which owns the worker and
 * marshals results back asynchronously.
 * SafeDisplayText additionally uses a compile-time built-in producer allowlist, but callers are not
 * authenticated by Source; integration boundaries must force untrusted producers to MetadataOnly.
 * History is bounded through parentless checkpoints. Compaction intentionally expires older commit
 * IDs, history entries and their undo availability while retaining the current notification state.
 */
class SFX2_DLLPUBLIC NotificationStore final
{
public:
    using Clock = std::function<sal_Int64()>;
    using IdProvider = std::function<OString()>;

    explicit NotificationStore(const OUString& rRepositoryURL = OUString(), Clock aClock = Clock(),
                               IdProvider aIdProvider = IdProvider());
    ~NotificationStore();

    NotificationStore(const NotificationStore&) = delete;
    NotificationStore& operator=(const NotificationStore&) = delete;

    static OUString profileRepositoryURL();

    NotificationStoreHealth health() const;
    OUString lastError() const;
    OString headCommitId() const;

    /** Reload the current main ref. Existing cached records remain intact if validation fails. */
    bool refresh();

    std::vector<NotificationRecord> query(NotificationView eView) const;
    sal_uInt32 count(NotificationView eView) const;
    std::vector<NotificationRecord> findByDedupeHash(const OString& rHash) const;
    std::vector<NotificationHistoryEntry> history(sal_uInt32 nLimit = 100) const;

    /** Capture records, history, preferences and health under one store lock. */
    NotificationCenterSnapshotRef snapshot(sal_uInt64 nGeneration,
                                           sal_uInt32 nHistoryLimit = 100) const;

    NotificationPreferences preferences() const;
    void setPreferences(const NotificationPreferences& rPreferences);

    NotificationMutationResult add(const NotificationDraft& rDraft, OString* pRecordId = nullptr);
    NotificationMutationResult markRead(const std::vector<OString>& rIds, bool bRead);
    NotificationMutationResult setPinned(const std::vector<OString>& rIds, bool bPinned);
    NotificationMutationResult archive(const std::vector<OString>& rIds);
    NotificationMutationResult remove(const std::vector<OString>& rIds);
    NotificationMutationResult restore(const std::vector<OString>& rIds);
    NotificationMutationResult deduplicate();
    NotificationMutationResult purgeExpired();
    NotificationMutationResult emptyTrash();
    /** Apply retention and record-count limits in one atomic maintenance commit. */
    NotificationMutationResult maintain();

    /**
     * Apply an inverse of a retained action commit as a new child without rewinding main. A
     * compaction checkpoint is not undoable, and commits older than that checkpoint have expired.
     */
    NotificationMutationResult undo(const OString& rCommitId);

private:
    struct Impl;
    std::unique_ptr<Impl> m_pImpl;
};

/**
 * Read-only state returned by NotificationCenterService. A snapshot is assembled on the service
 * worker and shared with UI consumers as std::shared_ptr<const NotificationCenterSnapshot>, so UI
 * code never observes or calls the synchronous NotificationStore directly.
 */
struct SFX2_DLLPUBLIC NotificationCenterSnapshot final
{
    NotificationCenterSnapshot(sal_uInt64 nGeneration, NotificationStoreHealth eHealth,
                               OUString aError, OString aHeadCommitId,
                               NotificationPreferences aPreferences,
                               std::vector<NotificationRecord> aRecords,
                               std::vector<NotificationHistoryEntry> aHistory);

    const sal_uInt64 Generation;
    const NotificationStoreHealth Health;
    const OUString Error;
    const OString HeadCommitId;
    const NotificationPreferences Preferences;
    const std::vector<NotificationRecord> Records;
    const std::vector<NotificationHistoryEntry> History;
};

struct SFX2_DLLPUBLIC NotificationCenterResult
{
    sal_uInt64 RequestId = 0;
    NotificationMutationResult Mutation;
    NotificationCenterSnapshotRef State;
    /** Set only for Add, including a deduplicated existing record. */
    OString RecordId;
};

/**
 * Serialized asynchronous facade for NotificationStore.
 *
 * The store is constructed, used and destroyed exclusively on one worker. The profile factory
 * delivers callbacks through the VCL event queue. The injectable repository factory is intended
 * for focused tests and embedders and requires a non-blocking dispatcher that queues completions
 * off the store worker and returns without waiting for them. An inline dispatcher is a contract
 * violation and its completion is suppressed.
 *
 * shutdown() stops accepting requests, stops profile callback delivery, drains every request
 * already accepted, and then joins the worker. Cancelled callbacks do not affect the durability of
 * their already-accepted mutations.
 */
class SFX2_DLLPUBLIC NotificationCenterService final
{
public:
    using Completion = std::function<void(NotificationCenterResult)>;
    using CompletionDispatcher = std::function<void(std::function<void()>)>;

    static std::unique_ptr<NotificationCenterService> createForProfile();
    static std::unique_ptr<NotificationCenterService>
    createForRepository(const OUString& rRepositoryURL,
                        const NotificationPreferences& rPreferences = NotificationPreferences(),
                        NotificationStore::Clock aClock = NotificationStore::Clock(),
                        NotificationStore::IdProvider aIdProvider = NotificationStore::IdProvider(),
                        CompletionDispatcher aDispatcher = CompletionDispatcher());

    ~NotificationCenterService();

    NotificationCenterService(const NotificationCenterService&) = delete;
    NotificationCenterService& operator=(const NotificationCenterService&) = delete;

    sal_uInt64 requestSnapshot(Completion aCompletion);
    sal_uInt64 add(NotificationDraft aDraft, Completion aCompletion);
    sal_uInt64 markRead(std::vector<OString> aIds, bool bRead, Completion aCompletion);
    sal_uInt64 setPinned(std::vector<OString> aIds, bool bPinned, Completion aCompletion);
    sal_uInt64 archive(std::vector<OString> aIds, Completion aCompletion);
    sal_uInt64 remove(std::vector<OString> aIds, Completion aCompletion);
    sal_uInt64 restore(std::vector<OString> aIds, Completion aCompletion);
    sal_uInt64 deduplicate(Completion aCompletion);
    sal_uInt64 purgeExpired(Completion aCompletion);
    sal_uInt64 emptyTrash(Completion aCompletion);
    sal_uInt64 maintain(Completion aCompletion);
    sal_uInt64 undo(OString aCommitId, Completion aCompletion);
    sal_uInt64 setPreferences(NotificationPreferences aPreferences, Completion aCompletion);

    /**
     * Idempotent. Admission closes before callback cancellation and drain; a concurrent request is
     * accepted only if it linearizes before that close.
     */
    void shutdown();

private:
    struct Impl;
    explicit NotificationCenterService(std::unique_ptr<Impl> pImpl);
    std::unique_ptr<Impl> m_pImpl;
};
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
