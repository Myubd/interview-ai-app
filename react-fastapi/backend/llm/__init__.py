"""
llm/__init__.py
---------------
アプリ全体で使う LLMProvider のシングルトン管理。
OLLAMA_HOST 環境変数で接続先を切り替えられる（Docker 対応）。
"""
from __future__ import annotations

import os
from functools import lru_cache

from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    return OllamaProvider(host=host)
