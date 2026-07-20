/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationcenter.hxx>

#include <osl/file.hxx>
#include <rtl/textenc.h>
#include <tools/urlobj.hxx>
#include <unotools/tempfile.hxx>

#include <cppunit/TestAssert.h>
#include <cppunit/TestFixture.h>
#include <cppunit/extensions/HelperMacros.h>
#include <cppunit/plugin/TestPlugIn.h>

#include <zlib.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace
{
class TemporaryRepository
{
public:
    TemporaryRepository()
        : Directory(nullptr, true)
    {
        CPPUNIT_ASSERT(Directory.IsValid());
        Directory.EnableKillingFile();
    }

    const OUString& url() const { return Directory.GetURL(); }

private:
    utl::TempFileNamed Directory;
};

OUString childURL(const OUString& rParent, std::u16string_view rName)
{
    INetURLObject aURL(rParent);
    CPPUNIT_ASSERT(aURL.Append(rName, INetURLObject::EncodeMechanism::All));
    return aURL.GetMainURL(INetURLObject::DecodeMechanism::NONE);
}

std::string readFile(const OUString& rURL)
{
    osl::File aFile(rURL);
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.open(osl_File_OpenFlag_Read));
    sal_uInt64 nSize = 0;
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.getSize(nSize));
    std::string aResult(static_cast<std::size_t>(nSize), '\0');
    sal_uInt64 nRead = 0;
    if (nSize)
    {
        CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.read(aResult.data(), nSize, nRead));
        CPPUNIT_ASSERT_EQUAL(nSize, nRead);
    }
    return aResult;
}

bool fileExists(const OUString& rURL)
{
    osl::DirectoryItem aItem;
    return osl::DirectoryItem::get(rURL, aItem) == osl::FileBase::E_None;
}

OString fixedId(char c) { return OString(std::string(32, c)); }

OString sequentialId(unsigned int nValue)
{
    OString aValue = OString::number(nValue, 16);
    return OString(std::string(32 - aValue.getLength(), '0')) + aValue;
}

void createEmptyFile(const OUString& rURL)
{
    osl::File aFile(rURL);
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None,
                         aFile.open(osl_File_OpenFlag_Write | osl_File_OpenFlag_Create));
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.sync());
}

void writeFile(const OUString& rURL, std::string_view rContents)
{
    osl::File aFile(rURL);
    sal_uInt32 nFlags = osl_File_OpenFlag_Write;
    if (!fileExists(rURL))
        nFlags |= osl_File_OpenFlag_Create;
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.open(nFlags));
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.setSize(0));
    sal_uInt64 nWritten = 0;
    if (!rContents.empty())
    {
        CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None,
                             aFile.write(rContents.data(), rContents.size(), nWritten));
        CPPUNIT_ASSERT_EQUAL(static_cast<sal_uInt64>(rContents.size()), nWritten);
    }
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aFile.sync());
}

OUString looseObjectURL(const OUString& rRepositoryURL, const OString& rObjectId)
{
    CPPUNIT_ASSERT_EQUAL(sal_Int32(40), rObjectId.getLength());
    OUString aDirectory = OUString::fromUtf8(std::string_view(rObjectId.getStr(), 2));
    OUString aFilename = OUString::fromUtf8(std::string_view(rObjectId.getStr() + 2, 38));
    return childURL(childURL(childURL(rRepositoryURL, u"objects"), aDirectory), aFilename);
}

sfx2::NotificationDraft draft(std::u16string_view rTitle = u"Safe notification")
{
    sfx2::NotificationDraft aDraft;
    aDraft.Source = "cppunit";
    aDraft.Privacy = sfx2::NotificationPrivacy::SafeDisplayText;
    aDraft.Title = OUString(rTitle);
    return aDraft;
}

std::filesystem::path systemPath(const OUString& rURL)
{
    OUString aSystemPath;
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None,
                         osl::FileBase::getSystemPathFromFileURL(rURL, aSystemPath));
    OString aUtf8 = OUStringToOString(aSystemPath, RTL_TEXTENCODING_UTF8);
    const auto* pUtf8 = reinterpret_cast<const char8_t*>(aUtf8.getStr());
    return std::filesystem::path(std::u8string_view(pUtf8, aUtf8.getLength()));
}

bool inflatedObjectsContain(const OUString& rRepositoryURL, std::string_view rNeedle)
{
    std::filesystem::path aObjects = systemPath(childURL(rRepositoryURL, u"objects"));
    for (const auto& rEntry : std::filesystem::recursive_directory_iterator(aObjects))
    {
        if (!rEntry.is_regular_file())
            continue;
        std::ifstream aInput(rEntry.path(), std::ios::binary);
        std::string aCompressed((std::istreambuf_iterator<char>(aInput)),
                                std::istreambuf_iterator<char>());
        std::string aInflated(5 * 1024 * 1024, '\0');
        uLongf nSize = static_cast<uLongf>(aInflated.size());
        if (uncompress(reinterpret_cast<Bytef*>(aInflated.data()), &nSize,
                       reinterpret_cast<const Bytef*>(aCompressed.data()),
                       static_cast<uLong>(aCompressed.size()))
            != Z_OK)
            continue;
        aInflated.resize(nSize);
        if (aInflated.find(rNeedle) != std::string::npos)
            return true;
    }
    return false;
}

std::uintmax_t directoryBytes(const OUString& rRepositoryURL)
{
    std::uintmax_t nBytes = 0;
    for (const auto& rEntry :
         std::filesystem::recursive_directory_iterator(systemPath(rRepositoryURL)))
    {
        if (rEntry.is_regular_file())
            nBytes += rEntry.file_size();
    }
    return nBytes;
}

std::uintmax_t objectFileCount(const OUString& rRepositoryURL)
{
    std::uintmax_t nFiles = 0;
    std::filesystem::path aObjects = systemPath(childURL(rRepositoryURL, u"objects"));
    for (const auto& rEntry : std::filesystem::recursive_directory_iterator(aObjects))
    {
        if (rEntry.is_regular_file())
            ++nFiles;
    }
    return nFiles;
}

sfx2::NotificationRecord recordById(sfx2::NotificationStore& rStore, const OString& rId)
{
    std::vector<sfx2::NotificationRecord> aRecords = rStore.query(sfx2::NotificationView::All);
    auto aIt = std::find_if(aRecords.begin(), aRecords.end(),
                            [&rId](const auto& rRecord) { return rRecord.Id == rId; });
    CPPUNIT_ASSERT(aIt != aRecords.end());
    return *aIt;
}

class NotificationStoreTest final : public CppUnit::TestFixture
{
    CPPUNIT_TEST_SUITE(NotificationStoreTest);
    CPPUNIT_TEST(testBareRepositoryAndReload);
    CPPUNIT_TEST(testBulkFoldersAndRecoverableTombstones);
    CPPUNIT_TEST(testUndoCreatesNewCommitAndDetectsConflict);
    CPPUNIT_TEST(testPrivacyRedactionAndGuard);
    CPPUNIT_TEST(testCompareAndSwapRejectsLostUpdate);
    CPPUNIT_TEST(testNoOpHasNoUndoCommit);
    CPPUNIT_TEST(testCrossStoreReadsRefresh);
    CPPUNIT_TEST(testConcurrentInitializationAndStaleLockRecovery);
    CPPUNIT_TEST(testPermanentGuardContention);
    CPPUNIT_TEST(testRetentionLimitAndEpochZero);
    CPPUNIT_TEST(testCompactionBoundsHistoryUndoAndPendingRecovery);
    CPPUNIT_TEST(testUnsupportedRepositoryFeatureFailsClosed);
    CPPUNIT_TEST(testPreferenceBounds);
    CPPUNIT_TEST_SUITE_END();

public:
    void testBareRepositoryAndReload();
    void testBulkFoldersAndRecoverableTombstones();
    void testUndoCreatesNewCommitAndDetectsConflict();
    void testPrivacyRedactionAndGuard();
    void testCompareAndSwapRejectsLostUpdate();
    void testNoOpHasNoUndoCommit();
    void testCrossStoreReadsRefresh();
    void testConcurrentInitializationAndStaleLockRecovery();
    void testPermanentGuardContention();
    void testRetentionLimitAndEpochZero();
    void testCompactionBoundsHistoryUndoAndPendingRecovery();
    void testUnsupportedRepositoryFeatureFailsClosed();
    void testPreferenceBounds();
};

void NotificationStoreTest::testBareRepositoryAndReload()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aStore(
        aRepository.url(), [] { return sal_Int64(1000); }, [] { return fixedId('1'); });
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aStore.health());
    CPPUNIT_ASSERT_EQUAL(std::string("ref: refs/heads/main\n"),
                         readFile(childURL(aRepository.url(), u"HEAD")));
    std::string aConfig = readFile(childURL(aRepository.url(), u"config"));
    CPPUNIT_ASSERT(aConfig.find("bare = true") != std::string::npos);
    CPPUNIT_ASSERT(aConfig.find("auto = 0") != std::string::npos);

    OString aId;
    auto aAdd = aStore.add(draft(), &aId);
    CPPUNIT_ASSERT(aAdd.Success);
    CPPUNIT_ASSERT_EQUAL(fixedId('1'), aId);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(40), aAdd.CommitId.getLength());
    CPPUNIT_ASSERT_EQUAL(
        std::string(aAdd.CommitId) + "\n",
        readFile(childURL(childURL(childURL(aRepository.url(), u"refs"), u"heads"), u"main")));
    // Independently calculated Git blob ID for the exact JsonWriter-formatted snapshot.
    CPPUNIT_ASSERT(fileExists(childURL(childURL(childURL(aRepository.url(), u"objects"), u"47"),
                                       u"f3a04c1c9e31888c417286736e827946dbc213")));

    sfx2::NotificationStore aReloaded(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aReloaded.health());
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aReloaded.count(sfx2::NotificationView::Inbox));
    CPPUNIT_ASSERT_EQUAL(aAdd.CommitId, aReloaded.headCommitId());
}

void NotificationStoreTest::testBulkFoldersAndRecoverableTombstones()
{
    TemporaryRepository aRepository;
    sal_Int64 nTime = 100;
    unsigned int nId = 1;
    sfx2::NotificationStore aStore(
        aRepository.url(), [&nTime] { return nTime++; },
        [&nId] { return fixedId(static_cast<char>('0' + nId++)); });
    OString aFirst;
    OString aSecond;
    CPPUNIT_ASSERT(aStore.add(draft(u"First"), &aFirst).Success);
    CPPUNIT_ASSERT(aStore.add(draft(u"Second"), &aSecond).Success);

    auto aRead = aStore.markRead({ aFirst, aSecond }, true);
    CPPUNIT_ASSERT(aRead.Success);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(2), aRead.Affected);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(0), aStore.count(sfx2::NotificationView::Unread));
    CPPUNIT_ASSERT(aStore.archive({ aFirst }).Success);
    CPPUNIT_ASSERT(aStore.remove({ aFirst, aSecond }).Success);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(2), aStore.count(sfx2::NotificationView::Deleted));

    sfx2::NotificationStore aReloaded(aRepository.url(), [&nTime] { return nTime++; });
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(2), aReloaded.count(sfx2::NotificationView::Deleted));
    auto aRestore = aReloaded.restore({ aFirst, aSecond });
    CPPUNIT_ASSERT(aRestore.Success);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aReloaded.count(sfx2::NotificationView::Archived));
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aReloaded.count(sfx2::NotificationView::Inbox));
}

void NotificationStoreTest::testUndoCreatesNewCommitAndDetectsConflict()
{
    TemporaryRepository aRepository;
    sal_Int64 nTime = 100;
    sfx2::NotificationStore aStore(
        aRepository.url(), [&nTime] { return nTime++; }, [] { return fixedId('1'); });
    OString aId;
    CPPUNIT_ASSERT(aStore.add(draft(), &aId).Success);
    auto aDelete = aStore.remove({ aId });
    CPPUNIT_ASSERT(aDelete.Success);
    auto aUndo = aStore.undo(aDelete.CommitId);
    CPPUNIT_ASSERT(aUndo.Success);
    CPPUNIT_ASSERT(aUndo.CommitId != aDelete.CommitId);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aStore.count(sfx2::NotificationView::Inbox));
    CPPUNIT_ASSERT(aStore.markRead({ aId }, true).Success);
    auto aConflictingUndo = aStore.undo(aDelete.CommitId);
    CPPUNIT_ASSERT(!aConflictingUndo.Success);
    CPPUNIT_ASSERT(aConflictingUndo.Conflict);

    sfx2::NotificationStore aReloaded(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aReloaded.count(sfx2::NotificationView::Inbox));
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(0), aReloaded.count(sfx2::NotificationView::Unread));
}

void NotificationStoreTest::testPrivacyRedactionAndGuard()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aStore(
        aRepository.url(), [] { return sal_Int64(1000); }, [] { return fixedId('1'); });
    sfx2::NotificationDraft aPrivate;
    aPrivate.Source = "cppunit";
    aPrivate.Title = u"TOP-SECRET-PATH C:\\private\\document.odt"_ustr;
    aPrivate.Body = u"token=never-persist-this"_ustr;
    OString aId;
    CPPUNIT_ASSERT(aStore.add(aPrivate, &aId).Success);
    CPPUNIT_ASSERT(!inflatedObjectsContain(aRepository.url(), "TOP-SECRET-PATH"));
    CPPUNIT_ASSERT(!inflatedObjectsContain(aRepository.url(), "never-persist-this"));

    sfx2::NotificationStore aReloaded(aRepository.url());
    auto aRecords = aReloaded.query(sfx2::NotificationView::Inbox);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aRecords.size());
    CPPUNIT_ASSERT(aRecords.front().Title.isEmpty());
    CPPUNIT_ASSERT(aRecords.front().Body.isEmpty());

    auto aUnsafe = draft(u"Open file:///C:/private/document.odt");
    auto aRejected = aReloaded.add(aUnsafe);
    CPPUNIT_ASSERT(!aRejected.Success);
    auto aUnapproved = draft(u"Harmless text");
    aUnapproved.Source = "extension-producer";
    CPPUNIT_ASSERT(!aReloaded.add(aUnapproved).Success);
}

void NotificationStoreTest::testCompareAndSwapRejectsLostUpdate()
{
    TemporaryRepository aRepository;
    sal_Int64 nTime = 100;
    sfx2::NotificationStore aFirst(
        aRepository.url(), [&nTime] { return nTime++; }, [] { return fixedId('1'); });
    bool bAdvanced = false;
    sfx2::NotificationStore aStale(
        aRepository.url(), [&nTime] { return nTime++; },
        [&]
        {
            if (!bAdvanced)
            {
                bAdvanced = true;
                CPPUNIT_ASSERT(aFirst.add(draft(u"Concurrent"), nullptr).Success);
            }
            return fixedId('2');
        });

    auto aResult = aStale.add(draft(u"Stale"));
    CPPUNIT_ASSERT(!aResult.Success);
    CPPUNIT_ASSERT(aResult.Conflict);
    sfx2::NotificationStore aReloaded(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aReloaded.count(sfx2::NotificationView::Inbox));
}

void NotificationStoreTest::testNoOpHasNoUndoCommit()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aStore(
        aRepository.url(), [] { return sal_Int64(100); }, [] { return fixedId('1'); });
    OString aId;
    auto aAdd = aStore.add(draft(), &aId);
    CPPUNIT_ASSERT(aAdd.CreatedCommit);
    auto aEmpty = aStore.markRead({}, true);
    CPPUNIT_ASSERT(aEmpty.Success);
    CPPUNIT_ASSERT(!aEmpty.CreatedCommit);
    CPPUNIT_ASSERT(aEmpty.CommitId.isEmpty());
    auto aNoChange = aStore.markRead({ aId }, false);
    CPPUNIT_ASSERT(aNoChange.Success);
    CPPUNIT_ASSERT(!aNoChange.CreatedCommit);
    CPPUNIT_ASSERT(aNoChange.CommitId.isEmpty());
    CPPUNIT_ASSERT(!aStore.undo(aNoChange.CommitId).Success);
    CPPUNIT_ASSERT_EQUAL(aAdd.CommitId, aStore.headCommitId());
}

void NotificationStoreTest::testCrossStoreReadsRefresh()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aWriter(
        aRepository.url(), [] { return sal_Int64(100); }, [] { return fixedId('1'); });
    sfx2::NotificationStore aObserver(aRepository.url());
    auto aAdd = aWriter.add(draft());
    CPPUNIT_ASSERT(aAdd.Success);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aObserver.count(sfx2::NotificationView::Inbox));
    CPPUNIT_ASSERT_EQUAL(aAdd.CommitId, aObserver.headCommitId());
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aObserver.history().size());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationAction::Add, aObserver.history().front().Action);
}

void NotificationStoreTest::testConcurrentInitializationAndStaleLockRecovery()
{
    TemporaryRepository aRepository;
    createEmptyFile(childURL(aRepository.url(), u"HEAD"));
    std::unique_ptr<sfx2::NotificationStore> xFirst;
    std::unique_ptr<sfx2::NotificationStore> xSecond;
    std::thread aFirst([&]
                       { xFirst = std::make_unique<sfx2::NotificationStore>(aRepository.url()); });
    std::thread aSecond(
        [&] { xSecond = std::make_unique<sfx2::NotificationStore>(aRepository.url()); });
    aFirst.join();
    aSecond.join();
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, xFirst->health());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, xSecond->health());
    CPPUNIT_ASSERT_EQUAL(std::string("ref: refs/heads/main\n"),
                         readFile(childURL(aRepository.url(), u"HEAD")));

    OUString aLock
        = childURL(childURL(childURL(aRepository.url(), u"refs"), u"heads"), u"main.lock");
    createEmptyFile(aLock);
    sfx2::NotificationStore aRecovered(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aRecovered.health());
    CPPUNIT_ASSERT(!fileExists(aLock));
}

void NotificationStoreTest::testPermanentGuardContention()
{
    TemporaryRepository aRepository;
    sfx2::NotificationStore aInitialized(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aInitialized.health());
    OUString aGuardURL = childURL(aRepository.url(), u"notification.guard");
    CPPUNIT_ASSERT_EQUAL(std::string("LibreOffice notification history guard\n"),
                         readFile(aGuardURL));
    CPPUNIT_ASSERT(!fileExists(childURL(aRepository.url(), u"notification-operation.lock")));

#ifdef _WIN32
    // Windows sharing rules make a second write-capable OSL open deterministic even within this
    // process. Unix record locks are process-scoped; this fixture does not misrepresent two
    // same-process opens as inter-process proof. Its concurrent-constructor test and the source
    // contract cover the process mutex, while an actual Unix cross-process lock remains build QA.
    osl::File aHeldGuard(aGuardURL);
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None,
                         aHeldGuard.open(osl_File_OpenFlag_Read | osl_File_OpenFlag_Write));
    sfx2::NotificationStore aBlocked(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Unavailable, aBlocked.health());
    CPPUNIT_ASSERT(aBlocked.lastError().indexOf(u"busy") >= 0);
    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, aHeldGuard.close());

    sfx2::NotificationStore aResumed(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aResumed.health());
#endif
}

void NotificationStoreTest::testRetentionLimitAndEpochZero()
{
    TemporaryRepository aRepository;
    sal_Int64 nNow = 0;
    unsigned int nId = 1;
    sfx2::NotificationStore aStore(
        aRepository.url(), [&] { return nNow; }, [&] { return sequentialId(nId++); });
    sfx2::NotificationPreferences aPreferences;
    aPreferences.HistoryLimit = 100;
    aPreferences.HistoryRetentionDays = 1;
    aStore.setPreferences(aPreferences);

    OString aFirst;
    CPPUNIT_ASSERT(aStore.add(draft(u"Epoch zero"), &aFirst).Success);
    CPPUNIT_ASSERT(aStore.remove({ aFirst }).Success);
    auto aDeleted = aStore.query(sfx2::NotificationView::Deleted);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aDeleted.size());
    CPPUNIT_ASSERT(aDeleted.front().DeletedAt > 0);

    nNow = 24 * 60 * 60 + 2;
    auto aPurge = aStore.purgeExpired();
    CPPUNIT_ASSERT(aPurge.Success);
    CPPUNIT_ASSERT(aPurge.CreatedCommit);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(0), aStore.count(sfx2::NotificationView::Deleted));

    for (unsigned int i = 0; i < 101; ++i)
        CPPUNIT_ASSERT(aStore.add(draft(u"Bounded"), nullptr).Success);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(100), aStore.count(sfx2::NotificationView::All));
    CPPUNIT_ASSERT(directoryBytes(aRepository.url()) < 16 * 1024 * 1024);
    CPPUNIT_ASSERT(aStore.maintain().Success);
}

void NotificationStoreTest::testCompactionBoundsHistoryUndoAndPendingRecovery()
{
    TemporaryRepository aRepository;
    sal_Int64 nTime = 100;
    unsigned int nId = 1;
    sfx2::NotificationStore aStore(
        aRepository.url(), [&nTime] { return nTime++; }, [&nId] { return sequentialId(nId++); });

    OString aFirstId;
    OString aSecondId;
    auto aFirstAdd = aStore.add(draft(u"First retained record"), &aFirstId);
    CPPUNIT_ASSERT(aFirstAdd.Success);
    CPPUNIT_ASSERT(aStore.add(draft(u"Second retained record"), &aSecondId).Success);

    // Two adds plus 127 alternating state changes produce 129 reachable commits. The following
    // delete must compact the pre-delete state, then remain a normal child that is exactly undoable.
    for (unsigned int i = 0; i < 127; ++i)
    {
        auto aToggle = aStore.markRead({ aFirstId }, i % 2 == 0);
        CPPUNIT_ASSERT(aToggle.Success);
        CPPUNIT_ASSERT(aToggle.CreatedCommit);
    }
    OString aPreCompactionHead = aStore.headCommitId();
    sfx2::NotificationRecord aFirstBefore = recordById(aStore, aFirstId);
    sfx2::NotificationRecord aSecondBefore = recordById(aStore, aSecondId);
    CPPUNIT_ASSERT(aFirstBefore.Read);

    auto aThresholdDelete = aStore.remove({ aSecondId });
    CPPUNIT_ASSERT(aThresholdDelete.Success);
    CPPUNIT_ASSERT(aThresholdDelete.CreatedCommit);
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationAction::Delete, aThresholdDelete.Action);
    CPPUNIT_ASSERT_EQUAL(aThresholdDelete.CommitId, aStore.headCommitId());

    auto aHistory = aStore.history(1000);
    CPPUNIT_ASSERT_EQUAL(std::size_t(2), aHistory.size());
    CPPUNIT_ASSERT_EQUAL(aThresholdDelete.CommitId, aHistory[0].CommitId);
    CPPUNIT_ASSERT_EQUAL(aHistory[1].CommitId, aHistory[0].ParentId);
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationAction::Maintenance, aHistory[1].Action);
    CPPUNIT_ASSERT(aHistory[1].ParentId.isEmpty());
    OString aCheckpoint = aHistory[1].CommitId;
    CPPUNIT_ASSERT(!fileExists(looseObjectURL(aRepository.url(), aFirstAdd.CommitId)));
    CPPUNIT_ASSERT(directoryBytes(aRepository.url()) < 16 * 1024 * 1024);

    auto aUndo = aStore.undo(aThresholdDelete.CommitId);
    CPPUNIT_ASSERT(aUndo.Success);
    CPPUNIT_ASSERT(aFirstBefore == recordById(aStore, aFirstId));
    CPPUNIT_ASSERT(aSecondBefore == recordById(aStore, aSecondId));
    CPPUNIT_ASSERT(!aStore.undo(aCheckpoint).Success);

    // Model a crash after a parentless checkpoint was written to main.lock but before ref install.
    // The checkpoint-from header authorizes this one deterministic recovery without pretending the
    // checkpoint is a normal child. A pending marker then forces prune completion before the next
    // user mutation is accepted.
    OUString aHeads = childURL(childURL(aRepository.url(), u"refs"), u"heads");
    OUString aMain = childURL(aHeads, u"main");
    OUString aMainLock = childURL(aHeads, u"main.lock");
    OUString aPending = childURL(aRepository.url(), u"compaction.pending");
    writeFile(aMain, std::string(aPreCompactionHead) + "\n");
    writeFile(aMainLock, std::string(aCheckpoint) + "\n");
    writeFile(aPending, "notification-compaction-pending 1\n");

    sfx2::NotificationStore aRecovered(aRepository.url(), [&nTime] { return nTime++; });
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Ready, aRecovered.health());
    CPPUNIT_ASSERT_EQUAL(aCheckpoint, aRecovered.headCommitId());
    CPPUNIT_ASSERT(!fileExists(aMainLock));
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aRecovered.history(1000).size());
    CPPUNIT_ASSERT(aFirstBefore == recordById(aRecovered, aFirstId));
    CPPUNIT_ASSERT(aSecondBefore == recordById(aRecovered, aSecondId));

    // Force prune to fail twice while the durable marker and installed checkpoint remain. Neither
    // retry may write or install another timestamped checkpoint: disk use and the ref stay stable.
    OUString aPoisonDirectory = childURL(childURL(aRepository.url(), u"objects"), u"ff");
    osl::FileBase::RC ePoisonDirectory = osl::Directory::create(aPoisonDirectory);
    CPPUNIT_ASSERT(ePoisonDirectory == osl::FileBase::E_None
                   || ePoisonDirectory == osl::FileBase::E_EXIST);
    OUString aPruneBlocker = childURL(aPoisonDirectory, u"forced-prune-failure");
    createEmptyFile(aPruneBlocker);

    auto aFirstPruneFailure = aRecovered.remove({ aSecondId });
    CPPUNIT_ASSERT(!aFirstPruneFailure.Success);
    CPPUNIT_ASSERT_EQUAL(aCheckpoint, aRecovered.headCommitId());
    CPPUNIT_ASSERT(fileExists(aPending));
    std::uintmax_t nObjectsAfterFirstFailure = objectFileCount(aRepository.url());

    CPPUNIT_ASSERT(aRecovered.refresh());
    auto aSecondPruneFailure = aRecovered.remove({ aSecondId });
    CPPUNIT_ASSERT(!aSecondPruneFailure.Success);
    CPPUNIT_ASSERT_EQUAL(aCheckpoint, aRecovered.headCommitId());
    CPPUNIT_ASSERT_EQUAL(nObjectsAfterFirstFailure, objectFileCount(aRepository.url()));
    CPPUNIT_ASSERT(fileExists(aPending));

    CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None, osl::File::remove(aPruneBlocker));
    CPPUNIT_ASSERT(aRecovered.refresh());
    auto aDeleteAfterRecovery = aRecovered.remove({ aSecondId });
    CPPUNIT_ASSERT(aDeleteAfterRecovery.Success);
    CPPUNIT_ASSERT_EQUAL(aDeleteAfterRecovery.CommitId, aRecovered.headCommitId());
    CPPUNIT_ASSERT(!fileExists(aPending));
    CPPUNIT_ASSERT(aRecovered.history(1000).size() <= 2);
    CPPUNIT_ASSERT(directoryBytes(aRepository.url()) < 16 * 1024 * 1024);
}

void NotificationStoreTest::testUnsupportedRepositoryFeatureFailsClosed()
{
    TemporaryRepository aRepository;
    OUString aHooks = childURL(aRepository.url(), u"hooks");
    osl::FileBase::RC eCreate = osl::Directory::create(aHooks);
    CPPUNIT_ASSERT(eCreate == osl::FileBase::E_None || eCreate == osl::FileBase::E_EXIST);
    sfx2::NotificationStore aStore(aRepository.url());
    CPPUNIT_ASSERT_EQUAL(sfx2::NotificationStoreHealth::Unsupported, aStore.health());
    CPPUNIT_ASSERT(!aStore.add(draft()).Success);
}

void NotificationStoreTest::testPreferenceBounds()
{
    sfx2::NotificationPreferences aInput;
    aInput.MaxVisible = -1;
    aInput.Width = 10000;
    aInput.TimeoutSeconds = -10;
    aInput.OpacityPercent = 1;
    aInput.AccentColor = 0x7fffffff;
    aInput.HistoryRetentionDays = 0;
    aInput.HistoryLimit = 99999;
    auto aResult = sfx2::normalizeNotificationPreferences(aInput);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), aResult.MaxVisible);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(720), aResult.Width);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0), aResult.TimeoutSeconds);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(70), aResult.OpacityPercent);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(0xffffff), aResult.AccentColor);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), aResult.HistoryRetentionDays);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(5000), aResult.HistoryLimit);
}

CPPUNIT_TEST_SUITE_REGISTRATION(NotificationStoreTest);
}

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
