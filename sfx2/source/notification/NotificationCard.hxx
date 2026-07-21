/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include "NotificationViewModel.hxx"

#include <tools/link.hxx>

#include <memory>

namespace weld
{
class Builder;
class Button;
class CustomWeld;
class Image;
class Label;
class Widget;
}

namespace sfx2
{
class NotificationSeverityStrip;

/**
 * One compact bottom-right notification card, built from notificationcard.ui into a stack container.
 * Bound to a single display row; exposes Details and Dismiss outputs keyed by the record id. The
 * card never renders redacted text: it consumes the already-redacted NotificationDisplayRow.
 */
class NotificationCard final
{
public:
    NotificationCard(weld::Widget* pParent, const NotificationDisplayRow& rRow,
                     const NotificationPreferences& rPreferences);
    ~NotificationCard();

    weld::Widget* getWidget() const;

    void SetDetailsHdl(const Link<const OString&, void>& rLink) { m_aDetailsHdl = rLink; }
    void SetDismissHdl(const Link<const OString&, void>& rLink) { m_aDismissHdl = rLink; }

private:
    OString m_aId;
    Link<const OString&, void> m_aDetailsHdl;
    Link<const OString&, void> m_aDismissHdl;

    std::unique_ptr<weld::Builder> m_xBuilder;
    std::unique_ptr<weld::Widget> m_xTop;
    std::unique_ptr<weld::Image> m_xSevIcon;
    std::unique_ptr<weld::Label> m_xTitle;
    std::unique_ptr<weld::Label> m_xTime;
    std::unique_ptr<weld::Label> m_xBody;
    std::unique_ptr<weld::Label> m_xSource;
    std::unique_ptr<weld::Label> m_xCommit;
    std::unique_ptr<weld::Button> m_xDetails;
    std::unique_ptr<weld::Button> m_xDismiss;
    std::unique_ptr<NotificationSeverityStrip> m_xStrip;
    std::unique_ptr<weld::CustomWeld> m_xStripWeld;

    DECL_LINK(DetailsClickHdl, weld::Button&, void);
    DECL_LINK(DismissClickHdl, weld::Button&, void);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
