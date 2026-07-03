"""
db パッケージ

よく使うDB操作を一箇所からインポートできるようにまとめています。

使用例:
    from db import db_session, init_db
    from db import get_setting, set_setting
    from db import save_session, get_session, list_sessions, delete_session
    from db import get_or_create_knowledge_base
"""

from db.database import init_db, db_session, get_connection
from db.settings_repository import get_setting, set_setting, delete_setting, get_all_settings
from db.session_repository import (
    save_session,
    get_session,
    list_sessions,
    delete_session,
)
from db.knowledge_base_repository import (
    get_or_create_knowledge_base,
    list_knowledge_bases,
    save_document,
    list_active_documents,
)
from db.favorites_repository import (
    add_favorite,
    remove_favorite,
    remove_favorite_by_item,
    is_favorited,
    get_favorite_id,
    list_favorites,
    list_distinct_companies,
    list_distinct_session_types,
    count_favorites,
)

__all__ = [
    # database
    "init_db",
    "db_session",
    "get_connection",
    # settings
    "get_setting",
    "set_setting",
    "delete_setting",
    "get_all_settings",
    # sessions
    "save_session",
    "get_session",
    "list_sessions",
    "delete_session",
    # knowledge base
    "get_or_create_knowledge_base",
    "list_knowledge_bases",
    "save_document",
    "load_active_documents",
    # favorites
    "add_favorite",
    "remove_favorite",
    "remove_favorite_by_item",
    "is_favorited",
    "get_favorite_id",
    "list_favorites",
    "list_distinct_companies",
    "list_distinct_session_types",
    "count_favorites",
]
