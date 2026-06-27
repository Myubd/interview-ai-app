"""api/routes/health.py — Ollama 疎通確認"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import get_provider
from llm.ollama_provider import OllamaProvider

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"], description='"ok" または "degraded"')
    ollama: bool = Field(..., description="Ollama が起動しているか")
    models: list[str] = Field(..., examples=[["qwen3:8b", "nomic-embed-text"]])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="ヘルスチェック",
    description="サーバーと Ollama の疎通を確認します。`status: ok` なら AI 機能が使えます。",
    responses={
        200: {
            "description": "正常（ok）または Ollama 未接続（degraded）",
            "content": {
                "application/json": {
                    "examples": {
                        "ok": {
                            "summary": "正常",
                            "value": {"status": "ok", "ollama": True, "models": ["qwen3:8b"]},
                        },
                        "degraded": {
                            "summary": "Ollama 未接続",
                            "value": {"status": "degraded", "ollama": False, "models": []},
                        },
                    }
                }
            },
        }
    },
)
async def health_check() -> HealthResponse:
    provider = get_provider()
    ollama_ok = False
    models: list[str] = []

    if isinstance(provider, OllamaProvider):
        ollama_ok = provider.is_running()
        if ollama_ok:
            models = provider.list_models()

    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        ollama=ollama_ok,
        models=models,
    )
