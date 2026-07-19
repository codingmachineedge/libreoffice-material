/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * This file incorporates work covered by the following license notice:
 *
 *   Licensed to the Apache Software Foundation (ASF) under one or more
 *   contributor license agreements. See the NOTICE file distributed
 *   with this work for additional information regarding copyright
 *   ownership. The ASF licenses this file to you under the Apache
 *   License, Version 2.0 (the "License"); you may not use this file
 *   except in compliance with the License. You may obtain a copy of
 *   the License at http://www.apache.org/licenses/LICENSE-2.0 .
 */

#pragma once

#include <rtl/ustring.hxx>
#include <vector>

struct DownloadSource
{
    bool IsDirect;
    OUString URL;
    OUString Sha256;
    sal_Int64 Size;
    OUString ReleaseTag;
    OUString FileName;

    DownloadSource(bool bIsDirect, const OUString& aURL, const OUString& aSha256 = OUString(),
                   sal_Int64 nSize = -1, const OUString& aReleaseTag = OUString(),
                   const OUString& aFileName = OUString())
        : IsDirect(bIsDirect)
        , URL(aURL)
        , Sha256(aSha256)
        , Size(nSize)
        , ReleaseTag(aReleaseTag)
        , FileName(aFileName)
    {
    }
    DownloadSource(const DownloadSource& ds)
        : IsDirect(ds.IsDirect)
        , URL(ds.URL)
        , Sha256(ds.Sha256)
        , Size(ds.Size)
        , ReleaseTag(ds.ReleaseTag)
        , FileName(ds.FileName)
    {
    }

    DownloadSource& operator=(const DownloadSource& ds)
    {
        IsDirect = ds.IsDirect;
        URL = ds.URL;
        Sha256 = ds.Sha256;
        Size = ds.Size;
        ReleaseTag = ds.ReleaseTag;
        FileName = ds.FileName;
        return *this;
    }
};

struct ReleaseNote
{
    sal_uInt8 Pos;
    OUString URL;
    sal_uInt8 Pos2;
    OUString URL2;

    ReleaseNote(sal_uInt8 pos, const OUString& aURL) : Pos(pos), URL(aURL), Pos2(0), URL2() {};

    ReleaseNote(const ReleaseNote& rn) :Pos(rn.Pos), URL(rn.URL), Pos2(rn.Pos2), URL2(rn.URL2) {};
    ReleaseNote & operator=( const ReleaseNote& rn) { Pos=rn.Pos; URL=rn.URL; Pos2=rn.Pos2; URL2=rn.URL2; return *this; };
};

struct UpdateInfo
{
    OUString BuildId;
    OUString Version;
    OUString Description;
    std::vector< DownloadSource > Sources;
    std::vector< ReleaseNote > ReleaseNotes;
};

// Returns the URL of the release note for the given position
OUString getReleaseNote(const UpdateInfo& rInfo, sal_uInt8 pos, bool autoDownloadEnabled=false);

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
