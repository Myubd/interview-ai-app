"""
session_io/serializer.py
-------------------------
SessionStateのスナップショット作成・シリアライズ・デシリアライズ・復元を担う。

旧来のJSON export/import機能（バックアップ・他環境への移行用途）のコアロジック。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

SESSION_FORMAT_VERSION = "1.0"

# sessions テーブルの列に直接対応するキー
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

# progress_state(JSON)列にまとめて保存するインタビュー進行中の一時状態キー
PROGRESS_STATE_KEYS: list[str] = [
    "interview_started",
    "current_theme_index",
    "questions_asked_in_theme",
    "theme_messages",
    "selected_category",
]

# personality_results テーブルに保存するキー
PERSONALITY_KEYS: list[str] = [
    "pa_answers",
    "pa_axis_scores",
    "pa_result",
]

# JSON export/import で使う全キーの統合リスト
SAVE_KEYS: list[str] = (
    ["messages", "mock_evaluation"]
    + SESSION_DIRECT_KEYS
    + PROGRESS_STATE_KEYS
    + SESSION_JSON_KEYS
    + PERSONALITY_KEYS
)

# 復元時に上書きしないキー（UIフラグ系は初期値のままにする）
SKIP_RESTORE_KEYS: set[str] = {
    "is_generating",
    "is_evaluating",
    "is_refining",
    "is_generating_summary",
    "pa_is_generating",
    "awaiting_category_choice",
    "pending_prev_exchange",
    "pending_refine_instruction",
}


def build_session_snapshot(session_state: Any) -> dict:
    """StreamlitのセッションステートからJSONシリアライズ可能なスナップショットを作る。"""
    snapshot: dict = {
        "_version": SESSION_FORMAT_VERSION,
        "_saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    for key in SAVE_KEYS:
        value = getattr(session_state, key, None)
        if value is None:
            continue
        try:
            json.dumps(value)  # シリアライズ可能かテスト
            snapshot[key] = value
        except (TypeError, ValueError):
            pass  # シリアライズ不可の値は保存しない
    return snapshot


def serialize_session(session_state: Any) -> bytes:
    """セッションスナップショットをJSON bytes に変換する（ダウンロード用）。"""
    snapshot = build_session_snapshot(session_state)
    return json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")


def deserialize_session(file_bytes: bytes) -> tuple[dict, str | None]:
    """アップロードされたJSONバイト列をパースし、スナップショットdictを返す。

    Returns:
        (snapshot: dict, error_msg: str | None)
        パース失敗時は ({}, error_msg) を返す。
    """
    try:
        text = file_bytes.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return {}, f"ファイルの読み込みに失敗しました: {e}"

    if not isinstance(data, dict):
        return {}, "ファイル形式が不正です（JSON objectが必要です）。"

    # バージョン違いは警告のみで続行（将来的にはマイグレーション処理をここに追加）
    return data, None


def restore_session(session_state: Any, snapshot: dict) -> list[str]:
    """スナップショットの内容をセッションステートに書き戻す。

    Returns:
        復元できなかったキーのリスト（空なら完全復元）
    """
    skipped: list[str] = []
    for key in SAVE_KEYS:
        if key in SKIP_RESTORE_KEYS:
            continue
        if key not in snapshot:
            skipped.append(key)
            continue
        try:
            setattr(session_state, key, snapshot[key])
        except Exception:
            logger.warning("セッション復元: キー '%s' の設定をスキップしました", key, exc_info=True)
            skipped.append(key)

    # 復元後にUIフラグを安全な初期値にリセット
    for flag_key in SKIP_RESTORE_KEYS:
        if not hasattr(session_state, flag_key):
            setattr(session_state, flag_key, False)

    # profile_done は messages があれば True にする
    if snapshot.get("messages"):
        session_state.profile_done = True
        session_state.interview_started = True

    return skipped


def make_filename(prefix: str = "shukatu_session") -> str:
    """ダウンロードファイル名を生成する。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{prefix}_{timestamp}.json"
