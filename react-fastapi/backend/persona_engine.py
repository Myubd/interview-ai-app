"""
persona_engine.py  (v2)
------------------------
面接官ペルソナ（性格・立場・面接スタイル）切り替え機能。
AI模擬面接（mock_interview_engine）に統合して使用する。

変更点 v2:
- ストレス面接ペルソナを削除
- 圧迫色が強いベテラン型を「厳格・本質追求型」に留め、圧迫にならない程度に調整
- 4ペルソナ構成に整理
- mock_interview_engine の get_first_question_for_theme / judge_and_generate_followup の
  ペルソナ対応差し替え版を提供
"""

from __future__ import annotations

from utils import (
    HALLUCINATION_GUARD,
    INTERVIEWER_JAPANESE_STYLE,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    format_theme_history,
    polish_interviewer_japanese,
    sanitize_user_input,
    wrap_user_content,
)
from industry_engine import build_industry_prompt_block

# ============================================================
# ペルソナ定義（4種）
# ============================================================

PERSONAS: dict[str, dict] = {
    "standard": {
        "key": "standard",
        "name": "スタンダード",
        "icon": "👔",
        "role": "人事部 中堅面接官（5年以上の経験）",
        "personality": "バランス型。穏やかで丁寧、STAR構成で具体性を深掘りする。",
        "style_prompt": (
            "【ペルソナ: スタンダード面接官】\n"
            "・穏やかで丁寧なトーンで話してください。\n"
            "・STAR構成（状況→課題→行動→結果）を意識した深掘りをしてください。\n"
            "・学生の回答を一旦受け止めてから次の質問に移ってください。\n"
            "・「具体的な行動」と「結果・数字」を引き出すことを意識してください。\n"
        ),
        "focus_axes": ["具体性", "論理構成"],
        "sample_phrase": "なるほど、ありがとうございます。その中で、特にあなた自身が主体的に動いた場面はどこでしたか？",
    },
    "veteran": {
        "key": "veteran",
        "name": "ベテラン・厳格型",
        "icon": "🔍",
        "role": "事業部長 / 現場出身のシニア面接官（20年以上の経験）",
        "personality": "本質追求型。表面的な回答には「具体的には？」と切り込むが、高圧的にはならない。",
        "style_prompt": (
            "【ペルソナ: ベテラン・厳格型面接官】\n"
            "・現場経験豊富な上席として、本質を鋭く突く質問をしてください。\n"
            "・表面的・抽象的な回答には「具体的には？」「なぜそう思ったのですか？」と追及してください。\n"
            "・相槌は最小限（「ふむ」「なるほど」程度）にし、次の核心にすぐ移ってください。\n"
            "・ただし高圧的・威圧的にはならず、冷静で客観的な口調を保ってください。\n"
            "・敬体（です・ます調）を維持してください。\n"
        ),
        "focus_axes": ["論理構成", "思考の深さ", "具体性"],
        "sample_phrase": "それで？その状況で、あなた個人は具体的にどう動きましたか。チームの話ではなく、あなた自身の行動を聞かせてください。",
    },
    "hr_empathetic": {
        "key": "hr_empathetic",
        "name": "共感型・人柄重視",
        "icon": "🌸",
        "role": "人事部 採用担当（カルチャーフィット重視）",
        "personality": "温かく共感的。数字よりも価値観・人柄・チームとの相性を探る。",
        "style_prompt": (
            "【ペルソナ: 共感型・人柄重視面接官】\n"
            "・温かく、学生の感情や価値観に寄り添う言葉を意識してください。\n"
            "・「そのとき、どんな気持ちでしたか？」「チームの雰囲気はどうでしたか？」など、"
            "感情・関係性・価値観を引き出す質問を多用してください。\n"
            "・数字や成果よりも「なぜそうしたのか」「何を大切にしているのか」を掘り下げてください。\n"
            "・共感の相槌を自然に挟んでください（「そうだったんですね」「それは大変でしたね」等）。\n"
        ),
        "focus_axes": ["価値観・人柄", "熱意", "チームフィット"],
        "sample_phrase": "そうだったんですね。そのとき、一番つらかったのはどういう点でしたか？",
    },
    "logical": {
        "key": "logical",
        "name": "ロジカル・コンサル型",
        "icon": "📊",
        "role": "コンサルティングファーム / IT企業 選考面接官",
        "personality": "論理思考重視。問題分解・優先順位・因果関係を中心に深掘りする。",
        "style_prompt": (
            "【ペルソナ: ロジカル・コンサル型面接官】\n"
            "・「その課題をどのように分解しましたか？」「優先順位をどう決めましたか？」"
            "「そのアプローチを選んだ根拠は何ですか？」など、思考プロセスを掘り下げてください。\n"
            "・感情的な共感よりも、事実と論拠に基づいた会話を重視してください。\n"
            "・数字・規模感・インパクトの定量化を積極的に求めてください。\n"
            "・「もし〇〇だったらどう対応しましたか？」という仮説的な問いも使ってください。\n"
        ),
        "focus_axes": ["論理構成", "問題解決能力", "定量思考"],
        "sample_phrase": "その問題を解くにあたって、どのようにアプローチを分解して考えましたか？",
    },
}

DEFAULT_PERSONA_KEY = "standard"


# ============================================================
# 公開API: ペルソナ情報取得
# ============================================================

def get_persona(key: str) -> dict:
    """ペルソナキーからペルソナ辞書を取得する。不明なキーはスタンダードにフォールバック。"""
    return PERSONAS.get(key, PERSONAS[DEFAULT_PERSONA_KEY])


def list_personas() -> list[dict]:
    """全ペルソナのリストを返す（UIのセレクトボックス用）。"""
    return list(PERSONAS.values())


def build_persona_prompt_block(key: str) -> str:
    """プロンプトに差し込むペルソナ固有の指示ブロックを返す。"""
    persona = get_persona(key)
    return (
        f"\n【あなたの役割・立場】\n{persona['role']}\n"
        f"{persona['style_prompt']}"
    )


# ============================================================
# 公開API: ペルソナ付き質問生成
# mock_interview_engine の関数のペルソナ対応差し替え版
# ============================================================

def get_first_question_for_theme(
    model: str,
    persona_key: str,
    theme: dict,
    previous_theme_last_exchange: str | None,
    profile_text: str | None,
    rag_block: str | None,
    predicted_questions: list[dict] | None,
    used_question_indices: set[int],
    industry_key: str | None = None,
) -> dict:
    """ペルソナ付きでテーマの最初の質問を生成する。

    mock_interview_engine.get_first_question_for_theme() の
    ペルソナ対応版。シグネチャは persona_key を追加した以外は同じ。

    事前生成質問がある場合はそちらを優先（ペルソナに関わらず共通）。
    事前生成質問がない場合のみAI生成でペルソナを反映させる。

    Returns:
        {"question": str, "used_predicted_index": int | None, "ok": bool, "error_msg": str | None}
    """
    # 事前生成質問の流用チェック（mock_interview_engine と同ロジック）
    from mock_interview_engine import _pick_predicted_question_for_theme
    predicted_q, predicted_idx = _pick_predicted_question_for_theme(
        theme, predicted_questions, used_question_indices
    )
    if predicted_q:
        if previous_theme_last_exchange:
            question = f"ありがとうございます。それでは次に、{theme['title']}についてお伺いします。{predicted_q}"
        else:
            question = predicted_q
        question = polish_interviewer_japanese(question)
        return {"question": question, "used_predicted_index": predicted_idx, "ok": True, "error_msg": None}

    # AI生成（ペルソナ反映）
    persona_block = build_persona_prompt_block(persona_key)
    persona = get_persona(persona_key)
    industry_block = build_industry_prompt_block(industry_key or "general")

    profile_hint = ""
    if profile_text and profile_text.strip():
        safe_profile = sanitize_user_input(profile_text)
        profile_hint = f"\n【学生のプロフィール（履歴書相当）】\n{safe_profile}\n"

    rag_hint = ""
    if rag_block and rag_block.strip():
        rag_hint = f"\n{wrap_user_content(rag_block, max_length=4000)}\n"

    fallback_q = (
        f"{theme['title']}について教えてください。"
        if previous_theme_last_exchange is None
        else f"ありがとうございます。次に、{theme['title']}について教えてください。"
    )

    if previous_theme_last_exchange is None:
        prompt = f"""あなたは日本企業の新卒採用面接官です。これから模擬面接を始めます。
{USER_INPUT_BOUNDARY_NOTE}
{INTERVIEWER_JAPANESE_STYLE}
{persona_block}
{industry_block}
{profile_hint}{rag_hint}
【最初のテーマ】{theme['title']}
【聞き出したいこと】{theme['goal']}

あなたのペルソナらしい口調で、学生がリラックスして答えられる最初の質問を1つ作ってください。
敬体（です・ます調）で出力してください。

【出力ルール】
必ず以下のJSON形式のみで出力してください。
{{"question": "最初の質問文"}}
"""
    else:
        safe_exchange = wrap_user_content(previous_theme_last_exchange)
        prompt = f"""あなたは日本企業の新卒採用面接官です。テーマが変わります。
{USER_INPUT_BOUNDARY_NOTE}
{INTERVIEWER_JAPANESE_STYLE}
{persona_block}
{industry_block}
{profile_hint}{rag_hint}
【直前のやり取り】
{safe_exchange}

【次のテーマ】{theme['title']}
【聞き出したいこと】{theme['goal']}

あなたのペルソナらしい口調で、直前の回答への一言相槌と次テーマの最初の質問を自然につなげてください。
質問は1つだけ。敬体（です・ます調）で出力してください。

【出力ルール】
必ず以下のJSON形式のみで出力してください。
{{"question": "相槌＋次の質問文"}}
"""

    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["question"],
        fallback={"question": fallback_q},
        max_retries=2,
    )
    question = polish_interviewer_japanese(str(result.get("question", "")).strip()) or fallback_q
    return {
        "question": question,
        "used_predicted_index": None,
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


def judge_and_generate_followup(
    model: str,
    persona_key: str,
    theme: dict,
    theme_messages: list[dict],
    followups_asked_in_theme: int,
    profile_text: str | None,
    rag_block: str | None,
    industry_key: str | None = None,
) -> dict:
    """ペルソナ付きで深掘り質問を判定・生成する。

    mock_interview_engine.judge_and_generate_followup() の
    ペルソナ対応版。persona_key を追加した以外はシグネチャ同じ。

    Returns:
        {"continue": bool, "question": str, "ok": bool, "error_msg": str | None}
    """
    max_followups = theme["max_followups"][1]
    if followups_asked_in_theme >= max_followups:
        return {"continue": False, "question": "", "ok": True, "error_msg": None}

    persona_block = build_persona_prompt_block(persona_key)
    industry_block = build_industry_prompt_block(industry_key or "general")

    profile_hint = ""
    if profile_text and profile_text.strip():
        safe_profile = sanitize_user_input(profile_text)
        profile_hint = f"\n【学生のプロフィール】\n{safe_profile}\n"

    rag_hint = ""
    if rag_block and rag_block.strip():
        rag_hint = f"\n{wrap_user_content(rag_block, max_length=4000)}\n"

    prompt = f"""あなたは日本企業の新卒採用面接官です。模擬面接中です。
点数や評価は一切口にせず、自然な対話を続けてください。
{USER_INPUT_BOUNDARY_NOTE}
{INTERVIEWER_JAPANESE_STYLE}
{HALLUCINATION_GUARD}
{persona_block}
{industry_block}
{profile_hint}{rag_hint}
【現在のテーマ】{theme['title']}
【聞き出したいこと】{theme['goal']}

【これまでのやり取り】
{format_theme_history(theme_messages)}

【判断ルール】
・このテーマで既に{followups_asked_in_theme}回深掘りしており、深掘り上限は{max_followups}回です。
・上限に達している、または十分な具体的内容（行動・数字・結果）が聞けたと判断した場合は
  continue を false にしてください。
・まだ聞き出すべき情報がある場合のみ continue を true にし、
  あなたのペルソナらしい口調で次の深掘り質問を作ってください。
・continueがtrueの場合、直前の回答への短い相槌を1文添えてください（点数・評価コメントは絶対に含めない）。
・敬体（です・ます調）で出力してください。

【出力ルール】
必ず以下のJSON形式のみで出力してください。
{{"continue": true または false, "question": "相槌＋深掘り質問文（continueがfalseの場合は空文字）"}}
"""
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
