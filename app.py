import logging

import ollama
import streamlit as st

from db.database import init_db
from rag import Document

# ページ分割したモジュール
from components.sidebar import render_sidebar
from page_modules.career_page import render as render_career
from page_modules.personality_page import render as render_personality
from page_modules.mock_interview import render as render_mock_interview
from page_modules.company_matrix_page import render_company_matrix
from page_modules.predict_questions_page import render_predict_questions
from page_modules.history_page import render_history
from page_modules.interview import render as render_interview, build_conversation_history

#  共通化した初期化ユーティリティ
from state.initializer import init_session_state

# ============================================================
# 基本設定
# ============================================================
st.set_page_config(page_title="就活インタビューAI", layout="centered")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

init_db()

#from updater import check_and_update
#check_and_update()

# ============================================================
# Ollama 起動確認（早期フェイル）
# ============================================================
# 最初の API 呼び出しまでエラーに気づけない問題を防ぐため、
# 起動時に ollama.list() で接続を確認する。
# 失敗した場合は画面上にセットアップ案内を表示して st.stop() する。
@st.cache_data(ttl=30)
def _check_ollama() -> tuple[bool, str]:
    """Ollama への接続確認。結果を 30 秒キャッシュして毎描画の呼び出しコストを抑える。"""
    try:
        ollama.list()
        return True, ""
    except Exception as e:
        return False, str(e)

_ollama_ok, _ollama_err = _check_ollama()
if not _ollama_ok:
    st.error(
        "### ⚠️ Ollama に接続できません\n\n"
        "このアプリは **Ollama**（ローカル LLM）が起動している必要があります。\n\n"
        "**セットアップ手順:**\n"
        "1. [Ollama をインストール](https://ollama.com/download) してください\n"
        "2. ターミナルで以下を実行してモデルを取得します\n"
        "   ```\n"
        "   ollama pull qwen3:8b\n"
        "   ollama pull nomic-embed-text\n"
        "   ```\n"
        "3. Ollama が起動していることを確認してからページを再読み込みしてください\n\n"
        f"エラー詳細: `{_ollama_err}`"
    )
    st.stop()

st.markdown(
    """
    <style>
    /* 1. 全体の文字描画をくっきりシャープにする設定（ぼやけ防止） */
    html, body, [data-testid="stAppViewContainer"] {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        text-rendering: optimizeLegibility;
    }
    h1, h2, h3, h4, h5, h6, span, p {
        font-smooth: always;
    }

    /* 2. スマホ（画面幅が狭い端末）向けのレスポンシブ調整 */
    @media (max-width: 640px) {
        h1 {
            font-size: 1.8rem !important;
            line-height: 1.3 !important;
        }
        h2 {
            font-size: 1.4rem !important;
        }
        [data-testid="stHorizontalBlock"] {
            gap: 4px !important;
        }
        .stButton button {
            padding: 4px 8px !important;
            font-size: 13px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

if mode == "career_advisor":
    render_career(model_name)
    st.stop()

if mode == "personality":
    render_personality(model_name)
    st.stop()

if mode == "mock_interview":
    render_mock_interview(model_name)
    st.stop()

if mode == "predict_questions":
    render_predict_questions(model_name)
    st.stop()

if mode == "history":
    render_history()
    st.stop()

if mode == "company_matrix":
    render_company_matrix(model_name, build_conversation_history)
    st.stop()

# デフォルト: interview
render_interview(model_name)
