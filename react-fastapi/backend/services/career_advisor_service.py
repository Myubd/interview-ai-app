# -*- coding: utf-8 -*-
"""
services/career_advisor_service.py
--------------------------------------
「AIキャリアアドバイザー」機能のうち、DB永続化に依存する部分
（保存済みセッションからのコンテキスト構築）を担当する。
プロンプト・LLM呼び出し本体は career_advisor.py（shared/ に一本化済み）。

既存コードとの対応:
  streamlit版 page_modules/career_page.py の _build_advisor_context() が相当する。

Streamlit版との違い:
  streamlit版はグローバルな st.session_state（1つの面接フロー分の情報）を
  そのまま参照するが、React版はページごとに状態が独立しているため、
  「保存済みセッション（sessions テーブル）」を選んでもらい、そこから
  面接内容・自己PR・模擬面接評価・性格診断結果をまとめて読み込む。
"""
from __future__ import annotations

import asyncio
import json

from career_advisor import generate_career_advice
from db.session_repository import get_session, list_sessions
from db.personality_repository import get_personality_result
from db.settings_repository import get_setting

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _loads(raw, default):
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _build_context_sync(session_id: int) -> str:
    """_build_advisor_context() 相当。保存済みセッション+診断結果からコンテキスト文字列を組み立てる。"""
    data = get_session(session_id)
    if data is None:
        return ""
    session = data["session"]
    messages = data["messages"]
    parts: list[str] = []

    if session.get("profile_text"):
        parts.append(f"【学生プロフィール（事前入力）】\n{session['profile_text']}")

    if messages:
        lines = [f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}" for m in messages]
        parts.append("【自己PRインタビュー履歴】\n" + "\n".join(lines))

    if session.get("final_pr"):
        parts.append(f"【完成した自己PR】\n{session['final_pr']}")

    summary = _loads(session.get("interview_summary"), None)
    if summary:
        strength_lines = [f"・{s['point']}: {s['evidence']}" for s in summary.get("strengths", [])]
        weakness_lines = [f"・{w['point']}: {w['evidence']}" for w in summary.get("weaknesses", [])]
        fit_lines = [
            f"・{k}: {v['score']}点 ({v.get('reason', '')})"
            for k, v in summary.get("industry_fit", {}).items()
        ]
        summary_text = (
            "【面接サマリー】\n"
            + (("強み:\n" + "\n".join(strength_lines) + "\n") if strength_lines else "")
            + (("成長余地:\n" + "\n".join(weakness_lines) + "\n") if weakness_lines else "")
            + (("業界別フィット度:\n" + "\n".join(fit_lines) + "\n") if fit_lines else "")
            + (f"向いている職種・環境: {summary.get('fit_roles', '')}\n" if summary.get("fit_roles") else "")
            + (f"総評: {summary.get('overall_comment', '')}" if summary.get("overall_comment") else "")
        )
        parts.append(summary_text)

    pa_row = get_personality_result(session_id)
    if pa_row and pa_row.get("pa_axis_scores"):
        pa_result = _loads(pa_row.get("pa_result"), {})
        pa_scores = pa_row["pa_axis_scores"]
        score_lines = [f"・{k}: {v:.1f}/5" for k, v in pa_scores.items()]
        pa_text = (
            "【性格診断結果（ビッグファイブ）】\n"
            + "\n".join(score_lines) + "\n"
            + (f"サマリー: {pa_result.get('personality_summary', '')}" if pa_result.get("personality_summary") else "")
        )
        if pa_result.get("interview_tips"):
            pa_text += f"\n面接での活かし方: {pa_result['interview_tips']}"
        parts.append(pa_text)

    mock_eval = _loads(session.get("mock_interview_evaluation"), None)
    if mock_eval:
        score_lines = [f"・{k}: {v}/5" for k, v in mock_eval.get("scores", {}).items()]
        mock_text = (
            "【模擬面接評価】\n"
            + f"総合評価: {mock_eval.get('overall_summary', '')}\n"
            + ("スコア:\n" + "\n".join(score_lines) + "\n" if score_lines else "")
            + ("強みTOP3: " + " / ".join(mock_eval.get("top_strengths", [])) + "\n")
            + ("改善点TOP3: " + " / ".join(mock_eval.get("top_improvements", [])) + "\n")
            + ("次回練習ポイント: " + " / ".join(mock_eval.get("next_practice_points", [])))
        )
        parts.append(mock_text)

    company_prs = _loads(session.get("company_prs"), {})
    if company_prs:
        parts.append("【志望企業（カスタマイズPR作成済み）】\n" + "\n".join(f"・{n}" for n in company_prs.keys()))

    return "\n\n".join(parts)


class CareerAdvisorService:

    @staticmethod
    async def list_context_sessions() -> list[dict]:
        """コンテキストとして選択可能な保存済みセッション一覧を返す（履歴ページと同じ一覧）。"""
        return await _run(list_sessions)

    @classmethod
    async def build_context(cls, session_id: int | None) -> str:
        if session_id is None:
            return ""
        return await _run(cls._build_context_or_empty, session_id)

    @staticmethod
    def _build_context_or_empty(session_id: int) -> str:
        try:
            return _build_context_sync(session_id)
        except Exception:
            return ""

    @classmethod
    async def chat(
        cls,
        messages: list[dict],
        session_id: int | None = None,
    ) -> dict:
        """会話履歴（最後がユーザー発言）から、キャリアアドバイザーの返信を生成する。"""
        context_text = await cls.build_context(session_id)
        model = await _run(_model)
        return await _run(generate_career_advice, model, context_text, messages)


__all__ = ["CareerAdvisorService"]
