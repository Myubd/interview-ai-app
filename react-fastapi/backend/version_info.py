# -*- coding: utf-8 -*-
"""
version_info.py
-----------------
アプリバージョン管理（React+FastAPI版）。

streamlit/utils/version.py と同じ方針で version.txt を解決する。
- EXE実行時: _MEIPASS 直下の version.txt を読む（launch_fastapi.py の
  _base_path() と同じ解決方法。詳細はそちらのコメントを参照）
- 開発時:    このファイルと同じディレクトリの version.txt を読む
- どちらもなければ: "dev" を返す

version.txt は CI（.github/workflows/cd.yml の react-fastapi ビルドジョブ）が
Gitタグから生成して上書きする。streamlit/version.txt と同様、リポジトリには
デフォルト値をコミットしておき、リリースのたびに CI が上書きする運用とする。

提供するもの:
    APP_VERSION - 実行環境に応じたバージョン文字列（例: "3.3.0+9c814d0"）
    get_version() - バージョン文字列を解決して返す
"""

from __future__ import annotations

import os
import sys


def get_version() -> str:
    """実行環境に応じてバージョンを返す。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "version.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "dev"


APP_VERSION: str = get_version()  # 例: "3.3.0+9c814d0"
