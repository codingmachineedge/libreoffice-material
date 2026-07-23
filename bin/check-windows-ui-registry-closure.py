#!/usr/bin/env python3
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Generate and validate the WIN-SYS-016 registered UI inventory closure.

``WIN-SYS-016`` is the registry-closure gate named by
``docs/WINDOWS_UI_INVENTORY.md``. It requires a deterministic, regenerable
enumeration of every registered UI surface, each mapped to exactly one owner
and one ``WIN-`` inventory row. This tool produces that ledger.

Enumeration has two halves:

* Every tracked-or-untracked, non-ignored ``*.ui`` file discovered by the same
  Git walk that ``bin/check-windows-dialog-notification-contract.py`` uses. One
  ``.ui`` file is one surface. This includes the three notification ``.ui``
  files that the walk now sees.
* A maintained explicit list of native-only, custom-drawn, optional, and
  Windows-platform surfaces that have **no** ``.ui`` file for the walk to find
  (Start Center thumbnail view, the inline Find toolbar, application canvases,
  the MSI/updater lifecycle UI, and the native notification overlay window).

Owner mapping is the module (first path segment) for ``.ui`` surfaces and an
explicit declaration for native surfaces. Inventory-row mapping is an explicit,
reviewable table: exact-path overrides plus longest-prefix path rules. Any
surface with no confident row is assigned the explicit ``unassigned`` bucket so
the registry is an honest closure ledger rather than a guess.

Default mode validates that the checked-in registry matches a fresh
enumeration exactly: added, removed, or renamed ``.ui`` files, unmapped
surfaces, unknown inventory IDs, duplicated surfaces, and any hand-edited drift
all fail closed. Newly discovered ``unassigned`` surfaces that are not already
recorded in the checked-in baseline are reported and fail closed as part of the
exact comparison. ``--regenerate`` rewrites the registry deterministically
(stable sort, no timestamps).

This is a source-level closure ledger. It does not claim native
implementation, a successful build, or any runtime evidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "qa/windows-ui-contract/ui-registry.json"
INVENTORY_DOC = REPOSITORY / "docs/WINDOWS_UI_INVENTORY.md"

SCHEMA_VERSION = 1
CONTRACT = "windows-registered-ui-inventory-closure"
INVENTORY_ROW = "WIN-SYS-016"
PLATFORM = "windows"
GENERATOR = "bin/check-windows-ui-registry-closure.py"
UNASSIGNED = "unassigned"

INVENTORY_ID_PATTERN = re.compile(r"^WIN-[A-Z0-9]+-[0-9]+$")
_DOC_ROW_PATTERN = re.compile(r"^\|\s*(WIN-[A-Z0-9]+-[0-9]+)\s*\|")

SOURCE_NOTE = (
    "Deterministic source-level closure ledger for WIN-SYS-016. Regenerate "
    "with --regenerate. Not a claim of native implementation, a successful "
    "build, or any runtime evidence."
)

# --- Explicit inventory-row mapping table ---------------------------------
#
# The mapping is intentionally explicit and reviewable, never guessed. Exact
# overrides win over the longest matching path prefix; anything unmatched is
# recorded in the ``unassigned`` bucket. Prefix rules attribute a module (or a
# module subtree) to the inventory row the inventory document names as that
# path's owner. Prefix attribution is deliberately owner-level: it records who
# owns the surface, not that every dialog in that subtree is that exact row's
# anatomy. Per-surface refinement is future work tracked by WIN-SYS-016 itself.

OVERRIDES: Mapping[str, str] = {
    "sfx2/uiconfig/ui/startcenter.ui": "WIN-SC-001",
    "sfx2/uiconfig/ui/templatedlg.ui": "WIN-SYS-004",
    "sfx2/uiconfig/ui/documentpropertiesdialog.ui": "WIN-SYS-003",
    "sfx2/uiconfig/ui/notificationcard.ui": "WIN-SHL-003",
    "sfx2/uiconfig/ui/notificationmanager.ui": "WIN-SHL-003",
    "sfx2/uiconfig/ui/notificationstack.ui": "WIN-SHL-003",
    "cui/uiconfig/ui/optionsdialog.ui": "WIN-DLG-002",
    "svx/uiconfig/ui/findreplacedialog.ui": "WIN-DLG-005",
    "vcl/uiconfig/ui/printdialog.ui": "WIN-DLG-004",
    "vcl/uiconfig/ui/aboutbox.ui": "WIN-SYS-015",
    # WIN-SYS-015 Help/About & legacy/optional-feature dialogs (cui). The About and
    # Tip-of-the-Day surfaces are anatomy-pinned by bin/check-help-about-family.py; the
    # hyperlink/thesaurus/hyphenate/hangul-hanja/expert-config surfaces are owner-level
    # attribution only (per-surface anatomy deferred). cui has no module prefix rule, so
    # these must be enumerated explicitly to move them out of the unassigned bucket.
    "cui/uiconfig/ui/aboutdialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/tipofthedaydialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/aboutconfigdialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinkdlg.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinkdocpage.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinkinternetpage.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinkmailpage.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinknewdocpage.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyperlinkmarkdialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hyphenate.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/thesaurus.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hangulhanjaconversiondialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hangulhanjaadddialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hangulhanjaeditdictdialog.ui": "WIN-SYS-015",
    "cui/uiconfig/ui/hangulhanjaoptdialog.ui": "WIN-SYS-015",
    "desktop/uiconfig/ui/updatedialog.ui": "WIN-SYS-012",
    "desktop/uiconfig/ui/updateinstalldialog.ui": "WIN-SYS-012",
    "desktop/uiconfig/ui/updaterequireddialog.ui": "WIN-SYS-012",
    # WIN-IM-003 Impress slideshow settings. The Slide Show Settings dialog is
    # anatomy-pinned by bin/check-impress-slideshow-settings-contract.py, so it
    # is attributed to WIN-IM-003 explicitly rather than falling under the
    # sd/uiconfig/simpress/ -> WIN-IM-001 prefix rule with the rest of Impress.
    "sd/uiconfig/simpress/ui/presentationdialog.ui": "WIN-IM-003",
    # WIN-DLG-002 Options dialog (cui). The Tools > Options panes are self-evident
    # opt*page surfaces plus a few named Options sub-panes (connection-pool,
    # database registry, spelling options, security options-and-warnings,
    # LanguageTool config). cui has no module prefix rule, so these are
    # enumerated explicitly. Owner-level attribution; per-pane anatomy deferred.
    "cui/uiconfig/ui/optaccessibilitypage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optadvancedpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optasianpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optbasicidepage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optchartcolorspage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optctlpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optemailpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optfltrembedpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optfltrpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optfontspage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optgeneralpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/opthtmlpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optjsearchpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optlanguagespage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optlingupage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optonlineupdatepage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optpathspage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optproxypage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optsavepage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optsecuritypage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optuserpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/optviewpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/connpooloptions.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/dbregisterpage.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/spelloptionsdialog.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/securityoptionsdialog.ui": "WIN-DLG-002",
    "cui/uiconfig/ui/langtoolconfigpage.ui": "WIN-DLG-002",
    # WIN-DLG-001 destructive/confirmation query prompts (cui + svx + svtools +
    # vcl). Every query*.ui here is a modal confirmation/query message box
    # (delete/save/overwrite prompts, e.g. querydeletecolordialog.ui is a
    # GtkMessageDialog "Do you want to delete the color?"); savemodifieddialog.ui
    # is the form "Do you want to save your changes?" discard prompt. WIN-DLG-001
    # owns shared modal-dialog anatomy and destructive confirmation.
    "cui/uiconfig/ui/querychangelineenddialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletebitmapdialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletechartcolordialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletecolordialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletedictionarydialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletegradientdialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletehatchdialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletelineenddialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydeletelinestyledialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querydialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/queryduplicatedialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querynoloadedfiledialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querynosavefiledialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/querysavelistdialog.ui": "WIN-DLG-001",
    "cui/uiconfig/ui/queryupdategalleryfilelistdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querydeletecontourdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querydeleteobjectdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querydeletethemedialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querymodifyimagemapchangesdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querynewcontourdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querysavecontchangesdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/querysaveimagemapchangesdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/queryunlinkgraphicsdialog.ui": "WIN-DLG-001",
    "svx/uiconfig/ui/savemodifieddialog.ui": "WIN-DLG-001",
    "svtools/uiconfig/ui/querydeletedialog.ui": "WIN-DLG-001",
    "vcl/uiconfig/ui/querydialog.ui": "WIN-DLG-001",
    # WIN-SYS-009 safe mode / crash recovery / profile recovery (svx). The
    # Document Recovery wizard pages, Safe Mode, and the crash-report dialog.
    # (savemodifieddialog.ui is deliberately NOT here: it is a form save/discard
    # prompt, so it belongs with the WIN-DLG-001 confirmation cluster above.)
    "svx/uiconfig/ui/docrecoverybrokendialog.ui": "WIN-SYS-009",
    "svx/uiconfig/ui/docrecoveryprogressdialog.ui": "WIN-SYS-009",
    "svx/uiconfig/ui/docrecoveryrecoverdialog.ui": "WIN-SYS-009",
    "svx/uiconfig/ui/docrecoverysavedialog.ui": "WIN-SYS-009",
    "svx/uiconfig/ui/safemodedialog.ui": "WIN-SYS-009",
    "svx/uiconfig/ui/crashreportdlg.ui": "WIN-SYS-009",
    # WIN-CON-007 panels and side panes (svx sidebar decks). Every entry is a
    # non-dialog GtkGrid/GtkBox panel body hosted inside a sidebar deck (verified
    # no dialog toplevel), including the style-inspector, theme-selector, and
    # default-shapes panels.
    "svx/uiconfig/ui/sidebararea.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebareffect.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarempty.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarfontwork.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebargallery.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebargraphic.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarline.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarlists.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarparagraph.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarpossize.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarshadow.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebarstylespanel.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebartextcolumnspanel.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebartexteffect.ui": "WIN-CON-007",
    "svx/uiconfig/ui/sidebartextpanel.ui": "WIN-CON-007",
    "svx/uiconfig/ui/inspectortextpanel.ui": "WIN-CON-007",
    "svx/uiconfig/ui/themeselectorpanel.ui": "WIN-CON-007",
    "svx/uiconfig/ui/defaultshapespanel.ui": "WIN-CON-007",
    # WIN-DLG-004 Print dialog family (vcl printer pages / progress / CUPS
    # password + svtools printer setup). Owner-level attribution to the Print
    # dialog row; printdialog.ui itself is already an exact override above.
    "vcl/uiconfig/ui/printerdevicepage.ui": "WIN-DLG-004",
    "vcl/uiconfig/ui/printerpaperpage.ui": "WIN-DLG-004",
    "vcl/uiconfig/ui/printerpropertiesdialog.ui": "WIN-DLG-004",
    "vcl/uiconfig/ui/printprogressdialog.ui": "WIN-DLG-004",
    "vcl/uiconfig/ui/cupspassworddialog.ui": "WIN-DLG-004",
    "svtools/uiconfig/ui/printersetupdialog.ui": "WIN-DLG-004",
    # WIN-SYS-011 generic errors and conflicts (vcl). "no content"/"no printer"
    # generic error boxes and the document-locked conflict prompt.
    "vcl/uiconfig/ui/errornocontentdialog.ui": "WIN-SYS-011",
    "vcl/uiconfig/ui/errornoprinterdialog.ui": "WIN-SYS-011",
    "vcl/uiconfig/ui/openlockedquerybox.ui": "WIN-SYS-011",
    # WIN-SYS-013 restart-required lifecycle (svtools). The "restart to apply"
    # prompt shown after install/update/settings changes that need a relaunch.
    "svtools/uiconfig/ui/restartdialog.ui": "WIN-SYS-013",
    # WIN-BA-002 XForms model / form-design surfaces (svx). Data Navigator, the
    # XForms add-* model editors, the namespaces dialog, the XForms options page,
    # and the form-design property/navigator/link dialogs. (*menu.ui form context
    # menus are handled by the WIN-NAV-002 context-menu cluster instead.)
    "svx/uiconfig/ui/datanavigator.ui": "WIN-BA-002",
    "svx/uiconfig/ui/addconditiondialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/adddataitemdialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/addinstancedialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/addmodeldialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/addnamespacedialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/addsubmissiondialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/namespacedialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/xformspage.ui": "WIN-BA-002",
    "svx/uiconfig/ui/formfielddialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/formlinkwarndialog.ui": "WIN-BA-002",
    "svx/uiconfig/ui/formnavigator.ui": "WIN-BA-002",
    "svx/uiconfig/ui/formpropertydialog.ui": "WIN-BA-002",
    # WIN-WR-005 review / tracked changes (svx). The shared Accept-or-Reject
    # Changes manager, redline toolbar control, and redline filter/view pages.
    "svx/uiconfig/ui/acceptrejectchangesdialog.ui": "WIN-WR-005",
    "svx/uiconfig/ui/redlinecontrol.ui": "WIN-WR-005",
    "svx/uiconfig/ui/redlinefilterpage.ui": "WIN-WR-005",
    "svx/uiconfig/ui/redlineviewpage.ui": "WIN-WR-005",
    # WIN-NAV-002 context menus (svx + editeng + vcl + cui + svtools). Every
    # entry is a GtkMenu-rooted right-click/pop-up menu (verified). The screenshot
    # test harness menu (vcl/screenshotmenu.ui) is excluded as a non-product
    # surface, and the bibliography autofilter menu is already covered by the
    # extensions/uiconfig/sbibliography/ prefix rule.
    "svx/uiconfig/ui/cellmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/charsetmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/clipboardmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/colsmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/filtermenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/formdatamenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/formnavimenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/functionmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/gallerymenu1.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/gallerymenu2.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/imapmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/presetmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/rowsmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/rulermenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/selectionmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/stylemenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/xmlsecstatmenu.ui": "WIN-NAV-002",
    "svx/uiconfig/ui/zoommenu.ui": "WIN-NAV-002",
    "editeng/uiconfig/ui/spellmenu.ui": "WIN-NAV-002",
    "vcl/uiconfig/ui/editmenu.ui": "WIN-NAV-002",
    "cui/uiconfig/ui/entrycontextmenu.ui": "WIN-NAV-002",
    "svtools/uiconfig/ui/fileviewmenu.ui": "WIN-NAV-002",
    # WIN-SYS-007 certificates / digital signatures / macro security (cui + svx).
    # Certificate path, timestamp-authority URL, signature-line insert/sign,
    # stored-web-connection credentials, and the document classification dialog.
    "cui/uiconfig/ui/certdialog.ui": "WIN-SYS-007",
    "cui/uiconfig/ui/tsaurldialog.ui": "WIN-SYS-007",
    "cui/uiconfig/ui/signatureline.ui": "WIN-SYS-007",
    "cui/uiconfig/ui/signsignatureline.ui": "WIN-SYS-007",
    "cui/uiconfig/ui/storedwebconnectiondialog.ui": "WIN-SYS-007",
    "svx/uiconfig/ui/classificationdialog.ui": "WIN-SYS-007",
    # WIN-SYS-005 extension manager / additions (cui). The "Get more extensions"
    # additions browser and its per-entry fragment.
    "cui/uiconfig/ui/additionsdialog.ui": "WIN-SYS-005",
    "cui/uiconfig/ui/additionsfragment.ui": "WIN-SYS-005",
    # WIN-SYS-002 export flows (svtools). The graphic (PNG/JPEG/...) export
    # options dialog.
    "svtools/uiconfig/ui/graphicexport.ui": "WIN-SYS-002",
}

# (path_prefix, inventory_id). Prefixes always end with "/" so a module name is
# matched on a full segment boundary. Longest matching prefix wins.
PREFIX_RULES: Sequence[tuple[str, str]] = (
    ("sw/", "WIN-WR-001"),
    ("sc/", "WIN-CA-001"),
    ("sd/uiconfig/simpress/", "WIN-IM-001"),
    ("sd/uiconfig/sdraw/", "WIN-DR-001"),
    ("dbaccess/", "WIN-BA-001"),
    ("reportdesign/", "WIN-BA-002"),
    ("starmath/", "WIN-MA-001"),
    ("chart2/", "WIN-CH-001"),
    ("basctl/", "WIN-SYS-006"),
    ("xmlsecurity/", "WIN-SYS-007"),
    ("uui/", "WIN-SYS-011"),
    ("fpicker/", "WIN-DLG-003"),
    ("filter/", "WIN-SYS-002"),
    ("writerperfect/", "WIN-SYS-002"),
    ("desktop/", "WIN-SYS-005"),
    ("sfx2/", "WIN-SHL-001"),
    # Clean single-owner extension/formula subtrees. Each has a real
    # ``.../ui/`` path segment and one honest owning inventory row, so a subtree
    # prefix is safe (unlike the flat shared cui/svx modules, which get exact
    # overrides instead). spropctrlr = form-control property browser and
    # sabpilot = the form/data-source auto-pilots (Base form workflows,
    # WIN-BA-002); sbibliography = the Bibliography Database workspace
    # (WIN-BA-001); formula = the Function Wizard (Calc function controls,
    # WIN-CA-002). scanner/ is deliberately left unmapped (documented floor).
    ("extensions/uiconfig/spropctrlr/", "WIN-BA-002"),
    ("extensions/uiconfig/sabpilot/", "WIN-BA-002"),
    ("extensions/uiconfig/sbibliography/", "WIN-BA-001"),
    ("formula/", "WIN-CA-002"),
)

# Native-only / custom-drawn / optional / platform surfaces with no .ui file.
# Each is declared explicitly with its owner module and inventory row.
NATIVE_SURFACES: Sequence[Mapping[str, str]] = (
    {
        "surface": "native:calc-grid-canvas",
        "owner": "sc",
        "inventory_id": "WIN-CA-003",
        "note": "Custom-drawn Calc sheet grid/editing canvas; no uiconfig .ui.",
    },
    {
        "surface": "native:draw-canvas",
        "owner": "sd",
        "inventory_id": "WIN-DR-001",
        "note": "Custom-drawn Draw editing canvas; no uiconfig .ui.",
    },
    {
        "surface": "native:find-toolbar",
        "owner": "svx",
        "inventory_id": "WIN-INP-005",
        "note": "Inline Find toolbar search control built in code, not a .ui.",
    },
    {
        "surface": "native:impress-slide-canvas",
        "owner": "sd",
        "inventory_id": "WIN-IM-001",
        "note": "Custom-drawn Impress slide editing canvas; no uiconfig .ui.",
    },
    {
        "surface": "native:msi-install-lifecycle-ui",
        "owner": "instsetoo_native",
        "inventory_id": "WIN-SYS-013",
        "note": "Windows MSI install/repair/uninstall UI; platform installer, no .ui.",
    },
    {
        "surface": "native:notification-overlay-window",
        "owner": "sfx2",
        "inventory_id": "WIN-SHL-003",
        "note": "Bottom-right notification overlay host window; native shell surface.",
    },
    {
        "surface": "native:start-center-thumbnails-view",
        "owner": "sfx2",
        "inventory_id": "WIN-SC-005",
        "note": "Custom-drawn Start Center recent/template thumbnail grid.",
    },
    {
        "surface": "native:updater-lifecycle-ui",
        "owner": "extensions",
        "inventory_id": "WIN-SYS-012",
        "note": "Native updater check/download/stage UI; no uiconfig .ui.",
    },
    {
        "surface": "native:window-title-bars",
        "owner": "vcl",
        "inventory_id": "WIN-NAV-007",
        "note": "Native Windows window/floating title bars drawn by vcl/win.",
    },
    {
        "surface": "native:writer-document-canvas",
        "owner": "sw",
        "inventory_id": "WIN-WR-002",
        "note": "Custom-drawn Writer document/page canvas; no uiconfig .ui.",
    },
)


class ValidationError(RuntimeError):
    """Raised when the registered UI inventory closure is invalid."""


# --- Inventory document ----------------------------------------------------


def parse_valid_inventory_ids(doc_path: Path) -> frozenset[str]:
    """Return the set of stable ``WIN-`` IDs defined by the inventory table."""

    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValidationError(
            f"cannot read inventory document {doc_path}: {error}"
        ) from error
    ids = {
        match.group(1)
        for line in text.splitlines()
        for match in [_DOC_ROW_PATTERN.match(line)]
        if match is not None
    }
    if not ids:
        raise ValidationError(
            f"inventory document {doc_path} defines no WIN- inventory rows"
        )
    if INVENTORY_ROW not in ids:
        raise ValidationError(
            f"inventory document {doc_path} is missing the {INVENTORY_ROW} row"
        )
    return frozenset(ids)


# --- Surface enumeration ---------------------------------------------------


def repository_ui_paths(repo_root: Path) -> list[str]:
    """Return tracked plus untracked, non-ignored ``.ui`` files from Git.

    This reuses the walking rules of
    ``bin/check-windows-dialog-notification-contract.py``: a single
    ``git ls-files`` over cached and non-ignored other files, filtered to paths
    that still exist in the working tree, returned as sorted POSIX-relative
    strings.
    """

    command = [
        "git",
        "-C",
        str(repo_root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        "*.ui",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise ValidationError(
            f"cannot run git to discover .ui files: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationError(f"git .ui discovery failed: {detail}")

    seen: set[str] = set()
    paths: list[str] = []
    for raw_path in completed.stdout.decode(
        "utf-8", errors="surrogateescape"
    ).split("\0"):
        if not raw_path:
            continue
        # ``git ls-files --cached`` reports tracked files that are deleted in
        # the working tree; treat those as absent so the closure never records
        # a surface that no longer exists.
        if not (repo_root / PurePosixPath(raw_path)).is_file():
            continue
        posix = PurePosixPath(raw_path).as_posix()
        if posix not in seen:
            seen.add(posix)
            paths.append(posix)
    return sorted(paths)


def owner_for_ui_path(ui_path: str) -> str:
    """Return the owning module (first path segment) for a ``.ui`` surface."""

    head = PurePosixPath(ui_path).parts[0] if PurePosixPath(ui_path).parts else ""
    if not head:
        raise ValidationError(f"cannot determine owner module for {ui_path!r}")
    return head


def inventory_for_ui_path(ui_path: str) -> tuple[str, str]:
    """Map a ``.ui`` path to ``(inventory_id, mapped_by)``.

    Exact overrides win; otherwise the longest matching path prefix wins;
    otherwise the surface is recorded as ``unassigned``.
    """

    if ui_path in OVERRIDES:
        return OVERRIDES[ui_path], "override"
    best_prefix = ""
    best_id = ""
    for prefix, inventory_id in PREFIX_RULES:
        if ui_path.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_id = inventory_id
    if best_prefix:
        return best_id, "prefix"
    return UNASSIGNED, "unassigned"


def build_ui_surfaces(repo_root: Path) -> list[dict[str, str]]:
    """Enumerate and map every discovered ``.ui`` surface."""

    surfaces: list[dict[str, str]] = []
    for ui_path in repository_ui_paths(repo_root):
        inventory_id, mapped_by = inventory_for_ui_path(ui_path)
        surfaces.append(
            {
                "kind": "ui-file",
                "surface": ui_path,
                "owner": owner_for_ui_path(ui_path),
                "inventory_id": inventory_id,
                "mapped_by": mapped_by,
            }
        )
    return sorted(surfaces, key=lambda item: item["surface"])


def build_native_surfaces() -> list[dict[str, str]]:
    """Return the maintained explicit native-only surface list, normalized."""

    surfaces: list[dict[str, str]] = []
    for declared in NATIVE_SURFACES:
        surfaces.append(
            {
                "kind": "native",
                "surface": declared["surface"],
                "owner": declared["owner"],
                "inventory_id": declared["inventory_id"],
                "mapped_by": "native",
                "note": declared["note"],
            }
        )
    return sorted(surfaces, key=lambda item: item["surface"])


# --- Mapping-table integrity ----------------------------------------------


def validate_mapping_tables(valid_ids: frozenset[str]) -> None:
    """Fail closed on a malformed or internally inconsistent mapping table."""

    # Every referenced inventory ID must be a real inventory row.
    for ui_path, inventory_id in OVERRIDES.items():
        if inventory_id not in valid_ids:
            raise ValidationError(
                f"override for {ui_path!r} names unknown inventory ID "
                f"{inventory_id!r}"
            )
    seen_prefixes: set[str] = set()
    for prefix, inventory_id in PREFIX_RULES:
        if not prefix.endswith("/"):
            raise ValidationError(
                f"prefix rule {prefix!r} must end with '/' to match a segment"
            )
        if prefix in seen_prefixes:
            raise ValidationError(f"duplicate prefix rule {prefix!r}")
        seen_prefixes.add(prefix)
        if inventory_id not in valid_ids:
            raise ValidationError(
                f"prefix rule {prefix!r} names unknown inventory ID "
                f"{inventory_id!r}"
            )

    native_keys: set[str] = set()
    for declared in NATIVE_SURFACES:
        surface = declared["surface"]
        if not surface.startswith("native:"):
            raise ValidationError(
                f"native surface {surface!r} must use a 'native:' key"
            )
        if surface in native_keys:
            raise ValidationError(f"duplicate native surface {surface!r}")
        native_keys.add(surface)
        if not declared["owner"]:
            raise ValidationError(f"native surface {surface!r} has no owner")
        if not declared.get("note"):
            raise ValidationError(f"native surface {surface!r} has no note")
        if declared["inventory_id"] not in valid_ids:
            raise ValidationError(
                f"native surface {surface!r} names unknown inventory ID "
                f"{declared['inventory_id']!r}"
            )


def _check_unique_surfaces(surfaces: Sequence[Mapping[str, str]]) -> None:
    """Reject duplicate surface identities (one surface, one owner/one row)."""

    seen: set[str] = set()
    for surface in surfaces:
        key = surface["surface"]
        if key in seen:
            raise ValidationError(f"duplicate surface entry: {key}")
        seen.add(key)


def _validate_surface_ids(
    surfaces: Iterable[Mapping[str, str]], valid_ids: frozenset[str]
) -> None:
    for surface in surfaces:
        inventory_id = surface["inventory_id"]
        if inventory_id == UNASSIGNED:
            continue
        if inventory_id not in valid_ids:
            raise ValidationError(
                f"surface {surface['surface']!r} maps to unknown inventory ID "
                f"{inventory_id!r}"
            )


# --- Registry assembly -----------------------------------------------------


def build_registry(
    repo_root: Path, valid_ids: frozenset[str] | None = None
) -> dict[str, object]:
    """Produce the full, deterministic registry structure from the tree."""

    repo_root = repo_root.resolve()
    if valid_ids is None:
        valid_ids = parse_valid_inventory_ids(repo_root / "docs/WINDOWS_UI_INVENTORY.md")

    validate_mapping_tables(valid_ids)

    ui_surfaces = build_ui_surfaces(repo_root)
    native_surfaces = build_native_surfaces()

    _check_unique_surfaces(ui_surfaces)
    _check_unique_surfaces(native_surfaces)
    native_keys = {item["surface"] for item in native_surfaces}
    ui_keys = {item["surface"] for item in ui_surfaces}
    collision = native_keys & ui_keys
    if collision:
        raise ValidationError(
            "native surface key collides with a .ui surface: "
            + ", ".join(sorted(collision))
        )

    _validate_surface_ids(ui_surfaces, valid_ids)
    _validate_surface_ids(native_surfaces, valid_ids)

    all_surfaces = ui_surfaces + native_surfaces
    unassigned = sum(1 for s in all_surfaces if s["inventory_id"] == UNASSIGNED)
    assigned = len(all_surfaces) - unassigned

    mapping = {
        "overrides": [
            {"surface": path, "inventory_id": OVERRIDES[path]}
            for path in sorted(OVERRIDES)
        ],
        "prefix_rules": [
            {"prefix": prefix, "inventory_id": inventory_id}
            for prefix, inventory_id in sorted(PREFIX_RULES)
        ],
    }

    counts = {
        "ui_surfaces": len(ui_surfaces),
        "native_surfaces": len(native_surfaces),
        "total_surfaces": len(all_surfaces),
        "assigned": assigned,
        "unassigned": unassigned,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "inventory_row": INVENTORY_ROW,
        "platform": PLATFORM,
        "generator": GENERATOR,
        "source_note": SOURCE_NOTE,
        "unassigned_id": UNASSIGNED,
        "counts": counts,
        "mapping": mapping,
        "native_surfaces": native_surfaces,
        "surfaces": ui_surfaces,
    }


# --- Registry file I/O -----------------------------------------------------


def serialize_registry(registry: Mapping[str, object]) -> str:
    """Serialize deterministically: stable order, 2-space indent, trailing LF."""

    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def write_registry(registry_path: Path, registry: Mapping[str, object]) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialize_registry(registry))


def read_registry(registry_path: Path) -> dict[str, object]:
    try:
        with registry_path.open("r", encoding="utf-8") as stream:
            text = stream.read()
    except OSError as error:
        raise ValidationError(
            f"cannot read registry {registry_path}: {error}"
        ) from error
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"registry {registry_path} is not valid JSON: {error}"
        ) from error
    if not isinstance(data, dict):
        raise ValidationError(f"registry {registry_path} must be a JSON object")
    return data


# --- Comparison ------------------------------------------------------------


def _surface_index(
    surfaces: object,
) -> dict[str, Mapping[str, object]]:
    index: dict[str, Mapping[str, object]] = {}
    if not isinstance(surfaces, list):
        raise ValidationError("registry surfaces section must be a list")
    for surface in surfaces:
        if not isinstance(surface, dict) or "surface" not in surface:
            raise ValidationError("registry surface entry is malformed")
        key = surface["surface"]
        if not isinstance(key, str):
            raise ValidationError("registry surface key must be a string")
        if key in index:
            raise ValidationError(f"duplicate surface entry in registry: {key}")
        index[key] = surface
    return index


def _format_keys(keys: Iterable[str], limit: int = 12) -> str:
    values = sorted(keys)
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f"; ... and {len(values) - limit} more"
    return "; ".join(shown) + suffix


def _diff_surface_section(
    section: str,
    expected: object,
    actual: object,
) -> list[str]:
    expected_index = _surface_index(expected)
    actual_index = _surface_index(actual)
    failures: list[str] = []

    missing = set(expected_index) - set(actual_index)
    stale = set(actual_index) - set(expected_index)
    if missing:
        new_unassigned = {
            key
            for key in missing
            if expected_index[key].get("inventory_id") == UNASSIGNED
        }
        assigned_missing = missing - new_unassigned
        if assigned_missing:
            failures.append(
                f"{len(assigned_missing)} {section} surface(s) missing from "
                f"registry: {_format_keys(assigned_missing)}"
            )
        if new_unassigned:
            failures.append(
                f"{len(new_unassigned)} new unassigned {section} surface(s) "
                f"beyond the checked-in baseline: {_format_keys(new_unassigned)}"
            )
    if stale:
        failures.append(
            f"{len(stale)} {section} registry surface(s) with no matching "
            f"source surface: {_format_keys(stale)}"
        )

    for key in sorted(set(expected_index) & set(actual_index)):
        if expected_index[key] != actual_index[key]:
            failures.append(
                f"{section} surface {key!r} drifted from its generated mapping: "
                f"expected {expected_index[key]!r}, found {actual_index[key]!r}"
            )
    return failures


def compare_registry(
    expected: Mapping[str, object], actual: Mapping[str, object]
) -> None:
    """Fail closed with a focused diff when ``actual`` is not a fresh registry."""

    failures: list[str] = []

    failures.extend(
        _diff_surface_section(
            "ui-file", expected.get("surfaces"), actual.get("surfaces")
        )
    )
    failures.extend(
        _diff_surface_section(
            "native",
            expected.get("native_surfaces"),
            actual.get("native_surfaces"),
        )
    )

    for field in (
        "schema_version",
        "contract",
        "inventory_row",
        "platform",
        "generator",
        "source_note",
        "unassigned_id",
        "counts",
        "mapping",
    ):
        if expected.get(field) != actual.get(field):
            failures.append(
                f"registry field {field!r} drifted: expected "
                f"{expected.get(field)!r}, found {actual.get(field)!r}"
            )

    if failures:
        raise ValidationError("\n".join(failures))


def validate_contract(repo_root: Path, registry_path: Path) -> dict[str, object]:
    """Validate the checked-in registry against a fresh enumeration."""

    expected = build_registry(repo_root)
    actual = read_registry(registry_path)
    compare_registry(expected, actual)
    return expected


# --- CLI -------------------------------------------------------------------


def _counts_text(counts: Mapping[str, object]) -> str:
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPOSITORY,
        help="repository root to scan (default: script repository)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="registry JSON (default: qa/windows-ui-contract/ui-registry.json)",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the registry deterministically from a fresh enumeration",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = args.repo_root.resolve()
    registry_path = (
        args.registry.resolve()
        if args.registry is not None
        else repo_root / "qa/windows-ui-contract/ui-registry.json"
    )
    try:
        if args.regenerate:
            registry = build_registry(repo_root)
            write_registry(registry_path, registry)
        expected = validate_contract(repo_root, registry_path)
    except ValidationError as error:
        print(
            f"Windows UI registry closure failed:\n{error}",
            file=sys.stderr,
        )
        return 1

    counts = expected["counts"]
    assert isinstance(counts, dict)
    print(
        "Windows UI registry closure passed: "
        f"{counts['total_surfaces']} registered surfaces"
    )
    print(f"  counts: {_counts_text(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
