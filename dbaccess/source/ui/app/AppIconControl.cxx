/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 * This file incorporates work covered by the following license notice:
 *
 *   Licensed to the Apache Software Foundation (ASF) under one or more
 *   contributor license agreements. See the NOTICE file distributed
 *   with this work for additional information regarding copyright
 *   ownership. The ASF licenses this file to you under the Apache
 *   License, Version 2.0 (the "License"); you may not use this file
 *   except in compliance with the License. You may obtain a copy of
 *   the License at http://www.apache.org/licenses/LICENSE-2.0 .
 */

#include "AppIconControl.hxx"
#include <core_resource.hxx>
#include <strings.hrc>
#include <bitmaps.hlst>
#include <sfx2/thumbnailviewitem.hxx>
#include <vcl/bitmap.hxx>
#include <vcl/event.hxx>
#include <vcl/i18nhelp.hxx>
#include <vcl/mnemonic.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/MaterialTokens.hxx>
#include <tools/color.hxx>
#include <callbacks.hxx>
#include <AppElementType.hxx>

#include <cstdlib>
#include <optional>
#include <string_view>

namespace
{
// Guarded Material Base navigation-rail selection colours (docs/design 12.1). Same
// env + high-contrast guard idiom as sc/source/ui/app/inputwin.cxx's formula-bar
// resolver: only while the documented Material file-widget theme is active (and not
// forced high contrast) does the rail resolve tokens.
bool lcl_isMaterialBaseActive()
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return false;
    if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())
        return false;
    return true;
}

// The selected rail entry pairs @primary-container fill with @on-primary-container
// text (12.1 "Rail entries" selected state).
struct MaterialRailSelection
{
    Color aFill;
    Color aText;
};

std::optional<MaterialRailSelection> lcl_getMaterialRailSelection()
{
    if (!lcl_isMaterialBaseActive())
        return std::nullopt;
    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    const vcl::MaterialTokens aTokens
        = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    if (!aTokens.isValid())
        return std::nullopt;
    const std::optional<Color> oFill = aTokens.findColor("primary-container");
    const std::optional<Color> oText = aTokens.findColor("on-primary-container");
    if (!oFill || !oText)
        return std::nullopt;
    return MaterialRailSelection{ *oFill, *oText };
}
} // namespace

namespace dbaui
{
class OApplicationIconControlDropTarget final : public DropTargetHelper
{
private:
    OApplicationIconControl& m_rControl;

public:
    OApplicationIconControlDropTarget(OApplicationIconControl& rControl)
        : DropTargetHelper(rControl.GetDrawingArea()->get_drop_target())
        , m_rControl(rControl)
    {
    }

    virtual sal_Int8 AcceptDrop(const AcceptDropEvent& rEvt) override
    {
        return m_rControl.AcceptDrop(rEvt);
    }

    virtual sal_Int8 ExecuteDrop(const ExecuteDropEvent& rEvt) override
    {
        return m_rControl.ExecuteDrop(rEvt);
    }
};

OApplicationIconControl::OApplicationIconControl(std::unique_ptr<weld::ScrolledWindow> xScroll)
    : ThumbnailView(std::move(xScroll))
    , m_pActionListener(nullptr)
    , m_nMaxWidth(0)
    , m_nMaxHeight(0)
{
    mnVItemSpace = 6; // row spacing
    mbSelectOnFocus = false;
    DrawMnemonics(true);
}

void OApplicationIconControl::Fill()
{
    static constexpr struct CategoryDescriptor
    {
        TranslateId pLabelResId;
        ElementType eType;
        OUString aImageResId;
    } aCategories[] = { { RID_STR_TABLES_CONTAINER, E_TABLE, BMP_TABLEFOLDER_TREE_L },
                        { RID_STR_QUERIES_CONTAINER, E_QUERY, BMP_QUERYFOLDER_TREE_L },
                        { RID_STR_FORMS_CONTAINER, E_FORM, BMP_FORMFOLDER_TREE_L },
                        { RID_STR_REPORTS_CONTAINER, E_REPORT, BMP_REPORTFOLDER_TREE_L } };

    for (const CategoryDescriptor& aCategory : aCategories)
    {
        // E_TABLE is 0, but 0 means void so use id of enum + 1
        std::unique_ptr<ThumbnailViewItem> xItem(new ThumbnailViewItem(*this, aCategory.eType + 1));
        xItem->mbBorder = false;
        xItem->maPreview = Bitmap(aCategory.aImageResId);
        const Size aSize = xItem->maPreview.GetSizePixel();
        m_nMaxWidth = std::max(m_nMaxWidth, aSize.Width());
        m_nMaxHeight = std::max(m_nMaxHeight, aSize.Height());
        xItem->maTitle = DBA_RES(aCategory.pLabelResId);
        m_nMaxWidth = std::max<tools::Long>(m_nMaxWidth, GetTextWidth(xItem->maTitle));
        AppendItem(std::move(xItem));
    }

    const int nMargin = 12;
    const int nWidthRequest = m_nMaxWidth + 2 * nMargin;
    set_size_request(nWidthRequest, -1);
    // we expect a Resize at which point we'll set the item sizes based on our final size
}

ElementType OApplicationIconControl::GetSelectedItem() const
{
    for (const auto& rItem : mItemList)
    {
        if (!rItem->mbSelected)
            continue;
        return static_cast<ElementType>(rItem->mnId - 1);
    }
    return E_NONE;
}

void OApplicationIconControl::createIconAutoMnemonics(MnemonicGenerator& rMnemonics)
{
    for (const auto& rItem : mItemList)
        rMnemonics.RegisterMnemonic(rItem->maTitle);

    // exchange texts with generated mnemonics
    for (auto& rItem : mItemList)
        rItem->maTitle = rMnemonics.CreateMnemonic(rItem->maTitle);
}

void OApplicationIconControl::Resize()
{
    // fill the full width of the allocated area and give two lines of space to
    // center the title in
    setItemDimensions(GetOutputSizePixel().Width(), m_nMaxHeight, GetTextHeight() * 2, 0);
    ThumbnailView::Resize();
}

bool OApplicationIconControl::IsMnemonicChar(sal_Unicode cChar, ElementType& rType) const
{
    bool bRet = false;

    const vcl::I18nHelper& rI18nHelper = Application::GetSettings().GetUILocaleI18nHelper();
    for (const auto& rItem : mItemList)
    {
        if (rI18nHelper.MatchMnemonic(rItem->maTitle, cChar))
        {
            bRet = true;
            rType = static_cast<ElementType>(rItem->mnId - 1);
            break;
        }
    }

    return bRet;
}

bool OApplicationIconControl::DoKeyShortCut(const KeyEvent& rKEvt)
{
    bool bMod2 = rKEvt.GetKeyCode().IsMod2();
    sal_Unicode cChar = rKEvt.GetCharCode();
    ElementType eType(E_NONE);
    if (bMod2 && cChar && IsMnemonicChar(cChar, eType))
    {
        // shortcut is clicked
        deselectItems();
        SelectItem(eType + 1);
        return true;
    }

    return false;
}

bool OApplicationIconControl::KeyInput(const KeyEvent& rKEvt)
{
    return DoKeyShortCut(rKEvt) || ThumbnailView::KeyInput(rKEvt);
}

void OApplicationIconControl::SetDrawingArea(weld::DrawingArea* pDrawingArea)
{
    ThumbnailView::SetDrawingArea(pDrawingArea);
    m_xDropTarget.reset(new OApplicationIconControlDropTarget(*this));
}

sal_Int8 OApplicationIconControl::AcceptDrop(const AcceptDropEvent& rEvt)
{
    sal_Int8 nDropOption = DND_ACTION_NONE;
    if (m_pActionListener)
    {
        sal_uInt16 nEntry = GetItemId(rEvt.maPosPixel);
        if (nEntry)
        {
            deselectItems();
            SelectItem(nEntry);
            nDropOption
                = m_pActionListener->queryDrop(rEvt, m_xDropTarget->GetDataFlavorExVector());
        }
    }
    return nDropOption;
}

sal_Int8 OApplicationIconControl::ExecuteDrop(const ExecuteDropEvent& rEvt)
{
    if (m_pActionListener)
        m_pActionListener->executeDrop(rEvt);
    return DND_ACTION_NONE;
}

OApplicationIconControl::~OApplicationIconControl() {}

void OApplicationIconControl::GetFocus()
{
    ThumbnailView::GetFocus();
    Invalidate(); // redraw focus rect
}

void OApplicationIconControl::LoseFocus()
{
    ThumbnailView::LoseFocus();
    Invalidate(); // redraw focus rect
}

void OApplicationIconControl::UpdateColors(const StyleSettings& rSettings)
{
    // Keep the generic StyleSettings baseline, then, while the Material theme is
    // active, re-point the selected/highlighted rail entry to the Material
    // @primary-container / @on-primary-container pair (docs/design 12.1). Paint()
    // re-invokes UpdateColors + updateItemAttrsFromColors every frame, so these
    // members feed the item attributes on the next draw. Non-Material paths are
    // untouched; the whole surface stays source-declared (runtime_verified:false).
    ThumbnailView::UpdateColors(rSettings);

    if (const std::optional<MaterialRailSelection> oSelection = lcl_getMaterialRailSelection())
    {
        maHighlightColor = oSelection->aFill;
        maHighlightTextColor = oSelection->aText;
    }
}

tools::Rectangle OApplicationIconControl::GetFocusRect()
{
    if (HasFocus())
    {
        // Get the last selected item in the list
        for (tools::Long i = mFilteredItemList.size() - 1; i >= 0; --i)
        {
            ThumbnailViewItem* pItem = mFilteredItemList[i];
            if (pItem->isSelected())
            {
                tools::Rectangle aRet(pItem->getDrawArea());
                aRet.AdjustLeft(THUMBNAILVIEW_ITEM_CORNER);
                aRet.AdjustTop(1);
                aRet.AdjustRight(-THUMBNAILVIEW_ITEM_CORNER);
                aRet.AdjustBottom(-2);
                return aRet;
            }
        }
    }
    return tools::Rectangle();
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
