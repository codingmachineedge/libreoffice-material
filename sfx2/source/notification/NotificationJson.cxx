/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationJson.hxx"

#include <tools/json_writer.hxx>

#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <rtl/textenc.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <initializer_list>
#include <sstream>
#include <string_view>

namespace sfx2::notification_detail
{
namespace
{
constexpr std::string_view folderName(NotificationFolder eFolder)
{
    switch (eFolder)
    {
        case NotificationFolder::Inbox:
            return "inbox";
        case NotificationFolder::Archived:
            return "archived";
        case NotificationFolder::Deleted:
            return "deleted";
    }
    return "inbox";
}

NotificationFolder parseFolder(std::string_view rValue)
{
    if (rValue == "inbox")
        return NotificationFolder::Inbox;
    if (rValue == "archived")
        return NotificationFolder::Archived;
    if (rValue == "deleted")
        return NotificationFolder::Deleted;
    throw NotificationDataError("invalid notification folder");
}

constexpr std::string_view severityName(NotificationSeverity eSeverity)
{
    switch (eSeverity)
    {
        case NotificationSeverity::Information:
            return "information";
        case NotificationSeverity::Success:
            return "success";
        case NotificationSeverity::Warning:
            return "warning";
        case NotificationSeverity::Error:
            return "error";
    }
    return "information";
}

NotificationSeverity parseSeverity(std::string_view rValue)
{
    if (rValue == "information")
        return NotificationSeverity::Information;
    if (rValue == "success")
        return NotificationSeverity::Success;
    if (rValue == "warning")
        return NotificationSeverity::Warning;
    if (rValue == "error")
        return NotificationSeverity::Error;
    throw NotificationDataError("invalid notification severity");
}

constexpr std::string_view privacyName(NotificationPrivacy ePrivacy)
{
    return ePrivacy == NotificationPrivacy::SafeDisplayText ? "safe-display-text" : "metadata-only";
}

NotificationPrivacy parsePrivacy(std::string_view rValue)
{
    if (rValue == "metadata-only")
        return NotificationPrivacy::MetadataOnly;
    if (rValue == "safe-display-text")
        return NotificationPrivacy::SafeDisplayText;
    throw NotificationDataError("invalid notification privacy class");
}

bool isLowerHex(std::string_view rValue)
{
    return std::all_of(rValue.begin(), rValue.end(), [](unsigned char c)
                       { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
}

OUString decodeUtf8Strict(const std::string& rValue)
{
    OUString aValue = OUString::fromUtf8(rValue);
    if (OUStringToOString(aValue, RTL_TEXTENCODING_UTF8) != rValue)
        throw NotificationDataError("notification text is not valid UTF-8");
    return aValue;
}

void requirePrimitive(const boost::property_tree::ptree& rNode)
{
    if (!rNode.empty())
        throw NotificationDataError("expected a primitive JSON value");
}

void requireExactKeys(const boost::property_tree::ptree& rNode,
                      std::initializer_list<std::string_view> aAllowed)
{
    std::map<std::string, unsigned int> aSeen;
    for (const auto& rChild : rNode)
    {
        if (std::find(aAllowed.begin(), aAllowed.end(), rChild.first) == aAllowed.end())
            throw NotificationDataError("unknown notification JSON property");
        if (++aSeen[rChild.first] != 1)
            throw NotificationDataError("duplicate notification JSON property");
    }
    if (aSeen.size() != aAllowed.size())
        throw NotificationDataError("missing notification JSON property");
}

template <typename T> T primitive(const boost::property_tree::ptree& rNode, std::string_view rName)
{
    auto aIt = rNode.find(std::string(rName));
    if (aIt == rNode.not_found())
        throw NotificationDataError("missing notification JSON property");
    requirePrimitive(aIt->second);
    try
    {
        return aIt->second.get_value<T>();
    }
    catch (const boost::property_tree::ptree_error&)
    {
        throw NotificationDataError("invalid notification JSON value");
    }
}

void validateRecord(const NotificationRecord& rRecord)
{
    switch (rRecord.Severity)
    {
        case NotificationSeverity::Information:
        case NotificationSeverity::Success:
        case NotificationSeverity::Warning:
        case NotificationSeverity::Error:
            break;
        default:
            throw NotificationDataError("invalid notification severity");
    }
    switch (rRecord.Folder)
    {
        case NotificationFolder::Inbox:
        case NotificationFolder::Archived:
        case NotificationFolder::Deleted:
            break;
        default:
            throw NotificationDataError("invalid notification folder");
    }
    switch (rRecord.PreviousFolder)
    {
        case NotificationFolder::Inbox:
        case NotificationFolder::Archived:
            break;
        case NotificationFolder::Deleted:
        default:
            throw NotificationDataError("invalid notification restore folder");
    }
    if (rRecord.Privacy != NotificationPrivacy::MetadataOnly
        && rRecord.Privacy != NotificationPrivacy::SafeDisplayText)
        throw NotificationDataError("invalid notification privacy class");
    if (!isValidRecordId(rRecord.Id))
        throw NotificationDataError("invalid notification ID");
    if (!isValidSource(rRecord.Source))
        throw NotificationDataError("invalid notification source");
    if (!isValidSha256(rRecord.DedupeHash))
        throw NotificationDataError("invalid notification dedupe hash");
    if (rRecord.CreatedAt < 0 || rRecord.UpdatedAt < rRecord.CreatedAt || rRecord.DeletedAt < 0)
        throw NotificationDataError("invalid notification timestamp");
    if ((rRecord.Folder == NotificationFolder::Deleted) != (rRecord.DeletedAt != 0))
        throw NotificationDataError("invalid notification tombstone");
    if (rRecord.Title.getLength() > MaxTitleLength || rRecord.Body.getLength() > MaxBodyLength)
        throw NotificationDataError("notification display text is too long");
    if (rRecord.Privacy == NotificationPrivacy::MetadataOnly
        && (!rRecord.Title.isEmpty() || !rRecord.Body.isEmpty()))
        throw NotificationDataError("metadata-only notification contains display text");
    if (rRecord.Privacy == NotificationPrivacy::SafeDisplayText
        && (!isApprovedSafeDisplaySource(rRecord.Source) || !isSafeDisplayText(rRecord.Title)
            || !isSafeDisplayText(rRecord.Body)))
        throw NotificationDataError("notification display text failed the privacy guard");
}
}

bool isValidRecordId(std::string_view rId) { return rId.size() == 32 && isLowerHex(rId); }

bool isValidSource(std::string_view rSource)
{
    if (rSource.empty() || rSource.size() > 64)
        return false;
    return std::all_of(rSource.begin(), rSource.end(), [](unsigned char c)
                       { return std::isalnum(c) || c == '.' || c == '_' || c == '-'; });
}

bool isValidSha256(std::string_view rHash)
{
    return rHash.empty() || (rHash.size() == 64 && isLowerHex(rHash));
}

bool isApprovedSafeDisplaySource(std::string_view rSource)
{
    // This convention is intentionally small and auditable, but Source is caller-supplied and is
    // not an authentication boundary. Integrations must force untrusted callers to metadata-only;
    // this allowlist and the heuristic screen are additional defense in depth.
    static constexpr std::array<std::string_view, 4> Approved = {
        "libreoffice.core-ui",
        "libreoffice.notification",
        "libreoffice.update",
        "cppunit",
    };
    return std::find(Approved.begin(), Approved.end(), rSource) != Approved.end();
}

bool isSafeDisplayText(std::u16string_view rText)
{
    for (sal_Unicode c : rText)
    {
        if ((c < 0x20 && c != '\n' && c != '\t') || c == 0x7f)
            return false;
    }

    OUString aLower(rText);
    aLower = aLower.toAsciiLowerCase();
    static constexpr std::array<std::u16string_view, 17> aForbidden = {
        u"://",         u"file:",   u".uno:",    u"\\",      u"/home/",      u"/users/",
        u"/documents/", u"/mnt/",   u"password", u"passwd",  u"token=",      u"authorization:",
        u"bearer ",     u"api_key", u"apikey",   u"secret=", u"private key",
    };
    if (std::any_of(aForbidden.begin(), aForbidden.end(), [&aLower](std::u16string_view rNeedle)
                    { return aLower.indexOf(rNeedle) >= 0; }))
        return false;

    for (sal_Int32 i = 0; i + 2 < aLower.getLength(); ++i)
    {
        if (((aLower[i] >= 'a' && aLower[i] <= 'z')) && aLower[i + 1] == ':'
            && aLower[i + 2] == '/')
            return false;
    }
    return true;
}

std::string serializeRecords(const RecordMap& rRecords)
{
    if (rRecords.size() > MaxRecordCount)
        throw NotificationDataError("notification record limit exceeded");

    tools::JsonWriter aWriter;
    aWriter.put("schema", 1);
    {
        auto aRecords = aWriter.startArray("records");
        for (const auto& [rId, rRecord] : rRecords)
        {
            (void)rId;
            validateRecord(rRecord);
            auto aObject = aWriter.startStruct();
            aWriter.put("id", rRecord.Id);
            aWriter.put("source", rRecord.Source);
            aWriter.put("severity", severityName(rRecord.Severity));
            aWriter.put("folder", folderName(rRecord.Folder));
            aWriter.put("previousFolder", folderName(rRecord.PreviousFolder));
            aWriter.put("privacy", privacyName(rRecord.Privacy));
            aWriter.put("read", rRecord.Read);
            aWriter.put("pinned", rRecord.Pinned);
            aWriter.put("createdAt", rRecord.CreatedAt);
            aWriter.put("updatedAt", rRecord.UpdatedAt);
            aWriter.put("deletedAt", rRecord.DeletedAt);
            aWriter.put("title", rRecord.Title);
            aWriter.put("body", rRecord.Body);
            aWriter.put("dedupeHash", rRecord.DedupeHash);
        }
    }
    OString aJson = aWriter.finishAndGetAsOString();
    if (static_cast<std::size_t>(aJson.getLength()) > MaxSnapshotBytes)
        throw NotificationDataError("notification snapshot limit exceeded");
    return std::string(aJson.getStr(), aJson.getLength());
}

RecordMap parseRecords(std::string_view rJson)
{
    if (rJson.size() > MaxSnapshotBytes)
        throw NotificationDataError("notification snapshot limit exceeded");

    boost::property_tree::ptree aRoot;
    try
    {
        std::stringstream aStream{ std::string(rJson) };
        boost::property_tree::read_json(aStream, aRoot);
    }
    catch (const boost::property_tree::json_parser_error&)
    {
        throw NotificationDataError("invalid notification JSON");
    }

    requireExactKeys(aRoot, { "schema", "records" });
    if (primitive<sal_Int32>(aRoot, "schema") != 1)
        throw NotificationDataError("unsupported notification schema");

    auto aRecordsNode = aRoot.find("records");
    if (aRecordsNode == aRoot.not_found())
        throw NotificationDataError("missing notification records");

    RecordMap aRecords;
    for (const auto& rEntry : aRecordsNode->second)
    {
        if (!rEntry.first.empty())
            throw NotificationDataError("notification records must be a JSON array");
        if (aRecords.size() >= MaxRecordCount)
            throw NotificationDataError("notification record limit exceeded");

        const auto& rNode = rEntry.second;
        requireExactKeys(rNode, { "id", "source", "severity", "folder", "previousFolder", "privacy",
                                  "read", "pinned", "createdAt", "updatedAt", "deletedAt", "title",
                                  "body", "dedupeHash" });

        NotificationRecord aRecord;
        aRecord.Id = primitive<std::string>(rNode, "id");
        aRecord.Source = primitive<std::string>(rNode, "source");
        aRecord.Severity = parseSeverity(primitive<std::string>(rNode, "severity"));
        aRecord.Folder = parseFolder(primitive<std::string>(rNode, "folder"));
        aRecord.PreviousFolder = parseFolder(primitive<std::string>(rNode, "previousFolder"));
        aRecord.Privacy = parsePrivacy(primitive<std::string>(rNode, "privacy"));
        aRecord.Read = primitive<bool>(rNode, "read");
        aRecord.Pinned = primitive<bool>(rNode, "pinned");
        aRecord.CreatedAt = primitive<sal_Int64>(rNode, "createdAt");
        aRecord.UpdatedAt = primitive<sal_Int64>(rNode, "updatedAt");
        aRecord.DeletedAt = primitive<sal_Int64>(rNode, "deletedAt");
        aRecord.Title = decodeUtf8Strict(primitive<std::string>(rNode, "title"));
        aRecord.Body = decodeUtf8Strict(primitive<std::string>(rNode, "body"));
        aRecord.DedupeHash = primitive<std::string>(rNode, "dedupeHash");
        validateRecord(aRecord);
        if (!aRecords.emplace(aRecord.Id, aRecord).second)
            throw NotificationDataError("duplicate notification ID");
    }
    return aRecords;
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
