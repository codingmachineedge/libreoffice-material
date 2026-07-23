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

#include "AppView.hxx"
#include <strings.hrc>
#include <comphelper/diagnose_ex.hxx>
#include <tools/mapunit.hxx>
#include <vcl/event.hxx>
#include <vcl/weld/WaitObject.hxx>
#include <vcl/weld/Window.hxx>
#include <com/sun/star/sdbcx/XTablesSupplier.hpp>
#include <com/sun/star/sdb/XQueriesSupplier.hpp>
#include "AppDetailView.hxx"
#include "AppSwapWindow.hxx"
#include <vcl/settings.hxx>
#include <vcl/svapp.hxx>
#include <vcl/MaterialTokens.hxx>
#include <tools/color.hxx>
#include "AppTitleWindow.hxx"
#include "AppController.hxx"

#include <cstdlib>
#include <optional>
#include <string_view>

using namespace ::dbaui;

namespace
{
// Guarded Material Base rail/workspace hairline (docs/design/12-base-math-shared.md
// 12.1). Same env + high-contrast guard idiom as sc/source/ui/app/inputwin.cxx's
// formula-bar resolver: only while the documented Material file-widget theme is
// active (and not forced high contrast) does the panel|detail divider resolve its
// tint; otherwise the 1px divider box keeps the default background.
bool lcl_isMaterialBaseActive()
{
    const char* pThemeName = std::getenv("VCL_FILE_WIDGET_THEME");
    if (!pThemeName || std::string_view(pThemeName) != "material")
        return false;
    if (Application::GetSettings().GetStyleSettings().GetHighContrastMode())
        return false;
    return true;
}

// The rail's right hairline is @outline-variant (12.1 "Database nav rail":
// "right hairline @outline-variant at stroke-thin").
std::optional<Color> lcl_getMaterialPanelHairline()
{
    if (!lcl_isMaterialBaseActive())
        return std::nullopt;
    const bool bDark = Application::GetSettings().GetStyleSettings().GetWindowColor().IsDark();
    const vcl::MaterialTokens aTokens
        = vcl::MaterialTokens::fromThemeDefinition(bDark ? "dark"_ostr : OString());
    if (!aTokens.isValid())
        return std::nullopt;
    return aTokens.findColor("outline-variant");
}
} // namespace
using namespace ::com::sun::star::uno;
using namespace ::com::sun::star::ucb;
using namespace ::com::sun::star::sdb;
using namespace ::com::sun::star::sdbc;
using namespace ::com::sun::star::sdbcx;
using namespace ::com::sun::star::datatransfer::clipboard;
using namespace ::com::sun::star::lang;
using namespace ::com::sun::star::container;
using ::com::sun::star::sdb::application::NamedDatabaseObject;

OAppBorderWindow::OAppBorderWindow(OApplicationView* pParent, PreviewMode ePreviewMode)
    : InterimItemWindow(pParent, u"dbaccess/ui/appborderwindow.ui"_ustr, u"AppBorderWindow"_ustr, false)
    , m_xPanelParent(m_xBuilder->weld_container(u"panel"_ustr))
    , m_xDetailViewParent(m_xBuilder->weld_container(u"detail"_ustr))
    , m_xPanelDetailHairline(m_xBuilder->weld_container(u"panelhairline"_ustr))
    , m_xView(pParent)
{
    SetStyle(GetStyle() | WB_DIALOGCONTROL);

    // "Database" heads the rail, so it uses the kicker variant of the shared
    // OTitleWindow (docs/design 12.1 "Rail kicker"); the task-pane and object-list
    // headings keep the default heading style.
    m_xPanel.reset(new OTitleWindow(m_xPanelParent.get(), STR_DATABASE,
                                    OTitleWindow::TitleStyle::Kicker));
    std::shared_ptr<OChildWindow> xSwap = std::make_shared<OApplicationSwapWindow>(m_xPanel->getChildContainer(), *this);

    m_xPanel->setChildWindow(xSwap);

    // Material rail/workspace divider: tint the 1px hairline box @outline-variant
    // while the Material theme is active, else leave the default background.
    if (const std::optional<Color> oHairline = lcl_getMaterialPanelHairline())
        m_xPanelDetailHairline->set_background(*oHairline);

    m_xDetailView.reset(new OApplicationDetailView(m_xDetailViewParent.get(), *this, ePreviewMode));

    ImplInitSettings();
}

OAppBorderWindow::~OAppBorderWindow()
{
    disposeOnce();
}

void OAppBorderWindow::dispose()
{
    // destroy children
    m_xPanel.reset();
    m_xDetailView.reset();
    m_xPanelDetailHairline.reset();
    m_xPanelParent.reset();
    m_xDetailViewParent.reset();
    m_xView.reset();
    InterimItemWindow::dispose();
}

void OAppBorderWindow::GetFocus()
{
    if (m_xPanel)
        m_xPanel->GrabFocus();
}

OApplicationSwapWindow* OAppBorderWindow::getPanel() const
{
    return static_cast<OApplicationSwapWindow*>(m_xPanel->getChildWindow());
}

OApplicationView::OApplicationView( vcl::Window* pParent
                                    ,const Reference< XComponentContext >& _rxOrb
                                    ,OApplicationController& _rAppController
                                    ,PreviewMode _ePreviewMode
                                   ) :
    ODataView( pParent, _rAppController, _rxOrb, WB_DIALOGCONTROL )
    ,m_rAppController( _rAppController )
{
    m_pWin = VclPtr<OAppBorderWindow>::Create(this,_ePreviewMode);
    m_pWin->Show();

    ImplInitSettings();
}

OApplicationView::~OApplicationView()
{
    disposeOnce();
}

void OApplicationView::dispose()
{
    stopComponentListening(m_xObject);
    m_xObject.clear();
    m_pWin->Hide();
    m_pWin.disposeAndClear();
    ODataView::dispose();
}

void OApplicationView::createIconAutoMnemonics( MnemonicGenerator& _rMnemonics )
{
    if ( m_pWin && m_pWin->getPanel() )
        m_pWin->getPanel()->createIconAutoMnemonics( _rMnemonics );
}

void OApplicationView::setTaskExternalMnemonics( MnemonicGenerator const & _rMnemonics )
{
    if ( m_pWin && m_pWin->getDetailView() )
        m_pWin->getDetailView()->setTaskExternalMnemonics( _rMnemonics );
}

void OApplicationView::DataChanged( const DataChangedEvent& rDCEvt )
{
    ODataView::DataChanged( rDCEvt );

    if ( (rDCEvt.GetType() == DataChangedEventType::FONTS) ||
        (rDCEvt.GetType() == DataChangedEventType::DISPLAY) ||
        (rDCEvt.GetType() == DataChangedEventType::FONTSUBSTITUTION) ||
        ((rDCEvt.GetType() == DataChangedEventType::SETTINGS) &&
        (rDCEvt.GetFlags() & AllSettingsFlags::STYLE)) )
    {
        ImplInitSettings();
        Invalidate();
    }
}

void OApplicationView::resizeDocumentView(tools::Rectangle& _rPlayground)
{
    if ( m_pWin && !_rPlayground.IsEmpty() )
    {
        Size aFLSize = LogicToPixel(Size(3, 3), MapMode(MapUnit::MapAppFont));
        _rPlayground.Move( aFLSize.Width(),aFLSize.Height() );
        Size aOldSize = _rPlayground.GetSize();
        _rPlayground.SetSize( Size(aOldSize.Width() - 2*aFLSize.Width(), aOldSize.Height() - 2*aFLSize.Height()) );

        m_pWin->SetPosSizePixel(_rPlayground.TopLeft() , _rPlayground.GetSize() );
    }
    // just for completeness: there is no space left, we occupied it all ...
    _rPlayground.SetPos( _rPlayground.BottomRight() );
    _rPlayground.SetSize( Size( 0, 0 ) );
}

OApplicationView::ChildFocusState OApplicationView::getChildFocus() const
{
    ChildFocusState eChildFocus;
    if( m_pWin && getPanel() && getPanel()->HasChildPathFocus() )
        eChildFocus = PANELSWAP;
    else if ( m_pWin && getDetailView() && getDetailView()->HasChildPathFocus() )
        eChildFocus = DETAIL;
    else
        eChildFocus = NONE;
    return eChildFocus;
}

bool OApplicationView::PreNotify( NotifyEvent& rNEvt )
{
    switch(rNEvt.GetType())
    {
        case NotifyEventType::KEYINPUT:
        {
            const KeyEvent* pKeyEvent = rNEvt.GetKeyEvent();
            // give the pane the chance to intercept mnemonic accelerators
            // #i34790#
            if ( getPanel() && getPanel()->interceptKeyInput( *pKeyEvent ) )
                return true;
        }
        break;
        default:
        break;
    }

    return ODataView::PreNotify(rNEvt);
}

IClipboardTest* OApplicationView::getActiveChild() const
{
    IClipboardTest* pTest = nullptr;
    if (getChildFocus() == DETAIL)
        pTest = getDetailView();
    return pTest;
}

bool OApplicationView::isCopyAllowed()
{
    IClipboardTest* pTest = getActiveChild();
    return pTest && pTest->isCopyAllowed();
}

bool OApplicationView::isCutAllowed()
{
    IClipboardTest* pTest = getActiveChild();
    return pTest && pTest->isCutAllowed();
}

bool OApplicationView::isPasteAllowed()
{
    IClipboardTest* pTest = getActiveChild();
    return pTest && pTest->isPasteAllowed();
}

void OApplicationView::copy()
{
    IClipboardTest* pTest = getActiveChild();
    if ( pTest )
        pTest->copy();
}

void OApplicationView::cut()
{
    IClipboardTest* pTest = getActiveChild();
    if ( pTest )
        pTest->cut();
}

void OApplicationView::paste()
{
    IClipboardTest* pTest = getActiveChild();
    if ( pTest )
        pTest->paste();
}

OUString OApplicationView::getQualifiedName(const weld::TreeIter* _pEntry) const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getQualifiedName( _pEntry );
}

bool OApplicationView::isLeaf(const weld::TreeView& rTreeView, const weld::TreeIter& rEntry) const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return OApplicationDetailView::isLeaf(rTreeView, rEntry);
}

bool OApplicationView::isALeafSelected() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->isALeafSelected();
}

void OApplicationView::selectAll()
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->selectAll();
}

bool OApplicationView::isSortUp() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->isSortUp();
}

void OApplicationView::sortDown()
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->sortDown();
}

void OApplicationView::sortUp()
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->sortUp();
}

bool OApplicationView::isFilled() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->isFilled();
}

ElementType OApplicationView::getElementType() const
{
    OSL_ENSURE(m_pWin && getDetailView() && getPanel(),"Detail view is NULL! -> GPF");
    return getDetailView()->HasChildPathFocus() ? getDetailView()->getElementType() : getPanel()->getElementType();
}

sal_Int32 OApplicationView::getSelectionCount() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getSelectionCount();
}

sal_Int32 OApplicationView::getElementCount() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getElementCount();
}

void OApplicationView::getSelectionElementNames( std::vector< OUString>& _rNames ) const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->getSelectionElementNames( _rNames );
}

void OApplicationView::describeCurrentSelectionForControl(const weld::TreeView& rControl, Sequence<NamedDatabaseObject>& out_rSelectedObjects)
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->describeCurrentSelectionForControl(rControl, out_rSelectedObjects);
}

vcl::Window* OApplicationView::getMenuParent() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getMenuParent();
}

void OApplicationView::adjustMenuPosition(const weld::TreeView& rControl, ::Point& rPos) const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->adjustMenuPosition(rControl, rPos);
}

void OApplicationView::describeCurrentSelectionForType( const ElementType _eType, Sequence< NamedDatabaseObject >& _out_rSelectedObjects )
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->describeCurrentSelectionForType( _eType, _out_rSelectedObjects );
}

void OApplicationView::selectElements(const Sequence< OUString>& _aNames)
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->selectElements( _aNames );
}

std::unique_ptr<weld::TreeIter> OApplicationView::elementAdded(ElementType eType,const OUString& _rName, const Any& _rObject )
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->elementAdded(eType,_rName,_rObject);
}

void OApplicationView::elementRemoved(ElementType eType,const OUString& _rName )
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->elementRemoved(eType,_rName);
}

void OApplicationView::elementReplaced(ElementType _eType
                                                    ,const OUString& _rOldName
                                                    ,const OUString& _rNewName )
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->elementReplaced(_eType, _rOldName, _rNewName );
}

void OApplicationView::clearPages()
{
    OSL_ENSURE(m_pWin && getDetailView() && getPanel(),"Detail view is NULL! -> GPF");
    getPanel()->clearSelection();
    getDetailView()->clearPages();
}

void OApplicationView::selectContainer(ElementType _eType)
{
    OSL_ENSURE(m_pWin && getPanel(),"Detail view is NULL! -> GPF");
    weld::WaitObject aWO(GetFrameWeld());
    getPanel()->selectContainer(_eType);
}

std::unique_ptr<weld::TreeIter> OApplicationView::getEntry(const Point& rPosPixel) const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getEntry(rPosPixel);
}

PreviewMode OApplicationView::getPreviewMode() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->getPreviewMode();
}

bool OApplicationView::isPreviewEnabled() const
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    return getDetailView()->isPreviewEnabled();
}

void OApplicationView::switchPreview(PreviewMode _eMode)
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    getDetailView()->switchPreview(_eMode);
}

void OApplicationView::showPreview(const Reference< XContent >& _xContent)
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    stopComponentListening(m_xObject);
    m_xObject = nullptr;
    getDetailView()->showPreview(_xContent);
}

void OApplicationView::showPreview( const OUString& _sDataSourceName,
                                    const css::uno::Reference< css::sdbc::XConnection>& _xConnection,
                                    const OUString& _sName,
                                    bool _bTable)
{
    OSL_ENSURE(m_pWin && getDetailView(),"Detail view is NULL! -> GPF");
    if ( !isPreviewEnabled() )
        return;

    stopComponentListening(m_xObject);
    m_xObject = nullptr;
    try
    {
        Reference<XNameAccess> xNameAccess;
        if ( _bTable )
        {
            Reference<XTablesSupplier> xSup(_xConnection,UNO_QUERY);
            if ( xSup.is() )
                xNameAccess = xSup->getTables();
        }
        else
        {
            Reference<XQueriesSupplier> xSup(_xConnection,UNO_QUERY);
            if ( xSup.is() )
                xNameAccess = xSup->getQueries();
        }
        if ( xNameAccess.is() && xNameAccess->hasByName(_sName) )
            m_xObject.set(xNameAccess->getByName(_sName),UNO_QUERY);
    }
    catch( const Exception& )
    {
        DBG_UNHANDLED_EXCEPTION("dbaccess");
    }
    if ( m_xObject.is() )
        startComponentListening(m_xObject);
    getDetailView()->showPreview(_sDataSourceName,_sName,_bTable);
}

void OApplicationView::GetFocus()
{
    if (m_pWin && getChildFocus() == NONE)
        m_pWin->GrabFocus();
}

void OApplicationView::_disposing( const css::lang::EventObject& /*_rSource*/ )
{
    if ( m_pWin && getDetailView() )
        showPreview(nullptr);
}

void OApplicationView::ImplInitSettings()
{
    // FIXME RenderContext
    const StyleSettings& rStyleSettings = GetSettings().GetStyleSettings();

    vcl::Font aFont = rStyleSettings.GetFieldFont();
    aFont.SetColor( rStyleSettings.GetWindowTextColor() );
    SetPointFont(*GetOutDev(), aFont);

    SetTextColor( rStyleSettings.GetFieldTextColor() );
    SetTextFillColor();

    SetBackground( rStyleSettings.GetFieldColor() );
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
