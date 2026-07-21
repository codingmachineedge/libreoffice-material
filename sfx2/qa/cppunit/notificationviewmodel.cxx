/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/notificationcenter.hxx>

// The view-model is an internal, headless-testable transform layer; include it directly so the
// focused notification target exercises the real symbols the manager and stack UI depend on.
#include "../../source/notification/NotificationViewModel.hxx"

#include <cppunit/TestAssert.h>
#include <cppunit/TestFixture.h>
#include <cppunit/extensions/HelperMacros.h>

#include <memory>
#include <optional>
#include <set>
#include <string_view>
#include <vector>

using namespace sfx2;

namespace
{
NotificationRecord makeRecord(std::string_view rId, NotificationFolder eFolder, bool bRead,
                              sal_Int64 nCreatedAt,
                              NotificationSeverity eSeverity = NotificationSeverity::Information,
                              std::string_view rSource = "custom.source")
{
    NotificationRecord aRecord;
    aRecord.Id = OString(rId);
    aRecord.Source = OString(rSource);
    aRecord.Severity = eSeverity;
    aRecord.Folder = eFolder;
    aRecord.Read = bRead;
    aRecord.CreatedAt = nCreatedAt;
    return aRecord;
}

NotificationHistoryEntry makeHistory(std::string_view rCommit, NotificationAction eAction,
                                     sal_Int64 nTimestamp)
{
    NotificationHistoryEntry aEntry;
    aEntry.CommitId = OString(rCommit);
    aEntry.Action = eAction;
    aEntry.Timestamp = nTimestamp;
    return aEntry;
}

NotificationCenterSnapshotRef makeSnapshot(std::vector<NotificationRecord> aRecords,
                                           std::vector<NotificationHistoryEntry> aHistory = {},
                                           NotificationPreferences aPreferences
                                           = NotificationPreferences())
{
    return std::make_shared<const NotificationCenterSnapshot>(
        /*nGeneration*/ 1, NotificationStoreHealth::Ready, OUString(), OString(),
        std::move(aPreferences), std::move(aRecords), std::move(aHistory));
}

std::vector<OString> rowIds(const std::vector<NotificationDisplayRow>& rRows)
{
    std::vector<OString> aIds;
    aIds.reserve(rRows.size());
    for (const NotificationDisplayRow& rRow : rRows)
        aIds.push_back(rRow.Id);
    return aIds;
}

class NotificationViewModelTest final : public CppUnit::TestFixture
{
public:
    void testClampVisible();
    void testCounts();
    void testVisibleCardsNewestFirstAndCap();
    void testVisibleCardsExcludeArchivedAndDeleted();
    void testRowsForViewFilterAndSort();
    void testSelectionVectorStableSnapshotOrder();
    void testReconcileSelectionDropsVanished();
    void testLatestUndoableCommitSkipsMaintenance();
    void testMakeRowRedaction();
    void testDistinctSources();

    CPPUNIT_TEST_SUITE(NotificationViewModelTest);
    CPPUNIT_TEST(testClampVisible);
    CPPUNIT_TEST(testCounts);
    CPPUNIT_TEST(testVisibleCardsNewestFirstAndCap);
    CPPUNIT_TEST(testVisibleCardsExcludeArchivedAndDeleted);
    CPPUNIT_TEST(testRowsForViewFilterAndSort);
    CPPUNIT_TEST(testSelectionVectorStableSnapshotOrder);
    CPPUNIT_TEST(testReconcileSelectionDropsVanished);
    CPPUNIT_TEST(testLatestUndoableCommitSkipsMaintenance);
    CPPUNIT_TEST(testMakeRowRedaction);
    CPPUNIT_TEST(testDistinctSources);
    CPPUNIT_TEST_SUITE_END();
};

void NotificationViewModelTest::testClampVisible()
{
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), NotificationViewModel::ClampVisible(0));
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), NotificationViewModel::ClampVisible(-5));
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), NotificationViewModel::ClampVisible(1));
    CPPUNIT_ASSERT_EQUAL(sal_Int32(3), NotificationViewModel::ClampVisible(3));
    CPPUNIT_ASSERT_EQUAL(sal_Int32(10), NotificationViewModel::ClampVisible(10));
    CPPUNIT_ASSERT_EQUAL(sal_Int32(10), NotificationViewModel::ClampVisible(11));
}

void NotificationViewModelTest::testCounts()
{
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot({
        makeRecord("a", NotificationFolder::Inbox, /*read*/ false, 10),
        makeRecord("b", NotificationFolder::Inbox, /*read*/ true, 20),
        makeRecord("c", NotificationFolder::Inbox, /*read*/ false, 30),
        makeRecord("d", NotificationFolder::Archived, /*read*/ true, 40),
        makeRecord("e", NotificationFolder::Deleted, /*read*/ false, 50),
    });
    const NotificationCounts aCounts = NotificationViewModel::Counts(*xSnapshot);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(3), aCounts.Inbox);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(2), aCounts.Unread);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aCounts.Archived);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1), aCounts.Deleted);
}

void NotificationViewModelTest::testVisibleCardsNewestFirstAndCap()
{
    NotificationPreferences aPreferences;
    aPreferences.MaxVisible = 2;
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot(
        {
            makeRecord("old", NotificationFolder::Inbox, false, 10),
            makeRecord("mid", NotificationFolder::Inbox, false, 20),
            makeRecord("new", NotificationFolder::Inbox, false, 30),
        },
        {}, aPreferences);

    const std::vector<NotificationDisplayRow> aRows
        = NotificationViewModel::VisibleCards(*xSnapshot, aPreferences);
    CPPUNIT_ASSERT_EQUAL(std::size_t(2), aRows.size());
    // Newest first, capped at MaxVisible.
    CPPUNIT_ASSERT_EQUAL(OString("new"), aRows[0].Id);
    CPPUNIT_ASSERT_EQUAL(OString("mid"), aRows[1].Id);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(1),
                         NotificationViewModel::HiddenCardCount(*xSnapshot, aPreferences));
}

void NotificationViewModelTest::testVisibleCardsExcludeArchivedAndDeleted()
{
    NotificationPreferences aPreferences;
    aPreferences.MaxVisible = 5;
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot(
        {
            makeRecord("inbox", NotificationFolder::Inbox, false, 10),
            makeRecord("archived", NotificationFolder::Archived, false, 20),
            makeRecord("deleted", NotificationFolder::Deleted, false, 30),
        },
        {}, aPreferences);

    const std::vector<NotificationDisplayRow> aRows
        = NotificationViewModel::VisibleCards(*xSnapshot, aPreferences);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aRows.size());
    CPPUNIT_ASSERT_EQUAL(OString("inbox"), aRows[0].Id);
    CPPUNIT_ASSERT_EQUAL(sal_uInt32(0),
                         NotificationViewModel::HiddenCardCount(*xSnapshot, aPreferences));
}

void NotificationViewModelTest::testRowsForViewFilterAndSort()
{
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot({
        makeRecord("a", NotificationFolder::Inbox, false, 10, NotificationSeverity::Warning, "b.src"),
        makeRecord("b", NotificationFolder::Inbox, false, 30, NotificationSeverity::Error, "a.src"),
        makeRecord("c", NotificationFolder::Inbox, false, 20, NotificationSeverity::Warning, "a.src"),
        makeRecord("d", NotificationFolder::Archived, false, 40, NotificationSeverity::Warning,
                   "a.src"),
    });

    // Inbox + newest-first, no filters: b(30), c(20), a(10); the archived record is excluded.
    const std::vector<NotificationDisplayRow> aNewest = NotificationViewModel::RowsForView(
        *xSnapshot, NotificationView::Inbox, std::nullopt, OString(),
        NotificationSortOrder::Newest);
    CPPUNIT_ASSERT_EQUAL(std::size_t(3), aNewest.size());
    CPPUNIT_ASSERT((rowIds(aNewest) == std::vector<OString>{ "b", "c", "a" }));

    // Oldest-first reverses the order.
    const std::vector<NotificationDisplayRow> aOldest = NotificationViewModel::RowsForView(
        *xSnapshot, NotificationView::Inbox, std::nullopt, OString(),
        NotificationSortOrder::Oldest);
    CPPUNIT_ASSERT((rowIds(aOldest) == std::vector<OString>{ "a", "c", "b" }));

    // Severity filter keeps only Warning rows.
    const std::vector<NotificationDisplayRow> aWarning = NotificationViewModel::RowsForView(
        *xSnapshot, NotificationView::Inbox, NotificationSeverity::Warning, OString(),
        NotificationSortOrder::Newest);
    CPPUNIT_ASSERT((rowIds(aWarning) == std::vector<OString>{ "c", "a" }));

    // Source filter keeps only the requested producer.
    const std::vector<NotificationDisplayRow> aSource = NotificationViewModel::RowsForView(
        *xSnapshot, NotificationView::Inbox, std::nullopt, OString("a.src"),
        NotificationSortOrder::Newest);
    CPPUNIT_ASSERT((rowIds(aSource) == std::vector<OString>{ "b", "c" }));
}

void NotificationViewModelTest::testSelectionVectorStableSnapshotOrder()
{
    // INV-6: the selection collapses to exactly one vector, built once in stable snapshot order,
    // silently dropping ids no longer present.
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot({
        makeRecord("a", NotificationFolder::Inbox, false, 10),
        makeRecord("b", NotificationFolder::Inbox, false, 20),
        makeRecord("c", NotificationFolder::Inbox, false, 30),
        makeRecord("d", NotificationFolder::Inbox, false, 40),
    });
    const std::set<OString> aSelection{ OString("d"), OString("b"), OString("vanished") };

    const std::vector<OString> aVector
        = NotificationViewModel::SelectionVector(aSelection, *xSnapshot);
    // Snapshot order (b before d), and the vanished id is dropped.
    CPPUNIT_ASSERT((aVector == std::vector<OString>{ "b", "d" }));
}

void NotificationViewModelTest::testReconcileSelectionDropsVanished()
{
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot({
        makeRecord("a", NotificationFolder::Inbox, false, 10),
        makeRecord("b", NotificationFolder::Inbox, false, 20),
    });
    const std::set<OString> aSelection{ OString("a"), OString("gone") };
    const std::set<OString> aReconciled
        = NotificationViewModel::ReconcileSelection(aSelection, *xSnapshot);
    CPPUNIT_ASSERT_EQUAL(std::size_t(1), aReconciled.size());
    CPPUNIT_ASSERT(aReconciled.count(OString("a")) == 1);
    CPPUNIT_ASSERT(aReconciled.count(OString("gone")) == 0);
}

void NotificationViewModelTest::testLatestUndoableCommitSkipsMaintenance()
{
    // Newest real user action wins; maintenance checkpoints and sentinels are not undoable.
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot(
        {},
        {
            makeHistory("c1", NotificationAction::Add, 100),
            makeHistory("c2", NotificationAction::Maintenance, 300),
            makeHistory("c3", NotificationAction::Delete, 200),
        });
    CPPUNIT_ASSERT_EQUAL(OString("c3"),
                         NotificationViewModel::LatestUndoableCommit(*xSnapshot));

    // Only a maintenance checkpoint present: nothing is undoable.
    NotificationCenterSnapshotRef xMaintenanceOnly = makeSnapshot(
        {}, { makeHistory("m1", NotificationAction::Maintenance, 500) });
    CPPUNIT_ASSERT(NotificationViewModel::LatestUndoableCommit(*xMaintenanceOnly).isEmpty());
}

void NotificationViewModelTest::testMakeRowRedaction()
{
    // INV-5: metadata-only records never render title/body text, regardless of what they carry.
    NotificationRecord aMetadata
        = makeRecord("meta", NotificationFolder::Inbox, false, 10);
    aMetadata.Privacy = NotificationPrivacy::MetadataOnly;
    aMetadata.Title = u"private title"_ustr;
    aMetadata.Body = u"private body"_ustr;
    const NotificationDisplayRow aMetaRow = NotificationViewModel::MakeRow(aMetadata);
    CPPUNIT_ASSERT(aMetaRow.Redacted);
    CPPUNIT_ASSERT(aMetaRow.DisplayBody.isEmpty());
    CPPUNIT_ASSERT_EQUAL(OString("meta"), aMetaRow.Id);

    // Audited safe-display text with a non-empty title renders verbatim.
    NotificationRecord aSafe = makeRecord("safe", NotificationFolder::Inbox, false, 10);
    aSafe.Privacy = NotificationPrivacy::SafeDisplayText;
    aSafe.Title = u"Hello"_ustr;
    aSafe.Body = u"World"_ustr;
    const NotificationDisplayRow aSafeRow = NotificationViewModel::MakeRow(aSafe);
    CPPUNIT_ASSERT(!aSafeRow.Redacted);
    CPPUNIT_ASSERT_EQUAL(u"Hello"_ustr, aSafeRow.DisplayTitle);
    CPPUNIT_ASSERT_EQUAL(u"World"_ustr, aSafeRow.DisplayBody);

    // Safe-display convention but an empty title still redacts.
    NotificationRecord aEmpty = makeRecord("empty", NotificationFolder::Inbox, false, 10);
    aEmpty.Privacy = NotificationPrivacy::SafeDisplayText;
    aEmpty.Title = OUString();
    const NotificationDisplayRow aEmptyRow = NotificationViewModel::MakeRow(aEmpty);
    CPPUNIT_ASSERT(aEmptyRow.Redacted);
    CPPUNIT_ASSERT(aEmptyRow.DisplayBody.isEmpty());
}

void NotificationViewModelTest::testDistinctSources()
{
    NotificationCenterSnapshotRef xSnapshot = makeSnapshot({
        makeRecord("a", NotificationFolder::Inbox, false, 10, NotificationSeverity::Information,
                   "b.src"),
        makeRecord("b", NotificationFolder::Inbox, false, 20, NotificationSeverity::Information,
                   "a.src"),
        makeRecord("c", NotificationFolder::Archived, false, 30, NotificationSeverity::Information,
                   "b.src"),
        makeRecord("d", NotificationFolder::Inbox, false, 40, NotificationSeverity::Information, ""),
    });
    const std::vector<OString> aSources = NotificationViewModel::DistinctSources(*xSnapshot);
    // Sorted, de-duplicated, empty source excluded.
    CPPUNIT_ASSERT((aSources == std::vector<OString>{ "a.src", "b.src" }));

    // Non-core slugs are surfaced verbatim as their own label (no localization of raw slugs).
    CPPUNIT_ASSERT_EQUAL(u"custom.source"_ustr,
                         NotificationViewModel::SourceLabel(OString("custom.source")));
}

CPPUNIT_TEST_SUITE_REGISTRATION(NotificationViewModelTest);

} // namespace

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
