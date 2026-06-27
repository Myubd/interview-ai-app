# -*- coding: utf-8 -*-
"""
tests/conftest.py
-----------------
pytest 共通フィクスチャ。

設計上の注意:
    SQLite の ":memory:" データベースは「接続ごとに独立した DB」になる。
    init_db() と get_connection() が別々に接続を張ると別DBを参照してしまうため、
    テストでは tmpdir に一時ファイルDBを作り、環境変数 INTERVIEW_DB_PATH で
    全リポジトリ関数を同一ファイルに向ける方式を採用する。

フィクスチャ一覧:
    tmp_db_path  : テストごとに新鮮な一時DBファイルパスを返す (autouse=False)
    tmp_db       : tmp_db_path で init_db 済みのパスを返す（リポジトリテスト用）
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── sys.path 設定 ──────────────────────────────────────────────────────────────
APP_ROOT = Path(__file__).resolve().parent.parent   # interview_app_new/
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# ── ollama モックを最優先で差し込む ──────────────────────────────────────────
import types as _types
from unittest.mock import MagicMock
if "ollama" not in sys.modules:
    _mock = _types.ModuleType("ollama")
    # chat / embeddings をダミー属性として持たせておく。
    # 各テストでは patch() で上書きするため、ここでの戻り値は何でもよい。
    _mock.chat = MagicMock(return_value={"message": {"content": "{}"}})
    _mock.embeddings = MagicMock(return_value={"embedding": []})
    sys.modules["ollama"] = _mock


# ── 一時DBファイル フィクスチャ ───────────────────────────────────────────────

@pytest.fixture()
def tmp_db_path(monkeypatch, tmp_path):
    """テストごとに新鮮な一時 SQLite ファイルを作り、そのパスを返す。

    INTERVIEW_DB_PATH 環境変数をそのパスに設定するため、
    各リポジトリ関数（db_session() を内部で使うもの）は自動的にこのDBを参照する。
    テスト終了後は tmp_path が自動削除される。
    """
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("INTERVIEW_DB_PATH", db_file)
    return db_file


@pytest.fixture()
def tmp_db(tmp_db_path):
    """init_db 済みの一時DBパスを返す（セッション・設定リポジトリのテスト用）。"""
    from db.database import init_db
    init_db(tmp_db_path)
    return tmp_db_path
