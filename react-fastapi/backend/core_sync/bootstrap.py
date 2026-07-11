# -*- coding: utf-8 -*-
"""
core_sync/bootstrap.py
------------------------
アプリ起動時に1回呼ぶ。実際の初期化ロジックは local_ai_core.bootstrap_app に
一本化されている(以前はこのファイルに直接実装していたが、Archlife側で
同じロジックを別実装すると、パスの組み立て方の違いから「別々のcore.db /
別々のdevice_id」を見てしまう事故が起きたため、共通化した)。

このファイルは、既存の呼び出し側(es_sync.py / knowledge_sync.py /
schedule_sync.py が `from core_sync.bootstrap import get_profile_id` の形で
依存している)との互換性を保つための薄いラッパーとしてのみ存在する。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from local_ai_core.bootstrap import bootstrap_app  # NOTE: `from local_ai_core import bootstrap_app`
# ではなく必ずこの書き方にすること。backend/local_ai_core/ (submoduleのルート、
# __init__.pyを持たない)がPythonの名前空間パッケージとして`local_ai_core`を
# 名乗ってしまい、site-packages側の正しい `local_ai_core` パッケージと
# マージされる。サブモジュール(.memory, .permissions 等)は名前空間パッケージ
# 越しでも見えるが、`local_ai_core/__init__.py` 経由で再exportされる名前
# (bootstrap_app 等)は名前空間パッケージでは実行されないため見えなくなる。
from local_ai_core.paths import get_core_db_path
from local_ai_core.permissions import PermissionGate

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_MANIFEST_PATH = _BACKEND_DIR / "plugin_manifest.json"

_profile_id_cache: Optional[int] = None


def bootstrap() -> int:
    """FastAPIのlifespanから呼ぶ。profile_idを返す(以後の core_sync 呼び出しで使う)。

    core.db / device_identity.json のパスは local_ai_core.paths が解決する
    共有パスを使う(このファイル側では一切パスを組み立てない)。
    """
    global _profile_id_cache
    profile_id = bootstrap_app(_PLUGIN_MANIFEST_PATH)
    _profile_id_cache = profile_id
    return profile_id


def get_profile_id() -> int:
    """bootstrap()未実行なら実行してからprofile_idを返す(呼び出し側で毎回意識しなくてよい)。"""
    if _profile_id_cache is None:
        return bootstrap()
    return _profile_id_cache


def get_gate() -> PermissionGate:
    return PermissionGate(get_core_db_path())
