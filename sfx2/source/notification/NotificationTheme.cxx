/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationTheme.hxx"

#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>

#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>

namespace sfx2
{
OUString NotificationTheme::GetSeverityIconName(NotificationSeverity eSeverity)
{
    // Reuse the infobar severity-glyph convention so the notification icons match existing feedback.
    switch (eSeverity)
    {
        case NotificationSeverity::Information:
            return u"vcl/res/infobox.png"_ustr;
        case NotificationSeverity::Success:
            return u"vcl/res/successbox.png"_ustr;
        case NotificationSeverity::Warning:
            return u"vcl/res/warningbox.png"_ustr;
        case NotificationSeverity::Error:
            return u"vcl/res/errorbox.png"_ustr;
    }
    // Total mapping: every enumerator returns above. This is unreachable and mirrors Information.
    return u"vcl/res/infobox.png"_ustr;
}

NotificationAccentRole NotificationTheme::GetSeverityAccentRole(NotificationSeverity eSeverity)
{
    switch (eSeverity)
    {
        case NotificationSeverity::Information:
            return NotificationAccentRole::Accent;
        case NotificationSeverity::Success:
            return NotificationAccentRole::Success;
        case NotificationSeverity::Warning:
            return NotificationAccentRole::Warning;
        case NotificationSeverity::Error:
            return NotificationAccentRole::Error;
    }
    return NotificationAccentRole::Accent;
}

OUString NotificationTheme::GetSeverityLabel(NotificationSeverity eSeverity)
{
    switch (eSeverity)
    {
        case NotificationSeverity::Information:
            return SfxResId(STR_NOTIF_SEVERITY_INFORMATION);
        case NotificationSeverity::Success:
            return SfxResId(STR_NOTIF_SEVERITY_SUCCESS);
        case NotificationSeverity::Warning:
            return SfxResId(STR_NOTIF_SEVERITY_WARNING);
        case NotificationSeverity::Error:
            return SfxResId(STR_NOTIF_SEVERITY_ERROR);
    }
    return SfxResId(STR_NOTIF_SEVERITY_INFORMATION);
}

Color NotificationTheme::ResolveAccentColor(NotificationSeverity eSeverity,
                                            const NotificationPreferences& rPreferences)
{
    const StyleSettings& rStyle = Application::GetSettings().GetStyleSettings();

    // High contrast: restore the StyleSettings baseline and bypass Material tokens. Color remains
    // redundant with the severity icon and label, so window text keeps the strip meaningful.
    if (rStyle.GetHighContrastMode())
        return rStyle.GetWindowTextColor();

    switch (GetSeverityAccentRole(eSeverity))
    {
        case NotificationAccentRole::Error:
            return rStyle.GetErrorColor();
        case NotificationAccentRole::Warning:
            return rStyle.GetWarningColor();
        case NotificationAccentRole::Success:
            // The palette has no dedicated success slot; use a resolved green kept redundant with the
            // success icon and label rather than inventing a parallel token.
            return Color(0x2E, 0x7D, 0x32);
        case NotificationAccentRole::Accent:
            if (rPreferences.AccentColor >= 0 && !rPreferences.UseThemeColors)
                return Color(ColorTransparency,
                             static_cast<sal_uInt32>(rPreferences.AccentColor));
            return rStyle.GetAccentColor();
    }
    return rStyle.GetAccentColor();
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
