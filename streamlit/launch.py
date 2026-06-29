import os
import sys
import glob
import shutil
import socket
import subprocess
import time
import streamlit.web.cli as stcli


# ============================================================
# 設定
# ============================================================
OLLAMA_HOST = "http://localhost:11434"


# ============================================================
# ユーティリティ
# ============================================================

def _base_path() -> str:
    """PyInstaller の一時展開先、または開発時のスクリプトディレクトリを返す。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _cleanup_old_meipass() -> None:
    """古いPyInstaller一時フォルダを削除する。"""
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


def _kill_existing_streamlit(port: int = 8501) -> None:
    """起動前に同じポートをLISTENしている既存プロセスを終了する。"""
    my_pid = os.getpid()
    killed = False

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
            killed = True

    except Exception:
        pass

    if killed:
        for _ in range(50):
            time.sleep(0.1)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    if s.connect_ex(("127.0.0.1", port)) != 0:
                        break
            except Exception:
                break


# ============================================================
# Ollama インストール確認・自動セットアップ
# ============================================================

def _is_ollama_installed() -> bool:
    """Ollama が PATH または既知のインストール先にあるか確認する。"""
    if shutil.which("ollama") is not None:
        return True
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    default_path = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
    return os.path.isfile(default_path)


def _is_ollama_running() -> bool:
    """Ollama の HTTP API に疎通できるか確認する。"""
    try:
        host = OLLAMA_HOST.replace("http://", "").replace("https://", "")
        hostname, _, port_str = host.partition(":")
        port = int(port_str) if port_str else 11434
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((hostname, port)) == 0
    except Exception:
        return False


def _show_message(title: str, message: str, error: bool = False) -> None:
    """Windows のメッセージボックスにメッセージを表示する。"""
    try:
        import ctypes
        icon = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except Exception:
        stream = sys.stderr if error else sys.stdout
        if stream:
            stream.write(f"[{title}] {message}\n")


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
    """ollama serve をバックグラウンドで起動し、疎通確認するまで待つ。"""
    ollama_exe = shutil.which("ollama")
    if ollama_exe is None:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidate = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.isfile(candidate):
            ollama_exe = candidate

    if ollama_exe is None:
        return False

    try:
        subprocess.Popen(
            [ollama_exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:
        return False

    for _ in range(60):
        time.sleep(0.5)
        if _is_ollama_running():
            return True
    return False


def _ensure_ollama() -> None:
    """Ollama のインストール・起動を保証する。

    1. 未インストールなら同梱インストーラーで自動インストール
    2. 未起動なら ollama serve を自動起動
    3. 失敗してもアプリ自体は起動させる（画面上で check_ollama.py がエラーを表示）
    """
    if not _is_ollama_installed():
        success = _install_ollama()
        if not success:
            return  # インストール失敗でも続行

    if _is_ollama_running():
        return

    started = _start_ollama_service()
    if not started:
        _show_message(
            "Ollama を起動できませんでした",
            "Ollama サービスの起動に失敗しました。\n"
            "Ollama が正しくインストールされているか確認するか、\n"
            "手動で Ollama を起動してからアプリを再起動してください。",
            error=True,
        )


# ============================================================
# メイン
# ============================================================

def main():
    _cleanup_old_meipass()
    _kill_existing_streamlit()

    # Ollama のインストール・起動を保証する
    _ensure_ollama()

    base_path = _base_path()
    app_path = os.path.join(base_path, "app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false"
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
