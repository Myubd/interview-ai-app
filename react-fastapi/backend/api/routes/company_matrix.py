"""
api/routes/company_matrix.py
--------------------------------
企業比較マトリクスエンドポイント。
ビジネスロジックは CompanyMatrixService に委譲する。

既存コードとの対応:
  streamlit版 page_modules/company_matrix_page.py が相当する。

GET  /companies       比較対象の企業KB一覧を取得
POST /motivations      選択企業ごとの志望動機文を一括生成
POST /matrix            比較マトリクス（固定7軸＋追加軸）を生成
POST /matrix/export-csv 生成済みマトリクスをCSVに変換
POST /why-not-others    「なぜ他社でなくこの企業か」差別化ポイントを生成
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from services.company_matrix_service import (
    CompanyMatrixService,
    CompanyNotFoundError,
    GenerationFailedError,
    MAX_COMPANIES,
    MATRIX_AXES_FIXED,
    VALUE_FIT_AXIS_KEY,
    VALUE_FIT_NOTE,
)
from services.rag_helpers import build_conversation_history

router = APIRouter()


class MessageSchema(BaseModel):
    role: str
    content: str


# ============================================================
# 企業一覧・定数
# ============================================================

class CompanyKbSchema(BaseModel):
    id: int
    name: str
    kb_type: str
    is_active: bool | int
    created_at: str


@router.get("/companies", response_model=list[CompanyKbSchema])
async def list_companies() -> list[CompanyKbSchema]:
    kbs = await CompanyMatrixService.list_company_kbs()
    return [CompanyKbSchema(**kb) for kb in kbs]


class ConstantsResponse(BaseModel):
    max_companies: int
    matrix_axes_fixed: list[str]
    value_fit_axis_key: str
    value_fit_note: str


@router.get("/constants", response_model=ConstantsResponse)
async def get_constants() -> ConstantsResponse:
    return ConstantsResponse(
        max_companies=MAX_COMPANIES,
        matrix_axes_fixed=MATRIX_AXES_FIXED,
        value_fit_axis_key=VALUE_FIT_AXIS_KEY,
        value_fit_note=VALUE_FIT_NOTE,
    )


def _history(profile_text: str, messages: list[MessageSchema]) -> str:
    return build_conversation_history(profile_text, [m.model_dump() for m in messages])


# ============================================================
# ①志望動機（一括）
# ============================================================

class MotivationsRequest(BaseModel):
    company_kb_ids: list[int]
    pr_text: str = ""
    profile_text: str = ""
    messages: list[MessageSchema] = []


class MotivationResult(BaseModel):
    company_name: str
    motivation_text: str
    key_points: list[str]
    ok: bool
    error_msg: str | None = None


@router.post("/motivations", response_model=list[MotivationResult])
async def generate_motivations(req: MotivationsRequest) -> list[MotivationResult]:
    history = _history(req.profile_text, req.messages)
    try:
        results = await CompanyMatrixService.generate_motivations(
            req.company_kb_ids, req.pr_text, history,
        )
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [MotivationResult(**r) for r in results]


# ============================================================
# ②比較マトリクス
# ============================================================

class MatrixRequest(BaseModel):
    company_kb_ids: list[int]
    pr_text: str = ""
    additional_axes: list[str] = []


class MatrixCellSchema(BaseModel):
    score: int
    comment: str


class MatrixResponse(BaseModel):
    axes: list[str]
    companies: list[str]
    matrix: dict[str, dict[str, MatrixCellSchema]]
    overall_recommendation: str
    ok: bool
    error_msg: str | None = None


@router.post("/matrix", response_model=MatrixResponse)
async def generate_matrix(req: MatrixRequest) -> MatrixResponse:
    if len(req.company_kb_ids) < 2:
        raise HTTPException(status_code=400, detail="比較マトリクスの生成には2社以上の選択が必要です。")
    try:
        result = await CompanyMatrixService.generate_matrix(
            req.company_kb_ids, req.pr_text, req.additional_axes,
        )
    except CompanyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return MatrixResponse(**result)


@router.post("/matrix/export-csv", response_class=PlainTextResponse)
async def export_matrix_csv(result: MatrixResponse) -> str:
    return await CompanyMatrixService.export_matrix_csv(result.model_dump())


# ============================================================
# ③差別化ポイント
# ============================================================

class WhyNotRequest(BaseModel):
    target_kb_id: int
    other_kb_ids: list[int]
    pr_text: str = ""
    profile_text: str = ""
    messages: list[MessageSchema] = []


class DifferentiatorSchema(BaseModel):
    point: str
    vs_others: str = ""


class WhyNotResponse(BaseModel):
    target_name: str
    differentiators: list[DifferentiatorSchema]
    answer_template: str
    ok: bool
    error_msg: str | None = None


@router.post("/why-not-others", response_model=WhyNotResponse)
async def generate_why_not_others(req: WhyNotRequest) -> WhyNotResponse:
    if not req.other_kb_ids:
        raise HTTPException(status_code=400, detail="比較対象となる他社をもう1社以上指定してください。")
    history = _history(req.profile_text, req.messages)
    try:
        result = await CompanyMatrixService.generate_why_not(
            req.target_kb_id, req.other_kb_ids, req.pr_text, history,
        )
    except CompanyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GenerationFailedError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return WhyNotResponse(**result)
