# -*- coding: utf-8 -*-
"""
prompts/mock_interview.py
--------------------------
AI模擬面接（mock_interview_engine.py）の評価プロンプトテンプレート。

テンプレートは str.format() / f-string で展開する。
"""

MOCK_EVALUATION_PROMPT = """あなたは経験豊富な日本企業の新卒採用面接官です。
以下の【模擬面接の全記録】を読み、採用担当者として総括的なフィードバックを行ってください。
{hallucination_guard}
{injection_note}
{context_hint}
【模擬面接の全記録】
{safe_history}

【評価軸】（各1〜5点）
・論理構成: 回答がSTAR構成等で筋道立てて話せているか
・具体性: 数字や固有名詞、エピソードの解像度
・熱意: 意欲や前向きさが伝わるか
・企業理解度: 志望企業・業界への理解が感じられるか
・コミュニケーション力: 質問の意図を汲み、簡潔で分かりやすく話せているか

【作成してほしい内容】
1. overall_summary: 総合評価（3〜4文程度、敬体）
2. scores: 上記5軸のスコア
3. top_strengths: 良かった点を3つ（簡潔に）
4. top_improvements: 改善すべき点を3つ（具体的に、次にどうすればよいかも添える）
5. model_answers: 記録の中から特に重要な質問を3〜5個選び、各質問に対する模範回答例
   （学生の実際の発言内容をベースに、より良い表現に磨き上げたもの。記録にない事実は創作しないこと）
6. next_practice_points: 次回の模擬面接practice前に意識すべき練習ポイントを2〜3個

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

{{
  "overall_summary": "総合評価の文章",
  "scores": {{{axes_json_hint}}},
  "top_strengths": ["強み1", "強み2", "強み3"],
  "top_improvements": ["改善点1", "改善点2", "改善点3"],
  "model_answers": [
    {{"question": "質問文", "model_answer": "模範回答例"}}
  ],
  "next_practice_points": ["練習ポイント1", "練習ポイント2"]
}}
"""
