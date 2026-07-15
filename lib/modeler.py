# modeler.py
"""
The Modeler — the per-patient connections layer (lifecycle Push 2).

A background reasoning pass (DeepSeek-V4-Pro via get_model("modeler")) over one
patient's longitudinal record producing, in raw_profile['connections']:

  edges         typed links (treatment<->symptom observed, biomarker->therapy
                guideline-derived, ...) with mandatory evidence references
  expectations  internal predictions with time windows + machine-checkable
                specs; their hits/misses against later patient_events form the
                self-calibration loop
  reflections   higher-level synthesized facts; when active they enter the
                pending-confirmation queue (NEVER self-commit)
  calibration   hit/miss/expired counters (the flip-gate metric)

Flags (env-direct, default false — NEVER feature_enabled(), which defaults true):
  FEATURE_MODELER         compute + store + report/graph endpoint  (shadow)
  FEATURE_MODELER_ACTIVE  the three consumers go live (implies MODELER)

Invariants
----------
- De-identify before the LLM: the payload passes through lib/deidentify helpers
  and EVERY timestamp is rendered as a relative day offset ("T-12d") — the PII
  leak guard flags full ISO dates by design. detect_pii_leaks runs on the
  patient-derived sections (never the public guideline excerpts); any hit
  aborts the run.
- Every edge/expectation/resolution/reflection must cite evidence that resolves
  to the input index; cycle/timing expectations additionally require
  treatment-timeline evidence. Violating items are dropped item-wise.
- The LLM can propose `hypothesis` and refutations; `corroborated` is COMPUTED
  (times_seen >= 2 AND evidence spans >= 2 kinds), never minted by the model.
- No prognosis / survival / outcome-probability statements (prompt + validator).
- Failed runs never advance the watermark; merge is identity-keyed, so
  duplicate cron deliveries are harmless (idempotent).
- No PHI/PII in logs — counts and types only.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("modeler")

CONNECTIONS_VERSION = 1

# Debounce gates (locked decisions)
MIN_NEW_EVENTS = 3
MIN_RUN_INTERVAL_HOURS = 1
MAX_RUNS_PER_DAY = 2

# Caps
EDGE_CAP = 50
OPEN_EXPECTATION_CAP = 10
RESOLVED_EXPECTATION_KEEP = 30
REFLECTION_CAP = 20
EVIDENCE_PER_ITEM_CAP = 5
PER_RUN_EDGE_CAP = 8
PER_RUN_EXPECTATION_CAP = 4
PER_RUN_REFLECTION_CAP = 3
MAX_WINDOW_DAYS = 180
CALIBRATION_HISTORY_CAP = 20

# Input assembly
TIMELINE_TAIL_DAYS = 60
TIMELINE_EVENT_LIMIT = 120
CONVERSATION_TURNS = 30
CONVERSATION_CHARS_PER_TURN = 200
GUIDELINE_TOP_K = 6

LLM_TIMEOUT_S = 45
LLM_MAX_TOKENS = 3500   # 2500 truncated rich-profile outputs mid-JSON (go-live seed run)
LLM_TEMPERATURE = 0.2

# Event kinds excluded from the Modeler's timeline AND (because the debounce
# counts post-filter) from the MIN_NEW_EVENTS gate: shadow bookkeeping and
# high-volume trials-browsing telemetry carry no longitudinal signal.
# trial_feedback (saves/removes) IS ingested — a saved trial is real signal.
_EXCLUDED_EVENT_KINDS = ("shadow_extraction", "trials_shown")

VALID_RELS = (
    "causes", "exacerbates", "relieves", "indicates",
    "supports_therapy", "contraindicates", "temporal_assoc",
)
VALID_NODE_TYPES = ("treatment", "symptom", "biomarker", "condition", "therapy_option", "finding")

# Prognosis vocabulary the validator rejects anywhere in generated statements.
_PROGNOSIS_TERMS = ("survival", "prognosis", "life expectancy", "mortality",
                    "chance of dying", "will be cured", "terminal")

_TIMING_WORDS = re.compile(r"\bcycle|\bweek|\bday|\bmonth", re.IGNORECASE)


def modeler_enabled() -> bool:
    return os.getenv("FEATURE_MODELER", "false").lower() == "true"


def modeler_active() -> bool:
    return modeler_enabled() and os.getenv("FEATURE_MODELER_ACTIVE", "false").lower() == "true"


def _now() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime) -> str:
    return dt.isoformat() + "Z"


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "").split("+")[0]
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def relativize(ts: Any, now: datetime) -> str:
    """ISO timestamp -> guard-safe relative day offset ("T-12d" / "T+6d")."""
    dt = _parse_ts(ts)
    if dt is None:
        return "T-?"
    days = (now - dt).days
    return f"T-{days}d" if days >= 0 else f"T+{-days}d"


def absolutize_window(opens_in_days: int, closes_in_days: int, now: datetime) -> Dict[str, str]:
    return {
        "opens": _iso(now + timedelta(days=int(opens_in_days))),
        "closes": _iso(now + timedelta(days=int(closes_in_days))),
    }


def ensure_connections(profile: dict) -> dict:
    connections = profile.setdefault("connections", {})
    connections.setdefault("version", CONNECTIONS_VERSION)
    connections.setdefault("meta", {
        "last_run_at": None, "watermark": None,
        "runs": {"date": None, "count": 0},
        "last_run_status": None, "model": None, "run_count": 0,
    })
    connections.setdefault("edges", [])
    connections.setdefault("expectations", [])
    connections.setdefault("reflections", [])
    connections.setdefault("calibration", {
        "hits": 0, "misses": 0, "expired": 0, "open": 0,
        "hit_rate": None, "by_basis": {}, "history": [],
    })
    return connections


def should_run(connections: dict, new_event_count: int, now: datetime) -> Tuple[bool, str]:
    """Debounce gates: >=3 new events, >=1h since last run, <=2 runs/day."""
    if new_event_count < MIN_NEW_EVENTS:
        return False, "min_events"
    meta = connections.get("meta") or {}
    last_run = _parse_ts(meta.get("last_run_at"))
    if last_run and (now - last_run) < timedelta(hours=MIN_RUN_INTERVAL_HOURS):
        return False, "min_interval"
    runs = meta.get("runs") or {}
    if runs.get("date") == now.strftime("%Y-%m-%d") and int(runs.get("count", 0)) >= MAX_RUNS_PER_DAY:
        return False, "daily_cap"
    return True, "due"


# ---------------------------------------------------------------------------
# Input assembly
# ---------------------------------------------------------------------------

def build_guideline_query(profile: dict) -> str:
    """Retrieval query from the patient's regimen + symptoms + biomarkers."""
    parts: List[str] = []
    for tx in (profile.get("treatments") or [])[:3]:
        if isinstance(tx, dict) and tx.get("regimen"):
            parts.append(str(tx["regimen"]))
    parts.extend(str(s) for s in (profile.get("symptoms") or [])[:4])
    biomarkers = (profile.get("primaryDiagnosis") or {}).get("biomarkers") or {}
    parts.extend(f"{k} {v}" for k, v in list(biomarkers.items())[:3] if v)
    parts.append("expected side effects timing monitoring")
    return " ".join(parts)


def _belief_digest(profile: dict, now: datetime) -> str:
    """Compact belief-status lines; PII paths skipped or reduced."""
    skip_paths = ("patient.zipCode", "patient.firstName", "meta.")
    lines: List[str] = []
    for path, entry in sorted(((profile.get("beliefs") or {}).get("fields") or {}).items()):
        if any(path == p or path.startswith(p) for p in skip_paths):
            continue
        value = entry.get("value")
        if isinstance(value, dict):
            value = json.dumps({k: v for k, v in value.items() if k not in ("startDate",)})
        lines.append(f"- {path} = {value} ({entry.get('status')}, conf {entry.get('confidence')})")
        if len(lines) >= 40:
            break
    return "\n".join(lines) or "(no beliefs recorded yet)"


def assemble_modeler_input(profile: dict, events: List[dict], screenings: Dict[str, list],
                           excerpts: List[str], chunks: List[dict],
                           connections: dict, now: datetime,
                           ) -> Tuple[str, Dict[str, str], Set[str]]:
    """
    Build the payload string, the guard components (patient-derived sections
    only), and the evidence index (E*/C*/G* ids + belief paths) the validator
    resolves references against. All timestamps relativized.
    """
    from deidentify import deidentify_raw_profile

    safe_profile = deidentify_raw_profile(profile)
    summary = (
        "PATIENT SUMMARY (de-identified)\n"
        f"Diagnosis: {json.dumps((safe_profile.get('primaryDiagnosis') or {}))}\n"
        f"Treatments: {json.dumps(safe_profile.get('treatments') or [])}\n"
        f"Symptoms: {json.dumps(safe_profile.get('symptoms') or [])}\n"
        "BELIEFS\n" + _belief_digest(profile, now)
    )

    timeline_lines: List[str] = []
    index: Set[str] = set()
    for i, e in enumerate(events, 1):
        eid = f"E{i}"
        index.add(eid)
        payload = e.get("payload") or {}
        compact = {k: v for k, v in payload.items() if k not in ("decisions",)}
        timeline_lines.append(
            f"{eid} [{relativize(e.get('recorded_at'), now)}] {e.get('kind')}"
            f"{' ' + str(e.get('path')) if e.get('path') else ''} {json.dumps(compact)[:220]}"
        )
    timeline = "TIMELINE (newest first)\n" + ("\n".join(timeline_lines) or "(no events)")

    screening_lines = []
    for instrument, series in (screenings or {}).items():
        pts = ", ".join(
            f"({relativize(p.get('completed_at'), now)}, {p.get('total_score')}, {p.get('severity_label')})"
            for p in series[-8:]
        )
        screening_lines.append(f"- {instrument}: {pts}")
    screening = "SCREENING SERIES\n" + ("\n".join(screening_lines) or "(none)")

    convo_lines = []
    for i, text in enumerate(excerpts, 1):
        cid = f"C{i}"
        index.add(cid)
        convo_lines.append(f"{cid} {text}")
    conversation = "RECENT CONVERSATION (de-identified excerpts)\n" + ("\n".join(convo_lines) or "(none)")

    guideline_lines = []
    for i, chunk in enumerate(chunks, 1):
        gid = f"G{i}"
        index.add(gid)
        ref = f"{chunk.get('filename')}#chunk{chunk.get('chunk_index')}"
        guideline_lines.append(f"{gid} [{ref}] {(chunk.get('content') or '')[:400]}")
    guidelines = "GUIDELINE EXCERPTS (public corpus)\n" + ("\n".join(guideline_lines) or "(none)")

    # Belief paths are citable evidence too.
    index.update(((profile.get("beliefs") or {}).get("fields") or {}).keys())

    graph_render = render_current_graph(connections, now)

    payload = "\n\n".join([summary, timeline, screening, conversation, guidelines,
                           "CURRENT GRAPH\n" + graph_render])
    guard_components = {
        "patient_summary": summary,
        "timeline": timeline,
        "screening": screening,
        "conversation": conversation,
        # guidelines deliberately excluded — public corpus (chat-route parity)
    }
    return payload, guard_components, index


def render_current_graph(connections: dict, now: datetime) -> str:
    lines: List[str] = []
    for e in (connections.get("edges") or [])[:EDGE_CAP]:
        lines.append(f"- edge {e.get('id')} [{e.get('status')}, strength {e.get('strength')}]")
    for x in connections.get("expectations") or []:
        if x.get("status") == "open":
            window = x.get("window") or {}
            lines.append(
                f"- OPEN expectation {x.get('id')}: {x.get('statement')} "
                f"(window {relativize(window.get('opens'), now)}..{relativize(window.get('closes'), now)})"
            )
    return "\n".join(lines) or "(empty — first run)"


# ---------------------------------------------------------------------------
# LLM call + strict parsing
# ---------------------------------------------------------------------------

_MODELER_SYSTEM_PROMPT = """You are an internal clinical-reasoning engine for an oncology support app.
You analyze ONE patient's longitudinal record and maintain their connections graph.
Your output is NEVER shown to the patient. Respond with JSON only.

TASKS
1. EDGES — propose/update typed links between this patient's treatments, symptoms,
   biomarkers, and conditions. rel must be one of:
   causes | exacerbates | relieves | indicates | supports_therapy | contraindicates | temporal_assoc
2. EXPECTATIONS — internal predictions with day-offset windows and a machine-checkable
   check spec. Optionally include an "ask" (register-matched question topic phrasing,
   containing NO patient-specific values).
3. RESOLUTIONS — for OPEN expectations listed in CURRENT GRAPH, propose outcome
   hit or miss ONLY if a specific timeline item supports it.
4. REFLECTIONS — higher-level facts synthesized from scattered data, each with a
   rationale and optionally a proposed_belief {"path", "value"}.

HARD RULES
- Every edge, expectation, resolution, and reflection MUST cite >=1 evidence id from
  the input (E*, C*, G*, or an exact belief path). No evidence -> omit the item.
- Cycle- or timing-based expectations REQUIRE treatment-timeline evidence (an E* item
  or belief path showing the regimen and its timing). Never infer timing from symptoms alone.
- NO prognosis, survival, mortality, or outcome-probability statements anywhere.
- Do not restate existing corroborated edges unless their status or strength should change.
- Windows are day offsets from today: {"opens_in_days": int >= 0, "closes_in_days": int > opens, <= 180}.
- Limits per run: <= 8 edges, <= 4 new expectations, <= 3 reflections.

OUTPUT SHAPE (exactly):
{"edges": [{"src": {"type","key","label"}, "rel", "dst": {"type","key","label"},
            "status": "hypothesis" | "refuted", "strength": 0..1,
            "evidence": [{"kind": "event"|"guideline"|"belief"|"conversation", "ref": "<id>", "note": "<=15 words"}]}],
 "expectations": {"open": [{"statement", "basis": "guideline"|"observed_pattern",
                            "opens_in_days", "closes_in_days",
                            "check": {"kind", "path_prefix"?, "payload_field"?, "op": "gte"|"lte"|"eq"?, "value"?},
                            "ask": {"plain", "technical"}?,
                            "evidence": [...]}],
                  "resolve": [{"id", "outcome": "hit"|"miss", "evidence": [...]}]},
 "reflections": [{"statement", "rationale", "proposed_belief": {"path", "value"}?,
                  "evidence": [...]}]}
"""


def call_modeler_llm(payload: str) -> Optional[dict]:
    """One V4-Pro call, JSON mode, no Groq fallback (quality > availability here)."""
    from llm_utils import get_together_client
    from model_registry import get_model

    client = get_together_client()
    if not client:
        logger.warning("Modeler: Together client unavailable")
        return None
    kwargs = dict(
        model=get_model("modeler"),
        messages=[{"role": "system", "content": _MODELER_SYSTEM_PROMPT},
                  {"role": "user", "content": payload}],
        response_format={"type": "json_object"},
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    try:
        try:
            response = client.chat.completions.create(timeout=LLM_TIMEOUT_S, **kwargs)
        except TypeError:
            response = client.chat.completions.create(**kwargs)
        if response and response.choices:
            content = (response.choices[0].message.content or "").strip()
            # Some runs wrap the JSON in markdown fences despite json mode.
            if content.startswith("```"):
                content = content.split("```", 2)[1]
                content = content[4:] if content.startswith("json") else content
            # Truncated output (hit max_tokens) parses as garbage — detect and
            # log distinctly so the run event tells the real story.
            finish = getattr(response.choices[0], "finish_reason", None)
            if finish == "length":
                logger.warning("Modeler output truncated at max_tokens; run rejected")
                return None
            return json.loads(content or "{}")
    except Exception as e:
        logger.warning(f"Modeler LLM call failed ({type(e).__name__})")
    return None


def _valid_evidence(items: Any, index: Set[str]) -> Optional[List[dict]]:
    """Validate + normalize an evidence list; None when invalid/empty."""
    if not isinstance(items, list) or not items:
        return None
    out = []
    for ev in items[:EVIDENCE_PER_ITEM_CAP]:
        if not isinstance(ev, dict):
            return None
        ref = str(ev.get("ref") or "").strip()
        kind = str(ev.get("kind") or "").strip()
        if not ref or ref not in index:
            return None
        out.append({"kind": kind or "event", "ref": ref, "note": str(ev.get("note") or "")[:120]})
    return out


def _has_prognosis_language(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in _PROGNOSIS_TERMS)


def _evidence_has_treatment_timeline(evidence: List[dict], index: Set[str]) -> bool:
    """Timing expectations need at least one event/belief evidence touching treatments."""
    for ev in evidence:
        if ev["ref"].startswith("E") or ev["ref"].startswith("treatments."):
            return True
    return False


def parse_modeler_output(raw: Any, index: Set[str]) -> Tuple[dict, Dict[str, int]]:
    """
    Strict, item-wise validation. Returns (ops, rejects) where ops =
    {edges:[], expectations_open:[], expectations_resolve:[], reflections:[]}.
    Individually invalid items are dropped and counted; a non-dict raw input
    yields empty ops (the caller treats that as a rejected run).
    """
    rejects: Dict[str, int] = {"edges": 0, "expectations": 0, "resolutions": 0, "reflections": 0}
    ops = {"edges": [], "expectations_open": [], "expectations_resolve": [], "reflections": []}
    if not isinstance(raw, dict):
        return ops, rejects

    for e in (raw.get("edges") or [])[:PER_RUN_EDGE_CAP]:
        try:
            src, dst = e["src"], e["dst"]
            rel = e["rel"]
            if rel not in VALID_RELS:
                raise ValueError("rel")
            if src.get("type") not in VALID_NODE_TYPES or dst.get("type") not in VALID_NODE_TYPES:
                raise ValueError("node type")
            status = e.get("status", "hypothesis")
            if status not in ("hypothesis", "refuted"):   # model can't mint corroborated
                raise ValueError("status")
            evidence = _valid_evidence(e.get("evidence"), index)
            if evidence is None:
                raise ValueError("evidence")
            if status == "refuted" and not any(ev["ref"].startswith("E") for ev in evidence):
                raise ValueError("refuted needs event evidence")
            strength = max(0.0, min(1.0, float(e.get("strength", 0.5))))
            label_text = f"{src.get('label', '')} {dst.get('label', '')}"
            if _has_prognosis_language(label_text):
                raise ValueError("prognosis")
            ops["edges"].append({
                "src": {"type": src["type"], "key": str(src.get("key") or src.get("label")),
                        "label": str(src.get("label"))[:60]},
                "rel": rel,
                "dst": {"type": dst["type"], "key": str(dst.get("key") or dst.get("label")),
                        "label": str(dst.get("label"))[:60]},
                "status": status, "strength": strength, "evidence": evidence,
            })
        except (KeyError, TypeError, ValueError):
            rejects["edges"] += 1

    expectations = raw.get("expectations") or {}
    for x in (expectations.get("open") or [])[:PER_RUN_EXPECTATION_CAP]:
        try:
            statement = str(x["statement"])[:200]
            if _has_prognosis_language(statement):
                raise ValueError("prognosis")
            basis = x.get("basis")
            if basis not in ("guideline", "observed_pattern"):
                raise ValueError("basis")
            opens, closes = int(x["opens_in_days"]), int(x["closes_in_days"])
            if not (0 <= opens < closes <= MAX_WINDOW_DAYS):
                raise ValueError("window")
            evidence = _valid_evidence(x.get("evidence"), index)
            if evidence is None:
                raise ValueError("evidence")
            if _TIMING_WORDS.search(statement) and not _evidence_has_treatment_timeline(evidence, index):
                raise ValueError("timing without treatment evidence")
            check = x.get("check") if isinstance(x.get("check"), dict) else {}
            ask = x.get("ask") if isinstance(x.get("ask"), dict) else None
            if ask and not (ask.get("plain") and ask.get("technical")):
                ask = None
            ops["expectations_open"].append({
                "statement": statement, "basis": basis,
                "opens_in_days": opens, "closes_in_days": closes,
                "check": {k: check[k] for k in ("kind", "path_prefix", "payload_field", "op", "value")
                          if k in check},
                "ask": ({"plain": str(ask["plain"])[:160], "technical": str(ask["technical"])[:160]}
                        if ask else None),
                "evidence": evidence,
            })
        except (KeyError, TypeError, ValueError):
            rejects["expectations"] += 1

    for r in expectations.get("resolve") or []:
        try:
            outcome = r["outcome"]
            if outcome not in ("hit", "miss"):
                raise ValueError("outcome")
            evidence = _valid_evidence(r.get("evidence"), index)
            if evidence is None or not any(ev["ref"].startswith("E") for ev in evidence):
                raise ValueError("resolution needs event evidence")
            ops["expectations_resolve"].append({
                "id": str(r["id"]), "outcome": outcome, "evidence": evidence,
            })
        except (KeyError, TypeError, ValueError):
            rejects["resolutions"] += 1

    for r in (raw.get("reflections") or [])[:PER_RUN_REFLECTION_CAP]:
        try:
            statement = str(r["statement"])[:200]
            if _has_prognosis_language(statement):
                raise ValueError("prognosis")
            evidence = _valid_evidence(r.get("evidence"), index)
            if evidence is None:
                raise ValueError("evidence")
            proposed = r.get("proposed_belief")
            if proposed is not None:
                if not (isinstance(proposed, dict) and proposed.get("path") and
                        str(proposed["path"]).split(".")[0] in
                        ("patient", "primaryDiagnosis", "treatments", "symptoms")):
                    raise ValueError("proposed_belief")
                proposed = {"path": str(proposed["path"]), "value": proposed.get("value")}
            ops["reflections"].append({
                "statement": statement,
                "rationale": str(r.get("rationale") or "")[:300],
                "proposed_belief": proposed,
                "evidence": evidence,
            })
        except (KeyError, TypeError, ValueError):
            rejects["reflections"] += 1

    return ops, rejects


# ---------------------------------------------------------------------------
# Merge + calibration (pure code — the LLM never mutates the graph directly)
# ---------------------------------------------------------------------------

def _edge_id(src_key: str, rel: str, dst_key: str) -> str:
    from patient_model import _slug
    return f"{_slug(src_key)}--{rel}--{_slug(dst_key)}"


def _resolve_evidence_refs(evidence: List[dict], events: List[dict], chunks: List[dict]) -> List[dict]:
    """Map E*/G* refs to durable references for storage."""
    out = []
    for ev in evidence:
        ref = ev["ref"]
        durable = ref
        if ref.startswith("E"):
            try:
                event = events[int(ref[1:]) - 1]
                durable = f"event:{event.get('kind')}@{event.get('recorded_at')}"
            except (ValueError, IndexError):
                pass
        elif ref.startswith("G"):
            try:
                chunk = chunks[int(ref[1:]) - 1]
                durable = f"guideline:{chunk.get('filename')}#chunk{chunk.get('chunk_index')}"
            except (ValueError, IndexError):
                pass
        elif ref.startswith("C"):
            durable = "conversation"
        out.append({"kind": ev["kind"], "ref": durable, "note": ev.get("note", "")})
    return out


def _evidence_kinds(evidence: List[dict]) -> Set[str]:
    return {ev.get("kind", "") for ev in evidence}


def merge_graph(connections: dict, ops: dict, events: List[dict], chunks: List[dict],
                now: datetime) -> Dict[str, int]:
    """Apply validated ops to the graph. Returns delta counters."""
    edges = connections["edges"]
    by_id = {e["id"]: e for e in edges}
    deltas = {"new_edges": 0, "updated_edges": 0, "expectations_opened": 0}
    now_iso = _iso(now)

    for op in ops["edges"]:
        eid = _edge_id(op["src"]["key"], op["rel"], op["dst"]["key"])
        durable_evidence = _resolve_evidence_refs(op["evidence"], events, chunks)
        existing = by_id.get(eid)
        if existing:
            existing["strength"] = round(max(0.0, min(1.0,
                0.7 * float(existing.get("strength", 0.5)) + 0.3 * op["strength"])), 3)
            existing["times_seen"] = int(existing.get("times_seen", 1)) + 1
            seen_refs = {ev["ref"] for ev in existing.get("evidence", [])}
            for ev in durable_evidence:
                if ev["ref"] not in seen_refs and len(existing["evidence"]) < EVIDENCE_PER_ITEM_CAP:
                    existing["evidence"].append(ev)
                    seen_refs.add(ev["ref"])
            existing["last_updated"] = now_iso
            if op["status"] == "refuted":
                existing["status"] = "refuted"
            elif (existing["status"] == "hypothesis"
                  and existing["times_seen"] >= 2
                  and len(_evidence_kinds(existing["evidence"])) >= 2):
                existing["status"] = "corroborated"
            deltas["updated_edges"] += 1
        else:
            edge = {
                "id": eid, "src": op["src"], "rel": op["rel"], "dst": op["dst"],
                "status": op["status"] if op["status"] == "refuted" else "hypothesis",
                "strength": round(op["strength"], 3),
                "evidence": durable_evidence,
                "first_seen": now_iso, "last_updated": now_iso, "times_seen": 1,
            }
            edges.append(edge)
            by_id[eid] = edge
            deltas["new_edges"] += 1

    # Prune at cap: refuted first, then weakest, then stalest.
    if len(edges) > EDGE_CAP:
        status_weight = {"refuted": 0, "hypothesis": 1, "corroborated": 2}
        edges.sort(key=lambda e: (status_weight.get(e.get("status"), 1),
                                  float(e.get("strength", 0)),
                                  str(e.get("last_updated", ""))), reverse=True)
        del edges[EDGE_CAP:]

    # New expectations (dedupe by statement slug vs open ones).
    from patient_model import _slug
    open_slugs = {_slug(x["statement"])[:60] for x in connections["expectations"]
                  if x.get("status") == "open"}
    open_count = sum(1 for x in connections["expectations"] if x.get("status") == "open")
    for op in ops["expectations_open"]:
        slug = _slug(op["statement"])[:60]
        if slug in open_slugs or open_count >= OPEN_EXPECTATION_CAP:
            continue
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": exp_id,
            "statement": op["statement"], "basis": op["basis"],
            "evidence": _resolve_evidence_refs(op["evidence"], events, chunks),
            "window": absolutize_window(op["opens_in_days"], op["closes_in_days"], now),
            "check": op["check"],
            "status": "open", "created_at": _iso(now),
            "resolved_at": None, "resolution_evidence": None,
        }
        if op.get("ask"):
            entry["ask"] = {"topic": f"exp:{exp_id}", **op["ask"]}
        connections["expectations"].append(entry)
        open_slugs.add(slug)
        open_count += 1
        deltas["expectations_opened"] += 1

    return deltas


def _check_matches_event(check: dict, event: dict) -> bool:
    """Deterministic expectation matcher against one event."""
    if not check or check.get("kind") != event.get("kind"):
        return False
    prefix = check.get("path_prefix")
    if prefix and not str(event.get("path") or "").startswith(prefix):
        return False
    field = check.get("payload_field")
    if field:
        value = (event.get("payload") or {}).get(field)
        if value is None:
            return False
        op = check.get("op", "gte")
        try:
            value_num, target = float(value), float(check.get("value", 0))
            return {"gte": value_num >= target, "lte": value_num <= target,
                    "eq": value_num == target}.get(op, False)
        except (TypeError, ValueError):
            return str(value).lower() == str(check.get("value", "")).lower()
    return True


def check_expectations(connections: dict, new_events: List[dict], resolutions: List[dict],
                       events_index: List[dict], now: datetime) -> List[dict]:
    """
    Resolve open expectations via (1) the deterministic matcher, (2) verified
    LLM resolutions, (3) expiry. Returns resolution records for event emission.
    """
    resolved: List[dict] = []
    calibration = connections["calibration"]
    llm_res_by_id = {r["id"]: r for r in resolutions}

    for exp in connections["expectations"]:
        if exp.get("status") != "open":
            continue
        window = exp.get("window") or {}
        opens, closes = _parse_ts(window.get("opens")), _parse_ts(window.get("closes"))
        outcome = None
        resolution_evidence = None

        # 1. Deterministic matcher over new events inside the window.
        for event in new_events:
            ts = _parse_ts(event.get("recorded_at"))
            if ts and opens and closes and opens <= ts <= closes and \
                    _check_matches_event(exp.get("check") or {}, event):
                outcome = "hit"
                resolution_evidence = f"event:{event.get('kind')}@{event.get('recorded_at')}"
                break

        # 2. Verified LLM resolution (evidence must be an in-window event).
        if outcome is None and exp["id"] in llm_res_by_id:
            res = llm_res_by_id[exp["id"]]
            for ev in res["evidence"]:
                if ev["ref"].startswith("E"):
                    try:
                        event = events_index[int(ev["ref"][1:]) - 1]
                        ts = _parse_ts(event.get("recorded_at"))
                        if ts and opens and closes and opens <= ts <= closes:
                            outcome = res["outcome"]
                            resolution_evidence = f"event:{event.get('kind')}@{event.get('recorded_at')}"
                            break
                    except (ValueError, IndexError):
                        continue

        # 3. Expiry.
        if outcome is None and closes and now > closes:
            outcome = "expired"

        if outcome:
            exp["status"] = outcome
            exp["resolved_at"] = _iso(now)
            exp["resolution_evidence"] = resolution_evidence
            calibration[("hits" if outcome == "hit" else
                         "misses" if outcome == "miss" else "expired")] += 1
            basis_stats = calibration["by_basis"].setdefault(
                exp.get("basis", "unknown"), {"hits": 0, "misses": 0, "expired": 0})
            basis_stats[("hits" if outcome == "hit" else
                         "misses" if outcome == "miss" else "expired")] += 1
            resolved.append({"id": exp["id"], "outcome": outcome,
                             "statement": exp["statement"], "basis": exp.get("basis"),
                             "window": window, "resolution_evidence": resolution_evidence})

    calibration["open"] = sum(1 for x in connections["expectations"] if x.get("status") == "open")
    denominator = calibration["hits"] + calibration["misses"] + calibration["expired"]
    calibration["hit_rate"] = round(calibration["hits"] / denominator, 3) if denominator else None
    if resolved:
        calibration["history"].insert(0, {
            "run_at": _iso(now),
            "resolved": [f"{r['id']}:{r['outcome']}" for r in resolved],
        })
        del calibration["history"][CALIBRATION_HISTORY_CAP:]

    # Trim resolved expectations beyond the keep window (oldest-resolved first).
    resolved_entries = [x for x in connections["expectations"] if x.get("status") != "open"]
    if len(resolved_entries) > RESOLVED_EXPECTATION_KEEP:
        resolved_entries.sort(key=lambda x: str(x.get("resolved_at") or ""))
        drop_ids = {x["id"] for x in resolved_entries[:-RESOLVED_EXPECTATION_KEEP]}
        connections["expectations"] = [x for x in connections["expectations"]
                                       if x["id"] not in drop_ids]
    return resolved


def store_reflections(connections: dict, ops: dict, events: List[dict], chunks: List[dict],
                      now: datetime) -> int:
    """Add validated reflections to the graph JSON (status=proposed). Dedupe by statement."""
    from patient_model import _slug
    existing_slugs = {_slug(r["statement"])[:60] for r in connections["reflections"]}
    added = 0
    for op in ops["reflections"]:
        slug = _slug(op["statement"])[:60]
        if slug in existing_slugs:
            continue
        connections["reflections"].insert(0, {
            "id": f"refl_{uuid.uuid4().hex[:8]}",
            "statement": op["statement"], "rationale": op["rationale"],
            "evidence": _resolve_evidence_refs(op["evidence"], events, chunks),
            "proposed_belief": op["proposed_belief"],
            "status": "proposed", "created_at": _iso(now),
        })
        existing_slugs.add(slug)
        added += 1
    del connections["reflections"][REFLECTION_CAP:]
    return added


def enqueue_reflections(user_id: str, profile: dict, connections: dict) -> int:
    """
    ACTIVE only: route proposed reflections with a proposed_belief through the
    pending-confirmation queue (FORCE-pending regardless of stakes — the
    Modeler may raise its hand but never silently edit the record).
    """
    from patient_model import (
        ReconcileDecision, apply_decisions, get_belief, is_high_stakes, _norm_value,
    )
    queued = 0
    for refl in connections.get("reflections") or []:
        if refl.get("status") != "proposed" or not refl.get("proposed_belief"):
            continue
        path = refl["proposed_belief"]["path"]
        value = refl["proposed_belief"].get("value")
        prior = get_belief(profile, path)
        if prior and prior.get("status") != "invalidated" and \
                _norm_value(prior.get("value")) == _norm_value(value):
            refl["status"] = "confirmed"     # already known — nothing to ask
            continue
        decision = ReconcileDecision(
            path=path, action="PENDING_CONFIRMATION", new_value=value,
            old_value=(prior or {}).get("value"), confidence=0.6,
            source="modeler", reason="modeler_reflection",
            high_stakes=is_high_stakes(path),
        )
        result = apply_decisions(user_id, profile, [decision],
                                 session_id="modeler", shadow=False)
        if any(p.get("path") == path for p in result.pending_confirmations):
            refl["status"] = "queued"
            queued += 1
        # else: queue full — stays 'proposed', retried next run
    return queued


# ---------------------------------------------------------------------------
# Consumers (pure renderers — call sites gate on modeler_active())
# ---------------------------------------------------------------------------

def render_connections_summary(connections: dict, now: datetime,
                               max_edges: int = 3, max_expectations: int = 2) -> Optional[str]:
    """Compact, guard-safe (date-free) summary for the chat prompt block."""
    if not connections:
        return None
    corroborated = sorted(
        (e for e in connections.get("edges") or [] if e.get("status") == "corroborated"),
        key=lambda e: float(e.get("strength", 0)), reverse=True)[:max_edges]
    lines = [f"• {e['src']['label']} ↔ {e['dst']['label']} ({e['rel'].replace('_', ' ')}) — "
             f"seen in this patient's reports" for e in corroborated]
    open_in_window = [
        x for x in connections.get("expectations") or []
        if x.get("status") == "open"
        and (_parse_ts((x.get("window") or {}).get("opens")) or now) <= now
        and now <= (_parse_ts((x.get("window") or {}).get("closes")) or now)
    ][:max_expectations]
    lines.extend(f"• Watching for: {x['statement']}" for x in open_in_window)
    return "\n".join(lines) if lines else None


def expectation_question_candidates(connections: dict, now: datetime) -> List[dict]:
    """Open, in-window expectations with ask blocks — question-policy input."""
    out = []
    for x in connections.get("expectations") or []:
        if x.get("status") != "open" or not x.get("ask"):
            continue
        window = x.get("window") or {}
        opens, closes = _parse_ts(window.get("opens")), _parse_ts(window.get("closes"))
        if opens and closes and opens <= now <= closes:
            out.append({
                "topic": x["ask"]["topic"],
                "importance": 0.55,
                "directive": {"plain": x["ask"]["plain"], "technical": x["ask"]["technical"]},
            })
    return out


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _resolve_slug(user_id: str, profile: dict) -> str:
    """Best-effort cancer slug (mirrors api._resolve_cancer_slug, lib-safe)."""
    try:
        from profile_validator import derive_universal_core
        slug = (derive_universal_core(profile or {}) or {}).get("cancer_slug")
        if slug:
            return slug
    except Exception:
        pass
    try:
        from supabase_storage import get_cancer_slug
        return get_cancer_slug(user_id) or "general"
    except Exception:
        return "general"


def _gather_conversation_excerpts(user_id: str, now: datetime) -> List[str]:
    from deidentify import deidentify_conversation_context
    from supabase_storage import get_conversation_messages, list_conversations

    excerpts: List[str] = []
    conversations = list_conversations(user_id, limit=2)
    turns_remaining = CONVERSATION_TURNS
    for convo in conversations:
        if turns_remaining <= 0:
            break
        messages = get_conversation_messages(user_id, convo["id"], limit=turns_remaining)
        for m in messages[-turns_remaining:]:
            content = deidentify_conversation_context(
                (m.get("content") or "")[:CONVERSATION_CHARS_PER_TURN])
            excerpts.append(f"[{relativize(m.get('created_at'), now)}] {m.get('role')}: {content}")
            turns_remaining -= 1
    return excerpts


def run_for_user(user_id: str, trigger: str = "manual", force: bool = False) -> Dict[str, Any]:
    """
    Execute one Modeler pass. Returns a status dict (counts only — no PHI).
    Failed runs never advance the watermark.
    """
    from deidentify import detect_pii_leaks
    from model_registry import get_model
    from pdf_utils import hybrid_search
    from supabase_storage import (
        append_patient_event, load_all_chunks, load_all_screening_history,
        load_patient_events, load_profile, save_connections,
    )

    if not modeler_enabled():
        return {"status": "disabled"}

    now = _now()
    profile = load_profile(user_id)
    if not profile:
        return {"status": "skipped", "reason": "no_profile"}
    connections = ensure_connections(profile)
    meta = connections["meta"]

    watermark = meta.get("watermark")
    new_events = load_patient_events(user_id, limit=TIMELINE_EVENT_LIMIT, since=watermark) \
        if watermark else load_patient_events(user_id, limit=TIMELINE_EVENT_LIMIT)
    new_events = [e for e in new_events if e.get("kind") not in _EXCLUDED_EVENT_KINDS]

    if not force:
        due, reason = should_run(connections, len(new_events), now)
        if not due:
            return {"status": "skipped", "reason": reason}

    # Context tail: everything in the last 60 days (plus the new events).
    tail_since = _iso(now - timedelta(days=TIMELINE_TAIL_DAYS))
    events = load_patient_events(user_id, limit=TIMELINE_EVENT_LIMIT, since=tail_since)
    events = [e for e in events if e.get("kind") not in _EXCLUDED_EVENT_KINDS]
    seen_ts = {e.get("recorded_at") for e in events}
    events.extend(e for e in new_events if e.get("recorded_at") not in seen_ts)

    screenings = load_all_screening_history(user_id)
    excerpts = _gather_conversation_excerpts(user_id, now)
    try:
        chunks = hybrid_search(build_guideline_query(profile), load_all_chunks(),
                               top_k=GUIDELINE_TOP_K,
                               cancer_types=[_resolve_slug(user_id, profile), "general"])
    except Exception:
        chunks = []

    payload, guard_components, index = assemble_modeler_input(
        profile, events, screenings, excerpts, chunks, connections, now)

    leaks = detect_pii_leaks(guard_components)
    if leaks:
        leak_types = ",".join(sorted({name for name, _s in leaks}))
        logger.warning(f"Modeler payload failed PII guard ({leak_types}); run aborted")
        meta["last_run_status"] = "pii_guard"
        save_connections(user_id, connections)
        return {"status": "error", "reason": "pii_guard"}

    raw = call_modeler_llm(payload)
    if raw is None:
        meta["last_run_status"] = "llm_error"
        save_connections(user_id, connections)
        return {"status": "error", "reason": "llm_error"}

    ops, rejects = parse_modeler_output(raw, index)
    total_ops = sum(len(v) for v in ops.values())
    if total_ops == 0 and sum(rejects.values()) > 0:
        meta["last_run_status"] = "parse_rejected"
        save_connections(user_id, connections)
        return {"status": "error", "reason": "parse_rejected", "rejects": rejects}

    deltas = merge_graph(connections, ops, events, chunks, now)
    resolved = check_expectations(connections, new_events, ops["expectations_resolve"],
                                  events, now)
    reflections_added = store_reflections(connections, ops, events, chunks, now)

    # Bookkeeping + watermark (only on success).
    today = now.strftime("%Y-%m-%d")
    runs = meta.get("runs") or {}
    meta["runs"] = {"date": today,
                    "count": (int(runs.get("count", 0)) + 1) if runs.get("date") == today else 1}
    meta["last_run_at"] = _iso(now)
    meta["last_run_status"] = "ok"
    meta["model"] = get_model("modeler")
    meta["run_count"] = int(meta.get("run_count", 0)) + 1
    if new_events:
        timestamps = sorted(str(e.get("recorded_at")) for e in new_events if e.get("recorded_at"))
        if timestamps:
            meta["watermark"] = timestamps[-1]

    queued = enqueue_reflections(user_id, profile, connections) if modeler_active() else 0

    if not save_connections(user_id, connections):
        return {"status": "error", "reason": "save_failed"}

    run_summary = {
        "status": "ok",
        **deltas,
        "resolved": len(resolved),
        "reflections_added": reflections_added,
        "reflections_queued": queued,
        "rejects": rejects,
        "trigger": trigger,
    }
    append_patient_event(user_id, "modeler_run", payload=run_summary, source="system")
    for r in resolved:
        append_patient_event(user_id, f"expectation_{r['outcome']}",
                             path=f"connections.expectations.{r['id']}",
                             payload={"statement": r["statement"], "basis": r["basis"],
                                      "window": r["window"],
                                      "resolution_evidence": r["resolution_evidence"]},
                             source="system")
    return {"status": "ran", "run": run_summary}
