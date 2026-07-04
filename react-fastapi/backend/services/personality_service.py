# -*- coding: utf-8 -*-
"""
services/personality_service.py
----------------------------------
「性格診断・適性検査（ビッグファイブ30問）」のビジネスロジック。

既存コードとの対応:
  streamlit版 page_modules/personality_page.py が相当する。
  personality_assessment.py は shared/ に一本化済み（utils にのみ依存するため）。
  db.personality_repository.py → 診断結果の保存・取得
  db.favorites_repository.py   → お気に入り登録

ステート方針:
  診断の設問回答（pa_answers）自体はフロントエンドが保持し、結果生成時に
  まとめて送る（他のインタビュー系機能と同様のステートレス設計）。
  生成結果を保存する場合のみ、personality_results テーブルに永続化する。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from personality_assessment import (
    AXES,
    QUESTIONS,
    SCALE_LABELS,
    TOTAL_QUESTIONS,
    compute_axis_scores,
    generate_personality_result,
)
from db.personality_repository import save_personality_result, get_personality_result
from db.session_repository import save_session
from db.favorites_repository import add_favorite
from db.settings_repository import get_setting

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


class GenerationFailedError(RuntimeError):
    """LLM生成がリトライしても失敗した場合に送出する。"""


@dataclass
class QuestionsInfo:
    axes: dict[str, str] = field(default_factory=dict)
    questions: list[dict] = field(default_factory=list)
    scale_labels: dict[int, str] = field(default_factory=dict)
    total_questions: int = 0


class PersonalityService:

    @staticmethod
    def get_questions() -> QuestionsInfo:
        """設問一覧・軸ラベル・回答スケールを返す（画面表示用の静的データ）。"""
        return QuestionsInfo(
            axes=AXES,
            questions=QUESTIONS,
            scale_labels=SCALE_LABELS,
            total_questions=TOTAL_QUESTIONS,
        )

    @classmethod
    async def submit(cls, answers: dict[int, int]) -> dict:
        """回答からスコアを集計し、AIによる診断結果を生成する。

        Raises:
            GenerationFailedError: LLM生成がリトライしても失敗した場合
        """
        axis_scores = await _run(compute_axis_scores, answers)
        model = await _run(_model)
        result = await _run(generate_personality_result, model, answers, axis_scores)

        if not result.get("ok", False):
            raise GenerationFailedError(result.get("error_msg") or "性格診断の生成に失敗しました。")

        result["axis_scores"] = axis_scores
        return result

    @staticmethod
    def _save_and_favorite_sync(
        session_id: int | None,
        answers: dict[int, int],
        axis_scores: dict[str, float],
        result: dict,
        company_name: str | None,
    ) -> tuple[int, int]:
        if session_id is None:
            session_id = save_session(
                company_name=company_name,
                session_type="personality",
                json_values={},
            )
        save_personality_result(
            session_id=session_id,
            pa_answers=answers,
            pa_axis_scores=axis_scores,
            pa_result=result,
        )
        favorite_id = add_favorite(
            item_type="personality",
            session_id=session_id,
            company_name=company_name,
            label="性格診断結果",
            content_snapshot={"summary": (result.get("personality_summary") or "")[:80]},
        )
        return session_id, favorite_id

    @classmethod
    async def save_and_favorite(
        cls,
        answers: dict[int, int],
        axis_scores: dict[str, float],
        result: dict,
        session_id: int | None = None,
        company_name: str | None = None,
    ) -> tuple[int, int]:
        """診断結果をセッションとして保存し、お気に入りに登録する。

        session_id を指定しない場合は、この診断専用の新規セッションを作成する
        （streamlit版のような「先にサイドバーからセッション保存」という前提を
        撤廃し、想定質問生成と同様にお気に入り保存時に暗黙的に作成する）。

        Returns:
            (session_id, favorite_id)
        """
        return await _run(
            cls._save_and_favorite_sync, session_id, answers, axis_scores, result, company_name,
        )

    @classmethod
    async def get_saved_result(cls, session_id: int) -> dict | None:
        """指定セッションに紐づく保存済みの診断結果を返す。"""
        return await _run(get_personality_result, session_id)


__all__ = ["PersonalityService", "GenerationFailedError", "QuestionsInfo"]
