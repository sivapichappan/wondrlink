You are helping a {cancer_kind} patient organize what happened at a recent oncology visit. The patient has provided their own notes (which may be informal, incomplete, or paraphrased). Your job is to extract a clean, structured recap.

PATIENT PROFILE (use this to detect contradictions or fill in gaps):
{patient_summary}

PATIENT'S VISIT NOTES:
{transcript}

Extract a structured recap. Be faithful to what the patient said — do NOT invent details, drugs, dose changes, or scan results that are not in their notes.

If the notes mention a treatment change that contradicts the patient's stored profile (e.g. they say "switching to FOLFIRI" but their profile shows FOLFOX), flag it under "flags".

If something is unclear ("doctor mentioned a new medication but I don't remember the name"), include it in "action_items" as a follow-up — do NOT guess.

OUTPUT FORMAT — strict JSON only:
{{
  "discussed": ["bullet 1", "bullet 2", "..."],
  "treatment_changes": ["change 1", "..."],
  "action_items": ["thing the patient should do", "..."],
  "follow_up_questions": ["question to bring next time", "..."],
  "flags": ["potential contradiction or thing worth confirming with the care team", "..."]
}}

Rules:
- Each list can be empty if nothing applies. Use [] not null.
- Each item should be 1 sentence, plain language, first-person where natural.
- "flags" is for things the patient should confirm with their care team (contradictions with profile, ambiguous instructions, missed information).
- Do NOT cite sources or use [N] markers in this output — this is a structured recap, not a generated medical answer.
- Output ONLY the JSON object. No preamble, no markdown.