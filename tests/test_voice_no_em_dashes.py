# test_voice_no_em_dashes.py
"""A patient never sees an em dash. Enforced in code, not asked for in a prompt.

The style rule has been in the system prompt since the beginning and was broken
constantly. That was never really the model's fault: `chat_base.md` contains 29
em dashes and each per-cancer overlay another 10 to 46, so it is being told not
to use a mark its own instructions use throughout. A model copies the register
of its instructions far more reliably than it obeys a rule stated inside them.

And the very first question of the manual walkthrough — a plain "Hello" — came
back with one, from a HARDCODED string of ours. No model was involved at all.

So the guarantee is a deterministic pass over the text on its way out, and these
tests cover both halves: the function cannot leave one behind, and every exit
that shows a patient text actually calls it.

Offline: no LLM, no database.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "lib"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

from llm_utils import enforce_voice, enforce_voice_deep  # noqa: E402

DASHES = "—–―"


class TestNothingSurvives:

    CASES = [
        "Hi Maria — what would you like to talk through today?",
        "It is hard — but you are not alone.",
        "The results—good news—came back today.",
        "Endocrine therapy is the backbone — tamoxifen or an aromatase inhibitor.",
        "Some people notice joint aches – it usually settles.",
        "Call your team —— this is urgent.",
        "ends with a dash —",
        "— starts with one",
        "―horizontal bar―",
        "a — b – c ― d",
        "**bold — inside markdown**",
        "line one —\nline two",
    ]

    @pytest.mark.parametrize("text", CASES, ids=range(len(CASES)))
    def test_no_dash_survives(self, text):
        out, n = enforce_voice(text)
        assert n > 0
        assert not any(d in out for d in DASHES), repr(out)

    def test_clean_text_is_returned_untouched(self):
        # The common case. Rewriting text that was already fine is how a
        # cleanup pass introduces its own bugs.
        for text in ("no dashes here", "a hyphen-joined word", "5 to 10 minutes", ""):
            out, n = enforce_voice(text)
            assert out == text and n == 0

    def test_it_reports_how_many_it_removed(self):
        # Persisted per turn, so we can see how hard the model is pushing
        # against the rule rather than guessing.
        _out, n = enforce_voice("a — b — c")
        assert n == 2


class TestItDoesNotDestroyStructure:
    """The filter runs on the ANSWER, which now carries headings and lists.

    Its tidy pass used to be an unanchored `[ \\t]{2,} -> " "`, which is exactly
    the sweep that once flattened the indentation of the JSON examples in the
    prompt files. Same regex, now on patient-facing text: it only fires when the
    text contains a dash, which the model emits constantly.
    """

    def test_a_nested_bullet_keeps_its_indentation(self):
        text = "Options:\n- endocrine therapy\n    - tamoxifen — for most people\n    - an AI"
        out, _ = enforce_voice(text)
        assert "\n    - tamoxifen" in out, repr(out)
        assert "\n    - an AI" in out, repr(out)

    def test_a_dash_bulleted_sub_item_stays_a_sub_item(self):
        # The bullet rule captures the leading whitespace and puts it back.
        # Swallowing it promotes a sub-point to a top-level one.
        out, _ = enforce_voice("- top\n    — nested\n— other top")
        assert out == "- top\n    - nested\n- other top", repr(out)

    def test_a_heading_survives(self):
        out, _ = enforce_voice("## What to expect\nHot flashes — and stiffness.")
        assert out.startswith("## What to expect\n")

    def test_a_paragraph_break_is_not_collapsed(self):
        out, _ = enforce_voice("First line — here.\n\nSecond paragraph.")
        assert "\n\n" in out, repr(out)


class TestATruncatedAnswerDegradesToShorter:
    """max_tokens is a hard cut and lands wherever it lands. Under the labelled
    format that can leave a heading pointing at nothing, which reads as a broken
    card rather than a short answer."""

    def test_a_dangling_trailing_heading_is_dropped(self):
        from llm_utils import extract_followups
        out, _ = extract_followups("The answer.\n\n## What to expect\nDetails.\n\n## Cut off")
        assert out.endswith("Details.")
        assert "Cut off" not in out

    def test_a_heading_with_content_under_it_is_kept(self):
        from llm_utils import extract_followups
        text = "The answer.\n\n## When to call your team\n- Pain at night"
        out, _ = extract_followups(text)
        assert "## When to call your team" in out
        assert "- Pain at night" in out

    def test_a_real_questions_heading_is_not_eaten_as_a_lead_in(self):
        """The lead-in stripper matches any trailing line about questions to ask
        that ends in a colon. A section label has that exact shape, and deleting
        one would take its content with it."""
        from llm_utils import extract_followups
        text = ("The answer.\n\n## Questions to ask your team:\n"
                "- Is this normal?\n\nFOLLOWUPS:\n- Something else?\n")
        out, ups = extract_followups(text)
        assert "## Questions to ask your team" in out
        assert "- Is this normal?" in out
        assert ups == ["Something else?"]

    def test_a_horizontal_rule_is_removed(self):
        """The prompt forbids it and the model emits it anyway (twice in the
        first structured run). It renders as a hard black line and says nothing
        a heading does not. Asking is not enforcing."""
        from llm_utils import extract_followups
        out, _ = extract_followups("The answer.\n\n---\n\n## Next\nMore text.")
        assert "---" not in out
        assert "## Next" in out and "More text." in out

    def test_a_prose_lead_in_is_still_stripped(self):
        from llm_utils import extract_followups
        text = ("The answer.\n\nHere are some questions you might explore next:\n"
                "\nFOLLOWUPS:\n- What now?\n")
        out, ups = extract_followups(text)
        assert "explore next" not in out
        assert ups == ["What now?"]


class TestTheChatDepthLevelsAreTheirOwn:
    """`standard` and `deep` used to fall through into `normal` and `detailed`.

    That was fine while the shapes matched and a trap the moment they must not:
    brief/normal/detailed are frozen for five non-chat callers, four of which
    parse JSON back or assert a minimum length, so a smaller budget fails hard
    rather than shortening.
    """

    def test_standard_and_deep_resolve_on_their_own(self):
        from llm_utils import get_response_settings
        for level in ("guided", "standard", "deep"):
            s = get_response_settings(level)
            assert s["max_tokens"] > 0 and s["system_message"]

    def test_the_frozen_levels_are_untouched(self):
        from llm_utils import get_response_settings
        frozen = {
            "brief": (150, 200, False),
            "normal": (250, 400, True),
            "detailed": (400, 600, True),
        }
        for level, (plain, boosted, resources) in frozen.items():
            assert get_response_settings(level)["max_tokens"] == plain, level
            assert get_response_settings(level, query_type="treatment")["max_tokens"] == boosted, level
            assert get_response_settings(level)["include_resources"] is resources, level

    def test_an_unknown_level_still_falls_back_to_normal(self):
        from llm_utils import get_response_settings
        assert get_response_settings("nonsense")["max_tokens"] == \
            get_response_settings("normal")["max_tokens"]


class TestTheReplacementReadsCorrectly:
    """A filter that leaves mangled English is worse than the em dash. The
    cautionary tale is next door: soften_tone rewrites "you should" with no
    clause awareness, so "you shouldn't" becomes "it might help ton't"."""

    def test_a_parenthetical_becomes_commas(self):
        assert enforce_voice("The results—good news—came back.")[0] == \
            "The results, good news, came back."

    def test_an_aside_becomes_one_comma(self):
        assert enforce_voice("It is hard — but you are not alone.")[0] == \
            "It is hard, but you are not alone."

    def test_a_number_range_becomes_to(self):
        # "cycles 2, 3" would say something different from "cycles 2 to 3".
        assert enforce_voice("Take it for cycles 2—3.")[0] == "Take it for cycles 2 to 3."
        assert enforce_voice("5–10 minutes")[0] == "5 to 10 minutes"

    def test_a_line_leading_dash_becomes_a_bullet(self):
        # A comma at the start of a line would be nonsense.
        assert enforce_voice("— first\n— second")[0] == "- first\n- second"

    def test_it_never_leaves_a_doubled_or_orphan_comma(self):
        for text in ("a —, b", "a, — b", "hard — .", "x — ; y"):
            out, _ = enforce_voice(text)
            assert ",," not in out
            assert " ," not in out
            assert ", ." not in out and ", ;" not in out

    def test_it_never_leaves_a_double_space(self):
        assert "  " not in enforce_voice("a  —  b")[0]


class TestNestedPayloads:
    """Pre-visit, visit recap, appeal and deep research each return a dict of
    sections. Cleaning them field by field means the next field someone adds is
    missed."""

    def test_it_walks_dicts_and_lists(self):
        payload = {
            "title": "Your visit — a summary",
            "sections": [
                {"heading": "What was said", "body": "The scan was clear — good news."},
                {"heading": "Next", "body": ["Call — soon", "Rest"]},
            ],
            "count": 3,
            "ok": True,
            "nothing": None,
        }
        out = enforce_voice_deep(payload)
        blob = str(out)
        assert not any(d in blob for d in DASHES)
        # Shape and non-string values are untouched.
        assert out["count"] == 3 and out["ok"] is True and out["nothing"] is None
        assert len(out["sections"]) == 2
        assert out["sections"][1]["body"][1] == "Rest"

    def test_keys_are_left_alone(self):
        # Keys are field names the client reads, not prose. Rewriting one
        # silently breaks the contract with the app.
        out = enforce_voice_deep({"a—b": "text — here"})
        assert "a—b" in out


class TestOurOwnCannedStringsAreClean:
    """The walkthrough's question 1 is the greeting short-circuit: no model
    runs at all. An em dash there is ours, and it shipped."""

    def test_the_greeting_has_none(self):
        from llm_utils import greeting_response
        for name in ("Maria", ""):
            assert not any(d in greeting_response(name) for d in DASHES)

    def test_the_off_topic_refusal_has_none(self):
        # Chat no longer refuses off-topic (gate inversion 2026-08-24), but
        # deep research still renders this copy, so it stays pinned clean.
        from confidence import render_off_topic_response
        for slug in ("breast", "colorectal", None):
            assert not any(d in render_off_topic_response(slug) for d in DASHES)

    def test_the_wall_copy_has_none(self):
        """Wall responses skip enforce_voice on the canned path (like the
        crisis cards), so the copy itself must be clean by construction."""
        from walls import (WALL_LIMIT_SENTENCES, WALL_TYPES,
                           render_prognosis_wall_response, wall_prompt_block)
        assert not any(d in render_prognosis_wall_response() for d in DASHES)
        for wall_type in WALL_TYPES:
            assert not any(d in WALL_LIMIT_SENTENCES[wall_type] for d in DASHES)
            assert not any(d in wall_prompt_block(wall_type) for d in DASHES)

    def test_the_crisis_responses_have_none(self):
        from confidence import render_crisis_response
        for cat in ("self_harm", "medical_emergency", "urgent_oncology"):
            assert not any(d in render_crisis_response(cat) for d in DASHES)

    def test_the_hedged_fallback_has_none(self):
        from verify import HEDGED_FALLBACK_RESPONSE
        assert not any(d in HEDGED_FALLBACK_RESPONSE for d in DASHES)

    def test_the_soft_disclaimer_is_gone_from_the_answer(self):
        """It prepended "Note: some details below should be verified with your
        care team" whenever the verifier was unsure. That duplicated the
        always-visible session banner and was vaguer than it: which details?
        A patient cannot act on it, so it read as alarm."""
        api = (_REPO / "api" / "index.py").read_text()
        assert "SOFT_DISCLAIMER_PREFIX" not in api

    def test_the_verifier_verdict_is_still_recorded(self):
        # Removing the text must not lose the signal: it is how we tell, in an
        # exported run, which answers the fact-checker doubted.
        api = (_REPO / "api" / "index.py").read_text()
        assert '"debug_info": response_data.get("debug_info")' in api

    def test_the_attorney_reviewed_footer_is_untouched(self):
        # shared/disclaimers.ts is verbatim-required copy. The redundant one
        # that went was engineering copy in verify.py; this one is not ours to
        # edit.
        d = (_REPO / "shared" / "disclaimers.ts").read_text()
        assert "Informational only. Verify with your oncologist." in d
        card = (_REPO / "mobile" / "components" / "chat" / "BotResponseCard.tsx").read_text()
        assert "PER_MESSAGE_FOOTER" in card

    def test_the_glossary_fallback_has_none(self):
        from llm_utils import GLOSSARY_FALLBACK
        assert not any(d in GLOSSARY_FALLBACK for d in DASHES)


class TestEveryPatientFacingExitIsWired:
    """A filter nobody calls is decoration. These assert the wiring, because a
    new surface added later is exactly how this reopens."""

    API = (_REPO / "api" / "index.py").read_text()

    def test_the_chat_answer_goes_through_it(self):
        assert "final_answer, _dashes = enforce_voice(final_answer)" in self.API

    def test_it_runs_after_the_tone_softener(self):
        # soften_tone can introduce text; running before it would miss that.
        assert self.API.index("soften_tone(final_answer)") < \
            self.API.index("enforce_voice(final_answer)")

    def test_the_reviewer_sandbox_chat_goes_through_it(self):
        assert "answer, _ = enforce_voice(answer)" in self.API

    @pytest.mark.parametrize("generator", [
        "generate_previsit_questions",
        "generate_visit_recap",
        "generate_insurance_appeal",
        "generate_deep_research",
    ])
    def test_every_structured_generator_is_wrapped(self, generator):
        assert f"enforce_voice_deep({generator}(" in self.API, (
            f"{generator} output reaches a patient unfiltered")

    def test_the_glossary_is_wired(self):
        src = (_REPO / "lib" / "llm_utils.py").read_text()
        assert "enforce_voice(answer)[0]" in src

    def test_the_eval_harness_sees_what_the_patient_sees(self):
        # Otherwise the metrics score text nobody is served.
        harness = (_REPO / "scripts" / "eval" / "run_evals.py").read_text()
        assert "enforce_voice(answer)" in harness

    def test_it_is_not_applied_inside_call_llm(self):
        """The one place it must NOT go.

        The extractor, verifier and modeler all call call_llm and parse JSON
        back. Rewriting punctuation inside a JSON string would corrupt them,
        and the failure would look like a model problem.
        """
        src = (_REPO / "lib" / "llm_utils.py").read_text()
        start = src.index("def call_llm(")
        end = src.index("\ndef ", start + 10)
        assert "enforce_voice" not in src[start:end]


class TestTheAnswerDoesNotPromiseWhatTheScreenHides:
    """The model writes a lead-in before its FOLLOWUPS: block — "Here are some
    questions you might explore next:". The block is stripped and rendered as
    chips, but the lead-in survived, so the answer ended by promising a list and
    then showed nothing. Reported from a device."""

    def test_the_lead_in_goes_with_the_block(self):
        from llm_utils import extract_followups
        out, ups = extract_followups(
            "Some advice here.\n\nHere are some questions you might explore next:"
            # Was "What does HR mean?"; the chip-jargon filter now drops
            # acronyms, and this test is about the LEAD-IN, not the chips.
            "\n\nFOLLOWUPS:\n- What helps with tiredness?\n- How do I manage side effects?")
        assert out == "Some advice here."
        assert len(ups) == 2

    def test_other_phrasings_too(self):
        # The old rule matched one exact sentence; this matches the shape.
        from llm_utils import extract_followups
        for lead in ("You may want to consider these questions next:",
                     "Here are a few things to ask about next:",
                     "Some questions to explore:"):
            out, _ = extract_followups(f"Advice.\n\n{lead}\n\nFOLLOWUPS:\n- One?")
            assert out == "Advice.", f"{lead!r} left behind: {out!r}"

    def test_a_genuine_list_is_left_alone(self):
        # Over-eager stripping would eat real content.
        from llm_utils import extract_followups
        text = "Ends with a real list:\nThings to bring:\n- notes\n- a friend"
        out, ups = extract_followups(text)
        assert out == text and ups == []

    def test_an_answer_with_no_block_is_untouched(self):
        from llm_utils import extract_followups
        text = "A normal answer that mentions questions for your doctor."
        out, ups = extract_followups(text)
        assert out == text and ups == []


def _strip_js_comments(source: str) -> str:
    """Source with // and /* */ removed, so an assertion reads the code only.

    These files explain in prose why a prop is absent, and a bare substring
    check would find the explanation and call it the bug.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


class TestTheChatCardShowsWhatItPromises:
    """Four things reported from a real device on one screenshot."""

    CARD = (_REPO / "mobile" / "components" / "chat" / "BotResponseCard.tsx").read_text()
    RESOURCES = (_REPO / "mobile" / "components" / "chat" / "ResourcesRow.tsx").read_text()
    MARKDOWN = (_REPO / "mobile" / "components" / "chat" / "MarkdownText.tsx").read_text()
    BUBBLE = (_REPO / "mobile" / "components" / "chat" / "MessageBubble.tsx").read_text()

    def test_followups_render_outside_the_card_entirely(self):
        """Two moves. First out of "Show details" (below the fold, after two
        other sections, while the answer announced them). Then out of the CARD:
        they read on the whole thread rather than one answer, and at card width
        they were clipped mid-question ("...HER2 status mea...")."""
        # Home and /chat/:id share one surface now (redesign change 3).
        thread = (_REPO / "mobile" / "components" / "chat" / "ConversationSurface.tsx").read_text()
        assert "FollowupChips" in thread
        assert "FollowupChips" not in self.CARD

    def test_the_questions_are_not_truncated(self):
        chips = (_REPO / "mobile" / "components" / "chat" / "FollowupChips.tsx").read_text()
        assert "numberOfLines" not in chips

    def test_only_one_thing_on_the_card_is_called_sources(self):
        # ResourcesRow said SOURCES and SourceCitations said "N sources", so one
        # answer showed two different counts of two different things.
        assert "WHERE TO GET HELP" in self.RESOURCES
        assert ">SOURCES<" not in self.RESOURCES

    def test_sources_moved_out_of_every_message(self):
        """They hung off each answer behind "Show details", which put a research
        artifact in the middle of a conversation about someone's own cancer, on
        every message. And it answered the wrong question: nobody asks what
        backed sentence four, they ask what the thing is built on."""
        assert "SourceCitations" not in self.CARD
        chat_input = (_REPO / "mobile" / "components" / "chat" / "ChatInput.tsx").read_text()
        assert "Sources used" in chat_input, "not reachable from the + menu"

    def test_the_sources_sheet_keeps_the_link_to_each_question(self):
        # Grouping by answer without the question loses which is which.
        sheet = (_REPO / "mobile" / "components" / "chat" / "SourcesSheet.tsx").read_text()
        assert "groupByQuestion" in sheet
        assert "role === 'user'" in sheet

    def test_the_summary_line_still_names_what_is_hidden(self):
        assert "to get help" in self.CARD

    def test_thumbs_and_copy_are_not_on_the_reading_surface(self):
        # They live in the select-text sheet now, not under every answer.
        assert "MessageActions" not in self.CARD

    def test_rn_selectable_is_not_used_anywhere_in_chat(self):
        """It cannot do what it looks like it does, and it breaks what does.

        RCTParagraphComponentView implements `selectable` as a long-press
        recognizer plus an edit menu whose copy: takes NSMakeRange(0, length) —
        the whole node. There is no partial selection at any nesting level, so
        two shipped attempts at moving the prop between the markdown `text` and
        `textgroup` rules could never have worked. It also installs a NATIVE
        gesture recognizer that competes with the JS long press that opens the
        sheet, so leaving it behind would make the sheet fire intermittently.
        """
        # Comments in these files explain WHY it is gone, so assert against the
        # code with the prose stripped out.
        for source in (self.MARKDOWN, self.BUBBLE):
            code = _strip_js_comments(source)
            assert not re.search(r"\bselectable\b", code)
        assert "selectableRules" not in _strip_js_comments(self.MARKDOWN)

    def test_both_sides_of_the_conversation_reach_the_select_sheet(self):
        assert "onSelectText" in self.CARD and "onLongPress" in self.CARD
        assert "onSelectText" in self.BUBBLE and "onLongPress" in self.BUBBLE

    def test_the_sheet_selects_with_a_real_uitextview(self):
        """editable={false} on a multiline TextInput is the entire mechanism.

        RCTTextInputComponentView sets only `.editable`, so the backing
        RCTUITextView (a UITextView) keeps isSelectable — which is drag
        selection, grab handles, and the system Copy/Share/Look Up menu.
        """
        sheet = (_REPO / "mobile" / "components" / "chat" / "SelectTextSheet.tsx").read_text()
        assert "TextInput" in sheet
        assert "editable={false}" in sheet
        assert "multiline" in sheet

    def test_the_phone_does_not_reintroduce_em_dashes(self):
        """markdown-it's typographer rewrites "--" as an en dash and "---" as an
        em dash. It runs on the phone, AFTER enforce_voice cleaned the answer on
        the server, so the guarantee had a hole in it on the surface that
        matters most."""
        assert "typographer: false" in self.MARKDOWN


class TestTheCorpusIsNotRedownloadedEveryTurn:
    """Measured on production: a warm chat turn took ~13s, of which ~9s was
    re-downloading all 9,138 guideline chunks over ten sequential database
    requests. The corpus is static between manual re-ingests. The model call was
    about 2s of the 13."""

    STORAGE = (_REPO / "lib" / "supabase_storage.py").read_text()
    API = (_REPO / "api" / "index.py").read_text()

    def test_there_is_a_cache_with_a_bounded_lifetime(self):
        # Forever would mean a re-ingest needs a redeploy to be seen.
        assert "_CHUNK_CACHE" in self.STORAGE
        assert "_CHUNK_CACHE_TTL_SECONDS" in self.STORAGE

    def test_a_cold_burst_only_downloads_once(self):
        # Without the lock, every request arriving at a cold container starts
        # its own 9-second download.
        assert "_chunk_cache_lock" in self.STORAGE
        assert "with _chunk_cache_lock:" in self.STORAGE

    def test_callers_get_copies_not_the_cached_dicts(self):
        """The subtle one. hybrid_search writes `_similarity` onto the chunk
        dicts it scores, so handing out the cached objects would let one
        query's scores leak into the next query's confidence calculation."""
        assert "[dict(c) for c in cached]" in self.STORAGE

    def test_the_mutation_isolation_actually_holds(self):
        from supabase_storage import _CHUNK_CACHE, load_all_chunks
        _CHUNK_CACHE["rows"] = [{"content": "x", "filename": "f.pdf"}]
        import time as _t
        _CHUNK_CACHE["loaded_at"] = _t.time()
        first = load_all_chunks()
        first[0]["_similarity"] = 0.99
        assert "_similarity" not in load_all_chunks()[0]
        _CHUNK_CACHE["rows"] = None

    def test_there_is_a_warm_endpoint(self):
        assert '@app.route("/api/warm"' in self.API

    def test_warming_never_surfaces_a_failure(self):
        # It is an optimisation. Someone opening a chat must not see it fail.
        warm = self.API.split('def api_warm():')[1].split('\n@app.route')[0]
        assert 'return jsonify({"status": "ok", "warmed": False}), 200' in warm

    def test_warming_returns_no_patient_data(self):
        # Assert on what it RETURNS, not on the prose around it: the first
        # version of this test failed on the word "patient" in the docstring
        # explaining that it returns no patient data.
        import re as _re
        warm = self.API.split('def api_warm():')[1].split('\n@app.route')[0]
        returned = " ".join(_re.findall(r"jsonify\((.*?)\)", warm, _re.DOTALL))
        for leak in ("raw_profile", "patient_profiles", "message", "answer",
                     "user_id", "profile"):
            assert leak not in returned, f"{leak} in the warm response"

    def test_the_app_warms_when_a_chat_opens_or_a_greeting_lands(self):
        hook = (_REPO / "mobile" / "hooks" / "useChat.ts").read_text()
        assert "warmUp()" in hook
        assert "greeting-shortcircuit" in hook

    def test_the_client_call_cannot_throw(self):
        chat = (_REPO / "mobile" / "lib" / "api" / "chat.ts").read_text()
        block = chat.split("export function warmUp()")[1]
        assert ".catch(() => {})" in block


class TestChipsNeverSpeakJargon:
    """A follow-up chip is Sage OFFERING a question, not the patient asking
    one, so rule 2 of the trajectory brief applies at its strictest:
    "Adapt up, never lead up... Acronyms never appear in titles, buttons, or
    push notifications."

    Reported from a real screenshot: a patient who had never typed the word
    was offered "How does my HER2 status affect my treatment options?"
    """

    def test_the_reported_chip_is_dropped(self):
        from llm_utils import extract_followups
        body = ("Fatigue is common.\n\nFOLLOWUPS:\n"
                "- How does my HER2 status affect my treatment options?\n"
                "- What are some ways to manage stress during treatment?\n")
        _clean, ups = extract_followups(body)
        assert all('HER2' not in u for u in ups)
        assert ups == ['What are some ways to manage stress during treatment?']

    def test_markers_scales_and_scans_are_all_dropped(self):
        from llm_utils import _chip_is_plain
        for q in [
            'What does my MSI result mean?',
            'What are my PD-L1 levels?',
            'What is my ECOG score?',
            'Should I have a BRCA test?',
            'What will the MRI show?',
            'What are the biomarker results?',
        ]:
            assert _chip_is_plain(q) is False, q

    def test_plain_questions_survive(self):
        from llm_utils import _chip_is_plain
        for q in [
            'What are some ways to manage stress during treatment?',
            'Are there lifestyle changes to boost my energy?',
            'How will we know if the treatment is working?',
            'Can I still work during treatment?',
            "I'm worried about money, what help is there?",
        ]:
            assert _chip_is_plain(q) is True, q

    def test_stage_numerals_are_not_acronyms(self):
        """"Stage IV" is how staging is written on the patient's own
        paperwork. Dropping it would be over-correction."""
        from llm_utils import _chip_is_plain
        assert _chip_is_plain('What does stage IV mean for me?') is True
        assert _chip_is_plain('Is stage III different from stage II?') is True

    def test_dropping_never_empties_the_answer(self):
        """The chips are optional; the ANSWER must survive losing all of them."""
        from llm_utils import extract_followups
        body = "The answer text.\n\nFOLLOWUPS:\n- What is my HER2 status?\n- What is my ECOG score?\n"
        clean, ups = extract_followups(body)
        assert ups == []
        assert clean.strip() == 'The answer text.'
