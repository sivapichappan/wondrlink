"""/api/review/* — the review workspace endpoints (SPEC §5.4, acceptance #2).

Every database call in this module goes through the restricted sage_review
client from .db. That is acceptance #2, enforced two ways: the import-graph
test proves nothing here can reach a privileged client, and
tests/test_connection_map_review_api.py walks this blueprint's view functions
asserting each one resolves its data through get_review_client().

AUTHENTICATION IS INJECTED, NOT IMPORTED. Verifying a caller's token lives in
modules this package is forbidden to import (they read patient data). So the
app passes its verify function in at registration:

    from connection_map.review.api import build_review_blueprint
    app.register_blueprint(build_review_blueprint(verify_token=verify_token))

The blueprint then maps the verified auth user to a reviewer row — through the
restricted client — and refuses anyone who is not an active reviewer. A patient
token gets 403 here, and a reviewer token gets 403 on patient endpoints because
reviewer and patient accounts are mutually exclusive at the database.

Errors are uniform on purpose: 403 carries no detail about whether the account
exists, is a patient, or is a revoked reviewer. Detail would make this endpoint
an account-status oracle.
"""

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from flask import Blueprint, g, jsonify, request

from connection_map.concepts import RELATIONSHIP_TYPES
from connection_map.review.copy_lint import review_edit_concerns
from connection_map.review.db import ReviewBoundaryError, get_review_client

ATTESTATION_TEXT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "config" / "connection_map" / "attestation_text.yaml"
)

# Fields a reviewer may change on an edge (§5.4: Reword edits patient_phrasing;
# prevalence band and urgency are review inputs). Everything else — above all
# the evidence — is not editable from review at all.
EDITABLE_EDGE_FIELDS = {
    "patient_phrasing", "urgency",
    "expected_prevalence_low", "expected_prevalence_high",
    "status", "rejection_reason",
}

QUEUE_PAGE_LIMIT = 50


@lru_cache(maxsize=1)
def load_attestation_text() -> Dict[str, Any]:
    with open(ATTESTATION_TEXT_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def attestation_text_for_tier(tier: str) -> Optional[Dict[str, str]]:
    """The signed wording for a tier, or None if no approved wording exists.

    None is a REFUSAL, not a fallback: tier C has no attorney-approved
    sentence yet (PLAN.md D2), and signing the v1 sentence for an inferred
    connection would claim more than the evidence supports.
    """
    doc = load_attestation_text()
    version = doc.get("current_version")
    entry = (doc.get("versions") or {}).get(version) or {}
    if tier in (entry.get("applies_to_tiers") or []):
        return {"version": version, "text": entry.get("text", "")}
    return None


def _ip_hash() -> Optional[str]:
    addr = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    addr = addr.split(",")[0].strip()
    if not addr:
        return None
    salt = os.environ.get("IP_HASH_SALT", "")
    return hashlib.sha256((salt + addr).encode("utf-8")).hexdigest()[:32]


def build_review_blueprint(verify_token: Callable[[str], Optional[Dict[str, Any]]]) -> Blueprint:
    bp = Blueprint("connection_map_review", __name__, url_prefix="/api/review")

    # ------------------------------------------------------------------
    # Auth: token -> auth user -> ACTIVE reviewer row, or a uniform 401/403.
    # ------------------------------------------------------------------
    @bp.before_request
    def _require_reviewer():
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        user = verify_token(auth[len("Bearer "):])
        if not user or not user.get("user_id"):
            return jsonify({"error": "INVALID_TOKEN"}), 401

        try:
            client = get_review_client()
            rows = (client.table("reviewer")
                    .select("id, role, credential, status, full_name")
                    .eq("auth_user_id", user["user_id"])
                    .execute()).data or []
        except ReviewBoundaryError:
            # Fail closed, and say nothing about why.
            return jsonify({"error": "REVIEW_UNAVAILABLE"}), 503

        if not rows or rows[0].get("status") != "active":
            # Uniform: no distinction between "not a reviewer", "revoked", or
            # "is a patient". Detail here is an account-status oracle.
            return jsonify({"error": "FORBIDDEN"}), 403

        g.reviewer = rows[0]
        return None

    # ------------------------------------------------------------------
    # The queue (§5.4): one candidate per row, every quotation ON the row.
    # ------------------------------------------------------------------
    @bp.get("/queue")
    def review_queue():
        client = get_review_client()
        status = request.args.get("status", "candidate")
        if status not in ("candidate", "in_review", "approved", "rejected"):
            return jsonify({"error": "BAD_STATUS"}), 400

        edges = (client.table("master_edge")
                 .select("id, src_concept_id, dst_concept_id, relationship, urgency, "
                         "tier, status, candidate_origin, patient_phrasing, "
                         "expected_prevalence_low, expected_prevalence_high")
                 .eq("status", status)
                 .order("tier")
                 .limit(QUEUE_PAGE_LIMIT)
                 .execute()).data or []

        if not edges:
            return jsonify({"status": "ok", "items": [], "count": 0})

        concept_ids = sorted({e["src_concept_id"] for e in edges}
                             | {e["dst_concept_id"] for e in edges})
        concepts = {c["id"]: c for c in (client.table("concept")
                    .select("id, slug, display_clinical, display_patient, domain")
                    .in_("id", concept_ids).execute()).data or []}

        edge_ids = [e["id"] for e in edges]
        evidence = (client.table("master_edge_evidence")
                    .select("master_edge_id, source_document_id, section_ref, "
                            "quoted_sentence, char_offset, ordinal")
                    .in_("master_edge_id", edge_ids)
                    .order("ordinal")
                    .execute()).data or []
        doc_ids = sorted({ev["source_document_id"] for ev in evidence})
        docs = {d["id"]: d for d in (client.table("source_document")
                .select("id, title, publisher, scope, cancer")
                .in_("id", doc_ids).execute()).data or []} if doc_ids else {}

        by_edge: Dict[str, List[Dict[str, Any]]] = {}
        for ev in evidence:
            doc = docs.get(ev["source_document_id"], {})
            by_edge.setdefault(ev["master_edge_id"], []).append({
                "quoted_sentence": ev["quoted_sentence"],
                "section_ref": ev["section_ref"],
                "document_title": doc.get("title"),
                "publisher": doc.get("publisher"),
                # §5.4: each quotation labelled with its source scope.
                "scope": doc.get("scope"),
            })

        items = []
        for e in edges:
            src = concepts.get(e["src_concept_id"], {})
            dst = concepts.get(e["dst_concept_id"], {})
            items.append({
                "id": e["id"],
                "relationship": e["relationship"],
                "tier": e["tier"],
                "urgency": e["urgency"],
                "status": e["status"],
                # §6.4: a bare label, nothing more, whatever the origin.
                "origin": e["candidate_origin"].replace("_", " "),
                "src": {"slug": src.get("slug"), "display": src.get("display_clinical"),
                        "display_patient": src.get("display_patient")},
                "dst": {"slug": dst.get("slug"), "display": dst.get("display_clinical"),
                        "display_patient": dst.get("display_patient")},
                "patient_phrasing": e["patient_phrasing"],
                "expected_prevalence_low": e["expected_prevalence_low"],
                "expected_prevalence_high": e["expected_prevalence_high"],
                "evidence": by_edge.get(e["id"], []),
                "attestation": attestation_text_for_tier(e["tier"]),
            })
        return jsonify({"status": "ok", "items": items, "count": len(items)})

    # ------------------------------------------------------------------
    # Edit (§5.4 Reword + D1). Wording and metadata only; never evidence.
    # ------------------------------------------------------------------
    @bp.patch("/edge/<edge_id>")
    def edit_edge(edge_id: str):
        payload = request.get_json(silent=True) or {}
        unknown = set(payload) - EDITABLE_EDGE_FIELDS
        if unknown:
            return jsonify({"error": "FIELD_NOT_EDITABLE",
                            "fields": sorted(unknown)}), 400
        if not payload:
            return jsonify({"error": "EMPTY_EDIT"}), 400

        client = get_review_client()

        result: Dict[str, Any] = {"status": "ok"}
        if "patient_phrasing" in payload:
            rows = (client.table("master_edge_evidence")
                    .select("quoted_sentence")
                    .eq("master_edge_id", edge_id)
                    .execute()).data or []
            current = (client.table("master_edge")
                       .select("patient_phrasing")
                       .eq("id", edge_id)
                       .execute()).data or [{}]
            check = review_edit_concerns(
                payload["patient_phrasing"],
                quoted_sentences=[r["quoted_sentence"] for r in rows],
                previous_text=current[0].get("patient_phrasing"))
            # D1: warn, never block. Hard §8 problems DO block, for everyone —
            # they are the publication gate's rules surfaced early.
            if check["blocking"]:
                return jsonify({"error": "COPY_RULES", "problems": check["blocking"]}), 422
            result["concerns"] = check["concerns"]

        updated = (client.table("master_edge")
                   .update(payload)
                   .eq("id", edge_id)
                   .execute()).data or []
        if not updated:
            return jsonify({"error": "NOT_FOUND"}), 404

        client.table("audit_log").insert({
            "actor_id": g.reviewer["id"],
            "actor_role": g.reviewer["role"],
            "action": "edit_edge",
            "target_table": "master_edge",
            "target_id": edge_id,
            "metadata": {"fields": sorted(payload)},
        }).execute()
        return jsonify(result)

    # ------------------------------------------------------------------
    # Sign (§5.6). The database snapshots capacity and hash; we only route.
    # ------------------------------------------------------------------
    @bp.post("/edge/<edge_id>/attest")
    def attest_edge(edge_id: str):
        payload = request.get_json(silent=True) or {}
        decision = payload.get("decision")
        if decision not in ("approve", "reject"):
            return jsonify({"error": "BAD_DECISION"}), 400

        client = get_review_client()
        rows = (client.table("master_edge")
                .select("tier, status, rejection_reason")
                .eq("id", edge_id).execute()).data or []
        if not rows:
            return jsonify({"error": "NOT_FOUND"}), 404
        edge = rows[0]

        text = attestation_text_for_tier(edge["tier"])
        if text is None:
            # Tier C until its attorney-approved variant lands. Refuse, never
            # fall back to wording that overclaims.
            return jsonify({"error": "NO_ATTESTATION_TEXT_FOR_TIER",
                            "tier": edge["tier"]}), 409

        if decision == "reject":
            reason = payload.get("rejection_reason")
            if not reason:
                # §5.4: reject requires a structured reason.
                return jsonify({"error": "REJECTION_REASON_REQUIRED"}), 400
            update: Dict[str, Any] = {"status": "rejected", "rejection_reason": reason}
        else:
            update = {"status": "approved", "rejection_reason": None}

        updated = (client.table("master_edge")
                   .update(update).eq("id", edge_id).execute()).data or []
        if not updated:
            return jsonify({"error": "NOT_FOUND"}), 404

        signed = client.rpc("connection_map_attest", {
            "p_edge_id": edge_id,
            "p_reviewer_id": g.reviewer["id"],
            "p_decision": decision,
            "p_text_version": text["version"],
            "p_text": text["text"],
            "p_ip_hash": _ip_hash(),
        }).execute()
        return jsonify({"status": "ok", "attestation_id": signed.data,
                        "decision": decision})

    # ------------------------------------------------------------------
    # Publication (§5.7). The database gate decides; these expose it.
    # ------------------------------------------------------------------
    @bp.get("/version/<version_id>/blockers")
    def version_blockers(version_id: str):
        client = get_review_client()
        rows = client.rpc("connection_map_publication_blockers",
                          {"p_version_id": version_id}).execute().data or []
        return jsonify({"status": "ok", "blockers": rows, "publishable": not rows})

    @bp.post("/version/<version_id>/publish")
    def publish_version(version_id: str):
        if g.reviewer.get("role") != "admin":
            # §5.1: an admin publishes; an attesting physician cannot (the
            # person cutting the release is not the person vouching for it).
            return jsonify({"error": "FORBIDDEN"}), 403
        client = get_review_client()
        published = client.rpc("connection_map_publish", {
            "p_version_id": version_id,
            "p_actor_id": g.reviewer["id"],
        }).execute()
        return jsonify({"status": "ok", "version_id": published.data})

    # ------------------------------------------------------------------
    # D3: physicians may add concepts.
    # ------------------------------------------------------------------
    @bp.post("/concept")
    def propose_concept():
        payload = request.get_json(silent=True) or {}
        slug = (payload.get("slug") or "").strip()
        domain = payload.get("domain")
        display = (payload.get("display_clinical") or "").strip()
        if not slug or not display or domain is None:
            return jsonify({"error": "MISSING_FIELDS"}), 400

        client = get_review_client()
        inserted = (client.table("concept").insert({
            "slug": slug,
            "domain": domain,
            "display_clinical": display,
            "display_patient": payload.get("display_patient"),
            "instrument": payload.get("instrument"),
            "cancer_scopes": payload.get("cancer_scopes") or ["breast"],
        }).execute()).data or []

        client.table("audit_log").insert({
            "actor_id": g.reviewer["id"],
            "actor_role": g.reviewer["role"],
            "action": "propose_concept",
            "target_table": "concept",
            "target_id": slug,
            "metadata": {"domain": domain},
        }).execute()
        return jsonify({"status": "ok", "concept": inserted[0] if inserted else None})

    @bp.get("/meta")
    def review_meta():
        return jsonify({
            "status": "ok",
            "reviewer": {"name": g.reviewer.get("full_name"),
                         "role": g.reviewer.get("role")},
            "relationship_types": list(RELATIONSHIP_TYPES),
        })

    return bp
