# -*- coding: utf-8 -*-
"""
industry_engine.py
------------------
業界別面接モード定義モジュール。

各業界ごとに以下をカスタマイズする:
- テーマ構成（MOCK_INTERVIEW_THEMES の差し替え）
- 評価軸（EVAL_AXES の差し替え）
- 面接官へのプロンプト追加指示
- 代表的な質問のヒント

使い方:
    from industry_engine import get_industry, list_industries, get_themes_for_industry, get_eval_axes_for_industry
"""

from __future__ import annotations

# ============================================================
# 業界定義
# ============================================================

INDUSTRIES: dict[str, dict] = {
    "general": {
        "key": "general",
        "name": "汎用（業界指定なし）",
        "icon": "🏢",
        "description": "業界を限定せず、一般的な新卒採用面接を想定した標準モード。",
        "eval_axes": ["論理構成", "具体性", "熱意", "企業理解度", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": (
                    "面接冒頭として、学生の大学・学部・専攻、これまで力を入れてきたこと、"
                    "自己紹介として話しやすい人柄や関心を簡潔に引き出す。"
                ),
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "gakuchika",
                "title": "ガクチカ（学生時代に力を入れたこと）",
                "goal": "学生時代に最も力を入れた活動の内容・役割・課題・行動・結果を、具体的な数字や固有名詞を交えて引き出す。",
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "motivation",
                "title": "志望動機",
                "goal": "なぜこの業界・企業を志望するのか、企業のどの点に魅力を感じているのかを具体的に引き出す。",
                "base_questions": (2, 2),
                "max_followups": (2, 3),
            },
            {
                "key": "company_fit",
                "title": "企業理解",
                "goal": "企業の事業内容や求める人物像をどの程度理解しているか、自分の強みとどう結びつくかを引き出す。",
                "base_questions": (1, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "学生から面接官への質問（逆質問）を促し、入社意欲や企業理解の深さを確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": "",  # 追加指示なし
    },

    "it": {
        "key": "it",
        "name": "IT・テクノロジー",
        "icon": "💻",
        "description": "論理的思考・技術への関心・問題解決力を重視するITエンジニア・総合職向け。",
        "eval_axes": ["論理構成", "技術理解度", "問題解決力", "学習意欲", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": "学部・専攻・技術的な関心領域・得意なスキルを簡潔に引き出す。",
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "gakuchika",
                "title": "技術的な取り組み（ガクチカ）",
                "goal": (
                    "開発経験・研究・ハッカソン・個人開発など、技術的な活動での"
                    "課題・アプローチ・工夫・成果を引き出す。具体的な技術スタックや数値も確認する。"
                ),
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "problem_solving",
                "title": "問題解決・論理的思考",
                "goal": (
                    "技術的または非技術的な問題に直面したとき、どのように分解・分析・解決したかを引き出す。"
                    "「なぜその手段を選んだか」の根拠を深掘りする。"
                ),
                "base_questions": (1, 2),
                "max_followups": (2, 3),
            },
            {
                "key": "motivation",
                "title": "志望動機・キャリアビジョン",
                "goal": (
                    "IT業界・当該企業を志望する理由と、5年後のキャリアイメージを引き出す。"
                    "技術的な成長意欲や事業への関心の深さを確認する。"
                ),
                "base_questions": (2, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "技術的・事業的な視点から鋭い逆質問ができるか確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": (
            "【業界別追加指示: IT・テクノロジー】\n"
            "・技術的な経験や思考プロセスを深掘りしてください。\n"
            "・「なぜその技術/アプローチを選んだか」の根拠を必ず確認してください。\n"
            "・数字・スケール（ユーザー数・処理件数・改善率など）を積極的に引き出してください。\n"
            "・学習意欲（新しい技術への関心・自己学習の習慣）についても触れてください。\n"
        ),
    },

    "consulting": {
        "key": "consulting",
        "name": "コンサルティング",
        "icon": "📊",
        "description": "論理思考・定量的分析・問題構造化能力を重視するコンサル向け選考。",
        "eval_axes": ["論理構成", "問題分解力", "定量思考", "リーダーシップ", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": "強みと実績を簡潔かつ構造的に自己紹介できるかを確認する。",
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "leadership",
                "title": "リーダーシップ・変革経験",
                "goal": (
                    "チームや組織を動かした経験・課題を定義して解決した経験を引き出す。"
                    "役割・意思決定・結果の定量的な説明を求める。"
                ),
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "case_thinking",
                "title": "問題解決・ケース的思考",
                "goal": (
                    "複雑な課題をどのように分解・優先順位付けして解決したか。"
                    "仮説思考・MECEな分解・根拠のある提案ができるかを確認する。"
                ),
                "base_questions": (2, 2),
                "max_followups": (3, 3),
            },
            {
                "key": "motivation",
                "title": "志望動機・コンサル理解",
                "goal": (
                    "なぜコンサルを志望するか、コンサルタントの仕事をどう理解しているか。"
                    "クライアントワーク・プロジェクト型の働き方への覚悟も確認する。"
                ),
                "base_questions": (1, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "事業・戦略・キャリアパスについて鋭い逆質問ができるかを確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": (
            "【業界別追加指示: コンサルティング】\n"
            "・回答の論理構成（結論→理由→具体例）を特に意識して深掘りしてください。\n"
            "・「その課題をどのように分解しましたか？」「なぜその優先順位にしましたか？」を積極的に問ってください。\n"
            "・数字・規模感・インパクトを必ず引き出してください。\n"
            "・「もし〇〇だったら？」という仮説的問いも活用してください。\n"
        ),
    },

    "finance": {
        "key": "finance",
        "name": "金融・銀行・証券",
        "icon": "🏦",
        "description": "誠実さ・責任感・顧客志向を重視する金融機関向け。ガクチカの粘り強さも重要。",
        "eval_axes": ["誠実さ・責任感", "論理構成", "顧客志向", "ストレス耐性", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": "人柄・専攻・金融への関心の入口を丁寧に引き出す。",
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "gakuchika",
                "title": "ガクチカ（粘り強さ・達成志向）",
                "goal": (
                    "困難を乗り越えた経験・目標に向けて粘り強く取り組んだ経験を引き出す。"
                    "プロセスでの誠実さや責任感も確認する。"
                ),
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "stress_resilience",
                "title": "ストレス耐性・困難への対処",
                "goal": (
                    "プレッシャーの高い状況・失敗経験からの立ち直り方を引き出す。"
                    "感情コントロール・再挑戦へのアプローチを確認する。"
                ),
                "base_questions": (1, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "motivation",
                "title": "志望動機・金融業界理解",
                "goal": (
                    "なぜ金融・この機関を志望するか、顧客・社会への貢献意識を引き出す。"
                    "業界の役割についての理解度も確認する。"
                ),
                "base_questions": (2, 2),
                "max_followups": (2, 3),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "入行後のキャリアや働き方について具体的な関心を示せるか確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": (
            "【業界別追加指示: 金融・銀行・証券】\n"
            "・誠実さ・責任感が伝わるエピソードを丁寧に深掘りしてください。\n"
            "・「そのとき周囲にどう働きかけましたか？」「約束や期日を守るために何をしましたか？」を確認してください。\n"
            "・数字（貢献量・改善率・人数など）を引き出しつつ、過程の誠実さも評価してください。\n"
            "・高圧的にならず、信頼感のある対話を心がけてください。\n"
        ),
    },

    "manufacturing": {
        "key": "manufacturing",
        "name": "メーカー・製造業",
        "icon": "🏭",
        "description": "ものづくりへの情熱・チームワーク・長期的視点を重視するメーカー向け。",
        "eval_axes": ["チームワーク", "粘り強さ・達成志向", "論理構成", "ものづくり志向", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": "専攻・研究テーマ・ものづくりや技術への関心を引き出す。",
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "gakuchika",
                "title": "ガクチカ（チームワーク・粘り強さ）",
                "goal": (
                    "チームで成果を出した経験・困難な目標に長期的に取り組んだ経験を引き出す。"
                    "役割・貢献・チーム内の関係構築も確認する。"
                ),
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "research_technical",
                "title": "研究・技術的経験",
                "goal": (
                    "卒業研究・技術的なプロジェクトの内容・課題・アプローチ・成果を引き出す。"
                    "専門性をどう仕事に活かすかも確認する。"
                ),
                "base_questions": (1, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "motivation",
                "title": "志望動機・ものづくりへの想い",
                "goal": (
                    "なぜメーカー・この企業を志望するか、製品や技術への具体的な関心を引き出す。"
                    "長期的なキャリアビジョンも確認する。"
                ),
                "base_questions": (2, 2),
                "max_followups": (2, 3),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "製品・技術・職場環境についての具体的な関心を示せるか確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": (
            "【業界別追加指示: メーカー・製造業】\n"
            "・チームの中での役割・貢献・調整力を具体的に引き出してください。\n"
            "・「その活動を長期間続けられた理由は何ですか？」と粘り強さを深掘りしてください。\n"
            "・ものづくり・技術への情熱が伝わるエピソードを引き出してください。\n"
            "・温かく安心感のある雰囲気で面接を進めてください。\n"
        ),
    },

    "trading": {
        "key": "trading",
        "name": "総合商社・専門商社",
        "icon": "🌏",
        "description": "グローバル志向・タフネス・ビジネス開発力を重視する商社向け。",
        "eval_axes": ["行動力・突破力", "グローバル志向", "論理構成", "リーダーシップ", "コミュニケーション力"],
        "themes": [
            {
                "key": "self_intro",
                "title": "自己紹介",
                "goal": "海外経験・語学力・チャレンジ精神を含む自己紹介を引き出す。",
                "base_questions": (1, 1),
                "max_followups": (0, 1),
            },
            {
                "key": "gakuchika",
                "title": "ガクチカ（挑戦・突破経験）",
                "goal": (
                    "困難な状況に飛び込んで成果を出した経験を引き出す。"
                    "海外・異文化経験・起業的行動・大きな目標への挑戦が特に重視される。"
                ),
                "base_questions": (2, 3),
                "max_followups": (4, 4),
            },
            {
                "key": "leadership_initiative",
                "title": "リーダーシップ・主体性",
                "goal": (
                    "自ら課題を発見し率先して動いた経験を引き出す。"
                    "組織を動かした経験・ゼロからの立ち上げ経験も確認する。"
                ),
                "base_questions": (1, 2),
                "max_followups": (2, 3),
            },
            {
                "key": "motivation",
                "title": "志望動機・商社の理解",
                "goal": (
                    "なぜ商社・この企業を志望するか、トレーディングや事業投資への理解を確認する。"
                    "グローバルに働きたい理由・具体的なビジネスイメージも引き出す。"
                ),
                "base_questions": (2, 2),
                "max_followups": (2, 2),
            },
            {
                "key": "reverse_q",
                "title": "逆質問",
                "goal": "海外赴任・事業投資・キャリアパスについて意欲的な逆質問ができるか確認する。",
                "base_questions": (1, 1),
                "max_followups": (1, 1),
            },
        ],
        "industry_prompt": (
            "【業界別追加指示: 総合商社・専門商社】\n"
            "・「なぜそのタイミングで動きましたか？」「周囲が反対する中でどう突き進みましたか？」と行動力を深掘りしてください。\n"
            "・スケールの大きさ・グローバルな視野を引き出すことを意識してください。\n"
            "・タフネス・逆境での粘り強さも評価ポイントです。\n"
            "・エネルギッシュで対話を楽しむ雰囲気で進めてください。\n"
        ),
    },
}

DEFAULT_INDUSTRY_KEY = "general"


# ============================================================
# 公開API
# ============================================================

def get_industry(key: str) -> dict:
    """業界キーから業界定義を返す。不明なキーはgeneralにフォールバック。"""
    return INDUSTRIES.get(key, INDUSTRIES[DEFAULT_INDUSTRY_KEY])


def list_industries() -> list[dict]:
    """全業界のリストを返す（UI用）。"""
    return list(INDUSTRIES.values())


def get_themes_for_industry(key: str) -> list[dict]:
    """業界に対応するテーマリストを返す。"""
    return get_industry(key)["themes"]


def get_eval_axes_for_industry(key: str) -> list[str]:
    """業界に対応する評価軸リストを返す。"""
    return get_industry(key)["eval_axes"]


def get_industry_prompt(key: str) -> str:
    """業界固有のプロンプト追加指示を返す。"""
    return get_industry(key).get("industry_prompt", "")


def build_industry_prompt_block(key: str) -> str:
    """プロンプトに差し込む業界固有の指示ブロックを返す。空の場合は空文字。"""
    prompt = get_industry_prompt(key)
    return f"\n{prompt}\n" if prompt.strip() else ""
