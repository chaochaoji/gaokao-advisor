"""API integration tests using FastAPI TestClient."""
import os, sys
os.environ["ZXF_EMBEDDING_MODE"] = "api"
os.environ["ZXF_RERANKER_MODE"] = "mock"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)

from fastapi.testclient import TestClient
from app_api import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_200(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert "database" in r.json()["services"]


class TestConversationsCRUD:
    def test_create_session(self):
        r = client.post("/api/conversations")
        assert r.status_code == 200
        data = r.json()
        assert len(data["id"]) == 8
        assert data["title"] == "New Chat"

    def test_list_sessions(self):
        for _ in range(2):
            client.post("/api/conversations")
        r = client.get("/api/conversations")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_get_messages_empty(self):
        r = client.post("/api/conversations")
        sid = r.json()["id"]
        r = client.get(f"/api/conversations/{sid}/messages")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_messages_nonexistent(self):
        r = client.get("/api/conversations/nonexist/messages")
        assert r.status_code == 404

    def test_rename_and_delete_session(self):
        r = client.post("/api/conversations")
        sid = r.json()["id"]
        # Rename
        r = client.patch(f"/api/conversations/{sid}/title", json={"title": "Test"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # Delete
        r = client.delete(f"/api/conversations/{sid}")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        # Verify deleted
        r = client.get(f"/api/conversations/{sid}/messages")
        assert r.status_code == 404


class TestConfig:
    def test_get_config(self):
        r = client.get("/api/config")
        assert r.status_code == 200
        assert "llm_primary_model" in r.json()

    def test_save_config(self):
        # Backup real .env to avoid corrupting user config
        import os as _os
        env_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), ".env")
        backup = None
        if _os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                backup = f.read()

        try:
            r = client.put("/api/config", json={
                "llm_primary_model": "test-model", "llm_primary_api_key": "",
                "llm_fallback_model": "", "llm_fallback_api_key": "",
                "llm_primary_api_type": "auto", "llm_primary_base_url": "",
                "llm_fallback_api_type": "auto", "llm_fallback_base_url": "",
                "embedding_api_key": "", "embedding_mode": "api",
                "reranker_mode": "mock", "gradio_port": 7860})
            assert r.status_code == 200
            assert r.json() == {"ok": True}
        finally:
            # Restore original .env
            if backup is not None:
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(backup)


class TestQuote:
    def test_quote_empty_query(self):
        r = client.post("/api/tools/quote", json={"query": "", "top_k": 3})
        assert r.status_code == 200
        assert "error" in r.json()


class TestSearch:
    def test_search(self):
        r = client.get("/api/tools/search?q=test")
        assert r.status_code == 200
        assert "results" in r.json()


class TestRoot:
    def test_root_returns_html(self):
        r = client.get("/")
        assert r.status_code == 200
