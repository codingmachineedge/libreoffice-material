/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <QtInstancePopover.hxx>
#include <QtInstancePopover.moc>

#include <QtGui/QGuiApplication>
#include <QtGui/QScreen>

#include <algorithm>

QtInstancePopover::QtInstancePopover(QWidget* pWidget)
    : QtInstanceContainer(pWidget)
{
}

void QtInstancePopover::popup_at_rect(weld::Widget* pParent, const tools::Rectangle& rRect,
                                      weld::Placement ePlace)
{
    SolarMutexGuard g;

    assert(ePlace == weld::Placement::Under && "placement type not supported yet");
    (void)ePlace;

    GetQtInstance().RunInMainThread([&] {
        QWidget* pPopoverWidget = getQWidget();
        QWidget* pParentWidget = QtInstance::GetQWidget(pParent);
        const QPoint aAnchor = pParentWidget->mapToGlobal(toQPoint(rRect.BottomLeft()));
        QScreen* pScreen = QGuiApplication::screenAt(aAnchor);
        if (!pScreen)
            pScreen = pParentWidget->screen();
        if (!pScreen)
            pScreen = QGuiApplication::primaryScreen();

        QRect aWorkArea;
        if (pScreen)
        {
            aWorkArea = pScreen->availableGeometry();
            const QSize aAvailable = aWorkArea.size();
            pPopoverWidget->setMinimumSize(pPopoverWidget->minimumSize().boundedTo(aAvailable));
            pPopoverWidget->setMaximumSize(aAvailable);
        }
        pPopoverWidget->adjustSize();
        if (pScreen)
            pPopoverWidget->resize(pPopoverWidget->size().boundedTo(aWorkArea.size()));

        QPoint aPos = aAnchor;
        aPos.setX(aPos.x() + rRect.GetWidth() - pPopoverWidget->width() / 2);
        if (pScreen)
        {
            const int nMaximumX
                = std::max(aWorkArea.left(), aWorkArea.right() - pPopoverWidget->width() + 1);
            const int nMaximumY
                = std::max(aWorkArea.top(), aWorkArea.bottom() - pPopoverWidget->height() + 1);
            aPos.setX(std::clamp(aPos.x(), aWorkArea.left(), nMaximumX));
            aPos.setY(std::clamp(aPos.y(), aWorkArea.top(), nMaximumY));
        }

        pPopoverWidget->move(aPos);
        pPopoverWidget->show();
    });
}

void QtInstancePopover::popdown()
{
    SolarMutexGuard g;

    GetQtInstance().RunInMainThread([&] { getQWidget()->hide(); });
}

void QtInstancePopover::resize_to_request() { assert(false && "Not implemented yet"); }

bool QtInstancePopover::eventFilter(QObject* pObject, QEvent* pEvent)
{
    if (pObject == getQWidget() && pEvent->type() == QEvent::Close)
    {
        // signal that the popup was closed when control returns to the
        // main loop (at which point the event to close the popup has
        // actually been processed)
        QMetaObject::invokeMethod(this,
                                  [this] {
                                      SolarMutexGuard g;
                                      signal_closed();
                                  },
                                  Qt::QueuedConnection);
    }

    return QtInstanceWidget::eventFilter(pObject, pEvent);
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab cinoptions=b1,g0,N-s cinkeys+=0=break: */
