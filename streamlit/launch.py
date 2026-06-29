"""
streamlit/launch.py
--------------------
Streamlit版 Interview App のランチャー。（修正版）

【修正内容】
1. _get_ollama_exe() を共通ヘルパーとして追加
   → _get_installed_models() と _pull_model() もフルパスで呼ぶように統一
   → インストール直後PATHが通っていない場合でも動作する

2. _install_ollama() のインストール確認をリトライ付きに変更
   → インストール直後のファイル書き込みラグで誤判定しなくなる

3. _pull_model() を \\r 対応の1バイト読みに変更
   → ollama pull の進捗がコンソールにリアルタイム表示される
"""
import os
import sys
import glob
import shutil
import socket
import subprocess
import time
import streamlit.web.cli as stcli
import urllib.request
import tempfile


# ============================================================
# 設定
# ============================================================
OLLAMA_HOST = "http://localhost:11434"

# 自動インストール対象モデル
REQUIRED_MODELS = [
    "qwen3:8b",           # チャット用
    "nomic-embed-text",   # RAG用
]


# ============================================================
# ログ・進捗表示
# ============================================================

def _log(message: str, level: str = "INFO") -> None:
    """コンソールに色付きでメッセージを出力する。"""
    colors = {
        "INFO":    "\033[94m",
        "SUCCESS": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR":   "\033[91m",
    }
    reset = "\033[0m"
    color = colors.get(level, "\033[94m")
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {level:<8}{reset} {message}", flush=True)


def _format_bytes(bytes_size: int) -> str:
    """バイト数を人間が読みやすいフォーマットに変換する。"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


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
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
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
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
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
# Ollama パス解決（共通ヘルパー）  ← 修正1
# ============================================================

def _get_ollama_exe() -> str | None:
    """
    ollama の実行ファイルパスを返す。
    PATH → LOCALAPPDATA/Programs/Ollama/ の順で探す。
    見つからなければ None。
    """
    exe = shutil.which("ollama")
    if exe:
        return exe
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


# ============================================================
# Ollama インストール確認・自動セットアップ
# ============================================================

def _is_ollama_installed() -> bool:
    """Ollama が PATH または既知のインストール先にあるか確認する。"""
    return _get_ollama_exe() is not None


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


def _download_with_progress(url: str, filepath: str) -> bool:
    """ダウンロード進捗を表示しながらファイルをダウンロードする。"""
    try:
        _log("Ollama セットアップファイルをダウンロード中...", "INFO")

        class ProgressHook:
            def __init__(self):
                self.last_update = time.time()
                self.last_percent = -1

            def __call__(self, block_num, block_size, total_size):
                if total_size < 0:
                    _log(f"  ダウンロード中... {_format_bytes(block_num * block_size)}", "INFO")
                    return
                downloaded = min(block_num * block_size, total_size)
                percent = int(100 * downloaded / total_size)
                now = time.time()
                if percent != self.last_percent and (now - self.last_update > 0.5 or percent == 100):
                    bar_length = 30
                    filled = int(bar_length * percent / 100)
                    bar = "█" * filled + "░" * (bar_length - filled)
                    _log(
                        f"  {bar} {percent}% "
                        f"({_format_bytes(downloaded)} / {_format_bytes(total_size)})",
                        "INFO",
                    )
                    self.last_update = now
                    self.last_percent = percent

        urllib.request.urlretrieve(url, filepath, ProgressHook())
        _log("ダウンロード完了", "SUCCESS")
        return True
    except Exception as e:
        _log(f"ダウンロード失敗: {e}", "ERROR")
        return False


def _show_message(title: str, message: str, error: bool = False) -> None:
    """Windows のメッセージボックスにメッセージを表示する（フォールバック付き）。"""
    try:
        import ctypes
        icon = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except Exception:
        level = "ERROR" if error else "INFO"
        _log(f"[{title}] {message}", level)


def _install_ollama() -> bool:
    """Ollama を公式サイトからダウンロードしてサイレントインストールする。"""
    OLLAMA_DOWNLOAD_URL = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"

    _log("=" * 60, "INFO")
    _log("Ollama のインストールを開始します", "WARNING")
    _log("=" * 60, "INFO")

    tmp_dir = tempfile.mkdtemp()
    installer = os.path.join(tmp_dir, "OllamaSetup.exe")

    _log("[1/3] ダウンロード", "INFO")
    if not _download_with_progress(OLLAMA_DOWNLOAD_URL, installer):
        _show_message(
            "Ollama ダウンロード失敗",
            "Ollama のダウンロードに失敗しました。\n"
            "インターネット接続を確認してください。\n\n"
            "手動でインストール: https://ollama.com",
            error=True,
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    _log("[2/3] Ollama をインストール中...", "INFO")
    _log("  （インストールウィンドウが表示される場合があります）", "INFO")

    try:
        result = subprocess.run(
            [installer, "/verysilent", "/norestart"],
            check=True,
            timeout=300,
        )
        if result.returncode == 0:
            _log("Ollama インストール完了", "SUCCESS")
        else:
            _log(f"インストール終了コード: {result.returncode}", "WARNING")
            return False
    except subprocess.TimeoutExpired:
        _log("インストール処理がタイムアウトしました", "ERROR")
        _show_message("Ollama インストール失敗", "インストール処理がタイムアウトしました。\n手動でインストール: https://ollama.com", error=True)
        return False
    except subprocess.CalledProcessError as e:
        _log(f"インストール失敗（終了コード: {e.returncode}）", "ERROR")
        _show_message("Ollama インストール失敗", f"インストールに失敗しました（終了コード: {e.returncode}）。\n手動でインストール: https://ollama.com", error=True)
        return False
    except Exception as e:
        _log(f"インストール中にエラー: {e}", "ERROR")
        _show_message("Ollama インストールエラー", f"エラー: {e}\n手動でインストール: https://ollama.com", error=True)
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # 修正2: インストール直後のファイル書き込みラグに対応してリトライ
    _log("[3/3] インストール確認中...", "INFO")
    for _ in range(10):
        time.sleep(1.0)
        if _is_ollama_installed():
            _log("Ollama のインストールが確認できました", "SUCCESS")
            _log("=" * 60, "INFO")
            return True

    _log("Ollama がインストールされていません（確認タイムアウト）", "ERROR")
    return False


def _start_ollama_service() -> bool:
    """Ollama サービスをバックグラウンドで起動し、疎通確認するまで待つ。"""
    _log("Ollama サービスを起動中...", "INFO")

    ollama_exe = _get_ollama_exe()  # 修正1: 共通ヘルパーを使用
    if ollama_exe is None:
        _log("Ollama の実行ファイルが見つかりません", "ERROR")
        return False

    try:
        subprocess.Popen(
            [ollama_exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        _log("Ollama プロセスを起動しました", "INFO")
    except Exception as e:
        _log(f"Ollama プロセスの起動に失敗: {e}", "ERROR")
        return False

    _log("Ollama が応答するまで待機中...", "INFO")
    for i in range(60):
        time.sleep(0.5)
        if _is_ollama_running():
            elapsed = (i + 1) * 0.5
            _log(f"Ollama が起動しました（{elapsed:.1f}秒）", "SUCCESS")
            return True
        if (i + 1) % 20 == 0:
            _log(f"  待機中... {(i + 1) * 0.5:.0f}秒経過", "INFO")

    _log("Ollama が起動できませんでした（タイムアウト）", "ERROR")
    return False


# ============================================================
# モデルの確認・自動インストール
# ============================================================

def _get_installed_models() -> list[str]:
    """Ollama にインストール済みのモデル一覧を取得する。"""
    ollama_exe = _get_ollama_exe()  # 修正1: コマンド名直書きをやめてフルパスで呼ぶ
    if ollama_exe is None:
        _log("ollama コマンドが見つかりません（モデル一覧取得スキップ）", "WARNING")
        return []
    try:
        result = subprocess.run(
            [ollama_exe, "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        models = []
        for line in result.stdout.splitlines()[1:]:  # ヘッダーをスキップ
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception as e:
        _log(f"モデル一覧の取得に失敗: {e}", "WARNING")
        return []


def _pull_model(model_name: str) -> bool:
    """
    Ollama でモデルをダウンロードする。
    修正3: ollama pull は \\r で進捗を上書きするため、1バイトずつ読んで行を組み立てる。
    """
    ollama_exe = _get_ollama_exe()  # 修正1: フルパスで呼ぶ
    if ollama_exe is None:
        _log(f"✗ ollama コマンドが見つかりません（{model_name} スキップ）", "ERROR")
        return False

    _log(f"モデル '{model_name}' をダウンロード中...", "INFO")

    try:
        process = subprocess.Popen(
            [ollama_exe, "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # テキストモードにせず bytes で受け取り、自前でデコードする
        )

        buf = bytearray()
        last_logged_percent = -1

        while True:
            ch = process.stdout.read(1)
            if not ch:
                if buf.strip():
                    _log(f"  {buf.decode('utf-8', errors='replace').strip()}", "INFO")
                break

            if ch in (b"\n", b"\r"):
                line = buf.decode("utf-8", errors="replace").strip()
                buf.clear()
                if not line:
                    continue
                if "%" in line:
                    try:
                        pct_str = [t for t in line.split() if t.endswith("%")]
                        pct = int(pct_str[0].rstrip("%")) if pct_str else -1
                    except Exception:
                        pct = -1
                    # 5% 刻み or 100% だけログに出す
                    if pct == 100 or (pct >= 0 and pct // 5 != last_logged_percent // 5):
                        _log(f"  {line}", "INFO")
                        last_logged_percent = pct
                else:
                    _log(f"  {line}", "INFO")
            else:
                buf.extend(ch)

        process.wait(timeout=3600)

        if process.returncode == 0:
            _log(f"✓ モデル '{model_name}' のダウンロード完了", "SUCCESS")
            return True
        else:
            _log(f"✗ モデル '{model_name}' のダウンロード失敗（コード: {process.returncode}）", "ERROR")
            return False

    except subprocess.TimeoutExpired:
        _log(f"✗ モデル '{model_name}' のダウンロードがタイムアウト", "ERROR")
        return False
    except Exception as e:
        _log(f"✗ モデル '{model_name}' のダウンロード中にエラー: {e}", "ERROR")
        return False


def _ensure_models() -> None:
    """必要なモデルがインストール済みか確認し、不足していればダウンロードする。"""
    _log("=" * 60, "INFO")
    _log("必要なモデルを確認しています", "INFO")
    _log("=" * 60, "INFO")

    installed_models = _get_installed_models()
    _log(f"インストール済みモデル: {', '.join(installed_models) if installed_models else 'なし'}", "INFO")

    models_to_download = []
    for model in REQUIRED_MODELS:
        base_name = model.split(":")[0]
        is_installed = any(base_name in m for m in installed_models)
        if is_installed:
            _log(f"✓ モデル '{model}' は既にインストール済み", "SUCCESS")
        else:
            _log(f"✗ モデル '{model}' がインストールされていません", "WARNING")
            models_to_download.append(model)

    if models_to_download:
        _log("", "INFO")
        _log(f"{len(models_to_download)} 個のモデルをダウンロード開始...", "WARNING")
        _log("  （数GB のダウンロードのため、数分～十数分かかります）", "INFO")
        _log("", "INFO")
        for i, model in enumerate(models_to_download, 1):
            _log(f"[{i}/{len(models_to_download)}] {model}", "INFO")
            success = _pull_model(model)
            if not success:
                _log(f"⚠️  モデル '{model}' のダウンロードに失敗しました", "WARNING")
                _log(f"   手動でダウンロード: ollama pull {model}", "INFO")
            _log("", "INFO")
        _log("=" * 60, "INFO")
    else:
        _log("✓ すべての必要なモデルがインストール済みです", "SUCCESS")
        _log("=" * 60, "INFO")


def _ensure_ollama() -> None:
    """Ollama のインストール・起動・モデル準備を保証する。"""
    if _is_ollama_installed():
        _log("✓ Ollama はインストール済みです", "SUCCESS")
    else:
        _log("✗ Ollama がインストールされていません", "WARNING")
        success = _install_ollama()
        if not success:
            _log("Ollama のインストールに失敗しました（続行）", "WARNING")
            return

    if _is_ollama_running():
        _log("✓ Ollama は既に起動しています", "SUCCESS")
    else:
        _log("✗ Ollama が起動していません", "WARNING")
        started = _start_ollama_service()
        if not started:
            _show_message(
                "Ollama 起動エラー",
                "Ollama サービスの起動に失敗しました。\n"
                "Ollama が正しくインストールされているか確認するか、\n"
                "手動で Ollama を起動してからアプリを再起動してください。",
                error=True,
            )
            return

    _ensure_models()


# ============================================================
# メイン
# ============================================================

def main():
    _log("=" * 60, "INFO")
    _log("Interview App を起動しています", "INFO")
    _log("=" * 60, "INFO")

    _cleanup_old_meipass()
    _kill_existing_streamlit()

    # Ollama のインストール・起動・モデル準備を保証する
    _ensure_ollama()

    base_path = _base_path()
    app_path = os.path.join(base_path, "app.py")

    _log("Streamlit を起動中...", "INFO")
    _log("=" * 60, "INFO")

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
