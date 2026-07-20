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

namespace sfx2::notification_detail
{
/** Typed adapter around the generated org.openoffice.Office.UI.NotificationCenter accessors. */
class NotificationConfiguration final
{
public:
    static NotificationPreferences read();
    static void write(const NotificationPreferences& rPreferences);
};
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
