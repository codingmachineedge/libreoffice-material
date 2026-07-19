/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sal/config.h>

#include <cstddef>
#include <string_view>

#include <test/bootstrapfixture.hxx>

#include <com/sun/star/deployment/UpdateInformationEntry.hpp>
#include <com/sun/star/deployment/UpdateInformationProvider.hpp>
#include <com/sun/star/xml/dom/XNodeList.hpp>

#include "../../source/update/check/updatecheck.hxx"
#include "../../source/update/check/updateprotocol.hxx"

using namespace com::sun::star;
using namespace com::sun::star::xml;

namespace testupdate {

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
                u"https://github.com/codingmachineedge/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
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
            u"https://github.com/codingmachineedge/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
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

        DownloadSource aWrongName(aSource);
        aWrongName.FileName = u"other.msi"_ustr;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongName));

        DownloadSource aWrongSize(aSource);
        aWrongSize.Size = 0;
        CPPUNIT_ASSERT(!isTrustedMaterialUpdateSource(aWrongSize));
    }

    void testVerifiedUpdateFile()
    {
        DownloadSource aSource(
            true,
            u"https://github.com/codingmachineedge/libreoffice-material/releases/download/windows-msi-test/LibreOfficeMaterial-Windows-x64.msi"_ustr,
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

    CPPUNIT_TEST_SUITE(Test);
    CPPUNIT_TEST(testGetUpdateInformationEnumeration);
    CPPUNIT_TEST(testCheckUpdateAvailable);
    CPPUNIT_TEST(testCheckUpToDate);
    CPPUNIT_TEST(testWrongMimeIsIgnored);
    CPPUNIT_TEST(testMissingHashIsIgnored);
    CPPUNIT_TEST(testTrustedSourceValidation);
    CPPUNIT_TEST(testVerifiedUpdateFile);
    CPPUNIT_TEST_SUITE_END();

private:
    uno::Reference< deployment::XUpdateInformationProvider > m_xProvider;
    uno::Sequence< OUString > m_aRepositoryList;
};

CPPUNIT_TEST_SUITE_REGISTRATION(testupdate::Test);
} // namespace testupdate

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
