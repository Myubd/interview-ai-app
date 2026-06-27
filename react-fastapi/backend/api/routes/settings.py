"""api/routes/settings.py — LLMモデル・接続設定"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from db.settings_repository import get_setting, set_setting

router = APIRouter()

_DEFAULTS = {
    "chat_model":  "qwen3:8b",
    "embed_model": "nomic-embed-text",
    "ollama_host": "http://localhost:11434",
}


class SettingsResponse(BaseModel):
    chat_model: str  = Field(..., examples=["qwen3:8b"],            description="会話・生成に使う Ollama モデル名")
    embed_model: str = Field(..., examples=["nomic-embed-text"],     description="RAG 埋め込みに使う Ollama モデル名")
    ollama_host: str = Field(..., examples=["http://localhost:11434"], description="Ollama サーバーの URL")


class SettingsUpdateRequest(BaseModel):
    chat_model: str | None  = Field(None, examples=["llama3.2:3b"])
    embed_model: str | None = Field(None, examples=["nomic-embed-text"])
    ollama_host: str | None = Field(None, examples=["http://localhost:11434"])


@router.get(
    "/",
    response_model=SettingsResponse,
    summary="設定を取得",
)
async def get_settings() -> SettingsResponse:
    return SettingsResponse(
        chat_model  = get_setting("chat_model")  or _DEFAULTS["chat_model"],
        embed_model = get_setting("embed_model") or _DEFAULTS["embed_model"],
        ollama_host = get_setting("ollama_host") or _DEFAULTS["ollama_host"],
    )


@router.patch(
    "/",
    response_model=SettingsResponse,
    summary="設定を更新",
    description="指定したフィールドのみ更新します。変更は即時反映されます。",
)
async def update_settings(req: SettingsUpdateRequest) -> SettingsResponse:
    for key, value in req.model_dump(exclude_none=True).items():
        set_setting(key, value)
    return await get_settings()
