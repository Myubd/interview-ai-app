"""api/routes/permissions.py — 他アプリ・共通基盤へのデータ共有許可の管理

local-ai-core の PermissionGate をそのまま薄くラップしたエンドポイント。
「申告されているだけでまだ許可していないスコープ」の一覧取得と、
ユーザーによる許可(grant)/失効(revoke)、現在の許可一覧の取得を提供する。
このAPIが呼ばれても、ユーザーが明示的にgrantしない限り何も共有されない。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core_sync import get_gate, get_profile_id

router = APIRouter()


class PendingScope(BaseModel):
    app_key: str = Field(..., examples=["interview_app"])
    scope: str = Field(..., examples=["memory:read:career.*"])
    purpose: str = Field(..., examples=["過去の自己分析結果を面接対策の提案に活かすため"])


class GrantedScope(BaseModel):
    app_key: str
    scope: str
    purpose: str
    granted_at: str
    expires_at: str | None


class GrantRequest(BaseModel):
    app_key: str
    scope: str


@router.get(
    "/pending",
    response_model=list[PendingScope],
    summary="まだ許可していないデータ共有リクエストの一覧",
)
async def list_pending() -> list[PendingScope]:
    gate = get_gate()
    profile_id = get_profile_id()
    return [PendingScope(**item) for item in gate.pending_requests(profile_id)]


@router.get(
    "/granted",
    response_model=list[GrantedScope],
    summary="現在許可しているデータ共有の一覧",
)
async def list_granted() -> list[GrantedScope]:
    gate = get_gate()
    profile_id = get_profile_id()
    return [
        GrantedScope(
            app_key=g.app_key, scope=g.scope, purpose=g.purpose,
            granted_at=g.granted_at, expires_at=g.expires_at,
        )
        for g in gate.list_grants(profile_id)
    ]


@router.post(
    "/grant",
    status_code=204,
    summary="データ共有を許可する",
)
async def grant(req: GrantRequest) -> None:
    gate = get_gate()
    profile_id = get_profile_id()
    gate.grant(profile_id, req.app_key, req.scope)


@router.post(
    "/revoke",
    status_code=204,
    summary="データ共有の許可を取り消す",
)
async def revoke(req: GrantRequest) -> None:
    gate = get_gate()
    profile_id = get_profile_id()
    gate.revoke(profile_id, req.app_key, req.scope)
