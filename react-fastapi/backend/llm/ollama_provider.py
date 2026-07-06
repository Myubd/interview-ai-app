"""
llm/ollama_provider.py
-----------------------
[置き換え済み] local_ai_core.llm.ollama_provider.OllamaProvider を土台にした
互換ラッパー。「プライバシーファーストなローカルAIエコシステム」共通化の
Phase 1 対応。

変更点:
  - 内部実装を `ollama` パッケージ直叩きから、local_ai_core が使う
    httpx 経由のREST呼び出しに変更(Ollamaが公開する同一のREST APIを
    利用するため、外部から見た挙動は変わらない)。
  - 既存コードとの互換性のため、コンストラクタ引数は `host=` のまま維持。
  - `is_running()` / `list_models()` は local_ai_core 側に実装済みのものを
    そのまま継承して使う(健康チェックAPI `api/routes/health.py` は無改修で動く)。
  - OpenAIProvider / ClaudeProvider は「未実装スタブ」だったものを、
    local_ai_core の実装(オプトイン専用の外部API呼び出し)に置き換えた。
    ただし本アプリはローカル完結が前提のため、既定では使用しない。

移行前の実装は `llm/ollama_provider.py.bak` として同梱(参考用)。
"""
from __future__ import annotations

from local_ai_core.llm.ollama_provider import OllamaProvider as _CoreOllamaProvider
from local_ai_core.llm.external_providers import (
    ClaudeProvider as _CoreClaudeProvider,
    OpenAIProvider as _CoreOpenAIProvider,
)


class OllamaProvider(_CoreOllamaProvider):
    """Ollama ローカル LLM プロバイダー(local_ai_core 実装への委譲)。"""

    DEFAULT_CHAT_MODEL = "qwen3:8b"
    DEFAULT_EMBED_MODEL = "nomic-embed-text"

    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_chat_model: str = DEFAULT_CHAT_MODEL,
        default_embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        # 旧コンストラクタ引数名(host / default_chat_model / default_embed_model)を
        # local_ai_core 側の引数名(base_url / model / embed_model)にマッピングする。
        super().__init__(base_url=host, model=default_chat_model, embed_model=default_embed_model)
        # 旧コードが `provider.default_chat_model` を直接参照している箇所との互換用
        self.default_chat_model = default_chat_model
        self.default_embed_model = default_embed_model


# ---------------------------------------------------------------------------
# 外部プロバイダー(オプトイン)。以前は NotImplementedError を投げるだけの
# スタブだったが、local_ai_core の実装に置き換えて実際に動くようにした。
# 本アプリはローカル完結が前提のため、UIから明示的に許可されない限り使わない。
# ---------------------------------------------------------------------------

class OpenAIProvider(_CoreOpenAIProvider):
    """OpenAI API プロバイダー(オプトイン時のみ使用)。"""


class ClaudeProvider(_CoreClaudeProvider):
    """Anthropic Claude API プロバイダー(オプトイン時のみ使用)。"""
