# test_connection_map_review_boundary.py
"""The §5.8 PHI-boundary gate for Phase 2.

§5.8 lists four required tests. Three of them can run offline and live here.
The fourth ("connect as sage_review, assert a permission error on every patient
table") needs a real Postgres session, which pytest cannot reach from this
repo, so it runs as probes in docs/connection_map/phase2_probe_checklist.md and
this file instead pins the migration text that produces that behaviour.

The compliance argument is: the database refuses (proved by probe), the code
cannot ask (proved by the import-graph test), the routing cannot slip (proved
by the client test), and the client cannot silently degrade (proved below).
"""

import ast
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))

REVIEW_PKG = _REPO / "lib" / "connection_map" / "review"
ROLE_SQL = _REPO / "supabase_migrations" / "2026_07_28_connection_map_sage_review_role.sql"
REVIEWER_SQL = _REPO / "supabase_migrations" / "2026_07_28_connection_map_reviewers.sql"

# Anything that reads patient data. A review module importing any of these is
# the failure §5.8 exists to prevent.
PATIENT_MODULES = {
    "patient_model", "supabase_storage", "modeler", "question_policy",
    "profile_utils", "learning_loop", "safety_classifier", "llm_utils",
    "clinical_trials", "vector_search", "pdf_utils", "index",
}

# Tables sage_review must hold no privilege on.
PATIENT_TABLES = [
    "patient_edge", "patient_edge_event", "patient_profiles", "accounts",
    "conversations", "messages", "chat_messages", "chat_feedback",
    "patient_events", "safety_classifications", "screening_scores",
    "glossary_terms", "user_acknowledgements", "consent_withdrawals",
    "rate_limits", "pattern_records",
]

# What the role may reach, and with which privileges.
REVIEW_GRANTS = {
    "concept": {"SELECT", "INSERT", "UPDATE"},
    "source_document": {"SELECT"},
    "source_section": {"SELECT"},
    "extraction_run": {"SELECT"},
    "master_edge": {"SELECT", "UPDATE"},
    "master_edge_evidence": {"SELECT"},
    "master_map_version": {"SELECT", "INSERT", "UPDATE"},
    "reviewer": {"SELECT", "INSERT", "UPDATE"},
    "reviewer_assignment": {"SELECT", "INSERT", "UPDATE"},
    "audit_log": {"SELECT", "INSERT"},
}


def role_sql() -> str:
    return ROLE_SQL.read_text(encoding="utf-8")


def imported_names(path: Path) -> set:
    """Top-level module names imported by a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import, stays inside the package
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


class TestImportGraph:
    """§5.8 test 3: no module under review/ imports a patient model."""

    def test_package_exists(self):
        assert REVIEW_PKG.is_dir()
        assert list(REVIEW_PKG.glob("*.py"))

    @pytest.mark.parametrize("path", sorted(REVIEW_PKG.glob("*.py")), ids=lambda p: p.name)
    def test_no_patient_imports(self, path):
        offending = imported_names(path) & PATIENT_MODULES
        assert not offending, f"{path.name} imports patient module(s): {sorted(offending)}"

    def test_transitively_clean(self):
        """A review module may import another connection_map module, so follow
        those one level down too: a clean direct import list is worthless if
        the thing it imports reads patient data."""
        seen, queue = set(), list(REVIEW_PKG.glob("*.py"))
        cm_root = _REPO / "lib" / "connection_map"
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            names = imported_names(path)
            assert not (names & PATIENT_MODULES), f"{path.name} reaches a patient module"
            for name in names:
                if name == "connection_map":
                    for sibling in cm_root.glob("*.py"):
                        if sibling not in seen:
                            queue.append(sibling)


class TestClientFailsClosed:
    """The client must never quietly become a privileged one."""

    def test_never_reads_the_service_role_key(self):
        # The service-role key bypasses RLS. If this module can read it, one
        # careless edit reinstates full patient access.
        text = (REVIEW_PKG / "db.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
        assert "SUPABASE_SERVICE_ROLE_KEY" not in code

    def test_does_not_import_the_shared_admin_client(self):
        names = imported_names(REVIEW_PKG / "db.py")
        assert "supabase_client" not in names, "would expose get_admin_client()"

    def test_raises_without_a_secret(self, monkeypatch):
        from connection_map.review import db

        db.reset_review_client()
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(db.ReviewBoundaryError):
            db.mint_review_token()

    def test_raises_rather_than_returning_a_client_without_a_secret(self, monkeypatch):
        from connection_map.review import db

        db.reset_review_client()
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(db.ReviewBoundaryError):
            db.get_review_client()
        db.reset_review_client()

    def test_token_selects_the_restricted_role(self, monkeypatch):
        import jwt as pyjwt
        from connection_map.review import db

        monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-not-a-real-one")
        token = db.mint_review_token(now=1_000_000)
        claims = pyjwt.decode(token, "test-secret-not-a-real-one", algorithms=["HS256"],
                              options={"verify_exp": False})  # fixed clock, not a live token
        assert claims["role"] == "sage_review"
        assert claims["exp"] == 1_000_000 + db.TOKEN_TTL_SECONDS

    def test_token_is_rejected_under_the_wrong_secret(self, monkeypatch):
        import jwt as pyjwt
        from connection_map.review import db

        monkeypatch.setenv("SUPABASE_JWT_SECRET", "the-real-secret")
        token = db.mint_review_token(now=1_000_000)
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(token, "a-different-secret", algorithms=["HS256"],
                         options={"verify_exp": False})

    def test_token_is_short_lived(self):
        from connection_map.review import db

        assert 0 < db.TOKEN_TTL_SECONDS <= 3600

    def test_describe_boundary_leaks_nothing(self, monkeypatch):
        from connection_map.review import db

        monkeypatch.setenv("SUPABASE_JWT_SECRET", "super-secret-value")
        monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
        monkeypatch.setenv("SUPABASE_KEY", "anon-key-value")
        out = db.describe_boundary()
        blob = repr(out)
        assert "super-secret-value" not in blob and "anon-key-value" not in blob
        assert out["configured"] is True


class TestRoleMigration:
    """§5.8 test 1's static half: the SQL that produces the refusal."""

    def test_role_is_created_idempotently(self):
        assert "CREATE ROLE sage_review NOLOGIN" in role_sql()
        assert "FROM pg_roles WHERE rolname = 'sage_review'" in role_sql()

    def test_role_never_bypasses_rls(self):
        # service_role has BYPASSRLS; if sage_review ever gained it, every
        # policy in the schema would stop applying to reviewers.
        assert "ALTER ROLE sage_review NOLOGIN NOBYPASSRLS" in role_sql()
        # Check the role-defining statements themselves rather than the whole
        # file, so prose mentioning the attribute doesn't trip the test.
        statements = re.findall(r"(?:CREATE|ALTER)\s+ROLE\s+[^;]*;", role_sql(), re.IGNORECASE)
        assert statements
        for stmt in statements:
            assert "BYPASSRLS" not in stmt.replace("NOBYPASSRLS", ""), stmt
            assert "SUPERUSER" not in stmt.replace("NOSUPERUSER", ""), stmt
            assert "CREATEROLE" not in stmt.replace("NOCREATEROLE", ""), stmt

    def test_postgrest_can_switch_into_it(self):
        assert "GRANT sage_review TO authenticator" in role_sql()

    def test_every_patient_table_is_revoked(self):
        text = role_sql()
        for table in PATIENT_TABLES:
            assert f"'{table}'" in text, f"{table} missing from the revoke list"
        assert "REVOKE ALL PRIVILEGES ON %I FROM sage_review" in text

    def test_auth_schema_is_revoked(self):
        text = role_sql()
        assert "REVOKE ALL PRIVILEGES ON SCHEMA auth FROM sage_review" in text

    def test_no_patient_table_is_granted(self):
        # The grant block's table list must not overlap the patient list.
        text = role_sql()
        block = text[text.index("spec   TEXT[][]"):text.index("GRANT USAGE, SELECT ON SEQUENCE")]
        granted = set(re.findall(r"\['(\w+)',\s*'", block))
        assert granted == set(REVIEW_GRANTS), granted
        assert not granted & set(PATIENT_TABLES)

    @pytest.mark.parametrize("table,privs", sorted(REVIEW_GRANTS.items()))
    def test_grants_match_the_intended_posture(self, table, privs):
        block = role_sql()
        m = re.search(rf"\['{table}',\s*'([A-Z,]+)'\]", block)
        assert m, f"no grant line for {table}"
        assert set(m.group(1).split(",")) == privs

    def test_delete_is_granted_nowhere(self):
        for privs in REVIEW_GRANTS.values():
            assert "DELETE" not in privs

    def test_every_granted_table_also_gets_a_policy(self):
        # The footgun this guards: these tables have RLS enabled and
        # sage_review does not bypass it, so a grant WITHOUT a policy returns
        # zero rows SILENTLY instead of erroring. A review queue would just
        # look empty. Verified on sage-dev before the migration was written.
        text = role_sql()
        assert "FOR SELECT TO sage_review USING (true)" in text
        assert "FOR INSERT TO sage_review WITH CHECK (true)" in text
        assert "FOR UPDATE TO sage_review USING (true) WITH CHECK (true)" in text
        # The loop derives policies from the same list that drives the grants,
        # so they cannot drift apart.
        assert "FOREACH cmd IN ARRAY string_to_array(privs, ',')" in text

    def test_audit_log_sequence_is_usable(self):
        assert "GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO sage_review" in role_sql()

    def test_grant_block_fails_loudly_on_a_missing_table(self):
        assert "expected table % to exist before granting" in role_sql()


class TestReviewerSchema:
    def test_only_physicians_may_attest(self):
        # §5.1, enforced as a database CHECK rather than in the application.
        assert re.search(
            r"CHECK \(role <> 'reviewer_attesting' OR credential IN \('MD','DO'\)\)",
            REVIEWER_SQL.read_text(encoding="utf-8"))

    def test_audit_log_is_hard_append_only(self):
        # Acceptance #25: UPDATE *and* DELETE. Unlike patient_edge_event,
        # which must keep DELETE for right-to-delete.
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        assert "BEFORE UPDATE OR DELETE ON audit_log" in text

    def test_patient_event_log_keeps_its_delete_carve_out(self):
        # Guard against someone "consistently" hardening both tables and
        # breaking MHMDA/GDPR erasure.
        patient_sql = (_REPO / "supabase_migrations"
                       / "2026_07_28_connection_map_patient.sql").read_text(encoding="utf-8")
        assert "BEFORE UPDATE ON patient_edge_event" in patient_sql
        assert "BEFORE UPDATE OR DELETE ON patient_edge_event" not in patient_sql

    def test_reviewer_and_patient_accounts_are_mutually_exclusive(self):
        # Acceptance #5, enforced in both directions.
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        assert "connection_map_reviewer_not_a_patient" in text
        assert "connection_map_patient_not_a_reviewer" in text
        assert "CREATE TRIGGER reviewer_not_a_patient" in text
        assert "patient_not_a_reviewer" in text

    def test_patient_side_trigger_tolerates_a_missing_table(self):
        # sage-dev has no patient_profiles yet; the migration must still apply.
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        assert "to_regclass('public.patient_profiles') IS NOT NULL" in text

    def test_functions_pin_search_path(self):
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        for name in re.findall(r"CREATE OR REPLACE FUNCTION (\w+)", text):
            head = text[text.index(f"CREATE OR REPLACE FUNCTION {name}"):]
            assert "SET search_path = public, pg_temp" in head[:head.index("AS $$")], name


class TestDependencyIsDeclared:
    def test_pyjwt_is_explicit(self):
        # It resolves transitively via supabase-auth today, but the token it
        # mints IS the boundary; the mobile side already lost a build to a
        # dependency that only resolved through hoisting.
        assert "PyJWT" in (_REPO / "requirements.txt").read_text(encoding="utf-8")
