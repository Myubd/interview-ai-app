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
    0. shared/ を sys.path の末尾に追加（フォールバック用、最優先ではない）
    1. configure_page()        - st.set_page_config は最初の st.* 呼び出しでなければならない
    2. init_logging()          - 早期にロギングを設定する
    3. init_db()               - DB スキーマ確保
    4. run_update_check()      - アップデート確認
    5. ensure_ollama_running() - Ollama 未起動なら st.stop()
"""

# ============================================================
# shared/ ブートストラップ（他のどの import よりも先に実行する）
# ------------------------------------------------------------
# industry_engine / persona_engine / mock_interview_engine /
# answer_assist / prompts パッケージは shared/ に一本化されており、
# streamlit/ 側には物理コピーを置かない。
# shared/ を sys.path の末尾に「追加」することで、streamlit/ 側に
# 存在しないモジュール（上記5つ）だけが shared/ にフォールバックする。
#
# 注意: 先頭に insert してはいけない。shared/ には db/・rag/ も
# 参考として存在するが、これらは Python のパッケージ相対 import
# （`from db.database import ...` 等）の都合上アプリ固有の兄弟
# モジュール（database.py の DB パス解決、rag/core.py の埋め込み
# 実装）と同一ディレクトリに存在する必要があるため、streamlit/db/・
# streamlit/rag/ に物理コピーを維持している。shared/ を先頭に挿入
# すると db・rag の名前解決が shared/ 側に奪われ、DB保存先が
# 意図せず変わる等の事故につながるため、必ず streamlit/ 側の解決を
# 優先させる（= shared/ は末尾に追加してフォールバック専用にする）。
# 詳細は shared/MIGRATION_GUIDE.md を参照。
# ============================================================
import sys as _sys
from pathlib import Path as _Path

_SHARED_DIR = _Path(__file__).resolve().parent.parent / "shared"
if str(_SHARED_DIR) not in _sys.path:
    _sys.path.append(str(_SHARED_DIR))

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
