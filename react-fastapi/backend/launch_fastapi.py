"""
launch_fastapi.py
------------------
FastAPI版 Interview App のランチャー。

PyInstaller でビルドされた exe から実行されることを想定。
- uvicorn でバックエンド（FastAPI）を起動
- フロントエンド（React ビルド済み静的ファイル）をバックエンド経由で配信
- 起動後にブラウザを自動で開く
"""
from __future__ import annotations

import os
import glob
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser


# ============================================================
# 設定
# ============================================================
BACKEND_PORT = 8000
FRONTEND_PORT = 8000   # バックエンドが静的ファイルも配信するため同じ
APP_URL = f"http://localhost:{BACKEND_PORT}"
STARTUP_TIMEOUT = 30   # バックエンド起動待ちタイムアウト（秒）


# ============================================================
# ユーティリティ
# ============================================================

def _base_path() -> str:
    """PyInstaller の一時展開先、または開発時のスクリプトディレクトリを返す。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _cleanup_old_meipass() -> None:
    """古い PyInstaller 一時フォルダを削除する。"""
    current = getattr(sys, "_MEIPASS", None)
    if current is None:
        return
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    if not temp_dir:
        return
    for folder in glob.glob(os.path.join(temp_dir, "_MEI*")):
        if os.path.abspath(folder) == os.path.abspath(current):
            continue
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass


def _kill_existing_process(port: int) -> None:
    """指定ポートを LISTEN しているプロセスを終了する。"""
    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
        )
        target_pids: set[int] = set()
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid == 0 or pid == my_pid:
                    continue
                target_pids.add(pid)

        for pid in target_pids:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
            )
    except Exception:
        pass

    # ポートが解放されるまで待つ（最大 5 秒）
    for _ in range(50):
        time.sleep(0.1)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    break
        except Exception:
            break


def _wait_for_server(port: int, timeout: int = STARTUP_TIMEOUT) -> bool:
    """サーバーが起動するまで待つ。タイムアウトした場合 False を返す。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def _open_browser() -> None:
    """サーバー起動後にブラウザを開く。"""
    if _wait_for_server(BACKEND_PORT):
        webbrowser.open(APP_URL)


# ============================================================
# メイン
# ============================================================

def main() -> None:
    _cleanup_old_meipass()
    _kill_existing_process(BACKEND_PORT)

    base = _base_path()

    # 環境変数でパスを通す
    os.environ.setdefault("INTERVIEW_STATIC_DIR", os.path.join(base, "frontend_dist"))
    os.environ.setdefault("PYTHONPATH", base)

    # ブラウザを別スレッドで開く（サーバー起動完了を待ってから）
    threading.Thread(target=_open_browser, daemon=True).start()

    # uvicorn でバックエンドを起動
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=BACKEND_PORT,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
