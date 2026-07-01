#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/check_sync.py
---------------------
db/ パッケージと rag/ パッケージ（rag/core.py を除く）は、Pythonのパッケージ
相対 import の都合上 shared/ への一本化ができず、streamlit/ ・
react-fastapi/backend/ にそれぞれ物理コピーを維持している（詳細は
MIGRATION_GUIDE.md を参照）。

このスクリプトは、それらのファイルが3箇所（shared/, streamlit/,
react-fastapi/backend/）で内容一致しているかを確認し、ズレがあれば
一覧表示して非ゼロ終了する。CI やコミット前フックでの利用を想定。

使い方:
    python3 shared/check_sync.py
"""
from __future__ import annotations

import filecmp
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "shared"
STREAMLIT = REPO_ROOT / "streamlit"
REACT_FASTAPI = REPO_ROOT / "react-fastapi" / "backend"

# 3箇所で内容一致しているべきファイル（rag/core.py は意図的に除外）
SYNCED_RELATIVE_PATHS = [
    "db/__init__.py",
    "db/database.py",
    "db/session_repository.py",
    "db/knowledge_base_repository.py",
    "db/settings_repository.py",
    "db/personality_repository.py",
    "rag/__init__.py",
    "rag/extraction.py",
    "rag/persistence.py",
]


def main() -> int:
    mismatches: list[str] = []
    missing: list[str] = []

    for rel_path in SYNCED_RELATIVE_PATHS:
        shared_file = SHARED / rel_path
        streamlit_file = STREAMLIT / rel_path
        fastapi_file = REACT_FASTAPI / rel_path

        for label, f in [
            ("shared", shared_file),
            ("streamlit", streamlit_file),
            ("react-fastapi/backend", fastapi_file),
        ]:
            if not f.exists():
                missing.append(f"{rel_path} が {label} に存在しません: {f}")

        if shared_file.exists() and streamlit_file.exists():
            if not filecmp.cmp(shared_file, streamlit_file, shallow=False):
                mismatches.append(f"{rel_path}: shared/ と streamlit/ で内容が異なります")

        if shared_file.exists() and fastapi_file.exists():
            if not filecmp.cmp(shared_file, fastapi_file, shallow=False):
                mismatches.append(f"{rel_path}: shared/ と react-fastapi/backend/ で内容が異なります")

    if missing or mismatches:
        print("❌ shared/ 同期チェック失敗\n")
        for m in missing:
            print(f"  [missing] {m}")
        for m in mismatches:
            print(f"  [diff]    {m}")
        print(
            "\n db/ パッケージ・rag/ パッケージ（core.py除く）は3箇所で内容が"
            "\n 一致している必要があります。詳細は shared/MIGRATION_GUIDE.md を参照してください。"
        )
        return 1

    print(f"✅ shared/ 同期チェック成功（{len(SYNCED_RELATIVE_PATHS)} ファイル、3箇所すべて一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
