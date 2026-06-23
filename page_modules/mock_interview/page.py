"""
page_modules/mock_interview/page.py
AI模擬面接ページのエントリーポイント。
各サブモジュールを組み合わせてページ全体を描画する。
"""

import streamlit as st

import mock_interview_engine as mie

from .persona_selector import render_persona_selector, render_persona_badge
from .interview_flow import start_interview
from .interview_chat import render_chat_history, render_chat_input
from .evaluation_section import render_result


def render(model_name: str) -> None:
    st.title("🎤 AI模擬面接")
    st.write(
        "面接官タイプを選んで模擬面接を行います。"
        "面接中は点数を出さず自然な対話で進み、各回答の直後に「質問意図・改善点」が表示されます。"
        "終了後にまとめて総合評価をお伝えします。"
    )

    if st.button("← インタビューに戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    # ── ペルソナ選択 or バッジ表示 ─────────────────────────────
    if not st.session_state.mock_started:
        render_persona_selector()
    else:
        render_persona_badge()

    # ── 結果表示フェーズ ────────────────────────────────────────
    if st.session_state.mock_complete:
        render_result(model_name)
        st.stop()

    # ── 面接開始（最初の質問生成）──────────────────────────────
    if not st.session_state.mock_started:
        start_interview(model_name)

    # 現在のテーマ表示（業界別テーマ数を反映）
    industry_key = st.session_state.get("mock_industry_key", "general")
    current_theme = mie.get_theme(st.session_state.mock_theme_index, industry_key=industry_key)
    total_themes = mie.get_total_themes(industry_key=industry_key)
    if current_theme:
        st.caption(
            f"📍 現在のテーマ: {current_theme['title']}"
            f"（{st.session_state.mock_theme_index + 1}/{total_themes}）"
        )

    # ── 会話履歴 + 振り返りUI ───────────────────────────────────
    render_chat_history(model_name)

    # ── チャット入力 + 終了ボタン ────────────────────────────────
    render_chat_input(model_name)
