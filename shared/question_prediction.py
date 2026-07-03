"""
question_prediction.py
-----------------------
生成した自己PRとインタビュー記録をもとに、面接本番で想定される質問と
そのまま話せる水準の模範回答例を自動生成するモジュール。

設計方針:
- 入力: 完成した自己PR本文 + インタビュー全履歴（+ 任意で企業情報RAGブロック）
- 出力: 8問の想定質問 × {質問文・カテゴリ・模範回答例（200字前後のフル文章）}
- 質問カテゴリは「深掘り系・動機系・弱み系・状況対応系」の4種をバランスよく含める
- 模範回答例はそのまま声に出しても違和感のない敬体（です・ます調）のフル文章にする
- ハルシネーション防止: インタビュー記録・自己PRに存在する事実のみ使用
- Prompt Injection対策: 自己PR・履歴はwrap_user_contentでラッピング
- utils.call_ollama_with_json_array_retry でリトライ・スキーマ検証
"""

from __future__ import annotations

from utils import (
    HALLUCINATION_GUARD,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_array_retry,
    wrap_user_content,
)

# 生成する質問数
NUM_QUESTIONS = 8

# 質問カテゴリ定義（プロンプトへの指示とUI表示ラベルを兼ねる）
QUESTION_CATEGORIES = {
    "deep_dive":   "深掘り系（自己PRのエピソードをさらに具体的に聞く）",
    "motivation":  "志望動機系（なぜこの企業・職種なのかを問う）",
    "weakness":    "弱み・失敗系（課題や反省点を引き出す）",
    "situational": "状況対応系（もし〜だったらどうするかを問う）",
}

CATEGORY_LABELS = {
    "deep_dive":   "🔍 深掘り",
    "motivation":  "💡 動機",
    "weakness":    "🌱 弱み・失敗",
    "situational": "🎯 状況対応",
}

PREDICT_PROMPT_TEMPLATE = """あなたは経験豊富な日本企業の新卒採用面接官です。
以下の【学生の自己PR】と【インタビュー記録】を読み、この学生が面接本番で受けそうな
想定質問と、その質問に対する模範回答例を{num_questions}問分作成してください。
{hallucination_guard}
{injection_note}
【学生の自己PR】
{pr_block}

【インタビュー記録】
{interview_block}

{rag_block}
【質問カテゴリの配分（必ず守ること）】
・deep_dive（深掘り系）: 3問
・motivation（志望動機系）: 2問
・weakness（弱み・失敗系）: 2問
・situational（状況対応系）: 1問

【各質問・回答の作成ルール】
・質問文は面接官が実際に口頭で問いかける自然な日本語にすること（敬体）。
・模範回答例は「学生がそのまま声に出して答えられる」水準のフル文章にすること（敬体、200文字前後）。
・模範回答例はインタビュー記録・自己PRに記載された事実のみを使い、存在しない数字・エピソードを創作してはならない。
・情報が足りない部分（特に志望動機系・状況対応系）は、学生の価値観や行動傾向から論理的に推定して書いてよいが、
  「〜だと考えています」「〜したいと思っています」など推定であることが伝わる表現にすること。
・8問全体で同じエピソードを繰り返し使わず、自己PRの異なる側面を引き出す内容にすること。

【出力ルール】
必ず以下のJSON配列形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

[
  {{
    "category": "deep_dive または motivation または weakness または situational のいずれか",
    "question": "面接官の質問文（口頭で問いかける自然な日本語）",
    "model_answer": "模範回答例（そのまま声に出せるフル文章、敬体、200文字前後）"
  }},
  ...（{num_questions}問分）
]
"""


def generate_predicted_questions(
    model: str,
    pr_text: str,
    conversation_history: str,
    rag_block: str = "",
) -> tuple[list[dict], bool, str | None]:
    """想定質問と模範回答例を生成する。

    Args:
        model: Ollamaモデル名
        pr_text: 完成した自己PR本文
        conversation_history: build_conversation_history() の戻り値
        rag_block: RAGから取得した企業情報ブロック（任意）

    Returns:
        (questions: list[dict], ok: bool, error_msg: str | None)

        questions の各要素:
            {
                "category": str,          # "deep_dive" | "motivation" | "weakness" | "situational"
                "category_label": str,    # UI表示用ラベル
                "question": str,          # 質問文
                "model_answer": str,      # 模範回答例
            }
    """
    pr_block = wrap_user_content(pr_text)
    interview_block = wrap_user_content(conversation_history)

    prompt = PREDICT_PROMPT_TEMPLATE.format(
        num_questions=NUM_QUESTIONS,
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        pr_block=pr_block,
        interview_block=interview_block,
        rag_block=f"【企業情報（参考）】\n{rag_block}\n" if rag_block.strip() else "",
    )

    fallback: list[dict] = []
    data, ok, error_msg = call_ollama_with_json_array_retry(
        model=model,
        prompt=prompt,
        item_required_keys=["category", "question", "model_answer"],
        fallback=fallback,
        max_retries=2,
    )

    if not ok:
        return [], False, error_msg

    # カテゴリラベルを付与・検証
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        question = str(item.get("question", "")).strip()
        model_answer = str(item.get("model_answer", "")).strip()
        if not question or not model_answer:
            continue
        result.append({
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, "📝 その他"),
            "question": question,
            "model_answer": model_answer,
        })

    return result, True, None


# ============================================================
# RAG資料ベース版（自己PR・インタビュー履歴を前提にしない独立生成）
# ============================================================

RAG_PREDICT_PROMPT_TEMPLATE = """あなたは経験豊富な日本企業の新卒採用面接官です。
以下の【学生の履歴書情報】と【志望企業の情報】を読み、この学生が面接本番で受けそうな
想定質問と、その質問に対する模範回答例を{num_questions}問分作成してください。
{hallucination_guard}
{injection_note}
【学生の履歴書情報】
{resume_block}

【志望企業の情報】
{company_block}

【質問カテゴリの配分（必ず守ること）】
・deep_dive（深掘り系）: 3問
・motivation（志望動機系）: 2問
・weakness（弱み・失敗系）: 2問
・situational（状況対応系）: 1問

【各質問・回答の作成ルール】
・質問文は面接官が実際に口頭で問いかける自然な日本語にすること（敬体）。
・模範回答例は「学生がそのまま声に出して答えられる」水準のフル文章にすること（敬体、200文字前後）。
・模範回答例は履歴書情報・企業情報に記載された事実のみを使い、存在しない数字・エピソードを創作してはならない。
・履歴書情報だけでは分からない部分（特に志望動機系・状況対応系）は、企業情報と一般的な就活生の
  価値観から論理的に推定して書いてよいが、「〜だと考えています」「〜したいと思っています」など
  推定であることが伝わる表現にすること。
・8問全体で同じ内容を繰り返し使わず、履歴書の異なる側面を引き出す内容にすること。

【出力ルール】
必ず以下のJSON配列形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

[
  {{
    "category": "deep_dive または motivation または weakness または situational のいずれか",
    "question": "面接官の質問文（口頭で問いかける自然な日本語）",
    "model_answer": "模範回答例（そのまま声に出せるフル文章、敬体、200文字前後）"
  }},
  ...（{num_questions}問分）
]
"""


def generate_predicted_questions_from_rag(
    model: str,
    resume_block: str,
    company_block: str,
) -> tuple[list[dict], bool, str | None]:
    """履歴書・企業情報（RAG検索結果）のみから想定質問と模範回答例を生成する。

    自己PRやインタビュー履歴の完成を前提にしない、独立した入口。
    「想定質問生成」を単独ページとして使う場合に利用する。

    Args:
        model: Ollamaモデル名
        resume_block: 履歴書KBから検索・整形した参考テキスト（rag.format_context()の出力等）
        company_block: 企業KBから検索・整形した参考テキスト（同上）

    Returns:
        (questions: list[dict], ok: bool, error_msg: str | None)
        questions の各要素の形式は generate_predicted_questions() と同じ。
    """
    safe_resume = wrap_user_content(resume_block) if resume_block.strip() else "（履歴書情報なし）"
    safe_company = wrap_user_content(company_block) if company_block.strip() else "（企業情報なし）"

    prompt = RAG_PREDICT_PROMPT_TEMPLATE.format(
        num_questions=NUM_QUESTIONS,
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        resume_block=safe_resume,
        company_block=safe_company,
    )

    fallback: list[dict] = []
    data, ok, error_msg = call_ollama_with_json_array_retry(
        model=model,
        prompt=prompt,
        item_required_keys=["category", "question", "model_answer"],
        fallback=fallback,
        max_retries=2,
    )

    if not ok:
        return [], False, error_msg

    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        question = str(item.get("question", "")).strip()
        model_answer = str(item.get("model_answer", "")).strip()
        if not question or not model_answer:
            continue
        result.append({
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, "📝 その他"),
            "question": question,
            "model_answer": model_answer,
        })

    return result, True, None
