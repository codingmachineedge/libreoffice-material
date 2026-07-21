/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <startcentercard.hxx>

#include <sfx2/thumbnailview.hxx>
#include <sfx2/thumbnailviewitem.hxx>

#include <vcl/MaterialTokens.hxx>
#include <vcl/outdev.hxx>
#include <vcl/font.hxx>
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <tools/color.hxx>
#include <tools/fontenum.hxx>
#include <tools/gen.hxx>

#include <cstdlib>
#include <optional>
#include <string_view>

namespace sfx2
{
bool IsMaterialStartCenterActive()
{
    // Only the documented Material file-widget activation. Identical guard idiom
    // to sd/source/ui/app/scalectrl.cxx: under any other theme this is false and
    // the Start Center card renderer draws nothing.
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    return pThemeName && std::string_view(pThemeName) == "material";
}

namespace
{
// Resolve a required Material color role from the single token table. The role
// name literals below are the card's contract with definition.xml; token drift
// is caught fail-closed by bin/check-windows-startcenter-cards.py. The fallback
// is only a defensive neutral so drawing is never seeded from an uninitialized
// color if the definition is unreadable at runtime.
Color lcl_color(const vcl::MaterialTokens& rTokens, std::string_view rRole, const Color& rFallback)
{
    if (const std::optional<Color> oColor = rTokens.findColor(rRole))
        return *oColor;
    return rFallback;
}

tools::Long lcl_radius(const vcl::MaterialTokens& rTokens, std::string_view rName,
                       tools::Long nFallback)
{
    if (const std::optional<sal_Int32> oRadius = rTokens.findRadius(rName))
        return *oRadius;
    return nFallback;
}

void lcl_setFont(vcl::RenderContext& rDev, tools::Long nHeightPx, FontWeight eWeight,
                 const Color& rColor)
{
    vcl::Font aFont(rDev.GetFont());
    aFont.SetFontHeight(nHeightPx);
    aFont.SetWeight(eWeight);
    rDev.SetFont(aFont);
    rDev.SetTextColor(rColor);
    rDev.SetTextFillColor();
}

// Draw one Material document card into its grid cell (rArea == item draw area).
void lcl_paintCard(vcl::RenderContext& rDev, const tools::Rectangle& rArea,
                   const ThumbnailViewItem& rItem, bool bHover, bool bFocused,
                   const vcl::MaterialTokens& rTokens)
{
    const Color aSurface = lcl_color(rTokens, "surface", COL_WHITE);
    const Color aPreviewFill = lcl_color(rTokens, "surface-container-low", COL_LIGHTGRAY);
    const Color aOutlineVariant = lcl_color(rTokens, "outline-variant", COL_GRAY);
    const Color aPrimary = lcl_color(rTokens, "primary", COL_BLUE);
    const Color aBadgeFill = lcl_color(rTokens, "primary-container", COL_LIGHTBLUE);
    const Color aBadgeIcon = lcl_color(rTokens, "on-primary-container", COL_BLACK);
    const Color aTitleColor = lcl_color(rTokens, "on-surface", COL_BLACK);
    const Color aMetaColor = lcl_color(rTokens, "on-surface-variant", COL_GRAY);

    const tools::Long nCardRadius = lcl_radius(rTokens, "corner-container", 12);
    const tools::Long nBadgeRadius = lcl_radius(rTokens, "corner-small", 8);
    const tools::Long nFocusRadius = lcl_radius(rTokens, "corner-focus", 6);

    // Card container: @surface fill, @outline-variant hairline (or @primary on
    // hover), corner-container radius, clipped. Hover currently recolours the
    // border only; the paired soft-shadow elevation cue is deferred, so this does
    // not yet meet the "never colour alone" (WCAG use-of-colour) guarantee.
    rDev.SetFillColor(aSurface);
    rDev.SetLineColor(bHover ? aPrimary : aOutlineVariant);
    rDev.DrawRect(rArea, nCardRadius, nCardRadius);

    // Preview region: top SC_CARD_PREVIEW_HEIGHT px, @surface-container-low fill,
    // hairline @outline-variant bottom border.
    const tools::Long nPreviewBottom = rArea.Top() + SC_CARD_PREVIEW_HEIGHT;
    const tools::Rectangle aPreview(rArea.Left(), rArea.Top(), rArea.Right(), nPreviewBottom);
    rDev.SetLineColor();
    rDev.SetFillColor(aPreviewFill);
    rDev.DrawRect(aPreview);
    rDev.SetLineColor(aOutlineVariant);
    rDev.DrawLine(Point(rArea.Left(), nPreviewBottom), Point(rArea.Right(), nPreviewBottom));

    // Page thumbnail: SC_CARD_THUMB_WIDTH x SC_CARD_THUMB_HEIGHT @surface page,
    // @outline-variant border, 6px radius. Draw the real preview when present,
    // otherwise the placeholder text bars.
    const Point aPreviewCenter = aPreview.Center();
    const tools::Rectangle aThumb(
        aPreviewCenter.X() - SC_CARD_THUMB_WIDTH / 2, aPreviewCenter.Y() - SC_CARD_THUMB_HEIGHT / 2,
        aPreviewCenter.X() + SC_CARD_THUMB_WIDTH / 2, aPreviewCenter.Y() + SC_CARD_THUMB_HEIGHT / 2);
    rDev.SetFillColor(aSurface);
    rDev.SetLineColor(aOutlineVariant);
    rDev.DrawRect(aThumb, SC_CARD_THUMB_RADIUS, SC_CARD_THUMB_RADIUS);
    if (!rItem.maPreview.IsEmpty())
    {
        rDev.DrawBitmap(Point(aThumb.Left() + 1, aThumb.Top() + 1),
                        Size(SC_CARD_THUMB_WIDTH - 2, SC_CARD_THUMB_HEIGHT - 2), rItem.maPreview);
    }
    else
    {
        rDev.SetLineColor();
        rDev.SetFillColor(aOutlineVariant);
        const tools::Long nBarX = aThumb.Left() + 8;
        const tools::Long nBarW = SC_CARD_THUMB_WIDTH - 16;
        tools::Long nBarY = aThumb.Top() + 12;
        static const double kBars[4] = { 0.70, 1.0, 0.92, 0.80 };
        for (const double fBar : kBars)
        {
            rDev.DrawRect(tools::Rectangle(nBarX, nBarY,
                                           nBarX + static_cast<tools::Long>(nBarW * fBar),
                                           nBarY + 4));
            nBarY += 9;
        }
    }

    // App badge: SC_CARD_BADGE_SIZE chip, corner-small radius, @primary-container
    // fill, inset SC_CARD_BADGE_INSET from the preview top-right, holding a 16px
    // @on-primary-container document mark.
    const tools::Rectangle aBadge(aPreview.Right() - SC_CARD_BADGE_INSET - SC_CARD_BADGE_SIZE,
                                  aPreview.Top() + SC_CARD_BADGE_INSET,
                                  aPreview.Right() - SC_CARD_BADGE_INSET,
                                  aPreview.Top() + SC_CARD_BADGE_INSET + SC_CARD_BADGE_SIZE);
    rDev.SetLineColor();
    rDev.SetFillColor(aBadgeFill);
    rDev.DrawRect(aBadge, nBadgeRadius, nBadgeRadius);
    const Point aBadgeCenter = aBadge.Center();
    const tools::Rectangle aMark(aBadgeCenter.X() - SC_CARD_BADGE_ICON / 4,
                                 aBadgeCenter.Y() - SC_CARD_BADGE_ICON / 2,
                                 aBadgeCenter.X() + SC_CARD_BADGE_ICON / 4,
                                 aBadgeCenter.Y() + SC_CARD_BADGE_ICON / 2);
    rDev.SetFillColor();
    rDev.SetLineColor(aBadgeIcon);
    rDev.DrawRect(aMark);

    // Caption: SC_CARD_TITLE_TEXT px medium @on-surface name, single line and
    // end-ellipsized, over SC_CARD_META_TEXT px @on-surface-variant meta.
    const tools::Long nTextLeft = rArea.Left() + SC_CARD_CAPTION_PAD_X;
    const tools::Long nTextRight = rArea.Right() - SC_CARD_CAPTION_PAD_X;
    tools::Long nTextTop = nPreviewBottom + SC_CARD_CAPTION_PAD_TOP;
    lcl_setFont(rDev, SC_CARD_TITLE_TEXT, WEIGHT_MEDIUM, aTitleColor);
    const tools::Long nTitleH = rDev.GetTextHeight();
    rDev.DrawText(tools::Rectangle(nTextLeft, nTextTop, nTextRight, nTextTop + nTitleH),
                  rItem.getTitle(), DrawTextFlags::Left | DrawTextFlags::EndEllipsis);
    nTextTop += nTitleH + SC_CARD_META_GAP;
    lcl_setFont(rDev, SC_CARD_META_TEXT, WEIGHT_NORMAL, aMetaColor);
    rDev.DrawText(tools::Rectangle(nTextLeft, nTextTop, nTextRight, nTextTop + rDev.GetTextHeight()),
                  rItem.getHelpText(), DrawTextFlags::Left | DrawTextFlags::EndEllipsis);

    // Keyboard focus ring: @primary at stroke-standard, corner-focus geometry,
    // drawn just outside the card border (border recolour alone can fall below
    // 3:1 against @surface-container-low).
    if (bFocused)
    {
        const tools::Rectangle aRing(rArea.Left() - 2, rArea.Top() - 2, rArea.Right() + 2,
                                     rArea.Bottom() + 2);
        rDev.SetFillColor();
        rDev.SetLineColor(aPrimary);
        rDev.DrawRect(aRing, nFocusRadius, nFocusRadius);
    }
}
} // namespace

bool MaterialStartCenterCards::Paint(vcl::RenderContext& rRenderContext, ThumbnailView& rView,
                                     const std::vector<ThumbnailViewItem*>& rItems,
                                     const OUString& rEmptyMessage)
{
    if (!IsMaterialStartCenterActive())
        return false;

    const bool bDark
        = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();

    // Resolving the tokens re-reads and re-parses definition.xml from disk
    // (MaterialTokens::fromThemeDefinition -> WidgetDefinitionReader). Paint fires
    // on every invalidate, hover, selection change, scroll and resize, so cache the
    // parsed table once per scheme in function-local statics and reuse it instead of
    // doing synchronous file I/O + XML parse on each frame. definition.xml is a
    // static install asset selected once at start-up (VCL_FILE_WIDGET_THEME), so a
    // process-lifetime cache keyed by the light/dark scheme is safe.
    static const vcl::MaterialTokens aLightTokens
        = vcl::MaterialTokens::fromThemeDefinition(OString());
    static const vcl::MaterialTokens aDarkTokens
        = vcl::MaterialTokens::fromThemeDefinition("dark"_ostr);
    const vcl::MaterialTokens& aTokens = bDark ? aDarkTokens : aLightTokens;
    if (!aTokens.isValid())
        return false;

    auto popIt = rRenderContext.ScopedPush(vcl::PushFlags::ALL);

    // The card grid draws over @surface (windowbackground), per 06-containers 6.6.
    const Color aSurface = lcl_color(aTokens, "surface", COL_WHITE);
    const Size aOutputSize = rRenderContext.GetOutputSizePixel();
    rRenderContext.SetLineColor();
    rRenderContext.SetFillColor(aSurface);
    rRenderContext.DrawRect(tools::Rectangle(Point(), aOutputSize));

    // Empty / filtered grid: one full-width centred @on-surface-variant message.
    if (rItems.empty())
    {
        lcl_setFont(rRenderContext, SC_CARD_EMPTY_TEXT, WEIGHT_NORMAL,
                    lcl_color(aTokens, "on-surface-variant", COL_GRAY));
        const tools::Rectangle aMessageArea(
            SC_CARD_EMPTY_PADDING, SC_CARD_EMPTY_PADDING, aOutputSize.Width() - SC_CARD_EMPTY_PADDING,
            aOutputSize.Height() - SC_CARD_EMPTY_PADDING);
        rRenderContext.DrawText(aMessageArea, rEmptyMessage,
                                DrawTextFlags::Center | DrawTextFlags::MultiLine
                                    | DrawTextFlags::WordBreak);
        return true;
    }

    const bool bViewFocused = rView.HasFocus();
    for (const ThumbnailViewItem* pItem : rItems)
    {
        if (!pItem || !pItem->isVisible())
            continue;
        const tools::Rectangle& rArea = pItem->getDrawArea();
        if (rArea.IsEmpty())
            continue;
        lcl_paintCard(rRenderContext, rArea, *pItem, pItem->isHighlighted(),
                      bViewFocused && pItem->isSelected(), aTokens);
    }
    return true;
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
