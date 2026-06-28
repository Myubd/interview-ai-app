"""
api/routes/sessions.py
-----------------------
面接セッションの CRUD エンドポイント。

既存コードとの対応:
  db/session_repository.py → save_session / list_sessions / get_session / delete_session
    - save_session は keyword-only 引数で _UNSET sentinel を使っている
    - get_session は {"session": {...}, "messages": [...]} を返す
    - list_sessions はメタ情報のみのリスト

[変更点]
- GET /dashboard エンドポイントを追加。
  全セッションの mock_interview_evaluation を集計し、
  スコア推移・軸別推移・統計サマリーをまとめて返す。
  フロントの DashboardPage がこのエンドポイントだけで描画できるよう設計。
"""
from __future__ import annotations

import json
import logging
from statistics import mean

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
# ダッシュボード（スコア集計）
# ============================================================

@router.get("/dashboard")
async def get_dashboard() -> dict:
    """全評価済みセッションのスコアを集計してダッシュボード用データを返す。

    Returns:
        {
          "total_sessions": int,          # 全セッション数
          "evaluated_sessions": int,       # 評価済みセッション数
          "avg_overall_score": float,      # 総合スコア平均
          "best_overall_score": int,       # 最高総合スコア
          "score_trend": [                 # 時系列スコア推移（古い順）
            {
              "session_id": int,
              "company_name": str | None,
              "created_at": str,
              "overall_score": int,
              "axes": {axis_key: score, ...}
            }, ...
          ],
          "axes_avg": {axis_key: float, ...},  # 軸別平均スコア
          "axes_keys": [str, ...],             # 全軸キーのリスト（グラフの凡例用）
        }
    """
    all_sessions = list_sessions()
    total = len(all_sessions)

    trend: list[dict] = []
    axes_accumulator: dict[str, list[float]] = {}

    # 評価済みセッションのみ詳細を取得してスコアを集計
    for meta in all_sessions:
        if not meta.get("has_mock_evaluation"):
            continue

        detail = get_session(meta["id"])
        if detail is None:
            continue

        raw_eval = detail["session"].get("mock_interview_evaluation")
        if not raw_eval:
            continue

        # DB から取得した評価は JSON 文字列の場合がある
        if isinstance(raw_eval, str):
            try:
                raw_eval = json.loads(raw_eval)
            except (ValueError, TypeError):
                continue

        overall_score = raw_eval.get("overall_score")
        axes: dict = raw_eval.get("axes", {})

        if overall_score is None:
            continue

        trend.append({
            "session_id":   meta["id"],
            "company_name": meta.get("company_name"),
            "created_at":   meta["created_at"],
            "overall_score": int(overall_score),
            "axes": {k: int(v) for k, v in axes.items()},
        })

        for k, v in axes.items():
            axes_accumulator.setdefault(k, []).append(float(v))

    # 時系列は古い順（グラフの左→右が時間軸）
    trend.sort(key=lambda x: x["created_at"])

    evaluated = len(trend)
    avg_overall = round(mean(t["overall_score"] for t in trend), 1) if trend else 0.0
    best_overall = max((t["overall_score"] for t in trend), default=0)
    axes_avg = {k: round(mean(v), 1) for k, v in axes_accumulator.items()}

    # 軸キーは最新セッションの順序を保持（グラフ凡例の安定化）
    axes_keys: list[str] = []
    for t in reversed(trend):
        for k in t["axes"]:
            if k not in axes_keys:
                axes_keys.append(k)

    return {
        "total_sessions":    total,
        "evaluated_sessions": evaluated,
        "avg_overall_score": avg_overall,
        "best_overall_score": best_overall,
        "score_trend":       trend,
        "axes_avg":          axes_avg,
        "axes_keys":         axes_keys,
    }


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
