"""
updater.py
----------
起動時にGitHub Releasesを確認し、新バージョンがあれば
自動ダウンロード→インストーラー起動→アプリ終了する。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading

import requests
import streamlit as st

from utils import APP_VERSION

logger = logging.getLogger(__name__)

GITHUB_REPO = "Myubd/interview-ai-app"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _normalize(version: str) -> str:
    """'v1.2.3' → '1.2.3'"""
    return version.lstrip("v")


def _fetch_latest() -> tuple[str, str] | None:
    """
    最新リリースの (tag_name, installer_url) を返す。
    失敗した場合は None を返す。
    """
    try:
        res = requests.get(RELEASES_API, timeout=5)
        res.raise_for_status()
        data = res.json()
        tag = data.get("tag_name", "")
        assets = data.get("assets", [])
        for asset in assets:
            name: str = asset.get("name", "")
            if name.endswith(".exe"):
                return tag, asset["browser_download_url"]
    except Exception as e:
        logger.warning(f"[updater] バージョン確認失敗: {e}")
    return None


def _download_and_install(url: str) -> None:
    """インストーラーをダウンロードして起動し、アプリを終了する。"""
    try:
        st.session_state["_update_status"] = "downloading"
        res = requests.get(url, stream=True, timeout=120)
        res.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(
            suffix=".exe", delete=False, prefix="InterviewAppSetup_"
        )
        for chunk in res.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()

        st.session_state["_update_status"] = "ready"
        subprocess.Popen([tmp.name], close_fds=True)
        os._exit(0)

    except Exception as e:
        logger.error(f"[updater] ダウンロード失敗: {e}")
        st.session_state["_update_status"] = "error"


def check_and_update() -> None:
    """
    app.py の init_db() 直後に呼び出す。
    新バージョンがあれば自動でダウンロード・インストール・終了する。
    EXE以外（開発環境）では何もしない。
    """
    # 開発環境では動作しない
    if not getattr(sys, "frozen", False):
        return

    # APP_VERSION が "dev" の場合もスキップ
    if APP_VERSION == "dev":
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
    st.session_state.setdefault("_update_status", "starting")

    with st.spinner(f"新バージョン {latest_tag} をダウンロード中..."):
        t = threading.Thread(target=_download_and_install, args=(installer_url,), daemon=True)
        t.start()
        t.join(timeout=120)

    status = st.session_state.get("_update_status", "error")
    if status == "error":
        st.warning("アップデートのダウンロードに失敗しました。手動で更新してください。")
