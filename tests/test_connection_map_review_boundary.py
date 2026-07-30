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

# Anything that reads patient data, or that hands out something which can. A
# review module importing any of these is the failure §5.8 exists to prevent.
#
# supabase_client is FIRST for a reason: it exposes get_admin_client(), the
# service-role client that bypasses RLS and reads every patient table. It is
# also the way every other module in this repo talks to the database, so it is
# the import a Phase 3 handler is most likely to reach for out of habit. An
# earlier version of this list omitted it, and a review module importing it
# passed CI.
PATIENT_MODULES = {
    "supabase_client", "supabase_storage", "patient_model", "modeler",
    "question_policy", "profile_utils", "learning_loop", "safety_classifier",
    "safety_rules", "llm_utils", "clinical_trials", "vector_search",
    "pdf_utils", "auth_helpers", "rate_limit", "index",
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
    # Read-only on purpose: writing reviewer.auth_user_id fires the
    # mutual-exclusion trigger, which reads patient_profiles. As sage_review
    # that both fails and, if it were permitted, would turn the trigger's error
    # message into a patient-existence oracle. Provisioning is a service-role
    # operation behind an admin endpoint.
    "reviewer": {"SELECT"},
    "reviewer_assignment": {"SELECT"},
    "audit_log": {"SELECT", "INSERT"},
}


def role_sql() -> str:
    return ROLE_SQL.read_text(encoding="utf-8")


def imported_names(path: Path) -> set:
    """EVERY dotted segment of every module a file imports.

    Segments, not just the first one: `import lib.supabase_storage` has the
    top-level name `lib`, which looks innocent, so matching only the first
    segment misses it entirely. Returning all segments means the patient-module
    list catches the import however it is spelled.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.update(a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.update(node.module.split("."))
            # `from x import y` may import a MODULE named y, so count those too.
            for a in node.names:
                names.add(a.name)
    return names


def relative_targets(path: Path, pkg_root: Path) -> set:
    """Files reached by relative imports, so the walk can follow them.

    Skipping relative imports (as an earlier version did) leaves a review
    module free to reach anything through a sibling.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            target = base / (node.module.replace(".", "/") if node.module else "")
            for candidate in (Path(str(target) + ".py"), target / "__init__.py"):
                if candidate.exists() and pkg_root in candidate.parents:
                    out.add(candidate.resolve())
    return out


def review_modules() -> list:
    """Every Python file in the review package, including subpackages."""
    return sorted(REVIEW_PKG.rglob("*.py"))


class TestImportGraph:
    """§5.8 test 3: no module under review/ imports a patient model."""

    def test_package_exists(self):
        assert REVIEW_PKG.is_dir()
        assert review_modules()

    @pytest.mark.parametrize("path", review_modules(), ids=lambda p: p.name)
    def test_no_patient_imports(self, path):
        offending = imported_names(path) & PATIENT_MODULES
        assert not offending, f"{path.name} imports patient module(s): {sorted(offending)}"

    def test_transitively_clean(self):
        """Follow what review code actually reaches.

        A clean direct import list is worthless if the thing it imports reads
        patient data, so this walks connection_map modules and relative
        imports transitively rather than stopping at depth one.
        """
        cm_root = (_REPO / "lib" / "connection_map").resolve()
        seen: set = set()
        queue = [p.resolve() for p in review_modules()]
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            names = imported_names(path)
            offending = names & PATIENT_MODULES
            assert not offending, f"{path.name} reaches patient module(s): {sorted(offending)}"

            queue.extend(t for t in relative_targets(path, cm_root) if t not in seen)
            if "connection_map" in names:
                for sibling in cm_root.rglob("*.py"):
                    if sibling.resolve() not in seen:
                        queue.append(sibling.resolve())

    def test_the_walk_actually_covers_every_review_module(self):
        # Guards the guard: if review_modules() ever stopped globbing
        # subdirectories, the parametrized test above would silently cover
        # fewer files while still reporting green.
        assert set(review_modules()) >= set(REVIEW_PKG.glob("*.py"))
        assert (REVIEW_PKG / "db.py") in review_modules()

    def test_detects_a_planted_service_role_import(self, tmp_path):
        # Proves this gate fails when it should. An earlier version of the
        # patient-module list omitted supabase_client, so a file exactly like
        # this one passed CI while holding a client that reads every patient
        # table.
        planted = tmp_path / "planted.py"
        planted.write_text("from supabase_client import get_admin_client\n")
        assert imported_names(planted) & PATIENT_MODULES == {"supabase_client"}

        dotted = tmp_path / "dotted.py"
        dotted.write_text("import lib.supabase_storage\n")
        assert "supabase_storage" in imported_names(dotted) & PATIENT_MODULES

        from_pkg = tmp_path / "from_pkg.py"
        from_pkg.write_text("from lib import supabase_storage\n")
        assert imported_names(from_pkg) & PATIENT_MODULES


class TestClientFailsClosed:
    """The client must never quietly become a privileged one."""

    def test_never_reads_the_service_role_key(self):
        # The service-role key bypasses RLS. If this module can read it, one
        # careless edit reinstates full patient access.
        text = (REVIEW_PKG / "db.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
        assert "SUPABASE_SERVICE_ROLE_KEY" not in code

    @pytest.mark.parametrize("path", review_modules(), ids=lambda p: p.name)
    def test_does_not_import_the_shared_admin_client(self, path):
        # Parametrized over the whole package, not just db.py: the danger is a
        # Phase 3 handler reaching for get_admin_client() out of habit.
        assert "supabase_client" not in imported_names(path), "would expose get_admin_client()"

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

    def test_reviewer_trigger_defers_the_relation_to_run_time(self):
        # A static EXISTS(SELECT ... FROM patient_profiles) is parsed when the
        # statement is prepared, so the to_regclass guard above never gets to
        # skip it and the trigger raises "relation does not exist" wherever the
        # table is absent. Dynamic EXECUTE is what makes the guard real.
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        body = text[text.index("connection_map_reviewer_not_a_patient()"):]
        body = body[:body.index("$$;")]
        assert "EXECUTE 'SELECT EXISTS" in body
        assert "FROM patient_profiles p WHERE" not in body, \
            "static relation reference reintroduces the parse-time failure"

    def test_empty_tiers_array_is_rejected(self):
        # array_length of an empty array is NULL, and a CHECK passes on NULL,
        # so the obvious spelling admits an assignment covering no tiers.
        text = REVIEWER_SQL.read_text(encoding="utf-8")
        assert "cardinality(tiers) > 0" in text
        assert "array_length(tiers" not in text

    def test_provisioning_writes_are_not_available_to_the_review_role(self):
        # Both halves must agree: the grant list is read-only for these tables
        # and the migration explicitly withdraws any earlier write grant.
        assert REVIEW_GRANTS["reviewer"] == {"SELECT"}
        assert REVIEW_GRANTS["reviewer_assignment"] == {"SELECT"}
        text = role_sql()
        assert "REVOKE INSERT, UPDATE ON reviewer FROM sage_review" in text
        assert "REVOKE INSERT, UPDATE ON reviewer_assignment FROM sage_review" in text
        assert "DROP POLICY IF EXISTS reviewer_sage_review_insert ON reviewer" in text

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


class TestReviewRoleCannotDecideAnything:
    """§5.8 + §0 rule 1. sage_review held table-wide UPDATE on master_edge, so
    the restricted connection could set status='approved' with no attestation
    behind it. Found by probing the live database, not by reading the SQL: the
    update succeeded and left a real edge approved and unsigned.

    The application always refused it — EDITABLE_EDGE_FIELDS omits status and
    says why — but that made the guarantee depend on one Flask handler. The
    grant is now as narrow as the code always claimed.
    """

    GRANT_SQL = (_REPO / "supabase_migrations"
                 / "2026_08_04_connection_map_review_column_grants.sql").read_text()

    def _granted_columns(self):
        import re
        body = self.GRANT_SQL[self.GRANT_SQL.index("GRANT UPDATE ("):]
        inside = body[body.index("(") + 1:body.index(")")]
        return {re.sub(r"(--.*|,)", "", line).strip()
                for line in inside.splitlines() if line.strip()} - {""}

    def test_table_wide_update_is_revoked_first(self):
        # Postgres has no per-column REVOKE; the table grant must be dropped or
        # it keeps overriding the narrower one.
        revoke_at = self.GRANT_SQL.index("REVOKE UPDATE ON master_edge FROM sage_review")
        grant_at = self.GRANT_SQL.index("GRANT UPDATE (")
        assert revoke_at < grant_at

    def test_the_granted_columns_match_the_application(self):
        # Drift between these two is how the hole reopens: the API would refuse
        # a field the database still allows, or refuse one it no longer can.
        import sys
        sys.path.insert(0, str(_REPO / "lib"))
        from connection_map.review.api import (
            ATTESTING_ONLY_EDGE_FIELDS,
            EDITABLE_EDGE_FIELDS,
        )
        assert self._granted_columns() == EDITABLE_EDGE_FIELDS | ATTESTING_ONLY_EDGE_FIELDS

    def test_a_verdict_column_is_never_granted(self):
        for verdict in ("status", "rejection_reason"):
            assert verdict not in self._granted_columns(), (
                f"{verdict} moves only through connection_map_attest, which mints "
                "the signature in the same transaction")

    def test_the_columns_that_define_the_claim_are_never_granted(self):
        # Repointing src/dst or changing the relationship would rewrite what an
        # edge asserts without touching its wording.
        for structural in ("src_concept_id", "dst_concept_id", "relationship",
                           "tier", "candidate_origin"):
            assert structural not in self._granted_columns()
