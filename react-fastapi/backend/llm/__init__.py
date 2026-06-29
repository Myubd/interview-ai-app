"""
llm/__init__.py
---------------
アプリ全体で使う LLMProvider のシングルトン管理。
OLLAMA_HOST 環境変数で接続先を切り替えられる（Docker 対応）。

[修正]
@lru_cache を廃止し、呼び出しごとにDBからホストを解決するよう変更。
これにより設定画面で ollama_host を変更した際に即時反映される。
パフォーマンスへの影響はほぼない（DBからの1行SELECTのみ）。
"""
from __future__ import annotations

import os

from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider

# 環境変数フォールバック（DB未設定時 / DB初期化前の起動直後に使う）
_ENV_OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# キャッシュ（ollama_client.py と同じ差分検知方式）
_provider: OllamaProvider | None = None
_cached_host: str | None = None


def _resolve_host() -> str:
    """使用すべき Ollama ホストを解決する。
    優先順位: DB設定 → 環境変数 → デフォルト
    """
    try:
        from db.settings_repository import get_setting
        db_host = get_setting("ollama_host")
        if db_host and db_host.strip():
            return db_host.strip()
    except Exception:
        pass
    return _ENV_OLLAMA_HOST


def get_provider() -> LLMProvider:
    """LLMProvider を返す。ホストが変わっていれば新インスタンスを生成する。"""
    global _provider, _cached_host

    current_host = _resolve_host()
    if _provider is None or current_host != _cached_host:
        _provider = OllamaProvider(host=current_host)
        _cached_host = current_host

    return _provider
