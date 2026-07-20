/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "LocalGitRepository.hxx"
#include "NotificationJson.hxx"

#include <comphelper/hash.hxx>
#include <osl/file.hxx>
#include <osl/thread.hxx>
#include <rtl/textenc.h>
#include <rtl/uuid.h>
#include <tools/urlobj.hxx>

#include <zlib.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <charconv>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <limits>
#include <mutex>
#include <set>
#include <string_view>
#include <vector>

namespace sfx2::notification_detail
{
namespace
{
constexpr std::string_view HeadContents = "ref: refs/heads/main\n";
constexpr std::string_view ConfigContents = "[core]\n"
                                            "\trepositoryformatversion = 0\n"
                                            "\tfilemode = false\n"
                                            "\tbare = true\n"
                                            "\tlogallrefupdates = true\n"
                                            "[gc]\n"
                                            "\tauto = 0\n";
constexpr std::string_view GuardContents = "LibreOffice notification history guard\n";
constexpr std::string_view CompactionPendingContents = "notification-compaction-pending 1\n";
constexpr std::string_view Identity = "LibreOffice Notification History <local@localhost>";
constexpr std::size_t MaxCompressedObjectBytes = 20 * 1024 * 1024;
constexpr std::size_t MaxObjectHeaderBytes = 64;
constexpr std::size_t MaxTreeBodyBytes = 4 * 1024;
constexpr std::size_t MaxCommitBodyBytes = 4 * 1024;
constexpr std::size_t MaxHistoryDepth = 4096;
constexpr std::size_t MaxQuarantinedLocks = 8;

std::string randomSuffix();
void ensureControlFile(const OUString& rURL, std::string_view rContents);

OUString childURL(const OUString& rParent, std::u16string_view rName)
{
    INetURLObject aURL(rParent);
    if (aURL.GetProtocol() != INetProtocol::File
        || !aURL.Append(rName, INetURLObject::EncodeMechanism::All))
        throw GitRepositoryError(GitFailure::Unavailable, "invalid notification repository URL");
    return aURL.GetMainURL(INetURLObject::DecodeMechanism::NONE);
}

OUString pathURL(const OUString& rBase, std::initializer_list<std::u16string_view> aSegments)
{
    OUString aURL = rBase;
    for (std::u16string_view rSegment : aSegments)
        aURL = childURL(aURL, rSegment);
    return aURL;
}

std::mutex& repositoryProcessMutex()
{
    static std::mutex Mutex;
    return Mutex;
}

class RepositoryGuard final
{
public:
    explicit RepositoryGuard(const OUString& rRepositoryURL)
        : ProcessLock(repositoryProcessMutex())
        , File(pathURL(rRepositoryURL, { u"notification.guard" }))
    {
        // This create/validate is intentionally inside ProcessLock. Classic Unix fcntl locks are
        // process-scoped and closing any same-process descriptor for the file can release them.
        // No notification.guard descriptor may therefore be opened outside RepositoryGuard.
        ensureControlFile(pathURL(rRepositoryURL, { u"notification.guard" }), GuardContents);

        // The process mutex covers Unix's process-scoped record-lock semantics. A write-capable OSL
        // open without NoLock then excludes other processes: CreateFile denies FILE_SHARE_WRITE on
        // Windows, and LibreOffice enables the corresponding fcntl/flock path on Unix. Every reader
        // also takes this guard so compaction cannot prune an object during traversal. The permanent
        // control file is never renamed/removed, and a crash releases its OS handle automatically.
        osl::FileBase::RC eOpen = osl::FileBase::E_AGAIN;
        for (unsigned int i = 0; i < 100; ++i)
        {
            eOpen = File.open(osl_File_OpenFlag_Read | osl_File_OpenFlag_Write);
            if (eOpen == osl::FileBase::E_None)
                return;
            if (eOpen != osl::FileBase::E_AGAIN && eOpen != osl::FileBase::E_ACCES)
                break;
            if (i + 1 != 100)
                osl::Thread::wait(std::chrono::milliseconds(10));
        }
        if (eOpen == osl::FileBase::E_AGAIN || eOpen == osl::FileBase::E_ACCES)
            throw GitRepositoryError(GitFailure::Conflict, "notification repository is busy");
        throw GitRepositoryError(GitFailure::Unavailable, "cannot lock notification repository");
    }

private:
    // Members are destroyed in reverse order: close File before releasing ProcessLock.
    std::unique_lock<std::mutex> ProcessLock;
    osl::File File;
};

bool exists(const OUString& rURL)
{
    osl::DirectoryItem aItem;
    return osl::DirectoryItem::get(rURL, aItem) == osl::FileBase::E_None;
}

void requireRegularPath(const OUString& rURL, bool bDirectory)
{
    osl::DirectoryItem aItem;
    if (osl::DirectoryItem::get(rURL, aItem) != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "notification repository path is missing");
    osl::FileStatus aStatus(osl_FileStatus_Mask_Type);
    if (aItem.getFileStatus(aStatus) != osl::FileBase::E_None || aStatus.isLink()
        || (bDirectory ? !aStatus.isDirectory() : !aStatus.isRegular()))
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "notification repository contains an unsafe path");
}

void ensureDirectory(const OUString& rURL)
{
    osl::FileBase::RC eResult = osl::Directory::createPath(rURL);
    if (eResult != osl::FileBase::E_None && eResult != osl::FileBase::E_EXIST)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot create notification repository directory");
    requireRegularPath(rURL, true);
}

sal_uInt64 directoryBytes(const OUString& rURL, unsigned int nDepth = 0)
{
    if (nDepth > 8)
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "notification repository directory depth is unsupported");
    osl::Directory aDirectory(rURL);
    if (aDirectory.open() != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot enumerate notification repository");
    sal_uInt64 nTotal = 0;
    osl::DirectoryItem aItem;
    while (aDirectory.getNextItem(aItem) == osl::FileBase::E_None)
    {
        osl::FileStatus aStatus(osl_FileStatus_Mask_Type | osl_FileStatus_Mask_FileSize
                                | osl_FileStatus_Mask_FileURL);
        if (aItem.getFileStatus(aStatus) != osl::FileBase::E_None || aStatus.isLink())
            throw GitRepositoryError(GitFailure::Unsupported,
                                     "notification repository contains an unsafe path");
        if (aStatus.isDirectory())
            nTotal += directoryBytes(aStatus.getFileURL(), nDepth + 1);
        else if (aStatus.isRegular())
            nTotal += aStatus.getFileSize();
        if (nTotal > 1024ULL * 1024 * 1024)
            return nTotal;
    }
    return nTotal;
}

std::string readFile(const OUString& rURL, std::size_t nLimit)
{
    requireRegularPath(rURL, false);
    osl::File aFile(rURL);
    if (aFile.open(osl_File_OpenFlag_Read) != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable, "cannot open notification history file");
    sal_uInt64 nSize = 0;
    if (aFile.getSize(nSize) != osl::FileBase::E_None || nSize > nLimit
        || nSize > static_cast<sal_uInt64>(std::numeric_limits<std::size_t>::max()))
        throw GitRepositoryError(GitFailure::Corrupt, "notification history file is too large");
    std::string aResult(static_cast<std::size_t>(nSize), '\0');
    sal_uInt64 nRead = 0;
    if (nSize != 0
        && (aFile.read(aResult.data(), nSize, nRead) != osl::FileBase::E_None || nRead != nSize))
        throw GitRepositoryError(GitFailure::Unavailable, "cannot read notification history file");
    return aResult;
}

void writeAll(osl::File& rFile, std::string_view rContents)
{
    sal_uInt64 nWritten = 0;
    if (!rContents.empty()
        && (rFile.write(rContents.data(), rContents.size(), nWritten) != osl::FileBase::E_None
            || nWritten != rContents.size()))
        throw GitRepositoryError(GitFailure::Unavailable, "cannot write notification history file");
    if (rFile.sync() != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot synchronize notification history");
}

void ensureControlFile(const OUString& rURL, std::string_view rContents)
{
    bool bReplaceEmpty = false;
    if (exists(rURL))
    {
        std::string aExisting = readFile(rURL, 4096);
        if (aExisting == rContents)
            return;
        // An empty file is the only recoverable result of a creator crashing before its first
        // write. Never repair a non-empty control file whose meaning is unknown.
        if (!aExisting.empty())
            throw GitRepositoryError(GitFailure::Unsupported,
                                     "notification repository control file is not supported");
        bReplaceEmpty = true;
    }

    OUString aTemp = OUString::Concat(rURL) + u".tmp-" + OUString::fromUtf8(randomSuffix());
    osl::File aFile(aTemp);
    if (aFile.open(osl_File_OpenFlag_Write | osl_File_OpenFlag_Create) != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot create notification repository control file");
    try
    {
        writeAll(aFile, rContents);
        aFile.close();
        osl::FileBase::RC eInstall
            = bReplaceEmpty ? osl::File::replace(aTemp, rURL) : osl::File::move(aTemp, rURL);
        if (eInstall != osl::FileBase::E_None)
        {
            (void)osl::File::remove(aTemp);
            // A concurrent initializer is a valid winner only when it installed the exact bytes.
            if (!exists(rURL) || readFile(rURL, 4096) != rContents)
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot install notification repository control file");
        }
    }
    catch (...)
    {
        aFile.close();
        (void)osl::File::remove(aTemp);
        throw;
    }
}

bool isLowerHex(std::string_view rValue)
{
    return std::all_of(rValue.begin(), rValue.end(), [](unsigned char c)
                       { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
}

void requireObjectId(std::string_view rObjectId)
{
    if (rObjectId.size() != 40 || !isLowerHex(rObjectId))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git object ID");
}

std::string objectId(std::string_view rType, std::string_view rBody)
{
    std::string aObject;
    aObject.reserve(rType.size() + 32 + rBody.size());
    aObject.append(rType);
    aObject.push_back(' ');
    aObject.append(std::to_string(rBody.size()));
    aObject.push_back('\0');
    aObject.append(rBody);
    auto aHash = comphelper::Hash::calculateHash(aObject.data(), aObject.size(),
                                                 comphelper::HashType::SHA1);
    return comphelper::hashToString(aHash);
}

std::array<unsigned char, 20> decodeObjectId(std::string_view rObjectId)
{
    requireObjectId(rObjectId);
    std::array<unsigned char, 20> aBytes{};
    auto nHex = [](char c) -> unsigned char
    {
        return c <= '9' ? static_cast<unsigned char>(c - '0')
                        : static_cast<unsigned char>(c - 'a' + 10);
    };
    for (std::size_t i = 0; i < aBytes.size(); ++i)
        aBytes[i] = static_cast<unsigned char>((nHex(rObjectId[2 * i]) << 4)
                                               | nHex(rObjectId[2 * i + 1]));
    return aBytes;
}

std::string encodeObjectId(const unsigned char* pBytes)
{
    static constexpr char Hex[] = "0123456789abcdef";
    std::string aResult(40, '0');
    for (std::size_t i = 0; i < 20; ++i)
    {
        aResult[2 * i] = Hex[pBytes[i] >> 4];
        aResult[2 * i + 1] = Hex[pBytes[i] & 0x0f];
    }
    return aResult;
}

std::string randomSuffix()
{
    std::array<sal_uInt8, 16> aUuid{};
    rtl_createUuid(aUuid.data(), nullptr, true);
    static constexpr char Hex[] = "0123456789abcdef";
    std::string aResult(32, '0');
    for (std::size_t i = 0; i < aUuid.size(); ++i)
    {
        aResult[2 * i] = Hex[aUuid[i] >> 4];
        aResult[2 * i + 1] = Hex[aUuid[i] & 0x0f];
    }
    return aResult;
}

OUString objectURL(const OUString& rRepositoryURL, std::string_view rObjectId)
{
    requireObjectId(rObjectId);
    OUString aDirectory = OUString::fromUtf8(rObjectId.substr(0, 2));
    OUString aFile = OUString::fromUtf8(rObjectId.substr(2));
    return pathURL(rRepositoryURL, { u"objects", aDirectory, aFile });
}

std::string compressObject(std::string_view rObject)
{
    uLongf nCompressed = compressBound(static_cast<uLong>(rObject.size()));
    std::string aCompressed(static_cast<std::size_t>(nCompressed), '\0');
    int nResult = compress2(reinterpret_cast<Bytef*>(aCompressed.data()), &nCompressed,
                            reinterpret_cast<const Bytef*>(rObject.data()),
                            static_cast<uLong>(rObject.size()), Z_BEST_COMPRESSION);
    if (nResult != Z_OK)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot compress notification Git object");
    aCompressed.resize(static_cast<std::size_t>(nCompressed));
    return aCompressed;
}

std::string inflateObject(std::string_view rCompressed)
{
    struct InflateState final
    {
        InflateState()
        {
            if (inflateInit(&Stream) != Z_OK)
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot initialize notification Git decompression");
        }
        ~InflateState() { (void)inflateEnd(&Stream); }
        z_stream Stream{};
    } aState;

    aState.Stream.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(rCompressed.data()));
    aState.Stream.avail_in = static_cast<uInt>(rCompressed.size());
    std::string aInflated;
    aInflated.reserve(MaxObjectHeaderBytes);
    std::size_t nExpectedSize = 0;
    bool bHeaderParsed = false;

    while (true)
    {
        std::array<unsigned char, 4096> aChunk{};
        std::size_t nRemaining
            = bHeaderParsed ? nExpectedSize - aInflated.size() : MaxObjectHeaderBytes + 1;
        std::size_t nOutputCapacity
            = bHeaderParsed ? std::min(aChunk.size(), std::max<std::size_t>(1, nRemaining))
                            : nRemaining;
        aState.Stream.next_out = aChunk.data();
        aState.Stream.avail_out = static_cast<uInt>(nOutputCapacity);
        int nResult = inflate(&aState.Stream, Z_NO_FLUSH);
        std::size_t nProduced = nOutputCapacity - aState.Stream.avail_out;
        if (bHeaderParsed && nProduced > nRemaining)
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "notification Git object exceeds its declared size");
        aInflated.append(reinterpret_cast<const char*>(aChunk.data()), nProduced);

        if (!bHeaderParsed)
        {
            std::size_t nNull = aInflated.find('\0');
            if (nNull == std::string::npos)
            {
                if (aInflated.size() > MaxObjectHeaderBytes)
                    throw GitRepositoryError(GitFailure::Corrupt,
                                             "oversized notification Git object header");
            }
            else
            {
                if (nNull > MaxObjectHeaderBytes)
                    throw GitRepositoryError(GitFailure::Corrupt,
                                             "oversized notification Git object header");
                std::string_view aHeader(aInflated.data(), nNull);
                std::size_t nSpace = aHeader.find(' ');
                if (nSpace == std::string_view::npos || nSpace == 0)
                    throw GitRepositoryError(GitFailure::Corrupt,
                                             "invalid notification Git object header");
                std::string_view aType = aHeader.substr(0, nSpace);
                std::size_t nBodyLimit = 0;
                if (aType == "blob")
                    nBodyLimit = MaxSnapshotBytes;
                else if (aType == "tree")
                    nBodyLimit = MaxTreeBodyBytes;
                else if (aType == "commit")
                    nBodyLimit = MaxCommitBodyBytes;
                else
                    throw GitRepositoryError(GitFailure::Unsupported,
                                             "unsupported notification Git object type");
                std::string_view aSize = aHeader.substr(nSpace + 1);
                std::size_t nDeclared = 0;
                auto [pEnd, eError]
                    = std::from_chars(aSize.data(), aSize.data() + aSize.size(), nDeclared);
                if (eError != std::errc() || pEnd != aSize.data() + aSize.size()
                    || nDeclared > nBodyLimit)
                    throw GitRepositoryError(GitFailure::Corrupt,
                                             "invalid or oversized notification Git object size");
                nExpectedSize = nNull + 1 + nDeclared;
                aInflated.reserve(nExpectedSize);
                bHeaderParsed = true;
            }
        }
        if (bHeaderParsed && aInflated.size() > nExpectedSize)
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "notification Git object exceeds its declared size");

        if (nResult == Z_STREAM_END)
        {
            if (!bHeaderParsed || aInflated.size() != nExpectedSize || aState.Stream.avail_in != 0)
                throw GitRepositoryError(GitFailure::Corrupt,
                                         "truncated or trailing notification Git object data");
            return aInflated;
        }
        if (nResult != Z_OK || (nProduced == 0 && aState.Stream.avail_in == 0))
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "invalid notification Git object compression");
    }
}

void removeInternalTemp(const OUString& rURL) { (void)osl::File::remove(rURL); }

void writeLooseObject(const OUString& rRepositoryURL, std::string_view rType,
                      std::string_view rBody, const std::string& rObjectId);

std::pair<std::string, std::string> readLooseObject(const OUString& rRepositoryURL,
                                                    std::string_view rObjectId)
{
    requireObjectId(rObjectId);
    std::string aCompressed
        = readFile(objectURL(rRepositoryURL, rObjectId), MaxCompressedObjectBytes);
    std::string aInflated = inflateObject(aCompressed);

    std::size_t nNull = aInflated.find('\0');
    if (nNull == std::string::npos)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git object header");
    std::string_view aHeader(aInflated.data(), nNull);
    std::size_t nSpace = aHeader.find(' ');
    if (nSpace == std::string_view::npos || nSpace == 0)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git object header");
    std::string aType(aHeader.substr(0, nSpace));
    if (aType != "blob" && aType != "tree" && aType != "commit")
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "unsupported notification Git object type");
    std::size_t nDeclared = 0;
    std::string_view aSize = aHeader.substr(nSpace + 1);
    auto [pEnd, eError] = std::from_chars(aSize.data(), aSize.data() + aSize.size(), nDeclared);
    if (eError != std::errc() || pEnd != aSize.data() + aSize.size()
        || nDeclared != aInflated.size() - nNull - 1)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git object size");
    std::string aBody(aInflated.data() + nNull + 1, nDeclared);
    if (objectId(aType, aBody) != rObjectId)
        throw GitRepositoryError(GitFailure::Corrupt, "notification Git object hash mismatch");
    return { std::move(aType), std::move(aBody) };
}

void writeLooseObject(const OUString& rRepositoryURL, std::string_view rType,
                      std::string_view rBody, const std::string& rObjectId)
{
    OUString aObjectDirectory
        = pathURL(rRepositoryURL, { u"objects", OUString::fromUtf8(rObjectId.substr(0, 2)) });
    ensureDirectory(aObjectDirectory);
    OUString aTarget = objectURL(rRepositoryURL, rObjectId);
    if (exists(aTarget))
    {
        auto [aExistingType, aExistingBody] = readLooseObject(rRepositoryURL, rObjectId);
        if (aExistingType != rType || aExistingBody != rBody)
            throw GitRepositoryError(GitFailure::Corrupt, "notification Git object collision");
        return;
    }

    std::string aRaw;
    aRaw.reserve(rType.size() + 32 + rBody.size());
    aRaw.append(rType);
    aRaw.push_back(' ');
    aRaw.append(std::to_string(rBody.size()));
    aRaw.push_back('\0');
    aRaw.append(rBody);
    std::string aCompressed = compressObject(aRaw);
    OUString aTemp = childURL(aObjectDirectory, OUString::fromUtf8("tmp-" + randomSuffix()));
    osl::File aFile(aTemp);
    if (aFile.open(osl_File_OpenFlag_Write | osl_File_OpenFlag_Create) != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable, "cannot create notification Git object");
    try
    {
        writeAll(aFile, aCompressed);
        aFile.close();
        osl::FileBase::RC eMove = osl::File::move(aTemp, aTarget);
        if (eMove != osl::FileBase::E_None)
        {
            removeInternalTemp(aTemp);
            if (!exists(aTarget))
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot install notification Git object");
            auto [aExistingType, aExistingBody] = readLooseObject(rRepositoryURL, rObjectId);
            if (aExistingType != rType || aExistingBody != rBody)
                throw GitRepositoryError(GitFailure::Corrupt, "notification Git object collision");
        }
    }
    catch (...)
    {
        aFile.close();
        removeInternalTemp(aTemp);
        throw;
    }
}

OString readHead(const OUString& rRepositoryURL)
{
    OUString aRef = pathURL(rRepositoryURL, { u"refs", u"heads", u"main" });
    if (!exists(aRef))
        return OString();
    std::string aValue = readFile(aRef, 64);
    if (aValue.size() != 41 || aValue.back() != '\n')
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git ref");
    aValue.pop_back();
    requireObjectId(aValue);
    return OString(aValue);
}

void updateHead(const OUString& rRepositoryURL, const OString& rExpected, const OString& rNext)
{
    OUString aRef = pathURL(rRepositoryURL, { u"refs", u"heads", u"main" });
    OUString aLock = pathURL(rRepositoryURL, { u"refs", u"heads", u"main.lock" });
    osl::File aFile(aLock);
    osl::FileBase::RC eOpen = aFile.open(osl_File_OpenFlag_Write | osl_File_OpenFlag_Create);
    if (eOpen == osl::FileBase::E_EXIST)
        throw GitRepositoryError(GitFailure::Conflict, "notification history is locked");
    if (eOpen != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable, "cannot lock notification history");

    try
    {
        if (readHead(rRepositoryURL) != rExpected)
            throw GitRepositoryError(GitFailure::Conflict,
                                     "notification history changed concurrently");
        std::string aContents(rNext.getStr(), rNext.getLength());
        aContents.push_back('\n');
        writeAll(aFile, aContents);
        aFile.close();
        osl::FileBase::RC eInstall
            = exists(aRef) ? osl::File::replace(aLock, aRef) : osl::File::move(aLock, aRef);
        if (eInstall != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot advance notification history");
    }
    catch (...)
    {
        aFile.close();
        removeInternalTemp(aLock);
        throw;
    }
}

struct ParsedCommit
{
    std::string TreeId;
    OString ParentId;
    OString CheckpointFrom;
    OString Action;
    sal_uInt32 Affected = 0;
    sal_Int64 Timestamp = 0;
};

sal_Int64 parseIdentityTimestamp(std::string_view rLine, std::string_view rPrefix)
{
    if (!rLine.starts_with(rPrefix) || !rLine.ends_with(" +0000"))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git identity");
    std::string_view aTimestamp = rLine.substr(rPrefix.size(), rLine.size() - rPrefix.size() - 6);
    sal_Int64 nResult = 0;
    auto [pEnd, eError]
        = std::from_chars(aTimestamp.data(), aTimestamp.data() + aTimestamp.size(), nResult);
    if (eError != std::errc() || pEnd != aTimestamp.data() + aTimestamp.size() || nResult < 0)
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "invalid notification Git identity timestamp");
    return nResult;
}

ParsedCommit parseCommit(std::string_view rBody)
{
    std::size_t nMessage = rBody.find("\n\n");
    if (nMessage == std::string_view::npos)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit");
    std::string_view aHeaders = rBody.substr(0, nMessage);
    std::vector<std::string_view> aLines;
    while (!aHeaders.empty())
    {
        std::size_t nEnd = aHeaders.find('\n');
        aLines.push_back(aHeaders.substr(0, nEnd));
        if (nEnd == std::string_view::npos)
            break;
        aHeaders.remove_prefix(nEnd + 1);
    }
    if (aLines.size() != 3 && aLines.size() != 4)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit headers");
    if (!aLines[0].starts_with("tree "))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit tree");
    std::string aTree(aLines[0].substr(5));
    requireObjectId(aTree);
    std::size_t nIdentity = 1;
    OString aParent;
    OString aCheckpointFrom;
    if (aLines.size() == 4)
    {
        if (aLines[1].starts_with("parent "))
        {
            std::string_view aParentValue = aLines[1].substr(7);
            requireObjectId(aParentValue);
            aParent = OString(aParentValue);
        }
        else if (aLines[1].starts_with("checkpoint-from "))
        {
            std::string_view aCheckpointValue = aLines[1].substr(16);
            requireObjectId(aCheckpointValue);
            aCheckpointFrom = OString(aCheckpointValue);
        }
        else
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "invalid notification Git commit ancestry");
        nIdentity = 2;
    }
    std::string aIdentityPrefix = "author " + std::string(Identity) + " ";
    std::string aCommitterPrefix = "committer " + std::string(Identity) + " ";
    sal_Int64 nTimestamp = parseIdentityTimestamp(aLines[nIdentity], aIdentityPrefix);
    if (parseIdentityTimestamp(aLines[nIdentity + 1], aCommitterPrefix) != nTimestamp)
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification Git identity timestamps differ");

    std::string_view aMessage = rBody.substr(nMessage + 2);
    if (!aMessage.ends_with('\n'))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit message");
    aMessage.remove_suffix(1);
    constexpr std::string_view MessagePrefix = "notification ";
    if (!aMessage.starts_with(MessagePrefix))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit message");
    aMessage.remove_prefix(MessagePrefix.size());
    std::size_t nSeparator = aMessage.find(' ');
    if (nSeparator == std::string_view::npos || nSeparator == 0)
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit action");
    std::string_view aAction = aMessage.substr(0, nSeparator);
    if (!std::all_of(aAction.begin(), aAction.end(),
                     [](unsigned char c) { return (c >= 'a' && c <= 'z') || c == '-'; }))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git commit action");
    std::string_view aAffected = aMessage.substr(nSeparator + 1);
    sal_uInt32 nAffected = 0;
    auto [pAffectedEnd, eAffectedError]
        = std::from_chars(aAffected.data(), aAffected.data() + aAffected.size(), nAffected);
    if (eAffectedError != std::errc() || pAffectedEnd != aAffected.data() + aAffected.size())
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git affected count");
    if (!aCheckpointFrom.isEmpty() && (aAction != "maintenance" || nAffected != 0))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification Git checkpoint action");
    return { std::move(aTree), std::move(aParent), std::move(aCheckpointFrom),
             OString(aAction), nAffected,          nTimestamp };
}

std::string blobIdFromTree(std::string_view rTree)
{
    static constexpr std::string_view Prefix = "100644 notifications.json";
    if (rTree.size() != Prefix.size() + 1 + 20 || !rTree.starts_with(Prefix)
        || rTree[Prefix.size()] != '\0')
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "unsupported notification Git tree layout");
    return encodeObjectId(reinterpret_cast<const unsigned char*>(
        rTree.data() + static_cast<std::ptrdiff_t>(Prefix.size() + 1)));
}

ParsedCommit validateSnapshotObjects(const OUString& rRepositoryURL, const OString& rCommitId)
{
    auto [aCommitType, aCommitBody] = readLooseObject(rRepositoryURL, rCommitId);
    if (aCommitType != "commit")
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history ref does not name a commit");
    ParsedCommit aCommit = parseCommit(aCommitBody);
    auto [aTreeType, aTreeBody] = readLooseObject(rRepositoryURL, aCommit.TreeId);
    if (aTreeType != "tree")
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history commit does not name a tree");
    std::string aBlobId = blobIdFromTree(aTreeBody);
    auto [aBlobType, aBlobBody] = readLooseObject(rRepositoryURL, aBlobId);
    if (aBlobType != "blob" || aBlobBody.size() > MaxSnapshotBytes)
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history tree does not name a bounded blob");
    (void)parseRecords(aBlobBody);
    return aCommit;
}

bool isOwnedQuarantineName(std::string_view rName)
{
    constexpr std::string_view Prefix = "main-lock-";
    return rName.starts_with(Prefix) && rName.size() == Prefix.size() + 32
           && isLowerHex(rName.substr(Prefix.size()));
}

void pruneOwnedQuarantines(const OUString& rLostFound)
{
    osl::Directory aDirectory(rLostFound);
    if (aDirectory.open() != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot enumerate notification lock quarantine");
    std::vector<OUString> aOwned;
    osl::DirectoryItem aItem;
    while (aDirectory.getNextItem(aItem) == osl::FileBase::E_None)
    {
        osl::FileStatus aStatus(osl_FileStatus_Mask_Type | osl_FileStatus_Mask_FileName
                                | osl_FileStatus_Mask_FileURL);
        if (aItem.getFileStatus(aStatus) != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot inspect notification lock quarantine");
        OString aName = OUStringToOString(aStatus.getFileName(), RTL_TEXTENCODING_ASCII_US);
        if (!aStatus.isLink() && aStatus.isRegular() && isOwnedQuarantineName(aName))
            aOwned.push_back(aStatus.getFileURL());
    }
    std::sort(aOwned.begin(), aOwned.end());
    while (aOwned.size() >= MaxQuarantinedLocks)
    {
        if (osl::File::remove(aOwned.front()) != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot bound notification lock quarantine");
        aOwned.erase(aOwned.begin());
    }
}

bool quarantineLock(const OUString& rRepositoryURL, const OUString& rLock)
{
    OUString aLostFound = pathURL(rRepositoryURL, { u"lost-found" });
    ensureDirectory(aLostFound);
    pruneOwnedQuarantines(aLostFound);
    OUString aDestination = childURL(aLostFound, OUString::fromUtf8("main-lock-" + randomSuffix()));
    osl::FileBase::RC eMove = osl::File::move(rLock, aDestination);
    if (eMove == osl::FileBase::E_NOENT)
        return false;
    if (eMove != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot quarantine invalid notification history lock");
    return true;
}

void recoverMainLock(const OUString& rRepositoryURL)
{
    OUString aRef = pathURL(rRepositoryURL, { u"refs", u"heads", u"main" });
    OUString aLock = pathURL(rRepositoryURL, { u"refs", u"heads", u"main.lock" });
    if (!exists(aLock))
        return;

    try
    {
        std::string aContents = readFile(aLock, 64);
        if (aContents.empty())
        {
            if (osl::File::remove(aLock) != osl::FileBase::E_None)
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot clear abandoned notification history lock");
            return;
        }
        if (aContents.size() != 41 || aContents.back() != '\n')
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "invalid notification history lock contents");
        aContents.pop_back();
        requireObjectId(aContents);
        OString aProposed(aContents);
        OString aCurrent = readHead(rRepositoryURL);
        if (aProposed == aCurrent)
        {
            if (osl::File::remove(aLock) != osl::FileBase::E_None)
                throw GitRepositoryError(GitFailure::Unavailable,
                                         "cannot clear redundant notification history lock");
            return;
        }
        ParsedCommit aPending = validateSnapshotObjects(rRepositoryURL, aProposed);
        bool bInitialRoot = aCurrent.isEmpty() && aPending.ParentId.isEmpty()
                            && aPending.CheckpointFrom.isEmpty();
        bool bFastForward = aPending.ParentId == aCurrent && !aCurrent.isEmpty()
                            && aPending.CheckpointFrom.isEmpty();
        bool bCheckpoint = aPending.ParentId.isEmpty() && aPending.CheckpointFrom == aCurrent
                           && !aCurrent.isEmpty() && aPending.Action == "maintenance"
                           && aPending.Affected == 0;
        if (!bInitialRoot && !bFastForward && !bCheckpoint)
            throw GitRepositoryError(GitFailure::Corrupt,
                                     "notification history lock is not a valid next commit");
        osl::FileBase::RC eInstall
            = exists(aRef) ? osl::File::replace(aLock, aRef) : osl::File::move(aLock, aRef);
        if (eInstall != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot recover notification history ref");
    }
    catch (const GitRepositoryError&)
    {
        if (exists(aLock))
            (void)quarantineLock(rRepositoryURL, aLock);
        throw;
    }
}

void rejectUnsupportedLayout(const OUString& rRepositoryURL)
{
    if (exists(pathURL(rRepositoryURL, { u"packed-refs" }))
        || exists(pathURL(rRepositoryURL, { u"index" }))
        || exists(pathURL(rRepositoryURL, { u"hooks" }))
        || exists(pathURL(rRepositoryURL, { u"objects", u"pack" }))
        || exists(pathURL(rRepositoryURL, { u"objects", u"info", u"alternates" }))
        || exists(pathURL(rRepositoryURL, { u"refs", u"replace" })))
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "unsupported notification Git repository feature");
}

struct WrittenSnapshot
{
    std::string BlobId;
    std::string TreeId;
    std::string CommitId;
};

WrittenSnapshot writeSnapshotObjects(const OUString& rRepositoryURL, std::string_view rJson,
                                     const OString& rParent, const OString& rCheckpointFrom,
                                     std::string_view rAction, sal_uInt32 nAffected,
                                     sal_Int64 nTimestamp)
{
    if (!rParent.isEmpty() && !rCheckpointFrom.isEmpty())
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification snapshot has two ancestry headers");
    std::string aBlobId = objectId("blob", rJson);
    writeLooseObject(rRepositoryURL, "blob", rJson, aBlobId);

    std::string aTreeBody = "100644 notifications.json";
    aTreeBody.push_back('\0');
    auto aBlobBytes = decodeObjectId(aBlobId);
    aTreeBody.append(reinterpret_cast<const char*>(aBlobBytes.data()), aBlobBytes.size());
    std::string aTreeId = objectId("tree", aTreeBody);
    writeLooseObject(rRepositoryURL, "tree", aTreeBody, aTreeId);

    std::string aCommitBody = "tree " + aTreeId + "\n";
    if (!rParent.isEmpty())
        aCommitBody += "parent " + std::string(rParent) + "\n";
    else if (!rCheckpointFrom.isEmpty())
        aCommitBody += "checkpoint-from " + std::string(rCheckpointFrom) + "\n";
    std::string aWhen = std::to_string(nTimestamp) + " +0000\n";
    aCommitBody += "author " + std::string(Identity) + " " + aWhen;
    aCommitBody += "committer " + std::string(Identity) + " " + aWhen;
    aCommitBody
        += "\nnotification " + std::string(rAction) + " " + std::to_string(nAffected) + "\n";
    std::string aCommitId = objectId("commit", aCommitBody);
    writeLooseObject(rRepositoryURL, "commit", aCommitBody, aCommitId);
    return { std::move(aBlobId), std::move(aTreeId), std::move(aCommitId) };
}

ParsedCommit readCommitUnlocked(const OUString& rRepositoryURL, const OString& rCommitId)
{
    requireObjectId(rCommitId);
    auto [aCommitType, aCommitBody] = readLooseObject(rRepositoryURL, rCommitId);
    if (aCommitType != "commit")
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history ref does not name a commit");
    return parseCommit(aCommitBody);
}

GitSnapshot readCommitMetadataUnlocked(const OUString& rRepositoryURL, const OString& rCommitId)
{
    ParsedCommit aCommit = readCommitUnlocked(rRepositoryURL, rCommitId);
    return { rCommitId,
             std::move(aCommit.ParentId),
             std::move(aCommit.CheckpointFrom),
             std::move(aCommit.Action),
             aCommit.Affected,
             aCommit.Timestamp,
             std::string() };
}

GitSnapshot readSnapshotUnlocked(const OUString& rRepositoryURL, const OString& rCommitId)
{
    ParsedCommit aCommit = readCommitUnlocked(rRepositoryURL, rCommitId);
    auto [aTreeType, aTreeBody] = readLooseObject(rRepositoryURL, aCommit.TreeId);
    if (aTreeType != "tree")
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history commit does not name a tree");
    std::string aBlobId = blobIdFromTree(aTreeBody);
    auto [aBlobType, aBlobBody] = readLooseObject(rRepositoryURL, aBlobId);
    if (aBlobType != "blob" || aBlobBody.size() > MaxSnapshotBytes)
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification history tree does not name a bounded blob");
    return { rCommitId,
             std::move(aCommit.ParentId),
             std::move(aCommit.CheckpointFrom),
             std::move(aCommit.Action),
             aCommit.Affected,
             aCommit.Timestamp,
             std::move(aBlobBody) };
}

bool readReusablePendingCheckpoint(const OUString& rRepositoryURL, const OString& rCommitId,
                                   std::string_view rJson, WrittenSnapshot& rObjects)
{
    ParsedCommit aCommit = readCommitUnlocked(rRepositoryURL, rCommitId);
    if (!aCommit.ParentId.isEmpty() || aCommit.CheckpointFrom.isEmpty()
        || aCommit.Action != "maintenance" || aCommit.Affected != 0)
        return false;

    auto [aTreeType, aTreeBody] = readLooseObject(rRepositoryURL, aCommit.TreeId);
    if (aTreeType != "tree")
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification checkpoint does not name a tree");
    std::string aBlobId = blobIdFromTree(aTreeBody);
    auto [aBlobType, aBlobBody] = readLooseObject(rRepositoryURL, aBlobId);
    if (aBlobType != "blob" || aBlobBody.size() > MaxSnapshotBytes)
        throw GitRepositoryError(GitFailure::Corrupt,
                                 "notification checkpoint does not name a bounded blob");
    (void)parseRecords(aBlobBody);
    if (aBlobBody != rJson)
        throw GitRepositoryError(GitFailure::Conflict,
                                 "pending notification checkpoint snapshot changed");

    rObjects = { std::move(aBlobId), std::move(aCommit.TreeId), std::string(rCommitId) };
    return true;
}

void pruneUnreachableLooseObjects(const OUString& rRepositoryURL,
                                  const std::set<std::string>& rKeep)
{
    OUString aObjectsURL = pathURL(rRepositoryURL, { u"objects" });
    osl::Directory aObjects(aObjectsURL);
    if (aObjects.open() != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot enumerate notification Git objects");
    osl::DirectoryItem aDirectoryItem;
    while (aObjects.getNextItem(aDirectoryItem) == osl::FileBase::E_None)
    {
        osl::FileStatus aDirectoryStatus(osl_FileStatus_Mask_Type | osl_FileStatus_Mask_FileName
                                         | osl_FileStatus_Mask_FileURL);
        if (aDirectoryItem.getFileStatus(aDirectoryStatus) != osl::FileBase::E_None
            || aDirectoryStatus.isLink())
            throw GitRepositoryError(GitFailure::Unsupported,
                                     "notification Git objects contain an unsafe path");
        OString aDirectoryName
            = OUStringToOString(aDirectoryStatus.getFileName(), RTL_TEXTENCODING_ASCII_US);
        if (!aDirectoryStatus.isDirectory() || aDirectoryName.getLength() != 2
            || !isLowerHex(aDirectoryName))
            continue;

        osl::Directory aDirectory(aDirectoryStatus.getFileURL());
        if (aDirectory.open() != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot enumerate notification Git object directory");
        osl::DirectoryItem aObjectItem;
        while (aDirectory.getNextItem(aObjectItem) == osl::FileBase::E_None)
        {
            osl::FileStatus aObjectStatus(osl_FileStatus_Mask_Type | osl_FileStatus_Mask_FileName
                                          | osl_FileStatus_Mask_FileURL);
            if (aObjectItem.getFileStatus(aObjectStatus) != osl::FileBase::E_None
                || aObjectStatus.isLink() || !aObjectStatus.isRegular())
                throw GitRepositoryError(GitFailure::Unsupported,
                                         "notification Git object path is unsupported");
            OString aObjectName
                = OUStringToOString(aObjectStatus.getFileName(), RTL_TEXTENCODING_ASCII_US);
            bool bLooseObject = aObjectName.getLength() == 38 && isLowerHex(aObjectName);
            bool bInternalTemp = aObjectName.startsWith("tmp-");
            if (!bLooseObject && !bInternalTemp)
                throw GitRepositoryError(GitFailure::Unsupported,
                                         "notification Git object filename is unsupported");
            std::string aObjectId = std::string(aDirectoryName) + std::string(aObjectName);
            if (bInternalTemp || rKeep.find(aObjectId) == rKeep.end())
            {
                if (osl::File::remove(aObjectStatus.getFileURL()) != osl::FileBase::E_None)
                    throw GitRepositoryError(GitFailure::Unavailable,
                                             "cannot prune notification Git object");
            }
        }
        aDirectory.close();
        (void)osl::Directory::remove(aDirectoryStatus.getFileURL());
    }
}
}

LocalGitRepository::LocalGitRepository(const OUString& rRepositoryURL)
    : m_aRepositoryURL(rRepositoryURL)
{
    INetURLObject aURL(rRepositoryURL);
    if (rRepositoryURL.isEmpty() || aURL.GetProtocol() != INetProtocol::File)
        throw GitRepositoryError(GitFailure::Unavailable, "notification repository is not local");

    ensureDirectory(m_aRepositoryURL);
    rejectUnsupportedLayout(m_aRepositoryURL);
    ensureDirectory(pathURL(m_aRepositoryURL, { u"objects" }));
    ensureDirectory(pathURL(m_aRepositoryURL, { u"refs" }));
    ensureDirectory(pathURL(m_aRepositoryURL, { u"refs", u"heads" }));
    ensureControlFile(pathURL(m_aRepositoryURL, { u"HEAD" }), HeadContents);
    ensureControlFile(pathURL(m_aRepositoryURL, { u"config" }), ConfigContents);
    RepositoryGuard aGuard(m_aRepositoryURL);
    recoverMainLock(m_aRepositoryURL);

    OString aHead = readHead(m_aRepositoryURL);
    if (!aHead.isEmpty())
    {
        GitSnapshot aSnapshot = readSnapshotUnlocked(m_aRepositoryURL, aHead);
        (void)parseRecords(aSnapshot.Json);
    }
}

OString LocalGitRepository::head() const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    return readHead(m_aRepositoryURL);
}

GitSnapshot LocalGitRepository::currentSnapshot() const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    OString aHead = readHead(m_aRepositoryURL);
    return aHead.isEmpty() ? GitSnapshot() : readSnapshotUnlocked(m_aRepositoryURL, aHead);
}

GitSnapshot LocalGitRepository::readSnapshot(const OString& rCommitId) const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    return readSnapshotUnlocked(m_aRepositoryURL, rCommitId);
}

std::vector<GitSnapshot> LocalGitRepository::readHistory(const OString& rHead,
                                                         sal_uInt32 nLimit) const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    if (readHead(m_aRepositoryURL) != rHead)
        throw GitRepositoryError(GitFailure::Conflict,
                                 "notification history changed before history read");
    std::vector<GitSnapshot> aResult;
    OString aCurrent = rHead;
    std::set<OString> aVisited;
    while (!aCurrent.isEmpty() && aResult.size() < nLimit)
    {
        if (!aVisited.insert(aCurrent).second)
            throw GitRepositoryError(GitFailure::Corrupt, "cycle in notification Git history");
        aResult.push_back(readCommitMetadataUnlocked(m_aRepositoryURL, aCurrent));
        aCurrent = aResult.back().ParentId;
    }
    return aResult;
}

GitUndoTarget LocalGitRepository::readUndoTarget(const OString& rTarget, const OString& rHead) const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    requireObjectId(rTarget);
    if (!rHead.isEmpty())
        requireObjectId(rHead);
    if (readHead(m_aRepositoryURL) != rHead)
        throw GitRepositoryError(GitFailure::Conflict,
                                 "notification history changed before undo read");
    OString aCurrent = rHead;
    std::set<OString> aVisited;
    for (std::size_t i = 0; i < MaxHistoryDepth && !aCurrent.isEmpty(); ++i)
    {
        if (!aVisited.insert(aCurrent).second)
            throw GitRepositoryError(GitFailure::Corrupt, "cycle in notification Git history");
        GitSnapshot aSnapshot = readCommitMetadataUnlocked(m_aRepositoryURL, aCurrent);
        if (aCurrent == rTarget)
        {
            GitUndoTarget aResult;
            aResult.Found = true;
            aResult.Target = readSnapshotUnlocked(m_aRepositoryURL, aCurrent);
            if (!aResult.Target.ParentId.isEmpty())
            {
                aResult.Parent = readSnapshotUnlocked(m_aRepositoryURL, aResult.Target.ParentId);
                aResult.HasParent = true;
            }
            return aResult;
        }
        aCurrent = aSnapshot.ParentId;
    }
    if (!aCurrent.isEmpty())
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "notification Git history exceeds the supported depth");
    return GitUndoTarget();
}

bool LocalGitRepository::isAncestor(const OString& rPossibleAncestor,
                                    const OString& rCommitId) const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    requireObjectId(rPossibleAncestor);
    requireObjectId(rCommitId);
    OString aCurrent = rCommitId;
    std::set<OString> aVisited;
    for (std::size_t i = 0; i < MaxHistoryDepth && !aCurrent.isEmpty(); ++i)
    {
        if (aCurrent == rPossibleAncestor)
            return true;
        if (!aVisited.insert(aCurrent).second)
            throw GitRepositoryError(GitFailure::Corrupt, "cycle in notification Git history");
        aCurrent = readCommitMetadataUnlocked(m_aRepositoryURL, aCurrent).ParentId;
    }
    if (!aCurrent.isEmpty())
        throw GitRepositoryError(GitFailure::Unsupported,
                                 "notification Git history exceeds the supported depth");
    return false;
}

OString LocalGitRepository::commitSnapshot(std::string_view rJson, const OString& rExpectedHead,
                                           std::string_view rAction, sal_uInt32 nAffected,
                                           sal_Int64 nTimestamp)
{
    if (rJson.size() > MaxSnapshotBytes)
        throw GitRepositoryError(GitFailure::Corrupt, "notification snapshot is too large");
    if (!rExpectedHead.isEmpty() && (rExpectedHead.getLength() != 40 || !isLowerHex(rExpectedHead)))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid expected notification Git ref");
    if (rAction.empty() || rAction.size() > 48
        || !std::all_of(rAction.begin(), rAction.end(),
                        [](unsigned char c) { return (c >= 'a' && c <= 'z') || c == '-'; }))
        throw GitRepositoryError(GitFailure::Unavailable, "invalid notification history action");
    if (nTimestamp < 0)
        throw GitRepositoryError(GitFailure::Unavailable, "invalid notification history timestamp");

    RepositoryGuard aGuard(m_aRepositoryURL);
    WrittenSnapshot aWritten = writeSnapshotObjects(m_aRepositoryURL, rJson, rExpectedHead,
                                                    OString(), rAction, nAffected, nTimestamp);
    OString aResult(aWritten.CommitId);
    updateHead(m_aRepositoryURL, rExpectedHead, aResult);
    return aResult;
}

bool LocalGitRepository::needsCompaction(sal_uInt32 nMaximumCommits, sal_uInt64 nMaximumBytes) const
{
    RepositoryGuard aGuard(m_aRepositoryURL);
    if (exists(pathURL(m_aRepositoryURL, { u"compaction.pending" })))
        return true;
    if (directoryBytes(m_aRepositoryURL) > nMaximumBytes)
        return true;
    OString aCurrent = readHead(m_aRepositoryURL);
    for (sal_uInt32 i = 0; !aCurrent.isEmpty() && i <= nMaximumCommits; ++i)
    {
        if (i == nMaximumCommits)
            return true;
        aCurrent = readCommitMetadataUnlocked(m_aRepositoryURL, aCurrent).ParentId;
    }
    return false;
}

OString LocalGitRepository::compactSnapshot(std::string_view rJson, const OString& rExpectedHead,
                                            std::string_view rAction, sal_uInt32 nAffected,
                                            sal_Int64 nTimestamp)
{
    if (rJson.size() > MaxSnapshotBytes || rExpectedHead.isEmpty()
        || rExpectedHead.getLength() != 40 || !isLowerHex(rExpectedHead))
        throw GitRepositoryError(GitFailure::Corrupt, "invalid notification compaction snapshot");
    if (rAction != "maintenance" || nAffected != 0 || nTimestamp < 0)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "invalid notification compaction metadata");

    RepositoryGuard aGuard(m_aRepositoryURL);
    if (readHead(m_aRepositoryURL) != rExpectedHead)
        throw GitRepositoryError(GitFailure::Conflict,
                                 "notification history changed before compaction");
    OUString aPending = pathURL(m_aRepositoryURL, { u"compaction.pending" });
    bool bPending = exists(aPending);
    // Validate an existing durable gate before trusting it, or create the gate before any new
    // objects/ref are installed. A malformed marker must never be silently accepted and deleted.
    ensureControlFile(aPending, CompactionPendingContents);
    WrittenSnapshot aInstalledCheckpoint;
    if (bPending
        && readReusablePendingCheckpoint(m_aRepositoryURL, rExpectedHead, rJson,
                                         aInstalledCheckpoint))
    {
        // The prior attempt already installed this parentless checkpoint. Retrying only the
        // idempotent prune avoids a fresh timestamped checkpoint on every persistent failure.
        pruneUnreachableLooseObjects(m_aRepositoryURL,
                                     { aInstalledCheckpoint.BlobId, aInstalledCheckpoint.TreeId,
                                       aInstalledCheckpoint.CommitId });
        if (osl::File::remove(aPending) != osl::FileBase::E_None)
            throw GitRepositoryError(GitFailure::Unavailable,
                                     "cannot complete notification history compaction");
        return rExpectedHead;
    }

    WrittenSnapshot aWritten = writeSnapshotObjects(m_aRepositoryURL, rJson, OString(),
                                                    rExpectedHead, rAction, nAffected, nTimestamp);
    OString aResult(aWritten.CommitId);
    updateHead(m_aRepositoryURL, rExpectedHead, aResult);
    pruneUnreachableLooseObjects(m_aRepositoryURL,
                                 { aWritten.BlobId, aWritten.TreeId, aWritten.CommitId });
    if (osl::File::remove(aPending) != osl::FileBase::E_None)
        throw GitRepositoryError(GitFailure::Unavailable,
                                 "cannot complete notification history compaction");
    return aResult;
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
