"""
session_io/db_io.py
--------------------
SessionState と SQLite（sessions / messages / personality_results テーブル）の
間の読み書きを担う。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from db import knowledge_base_repository as kb_repo
from db import session_repository as session_repo
from db import personality_repository as personality_repo
from db.session_repository import _from_json_str  # noqa: F401
from session_io.serializer import (
    SESSION_DIRECT_KEYS,
    SESSION_JSON_KEYS,
    PROGRESS_STATE_KEYS,
    SKIP_RESTORE_KEYS,
    SAVE_KEYS,
)

_UNSET = object()
RESUME_KB_NAME = "共通履歴書"


def save_session_to_db(
    session_state: Any,
    session_id: int | None = None,
    company_name: str | None | object = _UNSET,
    session_type: str | None | object = _UNSET,
    knowledge_base_id: int | None | object = _UNSET,
) -> int:
    """セッションステートの内容をSQLiteに保存する（新規作成 or 既存セッションの更新）。

    Returns:
        保存されたセッションの sessions.id
    """
    direct_values = {
        key: getattr(session_state, key, None) for key in session_repo.SESSION_DIRECT_KEYS
    }
    json_values = {
        key: getattr(session_state, key, None) for key in session_repo.SESSION_JSON_KEYS
    }
    mock_evaluation = getattr(session_state, "mock_evaluation", None)
    progress_state = {
        key: getattr(session_state, key, None) for key in session_repo.PROGRESS_STATE_KEYS
    }
    messages = getattr(session_state, "messages", None) or []

    session_id = session_repo.save_session(
        session_id=session_id,
        company_name=company_name,
        session_type=session_type,
        knowledge_base_id=knowledge_base_id,
        direct_values=direct_values,
        json_values=json_values,
        progress_state=progress_state,
        mock_evaluation=mock_evaluation,
        messages=messages,
    )

    pa_answers = getattr(session_state, "pa_answers", None)
    pa_axis_scores = getattr(session_state, "pa_axis_scores", None)
    pa_result = getattr(session_state, "pa_result", None)
    personality_repo.save_personality_result(session_id, pa_answers, pa_axis_scores, pa_result)

    return session_id


def list_sessions() -> list[dict]:
    """全セッションの一覧をメタ情報のみで返す（新しい順）。"""
    return session_repo.list_sessions()


def load_session_from_db(session_state: Any, session_id: int) -> bool:
    """指定したsession_idの内容をDBから読み込み、session_stateに復元する。

    Returns:
        成功したら True、該当セッションが見つからなければ False
    """
    result = session_repo.get_session(session_id)
    if result is None:
        return False
    row = result["session"]
    messages = result["messages"]

    # sessions直接列
    for key in session_repo.SESSION_DIRECT_KEYS:
        value = row.get(key)
        if key == "interview_complete":
            value = bool(value)
        setattr(session_state, key, value)
    session_state.current_company_name = row.get("company_name") or ""

    # RAG資料を復元
    try:
        from rag import load_active_documents

        kb_ids: list[int] = []
        resume_kb_id = kb_repo.get_or_create_knowledge_base(RESUME_KB_NAME, "resume")
        if resume_kb_id:
            kb_ids.append(resume_kb_id)
        if row.get("knowledge_base_id"):
            kb_ids.append(row["knowledge_base_id"])
        session_state.rag_documents = load_active_documents(list(dict.fromkeys(kb_ids)))
        session_state.rag_restore_error = None
    except Exception as e:
        logger.error("RAGドキュメント復元失敗 (session_id=%s)", row.get("id"), exc_info=True)
        session_state.rag_documents = []
        session_state.rag_restore_error = str(e)

    # sessions JSON列
    json_defaults = {
        "pr_variants": [],
        "predicted_questions": [],
        "company_prs": {},
    }
    for key in session_repo.SESSION_JSON_KEYS:
        setattr(session_state, key, _from_json_str(row.get(key), json_defaults.get(key)))

    session_state.mock_evaluation = _from_json_str(row.get("mock_interview_evaluation"), None)

    # progress_state
    progress_state = _from_json_str(row.get("progress_state"), {})
    for key in session_repo.PROGRESS_STATE_KEYS:
        if key in progress_state:
            setattr(session_state, key, progress_state[key])

    session_state.messages = messages

    # personality_results
    pa_row = personality_repo.get_personality_result(session_id)
    if pa_row is not None:
        session_state.pa_answers = pa_row.get("pa_answers", {})
        session_state.pa_axis_scores = pa_row.get("pa_axis_scores", {})
        session_state.pa_result = pa_row.get("pa_result")

    # UIフラグは安全な初期値にリセット
    for flag_key in SKIP_RESTORE_KEYS:
        setattr(session_state, flag_key, False)

    if messages:
        session_state.profile_done = True
        session_state.interview_started = True

    return True


def delete_session(session_id: int) -> None:
    """セッションを削除する（messages, personality_resultsもCASCADEで連動削除される）。"""
    session_repo.delete_session(session_id)
