import startup

# ============================================================
# 起動フェーズ（ページ設定・DB初期化・Ollama確認 等）
# ============================================================
startup.run()

# ============================================================
# アプリ本体の import（起動フェーズ完了後に行う）
# ============================================================
import streamlit as st

from components.sidebar import render_sidebar
from page_modules.mock_interview import render as render_mock_interview
from page_modules.predict_questions_page import render_predict_questions
from page_modules.history_page import render_history
from page_modules.dashboard_page import render as render_dashboard
from page_modules.interview import render as render_interview
from state.initializer import init_session_state

# ============================================================
# セッション状態の初期化（全グループ一括）
# ============================================================
init_session_state()

# ============================================================
# サイドバー描画（model_name を取得）
# ============================================================
model_name = render_sidebar()

# ============================================================
# ページルーティング
# ============================================================
mode = st.session_state.app_mode

if mode == "mock_interview":
    render_mock_interview(model_name)
    st.stop()

if mode == "predict_questions":
    render_predict_questions(model_name)
    st.stop()

if mode == "history":
    render_history()
    st.stop()

if mode == "dashboard":
    render_dashboard()
    st.stop()

# デフォルト: interview
render_interview(model_name)
