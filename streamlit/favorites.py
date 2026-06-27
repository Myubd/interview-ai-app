"""
favorites.py
-------------
「お気に入り」機能のCRUDモジュール。

設計方針:
- 全セッション共通の favorites テーブルで管理する。
- お気に入りの単位:
    - 性格診断     → item_type="personality"   item_id=session_id
    - 企業比較     → item_type="company_matrix" item_id=session_id（比較全体）
    - 想定質問     → item_type="question_set"   item_id=session_id
    - 面接履歴     → item_type="interview"      item_id=session_id
    - AI相談(会話) → item_type="career_advice"  item_id=session_id
    - AI相談(個別) → item_type="advice_message" item_id=任意の整数ハッシュ or rowid
                     ただし content_snapshot で本文を保持する
- 会社別・面接種別での絞り込みを可能にするために
  company_name / session_type 列を持つ。
- 保存した日付を表示するために saved_at 列を持つ。
- content_snapshot: お気に入りに保存した時点の「要約テキスト」を保持する。
  一覧表示でDBを何度も引かずにカードを描画できるようにする。

テーブル定義（db/database.py の init_db で作成することを想定）:
    CREATE TABLE IF NOT EXISTS favorites (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type      TEXT NOT NULL,
        item_id        INTEGER,
        session_id     INTEGER,          -- 親セッションへの参照（任意）
        company_name   TEXT,
        session_type   TEXT,
        label          TEXT,             -- ユーザーが付けたメモ（任意）
        content_snapshot TEXT,           -- 保存時点の要約テキスト（JSON文字列）
        saved_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
    );
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from db.database import db_session
from db.session_repository import _to_json_str as _to_snapshot, _from_json_str as _from_snapshot

# お気に入りのアイテムタイプ定義（UIラベルも兼ねる）
ITEM_TYPE_LABELS: dict[str, str] = {
    "personality":    "🧠 性格診断",
    "company_matrix": "🏢 企業比較",
    "question_set":   "🎯 想定質問",
    "interview":      "🎤 面接履歴",
    "career_advice":  "🤖 AI相談（会話）",
    "advice_message": "💬 AI相談（個別）",
}

# 絞り込みに使うフィルタ選択肢（"" = 全件）
FILTER_ALL = ""


# ============================================================
# 公開API: 追加 / 削除 / 一覧
# ============================================================

def add_favorite(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
    company_name: str | None = None,
    session_type: str | None = None,
    label: str | None = None,
    content_snapshot: Any = None,
) -> int:
    """お気に入りを追加し、新規レコードの id を返す。

    同一 (item_type, item_id, session_id) の組み合わせが既に存在する場合は
    追加せずに既存の id を返す（重複防止）。
    """
    with db_session() as conn:
        # 重複チェック
        existing = conn.execute(
            """
            SELECT id FROM favorites
            WHERE item_type = ? AND item_id IS ? AND session_id IS ?
            """,
            (item_type, item_id, session_id),
        ).fetchone()
        if existing:
            return existing["id"]

        cur = conn.execute(
            """
            INSERT INTO favorites
                (item_type, item_id, session_id, company_name, session_type,
                 label, content_snapshot, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_type,
                item_id,
                session_id,
                company_name,
                session_type,
                label,
                _to_snapshot(content_snapshot),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return cur.lastrowid


def remove_favorite(favorite_id: int) -> None:
    """指定 id のお気に入りを削除する。"""
    with db_session() as conn:
        conn.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))


def remove_favorite_by_item(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
) -> None:
    """(item_type, item_id, session_id) で指定してお気に入りを削除する。"""
    with db_session() as conn:
        conn.execute(
            """
            DELETE FROM favorites
            WHERE item_type = ? AND item_id IS ? AND session_id IS ?
            """,
            (item_type, item_id, session_id),
        )


def is_favorited(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
) -> bool:
    """指定したアイテムがお気に入り済みかどうかを返す。"""
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM favorites
            WHERE item_type = ? AND item_id IS ? AND session_id IS ?
            LIMIT 1
            """,
            (item_type, item_id, session_id),
        ).fetchone()
    return row is not None


def get_favorite_id(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
) -> int | None:
    """お気に入り済みなら favorites.id を返す。未登録なら None。"""
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT id FROM favorites
            WHERE item_type = ? AND item_id IS ? AND session_id IS ?
            LIMIT 1
            """,
            (item_type, item_id, session_id),
        ).fetchone()
    return row["id"] if row else None


def list_favorites(
    item_type: str | None = None,
    company_name: str | None = None,
    session_type: str | None = None,
) -> list[dict]:
    """お気に入り一覧を返す（新しい順）。

    Args:
        item_type:    絞り込むアイテムタイプ（None = 全種類）
        company_name: 絞り込む会社名（None = 全社）
        session_type: 絞り込む面接種別（None = 全種別）

    Returns:
        [{"id", "item_type", "item_id", "session_id", "company_name",
          "session_type", "label", "content_snapshot"(parsed), "saved_at"}, ...]
    """
    conditions = []
    params: list[Any] = []

    if item_type:
        conditions.append("item_type = ?")
        params.append(item_type)
    if company_name:
        conditions.append("company_name = ?")
        params.append(company_name)
    if session_type:
        conditions.append("session_type = ?")
        params.append(session_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT id, item_type, item_id, session_id,
                   company_name, session_type, label,
                   content_snapshot, saved_at
            FROM favorites
            {where}
            ORDER BY saved_at DESC
            """,
            params,
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["content_snapshot"] = _from_snapshot(d.get("content_snapshot"), None)
        result.append(d)
    return result


def list_distinct_companies() -> list[str]:
    """お気に入りに登録されている会社名の重複なしリストを返す。"""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT company_name FROM favorites WHERE company_name IS NOT NULL ORDER BY company_name"
        ).fetchall()
    return [r["company_name"] for r in rows]


def list_distinct_session_types() -> list[str]:
    """お気に入りに登録されている面接種別の重複なしリストを返す。"""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT DISTINCT session_type FROM favorites WHERE session_type IS NOT NULL ORDER BY session_type"
        ).fetchall()
    return [r["session_type"] for r in rows]


def count_favorites() -> int:
    """お気に入りの総件数を返す。"""
    with db_session() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM favorites").fetchone()
    return row["cnt"] if row else 0


# ============================================================
# 保存ルール定義
# ============================================================
# セッション保存時の自動/手動保存対象を一元管理する。
# app.py から参照して UI を制御する。

# セッション保存時に「自動保存」されるデータ種別
AUTO_SAVE_ITEM_TYPES: list[str] = [
    "career_advice",  # AIキャリア相談履歴
    "company_matrix", # 企業比較結果
]

# セッション保存時に「手動保存（ユーザーが選択）」できるデータ種別
MANUAL_SAVE_ITEM_TYPES: list[str] = [
    "question_set",   # 想定質問セット
]

# 保存しない（一時的な生成）データ種別のメモ（コード上は保存処理を呼ばない）
# "generation_temp"  : 一時的な生成失敗
# "trial_question"   : 試しに作った質問
# "unused_comparison": 不要な比較

def build_auto_save_snapshot(session_state: Any) -> dict[str, Any]:
    """セッション保存時に自動保存するデータのスナップショットを返す。

    Returns:
        {
          "career_advice": {...} | None,
          "company_matrix": {...} | None,
        }
    """
    snapshot: dict[str, Any] = {}

    # AIキャリア相談履歴
    ca_messages = getattr(session_state, "ca_messages", None)
    if ca_messages:
        snippet = ca_messages[-1]["content"][:80] if ca_messages else ""
        snapshot["career_advice"] = {
            "message_count": len(ca_messages),
            "last_snippet": snippet,
        }
    else:
        snapshot["career_advice"] = None

    # 企業比較結果
    cm_matrix = getattr(session_state, "cm_matrix_result", None)
    cm_motivations = getattr(session_state, "cm_motivations", None)
    if cm_matrix or cm_motivations:
        company_names = []
        if cm_motivations:
            company_names = [m.get("company_name", "") for m in cm_motivations if isinstance(m, dict)]
        snapshot["company_matrix"] = {
            "companies": company_names,
            "has_matrix": bool(cm_matrix),
        }
    else:
        snapshot["company_matrix"] = None

    return snapshot
