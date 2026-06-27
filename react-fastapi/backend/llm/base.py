"""
llm/base.py
-----------
LLMプロバイダーの抽象基底クラス。
将来的に OpenAI / Claude 等への切り替えをここだけで吸収する。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ChatMessage:
    role: str   # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str


class LLMProvider(ABC):
    """チャット補完を提供するプロバイダーの基底クラス。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """非ストリーミングでテキストを返す。"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """SSE向けにテキストをチャンク単位で返す。"""
        ...

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """テキストリストをベクトルに変換する。"""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """利用可能なモデル名のリストを返す。"""
        ...
