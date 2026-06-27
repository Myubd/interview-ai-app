"""
components/sidebar/settings.py
--------------------------------
Ollamaのチャット・埋め込みモデル名を設定するパネルを描画する。
"""

import streamlit as st

from db.settings_repository import get_setting, set_setting
from interview_engine import DEFAULT_MAX_QUESTIONS_PER_THEME

DEFAULT_CHAT_MODEL = "qwen3:8b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"


def render_settings() -> str:
    """モデル設定UIを描画し、選択中のチャットモデル名を返す。"""
    st.header("⚙️ 設定")

    saved_model = get_setting("chat_model", DEFAULT_CHAT_MODEL)
    model_name = st.text_input("Ollamaチャットモデル名", value=saved_model)
    if model_name and model_name != saved_model:
        set_setting("chat_model", model_name)
    st.caption("例: qwen3:8b / qwen3:4b / gpt-oss:20b")

    saved_embed = get_setting("embed_model", DEFAULT_EMBED_MODEL)
    embed_model = st.text_input("Ollama埋め込みモデル名", value=saved_embed)
    if embed_model and embed_model != saved_embed:
        set_setting("embed_model", embed_model)
    st.caption("例: nomic-embed-text / mxbai-embed-large")

    st.caption(
        f"質問はテーマごとに、直前の回答を踏まえてAIがその場で生成します"
        f"（1テーマあたり最大{DEFAULT_MAX_QUESTIONS_PER_THEME}問まで自動で深掘りします）。"
    )
    return model_name or DEFAULT_CHAT_MODEL
