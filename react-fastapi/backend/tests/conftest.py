# -*- coding: utf-8 -*-
"""
tests/conftest.py
------------------
pytest 共通フィクスチャ。

設計方針:
  - ollama は sys.modules に差し込んだモックで完全にオフライン実行
  - DB は tempfile の一時 SQLite ファイルを使い、環境変数で向き先を制御
  - FastAPI TestClient は DB 初期化済みの状態で提供

マーカー:
  unit        外部依存なし（純粋関数テスト）
  integration DB を使うテスト（ollama は不要）
  api         TestClient を使うエンドポイントテスト
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── sys.path ───────────────────────────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# shared/ はフォールバック専用として末尾に追加する（db/・rag/ は
# backend/ 側の実装を優先させる必要があるため、先頭に insert しない。
# main.py の起動ブートストラップと同じ理由。詳細は main.py 内のコメント
# および shared/MIGRATION_GUIDE.md を参照）。
_SHARED_DIR = BACKEND_ROOT / "shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.append(str(_SHARED_DIR))

# ── ollama モックを最優先で差し込む ────────────────────────
#    import より前に差し込まないと本物が呼ばれる
if "ollama" not in sys.modules:
    _mock_ollama = types.ModuleType("ollama")
    _mock_ollama.Client = MagicMock()
    _mock_ollama.AsyncClient = MagicMock()
    _mock_ollama.chat = MagicMock(return_value={"message": {"content": "{}"}})
    _mock_ollama.embeddings = MagicMock(return_value={"embedding": [0.1] * 768})
    sys.modules["ollama"] = _mock_ollama


# ── 一時 DB フィクスチャ ────────────────────────────────────

@pytest.fixture()
def tmp_db_path(monkeypatch, tmp_path):
    """テストごとに新鮮な一時 SQLite ファイルパスを返す。"""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("INTERVIEW_DB_PATH", db_file)
    return db_file


@pytest.fixture()
def tmp_db(tmp_db_path):
    """init_db 済みの一時 DB パスを返す。"""
    from db.database import init_db
    init_db(tmp_db_path)
    return tmp_db_path


# ── FastAPI TestClient フィクスチャ ─────────────────────────

@pytest.fixture()
def client(tmp_db):
    """DB 初期化済みの TestClient を返す。"""
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c
