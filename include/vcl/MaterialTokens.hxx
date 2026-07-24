/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 *
 */

#pragma once

#include <vcl/dllapi.h>
#include <tools/color.hxx>
#include <rtl/string.hxx>
#include <rtl/ustring.hxx>
#include <map>
#include <optional>
#include <string_view>
#include <vector>

namespace vcl
{
/**
 * A queryable, read-only view of the Material widget definition's semantic
 * token tables: the color palette (per scheme), corner-radius shape tokens and
 * integer metric tokens.
 *
 * Every value is sourced exclusively from the theme definition file
 * (vcl/uiconfig/theme_definitions/material/definition.xml) through the existing
 * WidgetDefinitionReader reading path. This class hard-codes no palette,
 * radius or metric literal, so its data can never drift from the definition it
 * mirrors: the single source of truth stays the XML. The published token-name
 * vocabulary (MaterialColorRole / MaterialShapeToken / MaterialMetricToken) is
 * validated 1:1 against that file both at load time (isValid() turns false on
 * any mismatch) and statically by bin/check-material-token-accessor.py.
 *
 * Callers use this table wherever native application code needs a Material
 * color, radius or metric by name instead of repeating a raw hex literal or an
 * ad-hoc pixel constant.
 */
class VCL_DLLPUBLIC MaterialTokens
{
public:
    /** Palette scheme keys, matching the `scheme` attribute in definition.xml.
        The default (light) palette carries no scheme attribute, hence "". */
    static constexpr std::string_view LIGHT_SCHEME = "";
    static constexpr std::string_view DARK_SCHEME = "dark";

    MaterialTokens();

    /** Build from an explicit definition file URL. @p rColorScheme selects the
        active palette ("" = default/light); an unknown scheme falls back to the
        default palette, matching WidgetDefinitionReader::read(). */
    static MaterialTokens fromDefinitionFile(const OUString& rDefinitionFileUrl,
                                             const OUString& rResourcePath,
                                             const OString& rColorScheme = OString());

    /** Build from the bundled Material theme definition at
        $BRAND_BASE_DIR/<share>/theme_definitions/material/definition.xml. */
    static MaterialTokens fromThemeDefinition(const OString& rColorScheme = OString());

    /** Compose the active palette scheme key from a bounded accent base name and
        the dark flag, matching the definition.xml scheme naming exactly:
          bDark == false -> "<accent>"       (Violet is the unnamed default "")
          bDark == true  -> "<accent>-dark"  (Violet is "dark")
        @p rAccentBase is the light-scheme name ("" = Violet, "blue", "teal",
        "green", "amber", "rose"); the dark variants append "-dark". Violet with
        any dark flag resolves to the byte-identical default ("" / "dark") path,
        so genuine captures never drift. This mints no palette: an unknown accent
        composes a key that fromDefinitionFile()/read() falls back to default on. */
    static OString computeMaterialScheme(std::string_view rAccentBase, bool bDark);

    /** Accent-aware convenience over fromThemeDefinition(): resolves the active
        scheme via computeMaterialScheme(rAccentBase, bDark). Violet + any dark
        flag stays byte-identical to the default/"dark" path. */
    static MaterialTokens fromThemeDefinition(std::string_view rAccentBase, bool bDark);

    /** True only when the file was read, every token section validated, and the
        loaded token names matched the published vocabulary exactly. */
    bool isValid() const { return mbValid; }

    /** The active palette scheme this instance resolves color roles against. */
    const OString& getActiveScheme() const { return maActiveScheme; }

    /** Active-scheme color lookup by semantic role name (e.g. "primary",
        "on-surface-variant"). std::nullopt for an unknown role. */
    std::optional<Color> findColor(std::string_view rRole) const;
    /** Color lookup in a named scheme ("" = light, "dark"). */
    std::optional<Color> findColor(std::string_view rScheme, std::string_view rRole) const;

    /** Corner-radius token lookup by name (e.g. "corner-toolbar"). */
    std::optional<sal_Int32> findRadius(std::string_view rName) const;
    /** Integer metric token lookup by name (e.g. "size-compact-control"). */
    std::optional<sal_Int32> findMetric(std::string_view rName) const;

    /** Sorted token-name vocabularies (active scheme for colors). */
    std::vector<OString> colorRoleNames() const;
    std::vector<OString> radiusNames() const;
    std::vector<OString> metricNames() const;
    std::vector<OString> schemeNames() const;

private:
    bool mbValid = false;
    OString maActiveScheme;
    std::map<OString, std::map<OString, Color>> maColorPalettes;
    std::map<OString, sal_Int32> maRadiusTokens;
    std::map<OString, sal_Int32> maMetricTokens;
};

} // namespace vcl

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
