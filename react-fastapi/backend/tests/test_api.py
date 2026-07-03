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


# ============================================================
# GET/POST/DELETE /api/v1/favorites
# ============================================================

class TestFavorites:

    def test_create_and_list_favorite(self, client):
        res = client.post(
            "/api/v1/favorites",
            json={
                "item_type": "question_set",
                "session_id": 1,
                "company_name": "テスト企業",
                "label": "想定質問 - テスト企業",
                "content_snapshot": {"question_count": 8},
            },
        )
        assert res.status_code == 200
        fav_id = res.json()["id"]
        assert isinstance(fav_id, int)

        res = client.get("/api/v1/favorites", params={"item_type": "question_set"})
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 1
        assert items[0]["id"] == fav_id
        assert items[0]["content_snapshot"] == {"question_count": 8}

    def test_create_favorite_is_idempotent(self, client):
        """同一 (item_type, item_id, session_id) は重複追加されず同じIDを返す。"""
        payload = {"item_type": "personality", "session_id": 5}
        res1 = client.post("/api/v1/favorites", json=payload)
        res2 = client.post("/api/v1/favorites", json=payload)
        assert res1.json()["id"] == res2.json()["id"]

    def test_is_favorited(self, client):
        client.post("/api/v1/favorites", json={"item_type": "company_matrix", "session_id": 42})

        res = client.get(
            "/api/v1/favorites/is-favorited",
            params={"item_type": "company_matrix", "session_id": 42},
        )
        assert res.status_code == 200
        assert res.json()["favorited"] is True

        res = client.get(
            "/api/v1/favorites/is-favorited",
            params={"item_type": "company_matrix", "session_id": 999},
        )
        assert res.json()["favorited"] is False

    def test_delete_favorite_by_item(self, client):
        client.post("/api/v1/favorites", json={"item_type": "career_advice", "session_id": 7})
        res = client.delete(
            "/api/v1/favorites/by-item",
            params={"item_type": "career_advice", "session_id": 7},
        )
        assert res.status_code == 200

        res = client.get(
            "/api/v1/favorites/is-favorited",
            params={"item_type": "career_advice", "session_id": 7},
        )
        assert res.json()["favorited"] is False

    def test_delete_favorite_by_id(self, client):
        create_res = client.post("/api/v1/favorites", json={"item_type": "interview", "session_id": 9})
        fav_id = create_res.json()["id"]

        res = client.delete(f"/api/v1/favorites/{fav_id}")
        assert res.status_code == 200

        res = client.get("/api/v1/favorites", params={"item_type": "interview"})
        assert all(item["id"] != fav_id for item in res.json())

    def test_meta(self, client):
        client.post(
            "/api/v1/favorites",
            json={"item_type": "question_set", "session_id": 1, "company_name": "テスト企業"},
        )
        res = client.get("/api/v1/favorites/meta")
        assert res.status_code == 200
        body = res.json()
        assert "テスト企業" in body["companies"]
        assert body["count"] >= 1
        assert "question_set" in body["item_type_labels"]


# ============================================================
# POST /api/v1/predicted-questions/generate
# POST /api/v1/predicted-questions/save-and-favorite
# ============================================================

class TestPredictedQuestions:

    def test_generate_success(self, client):
        """PredictionService.generate をモックして LLM なしでテスト。"""
        from services.prediction_service import GenerateResult, PredictedQuestion

        mock_result = GenerateResult(
            questions=[
                PredictedQuestion(
                    category="deep_dive",
                    category_label="🔍 深掘り",
                    question="そのエピソードで最も苦労した点は？",
                    model_answer="最も苦労したのは...",
                ),
            ]
        )
        with patch(
            "api.routes.predicted_questions.PredictionService.generate",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            res = client.post(
                "/api/v1/predicted-questions/generate",
                json={"company_kb_id": 1},
            )
        assert res.status_code == 200
        body = res.json()
        assert len(body["questions"]) == 1
        assert body["questions"][0]["category"] == "deep_dive"

    def test_generate_insufficient_material_returns_400(self, client):
        from services.prediction_service import InsufficientMaterialError

        with patch(
            "api.routes.predicted_questions.PredictionService.generate",
            new_callable=AsyncMock,
            side_effect=InsufficientMaterialError("履歴書・企業情報のどちらも見つかりませんでした。"),
        ):
            res = client.post(
                "/api/v1/predicted-questions/generate",
                json={"company_kb_id": 1},
            )
        assert res.status_code == 400

    def test_generate_failure_returns_500(self, client):
        from services.prediction_service import GenerationFailedError

        with patch(
            "api.routes.predicted_questions.PredictionService.generate",
            new_callable=AsyncMock,
            side_effect=GenerationFailedError("生成に失敗しました。"),
        ):
            res = client.post(
                "/api/v1/predicted-questions/generate",
                json={"company_kb_id": 1},
            )
        assert res.status_code == 500

    def test_save_and_favorite(self, client):
        with patch(
            "api.routes.predicted_questions.PredictionService.save_and_favorite",
            new_callable=AsyncMock,
            return_value=(1, 1),
        ):
            res = client.post(
                "/api/v1/predicted-questions/save-and-favorite",
                json={
                    "company_kb_id": 1,
                    "company_name": "テスト企業",
                    "questions": [
                        {
                            "category": "deep_dive",
                            "category_label": "🔍 深掘り",
                            "question": "Q1",
                            "model_answer": "A1",
                        }
                    ],
                },
            )
        assert res.status_code == 200
        body = res.json()
        assert body["session_id"] == 1
        assert body["favorite_id"] == 1


# ============================================================
# GET /api/v1/version
# ============================================================

class TestVersion:

    def test_get_version(self, client):
        res = client.get("/api/v1/version")
        assert res.status_code == 200
        body = res.json()
        assert "version" in body
        assert isinstance(body["version"], str)
        assert body["version"] != ""


# ============================================================
# POST /api/v1/interview/*
# ============================================================

class TestInterviewFlow:

    def test_start(self, client):
        from services.interview_flow_service import QuestionResult

        with patch(
            "api.routes.interview.InterviewFlowService.start",
            new_callable=AsyncMock,
            return_value=QuestionResult(status="question", theme_index=0, theme_title="学歴・専攻", question="Q?", questions_asked_in_theme=1),
        ):
            res = client.post("/api/v1/interview/start", json={"profile_text": ""})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "question"
        assert body["theme_title"] == "学歴・専攻"

    def test_next_question(self, client):
        from services.interview_flow_service import QuestionResult

        with patch(
            "api.routes.interview.InterviewFlowService.next_question",
            new_callable=AsyncMock,
            return_value=QuestionResult(status="complete"),
        ):
            res = client.post(
                "/api/v1/interview/next",
                json={
                    "theme_index": 3,
                    "theme_messages": [{"role": "assistant", "content": "Q"}, {"role": "user", "content": "A"}],
                    "questions_asked_in_theme": 1,
                    "selected_category": None,
                    "profile_text": "",
                    "messages": [],
                },
            )
        assert res.status_code == 200
        assert res.json()["status"] == "complete"

    def test_choose_category(self, client):
        from services.interview_flow_service import QuestionResult

        with patch(
            "api.routes.interview.InterviewFlowService.choose_category",
            new_callable=AsyncMock,
            return_value=QuestionResult(status="question", theme_index=1, theme_title="熱中したこと", question="Q?", questions_asked_in_theme=1),
        ):
            res = client.post(
                "/api/v1/interview/choose-category",
                json={"theme_index": 1, "category": "アルバイト", "profile_text": "", "messages": []},
            )
        assert res.status_code == 200
        assert res.json()["question"] == "Q?"

    def test_summary(self, client):
        mock_summary = {
            "strengths": [{"point": "粘り強さ", "evidence": "3年間継続"}],
            "weaknesses": [], "fit_roles": "営業職", "industry_fit": {}, "overall_comment": "良い",
        }
        with patch(
            "api.routes.interview.InterviewFlowService.generate_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ):
            res = client.post("/api/v1/interview/summary", json={"profile_text": "", "messages": []})
        assert res.status_code == 200
        assert res.json()["fit_roles"] == "営業職"

    def test_summary_failure_returns_500(self, client):
        with patch(
            "api.routes.interview.InterviewFlowService.generate_summary",
            new_callable=AsyncMock,
            side_effect=RuntimeError("失敗しました"),
        ):
            res = client.post("/api/v1/interview/summary", json={"profile_text": "", "messages": []})
        assert res.status_code == 500

    def test_pr_variants(self, client):
        mock_variants = [{"type": "result", "label": "結果重視型", "content": "PR本文"}]
        with patch(
            "api.routes.interview.InterviewFlowService.generate_variants",
            new_callable=AsyncMock,
            return_value=mock_variants,
        ):
            res = client.post("/api/v1/interview/pr/variants", json={"profile_text": "", "messages": []})
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_pr_evaluate(self, client):
        mock_eval = {"scores": {"具体性": 4}, "summary": "良い", "improvements": []}
        with patch(
            "api.routes.interview.InterviewFlowService.evaluate",
            new_callable=AsyncMock,
            return_value=mock_eval,
        ):
            res = client.post("/api/v1/interview/pr/evaluate", json={"pr_text": "PR本文"})
        assert res.status_code == 200
        assert res.json()["summary"] == "良い"

    def test_pr_refine(self, client):
        mock_result = {"pr_text": "リライト後", "ok": True, "error_msg": None}
        with patch(
            "api.routes.interview.InterviewFlowService.refine",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            res = client.post(
                "/api/v1/interview/pr/refine",
                json={"pr_text": "PR本文", "instruction": "もっと簡潔に", "profile_text": "", "messages": []},
            )
        assert res.status_code == 200
        assert res.json()["pr_text"] == "リライト後"

    def test_pr_refine_presets(self, client):
        res = client.get("/api/v1/interview/pr/refine-presets")
        assert res.status_code == 200
        body = res.json()
        assert "concise" in body

    def test_pr_company(self, client):
        mock_results = [{"company_name": "テスト企業", "pr_text": "カスタムPR", "points": [], "ok": True, "error_msg": None}]
        with patch(
            "api.routes.interview.InterviewFlowService.generate_company_prs",
            new_callable=AsyncMock,
            return_value=mock_results,
        ):
            res = client.post(
                "/api/v1/interview/pr/company",
                json={
                    "base_pr": "ベースPR",
                    "companies": [{"name": "テスト企業", "info": "情報"}],
                    "profile_text": "",
                    "messages": [],
                },
            )
        assert res.status_code == 200
        assert res.json()[0]["company_name"] == "テスト企業"


# ============================================================
# POST /api/v1/predicted-questions/generate-from-pr
# POST /api/v1/predicted-questions/save-and-favorite-pr-based
# ============================================================

class TestPredictedQuestionsFromPr:

    def test_generate_from_pr(self, client):
        from services.prediction_service import GenerateResult, PredictedQuestion

        mock_result = GenerateResult(
            questions=[
                PredictedQuestion(category="motivation", category_label="💡 動機", question="Q?", model_answer="A"),
            ]
        )
        with patch(
            "api.routes.predicted_questions.PredictionService.generate_from_pr",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            res = client.post(
                "/api/v1/predicted-questions/generate-from-pr",
                json={"pr_text": "自己PR本文", "profile_text": "", "messages": []},
            )
        assert res.status_code == 200
        assert len(res.json()["questions"]) == 1

    def test_save_and_favorite_pr_based(self, client):
        with patch(
            "api.routes.predicted_questions.PredictionService.save_and_favorite_pr_based",
            new_callable=AsyncMock,
            return_value=(1, 1),
        ):
            res = client.post(
                "/api/v1/predicted-questions/save-and-favorite-pr-based",
                json={
                    "questions": [
                        {"category": "motivation", "category_label": "💡 動機", "question": "Q?", "model_answer": "A"}
                    ],
                    "company_name": None,
                },
            )
        assert res.status_code == 200
        body = res.json()
        assert body["session_id"] == 1
        assert body["favorite_id"] == 1
