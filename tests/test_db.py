# -*- coding: utf-8 -*-
"""
tests/test_db.py
-----------------
DB層（db/database.py / session_repository / settings_repository）のテスト。

pytest 実行時は conftest.py の tmp_db フィクスチャにより
テストごとに新鮮な一時 SQLite ファイルが作られ、環境変数 INTERVIEW_DB_PATH
でリポジトリ全体を同一ファイルに向ける。実ファイルへの書き込みは行わない。
"""
from __future__ import annotations

import json
import sqlite3

import pytest


# ============================================================
# db.database
# ============================================================

class TestDatabase:
    """init_db / get_connection / db_session の基本動作。"""

    def test_init_db_creates_tables(self, tmp_db):
        """init_db 後に主要テーブルが存在することを確認。"""
        from db.database import get_connection
        conn = get_connection(tmp_db)
        tables = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        for expected in ("sessions", "messages", "settings", "knowledge_bases",
                         "documents", "document_chunks", "favorites"):
            assert expected in tables, f"テーブル {expected} が存在しない"

    def test_init_db_is_idempotent(self, tmp_db):
        """init_db を複数回呼んでもエラーにならない（冪等性）。"""
        from db.database import init_db
        init_db(tmp_db)  # 2回目

    def test_get_connection_returns_sqlite_row_factory(self, tmp_db):
        """get_connection の row_factory が sqlite3.Row であることを確認。"""
        from db.database import get_connection
        conn = get_connection(tmp_db)
        assert conn.row_factory is sqlite3.Row
        conn.close()

    def test_foreign_keys_enabled(self, tmp_db):
        """外部キー制約が有効になっていることを確認。"""
        from db.database import get_connection
        conn = get_connection(tmp_db)
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()

    def test_db_session_context_manager_commit(self, tmp_db):
        """db_session で正常終了した場合、データがコミットされる。"""
        from db.database import db_session, get_connection
        with db_session(tmp_db) as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                ("ctx_test_key", "ctx_test_value"),
            )
        # コミットされているか確認
        conn2 = get_connection(tmp_db)
        row = conn2.execute(
            "SELECT value FROM settings WHERE key = ?", ("ctx_test_key",)
        ).fetchone()
        conn2.close()
        assert row is not None
        assert row["value"] == "ctx_test_value"

    def test_db_session_rollback_on_exception(self, tmp_db):
        """db_session 内で例外が起きた場合はロールバックされる。"""
        from db.database import db_session, get_connection
        with pytest.raises(ValueError):
            with db_session(tmp_db) as conn:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    ("rollback_key", "v"),
                )
                raise ValueError("強制ロールバック")
        # ロールバックされているか確認
        conn2 = get_connection(tmp_db)
        row = conn2.execute(
            "SELECT value FROM settings WHERE key = ?", ("rollback_key",)
        ).fetchone()
        conn2.close()
        assert row is None

    def test_env_var_db_path_used(self, monkeypatch):
        """INTERVIEW_DB_PATH 環境変数が接続先として使われる。"""
        from db.database import _resolve_db_path
        monkeypatch.setenv("INTERVIEW_DB_PATH", "/tmp/custom_test.db")
        assert _resolve_db_path() == "/tmp/custom_test.db"

    def test_default_db_path_when_env_not_set(self, monkeypatch):
        """INTERVIEW_DB_PATH が未設定の場合はデフォルトパスを返す。"""
        from db.database import _resolve_db_path
        monkeypatch.delenv("INTERVIEW_DB_PATH", raising=False)
        path = _resolve_db_path()
        assert path.endswith("career_support.db")

    def test_schema_migrations_table_created(self, tmp_db):
        """マイグレーション管理テーブルが作成されていること。"""
        from db.database import get_connection
        conn = get_connection(tmp_db)
        tables = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert "schema_migrations" in tables

    def test_indexes_created(self, tmp_db):
        """パフォーマンス用インデックスが作成されていること。"""
        from db.database import get_connection
        conn = get_connection(tmp_db)
        indexes = {
            r[0] for r in
            conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        conn.close()
        for expected in ("idx_sessions_created_at", "idx_messages_session_id",
                         "idx_documents_kb_id", "idx_chunks_document_id"):
            assert expected in indexes, f"インデックス {expected} が存在しない"


# ============================================================
# db.session_repository
# ============================================================

class TestSessionRepository:
    """sessions / messages テーブルの CRUD テスト。"""

    def test_save_session_creates_new_session(self, tmp_db):
        """session_id=None で呼ぶと新規セッションが作成され、IDが返る。"""
        from db.session_repository import save_session
        sid = save_session(company_name="テスト株式会社", session_type="一次面接")
        assert isinstance(sid, int)
        assert sid > 0

    def test_save_session_returns_incremented_id(self, tmp_db):
        """2回保存すると異なるIDが返る（連番）。"""
        from db.session_repository import save_session
        sid1 = save_session(company_name="A社")
        sid2 = save_session(company_name="B社")
        assert sid2 > sid1

    def test_get_session_returns_saved_data(self, tmp_db):
        """保存したデータが get_session で取得できる。"""
        from db.session_repository import save_session, get_session
        sid = save_session(
            company_name="サンプル株式会社",
            session_type="模擬面接",
            direct_values={"profile_text": "東京大学工学部"},
        )
        result = get_session(sid)
        assert result is not None
        assert result["session"]["company_name"] == "サンプル株式会社"
        assert result["session"]["session_type"] == "模擬面接"
        assert result["session"]["profile_text"] == "東京大学工学部"

    def test_get_session_nonexistent_returns_none(self, tmp_db):
        """存在しないIDを渡すと None が返る。"""
        from db.session_repository import get_session
        assert get_session(99999) is None

    def test_save_session_update_existing(self, tmp_db):
        """既存 session_id を渡すと更新される。"""
        from db.session_repository import save_session, get_session
        sid = save_session(company_name="更新前株式会社")
        save_session(
            session_id=sid,
            company_name="更新後株式会社",
            direct_values={"interview_complete": True},
        )
        result = get_session(sid)
        assert result["session"]["company_name"] == "更新後株式会社"
        assert result["session"]["interview_complete"] == 1

    def test_save_session_with_messages(self, tmp_db):
        """messages を渡すとメッセージが保存される。"""
        from db.session_repository import save_session, get_session
        messages = [
            {"role": "assistant", "content": "よろしくお願いします。", "theme_index": 0},
            {"role": "user", "content": "はい、よろしくお願いします。", "theme_index": 0},
        ]
        sid = save_session(company_name="メッセージ付き", messages=messages)
        result = get_session(sid)
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "assistant"
        assert result["messages"][1]["content"] == "はい、よろしくお願いします。"

    def test_save_session_messages_replaced_on_update(self, tmp_db):
        """更新時にメッセージは全件入れ替えられる。"""
        from db.session_repository import save_session, get_session
        sid = save_session(
            company_name="A社",
            messages=[{"role": "user", "content": "古いメッセージ", "theme_index": 0}],
        )
        save_session(
            session_id=sid,
            messages=[
                {"role": "assistant", "content": "新しいメッセージ1", "theme_index": 1},
                {"role": "user", "content": "新しいメッセージ2", "theme_index": 1},
            ],
        )
        result = get_session(sid)
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == "新しいメッセージ1"

    def test_save_session_json_values(self, tmp_db):
        """json_values で渡したリストデータが正しく保存・取得できる。"""
        from db.session_repository import save_session, get_session
        sid = save_session(
            company_name="JSON株式会社",
            json_values={"predicted_questions": ["Q1", "Q2", "Q3"]},
        )
        result = get_session(sid)
        raw = result["session"]["predicted_questions"]
        parsed = json.loads(raw) if raw else []
        assert parsed == ["Q1", "Q2", "Q3"]

    def test_save_session_progress_state(self, tmp_db):
        """progress_state が JSON 文字列として保存される。"""
        from db.session_repository import save_session, get_session
        state = {
            "interview_started": True,
            "current_theme_index": 2,
            "questions_asked_in_theme": 1,
        }
        sid = save_session(company_name="進捗テスト", progress_state=state)
        result = get_session(sid)
        raw = result["session"]["progress_state"]
        parsed = json.loads(raw) if raw else {}
        assert parsed["current_theme_index"] == 2

    def test_list_sessions_empty(self, tmp_db):
        """セッションが1件もないときは空リストを返す。"""
        from db.session_repository import list_sessions
        result = list_sessions()
        assert isinstance(result, list)
        assert result == []

    def test_list_sessions_returns_all(self, tmp_db):
        """保存したセッションが全件 list_sessions に含まれる。"""
        from db.session_repository import save_session, list_sessions
        save_session(company_name="一覧テストA")
        save_session(company_name="一覧テストB")
        sessions = list_sessions()
        assert len(sessions) == 2
        companies = [s["company_name"] for s in sessions]
        assert "一覧テストA" in companies
        assert "一覧テストB" in companies

    def test_save_session_mock_evaluation(self, tmp_db):
        """mock_evaluation が正しくシリアライズ・デシリアライズされる。"""
        from db.session_repository import save_session, get_session
        evaluation = {
            "overall_summary": "良い面接でした。",
            "scores": {"論理構成": 4, "具体性": 3},
            "top_strengths": ["明確", "具体的"],
        }
        sid = save_session(company_name="評価テスト", mock_evaluation=evaluation)
        result = get_session(sid)
        raw = result["session"]["mock_interview_evaluation"]
        parsed = json.loads(raw) if raw else {}
        assert parsed["overall_summary"] == "良い面接でした。"
        assert parsed["scores"]["論理構成"] == 4

    def test_company_name_not_overwritten_when_unset(self, tmp_db):
        """company_name を省略して更新すると、既存の値が保持される。"""
        from db.session_repository import save_session, get_session
        sid = save_session(company_name="元の会社名")
        save_session(session_id=sid, direct_values={"profile_text": "更新のみ"})
        result = get_session(sid)
        assert result["session"]["company_name"] == "元の会社名"

    def test_empty_messages_list(self, tmp_db):
        """messages=[] で更新するとメッセージが0件になる。"""
        from db.session_repository import save_session, get_session
        sid = save_session(
            company_name="空メッセージ",
            messages=[{"role": "user", "content": "初回", "theme_index": 0}],
        )
        save_session(session_id=sid, messages=[])
        result = get_session(sid)
        assert result["messages"] == []

    def test_messages_order_preserved(self, tmp_db):
        """メッセージが保存順（id ASC）で返される。"""
        from db.session_repository import save_session, get_session
        msgs = [
            {"role": "assistant", "content": f"質問{i}", "theme_index": 0}
            for i in range(5)
        ]
        sid = save_session(company_name="順序テスト", messages=msgs)
        result = get_session(sid)
        for i, msg in enumerate(result["messages"]):
            assert msg["content"] == f"質問{i}"


# ============================================================
# db.settings_repository
# ============================================================

class TestSettingsRepository:
    """settings テーブルの CRUD テスト。"""

    def test_set_and_get_setting(self, tmp_db):
        """set_setting で保存した値が get_setting で取得できる。"""
        from db.settings_repository import set_setting, get_setting
        set_setting("model_name", "qwen3:8b")
        assert get_setting("model_name") == "qwen3:8b"

    def test_get_setting_default_when_missing(self, tmp_db):
        """存在しないキーは default 値を返す。"""
        from db.settings_repository import get_setting
        assert get_setting("nonexistent_key", default="DEFAULT") == "DEFAULT"

    def test_get_setting_none_when_no_default(self, tmp_db):
        """存在しないキーで default 省略時は None を返す。"""
        from db.settings_repository import get_setting
        assert get_setting("another_nonexistent") is None

    def test_set_setting_overwrite(self, tmp_db):
        """同じキーに set_setting を2回呼ぶと上書きされる。"""
        from db.settings_repository import set_setting, get_setting
        set_setting("overwrite_key", "初回値")
        set_setting("overwrite_key", "上書き値")
        assert get_setting("overwrite_key") == "上書き値"

    def test_delete_setting(self, tmp_db):
        """delete_setting 後は get_setting が None を返す。"""
        from db.settings_repository import set_setting, get_setting, delete_setting
        set_setting("delete_me", "temporary")
        delete_setting("delete_me")
        assert get_setting("delete_me") is None

    def test_delete_nonexistent_setting_no_error(self, tmp_db):
        """存在しないキーを delete しても例外にならない。"""
        from db.settings_repository import delete_setting
        delete_setting("never_existed_key")

    def test_get_all_settings_empty(self, tmp_db):
        """設定が1件もないとき get_all_settings は空 dict を返す。"""
        from db.settings_repository import get_all_settings
        assert get_all_settings() == {}

    def test_get_all_settings_returns_all(self, tmp_db):
        """複数の設定を保存すると get_all_settings に全件含まれる。"""
        from db.settings_repository import set_setting, get_all_settings
        set_setting("key_alpha", "value_alpha")
        set_setting("key_beta", "value_beta")
        all_settings = get_all_settings()
        assert all_settings["key_alpha"] == "value_alpha"
        assert all_settings["key_beta"] == "value_beta"

    def test_set_setting_none_value(self, tmp_db):
        """value=None で設定を保存でき、get_setting が None を返す。"""
        from db.settings_repository import set_setting, get_setting
        set_setting("null_value_key", None)
        result = get_setting("null_value_key", default="SHOULD_NOT_APPEAR")
        assert result is None

    def test_set_setting_special_characters(self, tmp_db):
        """日本語・記号を含む値も正しく保存・取得できる。"""
        from db.settings_repository import set_setting, get_setting
        set_setting("japanese_key", "日本語の値：テスト！")
        assert get_setting("japanese_key") == "日本語の値：テスト！"
