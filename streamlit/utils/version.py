"""
utils/version.py
-----------------
アプリバージョン管理。

提供するもの:
    APP_VERSION - 実行環境に応じたバージョン文字列（例: "1.2.3+abc1234"）
    get_version() - バージョン文字列を解決して返す
"""

from __future__ import annotations

import os
import sys


def get_version() -> str:
    """実行環境に応じてバージョンを返す。

    - EXE実行時: _MEIPASSのversion.txtを読む
    - 開発時:    プロジェクトルートのversion.txtを読む
    - どちらもなければ: "dev" を返す
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    # utils/ パッケージ内からプロジェクトルートを指す（../version.txt）
    path = os.path.join(base, "..", "version.txt")
    if not os.path.exists(path):
        # EXE実行時は _MEIPASS 直下にある
        path = os.path.join(base, "version.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "dev"


APP_VERSION: str = get_version()  # 例: "1.2.3+abc1234"
