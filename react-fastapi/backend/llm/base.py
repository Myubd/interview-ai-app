"""
llm/base.py
-----------
[置き換え済み] local_ai_core.llm.base への薄い再エクスポート。

以前はこのファイルに LLMProvider / ChatMessage / ChatResponse を直接定義していたが、
「プライバシーファーストなローカルAIエコシステム」共通化の Phase 1 により、
アプリ非依存の共通パッケージ local_ai_core に実装を移した。

後方互換性:
  - ChatMessage(role, content) は変更なし
  - ChatResponse(content, model) は変更なし。local_ai_core版は
    provider / usage フィールドが追加されているが、両方ともデフォルト値を
    持つため既存コード(response.content / response.model のみ参照)は無改修で動く
  - LLMProvider は抽象メソッドとして is_available() が追加された。
    既存の OllamaProvider 実装(llm/ollama_provider.py)側で対応済み
"""
from __future__ import annotations

from local_ai_core.llm.base import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    LLMProviderError,
)

__all__ = ["ChatMessage", "ChatResponse", "LLMProvider", "LLMProviderError"]
