"""
api/routes/personality.py
----------------------------
性格診断・適性検査（ビッグファイブ30問）エンドポイント。
ビジネスロジックは PersonalityService に委譲する。

既存コードとの対応:
  streamlit版 page_modules/personality_page.py が相当する。

GET  /questions           設問一覧・軸ラベル・回答スケールを取得
POST /submit               回答を送信し、AIによる診断結果を生成する
POST /save-and-favorite    診断結果をセッションとして保存し、お気に入りに登録する
GET  /result/{session_id}  保存済みの診断結果を取得する
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.personality_service import PersonalityService, GenerationFailedError

router = APIRouter()


# ============================================================
# 設問一覧
# ============================================================

class QuestionSchema(BaseModel):
    id: int
    axis: str
    text: str
    reverse: bool


class QuestionsResponse(BaseModel):
    axes: dict[str, str]
    questions: list[QuestionSchema]
    scale_labels: dict[int, str]
    total_questions: int


@router.get("/questions", response_model=QuestionsResponse)
async def get_questions() -> QuestionsResponse:
    info = PersonalityService.get_questions()
    return QuestionsResponse(
        axes=info.axes,
        questions=info.questions,
        scale_labels=info.scale_labels,
        total_questions=info.total_questions,
    )


# ============================================================
# 診断結果生成
# ============================================================

class SubmitRequest(BaseModel):
    answers: dict[int, int]  # {question_id: 1〜5}


class StrengthItem(BaseModel):
    point: str = ""
    detail: str = ""


class CautionItem(BaseModel):
    point: str = ""
    hint: str = ""


class RoleItem(BaseModel):
    role: str
    score: float


class IndustryFitEntry(BaseModel):
    score: int
    reason: str = ""


class SubmitResponse(BaseModel):
    axis_scores: dict[str, float]
    consistency_score: int = 0
    personality_summary: str = ""
    strengths: list[StrengthItem] = []
    cautions: list[CautionItem] = []
    fit_environments: str = ""
    industry_fit: dict[str, IndustryFitEntry] = {}
    recommended_roles: list[RoleItem] = []
    interview_strengths: list[str] = []
    interview_risks: list[str] = []
    interview_tips: str = ""


@router.post("/submit", response_model=SubmitResponse)
async def submit(req: SubmitRequest) -> SubmitResponse:
    try:
        result = await PersonalityService.submit(req.answers)
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SubmitResponse(**result)


# ============================================================
# 保存 + お気に入り登録
# ============================================================

class SaveAndFavoriteRequest(BaseModel):
    answers: dict[int, int]
    axis_scores: dict[str, float]
    result: dict
    session_id: int | None = None
    company_name: str | None = None


class SaveAndFavoriteResponse(BaseModel):
    session_id: int
    favorite_id: int


@router.post("/save-and-favorite", response_model=SaveAndFavoriteResponse)
async def save_and_favorite(req: SaveAndFavoriteRequest) -> SaveAndFavoriteResponse:
    session_id, favorite_id = await PersonalityService.save_and_favorite(
        answers=req.answers,
        axis_scores=req.axis_scores,
        result=req.result,
        session_id=req.session_id,
        company_name=req.company_name,
    )
    return SaveAndFavoriteResponse(session_id=session_id, favorite_id=favorite_id)


# ============================================================
# 保存済み結果の取得（AIキャリアアドバイザー等、他機能からの参照用）
# ============================================================

@router.get("/result/{session_id}")
async def get_result(session_id: int) -> dict:
    result = await PersonalityService.get_saved_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="診断結果が見つかりません。")
    return result
