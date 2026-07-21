"""
Second-pass LLM verification for hallucination mitigation.

Uses Groq Llama 3.1 8B (fast, cheap) to fact-check the primary LLM's
response against the retrieved source chunks. Adds ~1-1.5s latency per
chat call. Returns a verification verdict + recommended action.
"""

import json
import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


VERIFIER_SYSTEM = """You are a medical fact-checker. Your job is to verify whether an AI assistant's response is grounded in the provided source excerpts.

You will receive:
1. A user's question
2. Source excerpts (medical guidelines)
3. The AI's response

Output a JSON object with these exact keys:
- "verified": boolean — true if all major medical claims are supported by sources OR the response appropriately hedges/refuses
- "fabrication_risk": "low" | "medium" | "high" — risk that the response contains invented details
- "unsupported_claims": array of strings — specific claims in the response NOT supported by sources (max 3)
- "recommended_action": "pass" | "add_disclaimer" | "regenerate" — what to do with this response

GUIDELINES:
- A response that says "I don't have information on this" or "consult your care team" is ALWAYS verified=true.
- Generic empathy/tone (acknowledgment, validation) does NOT need source support — only medical claims do.
- Specific drug names, dosages, percentages, statistics, NCT trial numbers, study citations: these MUST be in the sources.
- Hedging language ("may", "some patients", "discuss with team") reduces fabrication risk.
- Output ONLY valid JSON. No extra text."""


def verify_response(response: str, retrieved_chunks: List[Any], query: str) -> Dict[str, Any]:
    """
    Verify a response against retrieved source chunks using Groq 8B.

    Returns:
        dict with keys: verified (bool), fabrication_risk (str),
        unsupported_claims (list[str]), recommended_action (str)
    """
    # Default fail-safe response if anything goes wrong
    default_pass = {
        'verified': True,
        'fabrication_risk': 'unknown',
        'unsupported_claims': [],
        'recommended_action': 'pass',
        'verifier_used': 'none',
    }

    if not response or len(response.strip()) < 30:
        return default_pass

    # Format sources concisely for verifier
    sources_text = ""
    if retrieved_chunks:
        for i, chunk in enumerate(retrieved_chunks[:5]):
            if isinstance(chunk, dict):
                content = chunk.get('content', '') or ''
                filename = chunk.get('filename', 'guideline')
            else:
                content = str(chunk)
                filename = 'guideline'
            # Truncate each chunk for verifier (it doesn't need full text)
            sources_text += f"\n[Source {i+1}: {filename}]\n{content[:500]}\n"
    else:
        sources_text = "\n(No source excerpts retrieved.)\n"

    verifier_prompt = f"""USER QUESTION: {query[:500]}

SOURCE EXCERPTS:
{sources_text}

AI RESPONSE TO VERIFY:
{response[:2000]}

Output the JSON object now. No prose, no preamble — just the JSON."""

    try:
        from llm_utils import get_groq_client
        from model_registry import get_model
        client = get_groq_client()
        if not client:
            logger.warning("Groq unavailable for verification — passing through")
            return default_pass

        import time as _time
        from ai_gateway import log_llm_call
        _t0 = _time.perf_counter()
        completion = client.chat.completions.create(
            model=get_model("verifier"),
            messages=[
                {"role": "system", "content": VERIFIER_SYSTEM},
                {"role": "user", "content": verifier_prompt}
            ],
            max_tokens=400,
            temperature=0.1,
            top_p=0.9,
        )
        log_llm_call("verify", "groq", get_model("verifier"),
                     int((_time.perf_counter() - _t0) * 1000),
                     usage=getattr(completion, "usage", None))

        if not completion or not completion.choices:
            return default_pass

        verdict_text = completion.choices[0].message.content or ""

        # Extract JSON from response (LLM sometimes wraps it)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', verdict_text, re.DOTALL)
        if not json_match:
            logger.warning(f"Verifier returned no JSON: {verdict_text[:200]}")
            return default_pass

        try:
            verdict = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            logger.warning(f"Verifier JSON parse failed: {verdict_text[:200]}")
            return default_pass

        # Normalize and validate
        result = {
            'verified': bool(verdict.get('verified', True)),
            'fabrication_risk': verdict.get('fabrication_risk', 'unknown') if verdict.get('fabrication_risk') in ('low', 'medium', 'high', 'unknown') else 'unknown',
            'unsupported_claims': verdict.get('unsupported_claims', [])[:3] if isinstance(verdict.get('unsupported_claims'), list) else [],
            'recommended_action': verdict.get('recommended_action', 'pass') if verdict.get('recommended_action') in ('pass', 'add_disclaimer', 'regenerate') else 'pass',
            'verifier_used': 'groq-8b',
        }

        logger.info(f"Verification: verified={result['verified']}, risk={result['fabrication_risk']}, action={result['recommended_action']}")
        return result

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return default_pass


HEDGED_FALLBACK_RESPONSE = (
    "I want to make sure I give you accurate information, and I'm not "
    "fully confident in what I had drafted for this question. This is "
    "exactly the kind of thing your oncology team is best equipped to "
    "answer for your specific situation.\n\n"
    "If you'd like additional support navigating this, you can reach a "
    "Personal Navigator from the WondrLink Foundation at "
    "www.wondrlinkfoundation.org"
)


SOFT_DISCLAIMER_PREFIX = (
    "*Note: Some details below should be verified with your care team — "
    "they can confirm what applies specifically to your situation.*\n\n"
)
