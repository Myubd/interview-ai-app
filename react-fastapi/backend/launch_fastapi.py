"""
launch_fastapi.py
------------------
FastAPI版 Interview App のランチャー。

PyInstaller でビルドされた exe から実行されることを想定。
- Ollama のインストール確認・自動インストール
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

# Ollama 設定
OLLAMA_HOST = "http://localhost:11434"


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
# Ollama インストール確認・自動セットアップ
# ============================================================

def _is_ollama_installed() -> bool:
    """Ollama が PATH に存在するか、または既知のインストール先にあるか確認する。"""
    # PATH から探す
    if shutil.which("ollama") is not None:
        return True
    # Windows デフォルトインストール先
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    default_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
    return os.path.isfile(default_path)


def _is_ollama_running() -> bool:
    """Ollama の HTTP API に疎通できるか確認する。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            host = OLLAMA_HOST.replace("http://", "").replace("https://", "")
            hostname, _, port_str = host.partition(":")
            port = int(port_str) if port_str else 11434
            return s.connect_ex((hostname, port)) == 0
    except Exception:
        return False


def _install_ollama() -> bool:
    """Ollama を公式サイトからダウンロードしてサイレントインストールする。"""
    import tempfile
    import urllib.request

    OLLAMA_DOWNLOAD_URL = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"

    _show_message(
        "Ollama をインストールしています",
        "Ollama がインストールされていないため、自動的にダウンロード・インストールします。
"
        "ダウンロードには数分かかる場合があります。

しばらくお待ちください…",
    )

    tmp_dir = tempfile.mkdtemp()
    installer = os.path.join(tmp_dir, "OllamaSetup.exe")

    try:
        urllib.request.urlretrieve(OLLAMA_DOWNLOAD_URL, installer)
    except Exception as e:
        _show_message(
            "Ollama ダウンロード失敗",
            f"Ollama のダウンロードに失敗しました: {e}
"
            "インターネット接続を確認するか、
"
            "https://ollama.com から手動でインストールしてください。",
            error=True,
        )
        return False

    try:
        result = subprocess.run(
            [installer, "/verysilent", "/norestart"],
            check=True,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        _show_message(
            "Ollama インストール失敗",
            f"Ollama のインストールに失敗しました（終了コード: {e.returncode}）。
"
            "https://ollama.com から手動でインストールしてください。",
            error=True,
        )
        return False
    except Exception as e:
        _show_message(
            "Ollama インストールエラー",
            f"インストール中にエラーが発生しました: {e}
"
            "https://ollama.com から手動でインストールしてください。",
            error=True,
        )
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)



def _start_ollama_service() -> bool:
    """Ollama サービスをバックグラウンドで起動し、疎通確認するまで待つ。
    
    起動に成功した場合 True を返す。
    """
    ollama_exe = shutil.which("ollama")
    if ollama_exe is None:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidate = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.isfile(candidate):
            ollama_exe = candidate

    if ollama_exe is None:
        return False

    try:
        # `ollama serve` を独立したプロセスとして起動
        subprocess.Popen(
            [ollama_exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:
        return False

    # 起動待ち（最大 30 秒）
    for _ in range(60):
        time.sleep(0.5)
        if _is_ollama_running():
            return True
    return False


def _ensure_ollama() -> None:
    """Ollama のインストール・起動を保証する。

    1. インストール済みかチェック → なければ同梱インストーラーで自動インストール
    2. 既に起動中かチェック → 起動していなければ `ollama serve` を呼ぶ
    3. いずれも失敗したらダイアログを出して続行（アプリ自体は起動させる）
    """
    if not _is_ollama_installed():
        success = _install_ollama()
        if not success:
            # インストール失敗でも続行（後で手動インストールしてもらう）
            return

    if _is_ollama_running():
        return  # 既に起動中

    started = _start_ollama_service()
    if not started:
        _show_message(
            "Ollama を起動できませんでした",
            "Ollama サービスの起動に失敗しました。\n"
            "Ollama が正しくインストールされているか確認するか、\n"
            "手動で Ollama を起動してからアプリを再起動してください。",
            error=True,
        )


def _show_message(title: str, message: str, error: bool = False) -> None:
    """Windows のメッセージボックス、または標準エラー出力にメッセージを表示する。"""
    try:
        import ctypes
        icon = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except Exception:
        stream = sys.stderr if error else sys.stdout
        if stream:
            stream.write(f"[{title}] {message}\n")


# ============================================================
# メイン
# ============================================================

def _fix_stdio() -> None:
    """PyInstaller 環境で stdout/stderr が None になる場合の対策。

    uvicorn の logging 設定が isatty() を呼ぶため、
    sys.stdout / sys.stderr が None だと AttributeError でクラッシュする。
    """
    import io
    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(
            open(os.devnull, "wb"), encoding="utf-8", errors="replace"
        )
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(
            open(os.devnull, "wb"), encoding="utf-8", errors="replace"
        )


def _resolve_db_path() -> str:
    """DBファイルの保存先をユーザーフォルダに返す。

    Program Files 以下は書き込み禁止のため
    %APPDATA%\\InterviewApp\\career_support.db に保存する。
    例: C:\\Users\\username\\AppData\\Roaming\\InterviewApp\\career_support.db
    """
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    db_dir = os.path.join(app_data, "InterviewApp")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "career_support.db")


def main() -> None:
    _fix_stdio()
    _cleanup_old_meipass()
    _kill_existing_process(BACKEND_PORT)

    # Ollama のインストール・起動を保証する
    _ensure_ollama()

    base = _base_path()

    # 環境変数でパスを通す
    os.environ.setdefault("INTERVIEW_STATIC_DIR", os.path.join(base, "frontend_dist"))
    os.environ.setdefault("PYTHONPATH", base)

    # DBをユーザーフォルダに保存（Program Files は書き込み禁止のため）
    os.environ.setdefault("INTERVIEW_DB_PATH", _resolve_db_path())

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
