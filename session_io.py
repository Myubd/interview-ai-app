"""
session_io.py
-------------
インタビューセッションの保存・復元を行うモジュール。

[v2: SQLite対応]
- SQLite（db/career_support.db の sessions / messages / personality_results テーブル）
  を正式な保存先とする。
- 旧来のJSON export/import機能（serialize_session, deserialize_session,
  build_session_snapshot, restore_session, make_filename）はそのまま残し、
  「バックアップ・他環境への移行」用途として提供する
  （st.download_button でのエクスポート、アップロードでのインポートに利用）。
- 個人情報を含むデータのため、外部サービスへの送信は一切行わない方針は維持する。
- 1人のユーザーが複数の面接セッション（会社ごと・面接種別ごと）を記録し、
  一覧から過去のセッションを振り返れることを主目的とする（ユーザー管理はしない）。

DB保存されるデータ（sessionsテーブルの主な列）:
    company_name           : 会社名
    session_type           : 面接種別（模擬面接 / 一次面接対策 / 最終面接対策 等）
    profile_text            : 事前入力プロフィール
    interview_complete      : インタビュー完了フラグ
    final_pr                : 選択・微調整後の最終自己PR
    pr_variants              : 3パターン自己PR案（JSON文字列）
    selected_variant_index  : 選択中の案インデックス
    interview_summary       : 面接サマリー
    predicted_questions     : 想定質問リスト（JSON文字列）
    company_prs              : 企業別カスタマイズPR（JSON文字列）
    progress_state           : インタビュー進行中の一時状態（JSON文字列）
        - interview_started, current_theme_index, questions_asked_in_theme,
          theme_messages, selected_category をまとめて保持

別テーブルに保存されるデータ:
    messages              : messagesテーブル（session_idに対する1:N、発言ごとに1行）
    pa_answers/pa_axis_scores/pa_result : personality_resultsテーブル（session_idに対する1:1想定）

[v3: リポジトリ層への分離]
- sessions / messages / personality_results / knowledge_bases への実際のDB
  読み書き（SQL）は db/session_repository.py, db/personality_repository.py,
  db/knowledge_base_repository.py に移動した。
- このファイルは、StreamlitのSessionStateとDB行（dict）の間の変換、および
  旧来のJSON export/import（バックアップ・他環境への移行用途）に専念する。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from db import knowledge_base_repository as kb_repo
from db import session_repository as session_repo
from db import personality_repository as personality_repo
from db.session_repository import _to_json_str, _from_json_str  # noqa: F401（重複定義を排除し一元化）

SESSION_FORMAT_VERSION = "1.0"
_UNSET = object()
RESUME_KB_NAME = "共通履歴書"


# 互換性のため、既存呼び出し元向けに同名関数を再エクスポートする。
# 実体は db/knowledge_base_repository.py に移動済み。
_get_or_create_knowledge_base = kb_repo.get_or_create_knowledge_base

# ============================================================
# sessions テーブルの列に直接対応するキー（そのままUPDATE/SELECTする）
# ============================================================
_SESSION_DIRECT_KEYS: list[str] = [
    "profile_text",
    "interview_complete",
    "final_pr",
    "selected_variant_index",
    "interview_summary",
]

# sessions テーブルの列だが、JSON文字列として保存する必要があるキー
_SESSION_JSON_KEYS: list[str] = [
    "pr_variants",
    "predicted_questions",
    "company_prs",
]

# progress_state(JSON)列にまとめて保存する、インタビュー進行中の一時状態キー
_PROGRESS_STATE_KEYS: list[str] = [
    "interview_started",
    "current_theme_index",
    "questions_asked_in_theme",
    "theme_messages",
    "selected_category",
]

# personality_results テーブルに保存するキー
_PERSONALITY_KEYS: list[str] = [
    "pa_answers",
    "pa_axis_scores",
    "pa_result",
]

# 後方互換: JSON export/import（build_session_snapshot等）で使う全キーの統合リスト
_SAVE_KEYS: list[str] = (
    ["messages", "mock_evaluation"]
    + _SESSION_DIRECT_KEYS
    + _PROGRESS_STATE_KEYS
    + _SESSION_JSON_KEYS
    + _PERSONALITY_KEYS
)

# 復元時に上書きしないキー（UIフラグ系は初期値のままにする）
_SKIP_RESTORE_KEYS: set[str] = {
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
    """StreamlitのセッションステートからJSONシリアライズ可能なスナップショットを作る。

    Args:
        session_state: st.session_state

    Returns:
        JSONシリアライズ可能なdict
    """
    snapshot: dict = {
        "_version": SESSION_FORMAT_VERSION,
        "_saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    for key in _SAVE_KEYS:
        value = getattr(session_state, key, None)
        if value is None:
            continue
        # numpy配列等のシリアライズ非対応型はスキップ（pa_axis_scoresはdictなので問題なし）
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

    version = data.get("_version", "不明")
    if version != SESSION_FORMAT_VERSION:
        # バージョン違いは警告のみで続行（後方互換を試みる）
        pass  # 将来的にはマイグレーション処理をここに追加

    return data, None


def restore_session(session_state: Any, snapshot: dict) -> list[str]:
    """スナップショットの内容をセッションステートに書き戻す。

    Args:
        session_state: st.session_state
        snapshot: deserialize_session() で取得した dict

    Returns:
        復元できなかったキーのリスト（空なら完全復元）
    """
    skipped: list[str] = []
    for key in _SAVE_KEYS:
        if key in _SKIP_RESTORE_KEYS:
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
    for flag_key in _SKIP_RESTORE_KEYS:
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


# ============================================================
# SQLite永続化: 保存
# ============================================================
# _to_json_str / _from_json_str は db/session_repository.py で定義し、
# ファイル冒頭の import でここへ取り込んでいる（重複定義を排除）。

def save_session_to_db(
    session_state: Any,
    session_id: int | None = None,
    company_name: str | None | object = _UNSET,
    session_type: str | None | object = _UNSET,
    knowledge_base_id: int | None | object = _UNSET,
) -> int:
    """セッションステートの内容をSQLiteに保存する（新規作成 or 既存セッションの更新）。

    Args:
        session_state: st.session_state
        session_id: 更新対象のsessions.id。Noneなら新規セッションとして作成する。
        company_name: 会社名。省略時は既存値を変更しない。Noneを渡すと空にする。
        session_type: 面接種別。省略時は既存値を変更しない。Noneを渡すと空にする。
        knowledge_base_id: 企業knowledge_baseのid。省略時は既存値を変更しない。Noneを渡すと空にする。

    Returns:
        保存されたセッションの sessions.id（新規作成時は新しいid、更新時は引数のid）
    """
    direct_values = {
        key: getattr(session_state, key, None) for key in session_repo.SESSION_DIRECT_KEYS
    }

    json_values = {
        key: getattr(session_state, key, None) for key in session_repo.SESSION_JSON_KEYS
    }

    # AI模擬面接「完了後」の評価結果（途中経過の会話履歴は保存しない）。
    # session_state側の属性名(mock_evaluation)とDB列名(mock_interview_evaluation)が
    # 異なるため、SESSION_JSON_KEYSの汎用ループには含めず個別に扱う。
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

    # personality_results: このセッションに紐づく性格診断データがあれば保存
    pa_answers = getattr(session_state, "pa_answers", None)
    pa_axis_scores = getattr(session_state, "pa_axis_scores", None)
    pa_result = getattr(session_state, "pa_result", None)
    personality_repo.save_personality_result(session_id, pa_answers, pa_axis_scores, pa_result)

    return session_id


# ============================================================
# SQLite永続化: 一覧
# ============================================================

def list_sessions() -> list[dict]:
    """全セッションの一覧をメタ情報のみで返す（新しい順）。

    一覧画面表示用。messages本文等の重いデータは含まない。

    Returns:
        [{"id", "company_name", "session_type", "status", "interview_complete",
          "created_at", "updated_at", "has_mock_evaluation"}, ...]
    """
    return session_repo.list_sessions()


# ============================================================
# SQLite永続化: 読み込み（DB -> session_state）
# ============================================================

def load_session_from_db(session_state: Any, session_id: int) -> bool:
    """指定したsession_idの内容をDBから読み込み、session_stateに復元する。

    Args:
        session_state: st.session_state
        session_id: sessions.id

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

    # RAG資料を、共通履歴書KB + セッションに紐づく企業KBから復元する。
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

    # AI模擬面接「完了後」の評価結果（途中経過は保存対象外のため復元もしない）
    session_state.mock_evaluation = _from_json_str(row.get("mock_interview_evaluation"), None)

    # progress_state
    progress_state = _from_json_str(row.get("progress_state"), {})
    for key in session_repo.PROGRESS_STATE_KEYS:
        if key in progress_state:
            setattr(session_state, key, progress_state[key])

    # messages
    session_state.messages = messages

    # personality_results
    pa_row = personality_repo.get_personality_result(session_id)
    if pa_row is not None:
        session_state.pa_answers = pa_row.get("pa_answers", {})
        session_state.pa_axis_scores = pa_row.get("pa_axis_scores", {})
        session_state.pa_result = pa_row.get("pa_result")

    # UIフラグは安全な初期値にリセット
    for flag_key in _SKIP_RESTORE_KEYS:
        setattr(session_state, flag_key, False)

    # profile_done は messages があれば True にする（旧restore_session と同じ挙動）
    if messages:
        session_state.profile_done = True
        session_state.interview_started = True

    return True


def delete_session(session_id: int) -> None:
    """セッションを削除する（messages, personality_resultsもCASCADEで連動削除される）。"""
    session_repo.delete_session(session_id)


# ============================================================
# SQLite <-> JSON 相互変換（バックアップ・移行用）
# ============================================================

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
    """JSONバイト列（serialize_session または export_session_as_json の出力）を
    パースし、新規セッションとしてDBに保存する（バックアップからの復元・移行用）。

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
    for key in _SAVE_KEYS:
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
