# -*- coding: utf-8 -*-
"""
services/company_matrix_service.py
--------------------------------------
「企業比較マトリクス」機能のビジネスロジック。

既存コードとの対応:
  streamlit版 page_modules/company_matrix_page.py が相当する。
  company_matrix.py は shared/ に一本化済み（utils にのみ依存するため）。
  db.knowledge_base_repository.py → 企業KB（種別 "company"）の読み込み
  rag.persistence.load_active_documents → KB本文の読み込み

ステート方針:
  選択企業・追加比較軸・自己PRはフロントエンドが保持し、毎回のリクエストで渡す
  （他のインタビュー系機能と同様のステートレス設計）。
"""
from __future__ import annotations

import asyncio

from company_matrix import (
    MAX_COMPANIES,
    MATRIX_AXES_FIXED,
    VALUE_FIT_AXIS_KEY,
    VALUE_FIT_NOTE,
    generate_motivation_for_all,
    generate_comparison_matrix,
    generate_why_not_others,
    export_matrix_to_csv_rows,
)
from db.knowledge_base_repository import list_knowledge_bases, get_knowledge_base
from rag.persistence import load_active_documents
from db.settings_repository import get_setting

DEFAULT_CHAT_MODEL = "qwen3:8b"


def _model() -> str:
    return get_setting("chat_model") or DEFAULT_CHAT_MODEL


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


class CompanyNotFoundError(ValueError):
    """指定された企業KBが見つからない、または種別が company でない場合に送出する。"""


class GenerationFailedError(RuntimeError):
    """LLM生成が例外を送出した場合に送出する。"""


class CompanyMatrixService:

    @staticmethod
    def _build_company_dict_sync(kb_id: int) -> dict:
        kb = get_knowledge_base(kb_id)
        if kb is None or kb.get("kb_type") != "company":
            raise CompanyNotFoundError(f"企業KB(id={kb_id})が見つかりません。")
        docs = load_active_documents([kb_id])
        info_text = "\n".join(chunk for doc in docs for chunk in doc.chunks)
        return {"name": kb.get("name", "企業名不明"), "info": info_text, "industry": ""}

    @classmethod
    async def _build_companies(cls, kb_ids: list[int]) -> list[dict]:
        kb_ids = kb_ids[:MAX_COMPANIES]
        return [await _run(cls._build_company_dict_sync, kb_id) for kb_id in kb_ids]

    @classmethod
    async def list_company_kbs(cls) -> list[dict]:
        """種別 "company" のナレッジベース一覧を返す（企業選択UI用）。"""
        return await _run(list_knowledge_bases, "company")

    # ── ①志望動機（一括） ────────────────────────────────────

    @classmethod
    async def generate_motivations(
        cls, company_kb_ids: list[int], pr_text: str, conversation_history: str,
    ) -> list[dict]:
        companies = await cls._build_companies(company_kb_ids)
        model = await _run(_model)
        try:
            return await _run(
                generate_motivation_for_all, model, companies, pr_text, conversation_history,
            )
        except Exception as e:
            raise GenerationFailedError(str(e)) from e

    # ── ②比較マトリクス ──────────────────────────────────────

    @classmethod
    async def generate_matrix(
        cls, company_kb_ids: list[int], pr_text: str, additional_axes: list[str],
    ) -> dict:
        companies = await cls._build_companies(company_kb_ids)
        model = await _run(_model)
        try:
            return await _run(
                generate_comparison_matrix, model, companies, pr_text, additional_axes,
            )
        except Exception as e:
            raise GenerationFailedError(str(e)) from e

    @staticmethod
    async def export_matrix_csv(matrix_result: dict) -> str:
        return await _run(export_matrix_to_csv_rows, matrix_result)

    # ── ③差別化ポイント ──────────────────────────────────────

    @classmethod
    async def generate_why_not(
        cls,
        target_kb_id: int,
        other_kb_ids: list[int],
        pr_text: str,
        conversation_history: str,
    ) -> dict:
        target = await _run(cls._build_company_dict_sync, target_kb_id)
        others = await cls._build_companies(other_kb_ids)
        model = await _run(_model)
        try:
            return await _run(
                generate_why_not_others, model, target, others, pr_text, conversation_history,
            )
        except Exception as e:
            raise GenerationFailedError(str(e)) from e


__all__ = [
    "CompanyMatrixService",
    "CompanyNotFoundError",
    "GenerationFailedError",
    "MAX_COMPANIES",
    "MATRIX_AXES_FIXED",
    "VALUE_FIT_AXIS_KEY",
    "VALUE_FIT_NOTE",
]
