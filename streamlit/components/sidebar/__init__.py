"""
components/sidebar/__init__.py
--------------------------------
サイドバーパッケージ。外部からは render_sidebar() だけを使う。

サブモジュール構成:
    navigation.py   - バージョン情報・警告バナー・ナビゲーションボタン
    settings.py     - モデル設定パネル
    rag_panel.py    - 履歴書・企業情報アップロード・読み込みパネル
    session_panel.py - セッション保存・バックアップ・リセットパネル
"""

import streamlit as st

from components.sidebar.navigation import (
    render_version_info,
    render_warning_banner,
    render_navigation,
)
from components.sidebar.settings import render_settings
from components.sidebar.rag_panel import render_rag_panel
from components.sidebar.session_panel import render_session_panel


def render_sidebar() -> str:
    """サイドバーを描画し、選択されたモデル名を返す。

    ナビゲーションのクリックは st.session_state.app_mode を直接書き換える。
    """
    with st.sidebar:
        render_version_info()
        render_warning_banner()
        render_navigation()
        st.write("---")
        model_name = render_settings()
        st.write("---")
        render_rag_panel()
        render_session_panel(model_name)

    return model_name


__all__ = ["render_sidebar"]
