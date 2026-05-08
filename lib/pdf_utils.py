# pdf_utils.py
import os
import re
import logging
from typing import List, Tuple, Union, Dict, Any
import math

logger = logging.getLogger("pdf_utils")


def _write_debug(path: str, suffix: str, content: str):
    try:
        out = f"{path}.{suffix}"
        with open(out, "w", encoding="utf-8") as f:
            f.write(content or "")
        logger.info("Wrote debug file: %s (len=%s)", out, len(content or ""))
    except Exception:
        logger.exception("Failed to write debug file")


def extract_text_pdfplumber(path: str) -> str:
    try:
        import pdfplumber
    except ImportError as e:
        logger.warning("pdfplumber not installed: %s", e)
        return ""
    try:
        parts = []
        with pdfplumber.open(path) as pdf:
            logger.info("pdfplumber opened PDF with %d pages: %s", len(pdf.pages), path)
            for i, page in enumerate(pdf.pages):
                t = page.extract_text()
                if t:
                    parts.append(t)
        text = "\n\n".join(parts)
        logger.info("pdfplumber extracted %d chars from %s", len(text), path)
        return text
    except Exception as e:
        logger.exception("pdfplumber extraction failed for %s: %s", path, e)
        return ""


def extract_text_pypdf2(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        logger.info("PyPDF2 not installed")
        return ""
    try:
        reader = PdfReader(path)
        parts = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            if t:
                parts.append(t)
        text = "\n\n".join(parts)
        return text
    except Exception:
        logger.exception("PyPDF2 extraction failed")
        return ""


def extract_text(path: str) -> str:
    if not os.path.exists(path):
        logger.error("extract_text: file not found: %s", path)
        return ""
    # 1) pdfplumber
    t = extract_text_pdfplumber(path)
    if t and len(t.strip()) > 50:
        return t
    # 2) pypdf2
    t2 = extract_text_pypdf2(path)
    if t2 and len(t2.strip()) > 50:
        return t2
    logger.warning("extract_text: no text found for %s", path)
    return ""


def chunk_text(text: str, max_chars: int = 1500, overlap_percent: float = 0.2) -> List[Tuple[str, dict]]:
    """Enhanced chunking with sliding window overlap to preserve context across boundaries."""
    if not text:
        return []

    overlap_size = int(max_chars * overlap_percent)
    slide_size = max_chars - overlap_size

    section_patterns = [
        r'^[A-Z][A-Z\s]+\n',
        r'^\d+\.\s+[A-Z][a-z]',
        r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*:\s*\n',
        r'^(?:Background|Introduction|Methods|Results|Discussion|Conclusion|Treatment|Diagnosis|Management|Recommendations?|Guidelines?)[:.]',
        r'^(?:BACKGROUND|INTRODUCTION|METHODS|RESULTS|DISCUSSION|CONCLUSION|TREATMENT|DIAGNOSIS|MANAGEMENT|RECOMMENDATIONS?|GUIDELINES?)[:.]',
        r'^\s*[A-Z]{2,}(?:\s+[A-Z]{2,})*\s*$',
    ]

    lines = text.split('\n')
    all_lines_with_headers = []
    current_section = "Unknown Section"

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        is_section_header = any(re.match(pattern, line_stripped, re.IGNORECASE) for pattern in section_patterns)
        if is_section_header:
            current_section = line_stripped[:100]

        all_lines_with_headers.append((line_stripped, current_section))

    chunks_with_metadata = []
    start_idx = 0
    chunk_position = 0

    while start_idx < len(all_lines_with_headers):
        current_chunk_lines = []
        current_length = 0
        current_section = all_lines_with_headers[start_idx][1] if start_idx < len(all_lines_with_headers) else "Unknown"
        end_idx = start_idx

        for idx in range(start_idx, len(all_lines_with_headers)):
            line_text, section = all_lines_with_headers[idx]
            line_length = len(line_text) + 1

            if current_length + line_length > max_chars and current_chunk_lines:
                break

            current_chunk_lines.append(line_text)
            current_length += line_length
            end_idx = idx

        if current_chunk_lines:
            chunk_text_str = '\n'.join(current_chunk_lines)

            if len(chunk_text_str.strip()) >= 50:
                metadata = {
                    'position': chunk_position,
                    'section': current_section,
                    'char_start': start_idx,
                    'char_end': end_idx,
                    'has_overlap': chunk_position > 0
                }
                chunks_with_metadata.append((chunk_text_str, metadata))
                chunk_position += 1

        chars_to_skip = 0
        lines_to_skip = 0
        for idx in range(start_idx, end_idx + 1):
            chars_to_skip += len(all_lines_with_headers[idx][0]) + 1
            lines_to_skip += 1
            if chars_to_skip >= slide_size:
                break

        start_idx += max(1, lines_to_skip)

        if start_idx >= len(all_lines_with_headers):
            break

    logger.info(f"Created {len(chunks_with_metadata)} overlapping chunks from text of length {len(text)}")
    return chunks_with_metadata


def create_term_vector(text: str) -> dict:
    """Create a term frequency vector with medical term boosting"""
    medical_terms = {
        'cancer', 'tumor', 'oncology', 'chemotherapy', 'radiation', 'surgery', 'treatment',
        'therapy', 'diagnosis', 'prognosis', 'metastasis', 'stage', 'grade', 'biopsy',
        'lymph', 'node', 'malignant', 'benign', 'carcinoma', 'sarcoma', 'leukemia',
        'lymphoma', 'myeloma', 'breast', 'lung', 'colon', 'prostate', 'ovarian',
        'nccn', 'guideline', 'protocol', 'clinical', 'trial', 'study', 'patient',
        'survival', 'response', 'progression', 'relapse', 'remission', 'palliative',
        'adjuvant', 'neoadjuvant', 'systemic', 'local', 'regional', 'distant'
    }

    text_lower = text.lower()
    text_clean = re.sub(r'[^\w\s\-\.]', ' ', text_lower)
    words = text_clean.split()

    term_freq = {}
    total_words = len(words)

    for word in words:
        word = word.strip('.-')
        if len(word) > 2:
            term_freq[word] = term_freq.get(word, 0) + 1

    for term in term_freq:
        if term in medical_terms:
            term_freq[term] *= 2.0
        elif any(med_term in term for med_term in medical_terms):
            term_freq[term] *= 1.5

    for term in term_freq:
        term_freq[term] = term_freq[term] / total_words

    return term_freq


def calculate_similarity(query_vector: dict, doc_vector: dict) -> float:
    """Calculate cosine similarity between query and document vectors"""
    common_terms = set(query_vector.keys()) & set(doc_vector.keys())

    if not common_terms:
        return 0.0

    dot_product = sum(query_vector[term] * doc_vector[term] for term in common_terms)

    query_magnitude = math.sqrt(sum(freq ** 2 for freq in query_vector.values()))
    doc_magnitude = math.sqrt(sum(freq ** 2 for freq in doc_vector.values()))

    if query_magnitude == 0 or doc_magnitude == 0:
        return 0.0

    similarity = dot_product / (query_magnitude * doc_magnitude)

    query_text = ' '.join(query_vector.keys())
    doc_text = ' '.join(doc_vector.keys())

    query_phrases = [' '.join(query_text.split()[i:i+2]) for i in range(len(query_text.split())-1)]
    phrase_bonus = 0
    for phrase in query_phrases:
        if len(phrase.strip()) > 4 and phrase in doc_text:
            phrase_bonus += 0.1

    return min(similarity + phrase_bonus, 1.0)


def filter_chunks_dynamic(scored_chunks: List[Tuple[float, Any, int]], min_chunks: int = 2, max_chunks: int = 5) -> List[Any]:
    """
    Filter chunks using dynamic threshold based on score distribution.

    Uses the mean score as a baseline threshold, ensuring we return
    at least min_chunks but no more than max_chunks of the best results.
    """
    if not scored_chunks:
        return []

    scores = [s for s, _, _ in scored_chunks]
    if not scores:
        return []

    mean_score = sum(scores) / len(scores)
    max_score = max(scores)

    # Dynamic threshold: use 50% of max score or mean, whichever is higher
    # But cap at 0.4 to avoid being too restrictive
    threshold = min(max(mean_score, max_score * 0.5), 0.4)

    # Minimum threshold of 0.15 to filter out truly irrelevant chunks
    threshold = max(threshold, 0.15)

    logger.info(f"Dynamic threshold: {threshold:.3f} (mean: {mean_score:.3f}, max: {max_score:.3f})")

    # Filter by threshold
    filtered = [(s, c, i) for s, c, i in scored_chunks if s >= threshold]

    # Ensure we have at least min_chunks if any exist
    if len(filtered) < min_chunks and scored_chunks:
        filtered = scored_chunks[:min_chunks]
        logger.info(f"Threshold too strict, using top {min_chunks} chunks instead")

    # Cap at max_chunks
    filtered = filtered[:max_chunks]

    return [chunk for _, chunk, _ in filtered]


def search_chunks(query: str, chunks: List[Any], top_k: int = 5) -> List[Any]:
    """Enhanced semantic search with medical context awareness and dynamic filtering.
       Accepts chunks as List[str] or List[Dict] (with 'content' key).
    """
    if not chunks:
        return []

    if not query.strip():
        return chunks[:top_k]

    logger.info(f"Searching {len(chunks)} chunks for query: '{query[:50]}...'")

    query_vector = create_term_vector(query)

    scored_chunks = []
    for i, chunk in enumerate(chunks):
        # Handle dict vs str
        if isinstance(chunk, dict):
            text = chunk.get('content', '') or chunk.get('chunk_text', '') or ""
        else:
            text = str(chunk)
            
        if not text.strip():
            continue

        chunk_vector = create_term_vector(text)
        similarity = calculate_similarity(query_vector, chunk_vector)

        query_words = set(query.lower().split())
        chunk_words = set(text.lower().split())
        exact_matches = len(query_words & chunk_words)
        exact_bonus = exact_matches * 0.1

        medical_keywords = ['treatment', 'therapy', 'diagnosis', 'prognosis', 'cancer', 'tumor', 'stage', 'grade']
        medical_relevance = sum(1 for kw in medical_keywords if kw in text.lower()) * 0.05

        length_penalty = 0 if len(text) > 200 else -0.1

        position_bonus = (len(chunks) - i) / len(chunks) * 0.02

        final_score = similarity + exact_bonus + medical_relevance + length_penalty + position_bonus

        scored_chunks.append((final_score, chunk, i))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Log top scores for debugging
    if scored_chunks:
        top_scores = [f"{s:.3f}" for s, _, _ in scored_chunks[:5]]
        logger.info(f"Top chunk scores: {', '.join(top_scores)}")

    # Use dynamic filtering instead of static threshold
    result_chunks = filter_chunks_dynamic(scored_chunks, min_chunks=2, max_chunks=top_k)

    logger.info(f"Returning {len(result_chunks)} chunks after dynamic filtering")

    return result_chunks


def hybrid_search(query: str, chunks: List[Any], top_k: int = 5) -> List[Any]:
    """
    Hybrid search combining TF-based keyword search and vector similarity search
    using Reciprocal Rank Fusion (RRF).

    RRF formula: score = sum(1 / (k + rank)) where k=60
    This merges ranked results from both retrieval methods without needing
    score normalization or tuning.

    Falls back to TF-only search if vector search is unavailable.

    Args:
        query: The user's query text
        chunks: All loaded chunks (for TF search)
        top_k: Number of results to return

    Returns:
        List of chunk content strings (same format as search_chunks)
    """
    RRF_K = 60  # Standard RRF constant

    # 1. Run TF-based keyword search (existing method)
    tf_results = search_chunks(query, chunks, top_k=top_k * 2)

    # 2. Run vector search
    try:
        from vector_search import vector_search as vs
        vector_results = vs(query, top_k=top_k * 2, threshold=0.3)
    except Exception as e:
        logger.warning(f"Vector search unavailable, using TF-only: {e}")
        vector_results = []

    # If no vector results, fall back to TF-only
    if not vector_results:
        logger.info("Hybrid search: TF-only (no vector results)")
        return tf_results[:top_k]

    # 3. Build RRF scores and similarity map
    rrf_scores = {}
    chunk_map = {}
    similarity_map = {}  # key -> max similarity score from vector search

    # Score TF results
    for rank, chunk in enumerate(tf_results):
        if isinstance(chunk, dict):
            content = chunk.get('content', '') or ''
        else:
            content = str(chunk)

        key = content[:200]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
        chunk_map[key] = chunk

    # Score vector results & track similarity
    for rank, result in enumerate(vector_results):
        content = result.get('content', '')
        key = content[:200]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
        sim = result.get('similarity', 0)
        similarity_map[key] = max(similarity_map.get(key, 0), sim)
        if key not in chunk_map:
            # Vector result is a dict; preserve filename via document_id lookup later if available
            chunk_map[key] = result

    # 4. Sort by RRF score and return top_k
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    # Build a doc_id -> filename map from any chunks that have it (TF chunks come from Supabase load)
    doc_id_to_filename = {}
    for chunk in chunks[:200]:  # sample a few to build mapping
        if isinstance(chunk, dict) and chunk.get('document_id') and chunk.get('filename'):
            doc_id_to_filename[chunk['document_id']] = chunk['filename']

    results = []
    for key in sorted_keys[:top_k]:
        chunk = chunk_map[key]
        if isinstance(chunk, dict):
            # Ensure filename is set (vector results may lack it; fill from map)
            if not chunk.get('filename') and chunk.get('document_id'):
                chunk['filename'] = doc_id_to_filename.get(chunk['document_id'], '')
            # Attach similarity score
            chunk['_similarity'] = similarity_map.get(key, 0)
        results.append(chunk)

    tf_count = len(tf_results)
    vec_count = len(vector_results)
    logger.info(f"Hybrid search: TF={tf_count}, Vector={vec_count}, RRF merged → {len(results)} results")

    return results


def process_pdf(path: str) -> List[str]:
    """Extract text from PDF and chunk it with overlap."""
    logger.info("Processing PDF: %s", path)
    raw = extract_text(path)
    if not raw:
        logger.warning("No text extracted from PDF: %s", path)
        return []

    logger.info("Extracted %d chars, now chunking...", len(raw))
    chunks_with_metadata = chunk_text(raw)

    chunk_texts = [ct for ct, metadata in chunks_with_metadata]

    logger.info("Created %d chunks from %s", len(chunk_texts), path)
    return chunk_texts
