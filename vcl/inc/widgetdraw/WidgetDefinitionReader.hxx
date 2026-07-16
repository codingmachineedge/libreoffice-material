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
#include <widgetdraw/WidgetDefinition.hxx>
#include <map>
#include <memory>
#include <rtl/string.hxx>
#include <rtl/ustring.hxx>
#include <tools/XmlWalker.hxx>

namespace vcl
{
class VCL_DLLPUBLIC WidgetDefinitionReader
{
private:
    OUString m_rDefinitionFile;
    OUString m_rResourcePath;
    OString m_aScheme;
    std::map<OString, Color> m_aColorTokens;
    bool m_bValid;

    SAL_DLLPRIVATE bool readColor(OString const& rValue, Color& rColor) const;
    SAL_DLLPRIVATE bool readColorPalette(tools::XmlWalker& rWalker,
                                         std::map<OString, Color>& rColorTokens) const;

    SAL_DLLPRIVATE void readDefinition(tools::XmlWalker& rWalker,
                                       WidgetDefinition& rWidgetDefinition, ControlType eType,
                                       const std::map<OString, sal_Int32>& rRadiusTokens);

    SAL_DLLPRIVATE void readPart(tools::XmlWalker& rWalker,
                                 const std::shared_ptr<WidgetDefinitionPart>& rpPart,
                                 const std::map<OString, sal_Int32>& rRadiusTokens);

    SAL_DLLPRIVATE void readDrawingDefinition(tools::XmlWalker& rWalker,
                                              const std::shared_ptr<WidgetDefinitionState>& rStates,
                                              const std::map<OString, sal_Int32>& rRadiusTokens);

public:
    WidgetDefinitionReader(OUString aDefinitionFile, OUString aResourcePath,
                           OString aScheme = OString());
    bool read(WidgetDefinition& rWidgetDefinition);
};

} // end vcl namespace

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
