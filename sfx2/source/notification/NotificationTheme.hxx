/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/dllapi.h>
#include <sfx2/notificationcenter.hxx>

#include <tools/color.hxx>
#include <rtl/ustring.hxx>

namespace sfx2
{
/** Semantic accent role a severity resolves to. Kept separate from the concrete color so the
    severity mapping is a pure, total function that unit tests can exercise without VCL. */
enum class NotificationAccentRole
{
    Accent, ///< theme accent / primary (Information, and Success where no success role exists)
    Success, ///< resolved success role (green), color kept redundant with icon + label
    Warning,
    Error
};

/**
 * Material feedback tokens resolved within the weld constraints. Standard weld widgets already
 * inherit Material shape/type/color from the compiled native theme; only the severity accent color,
 * severity icon, and the custom 4px strip need bespoke resolution here.
 */
class SFX2_DLLPUBLIC NotificationTheme
{
public:
    /** Total severity -> icon-name mapping (reuses the infobar severity glyph convention). Pure. */
    static OUString GetSeverityIconName(NotificationSeverity eSeverity);

    /** Total severity -> accent-role mapping. Pure; no default fallthrough. */
    static NotificationAccentRole GetSeverityAccentRole(NotificationSeverity eSeverity);

    /** Localized severity label ("Information"/"Success"/"Warning"/"Error"). */
    static OUString GetSeverityLabel(NotificationSeverity eSeverity);

    /** Resolve the concrete severity accent color from semantic StyleSettings feedback slots,
        honoring an explicit preference accent for Information when theme colors are disabled. In
        resolved high contrast this returns system window-text so color stays meaningful. */
    static Color ResolveAccentColor(NotificationSeverity eSeverity,
                                    const NotificationPreferences& rPreferences);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
