# -*- coding: utf-8 -*-
"""
services/prediction_service.py
--------------------------------
「想定質問生成」（RAGベース版）のビジネスロジックを
APIルーターから分離したサービス層。

既存コードとの対応:
  question_prediction.generate_predicted_questions_from_rag() → LLM生成本体（shared/、utils にのみ依存）
  rag.persistence.load_active_documents() / rag.core.format_context() → 履歴書・企業KBの読み込み
  db.knowledge_base_repository.get_or_create_knowledge_base() → 共通履歴書KBの解決
  db.session_repository.save_session() → お気に入り登録用のセッション作成
  db.favorites_repository.add_favorite() → お気に入り登録

InterviewService と同様、同期関数（question_prediction / rag）は
asyncio.get_running_loop().run_in_executor() でスレッドプールに逃がし、
FastAPI のイベントループをブロックしないようにする。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from question_prediction import (
    generate_predicted_questions_from_rag,
    generate_predicted_questions,
    CATEGORY_LABELS,
)
from rag.persistence import (
    get_or_create_knowledge_base,
    load_active_documents,
    RESUME_KB_NAME,
)
from rag.core import format_context
from services.rag_helpers import build_conversation_history, build_rag_block_from_active_kbs
from db.knowledge_base_repository import get_knowledge_base
from db.session_repository import save_session
from db.favorites_repository import add_favorite
from db.settings_repository import get_setting

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


async def _run(fn, *args, **kwargs):
    """同期関数をデフォルトスレッドプールで実行し await 可能にする。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


# ============================================================
# データクラス（サービス層の入出力型）
# ============================================================

@dataclass
class PredictedQuestion:
    category: str
    category_label: str
    question: str
    model_answer: str


@dataclass
class GenerateResult:
    questions: list[PredictedQuestion] = field(default_factory=list)


class InsufficientMaterialError(ValueError):
    """履歴書・企業情報のどちらも見つからなかった場合に送出する。"""


class GenerationFailedError(RuntimeError):
    """LLM生成がリトライしても失敗した場合に送出する。"""


# ============================================================
# PredictionService
# ============================================================

class PredictionService:

    @staticmethod
    def _load_blocks_sync(company_kb_id: int) -> tuple[str, str]:
        """履歴書KB・企業KBからテキストを読み込み、RAG用ブロック文字列を返す。"""
        resume_kb_id = get_or_create_knowledge_base(RESUME_KB_NAME, "resume")
        documents = load_active_documents([resume_kb_id, company_kb_id])

        resume_results = [
            (d.doc_type, c, 1.0) for d in documents if d.doc_type == "resume" for c in d.chunks
        ]
        company_results = [
            (d.doc_type, c, 1.0) for d in documents if d.doc_type == "company" for c in d.chunks
        ]
        resume_block = format_context(resume_results)
        company_block = format_context(company_results)
        return resume_block, company_block

    @classmethod
    async def generate(cls, company_kb_id: int) -> GenerateResult:
        """指定した企業KBと共通履歴書KBから想定質問セットを生成する。

        Raises:
            InsufficientMaterialError: 履歴書・企業情報のどちらも見つからない場合
            GenerationFailedError: LLM生成がリトライしても失敗した場合
        """
        kb = await _run(get_knowledge_base, company_kb_id)
        if kb is None or kb.get("kb_type") != "company":
            raise InsufficientMaterialError("指定された企業のナレッジベースが見つかりません。")

        resume_block, company_block = await _run(cls._load_blocks_sync, company_kb_id)

        if not resume_block.strip() and not company_block.strip():
            raise InsufficientMaterialError(
                "履歴書・企業情報のどちらも見つかりませんでした。"
                "サイドバーから資料をアップロードしてください。"
            )

        model = await _run(_model)
        questions, ok, error_msg = await _run(
            generate_predicted_questions_from_rag, model, resume_block, company_block
        )

        if not ok or not questions:
            raise GenerationFailedError(error_msg or "想定質問の生成に失敗しました。")

        return GenerateResult(
            questions=[
                PredictedQuestion(
                    category=q["category"],
                    category_label=q.get("category_label", CATEGORY_LABELS.get(q["category"], "📝 その他")),
                    question=q["question"],
                    model_answer=q["model_answer"],
                )
                for q in questions
            ]
        )

    @staticmethod
    def _save_and_favorite_sync(
        company_kb_id: int,
        company_name: str,
        questions: list[dict],
    ) -> tuple[int, int]:
        session_id = save_session(
            company_name=company_name,
            session_type="question_set",
            knowledge_base_id=company_kb_id,
            json_values={"predicted_questions": questions},
        )
        favorite_id = add_favorite(
            item_type="question_set",
            session_id=session_id,
            company_name=company_name,
            label=f"想定質問 - {company_name}",
            content_snapshot={"question_count": len(questions)},
        )
        return session_id, favorite_id

    @classmethod
    async def save_and_favorite(
        cls,
        company_kb_id: int,
        company_name: str,
        questions: list[dict],
    ) -> tuple[int, int]:
        """生成済みの想定質問セットをセッションとして保存し、お気に入りに登録する。

        Returns:
            (session_id, favorite_id)
        """
        return await _run(cls._save_and_favorite_sync, company_kb_id, company_name, questions)

    # ============================================================
    # ⑥想定質問（自己PR＋会話履歴ベース版）
    # ------------------------------------------------------------
    # streamlit版 page_modules/interview/predicted_questions_section.py が相当。
    # 特定の企業KBではなく、アクティブな全KB + 完成した自己PR + インタビュー全履歴
    # を根拠に質問を生成する（generate() とは入力も呼び出す関数も異なる）。
    # ============================================================

    @classmethod
    async def generate_from_pr(
        cls, pr_text: str, profile_text: str, messages: list[dict],
    ) -> GenerateResult:
        history = await _run(build_conversation_history, profile_text, messages)
        rag_block = await _run(build_rag_block_from_active_kbs, history)
        model = await _run(_model)
        questions, ok, error_msg = await _run(
            generate_predicted_questions, model, pr_text, history, rag_block
        )
        if not ok or not questions:
            raise GenerationFailedError(error_msg or "想定質問の生成に失敗しました。")
        return GenerateResult(
            questions=[
                PredictedQuestion(
                    category=q["category"],
                    category_label=q.get("category_label", CATEGORY_LABELS.get(q["category"], "📝 その他")),
                    question=q["question"],
                    model_answer=q["model_answer"],
                )
                for q in questions
            ]
        )

    @staticmethod
    def _save_and_favorite_pr_based_sync(
        company_name: str | None, questions: list[dict],
    ) -> tuple[int, int]:
        session_id = save_session(
            company_name=company_name,
            session_type="question_set",
            knowledge_base_id=None,
            json_values={"predicted_questions": questions},
        )
        favorite_id = add_favorite(
            item_type="question_set",
            session_id=session_id,
            company_name=company_name,
            label="想定質問セット（自己PRより）",
            content_snapshot={"question_count": len(questions)},
        )
        return session_id, favorite_id

    @classmethod
    async def save_and_favorite_pr_based(
        cls, questions: list[dict], company_name: str | None = None,
    ) -> tuple[int, int]:
        return await _run(cls._save_and_favorite_pr_based_sync, company_name, questions)
