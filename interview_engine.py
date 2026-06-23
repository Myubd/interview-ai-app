"""
interview_engine.py
--------------------
固定テンプレート文を廃止し、AIがその場で質問文を生成する「動的インタビュー」エンジン。

設計方針:
- テーマ（topic）の「順番」と「目的」は固定するが、「質問の言い回し・粒度・回数」はAIが
  会話の流れを見て都度決める。
- 暴走防止のため、1テーマあたりの質問数には上限を設ける（初回質問＋深掘り最大1回＝計2問まで）。
- 「熱中したこと」テーマだけ、最初にカテゴリ選択（部活/バイト/ボランティア/その他）を挟み、
  選択結果に応じた質問をAIに生成させる。
- 質問生成・継続判定は1回のOllama呼び出しでJSONとしてまとめて行い、呼び出し回数を抑える。
- 事前入力フォーム（学歴・職歴・資格／免許）で取得済みの情報は「プロフィール」として
  全テーマの質問生成プロンプトに渡し、AIが重複して質問しないようにする。

[変更点 v2]
- utils.call_ollama_with_json_retry を使い、JSON失敗時のリトライ・スキーマ検証を追加
- utils.sanitize_user_input / wrap_user_content でPrompt Injection対策を追加
- ハルシネーション抑制ヒントを面接質問プロンプトにも追加（学生情報の創作防止）
"""

from __future__ import annotations

import logging

from prompts.interviewer import (
    FIRST_QUESTION_MID_PROMPT,
    FIRST_QUESTION_PROMPT,
    INTERVIEWER_JAPANESE_STYLE,
    QUESTION_SYSTEM_PROMPT,
    TRANSITION_SYSTEM_PROMPT,
)
from utils import (
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    format_theme_history,
    polish_interviewer_japanese,
    sanitize_user_input,
    wrap_user_content,
)

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_THEME = 2

THEMES = [
    {
        "key": "education",
        "title": "学歴・専攻",
        "goal": (
            "学生の専攻分野・関心のある研究テーマなど、学業面でのバックグラウンドを把握する。"
            "学校名・学部名・卒業年などの基本情報は事前入力フォームで取得済みであることが多いため、"
            "それらが分かっている場合は重ねて聞かず、専攻を選んだ理由や特に関心を持って取り組んだ"
            "テーマ・授業など、フォームだけでは分からない部分を聞くこと。"
        ),
        "needs_category_choice": False,
    },
    {
        "key": "passion",
        "title": "熱中したこと",
        "goal": (
            "学生が学生時代に最も力を入れた活動（部活・サークル、アルバイト、ボランティア等）について、"
            "活動内容・役割・規模感などの基本情報を把握する。事前入力フォームの職歴に関連する記載が"
            "あれば、それを踏まえてより具体的な質問にすること。"
        ),
        "needs_category_choice": True,
    },
    {
        "key": "challenge",
        "title": "苦労・工夫したエピソード",
        "goal": (
            "前のテーマで聞いた活動の中で、学生が直面した課題・苦労と、それに対してどう考え行動したか、"
            "結果どうなったかという「具体的なエピソード」を、数字や固有名詞を交えて引き出す。"
        ),
        "needs_category_choice": False,
    },
    {
        "key": "personal",
        "title": "休日の過ごし方",
        "goal": "学生のプライベートな一面・価値観・人柄が伝わるような、リラックスした話題を聞く。",
        "needs_category_choice": False,
    },
]

CATEGORY_OPTIONS = ["部活・サークル", "アルバイト", "ボランティア", "その他の活動"]


# ── プロンプトテンプレート ─────────────────────────────────────────────────────
# prompts/interviewer.py で一元管理（このファイルの先頭でインポート済み）


# ── ヘルパー ──────────────────────────────────────────────────────────────────
# テーマ内会話履歴の整形は utils.format_theme_history に一元化（mock_interview_engine.py と共有）


def _format_profile_hint(profile_text: str | None) -> str:
    if not profile_text or not profile_text.strip():
        return ""
    # プロフィールはユーザー入力なのでサニタイズ
    safe_profile = sanitize_user_input(profile_text)
    return (
        "\n【事前入力フォームで取得済みの情報（履歴書相当）】\n"
        f"{safe_profile}\n"
        "※ ここに書かれている内容は既に分かっているので、同じ内容を重ねて質問しないでください。\n"
    )


# ── 公開API ───────────────────────────────────────────────────────────────────

def get_first_question_for_theme(
    model: str,
    theme: dict,
    selected_category: str | None,
    previous_theme_last_exchange: str | None,
    profile_text: str | None = None,
) -> dict:
    """テーマの最初の質問文を生成する。

    Returns: {"question": str, "ok": bool, "error_msg": str | None}
    """
    category_hint = ""
    if theme["needs_category_choice"] and selected_category:
        safe_cat = sanitize_user_input(selected_category)
        category_hint = f"【学生が選んだカテゴリ】\n{safe_cat}\n（このカテゴリに即した具体的な質問にしてください）\n"

    profile_hint = _format_profile_hint(profile_text)
    fallback_q = (
        f"{theme['title']}について教えてください。"
        if previous_theme_last_exchange is None
        else f"ありがとうございます。次に、{theme['title']}について教えてください。"
    )

    if previous_theme_last_exchange is None:
        logger.debug("get_first_question_for_theme: 冒頭質問生成 theme=%s", theme["key"])
        prompt = FIRST_QUESTION_PROMPT.format(
            injection_note=USER_INPUT_BOUNDARY_NOTE,
            japanese_style=INTERVIEWER_JAPANESE_STYLE,
            profile_hint=profile_hint,
            theme_title=theme["title"],
            theme_goal=theme["goal"],
            category_hint=category_hint,
        )
    else:
        # 前テーマのやり取りをラッピング（Injection対策）
        logger.debug("get_first_question_for_theme: テーマ移行質問生成 theme=%s", theme["key"])
        safe_exchange = wrap_user_content(previous_theme_last_exchange)
        prompt = FIRST_QUESTION_MID_PROMPT.format(
            injection_note=USER_INPUT_BOUNDARY_NOTE,
            japanese_style=INTERVIEWER_JAPANESE_STYLE,
            profile_hint=profile_hint,
            last_exchange=safe_exchange,
            theme_title=theme["title"],
            theme_goal=theme["goal"],
            category_hint=category_hint,
        )

    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["question"],
        fallback={"question": fallback_q},
        max_retries=2,
    )
    question = polish_interviewer_japanese(str(result.get("question", "")).strip()) or fallback_q
    return {"question": question, "ok": result["ok"], "error_msg": result.get("error_msg")}


def judge_and_generate_next_question(
    model: str,
    theme: dict,
    theme_messages: list[dict],
    questions_asked_in_theme: int,
    selected_category: str | None,
    profile_text: str | None = None,
) -> dict:
    """現在のテーマ内で、次の質問を続けるべきかどうかを判定し、続けるなら質問文も生成する。

    Returns: {"continue": bool, "question": str, "ok": bool, "error_msg": str | None}
    """
    logger.debug(
        "judge_and_generate_next_question: theme=%s asked=%d max=%d",
        theme["key"], questions_asked_in_theme, MAX_QUESTIONS_PER_THEME,
    )
    if questions_asked_in_theme >= MAX_QUESTIONS_PER_THEME:
        logger.info("テーマ '%s' 上限到達。インタビュー継続=False", theme["key"])
        return {"continue": False, "question": "", "ok": True, "error_msg": None}

    category_hint = ""
    if theme["needs_category_choice"] and selected_category:
        safe_cat = sanitize_user_input(selected_category)
        category_hint = f"【学生が選んだカテゴリ】\n{safe_cat}\n"

    prompt = QUESTION_SYSTEM_PROMPT.format(
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        japanese_style=INTERVIEWER_JAPANESE_STYLE,
        profile_hint=_format_profile_hint(profile_text),
        theme_title=theme["title"],
        theme_goal=theme["goal"],
        category_hint=category_hint,
        theme_history=format_theme_history(theme_messages),
        questions_asked_in_theme=questions_asked_in_theme,
        max_questions=MAX_QUESTIONS_PER_THEME,
    )

    fallback = {"continue": False, "question": ""}
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["continue", "question"],
        type_checks={"continue": bool},
        fallback=fallback,
        max_retries=2,
    )
    return {
        "continue": bool(result.get("continue", False)),
        "question": polish_interviewer_japanese(str(result.get("question", "")).strip()),
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }
