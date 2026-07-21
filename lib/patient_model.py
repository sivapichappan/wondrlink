# patient_model.py
"""
The patient belief store + extract-and-reconcile pipeline (lifecycle foundation).

Every profile fact becomes a *belief*: {value, confidence, status, source,
timestamps, history}. Beliefs live in raw_profile['beliefs'] so the existing
read path (`load_profile` -> raw_profile) needs no changes. The materialized
profile fields (patient.*, primaryDiagnosis.*, treatments[], symptoms[]) remain
canonical for every existing reader; committing a belief also writes the
materialized field. Facts pending user confirmation live only in
beliefs['pending'] and never touch materialized fields.

Pipeline (wired to /api/chat in shadow mode first, then as the writer):
    extract_facts(message, profile)      regex + LLM candidates, merged
    reconcile(candidates, beliefs)       pure function -> decisions
    apply_decisions(...)                 shadow: events only / live: beliefs + profile

Invariants
----------
- De-identify before any external LLM call (profile context comes from
  llm_utils._extraction_profile_context, which scrubs + PII-guards).
- Provisional facts NEVER silently overwrite confirmed ones.
- High-stakes facts (stage, site, histology, biomarkers, treatments,
  comorbidities) never self-commit from implicit chat mentions; they go to the
  pending-confirmation queue and surface as "is that right?" chips.
- Nothing is destroyed: value changes append to a capped history;
  treatment "removals" materialize as status='completed'.
- No PHI/PII in logs: log paths/actions/counts, never values.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("patient_model")

BELIEFS_VERSION = 1

# Confidence conventions
CONF_FORM = 1.0
CONF_REGEX = 0.95
CONF_LLM_DEFAULT = 0.6
CONF_LLM_MIN, CONF_LLM_MAX = 0.3, 0.9
CONF_COMMIT_FLOOR = 0.5          # below this a new fact is skipped entirely

PENDING_QUEUE_CAP = 3
PENDING_MAX_ATTEMPTS = 3
PENDING_MAX_AGE_DAYS = 14
HISTORY_CAP = 5

EXTRACTOR_TIMEOUT_S = 10

# Paths whose values change clinical behavior (trial matching, guidance).
# Prefix match. These never self-commit from implicit chat mentions.
HIGH_STAKES_PREFIXES: Tuple[str, ...] = (
    "primaryDiagnosis.stage",
    "primaryDiagnosis.site",
    "primaryDiagnosis.histology",
    "primaryDiagnosis.biomarkers.",
    "treatments.",
    "patient.comorbidities.",
)

# Human labels for confirmation prompts (never expose raw dotted paths to users)
_PATH_LABELS = {
    "primaryDiagnosis.stage": "cancer stage",
    "primaryDiagnosis.site": "cancer type",
    "primaryDiagnosis.histology": "tumor type (histology)",
    "patient.age": "age",
    "patient.zipCode": "ZIP code",
    "patient.weight": "weight",
    "patient.firstName": "name",
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_") or "unknown"


def _norm_value(value: Any) -> Any:
    """Normalized form for equality comparison."""
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, dict):
        return {k: _norm_value(v) for k, v in sorted(value.items())}
    return value


def is_high_stakes(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in HIGH_STAKES_PREFIXES)


def path_label(path: str) -> str:
    if path in _PATH_LABELS:
        return _PATH_LABELS[path]
    if path.startswith("primaryDiagnosis.biomarkers."):
        return f"{path.rsplit('.', 1)[-1].upper()} biomarker result"
    if path.startswith("treatments."):
        return "treatment"
    if path.startswith("symptoms."):
        return "symptom"
    if path.startswith("patient.comorbidities."):
        return "health condition"
    return path.rsplit(".", 1)[-1]


# ---------------------------------------------------------------------------
# Belief store accessors
# ---------------------------------------------------------------------------

def ensure_beliefs(profile: dict) -> dict:
    """Return profile['beliefs'], creating the empty structure if absent."""
    beliefs = profile.setdefault("beliefs", {})
    beliefs.setdefault("version", BELIEFS_VERSION)
    beliefs.setdefault("fields", {})
    beliefs.setdefault("pending", [])
    return beliefs


def get_belief(profile: dict, path: str) -> Optional[dict]:
    return (profile.get("beliefs") or {}).get("fields", {}).get(path)


# ---------------------------------------------------------------------------
# Candidate facts + extraction
# ---------------------------------------------------------------------------

@dataclass
class CandidateFact:
    path: str
    value: Any
    confidence: float
    source: str                    # chat_regex | chat_llm | form | screening | system
    polarity: str = "affirm"       # affirm | negate
    evidence: str = ""             # short paraphrase (may quote the user's own words)


@dataclass
class ReconcileDecision:
    path: str
    action: str                    # ADD | UPDATE | INVALIDATE | NOOP | PENDING_CONFIRMATION
    new_value: Any
    old_value: Optional[Any]
    confidence: float
    source: str
    reason: str
    high_stakes: bool = False


@dataclass
class ApplyResult:
    committed_paths: List[str] = field(default_factory=list)
    pending_confirmations: List[dict] = field(default_factory=list)
    events_written: int = 0
    shadow: bool = False


_EXTRACTOR_SYSTEM_PROMPT = """You extract structured medical-profile facts from ONE patient chat message.

Output ONLY a JSON object: {"facts": [ ... ]}. Each fact:
  {"path": "<dotted path>", "value": <value>, "confidence": <0..1>,
   "polarity": "affirm" | "negate", "evidence": "<=12 words from the message"}

Allowed path patterns (use EXACTLY these shapes):
  patient.age                      (integer years)
  patient.firstName                (string)
  patient.zipCode                  (5-digit string)
  patient.weight                   (lbs, number)
  patient.heightFt / patient.heightIn
  patient.race_ethnicity
  patient.ecog                     (0-4)
  patient.comorbidities.<name>     (value: the condition name)
  primaryDiagnosis.site            (cancer type, e.g. "colon", "breast")
  primaryDiagnosis.stage           ("Stage I".."Stage IV")
  primaryDiagnosis.histology
  primaryDiagnosis.biomarkers.<MARKER>   (e.g. KRAS, NRAS, BRAF, MSI, MMR, HER2; value = result)
  treatments.<regimen>             (value: {"regimen": "...", "status": "active|completed|planned", "line": "..."} — include only known keys)
  symptoms.<name>                  (value: the symptom name)

Rules:
- Extract ONLY facts the patient states about THEMSELVES (or, for caregivers, the patient they care for).
- "polarity":"negate" when they say something stopped / is not true ("I'm not on FOLFOX anymore", "the pain is gone").
- Do NOT extract questions, hypotheticals, or facts about other people.
- Do NOT repeat facts already in CURRENT PROFILE unless the message CHANGES them.
- No facts -> {"facts": []}.

CURRENT PROFILE (de-identified):
{current_profile_json}
"""


def _flatten_v1_updates(updates: dict, source: str, confidence: float) -> List[CandidateFact]:
    """Convert the legacy nested-updates dict into CandidateFacts."""
    out: List[CandidateFact] = []
    if not isinstance(updates, dict):
        return out

    patient = updates.get("patient") or {}
    for key, val in patient.items():
        if key == "comorbidities" and isinstance(val, list):
            for c in val:
                out.append(CandidateFact(f"patient.comorbidities.{_slug(c)}", c, confidence, source))
        elif val not in (None, ""):
            out.append(CandidateFact(f"patient.{key}", val, confidence, source))

    dx = updates.get("primaryDiagnosis") or {}
    for key, val in dx.items():
        if key == "biomarkers" and isinstance(val, dict):
            for marker, result in val.items():
                if result not in (None, ""):
                    out.append(CandidateFact(
                        f"primaryDiagnosis.biomarkers.{str(marker).upper()}", result, confidence, source))
        elif val not in (None, ""):
            out.append(CandidateFact(f"primaryDiagnosis.{key}", val, confidence, source))

    for tx in updates.get("treatments") or []:
        if isinstance(tx, dict):
            name = tx.get("regimen") or tx.get("category")
            if name:
                out.append(CandidateFact(f"treatments.{_slug(name)}",
                                         {k: v for k, v in tx.items() if v not in (None, "")},
                                         confidence, source))

    for sym in updates.get("symptoms") or []:
        if isinstance(sym, str) and sym.strip():
            out.append(CandidateFact(f"symptoms.{_slug(sym)}", sym.strip(), confidence, source))

    return out


def _parse_llm_facts(raw: Any) -> List[CandidateFact]:
    out: List[CandidateFact] = []
    facts = raw.get("facts") if isinstance(raw, dict) else None
    if not isinstance(facts, list):
        return out
    for f in facts:
        if not isinstance(f, dict):
            continue
        path = str(f.get("path") or "").strip()
        value = f.get("value")
        if not path or value in (None, ""):
            continue
        # Only accept known path shapes — the model must not invent namespaces.
        if not path.startswith(("patient.", "primaryDiagnosis.", "treatments.", "symptoms.")):
            continue
        # Normalize the identity segment deterministically — the model writes
        # "treatments.FOLFOX" / "symptoms.hotflashes"; belief paths are slugged
        # from the VALUE where it names the thing (it preserves separators the
        # model drops from path segments), and biomarkers are uppercased.
        parts = path.split(".")
        if parts[0] == "treatments" and len(parts) == 2:
            name = value.get("regimen") if isinstance(value, dict) else None
            path = f"treatments.{_slug(str(name) if name else parts[1])}"
        elif parts[0] == "symptoms" and len(parts) == 2:
            name = value if isinstance(value, str) else parts[1]
            path = f"symptoms.{_slug(str(name))}"
        elif parts[:2] == ["patient", "comorbidities"] and len(parts) == 3:
            name = value if isinstance(value, str) else parts[2]
            path = f"patient.comorbidities.{_slug(str(name))}"
        elif parts[:2] == ["primaryDiagnosis", "biomarkers"] and len(parts) == 3:
            path = f"primaryDiagnosis.biomarkers.{parts[2].upper()}"
        try:
            conf = float(f.get("confidence", CONF_LLM_DEFAULT))
        except (TypeError, ValueError):
            conf = CONF_LLM_DEFAULT
        conf = max(CONF_LLM_MIN, min(CONF_LLM_MAX, conf))
        polarity = "negate" if str(f.get("polarity", "affirm")).lower() == "negate" else "affirm"
        out.append(CandidateFact(path, value, conf, "chat_llm", polarity,
                                 str(f.get("evidence") or "")[:120]))
    return out


def extract_facts(message: str, current_profile: dict) -> List[CandidateFact]:
    """
    Regex + LLM extraction, merged (regex wins on path collisions).

    Skips the LLM for very short messages. Never raises — returns what it has.
    """
    from llm_utils import (
        _quick_extract_profile_updates,
        _extraction_profile_context,
        get_together_client,
        get_groq_client,
    )

    candidates: List[CandidateFact] = _flatten_v1_updates(
        _quick_extract_profile_updates(message) or {}, "chat_regex", CONF_REGEX)
    regex_paths = {c.path for c in candidates}

    if len((message or "").strip()) < 15:
        return candidates

    client = get_together_client() or get_groq_client()
    if not client:
        return candidates

    try:
        from model_registry import get_model
        model = get_model("extractor") if get_together_client() else get_model("fallback")
        system = _EXTRACTOR_SYSTEM_PROMPT.replace(
            "{current_profile_json}", _extraction_profile_context(current_profile))
        kwargs = dict(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": message}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        import time as _time
        from ai_gateway import log_llm_call
        _t0 = _time.perf_counter()
        try:
            response = client.chat.completions.create(timeout=EXTRACTOR_TIMEOUT_S, **kwargs)
        except TypeError:
            # SDK without per-request timeout support
            response = client.chat.completions.create(**kwargs)
        log_llm_call("extract",
                     "together" if get_together_client() else "groq",
                     model, int((_time.perf_counter() - _t0) * 1000),
                     usage=getattr(response, "usage", None))
        if response and response.choices:
            parsed = json.loads(response.choices[0].message.content or "{}")
            for cand in _parse_llm_facts(parsed):
                if cand.path not in regex_paths:
                    candidates.append(cand)
    except Exception as e:
        logger.warning(f"LLM fact extraction failed ({type(e).__name__}); regex-only this turn")

    return candidates


def candidates_to_v1_updates(candidates: List[CandidateFact]) -> dict:
    """
    Convert candidate facts back into the legacy nested-updates dict so the v1
    write path (update_profile_with_sources) behaves as before while v2 runs
    in shadow. Reproduces v1's regex-short-circuit semantics: when regex found
    anything, only regex facts are written (v1 skipped the LLM entirely).
    Negations are dropped (v1 had no concept of them).
    """
    regex_facts = [c for c in candidates if c.source == "chat_regex" and c.polarity == "affirm"]
    pool = regex_facts if regex_facts else [c for c in candidates if c.polarity == "affirm"]

    out: dict = {}
    for cand in pool:
        parts = cand.path.split(".")
        if parts[0] == "patient" and len(parts) == 2:
            out.setdefault("patient", {})[parts[1]] = cand.value
        elif parts[:2] == ["patient", "comorbidities"] and len(parts) == 3:
            comorbidities = out.setdefault("patient", {}).setdefault("comorbidities", [])
            name = cand.value if isinstance(cand.value, str) else parts[2]
            if name not in comorbidities:
                comorbidities.append(name)
        elif parts[0] == "primaryDiagnosis" and len(parts) == 2:
            out.setdefault("primaryDiagnosis", {})[parts[1]] = cand.value
        elif parts[:2] == ["primaryDiagnosis", "biomarkers"] and len(parts) == 3:
            out.setdefault("primaryDiagnosis", {}).setdefault("biomarkers", {})[parts[2]] = cand.value
        elif parts[0] == "treatments" and isinstance(cand.value, dict):
            out.setdefault("treatments", []).append(dict(cand.value))
        elif parts[0] == "symptoms":
            name = cand.value if isinstance(cand.value, str) else parts[-1]
            symptoms = out.setdefault("symptoms", [])
            if name not in symptoms:
                symptoms.append(name)
    return out


# ---------------------------------------------------------------------------
# Reconcile (pure — no I/O, no LLM)
# ---------------------------------------------------------------------------

def reconcile(candidates: List[CandidateFact], beliefs: dict) -> List[ReconcileDecision]:
    """Decide what each candidate fact does to the belief store. Pure function."""
    fields = (beliefs or {}).get("fields", {})
    decisions: List[ReconcileDecision] = []

    for cand in candidates:
        prior = fields.get(cand.path)
        prior_value = prior.get("value") if prior else None
        prior_conf = float(prior.get("confidence", 0)) if prior else 0.0
        prior_status = prior.get("status") if prior else None
        stakes = is_high_stakes(cand.path)
        explicit = cand.source in ("chat_regex", "form") and cand.confidence >= 0.9

        def decision(action: str, reason: str) -> ReconcileDecision:
            return ReconcileDecision(
                path=cand.path, action=action, new_value=cand.value,
                old_value=prior_value, confidence=cand.confidence,
                source=cand.source, reason=reason, high_stakes=stakes)

        # Negations invalidate whatever we believed.
        if cand.polarity == "negate":
            if prior and prior_status != "invalidated":
                decisions.append(decision("INVALIDATE", "negation"))
            else:
                decisions.append(decision("NOOP", "negation_without_prior"))
            continue

        if prior is None or prior_status == "invalidated":
            if cand.confidence < CONF_COMMIT_FLOOR:
                decisions.append(decision("NOOP", "low_confidence_skip"))
            elif stakes and not explicit:
                decisions.append(decision("PENDING_CONFIRMATION", "high_stakes_new"))
            else:
                decisions.append(decision("ADD", "no_prior"))
            continue

        if _norm_value(prior_value) == _norm_value(cand.value):
            decisions.append(decision("NOOP", "reinforces_existing"))
            continue

        # Value conflict.
        if prior_status == "confirmed":
            if stakes:
                decisions.append(decision("PENDING_CONFIRMATION", "conflicts_confirmed_high_stakes"))
            elif explicit:
                decisions.append(decision("UPDATE", "explicit_user_change"))
            else:
                decisions.append(decision("PENDING_CONFIRMATION", "conflicts_confirmed"))
            continue

        # Provisional prior.
        if stakes and not explicit:
            decisions.append(decision("PENDING_CONFIRMATION", "high_stakes_change"))
        elif cand.confidence >= prior_conf - 0.1:
            decisions.append(decision("UPDATE", "newer_evidence"))
        else:
            decisions.append(decision("NOOP", "lower_confidence_conflict"))

    return decisions


# ---------------------------------------------------------------------------
# Materialization (beliefs -> canonical profile fields)
# ---------------------------------------------------------------------------

def _materialize(profile: dict, path: str, value: Any, invalidate: bool = False) -> None:
    """Write a committed belief into the canonical profile shape."""
    parts = path.split(".")

    if parts[0] == "treatments" and len(parts) == 2:
        treatments = profile.setdefault("treatments", [])
        key = parts[1]
        for tx in treatments:
            if isinstance(tx, dict) and _slug(tx.get("regimen") or tx.get("category") or "") == key:
                if invalidate:
                    tx["status"] = "completed"      # never delete a treatment record
                elif isinstance(value, dict):
                    tx.update(value)
                return
        if not invalidate and isinstance(value, dict):
            treatments.append(dict(value))
        return

    if parts[0] == "symptoms" and len(parts) == 2:
        symptoms = profile.setdefault("symptoms", [])
        name = value if isinstance(value, str) else parts[1]
        if invalidate:
            profile["symptoms"] = [s for s in symptoms if _slug(str(s)) != parts[1]]
        elif all(_slug(str(s)) != parts[1] for s in symptoms):
            symptoms.append(name)
        return

    if parts[:2] == ["patient", "comorbidities"] and len(parts) == 3:
        patient = profile.setdefault("patient", {})
        comorbidities = patient.setdefault("comorbidities", [])
        name = value if isinstance(value, str) else parts[2]
        if invalidate:
            patient["comorbidities"] = [c for c in comorbidities if _slug(str(c)) != parts[2]]
        elif all(_slug(str(c)) != parts[2] for c in comorbidities):
            comorbidities.append(name)
        return

    # Plain dotted scalar (patient.age, primaryDiagnosis.stage,
    # primaryDiagnosis.biomarkers.KRAS, ...)
    node = profile
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    if invalidate:
        node.pop(parts[-1], None)
    else:
        node[parts[-1]] = value


def _write_belief(beliefs: dict, decision: ReconcileDecision,
                  session_id: Optional[str], status: str) -> None:
    fields = beliefs["fields"]
    now = _now_iso()
    prior = fields.get(decision.path)
    entry = {
        "value": decision.new_value,
        "confidence": decision.confidence,
        "status": status,
        "source": _canonical_source(decision.source),
        "session_id": session_id,
        "first_observed": (prior or {}).get("first_observed", now),
        "last_updated": now,
        "history": list((prior or {}).get("history", [])),
    }
    if status == "confirmed":
        entry["confirmed_at"] = now
    if prior and _norm_value(prior.get("value")) != _norm_value(decision.new_value):
        entry["history"].insert(0, {
            "value": prior.get("value"),
            "status": prior.get("status"),
            "source": prior.get("source"),
            "superseded_at": now,
            "reason": decision.reason,
        })
        entry["history"] = entry["history"][:HISTORY_CAP]
    fields[decision.path] = entry


def _canonical_source(source: str) -> str:
    return {"chat_regex": "chat", "chat_llm": "chat"}.get(source, source)


def _confirmation_prompt(path: str, value: Any) -> str:
    label = path_label(path)
    if isinstance(value, dict):
        pretty = value.get("regimen") or value.get("status") or json.dumps(value)
    else:
        pretty = str(value)
    if path == "primaryDiagnosis.stage":
        return f"It sounds like your cancer may be {pretty}. Did I get that right?"
    if path.startswith("primaryDiagnosis.biomarkers."):
        return f"I noted your {label} as {pretty}. Is that right?"
    if path.startswith("treatments."):
        return f"I noted a treatment update: {pretty}. Is that right?"
    return f"I noted your {label} as {pretty}. Is that right?"


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_decisions(user_id: str, profile: dict, decisions: List[ReconcileDecision],
                    session_id: Optional[str] = None, shadow: bool = False) -> ApplyResult:
    """
    Apply reconcile decisions.

    shadow=True: write ONLY patient_events (kind='shadow_extraction') — the
    profile is untouched (legacy v1 extraction remains the writer).
    shadow=False: mutate beliefs + materialized fields + pending queue, append
    events, and save the profile.
    """
    from supabase_storage import append_patient_event, save_profile

    result = ApplyResult(shadow=shadow)
    if not decisions:
        return result

    if shadow:
        payload = {
            "decisions": [
                {"path": d.path, "action": d.action, "reason": d.reason,
                 "old": d.old_value, "new": d.new_value,
                 "confidence": d.confidence, "high_stakes": d.high_stakes}
                for d in decisions
            ],
        }
        if append_patient_event(user_id, "shadow_extraction", payload=payload,
                                source="chat", session_id=session_id):
            result.events_written += 1
        return result

    beliefs = ensure_beliefs(profile)
    now = _now_iso()
    changed = False

    _expire_pending(beliefs, now)

    for d in decisions:
        if d.action == "NOOP":
            if d.reason == "reinforces_existing":
                prior = beliefs["fields"].get(d.path)
                if prior:
                    prior["confidence"] = max(float(prior.get("confidence", 0)), d.confidence)
                    prior["last_updated"] = now
                    changed = True
            continue

        if d.action in ("ADD", "UPDATE"):
            _write_belief(beliefs, d, session_id, status="provisional")
            _materialize(profile, d.path, d.new_value)
            append_patient_event(user_id, f"belief_{d.action.lower()}", path=d.path,
                                 payload={"old": d.old_value, "new": d.new_value,
                                          "confidence": d.confidence, "reason": d.reason},
                                 source=_canonical_source(d.source), session_id=session_id)
            result.events_written += 1
            result.committed_paths.append(d.path)
            changed = True

        elif d.action == "INVALIDATE":
            prior = beliefs["fields"].get(d.path)
            if prior:
                prior_history = {
                    "value": prior.get("value"), "status": prior.get("status"),
                    "source": prior.get("source"), "superseded_at": now, "reason": d.reason,
                }
                prior["status"] = "invalidated"
                prior["last_updated"] = now
                prior.setdefault("history", []).insert(0, prior_history)
                prior["history"] = prior["history"][:HISTORY_CAP]
            _materialize(profile, d.path, d.old_value, invalidate=True)
            append_patient_event(user_id, "belief_invalidate", path=d.path,
                                 payload={"old": d.old_value, "reason": d.reason},
                                 source=_canonical_source(d.source), session_id=session_id)
            result.events_written += 1
            result.committed_paths.append(d.path)
            changed = True

        elif d.action == "PENDING_CONFIRMATION":
            pending = beliefs["pending"]
            pending[:] = [p for p in pending if p.get("path") != d.path]
            if len(pending) < PENDING_QUEUE_CAP:
                entry = {
                    "id": f"conf_{uuid.uuid4().hex[:12]}",
                    "path": d.path,
                    "proposed_value": d.new_value,
                    "previous_value": d.old_value,
                    "confidence": d.confidence,
                    "prompt": _confirmation_prompt(d.path, d.new_value),
                    "created_at": now,
                    "session_id": session_id,
                    "attempts": 0,
                }
                pending.append(entry)
                append_patient_event(user_id, "pending_created", path=d.path,
                                     payload={"proposed": d.new_value, "reason": d.reason},
                                     source=_canonical_source(d.source), session_id=session_id)
                result.events_written += 1
                changed = True

    result.pending_confirmations = list(beliefs.get("pending", []))

    if changed:
        if not save_profile(user_id, profile):
            logger.error("apply_decisions: save_profile failed")

    return result


def _expire_pending(beliefs: dict, now_iso: str) -> None:
    """Drop pending confirmations that were asked too often or are too old."""
    def alive(p: dict) -> bool:
        if int(p.get("attempts", 0)) >= PENDING_MAX_ATTEMPTS:
            return False
        try:
            created = datetime.fromisoformat(str(p.get("created_at", "")).rstrip("Z"))
            return (datetime.utcnow() - created).days < PENDING_MAX_AGE_DAYS
        except ValueError:
            return True
    beliefs["pending"] = [p for p in beliefs.get("pending", []) if alive(p)]


def confirm_belief(user_id: str, confirmation_id: str, accept: bool) -> Dict[str, Any]:
    """
    Resolve a pending confirmation (the "is that right?" chip).

    accept=True  -> belief committed as confirmed + materialized.
    accept=False -> pending dropped, rejection recorded; returns a gentle
                    follow-up question the client can prefill.
    """
    from supabase_storage import append_patient_event, load_profile, save_profile

    profile = load_profile(user_id)
    if not profile:
        return {"status": "not_found"}
    beliefs = ensure_beliefs(profile)
    entry = next((p for p in beliefs["pending"] if p.get("id") == confirmation_id), None)
    if entry is None:
        return {"status": "not_found"}

    beliefs["pending"] = [p for p in beliefs["pending"] if p.get("id") != confirmation_id]
    path = entry["path"]

    if accept:
        decision = ReconcileDecision(
            path=path, action="ADD", new_value=entry["proposed_value"],
            old_value=entry.get("previous_value"),
            confidence=max(float(entry.get("confidence", 0)), 0.9),
            source="chat", reason="user_confirmed", high_stakes=is_high_stakes(path))
        _write_belief(beliefs, decision, entry.get("session_id"), status="confirmed")
        _materialize(profile, path, entry["proposed_value"])
        append_patient_event(user_id, "belief_confirm", path=path,
                             payload={"value": entry["proposed_value"]}, source="chat")
        out: Dict[str, Any] = {"status": "confirmed", "path": path}
    else:
        append_patient_event(user_id, "belief_reject", path=path,
                             payload={"rejected": entry["proposed_value"]}, source="chat")
        out = {
            "status": "rejected",
            "path": path,
            "corrected_question": f"Thanks for catching that. What is the correct {path_label(path)}?",
        }

    if not save_profile(user_id, profile):
        logger.error("confirm_belief: save_profile failed")
        return {"status": "error"}
    return out


# ---------------------------------------------------------------------------
# Form absorption — the wizard stays a first-class accelerator
# ---------------------------------------------------------------------------

_FORM_SCALAR_PATHS: Tuple[Tuple[str, str], ...] = (
    ("patient", "firstName"), ("patient", "age"), ("patient", "sex"),
    ("patient", "zipCode"), ("patient", "ecog"), ("patient", "weight"),
    ("patient", "heightFt"), ("patient", "heightIn"), ("patient", "race_ethnicity"),
    ("patient", "allergies"),
    ("primaryDiagnosis", "site"), ("primaryDiagnosis", "stage"),
    ("primaryDiagnosis", "histology"),
)


def absorb_form_profile(profile: dict, only_missing: bool = False) -> int:
    """
    Upsert beliefs from the materialized profile with source=form, confirmed,
    confidence 1.0 — the wizard/manual form is authoritative user input.
    Called on profile upload so form saves keep the belief store in sync.

    only_missing=True is the lazy-sync mode used before reconcile in the chat
    write path: it creates beliefs only for materialized fields that have no
    belief yet (legacy stragglers the backfill missed), never touching
    existing ones — so a negation of a legacy fact has a prior to invalidate.

    Returns the number of belief fields written/updated.
    """
    beliefs = ensure_beliefs(profile)
    now = _now_iso()
    count = 0

    def upsert(path: str, value: Any) -> None:
        nonlocal count
        prior = beliefs["fields"].get(path)
        if only_missing and prior is not None:
            return
        entry = {
            "value": value, "confidence": CONF_FORM, "status": "confirmed",
            "source": "form", "session_id": None,
            "first_observed": (prior or {}).get("first_observed", now),
            "last_updated": now, "confirmed_at": now,
            "history": list((prior or {}).get("history", [])),
        }
        if prior and _norm_value(prior.get("value")) != _norm_value(value):
            entry["history"].insert(0, {
                "value": prior.get("value"), "status": prior.get("status"),
                "source": prior.get("source"), "superseded_at": now,
                "reason": "form_update",
            })
            entry["history"] = entry["history"][:HISTORY_CAP]
        beliefs["fields"][path] = entry
        count += 1

    for section, key in _FORM_SCALAR_PATHS:
        val = (profile.get(section) or {}).get(key)
        if val not in (None, "", []):
            upsert(f"{section}.{key}", val)

    for marker, result in ((profile.get("primaryDiagnosis") or {}).get("biomarkers") or {}).items():
        if result not in (None, ""):
            upsert(f"primaryDiagnosis.biomarkers.{str(marker).upper()}", result)

    for c in (profile.get("patient") or {}).get("comorbidities") or []:
        if isinstance(c, str) and c.strip():
            upsert(f"patient.comorbidities.{_slug(c)}", c)

    for tx in profile.get("treatments") or []:
        if isinstance(tx, dict):
            name = tx.get("regimen") or tx.get("category")
            if name:
                clean = {k: v for k, v in tx.items() if v not in (None, "", [])}
                upsert(f"treatments.{_slug(name)}", clean)

    for sym in profile.get("symptoms") or []:
        if isinstance(sym, str) and sym.strip():
            upsert(f"symptoms.{_slug(sym)}", sym.strip())

    return count


# Persistence-layer sub-objects that live inside raw_profile but are NOT part
# of what a form/wizard submits. A profile upload must never wipe them.
PRESERVED_PROFILE_KEYS: Tuple[str, ...] = (
    "beliefs", "model_state", "_sources",
    "visit_recaps", "previsit_questions", "appeal_drafts", "privacy_appeals",
)


def carry_over_app_state(incoming: dict, existing: Optional[dict]) -> dict:
    """Copy preserved sub-objects from the stored profile into an uploaded one."""
    if not existing:
        return incoming
    for key in PRESERVED_PROFILE_KEYS:
        if key not in incoming and key in existing:
            incoming[key] = existing[key]
    return incoming


# ---------------------------------------------------------------------------
# Register (communication level) signal — no LLM, cheap per-turn heuristic
# ---------------------------------------------------------------------------

_TECHNICAL_TERMS = (
    "adjuvant", "neoadjuvant", "metasta", "carcinoma", "adenocarcinoma", "msi", "mss",
    "kras", "nras", "braf", "her2", "egfr", "pd-l1", "tmb", "dpyd", "ugt1a1",
    "folfox", "folfiri", "capox", "xelox", "capecitabine", "oxaliplatin", "irinotecan",
    "bevacizumab", "cetuximab", "pembrolizumab", "nivolumab", "immunotherapy",
    "ecog", "neutropenia", "prognosis", "progression-free", "resection", "lymph node",
    "biomarker", "germline", "somatic", "first-line", "second-line", "maintenance",
)


def update_register_signal(message: str, profile: dict) -> str:
    """
    Track how technically the patient speaks (plain | mixed | technical) as a
    belief, blended across turns so one jargon-y message doesn't flip it.
    Returns the current register.
    """
    text = (message or "").lower()
    words = max(len(text.split()), 1)
    hits = sum(1 for t in _TECHNICAL_TERMS if t in text)
    turn_score = min(hits / max(words / 20.0, 1.0), 2.0)   # jargon density per ~20 words

    beliefs = ensure_beliefs(profile)
    prior = beliefs["fields"].get("meta.communication_register") or {}
    prior_score = float((prior.get("value") or {}).get("score", 0.4)) \
        if isinstance(prior.get("value"), dict) else 0.4
    blended = 0.7 * prior_score + 0.3 * turn_score

    register = "plain" if blended < 0.35 else ("technical" if blended > 0.9 else "mixed")
    now = _now_iso()
    beliefs["fields"]["meta.communication_register"] = {
        "value": {"register": register, "score": round(blended, 3)},
        "confidence": 0.7,
        "status": "provisional",
        "source": "system",
        "session_id": None,
        "first_observed": prior.get("first_observed", now),
        "last_updated": now,
        "history": [],
    }
    return register
