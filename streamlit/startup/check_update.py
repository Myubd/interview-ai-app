"""
startup/check_update.py
-----------------------
アップデートチェックを実行する。
updater モジュールの check_and_update() を呼び出すだけの薄いラッパー。

updater は PyInstaller バンドル版にのみ含まれる場合があるため、
ImportError を黙って無視する設計にしている。
"""

import logging

logger = logging.getLogger(__name__)


def run_update_check() -> None:
    """アップデートチェックを実行する。updater が存在しない場合はスキップする。"""
    try:
        from updater import check_and_update
        check_and_update()
    except ImportError:
        logger.debug("updater モジュールが見つかりません。アップデートチェックをスキップします。")
