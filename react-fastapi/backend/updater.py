"""
updater.py（React + FastAPI版）
--------------------------------
起動時にGitHub Releasesを確認し、新バージョンがあれば
自動ダウンロード→インストーラー起動→アプリ終了する。

streamlit/updater.py と同じ設計方針を踏襲している:
- GitHub REST APIの未認証レート制限（60回/時/IP）対策として、
  結果を %APPDATA%\\InterviewApp\\update_cache_fastapi.json にキャッシュ
- TTL内は再リクエストしない
- リクエストする場合もETagで条件付きGET（304はレート制限にカウントされない）
- リクエスト自体が失敗（403レート制限超過など）した場合は、
  古くてもキャッシュがあればそれにフォールバックする

Streamlit版との相違点:
- 依存ライブラリを増やさないため、requests ではなく標準ライブラリの
  urllib.request を使用する（launch_fastapi.py の _download_with_progress と同じ方針）。
- GitHubリリースには Streamlit版インストーラー（InterviewAppSetup.exe）と
  FastAPI版インストーラー（InterviewAppSetupFastAPI.exe）の両方が同じ
  リリースに同梱されるため、拡張子(.exe)だけでなく完全なファイル名で
  アセットを絞り込む。これをしないと誤って別バージョン向けの
  インストーラーを取得してしまう可能性がある。
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from utils import APP_VERSION

logger = logging.getLogger(__name__)

GITHUB_REPO = "Myubd/interview-ai-app"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# このアプリ（FastAPI版）が探すインストーラーのアセット名。
# 同じリリースにStreamlit版のインストーラーも同梱されているため、
# 拡張子一致ではなく完全一致で絞り込む。
INSTALLER_ASSET_NAME = "InterviewAppSetupFastAPI.exe"

# キャッシュのTTL。この時間内は同じキャッシュ結果を使い回し、
# GitHub APIへのリクエスト自体を行わない。
_CACHE_TTL_SECONDS = 60 * 60  # 1時間


def _cache_path() -> Path:
    """update_cache_fastapi.json の保存先。db側と同じ %APPDATA%\\InterviewApp を使う。"""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA") or str(Path.home())
        base = Path(appdata) / "InterviewApp"
    else:
        base = Path(__file__).resolve().parent
    return base / "update_cache_fastapi.json"


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


def _ssl_context() -> ssl.SSLContext:
    """PyInstaller環境でcertifiバンドルが無い場合に備えたSSLコンテキスト。

    launch_fastapi.py の _download_with_progress と同じフォールバック方針。
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        try:
            return ssl.create_default_context()
        except Exception:
            return ssl._create_unverified_context()


def _fetch_release_data() -> dict[str, Any] | None:
    """
    GitHub Releases APIから最新リリース情報(dict)を取得する。
    キャッシュ・ETag・レート制限フォールバックをまとめて面倒見る共通処理。
    """
    cache = _load_cache()
    now = time.time()

    fetched_at = cache.get("fetched_at", 0)
    if cache.get("data") and (now - fetched_at) < _CACHE_TTL_SECONDS:
        logger.debug("[updater] キャッシュがTTL内のためAPIリクエストをスキップ")
        return cache["data"]

    headers = {
        # GitHub APIはUser-Agent必須
        "User-Agent": "InterviewApp-Updater",
        "Accept": "application/vnd.github+json",
    }
    etag = cache.get("etag")
    if etag:
        headers["If-None-Match"] = etag

    req = urllib.request.Request(RELEASES_API, headers=headers)
    ctx = _ssl_context()

    try:
        with urllib.request.urlopen(req, timeout=5, context=ctx) as res:
            data = json.loads(res.read().decode("utf-8"))
            new_cache = {
                "etag": res.headers.get("ETag", ""),
                "fetched_at": now,
                "data": data,
            }
            _save_cache(new_cache)
            return data

    except urllib.error.HTTPError as e:
        if e.code == 304:
            # 更新なし。レート制限にはカウントされない。
            logger.debug("[updater] 304 Not Modified（キャッシュを継続利用）")
            cache["fetched_at"] = now
            _save_cache(cache)
            return cache.get("data")

        remaining = e.headers.get("X-RateLimit-Remaining") if e.headers else None
        reset = e.headers.get("X-RateLimit-Reset") if e.headers else None
        logger.warning(
            f"[updater] バージョン確認失敗: {e} "
            f"(X-RateLimit-Remaining={remaining}, X-RateLimit-Reset={reset})"
        )

    except Exception as e:
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
    FastAPI版インストーラー（INSTALLER_ASSET_NAME）が
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

    フロントエンドのバージョン表示用エンドポイントから呼ばれる想定。
    check_and_update() と同じキャッシュ/ETagを共有する。
    """
    data = _fetch_release_data()
    if data is None:
        return None, "バージョン情報の取得に失敗しました（キャッシュもありません）"
    return data.get("tag_name", ""), None


def check_and_update() -> None:
    """
    launch_fastapi.py の main() から、uvicorn起動前に呼び出す。
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

    logger.info(f"[updater] 新バージョン検出: {current} → {latest}")

    try:
        ctx = _ssl_context()
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)

        tmp = tempfile.NamedTemporaryFile(
            suffix=".exe", delete=False, prefix="InterviewAppSetupFastAPI_"
        )
        tmp.close()
        logger.info(f"[updater] 新バージョン {latest_tag} をダウンロード中...")
        urllib.request.urlretrieve(installer_url, tmp.name)

        # インストール完了後にアプリを自動再起動させる
        # batスクリプト経由でインストール完了を待ってから再起動
        exe_path = sys.executable
        restart_bat = tempfile.NamedTemporaryFile(
            suffix=".bat", delete=False, prefix="restart_interview_fastapi_"
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
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        os._exit(0)

    except Exception as e:
        logger.error(f"[updater] ダウンロード失敗: {e}")
