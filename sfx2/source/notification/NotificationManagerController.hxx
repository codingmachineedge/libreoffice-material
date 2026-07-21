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

#include <sfx2/notificationcenter.hxx>

#include <tools/link.hxx>
#include <vcl/vclptr.hxx>
#include <vcl/weld/TreeView.hxx>

#include <functional>
#include <memory>
#include <optional>
#include <set>
#include <vector>

namespace vcl
{
class Window;
}
namespace weld
{
class Button;
class CheckButton;
class ItemView;
class Label;
class MenuButton;
class Toggleable;
class ToggleButton;
class Widget;
}

namespace sfx2
{
class NotificationPresenter;
class NotificationOverlayWindow;

/**
 * Lazy notification manager overlay. A non-dialog surface anchored bottom-right of the owner work
 * area. Reads only the retained snapshot + view-model; every bulk action passes the complete selected
 * id vector to exactly one service method (INV-6). No text search field this checkpoint (INV-2):
 * filtering is folder tab + severity/source/sort menu buttons.
 */
class NotificationManagerController final
{
public:
    NotificationManagerController(NotificationPresenter& rPresenter, vcl::Window* pOwner);
    ~NotificationManagerController();

    void SetSnapshot(const NotificationCenterSnapshotRef& xSnapshot);
    void Show(const OString& rFocusId);
    void Hide();
    bool IsVisible() const;
    void Reanchor(vcl::Window* pOwner);

private:
    NotificationPresenter& m_rPresenter;
    VclPtr<NotificationOverlayWindow> m_xOverlay;
    NotificationCenterSnapshotRef m_xSnapshot;

    NotificationView m_eView = NotificationView::Inbox;
    std::optional<NotificationSeverity> m_oSeverityFilter;
    OString m_aSourceFilter;
    NotificationSortOrder m_eSort = NotificationSortOrder::Newest;
    std::set<OString> m_aSelection;
    OString m_aFocusId;

    // Header + tabs
    std::unique_ptr<weld::Label> m_xHeaderTitle;
    std::unique_ptr<weld::Button> m_xClose;
    std::unique_ptr<weld::ToggleButton> m_xTabInbox;
    std::unique_ptr<weld::ToggleButton> m_xTabUnread;
    std::unique_ptr<weld::ToggleButton> m_xTabArchived;
    std::unique_ptr<weld::ToggleButton> m_xTabDeleted;
    std::unique_ptr<weld::ToggleButton> m_xTabHistory;
    std::unique_ptr<weld::ToggleButton> m_xTabCustomize;

    // Filter + sort
    std::unique_ptr<weld::Widget> m_xFilterBar;
    std::unique_ptr<weld::MenuButton> m_xSevFilter;
    std::unique_ptr<weld::MenuButton> m_xSrcFilter;
    std::unique_ptr<weld::MenuButton> m_xSortButton;

    // Bulk bar
    std::unique_ptr<weld::Widget> m_xBulkBar;
    std::unique_ptr<weld::CheckButton> m_xSelectAll;
    std::unique_ptr<weld::Label> m_xSelectedLabel;
    std::unique_ptr<weld::Button> m_xBulkRead;
    std::unique_ptr<weld::Button> m_xBulkArchive;
    std::unique_ptr<weld::Button> m_xBulkDelete;
    std::unique_ptr<weld::Button> m_xBulkPin;
    std::unique_ptr<weld::Button> m_xUndo;
    std::unique_ptr<weld::MenuButton> m_xMaintenance;

    // Panels
    std::unique_ptr<weld::Widget> m_xListPanel;
    std::unique_ptr<weld::Widget> m_xHistoryPanel;
    std::unique_ptr<weld::Widget> m_xCustomizePanel;

    // List + detail
    std::unique_ptr<weld::TreeView> m_xList;
    std::unique_ptr<weld::Label> m_xDetailSeverity;
    std::unique_ptr<weld::Label> m_xDetailTitle;
    std::unique_ptr<weld::Label> m_xDetailBody;
    std::unique_ptr<weld::Label> m_xDetailSource;
    std::unique_ptr<weld::Label> m_xDetailCreated;
    std::unique_ptr<weld::Label> m_xDetailRecord;
    std::unique_ptr<weld::Label> m_xDetailPinned;
    std::unique_ptr<weld::Button> m_xDetailRead;
    std::unique_ptr<weld::Button> m_xDetailArchive;
    std::unique_ptr<weld::Button> m_xDetailDelete;
    std::unique_ptr<weld::Button> m_xDetailPin;

    // History
    std::unique_ptr<weld::Button> m_xUndo2;
    std::unique_ptr<weld::TreeView> m_xHistory;

    // Customize (toggle-button groups; never combo/entry per INV-2)
    std::unique_ptr<weld::ToggleButton> m_xPrefWidthCompact;
    std::unique_ptr<weld::ToggleButton> m_xPrefWidthStandard;
    std::unique_ptr<weld::ToggleButton> m_xPrefWidthWide;
    std::unique_ptr<weld::ToggleButton> m_xPrefVisible1;
    std::unique_ptr<weld::ToggleButton> m_xPrefVisible3;
    std::unique_ptr<weld::ToggleButton> m_xPrefVisible5;
    std::unique_ptr<weld::ToggleButton> m_xPrefDismissOff;
    std::unique_ptr<weld::ToggleButton> m_xPrefDismiss5;
    std::unique_ptr<weld::ToggleButton> m_xPrefDismiss10;
    std::unique_ptr<weld::ToggleButton> m_xPrefAnimations;

    void Create(vcl::Window* pOwner);
    void RepopulateAll();
    void UpdateTabs(const NotificationCounts& rCounts);
    void UpdateVisibility();
    void PopulateSourceFilter();
    void PopulateList();
    void PopulateDetail();
    void PopulateHistory();
    void SyncCustomizeControls();
    std::vector<OString> BuildSelectionVector() const;
    void SubmitBulk(const std::function<void(NotificationCenterService&, std::vector<OString>)>& rCall);
    void ApplyPreferences(const NotificationPreferences& rPreferences);

    DECL_LINK(CloseHdl, weld::Button&, void);
    DECL_LINK(TabHdl, weld::Toggleable&, void);
    DECL_LINK(SelectAllHdl, weld::Toggleable&, void);
    DECL_LINK(SevFilterHdl, const OUString&, void);
    DECL_LINK(SrcFilterHdl, const OUString&, void);
    DECL_LINK(SortHdl, const OUString&, void);
    DECL_LINK(MaintenanceHdl, const OUString&, void);
    DECL_LINK(BulkReadHdl, weld::Button&, void);
    DECL_LINK(BulkArchiveHdl, weld::Button&, void);
    DECL_LINK(BulkDeleteHdl, weld::Button&, void);
    DECL_LINK(BulkPinHdl, weld::Button&, void);
    DECL_LINK(UndoHdl, weld::Button&, void);
    DECL_LINK(ListSelectHdl, weld::ItemView&, void);
    DECL_LINK(ListToggleHdl, const weld::TreeView::iter_col&, void);
    DECL_LINK(DetailReadHdl, weld::Button&, void);
    DECL_LINK(DetailArchiveHdl, weld::Button&, void);
    DECL_LINK(DetailDeleteHdl, weld::Button&, void);
    DECL_LINK(DetailPinHdl, weld::Button&, void);
    DECL_LINK(PrefWidthHdl, weld::Toggleable&, void);
    DECL_LINK(PrefVisibleHdl, weld::Toggleable&, void);
    DECL_LINK(PrefDismissHdl, weld::Toggleable&, void);
    DECL_LINK(PrefAnimationsHdl, weld::Toggleable&, void);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
