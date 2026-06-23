"""
interview/page.py
自己PR引き出しインタビュー（メインフロー）ページ
"""

import streamlit as st

from page_modules.interview.helpers import build_conversation_history  # app.py から再エクスポート用
from page_modules.interview.interview_ui import render_profile_form, render_interview_ui
from page_modules.interview.summary_section import render_summary_section
from page_modules.interview.pr_generation_section import render_pr_generation_section
from page_modules.interview.pr_evaluation_section import render_pr_evaluation_section
from page_modules.interview.predicted_questions_section import render_predicted_questions_section
from page_modules.interview.company_pr_section import render_company_pr_section


def render(model_name: str):
    st.title("🗣️ 一問一答：自己PR引き出しインタビュー")
    st.write("AIがあなたの回答を踏まえながら質問を考え、強みを掘り下げて、最後に自己PRを作成します。")

    # ── 事前入力フォーム ────────────────────────────────────────
    if not st.session_state.profile_done:
        render_profile_form()
        st.stop()

    # ── インタビュー本体（開始〜質問応答ループ） ──────────────────
    render_interview_ui(model_name)

    # ── インタビュー完了後 ───────────────────────────────────────
    if st.session_state.interview_complete:
        _render_post_interview(model_name)


def _render_post_interview(model_name: str):
    st.write("---")

    render_summary_section(model_name)
    st.write("---")

    # PR生成フロー：ステップ1〜2（バリアント選択まで）
    if st.session_state.selected_variant_index is None:
        render_pr_generation_section(model_name)
        return

    # ステップ3以降（評価・微調整・想定質問・企業別PR）
    render_pr_evaluation_section(model_name)
    st.write("---")
    render_predicted_questions_section(model_name)
    render_company_pr_section(model_name)
