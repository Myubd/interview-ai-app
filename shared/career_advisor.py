# -*- coding: utf-8 -*-
"""
career_advisor.py
-------------------
AIキャリアアドバイザー機能のプロンプト・LLM呼び出しロジック。

既存コードとの対応:
  streamlit版 page_modules/career_page.py の _ADVISOR_SYSTEM / render() 内の
  LLM呼び出し部分が相当する（_build_advisor_context() はDB永続化に依存する
  ため、react-fastapi/backend/services/career_advisor_service.py 側に置く）。

[shared/ 一本化]
utils にのみ依存し、db・rag のようなアプリ固有の兄弟モジュールに依存しない
ため、shared/ に配置した（詳細は shared/MIGRATION_GUIDE.md を参照）。

設計方針:
- call_ollama_with_text_retry はシングルターン（単一プロンプト）前提のため、
  システムプロンプト＋会話履歴＋新規質問を1テキストにまとめて渡す
  （streamlit版と同じ方式）。
"""
from __future__ import annotations

from utils import HALLUCINATION_GUARD, sanitize_user_input, call_ollama_with_text_retry

ADVISOR_SYSTEM_TEMPLATE = """あなたは経験豊富な日本の就職活動エージェント兼キャリアアドバイザーです。
学生の就活を包括的にサポートします。

【あなたのスタンス】
・学生のデータ（インタビュー・自己PR・性格診断・模擬面接評価）を最大限に活用し、
  その学生に合った具体的・個別的なアドバイスを提供してください。
・「一般論」や「誰にでも言えること」は避け、学生のエピソード・強み・課題を踏まえた
  パーソナライズされた回答をしてください。
・ガクチカ相談・ES添削・面接不安・業界研究・企業比較・将来の働き方など、
  就活に関することであれば何でも答えてください。
・ES文章の添削を求められたら、具体的に文章を書き直して見せてください。
・数字や根拠を使って、論理的かつ温かみのあるトーンで話してください。
・敬体（です・ます調）を使い、親しみやすく、でも的確なアドバイスを心がけてください。
・就活と関係のない話題（料理・ゲーム等）には「就活関連のご相談を専門としています」と
  丁丁寧にお断りし、就活の話題に引き戻してください。
{hallucination_guard}
【学生の情報】
{context}
"""


def generate_career_advice(
    model: str,
    context_text: str,
    history_messages: list[dict],
) -> dict:
    """会話履歴と学生情報コンテキストから、キャリアアドバイザーの返信を生成する。

    Args:
        model: Ollamaモデル名
        context_text: _build_advisor_context() 相当のコンテキスト文字列（空文字可）
        history_messages: [{"role": "user"|"assistant", "content": str}, ...]
                           最後の要素が今回の学生の発言（role="user"）である想定。

    Returns:
        {"reply": str, "ok": bool, "error_msg": str | None}
    """
    system_prompt = ADVISOR_SYSTEM_TEMPLATE.format(
        hallucination_guard=HALLUCINATION_GUARD,
        context=sanitize_user_input(context_text, max_length=8000) if context_text.strip() else "（まだデータがありません）",
    )
    history_text = "\n".join(
        f"{'アドバイザー' if m['role'] == 'assistant' else 'ユーザー'}: {m['content']}"
        for m in history_messages[-20:]
    )
    full_prompt = f"{system_prompt}\n\n【会話履歴】\n{history_text}"

    result = call_ollama_with_text_retry(
        model=model,
        prompt=full_prompt,
        fallback="⚠️ 応答の生成に失敗しました。しばらく待ってから再度お試しください。",
        min_length=10,
        max_retries=1,
    )
    return {
        "reply": result["text"],
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


__all__ = ["generate_career_advice", "ADVISOR_SYSTEM_TEMPLATE"]
