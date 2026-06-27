"""
startup/__init__.py
-------------------
アプリ起動時の初期化処理をまとめるパッケージ。

app.py からは `import startup; startup.run()` と呼び出すだけでよい。

サブモジュール:
    page_config   - ページ設定・CSS/JS 注入
    check_ollama  - Ollama 接続確認
    check_update  - アップデートチェック

呼び出し順（順序が重要）:
    1. configure_page()        - st.set_page_config は最初の st.* 呼び出しでなければならない
    2. init_logging()          - 早期にロギングを設定する
    3. init_db()               - DB スキーマ確保
    4. run_update_check()      - アップデート確認
    5. ensure_ollama_running() - Ollama 未起動なら st.stop()
"""

import logging

from startup.page_config import configure_page
from startup.check_ollama import ensure_ollama_running
from startup.check_update import run_update_check


def _init_logging() -> None:
    """アプリ全体のロギング設定を行う。"""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run() -> None:
    """起動フェーズのすべての初期化処理を順番に実行する。

    app.py の先頭で一度だけ呼び出す。
    """
    from db.database import init_db  # 循環 import 回避のためここで import

    configure_page()           # 1. ページ設定・CSS/JS（st.set_page_config を含む）
    _init_logging()            # 2. ロギング設定
    init_db()                  # 3. DB 初期化
    run_update_check()         # 4. アップデートチェック
    ensure_ollama_running()    # 5. Ollama 起動確認（失敗時は st.stop()）


__all__ = ["run", "configure_page", "ensure_ollama_running", "run_update_check"]
