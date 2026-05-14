"""
Confidence scoring and off-topic detection for hallucination mitigation.

Two-tier filter for the multi-cancer expansion:
  Tier 1 — `is_in_oncology_domain(query, retrieved)` — hard gate. "Is this
           query about oncology / cancer care at all?" Keyword + retrieval-
           similarity check. Rejects genuinely off-topic input (non-medical,
           unrelated diseases). Cancer-agnostic.
  Tier 2 — `route_to_corpus(query, retrieved, selected_cancer)` — soft
           routing. "Should we answer from the selected cancer's corpus,
           the general cross-cutting corpus, or flag a different-cancer
           query for switching?"

Back-compat shim: `is_on_topic(...)` is preserved as an alias for
`is_in_oncology_domain(...)` so older call sites keep working without edits.

The internal confidence values produced here are NOT shown to end users.
They gate response behavior — off-topic refusal, hedging, stricter
verification thresholds.
"""

import logging
import re
from typing import Any, Dict, List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)


# Broad oncology vocabulary — used by the Tier 1 in-domain gate. Cancer-
# specific terms (folfox, colonoscopy, KRAS, BRAF, colostomy, …) moved
# into config/cancers/<slug>/* and accessed via the registry; they aren't
# the gate anymore.
ONCOLOGY_KEYWORDS = {
    # Disease terms (universal)
    'cancer', 'tumor', 'tumour', 'malignant', 'metastasis', 'metastatic',
    'oncology', 'oncologist', 'carcinoma', 'adenocarcinoma', 'neoplasm',
    'lymphoma', 'leukemia', 'sarcoma', 'melanoma',
    # Treatment categories (universal)
    'chemotherapy', 'chemo', 'radiation', 'radiotherapy', 'surgery',
    'immunotherapy', 'targeted therapy', 'hormone therapy', 'endocrine',
    'chemoradiation',
    # Diagnostic categories (universal)
    'biopsy', 'screening', 'staging', 'biomarker', 'mutation', 'gene panel',
    'pathology', 'tumor marker', 'pet scan', 'ct scan', 'mri',
    'blood test', 'blood work', 'lab', 'labs', 'scan',
    # Symptoms / experience (universal — applies to most cancers)
    'nausea', 'fatigue', 'neuropathy', 'mucositis', 'recurrence', 'remission',
    'palliative', 'hospice', 'survivorship', 'side effect', 'side effects',
    'fever', 'chills', 'bleeding', 'shortness of breath',
    # Care concepts
    'oncology team', 'care team', 'caregiver', 'patient', 'diagnosis',
    'treatment', 'prognosis', 'clinical trial', 'compassionate use',
    'expanded access', 'navigator',
    # Profile-related
    'my stage', 'my diagnosis', 'my treatment', 'my profile',
    # Mental health (universal in cancer care)
    'depression', 'anxiety', 'phq', 'gad', 'pss', 'isi', 'distress',
    'stress', 'sleep', 'insomnia',
    'wellness', 'wellbeing',
    'family', 'children', 'kids', 'sister', 'brother',
    # Common emotional / caregiver-burden language patients use without
    # invoking the formal clinical terms above.
    'exhausted', 'overwhelmed', 'drained', 'worn out', 'burnout',
    'hopeless', 'feeling down', 'feeling sad', 'so sad',
    'caring for', 'caring for my', 'looking after',
    'support group', 'support groups',
    # Generic medical / health vocabulary (broader catch)
    'doctor', 'physician', 'specialist', 'health', 'medical', 'medicine',
    'medication', 'drug', 'prescription', 'symptom', 'pain',
    'sick', 'illness', 'disease', 'condition',
    'hospital', 'clinic', 'appointment', 'er', 'emergency',
    'therapy', 'rehab', 'recovery',
    # Cross-cutting supportive care (universal)
    'chemo brain', 'cognitive', 'fertility', 'sexuality', 'intimacy',
    'financial toxicity', 'financial', 'insurance', 'appeal',
    'second opinion', 'genetic testing', 'genetic counseling',
}

# Back-compat alias — older call sites import CANCER_KEYWORDS
CANCER_KEYWORDS = ONCOLOGY_KEYWORDS


def is_in_oncology_domain(query: str, retrieved_chunks: List[Any] = None) -> Tuple[bool, str]:
    """
    Tier 1 — is the query within the oncology / cancer-care domain at all?

    Returns:
        (in_domain: bool, reason: str)

    A query is considered in-domain if ANY of:
      1. It contains broad oncology keywords, OR
      2. The retrieval similarity is high enough to suggest relevance, OR
      3. It's a conversational / meta-query (greeting, "help me", etc.)
    """
    if not query or len(query.strip()) < 3:
        return True, "trivial-query"  # let it through; LLM handles

    q_lower = query.lower()

    # Word-boundary keyword match. Substring matching produces false positives
    # like "er" matching "battery" — fixed by requiring \b…\b around the keyword.
    keyword_hit = any(re.search(r'\b' + re.escape(kw) + r'\b', q_lower) for kw in ONCOLOGY_KEYWORDS)
    if keyword_hit:
        return True, "keyword-match"

    # Retrieval-based check: require very high similarity AND multiple
    # high-sim chunks. e5-large inflates scores so the bar is 0.82 for 2+
    # chunks.
    if retrieved_chunks:
        high_sim_chunks = sum(
            1 for c in retrieved_chunks
            if isinstance(c, dict) and (c.get('_similarity', 0) or c.get('similarity', 0)) >= 0.82
        )
        if high_sim_chunks >= 2:
            return True, f"retrieval-match ({high_sim_chunks} high-sim chunks)"

    # Conversational / profile-management queries are in-domain
    conversational = ['hello', 'hi ', 'thanks', 'thank you', 'who are you',
                      'what can you do', 'help me', 'i need help', 'goodbye']
    if any(c in q_lower for c in conversational):
        return True, "conversational"

    return False, "no-keyword-no-retrieval"


# Back-compat alias used by older callers (api/index.py imports both names).
def is_on_topic(query: str, retrieved_chunks: List[Any] = None) -> Tuple[bool, str]:
    return is_in_oncology_domain(query, retrieved_chunks)


CorpusRoute = Literal["selected", "general", "different_cancer", "out_of_scope"]


def route_to_corpus(
    query: str,
    retrieved_chunks: Optional[List[Any]] = None,
    selected_cancer: Optional[str] = None,
) -> Tuple[CorpusRoute, str]:
    """
    Tier 2 — given a query that passed Tier 1, route it to a corpus slice.

    Returns:
        (route, reason)

    Routes:
      - "selected"        : answer from the selected cancer's corpus.
      - "general"         : answer from the general/cross-cutting corpus
                            (chemo brain, distress, palliative, fertility,
                            financial, caregiver). Selected cancer's
                            overlay still informs the prompt.
      - "different_cancer": the query strongly references a different
                            cancer than the user's selected one — surface
                            a "want to switch?" prompt instead of trying
                            to answer.
      - "out_of_scope"    : caller probably wants to fall through to a
                            Tier-1 rejection (kept as an explicit route
                            in case downstream code branches on it).

    The routing decision uses the cancer_types tags on retrieved chunks
    (when present) plus query-text heuristics. When chunks are untagged
    (pre-backfill) we default to "selected" to avoid regression.
    """
    if not query:
        return "selected", "empty-query"

    q_lower = query.lower()
    chunks = retrieved_chunks or []

    # Count cancer_types coverage in retrieved chunks
    selected_hits = 0
    general_hits = 0
    other_cancer_hits = 0
    for c in chunks:
        if not isinstance(c, dict):
            continue
        tags = c.get('cancer_types')
        if not tags:
            continue
        if isinstance(tags, str):
            tags = [tags]
        if 'general' in tags:
            general_hits += 1
        if selected_cancer and selected_cancer in tags:
            selected_hits += 1
        if selected_cancer:
            others = [t for t in tags if t not in ('general', selected_cancer)]
            if others:
                other_cancer_hits += 1

    # Query-text heuristic: explicit reference to a different cancer
    # (used only when we have a selected_cancer)
    if selected_cancer:
        try:
            from lib import cancer_registry as _registry
            for slug in _registry.list_all():
                if slug == selected_cancer:
                    continue
                cfg = _registry.get(slug) or {}
                display_low = (cfg.get('display_name') or '').lower()
                if not display_low:
                    continue
                # Match against display name or its primary word
                primary_term = display_low.split()[0] if display_low else ''
                if primary_term and primary_term in q_lower:
                    return "different_cancer", f"query mentions {slug}"
                for alias in (cfg.get('aliases') or []):
                    if alias.lower() in q_lower:
                        return "different_cancer", f"query mentions {slug} alias ({alias})"
        except Exception:
            pass

    # Chunk-tag heuristic
    if selected_hits >= 1:
        return "selected", f"selected_cancer chunks hit ({selected_hits})"
    if general_hits >= 1 and other_cancer_hits == 0:
        return "general", f"general-only chunks ({general_hits})"
    if other_cancer_hits >= 2 and selected_hits == 0:
        return "different_cancer", "retrieval points to a different cancer"

    # Fallback — keep the user in their selected corpus.
    return "selected", "fallback-to-selected"


def compute_retrieval_confidence(retrieved_chunks: List[Any]) -> Dict[str, Any]:
    """
    Compute internal confidence metrics for the retrieved chunks.

    Returns dict with:
      - level: 'high' | 'medium' | 'low'
      - max_similarity: float
      - avg_similarity: float
      - chunk_count: int
    """
    if not retrieved_chunks:
        return {
            'level': 'low',
            'max_similarity': 0.0,
            'avg_similarity': 0.0,
            'chunk_count': 0,
        }

    similarities = []
    for chunk in retrieved_chunks:
        if isinstance(chunk, dict):
            sim = chunk.get('_similarity', 0) or chunk.get('similarity', 0)
            similarities.append(sim)

    if not similarities or all(s == 0 for s in similarities):
        # No vector similarity available — can't assess confidence well
        return {
            'level': 'medium',
            'max_similarity': 0.0,
            'avg_similarity': 0.0,
            'chunk_count': len(retrieved_chunks),
        }

    max_sim = max(similarities)
    avg_sim = sum(similarities) / len(similarities)

    if max_sim >= 0.75:
        level = 'high'
    elif max_sim >= 0.55:
        level = 'medium'
    else:
        level = 'low'

    return {
        'level': level,
        'max_similarity': round(max_sim, 3),
        'avg_similarity': round(avg_sim, 3),
        'chunk_count': len(retrieved_chunks),
    }


# Off-topic refusal — templated so the cancer scope adapts per user.
# The {cancer_phrase} placeholder gets filled like:
#   "colorectal cancer education, treatment, screening, and wellness"
# when the user has a selected cancer, or
#   "cancer education, treatment, screening, and wellness"
# when no selected cancer (fallback).
OFF_TOPIC_RESPONSE_TEMPLATE = (
    "That seems outside what WondrLink can reliably help with. WondrLink "
    "focuses on {cancer_phrase} for patients and caregivers.\n\n"
    "If you have a question I can help with — your treatment, side effects, "
    "screening, mental wellness, or how to support a loved one — please ask.\n\n"
    "If you need broader support, you can reach out to a Personal Navigator "
    "from the WondrLink Foundation at www.wondrlinkfoundation.org"
)

# "We noticed you're asking about a different cancer — want to switch?"
CROSS_CANCER_PROMPT_TEMPLATE = (
    "It sounds like you're asking about {other_cancer_kind}, which is "
    "different from your current WondrChat focus ({selected_cancer_kind}). "
    "I can help you switch your focus in Settings → Profile, or I can keep "
    "answering general questions in the meantime.\n\n"
    "If you'd like a Personal Navigator to walk you through this, you can "
    "reach out to the WondrLink Foundation at www.wondrlinkfoundation.org"
)


def render_off_topic_response(selected_cancer: Optional[str] = None) -> str:
    """Compose the off-topic refusal message for the user's selected cancer."""
    if selected_cancer:
        try:
            from lib import cancer_registry as _registry
            name = (_registry.display_name(selected_cancer) or "").lower()
            if name:
                cancer_phrase = f"{name} education, treatment, screening, and wellness"
                return OFF_TOPIC_RESPONSE_TEMPLATE.format(cancer_phrase=cancer_phrase)
        except Exception:
            pass
    return OFF_TOPIC_RESPONSE_TEMPLATE.format(
        cancer_phrase="cancer education, treatment, screening, and wellness"
    )


# Back-compat constant — older callers `from confidence import OFF_TOPIC_RESPONSE`.
# Equals the colorectal-rendered template for parity with the pre-refactor literal.
OFF_TOPIC_RESPONSE = render_off_topic_response("colorectal")
