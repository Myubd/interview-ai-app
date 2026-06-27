# -*- coding: utf-8 -*-
"""
tests/test_integration.py
--------------------------
DB を使うインテグレーションテスト。
ollama は不要（モック済み）。

対象:
  db/session_repository.py
  db/settings_repository.py
  db/knowledge_base_repository.py
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


# ============================================================
# セッションリポジトリ
# ============================================================

class TestSessionRepository:

    def test_create_and_list(self, tmp_db):
        from db.session_repository import save_session, list_sessions
        sid = save_session(company_name="テスト株式会社", session_type="mock")
        assert isinstance(sid, int)
        sessions = list_sessions()
        ids = [s["id"] for s in sessions]
        assert sid in ids

    def test_get_session(self, tmp_db):
        from db.session_repository import save_session, get_session
        sid = save_session(company_name="A社", session_type="mock")
        result = get_session(sid)
        assert result is not None
        assert result["session"]["company_name"] == "A社"

    def test_get_nonexistent_returns_none(self, tmp_db):
        from db.session_repository import get_session
        assert get_session(99999) is None

    def test_delete_session(self, tmp_db):
        from db.session_repository import save_session, delete_session, get_session
        sid = save_session(company_name="削除テスト")
        delete_session(sid)
        assert get_session(sid) is None

    def test_save_messages(self, tmp_db):
        from db.session_repository import save_session, get_session
        messages = [
            {"role": "assistant", "content": "自己紹介をしてください。"},
            {"role": "user",      "content": "はい、田中です。"},
        ]
        sid = save_session(company_name="B社", messages=messages)
        result = get_session(sid)
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "自己紹介をしてください。"

    def test_update_via_save_session(self, tmp_db):
        from db.session_repository import save_session, get_session
        sid = save_session(company_name="C社")
        save_session(
            session_id=sid,
            direct_values={"interview_complete": True},
        )
        result = get_session(sid)
        assert result["session"]["interview_complete"] in (True, 1)


# ============================================================
# 設定リポジトリ
# ============================================================

class TestSettingsRepository:

    def test_get_default_none(self, tmp_db):
        from db.settings_repository import get_setting
        assert get_setting("nonexistent_key") is None

    def test_set_and_get(self, tmp_db):
        from db.settings_repository import get_setting, set_setting
        set_setting("chat_model", "qwen3:8b")
        assert get_setting("chat_model") == "qwen3:8b"

    def test_overwrite(self, tmp_db):
        from db.settings_repository import get_setting, set_setting
        set_setting("chat_model", "first")
        set_setting("chat_model", "second")
        assert get_setting("chat_model") == "second"


# ============================================================
# ナレッジベースリポジトリ
# ============================================================

class TestKnowledgeBaseRepository:

    def test_create_and_get(self, tmp_db):
        from db.knowledge_base_repository import (
            get_or_create_knowledge_base,
            get_knowledge_base,
        )
        kb_id = get_or_create_knowledge_base("履歴書A", "resume")
        assert isinstance(kb_id, int)
        kb = get_knowledge_base(kb_id)
        assert kb is not None
        assert kb["name"] == "履歴書A"
        assert kb["kb_type"] == "resume"

    def test_list(self, tmp_db):
        from db.knowledge_base_repository import (
            get_or_create_knowledge_base,
            list_knowledge_bases,
        )
        get_or_create_knowledge_base("履歴書B", "resume")
        get_or_create_knowledge_base("企業C", "company")
        all_kbs = list_knowledge_bases()
        assert len(all_kbs) >= 2

    def test_list_filter_by_type(self, tmp_db):
        from db.knowledge_base_repository import (
            get_or_create_knowledge_base,
            list_knowledge_bases,
        )
        get_or_create_knowledge_base("履歴書D", "resume")
        get_or_create_knowledge_base("企業E", "company")
        resumes = list_knowledge_bases(kb_type="resume")
        assert all(k["kb_type"] == "resume" for k in resumes)

    def test_delete(self, tmp_db):
        from db.knowledge_base_repository import (
            get_or_create_knowledge_base,
            delete_knowledge_base,
            get_knowledge_base,
        )
        kb_id = get_or_create_knowledge_base("削除KB", "resume")
        delete_knowledge_base(kb_id)
        assert get_knowledge_base(kb_id) is None

    def test_get_or_create_idempotent(self, tmp_db):
        """同名・同タイプで2回呼んでも同じ ID が返る。"""
        from db.knowledge_base_repository import get_or_create_knowledge_base
        id1 = get_or_create_knowledge_base("重複テスト", "resume")
        id2 = get_or_create_knowledge_base("重複テスト", "resume")
        assert id1 == id2
