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
#include <i18nutil/transliteration.hxx>
#include <rtl/character.hxx>
#include <sfx2/sfxresid.hxx>
#include <sfx2/strings.hrc>
#include <unotools/textsearch.hxx>
#include <vcl/svapp.hxx>
#include <vcl/timer.hxx>
#include <vcl/weld/Builder.hxx>
#include <vcl/weld/Button.hxx>
#include <vcl/weld/CheckButton.hxx>
#include <vcl/weld/ComboBox.hxx>
#include <vcl/weld/Entry.hxx>
#include <vcl/weld/Label.hxx>
#include <vcl/weld/Popover.hxx>
#include <vcl/weld/TextView.hxx>
#include <vcl/weld/Widget.hxx>

#include <unicode/regex.h>
#include <unicode/utypes.h>

#include <algorithm>
#include <cassert>
#include <chrono>
#include <memory>
#include <utility>
#include <vector>

namespace sfx2
{
namespace
{
constexpr sal_uInt64 RegexPreviewDebounceMilliseconds = 200;
constexpr int RegexPopoverMaximumWidth = 780;
constexpr int RegexPopoverMaximumHeight = 620;
constexpr int RegexPopoverParentMargin = 24;
constexpr int RegexPopoverFallbackWidth = 720;
constexpr int RegexPopoverFallbackHeight = 560;

sal_Int32 lclAdvancePastEmptyMatch(const OUString& rText, sal_Int32 nPosition)
{
    if (nPosition >= rText.getLength())
        return rText.getLength() + 1;

    rText.iterateCodePoints(&nPosition);
    return nPosition;
}

OUString lclExpandLegacyWordBounds(const OUString& rPattern)
{
#ifndef DISABLE_WORDBOUND_EMULATION
    return rPattern.replaceAll(u"\\<"_ustr, u"\\b(?=\\w)"_ustr)
        .replaceAll(u"\\>"_ustr, u"(?<=\\w)\\b"_ustr);
#else
    return rPattern;
#endif
}

std::unique_ptr<icu::RegexPattern> lclCompilePattern(const RegexSearchState& rState,
                                                     const OUString& rEffectivePattern,
                                                     RegexSearchEvaluation& rEvaluation)
{
    UErrorCode nStatus = U_ZERO_ERROR;
    UParseError aParseError{};
    uint32_t nFlags = UREGEX_UWORD;
    if (rState.Flags.CaseInsensitive)
        nFlags |= UREGEX_CASE_INSENSITIVE;

    const icu::UnicodeString aIcuPattern(reinterpret_cast<const UChar*>(rEffectivePattern.getStr()),
                                         rEffectivePattern.getLength());
    std::unique_ptr<icu::RegexPattern> xPattern(
        icu::RegexPattern::compile(aIcuPattern, nFlags, aParseError, nStatus));
    if (!U_FAILURE(nStatus) && xPattern)
        return xPattern;

    rEvaluation.IsValid = false;
    rEvaluation.ErrorCode = OUString::createFromAscii(u_errorName(nStatus));
    if (aParseError.offset >= 0)
    {
        const sal_Int32 nModePrefixLength
            = rEffectivePattern.getLength() - rState.Pattern.getLength();
        rEvaluation.ErrorOffset = std::max<sal_Int32>(0, aParseError.offset - nModePrefixLength);
    }
    return nullptr;
}

struct RegexPreviewDeadline
{
    std::chrono::steady_clock::time_point End;
};

UBool U_CALLCONV lclRegexPreviewMatchCallback(const void* pContext, int32_t)
{
    const auto* pDeadline = static_cast<const RegexPreviewDeadline*>(pContext);
    return std::chrono::steady_clock::now() < pDeadline->End;
}

bool lclIsPreviewBudgetError(UErrorCode nStatus)
{
    return nStatus == U_REGEX_TIME_OUT || nStatus == U_REGEX_STOPPED_BY_CALLER
           || nStatus == U_REGEX_STACK_OVERFLOW;
}

OUString lclClipPreviewText(const OUString& rText, bool& rWasClipped)
{
    if (rText.getLength() <= RegexSearchService::PreviewMaxTextCodeUnits)
    {
        rWasClipped = false;
        return rText;
    }

    sal_Int32 nLength = RegexSearchService::PreviewMaxTextCodeUnits;
    if (nLength > 0 && rtl::isHighSurrogate(rText[nLength - 1])
        && rtl::isLowSurrogate(rText[nLength]))
    {
        --nLength;
    }
    rWasClipped = true;
    return rText.copy(0, nLength);
}

int lclResponsivePopoverRequest(int nAvailable, int nFallback, int nMaximum)
{
    if (nAvailable <= 0)
        return nFallback;
    const int nParentBound = nAvailable > RegexPopoverParentMargin
                                 ? nAvailable - RegexPopoverParentMargin
                                 : nAvailable;
    return std::max(1, std::min(nMaximum, nParentBound));
}
} // namespace

class RegexBuilderPopover final
{
    weld::Widget* m_pParent;
    std::unique_ptr<weld::Builder> m_xBuilder;
    std::unique_ptr<weld::Popover> m_xPopover;
    RegexSearchState m_aState;
    Timer m_aPreviewTimer;

    std::unique_ptr<weld::Widget> m_xContent;
    std::unique_ptr<weld::Entry> m_xPatternEntry;
    std::unique_ptr<weld::CheckButton> m_xRegexMode;
    std::unique_ptr<weld::CheckButton> m_xCaseInsensitive;
    std::unique_ptr<weld::CheckButton> m_xGlobal;
    std::unique_ptr<weld::CheckButton> m_xMultiline;
    std::unique_ptr<weld::CheckButton> m_xDotAll;
    std::unique_ptr<weld::TextView> m_xTestText;
    std::unique_ptr<weld::Label> m_xValidityLabel;
    std::unique_ptr<weld::Label> m_xMatchLabel;
    std::unique_ptr<weld::Button> m_xApplyButton;
    std::unique_ptr<weld::Button> m_xCancelButton;
    std::vector<std::pair<std::unique_ptr<weld::Button>, OUString>> m_aInsertButtons;
    Link<RegexBuilderPopover&, void> m_aApplyHdl;
    Link<weld::Popover&, void> m_aClosedHdl;
    bool m_bCloseNotified = true;

    void NotifyClosed()
    {
        m_aPreviewTimer.Stop();
        if (m_bCloseNotified)
            return;
        m_bCloseNotified = true;
        m_aClosedHdl.Call(*m_xPopover);
    }

    void ReadStateFromWidgets()
    {
        m_aState.Pattern = m_xPatternEntry->get_text();
        m_aState.TestText = m_xTestText->get_text();
        m_aState.Mode = m_xRegexMode->get_active() ? RegexSearchMode::RegularExpression
                                                   : RegexSearchMode::Literal;
        m_aState.Flags.CaseInsensitive = m_xCaseInsensitive->get_active();
        m_aState.Flags.Global = m_xGlobal->get_active();
        m_aState.Flags.Multiline = m_xMultiline->get_active();
        m_aState.Flags.DotMatchesNewline = m_xDotAll->get_active();
    }

    void UpdateControlSensitivity()
    {
        const bool bRegex = m_aState.Mode == RegexSearchMode::RegularExpression;
        m_xMultiline->set_sensitive(bRegex);
        m_xDotAll->set_sensitive(bRegex);
        for (auto& rInsert : m_aInsertButtons)
            rInsert.first->set_sensitive(bRegex);
    }

    void SetPreviewPending()
    {
        ReadStateFromWidgets();
        UpdateControlSensitivity();
        m_aPreviewTimer.Stop();
        m_xApplyButton->set_sensitive(false);
        m_xPatternEntry->set_message_type(weld::EntryMessageType::Normal);
        m_xValidityLabel->set_label(SfxResId(STR_REGEX_BUILDER_PREVIEW_PENDING));
        m_xValidityLabel->set_label_type(weld::LabelType::Normal);
        m_xMatchLabel->set_label(SfxResId(STR_REGEX_BUILDER_PREVIEW_PENDING));
        m_aPreviewTimer.Start();
    }

    void UpdatePreview()
    {
        m_aPreviewTimer.Stop();
        ReadStateFromWidgets();
        UpdateControlSensitivity();

        const RegexSearchEvaluation aEvaluation = RegexSearchService::EvaluatePreview(m_aState);
        m_xApplyButton->set_sensitive(aEvaluation.IsValid);
        m_xPatternEntry->set_message_type(aEvaluation.IsValid ? weld::EntryMessageType::Normal
                                                              : weld::EntryMessageType::Error);

        if (!aEvaluation.IsValid)
        {
            OUString aError;
            if (aEvaluation.ErrorOffset >= 0)
            {
                aError
                    = SfxResId(STR_REGEX_BUILDER_INVALID_AT)
                          .replaceFirst(u"%1"_ustr, aEvaluation.ErrorCode)
                          .replaceFirst(u"%2"_ustr, OUString::number(aEvaluation.ErrorOffset + 1));
            }
            else
            {
                aError = SfxResId(STR_REGEX_BUILDER_INVALID)
                             .replaceFirst(u"%1"_ustr, aEvaluation.ErrorCode);
            }
            m_xValidityLabel->set_label(aError);
            m_xValidityLabel->set_label_type(weld::LabelType::Error);
            m_xMatchLabel->set_label(SfxResId(STR_REGEX_BUILDER_MATCHES_UNAVAILABLE));
            return;
        }

        if (aEvaluation.PreviewSkipped)
        {
            m_xValidityLabel->set_label(SfxResId(STR_REGEX_BUILDER_PREVIEW_SKIPPED));
            m_xValidityLabel->set_label_type(weld::LabelType::Normal);
            m_xMatchLabel->set_label(SfxResId(STR_REGEX_BUILDER_PREVIEW_SKIPPED));
            return;
        }

        m_xValidityLabel->set_label(m_aState.Pattern.isEmpty()
                                        ? SfxResId(STR_REGEX_BUILDER_ENTER_PATTERN)
                                        : SfxResId(STR_REGEX_BUILDER_VALID));
        m_xValidityLabel->set_label_type(weld::LabelType::Normal);

        OUString aMatchText;
        if (m_aState.Pattern.isEmpty())
            aMatchText = SfxResId(STR_REGEX_BUILDER_MATCH_NONE);
        else if (aEvaluation.Matches.empty())
            aMatchText = SfxResId(STR_REGEX_BUILDER_MATCH_NONE);
        else if (!m_aState.Flags.Global && aEvaluation.Matches.size() == 1)
            aMatchText = SfxResId(STR_REGEX_BUILDER_MATCH_FIRST);
        else if (aEvaluation.Matches.size() == 1)
            aMatchText = SfxResId(STR_REGEX_BUILDER_MATCH_ONE);
        else
            aMatchText
                = SfxResId(STR_REGEX_BUILDER_MATCH_COUNT)
                      .replaceFirst(u"%1"_ustr, OUString::number(aEvaluation.Matches.size()));

        if (aEvaluation.BudgetExceeded)
            aMatchText = SfxResId(STR_REGEX_BUILDER_PREVIEW_BUDGET);
        else if (aEvaluation.Truncated)
            aMatchText += u" "_ustr + SfxResId(STR_REGEX_BUILDER_MATCH_TRUNCATED);
        if (aEvaluation.InputTruncated)
            aMatchText += u" "_ustr + SfxResId(STR_REGEX_BUILDER_INPUT_TRUNCATED);
        m_xMatchLabel->set_label(aMatchText);
    }

    void UpdateResponsiveSize()
    {
        int nX = 0;
        int nY = 0;
        int nParentWidth = 0;
        int nParentHeight = 0;
        if (m_pParent)
        {
            if (!m_pParent->get_extents_relative_to(*m_pParent, nX, nY, nParentWidth,
                                                    nParentHeight))
            {
                const Size aPreferredSize = m_pParent->get_preferred_size();
                nParentWidth = aPreferredSize.Width();
                nParentHeight = aPreferredSize.Height();
            }
        }

        m_xContent->set_size_request(
            lclResponsivePopoverRequest(nParentWidth, RegexPopoverFallbackWidth,
                                        RegexPopoverMaximumWidth),
            lclResponsivePopoverRequest(nParentHeight, RegexPopoverFallbackHeight,
                                        RegexPopoverMaximumHeight));
    }

    DECL_LINK(TextChangedHdl, weld::TextWidget&, void);
    DECL_LINK(ModeChangedHdl, weld::Toggleable&, void);
    DECL_LINK(InsertClickedHdl, weld::Button&, void);
    DECL_LINK(ApplyClickedHdl, weld::Button&, void);
    DECL_LINK(CancelClickedHdl, weld::Button&, void);
    DECL_LINK(PreviewTimerHdl, Timer*, void);
    DECL_LINK(PopoverClosedHdl, weld::Popover&, void);

public:
    RegexBuilderPopover(weld::Widget* pParent, const RegexSearchState& rState)
        : m_pParent(pParent)
        , m_xBuilder(Application::CreateBuilder(pParent, u"sfx/ui/regexbuilder.ui"_ustr))
        , m_xPopover(m_xBuilder->weld_popover(u"RegexBuilderPopover"_ustr))
        , m_aState(rState)
        , m_aPreviewTimer("sfx2::RegexBuilderPopover preview")
        , m_xContent(m_xBuilder->weld_widget(u"builder_content"_ustr))
        , m_xPatternEntry(m_xBuilder->weld_entry(u"pattern"_ustr))
        , m_xRegexMode(m_xBuilder->weld_check_button(u"regexmode"_ustr))
        , m_xCaseInsensitive(m_xBuilder->weld_check_button(u"caseinsensitive"_ustr))
        , m_xGlobal(m_xBuilder->weld_check_button(u"global"_ustr))
        , m_xMultiline(m_xBuilder->weld_check_button(u"multiline"_ustr))
        , m_xDotAll(m_xBuilder->weld_check_button(u"dotall"_ustr))
        , m_xTestText(m_xBuilder->weld_text_view(u"testtext"_ustr))
        , m_xValidityLabel(m_xBuilder->weld_label(u"validity"_ustr))
        , m_xMatchLabel(m_xBuilder->weld_label(u"matchsummary"_ustr))
        , m_xApplyButton(m_xBuilder->weld_button(u"apply"_ustr))
        , m_xCancelButton(m_xBuilder->weld_button(u"cancel"_ustr))
    {
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_start"_ustr), u"^"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_end"_ustr), u"$"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_any"_ustr), u"."_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_digit"_ustr), u"\\d"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_space"_ustr), u"\\s"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_word"_ustr), u"\\w"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_class"_ustr), u"[...]"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_group"_ustr), u"(...)"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_noncapture"_ustr),
                                      u"(?:...)"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_lookahead"_ustr),
                                      u"(?=...)"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_lookbehind"_ustr),
                                      u"(?<=...)"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_zero_more"_ustr), u"*"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_one_more"_ustr), u"+"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_optional"_ustr), u"?"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_range"_ustr), u"{n,m}"_ustr);
        m_aInsertButtons.emplace_back(m_xBuilder->weld_button(u"insert_escape"_ustr),
                                      u"\\Q...\\E"_ustr);

        m_xPatternEntry->set_text(m_aState.Pattern);
        m_xRegexMode->set_active(m_aState.Mode == RegexSearchMode::RegularExpression);
        m_xCaseInsensitive->set_active(m_aState.Flags.CaseInsensitive);
        m_xGlobal->set_active(m_aState.Flags.Global);
        m_xMultiline->set_active(m_aState.Flags.Multiline);
        m_xDotAll->set_active(m_aState.Flags.DotMatchesNewline);
        m_xTestText->set_text(m_aState.TestText);
        m_xTestText->set_monospace(true);

        m_xPatternEntry->connect_changed(LINK(this, RegexBuilderPopover, TextChangedHdl));
        m_xTestText->connect_changed(LINK(this, RegexBuilderPopover, TextChangedHdl));
        m_xRegexMode->connect_toggled(LINK(this, RegexBuilderPopover, ModeChangedHdl));
        m_xCaseInsensitive->connect_toggled(LINK(this, RegexBuilderPopover, ModeChangedHdl));
        m_xGlobal->connect_toggled(LINK(this, RegexBuilderPopover, ModeChangedHdl));
        m_xMultiline->connect_toggled(LINK(this, RegexBuilderPopover, ModeChangedHdl));
        m_xDotAll->connect_toggled(LINK(this, RegexBuilderPopover, ModeChangedHdl));
        for (auto& rInsert : m_aInsertButtons)
            rInsert.first->connect_clicked(LINK(this, RegexBuilderPopover, InsertClickedHdl));
        m_xApplyButton->connect_clicked(LINK(this, RegexBuilderPopover, ApplyClickedHdl));
        m_xCancelButton->connect_clicked(LINK(this, RegexBuilderPopover, CancelClickedHdl));
        m_xPopover->connect_closed(LINK(this, RegexBuilderPopover, PopoverClosedHdl));
        m_aPreviewTimer.SetTimeout(RegexPreviewDebounceMilliseconds);
        m_aPreviewTimer.SetInvokeHandler(LINK(this, RegexBuilderPopover, PreviewTimerHdl));

        UpdatePreview();
        m_xPatternEntry->grab_focus();
    }

    ~RegexBuilderPopover()
    {
        m_aPreviewTimer.Stop();
        m_aPreviewTimer.ClearInvokeHandler();
        m_xPopover->connect_closed(Link<weld::Popover&, void>());
    }

    void SetApplyHdl(const Link<RegexBuilderPopover&, void>& rLink) { m_aApplyHdl = rLink; }
    void SetClosedHdl(const Link<weld::Popover&, void>& rLink) { m_aClosedHdl = rLink; }
    void DisconnectHandlers()
    {
        m_aPreviewTimer.Stop();
        m_bCloseNotified = true;
        m_aApplyHdl = Link<RegexBuilderPopover&, void>();
        m_aClosedHdl = Link<weld::Popover&, void>();
    }

    void PopupAt(weld::Button& rAnchor)
    {
        UpdateResponsiveSize();
        const Size aAnchorSize = rAnchor.get_preferred_size();
        m_bCloseNotified = false;
        m_xPopover->popup_at_rect(&rAnchor, tools::Rectangle(Point(0, 0), aAnchorSize));
        m_xPatternEntry->grab_focus();
    }

    void Popdown()
    {
        m_aPreviewTimer.Stop();
        m_xPopover->popdown();
        // Some backends emit weld::Popover::closed for popdown(), while Qt currently only hides
        // the widget. Keep close bookkeeping and preview cancellation backend-independent.
        NotifyClosed();
    }
    const RegexSearchState& GetState() const { return m_aState; }
};

IMPL_LINK_NOARG(RegexBuilderPopover, TextChangedHdl, weld::TextWidget&, void)
{
    SetPreviewPending();
}

IMPL_LINK_NOARG(RegexBuilderPopover, ModeChangedHdl, weld::Toggleable&, void)
{
    SetPreviewPending();
}

IMPL_LINK(RegexBuilderPopover, InsertClickedHdl, weld::Button&, rButton, void)
{
    const auto aFound
        = std::find_if(m_aInsertButtons.begin(), m_aInsertButtons.end(),
                       [&rButton](const auto& rInsert) { return rInsert.first.get() == &rButton; });
    if (aFound == m_aInsertButtons.end())
        return;

    m_xPatternEntry->replace_selection(aFound->second);
    m_xPatternEntry->grab_focus();
    SetPreviewPending();
}

IMPL_LINK_NOARG(RegexBuilderPopover, ApplyClickedHdl, weld::Button&, void)
{
    ReadStateFromWidgets();
    m_aApplyHdl.Call(*this);
}

IMPL_LINK_NOARG(RegexBuilderPopover, CancelClickedHdl, weld::Button&, void)
{
    Popdown();
}

IMPL_LINK_NOARG(RegexBuilderPopover, PreviewTimerHdl, Timer*, void) { UpdatePreview(); }

IMPL_LINK(RegexBuilderPopover, PopoverClosedHdl, weld::Popover&, rPopover, void)
{
    (void)rPopover;
    NotifyClosed();
}

OUString RegexSearchService::GetEffectivePattern(const RegexSearchState& rState)
{
    if (rState.Mode != RegexSearchMode::RegularExpression)
        return rState.Pattern;

    OUString aModes;
    if (rState.Flags.Multiline)
        aModes += u"m"_ustr;
    if (rState.Flags.DotMatchesNewline)
        aModes += u"s"_ustr;

    if (aModes.isEmpty())
        return rState.Pattern;
    return u"(?"_ustr + aModes + u")"_ustr + rState.Pattern;
}

i18nutil::SearchOptions2 RegexSearchService::CreateSearchOptions(const RegexSearchState& rState)
{
    i18nutil::SearchOptions2 aOptions;
    aOptions.AlgorithmType2 = rState.Mode == RegexSearchMode::RegularExpression
                                  ? css::util::SearchAlgorithms2::REGEXP
                                  : css::util::SearchAlgorithms2::ABSOLUTE;
    aOptions.searchString = GetEffectivePattern(rState);
    if (rState.Flags.CaseInsensitive)
        aOptions.transliterateFlags |= TransliterationFlags::IGNORE_CASE;
    return aOptions;
}

RegexSearchEvaluation RegexSearchService::Validate(const RegexSearchState& rState)
{
    RegexSearchEvaluation aEvaluation;
    if (rState.Pattern.isEmpty() || rState.Mode != RegexSearchMode::RegularExpression)
        return aEvaluation;

    const OUString aEffectivePattern = GetEffectivePattern(rState);
    if (!lclCompilePattern(rState, aEffectivePattern, aEvaluation))
        return aEvaluation;

    // TextSearch expands LibreOffice's legacy word-boundary forms before ICU executes the
    // expression. Validate that same effective expression so direct-entry error state cannot
    // disagree with the preview or the eventual consumer search.
    const OUString aExpandedPattern = lclExpandLegacyWordBounds(aEffectivePattern);
    if (aExpandedPattern != aEffectivePattern)
    {
        RegexSearchEvaluation aExpandedEvaluation;
        if (!lclCompilePattern(rState, aExpandedPattern, aExpandedEvaluation))
        {
            aEvaluation.IsValid = false;
            aEvaluation.ErrorCode = aExpandedEvaluation.ErrorCode;
            // Expansion changes offsets, so an ICU offset in the expanded form would point at
            // the wrong character in the user's original pattern.
            aEvaluation.ErrorOffset = -1;
        }
    }
    return aEvaluation;
}

RegexSearchEvaluation RegexSearchService::EvaluatePreview(const RegexSearchState& rState)
{
    RegexSearchEvaluation aEvaluation;
    if (rState.Pattern.isEmpty())
        return aEvaluation;

    if (rState.Pattern.getLength() > PreviewMaxPatternCodeUnits)
    {
        aEvaluation.PreviewSkipped = true;
        return aEvaluation;
    }

    RegexSearchState aPreviewState(rState);
    aPreviewState.TestText = lclClipPreviewText(rState.TestText, aEvaluation.InputTruncated);
    if (rState.Mode == RegexSearchMode::Literal)
    {
        RegexSearchEvaluation aLiteralEvaluation = Evaluate(aPreviewState, PreviewMaxMatches);
        aLiteralEvaluation.InputTruncated = aEvaluation.InputTruncated;
        return aLiteralEvaluation;
    }

    const OUString aEffectivePattern = GetEffectivePattern(aPreviewState);
    std::unique_ptr<icu::RegexPattern> xPattern
        = lclCompilePattern(aPreviewState, aEffectivePattern, aEvaluation);
    if (!xPattern)
        return aEvaluation;

    const OUString aPreviewPattern = lclExpandLegacyWordBounds(aEffectivePattern);
    if (aPreviewPattern != aEffectivePattern)
    {
        RegexSearchEvaluation aExpandedEvaluation;
        xPattern = lclCompilePattern(aPreviewState, aPreviewPattern, aExpandedEvaluation);
        if (!xPattern)
        {
            aEvaluation.IsValid = false;
            aEvaluation.ErrorCode = aExpandedEvaluation.ErrorCode;
            return aEvaluation;
        }
    }

    UErrorCode nStatus = U_ZERO_ERROR;
    const icu::UnicodeString aIcuText(
        reinterpret_cast<const UChar*>(aPreviewState.TestText.getStr()),
        aPreviewState.TestText.getLength());
    RegexPreviewDeadline aDeadline{ std::chrono::steady_clock::now()
                                    + std::chrono::milliseconds(PreviewDeadlineMilliseconds) };
    std::unique_ptr<icu::RegexMatcher> xMatcher(xPattern->matcher(aIcuText, nStatus));
    if (!U_FAILURE(nStatus) && xMatcher)
        xMatcher->setTimeLimit(PreviewProcessingStepLimit, nStatus);
    if (!U_FAILURE(nStatus) && xMatcher)
        xMatcher->setStackLimit(PreviewStackLimitBytes, nStatus);
    if (!U_FAILURE(nStatus) && xMatcher)
        xMatcher->setMatchCallback(lclRegexPreviewMatchCallback, &aDeadline, nStatus);

    bool bFindReturnedFalse = false;
    while (!U_FAILURE(nStatus) && xMatcher)
    {
        if (!xMatcher->find(nStatus))
        {
            bFindReturnedFalse = true;
            break;
        }
        if (aEvaluation.Matches.size() >= static_cast<size_t>(PreviewMaxMatches))
        {
            aEvaluation.Truncated = true;
            break;
        }

        const sal_Int32 nStart = xMatcher->start(nStatus);
        const sal_Int32 nEnd = xMatcher->end(nStatus);
        if (U_FAILURE(nStatus))
            break;
        aEvaluation.Matches.push_back({ nStart, nEnd });
        if (!aPreviewState.Flags.Global)
            break;
    }

    // ICU can report U_REGEX_TIME_OUT only on the call following the one that stopped. A second
    // failed find is side-effect-free (the matcher has already reported no next match) and makes
    // the live-preview budget result observable instead of looking like a normal no-match result.
    if (bFindReturnedFalse && !U_FAILURE(nStatus) && xMatcher)
        (void)xMatcher->find(nStatus);

    if (lclIsPreviewBudgetError(nStatus))
        aEvaluation.BudgetExceeded = true;
    else if (U_FAILURE(nStatus))
    {
        aEvaluation.IsValid = false;
        aEvaluation.ErrorCode = OUString::createFromAscii(u_errorName(nStatus));
    }
    return aEvaluation;
}

RegexSearchEvaluation RegexSearchService::Evaluate(const RegexSearchState& rState,
                                                   sal_Int32 nMatchLimit)
{
    RegexSearchEvaluation aEvaluation = Validate(rState);
    if (!aEvaluation.IsValid || rState.Pattern.isEmpty())
        return aEvaluation;

    utl::TextSearch aSearch(CreateSearchOptions(rState));
    sal_Int32 nCursor = 0;
    const sal_Int32 nTextLength = rState.TestText.getLength();
    nMatchLimit = std::max<sal_Int32>(1, nMatchLimit);

    while (nCursor <= nTextLength)
    {
        sal_Int32 nStart = nCursor;
        sal_Int32 nEnd = nTextLength;
        if (!aSearch.SearchForward(rState.TestText, &nStart, &nEnd))
            break;

        if (aEvaluation.Matches.size() >= static_cast<size_t>(nMatchLimit))
        {
            aEvaluation.Truncated = true;
            break;
        }

        aEvaluation.Matches.push_back({ nStart, nEnd });
        if (!rState.Flags.Global)
            break;
        nCursor = nEnd > nStart ? nEnd : lclAdvancePastEmptyMatch(rState.TestText, nEnd);
    }

    return aEvaluation;
}

RegexSearchController::RegexSearchController(
    weld::Widget* pParent, weld::Entry& rEntry, weld::Button& rBuilderButton,
    const Link<weld::TextWidget&, void>& rOwnerEntryChangedHdl,
    const Link<weld::Button&, void>& rOwnerBuilderClickedHdl)
    : m_pBuilderParent(pParent)
    , m_pSearchWidget(&rEntry)
    , m_pEntry(&rEntry)
    , m_pBuilderButton(&rBuilderButton)
    , m_aOriginalSearchTooltip(m_pSearchWidget->get_tooltip_text())
    , m_aOriginalBuilderTooltip(m_pBuilderButton->get_tooltip_text())
    , m_aOriginalBuilderAccessibleName(m_pBuilderButton->get_accessible_name())
    , m_aOriginalBuilderAccessibleDescription(m_pBuilderButton->get_accessible_description())
    , m_aOwnerEntryChangedHdl(rOwnerEntryChangedHdl)
    , m_aOwnerBuilderClickedHdl(rOwnerBuilderClickedHdl)
{
    Initialize();
}

RegexSearchController::RegexSearchController(
    weld::Widget* pParent, weld::ComboBox& rComboBox, weld::Button& rBuilderButton,
    const Link<weld::ComboBox&, void>& rOwnerComboChangedHdl,
    const Link<weld::Button&, void>& rOwnerBuilderClickedHdl)
    : m_pBuilderParent(pParent)
    , m_pSearchWidget(&rComboBox)
    , m_pComboBox(&rComboBox)
    , m_pBuilderButton(&rBuilderButton)
    , m_aOriginalSearchTooltip(m_pSearchWidget->get_tooltip_text())
    , m_aOriginalBuilderTooltip(m_pBuilderButton->get_tooltip_text())
    , m_aOriginalBuilderAccessibleName(m_pBuilderButton->get_accessible_name())
    , m_aOriginalBuilderAccessibleDescription(m_pBuilderButton->get_accessible_description())
    , m_aOwnerComboChangedHdl(rOwnerComboChangedHdl)
    , m_aOwnerBuilderClickedHdl(rOwnerBuilderClickedHdl)
{
    assert(m_pComboBox->has_entry());
    Initialize();
}

void RegexSearchController::Initialize()
{
    m_aState.Pattern = GetSearchText();
    m_pBuilderButton->set_accessible_name(SfxResId(STR_REGEX_BUILDER_ACCESSIBLE_NAME));
    m_pBuilderButton->set_accessible_description(
        SfxResId(STR_REGEX_BUILDER_ACCESSIBLE_DESCRIPTION));
    m_pBuilderButton->set_tooltip_text(SfxResId(STR_REGEX_BUILDER_TOOLTIP));
    if (m_pEntry)
        m_pEntry->connect_changed(LINK(this, RegexSearchController, EntryChangedHdl));
    else
        m_pComboBox->connect_changed(LINK(this, RegexSearchController, ComboChangedHdl));
    m_pBuilderButton->connect_clicked(LINK(this, RegexSearchController, BuilderClickedHdl));
    UpdateSearchValidity();
}

RegexSearchController::~RegexSearchController()
{
    if (m_xBuilderPopover)
    {
        m_xBuilderPopover->DisconnectHandlers();
        if (m_bBuilderPopoverOpen)
            m_xBuilderPopover->Popdown();
        m_xBuilderPopover.reset();
    }
    if (m_pEntry)
        m_pEntry->connect_changed(m_aOwnerEntryChangedHdl);
    else
        m_pComboBox->connect_changed(m_aOwnerComboChangedHdl);
    m_pBuilderButton->connect_clicked(m_aOwnerBuilderClickedHdl);
    m_pSearchWidget->set_tooltip_text(m_aOriginalSearchTooltip);
    m_pBuilderButton->set_tooltip_text(m_aOriginalBuilderTooltip);
    m_pBuilderButton->set_accessible_name(m_aOriginalBuilderAccessibleName);
    m_pBuilderButton->set_accessible_description(m_aOriginalBuilderAccessibleDescription);
}

OUString RegexSearchController::GetSearchText() const
{
    return m_pEntry ? m_pEntry->get_text() : m_pComboBox->get_active_text();
}

void RegexSearchController::SetSearchText(const OUString& rText)
{
    m_bProgrammaticTextUpdate = true;
    if (m_pEntry)
        m_pEntry->set_text(rText);
    else
        m_pComboBox->set_entry_text(rText);
    m_bProgrammaticTextUpdate = false;
}

void RegexSearchController::SetSearchMessageType(weld::EntryMessageType eType)
{
    if (m_pEntry)
        m_pEntry->set_message_type(eType);
    else
        m_pComboBox->set_entry_message_type(eType);
}

void RegexSearchController::NotifyOwnerChanged()
{
    if (m_pEntry)
        m_aOwnerEntryChangedHdl.Call(*m_pEntry);
    else
        m_aOwnerComboChangedHdl.Call(*m_pComboBox);
}

void RegexSearchController::NotifyStateChanged()
{
    NotifyOwnerChanged();
    m_aChangedHdl.Call(*this);
}

void RegexSearchController::SetState(const RegexSearchState& rState)
{
    m_aState = rState;
    SetSearchText(m_aState.Pattern);
    UpdateSearchValidity();
    NotifyStateChanged();
}

void RegexSearchController::SetTestText(const OUString& rTestText)
{
    m_aState.TestText = rTestText;
}

i18nutil::SearchOptions2 RegexSearchController::GetSearchOptions() const
{
    return RegexSearchService::CreateSearchOptions(m_aState);
}

RegexSearchEvaluation RegexSearchController::Evaluate(sal_Int32 nMatchLimit) const
{
    return RegexSearchService::Evaluate(m_aState, nMatchLimit);
}

void RegexSearchController::ShowBuilder()
{
    if (m_xBuilderPopover)
    {
        m_xBuilderPopover->DisconnectHandlers();
        if (m_bBuilderPopoverOpen)
            m_xBuilderPopover->Popdown();
        m_xBuilderPopover.reset();
    }

    m_xBuilderPopover = std::make_unique<RegexBuilderPopover>(m_pBuilderParent, m_aState);
    m_xBuilderPopover->SetApplyHdl(LINK(this, RegexSearchController, BuilderApplyHdl));
    m_xBuilderPopover->SetClosedHdl(LINK(this, RegexSearchController, BuilderClosedHdl));
    m_bBuilderPopoverOpen = true;
    m_xBuilderPopover->PopupAt(*m_pBuilderButton);
}

IMPL_LINK(RegexSearchController, BuilderApplyHdl, RegexBuilderPopover&, rPopover, void)
{
    m_aState = rPopover.GetState();
    SetSearchText(m_aState.Pattern);
    UpdateSearchValidity();
    rPopover.Popdown();
    NotifyStateChanged();
}

IMPL_LINK_NOARG(RegexSearchController, BuilderClosedHdl, weld::Popover&, void)
{
    m_bBuilderPopoverOpen = false;
}

void RegexSearchController::UpdateSearchValidity()
{
    if (m_aState.Pattern.getLength() > RegexSearchService::PreviewMaxPatternCodeUnits)
    {
        SetSearchMessageType(weld::EntryMessageType::Normal);
        m_pSearchWidget->set_tooltip_text(SfxResId(STR_REGEX_BUILDER_PREVIEW_SKIPPED));
        return;
    }

    const RegexSearchEvaluation aEvaluation = RegexSearchService::Validate(m_aState);
    SetSearchMessageType(aEvaluation.IsValid ? weld::EntryMessageType::Normal
                                             : weld::EntryMessageType::Error);
    m_pSearchWidget->set_tooltip_text(
        aEvaluation.IsValid
            ? m_aOriginalSearchTooltip
            : SfxResId(STR_REGEX_BUILDER_INVALID).replaceFirst(u"%1"_ustr, aEvaluation.ErrorCode));
}

IMPL_LINK(RegexSearchController, EntryChangedHdl, weld::TextWidget&, rEntry, void)
{
    if (m_bProgrammaticTextUpdate)
        return;
    m_aState.Pattern = GetSearchText();
    UpdateSearchValidity();
    m_aOwnerEntryChangedHdl.Call(rEntry);
    m_aChangedHdl.Call(*this);
}

IMPL_LINK(RegexSearchController, ComboChangedHdl, weld::ComboBox&, rComboBox, void)
{
    if (m_bProgrammaticTextUpdate)
        return;
    m_aState.Pattern = GetSearchText();
    UpdateSearchValidity();
    m_aOwnerComboChangedHdl.Call(rComboBox);
    m_aChangedHdl.Call(*this);
}

IMPL_LINK(RegexSearchController, BuilderClickedHdl, weld::Button&, rButton, void)
{
    ShowBuilder();
    m_aOwnerBuilderClickedHdl.Call(rButton);
}

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
