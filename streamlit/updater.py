"""
updater.py
----------
起動時にGitHub Releasesを確認し、新バージョンがあれば
自動ダウンロード→インストーラー起動→アプリ終了する。

GitHub REST APIの未認証レート制限（60回/時/IP）を消費しすぎないよう、
取得結果を %APPDATA%\\InterviewApp\\update_cache.json にキャッシュし、
- TTL内であれば再リクエストしない
- リクエストする場合もETagで条件付きGET（304時はレート制限にカウントされない）
- リクエスト自体が失敗（403レート制限超過など）した場合は、
  古くてもキャッシュがあればそれにフォールバックする
という方針で実装している。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
import streamlit as st

from utils import APP_VERSION

logger = logging.getLogger(__name__)

GITHUB_REPO = "Myubd/interview-ai-app"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# このアプリ（Streamlit版）が探すインストーラーのアセット名。
# 同じリリースにReact+FastAPI版のインストーラー（InterviewAppSetupFastAPI.exe）も
# 同梱されているため、拡張子一致ではなく完全一致で絞り込む。
# これをしないと、GitHub APIが返すassetsの順序次第で
# 誤って別バージョン向けのインストーラーを取得する可能性がある。
INSTALLER_ASSET_NAME = "InterviewAppSetup.exe"

# キャッシュのTTL。この時間内は同じキャッシュ結果を使い回し、
# GitHub APIへのリクエスト自体を行わない。
_CACHE_TTL_SECONDS = 60 * 60  # 1時間


def _cache_path() -> Path:
    """update_cache.json の保存先。db.database と同様に %APPDATA%\\InterviewApp を使う。"""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA") or str(Path.home())
        base = Path(appdata) / "InterviewApp"
    else:
        base = Path(__file__).resolve().parent
    return base / "update_cache.json"


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.debug(f"[updater] キャッシュ保存失敗: {e}")


def _fetch_release_data() -> dict[str, Any] | None:
    """
    GitHub Releases APIから最新リリース情報(dict)を取得する。
    キャッシュ・ETag・レート制限フォールバックをまとめて面倒見る共通処理。

    戻り値は GitHub API の releases/latest レスポンス相当の dict
    （少なくとも tag_name / assets キーを持つ）。取得も代替も
    できない場合のみ None を返す。
    """
    cache = _load_cache()
    now = time.time()

    fetched_at = cache.get("fetched_at", 0)
    if cache.get("data") and (now - fetched_at) < _CACHE_TTL_SECONDS:
        logger.debug("[updater] キャッシュがTTL内のためAPIリクエストをスキップ")
        return cache["data"]

    headers = {}
    etag = cache.get("etag")
    if etag:
        headers["If-None-Match"] = etag

    try:
        res = requests.get(RELEASES_API, headers=headers, timeout=5)

        if res.status_code == 304:
            # 更新なし。レート制限にはカウントされない。
            # fetched_atだけ更新してTTLを延長する。
            logger.debug("[updater] 304 Not Modified（キャッシュを継続利用）")
            cache["fetched_at"] = now
            _save_cache(cache)
            return cache.get("data")

        res.raise_for_status()
        data = res.json()

        new_cache = {
            "etag": res.headers.get("ETag", ""),
            "fetched_at": now,
            "data": data,
        }
        _save_cache(new_cache)
        return data

    except Exception as e:
        response = getattr(e, "response", None)
        if response is not None:
            logger.warning(
                f"[updater] バージョン確認失敗: {e} "
                f"(X-RateLimit-Remaining={response.headers.get('X-RateLimit-Remaining')}, "
                f"X-RateLimit-Reset={response.headers.get('X-RateLimit-Reset')})"
            )
        else:
            logger.warning(f"[updater] バージョン確認失敗: {e}")

        # リクエスト自体が失敗した場合（403レート制限超過など）は、
        # 古くてもキャッシュがあればそれを使う。
        if cache.get("data"):
            logger.info("[updater] リクエスト失敗のため古いキャッシュにフォールバック")
            return cache["data"]
        return None


def _normalize(version: str) -> str:
    """'v1.2.3' → '1.2.3'"""
    return version.lstrip("v")


def _fetch_latest() -> tuple[str, str] | None:
    """
    最新リリースの (tag_name, installer_url) を返す。
    Streamlit版インストーラー（INSTALLER_ASSET_NAME）が
    見つからない場合、または取得自体に失敗した場合は None を返す。
    """
    data = _fetch_release_data()
    if data is None:
        return None
    tag = data.get("tag_name", "")
    assets = data.get("assets", [])
    for asset in assets:
        if asset.get("name", "") == INSTALLER_ASSET_NAME:
            return tag, asset["browser_download_url"]
    logger.warning(
        f"[updater] リリース {tag} に {INSTALLER_ASSET_NAME} が見つかりません"
    )
    return None


def fetch_latest_version() -> tuple[str | None, str | None]:
    """最新バージョンのタグ名を返す。失敗時は (None, エラーメッセージ) を返す。

    サイドバーのバージョン表示用。EXE・開発環境どちらでも動作する。
    check_and_update() と同じキャッシュ/ETagを共有するため、
    サイドバー表示とアップデートチェックで別々にAPIを叩くことがなくなった。
    """
    data = _fetch_release_data()
    if data is None:
        return None, "バージョン情報の取得に失敗しました（キャッシュもありません）"
    return data.get("tag_name", ""), None


def check_and_update() -> None:
    """
    app.py の init_db() 直後に呼び出す。
    新バージョンがあれば自動でダウンロード・インストール・終了する。
    EXE以外（開発環境）では何もしない。
    """
    # 開発環境では動作しない
    if not getattr(sys, "frozen", False):
        return

    # APP_VERSION が "dev" または空の場合もスキップ
    if not APP_VERSION or APP_VERSION == "dev":
        return

    result = _fetch_latest()
    if result is None:
        return

    latest_tag, installer_url = result
    current = _normalize(APP_VERSION.split("+")[0])  # "1.2.3+abc1234" → "1.2.3"
    latest = _normalize(latest_tag)

    if current == latest:
        return  # 最新版なので何もしない

    # 新バージョンあり → ダウンロード開始
    logger.info(f"[updater] 新バージョン検出: {current} → {latest}")

    with st.spinner(f"新バージョン {latest_tag} をダウンロード中..."):
        try:
            res = requests.get(installer_url, stream=True, timeout=120)
            res.raise_for_status()

            tmp = tempfile.NamedTemporaryFile(
                suffix=".exe", delete=False, prefix="InterviewAppSetup_"
            )
            for chunk in res.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp.close()

            # インストール完了後にアプリを自動再起動させる
            # batスクリプト経由でインストール完了を待ってから再起動
            exe_path = sys.executable
            restart_bat = tempfile.NamedTemporaryFile(
                suffix=".bat", delete=False, prefix="restart_interview_"
            )
            restart_bat.write(
                f'@echo off\n'
                f'start /wait "" "{tmp.name}" /SILENT /CLOSEAPPLICATIONS\n'
                f'for /d %%i in ("%TEMP%\\_MEI*") do rmdir /s /q "%%i"\n'
                f'timeout /t 3 /nobreak > nul\n'
                f'start "" "{exe_path}"\n'
                .encode("utf-8")
            )
            restart_bat.close()
            subprocess.Popen(
                ["cmd", "/c", restart_bat.name],
                close_fds=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            os._exit(0)

        except Exception as e:
            logger.error(f"[updater] ダウンロード失敗: {e}")
            st.warning("アップデートのダウンロードに失敗しました。手動で更新してください。")
