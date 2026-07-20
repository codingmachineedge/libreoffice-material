/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationConfiguration.hxx"

#include <comphelper/configuration.hxx>
#include <officecfg/Office/UI/NotificationCenter.hxx>

namespace sfx2::notification_detail
{
NotificationPreferences NotificationConfiguration::read()
{
    NotificationPreferences aPreferences;
    aPreferences.Enabled = officecfg::Office::UI::NotificationCenter::Display::Enabled::get();
    aPreferences.MaxVisible = officecfg::Office::UI::NotificationCenter::Display::MaxVisible::get();
    aPreferences.Width = officecfg::Office::UI::NotificationCenter::Display::Width::get();
    aPreferences.TimeoutSeconds
        = officecfg::Office::UI::NotificationCenter::Display::TimeoutSeconds::get();
    aPreferences.HorizontalInset
        = officecfg::Office::UI::NotificationCenter::Display::HorizontalInset::get();
    aPreferences.VerticalInset
        = officecfg::Office::UI::NotificationCenter::Display::VerticalInset::get();
    aPreferences.CornerRadius
        = officecfg::Office::UI::NotificationCenter::Display::CornerRadius::get();
    aPreferences.OpacityPercent
        = officecfg::Office::UI::NotificationCenter::Display::OpacityPercent::get();
    aPreferences.UseThemeColors
        = officecfg::Office::UI::NotificationCenter::Display::UseThemeColors::get();
    aPreferences.AccentColor
        = officecfg::Office::UI::NotificationCenter::Display::AccentColor::get();
    aPreferences.Animations = officecfg::Office::UI::NotificationCenter::Display::Animations::get();
    aPreferences.HistoryRetentionDays
        = officecfg::Office::UI::NotificationCenter::History::RetentionDays::get();
    aPreferences.HistoryLimit = officecfg::Office::UI::NotificationCenter::History::Limit::get();
    return normalizeNotificationPreferences(aPreferences);
}

void NotificationConfiguration::write(const NotificationPreferences& rPreferences)
{
    const NotificationPreferences aPreferences = normalizeNotificationPreferences(rPreferences);
    auto xChanges = comphelper::ConfigurationChanges::create();
    officecfg::Office::UI::NotificationCenter::Display::Enabled::set(aPreferences.Enabled,
                                                                     xChanges);
    officecfg::Office::UI::NotificationCenter::Display::MaxVisible::set(aPreferences.MaxVisible,
                                                                        xChanges);
    officecfg::Office::UI::NotificationCenter::Display::Width::set(aPreferences.Width, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::TimeoutSeconds::set(
        aPreferences.TimeoutSeconds, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::HorizontalInset::set(
        aPreferences.HorizontalInset, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::VerticalInset::set(
        aPreferences.VerticalInset, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::CornerRadius::set(aPreferences.CornerRadius,
                                                                          xChanges);
    officecfg::Office::UI::NotificationCenter::Display::OpacityPercent::set(
        aPreferences.OpacityPercent, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::UseThemeColors::set(
        aPreferences.UseThemeColors, xChanges);
    officecfg::Office::UI::NotificationCenter::Display::AccentColor::set(aPreferences.AccentColor,
                                                                         xChanges);
    officecfg::Office::UI::NotificationCenter::Display::Animations::set(aPreferences.Animations,
                                                                        xChanges);
    officecfg::Office::UI::NotificationCenter::History::RetentionDays::set(
        aPreferences.HistoryRetentionDays, xChanges);
    officecfg::Office::UI::NotificationCenter::History::Limit::set(aPreferences.HistoryLimit,
                                                                   xChanges);
    xChanges->commit();
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
