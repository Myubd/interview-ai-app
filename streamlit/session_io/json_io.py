"""
session_io/json_io.py
----------------------
DBセッションのJSONエクスポートと、JSONファイルからのインポートを担う。

バックアップ・他環境への移行用途。
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from db import knowledge_base_repository as kb_repo
from db import session_repository as session_repo
from db import personality_repository as personality_repo
from db.session_repository import _from_json_str
from session_io.serializer import (
    SESSION_FORMAT_VERSION,
    SAVE_KEYS,
    deserialize_session,
)
from session_io.db_io import save_session_to_db

import json


def export_session_as_json(session_id: int) -> bytes:
    """DB上の指定セッションを、旧来互換のJSON bytes に変換する（バックアップ用）。"""
    result = session_repo.get_session(session_id)
    if result is None:
        raise ValueError(f"session_id={session_id} が見つかりません。")
    row = result["session"]
    messages = result["messages"]

    snapshot: dict = {
        "_version": SESSION_FORMAT_VERSION,
        "_saved_at": datetime.now().isoformat(timespec="seconds"),
        "_source": "sqlite_export",
        "company_name": row.get("company_name"),
        "session_type": row.get("session_type"),
        "knowledge_base_id": row.get("knowledge_base_id"),
        "messages": messages,
    }
    for key in session_repo.SESSION_DIRECT_KEYS:
        snapshot[key] = row.get(key)
    for key in session_repo.SESSION_JSON_KEYS:
        snapshot[key] = _from_json_str(row.get(key), None)

    progress_state = _from_json_str(row.get("progress_state"), {})
    for key in session_repo.PROGRESS_STATE_KEYS:
        if key in progress_state:
            snapshot[key] = progress_state[key]

    snapshot["mock_evaluation"] = _from_json_str(row.get("mock_interview_evaluation"), None)

    pa_row = personality_repo.get_personality_result(session_id)
    if pa_row is not None:
        snapshot["pa_answers"] = pa_row.get("pa_answers") or None
        snapshot["pa_axis_scores"] = pa_row.get("pa_axis_scores") or None
        snapshot["pa_result"] = pa_row.get("pa_result")

    return json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")


def import_json_as_session(file_bytes: bytes) -> tuple[int | None, str | None]:
    """JSONバイト列をパースし、新規セッションとしてDBに保存する（バックアップからの復元・移行用）。

    Returns:
        (session_id, error_msg)。失敗時は (None, error_msg)。
    """
    snapshot, error_msg = deserialize_session(file_bytes)
    if error_msg:
        return None, error_msg

    class _TempState:
        """snapshotのdictをsession_state風のオブジェクトとして扱うための薄いラッパー。"""
        pass

    temp_state = _TempState()
    for key in SAVE_KEYS:
        setattr(temp_state, key, snapshot.get(key))

    knowledge_base_id = snapshot.get("knowledge_base_id")
    if knowledge_base_id is not None:
        existing_kb = kb_repo.get_knowledge_base(knowledge_base_id)
        if existing_kb is None:
            knowledge_base_id = None

    if knowledge_base_id is None and snapshot.get("company_name"):
        knowledge_base_id = kb_repo.get_or_create_knowledge_base(snapshot["company_name"], "company")

    session_id = save_session_to_db(
        temp_state,
        session_id=None,
        company_name=snapshot.get("company_name"),
        session_type=snapshot.get("session_type"),
        knowledge_base_id=knowledge_base_id,
    )
    return session_id, None
