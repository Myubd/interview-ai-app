# -*- coding: utf-8 -*-
"""
db/session_repository.py
-------------------------
sessions / messages テーブルに対するCRUD処理を担うリポジトリモジュール。

[元 session_io.py からの分離について]
- session_io.py にあったDB永続化処理（保存・一覧・読み込み・削除）のうち、
  sessions / messages テーブルに関する部分をここに移植した。
- personality_results に関する処理は db/personality_repository.py に分離した。
- knowledge_bases の取得・作成（_get_or_create_knowledge_base）は
  db/knowledge_base_repository.py に分離し、ここではそれを呼び出す。
- StreamlitのSessionStateとの相互変換（build_session_snapshot, restore_session,
  serialize_session, deserialize_session 等のJSON export/import機能）は
  アプリ層の責務として session_io.py 側に残している。
  このモジュールは「DBの行 dict」と「sessions/messagesテーブル」の間の
  入出力のみを担当する。
"""

from __future__ import annotations

import json
from typing import Any

from db.database import db_session
from db.knowledge_base_repository import get_or_create_knowledge_base
from db.personality_repository import (
    get_personality_result,
    save_personality_result,
)

_UNSET = object()

# ============================================================
# sessions テーブルの列に直接対応するキー（そのままUPDATE/SELECTする）
# ============================================================
SESSION_DIRECT_KEYS: list[str] = [
    "profile_text",
    "interview_complete",
    "final_pr",
    "selected_variant_index",
    "interview_summary",
]

# sessions テーブルの列だが、JSON文字列として保存する必要があるキー
SESSION_JSON_KEYS: list[str] = [
    "pr_variants",
    "predicted_questions",
    "company_prs",
]

# progress_state(JSON)列にまとめて保存する、インタビュー進行中の一時状態キー
PROGRESS_STATE_KEYS: list[str] = [
    "interview_started",
    "current_theme_index",
    "questions_asked_in_theme",
    "theme_messages",
    "selected_category",
]


def _to_json_str(value: Any) -> str | None:
    """JSONシリアライズ可能な値をJSON文字列に変換する。Noneや空はNoneを返す。"""
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _from_json_str(text: str | None, default: Any) -> Any:
    """DBから読み出したJSON文字列をパースする。Noneやパース失敗時はdefaultを返す。"""
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def save_session(
    *,
    session_id: int | None = None,
    company_name: str | None | object = _UNSET,
    session_type: str | None | object = _UNSET,
    knowledge_base_id: int | None | object = _UNSET,
    direct_values: dict[str, Any] | None = None,
    json_values: dict[str, Any] | None = None,
    progress_state: dict[str, Any] | None = None,
    mock_evaluation: Any = None,
    messages: list[dict] | None = None,
) -> int:
    """sessionsテーブルへの新規作成 or 更新と、messagesの入れ替えを行う。

    Args:
        session_id: 更新対象のsessions.id。Noneなら新規セッションとして作成する。
        company_name: 会社名。省略時(_UNSET)は既存値を変更しない。Noneを渡すと空にする。
        session_type: 面接種別。省略時(_UNSET)は既存値を変更しない。Noneを渡すと空にする。
        knowledge_base_id: 企業knowledge_baseのid。省略時(_UNSET)は既存値を変更しない。
        direct_values: SESSION_DIRECT_KEYS に対応する値のdict
        json_values: SESSION_JSON_KEYS に対応する値のdict（JSON変換前の生の値）
        progress_state: PROGRESS_STATE_KEYS をまとめたdict（JSON変換前）
        mock_evaluation: AI模擬面接の完了後評価結果（JSON変換前）
        messages: [{"role", "content", "theme_index"}, ...]

    Returns:
        保存されたセッションの sessions.id（新規作成時は新しいid、更新時は引数のid）
    """
    direct_values = dict(direct_values or {})
    direct_values["interview_complete"] = int(bool(direct_values.get("interview_complete")))

    json_str_values = {
        key: _to_json_str((json_values or {}).get(key)) for key in SESSION_JSON_KEYS
    }
    progress_state_json = _to_json_str(progress_state or {})
    mock_evaluation_json = _to_json_str(mock_evaluation)

    with db_session() as conn:
        if session_id is None:
            cur = conn.execute(
                """
                INSERT INTO sessions (
                    company_name, session_type, knowledge_base_id,
                    profile_text, interview_complete, final_pr,
                    selected_variant_index, interview_summary,
                    pr_variants, predicted_questions, company_prs,
                    progress_state, mock_interview_evaluation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None if company_name is _UNSET else company_name,
                    None if session_type is _UNSET else session_type,
                    None if knowledge_base_id is _UNSET else knowledge_base_id,
                    direct_values.get("profile_text"),
                    direct_values.get("interview_complete"),
                    direct_values.get("final_pr"),
                    direct_values.get("selected_variant_index"),
                    direct_values.get("interview_summary"),
                    json_str_values.get("pr_variants"),
                    json_str_values.get("predicted_questions"),
                    json_str_values.get("company_prs"),
                    progress_state_json,
                    mock_evaluation_json,
                ),
            )
            session_id = cur.lastrowid
        else:
            # company_name / session_type / knowledge_base_id は
            # 引数を省略した場合のみ変更しない。Noneが渡された場合はNULLへ更新する。
            set_clauses = [
                "profile_text = ?",
                "interview_complete = ?",
                "final_pr = ?",
                "selected_variant_index = ?",
                "interview_summary = ?",
                "pr_variants = ?",
                "predicted_questions = ?",
                "company_prs = ?",
                "progress_state = ?",
                "mock_interview_evaluation = ?",
                "updated_at = datetime('now', 'localtime')",
            ]
            params: list[Any] = [
                direct_values.get("profile_text"),
                direct_values.get("interview_complete"),
                direct_values.get("final_pr"),
                direct_values.get("selected_variant_index"),
                direct_values.get("interview_summary"),
                json_str_values.get("pr_variants"),
                json_str_values.get("predicted_questions"),
                json_str_values.get("company_prs"),
                progress_state_json,
                mock_evaluation_json,
            ]
            if company_name is not _UNSET:
                set_clauses.append("company_name = ?")
                params.append(company_name)
            if session_type is not _UNSET:
                set_clauses.append("session_type = ?")
                params.append(session_type)
            if knowledge_base_id is not _UNSET:
                set_clauses.append("knowledge_base_id = ?")
                params.append(knowledge_base_id)

            params.append(session_id)
            conn.execute(
                f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )

        # messages は毎回全削除して入れ直す（差分更新より単純で確実、件数も少ないため許容）
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        for msg in messages or []:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", ""))
            content = str(msg.get("content", ""))
            theme_index = msg.get("theme_index")
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, theme_index)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, theme_index),
            )

    return session_id


def list_sessions() -> list[dict]:
    """全セッションの一覧をメタ情報のみで返す（新しい順）。

    一覧画面表示用。messages本文等の重いデータは含まない。

    Returns:
        [{"id", "company_name", "session_type", "status", "interview_complete",
          "created_at", "updated_at", "has_mock_evaluation"}, ...]
    """
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, company_name, session_type, status, interview_complete,
                   created_at, updated_at,
                   (mock_interview_evaluation IS NOT NULL) AS has_mock_evaluation
            FROM sessions
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_session(session_id: int) -> dict | None:
    """指定したsession_idのsessions行とmessagesをまとめて返す。

    Returns:
        見つからない場合はNone。見つかった場合は
        {"session": {...}, "messages": [{"role","content","theme_index"}, ...]}
    """
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        row = dict(row)

        message_rows = conn.execute(
            """
            SELECT role, content, theme_index FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    messages = [
        {"role": m["role"], "content": m["content"], "theme_index": m["theme_index"]}
        for m in message_rows
    ]
    return {"session": row, "messages": messages}


def delete_session(session_id: int) -> None:
    """セッションを削除し、紐づくRAGファイルも安全にクリーンアップする。

    削除順序:
    1. sessions.knowledge_base_id を取得（NULLなら実ファイルなし）
    2. そのKBに属するドキュメントの file_path / embedding_path を収集
    3. DBレコードを削除（CASCADE で messages / personality_results も連動削除）
    4. 収集したファイルパスを unlink（DB削除後に行うことで、
       ファイルだけ消えてレコードが残る状態を防ぐ）
    5. KBが他のセッションから参照されていなければKBレコードも削除
       （「共通履歴書」KBは複数セッションで共有されるため除外する）

    Notes:
        - unlink 失敗はログ警告に留め、セッション削除自体はロールバックしない。
        - 実ファイルが既に存在しない場合は静かにスキップする（missing_ok=True）。
    """
    import logging
    from pathlib import Path
    from db import knowledge_base_repository as kb_repo

    logger = logging.getLogger(__name__)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    RESUME_KB_NAME = "共通履歴書"

    # 1. knowledge_base_id を取得
    with db_session() as conn:
        row = conn.execute(
            "SELECT knowledge_base_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    kb_id: int | None = row["knowledge_base_id"] if row else None

    # 2. 削除対象ファイルパスを収集（KB が存在する場合のみ）
    file_paths_to_delete: list[str] = []
    kb_info: dict | None = None
    if kb_id is not None:
        kb_info = kb_repo.get_knowledge_base(kb_id)
        # 「共通履歴書」KBはセッションをまたいで共有するため削除しない
        if kb_info and kb_info.get("name") != RESUME_KB_NAME:
            for doc in kb_repo.list_document_versions(kb_id):
                for key in ("file_path", "embedding_path"):
                    p = doc.get(key)
                    if p:
                        file_paths_to_delete.append(p)

    # 3. DBレコードを削除
    with db_session() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # 4. 実ファイルを削除
    for rel_path in file_paths_to_delete:
        try:
            (PROJECT_ROOT / rel_path).unlink(missing_ok=True)
        except OSError as e:
            logger.warning("RAGファイル削除失敗（続行します）: %s — %s", rel_path, e)

    # 5. KBレコード削除（他セッションから参照されていなければ）
    if kb_id is not None and kb_info and kb_info.get("name") != RESUME_KB_NAME:
        with db_session() as conn:
            ref_count = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE knowledge_base_id = ?", (kb_id,)
            ).fetchone()[0]
        if ref_count == 0:
            try:
                kb_repo.delete_knowledge_base(kb_id)
            except Exception as e:
                logger.warning("KBレコード削除失敗（続行します）: kb_id=%d — %s", kb_id, e)


__all__ = [
    "SESSION_DIRECT_KEYS",
    "SESSION_JSON_KEYS",
    "PROGRESS_STATE_KEYS",
    "save_session",
    "list_sessions",
    "get_session",
    "delete_session",
    # 元々session_io.pyにあったknowledge_base/personality系の再エクスポート
    # （session_io.py側の互換性のため）
    "get_or_create_knowledge_base",
    "get_personality_result",
    "save_personality_result",
]
