# -*- coding: utf-8 -*-
"""
services/interview_service.py
------------------------------
模擬面接のビジネスロジックを APIルーターから分離したサービス層。

ルーターは HTTP の入出力だけを担い、
エンジン呼び出し・状態変換・エラーハンドリングは全てここで行う。

同期エンジン関数（persona_engine / mock_interview_engine）は
asyncio.get_running_loop().run_in_executor() でスレッドプールに逃がし、
FastAPI のイベントループをブロックしないようにする。

[変更点]
- asyncio.get_event_loop() → asyncio.get_running_loop() に変更
  Python 3.10 以降で get_event_loop() はイベントループが存在しない文脈で
  DeprecationWarning を出す。get_running_loop() は常に現在のループを
  確実に取得でき、コルーチン外（= ループが存在しない）での誤用を
  TypeError で早期に検知できる。

- evaluate() のスコア変換にゼロ除算ガードを追加し、
  空スコア時の意図をコメントで明示。

- SSE エラーイベントのログを ERROR レベルで出力するよう統一。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from db.settings_repository import get_setting

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


# ============================================================
# データクラス（サービス層の入出力型）
# ============================================================

@dataclass
class StartResult:
    theme_index: int
    theme_title: str
    question: str


@dataclass
class SseEvent:
    event: str   # "question" | "transition" | "finished" | "error"
    data: dict


# ============================================================
# ヘルパー: 同期関数を非同期で実行
# ============================================================

async def _run(fn, *args, **kwargs):
    """同期関数をデフォルトスレッドプールで実行し await 可能にする。

    asyncio.get_running_loop() を使うことで:
    - Python 3.10+ の DeprecationWarning を回避する
    - コルーチン外で誤って呼んだ場合に RuntimeError で即座に気づける
      （get_event_loop() は暗黙にループを生成してしまい、バグが潜伏する）
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ============================================================
# InterviewService
# ============================================================

class InterviewService:
    """
    模擬面接の開始・回答処理・評価を担うサービス。
    ルーターから import して使う（インスタンス不要、クラスメソッド構成）。
    """

    # ── ペルソナ一覧 ────────────────────────────────────────────

    @staticmethod
    async def list_personas() -> list[dict]:
        from persona_engine import list_personas
        return await _run(list_personas)

    # ── テーマ一覧 ──────────────────────────────────────────────

    @staticmethod
    async def list_themes(industry_key: str = "general") -> list[dict]:
        from mock_interview_engine import get_active_themes
        themes = await _run(get_active_themes, industry_key)
        return [
            {"index": i, "key": t["key"], "title": t["title"]}
            for i, t in enumerate(themes)
        ]

    # ── 面接開始（最初の質問を生成）────────────────────────────

    @staticmethod
    async def start(
        industry_key: str,
        persona_key: str,
        profile_text: str,
        rag_block: str | None,
        predicted_questions: list[dict] | None,
    ) -> StartResult:
        from mock_interview_engine import get_active_themes
        from persona_engine import get_first_question_for_theme

        model = _model()
        themes = await _run(get_active_themes, industry_key)
        if not themes:
            raise ValueError(f"業界 '{industry_key}' のテーマが見つかりません")

        theme = themes[0]
        result = await _run(
            get_first_question_for_theme,
            model=model,
            persona_key=persona_key,
            theme=theme,
            previous_theme_last_exchange=None,
            profile_text=profile_text or None,
            rag_block=rag_block,
            predicted_questions=predicted_questions,
            used_question_indices=set(),
            industry_key=industry_key,
        )

        return StartResult(
            theme_index=0,
            theme_title=theme["title"],
            question=result["question"],
        )

    # ── 回答処理（SSE イベントを生成）──────────────────────────

    @staticmethod
    async def answer_stream(
        theme_index: int,
        followups_asked: int,
        messages: list[dict],
        industry_key: str,
        persona_key: str,
        profile_text: str,
        rag_block: str | None,
        predicted_questions: list[dict] | None,
    ) -> AsyncIterator[SseEvent]:
        """
        回答を受け取り、次のアクション（深掘り / テーマ遷移 / 終了）を
        SSE イベントとして非同期に yield する。

        呼び出し側は `async for event in InterviewService.answer_stream(...)` で受け取る。

        Note: SSE はヘッダー送信後にエラーが起きても HTTP 200 のまま流れる仕様。
        フロント側は必ず `event: error` をハンドリングすること。
        """
        from mock_interview_engine import get_active_themes, is_interview_finished, get_theme
        from persona_engine import get_first_question_for_theme, judge_and_generate_followup

        model = _model()

        try:
            themes = await _run(get_active_themes, industry_key)

            if theme_index >= len(themes):
                logger.error("answer_stream: theme_index=%d が範囲外 (全%d件)", theme_index, len(themes))
                yield SseEvent("error", {"message": "Invalid theme_index"})
                return

            theme = themes[theme_index]

            # ── 深掘り判定（同期→スレッドプール）──────────────
            followup_result = await _run(
                judge_and_generate_followup,
                model=model,
                persona_key=persona_key,
                theme=theme,
                theme_messages=messages,
                followups_asked_in_theme=followups_asked,
                profile_text=profile_text or None,
                rag_block=rag_block,
                industry_key=industry_key,
            )

            if followup_result.get("continue") and followup_result.get("question"):
                yield SseEvent("question", {
                    "text": followup_result["question"],
                    "is_followup": True,
                    "theme_index": theme_index,
                })
                return

            # ── 次テーマへ ──────────────────────────────────────
            next_index = theme_index + 1
            finished = await _run(is_interview_finished, next_index, industry_key)

            if finished:
                yield SseEvent("finished", {"message": "面接が終了しました"})
                return

            next_theme = await _run(get_theme, next_index, industry_key)
            yield SseEvent("transition", {
                "theme_index": next_index,
                "theme_title": next_theme["title"],
            })

            # 直前テーマの最後のやり取り（つなぎ文生成用）
            last_exchange: str | None = None
            if messages:
                tail = messages[-2:] if len(messages) >= 2 else messages
                last_exchange = "\n".join(
                    f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}"
                    for m in tail
                )

            next_result = await _run(
                get_first_question_for_theme,
                model=model,
                persona_key=persona_key,
                theme=next_theme,
                previous_theme_last_exchange=last_exchange,
                profile_text=profile_text or None,
                rag_block=rag_block,
                predicted_questions=predicted_questions,
                used_question_indices=set(),
                industry_key=industry_key,
            )

            yield SseEvent("question", {
                "text": next_result["question"],
                "is_followup": False,
                "theme_index": next_index,
            })

        except Exception as exc:
            logger.exception("InterviewService.answer_stream error")
            yield SseEvent("error", {"message": str(exc)})

    # ── 終了後評価 ──────────────────────────────────────────────

    @staticmethod
    async def evaluate(
        messages: list[dict],
        industry_key: str,
        profile_text: str,
        rag_block: str | None,
    ) -> dict:
        from mock_interview_engine import (
            generate_mock_interview_evaluation,
            build_full_history_text,
        )

        model = _model()
        full_history = await _run(build_full_history_text, messages)
        result = await _run(
            generate_mock_interview_evaluation,
            model=model,
            full_history=full_history,
            industry_key=industry_key,
            profile_text=profile_text or None,
            rag_block=rag_block,
        )

        if not result.get("ok"):
            raise RuntimeError(result.get("error_msg", "Evaluation failed"))

        # ── スコア変換: バックエンド(1-5) → フロント(0-100%) ──────────────
        # scores が空の場合（LLM が軸を返せなかった等）は overall_score=0 とし、
        # フロント側でエラーではなく「評価データなし」として扱う。
        raw_scores: dict = result.get("scores", {})
        if raw_scores:
            axes = {k: round(v / 5 * 100) for k, v in raw_scores.items()}
            overall_score = round(sum(axes.values()) / len(axes))
        else:
            # スコアが空 = LLM の応答が不完全。0 を返して UI 側で案内する。
            logger.warning("evaluate: scores が空です。LLM の応答を確認してください。")
            axes = {}
            overall_score = 0

        return {
            "overall_score": overall_score,
            "axes": axes,
            "strengths":    result.get("top_strengths", []),
            "improvements": result.get("top_improvements", []),
            "next_steps":   result.get("next_practice_points", []),
            "overall_summary": result.get("overall_summary", ""),
            "model_answers":   result.get("model_answers", []),
            "ok": result["ok"],
        }


# ============================================================
# SSE フォーマット変換ユーティリティ
# ============================================================

def format_sse(event: SseEvent) -> str:
    """SseEvent を SSE テキスト形式に変換する。"""
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


async def sse_generator(
    stream: AsyncIterator[SseEvent],
) -> AsyncIterator[str]:
    """SseEvent の非同期イテレータを SSE テキストストリームに変換する。"""
    async for event in stream:
        yield format_sse(event)
