"""
api/routes/favorites.py
-------------------------
「お気に入り」機能のエンドポイント。

既存コードとの対応:
  db/favorites_repository.py → add_favorite / remove_favorite / list_favorites 等

ビジネスロジックと呼べるほどの分岐がないため、Streamlit版と同様に
サービス層を挟まず db/favorites_repository を直接呼び出す
（mock-interview のように LLM 呼び出し・非同期化が必要な処理はない）。

GET    /                          一覧（item_type / company_name / session_type フィルタ可）
POST   /                          追加（重複時は既存IDを返す）
DELETE /{favorite_id}             id指定で削除
DELETE /by-item                   (item_type, item_id, session_id) 指定で削除
GET    /is-favorited              (item_type, item_id, session_id) がお気に入り済みか判定
GET    /meta                      絞り込み用メタ情報（会社名一覧・種別一覧・総件数）
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

from db.favorites_repository import (
    add_favorite as _add_favorite,
    remove_favorite as _remove_favorite,
    remove_favorite_by_item as _remove_favorite_by_item,
    is_favorited as _is_favorited,
    get_favorite_id as _get_favorite_id,
    list_favorites as _list_favorites,
    list_distinct_companies,
    list_distinct_session_types,
    count_favorites,
    ITEM_TYPE_LABELS,
)

router = APIRouter()


# ============================================================
# スキーマ
# ============================================================

class FavoriteCreateRequest(BaseModel):
    item_type: str
    item_id: int | None = None
    session_id: int | None = None
    company_name: str | None = None
    session_type: str | None = None
    label: str | None = None
    content_snapshot: Any = None


class FavoriteCreateResponse(BaseModel):
    id: int


# ============================================================
# 一覧・メタ情報
# ============================================================

@router.get("")
async def list_favorites(
    item_type: str | None = None,
    company_name: str | None = None,
    session_type: str | None = None,
) -> list[dict]:
    return _list_favorites(
        item_type=item_type or None,
        company_name=company_name or None,
        session_type=session_type or None,
    )


@router.get("/meta")
async def get_favorites_meta() -> dict:
    return {
        "item_type_labels": ITEM_TYPE_LABELS,
        "companies": list_distinct_companies(),
        "session_types": list_distinct_session_types(),
        "count": count_favorites(),
    }


@router.get("/is-favorited")
async def get_is_favorited(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
) -> dict:
    favorited = _is_favorited(item_type, item_id=item_id, session_id=session_id)
    fav_id = _get_favorite_id(item_type, item_id=item_id, session_id=session_id) if favorited else None
    return {"favorited": favorited, "favorite_id": fav_id}


# ============================================================
# 追加・削除
# ============================================================

@router.post("", response_model=FavoriteCreateResponse)
async def create_favorite(req: FavoriteCreateRequest) -> FavoriteCreateResponse:
    fav_id = _add_favorite(
        item_type=req.item_type,
        item_id=req.item_id,
        session_id=req.session_id,
        company_name=req.company_name,
        session_type=req.session_type,
        label=req.label,
        content_snapshot=req.content_snapshot,
    )
    return FavoriteCreateResponse(id=fav_id)


@router.delete("/by-item")
async def delete_favorite_by_item(
    item_type: str,
    item_id: int | None = None,
    session_id: int | None = None,
) -> dict:
    _remove_favorite_by_item(item_type, item_id=item_id, session_id=session_id)
    return {"ok": True}


@router.delete("/{favorite_id}")
async def delete_favorite(favorite_id: int) -> dict:
    _remove_favorite(favorite_id)
    return {"ok": True}
