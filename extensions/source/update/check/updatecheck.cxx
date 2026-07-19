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

#include <iterator>
#include <string_view>

#include <comphelper/hash.hxx>
#include <comphelper/scopeguard.hxx>
#include <config_folders.h>

#include "updatecheck.hxx"

#include <cppuhelper/implbase.hxx>
#include <com/sun/star/beans/XFastPropertySet.hpp>
#include <com/sun/star/deployment/UpdateInformationProvider.hpp>
#include <com/sun/star/frame/Desktop.hpp>
#include <com/sun/star/office/Quickstart.hpp>
#include <com/sun/star/system/SystemShellExecute.hpp>
#include <com/sun/star/system/SystemShellExecuteException.hpp>
#include <com/sun/star/system/SystemShellExecuteFlags.hpp>
#include <com/sun/star/task/XJob.hpp>
#include <com/sun/star/task/XJobExecutor.hpp>

#include <rtl/bootstrap.hxx>
#include <osl/process.h>
#include <osl/file.hxx>
#include <sal/macros.h>
#include <sal/log.hxx>
#include <comphelper/diagnose_ex.hxx>

#ifdef _WIN32
#include <o3tl/safeCoInitUninit.hxx>
#include <o3tl/char16_t2wchar_t.hxx>
#include <objbase.h>
#include <sddl.h>
#include <shlobj.h>
#include <windows.h>
#endif

#include "onlinecheck.hxx"
#include "updateprotocol.hxx"
#include "updatecheckconfig.hxx"

namespace beans = css::beans ;
namespace deployment = css::deployment ;
namespace lang = css::lang ;
namespace c3s = css::system ;
namespace task = css::task ;
namespace uno = css::uno ;

constexpr OUStringLiteral PROPERTY_TITLE = u"BubbleHeading";
constexpr OUStringLiteral PROPERTY_TEXT = u"BubbleText";
constexpr OUStringLiteral PROPERTY_SHOW_BUBBLE = u"BubbleVisible";
constexpr OUStringLiteral PROPERTY_CLICK_HDL = u"MenuClickHDL";
constexpr OUString PROPERTY_SHOW_MENUICON = u"MenuIconVisible"_ustr;

bool verifyUpdateFile(const OUString& rFileName, const DownloadSource& rSource)
{
    if (!isTrustedMaterialUpdateSource(rSource) || rFileName.isEmpty()
        || !rFileName.endsWith(OUString::Concat(u"/") + rSource.FileName))
        return false;

    osl::DirectoryItem aItem;
    if (osl::DirectoryItem::get(rFileName, aItem) != osl::FileBase::E_None)
        return false;

    osl::FileStatus aStatus(osl_FileStatus_Mask_FileSize);
    if (aItem.getFileStatus(aStatus) != osl::FileBase::E_None
        || static_cast<sal_Int64>(aStatus.getFileSize()) != rSource.Size)
    {
        return false;
    }

    osl::File aFile(rFileName);
    if (aFile.open(osl_File_OpenFlag_Read) != osl::FileBase::E_None)
        return false;

    comphelper::Hash aHash(comphelper::HashType::SHA256);
    for (;;)
    {
        sal_uInt8 aBuffer[64 * 1024];
        sal_uInt64 nRead = 0;
        if (aFile.read(aBuffer, sizeof(aBuffer), nRead) != osl::FileBase::E_None)
            return false;
        if (nRead == 0)
            break;
        aHash.update(aBuffer, nRead);
    }

    const OString aActualHash(comphelper::hashToString(aHash.finalize()));
    return OStringToOUString(aActualHash, RTL_TEXTENCODING_ASCII_US) == rSource.Sha256;
}

#ifdef _WIN32
namespace
{
void cleanupStagedWindowsInstaller(void* pInstallerLock, const OUString& rInstallerURL,
                                   const OUString& rDirectoryURL)
{
    if (pInstallerLock)
        CloseHandle(static_cast<HANDLE>(pInstallerLock));
    if (!rInstallerURL.isEmpty())
        osl_removeFile(rInstallerURL.pData);
    if (!rDirectoryURL.isEmpty())
        osl_removeDirectory(rDirectoryURL.pData);
}

bool stageVerifiedWindowsInstaller(const OUString& rSourceURL, const DownloadSource& rSource,
                                   OUString& rInstallerSystemPath, OUString& rInstallerURL,
                                   OUString& rDirectoryURL, void*& rInstallerLock)
{
    rInstallerSystemPath.clear();
    rInstallerURL.clear();
    rDirectoryURL.clear();
    rInstallerLock = nullptr;

    if (!isTrustedMaterialUpdateSource(rSource) || rSourceURL.isEmpty()
        || !rSourceURL.endsWith(OUString::Concat(u"/") + rSource.FileName))
    {
        return false;
    }

    OUString aSourceSystemPath;
    if (osl::FileBase::getSystemPathFromFileURL(rSourceURL, aSourceSystemPath)
        != osl::FileBase::E_None)
    {
        return false;
    }

    PWSTR pLocalAppData = nullptr;
    if (FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData, KF_FLAG_CREATE, nullptr,
                                    &pLocalAppData)))
    {
        return false;
    }
    const OUString aLocalAppData(o3tl::toU(pLocalAppData));
    CoTaskMemFree(pLocalAppData);

    GUID aGuid;
    wchar_t aGuidBuffer[40] = {};
    if (FAILED(CoCreateGuid(&aGuid)) || StringFromGUID2(aGuid, aGuidBuffer, std::size(aGuidBuffer)) == 0)
        return false;

    const OUString aDirectorySystemPath
        = aLocalAppData + u"\\LibreOfficeMaterialUpdate-"_ustr + o3tl::toU(aGuidBuffer);
    const OUString aInstallerSystemPath
        = aDirectorySystemPath + u"\\"_ustr + rSource.FileName;

    PSECURITY_DESCRIPTOR pSecurityDescriptor = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(
            L"D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;OW)", SDDL_REVISION_1,
            &pSecurityDescriptor, nullptr))
    {
        return false;
    }
    comphelper::ScopeGuard aSecurityGuard([&]() { LocalFree(pSecurityDescriptor); });
    SECURITY_ATTRIBUTES aSecurityAttributes
        = { static_cast<DWORD>(sizeof(SECURITY_ATTRIBUTES)), pSecurityDescriptor, FALSE };

    if (!CreateDirectoryW(o3tl::toW(aDirectorySystemPath.getStr()), &aSecurityAttributes))
        return false;

    HANDLE hSource = INVALID_HANDLE_VALUE;
    HANDLE hDestination = INVALID_HANDLE_VALUE;
    comphelper::ScopeGuard aCleanup([&]() {
        if (hSource != INVALID_HANDLE_VALUE)
            CloseHandle(hSource);
        if (hDestination != INVALID_HANDLE_VALUE)
            CloseHandle(hDestination);
        DeleteFileW(o3tl::toW(aInstallerSystemPath.getStr()));
        RemoveDirectoryW(o3tl::toW(aDirectorySystemPath.getStr()));
    });

    const DWORD nDirectoryAttributes
        = GetFileAttributesW(o3tl::toW(aDirectorySystemPath.getStr()));
    if (nDirectoryAttributes == INVALID_FILE_ATTRIBUTES
        || (nDirectoryAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0)
    {
        return false;
    }

    hSource = CreateFileW(o3tl::toW(aSourceSystemPath.getStr()), GENERIC_READ, FILE_SHARE_READ,
                          nullptr, OPEN_EXISTING,
                          FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (hSource == INVALID_HANDLE_VALUE)
        return false;

    hDestination = CreateFileW(o3tl::toW(aInstallerSystemPath.getStr()),
                               GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ,
                               &aSecurityAttributes, CREATE_NEW,
                               FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (hDestination == INVALID_HANDLE_VALUE)
        return false;

    LARGE_INTEGER aSourceSize;
    if (!GetFileSizeEx(hSource, &aSourceSize) || aSourceSize.QuadPart != rSource.Size)
        return false;

    comphelper::Hash aHash(comphelper::HashType::SHA256);
    sal_Int64 nTotalBytes = 0;
    for (;;)
    {
        sal_uInt8 aBuffer[64 * 1024];
        DWORD nRead = 0;
        if (!ReadFile(hSource, aBuffer, static_cast<DWORD>(sizeof(aBuffer)), &nRead, nullptr))
            return false;
        if (nRead == 0)
            break;

        DWORD nOffset = 0;
        while (nOffset < nRead)
        {
            DWORD nWritten = 0;
            if (!WriteFile(hDestination, aBuffer + nOffset, nRead - nOffset, &nWritten, nullptr)
                || nWritten == 0)
            {
                return false;
            }
            nOffset += nWritten;
        }
        aHash.update(aBuffer, nRead);
        nTotalBytes += nRead;
        if (nTotalBytes > rSource.Size)
            return false;
    }

    const OUString aActualHash
        = OStringToOUString(comphelper::hashToString(aHash.finalize()),
                            RTL_TEXTENCODING_ASCII_US);
    LARGE_INTEGER aBeginning = {};
    if (nTotalBytes != rSource.Size || aActualHash != rSource.Sha256
        || !FlushFileBuffers(hDestination)
        || !SetFilePointerEx(hDestination, aBeginning, nullptr, FILE_BEGIN))
    {
        return false;
    }

    if (osl::FileBase::getFileURLFromSystemPath(aDirectorySystemPath, rDirectoryURL)
            != osl::FileBase::E_None
        || osl::FileBase::getFileURLFromSystemPath(aInstallerSystemPath, rInstallerURL)
               != osl::FileBase::E_None)
    {
        return false;
    }

    CloseHandle(hSource);
    hSource = INVALID_HANDLE_VALUE;
    rInstallerSystemPath = aInstallerSystemPath;
    rInstallerLock = hDestination;
    hDestination = INVALID_HANDLE_VALUE;
    aCleanup.dismiss();
    return true;
}
}
#endif

// Returns the URL of the release note for the given position
OUString getReleaseNote(const UpdateInfo& rInfo, sal_uInt8 pos, bool autoDownloadEnabled)
{
    for (auto const& elem : rInfo.ReleaseNotes)
    {
        if( pos == elem.Pos )
        {
            if( (pos > 2) || !autoDownloadEnabled || elem.URL2.isEmpty() )
                return elem.URL;
        }
        else if( (pos == elem.Pos2) && ((1 == elem.Pos) || (2 == elem.Pos)) && autoDownloadEnabled )
            return elem.URL2;
    }

    return OUString();
}


namespace
{

OUString getBuildId()
{
    OUString aPathVal(u"${$BRAND_BASE_DIR/" LIBO_ETC_FOLDER "/" SAL_CONFIGFILE("version") ":buildid}"_ustr);
    rtl::Bootstrap::expandMacros(aPathVal);
    return aPathVal;
}


bool isObsoleteUpdateInfo(std::u16string_view rBuildId)
{
    return rBuildId != getBuildId() && !rBuildId.empty();
}


OUString getImageFromFileName(const OUString& aFile)
{
#ifndef _WIN32
    OUString aUnpackPath;
    if( osl_getExecutableFile(&aUnpackPath.pData) == osl_Process_E_None )
    {
        sal_uInt32 lastIndex = aUnpackPath.lastIndexOf('/');
        if ( lastIndex > 0 )
        {
            aUnpackPath = OUString::Concat(aUnpackPath.subView( 0, lastIndex+1 )) +
                "unpack_update";
        }

        oslFileHandle hOut = nullptr;
        oslProcess hProcess = nullptr;

        OUString aSystemPath;
        osl::File::getSystemPathFromFileURL(aFile, aSystemPath);

        oslProcessError rc = osl_executeProcess_WithRedirectedIO(
            aUnpackPath.pData,                                  // [in] Image name
            &aSystemPath.pData, 1,                              // [in] Arguments
            osl_Process_WAIT | osl_Process_NORMAL,              // [in] Options
            nullptr,                                               // [in] Security
            nullptr,                                               // [in] Working directory
            nullptr, 0,                                            // [in] Environment variables
            &hProcess,                                          // [out] Process handle
            nullptr, &hOut, nullptr                                   // [out] File handles for redirected I/O
        );

        if( osl_Process_E_None == rc )
        {
            // Create a guard to ensure correct cleanup in its dtor in any case
            comphelper::ScopeGuard g([hOut, hProcess] () {
                osl_closeFile(hOut);
                osl_freeProcessHandle(hProcess);
            });

            oslProcessInfo aInfo;
            aInfo.Size = sizeof(oslProcessInfo);

            if( osl_Process_E_None == osl_getProcessInfo(hProcess, osl_Process_EXITCODE, &aInfo) )
            {
                if( 0 == aInfo.Code )
                {
                    char       szBuffer[4096];
                    sal_uInt64 nBytesRead = 0;
                    const sal_uInt64 nBytesToRead = sizeof(szBuffer) - 1;

                    OUString aImageName;
                    while( osl_File_E_None == osl_readFile(hOut, szBuffer, nBytesToRead, &nBytesRead) )
                    {
                        char *pc = szBuffer + nBytesRead;
                        do
                        {
                            *pc = '\0'; --pc;
                        }
                        while( ('\n' == *pc) || ('\r' == *pc) );

                        aImageName += OUString(szBuffer, pc - szBuffer + 1, osl_getThreadTextEncoding());

                        if( nBytesRead < nBytesToRead )
                            break;
                    }

                    if( osl::FileBase::E_None == osl::FileBase::getFileURLFromSystemPath(aImageName, aImageName) )
                        return aImageName;
                }
            }
        }
    }
#endif

    return aFile;
}


uno::Reference< beans::XPropertySet > createMenuBarUI(
    const uno::Reference< uno::XComponentContext >& xContext,
    const uno::Reference< task::XJob >& xJob)
{
    if( !xContext.is() )
        throw uno::RuntimeException(
            u"UpdateCheckJob: empty component context"_ustr, uno::Reference< uno::XInterface > () );

    uno::Reference< lang::XMultiComponentFactory > xServiceManager(xContext->getServiceManager());
    if( !xServiceManager.is() )
        throw uno::RuntimeException(
            u"UpdateCheckJob: unable to obtain service manager from component context"_ustr, uno::Reference< uno::XInterface > () );

    uno::Reference< beans::XPropertySet > xMenuBarUI(
            xServiceManager->createInstanceWithContext( u"com.sun.star.setup.UpdateCheckUI"_ustr, xContext ),
            uno::UNO_QUERY_THROW);

    xMenuBarUI->setPropertyValue( PROPERTY_CLICK_HDL, uno::Any( xJob ) );

    return xMenuBarUI;
}


typedef sal_Bool (* OnlineCheckFunc) ();

class UpdateCheckThread : public WorkerThread
{

public:
    UpdateCheckThread( osl::Condition& rCondition,
        const uno::Reference<uno::XComponentContext>& xContext,
        rtl::Reference<UpdateCheck> const & controller );

    virtual void SAL_CALL join() override;
    virtual void SAL_CALL terminate() override;
    virtual void cancel() override;

    void cancelAsSoonAsPossible();

protected:
    virtual ~UpdateCheckThread() override;

    virtual void SAL_CALL run() override;
    virtual void SAL_CALL onTerminated() override;

    /* Wrapper around checkForUpdates */
    bool runCheck( bool & rbExtensionsChecked );

private:

    /* Used to avoid dialup login windows (on platforms we know how to double this) */
    static bool hasInternetConnection()
    {
#ifdef _WIN32
        return WNT_hasInternetConnection();
#else
        return true;
#endif
    }

    /* Creates a new instance of UpdateInformationProvider and returns this instance */
    uno::Reference<deployment::XUpdateInformationProvider> createProvider()
    {
        osl::MutexGuard aGuard(m_aMutex);
        m_xProvider = deployment::UpdateInformationProvider::create(m_xContext);
        return m_xProvider;
    };

    /* Returns the remembered instance of UpdateInformationProvider if any */
    uno::Reference<deployment::XUpdateInformationProvider> getProvider()
        { osl::MutexGuard aGuard(m_aMutex); return m_xProvider; };

    /* Releases the remembered instance of UpdateInformationProvider if any */
    void clearProvider()
        { osl::MutexGuard aGuard(m_aMutex); m_xProvider.clear(); };

    osl::Mutex      m_aMutex;

protected:
    osl::Condition& m_aCondition;

private:
    const uno::Reference<uno::XComponentContext> m_xContext;
    uno::Reference<deployment::XUpdateInformationProvider> m_xProvider;
    rtl::Reference<UpdateCheck> m_controller;
    bool m_cancelAsSoonAsPossible;
};


class ManualUpdateCheckThread : public UpdateCheckThread
{
public:
    ManualUpdateCheckThread( osl::Condition& rCondition, const uno::Reference<uno::XComponentContext>& xContext ) :
        UpdateCheckThread(rCondition, xContext, {}) {};

    virtual void SAL_CALL run() override;
};


class MenuBarButtonJob : public ::cppu::WeakImplHelper< task::XJob >
{
public:
    explicit MenuBarButtonJob(const rtl::Reference< UpdateCheck >& rUpdateCheck);

    // XJob
    virtual uno::Any SAL_CALL execute(const uno::Sequence<beans::NamedValue>&) override;

private:
    rtl::Reference< UpdateCheck > m_aUpdateCheck;
};

class DownloadThread :  public WorkerThread
{
public:
    DownloadThread(
        osl::Condition& rCondition,
        const uno::Reference<uno::XComponentContext>& xContext,
        const rtl::Reference< DownloadInteractionHandler >& rHandler,
        const OUString& rURL,
        const OUString& rCanonicalFileName );

    virtual void SAL_CALL run() override;
    virtual void cancel() override;
    virtual void SAL_CALL suspend() override;
    virtual void SAL_CALL onTerminated() override;

protected:
    virtual ~DownloadThread() override;

private:
    osl::Condition& m_aCondition;
    const uno::Reference<uno::XComponentContext> m_xContext;
    const OUString m_aURL;
    const OUString m_aCanonicalFileName;
    Download m_aDownload;
};



UpdateCheckThread::UpdateCheckThread( osl::Condition& rCondition,
                                      const uno::Reference<uno::XComponentContext>& xContext,
                                      rtl::Reference<UpdateCheck> const & controller ) :
    m_aCondition(rCondition),
    m_xContext(xContext),
    m_controller(controller),
    m_cancelAsSoonAsPossible(false)
{
    createSuspended();

    // actually run the thread
    resume();
}


UpdateCheckThread::~UpdateCheckThread()
{
}


void SAL_CALL
UpdateCheckThread::terminate()
{
    // Cancel potentially hanging http request ..
    cancel();
    // .. before terminating
    osl::Thread::terminate();
}


void SAL_CALL
UpdateCheckThread::join()
{
    uno::Reference< deployment::XUpdateInformationProvider > xProvider(getProvider());

    // do not join during an update check until #i73893# is fixed
    if( ! xProvider.is() )
    {
        osl::Thread::join();
    }
}


void
UpdateCheckThread::cancel()
{
    uno::Reference< deployment::XUpdateInformationProvider > xProvider(getProvider());

    if( xProvider.is() )
        xProvider->cancel();
}

void UpdateCheckThread::cancelAsSoonAsPossible() {
    {
        osl::MutexGuard g(m_aMutex);
        m_cancelAsSoonAsPossible = true;
    }
    m_aCondition.set();
}

bool
UpdateCheckThread::runCheck( bool & rbExtensionsChecked )
{
    bool ret = false;
    UpdateState eUIState = UPDATESTATE_NO_UPDATE_AVAIL;

    UpdateInfo aInfo;
    rtl::Reference< UpdateCheck > aController(UpdateCheck::get());

    if( checkForUpdates(aInfo, m_xContext, aController->getInteractionHandler(), createProvider()) )
    {
        aController->setUpdateInfo(aInfo);
        eUIState = UpdateCheck::getUIState(aInfo);
        ret = true;
    }
    else
        aController->setCheckFailedState();

    // We will only look for extension updates, when there is no 'check for office updates' dialog open
    // and when there was no office update found
    if ( ( eUIState != UPDATESTATE_UPDATE_AVAIL ) &&
         ( eUIState != UPDATESTATE_UPDATE_NO_DOWNLOAD ) &&
         !aController->isDialogShowing() &&
         !rbExtensionsChecked )
    {
        bool bHasExtensionUpdates = checkForExtensionUpdates( m_xContext );
        aController->setHasExtensionUpdates( bHasExtensionUpdates );
        if ( bHasExtensionUpdates )
            aController->setUIState( UPDATESTATE_EXT_UPD_AVAIL );
        rbExtensionsChecked = true;
    }

    // joining with this thread is safe again
    clearProvider();
    return ret;
}


void SAL_CALL
UpdateCheckThread::onTerminated()
{
    delete this;
}


void SAL_CALL
UpdateCheckThread::run()
{
    osl_setThreadName("UpdateCheckThread");

    TimeValue systime;
    TimeValue nExtCheckTime;
    osl_getSystemTime( &nExtCheckTime );

    osl::Condition::Result aResult = osl::Condition::result_timeout;
    TimeValue tv = { 10, 0 };

    // Initial wait to avoid doing further time consuming tasks during start-up
    aResult = m_aCondition.wait(&tv);
    {
        osl::MutexGuard g(m_aMutex);
        if (m_cancelAsSoonAsPossible) {
            goto done;
        }
    }

    try {
        bool bExtensionsChecked = false;

        while( schedule() )
        {
            /* Use cases:
             *  a) manual check requested from auto check thread - "last check" should not be checked (one time)
             *     a1) manual check was requested in the middle of a running auto check,
             *         condition is set
             *     a2) manual check was requested while waiting for a retry,
             *         condition is set
             *     a3) manual check was requested while waiting for time to next
             *         scheduled check elapsing, condition is set
             *     a4) manual check was requested during initial wait, condition is set
             *  b) check interval got changed, condition may be set - same sub-cases as a),
             *     but "last check" should be honored
             *  c) normal auto check mode, condition not set - "last check" should be honored
             */

            // Accessing const members without synchronization
            rtl::Reference< UpdateCheck > aController(UpdateCheck::get());
            rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext, *aController);

            // FIXME: remember last & offset ?
            sal_Int64 last   = rModel->getLastChecked();
            sal_Int64 offset = rModel->getCheckInterval();

            rModel.clear();

            // last == 0 means check immediately
            bool checkNow = last <= 0;

            // Reset the condition to avoid busy loops
            if( osl::Condition::result_ok == aResult )
            {
                m_aCondition.reset();
                aResult = osl::Condition::result_timeout;
                checkNow = aController->isDialogShowing();
            }

            if( ! checkNow )
            {
                osl_getSystemTime(&systime);

                // Go back to sleep until time has elapsed
                sal_Int64 next = last + offset;
                if( last + offset > systime.Seconds )
                {
                    // This can not be > 32 Bit for now ..
                    tv.Seconds = static_cast< sal_Int32 > (next - systime.Seconds);
                    aResult = m_aCondition.wait(&tv);
                    {
                        osl::MutexGuard g(m_aMutex);
                        if (m_cancelAsSoonAsPossible) {
                            goto done;
                        }
                    }
                    continue;
                }
            }

            static sal_uInt8 n = 0;

            if( ! hasInternetConnection() || ! runCheck( bExtensionsChecked ) )
            {
                // the extension update check should be independent from the office update check

                osl_getSystemTime( &systime );
                if ( nExtCheckTime.Seconds + offset < systime.Seconds )
                    bExtensionsChecked = false;

                // Increase next by 15, 60, .. minutes
                static const sal_Int32 nRetryInterval[] = { 900, 3600, 14400, 86400 };

                if( n < std::size(nRetryInterval) )
                    ++n;

                tv.Seconds = nRetryInterval[n-1];
                aResult = m_aCondition.wait(&tv);
                {
                    osl::MutexGuard g(m_aMutex);
                    if (m_cancelAsSoonAsPossible) {
                        goto done;
                    }
                }
            }
            else // reset retry counter
            {
                n = 0;
                bExtensionsChecked = false;
            }
        }
    }

    catch(const uno::Exception&) {
        // Silently catch all errors
        TOOLS_WARN_EXCEPTION("extensions.update", "Caught exception, thread terminated" );
    }

done:
    if (m_controller.is()) {
        m_controller->notifyUpdateCheckFinished();
    }
}


void SAL_CALL
ManualUpdateCheckThread::run()
{
    try {
        bool bExtensionsChecked = false;
        runCheck( bExtensionsChecked );
        m_aCondition.reset();
    }
    catch(const uno::Exception&) {
        // Silently catch all errors
        TOOLS_WARN_EXCEPTION("extensions.update", "Caught exception, thread terminated" );
    }
}


MenuBarButtonJob::MenuBarButtonJob(const rtl::Reference< UpdateCheck >& rUpdateCheck) :
    m_aUpdateCheck(rUpdateCheck)
{
};


uno::Any SAL_CALL
MenuBarButtonJob::execute(const uno::Sequence<beans::NamedValue>& )
{
    if ( m_aUpdateCheck->shouldShowExtUpdDlg() )
        m_aUpdateCheck->showExtensionDialog();
    else
        m_aUpdateCheck->showDialog();

    return uno::Any();
}


DownloadThread::DownloadThread(osl::Condition& rCondition,
                               const uno::Reference<uno::XComponentContext>& xContext,
                               const rtl::Reference< DownloadInteractionHandler >& rHandler,
                               const OUString& rURL,
                               const OUString& rCanonicalFileName) :
    m_aCondition(rCondition),
    m_xContext(xContext),
    m_aURL(rURL),
    m_aCanonicalFileName(rCanonicalFileName),
    m_aDownload(xContext, rHandler)
{
    createSuspended();
}


DownloadThread::~DownloadThread()
{
}


void SAL_CALL
DownloadThread::run()
{
    osl_setThreadName("DownloadThread");

#ifdef _WIN32
    int nNbCallCoInitializeExForReinit = 0;
    // for SystemShellExecute
    o3tl::safeCoInitializeEx(COINIT_APARTMENTTHREADED, nNbCallCoInitializeExForReinit);
#endif

    while( schedule() )
    {
        rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext);

        OUString aLocalFile = rModel->getLocalFileName();
        OUString aDownloadDest = rModel->getDownloadDestination();

        // release config class for now
        rModel.clear();

        static sal_uInt8 n = 0;
        if (!m_aDownload.start(m_aURL, aLocalFile, aDownloadDest, m_aCanonicalFileName))
        {
            // retry every 15s unless the dialog is not visible
            TimeValue tv(15, 0);

            if( ! UpdateCheck::get()->isDialogShowing() )
            {
                // Increase next by 1, 5, 15, 60, .. minutes
                static const sal_Int16 nRetryInterval[] = { 60, 300, 900, 3600 };

                if( n < std::size(nRetryInterval) )
                    ++n;

                tv.Seconds = nRetryInterval[n-1];
            }
            m_aCondition.wait(&tv);
        }
        else
        {
            // reset wait period after successful download
            n=0;
        }
    }
#ifdef _WIN32
    o3tl::safeCoUninitializeReinit(COINIT_MULTITHREADED, nNbCallCoInitializeExForReinit);
#endif
}


void DownloadThread::cancel()
{
    m_aDownload.stop();
    resume();

    rtl::Reference< UpdateCheck > aController(UpdateCheck::get());
    aController->cancelDownload();
}


void SAL_CALL DownloadThread::suspend()
{
    osl::Thread::suspend();
    m_aDownload.stop();
}


void SAL_CALL DownloadThread::onTerminated()
{
    delete this;
}


} // anonymous namespace

UpdateCheck::UpdateCheck()
    : m_eState(NOT_INITIALIZED)
    , m_eUpdateState(UPDATESTATES_COUNT)
    , m_pThread(nullptr)
#ifdef _WIN32
    , m_pInstallerLock(nullptr)
#endif
    , m_bHasExtensionUpdate(false)
    , m_bShowExtUpdDlg(false)
    , m_updateCheckRunning(false)
{
}

UpdateCheck::~UpdateCheck()
{
#ifdef _WIN32
    cleanupStagedWindowsInstaller(m_pInstallerLock, m_aStagedInstallerURL,
                                  m_aStagedInstallerDirectoryURL);
#endif
}

void
UpdateCheck::initialize(const uno::Sequence< beans::NamedValue >& rValues,
                        const uno::Reference<uno::XComponentContext>& xContext)
{
    std::scoped_lock aGuard(m_aMutex);

    if( NOT_INITIALIZED == m_eState )
    {
        NamedValueByNameAccess aNameAccess(rValues);
        UpdateCheckROModel aModel( aNameAccess );
        m_xContext = xContext;

        OUString aUpdateEntryVersion = aModel.getUpdateEntryVersion();

        aModel.getUpdateEntry(m_aUpdateInfo);

        bool obsoleteUpdateInfo = isObsoleteUpdateInfo(aUpdateEntryVersion);
        bool bContinueDownload = false;
        bool bDownloadAvailable = false;

        m_bHasExtensionUpdate = checkForPendingUpdates( xContext );
        m_bShowExtUpdDlg = false;

        OUString aLocalFileName = aModel.getLocalFileName();
        const bool bStoredUpdateTrusted
            = !m_aUpdateInfo.BuildId.isEmpty() && m_aUpdateInfo.Sources.size() == 1
              && isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0]);
        if ((!m_aUpdateInfo.BuildId.isEmpty() || !aLocalFileName.isEmpty())
            && !bStoredUpdateTrusted)
        {
            SAL_WARN("extensions.update",
                     "Discarding legacy or malformed persisted update state before resume");
            if (!aLocalFileName.isEmpty())
                osl_removeFile(aLocalFileName.pData);
            rtl::Reference<UpdateCheckConfig> aConfig = UpdateCheckConfig::get(xContext, *this);
            aConfig->clearUpdateFound();
            aConfig->clearLocalFileName();
            aConfig->storeDownloadPaused(false);
            m_aUpdateInfo = UpdateInfo();
            aLocalFileName.clear();
        }
        else if (!bStoredUpdateTrusted)
        {
            // getUpdateEntry historically synthesized an empty source even when
            // no update was stored. Do not expose that sentinel to UI code.
            m_aUpdateInfo = UpdateInfo();
        }

        if( !aLocalFileName.isEmpty() )
        {
            bContinueDownload = true;

            // Try to get the number of bytes already on disk
            osl::DirectoryItem aDirectoryItem;
            if( osl::DirectoryItem::E_None == osl::DirectoryItem::get(aLocalFileName, aDirectoryItem) )
            {
                osl::FileStatus aFileStatus(osl_FileStatus_Mask_FileSize);
                if( osl::DirectoryItem::E_None == aDirectoryItem.getFileStatus(aFileStatus) )
                {
                    sal_Int64 nDownloadSize = aModel.getDownloadSize();
                    sal_Int64 nFileSize = aFileStatus.getFileSize();

                    if( nDownloadSize > 0 )
                    {
                        if ( nDownloadSize <= nFileSize ) // we may have already downloaded everything
                        {
                            bContinueDownload = false;
                            if (!m_aUpdateInfo.Sources.empty()
                                && verifyUpdateFile(aLocalFileName, m_aUpdateInfo.Sources[0]))
                            {
                                bDownloadAvailable = true;
                                m_aImageName = getImageFromFileName(aLocalFileName);
                            }
                            else
                            {
                                SAL_WARN("extensions.update",
                                         "Discarding a completed update that failed release verification");
                                osl_removeFile(aLocalFileName.pData);
                                rtl::Reference<UpdateCheckConfig> aConfig
                                    = UpdateCheckConfig::get(xContext, *this);
                                aConfig->clearLocalFileName();
                                aConfig->storeDownloadPaused(false);
                            }
                        }
                        else // Calculate initial percent value.
                        {
                            sal_Int32 nPercent = static_cast<sal_Int32>(100 * nFileSize / nDownloadSize);
                            getUpdateHandler()->setProgress( nPercent );
                        }
                    }
                }
            }

            if ( bContinueDownload )
            {
                bool downloadPaused = aModel.isDownloadPaused();

                enableDownload(true, downloadPaused);
                setUIState(downloadPaused ? UPDATESTATE_DOWNLOAD_PAUSED : UPDATESTATE_DOWNLOADING);
            }

        }
        if ( !bContinueDownload )
        {
            // We do this intentionally only if no download is in progress ..
            if( obsoleteUpdateInfo )
            {
                // Bring-up release note for position 5 ..
                const OUString aURL(getReleaseNote(m_aUpdateInfo, 5));
                if( !aURL.isEmpty() )
                    showReleaseNote(aURL);

                // Data is outdated, probably due to installed update
                rtl::Reference< UpdateCheckConfig > aConfig = UpdateCheckConfig::get( xContext, *this );
                aConfig->clearUpdateFound();
                aConfig->clearLocalFileName();


                m_aUpdateInfo = UpdateInfo();
                // Remove outdated release notes
                storeReleaseNote( 1, OUString() );
                storeReleaseNote( 2, OUString() );
            }
            else
            {
                enableAutoCheck(aModel.isAutoCheckEnabled());
                if ( bDownloadAvailable )
                    setUIState( UPDATESTATE_DOWNLOAD_AVAIL );
                else
                {
                    setUIState(getUIState(m_aUpdateInfo));
                }
            }
        }
    }
}


void
UpdateCheck::cancel()
{
    std::unique_lock aGuard(m_aMutex);

    WorkerThread *pThread = m_pThread;
    UpdateState eUIState = getUIState(m_aUpdateInfo);

    aGuard.unlock();

    if( nullptr != pThread )
        pThread->cancel();

    setUIState(eUIState);
}


void
UpdateCheck::download()
{
    std::unique_lock aGuard(m_aMutex);
    UpdateInfo aInfo(m_aUpdateInfo);
    State eState = m_eState;
    aGuard.unlock();

    if (aInfo.Sources.size() != 1 || !isTrustedMaterialUpdateSource(aInfo.Sources[0]))
    {
        SAL_WARN("extensions.update", "download called without source");
        return;
    }

    if( aInfo.Sources[0].IsDirect )
    {
        // Ignore second click of a double click
        if( DOWNLOADING != eState )
        {
            shutdownThread(true);

            {
                std::scoped_lock aGuard2(m_aMutex);
                enableDownload(true);
            }
            setUIState(UPDATESTATE_DOWNLOADING);
        }
    }
    else
    {
        showReleaseNote(aInfo.Sources[0].URL); // Display in browser
    }
}

void UpdateCheck::install()
{
    OUString aInstallerURL;
    DownloadSource aSource(false, OUString());
    {
        std::scoped_lock aGuard(m_aMutex);
        aInstallerURL = m_aImageName;
        if (!m_aUpdateInfo.Sources.empty())
            aSource = m_aUpdateInfo.Sources[0];
#ifdef _WIN32
        if (m_pInstallerLock)
        {
            SAL_WARN("extensions.update", "The verified installer has already been started");
            return;
        }
#endif
    }

    // Recheck immediately after the user's approval. Windows then copies the
    // bytes into a protected, non-overwriting staging path and verifies that
    // exact copy while retaining a write/delete-excluding handle across launch.
    if (!verifyUpdateFile(aInstallerURL, aSource))
    {
        osl_removeFile(aInstallerURL.pData);
        rtl::Reference<UpdateCheckConfig> rModel = UpdateCheckConfig::get(m_xContext);
        rModel->clearLocalFileName();
        rModel->storeDownloadPaused(false);
        {
            std::scoped_lock aGuard(m_aMutex);
            m_aImageName.clear();
        }
        downloadStalled(
            u"Security verification failed immediately before installation. The installer was deleted and was not opened."_ustr);
        getUpdateHandler()->setVisible(true);
        return;
    }

#ifdef _WIN32
    OUString aInstallerPath;
    OUString aStagedInstallerURL;
    OUString aStagedInstallerDirectoryURL;
    void* pInstallerLock = nullptr;
    if (!stageVerifiedWindowsInstaller(aInstallerURL, aSource, aInstallerPath,
                                       aStagedInstallerURL, aStagedInstallerDirectoryURL,
                                       pInstallerLock))
    {
        downloadStalled(
            u"The verified installer could not be copied into a protected Windows staging directory. No installation was started."_ustr);
        getUpdateHandler()->setVisible(true);
        return;
    }

    wchar_t aSystemDirectory[MAX_PATH + 1] = {};
    const UINT nSystemDirectoryLength
        = GetSystemDirectoryW(aSystemDirectory,
                              static_cast<UINT>(std::size(aSystemDirectory)));
    if (nSystemDirectoryLength == 0
        || nSystemDirectoryLength >= static_cast<UINT>(std::size(aSystemDirectory)))
    {
        cleanupStagedWindowsInstaller(pInstallerLock, aStagedInstallerURL,
                                      aStagedInstallerDirectoryURL);
        downloadStalled(u"The trusted Windows Installer path could not be resolved."_ustr);
        getUpdateHandler()->setVisible(true);
        return;
    }

    const OUString aMsiexecPath(o3tl::toU(aSystemDirectory),
                                static_cast<sal_Int32>(nSystemDirectoryLength));
    OUString aMsiexecURL;
    if (osl::FileBase::getFileURLFromSystemPath(aMsiexecPath + u"\\msiexec.exe"_ustr,
                                                 aMsiexecURL)
        != osl::FileBase::E_None)
    {
        cleanupStagedWindowsInstaller(pInstallerLock, aStagedInstallerURL,
                                      aStagedInstallerDirectoryURL);
        downloadStalled(u"The trusted Windows Installer executable could not be resolved."_ustr);
        getUpdateHandler()->setVisible(true);
        return;
    }

    OUString aInstallSwitch(u"/i"_ustr);
    rtl_uString* aArguments[] = { aInstallSwitch.pData, aInstallerPath.pData };
    oslProcess hProcess = nullptr;
    const oslProcessError eError
        = osl_executeProcess(aMsiexecURL.pData, aArguments,
                             static_cast<sal_uInt32>(std::size(aArguments)),
                             osl_Process_DETACHED, nullptr, nullptr, nullptr, 0, &hProcess);
    if (eError == osl_Process_E_None)
    {
        osl_freeProcessHandle(hProcess);
        std::scoped_lock aGuard(m_aMutex);
        m_pInstallerLock = pInstallerLock;
        m_aStagedInstallerURL = aStagedInstallerURL;
        m_aStagedInstallerDirectoryURL = aStagedInstallerDirectoryURL;
        return;
    }
    cleanupStagedWindowsInstaller(pInstallerLock, aStagedInstallerURL,
                                  aStagedInstallerDirectoryURL);
#endif

    downloadStalled(
        u"The verified installer could not be started. No silent installation was attempted."_ustr);
    getUpdateHandler()->setVisible(true);
}


void
UpdateCheck::pause()
{
    std::unique_lock aGuard(m_aMutex);

    if( nullptr != m_pThread )
        m_pThread->suspend();

    rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext);
    aGuard.unlock();

    rModel->storeDownloadPaused(true);
    setUIState(UPDATESTATE_DOWNLOAD_PAUSED);
}


void
UpdateCheck::resume()
{
    std::unique_lock aGuard(m_aMutex);

    if( nullptr != m_pThread )
        m_pThread->resume();

    rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext);
    aGuard.unlock();

    rModel->storeDownloadPaused(false);
    setUIState(UPDATESTATE_DOWNLOADING);
}


void
UpdateCheck::closeAfterFailure()
{
    std::unique_lock aGuard(m_aMutex);

    if ( ( m_eState == DISABLED ) || ( m_eState == CHECK_SCHEDULED ) )
    {
        const UpdateState eUIState = getUIState( m_aUpdateInfo );
        aGuard.unlock();
        setUIState( eUIState, true );
    }
}

void UpdateCheck::notifyUpdateCheckFinished() {
    std::scoped_lock l(m_aMutex);
    m_updateCheckRunning = false;
    m_updateCheckFinished.notify_all();
}

void UpdateCheck::waitForUpdateCheckFinished() {
    UpdateCheckThread * thread;
    {
        std::scoped_lock l(m_aMutex);
        thread = dynamic_cast<UpdateCheckThread *>(m_pThread);
    }
    if (thread != nullptr) {
        thread->cancelAsSoonAsPossible();
    }
    for (;;) {
        std::unique_lock lock(m_aMutex);
        if (!m_updateCheckRunning) {
            return;
        }
        m_updateCheckFinished.wait(lock);
    }
}

void
UpdateCheck::shutdownThread(bool join)
{
    std::unique_lock aGuard(m_aMutex);

    // copy thread object pointer to stack
    osl::Thread *pThread = m_pThread;
    m_pThread = nullptr;
    aGuard.unlock();

    if( nullptr != pThread )
    {
        pThread->terminate();
        if( join )
        {
            m_aCondition.set();
            pThread->join();
            m_aCondition.reset();
        }
    }
}


void
UpdateCheck::enableAutoCheck(bool enable)
{
    // The (recursive) mutex is (at time of writing) always locked already here
    std::scoped_lock aGuard(m_aMutex);
    if( enable )
    {
        m_updateCheckRunning = true;
        m_pThread = new UpdateCheckThread(m_aCondition, m_xContext, this);
    }

    m_eState = enable ? CHECK_SCHEDULED : DISABLED;
}


void
UpdateCheck::enableDownload(bool enable, bool paused)
{
    OSL_ASSERT(nullptr == m_pThread);

    if (enable
        && (m_aUpdateInfo.Sources.size() != 1
            || !isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0])))
    {
        SAL_WARN("extensions.update", "Refusing to start a download without one trusted source");
        enable = false;
    }

    if( enable )
    {
        m_pThread = new DownloadThread(m_aCondition, m_xContext, this,
                                       m_aUpdateInfo.Sources[0].URL,
                                       m_aUpdateInfo.Sources[0].FileName);
        State eState = DISABLED;
        if( !paused )
        {
            eState = DOWNLOADING;
            m_pThread->resume();
        }
        else
            eState = DOWNLOAD_PAUSED;

        m_eState = eState;
    }
    else {
        enableAutoCheck(UpdateCheckConfig::get(m_xContext)->isAutoCheckEnabled());
    }

}


bool
UpdateCheck::downloadTargetExists(const OUString& rFileName)
{
    std::unique_lock aGuard(m_aMutex);

    rtl::Reference< UpdateHandler > aUpdateHandler(getUpdateHandler());
    UpdateState eUIState = UPDATESTATE_DOWNLOADING;

    bool cont = false;

    if( aUpdateHandler->isVisible() )
    {
        cont = aUpdateHandler->showOverwriteWarning();
        if( cont )
        {
            if( osl_File_E_None != osl_removeFile(rFileName.pData) )
            {
                // FIXME: error message
                cont = false;
            }
        }
        else
            eUIState = getUIState(m_aUpdateInfo);
    }
    else
    {
        const bool bVerified = !m_aUpdateInfo.Sources.empty()
                               && verifyUpdateFile(rFileName, m_aUpdateInfo.Sources[0]);
        if (bVerified)
        {
            m_aImageName = getImageFromFileName(rFileName);
            eUIState = UPDATESTATE_DOWNLOAD_AVAIL;
        }
        else
        {
            SAL_WARN("extensions.update",
                     "Replacing an existing update file that failed release verification");
            cont = osl_removeFile(rFileName.pData) == osl_File_E_None;
            rtl::Reference<UpdateCheckConfig> rModel = UpdateCheckConfig::get(m_xContext);
            rModel->clearLocalFileName();
            rModel->storeDownloadPaused(false);
        }
    }

    if( !cont )
    {
        shutdownThread(false);
        enableDownload(false);

        aGuard.unlock();
        setUIState(eUIState);
    }

    return cont;
}


bool UpdateCheck::checkDownloadDestination( const OUString& rFileName )
{
    std::scoped_lock aGuard(m_aMutex);

    rtl::Reference< UpdateHandler > aUpdateHandler( getUpdateHandler() );

    bool bReload = false;

    if( aUpdateHandler->isVisible() )
    {
        bReload = aUpdateHandler->showOverwriteWarning( rFileName );
    }

    return bReload;
}


void
UpdateCheck::downloadStalled(const OUString& rErrorMessage)
{
    std::unique_lock aGuard(m_aMutex);
    rtl::Reference< UpdateHandler > aUpdateHandler(getUpdateHandler());
    aGuard.unlock();

    aUpdateHandler->setErrorMessage(rErrorMessage);
    setUIState(UPDATESTATE_ERROR_DOWNLOADING);
}


void
UpdateCheck::downloadProgressAt(sal_Int8 nPercent)
{
    std::unique_lock aGuard(m_aMutex);
    rtl::Reference< UpdateHandler > aUpdateHandler(getUpdateHandler());
    aGuard.unlock();

    aUpdateHandler->setProgress(nPercent);
    setUIState(UPDATESTATE_DOWNLOADING);
}


void
UpdateCheck::downloadStarted(const OUString& rLocalFileName, sal_Int64 nFileSize)
{
    std::scoped_lock aGuard(m_aMutex);
    if (!m_aUpdateInfo.Sources.empty()
        && isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0]))
    {
        rtl::Reference< UpdateCheckConfig > aModel(UpdateCheckConfig::get(m_xContext));
        // Persist the signed-off manifest size, not a potentially absent or
        // misleading HTTP Content-Length. This makes resume/restart checks use
        // the same immutable value as final verification.
        aModel->storeLocalFileName(rLocalFileName, m_aUpdateInfo.Sources[0].Size);

        // Bring-up release note for position 1 ..
        const OUString aURL(getReleaseNote(m_aUpdateInfo, 1, aModel->isAutoDownloadEnabled()));
        if( !aURL.isEmpty() )
            showReleaseNote(aURL);
    }
    (void)nFileSize;
}


void
UpdateCheck::downloadFinished(const OUString& rLocalFileName)
{
    std::unique_lock aGuard(m_aMutex);
    UpdateInfo aUpdateInfo(m_aUpdateInfo);
    aGuard.unlock();

    // No more retries, and do not retain a pointer to a worker that deletes
    // itself in onTerminated(). The downloader has already flushed and closed
    // the file before this callback.
    shutdownThread(false);

    if (aUpdateInfo.Sources.empty()
        || !verifyUpdateFile(rLocalFileName, aUpdateInfo.Sources[0]))
    {
        SAL_WARN("extensions.update", "Downloaded installer failed size or SHA-256 verification");
        osl_removeFile(rLocalFileName.pData);
        rtl::Reference<UpdateCheckConfig> rModel = UpdateCheckConfig::get(m_xContext);
        rModel->clearLocalFileName();
        rModel->storeDownloadPaused(false);
        {
            std::scoped_lock aStateGuard(m_aMutex);
            m_aImageName.clear();
            m_eState = DISABLED;
        }
        downloadStalled(
            u"Security verification failed: the downloaded installer did not match the release size and SHA-256. The file was deleted and was not opened."_ustr);
        return;
    }

    {
        std::scoped_lock aStateGuard(m_aMutex);
        m_aImageName = getImageFromFileName(rLocalFileName);
        m_eState = DISABLED;
    }
    setUIState(UPDATESTATE_DOWNLOAD_AVAIL);

    // Bring-up release note for position 2 ..
    rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get( m_xContext );
    const OUString aURL(getReleaseNote(aUpdateInfo, 2, rModel->isAutoDownloadEnabled()));
    if( !aURL.isEmpty() )
        showReleaseNote(aURL);
}


void
UpdateCheck::cancelDownload()
{
    shutdownThread(true);

    std::scoped_lock aGuard(m_aMutex);
    enableDownload(false);

    rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext);

    OUString aLocalFile(rModel->getLocalFileName());
    rModel->clearLocalFileName();
    rModel->storeDownloadPaused(false);

    if( isObsoleteUpdateInfo(rModel->getUpdateEntryVersion()) )
    {
        rModel->clearUpdateFound(); // This wasn't done during init yet ..
        m_aUpdateInfo = UpdateInfo();
    }

    /*oslFileError rc =*/ osl_removeFile(aLocalFile.pData);
    // FIXME: error handling ..

}


void
UpdateCheck::showDialog(bool forceCheck)
{
    std::unique_lock aGuard(m_aMutex);

    bool update_found = !m_aUpdateInfo.BuildId.isEmpty() && m_aUpdateInfo.Sources.size() == 1
                        && isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0]);
    bool bSetUIState = ! m_aUpdateHandler.is();

    UpdateState eDialogState = UPDATESTATES_COUNT;

    switch( m_eState )
    {
    case DISABLED:
    case CHECK_SCHEDULED:
        if (!forceCheck && !m_aImageName.isEmpty())
            eDialogState = UPDATESTATE_DOWNLOAD_AVAIL;
        else if( forceCheck || ! update_found ) // Run check when forced or if we did not find an update yet
        {
            eDialogState = UPDATESTATE_CHECKING;
            bSetUIState = true;
        }
        else if(m_aUpdateInfo.Sources[0].IsDirect)
            eDialogState = UPDATESTATE_UPDATE_AVAIL;
        else
            eDialogState = UPDATESTATE_UPDATE_NO_DOWNLOAD;
        break;

    case DOWNLOADING:
        eDialogState = UPDATESTATE_DOWNLOADING;
        break;

    case DOWNLOAD_PAUSED:
        eDialogState = UPDATESTATE_DOWNLOAD_PAUSED;
        break;

    case NOT_INITIALIZED:
        OSL_ASSERT( false );
        break;
    }

    if( bSetUIState )
    {
        aGuard.unlock();
        setUIState(eDialogState, true); // suppress bubble as Dialog will be visible soon
        aGuard.lock();
    }

    getUpdateHandler()->setVisible();

    // Run check in separate thread ..
    if( UPDATESTATE_CHECKING == eDialogState )
    {
        if( DISABLED == m_eState )
        {
            // destructs itself when done, not cancellable for now ..
            new ManualUpdateCheckThread(m_aCondition, m_xContext);
        }

        m_aCondition.set();
    }
}

void
UpdateCheck::setUpdateInfo(const UpdateInfo& aInfo)
{
    std::unique_lock aGuard(m_aMutex);

    bool bSuppressBubble = aInfo.BuildId == m_aUpdateInfo.BuildId;
    m_aUpdateInfo = aInfo;
    if (!m_aUpdateInfo.BuildId.isEmpty()
        && (m_aUpdateInfo.Sources.size() != 1
            || !isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0])))
    {
        SAL_WARN("extensions.update", "Ignoring update metadata without one trusted source");
        m_aUpdateInfo = UpdateInfo();
    }

    OSL_ASSERT(DISABLED == m_eState || CHECK_SCHEDULED == m_eState);

    // Ignore leading non direct download if we get direct ones
    std::vector< DownloadSource >::iterator iter = std::find_if(m_aUpdateInfo.Sources.begin(), m_aUpdateInfo.Sources.end(),
        [](const DownloadSource& rSource) { return rSource.IsDirect; });

    if( (iter != m_aUpdateInfo.Sources.begin()) &&
        (iter != m_aUpdateInfo.Sources.end()) &&
        iter->IsDirect )
    {
        m_aUpdateInfo.Sources.erase(m_aUpdateInfo.Sources.begin(), --iter);
    }

    rtl::Reference< UpdateCheckConfig > rModel = UpdateCheckConfig::get(m_xContext, *this);
    OSL_ASSERT( rModel.is() );

    // Decide whether to use alternate release note pos ..
    bool autoDownloadEnabled = rModel->isAutoDownloadEnabled();

    for (auto & elem : m_aUpdateInfo.ReleaseNotes)
    {
        if( ((1 == elem.Pos) || (2 == elem.Pos)) && autoDownloadEnabled && !elem.URL2.isEmpty())
        {
            elem.URL = elem.URL2;
            elem.URL2.clear();
            elem.Pos = elem.Pos2;
            elem.Pos2 = 0;
        }
    }

    // do not move below store/clear ..
    rModel->updateLastChecked();

    UpdateState eUIState;
    if( !m_aUpdateInfo.Sources.empty() )
    {
        rModel->storeUpdateFound(aInfo, getBuildId());

        if( m_aUpdateInfo.Sources[0].IsDirect )
        {
            eUIState = UPDATESTATE_UPDATE_AVAIL;

            if( rModel->isAutoDownloadEnabled() )
            {
                shutdownThread(false);
                eUIState = UPDATESTATE_DOWNLOADING;
                enableDownload(true);
            }
        }
        else
            eUIState = UPDATESTATE_UPDATE_NO_DOWNLOAD;
    }
    else
    {
        eUIState = UPDATESTATE_NO_UPDATE_AVAIL;
        rModel->clearUpdateFound();
    }

    aGuard.unlock();
    setUIState(eUIState, bSuppressBubble);
}

bool UpdateCheck::hasOfficeUpdate() const
{
    std::unique_lock aGuard(m_aMutex);
    return !m_aUpdateInfo.BuildId.isEmpty() && m_aUpdateInfo.Sources.size() == 1
           && isTrustedMaterialUpdateSource(m_aUpdateInfo.Sources[0]);
}

void
UpdateCheck::setCheckFailedState()
{
    setUIState(UPDATESTATE_ERROR_CHECKING);
}


void UpdateCheck::handleMenuBarUI( const rtl::Reference< UpdateHandler >& rUpdateHandler,
                                   const uno::Reference<beans::XPropertySet>& xMenuBarUI,
                                   UpdateState& eState,
                                   bool suppressBubble )
{
    if ( ( UPDATESTATE_NO_UPDATE_AVAIL == eState ) && m_bHasExtensionUpdate )
        eState = UPDATESTATE_EXT_UPD_AVAIL;

    if ( UPDATESTATE_EXT_UPD_AVAIL == eState )
        m_bShowExtUpdDlg = true;
    else
        m_bShowExtUpdDlg = false;

    if( xMenuBarUI.is() )
    {
        if( UPDATESTATE_NO_UPDATE_AVAIL == eState )
        {
            xMenuBarUI->setPropertyValue( PROPERTY_SHOW_MENUICON, uno::Any(false) );
        }
        else
        {
            xMenuBarUI->setPropertyValue( PROPERTY_TITLE, uno::Any(rUpdateHandler->getBubbleTitle(eState)) );
            xMenuBarUI->setPropertyValue( PROPERTY_TEXT, uno::Any(rUpdateHandler->getBubbleText(eState)) );

            if( ! suppressBubble && ( ! rUpdateHandler->isVisible() || rUpdateHandler->isMinimized() ) )
                xMenuBarUI->setPropertyValue( PROPERTY_SHOW_BUBBLE, uno::Any( true ) );

            if( UPDATESTATE_CHECKING != eState )
                xMenuBarUI->setPropertyValue( PROPERTY_SHOW_MENUICON, uno::Any(true) );
        }
    }
}


void UpdateCheck::setUIState(UpdateState eState, bool suppressBubble)
{
    std::unique_lock aGuard(m_aMutex);

    if( ! m_xMenuBarUI.is() &&
        (DISABLED != m_eState) &&
        ( m_bHasExtensionUpdate || (UPDATESTATE_NO_UPDATE_AVAIL != eState)) &&
        (UPDATESTATE_CHECKING != eState) &&
        (UPDATESTATE_ERROR_CHECKING != eState)
    )
    {
        m_xMenuBarUI = createMenuBarUI(m_xContext, new MenuBarButtonJob(this));
    }

    // Show bubble only when the status has changed
    if ( eState == m_eUpdateState )
        suppressBubble = true;
    else
        m_eUpdateState = eState;

    rtl::Reference<UpdateHandler> aUpdateHandler(getUpdateHandler());
    OSL_ASSERT( aUpdateHandler.is() );

    UpdateInfo aUpdateInfo(m_aUpdateInfo);
    OUString aImageName(m_aImageName);
    uno::Reference<beans::XPropertySet> xMenuBarUI(m_xMenuBarUI);

    aGuard.unlock();

    handleMenuBarUI(aUpdateHandler, xMenuBarUI, eState, suppressBubble);

    if( (UPDATESTATE_UPDATE_AVAIL == eState)
     || (UPDATESTATE_DOWNLOAD_PAUSED == eState)
     || (UPDATESTATE_DOWNLOADING == eState) )
    {
        uno::Reference< uno::XComponentContext > xContext(m_xContext);

        OUString aDownloadDestination =
            UpdateCheckConfig::get(xContext, this)->getDownloadDestination();

        osl_getSystemPathFromFileURL(aDownloadDestination.pData, &aDownloadDestination.pData);

        aUpdateHandler->setDownloadPath(aDownloadDestination);
    }
    else if( UPDATESTATE_DOWNLOAD_AVAIL == eState )
    {
        aUpdateHandler->setDownloadFile(aImageName);
    }

    aUpdateHandler->setDescription(aUpdateInfo.Description);
    aUpdateHandler->setNextVersion(aUpdateInfo.Version);
    aUpdateHandler->setState(eState);
}


UpdateState
UpdateCheck::getUIState(const UpdateInfo& rInfo)
{
    UpdateState eUIState = UPDATESTATE_NO_UPDATE_AVAIL;

    if (!rInfo.BuildId.isEmpty() && rInfo.Sources.size() == 1
        && isTrustedMaterialUpdateSource(rInfo.Sources[0]))
    {
        if( rInfo.Sources[0].IsDirect )
            eUIState = UPDATESTATE_UPDATE_AVAIL;
        else
            eUIState = UPDATESTATE_UPDATE_NO_DOWNLOAD;
    }

    return eUIState;
}


void
UpdateCheck::showReleaseNote(const OUString& rURL) const
{
    const uno::Reference< c3s::XSystemShellExecute > xShellExecute(
        c3s::SystemShellExecute::create( m_xContext ) );

    try {
        xShellExecute->execute(rURL, OUString(), c3s::SystemShellExecuteFlags::URIS_ONLY);
    } catch(const c3s::SystemShellExecuteException&) {
    }
}


bool
UpdateCheck::storeReleaseNote(sal_Int8 nNum, const OUString &rURL)
{
    osl::FileBase::RC rc;
    OUString aTargetDir( UpdateCheckConfig::getAllUsersDirectory() + "/sun" );

    osl::Directory::createPath( aTargetDir );

    OUString aFileName = "releasenote" +
                              OUString::number( nNum ) +
                              ".url";

    OUString aFilePath;
    rc = osl::FileBase::getAbsoluteFileURL( aTargetDir, aFileName, aFilePath );
    if ( rc != osl::FileBase::E_None ) return false;

    osl::File::remove( aFilePath );

    // don't store empty release notes, but delete old ones
    if ( rURL.isEmpty() )
        return true;

    osl::File aFile( aFilePath );
    rc = aFile.open( osl_File_OpenFlag_Write | osl_File_OpenFlag_Create );
    if ( rc != osl::FileBase::E_None ) return false;

    OString aLineBuf("[InternetShortcut]\r\n"_ostr);
    sal_uInt64 nWritten = 0;

    OUString aURL( rURL );
#ifdef _WIN32
    rc = aFile.write( aLineBuf.getStr(), aLineBuf.getLength(), nWritten );
    if ( rc != osl::FileBase::E_None ) return false;
    aURL = "URL=" + rURL;
#endif
    aLineBuf = OUStringToOString( aURL, RTL_TEXTENCODING_UTF8 );
    rc = aFile.write( aLineBuf.getStr(), aLineBuf.getLength(), nWritten );
    if ( rc != osl::FileBase::E_None ) return false;

    aFile.close();
    return true;
}


void UpdateCheck::showExtensionDialog()
{
    if( ! m_xContext.is() )
        throw uno::RuntimeException(
            u"UpdateCheck::showExtensionDialog(): empty component context"_ustr, uno::Reference< uno::XInterface > () );

    uno::Reference< lang::XMultiComponentFactory > xServiceManager( m_xContext->getServiceManager() );
    if( !xServiceManager.is() )
        throw uno::RuntimeException(
            u"UpdateCheck::showExtensionDialog(): unable to obtain service manager from component context"_ustr, uno::Reference< uno::XInterface > () );

    uno::Reference<uno::XInterface> xService = xServiceManager->createInstanceWithContext(
        u"com.sun.star.deployment.ui.PackageManagerDialog"_ustr, m_xContext);
    uno::Reference< task::XJobExecutor > xExecutable( xService, uno::UNO_QUERY );
    if ( xExecutable.is() )
        xExecutable->trigger( u"SHOW_UPDATE_DIALOG"_ustr );
}


rtl::Reference<UpdateHandler>
UpdateCheck::getUpdateHandler()
{
    std::scoped_lock aGuard(m_aMutex);

    if( ! m_aUpdateHandler.is() )
        m_aUpdateHandler = new UpdateHandler(m_xContext, this);

    return m_aUpdateHandler;
}


uno::Reference< task::XInteractionHandler >
UpdateCheck::getInteractionHandler() const
{
    std::scoped_lock aGuard(m_aMutex);

    uno::Reference< task::XInteractionHandler > xHandler;

    if( m_aUpdateHandler.is() && m_aUpdateHandler->isVisible() )
        xHandler = m_aUpdateHandler.get();

    return xHandler;
}


bool
UpdateCheck::isDialogShowing() const
{
    std::scoped_lock aGuard(m_aMutex);
    return m_aUpdateHandler.is() && m_aUpdateHandler->isVisible();
};


void
UpdateCheck::autoCheckStatusChanged(bool enabled)
{
    std::unique_lock aGuard(m_aMutex);

    if( (CHECK_SCHEDULED == m_eState) && !enabled )
        shutdownThread(false);

    if( (DISABLED == m_eState) || (CHECK_SCHEDULED == m_eState) )
    {
        enableAutoCheck(enabled);
        UpdateState eState = getUIState(m_aUpdateInfo);
        aGuard.unlock();
        setUIState(eState);
    }
};


void
UpdateCheck::autoCheckIntervalChanged()
{
    // just wake-up
    m_aCondition.set();
};

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
