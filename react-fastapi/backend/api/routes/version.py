"""
api/routes/version.py
-----------------------
アプリバージョン情報を返す軽量エンドポイント。

既存コードとの対応:
  streamlit版の components/sidebar/navigation.py render_version_info() が
  相当する。React版はサイドバー描画時にこのエンドポイントを叩いて
  現在のバージョンを表示する。

  streamlit版が持つ「GitHub Releasesと比較して最新版か判定する」機能
  （updater.fetch_latest_version）は今回のスコアには含めていない。
  必要であれば別途 /version/latest のような形で追加する。

GET /   現在のバージョン文字列を返す
"""
from __future__ import annotations

from fastapi import APIRouter

from version_info import APP_VERSION

router = APIRouter()


@router.get("")
async def get_version() -> dict:
    return {"version": APP_VERSION}
