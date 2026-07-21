/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4     -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <templatedefaultview.hxx>
#include <sfx2/thumbnailview.hxx>
#include <sfx2/thumbnailviewitem.hxx>
#include <templateviewitem.hxx>
#include <startcentercard.hxx>
#include <sfx2/sfxresid.hxx>
#include <vcl/event.hxx>
#include <vcl/svapp.hxx>
#include <vcl/weld/Menu.hxx>

#include <sfx2/strings.hrc>

#include <memory>
#include <vector>

constexpr int gnItemPadding(5); //TODO:: Change padding to 10. It looks really crowded and occupied.
constexpr tools::Long gnTextHeight = 30;

TemplateDefaultView::TemplateDefaultView(std::unique_ptr<weld::ScrolledWindow> xWindow,
                                         std::unique_ptr<weld::Menu> xMenu)
    : TemplateLocalView(std::move(xWindow), std::move(xMenu))
{
    mbAllowMultiSelection = false;
    AbsoluteScreenPixelRectangle aScreen = Application::GetScreenPosSizePixel(Application::GetDisplayBuiltInScreen());
    tools::Long nItemMaxSize = std::min(aScreen.GetWidth(),aScreen.GetHeight()) > 800 ? 256 : 192;
    ThumbnailView::setItemDimensions( nItemMaxSize, nItemMaxSize, gnTextHeight, gnItemPadding );
    updateThumbnailDimensions(nItemMaxSize);

    // Material Start Center: lay the template grid out as Material document cards.
    // setItemDimensions() adds 2*padding to both axes, so SC_CARD_GRID_GAP is
    // pre-subtracted from the caption height as well as the width, leaving the drawn
    // cell at preview + caption instead of overshooting by 2*padding (see
    // RecentDocsView for the full rationale).
    // Guarded so the default/native thumbnail geometry above is untouched.
    if (sfx2::IsMaterialStartCenterActive())
        ThumbnailView::setItemDimensions(sfx2::SC_CARD_MIN_WIDTH - sfx2::SC_CARD_GRID_GAP,
                                         sfx2::SC_CARD_PREVIEW_HEIGHT,
                                         sfx2::SC_CARD_CAPTION_HEIGHT - sfx2::SC_CARD_GRID_GAP,
                                         sfx2::SC_CARD_GRID_GAP / 2);

    mfHighlightTransparence = 0.75;

    UpdateColors(Application::GetSettings().GetStyleSettings());
}

void TemplateDefaultView::UpdateColors(const StyleSettings& rSettings)
{
    TemplateLocalView::UpdateColors(rSettings);

    maFillColor = rSettings.GetWindowColor();
    maTextColor = rSettings.GetWindowTextColor();

    maHighlightColor = rSettings.GetHighlightColor();
    maHighlightTextColor = rSettings.GetHighlightTextColor();
}

void TemplateDefaultView::showAllTemplates()
{
    mnCurRegionId = 0;

    insertItems(maAllTemplates, false);
}

bool TemplateDefaultView::KeyInput( const KeyEvent& rKEvt )
{
    return ThumbnailView::KeyInput(rKEvt);
}

bool TemplateDefaultView::MouseButtonDown( const MouseEvent& rMEvt )
{
    if( rMEvt.IsLeft() && rMEvt.GetClicks() == 1 )
    {
        size_t nPos = ImplGetItem(rMEvt.GetPosPixel());
        ThumbnailViewItem* pItem = ImplGetItem(nPos);
        TemplateViewItem* pViewItem = dynamic_cast<TemplateViewItem*>(pItem);
        if(pViewItem)
            maOpenTemplateHdl.Call(pViewItem->getPath());
        return true;
    }

    return TemplateLocalView::MouseButtonDown(rMEvt);
}

void TemplateDefaultView::Paint(vcl::RenderContext& rRenderContext, const tools::Rectangle& rRect)
{
    // Material Start Center: draw the native Material template-card grid (scoped
    // to this Start Center view, not the shared Template Manager). Inert under
    // the default/native theme, where the base paint below runs unchanged.
    //
    // As in RecentDocsView, only take the Material path when mItemList is
    // non-empty: a populated grid, or the "no templates match this pattern"
    // message when a live search hides every card. With no templates at all,
    // fall through to the base paint rather than a filter-implying empty message.
    if (sfx2::IsMaterialStartCenterActive() && !mItemList.empty())
    {
        std::vector<ThumbnailViewItem*> aVisibleItems;
        aVisibleItems.reserve(mItemList.size());
        for (const std::unique_ptr<ThumbnailViewItem>& rxItem : mItemList)
            if (rxItem && rxItem->isVisible())
                aVisibleItems.push_back(rxItem.get());
        if (sfx2::MaterialStartCenterCards::Paint(rRenderContext, *this, aVisibleItems,
                                                  SfxResId(STR_SC_NO_TEMPLATE_MATCH)))
            return;
    }

    TemplateLocalView::Paint(rRenderContext, rRect);
}

void TemplateDefaultView::createContextMenu(const bool bIsBuiltIn)
{
    mxContextMenu->clear();
    mxContextMenu->append(u"open"_ustr,SfxResId(STR_OPEN));
    mxContextMenu->append(u"edit"_ustr,SfxResId(STR_EDIT_TEMPLATE));

    if (bIsBuiltIn)
    {
        mxContextMenu->set_sensitive(u"edit"_ustr, false);
    }

    deselectItems();
    mpSelectedItem->setSelection(true);
    maItemStateHdl.Call(mpSelectedItem);
    ContextMenuSelectHdl(mxContextMenu->popup_at_rect(GetDrawingArea(), tools::Rectangle(maPosition, Size(1,1))));
    Invalidate();
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
