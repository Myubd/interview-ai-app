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

# local_ai_core.prompts.guards.MEMORY_CONFIDENCE_GUARD と同じ方針を、shared/ を
# local_ai_core に依存させないままここでも守るためのローカルコピー。
# (shared/ は streamlit版・react-fastapi版の両方から使われ、streamlit版はまだ
#  local_ai_core を前提にしていないため、新規importは追加しない)
MEMORY_CONFIDENCE_GUARD = (
    "重要: 【本人確認済み】の記憶は事実として扱ってよいですが、"
    "【AIの推測・未確認】の記憶は、あくまで推測であり断定しないでください。"
    "推測情報に基づいて回答する場合は「〜という傾向があるようですが、違っていたら教えてください」"
    "のように、確認を促す言い方をしてください。"
)

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
{hallucination_guard}{memory_guard}
【学生の情報】
{context}
{memory_section}"""


def generate_career_advice(
    model: str,
    context_text: str,
    history_messages: list[dict],
    memory_context: str = "",
) -> dict:
    """会話履歴と学生情報コンテキストから、キャリアアドバイザーの返信を生成する。

    Args:
        model: Ollamaモデル名
        context_text: _build_advisor_context() 相当のコンテキスト文字列（空文字可）
        history_messages: [{"role": "user"|"assistant", "content": str}, ...]
                           最後の要素が今回の学生の発言（role="user"）である想定。
        memory_context: local-ai-core の AIメモリー(career.* 配下)を
                         `local_ai_core.memory.format_items_for_prompt` で整形した文字列。
                         呼び出し元がメモリー読み出し権限を持たない/未実装の場合は空文字のままでよく、
                         その場合このパラメータを渡す前と完全に同じ挙動になる(後方互換)。

    Returns:
        {"reply": str, "ok": bool, "error_msg": str | None}
    """
    memory_section = f"\n【AIメモリー(アプリ横断で蓄積された情報)】\n{memory_context}\n" if memory_context.strip() else ""
    system_prompt = ADVISOR_SYSTEM_TEMPLATE.format(
        hallucination_guard=HALLUCINATION_GUARD,
        memory_guard=f"\n{MEMORY_CONFIDENCE_GUARD}" if memory_context.strip() else "",
        context=sanitize_user_input(context_text, max_length=8000) if context_text.strip() else "（まだデータがありません）",
        memory_section=memory_section,
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
