"""
components/sidebar/navigation.py
---------------------------------
サイドバーのバージョン表示・警告バナー・ナビゲーションボタンを描画する。

[変更点]
- ダッシュボードページへのナビゲーション項目を追加。
"""

import streamlit as st

from utils import APP_VERSION
from updater import fetch_latest_version


def render_version_info() -> None:
    """バージョン情報と最新バージョンの有無を表示する。"""
    current = APP_VERSION
    if not current or current == "dev":
        st.caption("🔖 バージョン: dev（開発環境）")
        return
    latest, fetch_err = fetch_latest_version()
    if fetch_err or not latest:
        st.caption(f"🔖 現在のバージョン: {current}")
        return
    current_base = current.split("+")[0].lstrip("v")
    latest_base = latest.lstrip("v")
    if current_base == latest_base:
        st.caption(f"🔖 バージョン: {current}　✅ 最新")
    else:
        st.caption(f"🔖 現在: {current}")
        st.caption(f"🆕 最新バージョン: {latest} が利用可能です")


def render_warning_banner() -> None:
    """自動翻訳機能に関する注意書きを表示する。"""
    st.markdown(
        "━━━━━━━━━━━━━━━━  \n"
        "⚠️ **ご利用上の注意**  \n"
        "ブラウザの自動翻訳機能をご利用の場合、文字表示やAIの応答に問題が発生する場合があります。"
        "翻訳をオフにするか「原文を表示」でご利用ください。  \n"
        "━━━━━━━━━━━━━━━━"
    )


def render_navigation() -> None:
    """ページ切り替えナビゲーションボタンを描画する。"""
    st.subheader("サイドバー")

    _nav_items = [
        ("📄", "自己PR作成",          "interview"),
        ("🎯", "想定質問生成",          "predict_questions"),
        ("🎤", "AI模擬面接",           "mock_interview"),
        ("📈", "ダッシュボード",        "dashboard"),
        ("✅", "面接履歴",             "history"),
    ]
    for _icon, _label, _mode in _nav_items:
        _is_current = st.session_state.app_mode == _mode
        _button_label = f"{_icon} {_label}" + ("　◀" if _is_current else "")
        if st.button(
            _button_label,
            key=f"nav_{_mode}",
            use_container_width=True,
            type="primary" if _is_current else "secondary",
        ):
            if _mode == "mock_interview":
                st.session_state.app_mode = "mock_interview"
                st.session_state.mock_messages = []
                st.session_state.mock_theme_index = 0
                st.session_state.mock_theme_messages = []
                st.session_state.mock_followups_asked = 0
                st.session_state.mock_started = False
                st.session_state.mock_complete = False
                st.session_state.mock_used_predicted_indices = set()
                st.session_state.mock_evaluation = None
                st.session_state.mock_evaluation_error = None
                st.session_state.mock_is_generating = False
                st.session_state.mock_answer_reviews = {}
                st.session_state.mock_review_generating_for = None
                st.session_state.mock_persona_confirmed = False
                # ペルソナはリセットせず前回の選択を引き継ぐ
            else:
                st.session_state.app_mode = _mode
            st.rerun()
