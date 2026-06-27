# -*- coding: utf-8 -*-
"""
llm/ollama_client.py
---------------------
Ollamaクライアントのシングルトン管理モジュール。

モンキーパッチ（ollama.chat = client.chat）の代わりに、
このモジュールから get_client() でクライアントを取得して使う。
これにより import 順序に依存しない安全な設計になる。

使用方法:
    from llm.ollama_client import get_client

    client = get_client()
    response = client.chat(model=..., messages=..., format="json")
    vec = client.embeddings(model=..., prompt=...)
"""
from __future__ import annotations

import os
import ollama

_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# モジュールレベルのシングルトン
# 環境変数は起動時に1回だけ読まれる（再起動なしの動的変更は非対応）
_client: ollama.Client | None = None


def get_client() -> ollama.Client:
    """Ollamaクライアントのシングルトンを返す。初回のみ生成する。"""
    global _client
    if _client is None:
        _client = ollama.Client(host=_OLLAMA_HOST)
    return _client
