# test_glossary.py
"""
Flask test-client tests for the personal glossary: the explain endpoint
(validation, RAG-failure degradation) and the saved-term CRUD (auth,
ownership 404s, input caps). Generator + storage are mocked; the generator
itself is covered by its brief-prose contract at the endpoint boundary.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "lib"))
sys.path.insert(0, str(_REPO / "api"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_REPO / ".env")

import index  # noqa: E402

TEST_USER = {"user_id": "00000000-0000-4000-8000-000000000002"}
AUTH = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}

ROW = {"id": "11111111-1111-4111-8111-111111111111", "term": "ctDNA",
       "definition": "Tiny bits of tumor DNA in the blood.",
       "created_at": "2026-07-26T00:00:00Z", "updated_at": "2026-07-26T00:00:00Z"}


@pytest.fixture()
def client():
    index.app.config["TESTING"] = True
    with index.app.test_client() as c:
        yield c


@pytest.fixture()
def authed():
    with patch.object(index, "verify_token", return_value=TEST_USER), \
         patch("rate_limit.check_rate_limit", return_value=(True, 99)):
        yield


class TestExplain:
    def test_happy_path(self, client, authed):
        with patch.object(index, "load_all_chunks", return_value=[]), \
             patch.object(index, "hybrid_search", return_value=[]), \
             patch("supabase_storage.get_cancer_slug", return_value="colorectal"), \
             patch("llm_utils.generate_glossary_explanation",
                   return_value="Tiny bits of tumor DNA in the blood.") as gen:
            resp = client.post("/api/glossary/explain", headers=AUTH,
                               data=json.dumps({"term": "ctDNA"}))
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["status"] == "ok"
        assert body["definition"].startswith("Tiny bits")
        assert gen.call_args[0][0] == "ctDNA"

    def test_empty_term_400(self, client, authed):
        resp = client.post("/api/glossary/explain", headers=AUTH,
                           data=json.dumps({"term": "   "}))
        assert resp.status_code == 400

    def test_long_term_400(self, client, authed):
        resp = client.post("/api/glossary/explain", headers=AUTH,
                           data=json.dumps({"term": "x" * 121}))
        assert resp.status_code == 400

    def test_rag_failure_still_200(self, client, authed):
        with patch.object(index, "load_all_chunks", side_effect=RuntimeError("db down")), \
             patch("supabase_storage.get_cancer_slug", return_value=None), \
             patch("llm_utils.generate_glossary_explanation",
                   return_value="A plain answer.") as gen:
            resp = client.post("/api/glossary/explain", headers=AUTH,
                               data=json.dumps({"term": "margins"}))
        assert resp.status_code == 200
        # degraded call: no guidelines
        assert gen.call_args[0][1] == ""

    def test_requires_auth(self, client):
        resp = client.post("/api/glossary/explain",
                           headers={"Content-Type": "application/json"},
                           data=json.dumps({"term": "ctDNA"}))
        assert resp.status_code == 401


class TestCrud:
    def test_list(self, client, authed):
        with patch("supabase_storage.list_glossary_terms", return_value=[ROW]):
            resp = client.get("/api/glossary", headers=AUTH)
        body = resp.get_json()
        assert resp.status_code == 200 and body["terms"][0]["term"] == "ctDNA"

    def test_create(self, client, authed):
        with patch("supabase_storage.create_glossary_term", return_value=ROW) as fn:
            resp = client.post("/api/glossary", headers=AUTH,
                               data=json.dumps({"term": "ctDNA",
                                                "definition": "Tiny bits of tumor DNA in the blood."}))
        assert resp.status_code == 200
        assert resp.get_json()["term"]["id"] == ROW["id"]
        assert fn.call_args[0][0] == TEST_USER["user_id"]

    def test_create_missing_fields_400(self, client, authed):
        resp = client.post("/api/glossary", headers=AUTH,
                           data=json.dumps({"term": "ctDNA"}))
        assert resp.status_code == 400

    def test_create_caps_400(self, client, authed):
        resp = client.post("/api/glossary", headers=AUTH,
                           data=json.dumps({"term": "x" * 121, "definition": "d"}))
        assert resp.status_code == 400
        resp = client.post("/api/glossary", headers=AUTH,
                           data=json.dumps({"term": "t", "definition": "x" * 2001}))
        assert resp.status_code == 400

    def test_patch(self, client, authed):
        with patch("supabase_storage.update_glossary_term", return_value=ROW):
            resp = client.patch(f"/api/glossary/{ROW['id']}", headers=AUTH,
                                data=json.dumps({"definition": "Edited."}))
        assert resp.status_code == 200

    def test_patch_nothing_400(self, client, authed):
        resp = client.patch(f"/api/glossary/{ROW['id']}", headers=AUTH,
                            data=json.dumps({}))
        assert resp.status_code == 400

    def test_patch_not_owned_404(self, client, authed):
        with patch("supabase_storage.update_glossary_term", return_value=None):
            resp = client.patch(f"/api/glossary/{ROW['id']}", headers=AUTH,
                                data=json.dumps({"definition": "Edited."}))
        assert resp.status_code == 404

    def test_delete(self, client, authed):
        with patch("supabase_storage.delete_glossary_term", return_value=True):
            resp = client.delete(f"/api/glossary/{ROW['id']}", headers=AUTH)
        assert resp.status_code == 200

    def test_delete_not_owned_404(self, client, authed):
        with patch("supabase_storage.delete_glossary_term", return_value=False):
            resp = client.delete(f"/api/glossary/{ROW['id']}", headers=AUTH)
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        assert client.get("/api/glossary").status_code == 401
