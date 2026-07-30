#!/usr/bin/env python3
"""Draft the patient-facing wording a physician then reviews (SPEC §8, §5.4).

    python3 scripts/draft_connection_map_wording.py --kind all
    python3 scripts/draft_connection_map_wording.py --kind edges --limit 5 --dry-run
    python3 scripts/draft_connection_map_wording.py --kind concepts --force

Every candidate edge needs a `patient_phrasing` and every concept needs a
`display_patient` before a map can be published (§5.4, and the publication gate
checks both). Extraction produces neither: it reads guidelines, which are written
for clinicians. Without this the reviewer opens the queue to 81 blank wording
fields and has to author every sentence herself on a phone, which is not review,
and §5.4's own mockup shows the wording already drafted when she arrives.

WHAT KEEPS THIS SAFE. Nothing here is trusted. Every string passes
`lint_patient_copy` — the SAME check the publication gate applies — before it is
stored, and anything that fails is reported and left NULL rather than shown to a
physician as a starting point. She then approves, rewrites, or rejects each one.
The model drafts; it does not decide.

Writes only to `status='candidate'` edges. `patient_phrasing` is covered by
`connection_map_edge_hash`, so changing it on a signed edge would void the
attestation; the database refuses that too (2026_08_03), and this never asks.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TOGETHER_API_KEY.
Point at sage-dev with `set -a; . ./.env.development; set +a`.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.review.copy_lint import (  # noqa: E402
    CAUSAL_PATTERNS,
    CONFIDENCE_PATTERNS,
    EM_DASH,
    EN_DASH,
    lint_patient_copy,
)
from model_registry import get_model  # noqa: E402

PROMPTS = _REPO / "config" / "connection_map" / "prompts"

# Concepts are short noun phrases, so several fit in one call without the
# collapse a long prompt produces. Edges get one call each: each carries its own
# evidence, and extraction already showed this model returning the cheapest valid
# answer when a prompt grows.
CONCEPT_BATCH = 10

# A patient-facing name is a phrase, not an explanation. Eight, because
# "numbness or tingling in the hands or feet" is the right answer for peripheral
# neuropathy and a shorter one would be worse.
MAX_CONCEPT_WORDS = 8

# Words a patient would have to look up. The check this backs replaced a much
# blunter one — "reject if the name is unchanged from the clinical term" — which
# was wrong in both directions: §10.1 deliberately names most concepts in plain
# language already ("joint pain", "fatigue", "hot flashes", "mood"), so handing
# the same string back IS the correct answer, and it was rejecting 22 of 39 good
# names, while "HER2 protein status" sailed through because it differed.
#
# An explicit list rather than a cleverer heuristic: it is short, it is auditable,
# and being wrong about a word here costs a blank field the physician fills in,
# not a bad string reaching a patient. She reviews every name regardless.
JARGON = (
    "aromatase", "anthracycline", "taxane", "trastuzumab", "bisphosphonate",
    "denosumab", "neutrophil", "lymphedema", "lymphoedema", "arthralgia",
    "myalgia", "vasomotor", "neuropathy", "axillary", "sentinel", "adjuvant",
    "her2", "lvef", "ki-67", "ki67", "ecog", "erythema", "emesis", "alopecia",
    "dyspnea", "edema", "oedema", "receptor", "biomarker", "prophylaxis",
)


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def together_json(prompt: str, model: str, max_tokens: int = 1200) -> str:
    """One drafting call.

    `enable_thinking: False` for the same reason extraction needs it: this is a
    reasoning model, and with thinking on a longer prompt spends the whole budget
    before emitting a character, which `response_format=json_object` then turns
    into the cheapest valid object rather than an error.
    """
    from together import Together

    client = Together(api_key=os.environ["TOGETHER_API_KEY"])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,   # a little room to phrase naturally; still not writing prose
        response_format={"type": "json_object"},
        chat_template_kwargs={"enable_thinking": False},
    )
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return None
        return None


def concept_problems(phrase: Optional[str], clinical: str = "") -> List[str]:
    """Why a patient-facing concept name is unusable, or [].

    Deliberately NOT lint_patient_copy. That function judges SENTENCES, and its
    readability estimate is undefined on a two-word phrase: Flesch-Kincaid scored
    the entirely correct answer "chemotherapy" at grade 44, because one sentence
    of one five-syllable word is arithmetically off the scale. Running it here
    rejected the good answers and, having no notion of jargon, passed "HER2
    status" unchanged.

    So the §8 rules that apply to a phrase are applied — from copy_lint's own
    pattern tables, so there is still one source of truth for what §8 forbids —
    and the readability estimate is replaced by an explicit jargon list, which is
    what "a patient can read this" actually means for a two-word name.
    """
    if not phrase or not phrase.strip():
        return ["empty"]
    phrase = phrase.strip()
    problems: List[str] = []

    if EM_DASH in phrase or EN_DASH in phrase:
        problems.append("contains a dash; use plain words")
    lowered = phrase.lower()
    for pattern, label in CAUSAL_PATTERNS:
        if re.search(pattern, lowered):
            problems.append(f"contains the causal phrase '{label}'; a name states nothing about cause")
    for pattern in CONFIDENCE_PATTERNS:
        if re.search(pattern, lowered):
            problems.append("expresses confidence or probability; not permitted in patient copy")

    if len(phrase.split()) > MAX_CONCEPT_WORDS:
        problems.append(f"more than {MAX_CONCEPT_WORDS} words; this is a name, not an explanation")
    if phrase.endswith("."):
        problems.append("ends in a full stop; it is a phrase, not a sentence")
    found = [j for j in JARGON if j in lowered]
    if found:
        # The failure this catches is the clinical term handed back untranslated.
        # An identical-but-plain answer ("joint pain") is fine and common.
        problems.append(f"still clinical: {found[0]!r} is a word a patient would look up")
    return problems


def draft_edges(db, model: str, args) -> Dict[str, int]:
    edges = (db.table("master_edge")
             .select("id, src_concept_id, dst_concept_id, relationship, "
                     "patient_phrasing, status")
             .eq("status", "candidate")
             .execute()).data or []
    if not args.force:
        edges = [e for e in edges if not (e.get("patient_phrasing") or "").strip()]
    if args.limit:
        edges = edges[:args.limit]

    concepts = {c["id"]: c for c in (db.table("concept")
                .select("id, slug, display_clinical").execute()).data or []}
    template = load_prompt("patient_wording_edge.md")

    stats = {"drafted": 0, "rejected": 0, "no_answer": 0}
    rejected_detail: List[str] = []
    print(f"edges needing wording: {len(edges)}\n")

    for n, edge in enumerate(edges, 1):
        src = concepts.get(edge["src_concept_id"], {})
        dst = concepts.get(edge["dst_concept_id"], {})
        quotes = (db.table("master_edge_evidence")
                  .select("quoted_sentence")
                  .eq("master_edge_id", edge["id"])
                  .order("ordinal").limit(3).execute()).data or []
        evidence = "\n".join(f"- \"{q['quoted_sentence']}\"" for q in quotes
                             if q.get("quoted_sentence")) or "(no quotation)"

        prompt = (template
                  .replace("{src_display}", src.get("display_clinical", "?"))
                  .replace("{dst_display}", dst.get("display_clinical", "?"))
                  .replace("{relationship}", edge["relationship"])
                  .replace("{evidence}", evidence))
        try:
            raw = together_json(prompt, model)
        except Exception as exc:  # noqa: BLE001 - one bad edge must not end the run
            print(f"  [{n}/{len(edges)}] model error: {exc}")
            stats["no_answer"] += 1
            continue

        parsed = parse_json(raw)
        phrasing = (parsed or {}).get("patient_phrasing") if isinstance(parsed, dict) else None
        if not isinstance(phrasing, str) or not phrasing.strip():
            stats["no_answer"] += 1
            print(f"  [{n}/{len(edges)}] no answer: {raw.strip()[:80]}")
            continue

        phrasing = phrasing.strip()
        problems = lint_patient_copy(phrasing)
        if problems:
            # Never store it, and never show it to the physician as a starting
            # point: a sentence that breaks §8 is exactly what she must not be
            # nudged toward.
            stats["rejected"] += 1
            rejected_detail.append(f"{src.get('slug')} -> {dst.get('slug')}: {problems[0]}")
            print(f"  [{n}/{len(edges)}] REJECTED ({problems[0]})")
            print(f"        \"{phrasing[:100]}\"")
            continue

        stats["drafted"] += 1
        print(f"  [{n}/{len(edges)}] {src.get('slug')} -> {dst.get('slug')}")
        print(f"        \"{phrasing}\"")
        if not args.dry_run:
            db.table("master_edge").update(
                {"patient_phrasing": phrasing}).eq("id", edge["id"]).execute()

    if rejected_detail:
        print("\nrejected by the copy rules:")
        for line in rejected_detail:
            print(f"  {line}")
    return stats


def draft_concepts(db, model: str, args) -> Dict[str, int]:
    rows = (db.table("concept")
            .select("id, slug, domain, display_clinical, display_patient")
            .contains("cancer_scopes", [args.cancer])
            .execute()).data or []

    if not args.all_concepts:
        # Only concepts an actual candidate references. That is exactly what the
        # publication gate requires ("concept X has no display_patient" is raised
        # per edge in the version), and it avoids inventing patient names for
        # terms no patient will ever be shown. On the breast pilot this is 39 of
        # 60 — every biomarker falls out, because RELATIONSHIP_DOMAINS keeps
        # biomarkers off both ends of the two v1 relationships, and "estrogen
        # receptor status" has no honest six-word plain-English name anyway.
        edges = (db.table("master_edge")
                 .select("src_concept_id, dst_concept_id")
                 .eq("status", "candidate").execute()).data or []
        used = {e["src_concept_id"] for e in edges} | {e["dst_concept_id"] for e in edges}
        rows = [c for c in rows if c["id"] in used]

    if not args.force:
        rows = [c for c in rows if not (c.get("display_patient") or "").strip()]
    if args.limit:
        rows = rows[:args.limit]

    by_slug = {c["slug"]: c for c in rows}
    template = load_prompt("patient_wording_concept.md")
    stats = {"drafted": 0, "rejected": 0, "no_answer": 0}
    print(f"concepts needing a patient name: {len(rows)}\n")

    for start in range(0, len(rows), CONCEPT_BATCH):
        batch = rows[start:start + CONCEPT_BATCH]
        listing = "\n".join(
            f"- {c['slug']} ({c['domain']}): {c['display_clinical']}" for c in batch)
        try:
            raw = together_json(template.replace("{concepts}", listing), model)
        except Exception as exc:  # noqa: BLE001
            print(f"  batch {start // CONCEPT_BATCH + 1}: model error: {exc}")
            stats["no_answer"] += len(batch)
            continue

        parsed = parse_json(raw)
        items = (parsed or {}).get("concepts") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            stats["no_answer"] += len(batch)
            print(f"  batch {start // CONCEPT_BATCH + 1}: no answer: {raw.strip()[:80]}")
            continue

        answered = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            slug, phrase = item.get("slug"), item.get("display_patient")
            if slug not in by_slug:
                continue          # a slug we did not ask about
            answered.add(slug)
            problems = concept_problems(phrase)
            if problems:
                stats["rejected"] += 1
                print(f"  REJECTED {slug}: {problems[0]}  ({str(phrase)[:40]!r})")
                continue
            phrase = phrase.strip()
            stats["drafted"] += 1
            print(f"  {slug:32} {by_slug[slug]['display_clinical'][:28]:30} -> {phrase!r}")
            if not args.dry_run:
                db.table("concept").update(
                    {"display_patient": phrase}).eq("id", by_slug[slug]["id"]).execute()
        stats["no_answer"] += len({c["slug"] for c in batch} - answered)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=("edges", "concepts", "all"), default="all")
    ap.add_argument("--limit", type=int, default=0, help="max items (0 = all)")
    ap.add_argument("--cancer", default="breast")
    ap.add_argument("--force", action="store_true",
                    help="redraft wording that already exists")
    ap.add_argument("--all-concepts", action="store_true",
                    help="name every concept, not only those a candidate references")
    ap.add_argument("--dry-run", action="store_true", help="draft and lint, write nothing")
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
    model = get_model("connection_wording")
    print(f"model: {model}   target: {url}")
    print("(drafts only; every string is reviewed by a physician before a patient sees it)\n")

    started = time.time()
    totals = {"drafted": 0, "rejected": 0, "no_answer": 0}
    if args.kind in ("concepts", "all"):
        print("=" * 62 + "\nCONCEPT NAMES\n" + "=" * 62)
        for k, v in draft_concepts(db, model, args).items():
            totals[k] += v
    if args.kind in ("edges", "all"):
        print("\n" + "=" * 62 + "\nCONNECTION WORDING\n" + "=" * 62)
        for k, v in draft_edges(db, model, args).items():
            totals[k] += v

    print("\n" + "=" * 62)
    print(f"drafted and stored  {totals['drafted']}{'  (dry run)' if args.dry_run else ''}")
    print(f"rejected by §8      {totals['rejected']}  (left blank; never shown as a draft)")
    print(f"no answer           {totals['no_answer']}")
    print(f"elapsed             {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
