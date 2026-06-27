"""
interview/predicted_questions_section.py
面接想定質問＆模範回答例セクション
"""

from collections import defaultdict

import streamlit as st

from question_prediction import (
    generate_predicted_questions,
    CATEGORY_LABELS as Q_CATEGORY_LABELS,
)
from favorites import add_favorite, remove_favorite_by_item, is_favorited
from page_modules.interview.helpers import build_conversation_history, build_rag_block


def render_predicted_questions_section(model_name: str):
    st.subheader("🎤 面接想定質問＆模範回答例")
    st.caption("この自己PRを読んだ面接官が次に聞きそうな質問と、そのまま話せる模範回答例を生成します。")

    if st.session_state.predicted_questions is None:
        _render_generate_button(model_name)
    else:
        _render_questions_list()

    st.write("---")


# ──────────────────────────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────────────────────────

def _render_generate_button(model_name: str):
    predict_label = "💬 想定質問を生成する（8問）"
    if not st.session_state.is_predicting_questions:
        if st.button(predict_label):
            st.session_state.is_predicting_questions = True
            st.session_state.predict_questions_error = None
            st.rerun()
        if st.session_state.predict_questions_error:
            st.error(st.session_state.predict_questions_error)
    else:
        st.button(predict_label, disabled=True)
        with st.spinner("想定質問と模範回答例を生成中..."):
            try:
                history = build_conversation_history()
                rag_block = build_rag_block(history)
                questions, ok, err = generate_predicted_questions(
                    model_name,
                    st.session_state.final_pr,
                    history,
                    rag_block,
                )
                if ok and questions:
                    st.session_state.predicted_questions = questions
                    st.session_state.predict_questions_error = None
                else:
                    st.session_state.predict_questions_error = f"生成に失敗しました。詳細: {err}"
            except Exception as e:
                st.session_state.predict_questions_error = "想定質問の生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
        st.session_state.is_predicting_questions = False
        st.rerun()


def _render_questions_list():
    grouped = defaultdict(list)
    for q in st.session_state.predicted_questions:
        grouped[q["category"]].append(q)

    category_order = ["deep_dive", "motivation", "weakness", "situational"]
    for cat_key in category_order:
        items = grouped.get(cat_key, [])
        if not items:
            continue
        cat_label = Q_CATEGORY_LABELS.get(cat_key, cat_key)
        st.markdown(f"##### {cat_label}")
        for item in items:
            with st.expander(f"Q: {item['question']}"):
                st.markdown("**模範回答例:**")
                st.info(item["model_answer"])

    st.write("")
    col_regen, col_fav_q = st.columns([1, 1])
    with col_regen:
        if st.button("🔄 想定質問を再生成する"):
            st.session_state.predicted_questions = None
            st.rerun()
    with col_fav_q:
        _render_favorite_button()


def _render_favorite_button():
    session_id = st.session_state.get("current_session_id")
    is_fav = is_favorited("question_set", session_id=session_id) if session_id else False

    if is_fav:
        if st.button("⭐ お気に入り解除", key="iv_pq_fav_remove", use_container_width=True):
            remove_favorite_by_item("question_set", session_id=session_id)
            st.rerun()
    else:
        if st.button(
            "☆ お気に入りに追加", key="iv_pq_fav_add", use_container_width=True,
            help="この想定質問セットをお気に入りに保存",
        ):
            if not session_id:
                st.toast("先にサイドバーからセッションを保存してください。", icon="⚠️")
            else:
                qs = st.session_state.predicted_questions or []
                add_favorite(
                    item_type="question_set",
                    session_id=session_id,
                    company_name=st.session_state.get("current_company_name") or None,
                    session_type=None,
                    label="想定質問セット（自己PRより）",
                    content_snapshot={"question_count": len(qs)},
                )
                st.toast("お気に入りに追加しました ⭐", icon="⭐")
                st.rerun()
