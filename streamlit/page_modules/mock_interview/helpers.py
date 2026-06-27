"""
page_modules/mock_interview/helpers.py
RAGブロック構築などの純粋なユーティリティ関数
"""

import streamlit as st

from rag import build_query_from_student_answers, format_context, search_balanced
import mock_interview_engine as mie


def build_rag_block(query_text: str) -> str:
    """RAGドキュメントからコンテキストブロックを構築する。"""
    if not st.session_state.rag_documents:
        return ""
    query = build_query_from_student_answers(query_text) if query_text else "学生の自己PR・強み"
    results = search_balanced(query, st.session_state.rag_documents, top_k_per_type=4)
    return format_context(results)


def full_history_for_rag() -> str:
    """会話履歴全体をRAG用テキストとして返す。"""
    return mie.build_full_history_text(st.session_state.mock_messages)
