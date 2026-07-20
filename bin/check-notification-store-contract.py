#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Fail-closed source contract for the local notification history foundation.

This validator proves source structure and safety invariants. It complements,
but does not replace, compilation and the focused CppUnit runtime test.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MarkerRule:
    rule_id: str
    path: str
    marker: str
    rationale: str


REQUIRED_FILES = (
    "include/sfx2/notificationcenter.hxx",
    "sfx2/source/notification/NotificationJson.hxx",
    "sfx2/source/notification/NotificationJson.cxx",
    "sfx2/source/notification/LocalGitRepository.hxx",
    "sfx2/source/notification/LocalGitRepository.cxx",
    "sfx2/source/notification/NotificationCenterService.cxx",
    "sfx2/source/notification/NotificationConfiguration.hxx",
    "sfx2/source/notification/NotificationConfiguration.cxx",
    "sfx2/source/notification/NotificationStore.cxx",
    "sfx2/qa/cppunit/notificationcenterservice.cxx",
    "sfx2/qa/cppunit/notificationstore.cxx",
    "sfx2/CppunitTest_sfx2_notificationstore.mk",
    "sfx2/Library_sfx.mk",
    "sfx2/source/appl/app.cxx",
    "sfx2/source/appl/appdata.cxx",
    "sfx2/source/inc/appdata.hxx",
    "officecfg/registry/schema/org/openoffice/Office/UI/NotificationCenter.xcs",
)


REQUIRED_MARKERS = (
    MarkerRule(
        "folder-model",
        "include/sfx2/notificationcenter.hxx",
        "enum class NotificationFolder",
        "folders are an explicit persisted state",
    ),
    MarkerRule(
        "inbox-folder",
        "include/sfx2/notificationcenter.hxx",
        "Inbox,",
        "Inbox remains a first-class folder",
    ),
    MarkerRule(
        "unread-view",
        "include/sfx2/notificationcenter.hxx",
        "Unread,",
        "Unread remains an orthogonal view",
    ),
    MarkerRule(
        "archived-folder",
        "include/sfx2/notificationcenter.hxx",
        "Archived,",
        "Archived remains a first-class folder",
    ),
    MarkerRule(
        "deleted-folder",
        "include/sfx2/notificationcenter.hxx",
        "Deleted",
        "Deleted remains a recoverable tombstone folder",
    ),
    MarkerRule(
        "previous-folder",
        "include/sfx2/notificationcenter.hxx",
        "NotificationFolder PreviousFolder",
        "tombstones retain their restore destination",
    ),
    MarkerRule(
        "metadata-default",
        "include/sfx2/notificationcenter.hxx",
        "NotificationPrivacy Privacy = NotificationPrivacy::MetadataOnly;",
        "privacy defaults to metadata-only",
    ),
    MarkerRule(
        "bulk-read-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult markRead(",
        "bulk read and unread state is public",
    ),
    MarkerRule(
        "bulk-delete-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult remove(",
        "bulk deletion is public",
    ),
    MarkerRule(
        "restore-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult restore(",
        "deleted records remain recoverable",
    ),
    MarkerRule(
        "inverse-undo-api",
        "include/sfx2/notificationcenter.hxx",
        "Apply an inverse of a retained action commit as a new child",
        "undo is inverse-only within the retained history window",
    ),
    MarkerRule(
        "profile-location",
        "sfx2/source/notification/NotificationStore.cxx",
        "utl::Bootstrap::locateUserData(aUserData)",
        "history lives beneath the LibreOffice profile",
    ),
    MarkerRule(
        "fixed-profile-repository",
        "sfx2/source/notification/NotificationStore.cxx",
        'aURL.Append(u"notification-history.git"',
        "production history uses one fixed local directory",
    ),
    MarkerRule(
        "sha1-object-ids",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "comphelper::HashType::SHA1",
        "loose objects use genuine Git SHA-1 identifiers",
    ),
    MarkerRule(
        "zlib-writer",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "compress2(",
        "loose Git objects use zlib compression",
    ),
    MarkerRule(
        "zlib-reader",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "inflate(&aState.Stream",
        "loose Git objects are read with bounded streaming zlib inflation",
    ),
    MarkerRule(
        "fixed-main-head",
        "sfx2/source/notification/LocalGitRepository.cxx",
        '"ref: refs/heads/main\\n"',
        "history has one fixed main branch",
    ),
    MarkerRule(
        "bare-config",
        "sfx2/source/notification/LocalGitRepository.cxx",
        '"\\tbare = true\\n"',
        "the local history is a genuine bare repository",
    ),
    MarkerRule(
        "disable-auto-gc",
        "sfx2/source/notification/LocalGitRepository.cxx",
        '"\\tauto = 0\\n"',
        "automatic packing stays disabled",
    ),
    MarkerRule(
        "loose-blob",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'objectId("blob", rJson)',
        "a snapshot is stored as a Git blob",
    ),
    MarkerRule(
        "loose-tree",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'objectId("tree", aTreeBody)',
        "a genuine Git tree points to the snapshot",
    ),
    MarkerRule(
        "loose-commit",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'objectId("commit", aCommitBody)',
        "a genuine Git commit records each mutation",
    ),
    MarkerRule(
        "exclusive-ref-lock",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'u"main.lock"',
        "the main ref uses an exclusive lock file",
    ),
    MarkerRule(
        "ref-cas",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "readHead(rRepositoryURL) != rExpected",
        "ref updates compare against the expected head",
    ),
    MarkerRule(
        "atomic-ref-replace",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "osl::File::replace(aLock, aRef)",
        "an existing ref is atomically replaced",
    ),
    MarkerRule(
        "reject-hooks",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'pathURL(rRepositoryURL, { u"hooks" })',
        "repositories with hooks fail closed",
    ),
    MarkerRule(
        "reject-packs",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'pathURL(rRepositoryURL, { u"objects", u"pack" })',
        "packfiles are deliberately unsupported",
    ),
    MarkerRule(
        "reject-alternates",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'pathURL(rRepositoryURL, { u"objects", u"info", u"alternates" })',
        "object alternates cannot escape the repository",
    ),
    MarkerRule(
        "metadata-redaction",
        "sfx2/source/notification/NotificationJson.cxx",
        "metadata-only notification contains display text",
        "metadata-only records reject persisted display text",
    ),
    MarkerRule(
        "safe-text-guard",
        "sfx2/source/notification/NotificationJson.cxx",
        "notification display text failed the privacy guard",
        "explicit safe text is still screened for paths and secrets",
    ),
    MarkerRule(
        "tombstone-transition",
        "sfx2/source/notification/NotificationStore.cxx",
        "rRecord.PreviousFolder = rRecord.Folder;",
        "deletion records its recovery folder",
    ),
    MarkerRule(
        "restore-transition",
        "sfx2/source/notification/NotificationStore.cxx",
        "rRecord.Folder = rRecord.PreviousFolder;",
        "restore recovers the prior folder",
    ),
    MarkerRule(
        "undo-ancestry",
        "sfx2/source/notification/NotificationStore.cxx",
        "Repository->readUndoTarget(rCommitId, m_pImpl->Head)",
        "undo validates ancestry and captures its target under one prune-excluding lock",
    ),
    MarkerRule(
        "undo-conflict",
        "sfx2/source/notification/NotificationStore.cxx",
        "sameRecord(m_pImpl->Records, aTarget, rId)",
        "undo refuses to overwrite subsequently changed records",
    ),
    MarkerRule(
        "bulk-copy-before-commit",
        "sfx2/source/notification/NotificationStore.cxx",
        "RecordMap aNext = Records;",
        "bulk mutations operate on an isolated copy",
    ),
    MarkerRule(
        "configuration-registration",
        "officecfg/files.mk",
        "Office/UI/NotificationCenter",
        "the NotificationCenter schema is generated",
    ),
    MarkerRule(
        "configuration-display-group",
        "officecfg/registry/schema/org/openoffice/Office/UI/NotificationCenter.xcs",
        '<group oor:name="Display">',
        "notification form preferences are configurable",
    ),
    MarkerRule(
        "configuration-history-group",
        "officecfg/registry/schema/org/openoffice/Office/UI/NotificationCenter.xcs",
        '<group oor:name="History">',
        "history retention preferences are configurable",
    ),
    MarkerRule(
        "focused-test-target",
        "sfx2/CppunitTest_sfx2_notificationstore.mk",
        "gb_CppunitTest_CppunitTest,sfx2_notificationstore",
        "the foundation has a focused CppUnit target",
    ),
    MarkerRule(
        "test-zlib-dependency",
        "sfx2/CppunitTest_sfx2_notificationstore.mk",
        "\tzlib \\",
        "privacy tests can inspect compressed loose objects",
    ),
    MarkerRule(
        "runtime-reload-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testBareRepositoryAndReload",
        "bare repository reload is covered",
    ),
    MarkerRule(
        "runtime-tombstone-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testBulkFoldersAndRecoverableTombstones",
        "bulk tombstone recovery is covered",
    ),
    MarkerRule(
        "runtime-undo-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testUndoCreatesNewCommitAndDetectsConflict",
        "inverse-commit undo is covered",
    ),
    MarkerRule(
        "runtime-privacy-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "inflatedObjectsContain",
        "privacy is checked in decompressed loose objects",
    ),
    MarkerRule(
        "runtime-cas-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testCompareAndSwapRejectsLostUpdate",
        "concurrent ref changes are covered",
    ),
    MarkerRule(
        "created-commit-signal",
        "include/sfx2/notificationcenter.hxx",
        "bool CreatedCommit = false;",
        "callers can distinguish an undoable mutation from a no-op",
    ),
    MarkerRule(
        "history-action-model",
        "include/sfx2/notificationcenter.hxx",
        "enum class NotificationAction",
        "history exposes typed actions",
    ),
    MarkerRule(
        "public-refresh",
        "include/sfx2/notificationcenter.hxx",
        "bool refresh();",
        "multiple store instances can observe the current ref",
    ),
    MarkerRule(
        "pin-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult setPinned(",
        "the bulk manager can pin and unpin records",
    ),
    MarkerRule(
        "maintenance-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult maintain();",
        "retention and count limits have a public maintenance operation",
    ),
    MarkerRule(
        "empty-trash-api",
        "include/sfx2/notificationcenter.hxx",
        "NotificationMutationResult emptyTrash();",
        "the full manager can explicitly empty tombstones",
    ),
    MarkerRule(
        "worker-thread-contract",
        "include/sfx2/notificationcenter.hxx",
        "These calls must not run",
        "synchronous zlib and fsync work is kept off the UI thread",
    ),
    MarkerRule(
        "no-op-result",
        "sfx2/source/notification/NotificationStore.cxx",
        "noCommitSuccess(NotificationAction eAction)",
        "no-op bulk actions never expose an unrelated head as undoable",
    ),
    MarkerRule(
        "fresh-query",
        "sfx2/source/notification/NotificationStore.cxx",
        "(void)m_pImpl->observe();",
        "read APIs refresh the external main ref",
    ),
    MarkerRule(
        "positive-tombstone-time",
        "sfx2/source/notification/NotificationStore.cxx",
        "std::max<sal_Int64>({ 1, rRecord.CreatedAt, nNow })",
        "epoch-zero clocks still create valid tombstones",
    ),
    MarkerRule(
        "retention-pruning",
        "sfx2/source/notification/NotificationStore.cxx",
        "purgeExpiredRecords(",
        "expired tombstones can leave the current snapshot",
    ),
    MarkerRule(
        "record-limit-pruning",
        "sfx2/source/notification/NotificationStore.cxx",
        "enforceRecordLimits(",
        "adds prune eligible records instead of permanently bricking at the hard limit",
    ),
    MarkerRule(
        "snapshot-byte-bound",
        "sfx2/source/notification/NotificationStore.cxx",
        "SnapshotSafetyBudget",
        "current full snapshots have a byte budget in addition to a record count",
    ),
    MarkerRule(
        "audited-safe-producers",
        "sfx2/source/notification/NotificationJson.cxx",
        "isApprovedSafeDisplaySource",
        "built-in source conventions add defense in depth for display text",
    ),
    MarkerRule(
        "safe-source-not-authentication",
        "include/sfx2/notificationcenter.hxx",
        "allowlist is defense in depth rather than an",
        "the public Source string is not misrepresented as caller authentication",
    ),
    MarkerRule(
        "control-temp-install",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "cannot install notification repository control file",
        "HEAD and config initialization use a creator-loser-safe install",
    ),
    MarkerRule(
        "control-empty-recovery",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "An empty file is the only recoverable result",
        "crash-empty control files are repaired without accepting arbitrary contents",
    ),
    MarkerRule(
        "stale-lock-recovery",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "recoverMainLock(m_aRepositoryURL);",
        "an abandoned ref lock cannot permanently disable history",
    ),
    MarkerRule(
        "lock-fast-forward-validation",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "aPending.CheckpointFrom == aCurrent",
        "pending parentless checkpoints bind recovery to the prior main ref",
    ),
    MarkerRule(
        "permanent-operation-guard",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'u"notification.guard"',
        "all readers and writers lock one permanent validated control file",
    ),
    MarkerRule(
        "process-operation-mutex",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "std::unique_lock<std::mutex> ProcessLock",
        "same-process repositories serialize despite process-scoped Unix record locks",
    ),
    MarkerRule(
        "bounded-lock-quarantine",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "MaxQuarantinedLocks",
        "app-owned stale lock evidence cannot grow without bound",
    ),
    MarkerRule(
        "compaction-pending-gate",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'u"compaction.pending"',
        "a failed prune remains a durable gate on later writes",
    ),
    MarkerRule(
        "pending-compaction-reuse",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "readReusablePendingCheckpoint",
        "a retry reuses an already-installed checkpoint instead of amplifying failures",
    ),
    MarkerRule(
        "checkpoint-header",
        "sfx2/source/notification/LocalGitRepository.cxx",
        '"checkpoint-from "',
        "parentless compaction records the exact ref it replaces",
    ),
    MarkerRule(
        "pre-mutation-compaction",
        "sfx2/source/notification/NotificationStore.cxx",
        "Compact the retained pre-mutation state first.",
        "the returned action commit remains exactly undoable across a threshold",
    ),
    MarkerRule(
        "checkpoint-undo-boundary",
        "sfx2/source/notification/NotificationStore.cxx",
        "selected commit is a compaction checkpoint",
        "undo cannot interpret a checkpoint as an empty parent snapshot",
    ),
    MarkerRule(
        "stable-history-read",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "std::vector<GitSnapshot> LocalGitRepository::readHistory",
        "history traversal excludes concurrent pruning for the whole slice",
    ),
    MarkerRule(
        "metadata-history-traversal",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "readCommitMetadataUnlocked",
        "history and depth checks do not load every full snapshot blob",
    ),
    MarkerRule(
        "streaming-object-inflate",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "inflateInit(&Stream)",
        "loose objects are streamed until their declared type and size are known",
    ),
    MarkerRule(
        "type-specific-object-bounds",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "MaxCommitBodyBytes",
        "commit and tree objects cannot allocate the full snapshot budget",
    ),
    MarkerRule(
        "runtime-noop-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testNoOpHasNoUndoCommit",
        "no-op actions cannot undo an unrelated commit",
    ),
    MarkerRule(
        "runtime-freshness-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testCrossStoreReadsRefresh",
        "cross-store ref freshness is covered",
    ),
    MarkerRule(
        "runtime-init-lock-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testConcurrentInitializationAndStaleLockRecovery",
        "initialization races and abandoned locks are covered",
    ),
    MarkerRule(
        "runtime-permanent-guard-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testPermanentGuardContention",
        "the permanent guard contents and Windows contention path are covered",
    ),
    MarkerRule(
        "runtime-retention-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testRetentionLimitAndEpochZero",
        "retention, snapshot bounds, and epoch zero are covered",
    ),
    MarkerRule(
        "runtime-compaction-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "testCompactionBoundsHistoryUndoAndPendingRecovery",
        "more than 128 commits exercise pruning, exact undo and parentless-lock recovery",
    ),
    MarkerRule(
        "runtime-pending-retry-test",
        "sfx2/qa/cppunit/notificationstore.cxx",
        "nObjectsAfterFirstFailure",
        "repeated forced prune failures cannot advance the ref or add objects",
    ),
    MarkerRule(
        "immutable-service-snapshot",
        "include/sfx2/notificationcenter.hxx",
        "const std::vector<NotificationRecord> Records;",
        "UI consumers receive immutable record snapshots",
    ),
    MarkerRule(
        "const-service-snapshot-generation",
        "include/sfx2/notificationcenter.hxx",
        "const sal_uInt64 Generation;",
        "snapshot identity cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-health",
        "include/sfx2/notificationcenter.hxx",
        "const NotificationStoreHealth Health;",
        "snapshot health cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-error",
        "include/sfx2/notificationcenter.hxx",
        "const OUString Error;",
        "snapshot failure state cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-head",
        "include/sfx2/notificationcenter.hxx",
        "const OString HeadCommitId;",
        "snapshot repository identity cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-preferences",
        "include/sfx2/notificationcenter.hxx",
        "const NotificationPreferences Preferences;",
        "snapshot preferences cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-history",
        "include/sfx2/notificationcenter.hxx",
        "const std::vector<NotificationHistoryEntry> History;",
        "snapshot history cannot be mutated by consumers",
    ),
    MarkerRule(
        "const-service-snapshot-reference",
        "include/sfx2/notificationcenter.hxx",
        "std::shared_ptr<const NotificationCenterSnapshot>",
        "service consumers cannot obtain a mutable snapshot pointer",
    ),
    MarkerRule(
        "asynchronous-service-facade",
        "include/sfx2/notificationcenter.hxx",
        "class SFX2_DLLPUBLIC NotificationCenterService final",
        "the synchronous store is hidden behind one asynchronous facade",
    ),
    MarkerRule(
        "worker-owned-store-construction",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "pStore = std::make_unique<NotificationStore>",
        "the notification store is constructed on its worker",
    ),
    MarkerRule(
        "worker-owned-store-destruction",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "pStore.reset();",
        "the notification store is destroyed on its worker",
    ),
    MarkerRule(
        "serialized-service-queue",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "std::deque<Request> m_aRequests;",
        "notification requests are serialized through one queue",
    ),
    MarkerRule(
        "vcl-completion-dispatch",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "Application::PostUserEvent(LINK(this, UiCompletionQueue, handleEvent))",
        "profile completions return through the VCL event queue",
    ),
    MarkerRule(
        "vcl-event-self-lease",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "m_xEventKeepAlive = shared_from_this();",
        "a pending raw VCL Link retains its queue owner",
    ),
    MarkerRule(
        "vcl-handler-local-lease",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "auto xKeepAlive = shared_from_this();",
        "a completion may destroy the service without destroying its active handler",
    ),
    MarkerRule(
        "vcl-off-main-cancellation-deferral",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "const bool bCanCancelEvent = Application::IsMainThread();",
        "off-main shutdown must not race RemoveUserEvent against VCL dispatch",
    ),
    MarkerRule(
        "off-worker-completion-guard",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "Completion dispatcher ran on the store worker; ",
        "an inline completion cannot self-join the store worker",
    ),
    MarkerRule(
        "worker-identity-activation",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "g_pNotificationWorkerIdentity = m_xWorkerIdentity.get();",
        "inline dispatch detection is active for the full store-worker lifetime",
    ),
    MarkerRule(
        "repository-dispatcher-required",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "notification completion dispatcher must queue work off the store worker without ",
        "the injectable factory has no implicit inline completion path",
    ),
    MarkerRule(
        "conflict-snapshot-refresh",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "if (aResult.Mutation.Conflict)\n            (void)rStore.refresh();",
        "conflict results include the winning repository state",
    ),
    MarkerRule(
        "one-store-call-per-bulk-delete",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "aResult.Mutation = rStore.remove(aRequest.Ids);",
        "one bulk delete request maps to one atomic store mutation",
    ),
    MarkerRule(
        "generated-configuration-read",
        "sfx2/source/notification/NotificationConfiguration.cxx",
        "officecfg::Office::UI::NotificationCenter::Display::Enabled::get()",
        "profile preferences use generated office configuration accessors",
    ),
    MarkerRule(
        "generated-configuration-write",
        "sfx2/source/notification/NotificationConfiguration.cxx",
        "officecfg::Office::UI::NotificationCenter::History::Limit::set",
        "customized profile preferences are persisted through generated accessors",
    ),
    MarkerRule(
        "lazy-application-service",
        "sfx2/source/appl/app.cxx",
        "pImpl->mxNotificationCenter = sfx2::NotificationCenterService::createForProfile();",
        "the service starts only when first requested by the application",
    ),
    MarkerRule(
        "application-service-shutdown",
        "sfx2/source/appl/app.cxx",
        "pImpl->mxNotificationCenter.reset();",
        "the application joins the worker while VCL is still alive",
    ),
    MarkerRule(
        "application-service-complete-type",
        "sfx2/source/appl/appdata.cxx",
        "#include <sfx2/notificationcenter.hxx>",
        "application data destroys the lazy service with its complete type available",
    ),
    MarkerRule(
        "service-library-wiring",
        "sfx2/Library_sfx.mk",
        "sfx2/source/notification/NotificationCenterService \\",
        "the asynchronous service is compiled into the sfx library",
    ),
    MarkerRule(
        "configuration-library-wiring",
        "sfx2/Library_sfx.mk",
        "sfx2/source/notification/NotificationConfiguration \\",
        "the generated configuration adapter is compiled into the sfx library",
    ),
    MarkerRule(
        "service-cppunit-wiring",
        "sfx2/CppunitTest_sfx2_notificationstore.mk",
        "sfx2/qa/cppunit/notificationcenterservice \\",
        "the native service cases are part of the focused notification target",
    ),
    MarkerRule(
        "runtime-service-ordering-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testSerializedOrderingAndImmutableSnapshots",
        "serialized completion ordering and snapshot generations are covered",
    ),
    MarkerRule(
        "runtime-service-shutdown-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testShutdownDrainsAcceptedMutations",
        "shutdown durability is covered",
    ),
    MarkerRule(
        "runtime-service-concurrent-shutdown-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testConcurrentAdmissionAndShutdownLinearize",
        "producer admission racing shutdown is covered",
    ),
    MarkerRule(
        "runtime-service-reentrant-destruction-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testCompletionCanDestroyService",
        "an off-worker completion can destroy the service while the worker exits",
    ),
    MarkerRule(
        "runtime-service-dispatcher-contract-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testRepositoryFactoryRequiresAsyncDispatcher",
        "the injectable factory rejects its former inline default path",
    ),
    MarkerRule(
        "runtime-service-conflict-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testConflictRefreshesReturnedSnapshot",
        "service conflict recovery is covered",
    ),
    MarkerRule(
        "runtime-service-bulk-commit-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testBulkOperationCreatesOneActionCommitBelowCompaction",
        "below-threshold bulk manager requests are proven to add one action commit",
    ),
    MarkerRule(
        "runtime-service-privacy-test",
        "sfx2/qa/cppunit/notificationcenterservice.cxx",
        "testMetadataOnlyTextRemainsRedacted",
        "the service cannot re-expose metadata-only display text",
    ),
)


FORBIDDEN_MARKERS = (
    MarkerRule(
        "worker-reference-cleared-during-shutdown",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "m_xWorker.clear();",
        "shutdown must leave a stable joined worker reference for concurrent admission rejection",
    ),
    MarkerRule(
        "inline-repository-completion-default",
        "sfx2/source/notification/NotificationCenterService.cxx",
        "m_aDispatcher = [](std::function<void()> aCompletion) { aCompletion(); };",
        "repository completions must never default to the store worker",
    ),
    MarkerRule(
        "git-executable",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "git.exe",
        "runtime history cannot depend on an installed Git executable",
    ),
    MarkerRule(
        "process-execution",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "osl_executeProcess",
        "the history reader never executes a process",
    ),
    MarkerRule(
        "shell-execution",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "ShellExecute",
        "the history reader never invokes a shell",
    ),
    MarkerRule(
        "create-process",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "CreateProcess",
        "the history reader never starts a child process",
    ),
    MarkerRule(
        "libgit-runtime",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "git_repository_",
        "the small local writer does not acquire a hidden libgit dependency",
    ),
    MarkerRule(
        "remote-config",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "[remote ",
        "local history has no remote",
    ),
    MarkerRule(
        "network-url",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "https://",
        "local history has no network endpoint",
    ),
    MarkerRule(
        "serialized-callback",
        "include/sfx2/notificationcenter.hxx",
        "Callback",
        "historical records cannot serialize executable callbacks",
    ),
    MarkerRule(
        "serialized-command",
        "include/sfx2/notificationcenter.hxx",
        "CommandURL",
        "historical records cannot serialize UNO commands",
    ),
    MarkerRule(
        "serialized-document-url",
        "include/sfx2/notificationcenter.hxx",
        "DocumentURL",
        "historical records cannot serialize document locations",
    ),
    MarkerRule(
        "noop-head-as-commit",
        "sfx2/source/notification/NotificationStore.cxx",
        "aResult.CommitId = Head;",
        "no-op actions must not expose the previous head as their commit",
    ),
    MarkerRule(
        "post-mutation-checkpoint-result",
        "sfx2/source/notification/NotificationStore.cxx",
        "aResult.CommitId = aCheckpoint;",
        "mutation results must identify the actual action commit, not a checkpoint",
    ),
    MarkerRule(
        "removable-pid-operation-lock",
        "sfx2/source/notification/LocalGitRepository.cxx",
        'u"notification-operation.lock"',
        "PID lock takeover cannot safely compare-and-rename a replacement lock",
    ),
    MarkerRule(
        "operation-lock-bypass",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "osl_File_OpenFlag_NoLock",
        "the permanent repository guard must use OSL locking semantics",
    ),
    MarkerRule(
        "fixed-max-object-inflate",
        "sfx2/source/notification/LocalGitRepository.cxx",
        "MaxInflatedObjectBytes",
        "small commit and tree objects must not allocate the full snapshot maximum",
    ),
)


JSON_PROPERTY_ORDER = (
    'aWriter.put("id"',
    'aWriter.put("source"',
    'aWriter.put("severity"',
    'aWriter.put("folder"',
    'aWriter.put("previousFolder"',
    'aWriter.put("privacy"',
    'aWriter.put("read"',
    'aWriter.put("pinned"',
    'aWriter.put("createdAt"',
    'aWriter.put("updatedAt"',
    'aWriter.put("deletedAt"',
    'aWriter.put("title"',
    'aWriter.put("body"',
    'aWriter.put("dedupeHash"',
)

CONFIGURATION_FIELDS = (
    ("Display", "Enabled"),
    ("Display", "MaxVisible"),
    ("Display", "Width"),
    ("Display", "TimeoutSeconds"),
    ("Display", "HorizontalInset"),
    ("Display", "VerticalInset"),
    ("Display", "CornerRadius"),
    ("Display", "OpacityPercent"),
    ("Display", "UseThemeColors"),
    ("Display", "AccentColor"),
    ("Display", "Animations"),
    ("History", "RetentionDays"),
    ("History", "Limit"),
)


def load_snapshot(root: Path) -> tuple[dict[str, str], set[str]]:
    paths = set(REQUIRED_FILES)
    paths.update(rule.path for rule in REQUIRED_MARKERS)
    paths.update(rule.path for rule in FORBIDDEN_MARKERS)
    contents: dict[str, str] = {}
    present: set[str] = set()
    for relative in sorted(paths):
        path = root / relative
        if not path.is_file():
            continue
        present.add(relative)
        contents[relative] = path.read_text(encoding="utf-8")
    return contents, present


def _extract_braced_block(source: str, marker: str) -> str:
    start = source.find(marker)
    if start < 0:
        return ""
    brace = source.find("{", start + len(marker))
    if brace < 0:
        return ""
    depth = 0
    for position in range(brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[start : position + 1]
    return ""


def find_violations(
    contents: Mapping[str, str], present: set[str]
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path in REQUIRED_FILES:
        if path not in present:
            violations.append(
                {
                    "rule": "required-file",
                    "path": path,
                    "detail": "required notification-store source is missing",
                }
            )

    for rule in REQUIRED_MARKERS:
        if rule.marker not in contents.get(rule.path, ""):
            violations.append(
                {
                    "rule": rule.rule_id,
                    "path": rule.path,
                    "detail": f"missing {rule.marker!r}: {rule.rationale}",
                }
            )
    for rule in FORBIDDEN_MARKERS:
        if rule.marker in contents.get(rule.path, ""):
            violations.append(
                {
                    "rule": rule.rule_id,
                    "path": rule.path,
                    "detail": f"forbidden {rule.marker!r}: {rule.rationale}",
                }
            )

    json_source = contents.get(
        "sfx2/source/notification/NotificationJson.cxx", ""
    )
    serializer = _extract_braced_block(json_source, "std::string serializeRecords(")
    positions = [serializer.find(marker) for marker in JSON_PROPERTY_ORDER]
    if not serializer or any(position < 0 for position in positions) or positions != sorted(
        positions
    ):
        violations.append(
            {
                "rule": "deterministic-json-order",
                "path": "sfx2/source/notification/NotificationJson.cxx",
                "detail": "persisted JSON properties must retain their deterministic order",
            }
        )

    store_source = contents.get(
        "sfx2/source/notification/NotificationStore.cxx", ""
    )
    safe_text = _extract_braced_block(
        store_source,
        "if (rDraft.Privacy == NotificationPrivacy::SafeDisplayText)",
    )
    if (
        "aRecord.Title = rDraft.Title;" not in safe_text
        or "aRecord.Body = rDraft.Body;" not in safe_text
        or store_source.count("aRecord.Title = rDraft.Title;") != 1
        or store_source.count("aRecord.Body = rDraft.Body;") != 1
    ):
        violations.append(
            {
                "rule": "metadata-text-isolation",
                "path": "sfx2/source/notification/NotificationStore.cxx",
                "detail": "display text may only enter persisted records in the SafeDisplayText branch",
            }
        )

    service_source = contents.get(
        "sfx2/source/notification/NotificationCenterService.cxx", ""
    )
    completion_queue = _extract_braced_block(
        service_source, "class UiCompletionQueue final"
    )
    completion_post = _extract_braced_block(completion_queue, "void post(")
    retain_event_owner = completion_post.find(
        "m_xEventKeepAlive = shared_from_this();"
    )
    post_event = completion_post.find("Application::PostUserEvent(")
    completion_handler = _extract_braced_block(
        service_source, "IMPL_LINK_NOARG(UiCompletionQueue, handleEvent"
    )
    retain_handler_owner = completion_handler.find(
        "auto xKeepAlive = shared_from_this();"
    )
    release_event_owner = completion_handler.find("m_xEventKeepAlive.reset();")
    first_callback = completion_handler.find("rCompletion();")
    completion_shutdown = _extract_braced_block(completion_queue, "void shutdown()")
    check_cancel_affinity = completion_shutdown.find("Application::IsMainThread()")
    defer_off_main = completion_shutdown.find("if (!bCanCancelEvent)")
    detach_event = completion_shutdown.find("std::exchange(m_pEvent, nullptr)")
    move_event_owner = completion_shutdown.find(
        "std::move(m_xEventKeepAlive)"
    )
    cancel_event = completion_shutdown.find("Application::RemoveUserEvent(pEvent)")
    completion_finish = _extract_braced_block(
        completion_queue, "void finishShutdown()"
    )
    finish_on_main = completion_finish.find("Application::IsMainThread()")
    dispose_after_drain = completion_finish.find(
        "aCancelled.swap(m_aCompletions);"
    )
    if (
        min(
            retain_event_owner,
            post_event,
            retain_handler_owner,
            release_event_owner,
            first_callback,
            check_cancel_affinity,
            defer_off_main,
            detach_event,
            move_event_owner,
            cancel_event,
            finish_on_main,
            dispose_after_drain,
        )
        < 0
        or not retain_event_owner < post_event
        or not retain_handler_owner < release_event_owner < first_callback
        or not check_cancel_affinity < defer_off_main < detach_event
        or not detach_event < move_event_owner < cancel_event
        or not finish_on_main < dispose_after_drain
        or "m_aCompletions.clear()" in completion_post
        or "m_aCompletions.clear()" in completion_shutdown
        or "swap(m_aCompletions)" in completion_shutdown
    ):
        violations.append(
            {
                "rule": "vcl-completion-cancellation-ownership",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "the raw VCL event must retain its queue through dispatch or cancellation, including reentrant service destruction",
            }
        )

    worker = _extract_braced_block(service_source, "class NotificationWorker final")
    start_worker = _extract_braced_block(worker, "void start()")
    launch_worker = start_worker.find("launch();")
    record_launch = start_worker.find("m_bLaunched = true;")
    worker_destructor = worker.find(
        "~NotificationWorker() override { assert(!m_bLaunched || m_bJoined); }"
    )
    execute = _extract_braced_block(worker, "void execute() override")
    activate_worker_identity = execute.find(
        "g_pNotificationWorkerIdentity = m_xWorkerIdentity.get();"
    )
    construct = execute.find("std::make_unique<NotificationStore>(")
    process = execute.find("process(*pStore, std::move(aRequest))")
    destroy = execute.find("pStore.reset();")
    deactivate_worker_identity = execute.rfind(
        "g_pNotificationWorkerIdentity = nullptr;"
    )
    if (
        min(
            activate_worker_identity,
            construct,
            process,
            destroy,
            deactivate_worker_identity,
        )
        < 0
        or not activate_worker_identity
        < construct
        < process
        < destroy
        < deactivate_worker_identity
    ):
        violations.append(
            {
                "rule": "worker-store-lifetime-order",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "the store must be constructed, processed, and destroyed inside the worker",
            }
        )
    if (
        "public salhelper::Thread" not in worker
        or min(worker_destructor, launch_worker, record_launch) < 0
        or not launch_worker < record_launch
    ):
        violations.append(
            {
                "rule": "salhelper-worker-lifecycle-shape",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "the worker must use the salhelper execute signature and record launch only after launch succeeds",
            }
        )

    service_process = _extract_braced_block(
        worker, "void process(NotificationStore& rStore, Request aRequest)"
    )
    capture_worker_id = service_process.find(
        "auto xWorkerIdentity = m_xWorkerIdentity;"
    )
    dispatch_completion = service_process.find("m_aDispatcher(")
    reject_inline = service_process.find(
        "g_pNotificationWorkerIdentity == xWorkerIdentity.get()"
    )
    invoke_completion = service_process.find("aCompletion(std::move(aResult));")
    if (
        min(
            capture_worker_id,
            dispatch_completion,
            reject_inline,
            invoke_completion,
        )
        < 0
        or not capture_worker_id
        < dispatch_completion
        < reject_inline
        < invoke_completion
    ):
        violations.append(
            {
                "rule": "off-worker-completion-dispatch",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "the dispatcher must suppress callbacks that remain on the store worker",
            }
        )
    bulk_calls = (
        "rStore.markRead(aRequest.Ids, aRequest.Flag)",
        "rStore.setPinned(aRequest.Ids, aRequest.Flag)",
        "rStore.archive(aRequest.Ids)",
        "rStore.remove(aRequest.Ids)",
        "rStore.restore(aRequest.Ids)",
    )
    if any(service_process.count(call) != 1 for call in bulk_calls):
        violations.append(
            {
                "rule": "one-store-call-per-bulk-request",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "each service bulk branch must invoke its atomic store method exactly once",
            }
        )

    worker_stop = _extract_braced_block(worker, "void stopAccepting()")
    worker_shutdown = _extract_braced_block(worker, "void shutdown()")
    stop_admission = worker_stop.find("m_bAccepting = false")
    drain_signal = worker_stop.find("m_bStopWhenDrained = true")
    request_stop = worker_shutdown.find("stopAccepting();")
    join = worker_shutdown.find("join();")
    record_join = worker_shutdown.find("m_bJoined = true;")
    if (
        min(stop_admission, drain_signal, request_stop, join, record_join) < 0
        or not stop_admission < drain_signal
        or not request_stop < join < record_join
    ):
        violations.append(
            {
                "rule": "service-shutdown-drain-order",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "shutdown must stop admission, request queue drain, then join",
            }
        )

    service_impl = _extract_braced_block(
        service_source, "struct NotificationCenterService::Impl"
    )
    service_enqueue = _extract_braced_block(service_impl, "sal_uInt64 enqueue(")
    service_shutdown = _extract_braced_block(service_impl, "void shutdown()")
    close_admission = service_shutdown.find("m_xWorker->stopAccepting();")
    close_delivery = service_shutdown.find("m_xUiCompletions->shutdown();")
    drain_worker = service_shutdown.find("m_xWorker->shutdown();")
    finish_delivery = service_shutdown.find("m_xUiCompletions->finishShutdown();")
    if (
        "return m_xWorker->enqueue(std::move(aRequest));" not in service_enqueue
        or min(close_admission, close_delivery, drain_worker, finish_delivery) < 0
        or not close_admission < close_delivery < drain_worker < finish_delivery
        or "m_xWorker.clear()" in service_shutdown
        or "m_xWorker.reset()" in service_shutdown
    ):
        violations.append(
            {
                "rule": "stable-worker-reference-through-shutdown",
                "path": "sfx2/source/notification/NotificationCenterService.cxx",
                "detail": "shutdown and concurrent admission rejection must use one stable worker reference",
            }
        )

    configuration_source = contents.get(
        "sfx2/source/notification/NotificationConfiguration.cxx", ""
    )
    missing_configuration_accessors = []
    for group, field in CONFIGURATION_FIELDS:
        prefix = f"officecfg::Office::UI::NotificationCenter::{group}::{field}::"
        if configuration_source.count(prefix + "get()") != 1:
            missing_configuration_accessors.append(f"{group}.{field}.get")
        if configuration_source.count(prefix + "set") != 1:
            missing_configuration_accessors.append(f"{group}.{field}.set")
    if missing_configuration_accessors:
        violations.append(
            {
                "rule": "complete-generated-configuration-adapter",
                "path": "sfx2/source/notification/NotificationConfiguration.cxx",
                "detail": "missing or duplicate generated accessors: "
                + ", ".join(missing_configuration_accessors),
            }
        )
    configuration_schema = contents.get(
        "officecfg/registry/schema/org/openoffice/Office/UI/NotificationCenter.xcs",
        "",
    )
    schema_fields: list[tuple[str, str]] = []
    for group_match in re.finditer(
        r'<group oor:name="([^"]+)">(.*?)</group>',
        configuration_schema,
        flags=re.DOTALL,
    ):
        group = group_match.group(1)
        schema_fields.extend(
            (group, field)
            for field in re.findall(
                r'<prop oor:name="([^"]+)"', group_match.group(2)
            )
        )
    if tuple(schema_fields) != CONFIGURATION_FIELDS:
        violations.append(
            {
                "rule": "generated-configuration-schema-shape",
                "path": "officecfg/registry/schema/org/openoffice/Office/UI/NotificationCenter.xcs",
                "detail": "the generated adapter field list must exactly match the ordered schema properties",
            }
        )
    configuration_write = _extract_braced_block(
        configuration_source, "void NotificationConfiguration::write("
    )
    create_batch = configuration_write.find("ConfigurationChanges::create()")
    commit_batch = configuration_write.find("xChanges->commit();")
    last_setter = max(
        (
            configuration_write.find(
                f"NotificationCenter::{group}::{field}::set"
            )
            for group, field in CONFIGURATION_FIELDS
        ),
        default=-1,
    )
    if (
        min(create_batch, commit_batch, last_setter) < 0
        or not create_batch < last_setter < commit_batch
        or configuration_write.count("ConfigurationChanges::create()") != 1
        or configuration_write.count("xChanges->commit();") != 1
    ):
        violations.append(
            {
                "rule": "single-generated-configuration-batch",
                "path": "sfx2/source/notification/NotificationConfiguration.cxx",
                "detail": "all generated preference writes must be committed through one normalized batch",
            }
        )

    app_source = contents.get("sfx2/source/appl/app.cxx", "")
    app_destructor = _extract_braced_block(
        app_source, "SfxApplication::~SfxApplication()"
    )
    service_stop = app_destructor.find("pImpl->mxNotificationCenter.reset();")
    dying_broadcast = app_destructor.find("Broadcast( SfxHint(SfxHintId::Dying) )")
    if min(service_stop, dying_broadcast) < 0 or not service_stop < dying_broadcast:
        violations.append(
            {
                "rule": "application-service-shutdown-order",
                "path": "sfx2/source/appl/app.cxx",
                "detail": "the service must stop while VCL is alive and before the dying broadcast",
            }
        )

    git_source = contents.get(
        "sfx2/source/notification/LocalGitRepository.cxx", ""
    )
    update_head = _extract_braced_block(git_source, "void updateHead(")
    lock = update_head.find("aFile.open(")
    compare = update_head.find("readHead(rRepositoryURL) != rExpected")
    write = update_head.find("writeAll(aFile, aContents)")
    install = update_head.find("osl::File::replace(aLock, aRef)")
    if min(lock, compare, write, install) < 0 or not lock < compare < write < install:
        violations.append(
            {
                "rule": "lock-cas-install-order",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "ref mutation must lock, compare, write, then atomically install",
            }
        )

    object_writer = _extract_braced_block(git_source, "WrittenSnapshot writeSnapshotObjects(")
    blob = object_writer.find('objectId("blob", rJson)')
    tree = object_writer.find('objectId("tree", aTreeBody)')
    commit_object = object_writer.find('objectId("commit", aCommitBody)')
    commit = _extract_braced_block(
        git_source, "OString LocalGitRepository::commitSnapshot("
    )
    write_objects = commit.find("writeSnapshotObjects(")
    advance = commit.find("updateHead(")
    if (
        min(blob, tree, commit_object, write_objects, advance) < 0
        or not blob < tree < commit_object
        or not write_objects < advance
    ):
        violations.append(
            {
                "rule": "objects-before-ref",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "blob, tree and commit objects must be durable before the ref advances",
            }
        )

    operation_guard = _extract_braced_block(git_source, "class RepositoryGuard final")
    acquire_process = operation_guard.find("ProcessLock(repositoryProcessMutex())")
    initialize_guard = operation_guard.find(
        "ensureControlFile(pathURL(rRepositoryURL, { u\"notification.guard\" })"
    )
    open_lock = operation_guard.find(
        "osl_File_OpenFlag_Read | osl_File_OpenFlag_Write"
    )
    persistent_handle = operation_guard.find("osl::File File;")
    process_lock = operation_guard.find("std::unique_lock<std::mutex> ProcessLock")
    if (
        min(
            acquire_process,
            initialize_guard,
            open_lock,
            persistent_handle,
            process_lock,
        )
        < 0
        or not acquire_process < initialize_guard < open_lock
        or "osl_File_OpenFlag_NoLock" in operation_guard
    ):
        violations.append(
            {
                "rule": "permanent-operation-guard-shape",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "process exclusion must precede guard-file initialization and retained OSL locking",
            }
        )

    repository_constructor = _extract_braced_block(
        git_source, "LocalGitRepository::LocalGitRepository("
    )
    if "notification.guard" in repository_constructor:
        violations.append(
            {
                "rule": "guard-initialization-outside-lock",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "no same-process descriptor for notification.guard may close outside RepositoryGuard",
            }
        )

    history_reader = _extract_braced_block(
        git_source, "std::vector<GitSnapshot> LocalGitRepository::readHistory("
    )
    compaction_check = _extract_braced_block(
        git_source, "bool LocalGitRepository::needsCompaction("
    )
    if (
        "readCommitMetadataUnlocked(" not in history_reader
        or "readSnapshotUnlocked(" in history_reader
        or "readCommitMetadataUnlocked(" not in compaction_check
        or "readSnapshotUnlocked(" in compaction_check
    ):
        violations.append(
            {
                "rule": "metadata-only-history-depth",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "history and compaction depth traversal must not load full JSON blobs",
            }
        )

    inflater = _extract_braced_block(git_source, "std::string inflateObject(")
    initialize = inflater.find("inflateInit(&Stream)")
    parse_header = inflater.find("aInflated.find('\\0')")
    typed_blob = inflater.find('aType == "blob"')
    typed_commit = inflater.find('aType == "commit"')
    reserve_declared = inflater.find("aInflated.reserve(nExpectedSize)")
    if (
        min(initialize, parse_header, typed_blob, typed_commit, reserve_declared) < 0
        or not initialize < parse_header < typed_blob < typed_commit < reserve_declared
    ):
        violations.append(
            {
                "rule": "declared-type-inflate-order",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "streaming inflate must parse type and declared size before reserving the body",
            }
        )

    compact = _extract_braced_block(
        git_source, "OString LocalGitRepository::compactSnapshot("
    )
    pending_check = compact.find("bool bPending = exists(aPending)")
    pending = compact.find(
        "ensureControlFile(aPending, CompactionPendingContents)", pending_check
    )
    reuse_branch = compact.find("if (bPending", pending)
    reuse_helper = compact.find("readReusablePendingCheckpoint(", reuse_branch)
    retry_prune = compact.find("pruneUnreachableLooseObjects(", reuse_helper)
    retry_complete = compact.find("osl::File::remove(aPending)", retry_prune)
    reuse_return = compact.find("return rExpectedHead", retry_complete)
    compact_objects = compact.find("writeSnapshotObjects(", reuse_return)
    compact_advance = compact.find("updateHead(", compact_objects)
    prune = compact.find("pruneUnreachableLooseObjects(", compact_advance)
    complete = compact.find("osl::File::remove(aPending)", prune)
    if (
        min(
            pending_check,
            pending,
            reuse_branch,
            reuse_helper,
            retry_prune,
            retry_complete,
            reuse_return,
            pending,
            compact_objects,
            compact_advance,
            prune,
            complete,
        )
        < 0
        or not pending_check
        < pending
        < reuse_branch
        < reuse_helper
        < retry_prune
        < retry_complete
        < reuse_return
        < compact_objects
        < compact_advance
        < prune
        < complete
    ):
        violations.append(
            {
                "rule": "fail-closed-compaction-order",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "retry must prune an installed checkpoint in place; new compaction must gate objects/ref before prune and completion",
            }
        )

    checkpoint_reuse = _extract_braced_block(
        git_source, "bool readReusablePendingCheckpoint("
    )
    checkpoint_shape = checkpoint_reuse.find("!aCommit.ParentId.isEmpty()")
    checkpoint_origin = checkpoint_reuse.find("aCommit.CheckpointFrom.isEmpty()")
    checkpoint_action = checkpoint_reuse.find('aCommit.Action != "maintenance"')
    checkpoint_snapshot = checkpoint_reuse.find("aBlobBody != rJson")
    checkpoint_objects = checkpoint_reuse.find("rObjects = {")
    if (
        min(
            checkpoint_shape,
            checkpoint_origin,
            checkpoint_action,
            checkpoint_snapshot,
            checkpoint_objects,
        )
        < 0
        or not checkpoint_shape
        < checkpoint_origin
        < checkpoint_action
        < checkpoint_snapshot
        < checkpoint_objects
        or "writeSnapshotObjects(" in checkpoint_reuse
        or "updateHead(" in checkpoint_reuse
    ):
        violations.append(
            {
                "rule": "pending-checkpoint-reuse-shape",
                "path": "sfx2/source/notification/LocalGitRepository.cxx",
                "detail": "pending retries may reuse only the matching installed maintenance checkpoint and must not write or advance",
            }
        )

    store_commit = _extract_braced_block(
        store_source, "NotificationMutationResult commit("
    )
    check_bound = store_commit.find("Repository->needsCompaction(")
    checkpoint = store_commit.find("Repository->compactSnapshot(")
    user_commit = store_commit.find("Repository->commitSnapshot(")
    expose_user_commit = store_commit.find("aResult.CommitId = aCommit")
    if (
        min(check_bound, checkpoint, user_commit, expose_user_commit) < 0
        or not check_bound < checkpoint < user_commit < expose_user_commit
    ):
        violations.append(
            {
                "rule": "pre-mutation-compaction-order",
                "path": "sfx2/source/notification/NotificationStore.cxx",
                "detail": "compaction must precede the user commit and results must expose that action commit",
            }
        )
    return violations


def validate_repository(root: Path = REPOSITORY) -> None:
    contents, present = load_snapshot(root)
    violations = find_violations(contents, present)
    if violations:
        details = "\n".join(
            f"- {item['rule']} ({item['path']}): {item['detail']}"
            for item in violations
        )
        raise RuntimeError(f"notification-store contract failed:\n{details}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=REPOSITORY)
    args = parser.parse_args(argv)
    try:
        validate_repository(args.repository.resolve())
    except (OSError, RuntimeError, UnicodeError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        "Notification-store contract passed: public state model, deterministic redaction, "
        "bare loose-object Git, fixed local main ref, lock/CAS, tombstone/undo, bounded "
        "preferences, generated configuration, serialized async service, application shutdown, "
        "schema registration, and focused native-test wiring are intact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
