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

#include <sal/config.h>
#include <config_emscripten.h>
#include <config_features.h>

#include <desktop/dllapi.h>

#include <app.hxx>
#include "cmdlineargs.hxx"
#include "cmdlinehelp.hxx"

// needed before sal/main.h to avoid redefinition of macros
#include <prewin.h>

#if defined _WIN32
#include <o3tl/test_info.hxx>
#include <systools/win32/test_desktop.hxx>
#endif

#include <rtl/bootstrap.hxx>
#include <sal/main.h>
#include <tools/extendapplicationenvironment.hxx>
#include <vcl/svmain.hxx>

#if HAVE_FEATURE_BREAKPAD
#include <desktop/crashreport.hxx>
#endif

#include <postwin.h>

#ifdef _WIN32
// getenv / _putenv_s / _stricmp for the default-on Material activation that runs at
// the top of soffice_main() below. Plain C runtime headers only: this must stay
// usable before any framework/UNO initialization.
#include <stdlib.h>
#include <string.h>
#endif

#ifdef ANDROID
#  include <jni.h>
#  include <android/log.h>
#  include <salhelper/thread.hxx>

#  define LOGTAG "LibreOffice/sofficemain"
#  define LOGI(...) ((void)__android_log_print(ANDROID_LOG_INFO, LOGTAG, __VA_ARGS__))
#endif

extern "C" int DESKTOP_DLLPUBLIC soffice_main()
{
#ifdef _WIN32
    // Fork default: this build ships the Material widget theme active on Windows.
    // Upstream keeps the file-defined widget-draw path and the "material" theme
    // selection opt-in behind two environment variables that a stock product never
    // sets -- vcl/source/gdi/salgdilayout.cxx gates FileDefinitionWidgetDraw on
    // VCL_DRAW_WIDGETS_FROM_FILE, and the theme-name guards read VCL_FILE_WIDGET_THEME
    // -- so the shipped Material assets (vcl/Package_theme_definitions.mk installs
    // material/definition.xml) stay dormant. Default both variables ON here, at the
    // very top of soffice_main() before any consumer in this process reads them
    // (initWidgetDrawBackends and the getenv() theme guards all run later, inside
    // SVMain()). A user override always wins, and the whole activation can be turned
    // off with LIBREOFFICE_MATERIAL_THEME=off. Plain C runtime only -- this runs
    // before any framework/UNO/VCL initialization, so no OUString/VCL/UNO here. This
    // is source-declared wiring only; it makes no runtime or visual-verification claim.
    {
        // Full opt-out: LIBREOFFICE_MATERIAL_THEME=off (or =0), case-insensitive,
        // leaves the process environment exactly as the user set it.
        const char* pMaterialOptOut = getenv("LIBREOFFICE_MATERIAL_THEME");
        const bool bMaterialOptedOut = pMaterialOptOut != nullptr
            && (_stricmp(pMaterialOptOut, "off") == 0 || _stricmp(pMaterialOptOut, "0") == 0);
        if (!bMaterialOptedOut)
        {
            const char* pWidgetTheme = getenv("VCL_FILE_WIDGET_THEME");
            if (pWidgetTheme != nullptr)
            {
                // User override wins: never overwrite a theme the user already chose.
                // Only fill in the draw switch when it is unset AND the pre-set theme
                // is non-empty (an explicit empty theme still means "no file widgets").
                if (pWidgetTheme[0] != '\0'
                    && getenv("VCL_DRAW_WIDGETS_FROM_FILE") == nullptr)
                    _putenv_s("VCL_DRAW_WIDGETS_FROM_FILE", "1");
            }
            else
            {
                // Default on: select the Material theme and, unless the user already
                // set it, enable the file-defined widget-draw path.
                _putenv_s("VCL_FILE_WIDGET_THEME", "material");
                if (getenv("VCL_DRAW_WIDGETS_FROM_FILE") == nullptr)
                    _putenv_s("VCL_DRAW_WIDGETS_FROM_FILE", "1");
            }
        }
    }
#endif

#if defined _WIN32
    // If this is a UI test, we may need to switch to a dedicated desktop
    if (o3tl::IsRunningUITest())
        sal::systools::maybeCreateTestDesktop();
#endif

    sal_detail_initialize(sal::detail::InitializeSoffice, nullptr);

#if HAVE_FEATURE_BREAKPAD
    CrashReporter::installExceptionHandler();
#endif

#if defined ANDROID
    try {
        rtl::Bootstrap::setIniFilename("file:///assets/program/lofficerc");
#endif
    tools::extendApplicationEnvironment();

#if defined __EMSCRIPTEN__ && !HAVE_EMSCRIPTEN_JSPI
    //HACK: Qt5 QWasmEventDispatcher::processEvents
    // (qtbase/src/plugins/platforms/wasm/qwasmeventdispatcher.cpp) calls
    // emscripten_set_main_loop_arg with simulateInfiniteLoop == true, and as we use
    // -fwasm-exceptions (cf. solenv/gbuild/platform/EMSCRIPTEN_INTEL_GCC.mk), aDesktop allocated on
    // the stack would run into the issue warned about at
    // <https://emscripten.org/docs/api_reference/emscripten.h.html#c.emscripten_set_main_loop>
    // "Note: Currently, using the new Wasm exception handling and simulate_infinite_loop == true at
    // the same time does not work yet in C++ projects that have objects with destructors on the
    // stack at the time of the call."  (Also see the mailing list thread at
    // <https://groups.google.com/g/emscripten-discuss/c/xpWDVwyJu-M> "Implementation of
    // -fexceptions and -fwasm-exceptions" for why such automatic variables are destroyed with
    // -fwasm-exceptions but not with -fexceptions.)  So deliberately leak the Desktop instance
    // here:
    new desktop::Desktop();
#else
    desktop::Desktop aDesktop;
#endif
    // This string is used during initialization of the Gtk+ VCL module
    Application::SetAppName( u"soffice"_ustr );

    // handle --version and --help already here, otherwise they would be handled
    // after VCL initialization that might fail if $DISPLAY is not set
    const desktop::CommandLineArgs& rCmdLineArgs = desktop::Desktop::GetCommandLineArgs();
    const OUString& aUnknown( rCmdLineArgs.GetUnknown() );
    if ( !aUnknown.isEmpty() )
    {
        desktop::Desktop::InitApplicationServiceManager();
        desktop::displayCmdlineHelp( aUnknown );
        return EXIT_FAILURE;
    }
    if ( rCmdLineArgs.IsHelp() )
    {
        desktop::Desktop::InitApplicationServiceManager();
        desktop::displayCmdlineHelp( OUString() );
        return EXIT_SUCCESS;
    }
    if ( rCmdLineArgs.IsVersion() )
    {
        desktop::Desktop::InitApplicationServiceManager();
        desktop::displayVersion();
        return EXIT_SUCCESS;
    }

    return SVMain();
#if defined ANDROID
    } catch (const css::uno::Exception &e) {
        LOGI("Unhandled UNO exception: '%s'",
             OUStringToOString(e.Message, RTL_TEXTENCODING_UTF8).getStr());
        throw; // to get exception type printed
    }
#endif
}

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
