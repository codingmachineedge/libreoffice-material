/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <cstddef>
#include <cstring>
#include <iterator>
#include <string_view>

#include <comphelper/scopeguard.hxx>
#include <o3tl/char16_t2wchar_t.hxx>
#include <osl/file.h>
#include <osl/file.hxx>
#include <test/bootstrapfixture.hxx>

#include <com/sun/star/deployment/UpdateInformationEntry.hpp>
#include <com/sun/star/deployment/UpdateInformationProvider.hpp>
#include <com/sun/star/xml/dom/XNodeList.hpp>

#include "../../source/update/check/updatecheck.hxx"
#include "../../source/update/check/updateprotocol.hxx"

#ifdef _WIN32
#include <aclapi.h>
#include <sddl.h>
#include <windows.h>
#endif

using namespace com::sun::star;
using namespace com::sun::star::xml;

OUString rejectedInstallerDisposition(const OUString& rFileURL, oslFileError eRemove);

namespace testupdate {

#ifdef _WIN32
namespace
{
bool aclContainsFullAccessSid(PACL pAcl, const wchar_t* pExpectedSidString)
{
    PSID pExpectedSid = nullptr;
    CPPUNIT_ASSERT(ConvertStringSidToSidW(pExpectedSidString, &pExpectedSid));
    comphelper::ScopeGuard aSidGuard([&]() { LocalFree(pExpectedSid); });

    ACL_SIZE_INFORMATION aAclInformation{};
    CPPUNIT_ASSERT(GetAclInformation(pAcl, &aAclInformation, sizeof(aAclInformation),
                                     AclSizeInformation));
    for (DWORD nIndex = 0; nIndex < aAclInformation.AceCount; ++nIndex)
    {
        void* pRawAce = nullptr;
        CPPUNIT_ASSERT(GetAce(pAcl, nIndex, &pRawAce));
        const auto* pAce = static_cast<ACCESS_ALLOWED_ACE*>(pRawAce);
        if (pAce->Header.AceType == ACCESS_ALLOWED_ACE_TYPE
            && pAce->Mask == FILE_ALL_ACCESS
            && EqualSid(reinterpret_cast<PSID>(const_cast<DWORD*>(&pAce->SidStart)),
                        pExpectedSid))
        {
            return true;
        }
    }
    return false;
}

void assertProtectedStagingAcl(const OUString& rSystemPath)
{
    PACL pDacl = nullptr;
    PSECURITY_DESCRIPTOR pSecurityDescriptor = nullptr;
    CPPUNIT_ASSERT_EQUAL(
        DWORD(ERROR_SUCCESS),
        GetNamedSecurityInfoW(const_cast<wchar_t*>(o3tl::toW(rSystemPath.getStr())),
                              SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, nullptr, nullptr,
                              &pDacl, nullptr, &pSecurityDescriptor));
    comphelper::ScopeGuard aSecurityGuard([&]() { LocalFree(pSecurityDescriptor); });

    CPPUNIT_ASSERT(pDacl != nullptr);
    SECURITY_DESCRIPTOR_CONTROL nControl = 0;
    DWORD nRevision = 0;
    CPPUNIT_ASSERT(GetSecurityDescriptorControl(pSecurityDescriptor, &nControl, &nRevision));
    CPPUNIT_ASSERT((nControl & SE_DACL_PROTECTED) != 0);

    ACL_SIZE_INFORMATION aAclInformation{};
    CPPUNIT_ASSERT(GetAclInformation(pDacl, &aAclInformation, sizeof(aAclInformation),
                                     AclSizeInformation));
    CPPUNIT_ASSERT_EQUAL(DWORD(3), aAclInformation.AceCount);
    CPPUNIT_ASSERT(aclContainsFullAccessSid(pDacl, L"S-1-5-18"));
    CPPUNIT_ASSERT(aclContainsFullAccessSid(pDacl, L"S-1-5-32-544"));
    CPPUNIT_ASSERT(aclContainsFullAccessSid(pDacl, L"S-1-3-4"));
}
}
#endif

class Test : public test::BootstrapFixture
{
public:
    virtual void setUp() override
    {
        // so that comphelper::getProcessServiceFactory() works, m_xContext is
        // set up, etc.
        test::BootstrapFixture::setUp();

        if ( !m_xProvider.is() )
            m_xProvider = deployment::UpdateInformationProvider::create( m_xContext );

        // repositories that we will be checking
        m_aRepositoryList = { m_directories.getURLFromSrc( u"/extensions/qa/update/simple.xml" ) };
    }

    virtual void tearDown() override
    {
        m_xProvider.clear();
        m_aRepositoryList.realloc( 0 );
        test::BootstrapFixture::tearDown();
    }

protected:
    // test the getUpdateInformationEnumeration() method
    void testGetUpdateInformationEnumeration()
    {
        uno::Reference< container::XEnumeration > aUpdateInfoEnumeration =
            m_xProvider->getUpdateInformationEnumeration(
                m_aRepositoryList,
                u"TODO"_ustr ); // unused when we do not have a 'feed'

        if ( !aUpdateInfoEnumeration.is() )
            CPPUNIT_FAIL( "Calling getUpdateInformationEnumeration() with TODO failed." );

        if ( !aUpdateInfoEnumeration->hasMoreElements() )
            CPPUNIT_FAIL( "Should have more elements (this one is 1st)." );

        deployment::UpdateInformationEntry aEntry;
        if ( aUpdateInfoEnumeration->nextElement() >>= aEntry )
        {
            CPPUNIT_ASSERT_EQUAL( u"description"_ustr, aEntry.UpdateDocument->getNodeName() );

            uno::Reference< dom::XNodeList> xChildNodes = aEntry.UpdateDocument->getChildNodes();
            CPPUNIT_ASSERT( xChildNodes.is() );
#if 0
            for ( int i = 0; i < xChildNodes->getLength(); ++i )
            {
                fprintf( stderr, "node == %d\n", i );
                uno::Reference< dom::XElement > xChildId( xChildNodes->item( i ), uno::UNO_QUERY );
                if ( xChildId.is() )
                {
                    fprintf( stderr, "Name == %s\n", OUStringToOString( xChildId->getNodeName(), RTL_TEXTENCODING_UTF8 ).getStr() );
                    fprintf( stderr, "Value == %s\n", OUStringToOString( xChildId->getNodeValue(), RTL_TEXTENCODING_UTF8 ).getStr() );
                }
            }
#endif
            //uno::Reference< dom::XElement > xChildId( xChildNodes->item( 0 ), uno::UNO_QUERY );
            //CPPUNIT_ASSERT( xChildId.is() );
            //CPPUNIT_ASSERT( xChildId->getNodeValue() == "LibreOffice_3.4" );
            //fprintf( stderr, "Attribute == %s\n", OUStringToOString( aEntry.UpdateDocument->getAttribute( OUString( "test" ) ), RTL_TEXTENCODING_UTF8 ).getStr() );
            //fprintf( stderr, "Value == %s\n", OUStringToOString( xChildId->getNodeValue(), RTL_TEXTENCODING_UTF8 ).getStr() );
            // TODO check more deeply
        }
        else
            CPPUNIT_FAIL( "Wrong type of the entry." );
    }

    // test the checkForUpdates() method - update is available
    void testCheckUpdateAvailable()
    {
        UpdateInfo aInfo;
        rtl::Reference< UpdateCheck > aController( UpdateCheck::get() );

        if ( checkForUpdates( aInfo, m_xContext, aController->getInteractionHandler(), m_xProvider,
                    u"Windows",
                    u"X86_64",
                    m_aRepositoryList,
                    u"111111-222222-333333-444444",
                    u"InstallSetID"_ustr ) )
        {
            CPPUNIT_ASSERT_EQUAL( std::size_t(1), aInfo.Sources.size() );
            const DownloadSource& rSource = aInfo.Sources[0];
            CPPUNIT_ASSERT_EQUAL(
                u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
                rSource.URL);
            CPPUNIT_ASSERT_EQUAL(
                u"1b8743c701ccbb5839b6cc8dd25eec1ac4a6ca4c3094fd6a5b2a8a49e69e058e"_ustr,
                rSource.Sha256);
            CPPUNIT_ASSERT_EQUAL(sal_Int64(50), rSource.Size);
            CPPUNIT_ASSERT_EQUAL(u"windows-msi-test"_ustr, rSource.ReleaseTag);
            CPPUNIT_ASSERT_EQUAL(u"LibreOfficeMaterial-Windows-x64.msi"_ustr,
                                 rSource.FileName);
        }
        else
            CPPUNIT_FAIL( "Calling checkForUpdates() failed." );
    }

    // test the checkForUpdates() method - we are up-to-date
    void testCheckUpToDate()
    {
        UpdateInfo aInfo;
        rtl::Reference< UpdateCheck > aController( UpdateCheck::get() );

        if ( checkForUpdates( aInfo, m_xContext, aController->getInteractionHandler(), m_xProvider,
                    u"Windows",
                    u"X86_64",
                    m_aRepositoryList,
                    u"123456-abcdef-1a2b3c-4d5e6f",
                    u"InstallSetID"_ustr ) )
        {
            CPPUNIT_ASSERT( aInfo.Sources.empty() );
        }
        else
            CPPUNIT_FAIL( "Calling checkForUpdates() failed." );
    }

    void assertInvalidFeedIsIgnored(std::u16string_view rSourcePath)
    {
        UpdateInfo aInfo;
        aInfo.BuildId = u"stale-state-must-be-cleared"_ustr;
        aInfo.Sources.emplace_back(false, u"https://example.com/stale.msi"_ustr);

        const uno::Sequence<OUString> aRepositories
            = { m_directories.getURLFromSrc(rSourcePath) };
        rtl::Reference<UpdateCheck> aController(UpdateCheck::get());
        CPPUNIT_ASSERT(checkForUpdates(aInfo, m_xContext, aController->getInteractionHandler(),
                                       m_xProvider, u"Windows", u"X86_64", aRepositories,
                                       u"installed-build"_ustr, u"InstallSetID"_ustr));
        CPPUNIT_ASSERT(aInfo.BuildId.isEmpty());
        CPPUNIT_ASSERT(aInfo.Sources.empty());
        CPPUNIT_ASSERT_EQUAL(UPDATESTATE_NO_UPDATE_AVAIL, UpdateCheck::getUIState(aInfo));
    }

    void testWrongMimeIsIgnored()
    {
        assertInvalidFeedIsIgnored(u"/extensions/qa/update/wrong-mime.xml");
    }

    void testMissingHashIsIgnored()
    {
        assertInvalidFeedIsIgnored(u"/extensions/qa/update/missing-hash.xml");
    }

    void testTrustedSourceValidation()
    {
        DownloadSource aSource(
            true,
            u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
            u"1b8743c701ccbb5839b6cc8dd25eec1ac4a6ca4c3094fd6a5b2a8a49e69e058e"_ustr,
            50, u"windows-msi-test"_ustr, u"LibreOfficeMaterial-Windows-x64.msi"_ustr);
        CPPUNIT_ASSERT(isTrustedMaterialUpdateSource(aSource));

        DownloadSource aWrongHost(aSource);
        aWrongHost.URL = aWrongHost.URL.replaceFirst(u"github.com"_ustr, u"example.com"_ustr);
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongHost));

        DownloadSource aWrongHash(aSource);
        aWrongHash.Sha256 = u"1B8743C701CCBB5839B6CC8DD25EEC1AC4A6CA4C3094FD6A5B2A8A49E69E058E"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongHash));

        DownloadSource aWrongTag(aSource);
        aWrongTag.ReleaseTag = u"../latest"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongTag));

        DownloadSource aDotTag(aSource);
        aDotTag.ReleaseTag = u".."_ustr;
        aDotTag.URL
            = u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/../LibreOfficeMaterial-Windows-x64.msi"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aDotTag));

        DownloadSource aHiddenTag(aSource);
        aHiddenTag.ReleaseTag = u".hidden"_ustr;
        aHiddenTag.URL
            = u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/.hidden/LibreOfficeMaterial-Windows-x64.msi"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aHiddenTag));

        DownloadSource aWrongName(aSource);
        aWrongName.FileName = u"other.msi"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongName));

        DownloadSource aWrongSize(aSource);
        aWrongSize.Size = 0;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongSize));

        DownloadSource aQueryURL(aSource);
        aQueryURL.URL += u"?unexpected=1"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aQueryURL));
    }

    void testVerifiedUpdateFile()
    {
        DownloadSource aSource(
            true,
            u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
            u"1b8743c701ccbb5839b6cc8dd25eec1ac4a6ca4c3094fd6a5b2a8a49e69e058e"_ustr,
            50, u"windows-msi-test"_ustr, u"LibreOfficeMaterial-Windows-x64.msi"_ustr);
        const OUString aFixture
            = m_directories.getURLFromSrc(u"/extensions/qa/update/LibreOfficeMaterial-Windows-x64.msi");
        CPPUNIT_ASSERT(verifyUpdateFile(aFixture, aSource));

        DownloadSource aWrongHash(aSource);
        aWrongHash.Sha256 = u"0b8743c701ccbb5839b6cc8dd25eec1ac4a6ca4c3094fd6a5b2a8a49e69e058e"_ustr;
        CPPUNIT_ASSERT(!verifyUpdateFile(aFixture, aWrongHash));

        DownloadSource aWrongSize(aSource);
        aWrongSize.Size = 49;
        CPPUNIT_ASSERT(!verifyUpdateFile(aFixture, aWrongSize));
    }

    void testRejectedInstallerDisposition()
    {
        CPPUNIT_ASSERT_EQUAL(u"The file was deleted and was not opened."_ustr,
                             rejectedInstallerDisposition(u"file:///tmp/rejected.msi"_ustr,
                                                          osl_File_E_None));
        const OUString aRetained
            = rejectedInstallerDisposition(u"file:///tmp/rejected.msi"_ustr,
                                           osl_File_E_ACCES);
        CPPUNIT_ASSERT(aRetained.indexOf(u"could not delete"_ustr) >= 0);
        CPPUNIT_ASSERT(aRetained.indexOf(u"Do not open"_ustr) >= 0);
        CPPUNIT_ASSERT(aRetained.indexOf(u"rejected.msi"_ustr) >= 0);
    }

    void testWindowsInstallerCommand()
    {
        const OUString aInstallerPath
            = u"C:\\Users\\Example User\\AppData\\Local\\LibreOfficeMaterialUpdate-test\\LibreOfficeMaterial-Windows-x64.msi"_ustr;
        const WindowsInstallerCommand aCommand
            = buildWindowsInstallerCommand(u"C:\\Windows\\System32"_ustr, aInstallerPath);

        CPPUNIT_ASSERT_EQUAL(u"C:\\Windows\\System32\\msiexec.exe"_ustr,
                             aCommand.ExecutablePath);
        CPPUNIT_ASSERT_EQUAL(std::size_t(4), aCommand.Arguments.size());
        CPPUNIT_ASSERT_EQUAL(u"/i"_ustr, aCommand.Arguments[0]);
        CPPUNIT_ASSERT_EQUAL(aInstallerPath, aCommand.Arguments[1]);
        CPPUNIT_ASSERT_EQUAL(u"REBOOT=ReallySuppress"_ustr, aCommand.Arguments[2]);
        CPPUNIT_ASSERT_EQUAL(u"MSIRESTARTMANAGERCONTROL=DisableShutdown"_ustr,
                             aCommand.Arguments[3]);

        const auto aProcessArguments = aCommand.getProcessArguments();
        CPPUNIT_ASSERT_EQUAL(aCommand.Arguments.size(), aProcessArguments.size());
        for (std::size_t nIndex = 0; nIndex < aCommand.Arguments.size(); ++nIndex)
            CPPUNIT_ASSERT(aProcessArguments[nIndex] == aCommand.Arguments[nIndex].pData);
    }

#ifdef _WIN32
    void testExclusiveWindowsInstallerStagingFile()
    {
        wchar_t aTempDirectory[MAX_PATH + 1] = {};
        const DWORD nTempDirectoryLength
            = GetTempPathW(static_cast<DWORD>(std::size(aTempDirectory)), aTempDirectory);
        CPPUNIT_ASSERT(nTempDirectoryLength > 0);
        CPPUNIT_ASSERT(nTempDirectoryLength < std::size(aTempDirectory));

        wchar_t aTempFile[MAX_PATH + 1] = {};
        CPPUNIT_ASSERT(GetTempFileNameW(aTempDirectory, L"lou", 0, aTempFile) != 0);
        CPPUNIT_ASSERT(DeleteFileW(aTempFile));
        comphelper::ScopeGuard aFileGuard([&]() { DeleteFileW(aTempFile); });

        const OUString aTempFilePath(o3tl::toU(aTempFile));
        void* pFirstHandle
            = createExclusiveWindowsInstallerStagingFile(aTempFilePath, nullptr);
        CPPUNIT_ASSERT(pFirstHandle != nullptr);
        comphelper::ScopeGuard aHandleGuard(
            [&]() { CloseHandle(static_cast<HANDLE>(pFirstHandle)); });

        constexpr char aSentinel[] = "exclusive-create-new";
        DWORD nWritten = 0;
        CPPUNIT_ASSERT(WriteFile(static_cast<HANDLE>(pFirstHandle), aSentinel,
                                 static_cast<DWORD>(sizeof(aSentinel) - 1), &nWritten, nullptr));
        CPPUNIT_ASSERT_EQUAL(DWORD(sizeof(aSentinel) - 1), nWritten);

        SetLastError(ERROR_SUCCESS);
        CPPUNIT_ASSERT(createExclusiveWindowsInstallerStagingFile(aTempFilePath, nullptr)
                       == nullptr);
        CPPUNIT_ASSERT_EQUAL(DWORD(ERROR_FILE_EXISTS), GetLastError());

        LARGE_INTEGER aBeginning{};
        CPPUNIT_ASSERT(SetFilePointerEx(static_cast<HANDLE>(pFirstHandle), aBeginning, nullptr,
                                        FILE_BEGIN));
        char aActual[sizeof(aSentinel)] = {};
        DWORD nRead = 0;
        CPPUNIT_ASSERT(ReadFile(static_cast<HANDLE>(pFirstHandle), aActual,
                                static_cast<DWORD>(sizeof(aSentinel) - 1), &nRead, nullptr));
        CPPUNIT_ASSERT_EQUAL(DWORD(sizeof(aSentinel) - 1), nRead);
        CPPUNIT_ASSERT(std::memcmp(aSentinel, aActual, sizeof(aSentinel) - 1) == 0);
    }

    void testProtectedWindowsInstallerStagingAndReadLock()
    {
        DownloadSource aSource(
            true,
            u"https://github.com/Ding-Ding-Projects/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
            u"1b8743c701ccbb5839b6cc8dd25eec1ac4a6ca4c3094fd6a5b2a8a49e69e058e"_ustr,
            50, u"windows-msi-test"_ustr, u"LibreOfficeMaterial-Windows-x64.msi"_ustr);
        const OUString aFixture
            = m_directories.getURLFromSrc(u"/extensions/qa/update/LibreOfficeMaterial-Windows-x64.msi");

        OUString aInstallerSystemPath;
        OUString aInstallerURL;
        OUString aDirectoryURL;
        void* pInstallerLock = nullptr;
        CPPUNIT_ASSERT(stageVerifiedWindowsInstaller(aFixture, aSource, aInstallerSystemPath,
                                                     aInstallerURL, aDirectoryURL,
                                                     pInstallerLock));
        comphelper::ScopeGuard aStagingGuard([&]() {
            cleanupStagedWindowsInstaller(pInstallerLock, aInstallerURL, aDirectoryURL);
        });
        CPPUNIT_ASSERT(pInstallerLock != nullptr);

        OUString aDirectorySystemPath;
        CPPUNIT_ASSERT_EQUAL(osl::FileBase::E_None,
                             osl::FileBase::getSystemPathFromFileURL(aDirectoryURL,
                                                                     aDirectorySystemPath));
        assertProtectedStagingAcl(aDirectorySystemPath);
        assertProtectedStagingAcl(aInstallerSystemPath);

        HANDLE hRead = CreateFileW(o3tl::toW(aInstallerSystemPath.getStr()), GENERIC_READ,
                                   FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                                   FILE_ATTRIBUTE_NORMAL, nullptr);
        CPPUNIT_ASSERT(hRead != INVALID_HANDLE_VALUE);
        comphelper::ScopeGuard aReadGuard([&]() { CloseHandle(hRead); });

        SetLastError(ERROR_SUCCESS);
        HANDLE hWrite = CreateFileW(
            o3tl::toW(aInstallerSystemPath.getStr()), GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL, nullptr);
        CPPUNIT_ASSERT(hWrite == INVALID_HANDLE_VALUE);
        CPPUNIT_ASSERT_EQUAL(DWORD(ERROR_SHARING_VIOLATION), GetLastError());

        SetLastError(ERROR_SUCCESS);
        HANDLE hDelete = CreateFileW(
            o3tl::toW(aInstallerSystemPath.getStr()), DELETE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL, nullptr);
        CPPUNIT_ASSERT(hDelete == INVALID_HANDLE_VALUE);
        CPPUNIT_ASSERT_EQUAL(DWORD(ERROR_SHARING_VIOLATION), GetLastError());
    }
#endif

    CPPUNIT_TEST_SUITE(Test);
    CPPUNIT_TEST(testGetUpdateInformationEnumeration);
    CPPUNIT_TEST(testCheckUpdateAvailable);
    CPPUNIT_TEST(testCheckUpToDate);
    CPPUNIT_TEST(testWrongMimeIsIgnored);
    CPPUNIT_TEST(testMissingHashIsIgnored);
    CPPUNIT_TEST(testTrustedSourceValidation);
    CPPUNIT_TEST(testVerifiedUpdateFile);
    CPPUNIT_TEST(testRejectedInstallerDisposition);
    CPPUNIT_TEST(testWindowsInstallerCommand);
#ifdef _WIN32
    CPPUNIT_TEST(testExclusiveWindowsInstallerStagingFile);
    CPPUNIT_TEST(testProtectedWindowsInstallerStagingAndReadLock);
#endif
    CPPUNIT_TEST_SUITE_END();

private:
    uno::Reference< deployment::XUpdateInformationProvider > m_xProvider;
    uno::Sequence< OUString > m_aRepositoryList;
};

CPPUNIT_TEST_SUITE_REGISTRATION(testupdate::Test);
} // namespace testupdate

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
