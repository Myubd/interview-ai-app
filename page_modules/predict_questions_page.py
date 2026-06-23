"""
page_modules/predict_questions_page.py
想定質問生成ページ（company_page.py から分離）
"""

import streamlit as st

from rag import (
    load_active_documents, get_or_create_knowledge_base,
    list_knowledge_bases, format_context, RESUME_KB_NAME,
)
from question_prediction import (
    generate_predicted_questions_from_rag,
    CATEGORY_LABELS as Q_CATEGORY_LABELS,
)
from favorites import (
    add_favorite, remove_favorite_by_item, is_favorited,
    ITEM_TYPE_LABELS,
)

def render_predict_questions(model_name: str):
    st.title("🎯 想定質問生成")
    st.write(
        "保存済みの履歴書と、選択した企業の情報をもとに、面接で聞かれそうな質問と"
        "模範回答例をまとめて生成します。"
    )

    if st.button("← インタビューに戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    resume_kb_id = get_or_create_knowledge_base(RESUME_KB_NAME, "resume")
    company_kbs = list_knowledge_bases(kb_type="company")

    if not company_kbs:
        st.warning(
            "企業情報がまだ保存されていません。サイドバーの「📎 参考資料（RAG）」から、"
            "会社名を入力して企業情報をアップロードしてください。"
        )
        st.stop()

    kb_options = {kb["name"]: kb["id"] for kb in company_kbs}
    selected_name = st.selectbox(
        "企業を選択してください",
        options=list(kb_options.keys()),
        key="pq_company_selector",
    )
    selected_kb_id = kb_options[selected_name]

    if st.session_state.pq_selected_company_kb_id != selected_kb_id:
        st.session_state.pq_selected_company_kb_id = selected_kb_id
        st.session_state.pq_questions = None
        st.session_state.pq_error = None

    st.write("")

    if st.session_state.pq_questions is None:
        predict_label = f"💬 「{selected_name}」向けの想定質問を生成する（8問）"
        if not st.session_state.pq_is_generating:
            if st.button(predict_label, type="primary"):
                st.session_state.pq_is_generating = True
                st.session_state.pq_error = None
                st.rerun()
            if st.session_state.pq_error:
                st.error(st.session_state.pq_error)
        else:
            st.button(predict_label, disabled=True)
            with st.spinner("履歴書・企業情報を読み込み、想定質問を生成中..."):
                try:
                    documents = load_active_documents([resume_kb_id, selected_kb_id])
                    resume_results = [
                        (d.doc_type, c, 1.0) for d in documents if d.doc_type == "resume" for c in d.chunks
                    ]
                    company_results = [
                        (d.doc_type, c, 1.0) for d in documents if d.doc_type == "company" for c in d.chunks
                    ]
                    resume_block = format_context(resume_results)
                    company_block = format_context(company_results)

                    if not resume_block and not company_block:
                        st.session_state.pq_error = (
                            "履歴書・企業情報のどちらも見つかりませんでした。"
                            "サイドバーから資料をアップロードしてください。"
                        )
                    else:
                        questions, ok, err = generate_predicted_questions_from_rag(
                            model_name, resume_block, company_block,
                        )
                        if ok and questions:
                            st.session_state.pq_questions = questions
                            st.session_state.pq_error = None
                        else:
                            st.session_state.pq_error = f"生成に失敗しました。詳細: {err}"
                except Exception as e:
                    st.session_state.pq_error = "想定質問の生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
            st.session_state.pq_is_generating = False
            st.rerun()

    else:
        grouped = defaultdict(list)
        for q in st.session_state.pq_questions:
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
        _pq_btn_cols = st.columns([1, 1])
        with _pq_btn_cols[0]:
            if st.button("🔄 想定質問を再生成する"):
                st.session_state.pq_questions = None
                st.rerun()
        with _pq_btn_cols[1]:
            _pq_session_id = st.session_state.get("current_session_id")
            _pq_is_fav = is_favorited("question_set", session_id=_pq_session_id) if _pq_session_id else False
            if _pq_is_fav:
                if st.button("⭐ お気に入り解除", key="pq_fav_remove", use_container_width=True):
                    remove_favorite_by_item("question_set", session_id=_pq_session_id)
                    st.rerun()
            else:
                if st.button("☆ お気に入りに追加", key="pq_fav_add", use_container_width=True,
                             help="この質問セットをお気に入りに保存（先にセッション保存が必要）"):
                    if not _pq_session_id:
                        st.toast("先にサイドバーからセッションを保存してください。", icon="⚠️")
                    else:
                        _pq_qs = st.session_state.pq_questions or []
                        add_favorite(
                            item_type="question_set",
                            session_id=_pq_session_id,
                            company_name=selected_name if selected_name != "（選択してください）" else None,
                            label=f"想定質問 - {selected_name}",
                            content_snapshot={"question_count": len(_pq_qs)},
                        )
                        st.toast("お気に入りに追加しました ⭐", icon="⭐")
                        st.rerun()


# ──────────────────────────────────────────────────────────────
