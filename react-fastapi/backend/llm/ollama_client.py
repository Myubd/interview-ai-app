# -*- coding: utf-8 -*-
"""
llm/ollama_client.py
---------------------
[置き換え済み] local_ai_core.llm.ollama_provider.OllamaProvider (同期メソッド:
chat_sync/embed_sync/list_models) を土台にした互換アダプタ。
「プライバシーファーストなローカルAIエコシステム」共通化 Phase 1 対応。

背景:
  rag/core.py と utils.py は、以前は `ollama.Client` を直接受け取り、
  `.chat(model=..., messages=..., format="json")` や `.embeddings(...)` を
  辞書アクセス(`response["message"]["content"]` / `res["embedding"]`)で
  使っていた。この呼び出し方自体は変えず、内部実装だけを local_ai_core に
  委譲することで、以下を実現する。

  - Ollama呼び出しのロジック(接続先解決、エラーハンドリング)を
    local_ai_core に一元化し、Archlife 等の他アプリとも共有できるようにする
  - 既存コード(rag/core.py, utils.py)は無改修で動く

使用方法(変更なし):
    from llm.ollama_client import get_client

    client = get_client()
    response = client.chat(model=..., messages=..., format="json")
    vec = client.embeddings(model=..., prompt=...)
"""
from __future__ import annotations

import logging
import os

from local_ai_core.llm.ollama_provider import OllamaProvider as _CoreOllamaProvider
from local_ai_core.llm.base import ChatMessage as _ChatMessage, LLMProviderError as _LLMProviderError

logger = logging.getLogger(__name__)

# 環境変数から読んだフォールバックホスト（DB に設定がない場合に使用）
_ENV_OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# キャッシュ状態
_client: "_SyncOllamaClientAdapter | None" = None
_cached_host: str | None = None  # 直前に使ったホスト。差分検知に使う


def _resolve_host() -> str:
    """使用すべき Ollama ホストを解決する(旧実装と同一のロジック)。

    優先順位:
        1. DB（settings テーブル）の "ollama_host" キー
        2. 環境変数 OLLAMA_HOST
        3. デフォルト "http://localhost:11434"
    """
    try:
        from db.settings_repository import get_setting
        db_host = get_setting("ollama_host")
        if db_host and db_host.strip():
            return db_host.strip()
    except Exception:
        logger.debug("_resolve_host: DB からホストを取得できませんでした。環境変数を使用します。")
    return _ENV_OLLAMA_HOST


class _SyncOllamaClientAdapter:
    """旧 `ollama.Client` の代わりに get_client() が返すアダプタ。

    呼び出し側(rag/core.py, utils.py)が使っているメソッドだけをカバーする:
      - chat(model=..., messages=[{"role":..., "content":...}], format=None)
          -> {"message": {"content": "..."}}  (辞書アクセス互換)
      - embeddings(model=..., prompt=...)
          -> {"embedding": [...]}              (辞書アクセス互換)
      - list()
          -> {"models": [{"name": "..."}, ...]}
    """

    def __init__(self, host: str):
        self._provider = _CoreOllamaProvider(base_url=host)

    def chat(self, model: str, messages: list[dict], format: str | None = None) -> dict:
        chat_messages = [_ChatMessage(role=m["role"], content=m["content"]) for m in messages]
        try:
            resp = self._provider.chat_sync(chat_messages, model=model, format=format)
        except _LLMProviderError as e:
            # 旧実装(ollamaパッケージ)は接続失敗時に例外を投げていたため、
            # 呼び出し側(utils.py)のtry/exceptがそのまま機能するよう例外型を保つ。
            raise RuntimeError(str(e)) from e
        return {"message": {"content": resp.content}}

    def embeddings(self, model: str, prompt: str) -> dict:
        try:
            vectors = self._provider.embed_sync([prompt], model=model)
        except _LLMProviderError as e:
            raise RuntimeError(str(e)) from e
        return {"embedding": vectors[0] if vectors else []}

    def list(self) -> dict:
        names = self._provider.list_models()
        return {"models": [{"name": n} for n in names]}

    def is_running(self) -> bool:
        return self._provider.is_running()


def get_client() -> _SyncOllamaClientAdapter:
    """Ollamaクライアント(互換アダプタ)を返す。

    ホストが変わっていなければキャッシュ済みインスタンスを再利用し、
    変わっていれば新しいインスタンスを生成してキャッシュを更新する(旧実装と同一の挙動)。
    """
    global _client, _cached_host

    current_host = _resolve_host()

    if _client is None or current_host != _cached_host:
        if _cached_host is not None and current_host != _cached_host:
            logger.info(
                "Ollama ホストが変更されました: %s → %s。クライアントを再生成します。",
                _cached_host,
                current_host,
            )
        _client = _SyncOllamaClientAdapter(current_host)
        _cached_host = current_host

    return _client


def reset_client() -> None:
    """キャッシュ済みクライアントを強制リセットする。

    次回の get_client() 呼び出しで新しいインスタンスが生成される。
    テスト・強制再接続などに使う。
    """
    global _client, _cached_host
    _client = None
    _cached_host = None
    logger.debug("Ollama クライアントをリセットしました。")
