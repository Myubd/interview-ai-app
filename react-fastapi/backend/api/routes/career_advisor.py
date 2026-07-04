"""
api/routes/career_advisor.py
--------------------------------
AIキャリアアドバイザー（就活相談チャット）エンドポイント。
ビジネスロジックは CareerAdvisorService に委譲する。

既存コードとの対応:
  streamlit版 page_modules/career_page.py が相当する。

GET  /sessions   コンテキストとして選択可能な保存済みセッション一覧を取得
POST /chat        会話履歴を送信し、アドバイザーの返信を生成する
                  （session_id を指定すると、そのセッションの面接内容・自己PR・
                    模擬面接評価・性格診断結果を踏まえた回答になる）
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from services.career_advisor_service import CareerAdvisorService

router = APIRouter()


class SessionSummarySchema(BaseModel):
    id: int
    company_name: str | None = None
    session_type: str | None = None
    status: str
    interview_complete: int
    created_at: str
    updated_at: str
    has_mock_evaluation: int


@router.get("/sessions", response_model=list[SessionSummarySchema])
async def list_context_sessions() -> list[SessionSummarySchema]:
    sessions = await CareerAdvisorService.list_context_sessions()
    return [SessionSummarySchema(**s) for s in sessions]


class ChatMessageSchema(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    """会話履歴送信リクエスト。

    `messages` にフロント側で追記済みの全会話履歴（最後の要素が今回の
    ユーザーの発言）を含めて送ること。
    """
    messages: list[ChatMessageSchema]
    session_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    ok: bool
    error_msg: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    result = await CareerAdvisorService.chat(
        messages=[m.model_dump() for m in req.messages],
        session_id=req.session_id,
    )
    return ChatResponse(**result)
