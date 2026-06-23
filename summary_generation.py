"""
summary_generation.py
----------------------
インタビュー完了後に、会話全体から「面接サマリー」を生成するモジュール。

生成される内容:
1. 強み（3〜5項目）: インタビューから読み取れる学生の強み・特性
2. 弱み・成長余地（2〜3項目）: 控えめに、建設的な表現で提示
3. 向いている職種・環境（フリーテキスト）
4. 業界別フィット度（メーカー/IT/コンサル/金融/マスコミ/官公庁の6軸、各5段階）
5. 面接官への一言（総評）

設計方針:
- ハルシネーション防止: 強み・弱みはインタビュー中の具体的な発言を
  必ず根拠として引用する形式にし、AIが「それっぽい強み」を創作するリスクを下げる。
- 業界別フィット度は「○○が高いからメーカー向き」のような論拠も合わせて出力させ、
  スコアだけの結果にならないようにする。
- utils.py の call_ollama_with_json_retry を使い、JSON出力の安定性を確保する。
- Prompt Injection 対策として、会話履歴も wrap_user_content でラッピングする。
"""

from __future__ import annotations

import logging

from utils import (
    HALLUCINATION_GUARD,
    INDUSTRY_KEYS,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    normalize_industry_fit,
    wrap_user_content,
)

logger = logging.getLogger(__name__)

# ============================================================
# 定数
# ============================================================

# INDUSTRY_KEYS は utils.py で一元管理しているためここでの再定義は不要
# （from utils import INDUSTRY_KEYS でインポート済み）

SUMMARY_PROMPT_TEMPLATE = """あなたは経験豊富な日本の新卒採用コンサルタントです。
以下の【面接官と学生のインタビュー記録】を注意深く読み、学生のプロフィールを分析してください。
{hallucination_guard}
{injection_note}
【インタビュー記録】
{interview_block}

【分析のルール】
・強み・弱みは、必ず記録中の具体的な発言・エピソードを根拠として示すこと（根拠のない強みは書かない）。
・弱みは「批判」ではなく「成長余地」「改善のヒント」として建設的に表現すること。
・業界別フィット度は、学生の特性・価値観・経験がその業界に合致するかを1〜5の整数で評価し、
  必ず「そう判断した理由（根拠）」をひとこと添えること。
・向いている職種・環境は、職種名だけでなく「なぜその職種・環境に向いているか」も書くこと。
・記録が少ない/情報が足りない業界・職種については、スコアを低め（2以下）にし、
  理由欄に「情報不足のため評価困難」と明記すること（推測による高評価をしない）。

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

{{
  "strengths": [
    {{"point": "強み1（簡潔なタイトル）", "evidence": "根拠となる発言・エピソードの要約（1〜2文）"}},
    {{"point": "強み2", "evidence": "..."}},
    {{"point": "強み3", "evidence": "..."}}
  ],
  "weaknesses": [
    {{"point": "成長余地1（建設的な表現）", "evidence": "根拠または改善のヒント（1文）"}},
    {{"point": "成長余地2", "evidence": "..."}}
  ],
  "fit_roles": "向いている職種・環境の説明（職種名と理由をセットで、2〜4文程度）",
  "industry_fit": {{
    "メーカー": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}},
    "IT・Web": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}},
    "コンサル": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}},
    "金融": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}},
    "マスコミ・広告": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}},
    "官公庁・非営利": {{"score": 1〜5の整数, "reason": "判断根拠（1文）"}}
  }},
  "overall_comment": "面接官・就活アドバイザーとしての総評（3〜5文。具体的で建設的な内容）"
}}
"""


# ============================================================
# メイン関数
# ============================================================

def generate_interview_summary(model: str, conversation_history: str) -> dict | None:
    """インタビュー会話履歴から面接サマリーを生成する。

    Args:
        model: Ollamaモデル名
        conversation_history: build_conversation_history() の戻り値

    Returns:
        {
          "strengths": [{"point": str, "evidence": str}, ...],
          "weaknesses": [{"point": str, "evidence": str}, ...],
          "fit_roles": str,
          "industry_fit": {
              "メーカー": {"score": int, "reason": str}, ...
          },
          "overall_comment": str,
          "ok": bool,
          "error_msg": str | None,
        }
        or None（例外発生時）
    """
    # 会話履歴をInjectionガード付きでラッピング
    interview_block = wrap_user_content(conversation_history)

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        interview_block=interview_block,
    )

    fallback = {
        "strengths": [],
        "weaknesses": [],
        "fit_roles": "",
        "industry_fit": {k: {"score": 0, "reason": "生成に失敗しました"} for k in INDUSTRY_KEYS},
        "overall_comment": "",
    }

    try:
        result = call_ollama_with_json_retry(
            model=model,
            prompt=prompt,
            required_keys=["strengths", "weaknesses", "fit_roles", "industry_fit", "overall_comment"],
            fallback=fallback,
            max_retries=2,
        )
        # industry_fit のキー正規化・スコアクランプを utils の共通関数で処理
        if isinstance(result.get("industry_fit"), dict):
            result["industry_fit"] = normalize_industry_fit(result["industry_fit"])
        return result
    except Exception as e:
        logger.error("面接サマリー生成失敗", exc_info=True)
        return {**fallback, "ok": False, "error_msg": str(e)}
