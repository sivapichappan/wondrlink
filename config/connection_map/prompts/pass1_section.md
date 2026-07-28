You are reading one section of a clinical guideline and identifying
relationships that are stated **outright in that section**.

## What you may return

A JSON object: `{"candidates": [...]}`. Each candidate has exactly these keys:

- `src_concept_slug` — a slug from the CONCEPTS list below
- `dst_concept_slug` — a slug from the CONCEPTS list below
- `relationship` — one of the RELATIONSHIPS listed below
- `quoted_sentence` — the sentence from the SECTION TEXT that states this
  relationship, copied **exactly**

Return `{"candidates": []}` when the section states no relationship between two
listed concepts. That is a normal and frequent answer. An empty list is far more
useful than a strained one.

## The rule that matters most

`quoted_sentence` must be copied **character for character** from the SECTION
TEXT: same words, same capitalisation, same punctuation, same spacing. Do not
tidy it, do not fix a typo, do not join two sentences, do not trim a clause, do
not paraphrase. It is checked by exact string match against the source and a
candidate whose quotation does not match is discarded.

So: only propose a relationship you can point at a single real sentence for. If
the relationship is true but the section does not say it, do not return it. If
the section implies it but never states it, do not return it. If you find
yourself editing a sentence to make it fit, that candidate does not belong.

## Direction

`side_effect_of` runs symptom → treatment. "Joint pain is common with an
aromatase inhibitor" is `joint_pain` → `aromatase_inhibitor`, not the reverse.

`co_occurs_with` is symmetric; give the pair in either order, once.

## What not to do

- Do not invent a concept slug. Only slugs in the CONCEPTS list exist.
- Do not return a relationship type that is not listed.
- Do not return the same pair twice.
- Do not link a concept to itself.
- Do not reason about what is generally true in oncology. Read only this
  section. Another pass handles relationships spanning sections.

---

## RELATIONSHIPS

{relationships}

## CONCEPTS

{concepts}

## SOURCE

{document_title} — section {section_ref}

## SECTION TEXT

{section_text}
