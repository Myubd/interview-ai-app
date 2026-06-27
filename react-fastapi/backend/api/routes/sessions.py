"""
api/routes/sessions.py
-----------------------
面接セッションの CRUD エンドポイント。

既存コードとの対応:
  db/session_repository.py → save_session / list_sessions / get_session / delete_session
    - save_session は keyword-only 引数で _UNSET sentinel を使っている
    - get_session は {"session": {...}, "messages": [...]} を返す
    - list_sessions はメタ情報のみのリスト
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from db.session_repository import (
    save_session,
    list_sessions,
    get_session,
    delete_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# スキーマ
# ============================================================

class SessionCreateRequest(BaseModel):
    company_name: str = ""
    profile_text: str = ""
    session_type: str = "mock"


class SessionUpdateRequest(BaseModel):
    company_name: str | None = None
    session_type: str | None = None
    profile_text: str | None = None
    interview_complete: bool | None = None
    final_pr: str | None = None
    interview_summary: str | None = None
    pr_variants: list[dict] | None = None
    predicted_questions: list[dict] | None = None
    progress_state: dict | None = None
    mock_evaluation: dict | None = None
    messages: list[dict] | None = None


# ============================================================
# 一覧
# ============================================================

@router.get("/")
async def get_sessions() -> list[dict]:
    return list_sessions()


# ============================================================
# 新規作成
# ============================================================

@router.post("/", status_code=201)
async def create_new_session(req: SessionCreateRequest) -> dict:
    session_id = save_session(
        company_name=req.company_name or None,
        session_type=req.session_type or None,
        direct_values={"profile_text": req.profile_text or None},
    )
    return {"id": session_id}


# ============================================================
# 取得
# ============================================================

@router.get("/{session_id}")
async def get_session_by_id(session_id: int) -> dict:
    result = get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result  # {"session": {...}, "messages": [...]}


# ============================================================
# 更新（進捗・メッセージ保存）
# ============================================================

@router.patch("/{session_id}")
async def update_session_by_id(session_id: int, req: SessionUpdateRequest) -> dict:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    upd = req.model_dump(exclude_none=True)

    direct_values = {k: upd[k] for k in ("profile_text", "interview_complete", "final_pr", "interview_summary") if k in upd}
    json_values   = {k: upd[k] for k in ("pr_variants", "predicted_questions") if k in upd}

    # _UNSET で省略するか、値を渡すかを明示的に制御
    kwargs: dict = {
        "session_id": session_id,
        "direct_values": direct_values or None,
        "json_values": json_values or None,
        "progress_state": upd.get("progress_state"),
        "mock_evaluation": upd.get("mock_evaluation"),
        "messages": upd.get("messages"),
    }
    if "company_name" in upd:
        kwargs["company_name"] = upd["company_name"]
    if "session_type" in upd:
        kwargs["session_type"] = upd["session_type"]

    save_session(**kwargs)
    return get_session(session_id)  # type: ignore[return-value]


# ============================================================
# 削除
# ============================================================

@router.delete("/{session_id}", status_code=204)
async def delete_session_by_id(session_id: int) -> None:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)


# ============================================================
# JSON エクスポート
# ============================================================

@router.get("/{session_id}/export")
async def export_session(session_id: int) -> JSONResponse:
    result = get_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(
        content=result,
        headers={"Content-Disposition": f'attachment; filename="session_{session_id}.json"'},
    )


# ============================================================
# JSON インポート（エクスポート形式をそのまま受け付ける）
# ============================================================

class ImportRequest(BaseModel):
    data: dict


@router.post("/import", status_code=201)
async def import_session(req: ImportRequest) -> dict:
    try:
        sess = req.data.get("session", {})
        msgs = req.data.get("messages", [])
        session_id = save_session(
            company_name=sess.get("company_name"),
            session_type=sess.get("session_type"),
            direct_values={
                "profile_text": sess.get("profile_text"),
                "interview_complete": bool(sess.get("interview_complete", False)),
                "final_pr": sess.get("final_pr"),
                "interview_summary": sess.get("interview_summary"),
            },
            json_values={
                "pr_variants": sess.get("pr_variants"),
                "predicted_questions": sess.get("predicted_questions"),
            },
            mock_evaluation=sess.get("mock_interview_evaluation"),
            messages=msgs,
        )
        return {"id": session_id}
    except Exception as exc:
        logger.exception("Import failed")
        raise HTTPException(status_code=400, detail=str(exc))
