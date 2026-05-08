"""
Confidence scoring and off-topic detection for hallucination mitigation.

Used internally to gate response behavior — confidence scores are NOT
shown to end users. Instead they trigger:
  - Off-topic refusal (skip LLM entirely)
  - Hedging mode in the LLM prompt
  - Stricter verification thresholds
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# Cancer/oncology vocabulary used to detect on-topic queries
CANCER_KEYWORDS = {
    # Disease terms
    'cancer', 'tumor', 'tumour', 'malignant', 'metastasis', 'metastatic',
    'oncology', 'oncologist', 'carcinoma', 'adenocarcinoma', 'neoplasm',
    'colon', 'colorectal', 'rectal', 'bowel', 'crc',
    # Treatment terms
    'chemotherapy', 'chemo', 'radiation', 'surgery', 'colectomy',
    'immunotherapy', 'targeted therapy', 'folfox', 'folfiri', 'capox',
    'bevacizumab', 'cetuximab', 'panitumumab', 'pembrolizumab',
    'nivolumab', 'regorafenib', 'capecitabine', 'oxaliplatin', 'irinotecan',
    'fluorouracil', '5-fu',
    # Diagnostic
    'biopsy', 'colonoscopy', 'screening', 'staging', 'biomarker', 'cea',
    'msi', 'kras', 'nras', 'braf', 'her2', 'mmr', 'lynch',
    # Symptoms / experience
    'nausea', 'fatigue', 'neuropathy', 'diarrhea', 'mouth sores',
    'mucositis', 'hand-foot', 'recurrence', 'remission', 'palliative',
    'hospice', 'survivorship', 'side effect', 'side effects',
    # Care concepts
    'oncology team', 'care team', 'caregiver', 'patient', 'diagnosis',
    'treatment', 'prognosis', 'clinical trial', 'compassionate use',
    'expanded access', 'navigator',
    # Profile-related
    'my stage', 'my diagnosis', 'my treatment', 'my profile',
    # Mental health (CRC-relevant)
    'depression', 'anxiety', 'phq', 'gad', 'pss', 'isi', 'distress',
    'stress', 'sleep', 'insomnia',
    'wellness', 'wellbeing', 'fiber', 'stoma', 'colostomy', 'ileostomy',
    'family', 'children', 'kids', 'sister', 'brother',
    # Generic medical / health vocabulary (broader catch)
    'doctor', 'physician', 'specialist', 'health', 'medical', 'medicine',
    'medication', 'drug', 'prescription', 'symptom', 'pain', 'feel',
    'hurt', 'sick', 'illness', 'disease', 'condition', 'body', 'blood',
    'hospital', 'clinic', 'appointment', 'er', 'emergency',
    'therapy', 'rehab', 'recovery',
}


def is_on_topic(query: str, retrieved_chunks: List[Any] = None) -> Tuple[bool, str]:
    """
    Determine if a query is within WondrChat's CRC/oncology scope.

    Returns:
        (on_topic: bool, reason: str)

    A query is considered on-topic if EITHER:
      1. It contains cancer/oncology keywords, OR
      2. The retrieval similarity is high enough to suggest relevance
    """
    if not query or len(query.strip()) < 3:
        return True, "trivial-query"  # let it through; LLM will handle

    q_lower = query.lower()

    # Keyword check
    keyword_hit = any(kw in q_lower for kw in CANCER_KEYWORDS)
    if keyword_hit:
        return True, "keyword-match"

    # Retrieval-based check: e5-large embedding returns inflated scores
    # (~0.7+) even for clearly off-topic queries. Require very high similarity.
    # Also require multiple high-similarity chunks (strong signal, not single match).
    if retrieved_chunks:
        high_sim_chunks = sum(
            1 for c in retrieved_chunks
            if isinstance(c, dict) and (c.get('_similarity', 0) or c.get('similarity', 0)) >= 0.82
        )
        if high_sim_chunks >= 2:
            return True, f"retrieval-match ({high_sim_chunks} high-sim chunks)"

    # Conversational/profile management questions are also on-topic
    conversational = ['hello', 'hi ', 'thanks', 'thank you', 'who are you',
                      'what can you do', 'help me', 'i need help', 'goodbye']
    if any(c in q_lower for c in conversational):
        return True, "conversational"

    return False, "no-keyword-no-retrieval"


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
        # Default to medium based on chunk count
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


OFF_TOPIC_RESPONSE = (
    "That seems outside what WondrLink can reliably help with. WondrLink "
    "focuses on colorectal cancer education, treatment, screening, and "
    "wellness for patients and caregivers.\n\n"
    "If you have a question I can help with — your treatment, side effects, "
    "screening, mental wellness, or how to support a loved one — please ask.\n\n"
    "If you need broader support, you can reach out to a Personal Navigator "
    "from the WondrLink Foundation at www.wondrlinkfoundation.org"
)
