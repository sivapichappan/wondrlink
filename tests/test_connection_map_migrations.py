# test_connection_map_migrations.py
"""Static guardrails over the connection-map migration SQL.

Real database enforcement (does the trigger actually reject a bad quote?) can
only be proven against Postgres, which pytest cannot reach here — that lives in
docs/connection_map/phase1_probe_checklist.md, run via the Supabase MCP after
apply_migration. These tests are the in-repo half: they assert the SQL still
CONTAINS the constraints the compliance argument depends on, so a later edit
cannot quietly drop one. They also pin the SQL enum lists to
lib/connection_map/concepts.py so the two cannot drift.
"""

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

from connection_map.concepts import (  # noqa: E402
    CANDIDATE_ORIGINS,
    CONCEPT_DOMAINS,
    CONCEPT_INSTRUMENTS,
    EDGE_STATUSES,
    EDGE_TIERS,
    EDGE_URGENCIES,
    MAP_VERSION_STATUSES,
    PATIENT_EDGE_STATUSES,
    REJECTION_REASONS,
    RELATIONSHIP_TYPES,
    SOURCE_SCOPES,
)

MIGRATIONS = _REPO / "supabase_migrations"

FILES = {
    "concepts": MIGRATIONS / "2026_07_28_connection_map_concepts.sql",
    "corpus": MIGRATIONS / "2026_07_28_connection_map_corpus.sql",
    "edges": MIGRATIONS / "2026_07_28_connection_map_edges.sql",
    "map_versions": MIGRATIONS / "2026_07_28_connection_map_map_versions.sql",
    "patient": MIGRATIONS / "2026_07_28_connection_map_patient.sql",
}

TABLES = {
    "concepts": ["concept"],
    "corpus": ["source_document", "source_section"],
    "edges": ["extraction_run", "master_edge", "master_edge_evidence"],
    "map_versions": ["master_map_version"],
    "patient": ["patient_edge", "patient_edge_event"],
}

PATIENT_TABLES = TABLES["patient"]


def sql(key: str) -> str:
    return FILES[key].read_text(encoding="utf-8")


def all_sql() -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in FILES.values())


def check_values(text: str, column: str) -> set:
    """Extract the value list from `column ... CHECK (column IN ('a','b'))`."""
    m = re.search(
        rf"CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\((?P<vals>.*?)\)\s*\)",
        text, re.IGNORECASE | re.DOTALL)
    assert m, f"no CHECK ... IN list found for {column}"
    return set(re.findall(r"'([^']+)'", m.group("vals")))


class TestFilesExist:
    @pytest.mark.parametrize("key", sorted(FILES))
    def test_present(self, key):
        assert FILES[key].exists(), FILES[key]

    def test_filenames_sort_after_the_previous_migration(self):
        # Migrations apply in lexical filename order.
        names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
        for key in FILES:
            assert names.index(FILES[key].name) > names.index("2026_07_26_glossary_terms.sql")


class TestHouseStyle:
    @pytest.mark.parametrize("key", sorted(FILES))
    def test_tables_are_idempotent(self, key):
        text = sql(key)
        for table in TABLES[key]:
            assert re.search(rf"CREATE TABLE IF NOT EXISTS {table}\b", text), table

    @pytest.mark.parametrize("key", sorted(FILES))
    def test_rls_enabled_on_every_table(self, key):
        text = sql(key)
        for table in TABLES[key]:
            assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text, table

    @pytest.mark.parametrize("key", sorted(FILES))
    def test_indexes_are_idempotent(self, key):
        text = sql(key)
        for stmt in re.findall(r"CREATE INDEX[^;]*;", text, re.IGNORECASE):
            assert "IF NOT EXISTS" in stmt.upper(), stmt[:60]

    @pytest.mark.parametrize("key", sorted(FILES))
    def test_every_table_is_commented(self, key):
        text = sql(key)
        for table in TABLES[key]:
            if table == "extraction_run":
                continue  # implied infrastructure, documented in the file header
            assert f"COMMENT ON TABLE {table}" in text, table

    def test_no_create_type_enums(self):
        # House style is TEXT + CHECK; Postgres enums are harder to widen and
        # PostgREST returns them as strings anyway.
        assert not re.search(r"\bCREATE\s+TYPE\b", all_sql(), re.IGNORECASE)

    def test_triggers_and_policies_are_dropped_before_create(self):
        text = all_sql()
        for name in re.findall(r"CREATE\s+(?:CONSTRAINT\s+)?TRIGGER\s+(\w+)", text, re.IGNORECASE):
            assert re.search(rf"DROP TRIGGER IF EXISTS {name}\b", text), name
        for name in re.findall(r"CREATE\s+POLICY\s+(\w+)", text, re.IGNORECASE):
            assert re.search(rf"DROP POLICY IF EXISTS {name}\b", text), name

    def test_functions_are_replaceable(self):
        text = all_sql()
        created = re.findall(r"CREATE\s+(OR REPLACE\s+)?FUNCTION", text, re.IGNORECASE)
        assert created, "expected at least one function"
        assert all(c.strip() for c in created), "every function must be CREATE OR REPLACE"

    def test_every_function_pins_search_path(self):
        # The verification trigger looks up source_section unqualified. With a
        # mutable search_path a caller could resolve that to a decoy table and
        # have a fabricated quotation verify successfully. pg_temp must come
        # LAST so a temp table cannot shadow a real one.
        text = all_sql()
        names = re.findall(r"CREATE OR REPLACE FUNCTION (\w+)", text)
        assert names
        for name in names:
            body = text[text.index(f"CREATE OR REPLACE FUNCTION {name}"):]
            head = body[:body.index("AS $$")]
            assert "SET search_path = public, pg_temp" in head, name

    def test_no_explicit_constraint_shadows_a_postgres_generated_name(self):
        # Postgres auto-names a column-level CHECK `<table>_<column>_check`.
        # Reusing that name for an explicit table-level constraint fails with
        # "constraint already exists" at CREATE TABLE (hit while applying this
        # very migration).
        for key, tables in TABLES.items():
            text = sql(key)
            explicit = set(re.findall(r"CONSTRAINT (\w+)", text))
            inline_cols = set(re.findall(r"^\s+(\w+)\s+[A-Z]+.*?CHECK \(\1\b", text, re.MULTILINE))
            for table in tables:
                for col in inline_cols:
                    generated = f"{table}_{col}_check"
                    assert generated not in explicit, (
                        f"{generated} collides with the name Postgres generates "
                        f"for the inline CHECK on {table}.{col}")


class TestEnumsMatchPython:
    """lib/connection_map/concepts.py is the Python source of truth; these
    assertions fail if a CHECK list and the module drift apart."""

    def test_concept_domain(self):
        assert check_values(sql("concepts"), "domain") == set(CONCEPT_DOMAINS)

    def test_concept_instrument(self):
        assert check_values(sql("concepts"), "instrument") == set(CONCEPT_INSTRUMENTS)

    def test_source_scope(self):
        assert check_values(sql("corpus"), "scope") == set(SOURCE_SCOPES)

    def test_relationship(self):
        assert check_values(sql("edges"), "relationship") == set(RELATIONSHIP_TYPES)

    def test_urgency(self):
        assert check_values(sql("edges"), "urgency") == set(EDGE_URGENCIES)

    def test_edge_status(self):
        assert check_values(sql("edges"), "status") == set(EDGE_STATUSES)

    def test_candidate_origin(self):
        assert check_values(sql("edges"), "candidate_origin") == set(CANDIDATE_ORIGINS)

    def test_rejection_reason(self):
        assert check_values(sql("edges"), "rejection_reason") == set(REJECTION_REASONS)

    def test_map_version_status(self):
        assert check_values(sql("map_versions"), "status") == set(MAP_VERSION_STATUSES)

    def test_tier_c_widening_is_a_separate_migration(self):
        # The Phase 1 file still says A|B — published migrations are history.
        # D2's widening lands in 2026_07_30_connection_map_tier_c.sql, and the
        # Python enum now matches that later state.
        assert check_values(sql("edges"), "tier") == {"A", "B"}
        assert set(EDGE_TIERS) == {"A", "B", "C"}
        later = (MIGRATIONS / "2026_07_30_connection_map_tier_c.sql").read_text(encoding="utf-8")
        assert "CHECK (tier IN ('A','B','C'))" in later


class TestCitationInvariants:
    """The two invariants the feature's credibility rests on."""

    def test_evidence_verify_trigger_exists(self):
        text = sql("edges")
        assert "CREATE OR REPLACE FUNCTION connection_map_verify_evidence" in text
        assert re.search(
            r"CREATE TRIGGER master_edge_evidence_verify\s+BEFORE INSERT OR UPDATE",
            text), "verify must run BEFORE INSERT OR UPDATE"

    def test_verify_uses_exact_substring_comparison(self):
        text = sql("edges")
        assert re.search(
            r"substr\(\s*v_text,\s*NEW\.char_offset \+ 1,\s*char_length\(NEW\.quoted_sentence\)\s*\)",
            text), "exact offset+length comparison missing"
        assert "IS DISTINCT FROM NEW.quoted_sentence" in text

    def test_verify_has_no_fuzzy_escape_hatch(self):
        # §16: relaxing exact matching rejects the feature's core guarantee.
        text = sql("edges").lower()
        for banned in ("similarity(", "levenshtein", "ilike", "regexp_replace(v_text",
                       "lower(v_text)", "trim(v_text)", "unaccent"):
            assert banned not in text, banned

    def test_verify_cross_checks_document_and_section_ref(self):
        text = sql("edges")
        assert "v_document_id <> NEW.source_document_id" in text
        assert "v_section_ref <> NEW.section_ref" in text

    def test_zero_evidence_edge_is_blocked_at_commit(self):
        text = sql("edges")
        assert "CREATE OR REPLACE FUNCTION connection_map_edge_has_evidence" in text
        for trigger in ("master_edge_requires_evidence",
                        "master_edge_evidence_keeps_edge_covered"):
            m = re.search(
                rf"CREATE CONSTRAINT TRIGGER {trigger}(?P<body>.*?)EXECUTE FUNCTION",
                text, re.DOTALL)
            assert m, trigger
            assert "DEFERRABLE INITIALLY DEFERRED" in m.group("body"), trigger

    def test_edge_has_evidence_branches_on_triggering_table(self):
        # NEW is null in a DELETE trigger and master_edge has no
        # master_edge_id column, so the row reference must be table-aware.
        assert "TG_TABLE_NAME = 'master_edge'" in sql("edges")

    def test_evidence_section_fk_restricts_deletion(self):
        assert re.search(
            r"source_section_id\s+UUID NOT NULL REFERENCES source_section\(id\) ON DELETE RESTRICT",
            sql("edges"))

    def test_evidence_quote_is_non_empty(self):
        assert "CHECK (char_length(quoted_sentence) > 0)" in sql("edges")


class TestEdgeConstraints:
    def test_unique_relationship_triple(self):
        assert re.search(
            r"UNIQUE \(src_concept_id, dst_concept_id, relationship\)", sql("edges"))

    def test_rejection_reason_required_exactly_when_rejected(self):
        # Acceptance #26.
        assert re.search(
            r"CHECK \(\(status = 'rejected'\) = \(rejection_reason IS NOT NULL\)\)",
            sql("edges"))

    def test_no_self_loops(self):
        assert "CHECK (src_concept_id <> dst_concept_id)" in sql("edges")

    def test_priors_are_positive(self):
        text = sql("edges")
        assert "CHECK (prior_alpha > 0)" in text
        assert "CHECK (prior_beta > 0)" in text

    def test_prevalence_band_is_ordered_and_bounded(self):
        text = sql("edges")
        assert "expected_prevalence_low BETWEEN 0 AND 1" in text
        assert "expected_prevalence_high BETWEEN 0 AND 1" in text
        assert "expected_prevalence_low <= expected_prevalence_high" in text

    def test_literature_scan_edges_are_attributable(self):
        assert re.search(
            r"candidate_origin <> 'literature_scan' OR extraction_run_id IS NOT NULL",
            sql("edges"))


class TestRpc:
    def test_rpc_exists_and_returns_the_edge_id(self):
        text = sql("edges")
        assert "CREATE OR REPLACE FUNCTION insert_master_edge_with_evidence(p_edge JSONB, p_evidence JSONB)" in text
        assert "RETURNS UUID" in text

    def test_rpc_is_security_invoker(self):
        text = sql("edges")
        assert "SECURITY INVOKER" in text
        assert "SECURITY DEFINER" not in text, "definer rights would bypass the RLS wall"

    def test_rpc_execute_revoked_from_client_roles(self):
        text = sql("edges")
        for role in ("PUBLIC", "anon", "authenticated"):
            assert re.search(
                rf"REVOKE ALL ON FUNCTION insert_master_edge_with_evidence\(JSONB, JSONB\) FROM {role}",
                text), role
        assert "GRANT EXECUTE ON FUNCTION insert_master_edge_with_evidence(JSONB, JSONB) TO service_role" in text

    def test_rpc_refuses_empty_evidence(self):
        assert "at least one evidence row is required" in sql("edges")


class TestCorpusInvariants:
    def test_section_span_matches_text_length(self):
        assert "CHECK (char_end - char_start = char_length(text))" in sql("corpus")

    def test_document_scope_and_cancer_agree(self):
        assert re.search(
            r"CHECK \(\(scope = 'cancer_specific'\) = \(cancer IS NOT NULL\)\)", sql("corpus"))

    def test_file_path_is_the_upsert_key(self):
        assert re.search(r"file_path\s+TEXT NOT NULL UNIQUE", sql("corpus"))

    def test_sections_unique_per_document(self):
        text = sql("corpus")
        assert "UNIQUE (document_id, ordinal)" in text
        assert "UNIQUE (document_id, section_ref)" in text


class TestMapVersionInvariants:
    def test_published_rows_carry_stamp_freeze_and_governance_note(self):
        # §5.7 requires all three; the full itemized gate is Phase 3.
        assert re.search(
            r"CHECK \(status <> 'published'\s*OR \(published_at IS NOT NULL\s*"
            r"AND frozen_hash IS NOT NULL\s*AND governance_note IS NOT NULL\)\)",
            sql("map_versions"), re.DOTALL)

    def test_one_version_number_per_cancer(self):
        assert "UNIQUE (cancer, version)" in sql("map_versions")

    def test_published_by_is_not_an_auth_user(self):
        # §5.1: a reviewer account and a patient account are distinct.
        assert not re.search(r"published_by\s+UUID[^,]*REFERENCES auth\.users", sql("map_versions"))


class TestPatientTables:
    def test_patient_status_enum_matches_python(self):
        assert check_values(sql("patient"), "status") == set(PATIENT_EDGE_STATUSES)

    def test_owner_fk_cascades_from_auth_users(self):
        text = sql("patient")
        assert text.count(
            "patient_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE") == 1
        assert "patient_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE" in text

    def test_master_side_fks_restrict(self):
        # A master edge or version with live patient instantiations must not be
        # deletable out from under them.
        text = sql("patient")
        assert "REFERENCES master_edge(id) ON DELETE RESTRICT" in text
        assert "REFERENCES master_map_version(id) ON DELETE RESTRICT" in text

    def test_one_patient_edge_per_master_edge(self):
        assert "UNIQUE (patient_id, master_edge_id)" in sql("patient")

    def test_beta_counts_are_positive_integers(self):
        text = sql("patient")
        assert "alpha           INT NOT NULL CHECK (alpha > 0)" in text
        assert "beta            INT NOT NULL CHECK (beta > 0)" in text

    def test_event_log_blocks_update(self):
        text = sql("patient")
        assert "CREATE OR REPLACE FUNCTION connection_map_block_update" in text
        assert re.search(
            r"CREATE TRIGGER patient_edge_event_append_only\s+BEFORE UPDATE ON patient_edge_event",
            text)

    def test_event_log_still_allows_delete(self):
        # Right-to-delete carve-out: blocking DELETE here would strand patient
        # rows that delete_all_user_data has to be able to remove.
        text = sql("patient")
        assert "BEFORE UPDATE OR DELETE ON patient_edge_event" not in text
        assert "BEFORE DELETE ON patient_edge_event" not in text

    def test_own_rows_select_policies(self):
        text = sql("patient")
        for table, policy in (("patient_edge", "patient_edge_select"),
                              ("patient_edge_event", "patient_edge_event_select")):
            assert re.search(
                rf"CREATE POLICY {policy} ON {table}\s+FOR SELECT USING \(patient_id = auth\.uid\(\)\)",
                text), table

    def test_right_to_delete_parity(self):
        # Repo rule: every new user-data table joins delete_all_user_data in
        # the same change (MHMDA/GDPR).
        storage = (_REPO / "lib" / "supabase_storage.py").read_text(encoding="utf-8")
        start = storage.index("def delete_all_user_data")
        end = storage.index("\ndef ", start + 1)
        body = storage[start:end]
        for table in PATIENT_TABLES:
            assert table in body, f"{table} missing from delete_all_user_data"
        assert "'patient_id', user_id" in body.replace('"', "'") or \
               "eq('patient_id', user_id)" in body


class TestNoLearningLoopContact:
    def test_migrations_never_touch_the_dormant_pattern_store(self):
        # §0 rule 2 / acceptance #27.
        text = all_sql().lower()
        assert "pattern_records" not in text
        assert "learning_loop" not in text
