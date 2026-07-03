# -*- coding: utf-8 -*-
"""
services/interview_flow_service.py
-------------------------------------
「自己PR引き出しインタビュー」フロー全体（②〜⑤⑦）のビジネスロジック。

既存コードとの対応:
  streamlit版 page_modules/interview/ 一式（page.py, interview_ui.py,
  summary_section.py, pr_generation_section.py, pr_evaluation_section.py,
  company_pr_section.py）が相当する。

  interview_engine.py / pr_generation.py / summary_generation.py は
  shared/ に一本化済み（utils にのみ依存するため）。

ステート方針:
  mock-interview（services/interview_service.py）と同じく、サーバー側に
  会話状態を持たないステートレス設計。フロントエンドが `messages`
  （画面表示用の全履歴）と、テーマ内の `theme_messages` を保持し、
  毎回のリクエストで渡す。

  Streamlit版の build_conversation_history() 相当のテキスト整形も
  ここに実装し、TypeScript側で日本語ラベルの整形ロジックを重複させない。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from interview_engine import (
    THEMES,
    CATEGORY_OPTIONS,
    get_first_question_for_theme,
    judge_and_generate_next_question,
)
from pr_generation import (
    generate_pr_variants,
    evaluate_pr,
    generate_company_pr,
    refine_pr,
)
from summary_generation import generate_interview_summary
from services.rag_helpers import build_conversation_history, build_rag_block_from_active_kbs
from db.settings_repository import get_setting

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ============================================================
# ②インタビュー本体
# ============================================================

@dataclass
class QuestionResult:
    status: Literal["question", "awaiting_category_choice", "complete"]
    theme_index: int = 0
    theme_title: str = ""
    question: str = ""
    questions_asked_in_theme: int = 0
    category_options: list[str] = field(default_factory=list)


class InterviewFlowService:

    @staticmethod
    def _prev_exchange(messages: list[dict]) -> str | None:
        """直近のやり取り（面接官の質問＋学生の回答）をテーマ移行プロンプト用に整形する。"""
        if not messages:
            return None
        recent = messages[-2:]
        return "\n".join(
            f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}" for m in recent
        )

    @classmethod
    async def start(cls, profile_text: str) -> QuestionResult:
        """最初のテーマの最初の質問を生成する。"""
        theme = THEMES[0]
        model = await _run(_model)
        result = await _run(get_first_question_for_theme, model, theme, None, None, profile_text)
        return QuestionResult(
            status="question",
            theme_index=0,
            theme_title=theme["title"],
            question=result["question"],
            questions_asked_in_theme=1,
        )

    @classmethod
    async def _advance_to_theme(
        cls, new_index: int, messages: list[dict], profile_text: str,
    ) -> QuestionResult:
        if new_index >= len(THEMES):
            return QuestionResult(status="complete")

        theme = THEMES[new_index]
        if theme["needs_category_choice"]:
            return QuestionResult(
                status="awaiting_category_choice",
                theme_index=new_index,
                theme_title=theme["title"],
                category_options=CATEGORY_OPTIONS,
            )

        model = await _run(_model)
        prev_last = cls._prev_exchange(messages)
        result = await _run(get_first_question_for_theme, model, theme, None, prev_last, profile_text)
        return QuestionResult(
            status="question",
            theme_index=new_index,
            theme_title=theme["title"],
            question=result["question"],
            questions_asked_in_theme=1,
        )

    @classmethod
    async def next_question(
        cls,
        theme_index: int,
        theme_messages: list[dict],
        questions_asked_in_theme: int,
        selected_category: str | None,
        profile_text: str,
        messages: list[dict],
    ) -> QuestionResult:
        """回答を判定し、テーマ継続 or 次テーマへの移行を行う。

        Args:
            theme_messages: 現在のテーマ内の会話（直近の学生の回答を含む、追加済みの状態）
            messages: 画面表示用の全履歴（テーマ移行時の prev_exchange 算出に使う）
        """
        theme = THEMES[theme_index]
        model = await _run(_model)
        result = await _run(
            judge_and_generate_next_question,
            model, theme, theme_messages, questions_asked_in_theme, selected_category, profile_text,
        )
        if result["continue"] and result["question"]:
            return QuestionResult(
                status="question",
                theme_index=theme_index,
                theme_title=theme["title"],
                question=result["question"],
                questions_asked_in_theme=questions_asked_in_theme + 1,
            )
        return await cls._advance_to_theme(theme_index + 1, messages, profile_text)

    @classmethod
    async def choose_category(
        cls, theme_index: int, category: str, messages: list[dict], profile_text: str,
    ) -> QuestionResult:
        """カテゴリ選択後、そのテーマの最初の質問を生成する。"""
        theme = THEMES[theme_index]
        model = await _run(_model)
        prev_exchange = cls._prev_exchange(messages)
        result = await _run(get_first_question_for_theme, model, theme, category, prev_exchange, profile_text)
        return QuestionResult(
            status="question",
            theme_index=theme_index,
            theme_title=theme["title"],
            question=result["question"],
            questions_asked_in_theme=1,
        )

    # ============================================================
    # ③面接サマリー
    # ============================================================

    @classmethod
    async def generate_summary(cls, profile_text: str, messages: list[dict]) -> dict:
        history = build_conversation_history(profile_text, messages)
        model = await _run(_model)
        result = await _run(generate_interview_summary, model, history)
        if not result or not result.get("ok"):
            raise RuntimeError((result or {}).get("error_msg") or "サマリーの生成に失敗しました。")
        return result

    # ============================================================
    # ④自己PR生成
    # ============================================================

    @classmethod
    async def generate_variants(cls, profile_text: str, messages: list[dict]) -> list[dict]:
        history = build_conversation_history(profile_text, messages)
        rag_block = await _run(build_rag_block_from_active_kbs, history)
        model = await _run(_model)
        variants = await _run(generate_pr_variants, model, history, rag_block)
        if not variants:
            raise RuntimeError("自己PRの生成に失敗しました。Ollamaが起動しているかご確認ください。")
        return variants


    # ============================================================
    # ⑤PR評価・微調整
    # ============================================================

    @classmethod
    async def evaluate(cls, pr_text: str) -> dict:
        model = await _run(_model)
        result = await _run(evaluate_pr, model, pr_text)
        if result is None:
            raise RuntimeError("自己PRの評価に失敗しました。")
        return result

    @classmethod
    async def refine(
        cls, pr_text: str, instruction: str, profile_text: str, messages: list[dict],
    ) -> dict:
        history = build_conversation_history(profile_text, messages)
        model = await _run(_model)
        result = await _run(refine_pr, model, pr_text, instruction, history)
        return result

    # ============================================================
    # ⑦企業別カスタマイズPR
    # ============================================================

    @classmethod
    async def generate_company_prs(
        cls,
        base_pr: str,
        companies: list[dict],
        profile_text: str,
        messages: list[dict],
    ) -> list[dict]:
        """複数企業分のカスタマイズPRをまとめて生成する（Streamlit版の逐次ループを踏襲）。"""
        history = build_conversation_history(profile_text, messages)
        model = await _run(_model)
        results = []
        for entry in companies:
            result = await _run(
                generate_company_pr, model, base_pr, entry["name"], entry["info"], history,
            )
            results.append(result)
        return results
