# -*- coding: utf-8 -*-
"""
core_sync/knowledge_sync.py
-----------------------------
企業研究資料(knowledge_bases, kb_type="company")の要約だけを、
local-ai-core の knowledge_items(全アプリ横断のナレッジ台帳)へ反映する。

全文・チャンク・embeddingはこれまで通り backend/rag_data, backend/uploads,
sqlite の documents/document_chunks に残す。ここに書くのは
「他アプリから見えてもよい要約」だけで、資料そのもののコピーは作らない。

ユーザーが knowledge_items:write を許可していない場合は、共通台帳への
反映だけを静かに諦める(= このアプリ内の企業研究/RAG機能そのものは
knowledge_bases テーブル側で完結しており、影響を受けない)。
"""
from __future__ import annotations

from typing import Optional

from local_ai_core.knowledge import KnowledgeStore
from local_ai_core.permissions import PermissionDenied

from db.database import get_core_db_path
from core_sync.bootstrap import get_profile_id

APP_KEY = "interview_app"


def sync_company_knowledge_base(
    kb_id: int,
    name: str,
    document_count: Optional[int] = None,
) -> None:
    """企業KBの作成・更新時(get_or_create_knowledge_base呼び出し後など)に呼ぶ。"""
    store = KnowledgeStore(get_core_db_path())
    summary = (
        f"{document_count}件の資料が登録された企業研究ノート"
        if document_count
        else "企業研究ノート"
    )
    try:
        store.upsert(
            profile_id=get_profile_id(),
            app_key=APP_KEY,
            source_ref_id=str(kb_id),
            title=name,
            category="company",
            summary=summary,
            tags=[name],
        )
    except PermissionDenied:
        pass
