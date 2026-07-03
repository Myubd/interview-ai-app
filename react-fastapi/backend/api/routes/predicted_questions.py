"""
api/routes/predicted_questions.py
------------------------------------
想定質問生成（RAGベース版）エンドポイント。
ビジネスロジックは PredictionService に委譲し、
このルーターは HTTP の入出力のみを担う。

既存コードとの対応:
  question_prediction.generate_predicted_questions_from_rag → shared/ に一本化済み
  db/knowledge_base_repository.py → 企業KBの検証
  db/favorites_repository.py      → お気に入り登録

POST /generate           企業KB + 共通履歴書KBから想定質問セット（8問）を生成する
POST /save-and-favorite   生成済みの質問セットをセッションとして保存し、お気に入りに登録する
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.prediction_service import (
    PredictionService,
    InsufficientMaterialError,
    GenerationFailedError,
)

router = APIRouter()


class MessageSchema(BaseModel):
    role: str
    content: str


# ============================================================
# スキーマ
# ============================================================

class GenerateRequest(BaseModel):
    company_kb_id: int


class PredictedQuestionSchema(BaseModel):
    category: str
    category_label: str
    question: str
    model_answer: str


class GenerateResponse(BaseModel):
    questions: list[PredictedQuestionSchema]


class SaveAndFavoriteRequest(BaseModel):
    company_kb_id: int
    company_name: str
    questions: list[PredictedQuestionSchema]


class SaveAndFavoriteResponse(BaseModel):
    session_id: int
    favorite_id: int


# ============================================================
# 生成
# ============================================================

@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        result = await PredictionService.generate(company_kb_id=req.company_kb_id)
    except InsufficientMaterialError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return GenerateResponse(
        questions=[
            PredictedQuestionSchema(
                category=q.category,
                category_label=q.category_label,
                question=q.question,
                model_answer=q.model_answer,
            )
            for q in result.questions
        ]
    )


# ============================================================
# 保存 + お気に入り登録
# ============================================================

@router.post("/save-and-favorite", response_model=SaveAndFavoriteResponse)
async def save_and_favorite(req: SaveAndFavoriteRequest) -> SaveAndFavoriteResponse:
    session_id, favorite_id = await PredictionService.save_and_favorite(
        company_kb_id=req.company_kb_id,
        company_name=req.company_name,
        questions=[q.model_dump() for q in req.questions],
    )
    return SaveAndFavoriteResponse(session_id=session_id, favorite_id=favorite_id)


# ============================================================
# ⑥想定質問（自己PR＋会話履歴ベース版）
# streamlit版 page_modules/interview/predicted_questions_section.py が相当。
# ============================================================

class GenerateFromPrRequest(BaseModel):
    pr_text: str
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/generate-from-pr", response_model=GenerateResponse)
async def generate_from_pr(req: GenerateFromPrRequest) -> GenerateResponse:
    try:
        result = await PredictionService.generate_from_pr(
            req.pr_text, req.profile_text, [m.model_dump() for m in req.messages],
        )
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return GenerateResponse(
        questions=[
            PredictedQuestionSchema(
                category=q.category,
                category_label=q.category_label,
                question=q.question,
                model_answer=q.model_answer,
            )
            for q in result.questions
        ]
    )


class SaveAndFavoritePrBasedRequest(BaseModel):
    questions: list[PredictedQuestionSchema]
    company_name: str | None = None


@router.post("/save-and-favorite-pr-based", response_model=SaveAndFavoriteResponse)
async def save_and_favorite_pr_based(req: SaveAndFavoritePrBasedRequest) -> SaveAndFavoriteResponse:
    session_id, favorite_id = await PredictionService.save_and_favorite_pr_based(
        questions=[q.model_dump() for q in req.questions],
        company_name=req.company_name,
    )
    return SaveAndFavoriteResponse(session_id=session_id, favorite_id=favorite_id)
