# test_cancer_overlay_threading.py
"""The patient's cancer has to reach the MODEL, not just the retrieval filter.

`/api/chat` worked out the patient's cancer and used it to pick which guideline
chunks to search — then called the model without it. `call_llm` does not fail on
a missing `cancer_slug`; it falls back to colorectal. So every breast, lung, NHL,
prostate and pancreatic patient read their own guidelines while being instructed
to think in FOLFOX / KRAS / colonoscopy / Lynch terms.

Three things made it survive:

  1. **It cannot fail loudly.** The fallback is a designed behaviour used by
     legitimate callers, so a dropped argument is indistinguishable from a
     deliberate one at the call site.
  2. **No test score could move.** `scripts/eval/run_evals.py` has always passed
     `cancer_slug=cancer`, so the breast suite scored 7/7 at 100% while
     production was wrong. The bug existed ONLY in the app.
  3. **The comment said it was fixed.** `api/index.py` still reads "Threaded
     through retrieval (chunk filter) + LLM generators (overlay)".

So the load-bearing test here is not any single call site — it is the AST guard,
which fails on the NEXT `call_llm` someone adds without the argument.

Offline: no LLM, no database.
"""

import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))
sys.path.insert(0, str(_REPO / "api"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

import index  # noqa: E402
from prompts import assemble_system_prompt  # noqa: E402

TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000042"}
AUTH = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}

# Every file that is allowed to call call_llm.
CALLER_FILES = [_REPO / "api" / "index.py", _REPO / "lib" / "llm_utils.py"]


def call_llm_calls(path: Path):
    """Every `call_llm(...)` invocation in a file, as (lineno, keyword names)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        if name != "call_llm":
            continue
        out.append((node.lineno, {kw.arg for kw in node.keywords if kw.arg}))
    return out


class TestEveryModelCallCarriesTheCancer:
    """The guard. Not "is this one call site right" but "can this reopen"."""

    @pytest.mark.parametrize("path", CALLER_FILES, ids=lambda p: p.name)
    def test_no_call_llm_omits_cancer_slug(self, path):
        offenders = [line for line, kwargs in call_llm_calls(path)
                     if "cancer_slug" not in kwargs]
        assert not offenders, (
            f"{path.name}: call_llm without cancer_slug at line(s) {offenders}. "
            "It will silently use the colorectal overlay for every patient.")

    def test_the_guard_actually_finds_call_sites(self):
        # A guard that matches nothing passes forever. Two files, several calls.
        total = sum(len(call_llm_calls(p)) for p in CALLER_FILES)
        assert total >= 6, f"only found {total} call_llm calls — the AST walk broke"

    def test_the_eval_harness_passes_it_too(self):
        # This is why no score ever moved: the harness was always correct and
        # only production was wrong. If this regresses, the baseline stops
        # meaning anything.
        harness = _REPO / "scripts" / "eval" / "run_evals.py"
        assert all("cancer_slug" in kwargs for _line, kwargs in call_llm_calls(harness))


class TestTheOverlayIsActuallyDifferent:
    """If breast and colorectal produced the same system prompt, threading the
    slug would be a no-op and the whole fix would be theatre."""

    BREAST = assemble_system_prompt("breast")
    COLORECTAL = assemble_system_prompt("colorectal")

    def test_they_are_not_the_same_prompt(self):
        assert self.BREAST != self.COLORECTAL

    @pytest.mark.parametrize(
        "term", ["FOLFOX", "FOLFIRI", "colonoscopy", "Lynch", "KRAS", "oxaliplatin"])
    def test_no_colorectal_clinical_framing_in_the_breast_overlay(self, term):
        """Asserted on the OVERLAY, not the assembled prompt.

        `chat_base.md` is shared by every cancer and uses FOLFOX twice as a
        FORMATTING example ("for simple single-topic answers, e.g. 'what is
        FOLFOX'" and a citation-format sample). Those are illustrative, not
        clinical instruction, and rewriting them is a prompt change with its own
        eval window — deliberately not in this fix. What must be clean is the
        clinical framing the overlay supplies.
        """
        from cancer_registry import load_overlay_md
        overlay = (load_overlay_md("breast") or "").lower()
        assert overlay, "breast overlay is missing"
        assert term.lower() not in overlay, (
            f"'{term}' is in the BREAST clinical overlay")

    def test_the_colorectal_overlay_is_where_that_vocabulary_belongs(self):
        # Proves the assertion above is measuring something: the same terms are
        # densely present one directory over.
        from cancer_registry import load_overlay_md
        crc = (load_overlay_md("colorectal") or "").lower()
        assert all(t in crc for t in ("folfox", "colonoscopy", "lynch", "kras"))

    def test_the_breast_prompt_is_about_breast_cancer(self):
        lowered = self.BREAST.lower()
        assert "breast" in lowered
        # The things a breast overlay must actually carry to be worth threading.
        assert any(t in lowered for t in ("her2", "endocrine", "aromatase"))

    def test_an_unknown_slug_still_returns_a_usable_prompt(self):
        # Fail soft: a bad slug must not produce an empty system prompt.
        assert len(assemble_system_prompt("not-a-cancer")) > 500


class TestTheRouteSendsTheRightCancer:
    """End of the wire: a breast patient's request reaches call_llm as breast."""

    @pytest.fixture()
    def client(self):
        index.app.config["TESTING"] = True
        with index.app.test_client() as c:
            yield c

    def _post(self, client, message="What does HR positive mean for treatment?"):
        return client.post("/api/chat", data=json.dumps({"message": message}),
                           headers=AUTH)

    def test_a_breast_patient_reaches_the_model_as_breast(self, client):
        seen = {}

        def fake_call_llm(prompt, response_length="normal", **kwargs):
            seen.update(kwargs)
            return ("A breast cancer answer about endocrine therapy.", "together")

        profile = {"patient": {"firstName": "Maria"},
                   "primaryDiagnosis": {"site": "Breast", "stage": "IIB"}}

        with patch.object(index, "verify_token", return_value=TEST_USER), \
             patch("rate_limit.check_rate_limit", return_value=(True, 99)), \
             patch.object(index, "get_consent_status", return_value={"chat_disabled": False}), \
             patch.object(index, "load_all_chunks", return_value=[]), \
             patch.object(index, "get_conversation_history_by_id", return_value=[]), \
             patch.object(index, "hybrid_search", return_value=[]), \
             patch.object(index, "load_profile", return_value=profile), \
             patch.object(index, "_resolve_cancer_slug", return_value="breast"), \
             patch.object(index, "call_llm", side_effect=fake_call_llm), \
             patch("supabase_storage.get_account_basics", return_value={"perspective": "self"}):
            resp = self._post(client)

        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        assert seen.get("cancer_slug") == "breast", (
            f"call_llm received cancer_slug={seen.get('cancer_slug')!r}; "
            "None means the colorectal overlay")


class TestAskingAboutSomeoneElsesCancer:
    """`mismatch_detected` appends a system note telling the model the patient
    asked about a different cancer. It compared a hardcoded 'breast cancer'
    against profile_utils' "<site> <histology>" string, so it was correct only
    while histology was UNKNOWN. Once the chat learned it, "Breast invasive
    ductal carcinoma" no longer contained "breast cancer" — and a breast patient
    asking about breast cancer got the note. Late, silent, and only for profiles
    that were filling in, which is every real one."""

    def test_their_own_cancer_is_never_a_mismatch(self):
        assert index._mentions_other_cancer("is breast cancer hereditary?", "breast") is False

    def test_it_survives_the_histology_landing(self):
        # The regression that made this urgent: the check must not depend on
        # how the profile happens to render the diagnosis.
        for phrasing in ("breast cancer", "breast carcinoma", "mammary carcinoma"):
            assert index._mentions_other_cancer(f"tell me about {phrasing}", "breast") is False

    def test_a_genuinely_different_cancer_is_flagged(self):
        assert index._mentions_other_cancer("what about colon cancer?", "breast") is True
        assert index._mentions_other_cancer("tell me about bladder cancer", "kidney") is True

    def test_cancers_the_old_list_forgot(self):
        # The hardcoded list had no bladder, kidney, uterine or NHL.
        assert index._mentions_other_cancer("is DLBCL treated the same way?", "breast") is True
        assert index._mentions_other_cancer("what about endometrial cancer?", "breast") is True

    def test_naming_both_is_one_question_not_a_wrong_turn(self):
        assert index._mentions_other_cancer(
            "my sister has colon cancer, does that change my breast cancer risk?",
            "breast") is False

    def test_no_cancer_named_is_never_a_mismatch(self):
        # Deliberately NOT cancer_registry.resolve_slug, which falls back to
        # colorectal — every ordinary question would read as a mismatch for
        # every non-colorectal patient.
        for msg in ("what should I eat during chemo?", "I feel tired", "hello"):
            assert index._mentions_other_cancer(msg, "breast") is False

    def test_short_aliases_do_not_match_inside_words(self):
        # The alias list holds 'UC', 'CLL', 'RCC', 'SLL', 'PDAC'. Without word
        # boundaries 'uc' matches 'mucosal', 'much' and 'nucleus'.
        for msg in ("I have much mucosal irritation", "the nucleus of the problem",
                    "such a rough week"):
            assert index._mentions_other_cancer(msg, "breast") is False

    def test_a_patient_with_no_cancer_set_is_never_flagged(self):
        assert index._mentions_other_cancer("colon cancer", None) is False


class TestResourcesFollowThePatientsCancer:
    """config/cancers/<slug>/resources.yaml existed for all 10 cancers since the
    multi-cancer rollout and had ZERO callers, so every answer for every patient
    carried cancer.gov/types/colorectal and Colontown."""

    def _names(self, slug, query="I was just diagnosed", query_type="general"):
        from llm_utils import get_relevant_resources
        return [r["name"] for r in
                get_relevant_resources(query_type, True, query, cancer_slug=slug)]

    def test_a_breast_patient_gets_breast_organisations_first(self):
        names = self._names("breast")
        assert names, "no resources at all"
        assert any("Komen" in n or "Living Beyond Breast Cancer" in n for n in names[:2])

    def test_no_colorectal_organisation_reaches_a_breast_patient(self):
        blob = " ".join(self._names("breast")).lower()
        for term in ("colontown", "colorectal", "colon cancer"):
            assert term not in blob, f"'{term}' shown to a breast patient"

    def test_every_ready_cancer_has_resources_wired(self):
        from cancer_registry import list_ready
        for slug in list_ready():
            assert self._names(slug), f"{slug}: no resources resolved"

    @pytest.mark.parametrize("query_type,query", [
        ("treatment", "What does HR+/HER2- mean for my treatment?"),
        ("clinical_trial", "are there trials near me"),
        ("side_effect", "my joints hurt on letrozole"),
        ("emotional", "I am scared"),
        ("prognosis", "what does stage IIB mean"),
    ])
    def test_no_colon_link_survives_any_query_type(self, query_type, query):
        """The one the first pass missed.

        Every cancer's resources.yaml holds only the categories that matter to
        it — breast has no 'treatment' section. So a treatment question matched
        nothing, fell through to the generic list, and served 'ACS Colon
        Treatment' and the NCI colorectal PDQ under a breast answer. Caught by
        actually reading the response from production, not by the first test.
        """
        blob = " ".join(self._names("breast", query, query_type)).lower()
        assert blob, f"{query_type}: no resources at all"
        for term in ("colon", "colorectal", "colontown", "rectal"):
            assert term not in blob, f"{query_type}: '{term}' shown to a breast patient"

    def test_colorectal_patients_still_get_colorectal_links(self):
        # The filter must key off the patient's cancer, not the word.
        blob = " ".join(self._names("colorectal", "treatment options", "treatment")).lower()
        assert "colorectal" in blob or "colon" in blob

    def test_omitting_the_slug_keeps_the_old_behaviour(self):
        # Legacy callers (scripts/test_all_features.py, test_chatbot.py) pass no
        # slug and must be unaffected.
        assert self._names(None), "generic path returned nothing"

    def test_urls_are_never_duplicated(self):
        from llm_utils import get_relevant_resources
        out = get_relevant_resources("general", True, "diagnosed", cancer_slug="breast")
        urls = [r["url"] for r in out]
        assert len(urls) == len(set(urls))

    def test_at_most_five(self):
        from llm_utils import get_relevant_resources
        for slug in ("breast", "lung", None):
            assert len(get_relevant_resources("general", True, "diagnosed",
                                              cancer_slug=slug)) <= 5


class TestTheTurnRecordsWhatFired:
    """Reading fifty answers back without this means guessing which of a dozen
    pipeline stages produced each one."""

    SOURCE = (_REPO / "api" / "index.py").read_text()

    @staticmethod
    def _metadata_block(source: str) -> str:
        """The assistant_metadata literal, brace-matched.

        Splitting on the first '}' does not work — the dict holds nested calls
        and dict literals of its own.
        """
        start = source.index("assistant_metadata = {") + len("assistant_metadata = ")
        depth = 0
        for i in range(start, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    return source[start:i + 1]
        raise AssertionError("assistant_metadata literal is unbalanced")

    def test_persisted_metadata_carries_the_diagnostics(self):
        block = self._metadata_block(self.SOURCE)
        for field in ('"debug_info"', '"cancer_slug"', '"mismatch_detected"', '"tone"'):
            assert field in block, f"{field} not persisted with the turn"

    def test_it_carries_no_patient_text(self):
        # A query type and a verdict are not PHI; the message is.
        block = self._metadata_block(self.SOURCE)
        assert '"message"' not in block
        assert "response_data[\"answer\"]" not in block
