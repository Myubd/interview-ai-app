# -*- coding: utf-8 -*-
"""
core_sync/bootstrap.py
------------------------
アプリ起動時に1回呼ぶ。以下をまとめて行う(すべて冪等):

1. local-ai-core の共通スキーマ(core.db)を初期化する
2. このデバイス用の device_identity / profiles 行を用意する
   (ログイン不要の単一プロフィール前提。将来複数プロフィールに
   対応する場合はここを拡張する)
3. plugin_manifest.json を読み込み、自分自身(interview_app)を
   source_apps / permission_scopes に登録する(まだ何も読めない状態で申告するだけ)

このモジュールがどこにも書き込みを許可するわけではない点に注意。
実際のアクセス許可は、ユーザーが設定画面で PermissionGate.grant() を
呼んで初めて有効になる。
"""
from __future__ import annotations

import base64
import sqlite3
from pathlib import Path
from typing import Optional

from local_ai_core.schema import init_core_schema
from local_ai_core.identity import DeviceIdentity
from local_ai_core.permissions import PermissionGate
from local_ai_core.plugins import PluginManifest, register_plugin

from db.database import get_core_db_path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_MANIFEST_PATH = _BACKEND_DIR / "plugin_manifest.json"
_DEVICE_IDENTITY_PATH = _BACKEND_DIR / "device_identity.json"

_profile_id_cache: Optional[int] = None


def _ensure_device_and_profile(db_path: str, device_id: str, key_salt: bytes) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            "INSERT INTO device_identity (id, key_salt) VALUES (?, ?) "
            "ON CONFLICT(id) DO NOTHING",
            (device_id, base64.b64encode(key_salt).decode("ascii")),
        )
        row = conn.execute(
            "SELECT id FROM profiles WHERE device_id = ? ORDER BY id LIMIT 1",
            (device_id,),
        ).fetchone()
        if row is not None:
            profile_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO profiles (device_id, display_name) VALUES (?, ?)",
                (device_id, "デフォルトプロフィール"),
            )
            profile_id = cur.lastrowid
        conn.commit()
        return profile_id
    finally:
        conn.close()


def bootstrap() -> int:
    """FastAPIのlifespanから呼ぶ。profile_idを返す(以後の core_sync 呼び出しで使う)。"""
    global _profile_id_cache

    db_path = get_core_db_path()
    init_core_schema(db_path)

    identity = DeviceIdentity(storage_path=str(_DEVICE_IDENTITY_PATH))
    profile_id = _ensure_device_and_profile(db_path, identity.device_id, identity.key_salt)

    manifest = PluginManifest.load(_PLUGIN_MANIFEST_PATH)
    register_plugin(db_path, manifest)

    _profile_id_cache = profile_id
    return profile_id


def get_profile_id() -> int:
    """bootstrap()未実行なら実行してからprofile_idを返す(呼び出し側で毎回意識しなくてよい)。"""
    if _profile_id_cache is None:
        return bootstrap()
    return _profile_id_cache


def get_gate() -> PermissionGate:
    return PermissionGate(get_core_db_path())
