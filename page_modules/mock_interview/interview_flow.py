"""
page_modules/mock_interview/interview_flow.py
面接開始・テーマ進行（次テーマへの遷移）ロジック
"""

import streamlit as st

import mock_interview_engine as mie
from persona_engine import get_first_question_for_theme as persona_get_first_question

from .helpers import build_rag_block, full_history_for_rag


def _industry_key() -> str:
    """現在の業界キーをセッションから取得する。"""
    return st.session_state.get("mock_industry_key", "general")


def start_interview(model_name: str) -> None:
    """最初のテーマの第1問を取得してセッションに書き込む。"""
    intro = "こんにちは、本日面接を担当します。リラックスしてお答えください。\n\n"
    industry = _industry_key()
    first_theme = mie.get_theme(0, industry_key=industry)
    rag_block = build_rag_block("")

    with st.spinner("質問を準備中..."):
        result = persona_get_first_question(
            model=model_name,
            persona_key=st.session_state.mock_persona_key,
            theme=first_theme,
            previous_theme_last_exchange=None,
            profile_text=st.session_state.profile_text,
            rag_block=rag_block,
            predicted_questions=st.session_state.predicted_questions,
            used_question_indices=st.session_state.mock_used_predicted_indices,
            industry_key=industry,
        )

    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、簡易的な質問で開始します。", icon="⚠️")
    if result["used_predicted_index"] is not None:
        st.session_state.mock_used_predicted_indices.add(result["used_predicted_index"])

    first_question = result["question"]
    st.session_state.mock_messages.append({"role": "assistant", "content": intro + first_question})
    st.session_state.mock_theme_messages.append({"role": "assistant", "content": first_question})
    st.session_state.mock_started = True


def advance_to_next_theme(model_name: str) -> None:
    """現在のテーマを終了し、次テーマの第1問を取得してセッションに書き込む。"""
    industry = _industry_key()
    prev_messages = st.session_state.mock_theme_messages[-2:] if st.session_state.mock_theme_messages else []
    prev_last_exchange = (
        "\n".join(
            f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}"
            for m in prev_messages
        )
        if prev_messages
        else None
    )

    next_index = st.session_state.mock_theme_index + 1
    st.session_state.mock_theme_index = next_index
    st.session_state.mock_theme_messages = []
    st.session_state.mock_followups_asked = 0

    if mie.is_interview_finished(next_index, industry_key=industry):
        finish_msg = (
            "本日の模擬面接は以上です。お疲れ様でした！\n\n"
            "下の「結果を見る」ボタンから、今回の振り返りを確認できます。"
        )
        st.session_state.mock_messages.append({"role": "assistant", "content": finish_msg})
        return

    next_theme = mie.get_theme(next_index, industry_key=industry)
    rag_block = build_rag_block(full_history_for_rag())

    with st.spinner("次の質問を準備中..."):
        result = persona_get_first_question(
            model=model_name,
            persona_key=st.session_state.mock_persona_key,
            theme=next_theme,
            previous_theme_last_exchange=prev_last_exchange,
            profile_text=st.session_state.profile_text,
            rag_block=rag_block,
            predicted_questions=st.session_state.predicted_questions,
            used_question_indices=st.session_state.mock_used_predicted_indices,
            industry_key=industry,
        )

    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、簡易的な質問にしました。", icon="⚠️")
    if result["used_predicted_index"] is not None:
        st.session_state.mock_used_predicted_indices.add(result["used_predicted_index"])

    question = result["question"]
    st.session_state.mock_messages.append({"role": "assistant", "content": question})
    st.session_state.mock_theme_messages.append({"role": "assistant", "content": question})
