# -*- coding: utf-8 -*-
"""
db/database.py
---------------
SQLite接続管理とスキーマ初期化を行うモジュール。

設計方針:
- DBファイルは環境変数 INTERVIEW_DB_PATH で上書き可能。
  未設定時は db/career_support.db （ローカル単一ユーザー前提）。
  テスト時は ":memory:" を渡すことでインメモリDBを使用できる。
- 外部キー制約を有効化（PRAGMA foreign_keys = ON）
- 日本語データの文字化け防止のため、接続時にエンコーディング関連の設定は
  SQLite標準（UTF-8前提）に任せる。Python の sqlite3 は str <-> TEXT を
  自動的にUTF-8でやり取りするため、明示的な変換は不要。
- スキーマは "CREATE TABLE IF NOT EXISTS" で冪等に初期化できるようにする
  （アプリ起動のたびに呼んでも安全）。
"""

from __future__ import annotations

import os
import sys
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# このファイル（db/database.py）からの相対パスで db/career_support.db を指す
_DB_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _DB_DIR / "career_support.db"


def _resolve_db_path() -> str:
    """環境変数 INTERVIEW_DB_PATH が設定されていればそれを使い、なければデフォルトパスを返す。

    ":memory:" を渡すとインメモリDBになる（テスト用途）。

    PyInstaller でビルドした .exe の場合、__file__ は読み取り専用の
    _internal フォルダ（例: C:\\Program Files (x86)\\InterviewApp\\_internal\\）
    を指すため、DBファイルの作成に失敗する。
    sys.frozen が True のときは書き込み可能な %APPDATA%\\InterviewApp\\db\\ を使う。
    """
    env_path = os.environ.get("INTERVIEW_DB_PATH", "")
    if env_path:
        logger.debug("DB path from env: %s", env_path)
        return env_path

    # PyInstaller ビルド時: sys.frozen = True がセットされる
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA") or str(Path.home())
        base = Path(appdata) / "InterviewApp" / "db"
        logger.debug("Running as frozen executable, using APPDATA: %s", base)
    else:
        # 開発時: database.py と同じフォルダ（従来通り）
        base = _DB_DIR

    return str(base / "career_support.db")


def get_core_db_path() -> str:
    """local-ai-core の共通スキーマ(core.db)のパス。

    以前はここで「career_support.dbと同じディレクトリ」を独自に組み立てていたが、
    それだとArchlifeなど他アプリが別のディレクトリを見てしまい、
    core.dbがアプリごとに分裂する(=共通データ基盤にならない)問題があった。
    そのため、パス解決は local_ai_core.paths に一本化し、ここでは委譲するだけにする。
    旧環境変数 CORE_DB_PATH は local_ai_core.paths 側で後方互換として読まれる。
    """
    from local_ai_core.paths import get_core_db_path as _shared_get_core_db_path

    return _shared_get_core_db_path()


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- ============================================================
-- knowledge_bases: 知識ベース（企業 or 履歴書）単位のまとまり
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,              -- 表示名（例: "ソニー", "共通履歴書"）
    kb_type      TEXT NOT NULL CHECK (kb_type IN ('resume', 'company')),
    is_active    INTEGER NOT NULL DEFAULT 1, -- RAG検索対象に含めるか（0/1）
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ============================================================
-- documents: knowledge_baseに属する個別ファイル（複数バージョン可）
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_base_id  INTEGER NOT NULL,
    source_name        TEXT NOT NULL,        -- 元ファイル名
    file_path          TEXT,                 -- uploads/ 内の保存先パス（相対パス）
    version             INTEGER NOT NULL DEFAULT 1,
    is_active          INTEGER NOT NULL DEFAULT 1,  -- このKB内で現在使う版か
    embedding_path     TEXT,                 -- rag/ 内の .npy パス（document単位で1ファイル）
    created_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents(knowledge_base_id);

-- ============================================================
-- document_chunks: documentに属するチャンク（embeddingは親document
-- の .npy を chunk_index で参照する。テキストのみここに持つ）
-- ============================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   INTEGER NOT NULL,
    chunk_index   INTEGER NOT NULL,          -- 親.npy内の行インデックスと対応
    chunk_text    TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);

-- ============================================================
-- sessions: 面接セッション（会社ごと・種別ごとに複数記録）
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name            TEXT,
    session_type            TEXT,            -- 例: "模擬面接", "一次面接対策", "最終面接対策"
    status                  TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress / completed
    knowledge_base_id       INTEGER,         -- このセッションが参照するKB（company側）
    profile_text            TEXT,
    interview_complete      INTEGER NOT NULL DEFAULT 0,
    interview_summary       TEXT,
    final_pr                TEXT,
    pr_variants             TEXT,            -- JSON文字列として保持
    selected_variant_index  INTEGER,
    predicted_questions     TEXT,            -- JSON文字列として保持
    company_prs             TEXT,            -- JSON文字列として保持
    progress_state          TEXT,            -- JSON文字列: interview_started,
                                              -- current_theme_index, questions_asked_in_theme,
                                              -- theme_messages, selected_category 等の
                                              -- インタビュー進行中の一時状態をまとめて保持
    mock_interview_evaluation TEXT,          -- JSON文字列: AI模擬面接「完了後」の評価結果
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at);

-- ============================================================
-- messages: チャット履歴（sessionに1:N）
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    role          TEXT NOT NULL,             -- "user" / "assistant" など既存messages構造に合わせる
    content       TEXT NOT NULL,
    theme_index   INTEGER,                   -- current_theme_index相当（任意）
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

-- ============================================================
-- personality_results: Big Five診断結果
-- ============================================================
CREATE TABLE IF NOT EXISTS personality_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER,                 -- nullable: セッション非依存で受けることも許容
    pa_answers      TEXT,                    -- JSON文字列
    pa_axis_scores  TEXT,                    -- JSON文字列
    pa_result       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- ============================================================
-- settings: アプリ設定（key-value）
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- ============================================================
-- favorites: お気に入り保存（自己PR・模擬面接結果・質問セット等）
-- ============================================================
CREATE TABLE IF NOT EXISTS favorites (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type        TEXT NOT NULL,   -- personality / company_matrix / question_set / interview / career_advice / advice_message
    item_id          INTEGER,
    session_id       INTEGER,
    company_name     TEXT,
    session_type     TEXT,
    label            TEXT,
    content_snapshot TEXT,            -- 保存時点の要約テキスト（JSON文字列）
    saved_at         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """SQLite接続を返す。

    Args:
        db_path: 接続先パス。省略時は環境変数 INTERVIEW_DB_PATH またはデフォルトパスを使用。
                 ":memory:" を渡すとインメモリDBになる（テスト用途）。

    - row_factory を sqlite3.Row にして、列名でアクセスできるようにする
    - 外部キー制約を有効化する
    """
    path = db_path if db_path is not None else _resolve_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    logger.debug("Opening DB connection: %s", path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """with文で使える接続コンテキスト。正常終了時はcommit、例外時はrollbackする。

    Args:
        db_path: 接続先パス。省略時は環境変数 INTERVIEW_DB_PATH またはデフォルトパスを使用。
                 テスト時は ":memory:" を渡すことでインメモリDBを使用できる。

    使用例:
        with db_session() as conn:
            conn.execute("INSERT INTO sessions (...) VALUES (...)")

        # テスト時:
        with db_session(":memory:") as conn:
            ...
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        logger.error("DBトランザクション失敗。ロールバックします", exc_info=True)
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# マイグレーション管理
# ============================================================
# 新しいマイグレーションを追加するときは _MIGRATIONS リストの末尾に
#   (バージョン番号, "ALTER TABLE ... / CREATE INDEX ...") を追記するだけ。
# 番号は連番で、既存のものを変更・削除してはいけない（冪等性のため）。
# 実行済みのバージョンは schema_migrations テーブルで管理される。
# ============================================================

_MIGRATIONS: list[tuple[int, str]] = [
    (1, "ALTER TABLE sessions ADD COLUMN mock_interview_evaluation TEXT"),
    (2, "ALTER TABLE sessions ADD COLUMN scheduled_at TEXT"),  # 面接予定日時(ISO8601)。core_sync経由でschedule_itemsに反映
    # 今後のカラム追加はここに追記:
    # (3, "ALTER TABLE sessions ADD COLUMN new_column TEXT"),
]

_CREATE_MIGRATION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def _run_migrations(conn: sqlite3.Connection) -> None:
    """未適用のマイグレーションを順番に実行する。何度呼んでも安全（冪等）。"""
    conn.execute(_CREATE_MIGRATION_TABLE)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    for version, sql in _MIGRATIONS:
        if version in applied:
            continue
        try:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            logger.info("マイグレーション v%d を適用しました", version)
        except sqlite3.OperationalError as e:
            # 例: 既にカラムが存在する場合など — ログに残してスキップ
            logger.warning("マイグレーション v%d をスキップ（%s）", version, e)
            conn.execute("INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)", (version,))


def init_db(db_path: str | None = None) -> None:
    """スキーマを初期化する（既存テーブルがあれば何もしない）。アプリ起動時に呼ぶ。

    Args:
        db_path: 接続先パス。省略時は環境変数 INTERVIEW_DB_PATH またはデフォルトパスを使用。
    """
    path = db_path if db_path is not None else _resolve_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    logger.info("init_db: %s", path)
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA_SQL)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()
