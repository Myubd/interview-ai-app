"""
answer_assist.py  (v2)
-----------------------
各回答の直後に表示する「振り返り・質問意図解説」機能。
（リアルタイムカンペ機能は廃止し、面接後の学習用途に特化）

生成する内容（1回のLLM呼び出し）:
  1. intent        : この質問で面接官が「何を見ているか」（ペルソナ連携）
  2. good_points   : 学生の回答の良かった点（2〜3点）
  3. improvements  : 改善提案（2〜3点、具体的に）
  4. appeal_points : この質問でアピールできた/すべき要素（2〜3点）
  5. revised_example : より良い回答の一例（100〜150字、敬体）

ペルソナ連携:
  - ペルソナごとに「面接官が特に重視する軸」が異なるため、
    intent の文章とgood_points/improvementsの着眼点がペルソナで変わる。
  - build_persona_prompt_block() を受け取りプロンプトに差し込む。
"""

from __future__ import annotations

import logging

from prompts.answer_assist import REVIEW_PROMPT as _REVIEW_PROMPT
from prompts.guards import HALLUCINATION_GUARD
from utils import (
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    sanitize_user_input,
    wrap_user_content,
)

logger = logging.getLogger(__name__)

# ============================================================
# プロンプトテンプレート（prompts/answer_assist.py に移管）
# ============================================================
# _REVIEW_PROMPT は後方互換のためここでも参照可能（上でインポート済み）




# ============================================================
# 公開API
# ============================================================

def generate_answer_review(
    model: str,
    question: str,
    student_answer: str,
    persona_block: str = "",
    persona_name: str = "スタンダード",
    pr_text: str = "",
    conversation_history: str = "",
) -> dict:
    """各回答直後の振り返りフィードバックを生成する。

    Args:
        model: Ollamaモデル名
        question: 面接官の質問文
        student_answer: 学生の回答文
        persona_block: build_persona_prompt_block() の出力（ペルソナ指示文）
        persona_name: ペルソナ表示名（UI表示用）
        pr_text: 生成済み自己PR（任意）
        conversation_history: インタビュー全履歴（任意）

    Returns:
        {
          "intent": str,
          "good_points": [str, ...],
          "improvements": [str, ...],
          "appeal_points": [str, ...],
          "revised_example": str,
          "persona_name": str,
          "ok": bool,
          "error_msg": str | None,
        }
    """
    logger.info("回答レビュー生成: persona=%s", persona_name)
    safe_question = wrap_user_content(question)
    safe_answer = wrap_user_content(student_answer)

    context_parts = []
    if pr_text.strip():
        context_parts.append(f"【自己PR】\n{wrap_user_content(pr_text)}")
    if conversation_history.strip():
        context_parts.append(f"【インタビュー履歴】\n{wrap_user_content(conversation_history, max_length=3000)}")
    context_block = "\n\n".join(context_parts) if context_parts else "（参考情報なし）"

    persona_section = ""
    if persona_block.strip():
        persona_section = f"\n【この面接官のペルソナ・スタイル】\n{sanitize_user_input(persona_block, max_length=600)}\n"

    prompt = _REVIEW_PROMPT.format(
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        persona_block=persona_section,
        question_block=safe_question,
        answer_block=safe_answer,
        context_block=context_block,
    )

    fallback = {
        "intent": "",
        "good_points": [],
        "improvements": [],
        "appeal_points": [],
        "revised_example": "",
    }
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["intent", "good_points", "improvements", "appeal_points", "revised_example"],
        fallback=fallback,
        max_retries=2,
    )

    def _clean_list(val) -> list[str]:
        if not isinstance(val, list):
            return []
        return [str(v).strip() for v in val if str(v).strip()]

    return {
        "intent": str(result.get("intent", "")).strip(),
        "good_points": _clean_list(result.get("good_points")),
        "improvements": _clean_list(result.get("improvements")),
        "appeal_points": _clean_list(result.get("appeal_points")),
        "revised_example": str(result.get("revised_example", "")).strip(),
        "persona_name": persona_name,
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


# ============================================================
# STAR法評価 公開API
# ============================================================

from prompts.answer_assist import STAR_REVIEW_PROMPT as _STAR_REVIEW_PROMPT


def generate_star_review(
    model: str,
    question: str,
    student_answer: str,
) -> dict:
    """STAR法（Situation/Task/Action/Result）の観点で回答を評価する。

    Args:
        model: Ollamaモデル名
        question: 面接官の質問文
        student_answer: 学生の回答文

    Returns:
        {
          "situation": {"score": int, "comment": str},
          "task":      {"score": int, "comment": str},
          "action":    {"score": int, "comment": str},
          "result":    {"score": int, "comment": str},
          "star_total": int,          # 0〜12
          "star_summary": str,
          "star_tip": str,
          "ok": bool,
          "error_msg": str | None,
        }
    """
    logger.info("STAR法評価生成: question_len=%d", len(question))
    safe_question = wrap_user_content(question)
    safe_answer = wrap_user_content(student_answer)

    prompt = _STAR_REVIEW_PROMPT.format(
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        question_block=safe_question,
        answer_block=safe_answer,
    )

    fallback = {
        "situation": {"score": 0, "comment": ""},
        "task":      {"score": 0, "comment": ""},
        "action":    {"score": 0, "comment": ""},
        "result":    {"score": 0, "comment": ""},
        "star_total": 0,
        "star_summary": "",
        "star_tip": "",
    }
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["situation", "task", "action", "result", "star_total", "star_summary", "star_tip"],
        fallback=fallback,
        max_retries=2,
    )

    def _clean_element(raw, key: str) -> dict:
        if not isinstance(raw, dict):
            return {"score": 0, "comment": ""}
        try:
            score = max(0, min(3, int(raw.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        return {"score": score, "comment": str(raw.get("comment", "")).strip()}

    situation = _clean_element(result.get("situation"), "situation")
    task      = _clean_element(result.get("task"), "task")
    action    = _clean_element(result.get("action"), "action")
    result_el = _clean_element(result.get("result"), "result")

    try:
        star_total = max(0, min(12, int(result.get("star_total", 0))))
    except (TypeError, ValueError):
        star_total = situation["score"] + task["score"] + action["score"] + result_el["score"]

    return {
        "situation":    situation,
        "task":         task,
        "action":       action,
        "result":       result_el,
        "star_total":   star_total,
        "star_summary": str(result.get("star_summary", "")).strip(),
        "star_tip":     str(result.get("star_tip", "")).strip(),
        "ok":           result["ok"],
        "error_msg":    result.get("error_msg"),
    }
