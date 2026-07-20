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
#include <stdexcept>
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
thread_local const void* g_pNotificationWorkerIdentity = nullptr;

class UiCompletionQueue final : public std::enable_shared_from_this<UiCompletionQueue>
{
public:
    ~UiCompletionQueue() { shutdown(); }

    void post(std::function<void()> aCompletion)
    {
        std::scoped_lock aGuard(m_aMutex);
        if (!m_bAccepting)
        {
            // Main-thread shutdown disposes these after the worker join. Off-main shutdown cannot
            // touch ImplSVEvent safely, so retain the closures for disposal by a VCL event.
            m_aCompletions.push_back(std::move(aCompletion));
            if (m_bDisposeCancelledOnUi && !m_pEvent)
            {
                m_xEventKeepAlive = shared_from_this();
                m_pEvent = Application::PostUserEvent(LINK(this, UiCompletionQueue, handleEvent));
                if (!m_pEvent)
                    SAL_WARN("sfx.notification",
                             "Could not marshal cancelled notification callbacks to VCL");
            }
            return;
        }
        m_aCompletions.push_back(std::move(aCompletion));
        if (!m_pEvent)
        {
            // Application::PostUserEvent retains only the raw Link instance. Keep this queue
            // alive until the event is either handled or explicitly cancelled, including when a
            // completion destroys the owning NotificationCenterService from inside handleEvent.
            m_xEventKeepAlive = shared_from_this();
            m_pEvent = Application::PostUserEvent(LINK(this, UiCompletionQueue, handleEvent));
            if (!m_pEvent)
            {
                m_xEventKeepAlive.reset();
                SAL_WARN("sfx.notification",
                         "Could not post notification completion event; retaining callbacks");
            }
        }
    }

    void shutdown()
    {
        const bool bCanCancelEvent = Application::IsMainThread();
        ImplSVEvent* pEvent = nullptr;
        std::shared_ptr<UiCompletionQueue> xKeepAlive;
        {
            std::scoped_lock aGuard(m_aMutex);
            if (!m_bAccepting && (!bCanCancelEvent || !m_pEvent))
                return;
            m_bAccepting = false;
            m_bDisposeCancelledOnUi = !bCanCancelEvent;
            if (!bCanCancelEvent)
            {
                if (!m_pEvent && !m_aCompletions.empty())
                {
                    m_xEventKeepAlive = shared_from_this();
                    m_pEvent
                        = Application::PostUserEvent(LINK(this, UiCompletionQueue, handleEvent));
                    if (!m_pEvent)
                        SAL_WARN("sfx.notification",
                                 "Could not marshal retained notification callbacks to VCL");
                }
                return;
            }
            pEvent = std::exchange(m_pEvent, nullptr);
            xKeepAlive = std::move(m_xEventKeepAlive);
        }
        if (pEvent)
            Application::RemoveUserEvent(pEvent);
    }

    void finishShutdown()
    {
        if (!Application::IsMainThread())
            return;
        std::deque<std::function<void()>> aCancelled;
        {
            std::scoped_lock aGuard(m_aMutex);
            m_bDisposeCancelledOnUi = false;
            aCancelled.swap(m_aCompletions);
        }
    }

private:
    DECL_LINK(handleEvent, void*, void);

    std::mutex m_aMutex;
    std::deque<std::function<void()>> m_aCompletions;
    ImplSVEvent* m_pEvent = nullptr;
    std::shared_ptr<UiCompletionQueue> m_xEventKeepAlive;
    bool m_bAccepting = true;
    bool m_bDisposeCancelledOnUi = false;
};

IMPL_LINK_NOARG(UiCompletionQueue, handleEvent, void*, void)
{
    // The member self-lease makes shared_from_this valid on entry. This local lease then keeps the
    // handler alive if a completion synchronously shuts down and destroys its owning service.
    auto xKeepAlive = shared_from_this();
    std::deque<std::function<void()>> aCompletions;
    {
        std::scoped_lock aGuard(m_aMutex);
        m_pEvent = nullptr;
        m_xEventKeepAlive.reset();
        if (!m_bAccepting)
        {
            aCompletions.swap(m_aCompletions);
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
        catch (const css::uno::Exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification UI completion failed: " << rError.Message);
        }
        catch (const std::exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification UI completion failed: " << rError.what());
        }
        catch (...)
        {
            SAL_WARN("sfx.notification", "Notification UI completion failed with an unknown error");
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
        , m_xWorkerIdentity(std::make_shared<const int>(0))
        , m_bPersistPreferences(bPersistPreferences)
    {
        if (!m_aDispatcher)
            throw std::invalid_argument(
                "notification completion dispatcher must queue work off the store worker without "
                "waiting");
    }

    ~NotificationWorker() override { assert(!m_bLaunched || m_bJoined); }

    void start()
    {
        launch();
        m_bLaunched = true;
    }

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

    void stopAccepting()
    {
        {
            std::scoped_lock aGuard(m_aMutex);
            m_bAccepting = false;
            m_bStopWhenDrained = true;
        }
        m_aWorkAvailable.notify_one();
    }

    void shutdown()
    {
        std::scoped_lock aShutdownGuard(m_aShutdownMutex);
        if (m_bJoined)
            return;
        stopAccepting();
        join();
        m_bJoined = true;
    }

private:
    void execute() override
    {
        assert(g_pNotificationWorkerIdentity == nullptr);
        g_pNotificationWorkerIdentity = m_xWorkerIdentity.get();
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
        g_pNotificationWorkerIdentity = nullptr;
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
        auto xWorkerIdentity = m_xWorkerIdentity;
        try
        {
            m_aDispatcher(
                [aCompletion = std::move(aCompletion), aResult = std::move(aResult),
                 xWorkerIdentity = std::move(xWorkerIdentity)]() mutable
                {
                    if (g_pNotificationWorkerIdentity == xWorkerIdentity.get())
                    {
                        SAL_WARN("sfx.notification",
                                 "Completion dispatcher ran on the store worker; "
                                 "suppressing callback");
                        return;
                    }
                    aCompletion(std::move(aResult));
                });
        }
        catch (const css::uno::Exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification completion failed: " << rError.Message);
        }
        catch (const std::exception& rError)
        {
            SAL_WARN("sfx.notification", "Notification completion failed: " << rError.what());
        }
        catch (...)
        {
            SAL_WARN("sfx.notification", "Notification completion failed with an unknown error");
        }
    }

    OUString m_aRepositoryURL;
    NotificationPreferences m_aPreferences;
    NotificationStore::Clock m_aClock;
    NotificationStore::IdProvider m_aIdProvider;
    NotificationCenterService::CompletionDispatcher m_aDispatcher;
    const std::shared_ptr<const int> m_xWorkerIdentity;
    const bool m_bPersistPreferences;

    std::mutex m_aMutex;
    std::condition_variable m_aWorkAvailable;
    std::deque<Request> m_aRequests;
    bool m_bAccepting = true;
    bool m_bStopWhenDrained = false;
    sal_uInt64 m_nNextRequestId = 1;
    sal_uInt64 m_nGeneration = 0;

    std::mutex m_aShutdownMutex;
    bool m_bLaunched = false;
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
        m_xWorker->start();
    }

    ~Impl() { shutdown(); }

    sal_uInt64 enqueue(Request aRequest) { return m_xWorker->enqueue(std::move(aRequest)); }

    void shutdown()
    {
        m_xWorker->stopAccepting();
        if (m_xUiCompletions)
            m_xUiCompletions->shutdown();
        m_xWorker->shutdown();
        if (m_xUiCompletions)
            m_xUiCompletions->finishShutdown();
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
