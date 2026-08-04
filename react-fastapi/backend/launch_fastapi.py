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

【2026-08 リファクタ】
Ollama自動インストール・ポート待受・ブラウザ起動・クラッシュログ等の
汎用ロジックは local_ai_core.launcher_kit に切り出した(gateway等の他の
ランチャーでも同じ処理が必要になったため)。このファイルには、
このアプリ固有のもの(SSE進捗配信・DBパス解決・起動シーケンス)だけを残す。
"""
from __future__ import annotations

import multiprocessing
import os
import queue
import sys
import threading

from local_ai_core import launcher_kit as lk

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
# FastAPIのSSEエンドポイント(api/routes/setup_progress.py)がここから
# メッセージを取り出して配信する。この3つの名前・型は
# setup_progress.py側の契約になっているため変更しないこと。
setup_progress_queue: queue.Queue[dict] = queue.Queue()
setup_done = threading.Event()   # セットアップ完了フラグ
setup_error = threading.Event()  # セットアップ失敗フラグ


def _push_to_setup_queue(message: str, level: str, group: str | None) -> None:
    """launcher_kit.log() から呼ばれ、SSE配信用キューに積む。"""
    import time
    setup_progress_queue.put({
        "level":   level,
        "message": message,
        "ts":      time.strftime("%H:%M:%S"),
        "group":   group,
    })


lk.set_log_handler(_push_to_setup_queue)


def _resolve_db_path() -> str:
    """DBファイルの保存先をユーザーフォルダに返す。"""
    app_data = os.environ.get("APPDATA") or os.path.expanduser("~")
    db_dir = os.path.join(app_data, "InterviewApp")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "career_support.db")


def _ensure_ollama_and_set_events() -> None:
    """launcher_kit.ensure_ollama() を呼び、結果をsetup_done/setup_errorに反映する。"""
    ok = lk.ensure_ollama(REQUIRED_MODELS, on_error=setup_error.set)
    if ok:
        setup_done.set()


# ============================================================
# メイン
# ============================================================

def main() -> None:
    lk.hide_console_window()
    lk.fix_stdio()
    lk.suppress_child_console()

    lk.log("=" * 60, "INFO")
    lk.log("Interview App (FastAPI) を起動しています", "INFO")
    lk.log("=" * 60, "INFO")

    lk.cleanup_old_meipass()
    lk.kill_existing_process(BACKEND_PORT)

    # アップデートチェック（EXE実行時のみ動作。新バージョンがあれば
    # ダウンロード後に再起動して終了する。失敗してもここで起動を止めない）
    try:
        from updater import check_and_update
        check_and_update()
    except Exception as e:
        lk.log(f"アップデートチェックに失敗しました: {e}", "WARNING")

    base = lk.base_path()

    os.environ.setdefault("INTERVIEW_STATIC_DIR", os.path.join(base, "frontend_dist"))
    os.environ.setdefault("PYTHONPATH", base)
    os.environ.setdefault("INTERVIEW_DB_PATH", _resolve_db_path())
    # setup_progress.py が「本当にlaunch_fastapi.py経由で起動されたか」を
    # 判定するためのフラグ。`uvicorn main:app` を直接起動した開発時は
    # このモジュール自体はimportできてしまうが、_ensure_ollama() が
    # 一切実行されず setup_done が永遠にセットされないため、
    # フロントエンドのセットアップ画面が終わらなくなる事故を防ぐ。
    # (main.py の service_auth も同じフラグを見て、単体exe起動時は
    # gatewayのCookie認証をスキップする)
    os.environ["LAUNCH_FASTAPI_ORCHESTRATED"] = "1"

    lk.log("FastAPI サーバーを起動中...", "INFO")
    lk.log("=" * 60, "INFO")

    import uvicorn

    # uvicorn をデーモンスレッドで起動し、ポートが開いてから
    # setup_thread を開始する。
    # こうすることで SSEエンドポイントが確実に存在する状態でセットアップログを
    # 配信でき、「起動直後にログが出ない」問題を防ぐ。
    def _run_uvicorn():
        try:
            uvicorn.run(
                "main:app",
                host="127.0.0.1",
                port=BACKEND_PORT,
                log_level="warning",
                loop="asyncio",   # ARM/PyInstaller 環境での子プロセス生成を防ぐ
            )
        except Exception as e:
            lk.write_crash_log("InterviewApp", "uvicorn_thread内で例外が発生しました", e)
            setup_error.set()

    uvicorn_thread = threading.Thread(target=_run_uvicorn, daemon=True)
    uvicorn_thread.start()

    # サーバーが実際にリスニングを開始するまで待つ
    if not lk.wait_for_port(BACKEND_PORT, timeout=30.0):
        lk.log("FastAPI サーバーの起動がタイムアウトしました", "ERROR")
        setup_error.set()
    else:
        # ポートが開いた = SSEエンドポイントが使える状態
        # → すぐにブラウザを開いてセットアップログをリアルタイムで見せる
        lk.open_browser(APP_URL, BACKEND_PORT, timeout=STARTUP_TIMEOUT)

        # Ollama セットアップをバックグラウンドスレッドで実行
        setup_thread = threading.Thread(target=_ensure_ollama_and_set_events, daemon=True)
        setup_thread.start()

    # メインスレッドを生かし続ける（uvicorn_thread が daemon なので
    # メインが終了するとサーバーも落ちる）
    uvicorn_thread.join()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            lk.fix_stdio()  # まだ呼ばれていない可能性があるので念のため
        except Exception:
            pass
        lk.write_crash_log("InterviewApp", "main()内で未処理の例外が発生しました(起動直後に終了)", e)
        raise
