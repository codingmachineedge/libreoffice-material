/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <rtl/ustring.hxx>
#include <tools/long.hxx>

#include <vector>

// vcl::RenderContext is a typedef for OutputDevice; forward-declare the class.
class OutputDevice;
namespace vcl { typedef OutputDevice RenderContext; }
class ThumbnailView;
class ThumbnailViewItem;

namespace sfx2
{
/**
 * Native Material Start Center document-card anatomy.
 *
 * The Start Center's Recent Documents and Templates grids are card grids, per
 * docs/design/06-containers.md 6.6 and docs/design/09-start-center.md 9.1/9.10.
 * These metrics are the normative card geometry taken from those chapters (which
 * win over the prototype where they differ) and mirrored 1:1 by the fail-closed
 * contract bin/check-windows-startcenter-cards.py. The color/radius *values* are
 * never hard-coded here: they are resolved at draw time from the single Material
 * token table (vcl::MaterialTokens over definition.xml).
 *
 * Everything below is opt-in: it is drawn only when the documented Material
 * file-widget activation (VCL_FILE_WIDGET_THEME=material) is live. Under the
 * default/native theme IsMaterialStartCenterActive() is false and every entry
 * point is inert, so the existing ThumbnailView drawing path is untouched.
 */

// --- Card anatomy geometry (device pixels) -----------------------------------
inline constexpr tools::Long SC_CARD_MIN_WIDTH = 184;      ///< grid minmax() minimum card width
inline constexpr tools::Long SC_CARD_GRID_GAP = 16;        ///< grid gap between cards
inline constexpr tools::Long SC_CARD_PREVIEW_HEIGHT = 118; ///< preview region height
inline constexpr tools::Long SC_CARD_CAPTION_HEIGHT = 52;  ///< caption region height (10/12/12 pad + name + meta)
inline constexpr tools::Long SC_CARD_THUMB_WIDTH = 74;     ///< page-thumbnail placeholder width
inline constexpr tools::Long SC_CARD_THUMB_HEIGHT = 92;    ///< page-thumbnail placeholder height
inline constexpr tools::Long SC_CARD_THUMB_RADIUS = 6;     ///< page-thumbnail corner radius
inline constexpr tools::Long SC_CARD_BADGE_SIZE = 26;      ///< app-badge chip size
inline constexpr tools::Long SC_CARD_BADGE_INSET = 8;      ///< app-badge inset from preview top-right
inline constexpr tools::Long SC_CARD_BADGE_ICON = 16;      ///< app-badge glyph size
inline constexpr tools::Long SC_CARD_CAPTION_PAD_X = 12;   ///< caption horizontal padding
inline constexpr tools::Long SC_CARD_CAPTION_PAD_TOP = 10; ///< caption top padding
inline constexpr tools::Long SC_CARD_CAPTION_PAD_BOTTOM = 12; ///< caption bottom padding
inline constexpr tools::Long SC_CARD_TITLE_TEXT = 13;      ///< card title size (medium)
inline constexpr tools::Long SC_CARD_META_TEXT = 11;       ///< card meta size
inline constexpr tools::Long SC_CARD_META_GAP = 2;         ///< gap between title and meta
inline constexpr tools::Long SC_CARD_EMPTY_PADDING = 34;   ///< empty/filtered-grid message padding
inline constexpr tools::Long SC_CARD_EMPTY_TEXT = 13;      ///< empty/filtered-grid message size

/// True only when the documented Material file-widget theme is the active
/// activation (VCL_FILE_WIDGET_THEME=material). Mirrors the guard in
/// sd/source/ui/app/scalectrl.cxx so non-Material rendering paths stay inert.
bool IsMaterialStartCenterActive();

class MaterialStartCenterCards
{
public:
    /**
     * Paint the full Material card grid for @p rItems into @p rRenderContext.
     *
     * @return true when the Material theme is active and the grid (or the
     *         empty/filtered message @p rEmptyMessage) was drawn; false when the
     *         Material theme is inactive, in which case nothing is drawn and the
     *         caller must fall back to the default ThumbnailView paint.
     */
    static bool Paint(vcl::RenderContext& rRenderContext, ThumbnailView& rView,
                      const std::vector<ThumbnailViewItem*>& rItems,
                      const OUString& rEmptyMessage);
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
