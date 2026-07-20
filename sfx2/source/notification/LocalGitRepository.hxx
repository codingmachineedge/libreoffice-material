/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <rtl/string.hxx>
#include <rtl/ustring.hxx>
#include <sal/types.h>

#include <stdexcept>
#include <string>
#include <vector>

namespace sfx2::notification_detail
{
enum class GitFailure
{
    Unavailable,
    Corrupt,
    Unsupported,
    Conflict
};

class GitRepositoryError final : public std::runtime_error
{
public:
    GitRepositoryError(GitFailure eFailure, const std::string& rMessage)
        : std::runtime_error(rMessage)
        , Failure(eFailure)
    {
    }

    GitFailure Failure;
};

struct GitSnapshot
{
    OString CommitId;
    OString ParentId;
    /** Present only on a parentless compaction checkpoint. */
    OString CheckpointFrom;
    OString Action;
    sal_uInt32 Affected = 0;
    sal_Int64 Timestamp = 0;
    std::string Json;
};

struct GitUndoTarget
{
    bool Found = false;
    GitSnapshot Target;
    bool HasParent = false;
    GitSnapshot Parent;
};

/** Minimal, bounded loose-object Git writer/reader. It intentionally has no pack or remote support. */
class LocalGitRepository final
{
public:
    explicit LocalGitRepository(const OUString& rRepositoryURL);

    const OUString& repositoryURL() const { return m_aRepositoryURL; }
    OString head() const;
    GitSnapshot currentSnapshot() const;
    GitSnapshot readSnapshot(const OString& rCommitId) const;
    /** Read a stable history slice while compaction is excluded. */
    std::vector<GitSnapshot> readHistory(const OString& rHead, sal_uInt32 nLimit) const;
    /** Validate ancestry and read the target plus parent under one repository operation lock. */
    GitUndoTarget readUndoTarget(const OString& rTarget, const OString& rHead) const;
    bool isAncestor(const OString& rPossibleAncestor, const OString& rCommitId) const;

    /** Objects are written first, then main is advanced with an exclusive lock and CAS. */
    OString commitSnapshot(std::string_view rJson, const OString& rExpectedHead,
                           std::string_view rAction, sal_uInt32 nAffected, sal_Int64 nTimestamp);

    bool needsCompaction(sal_uInt32 nMaximumCommits, sal_uInt64 nMaximumBytes) const;
    /** Replace main with a parentless checkpoint and delete only unreachable loose objects. */
    OString compactSnapshot(std::string_view rJson, const OString& rExpectedHead,
                            std::string_view rAction, sal_uInt32 nAffected, sal_Int64 nTimestamp);

private:
    OUString m_aRepositoryURL;
};
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
