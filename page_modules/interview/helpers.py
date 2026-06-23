"""
interview/helpers.py
共通ヘルパー関数（会話履歴・RAGブロック・プロフィールテキスト生成）
"""

import streamlit as st

from rag import build_query_from_student_answers, format_context, search_balanced
from utils import sanitize_user_input


def build_conversation_history() -> str:
    history = ""
    if st.session_state.profile_text:
        history += (
            f"【事前情報（学生プロフィール／事前入力フォームより）】\n{st.session_state.profile_text}\n\n"
            "【ここからインタビュー本編】\n"
        )
    for msg in st.session_state.messages:
        role_label = "面接官" if msg["role"] == "assistant" else "学生"
        history += f"{role_label}: {msg['content']}\n"
    return history


def build_rag_block(conversation_history: str) -> str:
    if not st.session_state.rag_documents:
        return ""
    query = build_query_from_student_answers(conversation_history)
    results = search_balanced(query, st.session_state.rag_documents, top_k_per_type=4)
    rag_context = format_context(results)
    if not rag_context:
        return ""
    return (
        f"\n【参考資料】\n{rag_context}\n"
        "（参考資料に書かれた具体的な実績・数字・企業の特徴があれば、自然な形で自己PRに反映してください）\n"
    )


def build_profile_text(education: str, work_history: str, licenses: str) -> str:
    parts = []
    if education.strip():
        parts.append(f"【学歴】\n{sanitize_user_input(education.strip())}")
    if work_history.strip():
        parts.append(f"【職歴（インターン・アルバイト等）】\n{sanitize_user_input(work_history.strip())}")
    if licenses.strip():
        parts.append(f"【資格・免許】\n{sanitize_user_input(licenses.strip())}")
    return "\n\n".join(parts)
