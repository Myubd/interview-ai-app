# -*- coding: utf-8 -*-
"""
db/settings_repository.py
---------------------------
settings テーブル（key-valueのアプリ設定）に対する標準的なCRUD処理を担うリポジトリ。

[新規作成について]
既存コードに settings テーブルへの利用箇所が見当たらなかったため、
他リポジトリと一貫したインターフェースの標準的なget/set/delete/get_allを
新規に実装した。
"""

from __future__ import annotations

from db.database import db_session


def get_setting(key: str, default: str | None = None) -> str | None:
    """指定キーの設定値を取得する。存在しない場合はdefaultを返す。"""
    with db_session() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default


def set_setting(key: str, value: str | None) -> None:
    """指定キーの設定値を保存する（既存があれば上書き、なければ新規作成）。"""
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def delete_setting(key: str) -> None:
    """指定キーの設定値を削除する。"""
    with db_session() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def get_all_settings() -> dict[str, str | None]:
    """全設定値を {key: value} のdictで返す。"""
    with db_session() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}


__all__ = [
    "get_setting",
    "set_setting",
    "delete_setting",
    "get_all_settings",
]
