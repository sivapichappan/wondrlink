#!/usr/bin/env python3
"""
Connection-map literature extraction (SPEC-connection-map.md §6).

Reads the verbatim corpus, asks the model what relationships each section
STATES, verifies every quotation against the source, and writes surviving
candidates for a physician to review.

    python3 scripts/run_connection_map_extraction.py --pass 1 --limit 10
    python3 scripts/run_connection_map_extraction.py --pass 1            # all
    python3 scripts/run_connection_map_extraction.py --pass 2
    python3 scripts/run_connection_map_extraction.py --pass 1 --dry-run  # no writes

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TOGETHER_API_KEY.
Point at sage-dev with `set -a; . ./.env.development; set +a`.

Nothing this script writes reaches a patient. Every candidate is a proposal
for review, and every citation it stores is text copied out of the source.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.concepts import RELATIONSHIP_TYPES  # noqa: E402
from connection_map.extraction.validate import (  # noqa: E402
    parse_model_json,
    rejection_summary,
    validate_pass1,
    validate_pass2,
)
from model_registry import get_model  # noqa: E402

PROMPTS = _REPO / "config" / "connection_map" / "prompts"

# v1 enables these two (§4.3); the others are extracted later, not now.
PASS1_RELATIONSHIPS = ("side_effect_of", "co_occurs_with")

# Sections shorter than this are headings and page furniture.
MIN_SECTION_CHARS = 400
MAX_SECTION_CHARS = 12000

# A section must mention at least this many DISTINCT concepts to be worth a
# model call. The first pilot read a title page, a gene-profile table and a
# bibliography, and correctly found nothing in any of them: a reference list
# states no clinical relationships. Ranking by concept mentions puts the model
# in front of the passages that can actually contain one, which raises yield
# and cuts spend at the same time.
#
# This chooses WHICH SECTIONS TO READ. It does not decide what is true and it
# never sees the model's output — §6.3's ban on unconstrained discovery is
# about proposing relationships without a quotation, not about retrieval.
# Counting ANY concept was not enough: it favours clinician trial sections
# dense with treatment names and survival statistics, which state no
# symptom relationships at all (verified — the model correctly returned
# nothing for several). The two relationship types v1 enables need specific
# DOMAIN PAIRINGS present in the same section:
#
#   side_effect_of  needs a symptom/finding AND a treatment or procedure
#   co_occurs_with  needs two experience-side concepts
#
# so that is what a section has to contain to be worth reading.
SYMPTOM_SIDE = {"symptom", "lab_or_measure"}
TREATMENT_SIDE = {"treatment", "procedure"}
EXPERIENCE_SIDE = {"symptom", "daily_life"}


def concept_terms(concepts):
    """Searchable surface forms per concept: the clinical label, the part
    before any parenthetical gloss, and the slug's own words."""
    out = {}
    for c in concepts:
        label = (c.get("display_clinical") or "").lower().strip()
        forms = set()
        if label:
            forms.add(label)
            forms.add(label.split("(")[0].strip())
        forms.add(c["slug"].replace("_", " "))
        # The words the guidelines actually use. Measured: drug names appear
        # more often than the class names we chose.
        for a in (c.get("aliases") or []):
            forms.add(a.lower().strip())
        out[c["slug"]] = {f for f in forms if len(f) >= 4}
    return out


def mentions(text_lower, terms):
    """Distinct concepts mentioned in a section."""
    hit = set()
    for slug, forms in terms.items():
        if any(f in text_lower for f in forms):
            hit.add(slug)
    return hit


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def together_json(prompt: str, model: str, max_tokens: int = 4000) -> str:
    """One extraction call.

    `enable_thinking: False` is LOAD-BEARING, not a tuning knob. The extractor is
    a reasoning model, and on a real 12k-character section its thinking consumes
    the whole token budget before a single visible character is emitted (measured:
    completion_tokens hit the cap, content came back empty). Under
    `response_format=json_object` that does not surface as an error — the
    constrained decoder must emit SOME valid object, so it emits the cheapest one,
    `{"candidates": []}` in 7 tokens, or echoes the input back as
    `{"section_text": "..."}`. Both read as "the section states nothing".

    That cost a day of chasing the prompt. The same trap, with the same fix, is
    documented for the chat model in .claude/rules/backend-python.md.

    With thinking off the same section returns four cited candidates in 263
    tokens. Raising max_tokens does NOT substitute for this.
    """
    from together import Together

    client = Together(api_key=os.environ["TOGETHER_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.1,          # near-deterministic: this is extraction, not writing
        response_format={"type": "json_object"},
        chat_template_kwargs={"enable_thinking": False},
    )
    return resp.choices[0].message.content or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="pass_no", type=int, default=1, choices=(1, 2))
    ap.add_argument("--limit", type=int, default=0, help="max sections (0 = all)")
    ap.add_argument("--cancer", default="breast")
    ap.add_argument("--dry-run", action="store_true", help="validate, write nothing")
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        return 1
    if not os.environ.get("TOGETHER_API_KEY"):
        print("ERROR: TOGETHER_API_KEY is required")
        return 1

    from supabase import create_client

    db = create_client(url, key)
    model = get_model("connection_extractor")
    print(f"model: {model}   target: {url}")

    concepts = (db.table("concept")
                .select("id, slug, domain, display_clinical, aliases")
                .contains("cancer_scopes", [args.cancer])
                .execute()).data or []
    by_slug = {c["slug"]: c for c in concepts}
    # Both passes hand this to the validator so RELATIONSHIP_DOMAINS is enforced
    # rather than merely stated in the prompt.
    domains_by_slug = {c["slug"]: c["domain"] for c in concepts}
    if not concepts:
        print("ERROR: no concepts seeded; run scripts/seed_connection_map_concepts.py")
        return 1

    def _concept_line(c):
        line = f"- {c['slug']} ({c['domain']}): {c['display_clinical']}"
        al = c.get("aliases") or []
        if al:
            # Without these the model sees "exemestane" in the text and has no
            # slug to map it to, so a real side-effect sentence is unusable.
            line += f"  [also written as: {', '.join(al)}]"
        return line

    concept_lines = "\n".join(
        _concept_line(c) for c in sorted(concepts, key=lambda c: (c["domain"], c["slug"])))

    existing = {(e["src_concept_id"], e["dst_concept_id"], e["relationship"])
                for e in (db.table("master_edge")
                          .select("src_concept_id, dst_concept_id, relationship")
                          .execute()).data or []}
    id_to_slug = {c["id"]: c["slug"] for c in concepts}
    existing_triples = {(id_to_slug.get(s), id_to_slug.get(d), r)
                        for s, d, r in existing if s in id_to_slug and d in id_to_slug}

    if args.pass_no == 2:
        return run_pass2(db, args, model, by_slug, concept_lines, existing_triples,
                         domains_by_slug)

    # --- pass 1 -------------------------------------------------------------
    docs = {d["id"]: d for d in (db.table("source_document")
            .select("id, title, scope, cancer, file_path")
            .execute()).data or []}
    # The Phase 3 gate fixture lives in this database; it is not a guideline.
    doc_ids = [i for i, d in docs.items() if "__gate__" not in (d["file_path"] or "")]

    sections = (db.table("source_section")
                .select("id, document_id, section_ref, heading, text")
                .in_("document_id", doc_ids)
                .order("document_id")
                .execute()).data or []
    sections = [s for s in sections
                if MIN_SECTION_CHARS <= len(s["text"]) <= MAX_SECTION_CHARS]

    terms = concept_terms(concepts)
    domain_of = domains_by_slug
    eligible = len(sections)
    ranked = []
    for sec in sections:
        hit = mentions(sec["text"].lower(), terms)
        domains = {domain_of[s] for s in hit}
        can_side_effect = bool(domains & SYMPTOM_SIDE) and bool(domains & TREATMENT_SIDE)
        can_co_occur = len({s for s in hit if domain_of[s] in EXPERIENCE_SIDE}) >= 2
        if can_side_effect or can_co_occur:
            # Rank by how much of BOTH sides is present, not raw count.
            ranked.append((len(hit) + (3 if can_side_effect else 0), sec))
    ranked.sort(key=lambda pair: -pair[0])
    sections = [sec for _, sec in ranked]

    print(f"sections that could state an enabled relationship: "
          f"{len(sections)} of {eligible} eligible")
    if args.limit:
        sections = sections[:args.limit]
    print(f"sections to read: {len(sections)}\n")

    run_id = None
    if not args.dry_run:
        run = (db.table("extraction_run").insert({
            "cancer": args.cancer, "pass_number": 1, "model": model,
            "prompt_id": "pass1_section.md",
        }).execute()).data
        run_id = run[0]["id"] if run else None

    template = load_prompt("pass1_section.md")
    rel_lines = "\n".join(f"- {r}" for r in PASS1_RELATIONSHIPS)

    accepted_total, rejected_all, repaired_total, written = 0, [], 0, 0
    no_answer = 0
    seen_triples = set(existing_triples)
    started = time.time()

    for n, sec in enumerate(sections, 1):
        doc = docs.get(sec["document_id"], {})
        prompt = (template
                  .replace("{relationships}", rel_lines)
                  .replace("{concepts}", concept_lines)
                  .replace("{document_title}", doc.get("title") or "")
                  .replace("{section_ref}", sec["section_ref"])
                  .replace("{section_text}", sec["text"]))
        try:
            raw = together_json(prompt, model)
        except Exception as e:  # noqa: BLE001 - one bad section must not end the run
            print(f"  [{n}/{len(sections)}] {sec['section_ref']}: model error: {e}")
            continue

        ok, bad = validate_pass1(
            parse_model_json(raw), sec["text"],
            by_slug.keys(), PASS1_RELATIONSHIPS, existing_triples=seen_triples,
            concept_domains=domains_by_slug)

        repaired = sum(1 for c in ok if c.get("quote_repaired"))
        repaired_total += repaired
        accepted_total += len(ok)
        rejected_all.extend(bad)

        # A section the model did not ANSWER is a different event from a section
        # that states nothing, and it is the one worth interrupting for.
        unanswered = [r for r in bad
                      if r["reason"] in ("unparsable_response", "no_candidate_list")]
        no_answer += len(unanswered)
        for r in unanswered:
            print(f"  [{n}/{len(sections)}] {sec['section_ref']}: "
                  f"NO ANSWER ({r['reason']}: {r['detail']})")

        if ok:
            print(f"  [{n}/{len(sections)}] {doc.get('title','?')[:38]} {sec['section_ref']}: "
                  f"{len(ok)} accepted, {len(bad)} rejected"
                  + (f", {repaired} re-anchored" if repaired else ""))
        for cand in ok:
            seen_triples.add((cand["src_concept_slug"], cand["dst_concept_slug"],
                              cand["relationship"]))
            print(f"        {cand['src_concept_slug']} --{cand['relationship']}--> "
                  f"{cand['dst_concept_slug']}")
            print(f"          \"{cand['quoted_sentence'][:96]}\"")
            if args.dry_run or not run_id:
                continue
            try:
                db.rpc("insert_master_edge_with_evidence", {
                    "p_edge": {
                        "src_concept_id": by_slug[cand["src_concept_slug"]]["id"],
                        "dst_concept_id": by_slug[cand["dst_concept_slug"]]["id"],
                        "relationship": cand["relationship"],
                        "tier": "A",
                        "candidate_origin": "literature_scan",
                        "extraction_run_id": run_id,
                        "extraction_pass": 1,
                    },
                    "p_evidence": [{
                        "source_section_id": sec["id"],
                        "source_document_id": sec["document_id"],
                        "section_ref": sec["section_ref"],
                        "evidence_kind": "verbatim",
                        "quoted_sentence": cand["quoted_sentence"],
                        "char_offset": cand["char_offset"],
                        "ordinal": 0,
                    }],
                }).execute()
                written += 1
            except Exception as e:  # noqa: BLE001
                print(f"          WRITE FAILED: {str(e)[:140]}")

    elapsed = time.time() - started
    print("\n" + "=" * 62)
    print(f"sections read      {len(sections)}")
    print(f"candidates accepted {accepted_total}")
    print(f"  re-anchored       {repaired_total}  (stored the source's own words)")
    print(f"written to review   {written}{'  (dry run)' if args.dry_run else ''}")
    print(f"sections unanswered {no_answer}  (model did not answer; NOT 'states nothing')")
    print(f"rejected            {len(rejected_all)}")
    for reason, count in rejection_summary(rejected_all).items():
        print(f"  {reason:22} {count}")
    print(f"elapsed             {elapsed:.0f}s")
    if run_id:
        db.table("extraction_run").update({
            "finished_at": "now()",
            "stats": {"sections": len(sections), "accepted": accepted_total,
                      "written": written, "repaired": repaired_total,
                      "unanswered": no_answer,
                      "rejected": rejection_summary(rejected_all)},
        }).eq("id", run_id).execute()
    return 0


def run_pass2(db, args, model, by_slug, concept_lines, existing_triples,
              domains_by_slug) -> int:
    """Chain verified quotations across sections (§6.2). Never introduces a
    quotation: it may only cite evidence pass 1 already verified."""
    evidence = (db.table("master_edge_evidence")
                .select("id, quoted_sentence, section_ref, master_edge_id")
                .execute()).data or []
    if len(evidence) < 2:
        print("pass 2 needs at least two verified quotations; run pass 1 first")
        return 1

    quote_lines = "\n".join(
        f"- id={e['id']} ({e['section_ref']}): \"{e['quoted_sentence']}\""
        for e in evidence)
    existing_lines = "\n".join(f"- {s} --{r}--> {d}" for s, d, r in sorted(existing_triples)) or "(none)"

    prompt = (load_prompt("pass2_chain.md")
              .replace("{relationships}", "\n".join(f"- {r}" for r in RELATIONSHIP_TYPES))
              .replace("{concepts}", concept_lines)
              .replace("{existing}", existing_lines)
              .replace("{quotations}", quote_lines))

    print(f"chaining over {len(evidence)} verified quotations")
    raw = together_json(prompt, model, max_tokens=3000)
    ok, bad = validate_pass2(parse_model_json(raw), [e["id"] for e in evidence],
                             by_slug.keys(), RELATIONSHIP_TYPES,
                             existing_triples=existing_triples,
                             concept_domains=domains_by_slug)

    print(f"\nchains accepted {len(ok)}, rejected {len(bad)}")
    for reason, count in rejection_summary(bad).items():
        print(f"  {reason:22} {count}")
    for c in ok:
        print(f"\n  {c['src_concept_slug']} --{c['relationship']}--> {c['dst_concept_slug']}")
        print(f"    {c['reasoning'][:140]}")
        print(f"    cites {len(c['evidence_ids'])} quotations")

    if args.dry_run:
        print("\n(dry run: nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
