"""
interview/pr_generation_section.py
自己PR生成セクション（ステップ1: 生成・ステップ2: 3案選択）
"""

import streamlit as st

from pr_generation import generate_pr_variants
from page_modules.interview.helpers import build_conversation_history, build_rag_block


def render_pr_generation_section(model_name: str):
    """
    自己PR生成フロー（ステップ1・2）を描画する。
    ステップ3（評価・微調整）以降は pr_evaluation_section が担当。
    """
    # ── ステップ1: 生成ボタン ──────────────────────────────────────
    if st.session_state.pr_variants is None:
        generate_label = "✨ この内容で自己PRを自動生成する（3パターン）"
        if not st.session_state.is_generating:
            if st.button(generate_label, type="primary"):
                st.session_state.is_generating = True
                st.session_state.pr_generation_error = None
                st.rerun()
            if st.session_state.pr_generation_error:
                st.error(st.session_state.pr_generation_error)
        else:
            st.button(generate_label, type="primary", disabled=True)
            with st.spinner("これまでの回答から、3パターンの自己PRを生成中...（複数案生成のため通常より時間がかかります）"):
                try:
                    history = build_conversation_history()
                    rag_block = build_rag_block(history)
                    st.session_state.pr_variants = generate_pr_variants(model_name, history, rag_block)
                    st.session_state.pr_generation_error = None
                except Exception as e:
                    st.session_state.pr_variants = None
                    st.session_state.pr_generation_error = (
                        "自己PRの生成に失敗しました。Ollamaが起動しているか、"
                        f"モデル「{model_name}」が `ollama pull {model_name}` 済みかご確認ください。\n\n詳細: {e}"
                    )
            st.session_state.is_generating = False
            st.rerun()

    # ── ステップ2: 3案選択 ────────────────────────────────────────
    elif st.session_state.selected_variant_index is None:
        st.subheader("📝 3つの案から選んでください")
        st.caption("切り口の異なる3パターンを生成しました。気に入ったものを選ぶと、評価・微調整ができます。")
        for i, variant in enumerate(st.session_state.pr_variants):
            with st.container(border=True):
                st.markdown(f"**{variant['label']}**")
                st.write(variant["content"])
                if st.button("この案を選ぶ", key=f"select_variant_{i}"):
                    st.session_state.selected_variant_index = i
                    st.session_state.final_pr = variant["content"]
                    st.session_state.pr_evaluation = None
                    st.rerun()
        st.write("---")
        if st.button("🔁 3パターンを再生成する"):
            st.session_state.pr_variants = None
            st.rerun()
