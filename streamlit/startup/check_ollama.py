"""
startup/check_ollama.py
-----------------------
Ollama への接続確認を行い、失敗時は Streamlit 画面にセットアップ案内を
表示して st.stop() する。

[設計メモ]
- キャッシュは使わず毎描画でチェックする。
  @st.cache_data でキャッシュすると、Ollama が一時的に応答できない瞬間
  （LLM推論中・モデルロード中など）に ok=False がキャッシュされ、
  正常に戻った後もキャッシュ期限まで画面がエラーのまま凍りつくため。
- ollama.list() 自体は軽量なリスト取得 API なので毎描画でも問題ない。
- socket.setdefaulttimeout で上限を設けてハングを防ぐ。
"""

import socket as _socket

import ollama
import streamlit as st

_TIMEOUT_SEC = 5  # Ollama 接続タイムアウト（秒）


def _check_ollama() -> tuple[bool, str]:
    """Ollama への接続確認。成功なら (True, "")、失敗なら (False, エラー文字列) を返す。"""
    prev = _socket.getdefaulttimeout()
    try:
        _socket.setdefaulttimeout(_TIMEOUT_SEC)
        ollama.list()
        return True, ""
    except Exception as e:
        return False, str(e)
    finally:
        _socket.setdefaulttimeout(prev)


def ensure_ollama_running() -> None:
    """Ollama が起動していなければエラーを表示して st.stop() する。"""
    ok, err = _check_ollama()
    if not ok:
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
            f"エラー詳細: `{err}`"
        )
        st.stop()
