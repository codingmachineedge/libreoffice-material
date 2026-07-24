/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#include <vcl/MaterialTokens.hxx>

#include <widgetdraw/WidgetDefinitionReader.hxx>

#include <config_folders.h>
#include <rtl/bootstrap.hxx>
#include <rtl/strbuf.hxx>
#include <sal/log.hxx>

#include <array>
#include <map>
#include <mutex>

namespace vcl
{
namespace
{
// Canonical semantic vocabularies. These mirror the <palette>, <shapes> and
// <metrics> token names in
// vcl/uiconfig/theme_definitions/material/definition.xml exactly. No hex value,
// radius pixel or metric pixel is duplicated here: only the names live in C++,
// and every value is read from the file. fromDefinitionFile() rejects any file
// whose token names differ from these lists, and
// bin/check-material-token-accessor.py fails closed on any static drift.
constexpr std::array<std::string_view, 23> gMaterialColorRoles = {
    "primary",
    "on-primary",
    "primary-container",
    "on-primary-container",
    "primary-hover",
    "primary-pressed",
    "primary-action-hover",
    "primary-action-pressed",
    "surface",
    "surface-container",
    "surface-container-low",
    "on-surface",
    "on-surface-variant",
    "outline",
    "outline-variant",
    "disabled-container",
    "inverse-surface",
    "inverse-on-surface",
    "warning-container",
    "on-warning-container",
    "error-container",
    "on-error-container",
    "visited-link",
};

constexpr std::array<std::string_view, 8> gMaterialShapeTokens = {
    "corner-checkbox", "corner-indicator", "corner-focus",   "corner-small",
    "corner-control",  "corner-container", "corner-toolbar", "corner-pill",
};

constexpr std::array<std::string_view, 15> gMaterialMetricTokens = {
    "stroke-none",
    "stroke-thin",
    "stroke-standard",
    "stroke-track",
    "space-list-entry",
    "space-tab-inline",
    "height-floating-title",
    "size-menu-indicator",
    "height-window-title",
    "size-list-preview",
    "size-tree-node",
    "size-selection-control",
    "size-compact-control",
    "size-standard-control",
    "height-tab",
};

OString toOString(std::string_view rView)
{
    return OString(rView.data(), static_cast<sal_Int32>(rView.size()));
}

// True when the token map's key set is exactly the canonical name vocabulary
// (no missing name, no undeclared extra name).
template <std::size_t N>
bool namesMatchVocabulary(const std::map<OString, sal_Int32>& rTokens,
                          const std::array<std::string_view, N>& rVocabulary)
{
    if (rTokens.size() != rVocabulary.size())
        return false;
    for (const std::string_view rName : rVocabulary)
    {
        if (rTokens.find(toOString(rName)) == rTokens.end())
            return false;
    }
    return true;
}

template <std::size_t N>
bool colorNamesMatchVocabulary(const std::map<OString, Color>& rTokens,
                               const std::array<std::string_view, N>& rVocabulary)
{
    if (rTokens.size() != rVocabulary.size())
        return false;
    for (const std::string_view rName : rVocabulary)
    {
        if (rTokens.find(toOString(rName)) == rTokens.end())
            return false;
    }
    return true;
}

std::vector<OString> sortedKeys(const std::map<OString, sal_Int32>& rTokens)
{
    std::vector<OString> aResult;
    aResult.reserve(rTokens.size());
    for (auto const& [rName, rValue] : rTokens)
    {
        (void)rValue;
        aResult.push_back(rName);
    }
    return aResult;
}
}

MaterialTokens::MaterialTokens() = default;

MaterialTokens MaterialTokens::fromDefinitionFile(const OUString& rDefinitionFileUrl,
                                                  const OUString& rResourcePath,
                                                  const OString& rColorScheme)
{
    MaterialTokens aTokens;

    WidgetDefinitionReader aReader(rDefinitionFileUrl, rResourcePath, rColorScheme);
    if (!aReader.readTokenTables(aTokens.maColorPalettes, aTokens.maRadiusTokens,
                                 aTokens.maMetricTokens))
    {
        SAL_WARN("vcl.gdi", "MaterialTokens: could not read token tables from "
                                << rDefinitionFileUrl);
        return aTokens; // mbValid stays false
    }

    // Select the active palette exactly as read() does: prefer the requested
    // scheme, otherwise fall back to the default (light) palette.
    aTokens.maActiveScheme = rColorScheme;
    if (aTokens.maColorPalettes.find(aTokens.maActiveScheme) == aTokens.maColorPalettes.end()
        && !aTokens.maActiveScheme.isEmpty())
    {
        aTokens.maActiveScheme = OString();
    }
    auto const aActivePalette = aTokens.maColorPalettes.find(aTokens.maActiveScheme);
    if (aActivePalette == aTokens.maColorPalettes.end())
    {
        SAL_WARN("vcl.gdi", "MaterialTokens: no palette for requested scheme");
        return aTokens;
    }

    // Enforce 1:1 fidelity against the published vocabulary. Every palette scheme
    // shares the same names (readTokenTables guarantees this), so validating the
    // active palette validates all schemes.
    const bool bColorsMatch = colorNamesMatchVocabulary(aActivePalette->second, gMaterialColorRoles);
    const bool bRadiiMatch = namesMatchVocabulary(aTokens.maRadiusTokens, gMaterialShapeTokens);
    const bool bMetricsMatch = namesMatchVocabulary(aTokens.maMetricTokens, gMaterialMetricTokens);
    if (!bColorsMatch || !bRadiiMatch || !bMetricsMatch)
    {
        SAL_WARN("vcl.gdi", "MaterialTokens: definition token names diverge from the "
                            "published Material vocabulary");
        return aTokens;
    }

    aTokens.mbValid = true;
    return aTokens;
}

MaterialTokens MaterialTokens::fromThemeDefinition(const OString& rColorScheme)
{
    // definition.xml is an immutable installed resource: it cannot change while
    // soffice runs. Parsing it costs a file open plus a full XML walk of ~72 KB,
    // and several native call sites resolve a token from inside a paint or
    // primitive-decomposition helper (e.g. the Impress/Draw page grid color, the
    // Calc formula-bar and sheet-tab bands, the Base app-window surfaces). Without
    // memoisation each of those re-parsed the whole file on every repaint, which
    // is the dominant per-frame cost of the Material theme. Cache the parsed table
    // per scheme key; the returned value is a copy, so callers keep their existing
    // by-value semantics and no rendered pixel changes.
    static std::mutex aCacheMutex;
    static std::map<OString, MaterialTokens> aCache;

    {
        std::scoped_lock aGuard(aCacheMutex);
        auto aIterator = aCache.find(rColorScheme);
        if (aIterator != aCache.end())
            return aIterator->second;
    }

    OUString sResourcePath(u"$BRAND_BASE_DIR/" LIBO_SHARE_FOLDER
                           "/theme_definitions/material/"_ustr);
    rtl::Bootstrap::expandMacros(sResourcePath);
    OUString sDefinitionFile = sResourcePath + "definition.xml";
    MaterialTokens aTokens = fromDefinitionFile(sDefinitionFile, sResourcePath, rColorScheme);

    // A transient packaging or deployment failure must not poison the cache: only
    // a fully validated table is remembered, so a later successful read still wins.
    if (aTokens.isValid())
    {
        std::scoped_lock aGuard(aCacheMutex);
        aCache.emplace(rColorScheme, aTokens);
    }
    return aTokens;
}

OString MaterialTokens::computeMaterialScheme(std::string_view rAccentBase, bool bDark)
{
    // Compose the definition.xml scheme key: "<accent>" light / "<accent>-dark"
    // dark. Violet is the unnamed default, so an empty accent base yields "" for
    // light and the DARK_SCHEME key for dark -- byte-identical to the pre-accent
    // resolution path. This never mints a palette; an unknown accent simply
    // composes a key that fromDefinitionFile()/read() falls back to default on.
    OString aBase = toOString(rAccentBase);
    if (!bDark)
        return aBase;
    if (aBase.isEmpty())
        return toOString(DARK_SCHEME);
    OStringBuffer aKey(aBase);
    aKey.append("-");
    aKey.append(toOString(DARK_SCHEME));
    return aKey.makeStringAndClear();
}

MaterialTokens MaterialTokens::fromThemeDefinition(std::string_view rAccentBase, bool bDark)
{
    return fromThemeDefinition(computeMaterialScheme(rAccentBase, bDark));
}

std::optional<Color> MaterialTokens::findColor(std::string_view rRole) const
{
    return findColor(std::string_view(maActiveScheme.getStr(), maActiveScheme.getLength()), rRole);
}

std::optional<Color> MaterialTokens::findColor(std::string_view rScheme, std::string_view rRole) const
{
    auto const aPalette = maColorPalettes.find(toOString(rScheme));
    if (aPalette == maColorPalettes.end())
        return std::nullopt;
    auto const aColor = aPalette->second.find(toOString(rRole));
    if (aColor == aPalette->second.end())
        return std::nullopt;
    return aColor->second;
}

std::optional<sal_Int32> MaterialTokens::findRadius(std::string_view rName) const
{
    auto const aToken = maRadiusTokens.find(toOString(rName));
    if (aToken == maRadiusTokens.end())
        return std::nullopt;
    return aToken->second;
}

std::optional<sal_Int32> MaterialTokens::findMetric(std::string_view rName) const
{
    auto const aToken = maMetricTokens.find(toOString(rName));
    if (aToken == maMetricTokens.end())
        return std::nullopt;
    return aToken->second;
}

std::vector<OString> MaterialTokens::colorRoleNames() const
{
    std::vector<OString> aResult;
    auto const aPalette = maColorPalettes.find(maActiveScheme);
    if (aPalette == maColorPalettes.end())
        return aResult;
    aResult.reserve(aPalette->second.size());
    for (auto const& [rName, rColor] : aPalette->second)
    {
        (void)rColor;
        aResult.push_back(rName);
    }
    return aResult;
}

std::vector<OString> MaterialTokens::radiusNames() const { return sortedKeys(maRadiusTokens); }

std::vector<OString> MaterialTokens::metricNames() const { return sortedKeys(maMetricTokens); }

std::vector<OString> MaterialTokens::schemeNames() const
{
    std::vector<OString> aResult;
    aResult.reserve(maColorPalettes.size());
    for (auto const& [rScheme, rPalette] : maColorPalettes)
    {
        (void)rPalette;
        aResult.push_back(rScheme);
    }
    return aResult;
}

} // namespace vcl

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
