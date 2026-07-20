/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/notificationcenter.hxx>

#include <map>
#include <stdexcept>
#include <string>

namespace sfx2::notification_detail
{
using RecordMap = std::map<OString, NotificationRecord>;

inline constexpr std::size_t MaxRecordCount = 5000;
inline constexpr std::size_t MaxSnapshotBytes = 16 * 1024 * 1024;
inline constexpr sal_Int32 MaxTitleLength = 256;
inline constexpr sal_Int32 MaxBodyLength = 2048;

class NotificationDataError final : public std::runtime_error
{
public:
    explicit NotificationDataError(const std::string& rMessage)
        : std::runtime_error(rMessage)
    {
    }
};

std::string serializeRecords(const RecordMap& rRecords);
RecordMap parseRecords(std::string_view rJson);

bool isValidRecordId(std::string_view rId);
bool isValidSource(std::string_view rSource);
bool isValidSha256(std::string_view rHash);
bool isSafeDisplayText(std::u16string_view rText);
bool isApprovedSafeDisplaySource(std::string_view rSource);
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
