"""
utils/industry_utils.py
------------------------
業界キー正規化・業界フィット度スコアのユーティリティ。

提供するもの:
    INDUSTRY_KEYS           - 全モジュール共通の業界キー一覧
    normalize_industry_fit() - LLMが返した industry_fit dict のキー正規化
"""

from __future__ import annotations

# ============================================================
# 定数
# ============================================================

# 全モジュール共通の業界キー（ここで一元管理する）
INDUSTRY_KEYS: list[str] = [
    "メーカー",
    "IT・Web",
    "コンサル",
    "金融",
    "マスコミ・広告",
    "官公庁・非営利",
]

# LLMがキー名を微妙に変えて返してくることへの対応テーブル
_INDUSTRY_KEY_ALIASES: dict[str, str] = {
    "官公庁": "官公庁・非営利",
    "官公庁/非営利": "官公庁・非営利",
    "IT": "IT・Web",
    "IT/Web": "IT・Web",
    "マスコミ": "マスコミ・広告",
    "マスコミ/広告": "マスコミ・広告",
}


# ============================================================
# 公開API
# ============================================================

def normalize_industry_fit(industry_fit: dict) -> dict:
    """LLMが返した industry_fit dict のキーを正規化し、スコアを1〜5にクランプして返す。

    - キー名の表記ゆれを _INDUSTRY_KEY_ALIASES で吸収する
    - 欠落しているキーはスコア1・理由「情報不足のため評価困難」で補完する
    - スコアは int に変換し、1〜5 の範囲にクランプする

    Args:
        industry_fit: LLMが返した業界フィット度の生dict

    Returns:
        INDUSTRY_KEYS に正規化・補完された dict
    """
    if not isinstance(industry_fit, dict):
        industry_fit = {}

    # エイリアスで正規化
    normalized: dict = {}
    for raw_key, value in industry_fit.items():
        canonical = _INDUSTRY_KEY_ALIASES.get(raw_key, raw_key)
        normalized[canonical] = value

    result: dict = {}
    for key in INDUSTRY_KEYS:
        entry = normalized.get(key, {})
        if not isinstance(entry, dict):
            entry = {}
        try:
            score = max(1, min(5, int(entry.get("score", 1))))
        except (TypeError, ValueError):
            score = 1
        result[key] = {
            "score": score,
            "reason": str(entry.get("reason", "情報不足のため評価困難")),
        }
    return result
