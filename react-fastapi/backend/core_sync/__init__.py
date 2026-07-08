# -*- coding: utf-8 -*-
"""
core_sync
----------
interview_app の各リポジトリ層(sessions, knowledge_bases)から呼ばれ、
local-ai-core の共通データ層(memory / knowledge / schedule)へ、
権限ゲート(PermissionGate)経由で「要約・状態」だけを反映するモジュール群。

全文・生データはこれまで通りアプリ固有DBに残る。ユーザーが許可していない
項目は PermissionDenied となり、各 sync 関数側で静かに無視される
(=このパッケージが失敗しても、アプリ本来の機能には一切影響しない)。
"""
from .bootstrap import bootstrap, get_profile_id, get_gate
from .knowledge_sync import sync_company_knowledge_base
from .es_sync import sync_es_status
from .schedule_sync import sync_interview_schedule

__all__ = [
    "bootstrap",
    "get_profile_id",
    "get_gate",
    "sync_company_knowledge_base",
    "sync_es_status",
    "sync_interview_schedule",
]
