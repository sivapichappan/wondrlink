# test_connection_map_publication.py
"""Guardrails for attestation and the publication gate (SPEC §5.6, §5.7, §4.5).

Publication is the moment content becomes eligible to reach a patient, so every
§5.7 condition needs to be present and stay present. These are static checks
over the SQL; the behavioural proof is the run log in
docs/connection_map/phase3_probe_checklist.md, where each acceptance criterion
was exercised against a live database.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

MIGRATIONS = _REPO / "supabase_migrations"
ATTEST_SQL = MIGRATIONS / "2026_07_29_connection_map_attestation.sql"
PUBLISH_SQL = MIGRATIONS / "2026_07_29_connection_map_publication.sql"


def attest() -> str:
    return ATTEST_SQL.read_text(encoding="utf-8")


def executable(text: str) -> str:
    """SQL with comment lines removed, so prose explaining why something is
    excluded does not read as the thing being present."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("--"))


def hash_body() -> str:
    body = executable(attest())
    body = body[body.index("FUNCTION connection_map_edge_hash"):]
    return body[:body.index("$$;")]


def publish() -> str:
    return PUBLISH_SQL.read_text(encoding="utf-8")


# Every §5.7 condition, and the substring that proves it is checked.
GATE_CONDITIONS = {
    "every edge approved": "expected approved",
    "edge exists": "edge is not in master_edge",
    "relationship type enabled in version": "is not enabled in this version",
    "patient_phrasing non-empty": "patient_phrasing is empty",
    "at least one evidence row": "edge has no evidence",
    "evidence still verifies": "evidence no longer matches its source text",
    "concepts have display_patient": "has no display_patient",
    "edge has an attestation": "edge has no attestation",
    "latest attestation approves": "most recent attestation is a rejection",
    "signer was active at signing": "at signing",
    "signer held reviewer_attesting": "not reviewer_attesting",
    "signer credential is MD or DO": "attested by credential",
    "attestation not voided by edits": "attestation voided",
    "governance note present": "governance_note is required to publish",
}


class TestAttestationRecord:
    def test_is_append_only(self):
        # §5.6 / acceptance #25: reversing a decision means signing again.
        assert re.search(r"CREATE TRIGGER attestation_append_only\s+BEFORE UPDATE OR DELETE",
                         attest())

    def test_snapshots_signing_time_capacity(self):
        text = attest()
        for col in ("reviewer_role", "reviewer_credential",
                    "reviewer_affiliation", "reviewer_status"):
            assert col in text, col

    def test_snapshots_status_which_the_spec_omits(self):
        # Acceptance #7/#8 turn on standing AT SIGNING; reviewer holds only
        # current status, so it must be captured when signing or it is lost.
        assert "reviewer_status" in attest()

    def test_only_a_physician_can_be_recorded_as_attesting(self):
        assert re.search(
            r"CHECK \(reviewer_role = 'reviewer_attesting' AND reviewer_credential IN \('MD','DO'\)\)",
            attest())

    def test_signing_goes_through_a_function_not_a_raw_insert(self):
        # The snapshot and hash must come from live rows, not from the caller.
        text = attest()
        assert "CREATE OR REPLACE FUNCTION connection_map_attest" in text
        assert "connection_map_edge_hash(p_edge_id)" in text

    def test_signing_refuses_an_inactive_or_wrong_role_reviewer(self):
        text = attest()
        assert "may not attest (role %)" in text
        assert "is not active (status %)" in text

    def test_signing_writes_an_audit_row(self):
        assert "INSERT INTO audit_log" in attest()

    def test_review_role_cannot_write_attestations_directly(self):
        text = attest()
        assert "GRANT SELECT ON attestation TO sage_review" in text
        assert "GRANT INSERT ON attestation TO sage_review" not in text


class TestEdgeHash:
    def test_covers_evidence_not_just_the_edge(self):
        # §5.6: the hash covers the edge AND every evidence row, so editing
        # either voids the signature.
        body = hash_body()
        assert "FROM master_edge_evidence" in body
        assert "quoted_sentence" in body and "char_offset" in body

    def test_is_deterministic(self):
        assert "ORDER BY ev.ordinal, ev.id" in hash_body()

    def test_excludes_status(self):
        # Approving an edge must not void the signature that approves it.
        assert "e.status" not in hash_body()

    def test_excludes_timestamps(self):
        body = hash_body()
        assert "updated_at" not in body and "created_at" not in body


class TestPublicationGate:
    @pytest.mark.parametrize("condition,needle", sorted(GATE_CONDITIONS.items()))
    def test_condition_is_checked(self, condition, needle):
        assert needle in publish(), f"§5.7 condition not checked: {condition}"

    def test_reports_every_blocker_not_just_the_first(self):
        # A physician's time is the scarce resource; one round trip per
        # problem wastes it.
        text = publish()
        assert "RETURNS TABLE (edge_id UUID, problem TEXT)" in text
        assert text.count("UNION ALL") >= 10

    def test_publish_refuses_when_any_blocker_exists(self):
        assert "cannot publish, % blocker(s)" in publish()

    def test_there_is_no_override(self):
        # §16 lists admin override on publication as explicitly excluded.
        text = publish().lower()
        for banned in ("p_force", "p_override", "skip_checks", "force boolean"):
            assert banned not in text, banned

    def test_uses_the_latest_attestation_per_edge(self):
        text = publish()
        assert "DISTINCT ON (a.master_edge_id)" in text
        assert "ORDER BY a.master_edge_id, a.signed_at DESC" in text

    def test_evidence_recheck_is_exact_matching(self):
        # Same comparison the insert-time trigger uses; never relaxed.
        assert re.search(
            r"substr\(s\.text, ev\.char_offset \+ 1, char_length\(ev\.quoted_sentence\)\)",
            publish())

    def test_publish_freezes_and_stamps(self):
        text = publish()
        assert "frozen_hash = v_hash" in text
        assert "published_at = NOW()" in text

    def test_publish_supersedes_the_previous_version(self):
        assert "SET status = 'superseded'" in publish()

    def test_publish_writes_an_audit_row(self):
        assert "'publish', 'master_map_version'" in publish()


class TestVersionImmutability:
    def test_published_versions_are_immutable(self):
        # §4.5, deferred from Phase 1 until publication was defined.
        text = publish()
        assert "published map versions are immutable" in text
        assert re.search(r"CREATE TRIGGER master_map_version_immutable\s+BEFORE UPDATE", text)

    def test_the_only_permitted_change_is_being_superseded(self):
        text = publish()
        body = text[text.index("FUNCTION connection_map_map_version_immutable"):]
        assert "NEW.status = 'superseded'" in body
        for pinned in ("NEW.edge_ids IS NOT DISTINCT FROM OLD.edge_ids",
                       "NEW.frozen_hash IS NOT DISTINCT FROM OLD.frozen_hash",
                       "NEW.governance_note IS NOT DISTINCT FROM OLD.governance_note"):
            assert pinned in body, pinned


class TestEnabledRelationships:
    def test_versions_pin_which_types_they_may_contain(self):
        assert "enabled_relationships" in publish()

    def test_v1_default_matches_the_spec(self):
        # §4.3: only side_effect_of and co_occurs_with are enabled in v1.
        assert "DEFAULT ARRAY['side_effect_of','co_occurs_with']" in publish()

    def test_acts_through_can_never_be_enabled(self):
        # §4.3: authoring-only. A patient cannot validate a mediator.
        assert "NOT ('acts_through' = ANY(enabled_relationships))" in publish()

    def test_cannot_enable_nothing(self):
        assert "cardinality(enabled_relationships) > 0" in publish()


class TestHouseStyle:
    def test_functions_pin_search_path(self):
        for text in (attest(), publish()):
            for name in re.findall(r"CREATE OR REPLACE FUNCTION (\w+)", text):
                head = text[text.index(f"CREATE OR REPLACE FUNCTION {name}"):]
                assert "SET search_path = public, pg_temp" in head[:head.index("AS $$")], name

    def test_no_security_definer(self):
        for text in (attest(), publish()):
            assert "SECURITY DEFINER" not in text

    def test_client_roles_cannot_execute_the_functions(self):
        for text in (attest(), publish()):
            for fn in re.findall(r"REVOKE ALL ON FUNCTION (\w+)", text):
                assert f"FROM anon" in text and f"FROM authenticated" in text, fn

    def test_migrations_sort_after_phase_2(self):
        names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
        for f in (ATTEST_SQL, PUBLISH_SQL):
            assert names.index(f.name) > names.index(
                "2026_07_28_connection_map_sage_review_role.sql")


class TestTierCEvidence:
    """Owner decision D2: tier C exists, but inference may never masquerade as
    a quotation. All four behaviours below were probed on sage-dev."""

    def tier_c_sql(self) -> str:
        return (MIGRATIONS / "2026_07_30_connection_map_tier_c.sql").read_text(encoding="utf-8")

    def test_tier_c_is_storable(self):
        assert "CHECK (tier IN ('A','B','C'))" in self.tier_c_sql()

    def test_inferred_evidence_cannot_carry_a_quotation(self):
        # The property that protects patients: never fabricate a citation.
        text = self.tier_c_sql()
        assert "evidence_kind = 'inferred'" in text
        assert "AND quoted_sentence IS NULL" in text
        assert "reasoning IS NOT NULL" in text

    def test_verbatim_evidence_still_requires_a_quotation(self):
        assert re.search(
            r"evidence_kind = 'verbatim'\s*\n\s*AND quoted_sentence IS NOT NULL",
            self.tier_c_sql())

    def test_tier_a_and_b_reject_inferred_evidence(self):
        text = self.tier_c_sql()
        assert "requires verbatim evidence" in text
        assert "v_tier IN ('A','B')" in text

    def test_exact_matching_is_unchanged_for_verbatim_rows(self):
        # §16: never relax the citation check. Skipping applies only to rows
        # that make no quotation claim.
        text = self.tier_c_sql()
        assert re.search(
            r"substr\(v_text, NEW\.char_offset \+ 1, char_length\(NEW\.quoted_sentence\)\)",
            text)

    def test_hash_covers_the_new_fields(self):
        # Otherwise editing an inference's reasoning after signing would not
        # void the signature (acceptance #10).
        text = self.tier_c_sql()
        assert "ev.evidence_kind" in text and "ev.reasoning" in text

    def test_publication_gate_skips_inferred_rows_in_the_quote_recheck(self):
        text = self.tier_c_sql()
        assert "WHERE ev.evidence_kind = 'verbatim'" in text
        assert "has inferred evidence" in text

    def test_rpc_can_write_the_new_fields(self):
        # Without this, extraction could never create a tier C edge: its
        # evidence would default to verbatim with no quotation and be refused.
        text = self.tier_c_sql()
        assert "COALESCE(v_row->>'evidence_kind', 'verbatim')" in text
        assert "v_row->>'reasoning'" in text

    def test_tier_c_still_has_no_attestation_wording(self):
        # D2's remaining gate: signing tier C is refused until legal approves
        # a variant, because the v1 sentence ("consistent with the cited
        # sources") overclaims for an inference. Parsed, not string-matched:
        # the file's own comment explains the absence and mentions the name.
        import yaml
        cfg = yaml.safe_load(
            (_REPO / "config" / "connection_map" / "attestation_text.yaml")
            .read_text(encoding="utf-8"))
        covered = {t for v in cfg["versions"].values()
                   for t in (v.get("applies_to_tiers") or [])}
        assert covered == {"A", "B"}, f"tier C must have no signable wording yet: {covered}"

    def test_the_api_refuses_a_tier_without_wording(self):
        sys.path.insert(0, str(_REPO / "lib"))
        from connection_map.review.api import attestation_text_for_tier
        assert attestation_text_for_tier("A") is not None
        assert attestation_text_for_tier("C") is None
