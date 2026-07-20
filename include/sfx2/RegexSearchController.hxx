/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; c-basic-offset: 4; fill-column: 100 -*- */
/*
 * This file is part of the LibreOffice project.
 *
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/.
 */

#pragma once

#include <sfx2/dllapi.h>

#include <i18nutil/searchopt.hxx>
#include <rtl/ustring.hxx>
#include <tools/link.hxx>

#include <memory>
#include <vector>

namespace weld
{
enum class EntryMessageType;
class Button;
class ComboBox;
class Entry;
class TextWidget;
class Widget;
class Popover;
}

namespace sfx2
{
class RegexBuilderPopover;

enum class RegexSearchMode
{
    Literal,
    RegularExpression
};

/** User-visible flags shared by every search surface.

    Case-insensitive search maps to the i18nutil transliteration flag (and therefore ICU's i mode
    for regular expressions). Global controls whether Evaluate() returns all matches or stops after
    the first. Multiline and dot-matches-newline map to ICU's m and s modes and are ignored for
    literal search.
 */
struct SFX2_DLLPUBLIC RegexSearchFlags
{
    bool CaseInsensitive = true;
    bool Global = true;
    bool Multiline = false;
    bool DotMatchesNewline = false;
};

struct SFX2_DLLPUBLIC RegexSearchState
{
    OUString Pattern;
    OUString TestText;
    RegexSearchMode Mode = RegexSearchMode::Literal;
    RegexSearchFlags Flags;
};

struct SFX2_DLLPUBLIC RegexMatch
{
    sal_Int32 Start = 0;
    sal_Int32 End = 0;
};

struct SFX2_DLLPUBLIC RegexSearchEvaluation
{
    bool IsValid = true;
    OUString ErrorCode;
    sal_Int32 ErrorOffset = -1;
    std::vector<RegexMatch> Matches;
    bool Truncated = false;
    bool InputTruncated = false;
    bool BudgetExceeded = false;
    bool PreviewSkipped = false;
};

/** ICU-backed search service used by RegexSearchController and non-widget consumers.

    This deliberately routes actual searching through utl::TextSearch/SearchOptions2 instead of
    std::regex, so consumers get the same Unicode and regular-expression semantics as LibreOffice's
    document search implementation.
 */
class SFX2_DLLPUBLIC RegexSearchService final
{
public:
    /** Hard limits for the builder's live preview.

        These limits apply only to the builder's live UI and EvaluatePreview(), never to
        CreateSearchOptions() or Evaluate(). Pattern and text lengths are UTF-16 code units. The ICU
        time limit is measured in match engine steps; the deadline is a second wall-clock guard.
        Preview input is clipped without splitting a surrogate pair. A pattern over the pattern
        limit is neither synchronously validated nor truncated nor executed by the live UI.
     */
    static constexpr sal_Int32 PreviewMaxPatternCodeUnits = 1024;
    static constexpr sal_Int32 PreviewMaxTextCodeUnits = 16384;
    static constexpr sal_Int32 PreviewMaxMatches = 256;
    static constexpr sal_Int32 PreviewProcessingStepLimit = 2000;
    static constexpr sal_Int32 PreviewStackLimitBytes = 1024 * 1024;
    static constexpr sal_Int32 PreviewDeadlineMilliseconds = 100;

    static OUString GetEffectivePattern(const RegexSearchState& rState);
    static i18nutil::SearchOptions2 CreateSearchOptions(const RegexSearchState& rState);
    static RegexSearchEvaluation Validate(const RegexSearchState& rState);

    /** Evaluate a bounded, disposable live preview.

        Regular-expression preview uses ICU directly with UREGEX_UWORD, LibreOffice's legacy
        \\< / \\> word-boundary expansion, and the same i/m/s flag mapping as CreateSearchOptions().
        It intentionally clips test text and may therefore differ at the clip boundary. Actual
        consumer searches must use Evaluate() or CreateSearchOptions(); neither uses preview limits.
     */
    static RegexSearchEvaluation EvaluatePreview(const RegexSearchState& rState);

    static RegexSearchEvaluation Evaluate(const RegexSearchState& rState,
                                          sal_Int32 nMatchLimit = 1000);
};

/** Binds a text entry or editable combo box to an adjacent advanced-builder button.

    Consumers install their filtering callback with SetChangedHdl() and use GetSearchOptions() or
    Evaluate(). The controller owns neither widget; it must be destroyed before the widgets.

    weld widgets expose a single changed/clicked callback. To preserve an existing widget owner,
    pass its exact TextWidget or ComboBox callback to the matching constructor: the controller
    forwards events to it and restores it when destroyed. The ComboBox overload requires
    has_entry() and uses get_active_text(), set_entry_text(), and set_entry_message_type(); it never
    coerces the combo box to Entry. Install no other direct changed/clicked callback on these widgets
    while the controller is alive; route later integration through SetChangedHdl() or the owner
    callbacks.
 */
class SFX2_DLLPUBLIC RegexSearchController final
{
    weld::Widget* m_pBuilderParent;
    weld::Widget* m_pSearchWidget;
    weld::Entry* m_pEntry = nullptr;
    weld::ComboBox* m_pComboBox = nullptr;
    weld::Button* m_pBuilderButton;
    OUString m_aOriginalSearchTooltip;
    OUString m_aOriginalBuilderTooltip;
    OUString m_aOriginalBuilderAccessibleName;
    OUString m_aOriginalBuilderAccessibleDescription;
    RegexSearchState m_aState;
    std::unique_ptr<RegexBuilderPopover> m_xBuilderPopover;
    bool m_bBuilderPopoverOpen = false;
    bool m_bProgrammaticTextUpdate = false;
    Link<weld::TextWidget&, void> m_aOwnerEntryChangedHdl;
    Link<weld::ComboBox&, void> m_aOwnerComboChangedHdl;
    Link<weld::Button&, void> m_aOwnerBuilderClickedHdl;
    Link<RegexSearchController&, void> m_aChangedHdl;

    void Initialize();
    OUString GetSearchText() const;
    void SetSearchText(const OUString& rText);
    void SetSearchMessageType(weld::EntryMessageType eType);
    void NotifyOwnerChanged();
    void NotifyStateChanged();
    void UpdateSearchValidity();

    DECL_LINK(EntryChangedHdl, weld::TextWidget&, void);
    DECL_LINK(ComboChangedHdl, weld::ComboBox&, void);
    DECL_LINK(BuilderClickedHdl, weld::Button&, void);
    DECL_LINK(BuilderApplyHdl, RegexBuilderPopover&, void);
    DECL_LINK(BuilderClosedHdl, weld::Popover&, void);

public:
    RegexSearchController(weld::Widget* pParent, weld::Entry& rEntry, weld::Button& rBuilderButton,
                          const Link<weld::TextWidget&, void>& rOwnerEntryChangedHdl
                          = Link<weld::TextWidget&, void>(),
                          const Link<weld::Button&, void>& rOwnerBuilderClickedHdl
                          = Link<weld::Button&, void>());
    RegexSearchController(weld::Widget* pParent, weld::ComboBox& rComboBox,
                          weld::Button& rBuilderButton,
                          const Link<weld::ComboBox&, void>& rOwnerComboChangedHdl
                          = Link<weld::ComboBox&, void>(),
                          const Link<weld::Button&, void>& rOwnerBuilderClickedHdl
                          = Link<weld::Button&, void>());
    ~RegexSearchController();

    RegexSearchController(const RegexSearchController&) = delete;
    RegexSearchController& operator=(const RegexSearchController&) = delete;

    void SetChangedHdl(const Link<RegexSearchController&, void>& rLink) { m_aChangedHdl = rLink; }

    const RegexSearchState& GetState() const { return m_aState; }
    void SetState(const RegexSearchState& rState);
    void SetTestText(const OUString& rTestText);

    i18nutil::SearchOptions2 GetSearchOptions() const;
    RegexSearchEvaluation Evaluate(sal_Int32 nMatchLimit = 1000) const;
    void ShowBuilder();
};

} // namespace sfx2

/* vim:set shiftwidth=4 softtabstop=4 expandtab: */
