"""
pr_generation.py
-----------------
自己PRの「生成品質向上」まわりのロジックをまとめたモジュール。

含まれる機能:
1. generate_pr_variants : 3パターン（結果重視/プロセス重視/人柄重視）を1回の呼び出しでまとめて生成
2. evaluate_pr          : 採用担当者視点でのセルフ評価（4軸スコア + 総評 + 改善コメント）
3. generate_company_pr  : ベースの自己PRを特定企業の情報に合わせてカスタマイズ
4. refine_pr            : 既存の自己PRをベースにした微調整リライト

[変更点 v2]
- utils.HALLUCINATION_GUARD を全プロンプトに追加し、事実外創作を防止
- utils.call_ollama_with_json_retry によるリトライ・スキーマ検証
- utils.wrap_user_content / sanitize_user_input によるPrompt Injection対策
- refine_pr の指示文もサニタイズ対象に追加

[変更点 v3]
- generate_pr_variants が直接 ollama.chat を呼んでいた不一致を解消し、
  utils.call_ollama_with_json_array_retry に統一（リトライ・スキーマ検証が効くように）
- _strip_to_json（局所的なJSON抽出）を廃止し、utils._clean_json_raw で統一

[変更点 v4]
- refine_pr が直接 ollama.chat を呼び、リトライ・空応答チェックなしで返していた
  非対称性を解消。utils.call_ollama_with_text_retry に統一し、
  1回までの軽量リトライと空応答/極端な短文の検知を追加。
- refine_pr の戻り値を str から dict（pr_text/ok/error_msg）に変更し、
  失敗時にユーザーの元の自己PRを破壊せず、エラー内容も呼び出し元に伝えられるようにした。
"""

from __future__ import annotations

from utils import (
    HALLUCINATION_GUARD,
    REFINE_HALLUCINATION_GUARD,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_array_retry,
    call_ollama_with_json_retry,
    call_ollama_with_text_retry,
    sanitize_user_input,
    wrap_user_content,
)

VARIANT_LABELS = {
    "result": "結果重視型",
    "process": "プロセス重視型",
    "personality": "人柄重視型",
}

VARIANT_DESCRIPTIONS = {
    "result": "数字・成果・実績を前面に出し、インパクトを重視した自己PR",
    "process": "課題への向き合い方や工夫・粘り強さといったプロセスを重視した自己PR",
    "personality": "チームワークや価値観、人柄が伝わることを重視した自己PR",
}

EVAL_AXES = ["具体性", "熱意", "論理構成", "差別化"]


# ============================================================
# 1. 複数案生成
# ============================================================

def generate_pr_variants(model: str, conversation_history: str, rag_block: str) -> list[dict]:
    """3パターンの自己PRを1回の呼び出しでまとめて生成する。

    Returns: [{"type": "result", "label": "結果重視型", "content": "..."}, ...]
    """
    # 会話履歴はユーザー入力を含むためInjectionガードでラッピング
    interview_block = wrap_user_content(conversation_history)

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
以下の【面接官と学生のインタビュー記録】から、日本の新卒採用で高く評価される自己PRを
「異なる切り口」で3パターン作成してください。
{HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
{rag_block}
【3パターンの切り口】
1. type="result"（{VARIANT_DESCRIPTIONS['result']}）
2. type="process"（{VARIANT_DESCRIPTIONS['process']}）
3. type="personality"（{VARIANT_DESCRIPTIONS['personality']}）

【各パターン共通のルール】
・構成は「STAR構成（結論→背景・課題→行動→結果）＋入社後の活かし方」とすること。
・直訳調ではない、日本の面接官に刺さる自然で熱意のある敬体（です・ます調）にすること。
・文字数は400文字程度。
・3パターンは内容が似通いすぎないよう、切り口に応じてエピソードの見せ方を変えること。

【インタビュー記録】
{interview_block}

【出力ルール】
必ず以下のJSON配列の形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

[
  {{"type": "result", "content": "（結果重視型の自己PR本文）"}},
  {{"type": "process", "content": "（プロセス重視型の自己PR本文）"}},
  {{"type": "personality", "content": "（人柄重視型の自己PR本文）"}}
]
"""
    data, ok, error_msg = call_ollama_with_json_array_retry(
        model=model,
        prompt=prompt,
        item_required_keys=["type", "content"],
        fallback=[],
        max_retries=2,
    )

    if not ok or not data:
        # フォールバック: エラーメッセージを含む単一案
        fallback_content = error_msg or "生成に失敗しました。Ollamaの状態をご確認ください。"
        return [{"type": "result", "label": "自己PR（自動整形に失敗したため単一案で表示）", "content": fallback_content}]

    variants = []
    for item in data:
        v_type = str(item.get("type", "")).strip()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        label = VARIANT_LABELS.get(v_type, v_type or "自己PR案")
        variants.append({"type": v_type or "unknown", "label": label, "content": content})

    if not variants:
        return [{"type": "result", "label": "自己PR（自動整形に失敗したため単一案で表示）", "content": error_msg or ""}]

    return variants


# ============================================================
# 2. AIセルフ評価
# ============================================================

def evaluate_pr(model: str, pr_text: str) -> dict | None:
    """生成済みの自己PR本文を、採用担当者視点で評価する。

    Returns: {
        "scores": {"具体性": 4, ...},
        "summary": str,
        "improvements": [str, ...],
    }
    失敗時はNoneを返す。
    """
    # 自己PR本文もユーザー由来（生成AIを経由しているが元はユーザー入力）なのでラッピング
    safe_pr = wrap_user_content(pr_text)
    axes_json_hint = ", ".join(f'"{axis}": 1〜5の整数' for axis in EVAL_AXES)

    prompt = f"""あなたは日本企業で新卒採用を担当する、経験豊富な人事担当者です。
以下の自己PRを読み、採用担当者として率直に評価してください。
{USER_INPUT_BOUNDARY_NOTE}
【自己PR】
{safe_pr}

【評価軸】（各1〜5点）
・具体性: 数字や固有名詞、エピソードの解像度
・熱意: 意欲や前向きさが伝わるか
・論理構成: STAR構成が機能し、読みやすい流れになっているか
・差別化: ありきたりな表現に留まらず、その人らしさが出ているか

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

{{
  "scores": {{{axes_json_hint}}},
  "summary": "2〜3文程度の総評（敬体）",
  "improvements": ["改善提案1（具体的に）", "改善提案2（具体的に）"]
}}
"""
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["scores", "summary", "improvements"],
        fallback=None,
        max_retries=2,
    )
    if not result["ok"]:
        return None

    scores_raw = result.get("scores", {})
    scores = {}
    for axis in EVAL_AXES:
        try:
            val = int(scores_raw.get(axis, 0))
        except (TypeError, ValueError):
            val = 0
        scores[axis] = max(0, min(5, val))

    summary = str(result.get("summary", "")).strip()
    improvements = result.get("improvements", [])
    if not isinstance(improvements, list):
        improvements = []
    improvements = [str(i).strip() for i in improvements if str(i).strip()]

    return {"scores": scores, "summary": summary, "improvements": improvements}


# ============================================================
# 3. 企業別カスタマイズPR生成
# ============================================================

def generate_company_pr(
    model: str,
    base_pr: str,
    company_name: str,
    company_info: str,
    conversation_history: str,
) -> dict:
    """ベースとなる自己PRを、特定企業の情報に合わせてカスタマイズする。

    Args:
        model: Ollamaモデル名
        base_pr: カスタマイズ元の自己PR本文
        company_name: 企業名（表示用）
        company_info: 企業の特徴・求める人物像・事業内容などのテキスト
        conversation_history: インタビュー全履歴（ハルシネーション防止の参照用）

    Returns:
        {
            "company_name": str,
            "pr_text": str,       # カスタマイズ後の自己PR本文
            "points": [str, ...], # この企業向けに変えた主なポイント（1〜3点）
            "ok": bool,
            "error_msg": str | None,
        }
    """
    safe_base_pr = wrap_user_content(base_pr)
    safe_company_info = wrap_user_content(company_info)
    safe_history = wrap_user_content(conversation_history)
    safe_company_name = sanitize_user_input(company_name)

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
以下の【ベース自己PR】を、【企業情報】に合わせてカスタマイズしてください。
{HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
【企業名】
{safe_company_name}

【企業情報（事業内容・求める人物像・特徴など）】
{safe_company_info}

【ベース自己PR】
{safe_base_pr}

【カスタマイズのルール】
・企業の求める人物像・事業内容・バリューに合致するエピソードの側面を前面に出すこと。
・インタビュー記録にない新たな事実・数字・エピソードは創作しないこと（表現の強調はOK）。
・文字数は400文字程度を維持すること。
・敬体（です・ます調）を維持すること。
・変更したポイントを "points" に1〜3点で簡潔にまとめること。

【参考：元のインタビュー記録】
{safe_history}

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

{{
  "pr_text": "カスタマイズ後の自己PR本文（400文字程度、敬体）",
  "points": ["変更ポイント1", "変更ポイント2"]
}}
"""
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["pr_text", "points"],
        fallback={"pr_text": base_pr, "points": []},
        max_retries=2,
    )

    points = result.get("points", [])
    if not isinstance(points, list):
        points = []
    points = [str(p).strip() for p in points if str(p).strip()]

    return {
        "company_name": company_name,
        "pr_text": str(result.get("pr_text", base_pr)).strip() or base_pr,
        "points": points,
        "ok": result.get("ok", False),
        "error_msg": result.get("error_msg"),
    }


# ============================================================
# 4. 微調整リライト
# ============================================================

REFINE_PRESETS = {
    "concise": "全体的にもっと簡潔にしてください。冗長な表現を削り、要点を絞ってください。",
    "passionate": "もっと熱意や意欲が伝わる表現にしてください。ただし誇張しすぎず、誠実さは保ってください。",
    "formal": "より丁寧でフォーマルな印象にしてください。砕けた表現があれば改めてください。",
    "specific": "数字や固有名詞をできるだけ活かし、エピソードの具体性をさらに高めてください（インタビュー記録にない情報は創作しないでください）。",
}


def refine_pr(model: str, pr_text: str, instruction: str, conversation_history: str) -> dict:
    """既存の自己PR本文を、指示に沿ってリライトする（ゼロから再生成しない）。

    出力はJSON形式ではなく自由テキストのため、JSONパース・スキーマ検証は行わないが、
    他の生成関数との非対称性（リトライなし・空応答チェックなし）を解消するため、
    utils.call_ollama_with_text_retry を使い、最低限の堅牢性（1回までの軽量リトライ・
    空応答/極端な短文のリトライ対象化）を確保する。

    Returns:
        {
          "pr_text": str,        # リライト後の本文。失敗時は元のpr_text（変更なし）
          "ok": bool,
          "error_msg": str | None,
        }
    """
    # 指示文・PR本文・会話履歴をそれぞれサニタイズ
    safe_instruction = sanitize_user_input(instruction)
    safe_pr = wrap_user_content(pr_text)
    safe_history = wrap_user_content(conversation_history)

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
以下の【現在の自己PR】を、【リライト指示】に沿って書き直してください。
{REFINE_HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
【リライト指示】
{safe_instruction}

【現在の自己PR】
{safe_pr}

【厳守事項】
・元のエピソードや事実関係は変えないこと。
・以下の【参考：元のインタビュー記録】にない事実は創作しないこと。
・文字数は400文字程度を維持すること。
・敬体（です・ます調）を維持すること。
・本文のみを出力し、前置きや説明は一切付けないこと。

【参考：元のインタビュー記録】
{safe_history}
"""
    # 失敗時はリライト前の本文をそのまま返す（本文を空にしてユーザーの作業を失わせない）
    result = call_ollama_with_text_retry(
        model=model,
        prompt=prompt,
        fallback=pr_text,
        min_length=10,
        max_retries=1,
    )
    return {
        "pr_text": result["text"],
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }
