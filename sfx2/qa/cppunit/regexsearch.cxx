/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#include <sfx2/RegexSearchController.hxx>

#include <com/sun/star/util/SearchAlgorithms2.hpp>
#include <cppunit/TestAssert.h>
#include <rtl/ustrbuf.hxx>
#include <test/unoapi_test.hxx>

#include <chrono>

namespace
{
class RegexSearchTest : public UnoApiTest
{
public:
    RegexSearchTest()
        : UnoApiTest(u"/sfx2/qa/cppunit/data/"_ustr)
    {
    }
};

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testLiteralAndRegexHaveDifferentSemantics)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"."_ustr;
    aState.TestText = u"a.b"_ustr;
    aState.Flags.CaseInsensitive = false;

    auto aLiteral = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aLiteral.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(1), aLiteral.Matches.size());
    CPPUNIT_ASSERT_EQUAL(sal_Int32(1), aLiteral.Matches[0].Start);

    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    auto aRegex = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aRegex.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(3), aRegex.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testInvalidExpressionReportsIcuError)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"([A-Z]+"_ustr;
    aState.TestText = u"ABC"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;

    auto aEvaluation = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(!aEvaluation.IsValid);
    CPPUNIT_ASSERT(!aEvaluation.ErrorCode.isEmpty());
    CPPUNIT_ASSERT(aEvaluation.ErrorOffset >= 0);
    CPPUNIT_ASSERT(aEvaluation.Matches.empty());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testCaseInsensitiveFlagUsesUnicodeSearch)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"äpfel"_ustr;
    aState.TestText = u"ÄPFEL and äpfel"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.CaseInsensitive = true;

    auto aEvaluation = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aEvaluation.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testGlobalFlagControlsFirstVersusAllMatches)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"item"_ustr;
    aState.TestText = u"item item item"_ustr;
    aState.Flags.CaseInsensitive = false;
    aState.Flags.Global = false;

    auto aFirst = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aFirst.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(1), aFirst.Matches.size());
    CPPUNIT_ASSERT(!aFirst.Truncated);

    aState.Flags.Global = true;
    auto aAll = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aAll.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(3), aAll.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testMultilineAndDotAllFlags)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"^item.*done$"_ustr;
    aState.TestText = u"header\nitem\ncontinued\ndone\nfooter"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.CaseInsensitive = false;

    auto aWithoutFlags = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aWithoutFlags.IsValid);
    CPPUNIT_ASSERT(aWithoutFlags.Matches.empty());

    aState.Flags.Multiline = true;
    aState.Flags.DotMatchesNewline = true;
    auto aWithFlags = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aWithFlags.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(1), aWithFlags.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testOptionsUseLibreOfficeSearchEngine)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"^value.$"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.Multiline = true;
    aState.Flags.DotMatchesNewline = true;

    const auto aOptions = sfx2::RegexSearchService::CreateSearchOptions(aState);
    CPPUNIT_ASSERT_EQUAL(sal_Int16(css::util::SearchAlgorithms2::REGEXP), aOptions.AlgorithmType2);
    CPPUNIT_ASSERT_EQUAL(u"(?ms)^value.$"_ustr, aOptions.searchString);
    CPPUNIT_ASSERT(bool(aOptions.transliterateFlags & TransliterationFlags::IGNORE_CASE));
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testZeroWidthMatchAndPreviewLimitTerminate)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"(?=a)"_ustr;
    aState.TestText = u"aaaa"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.CaseInsensitive = false;

    auto aEvaluation = sfx2::RegexSearchService::Evaluate(aState, 2);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(2), aEvaluation.Matches.size());
    CPPUNIT_ASSERT(aEvaluation.Truncated);
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testLivePreviewHasExactTextAndMatchBounds)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"a"_ustr;
    aState.Flags.CaseInsensitive = false;

    OUStringBuffer aText(sfx2::RegexSearchService::PreviewMaxTextCodeUnits + 32);
    for (sal_Int32 nIndex = 0; nIndex < sfx2::RegexSearchService::PreviewMaxTextCodeUnits + 32;
         ++nIndex)
    {
        aText.append('a');
    }
    aState.TestText = aText.makeStringAndClear();

    const auto aEvaluation = sfx2::RegexSearchService::EvaluatePreview(aState);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT(aEvaluation.InputTruncated);
    CPPUNIT_ASSERT(aEvaluation.Truncated);
    CPPUNIT_ASSERT_EQUAL(size_t(sfx2::RegexSearchService::PreviewMaxMatches),
                         aEvaluation.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testLivePreviewNeverTruncatesAnOversizedPattern)
{
    sfx2::RegexSearchState aState;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;

    OUStringBuffer aPattern(sfx2::RegexSearchService::PreviewMaxPatternCodeUnits + 1);
    for (sal_Int32 nIndex = 0; nIndex < sfx2::RegexSearchService::PreviewMaxPatternCodeUnits + 1;
         ++nIndex)
    {
        aPattern.append('a');
    }
    aState.Pattern = aPattern.makeStringAndClear();
    aState.TestText = aState.Pattern;

    const auto aEvaluation = sfx2::RegexSearchService::EvaluatePreview(aState);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT(aEvaluation.PreviewSkipped);
    CPPUNIT_ASSERT(aEvaluation.Matches.empty());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testLivePreviewEmulatesLibreOfficeWordBounds)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"\\<word\\>"_ustr;
    aState.TestText = u"sword word wording"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.CaseInsensitive = false;

    const auto aEvaluation = sfx2::RegexSearchService::EvaluatePreview(aState);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT_EQUAL(size_t(1), aEvaluation.Matches.size());
    CPPUNIT_ASSERT_EQUAL(sal_Int32(6), aEvaluation.Matches[0].Start);
    CPPUNIT_ASSERT_EQUAL(sal_Int32(10), aEvaluation.Matches[0].End);
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testConsumerEvaluateDoesNotUseLivePreviewMatchCap)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"a"_ustr;
    aState.Flags.CaseInsensitive = false;

    OUStringBuffer aText(sfx2::RegexSearchService::PreviewMaxMatches + 1);
    for (sal_Int32 nIndex = 0; nIndex < sfx2::RegexSearchService::PreviewMaxMatches + 1; ++nIndex)
    {
        aText.append('a');
    }
    aState.TestText = aText.makeStringAndClear();

    const auto aEvaluation = sfx2::RegexSearchService::Evaluate(aState);
    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT(!aEvaluation.Truncated);
    CPPUNIT_ASSERT(!aEvaluation.InputTruncated);
    CPPUNIT_ASSERT_EQUAL(size_t(sfx2::RegexSearchService::PreviewMaxMatches + 1),
                         aEvaluation.Matches.size());
}

CPPUNIT_TEST_FIXTURE(RegexSearchTest, testPathologicalLivePreviewStopsAtBudget)
{
    sfx2::RegexSearchState aState;
    aState.Pattern = u"(a+)+$"_ustr;
    aState.Mode = sfx2::RegexSearchMode::RegularExpression;
    aState.Flags.CaseInsensitive = false;

    OUStringBuffer aText(sfx2::RegexSearchService::PreviewMaxTextCodeUnits);
    for (sal_Int32 nIndex = 0; nIndex < sfx2::RegexSearchService::PreviewMaxTextCodeUnits - 1;
         ++nIndex)
    {
        aText.append('a');
    }
    aText.append('!');
    aState.TestText = aText.makeStringAndClear();

    const auto aStart = std::chrono::steady_clock::now();
    const auto aEvaluation = sfx2::RegexSearchService::EvaluatePreview(aState);
    const auto aElapsed = std::chrono::steady_clock::now() - aStart;

    CPPUNIT_ASSERT(aEvaluation.IsValid);
    CPPUNIT_ASSERT(aEvaluation.BudgetExceeded);
    CPPUNIT_ASSERT(aEvaluation.Matches.empty());
    // The generous wall bound catches a lost ICU budget while tolerating a loaded CI worker.
    CPPUNIT_ASSERT(aElapsed < std::chrono::seconds(2));
}

} // namespace

CPPUNIT_PLUGIN_IMPLEMENT();

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
