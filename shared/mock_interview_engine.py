# -*- coding: utf-8 -*-
"""
mock_interview_engine.py
--------------------------
履歴書・企業情報（RAG）を理解したAIが面接官役となり、テーマに沿って質問→深掘りを行う
「AI模擬面接」モジュール。

設計方針:
- テーマ（自己紹介・ガクチカ・志望動機・企業理解・逆質問）ごとに「基本質問数」と
  「深掘り上限」を持つ。基本質問は question_prediction.py が事前生成した想定質問
  （あれば）を優先的に使い、なければその場でAIに質問を生成させる。
  深掘りは、基本質問への回答を踏まえてAIがその場で要否を判定し、必要なら生成する。
  （= 「70%事前生成・30%深掘り」という体験を、テーマごとの数量設計で実現する）
- 面接中はスコアを一切出さない。AIの返答は「軽い相槌＋次の質問」のみで、
  圧迫感のない自然な対話に留める。
- 全テーマが完了すると自動終了。ユーザーはいつでも「面接を終える」を選べる
  （途中終了時は、それまでの回答だけで終了後評価を生成する）。
- 終了後評価は1回のOllama呼び出しでまとめて生成する
  （総合評価・項目別スコア・強みTOP3・改善点TOP3・各質問の模範回答例・次回の練習ポイント）。
- 既存の interview_engine.py / question_prediction.py と同じく、
  utils.call_ollama_with_json_retry によるリトライ・スキーマ検証、
  sanitize_user_input / wrap_user_content によるInjection対策、
  HALLUCINATION_GUARD による事実外創作防止を踏襲する。

[補足: 質問文生成の実体について]
- ペルソナ（面接官タイプ）機能の導入に伴い、実際に質問文を生成する処理は
  persona_engine.py のペルソナ対応版（get_first_question_for_theme /
  judge_and_generate_followup）に一本化されている。app.py からもそちらが呼ばれる。
- 本ファイルが直接担うのは、事前生成質問の選択（_pick_predicted_question_for_theme、
  persona_engine.py からも参照される）、プロフィール/RAGヒントの整形
  （_format_profile_and_rag_hint）、終了後評価（generate_mock_interview_evaluation）、
  およびテーマ管理の補助関数（is_interview_finished / get_theme 等）。
"""

from __future__ import annotations

import logging

from prompts.guards import HALLUCINATION_GUARD
from prompts.interviewer import INTERVIEWER_JAPANESE_STYLE
from prompts.mock_interview import MOCK_EVALUATION_PROMPT
from utils import (
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    format_theme_history,
    polish_interviewer_japanese,
    sanitize_user_input,
    wrap_user_content,
)
from industry_engine import (
    get_themes_for_industry,
    get_eval_axes_for_industry,
    DEFAULT_INDUSTRY_KEY,
)

logger = logging.getLogger(__name__)

# ============================================================
# テーマ構造・評価軸（業界別に動的切り替え）
# ============================================================
# デフォルトは汎用（general）。
# セッション中は get_active_themes() / get_active_eval_axes() を使うことで
# 業界選択に応じたテーマ・評価軸が取得できる。

def get_active_themes(industry_key: str | None = None) -> list[dict]:
    """業界キーに対応するテーマリストを返す。Noneの場合はデフォルト業界を使用。"""
    return get_themes_for_industry(industry_key or DEFAULT_INDUSTRY_KEY)


def get_active_eval_axes(industry_key: str | None = None) -> list[str]:
    """業界キーに対応する評価軸リストを返す。Noneの場合はデフォルト業界を使用。"""
    return get_eval_axes_for_industry(industry_key or DEFAULT_INDUSTRY_KEY)


# 後方互換のためのデフォルト定数（汎用業界の値）
MOCK_INTERVIEW_THEMES: list[dict] = get_active_themes()
EVAL_AXES: list[str] = get_active_eval_axes()

# INTERVIEWER_JAPANESE_STYLE は utils.py で一元管理（interview_engine.py と共有）


# ============================================================
# ヘルパー
# ============================================================
# テーマ内会話履歴の整形（_format_theme_history相当）は
# utils.format_theme_history に一元化（interview_engine.py と共有）


def _pick_predicted_question_for_theme(
    theme: dict, predicted_questions: list[dict] | None, used_question_indices: set[int]
) -> tuple[str | None, int | None]:
    """question_prediction.py が生成した想定質問の中から、このテーマに近いカテゴリの
    未使用の質問を1つ選ぶ。

    question_prediction.py の category は
    "deep_dive" | "motivation" | "weakness" | "situational" の4種であり、
    本モジュールのテーマ（5種）とは一対一に対応しないため、近いものへマッピングする。

    Returns:
        (question_text, index_in_predicted_questions) のタプル。見つからなければ (None, None)。
    """
    if not predicted_questions:
        return None, None

    # テーマkey -> question_predictionのcategory（複数可）のマッピング
    category_map: dict[str, list[str]] = {
        "self_intro": [],  # 自己紹介は事前生成質問を使わず、常にAI生成（自然な導入のため）
        "gakuchika": ["deep_dive"],
        "motivation": ["motivation"],
        "company_fit": ["situational"],
        "reverse_q": [],  # 逆質問は学生側が質問する場であり、想定質問の流用対象外
    }
    allowed_categories = category_map.get(theme["key"], [])
    if not allowed_categories:
        return None, None

    for idx, q in enumerate(predicted_questions):
        if idx in used_question_indices:
            continue
        if q.get("category") in allowed_categories:
            return q.get("question", "").strip(), idx

    return None, None


def _format_profile_and_rag_hint(profile_text: str | None, rag_block: str | None) -> str:
    """プロフィール・RAG資料（履歴書・企業情報）のヒントをプロンプト用に整形する。"""
    parts = []
    if profile_text and profile_text.strip():
        safe_profile = sanitize_user_input(profile_text)
        parts.append(
            "\n【学生のプロフィール（履歴書相当）】\n"
            f"{safe_profile}\n"
        )
    if rag_block and rag_block.strip():
        # rag_block は rag.format_context() の出力で、既に整形済みテキストのため
        # 長文用の wrap_user_content で安全にラップする
        parts.append(f"\n{wrap_user_content(rag_block, max_length=4000)}\n")
    return "".join(parts)


# ============================================================
# 公開API: 終了後評価
# ============================================================

def generate_mock_interview_evaluation(
    model: str,
    full_history: str,
    profile_text: str | None = None,
    rag_block: str | None = None,
    industry_key: str | None = None,
) -> dict:
    """模擬面接終了後の総合評価を生成する。

    Args:
        model: Ollamaモデル名
        full_history: 面接全体の会話履歴（面接官・学生の発言を含む整形済みテキスト）
        profile_text: 学生プロフィール（任意）
        rag_block: RAG資料の参考情報ブロック（任意）

    Returns:
        {
            "overall_summary": str,                # 総合評価（3〜4文程度）
            "scores": {"論理構成": 1〜5, ...},      # 項目別スコア（EVAL_AXES全て）
            "top_strengths": [str, str, str],       # 強みTOP3
            "top_improvements": [str, str, str],    # 改善点TOP3
            "model_answers": [{"question": str, "model_answer": str}, ...],  # 模範回答例
            "next_practice_points": [str, ...],     # 次回の練習ポイント
            "ok": bool,
            "error_msg": str | None,
        }
    """
    logger.info("模擬面接評価を生成します（履歴長=%d文字, 業界=%s）", len(full_history), industry_key)
    active_axes = get_active_eval_axes(industry_key)
    safe_history = wrap_user_content(full_history, max_length=12000)
    context_hint = _format_profile_and_rag_hint(profile_text, rag_block)
    axes_json_hint = ", ".join(f'"{axis}": 1〜5の整数' for axis in active_axes)

    prompt = MOCK_EVALUATION_PROMPT.format(
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        context_hint=context_hint,
        safe_history=safe_history,
        axes_json_hint=axes_json_hint,
    )
    fallback = {
        "overall_summary": "",
        "scores": {},
        "top_strengths": [],
        "top_improvements": [],
        "model_answers": [],
        "next_practice_points": [],
    }
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=[
            "overall_summary", "scores", "top_strengths",
            "top_improvements", "model_answers", "next_practice_points",
        ],
        fallback=fallback,
        max_retries=2,
    )

    # スコアの補正（欠落軸は0埋め、範囲外は1〜5にクランプ）
    scores_raw = result.get("scores", {})
    if not isinstance(scores_raw, dict):
        scores_raw = {}
    scores = {}
    for axis in active_axes:
        try:
            val = int(scores_raw.get(axis, 0))
        except (TypeError, ValueError):
            val = 0
        scores[axis] = max(0, min(5, val))

    def _clean_str_list(value, limit: int | None = None) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        return cleaned[:limit] if limit else cleaned

    model_answers_raw = result.get("model_answers", [])
    model_answers = []
    if isinstance(model_answers_raw, list):
        for item in model_answers_raw:
            if not isinstance(item, dict):
                continue
            q = str(item.get("question", "")).strip()
            a = str(item.get("model_answer", "")).strip()
            if q and a:
                model_answers.append({"question": q, "model_answer": a})

    return {
        "overall_summary": str(result.get("overall_summary", "")).strip(),
        "scores": scores,
        "eval_axes": active_axes,   # 業界別評価軸を結果に含める
        "top_strengths": _clean_str_list(result.get("top_strengths"), limit=3),
        "top_improvements": _clean_str_list(result.get("top_improvements"), limit=3),
        "model_answers": model_answers,
        "next_practice_points": _clean_str_list(result.get("next_practice_points")),
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


# ============================================================
# 進行管理ヘルパー（app.py から呼ぶ想定の小さな補助関数）
# ============================================================

def is_interview_finished(theme_index: int, industry_key: str | None = None) -> bool:
    """全テーマを終えたかどうかを判定する。業界によってテーマ数が異なる。"""
    themes = get_active_themes(industry_key)
    return theme_index >= len(themes)


def get_theme(theme_index: int, industry_key: str | None = None) -> dict | None:
    """インデックスからテーマ辞書を取得する。範囲外ならNone。"""
    themes = get_active_themes(industry_key)
    if 0 <= theme_index < len(themes):
        return themes[theme_index]
    return None


def get_total_themes(industry_key: str | None = None) -> int:
    """業界のテーマ総数を返す。"""
    return len(get_active_themes(industry_key))


def build_full_history_text(messages: list[dict]) -> str:
    """模擬面接の全メッセージ履歴を、評価生成プロンプト用のテキストに整形する。"""
    lines = []
    for m in messages:
        label = "面接官" if m["role"] == "assistant" else "学生"
        content = sanitize_user_input(m["content"], max_length=2000) if m["role"] == "user" else m["content"]
        lines.append(f"{label}: {content}")
    return "\n".join(lines)
