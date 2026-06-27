"""
session_io/__init__.py
-----------------------
後方互換のための re-export。

既存コードが `from session_io import serialize_session` 等と書いていても
そのまま動くようにすべてのパブリックシンボルを再エクスポートする。

サブモジュール構成:
    serializer.py - スナップショット作成・シリアライズ・デシリアライズ・復元・定数定義
    db_io.py      - SessionState <-> SQLite の読み書き
    json_io.py    - JSONエクスポート・インポート（バックアップ・移行用）
"""

from session_io.serializer import (
    SESSION_FORMAT_VERSION,
    SESSION_DIRECT_KEYS,
    SESSION_JSON_KEYS,
    PROGRESS_STATE_KEYS,
    PERSONALITY_KEYS,
    SAVE_KEYS,
    SKIP_RESTORE_KEYS,
    build_session_snapshot,
    serialize_session,
    deserialize_session,
    restore_session,
    make_filename,
)

from session_io.db_io import (
    save_session_to_db,
    list_sessions,
    load_session_from_db,
    delete_session,
    RESUME_KB_NAME,
)

from session_io.json_io import (
    export_session_as_json,
    import_json_as_session,
)

__all__ = [
    # serializer
    "SESSION_FORMAT_VERSION",
    "SESSION_DIRECT_KEYS",
    "SESSION_JSON_KEYS",
    "PROGRESS_STATE_KEYS",
    "PERSONALITY_KEYS",
    "SAVE_KEYS",
    "SKIP_RESTORE_KEYS",
    "build_session_snapshot",
    "serialize_session",
    "deserialize_session",
    "restore_session",
    "make_filename",
    # db_io
    "save_session_to_db",
    "list_sessions",
    "load_session_from_db",
    "delete_session",
    "RESUME_KB_NAME",
    # json_io
    "export_session_as_json",
    "import_json_as_session",
]
