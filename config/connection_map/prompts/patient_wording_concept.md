You are giving medical terms their everyday names, for a cancer support app.

Each term below is what a clinician calls something. Give the words a patient
would use for the same thing. A doctor reviews every one of these.

## What you return

A JSON object:

`{"concepts": [{"slug": "...", "display_patient": "..."}]}`

One entry per term you were given, using the same slug. `display_patient` is a
short noun phrase, not a sentence — it gets dropped into the middle of a
question, so it must read naturally there.

Examples of the right idea:

| clinical | everyday |
|---|---|
| aromatase inhibitor | hormone pill |
| anthracycline chemotherapy | chemotherapy |
| peripheral neuropathy | numbness or tingling in the hands or feet |
| lymphedema | arm swelling |
| bone mineral density loss | thinning bones |
| taking the pill as prescribed | taking the pill every day |

## Rules

1. **No clinical jargon.** That is the whole point. If a patient would have to
   look the word up, it is wrong. Never say ECOG, LVEF, arthralgia, vasomotor.
2. **No dashes of any kind.** Use plain words.
3. **No numbers about how likely something is.**
4. **Keep it short.** Six words at most. A phrase, not an explanation.
5. **Do not say what causes what.** These are names for things, nothing more.
6. **Keep it accurate.** If the everyday name would be misleading, choose a
   plainer description instead of a wrong simplification. "Hormone pill" is fine
   for a specific hormone tablet. "Medicine" alone is not, because it says
   nothing.

Some of these are lab values or measurements. Name what the patient would
recognise: "bone density" rather than the acronym, "heart pumping strength"
rather than the ejection fraction.

## The terms

{concepts}

Return only the JSON object, with one entry per term above.
