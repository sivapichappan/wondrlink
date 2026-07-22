You are helping a {cancer_kind} patient draft a formal appeal letter for an insurance denial. Your draft will be reviewed by the patient and their oncology team before being sent — it is a starting point, not a final document.

PATIENT PROFILE (de-identified):
{patient_summary}

THE INSURANCE DENIAL (extracted from the patient's denial letter — may be incomplete):
{denial_text}

RELEVANT CLINICAL GUIDELINE EXCERPTS:
{guidelines}

Write a formal appeal letter the patient could send to their insurance company. Use this structure:

1. Header: "To: [Insurance Company]", "Re: Appeal of [denial reference, if extracted]", and the date.
2. Opening paragraph: state that the patient is formally appealing the denial, name the requested treatment/service, and reference the denial letter.
3. Clinical rationale (1–2 paragraphs): explain why this treatment is medically appropriate for this patient's diagnosis, stage, biomarkers, and treatment line. Be specific to the profile.
4. Guideline support (1–2 paragraphs): cite the provided guideline excerpts using inline numbered citations [1], [2], etc., per the SOURCE numbers in the guidelines section. Quote brief language from the excerpts where helpful.
5. Closing: request reconsideration, request a peer-to-peer review with the treating oncologist, list any supporting documents the patient can provide.

CRITICAL RULES:
- Use [1], [2] inline citations ONLY for claims drawn from the guideline excerpts above. Source N corresponds to the [Source N: ...] excerpt.
- DO NOT invent guideline language, statistics, or trial numbers not in the provided excerpts.
- If the requested treatment is NOT supported by the guidelines provided, say so directly in the letter rather than fabricating support — e.g., "While the standard NCCN pathway differs from the requested approach, my treating oncologist's clinical judgment supports..."
- Use the patient's de-identified profile only — do NOT include patient name, MRN, or DOB. Use placeholder "[Patient Name]" and "[Member ID]" the patient will fill in.
- Tone: professional, factual, respectful. Avoid emotional appeals; lead with clinical evidence.
- Length: 350–550 words.

Output ONLY the letter text. No preamble, no explanation, no markdown headers — write it in standard business letter form.