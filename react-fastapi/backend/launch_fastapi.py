"""
launch_fastapi.py
------------------
FastAPI版 Interview App のランチャー。

PyInstaller でビルドされた exe から実行されることを想定。
- Ollama のインストール確認・自動インストール
- Ollama モデルの自動ダウンロード（リアルタイム進捗をSSEで配信）
- uvicorn でバックエンド（FastAPI）を起動
- フロントエンド（React ビルド済み静的ファイル）をバックエンド経由で配信
- 起動後にブラウザを自動で開く
"""
from __future__ import annotations

import io
import os
import re
import glob
import json
import multiprocessing
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
import urllib.request
import tempfile

# ollama pull が出力する ANSI エスケープシーケンス（カーソル制御・
# 代替スクリーンモード切替・スピナーの色/移動コードなど）を除去するための
# 正規表現。例: "\x1b[?2026h", "\x1b[1G", "\x1b[K", "\x1b[A" など。
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """ANSI エスケープシーケンスと制御文字をテキストから取り除く。"""
    text = _ANSI_ESCAPE_RE.sub("", text)
    # スピナーの回転に使われる Braille 文字（⠋⠙⠹...）や残った制御文字も除去
    text = re.sub(r"[\u2800-\u28FF]", "", text)
    text = text.replace("\x1b", "")
    return text.strip()

# ============================================================
# モジュール多重ロード対策
# ============================================================
# このファイルが exe / `python launch_fastapi.py` のように直接実行されると
# Python はこれを "__main__" としてロードする。
# 一方 api/routes/setup_progress.py は `import launch_fastapi` をしており、
# これは "__main__" とは別の新しいモジュールインスタンスとして
# 再評価されてしまう（setup_progress_queue / setup_done / setup_error が
# 二重に存在してしまい、SSE 側が空のキューと未セットのEventを永遠に
# 読み続けてしまう＝セットアップ画面が無限ループする原因）。
#
# そこで "__main__" として実行された場合は、自分自身を
# sys.modules["launch_fastapi"] にも登録しておくことで、
# 後続の `import launch_fastapi` が同一インスタンスを参照するようにする。
if __name__ == "__main__":
    # ============================================================
    # PyInstaller + multiprocessing 対策（ARM / Windows 共通）
    # ============================================================
    # PyInstaller でビルドした exe を Windows/ARM 上で起動すると、
    # multiprocessing がサブプロセスを "spawn" モードで生成しようとして
    # exe 自体を再起動してしまう。その余計な子プロセスが
    # コンソールウィンドウやプロンプトとして画面に現れる原因になる。
    # freeze_support() を最初に呼ぶことでこの多重起動を防ぐ。
    multiprocessing.freeze_support()

    # ============================================================
    # モジュール多重ロード対策
    # ============================================================
    sys.modules.setdefault("launch_fastapi", sys.modules["__main__"])


# ============================================================
# 設定
# ============================================================
BACKEND_PORT = 8000
FRONTEND_PORT = 8000
APP_URL = f"http://localhost:{BACKEND_PORT}"
STARTUP_TIMEOUT = 30

OLLAMA_HOST = "http://localhost:11434"

# 自動インストール対象モデル
REQUIRED_MODELS = [
    "qwen3:8b",           # チャット用
    "nomic-embed-text",   # RAG用
]

# ============================================================
# グローバル進捗キュー（SSE配信用）
# ============================================================
# setup_progress_queue はセットアップの進捗メッセージを格納する。
# FastAPIのSSEエンドポイントがここからメッセージを取り出して配信する。
setup_progress_queue: queue.Queue[dict] = queue.Queue()
setup_done = threading.Event()   # セットアップ完了フラグ
setup_error = threading.Event()  # セットアップ失敗フラグ


# ============================================================
# ログ・進捗表示
# ============================================================

def _log(message: str, level: str = "INFO", group: str | None = None) -> None:
    """コンソールに色付きでメッセージを出力し、SSEキューにも積む。

    group を指定すると、フロントエンド側では「同じ group の前回行を
    新しい内容で上書き」する（ダウンロード進捗バーなどを縦に積み上げず、
    1行を更新し続ける表示にするため）。group が None の通常ログは
    常に新しい行として追加される。
    """
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

    # SSEキューへ積む（フロントエンドに配信される）
    setup_progress_queue.put({
        "level":   level,
        "message": message,
        "ts":      timestamp,
        "group":   group,
    })


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
    """サーバーが起動するまで待つ。"""
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
        _log(f"ブラウザを開いています: {APP_URL}", "INFO")
        webbrowser.open(APP_URL)


# ============================================================
# Ollama パス解決（共通ヘルパー）
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
    """Ollama が PATH または既定インストール先に存在するか確認する。"""
    return _get_ollama_exe() is not None


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


def _download_with_progress(url: str, filepath: str) -> bool:
    """ダウンロード進捗を表示しながらファイルをダウンロードする。

    PyInstaller 環境では certifi の証明書バンドルが同梱されないため、
    SSL コンテキストを明示的に作成して対応する。
    """
    import ssl
    import urllib.request

    try:
        _log("Ollama セットアップファイルをダウンロード中...", "INFO")

        # PyInstaller 環境での SSL 証明書エラー対策
        # 1) certifi が使えれば使う
        # 2) なければ OS の証明書ストアを使う
        # 3) それも無理なら検証をスキップ（最終手段）
        ctx: ssl.SSLContext | None = None
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
            _log("  SSL: certifi 証明書を使用", "INFO")
        except ImportError:
            try:
                ctx = ssl.create_default_context()
                _log("  SSL: OS 証明書ストアを使用", "INFO")
            except Exception:
                ctx = ssl._create_unverified_context()
                _log("  SSL: 証明書検証をスキップ（フォールバック）", "WARNING")

        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)

        last_update = time.time()
        last_percent = -1

        def _progress(block_num: int, block_size: int, total_size: int) -> None:
            nonlocal last_update, last_percent
            if total_size <= 0:
                _log(
                    f"  ダウンロード中... {_format_bytes(block_num * block_size)}",
                    "INFO",
                    group="ollama_installer_download",
                )
                return
            downloaded = min(block_num * block_size, total_size)
            percent = int(100 * downloaded / total_size)
            now = time.time()
            if percent != last_percent and (now - last_update > 0.5 or percent == 100):
                bar_length = 30
                filled = int(bar_length * percent / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                _log(
                    f"  {bar} {percent}% "
                    f"({_format_bytes(downloaded)} / {_format_bytes(total_size)})",
                    "INFO",
                    group="ollama_installer_download",
                )
                last_update = now
                last_percent = percent

        urllib.request.urlretrieve(url, filepath, _progress)
        _log("ダウンロード完了", "SUCCESS")
        return True

    except Exception as e:
        _log(f"ダウンロード失敗: {e}", "ERROR")
        return False


def _show_message(title: str, message: str, error: bool = False) -> None:
    """Windows のメッセージボックス、または標準エラー出力にメッセージを表示する。"""
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

    # インストール中の経過時間をリアルタイム表示するスレッド
    _install_done = threading.Event()
    def _show_install_progress() -> None:
        start = time.time()
        max_sec = 300  # タイムアウトと合わせる
        while not _install_done.wait(timeout=2.0):
            elapsed = int(time.time() - start)
            ratio = min(elapsed / max_sec, 1.0)
            bar_len = 30
            filled = int(bar_len * ratio)
            bar = "█" * filled + "░" * (bar_len - filled)
            m, s = divmod(elapsed, 60)
            _log(
                f"  {bar} インストール中... {m}分{s:02d}秒経過",
                "INFO",
                group="ollama_install_progress",
            )
    progress_thread = threading.Thread(target=_show_install_progress, daemon=True)
    progress_thread.start()

    try:
        result = subprocess.run(
            [installer, "/verysilent", "/norestart"],
            check=False,
            timeout=300,
        )
        _install_done.set()
        progress_thread.join(timeout=3)
        # 0 = 成功, 3010 = 成功（再起動推奨）
        if result.returncode not in (0, 3010):
            _log(f"インストール失敗（終了コード: {result.returncode}）", "ERROR")
            return False
        _log("Ollama インストール完了", "SUCCESS")

    except subprocess.TimeoutExpired:
        _install_done.set()
        _log("インストール処理がタイムアウトしました", "ERROR")
        return False
    except subprocess.CalledProcessError as e:
        _install_done.set()
        _log(f"インストール失敗（終了コード: {e.returncode}）", "ERROR")
        return False
    except Exception as e:
        _install_done.set()
        _log(f"インストール中にエラー: {e}", "ERROR")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    _log("[3/3] インストール確認中...", "INFO")
    # インストール直後はファイルが書き終わるまで少しかかるためリトライする
    max_checks = 10
    for i in range(max_checks):
        time.sleep(1.0)
        filled = int(30 * (i + 1) / max_checks)
        bar = "█" * filled + "░" * (30 - filled)
        _log(
            f"  {bar} 確認中 {i + 1}/{max_checks}",
            "INFO",
            group="ollama_verify_progress",
        )
        if _is_ollama_installed():
            _log("Ollama のインストールが確認できました", "SUCCESS")
            _log("=" * 60, "INFO")
            return True

    _log("Ollama がインストールされていません（確認タイムアウト）", "ERROR")
    return False


def _start_ollama_service() -> bool:
    """Ollama サービスをバックグラウンドで起動し、疎通確認するまで待つ。"""
    _log("Ollama サービスを起動中...", "INFO")

    ollama_exe = _get_ollama_exe()
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
    ollama_exe = _get_ollama_exe()
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
        for line in result.stdout.splitlines()[1:]:
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
    ollama pull は \\r で進捗を上書きするため、1バイトずつ読んで行を組み立てる。
    """
    ollama_exe = _get_ollama_exe()
    if ollama_exe is None:
        _log(f"✗ ollama コマンドが見つかりません（{model_name} スキップ）", "ERROR")
        return False

    _log(f"モデル '{model_name}' をダウンロード中...", "INFO")

    try:
        # Windows では ollama.exe（コンソールアプリ）を起動すると
        # 新しいコンソールウィンドウが自動生成される。
        # STARTF_USESHOWWINDOW + SW_MINIMIZE で最小化状態で起動し、
        # ユーザーが誤って閉じてダウンロードが中断されないようにする。
        # （×で閉じるとプロセスが終了してダウンロード失敗になるため）
        if sys.platform == "win32":
            _si = subprocess.STARTUPINFO()
            _si.dwFlags = subprocess.STARTF_USESHOWWINDOW
            _si.wShowWindow = 6  # SW_MINIMIZE
            _startupinfo = _si
        else:
            _startupinfo = None

        process = subprocess.Popen(
            [ollama_exe, "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=_startupinfo,
            # テキストモードにせず bytes で受け取り、自前でデコードする
        )

        buf = bytearray()
        last_logged_percent = -1
        last_plain_line = ""  # 進捗%を含まない行（"pulling manifest" 等）の重複抑制用

        def _emit(raw_line: str) -> None:
            nonlocal last_logged_percent, last_plain_line

            line = _strip_ansi(raw_line)
            if not line:
                return

            # 進捗行（% を含む）は間引いて表示
            if "%" in line:
                # "pulling xxx... 45% ▕████░░░░▏ 2.1 GB/4.7 GB" のような行
                try:
                    pct_str = [t for t in line.split() if t.endswith("%")]
                    pct = int(pct_str[0].rstrip("%")) if pct_str else -1
                except Exception:
                    pct = -1
                # 5% 刻み or 100% だけログに出す
                if pct == 100 or (pct >= 0 and pct // 5 != last_logged_percent // 5):
                    _log(f"  {line}", "INFO", group=f"pull:{model_name}")
                    last_logged_percent = pct
            else:
                # スピナーのフレーム違いだけで内容が同じ行（"pulling manifest" 等）は
                # 連投しない
                if line == last_plain_line:
                    return
                last_plain_line = line
                _log(f"  {line}", "INFO")

        while True:
            ch = process.stdout.read(1)
            if not ch:
                # EOF — バッファに残っている分を出力
                if buf.strip():
                    _emit(buf.decode("utf-8", errors="replace"))
                break

            if ch == b"\n":
                # \n のみを「行確定」として扱う
                raw_line = buf.decode("utf-8", errors="replace")
                buf.clear()
                _emit(raw_line)
            elif ch == b"\r":
                # \r はターミナルの「カーソルを行頭に戻して上書き」を意味する。
                # ここではバッファを破棄（次の内容で上書きされる想定）することで
                # "pulling manifest pulling manifest ..." の横並びを防ぐ。
                buf.clear()
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
            setup_error.set()
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
            setup_error.set()
            return

    _ensure_models()
    setup_done.set()


# ============================================================
# メイン
# ============================================================

def _fix_stdio() -> None:
    """PyInstaller 環境で stdout/stderr が None になる場合の対策。"""
    if sys.stdout is None:
        sys.stdout = io.TextIOWrapper(
            open(os.devnull, "wb"), encoding="utf-8", errors="replace"
        )
    if sys.stderr is None:
        sys.stderr = io.TextIOWrapper(
            open(os.devnull, "wb"), encoding="utf-8", errors="replace"
        )


def _suppress_child_console() -> None:
    """Windows で子プロセスにコンソールウィンドウが出ないようにする。

    PyInstaller の console=False exe は自分自身はコンソールなしで起動するが、
    内部で subprocess.Popen を呼ぶ際にデフォルトの creationflags が引き継がれず
    余分なウィンドウが表示されることがある。
    subprocess のデフォルト startupinfo を上書きして常に非表示にする。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # STARTF_USESHOWWINDOW = 1, SW_HIDE = 0
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        # subprocess.Popen のデフォルト startupinfo を差し替える
        # （Python 内部の _winapi 経由で全 Popen に適用）
        subprocess._default_startupinfo = startupinfo  # type: ignore[attr-defined]
    except Exception:
        pass  # 失敗しても動作に影響なし


def _resolve_db_path() -> str:
    """DBファイルの保存先をユーザーフォルダに返す。"""
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    db_dir = os.path.join(app_data, "InterviewApp")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "career_support.db")


def _wait_for_port(port: int, timeout: float = 30.0) -> bool:
    """ポートが Listen 状態になるまで待つ。timeout 秒以内に開けば True を返す。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main() -> None:
    _fix_stdio()
    _suppress_child_console()

    _log("=" * 60, "INFO")
    _log("Interview App (FastAPI) を起動しています", "INFO")
    _log("=" * 60, "INFO")

    _cleanup_old_meipass()
    _kill_existing_process(BACKEND_PORT)

    # アップデートチェック（EXE実行時のみ動作。新バージョンがあれば
    # ダウンロード後に再起動して終了する。失敗してもここで起動を止めない）
    try:
        from updater import check_and_update
        check_and_update()
    except Exception as e:
        _log(f"アップデートチェックに失敗しました: {e}", "WARNING")

    base = _base_path()

    os.environ.setdefault("INTERVIEW_STATIC_DIR", os.path.join(base, "frontend_dist"))
    os.environ.setdefault("PYTHONPATH", base)
    os.environ.setdefault("INTERVIEW_DB_PATH", _resolve_db_path())

    _log("FastAPI サーバーを起動中...", "INFO")
    _log("=" * 60, "INFO")

    import uvicorn

    # uvicorn をデーモンスレッドで起動し、ポートが開いてから
    # setup_thread を開始する。
    # こうすることで SSEエンドポイントが確実に存在する状態でセットアップログを
    # 配信でき、「起動直後にログが出ない」問題を防ぐ。
    uvicorn_thread = threading.Thread(
        target=lambda: uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=BACKEND_PORT,
            log_level="warning",
            loop="asyncio",   # ARM/PyInstaller 環境での子プロセス生成を防ぐ
        ),
        daemon=True,
    )
    uvicorn_thread.start()

    # サーバーが実際にリスニングを開始するまで待つ
    if not _wait_for_port(BACKEND_PORT, timeout=30.0):
        _log("FastAPI サーバーの起動がタイムアウトしました", "ERROR")
        setup_error.set()
    else:
        # ポートが開いた = SSEエンドポイントが使える状態
        # → すぐにブラウザを開いてセットアップログをリアルタイムで見せる
        _open_browser()

        # Ollama セットアップをバックグラウンドスレッドで実行
        setup_thread = threading.Thread(target=_ensure_ollama, daemon=True)
        setup_thread.start()

    # メインスレッドを生かし続ける（uvicorn_thread が daemon なので
    # メインが終了するとサーバーも落ちる）
    uvicorn_thread.join()


if __name__ == "__main__":
    main()
