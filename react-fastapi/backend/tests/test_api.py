# -*- coding: utf-8 -*-
"""
tests/test_api.py
------------------
FastAPI TestClient を使ったエンドポイントテスト。

Ollama は conftest.py でモック済み（オフライン実行）。
InterviewService は unittest.mock.patch で差し替え、
LLM 依存のルーターも同期的にテストできる。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.api


# ============================================================
# GET /api/v1/health
# ============================================================

class TestHealth:

    def test_health_degraded_when_ollama_offline(self, client):
        """Ollama がオフラインのとき degraded を返す。"""
        with patch("api.routes.health.get_provider") as mock_get:
            provider = MagicMock()
            provider.is_running.return_value = False
            mock_get.return_value = provider
            res = client.get("/api/v1/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "degraded"
        assert body["ollama"] is False

    def test_health_ok_when_ollama_online(self, client):
        """Ollama がオンラインのとき ok を返す。"""
        with patch("api.routes.health.get_provider") as mock_get:
            from llm.ollama_provider import OllamaProvider
            provider = MagicMock(spec=OllamaProvider)
            provider.is_running.return_value = True
            provider.list_models.return_value = ["qwen3:8b"]
            mock_get.return_value = provider
            res = client.get("/api/v1/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert "qwen3:8b" in body["models"]


# ============================================================
# GET /api/v1/settings/
# PATCH /api/v1/settings/
# ============================================================

class TestSettings:

    def test_get_settings_returns_defaults(self, client):
        res = client.get("/api/v1/settings/")
        assert res.status_code == 200
        body = res.json()
        assert "chat_model" in body
        assert "embed_model" in body
        assert "ollama_host" in body

    def test_patch_settings(self, client):
        res = client.patch(
            "/api/v1/settings/",
            json={"chat_model": "llama3.2:3b"},
        )
        assert res.status_code == 200
        assert res.json()["chat_model"] == "llama3.2:3b"

    def test_patch_partial(self, client):
        """一部フィールドだけ更新しても他は変わらない。"""
        client.patch("/api/v1/settings/", json={"chat_model": "model-a"})
        client.patch("/api/v1/settings/", json={"embed_model": "embed-b"})
        res = client.get("/api/v1/settings/")
        body = res.json()
        assert body["chat_model"] == "model-a"
        assert body["embed_model"] == "embed-b"


# ============================================================
# POST /api/v1/sessions/
# GET  /api/v1/sessions/
# GET  /api/v1/sessions/{id}
# PATCH /api/v1/sessions/{id}
# DELETE /api/v1/sessions/{id}
# ============================================================

class TestSessions:

    def test_create_session(self, client):
        res = client.post(
            "/api/v1/sessions/",
            json={"company_name": "テスト株式会社", "profile_text": "学生A"},
        )
        assert res.status_code == 201
        assert "id" in res.json()

    def test_list_sessions(self, client):
        client.post("/api/v1/sessions/", json={"company_name": "A社"})
        client.post("/api/v1/sessions/", json={"company_name": "B社"})
        res = client.get("/api/v1/sessions/")
        assert res.status_code == 200
        assert len(res.json()) >= 2

    def test_get_session(self, client):
        create = client.post("/api/v1/sessions/", json={"company_name": "C社"})
        sid = create.json()["id"]
        res = client.get(f"/api/v1/sessions/{sid}")
        assert res.status_code == 200
        body = res.json()
        assert "session" in body
        assert body["session"]["company_name"] == "C社"

    def test_get_nonexistent_session(self, client):
        res = client.get("/api/v1/sessions/99999")
        assert res.status_code == 404

    def test_update_session(self, client):
        create = client.post("/api/v1/sessions/", json={"company_name": "D社"})
        sid = create.json()["id"]
        res = client.patch(
            f"/api/v1/sessions/{sid}",
            json={"interview_complete": True},
        )
        assert res.status_code == 200

    def test_delete_session(self, client):
        create = client.post("/api/v1/sessions/", json={"company_name": "削除社"})
        sid = create.json()["id"]
        del_res = client.delete(f"/api/v1/sessions/{sid}")
        assert del_res.status_code == 204
        get_res = client.get(f"/api/v1/sessions/{sid}")
        assert get_res.status_code == 404

    def test_export_session(self, client):
        create = client.post("/api/v1/sessions/", json={"company_name": "E社"})
        sid = create.json()["id"]
        res = client.get(f"/api/v1/sessions/{sid}/export")
        assert res.status_code == 200
        body = res.json()
        assert "session" in body


# ============================================================
# GET  /api/v1/knowledge-bases/
# POST /api/v1/knowledge-bases/text
# DELETE /api/v1/knowledge-bases/{id}
# PATCH /api/v1/knowledge-bases/{id}/active
# ============================================================

class TestKnowledgeBases:

    def test_list_empty(self, client):
        res = client.get("/api/v1/knowledge-bases/")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_from_text(self, client):
        res = client.post(
            "/api/v1/knowledge-bases/text",
            json={
                "name": "テスト履歴書",
                "kb_type": "resume",
                "text": "○○大学 情報工学科 4年。Python・FastAPI の経験あり。",
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "テスト履歴書"

    def test_create_invalid_type(self, client):
        res = client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "X", "kb_type": "invalid", "text": "テスト"},
        )
        assert res.status_code == 400

    def test_create_empty_text(self, client):
        res = client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "空テスト", "kb_type": "resume", "text": "   "},
        )
        assert res.status_code == 400

    def test_delete_kb(self, client):
        create = client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "削除KB", "kb_type": "company", "text": "企業情報テスト"},
        )
        kb_id = create.json()["id"]
        del_res = client.delete(f"/api/v1/knowledge-bases/{kb_id}")
        assert del_res.status_code == 204
        get_res = client.get(f"/api/v1/knowledge-bases/{kb_id}")
        assert get_res.status_code == 404

    def test_toggle_active(self, client):
        create = client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "トグルKB", "kb_type": "resume", "text": "テスト"},
        )
        kb_id = create.json()["id"]
        res = client.patch(
            f"/api/v1/knowledge-bases/{kb_id}/active",
            json={"is_active": False},
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is False

    def test_list_filter_by_type(self, client):
        client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "履歴書フィルタ", "kb_type": "resume", "text": "テスト"},
        )
        client.post(
            "/api/v1/knowledge-bases/text",
            json={"name": "企業フィルタ", "kb_type": "company", "text": "テスト"},
        )
        res = client.get("/api/v1/knowledge-bases/?kb_type=resume")
        assert res.status_code == 200
        assert all(k["kb_type"] == "resume" for k in res.json())


# ============================================================
# GET /api/v1/mock-interview/personas
# GET /api/v1/mock-interview/themes
# POST /api/v1/mock-interview/start  （LLM をモック）
# POST /api/v1/mock-interview/evaluate （LLM をモック）
# ============================================================

class TestMockInterview:

    def test_list_personas(self, client):
        res = client.get("/api/v1/mock-interview/personas")
        assert res.status_code == 200
        personas = res.json()
        assert isinstance(personas, list)
        assert len(personas) > 0
        assert all("key" in p and "name" in p for p in personas)

    def test_list_themes(self, client):
        res = client.get("/api/v1/mock-interview/themes")
        assert res.status_code == 200
        themes = res.json()
        assert isinstance(themes, list)
        assert len(themes) > 0
        assert all("title" in t for t in themes)

    def test_start_interview(self, client):
        """InterviewService.start をモックして LLM なしでテスト。"""
        from services.interview_service import StartResult
        mock_result = StartResult(
            theme_index=0,
            theme_title="自己紹介",
            question="まず自己紹介をお願いします。",
        )
        with patch(
            "api.routes.mock_interview.InterviewService.start",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            res = client.post(
                "/api/v1/mock-interview/start",
                json={
                    "industry_key": "general",
                    "persona_key": "standard",
                    "profile_text": "テスト学生",
                },
            )
        assert res.status_code == 200
        body = res.json()
        assert body["theme_title"] == "自己紹介"
        assert "まず自己紹介" in body["question"]

    def test_evaluate(self, client):
        """InterviewService.evaluate をモックしてテスト。"""
        mock_eval = {
            "ok": True,
            "overall_score": 78,
            "axes": {"論理性": 80, "熱意": 75},
            "strengths": ["具体的なエピソードがある"],
            "improvements": ["結論を先に言う"],
            "next_steps": ["STAR法を練習する"],
        }
        with patch(
            "api.routes.mock_interview.InterviewService.evaluate",
            new_callable=AsyncMock,
            return_value=mock_eval,
        ):
            res = client.post(
                "/api/v1/mock-interview/evaluate",
                json={
                    "messages": [
                        {"role": "assistant", "content": "自己紹介をどうぞ。"},
                        {"role": "user", "content": "はい、田中と申します。"},
                    ],
                    "industry_key": "general",
                    "profile_text": "",
                },
            )
        assert res.status_code == 200
        body = res.json()
        assert body["overall_score"] == 78
        assert len(body["strengths"]) > 0
