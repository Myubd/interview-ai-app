"""
llm/ollama_provider.py
-----------------------
Ollama をバックエンドとする LLMProvider 実装。
既存の utils.py が直接 import ollama していた部分をここに集約し、
アプリコードは LLMProvider インターフェースのみに依存する。
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

import ollama

from llm.base import ChatMessage, ChatResponse, LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama ローカル LLM プロバイダー。"""

    DEFAULT_CHAT_MODEL = "qwen3:8b"
    DEFAULT_EMBED_MODEL = "nomic-embed-text"

    def __init__(
        self,
        host: str = "http://localhost:11434",
        default_chat_model: str = DEFAULT_CHAT_MODEL,
        default_embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        self._client = ollama.AsyncClient(host=host)
        self._sync_client = ollama.Client(host=host)
        self.default_chat_model = default_chat_model
        self.default_embed_model = default_embed_model

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        model = model or self.default_chat_model
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens

        response = await self._client.chat(
            model=model,
            messages=ollama_messages,
            options=options,
        )
        content = response.message.content or ""
        return ChatResponse(content=content, model=model)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        model = model or self.default_chat_model
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        async for chunk in await self._client.chat(
            model=model,
            messages=ollama_messages,
            stream=True,
            options={"temperature": temperature},
        ):
            text = chunk.message.content
            if text:
                yield text

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or self.default_embed_model
        results: list[list[float]] = []
        for text in texts:
            resp = await self._client.embeddings(model=model, prompt=text)
            results.append(resp.embedding)
        return results

    def list_models(self) -> list[str]:
        try:
            resp = self._sync_client.list()
            return [m.model for m in resp.models]
        except Exception as exc:
            logger.warning("Ollama list_models failed: %s", exc)
            return []

    def is_running(self) -> bool:
        """Ollama が起動しているかどうかを確認する。"""
        try:
            self._sync_client.list()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# 将来の拡張ポイント（未実装スタブ）
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    """OpenAI API プロバイダー（未実装）。"""

    async def chat(self, messages, model=None, temperature=0.7, max_tokens=None):
        raise NotImplementedError("OpenAIProvider is not yet implemented")

    async def chat_stream(self, messages, model=None, temperature=0.7):
        raise NotImplementedError("OpenAIProvider is not yet implemented")
        yield  # AsyncIterator として認識させるための dummy

    async def embed(self, texts, model=None):
        raise NotImplementedError("OpenAIProvider is not yet implemented")

    def list_models(self):
        raise NotImplementedError("OpenAIProvider is not yet implemented")


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API プロバイダー（未実装）。"""

    async def chat(self, messages, model=None, temperature=0.7, max_tokens=None):
        raise NotImplementedError("ClaudeProvider is not yet implemented")

    async def chat_stream(self, messages, model=None, temperature=0.7):
        raise NotImplementedError("ClaudeProvider is not yet implemented")
        yield

    async def embed(self, texts, model=None):
        raise NotImplementedError("ClaudeProvider is not yet implemented")

    def list_models(self):
        raise NotImplementedError("ClaudeProvider is not yet implemented")
