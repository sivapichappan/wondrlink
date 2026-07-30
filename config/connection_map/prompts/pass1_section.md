You are reading one section of a clinical guideline. Find every relationship the
section **states** between two concepts from the CONCEPTS list, and copy the
sentence that states it.

## What you return

A JSON object: `{"candidates": [...]}`. Each candidate has exactly these keys:

- `src_concept_slug` — a slug from the CONCEPTS list below
- `dst_concept_slug` — a slug from the CONCEPTS list below
- `relationship` — one of the RELATIONSHIPS listed below
- `quoted_sentence` — the sentence from the SECTION TEXT that states this
  relationship, copied **exactly**

If the section states no relationship between two listed concepts, return
`{"candidates": []}`.

## Copy the sentence exactly

`quoted_sentence` must be copied **character for character** from the SECTION
TEXT: same words, same capitalisation, same punctuation, same spacing, same line
breaks. Keep a reference marker such as `[1,11,12]` if it sits inside the
sentence. Do not tidy it, do not fix a typo, do not join two sentences, do not
trim a clause, do not paraphrase.

It is checked by exact string match against the source, so every candidate must
point at one real sentence in this section. If a relationship is true in oncology
but this section does not state it, leave it out.

## Worked examples

These four are from **other documents**, shown so you can see the shape of a good
answer. Never quote from them. Quote only from the SECTION TEXT.

**1. One sentence can carry more than one candidate, and unlisted symptoms carry
none.**

> Acute toxicities of radiation therapy include radiation dermatitis, breast swelling and/or itching, tightness in the axillary area, and fatigue.

```json
{"candidates": [
  {"src_concept_slug": "fatigue", "dst_concept_slug": "radiation_therapy",
   "relationship": "side_effect_of",
   "quoted_sentence": "Acute toxicities of radiation therapy include radiation dermatitis, breast swelling and/or itching, tightness in the axillary area, and fatigue."}
]}
```

Breast swelling and axillary tightness have no slug in the CONCEPTS list, so they
produce nothing. Fatigue does.

**2. A drug name maps to its concept through the "also written as" list, and the
reference marker stays in the quotation.**

> Delayed N&V is associated with cisplatin, cyclophosphamide, and other drugs (e.g., doxorubicin and ifosfamide) given at high doses or given on 2 or more consecutive days.[1,11,12]

```json
{"candidates": [
  {"src_concept_slug": "nausea", "dst_concept_slug": "anthracycline_chemotherapy",
   "relationship": "side_effect_of",
   "quoted_sentence": "Delayed N&V is associated with cisplatin, cyclophosphamide, and other drugs (e.g., doxorubicin and ifosfamide) given at high doses or given on 2 or more consecutive days.[1,11,12]"}
]}
```

Doxorubicin is listed under `anthracycline_chemotherapy`. Cisplatin and
cyclophosphamide are not in the list at all, so they produce nothing.

**3. Two experience-side concepts in one stated sentence.**

> Sleep disturbances frequently co-occur with cancer-related fatigue and may have common underlying mechanisms.

```json
{"candidates": [
  {"src_concept_slug": "sleep_quality", "dst_concept_slug": "fatigue",
   "relationship": "co_occurs_with",
   "quoted_sentence": "Sleep disturbances frequently co-occur with cancer-related fatigue and may have common underlying mechanisms."}
]}
```

**4. A reference-list entry names two concepts but states nothing.**

> Meek AG: Breast radiotherapy and lymphedema. Cancer 83 (12 Suppl American): 2788-97, 1998.

```json
{"candidates": []}
```

A bibliography entry is the title of another paper, not a claim this section
makes. The same goes for page headers, URLs, and running dates.

## Direction

`side_effect_of` runs from the experience to the treatment: `src` is the symptom,
lab value, or measure; `dst` is the treatment or procedure. "Joint pain is common
with an aromatase inhibitor" is `joint_pain` → `aromatase_inhibitor`, never the
reverse.

`co_occurs_with` is symmetric; give the pair in either order, once.

## What not to do

- Do not invent a concept slug. Only slugs in the CONCEPTS list exist.
- Do not return a relationship type that is not listed.
- Do not return the same pair twice.
- Do not link a concept to itself.
- Do not build a candidate out of a reference list, a page header, or a table of
  contents.
- Read only this section. Another pass chains relationships across sections.

---

## RELATIONSHIPS

{relationships}

## CONCEPTS

{concepts}

## SOURCE

{document_title} — section {section_ref}

## SECTION TEXT

The section begins after the next line and ends at the matching line below it.

----------------8<----------------
{section_text}
----------------8<----------------

## Now answer

Return the JSON object described at the top: one key, `candidates`, holding the
relationships the section above states. Do not echo the section text back. Do not
add any other top-level key.
