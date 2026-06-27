"""
api/routes/mock_interview.py
-----------------------------
模擬面接エンドポイント。
ビジネスロジックは InterviewService に委譲し、
このルーターは HTTP の入出力のみを担う。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.interview_service import InterviewService, sse_generator

router = APIRouter()


# ============================================================
# スキーマ
# ============================================================

class StartRequest(BaseModel):
    industry_key: str = "general"
    persona_key: str = "standard"
    profile_text: str = ""
    rag_block: str | None = None
    predicted_questions: list[dict] | None = None


class StartResponse(BaseModel):
    theme_index: int
    theme_title: str
    question: str


class AnswerRequest(BaseModel):
    """回答送信リクエスト。

    `messages` にフロント側で追記済みの全メッセージ履歴を含めて送ること。
    """
    theme_index: int
    followups_asked: int
    messages: list[dict]
    industry_key: str = "general"
    persona_key: str = "standard"
    profile_text: str = ""
    rag_block: str | None = None
    predicted_questions: list[dict] | None = None


class EvaluateRequest(BaseModel):
    messages: list[dict]
    industry_key: str = "general"
    profile_text: str = ""
    rag_block: str | None = None


# ============================================================
# ペルソナ一覧
# ============================================================

@router.get("/personas")
async def list_personas() -> list[dict]:
    return await InterviewService.list_personas()


# ============================================================
# テーマ一覧
# ============================================================

@router.get("/themes")
async def list_themes(industry_key: str = "general") -> list[dict]:
    return await InterviewService.list_themes(industry_key)


# ============================================================
# 面接開始
# ============================================================

@router.post("/start", response_model=StartResponse)
async def start_interview(req: StartRequest) -> StartResponse:
    try:
        result = await InterviewService.start(
            industry_key=req.industry_key,
            persona_key=req.persona_key,
            profile_text=req.profile_text,
            rag_block=req.rag_block,
            predicted_questions=req.predicted_questions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StartResponse(
        theme_index=result.theme_index,
        theme_title=result.theme_title,
        question=result.question,
    )


# ============================================================
# 回答送信 → SSE ストリーミング
# ============================================================

@router.post("/answer")
async def post_answer(req: AnswerRequest) -> StreamingResponse:
    stream = InterviewService.answer_stream(
        theme_index=req.theme_index,
        followups_asked=req.followups_asked,
        messages=req.messages,
        industry_key=req.industry_key,
        persona_key=req.persona_key,
        profile_text=req.profile_text,
        rag_block=req.rag_block,
        predicted_questions=req.predicted_questions,
    )
    return StreamingResponse(
        sse_generator(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # nginx バッファリング無効化
        },
    )


# ============================================================
# 終了後評価
# ============================================================

@router.post("/evaluate")
async def evaluate(req: EvaluateRequest) -> dict:
    try:
        return await InterviewService.evaluate(
            messages=req.messages,
            industry_key=req.industry_key,
            profile_text=req.profile_text,
            rag_block=req.rag_block,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
