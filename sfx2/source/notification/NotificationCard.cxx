/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationCard.hxx"
#include "NotificationTheme.hxx"

#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>

#include <vcl/outdev.hxx>
#include <vcl/svapp.hxx>
#include <vcl/weld/Builder.hxx>
#include <vcl/weld/Button.hxx>
#include <vcl/weld/Image.hxx>
#include <vcl/weld/Label.hxx>
#include <vcl/weld/customweld.hxx>

#include <algorithm>

namespace sfx2
{
/** 4px severity bar painted in the resolved accent, honoring the preference corner radius. In
    resolved high contrast the accent resolves to system window-text so the strip stays meaningful. */
class NotificationSeverityStrip final : public weld::CustomWidgetController
{
public:
    NotificationSeverityStrip(NotificationSeverity eSeverity,
                              const NotificationPreferences& rPreferences)
        : m_eSeverity(eSeverity)
        , m_nCornerRadius(std::clamp<sal_Int32>(rPreferences.CornerRadius, 0, 32))
        , m_bUseThemeColors(rPreferences.UseThemeColors)
        , m_nAccentColor(rPreferences.AccentColor)
    {
    }

    virtual void SetDrawingArea(weld::DrawingArea* pDrawingArea) override
    {
        weld::CustomWidgetController::SetDrawingArea(pDrawingArea);
        set_size_request(4, -1);
    }

    virtual void Paint(vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect) override
    {
        NotificationPreferences aPrefs;
        aPrefs.UseThemeColors = m_bUseThemeColors;
        aPrefs.AccentColor = m_nAccentColor;
        const Color aAccent = NotificationTheme::ResolveAccentColor(m_eSeverity, aPrefs);

        rRenderContext.SetLineColor();
        rRenderContext.SetFillColor(aAccent);
        const sal_uInt32 nRound = static_cast<sal_uInt32>(m_nCornerRadius);
        rRenderContext.DrawRect(rRect, nRound, nRound);
    }

private:
    NotificationSeverity m_eSeverity;
    sal_Int32 m_nCornerRadius;
    bool m_bUseThemeColors;
    sal_Int32 m_nAccentColor;
};

NotificationCard::NotificationCard(weld::Widget* pParent, const NotificationDisplayRow& rRow,
                                   const NotificationPreferences& rPreferences)
    : m_aId(rRow.Id)
    , m_xBuilder(Application::CreateBuilder(pParent, u"sfx/ui/notificationcard.ui"_ustr))
    , m_xTop(m_xBuilder->weld_widget(u"NotificationCard"_ustr))
    , m_xSevIcon(m_xBuilder->weld_image(u"sev_icon"_ustr))
    , m_xTitle(m_xBuilder->weld_label(u"title"_ustr))
    , m_xTime(m_xBuilder->weld_label(u"time"_ustr))
    , m_xBody(m_xBuilder->weld_label(u"body"_ustr))
    , m_xSource(m_xBuilder->weld_label(u"source"_ustr))
    , m_xCommit(m_xBuilder->weld_label(u"commit"_ustr))
    , m_xDetails(m_xBuilder->weld_button(u"details_button"_ustr))
    , m_xDismiss(m_xBuilder->weld_button(u"dismiss_button"_ustr))
    , m_xStrip(std::make_unique<NotificationSeverityStrip>(rRow.Severity, rPreferences))
    , m_xStripWeld(std::make_unique<weld::CustomWeld>(*m_xBuilder, u"sev_strip"_ustr, *m_xStrip))
{
    m_xSevIcon->set_from_icon_name(NotificationTheme::GetSeverityIconName(rRow.Severity));

    m_xTitle->set_label(rRow.DisplayTitle);
    m_xTime->set_label(rRow.RelativeTime);
    m_xSource->set_label(rRow.SourceLabel);

    if (rRow.Redacted || rRow.DisplayBody.isEmpty())
        m_xBody->set_visible(false);
    else
        m_xBody->set_label(rRow.DisplayBody);

    if (rRow.ShortCommit.isEmpty())
        m_xCommit->set_visible(false);
    else
        m_xCommit->set_label(OStringToOUString(rRow.ShortCommit, RTL_TEXTENCODING_ASCII_US));

    // Accessibility: name carries severity + title (redacted rows use the generic title); the
    // announcement is reinforcement, never the sole record.
    const OUString aSeverityLabel = NotificationTheme::GetSeverityLabel(rRow.Severity);
    m_xTop->set_accessible_name(SfxResId(STR_NOTIF_CARD_ACCESSIBLE)
                                    .replaceFirst(u"%1"_ustr, aSeverityLabel)
                                    .replaceFirst(u"%2"_ustr, rRow.DisplayTitle));
    m_xDismiss->set_accessible_name(
        SfxResId(STR_NOTIF_DISMISS).replaceFirst(u"%1"_ustr, rRow.DisplayTitle));

    m_xDetails->connect_clicked(LINK(this, NotificationCard, DetailsClickHdl));
    m_xDismiss->connect_clicked(LINK(this, NotificationCard, DismissClickHdl));
}

NotificationCard::~NotificationCard() {}

weld::Widget* NotificationCard::getWidget() const { return m_xTop.get(); }

IMPL_LINK_NOARG(NotificationCard, DetailsClickHdl, weld::Button&, void)
{
    m_aDetailsHdl.Call(m_aId);
}

IMPL_LINK_NOARG(NotificationCard, DismissClickHdl, weld::Button&, void)
{
    m_aDismissHdl.Call(m_aId);
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
