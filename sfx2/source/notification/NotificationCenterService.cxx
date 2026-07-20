/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationcenter.hxx>

#include "NotificationConfiguration.hxx"

#include <com/sun/star/uno/Exception.hpp>
#include <rtl/ref.hxx>
#include <sal/log.hxx>
#include <salhelper/thread.hxx>
#include <vcl/svapp.hxx>

#include <cassert>
#include <condition_variable>
#include <deque>
#include <exception>
#include <mutex>
#include <utility>

namespace sfx2
{
NotificationCenterSnapshot::NotificationCenterSnapshot(
    sal_uInt64 nGeneration, NotificationStoreHealth eHealth, OUString aError, OString aHeadCommitId,
    NotificationPreferences aPreferences, std::vector<NotificationRecord> aRecords,
    std::vector<NotificationHistoryEntry> aHistory)
    : Generation(nGeneration)
    , Health(eHealth)
    , Error(std::move(aError))
    , HeadCommitId(std::move(aHeadCommitId))
    , Preferences(std::move(aPreferences))
    , Records(std::move(aRecords))
    , History(std::move(aHistory))
{
}

namespace
{
class UiCompletionQueue final
{
public:
    ~UiCompletionQueue() { shutdown(); }

    void post(std::function<void()> aCompletion)
    {
        std::scoped_lock aGuard(m_aMutex);
        if (!m_bAccepting)
            return;
        m_aCompletions.push_back(std::move(aCompletion));
        if (!m_pEvent)
        {
            m_pEvent = Application::PostUserEvent(LINK(this, UiCompletionQueue, handleEvent));
            if (!m_pEvent)
                m_aCompletions.clear();
        }
    }

    void shutdown()
    {
        ImplSVEvent* pEvent = nullptr;
        {
            std::scoped_lock aGuard(m_aMutex);
            if (!m_bAccepting && !m_pEvent)
                return;
            m_bAccepting = false;
            m_aCompletions.clear();
            pEvent = std::exchange(m_pEvent, nullptr);
        }
        if (pEvent)
            Application::RemoveUserEvent(pEvent);
    }

private:
    DECL_LINK(handleEvent, void*, void);

    std::mutex m_aMutex;
    std::deque<std::function<void()>> m_aCompletions;
    ImplSVEvent* m_pEvent = nullptr;
    bool m_bAccepting = true;
};

IMPL_LINK_NOARG(UiCompletionQueue, handleEvent, void*, void)
{
    std::deque<std::function<void()>> aCompletions;
    {
        std::scoped_lock aGuard(m_aMutex);
        m_pEvent = nullptr;
        if (!m_bAccepting)
        {
            m_aCompletions.clear();
            return;
        }
        aCompletions.swap(m_aCompletions);
    }
    for (auto& rCompletion : aCompletions)
    {
        {
            std::scoped_lock aGuard(m_aMutex);
            if (!m_bAccepting)
                break;
        }
        try
        {
            rCompletion();
        }
        catch (const std::exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification UI completion failed: " << rError.what());
        }
    }
}

enum class RequestKind
{
    Snapshot,
    Add,
    MarkRead,
    SetPinned,
    Archive,
    Remove,
    Restore,
    Deduplicate,
    PurgeExpired,
    EmptyTrash,
    Maintain,
    Undo,
    SetPreferences
};

struct Request
{
    RequestKind Kind = RequestKind::Snapshot;
    sal_uInt64 Id = 0;
    NotificationDraft Draft;
    std::vector<OString> Ids;
    OString CommitId;
    NotificationPreferences Preferences;
    bool Flag = false;
    NotificationCenterService::Completion Completion;
};

NotificationMutationResult successfulRead()
{
    NotificationMutationResult aResult;
    aResult.Success = true;
    return aResult;
}

NotificationMutationResult failedRequest(const OUString& rError)
{
    NotificationMutationResult aResult;
    aResult.Error = rError;
    return aResult;
}

class NotificationWorker final : public salhelper::Thread
{
public:
    NotificationWorker(OUString aRepositoryURL, NotificationPreferences aPreferences,
                       NotificationStore::Clock aClock, NotificationStore::IdProvider aIdProvider,
                       NotificationCenterService::CompletionDispatcher aDispatcher,
                       bool bPersistPreferences)
        : salhelper::Thread("notification-center")
        , m_aRepositoryURL(std::move(aRepositoryURL))
        , m_aPreferences(normalizeNotificationPreferences(aPreferences))
        , m_aClock(std::move(aClock))
        , m_aIdProvider(std::move(aIdProvider))
        , m_aDispatcher(std::move(aDispatcher))
        , m_bPersistPreferences(bPersistPreferences)
    {
        if (!m_aDispatcher)
            m_aDispatcher = [](std::function<void()> aCompletion) { aCompletion(); };
    }

    ~NotificationWorker() override { assert(m_bJoined); }

    sal_uInt64 enqueue(Request aRequest)
    {
        sal_uInt64 nId = 0;
        {
            std::scoped_lock aGuard(m_aMutex);
            if (!m_bAccepting)
                return 0;
            nId = m_nNextRequestId++;
            aRequest.Id = nId;
            m_aRequests.push_back(std::move(aRequest));
        }
        m_aWorkAvailable.notify_one();
        return nId;
    }

    void shutdown()
    {
        std::scoped_lock aShutdownGuard(m_aShutdownMutex);
        if (m_bJoined)
            return;
        {
            std::scoped_lock aGuard(m_aMutex);
            m_bAccepting = false;
            m_bStopWhenDrained = true;
        }
        m_aWorkAvailable.notify_one();
        join();
        m_bJoined = true;
    }

private:
    void execute() override
    {
        std::unique_ptr<NotificationStore> pStore = std::make_unique<NotificationStore>(
            m_aRepositoryURL, std::move(m_aClock), std::move(m_aIdProvider));
        pStore->setPreferences(m_aPreferences);

        for (;;)
        {
            Request aRequest;
            {
                std::unique_lock aGuard(m_aMutex);
                m_aWorkAvailable.wait(aGuard, [this]
                                      { return m_bStopWhenDrained || !m_aRequests.empty(); });
                if (m_aRequests.empty())
                {
                    if (m_bStopWhenDrained)
                        break;
                    continue;
                }
                aRequest = std::move(m_aRequests.front());
                m_aRequests.pop_front();
            }
            process(*pStore, std::move(aRequest));
        }

        // NotificationStore owns the repository handle and is deliberately destroyed here, on the
        // same worker that constructed and used it.
        pStore.reset();
    }

    void process(NotificationStore& rStore, Request aRequest)
    {
        NotificationCenterResult aResult;
        aResult.RequestId = aRequest.Id;
        switch (aRequest.Kind)
        {
            case RequestKind::Snapshot:
                aResult.Mutation = successfulRead();
                break;
            case RequestKind::Add:
                aResult.Mutation = rStore.add(aRequest.Draft, &aResult.RecordId);
                break;
            case RequestKind::MarkRead:
                aResult.Mutation = rStore.markRead(aRequest.Ids, aRequest.Flag);
                break;
            case RequestKind::SetPinned:
                aResult.Mutation = rStore.setPinned(aRequest.Ids, aRequest.Flag);
                break;
            case RequestKind::Archive:
                aResult.Mutation = rStore.archive(aRequest.Ids);
                break;
            case RequestKind::Remove:
                aResult.Mutation = rStore.remove(aRequest.Ids);
                break;
            case RequestKind::Restore:
                aResult.Mutation = rStore.restore(aRequest.Ids);
                break;
            case RequestKind::Deduplicate:
                aResult.Mutation = rStore.deduplicate();
                break;
            case RequestKind::PurgeExpired:
                aResult.Mutation = rStore.purgeExpired();
                break;
            case RequestKind::EmptyTrash:
                aResult.Mutation = rStore.emptyTrash();
                break;
            case RequestKind::Maintain:
                aResult.Mutation = rStore.maintain();
                break;
            case RequestKind::Undo:
                aResult.Mutation = rStore.undo(aRequest.CommitId);
                break;
            case RequestKind::SetPreferences:
                try
                {
                    aRequest.Preferences = normalizeNotificationPreferences(aRequest.Preferences);
                    if (m_bPersistPreferences)
                        notification_detail::NotificationConfiguration::write(aRequest.Preferences);
                    rStore.setPreferences(aRequest.Preferences);
                    aResult.Mutation = successfulRead();
                }
                catch (const css::uno::Exception& rError)
                {
                    aResult.Mutation = failedRequest(rError.Message);
                }
                catch (const std::exception& rError)
                {
                    aResult.Mutation = failedRequest(OUString::fromUtf8(rError.what()));
                }
                break;
        }

        // A compare-and-swap conflict is reported to the caller, but the snapshot accompanying it
        // must reflect the winning repository state instead of the worker's stale precondition.
        if (aResult.Mutation.Conflict)
            (void)rStore.refresh();
        aResult.State = rStore.snapshot(++m_nGeneration, 1000);

        if (!aRequest.Completion)
            return;
        auto aCompletion = std::move(aRequest.Completion);
        try
        {
            m_aDispatcher(
                [aCompletion = std::move(aCompletion), aResult = std::move(aResult)]() mutable
                { aCompletion(std::move(aResult)); });
        }
        catch (const std::exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification completion failed: " << rError.what());
        }
    }

    OUString m_aRepositoryURL;
    NotificationPreferences m_aPreferences;
    NotificationStore::Clock m_aClock;
    NotificationStore::IdProvider m_aIdProvider;
    NotificationCenterService::CompletionDispatcher m_aDispatcher;
    const bool m_bPersistPreferences;

    std::mutex m_aMutex;
    std::condition_variable m_aWorkAvailable;
    std::deque<Request> m_aRequests;
    bool m_bAccepting = true;
    bool m_bStopWhenDrained = false;
    sal_uInt64 m_nNextRequestId = 1;
    sal_uInt64 m_nGeneration = 0;

    std::mutex m_aShutdownMutex;
    bool m_bJoined = false;
};
}

struct NotificationCenterService::Impl
{
    Impl(OUString aRepositoryURL, NotificationPreferences aPreferences,
         NotificationStore::Clock aClock, NotificationStore::IdProvider aIdProvider,
         CompletionDispatcher aDispatcher, bool bPersistPreferences,
         std::shared_ptr<UiCompletionQueue> xUiCompletions)
        : m_xUiCompletions(std::move(xUiCompletions))
        , m_xWorker(new NotificationWorker(std::move(aRepositoryURL), std::move(aPreferences),
                                           std::move(aClock), std::move(aIdProvider),
                                           std::move(aDispatcher), bPersistPreferences))
    {
        m_xWorker->launch();
    }

    ~Impl() { shutdown(); }

    sal_uInt64 enqueue(Request aRequest)
    {
        return m_xWorker.is() ? m_xWorker->enqueue(std::move(aRequest)) : 0;
    }

    void shutdown()
    {
        if (!m_xWorker.is())
            return;
        if (m_xUiCompletions)
            m_xUiCompletions->shutdown();
        m_xWorker->shutdown();
        m_xWorker.clear();
        m_xUiCompletions.reset();
    }

    std::shared_ptr<UiCompletionQueue> m_xUiCompletions;
    rtl::Reference<NotificationWorker> m_xWorker;
};

NotificationCenterService::NotificationCenterService(std::unique_ptr<Impl> pImpl)
    : m_pImpl(std::move(pImpl))
{
}

NotificationCenterService::~NotificationCenterService() { shutdown(); }

std::unique_ptr<NotificationCenterService> NotificationCenterService::createForProfile()
{
    NotificationPreferences aPreferences;
    try
    {
        aPreferences = notification_detail::NotificationConfiguration::read();
    }
    catch (const css::uno::Exception& rError)
    {
        SAL_WARN("sfx.notification",
                 "Could not read notification configuration: " << rError.Message);
    }
    catch (const std::exception& rError)
    {
        SAL_WARN("sfx.notification",
                 "Could not read notification configuration: " << rError.what());
    }
    auto xUiCompletions = std::make_shared<UiCompletionQueue>();
    CompletionDispatcher aDispatcher = [xUiCompletions](std::function<void()> aCompletion)
    { xUiCompletions->post(std::move(aCompletion)); };
    auto pImpl = std::make_unique<Impl>(NotificationStore::profileRepositoryURL(), aPreferences,
                                        NotificationStore::Clock(), NotificationStore::IdProvider(),
                                        std::move(aDispatcher), true, xUiCompletions);
    return std::unique_ptr<NotificationCenterService>(
        new NotificationCenterService(std::move(pImpl)));
}

std::unique_ptr<NotificationCenterService> NotificationCenterService::createForRepository(
    const OUString& rRepositoryURL, const NotificationPreferences& rPreferences,
    NotificationStore::Clock aClock, NotificationStore::IdProvider aIdProvider,
    CompletionDispatcher aDispatcher)
{
    auto pImpl
        = std::make_unique<Impl>(rRepositoryURL, rPreferences, std::move(aClock),
                                 std::move(aIdProvider), std::move(aDispatcher), false, nullptr);
    return std::unique_ptr<NotificationCenterService>(
        new NotificationCenterService(std::move(pImpl)));
}

sal_uInt64 NotificationCenterService::requestSnapshot(Completion aCompletion)
{
    Request aRequest;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::add(NotificationDraft aDraft, Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Add;
    aRequest.Draft = std::move(aDraft);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::markRead(std::vector<OString> aIds, bool bRead,
                                               Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::MarkRead;
    aRequest.Ids = std::move(aIds);
    aRequest.Flag = bRead;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::setPinned(std::vector<OString> aIds, bool bPinned,
                                                Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::SetPinned;
    aRequest.Ids = std::move(aIds);
    aRequest.Flag = bPinned;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::archive(std::vector<OString> aIds, Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Archive;
    aRequest.Ids = std::move(aIds);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::remove(std::vector<OString> aIds, Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Remove;
    aRequest.Ids = std::move(aIds);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::restore(std::vector<OString> aIds, Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Restore;
    aRequest.Ids = std::move(aIds);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::deduplicate(Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Deduplicate;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::purgeExpired(Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::PurgeExpired;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::emptyTrash(Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::EmptyTrash;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::maintain(Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Maintain;
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::undo(OString aCommitId, Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::Undo;
    aRequest.CommitId = std::move(aCommitId);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

sal_uInt64 NotificationCenterService::setPreferences(NotificationPreferences aPreferences,
                                                     Completion aCompletion)
{
    Request aRequest;
    aRequest.Kind = RequestKind::SetPreferences;
    aRequest.Preferences = std::move(aPreferences);
    aRequest.Completion = std::move(aCompletion);
    return m_pImpl ? m_pImpl->enqueue(std::move(aRequest)) : 0;
}

void NotificationCenterService::shutdown()
{
    if (m_pImpl)
        m_pImpl->shutdown();
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
