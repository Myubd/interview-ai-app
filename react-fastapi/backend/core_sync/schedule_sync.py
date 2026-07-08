# -*- coding: utf-8 -*-
"""
core_sync/schedule_sync.py
-----------------------------
sessions.scheduled_at(面接の予定日時)を、local-ai-core の schedule_items
(全アプリ横断の予定/タスク台帳)へ反映する。scheduled_atがNoneの場合は
「予定日未定」として共通の予定表には出さない。
"""
from __future__ import annotations

from typing import Optional

from local_ai_core.schedule import ScheduleStore
from local_ai_core.permissions import PermissionDenied

from db.database import get_core_db_path
from core_sync.bootstrap import get_profile_id

APP_KEY = "interview_app"


def sync_interview_schedule(
    session_id: int,
    company_name: Optional[str],
    scheduled_at: Optional[str],
) -> None:
    store = ScheduleStore(get_core_db_path())
    source_ref_id = str(session_id)

    if not scheduled_at:
        # 予定日が未設定/取り消された場合は、既存の共通予定があれば完了扱いにして
        # ライフサポートOS側の予定表に残り続けないようにする。
        try:
            store.set_status(get_profile_id(), APP_KEY, source_ref_id, status="cancelled")
        except PermissionDenied:
            pass
        return

    title = f"{company_name}の面接" if company_name else "面接"
    try:
        store.upsert(
            profile_id=get_profile_id(),
            app_key=APP_KEY,
            source_ref_id=source_ref_id,
            item_type="event",
            title=title,
            due_at=scheduled_at,
            status="open",
        )
    except PermissionDenied:
        pass
