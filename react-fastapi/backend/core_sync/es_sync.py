# -*- coding: utf-8 -*-
"""
core_sync/es_sync.py
----------------------
ES(自己PR)の「状態」だけを local-ai-core の memory_items へ反映する。

全文(final_pr / pr_variants の本文)はコピーしない。他アプリが必要とするのは
「A社向けのESは確定済みか、まだ案の段階か」という事実だけ、という想定。

confidenceの区別:
- final_pr が確定している = ユーザーが複数案から選んだ/書いた最終版がある
  → "user_confirmed"
- pr_variants しかない = AIが生成した案が並んでいるだけで、まだ確定していない
  → "ai_inferred"
"""
from __future__ import annotations

from typing import Optional

from local_ai_core.memory import MemoryStore
from local_ai_core.permissions import PermissionDenied

from db.database import get_core_db_path
from core_sync.bootstrap import get_profile_id

APP_KEY = "interview_app"


def sync_es_status(
    session_id: int,
    company_name: Optional[str],
    final_pr: Optional[str],
    pr_variants,
) -> None:
    if not company_name:
        return  # 会社名が未確定のセッションは、どの企業のESか特定できないためスキップ

    if final_pr:
        status, confidence = "finalized", "user_confirmed"
    elif pr_variants:
        status, confidence = "draft", "ai_inferred"
    else:
        return  # ESに関する情報が何もないセッションは同期対象外

    store = MemoryStore(get_core_db_path())
    key = f"career.es_status.{company_name}"
    try:
        store.set(
            profile_id=get_profile_id(),
            app_key=APP_KEY,
            key=key,
            value={"status": status, "session_id": session_id, "company_name": company_name},
            confidence=confidence,
        )
    except PermissionDenied:
        pass
