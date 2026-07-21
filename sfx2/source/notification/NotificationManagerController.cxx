/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include "NotificationManagerController.hxx"
#include "NotificationOverlayWindow.hxx"
#include "NotificationPresenter.hxx"
#include "NotificationTheme.hxx"

#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>

#include <vcl/svapp.hxx>
#include <vcl/weld/Builder.hxx>
#include <vcl/weld/Button.hxx>
#include <vcl/weld/CheckButton.hxx>
#include <vcl/weld/Label.hxx>
#include <vcl/weld/MenuButton.hxx>
#include <vcl/weld/ToggleButton.hxx>
#include <vcl/weld/TreeView.hxx>

#include <algorithm>
#include <utility>

namespace sfx2
{
namespace
{
const NotificationRecord* lclFindRecord(const NotificationCenterSnapshot& rSnapshot,
                                        const OString& rId)
{
    if (rId.isEmpty())
        return nullptr;
    for (const NotificationRecord& rRecord : rSnapshot.Records)
    {
        if (rRecord.Id == rId)
            return &rRecord;
    }
    return nullptr;
}

void lclEnforceRadio(weld::Toggleable& rActive, std::initializer_list<weld::Toggleable*> aGroup)
{
    // Radio behavior for a pill-toggle group: the clicked control stays active, siblings clear.
    for (weld::Toggleable* pButton : aGroup)
    {
        if (pButton)
            pButton->set_active(pButton == &rActive);
    }
}
} // namespace

NotificationManagerController::NotificationManagerController(NotificationPresenter& rPresenter,
                                                            vcl::Window* pOwner)
    : m_rPresenter(rPresenter)
{
    Create(pOwner);
}

NotificationManagerController::~NotificationManagerController()
{
    if (m_xOverlay)
        m_xOverlay.disposeAndClear();
}

bool NotificationManagerController::IsVisible() const { return m_xOverlay && m_xOverlay->IsVisible(); }

void NotificationManagerController::Create(vcl::Window* pOwner)
{
    if (!pOwner)
        return;

    // Focus-retaining variant: the manager is explicitly opened and traps focus while open.
    m_xOverlay = VclPtr<NotificationOverlayWindow>::Create(
        pOwner, u"sfx/ui/notificationmanager.ui"_ustr, u"NotificationManager"_ustr,
        /*bAllowCycleFocusOut*/ false);

    weld::Builder& r = m_xOverlay->GetBuilder();
    m_xHeaderTitle = r.weld_label(u"header_title"_ustr);
    m_xClose = r.weld_button(u"close_button"_ustr);
    m_xTabInbox = r.weld_toggle_button(u"tab_inbox"_ustr);
    m_xTabUnread = r.weld_toggle_button(u"tab_unread"_ustr);
    m_xTabArchived = r.weld_toggle_button(u"tab_archived"_ustr);
    m_xTabDeleted = r.weld_toggle_button(u"tab_deleted"_ustr);
    m_xTabHistory = r.weld_toggle_button(u"tab_history"_ustr);
    m_xTabCustomize = r.weld_toggle_button(u"tab_customize"_ustr);

    m_xFilterBar = r.weld_widget(u"filter_bar"_ustr);
    m_xSevFilter = r.weld_menu_button(u"sev_filter"_ustr);
    m_xSrcFilter = r.weld_menu_button(u"src_filter"_ustr);
    m_xSortButton = r.weld_menu_button(u"sort_button"_ustr);

    m_xBulkBar = r.weld_widget(u"bulk_bar"_ustr);
    m_xSelectAll = r.weld_check_button(u"select_all"_ustr);
    m_xSelectedLabel = r.weld_label(u"selected_label"_ustr);
    m_xBulkRead = r.weld_button(u"bulk_read"_ustr);
    m_xBulkArchive = r.weld_button(u"bulk_archive"_ustr);
    m_xBulkDelete = r.weld_button(u"bulk_delete"_ustr);
    m_xBulkPin = r.weld_button(u"bulk_pin"_ustr);
    m_xUndo = r.weld_button(u"undo_button"_ustr);
    m_xMaintenance = r.weld_menu_button(u"maintenance_menu"_ustr);

    m_xListPanel = r.weld_widget(u"list_panel"_ustr);
    m_xHistoryPanel = r.weld_widget(u"history_panel"_ustr);
    m_xCustomizePanel = r.weld_widget(u"customize_panel"_ustr);

    m_xList = r.weld_tree_view(u"list_view"_ustr);
    m_xDetailSeverity = r.weld_label(u"detail_severity"_ustr);
    m_xDetailTitle = r.weld_label(u"detail_title"_ustr);
    m_xDetailBody = r.weld_label(u"detail_body"_ustr);
    m_xDetailSource = r.weld_label(u"detail_source"_ustr);
    m_xDetailCreated = r.weld_label(u"detail_created"_ustr);
    m_xDetailRecord = r.weld_label(u"detail_record"_ustr);
    m_xDetailPinned = r.weld_label(u"detail_pinned"_ustr);
    m_xDetailRead = r.weld_button(u"detail_read"_ustr);
    m_xDetailArchive = r.weld_button(u"detail_archive"_ustr);
    m_xDetailDelete = r.weld_button(u"detail_delete"_ustr);
    m_xDetailPin = r.weld_button(u"detail_pin"_ustr);

    m_xUndo2 = r.weld_button(u"undo_button2"_ustr);
    m_xHistory = r.weld_tree_view(u"history_view"_ustr);

    m_xPrefWidthCompact = r.weld_toggle_button(u"pref_width_compact"_ustr);
    m_xPrefWidthStandard = r.weld_toggle_button(u"pref_width_standard"_ustr);
    m_xPrefWidthWide = r.weld_toggle_button(u"pref_width_wide"_ustr);
    m_xPrefVisible1 = r.weld_toggle_button(u"pref_visible_1"_ustr);
    m_xPrefVisible3 = r.weld_toggle_button(u"pref_visible_3"_ustr);
    m_xPrefVisible5 = r.weld_toggle_button(u"pref_visible_5"_ustr);
    m_xPrefDismissOff = r.weld_toggle_button(u"pref_dismiss_off"_ustr);
    m_xPrefDismiss5 = r.weld_toggle_button(u"pref_dismiss_5"_ustr);
    m_xPrefDismiss10 = r.weld_toggle_button(u"pref_dismiss_10"_ustr);
    m_xPrefAnimations = r.weld_toggle_button(u"pref_animations"_ustr);

    m_xOverlay->GetBuilder().weld_widget(u"NotificationManager"_ustr)
        ->set_accessible_name(SfxResId(STR_NOTIF_MANAGER_ACCESSIBLE));

    // List: multi-select with a checkbox column. Check is the default toggle type for this
    // TreeView, so enable_toggle_buttons() takes no argument.
    m_xList->set_selection_mode(SelectionMode::Multiple);
    m_xList->enable_toggle_buttons();

    // Severity filter menu.
    m_xSevFilter->append_item(u"all"_ustr, SfxResId(STR_NOTIF_FILTER_ALL_SEVERITIES));
    m_xSevFilter->append_item(u"info"_ustr, SfxResId(STR_NOTIF_SEVERITY_INFORMATION));
    m_xSevFilter->append_item(u"success"_ustr, SfxResId(STR_NOTIF_SEVERITY_SUCCESS));
    m_xSevFilter->append_item(u"warning"_ustr, SfxResId(STR_NOTIF_SEVERITY_WARNING));
    m_xSevFilter->append_item(u"error"_ustr, SfxResId(STR_NOTIF_SEVERITY_ERROR));

    // Source filter menu: seeded with the "all" reset item; the per-source items are rebuilt from the
    // snapshot in PopulateSourceFilter().
    m_xSrcFilter->append_item(u"all"_ustr, SfxResId(STR_NOTIF_FILTER_ALL_SOURCES));

    // Sort menu.
    m_xSortButton->append_item(u"newest"_ustr, SfxResId(STR_NOTIF_SORT_NEWEST));
    m_xSortButton->append_item(u"oldest"_ustr, SfxResId(STR_NOTIF_SORT_OLDEST));
    m_xSortButton->append_item(u"source"_ustr, SfxResId(STR_NOTIF_SORT_SOURCE));

    // Maintenance menu.
    m_xMaintenance->append_item(u"dedupe"_ustr, SfxResId(STR_NOTIF_MAINT_DEDUPE));
    m_xMaintenance->append_item(u"empty"_ustr, SfxResId(STR_NOTIF_MAINT_EMPTY));
    m_xMaintenance->append_item(u"maintain"_ustr, SfxResId(STR_NOTIF_MAINT_MAINTAIN));

    // History list columns are read-only text.
    m_xHistory->set_selection_mode(SelectionMode::Single);

    // Wire handlers.
    m_xClose->connect_clicked(LINK(this, NotificationManagerController, CloseHdl));
    m_xTabInbox->connect_toggled(LINK(this, NotificationManagerController, TabHdl));
    m_xTabUnread->connect_toggled(LINK(this, NotificationManagerController, TabHdl));
    m_xTabArchived->connect_toggled(LINK(this, NotificationManagerController, TabHdl));
    m_xTabDeleted->connect_toggled(LINK(this, NotificationManagerController, TabHdl));
    m_xTabHistory->connect_toggled(LINK(this, NotificationManagerController, TabHdl));
    m_xTabCustomize->connect_toggled(LINK(this, NotificationManagerController, TabHdl));

    m_xSevFilter->connect_selected(LINK(this, NotificationManagerController, SevFilterHdl));
    m_xSrcFilter->connect_selected(LINK(this, NotificationManagerController, SrcFilterHdl));
    m_xSortButton->connect_selected(LINK(this, NotificationManagerController, SortHdl));
    m_xMaintenance->connect_selected(LINK(this, NotificationManagerController, MaintenanceHdl));

    m_xSelectAll->connect_toggled(LINK(this, NotificationManagerController, SelectAllHdl));
    m_xBulkRead->connect_clicked(LINK(this, NotificationManagerController, BulkReadHdl));
    m_xBulkArchive->connect_clicked(LINK(this, NotificationManagerController, BulkArchiveHdl));
    m_xBulkDelete->connect_clicked(LINK(this, NotificationManagerController, BulkDeleteHdl));
    m_xBulkPin->connect_clicked(LINK(this, NotificationManagerController, BulkPinHdl));
    m_xUndo->connect_clicked(LINK(this, NotificationManagerController, UndoHdl));

    m_xList->connect_selection_changed(LINK(this, NotificationManagerController, ListSelectHdl));
    m_xList->connect_toggled(LINK(this, NotificationManagerController, ListToggleHdl));

    m_xDetailRead->connect_clicked(LINK(this, NotificationManagerController, DetailReadHdl));
    m_xDetailArchive->connect_clicked(LINK(this, NotificationManagerController, DetailArchiveHdl));
    m_xDetailDelete->connect_clicked(LINK(this, NotificationManagerController, DetailDeleteHdl));
    m_xDetailPin->connect_clicked(LINK(this, NotificationManagerController, DetailPinHdl));

    m_xUndo2->connect_clicked(LINK(this, NotificationManagerController, UndoHdl));

    m_xPrefWidthCompact->connect_toggled(LINK(this, NotificationManagerController, PrefWidthHdl));
    m_xPrefWidthStandard->connect_toggled(LINK(this, NotificationManagerController, PrefWidthHdl));
    m_xPrefWidthWide->connect_toggled(LINK(this, NotificationManagerController, PrefWidthHdl));
    m_xPrefVisible1->connect_toggled(LINK(this, NotificationManagerController, PrefVisibleHdl));
    m_xPrefVisible3->connect_toggled(LINK(this, NotificationManagerController, PrefVisibleHdl));
    m_xPrefVisible5->connect_toggled(LINK(this, NotificationManagerController, PrefVisibleHdl));
    m_xPrefDismissOff->connect_toggled(LINK(this, NotificationManagerController, PrefDismissHdl));
    m_xPrefDismiss5->connect_toggled(LINK(this, NotificationManagerController, PrefDismissHdl));
    m_xPrefDismiss10->connect_toggled(LINK(this, NotificationManagerController, PrefDismissHdl));
    m_xPrefAnimations->connect_toggled(LINK(this, NotificationManagerController, PrefAnimationsHdl));

    m_xTabInbox->set_active(true);
}

void NotificationManagerController::Reanchor(vcl::Window* pOwner)
{
    const bool bWasVisible = IsVisible();
    if (m_xOverlay)
        m_xOverlay.disposeAndClear();
    Create(pOwner);
    RepopulateAll();
    if (bWasVisible)
        Show(m_aFocusId);
}

void NotificationManagerController::SetSnapshot(const NotificationCenterSnapshotRef& xSnapshot)
{
    m_xSnapshot = xSnapshot;
    if (m_xSnapshot)
        m_aSelection = NotificationViewModel::ReconcileSelection(m_aSelection, *m_xSnapshot);
    RepopulateAll();
}

void NotificationManagerController::Show(const OString& rFocusId)
{
    if (!m_xOverlay || !m_xSnapshot)
        return;
    if (!rFocusId.isEmpty())
    {
        m_aFocusId = rFocusId;
        // Focus a specific record from a card: switch to the folder-neutral Inbox list.
        m_eView = NotificationView::Inbox;
        m_xTabInbox->set_active(true);
        RepopulateAll();
    }
    const NotificationPreferences& rPrefs = m_xSnapshot->Preferences;
    m_xOverlay->RepositionBottomRight(rPrefs.HorizontalInset, rPrefs.VerticalInset, 820);
    m_xOverlay->GrabFocus();
}

void NotificationManagerController::Hide()
{
    if (m_xOverlay)
        m_xOverlay->Hide();
}

std::vector<OString> NotificationManagerController::BuildSelectionVector() const
{
    if (!m_xSnapshot)
        return {};
    return NotificationViewModel::SelectionVector(m_aSelection, *m_xSnapshot);
}

void NotificationManagerController::SubmitBulk(
    const std::function<void(NotificationCenterService&, std::vector<OString>)>& rCall)
{
    // INV-6: build exactly one vector and hand it to one service method.
    std::vector<OString> aIds = BuildSelectionVector();
    if (aIds.empty())
        return;
    rCall(m_rPresenter.GetService(), std::move(aIds));
}

void NotificationManagerController::ApplyPreferences(const NotificationPreferences& rPreferences)
{
    m_rPresenter.GetService().setPreferences(rPreferences, m_rPresenter.MakeRefreshCompletion());
}

void NotificationManagerController::RepopulateAll()
{
    if (!m_xOverlay || !m_xSnapshot)
        return;
    const NotificationCounts aCounts = NotificationViewModel::Counts(*m_xSnapshot);
    UpdateTabs(aCounts);
    UpdateVisibility();
    PopulateSourceFilter();
    PopulateList();
    PopulateDetail();
    PopulateHistory();
    SyncCustomizeControls();
}

void NotificationManagerController::UpdateTabs(const NotificationCounts& rCounts)
{
    auto label = [](const OUString& rBase, sal_uInt32 nCount) {
        return SfxResId(STR_NOTIF_TAB_COUNT)
            .replaceFirst(u"%1"_ustr, rBase)
            .replaceFirst(u"%2"_ustr, OUString::number(nCount));
    };
    m_xTabInbox->set_label(label(SfxResId(STR_NOTIF_TAB_INBOX), rCounts.Inbox));
    m_xTabUnread->set_label(label(SfxResId(STR_NOTIF_TAB_UNREAD), rCounts.Unread));
    m_xTabArchived->set_label(label(SfxResId(STR_NOTIF_TAB_ARCHIVED), rCounts.Archived));
    m_xTabDeleted->set_label(label(SfxResId(STR_NOTIF_TAB_DELETED), rCounts.Deleted));
    m_xTabHistory->set_label(SfxResId(STR_NOTIF_TAB_HISTORY));
    m_xTabCustomize->set_label(SfxResId(STR_NOTIF_TAB_CUSTOMIZE));
}

void NotificationManagerController::UpdateVisibility()
{
    const bool bHistory = m_xTabHistory->get_active();
    const bool bCustomize = m_xTabCustomize->get_active();
    const bool bList = !bHistory && !bCustomize;

    m_xFilterBar->set_visible(bList);
    m_xBulkBar->set_visible(bList);
    m_xListPanel->set_visible(bList);
    m_xHistoryPanel->set_visible(bHistory);
    m_xCustomizePanel->set_visible(bCustomize);

    // Restore/Delete label swap for the Deleted folder.
    m_xBulkDelete->set_label(m_eView == NotificationView::Deleted ? SfxResId(STR_NOTIF_RESTORE)
                                                                  : SfxResId(STR_NOTIF_DELETE));
}

void NotificationManagerController::PopulateSourceFilter()
{
    if (!m_xSrcFilter || !m_xSnapshot)
        return;

    // Rebuild the dynamic per-source items from the snapshot, keeping the fixed "all" reset item. The
    // slugs are non-sensitive (the store forbids paths in Source), so they are safe to surface.
    m_xSrcFilter->clear();
    m_xSrcFilter->append_item(u"all"_ustr, SfxResId(STR_NOTIF_FILTER_ALL_SOURCES));

    const std::vector<OString> aSources = NotificationViewModel::DistinctSources(*m_xSnapshot);
    bool bActiveStillPresent = m_aSourceFilter.isEmpty();
    for (const OString& rSource : aSources)
    {
        m_xSrcFilter->append_item(OStringToOUString(rSource, RTL_TEXTENCODING_UTF8),
                                  NotificationViewModel::SourceLabel(rSource));
        if (rSource == m_aSourceFilter)
            bActiveStillPresent = true;
    }

    // If the previously selected source vanished from the snapshot, fall back to showing all sources.
    if (!bActiveStillPresent)
        m_aSourceFilter.clear();
}

void NotificationManagerController::PopulateList()
{
    if (!m_xListPanel->get_visible())
        return;

    m_xList->freeze();
    m_xList->clear();
    const std::vector<NotificationDisplayRow> aRows = NotificationViewModel::RowsForView(
        *m_xSnapshot, m_eView, m_oSeverityFilter, m_aSourceFilter, m_eSort);
    for (const NotificationDisplayRow& rRow : aRows)
    {
        m_xList->append();
        const int nRow = m_xList->n_children() - 1;
        const bool bSelected = m_aSelection.count(rRow.Id) != 0;
        m_xList->set_toggle(nRow, bSelected ? TRISTATE_TRUE : TRISTATE_FALSE);

        OUString aPrimary
            = NotificationTheme::GetSeverityLabel(rRow.Severity) + u": "_ustr + rRow.DisplayTitle;
        if (rRow.Unread)
            aPrimary += u" •"_ustr;
        m_xList->set_text(nRow, aPrimary, 0);
        m_xList->set_text(nRow, rRow.SourceLabel + u" · "_ustr + rRow.RelativeTime, 1);
        m_xList->set_id(nRow, OStringToOUString(rRow.Id, RTL_TEXTENCODING_UTF8));
    }
    m_xList->thaw();

    // Reflect focus selection in the tree.
    if (!m_aFocusId.isEmpty())
    {
        const OUString aFocus = OStringToOUString(m_aFocusId, RTL_TEXTENCODING_UTF8);
        for (int i = 0; i < m_xList->n_children(); ++i)
        {
            if (m_xList->get_id(i) == aFocus)
            {
                m_xList->select(i);
                break;
            }
        }
    }

    const std::vector<OString> aSelected = BuildSelectionVector();
    m_xSelectedLabel->set_label(
        SfxResId(STR_NOTIF_SELECTED)
            .replaceFirst(u"%1"_ustr, OUString::number(aSelected.size())));
    const bool bHasSelection = !aSelected.empty();
    m_xBulkRead->set_sensitive(bHasSelection);
    m_xBulkArchive->set_sensitive(bHasSelection);
    m_xBulkDelete->set_sensitive(bHasSelection);
    m_xBulkPin->set_sensitive(bHasSelection);
    m_xSelectAll->set_active(bHasSelection && aSelected.size() == aRows.size() && !aRows.empty());
}

void NotificationManagerController::PopulateDetail()
{
    const NotificationRecord* pRecord
        = m_xSnapshot ? lclFindRecord(*m_xSnapshot, m_aFocusId) : nullptr;
    const bool bHas = pRecord != nullptr;

    m_xDetailRead->set_sensitive(bHas);
    m_xDetailArchive->set_sensitive(bHas);
    m_xDetailDelete->set_sensitive(bHas);
    m_xDetailPin->set_sensitive(bHas);
    if (!bHas)
    {
        m_xDetailTitle->set_label(OUString());
        m_xDetailBody->set_label(OUString());
        m_xDetailSeverity->set_label(OUString());
        m_xDetailSource->set_label(OUString());
        m_xDetailCreated->set_label(OUString());
        m_xDetailRecord->set_label(OUString());
        m_xDetailPinned->set_label(OUString());
        return;
    }

    const NotificationDisplayRow aRow = NotificationViewModel::MakeRow(*pRecord);
    m_xDetailSeverity->set_label(NotificationTheme::GetSeverityLabel(aRow.Severity));
    m_xDetailTitle->set_label(aRow.DisplayTitle);
    m_xDetailBody->set_label(aRow.DisplayBody);
    m_xDetailSource->set_label(aRow.SourceLabel);
    m_xDetailCreated->set_label(aRow.RelativeTime);
    m_xDetailRecord->set_label(OStringToOUString(aRow.Id, RTL_TEXTENCODING_UTF8));
    m_xDetailPinned->set_label(aRow.Pinned ? SfxResId(STR_NOTIF_UNPIN) : SfxResId(STR_NOTIF_PIN));

    // Available actions follow the record's folder/read state.
    const bool bDeleted = pRecord->Folder == NotificationFolder::Deleted;
    m_xDetailRead->set_label(pRecord->Read ? SfxResId(STR_NOTIF_MARK_UNREAD)
                                           : SfxResId(STR_NOTIF_MARK_READ));
    m_xDetailArchive->set_visible(!bDeleted);
    m_xDetailDelete->set_label(bDeleted ? SfxResId(STR_NOTIF_RESTORE) : SfxResId(STR_NOTIF_DELETE));
    m_xDetailPin->set_label(pRecord->Pinned ? SfxResId(STR_NOTIF_UNPIN) : SfxResId(STR_NOTIF_PIN));

    const OUString aVerbArchive = SfxResId(STR_NOTIF_ACTION_FOR_RECORD)
                                      .replaceFirst(u"%1"_ustr, SfxResId(STR_NOTIF_ARCHIVE))
                                      .replaceFirst(u"%2"_ustr, aRow.DisplayTitle);
    m_xDetailArchive->set_accessible_name(aVerbArchive);
}

void NotificationManagerController::PopulateHistory()
{
    if (!m_xHistoryPanel->get_visible())
        return;
    m_xHistory->freeze();
    m_xHistory->clear();
    for (const NotificationHistoryEntry& rEntry : m_xSnapshot->History)
    {
        m_xHistory->append();
        const int nRow = m_xHistory->n_children() - 1;
        OString aShort = rEntry.CommitId;
        if (aShort.getLength() > 7)
            aShort = aShort.copy(0, 7);
        m_xHistory->set_text(nRow, OStringToOUString(aShort, RTL_TEXTENCODING_ASCII_US), 0);
        m_xHistory->set_text(nRow, OUString::number(rEntry.Affected), 1);
        m_xHistory->set_id(nRow, OStringToOUString(rEntry.CommitId, RTL_TEXTENCODING_ASCII_US));
    }
    m_xHistory->thaw();
}

void NotificationManagerController::SyncCustomizeControls()
{
    if (!m_xSnapshot)
        return;
    const NotificationPreferences& rPrefs = m_xSnapshot->Preferences;

    m_xPrefWidthCompact->set_active(rPrefs.Width < 380);
    m_xPrefWidthStandard->set_active(rPrefs.Width >= 380 && rPrefs.Width < 460);
    m_xPrefWidthWide->set_active(rPrefs.Width >= 460);

    m_xPrefVisible1->set_active(rPrefs.MaxVisible <= 1);
    m_xPrefVisible3->set_active(rPrefs.MaxVisible > 1 && rPrefs.MaxVisible <= 3);
    m_xPrefVisible5->set_active(rPrefs.MaxVisible > 3);

    m_xPrefDismissOff->set_active(rPrefs.TimeoutSeconds <= 0);
    m_xPrefDismiss5->set_active(rPrefs.TimeoutSeconds > 0 && rPrefs.TimeoutSeconds <= 5);
    m_xPrefDismiss10->set_active(rPrefs.TimeoutSeconds > 5);

    m_xPrefAnimations->set_active(rPrefs.Animations);
}

// --- handlers ---------------------------------------------------------------------------------

IMPL_LINK_NOARG(NotificationManagerController, CloseHdl, weld::Button&, void)
{
    m_rPresenter.CloseManager();
}

IMPL_LINK(NotificationManagerController, TabHdl, weld::Toggleable&, rToggle, void)
{
    if (!rToggle.get_active())
        return;
    // Radio behavior across the tab row.
    lclEnforceRadio(rToggle, { m_xTabInbox.get(), m_xTabUnread.get(), m_xTabArchived.get(),
                               m_xTabDeleted.get(), m_xTabHistory.get(), m_xTabCustomize.get() });

    if (&rToggle == m_xTabInbox.get())
        m_eView = NotificationView::Inbox;
    else if (&rToggle == m_xTabUnread.get())
        m_eView = NotificationView::Unread;
    else if (&rToggle == m_xTabArchived.get())
        m_eView = NotificationView::Archived;
    else if (&rToggle == m_xTabDeleted.get())
        m_eView = NotificationView::Deleted;
    RepopulateAll();
}

IMPL_LINK(NotificationManagerController, SelectAllHdl, weld::Toggleable&, rToggle, void)
{
    if (!m_xSnapshot)
        return;
    const std::vector<NotificationDisplayRow> aRows = NotificationViewModel::RowsForView(
        *m_xSnapshot, m_eView, m_oSeverityFilter, m_aSourceFilter, m_eSort);
    if (rToggle.get_active())
    {
        for (const NotificationDisplayRow& rRow : aRows)
            m_aSelection.insert(rRow.Id);
    }
    else
    {
        for (const NotificationDisplayRow& rRow : aRows)
            m_aSelection.erase(rRow.Id);
    }
    PopulateList();
}

IMPL_LINK(NotificationManagerController, SevFilterHdl, const OUString&, rIdent, void)
{
    if (rIdent == u"info")
        m_oSeverityFilter = NotificationSeverity::Information;
    else if (rIdent == u"success")
        m_oSeverityFilter = NotificationSeverity::Success;
    else if (rIdent == u"warning")
        m_oSeverityFilter = NotificationSeverity::Warning;
    else if (rIdent == u"error")
        m_oSeverityFilter = NotificationSeverity::Error;
    else
        m_oSeverityFilter.reset();
    PopulateList();
}

IMPL_LINK(NotificationManagerController, SrcFilterHdl, const OUString&, rIdent, void)
{
    m_aSourceFilter = rIdent == u"all" ? OString() : rIdent.toUtf8();
    PopulateList();
}

IMPL_LINK(NotificationManagerController, SortHdl, const OUString&, rIdent, void)
{
    if (rIdent == u"oldest")
        m_eSort = NotificationSortOrder::Oldest;
    else if (rIdent == u"source")
        m_eSort = NotificationSortOrder::Source;
    else
        m_eSort = NotificationSortOrder::Newest;
    PopulateList();
}

IMPL_LINK(NotificationManagerController, MaintenanceHdl, const OUString&, rIdent, void)
{
    NotificationCenterService& rSvc = m_rPresenter.GetService();
    if (rIdent == u"dedupe")
        rSvc.deduplicate(m_rPresenter.MakeRefreshCompletion());
    else if (rIdent == u"empty")
        rSvc.emptyTrash(m_rPresenter.MakeRefreshCompletion());
    else if (rIdent == u"maintain")
        rSvc.maintain(m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationManagerController, BulkReadHdl, weld::Button&, void)
{
    SubmitBulk([this](NotificationCenterService& rSvc, std::vector<OString> aIds) {
        rSvc.markRead(std::move(aIds), /*bRead*/ true, m_rPresenter.MakeRefreshCompletion());
    });
}

IMPL_LINK_NOARG(NotificationManagerController, BulkArchiveHdl, weld::Button&, void)
{
    SubmitBulk([this](NotificationCenterService& rSvc, std::vector<OString> aIds) {
        rSvc.archive(std::move(aIds), m_rPresenter.MakeRefreshCompletion());
    });
}

IMPL_LINK_NOARG(NotificationManagerController, BulkDeleteHdl, weld::Button&, void)
{
    const bool bRestore = m_eView == NotificationView::Deleted;
    SubmitBulk([this, bRestore](NotificationCenterService& rSvc, std::vector<OString> aIds) {
        if (bRestore)
            rSvc.restore(std::move(aIds), m_rPresenter.MakeRefreshCompletion());
        else
            rSvc.remove(std::move(aIds), m_rPresenter.MakeRefreshCompletion());
    });
}

IMPL_LINK_NOARG(NotificationManagerController, BulkPinHdl, weld::Button&, void)
{
    SubmitBulk([this](NotificationCenterService& rSvc, std::vector<OString> aIds) {
        rSvc.setPinned(std::move(aIds), /*bPinned*/ true, m_rPresenter.MakeRefreshCompletion());
    });
}

IMPL_LINK_NOARG(NotificationManagerController, UndoHdl, weld::Button&, void)
{
    if (!m_xSnapshot)
        return;
    const OString aCommit = NotificationViewModel::LatestUndoableCommit(*m_xSnapshot);
    if (aCommit.isEmpty())
        return;
    m_rPresenter.GetService().undo(aCommit, m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationManagerController, ListSelectHdl, weld::ItemView&, void)
{
    const OUString aId = m_xList->get_selected_id();
    m_aFocusId = aId.isEmpty() ? OString() : aId.toUtf8();
    PopulateDetail();
}

IMPL_LINK(NotificationManagerController, ListToggleHdl, const weld::TreeView::iter_col&, rRowCol, void)
{
    const OUString aId = m_xList->get_id(rRowCol.first);
    if (aId.isEmpty())
        return;
    const OString aKey = aId.toUtf8();
    if (m_xList->get_toggle(rRowCol.first) == TRISTATE_TRUE)
        m_aSelection.insert(aKey);
    else
        m_aSelection.erase(aKey);
    PopulateList();
}

IMPL_LINK_NOARG(NotificationManagerController, DetailReadHdl, weld::Button&, void)
{
    const NotificationRecord* pRecord
        = m_xSnapshot ? lclFindRecord(*m_xSnapshot, m_aFocusId) : nullptr;
    if (!pRecord)
        return;
    m_rPresenter.GetService().markRead({ pRecord->Id }, /*bRead*/ !pRecord->Read,
                                       m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationManagerController, DetailArchiveHdl, weld::Button&, void)
{
    if (m_aFocusId.isEmpty())
        return;
    m_rPresenter.GetService().archive({ m_aFocusId }, m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationManagerController, DetailDeleteHdl, weld::Button&, void)
{
    const NotificationRecord* pRecord
        = m_xSnapshot ? lclFindRecord(*m_xSnapshot, m_aFocusId) : nullptr;
    if (!pRecord)
        return;
    // A recoverable tombstone: delete is not a modal confirm here, and restore reverses it.
    if (pRecord->Folder == NotificationFolder::Deleted)
        m_rPresenter.GetService().restore({ pRecord->Id }, m_rPresenter.MakeRefreshCompletion());
    else
        m_rPresenter.GetService().remove({ pRecord->Id }, m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK_NOARG(NotificationManagerController, DetailPinHdl, weld::Button&, void)
{
    const NotificationRecord* pRecord
        = m_xSnapshot ? lclFindRecord(*m_xSnapshot, m_aFocusId) : nullptr;
    if (!pRecord)
        return;
    m_rPresenter.GetService().setPinned({ pRecord->Id }, /*bPinned*/ !pRecord->Pinned,
                                        m_rPresenter.MakeRefreshCompletion());
}

IMPL_LINK(NotificationManagerController, PrefWidthHdl, weld::Toggleable&, rToggle, void)
{
    if (!rToggle.get_active() || !m_xSnapshot)
        return;
    lclEnforceRadio(rToggle, { m_xPrefWidthCompact.get(), m_xPrefWidthStandard.get(),
                               m_xPrefWidthWide.get() });
    NotificationPreferences aPrefs = m_xSnapshot->Preferences;
    if (&rToggle == m_xPrefWidthCompact.get())
        aPrefs.Width = 340;
    else if (&rToggle == m_xPrefWidthStandard.get())
        aPrefs.Width = 420;
    else
        aPrefs.Width = 480;
    ApplyPreferences(aPrefs);
}

IMPL_LINK(NotificationManagerController, PrefVisibleHdl, weld::Toggleable&, rToggle, void)
{
    if (!rToggle.get_active() || !m_xSnapshot)
        return;
    lclEnforceRadio(rToggle,
                    { m_xPrefVisible1.get(), m_xPrefVisible3.get(), m_xPrefVisible5.get() });
    NotificationPreferences aPrefs = m_xSnapshot->Preferences;
    if (&rToggle == m_xPrefVisible1.get())
        aPrefs.MaxVisible = 1;
    else if (&rToggle == m_xPrefVisible3.get())
        aPrefs.MaxVisible = 3;
    else
        aPrefs.MaxVisible = 5;
    ApplyPreferences(aPrefs);
}

IMPL_LINK(NotificationManagerController, PrefDismissHdl, weld::Toggleable&, rToggle, void)
{
    if (!rToggle.get_active() || !m_xSnapshot)
        return;
    lclEnforceRadio(rToggle,
                    { m_xPrefDismissOff.get(), m_xPrefDismiss5.get(), m_xPrefDismiss10.get() });
    NotificationPreferences aPrefs = m_xSnapshot->Preferences;
    if (&rToggle == m_xPrefDismissOff.get())
        aPrefs.TimeoutSeconds = 0;
    else if (&rToggle == m_xPrefDismiss5.get())
        aPrefs.TimeoutSeconds = 5;
    else
        aPrefs.TimeoutSeconds = 10;
    ApplyPreferences(aPrefs);
}

IMPL_LINK(NotificationManagerController, PrefAnimationsHdl, weld::Toggleable&, rToggle, void)
{
    if (!m_xSnapshot)
        return;
    NotificationPreferences aPrefs = m_xSnapshot->Preferences;
    aPrefs.Animations = rToggle.get_active();
    ApplyPreferences(aPrefs);
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
