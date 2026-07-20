/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationcenter.hxx>

#include <unotools/tempfile.hxx>

#include <cppunit/TestAssert.h>
#include <cppunit/TestFixture.h>
#include <cppunit/extensions/HelperMacros.h>

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <vector>

namespace
{
static_assert(std::is_const_v<decltype(sfx2::NotificationCenterSnapshot::Records)>);
static_assert(std::is_const_v<decltype(sfx2::NotificationCenterSnapshot::History)>);

class TemporaryRepository
{
public:
    TemporaryRepository()
        : m_aDirectory(nullptr, true)
    {
        CPPUNIT_ASSERT(m_aDirectory.IsValid());
        m_aDirectory.EnableKillingFile();
    }

    const OUString& url() const { return m_aDirectory.GetURL(); }

private:
    utl::TempFileNamed m_aDirectory;
};

OString fixedId(char c) { return OString(std::string(32, c)); }

OString sequentialId(unsigned int nValue)
{
    OString aValue = OString::number(nValue, 16);
    return OString(std::string(32 - aValue.getLength(), '0')) + aValue;
}

sfx2::NotificationDraft draft(std::u16string_view rTitle)
{
    sfx2::NotificationDraft aDraft;
    aDraft.Source = "cppunit";
    aDraft.Privacy = sfx2::NotificationPrivacy::SafeDisplayText;
    aDraft.Title = OUString(rTitle);
    return aDraft;
}

class CompletionCollector
{
public:
    sfx2::NotificationCenterService::Completion callback()
    {
        return [this](sfx2::NotificationCenterResult aResult)
        {
            {
                std::scoped_lock aGuard(m_aMutex);
                m_aResults.push_back(std::move(aResult));
            }
            m_aChanged.notify_one();
        };
    }

    std::vector<sfx2::NotificationCenterResult> take(std::size_t nCount)
    {
        std::unique_lock aGuard(m_aMutex);
        CPPUNIT_ASSERT(m_aChanged.wait_for(aGuard, std::chrono::seconds(10),
                                           [this, nCount] { return m_aResults.size() >= nCount; }));
        std::vector<sfx2::NotificationCenterResult> aResults;
        aResults.reserve(nCount);
        for (std::size_t i = 0; i < nCount; ++i)
            aResults.push_back(std::move(m_aResults[i]));
        m_aResults.erase(m_aResults.begin(), m_aResults.begin() + nCount);
        return aResults;
    }

private:
    std::mutex m_aMutex;
    std::condition_variable m_aChanged;
    std::vector<sfx2::NotificationCenterResult> m_aResults;
};

class NotificationCenterServiceTest final : public CppUnit::TestFixture
{
    CPPUNIT_TEST_SUITE(NotificationCenterServiceTest);
    CPPUNIT_TEST(testSerializedOrderingAndImmutableSnapshots);
    CPPUNIT_TEST(testShutdownDrainsAcceptedMutations);
    CPPUNIT_TEST(testConflictRefreshesReturnedSnapshot);
    CPPUNIT_TEST(testBulkOperationCreatesExactlyOneCommit);
    CPPUNIT_TEST(testMetadataOnlyTextRemainsRedacted);
    CPPUNIT_TEST_SUITE_END();

public:
    void testSerializedOrderingAndImmutableSnapshots();
    void testShutdownDrainsAcceptedMutations();
    void testConflictRefreshesReturnedSnapshot();
    void testBulkOperationCreatesExactlyOneCommit();
    void testMetadataOnlyTextRemainsRedacted();
};

void NotificationCenterServiceTest::testSerializedOrderingAndImmutableSnapshots()
{
    TemporaryRepository aRepository;
    unsigned int nNextId = 1;
    sal_Int64 nNow = 100;
    auto xService = sfx2::NotificationCenterService::createForRepository(
        aRepository.url(), sfx2::NotificationPreferences(), [&nNow] { return nNow++; },
        [&nNextId] { return sequentialId(nNextId++); });
    CompletionCollector aCompletions;

    CPPUNIT_ASSERT_EQUAL(sal_uInt64(1), xService->add(draft(u"First"), aCompletions.callback()));
    CPPUNIT_ASSERT_EQUAL(sal_uInt64(2), xService->add(draft(u"Second"), aCompletions.callback()));
    CPPUNIT_ASSERT_EQUAL(sal_uInt64(3), xService->add(draft(u"Third"), aCompletions.callback()));

    auto aResults = aCompletions.take(3);
    for (std::size_t i = 0; i < aResults.size(); ++i)
    {
        CPPUNIT_ASSERT_EQUAL(static_cast<sal_uInt64>(i + 1), aResults[i].RequestId);
        CPPUNIT_ASSERT(aResults[i].Mutation.Success);
        CPPUNIT_ASSERT(aResults[i].State);
        CPPUNIT_ASSERT_EQUAL(static_cast<sal_uInt64>(i + 1), aResults[i].State->Generation);
        CPPUNIT_ASSERT_EQUAL(i + 1, aResults[i].State->Records.size());
    }
    CPPUNIT_ASSERT_EQUAL(u"Third"_ustr, aResults.back().State->Records.front().Title);
    xService->shutdown();
}

void NotificationCenterServiceTest::testShutdownDrainsAcceptedMutations()
{
    TemporaryRepository aRepository;
    unsigned int nNextId = 1;
    auto xService = sfx2::NotificationCenterService::createForRepository(
        aRepository.url(), sfx2::NotificationPreferences(), [] { return sal_Int64(200); },
        [&nNextId] { return sequentialId(nNextId++); });
    CompletionCollector aCompletions;

    constexpr std::size_t RequestCount = 24;
    for (std::size_t i = 0; i < RequestCount; ++i)
        CPPUNIT_ASSERT(xService->add(draft(u"Queued"), aCompletions.callback()) != 0);
    xService->shutdown();

    auto aResults = aCompletions.take(RequestCount);
    CPPUNIT_ASSERT(std::all_of(aResults.begin(), aResults.end(),
                               [](const auto& rResult) { return rResult.Mutation.Success; }));
    CPPUNIT_ASSERT_EQUAL(sal_uInt64(0), xService->requestSnapshot(aCompletions.callback()));

    sfx2::NotificationStore aReloaded(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(static_cast<sal_uInt32>(RequestCount),
                         aReloaded.count(sfx2::NotificationView::Inbox));
    CPPUNIT_ASSERT_EQUAL(RequestCount, aReloaded.history(100).size());
}

void NotificationCenterServiceTest::testConflictRefreshesReturnedSnapshot()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aWinner(
        aRepository.url(), [] { return sal_Int64(300); }, [] { return fixedId('1'); });
    bool bAdvanced = false;
    bool bWinnerSucceeded = false;
    OString aWinningCommit;
    auto xService = sfx2::NotificationCenterService::createForRepository(
        aRepository.url(), sfx2::NotificationPreferences(), [] { return sal_Int64(301); },
        [&]
        {
            if (!bAdvanced)
            {
                bAdvanced = true;
                auto aResult = aWinner.add(draft(u"Winner"));
                bWinnerSucceeded = aResult.Success;
                aWinningCommit = aResult.CommitId;
            }
            return fixedId('2');
        });
    CompletionCollector aCompletions;

    CPPUNIT_ASSERT(xService->add(draft(u"Stale"), aCompletions.callback()) != 0);
    auto aResult = std::move(aCompletions.take(1).front());
    CPPUNIT_ASSERT(!aResult.Mutation.Success);
    CPPUNIT_ASSERT(aResult.Mutation.Conflict);
    CPPUNIT_ASSERT(bWinnerSucceeded);
    CPPUNIT_ASSERT(aResult.State);
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aResult.State->Health);
    CPPUNIT_ASSERT_EQUAL(aWinningCommit, aResult.State->HeadCommitId);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aResult.State->Records.size());
    CPPUNIT_ASSERT_EQUAL(u"Winner"_ustr, aResult.State->Records.front().Title);
    xService->shutdown();
}

void NotificationCenterServiceTest::testBulkOperationCreatesExactlyOneCommit()
{
    TemporaryRepository aRepository;
    unsigned int nNextId = 1;
    sal_Int64 nNow = 400;
    auto xService = sfx2::NotificationCenterService::createForRepository(
        aRepository.url(), sfx2::NotificationPreferences(), [&nNow] { return nNow++; },
        [&nNextId] { return sequentialId(nNextId++); });
    CompletionCollector aCompletions;

    for (std::u16string_view aTitle : { u"One", u"Two", u"Three" })
        CPPUNIT_ASSERT(xService->add(draft(aTitle), aCompletions.callback()) != 0);
    auto aAdds = aCompletions.take(3);
    std::vector<OString> aIds;
    for (const auto& rAdd : aAdds)
        aIds.push_back(rAdd.RecordId);
    CPPUNIT_ASSERT_EQUAL(std::size_t(3), aAdds.back().State->History.size());

    CPPUNIT_ASSERT(xService->remove(aIds, aCompletions.callback()) != 0);
    auto aDelete = std::move(aCompletions.take(1).front());
    CPPUNIT_ASSERT(aDelete.Mutation.Success);
    CPPUNIT_ASSERT(aDelete.Mutation.CreatedCommit);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(3), aDelete.Mutation.Affected);
    CPPUNIT_ASSERT_EQUAL(std::size_t(4), aDelete.State->History.size());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationAction::Delete, aDelete.State->History.front().Action);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(3), aDelete.State->History.front().Affected);
    xService->shutdown();

    sfx2::NotificationStore aReloaded(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(std::size_t(4), aReloaded.history(100).size());
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(3), aReloaded.count(sfx2::NotificationView::Deleted));
}

void NotificationCenterServiceTest::testMetadataOnlyTextRemainsRedacted()
{
    TemporaryRepository aRepository;
    auto xService = sfx2::NotificationCenterService::createForRepository(
        aRepository.url(), sfx2::NotificationPreferences(), [] { return sal_Int64(500); },
        [] { return fixedId('5'); });
    CompletionCollector aCompletions;
    sfx2::NotificationDraft aPrivate;
    aPrivate.Source = "cppunit";
    aPrivate.Title = u"C:\\private\\document.odt"_ustr;
    aPrivate.Body = u"token=never-return-this"_ustr;

    CPPUNIT_ASSERT(xService->add(std::move(aPrivate), aCompletions.callback()) != 0);
    auto aResult = std::move(aCompletions.take(1).front());
    CPPUNIT_ASSERT(aResult.Mutation.Success);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aResult.State->Records.size());
    CPPUNIT_ASSERT(aResult.State->Records.front().Title.isEmpty());
    CPPUNIT_ASSERT(aResult.State->Records.front().Body.isEmpty());
    xService->shutdown();
}

CPPUNIT_TEST_SUITE_REGISTRATION(NotificationCenterServiceTest);
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
