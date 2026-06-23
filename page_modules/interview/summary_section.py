"""
interview/summary_section.py
面接サマリー（強み・弱み・向いている職種・業界別フィット度）セクション
"""

import streamlit as st

from summary_generation import generate_interview_summary
from utils import INDUSTRY_KEYS
from page_modules.interview.helpers import build_conversation_history


def render_summary_section(model_name: str):
    st.subheader("📊 面接サマリー（強み・弱み・向いている職種）")
    st.caption("インタビュー内容から、あなたの特性と業界別フィット度を分析します。")

    if st.session_state.interview_summary is None:
        summary_label = "🔍 面接サマリーを生成する"
        if not st.session_state.is_generating_summary:
            if st.button(summary_label):
                st.session_state.is_generating_summary = True
                st.session_state.summary_error = None
                st.rerun()
            if st.session_state.summary_error:
                st.error(st.session_state.summary_error)
        else:
            st.button(summary_label, disabled=True)
            with st.spinner("インタビュー内容を分析中..."):
                try:
                    history = build_conversation_history()
                    result = generate_interview_summary(model_name, history)
                    if result and result.get("ok"):
                        st.session_state.interview_summary = result
                        st.session_state.summary_error = None
                    else:
                        err = result.get("error_msg", "不明なエラー") if result else "生成に失敗しました"
                        st.session_state.summary_error = f"サマリーの生成に失敗しました。詳細: {err}"
                except Exception as e:
                    st.session_state.summary_error = "サマリーの生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
            st.session_state.is_generating_summary = False
            st.rerun()
    else:
        _render_summary_result()


def _render_summary_result():
    summary = st.session_state.interview_summary

    if summary.get("strengths"):
        st.markdown("#### 💪 強み")
        for item in summary["strengths"]:
            with st.container(border=True):
                st.markdown(f"**{item.get('point', '')}**")
                if item.get("evidence"):
                    st.caption(f"根拠: {item['evidence']}")

    if summary.get("weaknesses"):
        st.markdown("#### 🌱 成長余地")
        for item in summary["weaknesses"]:
            with st.container(border=True):
                st.markdown(f"**{item.get('point', '')}**")
                if item.get("evidence"):
                    st.caption(f"ヒント: {item['evidence']}")

    if summary.get("fit_roles"):
        st.markdown("#### 🎯 向いている職種・環境")
        st.info(summary["fit_roles"])

    industry_fit = summary.get("industry_fit", {})
    if industry_fit:
        st.markdown("#### 🏢 業界別フィット度")
        for row_start in range(0, len(INDUSTRY_KEYS), 2):
            row_keys = INDUSTRY_KEYS[row_start: row_start + 2]
            cols = st.columns(2)
            for col, key in zip(cols, row_keys):
                data = industry_fit.get(key, {})
                score = data.get("score", 0) if isinstance(data, dict) else 0
                reason = data.get("reason", "") if isinstance(data, dict) else ""
                stars = "⭐" * score + "☆" * (5 - score)
                with col:
                    st.markdown(f"**{key}**")
                    st.markdown(f"{stars}　{score}/5")
                    if reason:
                        st.caption(reason)

    if summary.get("overall_comment"):
        st.markdown("#### 💬 総評")
        st.success(summary["overall_comment"])

    if st.button("🔄 サマリーを再生成する"):
        st.session_state.interview_summary = None
        st.rerun()
