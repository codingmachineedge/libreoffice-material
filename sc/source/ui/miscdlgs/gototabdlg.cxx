/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#undef SC_DLLIMPLEMENTATION

#include <gototabdlg.hxx>
#include <sfx2/RegexSearchController.hxx>
#include <unotools/textsearch.hxx>
#include <vcl/vclenum.hxx>
#include <vcl/weld/Builder.hxx>
#include <vcl/weld/Dialog.hxx>

ScGoToTabDlg::ScGoToTabDlg(weld::Window* pParent)
    : GenericDialogController(pParent, u"modules/scalc/ui/gotosheetdialog.ui"_ustr,
                              u"GoToSheetDialog"_ustr)
    , m_xFrameMask(m_xBuilder->weld_frame(u"frame-mask"_ustr))
    , m_xEnNameMask(m_xBuilder->weld_entry(u"entry-mask"_ustr))
    , m_xRegexBuilderButton(m_xBuilder->weld_button(u"entry-mask_regex_builder"_ustr))
    , m_xFrameSheets(m_xBuilder->weld_frame(u"frame-sheets"_ustr))
    , m_xLb(m_xBuilder->weld_tree_view(u"treeview"_ustr))
{
    m_xLb->set_selection_mode(SelectionMode::Single);
    m_xLb->set_size_request(-1, m_xLb->get_height_rows(10));
    m_xLb->connect_item_activated(LINK(this, ScGoToTabDlg, DblClkHdl));
    m_xRegexSearchController = std::make_unique<sfx2::RegexSearchController>(
        m_xDialog.get(), *m_xEnNameMask, *m_xRegexBuilderButton,
        LINK(this, ScGoToTabDlg, FindNameHdl));

    // Preserve the legacy literal, case-sensitive default until the user explicitly chooses
    // different settings in the advanced builder.
    sfx2::RegexSearchState aState = m_xRegexSearchController->GetState();
    aState.Mode = sfx2::RegexSearchMode::Literal;
    aState.Flags.CaseInsensitive = false;
    m_xRegexSearchController->SetState(aState);
}

ScGoToTabDlg::~ScGoToTabDlg() {}

void ScGoToTabDlg::SetDescription(const OUString& rTitle, const OUString& rEntryLabel,
                                  const OUString& rListLabel, const OUString& rDlgHelpId,
                                  const OUString& rEnHelpId, const OUString& rLbHelpId)
{
    m_xDialog->set_title(rTitle);
    m_xFrameMask->set_label(rEntryLabel);
    m_xFrameSheets->set_label(rListLabel);
    m_xDialog->set_help_id(rDlgHelpId);
    m_xEnNameMask->set_help_id(rEnHelpId);
    m_xLb->set_help_id(rLbHelpId);
}

void ScGoToTabDlg::Insert(const OUString& rString, bool bSelected)
{
    maCacheSheetsNames.push_back(rString);
    m_xLb->append_text(rString);
    if (bSelected)
        m_xLb->select(m_xLb->n_children() - 1);
}

OUString ScGoToTabDlg::GetSelectedEntry() const { return m_xLb->get_selected_text(); }

IMPL_LINK_NOARG(ScGoToTabDlg, DblClkHdl, const weld::TreeIter&, bool)
{
    m_xDialog->response(RET_OK);
    return true;
}

IMPL_LINK_NOARG(ScGoToTabDlg, FindNameHdl, weld::TextWidget&, void)
{
    const sfx2::RegexSearchState& rState = m_xRegexSearchController->GetState();
    const bool bEmpty = rState.Pattern.isEmpty();
    const bool bValid = bEmpty || sfx2::RegexSearchService::Validate(rState).IsValid;
    // TextSearch intentionally equates straight and typographic quotes in literal mode. Keep the
    // old exact indexOf semantics until the user chooses different matching options.
    const bool bLegacyCompatibleLiteral
        = rState.Mode == sfx2::RegexSearchMode::Literal && !rState.Flags.CaseInsensitive;
    std::unique_ptr<utl::TextSearch> xSearch;
    if (bValid && !bEmpty && !bLegacyCompatibleLiteral)
        xSearch = std::make_unique<utl::TextSearch>(m_xRegexSearchController->GetSearchOptions());

    m_xLb->clear();
    for (const OUString& rSheetName : maCacheSheetsNames)
    {
        if (bEmpty
            || (bLegacyCompatibleLiteral && rSheetName.indexOf(rState.Pattern) >= 0)
            || (xSearch && xSearch->searchForward(rSheetName)))
            m_xLb->append_text(rSheetName);
    }
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
