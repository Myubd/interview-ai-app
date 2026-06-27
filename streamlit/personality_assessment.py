"""
personality_assessment.py
--------------------------

就活向け性格診断モジュール

v2改善内容
- Big Five 30問化
- consistency_score追加
- percentile追加 → v3で削除（簡易計算で統計的根拠が薄いため）
- industry_fit数式化（Part2）
- recommended_roles追加（Part2）
"""

from __future__ import annotations

from utils import (
    HALLUCINATION_GUARD,
    INDUSTRY_KEYS,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_retry,
    normalize_industry_fit,
    wrap_user_content,
)

# ============================================================
# Big Five
# ============================================================

AXES = {
    "extraversion": "外向性（積極性・社交性）",
    "conscientiousness": "誠実性（計画性・責任感）",
    "agreeableness": "協調性（思いやり・共感力）",
    "openness": "開放性（好奇心・創造性）",
    "neuroticism": "情緒安定性（ストレス耐性・冷静さ）",
}

# ============================================================
# 30問版
# ============================================================

QUESTIONS: list[dict] = [

    # =====================================================
    # 外向性
    # =====================================================

    {
        "id": 1,
        "axis": "extraversion",
        "text": "初対面の人とでも、すぐに打ち解けて話せる方だ",
        "reverse": False,
    },
    {
        "id": 2,
        "axis": "extraversion",
        "text": "グループのなかで自分から発言・提案することが多い",
        "reverse": False,
    },
    {
        "id": 3,
        "axis": "extraversion",
        "text": "にぎやかな場やイベントよりも、静かな環境の方が落ち着く",
        "reverse": True,
    },
    {
        "id": 4,
        "axis": "extraversion",
        "text": "人前で話すことに、あまり緊張しない",
        "reverse": False,
    },
    {
        "id": 21,
        "axis": "extraversion",
        "text": "新しい人間関係を作ることに抵抗が少ない",
        "reverse": False,
    },
    {
        "id": 22,
        "axis": "extraversion",
        "text": "一人で過ごす時間が何より好きだ",
        "reverse": True,
    },

    # =====================================================
    # 誠実性
    # =====================================================

    {
        "id": 5,
        "axis": "conscientiousness",
        "text": "締め切りや約束を守ることを、強く意識して行動している",
        "reverse": False,
    },
    {
        "id": 6,
        "axis": "conscientiousness",
        "text": "物事を始める前に、計画や段取りを立ててから取り組む",
        "reverse": False,
    },
    {
        "id": 7,
        "axis": "conscientiousness",
        "text": "やりかけの作業をそのままにしておくことがよくある",
        "reverse": True,
    },
    {
        "id": 8,
        "axis": "conscientiousness",
        "text": "細かいミスを防ぐため、見直しや確認を丁寧に行う方だ",
        "reverse": False,
    },
    {
        "id": 23,
        "axis": "conscientiousness",
        "text": "目標達成のために継続的な努力ができる",
        "reverse": False,
    },
    {
        "id": 24,
        "axis": "conscientiousness",
        "text": "気分次第で予定を変更することが多い",
        "reverse": True,
    },

    # =====================================================
    # 協調性
    # =====================================================

    {
        "id": 9,
        "axis": "agreeableness",
        "text": "チームで動くとき、メンバーの意見を引き出すよう心がける",
        "reverse": False,
    },
    {
        "id": 10,
        "axis": "agreeableness",
        "text": "困っている人がいると、自然に手を貸したくなる",
        "reverse": False,
    },
    {
        "id": 11,
        "axis": "agreeableness",
        "text": "意見の対立があっても、自分の主張を曲げないことが多い",
        "reverse": True,
    },
    {
        "id": 12,
        "axis": "agreeableness",
        "text": "相手の立場に立って考えることが得意だと思う",
        "reverse": False,
    },
    {
        "id": 25,
        "axis": "agreeableness",
        "text": "相手の気持ちの変化に気付きやすい",
        "reverse": False,
    },
    {
        "id": 26,
        "axis": "agreeableness",
        "text": "競争では協調より勝利を優先する",
        "reverse": True,
    },

    # =====================================================
    # 開放性
    # =====================================================

    {
        "id": 13,
        "axis": "openness",
        "text": "新しい分野の知識や技術を学ぶことが楽しい",
        "reverse": False,
    },
    {
        "id": 14,
        "axis": "openness",
        "text": "従来のやり方より、新しいアプローチを試してみたくなる方だ",
        "reverse": False,
    },
    {
        "id": 15,
        "axis": "openness",
        "text": "変化よりも安定・慣れた環境の方が仕事しやすい",
        "reverse": True,
    },
    {
        "id": 16,
        "axis": "openness",
        "text": "芸術・文化・哲学など、答えのない問いに興味を持つことが多い",
        "reverse": False,
    },
    {
        "id": 27,
        "axis": "openness",
        "text": "未知の分野にも積極的に挑戦したい",
        "reverse": False,
    },
    {
        "id": 28,
        "axis": "openness",
        "text": "新しい方法より慣れた方法を好む",
        "reverse": True,
    },

    # =====================================================
    # 情緒安定性
    # =====================================================

    {
        "id": 17,
        "axis": "neuroticism",
        "text": "プレッシャーがかかる場面でも、比較的冷静に対応できる",
        "reverse": False,
    },
    {
        "id": 18,
        "axis": "neuroticism",
        "text": "失敗してもすぐに気持ちを切り替えられる方だ",
        "reverse": False,
    },
    {
        "id": 19,
        "axis": "neuroticism",
        "text": "小さなことが気になって、なかなか頭から離れないことが多い",
        "reverse": True,
    },
    {
        "id": 20,
        "axis": "neuroticism",
        "text": "批判や否定的なフィードバックを受けても、落ち込みすぎない",
        "reverse": False,
    },
    {
        "id": 29,
        "axis": "neuroticism",
        "text": "予想外のトラブルにも冷静に対応できる",
        "reverse": False,
    },
    {
        "id": 30,
        "axis": "neuroticism",
        "text": "失敗を長く引きずることが多い",
        "reverse": True,
    },
]

SCALE_LABELS = {
    1: "全く当てはまらない",
    2: "あまり当てはまらない",
    3: "どちらともいえない",
    4: "やや当てはまる",
    5: "とても当てはまる",
}

TOTAL_QUESTIONS = len(QUESTIONS)

# ============================================================
# スコア集計
# ============================================================

def compute_axis_scores(answers: dict[int, int]) -> dict[str, float]:
    axis_totals = {axis: [] for axis in AXES}

    for q in QUESTIONS:
        raw = answers.get(q["id"])
        if raw is None:
            continue
        score = float(raw)
        if q["reverse"]:
            score = 6.0 - score
        axis_totals[q["axis"]].append(score)

    return {
        axis: round(sum(vals) / len(vals), 2) if vals else 0.0
        for axis, vals in axis_totals.items()
    }


# ============================================================
# 回答整合性（Consistency）
# ============================================================

def compute_consistency_score(answers: dict[int, int]) -> int:
    """回答の一貫性を簡易評価する。

    100点満点。70以上なら概ね信頼可能。
    """
    contradiction_pairs = [
        # 外向性
        (1, 3),
        (2, 22),
        # 誠実性
        (5, 7),
        (6, 24),
        # 協調性
        (9, 11),
        (10, 26),
        # 開放性
        (13, 15),
        (14, 28),
        # 情緒安定性
        (17, 19),
        (18, 30),
    ]

    score = 100
    for positive_q, reverse_q in contradiction_pairs:
        p = answers.get(positive_q)
        r = answers.get(reverse_q)
        if p is None or r is None:
            continue

        expected_reverse = 6 - p
        diff = abs(expected_reverse - r)
        if diff >= 3:
            score -= 8
        elif diff == 2:
            score -= 4

    return max(score, 0)


# ============================================================
# 業界適性
# ============================================================

def calculate_industry_fit(axis_scores: dict[str, float]) -> dict[str, int]:
    e = axis_scores["extraversion"]
    c = axis_scores["conscientiousness"]
    a = axis_scores["agreeableness"]
    o = axis_scores["openness"]
    n = axis_scores["neuroticism"]

    raw_scores = {
        "メーカー": 0.45 * c + 0.30 * a + 0.25 * n,
        "IT・Web": 0.45 * o + 0.35 * c + 0.20 * e,
        "コンサル": 0.35 * e + 0.35 * o + 0.30 * c,
        "金融": 0.50 * c + 0.30 * n + 0.20 * a,
        "マスコミ・広告": 0.45 * e + 0.35 * o + 0.20 * a,
        "官公庁・非営利": 0.40 * a + 0.35 * c + 0.25 * n,
    }

    return {
        industry: max(1, min(5, int(round(score))))
        for industry, score in raw_scores.items()
    }


# ============================================================
# おすすめ職種
# ============================================================

def calculate_recommended_roles(axis_scores: dict[str, float]) -> list[dict]:
    e = axis_scores["extraversion"]
    c = axis_scores["conscientiousness"]
    a = axis_scores["agreeableness"]
    o = axis_scores["openness"]
    n = axis_scores["neuroticism"]

    role_scores = [
        ("法人営業", 0.50 * e + 0.30 * a + 0.20 * c),
        ("人事", 0.40 * a + 0.30 * e + 0.30 * c),
        ("商品企画", 0.50 * o + 0.30 * e + 0.20 * c),
        ("マーケティング", 0.40 * o + 0.30 * e + 0.30 * c),
        ("コンサルタント", 0.35 * e + 0.35 * o + 0.30 * c),
        ("エンジニア", 0.45 * o + 0.35 * c + 0.20 * n),
        ("研究開発", 0.55 * o + 0.25 * c + 0.20 * n),
        ("経理・財務", 0.60 * c + 0.25 * n + 0.15 * a),
    ]

    role_scores.sort(key=lambda x: x[1], reverse=True)

    return [
        {"role": role, "score": round(score, 2)}
        for role, score in role_scores[:3]
    ]


# ============================================================
# AI結果生成プロンプト
# ============================================================

RESULT_PROMPT_TEMPLATE = """
あなたは経験豊富な就活キャリアアドバイザーです。

{hallucination_guard}
{injection_note}

以下のスコアのみを根拠として分析してください。

【Big Fiveスコア】
{scores_text}

【回答整合性】
{consistency_score}/100

【おすすめ職種】
{recommended_roles}

【業界適性】
{industry_fit_scores}

重要:
・存在しない性格特性を創作しない
・スコアに表れていない能力を推測しない
・断定しすぎない
・就活向けに実践的な助言を行う

必ずJSONのみ返してください

{{
  "personality_summary":"",

  "strengths":[
    {{
      "point":"",
      "detail":""
    }}
  ],

  "cautions":[
    {{
      "point":"",
      "hint":""
    }}
  ],

  "fit_environments":"",

  "industry_fit_reason":{{
    "メーカー":"",
    "IT・Web":"",
    "コンサル":"",
    "金融":"",
    "マスコミ・広告":"",
    "官公庁・非営利":""
  }},

  "interview_strengths":[
    ""
  ],

  "interview_risks":[
    ""
  ],

  "interview_tips":""
}}
"""

# ============================================================
# AI結果生成
# ============================================================

def generate_personality_result(
    model: str,
    answers: dict[int, int],
    axis_scores: dict[str, float],
) -> dict:
    consistency_score = compute_consistency_score(answers)
    industry_fit_scores = calculate_industry_fit(axis_scores)
    recommended_roles = calculate_recommended_roles(axis_scores)

    # --------------------------------------------------------
    # スコア表示用
    # --------------------------------------------------------
    scores_lines = []
    for axis_key, axis_label in AXES.items():
        score = axis_scores.get(axis_key, 0.0)
        rounded = int(round(score))
        bar = "█" * rounded + "░" * (5 - rounded)
        scores_lines.append(f"・{axis_label}: {score:.2f} [{bar}]")
    scores_text = "\n".join(scores_lines)

    # --------------------------------------------------------
    # 業界適性表示
    # --------------------------------------------------------
    industry_fit_text = "\n".join(
        f"{industry}: {score}/5" for industry, score in industry_fit_scores.items()
    )

    # --------------------------------------------------------
    # おすすめ職種表示
    # --------------------------------------------------------
    recommended_roles_text = "\n".join(
        f"{item['role']} (適性スコア {item['score']:.2f})" for item in recommended_roles
    )

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------
    prompt = RESULT_PROMPT_TEMPLATE.format(
        hallucination_guard=HALLUCINATION_GUARD,
        injection_note=USER_INPUT_BOUNDARY_NOTE,
        scores_text=scores_text,
        consistency_score=consistency_score,
        recommended_roles=recommended_roles_text,
        industry_fit_scores=industry_fit_text,
    )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------
    fallback = {
        "personality_summary": "",
        "strengths": [],
        "cautions": [],
        "fit_environments": "",
        "industry_fit_reason": {key: "生成失敗" for key in INDUSTRY_KEYS},
        "recommended_roles": [],
        "interview_strengths": [],
        "interview_risks": [],
        "interview_tips": "",
        "ok": False,
    }

    # --------------------------------------------------------
    # LLM呼び出し
    # --------------------------------------------------------
    try:
        result = call_ollama_with_json_retry(
            model=model,
            prompt=prompt,
            required_keys=[
                "personality_summary",
                "strengths",
                "cautions",
                "fit_environments",
                "industry_fit_reason",
                "interview_strengths",
                "interview_risks",
                "interview_tips",
            ],
            fallback=fallback,
            max_retries=2,
        )

        # ----------------------------------------------------
        # AI結果補正
        # ----------------------------------------------------
        # 注: call_ollama_with_json_retry は常に "ok" キーを含む dict を返すため、
        # ここで result["ok"] を補完する処理は不要（以前は到達しないコードがあった）。
        result["consistency_score"] = consistency_score

        result["industry_fit"] = {
            industry: {
                "score": score,
                "reason": result.get("industry_fit_reason", {}).get(industry, ""),
            }
            for industry, score in industry_fit_scores.items()
        }
        result["industry_fit"] = normalize_industry_fit(result["industry_fit"])

        # AIが変な職種を生成しても、数式計算結果（recommended_roles）を優先する
        result["recommended_roles"] = recommended_roles

        return result

    except Exception as e:
        return {
            **fallback,
            "consistency_score": consistency_score,
            "industry_fit": {
                k: {"score": v, "reason": "生成失敗"} for k, v in industry_fit_scores.items()
            },
            "recommended_roles": recommended_roles,
            "error_msg": str(e),
            "ok": False,
        }