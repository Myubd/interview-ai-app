"""
page_modules/mock_interview/persona_selector.py
面接官タイプ（ペルソナ）・業界選択UI
"""

import streamlit as st

from persona_engine import list_personas, get_persona
from industry_engine import list_industries, get_industry


def render_persona_selector() -> None:
    """面接開始前のペルソナ・業界選択UIを描画する。"""
    # ── ペルソナ選択 ─────────────────────────────────────────────
    personas = list_personas()
    persona_options = {
        p["key"]: f"{p['icon']} {p['name']}  ー  {p['personality']}"
        for p in personas
    }

    st.subheader("👔 面接官タイプを選んでください")
    selected_persona_key = st.radio(
        "面接官タイプ",
        options=list(persona_options.keys()),
        format_func=lambda k: persona_options[k],
        index=list(persona_options.keys()).index(st.session_state.mock_persona_key),
        key="mock_persona_radio_pre",
        label_visibility="collapsed",
    )
    st.session_state.mock_persona_key = selected_persona_key

    current_persona = get_persona(st.session_state.mock_persona_key)
    with st.expander("💬 この面接官のサンプル発言を見る"):
        st.caption(f"*「{current_persona['sample_phrase']}」*")
        st.caption(f"重視する軸: {' / '.join(current_persona['focus_axes'])}")

    st.write("---")

    # ── 業界選択 ────────────────────────────────────────────────
    industries = list_industries()
    st.subheader("🏢 業界別モードを選んでください")

    industry_keys = [ind["key"] for ind in industries]
    industry_labels = {
        ind["key"]: f"{ind['icon']} {ind['name']}"
        for ind in industries
    }

    current_idx = industry_keys.index(st.session_state.mock_industry_key) \
        if st.session_state.mock_industry_key in industry_keys else 0

    selected_industry_key = st.selectbox(
        "業界",
        options=industry_keys,
        format_func=lambda k: industry_labels[k],
        index=current_idx,
        key="mock_industry_select_pre",
        label_visibility="collapsed",
    )
    st.session_state.mock_industry_key = selected_industry_key

    current_industry = get_industry(selected_industry_key)
    st.caption(f"📋 {current_industry['description']}")

    # テーマ・評価軸プレビュー
    with st.expander("📌 この業界モードのテーマ構成・評価軸を確認する"):
        col_t, col_a = st.columns(2)
        with col_t:
            st.markdown("**テーマ構成**")
            for i, theme in enumerate(current_industry["themes"], start=1):
                st.markdown(f"{i}. {theme['title']}")
        with col_a:
            st.markdown("**評価軸**")
            for axis in current_industry["eval_axes"]:
                st.markdown(f"・{axis}")

    st.write("---")


def render_persona_badge() -> None:
    """面接中に現在のペルソナ・業界をバッジ表示する。"""
    persona = get_persona(st.session_state.mock_persona_key)
    industry = get_industry(st.session_state.mock_industry_key)
    st.caption(
        f"{persona['icon']} 面接官: **{persona['name']}**　"
        f"｜　{industry['icon']} 業界: **{industry['name']}**　"
        f"（評価軸: {' / '.join(industry['eval_axes'])}）"
    )
