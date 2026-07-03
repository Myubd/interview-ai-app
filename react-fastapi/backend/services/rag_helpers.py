# -*- coding: utf-8 -*-
"""
services/rag_helpers.py
--------------------------
自己PR作成フロー・想定質問（自己PRベース版）で共通して使う、
会話履歴の整形とRAG検索のヘルパー。

既存コードとの対応:
  streamlit版 page_modules/interview/helpers.py の
  build_conversation_history() / build_rag_block() が相当する。

db/・rag/ はアプリごとの物理コピー（管理対象外）に依存するため、
このファイル自体は shared/ に置かず、backend 固有のサービス層に置く
（shared/MIGRATION_GUIDE.md の「新しい共有ロジックを追加する場合の判断基準」を参照）。
"""
from __future__ import annotations

from db.knowledge_base_repository import list_knowledge_bases
from rag.persistence import load_active_documents
from rag.core import build_query_from_student_answers, search_balanced, format_context


def build_conversation_history(profile_text: str | None, messages: list[dict]) -> str:
    """helpers.build_conversation_history 相当。"""
    history = ""
    if profile_text:
        history += (
            f"【事前情報（学生プロフィール／事前入力フォームより）】\n{profile_text}\n\n"
            "【ここからインタビュー本編】\n"
        )
    for msg in messages:
        role_label = "面接官" if msg["role"] == "assistant" else "学生"
        history += f"{role_label}: {msg['content']}\n"
    return history


def build_rag_block_from_active_kbs(conversation_history: str) -> str:
    """helpers.build_rag_block 相当。

    アクティブな全KB（履歴書・企業情報を問わない）から、会話履歴（学生の発言）と
    意味的に近いチャンクを検索してブロック文字列を返す。
    """
    active_kb_ids = [kb["id"] for kb in list_knowledge_bases() if kb.get("is_active")]
    if not active_kb_ids:
        return ""
    documents = load_active_documents(active_kb_ids)
    if not documents:
        return ""
    query = build_query_from_student_answers(conversation_history)
    results = search_balanced(query, documents, top_k_per_type=4)
    rag_context = format_context(results)
    if not rag_context:
        return ""
    return (
        f"\n【参考資料】\n{rag_context}\n"
        "（参考資料に書かれた具体的な実績・数字・企業の特徴があれば、自然な形で自己PRに反映してください）\n"
    )
