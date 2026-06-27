# -*- coding: utf-8 -*-
"""
db/personality_repository.py
------------------------------
personality_results テーブル（Big Five診断結果）に対するCRUD処理を担うリポジトリ。

[元 session_io.py からの分離について]
save_session_to_db / load_session_from_db / export_session_as_json にあった
personality_results への保存・読み込み処理をここに切り出した。
session_id は1:1想定（呼び出し元が同一session_idで複数回保存する場合は
既存行をUPDATEする）。
"""

from __future__ import annotations

import json
from typing import Any

from db.database import db_session


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


def save_personality_result(
    session_id: int | None,
    pa_answers: Any = None,
    pa_axis_scores: Any = None,
    pa_result: str | None = None,
) -> int | None:
    """性格診断結果を保存する（既存行があればUPDATE、なければINSERT）。

    Args:
        session_id: 紐づくsessions.id（nullable: セッション非依存で受けることも許容）
        pa_answers: 回答データ（JSONシリアライズして保存）
        pa_axis_scores: 軸別スコア（JSONシリアライズして保存）
        pa_result: 診断結果テキスト

    Returns:
        保存した行のpersonality_results.id。何も保存すべき値がない場合はNone。
    """
    if not (pa_answers or pa_axis_scores or pa_result):
        return None

    with db_session() as conn:
        existing = None
        if session_id is not None:
            existing = conn.execute(
                "SELECT id FROM personality_results WHERE session_id = ?",
                (session_id,),
            ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE personality_results
                SET pa_answers = ?, pa_axis_scores = ?, pa_result = ?
                WHERE session_id = ?
                """,
                (_to_json_str(pa_answers), _to_json_str(pa_axis_scores), _to_json_str(pa_result), session_id),
            )
            return existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO personality_results (session_id, pa_answers, pa_axis_scores, pa_result)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, _to_json_str(pa_answers), _to_json_str(pa_axis_scores), _to_json_str(pa_result)),
            )
            return cur.lastrowid


def get_personality_result(session_id: int) -> dict | None:
    """指定session_idに紐づく最新の性格診断結果を返す（JSON列はデコード済み）。

    Returns:
        {"id", "session_id", "pa_answers", "pa_axis_scores", "pa_result", "created_at"}
        見つからない場合はNone。
    """
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM personality_results WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        row = dict(row)

    row["pa_answers"] = _from_json_str(row.get("pa_answers"), {})
    row["pa_axis_scores"] = _from_json_str(row.get("pa_axis_scores"), {})
    return row


def delete_personality_result(session_id: int) -> None:
    """指定session_idに紐づく性格診断結果を削除する。"""
    with db_session() as conn:
        conn.execute("DELETE FROM personality_results WHERE session_id = ?", (session_id,))


__all__ = [
    "save_personality_result",
    "get_personality_result",
    "delete_personality_result",
]
