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

#include <sidebar/DeckTitleBar.hxx>
#include <sfx2/sidebar/Theme.hxx>

#include <utility>
#include <cstdlib>
#include <vcl/bitmap.hxx>
#include <vcl/font.hxx>
#include <vcl/outdev.hxx>
#include <vcl/ptrstyle.hxx>
#include <vcl/weld/customweld.hxx>

#if OSL_DEBUG_LEVEL >= 2
#include <sidebar/Tools.hxx>
#endif

namespace sfx2::sidebar {

namespace {

/** WIN-CON-007: the Material deck title treatment is gated on the file-definition
    Material widget draw path (the same VCL_DRAW_WIDGETS_FROM_FILE gate the rail
    keys on), so the title-role restyle never touches the measured native deck
    title off the Material path. */
bool IsMaterialDeck()
{
    static const bool bMaterial = (std::getenv("VCL_DRAW_WIDGETS_FROM_FILE") != nullptr);
    return bMaterial;
}

/** WIN-CON-007: the deck title uses the Material `title` type role -- 120% scale,
    semibold weight, @on-surface on the @surface deck (design 06 s6.7 / site
    prototype "Properties"). Applied only on the Material path and re-applied on
    DataChanged so a live theme switch keeps the title role. */
void ApplyMaterialDeckTitleStyle(weld::Label& rLabel)
{
    if (!IsMaterialDeck())
        return;
    vcl::Font aFont(rLabel.get_font());
    aFont.SetWeight(WEIGHT_SEMIBOLD);
    Size aFontSize(aFont.GetFontSize());
    aFontSize.setHeight(aFontSize.Height() * Theme::GetInteger(Theme::Int_DeckTitleScalePercent) / 100);
    aFont.SetFontSize(aFontSize);
    rLabel.set_font(aFont);
    rLabel.set_font_color(Theme::GetColor(Theme::Color_DeckTitleText));
}

} // anonymous namespace

class GripWidget : public weld::CustomWidgetController
{
private:
    Bitmap maGrip;
public:
    virtual void SetDrawingArea(weld::DrawingArea* pDrawingArea) override
    {
        weld::CustomWidgetController::SetDrawingArea(pDrawingArea);
        StyleUpdated();
    }

    virtual void StyleUpdated() override
    {
        maGrip = Bitmap(u"sfx2/res/grip.png"_ustr);
        Size aGripSize(maGrip.GetSizePixel());
        set_size_request(aGripSize.Width(), aGripSize.Height());
        weld::CustomWidgetController::StyleUpdated();
    }

    virtual void Paint(vcl::RenderContext& rRenderContext, const tools::Rectangle& /*rRect*/) override
    {
        rRenderContext.SetBackground(Theme::GetColor(Theme::Color_DeckTitleBarBackground));
        rRenderContext.Erase();
        rRenderContext.DrawBitmap(Point(0, 0), maGrip);
    }
};

DeckTitleBar::DeckTitleBar (const OUString& rsTitle,
                            weld::Builder& rBuilder,
                            const OUString& rsHelpId,
                            std::function<void()> aCloserAction)
    : TitleBar(rBuilder, Theme::Color_DeckTitleBarBackground)
    , mxGripWidget(new GripWidget)
    , mxGripWeld(new weld::CustomWeld(rBuilder, u"grip"_ustr, *mxGripWidget))
    , mxLabel(rBuilder.weld_label(u"label"_ustr))
    , msHelpId(rsHelpId)
    , maCloserAction(std::move(aCloserAction))
    , mbIsCloserVisible(false)
{
    mxLabel->set_label(rsTitle);
    ApplyMaterialDeckTitleStyle(*mxLabel);
    mxGripWidget->SetPointer(PointerStyle::Move);

    if (maCloserAction)
        SetCloserVisible(true);
}

DeckTitleBar::~DeckTitleBar()
{
}

tools::Rectangle DeckTitleBar::GetDragArea() const
{
    int x, y, width, height;
    if (mxGripWidget->GetDrawingArea()->get_extents_relative_to(*mxTitlebar, x, y, width, height))
        return tools::Rectangle(Point(x, y), Size(width, height));
    return tools::Rectangle();
}

void DeckTitleBar::SetTitle(const OUString& rsTitle)
{
    mxLabel->set_label(rsTitle);
}

OUString DeckTitleBar::GetTitle() const
{
    return mxLabel->get_label();
}

void DeckTitleBar::SetCloserVisible (const bool bIsCloserVisible)
{
    if (mbIsCloserVisible == bIsCloserVisible)
        return;

    mbIsCloserVisible = bIsCloserVisible;

    mxToolBox->set_visible(mbIsCloserVisible);
}

void DeckTitleBar::HandleToolBoxItemClick()
{
    if (msToolBoxRId == "btn_help")
    {
        // Help toolbox button was clicked
        DeckTitleBar::ShowHelp(msHelpId);
    }
    else if ((msToolBoxRId.isEmpty()) || (msToolBoxRId == "btn_close"))
    {
        if (maCloserAction)
            maCloserAction();
    }
    // Reset the toolbox response id
    msToolBoxRId = "";
}

void DeckTitleBar::DataChanged()
{
    mxToolBox->set_item_icon_name(u"button"_ustr, u"sfx2/res/closedoc.png"_ustr);
    TitleBar::DataChanged();
    ApplyMaterialDeckTitleStyle(*mxLabel);
}

} // end of namespace sfx2::sidebar

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
