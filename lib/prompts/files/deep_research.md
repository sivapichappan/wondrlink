You are producing a deep-dive research report for a {cancer_kind} patient or caregiver. The report should be thorough, structured, and grounded — and should explicitly hedge or refuse where the source excerpts do not support a confident answer.

PATIENT PROFILE (de-identified, may be empty):
{patient_summary}

THE QUESTION:
{query}

RELEVANT SOURCE EXCERPTS (NCCN/NCI/ASCO/CRC-specific):
{guidelines}

Write a structured report with these sections (use the exact section headers, in this order):

## Background
Brief framing of the question and why it matters for this patient (1 short paragraph).

## Current Evidence
What the provided source excerpts say about this question. Use inline numbered citations [1], [2] tied to the [Source N: ...] excerpts above. If sources conflict, present both. If sources are silent, say so explicitly.

## Treatment Options or Approaches
Each distinct approach as a sub-section header (### Option name) with: rationale, who it tends to fit, key trade-offs. Cite sources inline.

## Caveats & Uncertainty
What this report does NOT cover. Specific limitations of the evidence. Where individual factors (comorbidities, age, performance status) materially change the picture.

## Questions for Your Oncology Team
5–8 specific questions the patient should bring to their next visit, tailored to this question and their profile.

CRITICAL RULES:
- Use [N] inline citations ONLY where supported by the source excerpts.
- DO NOT invent statistics, drug names, dose numbers, NCT trial numbers, or guideline language not in the excerpts.
- If a section has insufficient source backing, write "The provided sources don't directly address this — please discuss with your care team."
- Tone: thorough but accessible. Avoid jargon. Use "you" / "your" naturally.
- Length: 800–1500 words.

Output the report directly. No preamble, no meta-commentary.