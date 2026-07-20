/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <o3tl/char16_t2wchar_t.hxx>
#include <unotools/resmgr.hxx>
#include <vcl/fileregistration.hxx>

#include <prewin.h>
#include <Shobjidl.h>
#include <systools/win32/comtools.hxx>
#include <versionhelpers.h>
#include <postwin.h>

namespace vcl::fileregistration
{
static void LaunchModernSettingsDialogDefaultApps()
{
    sal::systools::COMReference<IApplicationActivationManager> pIf(
        CLSID_ApplicationActivationManager, nullptr, CLSCTX_INPROC_SERVER);

    DWORD pid;
    HRESULT hr = pIf->ActivateApplication(L"windows.immersivecontrolpanel_cw5n1h2txyewy"
                                          L"!microsoft.windows.immersivecontrolpanel",
                                          L"page=SettingsPageAppsDefaults", AO_NONE, &pid);
    if (SUCCEEDED(hr))
    {
        // Do not check error because we could at least open
        // the "Default apps" setting.
        pIf->ActivateApplication(L"windows.immersivecontrolpanel_cw5n1h2txyewy"
                                 L"!microsoft.windows.immersivecontrolpanel",
                                 L"page=SettingsPageAppsDefaults"
                                 L"&target=SettingsPageAppsDefaultsDefaultAppsListView",
                                 AO_NONE, &pid);
    }
}

void LaunchRegistrationUI()
{
    try
    {
        sal::systools::CoInitializeGuard aGuard(COINIT_APARTMENTTHREADED);
        if (IsWindows10OrGreater())
        {
            LaunchModernSettingsDialogDefaultApps();
        }
        else
        {
            sal::systools::COMReference<IApplicationAssociationRegistrationUI> pIf(
                CLSID_ApplicationAssociationRegistrationUI, nullptr, CLSCTX_INPROC_SERVER);

            // LaunchAdvancedAssociationUI only works for applications registered under
            // Software\RegisteredApplications. See scp2/source/ooo/registryitem_ooo.scp
            const OUString expanded = Translate::ExpandVariables("%PRODUCTNAME %PRODUCTVERSION");
            pIf->LaunchAdvancedAssociationUI(o3tl::toW(expanded.getStr()));
        }
    }
    catch (...)
    {
        // Just ignore any error here: this is not something we need to make sure to succeed
    }
}
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab cinoptions=b1,g0,N-s cinkeys+=0=break: */
