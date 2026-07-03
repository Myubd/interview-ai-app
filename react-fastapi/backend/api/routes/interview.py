"""
api/routes/interview.py
--------------------------
自己PR引き出しインタビュー（②〜⑤⑦）のエンドポイント。
ビジネスロジックは InterviewFlowService に委譲する。

既存コードとの対応:
  streamlit版 page_modules/interview/ 一式が相当する。

POST /start                最初のテーマの最初の質問を生成
POST /next                 回答を判定し、テーマ継続 or 次テーマへ移行
POST /choose-category      カテゴリ選択後の最初の質問を生成
POST /summary              面接サマリー生成
POST /pr/variants          自己PR 3パターン生成
POST /pr/evaluate          自己PR評価（4軸スコア）
POST /pr/refine            自己PR微調整リライト
GET  /pr/refine-presets    リライトのプリセット指示一覧
POST /pr/company           企業別カスタマイズPR生成（複数社まとめて）
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.interview_flow_service import InterviewFlowService
from pr_generation import REFINE_PRESETS

router = APIRouter()


class MessageSchema(BaseModel):
    role: str
    content: str


# ============================================================
# ②インタビュー本体
# ============================================================

class StartRequest(BaseModel):
    profile_text: str = ""


class QuestionResponse(BaseModel):
    status: str  # "question" | "awaiting_category_choice" | "complete"
    theme_index: int = 0
    theme_title: str = ""
    question: str = ""
    questions_asked_in_theme: int = 0
    category_options: list[str] = []


@router.post("/start", response_model=QuestionResponse)
async def start(req: StartRequest) -> QuestionResponse:
    result = await InterviewFlowService.start(req.profile_text)
    return QuestionResponse(**result.__dict__)


class NextRequest(BaseModel):
    theme_index: int
    theme_messages: list[MessageSchema]
    questions_asked_in_theme: int
    selected_category: str | None = None
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/next", response_model=QuestionResponse)
async def next_question(req: NextRequest) -> QuestionResponse:
    result = await InterviewFlowService.next_question(
        theme_index=req.theme_index,
        theme_messages=[m.model_dump() for m in req.theme_messages],
        questions_asked_in_theme=req.questions_asked_in_theme,
        selected_category=req.selected_category,
        profile_text=req.profile_text,
        messages=[m.model_dump() for m in req.messages],
    )
    return QuestionResponse(**result.__dict__)


class ChooseCategoryRequest(BaseModel):
    theme_index: int
    category: str
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/choose-category", response_model=QuestionResponse)
async def choose_category(req: ChooseCategoryRequest) -> QuestionResponse:
    result = await InterviewFlowService.choose_category(
        theme_index=req.theme_index,
        category=req.category,
        messages=[m.model_dump() for m in req.messages],
        profile_text=req.profile_text,
    )
    return QuestionResponse(**result.__dict__)


# ============================================================
# ③面接サマリー
# ============================================================

class SummaryRequest(BaseModel):
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/summary")
async def generate_summary(req: SummaryRequest) -> dict:
    try:
        return await InterviewFlowService.generate_summary(
            req.profile_text, [m.model_dump() for m in req.messages],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ④自己PR生成
# ============================================================

class VariantsRequest(BaseModel):
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/pr/variants")
async def generate_variants(req: VariantsRequest) -> list[dict]:
    try:
        return await InterviewFlowService.generate_variants(
            req.profile_text, [m.model_dump() for m in req.messages],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ⑤PR評価・微調整
# ============================================================

class EvaluateRequest(BaseModel):
    pr_text: str


@router.post("/pr/evaluate")
async def evaluate(req: EvaluateRequest) -> dict:
    try:
        return await InterviewFlowService.evaluate(req.pr_text)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


class RefineRequest(BaseModel):
    pr_text: str
    instruction: str
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/pr/refine")
async def refine(req: RefineRequest) -> dict:
    return await InterviewFlowService.refine(
        req.pr_text, req.instruction, req.profile_text, [m.model_dump() for m in req.messages],
    )


@router.get("/pr/refine-presets")
async def refine_presets() -> dict:
    return REFINE_PRESETS


# ============================================================
# ⑦企業別カスタマイズPR
# ============================================================

class CompanyEntry(BaseModel):
    name: str
    info: str


class CompanyPrRequest(BaseModel):
    base_pr: str
    companies: list[CompanyEntry]
    profile_text: str = ""
    messages: list[MessageSchema] = []


@router.post("/pr/company")
async def generate_company_prs(req: CompanyPrRequest) -> list[dict]:
    return await InterviewFlowService.generate_company_prs(
        req.base_pr,
        [c.model_dump() for c in req.companies],
        req.profile_text,
        [m.model_dump() for m in req.messages],
    )
