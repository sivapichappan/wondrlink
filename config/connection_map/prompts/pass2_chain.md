You are looking for relationships that **two or more already-verified
quotations together** support, where no single quotation states the whole
thing.

Every quotation below has already been checked word for word against its
source. You are reasoning over these quotations only. You are not reading the
guidelines, and you may not introduce a sentence that is not in this list.

## What you may return

A JSON object: `{"candidates": [...]}`. Each candidate has exactly these keys:

- `src_concept_slug` — a slug from the CONCEPTS list
- `dst_concept_slug` — a slug from the CONCEPTS list
- `relationship` — one of the RELATIONSHIPS listed
- `evidence_ids` — **two or more** ids from the QUOTATIONS list
- `reasoning` — one or two sentences on how those quotations combine

Return `{"candidates": []}` when nothing chains. That is a good answer.

## What "chains" means

Each cited quotation must carry real weight. If one of them alone already
states the relationship, that is a job for the other pass, not this one, and
you should not return it here. If a quotation is only loosely on topic and the
claim would stand without it, do not cite it.

A worked example of a real chain: one quotation says a treatment commonly
causes a symptom; a separate quotation says that symptom is a leading reason
patients stop that treatment. Together they support a relationship between the
symptom and stopping treatment that neither sentence states alone.

## Where this goes wrong

The temptation is to assemble something that sounds clinically sensible and
attach whichever quotations are nearest. That produces a claim no source
actually makes, wearing citations as decoration. A physician reviews every
candidate you return with the quotations beside it, so a chain that does not
hold is immediately visible and wastes their time, which is the scarcest thing
here.

Prefer returning three chains you are confident in over fifteen you are not.

## Also

- Never invent a concept slug or a relationship type.
- Do not return a pair that already appears in EXISTING RELATIONSHIPS.
- Do not link a concept to itself.
- Do not cite the same quotation twice in one candidate.

---

## RELATIONSHIPS

{relationships}

## CONCEPTS

{concepts}

## EXISTING RELATIONSHIPS

{existing}

## QUOTATIONS

{quotations}
