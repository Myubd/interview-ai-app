"""
Streamlit session_state の初期化ユーティリティ。

使い方:
    from state_initializer import init_session_state
    init_session_state()

特定のグループだけ初期化したい場合:
    from state_initializer import init_session_state
    init_session_state(groups=["interview", "mock_interview"])

State をリセットしたい場合（キーを削除して再初期化）:
    from state_initializer import reset_session_state
    reset_session_state(keys=["messages", "interview_started"])
"""

from __future__ import annotations

import copy
import streamlit as st

from state.definitions import STATE_DEFAULTS

# ---------------------------------------------------------------------------
# キーをグループに分類（部分的な初期化・リセットに使用）
# ---------------------------------------------------------------------------
GROUPS: dict[str, list[str]] = {
    "app": [
        "app_mode",
    ],
    "interview": [
        "messages", "current_theme_index", "questions_asked_in_theme",
        "theme_messages", "selected_category", "awaiting_category_choice",
        "pending_prev_exchange", "interview_complete", "interview_started",
        "final_pr", "is_generating", "pr_generation_error", "pr_variants",
        "selected_variant_index", "pr_evaluation", "pr_evaluation_error",
        "is_evaluating", "is_refining", "pending_refine_instruction",
        "pr_refine_error", "rag_documents", "rag_restore_error",
        "current_session_id", "current_company_name", "profile_done",
        "profile_text", "interview_summary", "is_generating_summary",
        "summary_error",
    ],
    "predict_questions": [
        "predicted_questions", "is_predicting_questions",
        "predict_questions_error",
    ],
    "company_pr": [
        "company_prs", "company_pr_inputs",
        "is_generating_company_prs", "company_pr_error",
    ],
    "personality": [
        "pa_answers", "pa_current_q", "pa_result",
        "pa_axis_scores", "pa_error", "pa_is_generating",
    ],
    "mock_interview": [
        "mock_messages", "mock_theme_index", "mock_theme_messages",
        "mock_followups_asked", "mock_started", "mock_complete",
        "mock_used_predicted_indices", "mock_evaluation",
        "mock_evaluation_error", "mock_is_generating", "mock_persona_key",
        "mock_answer_reviews", "mock_review_generating_for",
        "mock_persona_confirmed",
        "mock_industry_key",
        "mock_star_reviews", "mock_star_generating_for",
    ],
    "predict_questions_page": [
        "pq_selected_company_kb_id", "pq_questions",
        "pq_is_generating", "pq_error",
    ],
    "career_advisor": [
        "ca_messages", "ca_is_thinking",
    ],
    "company_matrix": [
        "cm_selected_kb_ids", "cm_additional_axes", "cm_motivations",
        "cm_matrix_result", "cm_why_not_others",
        "cm_is_generating", "cm_error",
    ],
}


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------

def _default(key: str) -> object:
    """
    STATE_DEFAULTS から深いコピーで初期値を返す。
    list / dict / set はそのまま共有すると複数セッション間でバグになるため
    deepcopy で安全に返す。
    """
    return copy.deepcopy(STATE_DEFAULTS[key])


def _keys_for_groups(groups: list[str]) -> list[str]:
    """グループ名のリストを受け取り、対応するキーの一覧を返す（重複除去）。"""
    seen: set[str] = set()
    keys: list[str] = []
    for g in groups:
        if g not in GROUPS:
            raise ValueError(f"Unknown group: '{g}'. Available: {list(GROUPS)}")
        for k in GROUPS[g]:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def init_session_state(groups: list[str] | None = None) -> None:
    """
    session_state を初期化する。既存のキーは上書きしない。

    Parameters
    ----------
    groups:
        初期化するグループ名のリスト。None の場合は全キーを対象にする。
    """
    if groups is None:
        target_keys = list(STATE_DEFAULTS.keys())
    else:
        target_keys = _keys_for_groups(groups)

    for key in target_keys:
        if key not in st.session_state:
            st.session_state[key] = _default(key)


def reset_session_state(
    keys: list[str] | None = None,
    groups: list[str] | None = None,
) -> None:
    """
    指定したキー / グループの session_state をデフォルト値にリセットする。

    Parameters
    ----------
    keys:
        リセットしたい個別キーのリスト。
    groups:
        リセットしたいグループ名のリスト。
    keys と groups の両方を指定した場合は和集合を対象にする。
    どちらも None の場合は全キーをリセットする。
    """
    target_keys: list[str]

    if keys is None and groups is None:
        target_keys = list(STATE_DEFAULTS.keys())
    else:
        seen: set[str] = set()
        target_keys = []
        for k in (keys or []):
            if k not in STATE_DEFAULTS:
                raise KeyError(f"Unknown session_state key: '{k}'")
            if k not in seen:
                seen.add(k)
                target_keys.append(k)
        for k in _keys_for_groups(groups or []):
            if k not in seen:
                seen.add(k)
                target_keys.append(k)

    for key in target_keys:
        st.session_state[key] = _default(key)
