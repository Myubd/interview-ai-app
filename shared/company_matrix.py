"""
company_matrix.py
------------------
複数企業の「志望動機・競合比較」マトリクス自動生成機能。

[shared/ 一本化 (2026-07)]
utils にのみ依存し、db・rag のようなアプリ固有の兄弟モジュールに
依存しないため、streamlit/ react-fastapi/backend/ の物理コピーを
廃止し shared/ に一本化した。詳細は shared/MIGRATION_GUIDE.md を参照。

設計方針:
- 学生が登録した複数の志望企業（最大8社）について、以下を一括生成・比較する:
    1. 志望動機カスタム文（各社300字程度）
    2. 企業比較マトリクス（複数軸でのスコア・テキスト評価）
    3. 「なぜ他社ではなくこの企業か」差別化ポイント（逆張り志望動機）
    4. 各企業固有のリスク・注意点（「この企業ではこう聞かれやすい質問」も含む）
- 比較軸は固定7軸 + ユーザー指定の追加軸（最大3軸）をサポート。
- 自己PR・インタビュー履歴・RAGで取得した企業情報を統合して生成する。
- 生成結果はCSVでエクスポートできるよう、フラットなデータ構造でも返す。

公開API:
  generate_company_motivation()      → 単一企業の志望動機文生成
  generate_motivation_for_all()      → 登録企業全社の志望動機を一括生成
  generate_comparison_matrix()       → 複数企業の比較マトリクス生成
  generate_why_not_others()          → 「なぜ他社でなくここか」差別化ポイント生成
  export_matrix_to_csv_rows()        → CSVエクスポート用のフラットデータ変換
"""

from __future__ import annotations

import csv
import io

from utils import (
    HALLUCINATION_GUARD,
    USER_INPUT_BOUNDARY_NOTE,
    call_ollama_with_json_array_retry,
    call_ollama_with_json_retry,
    sanitize_user_input,
    wrap_user_content,
)

# ============================================================
# 定数
# ============================================================

MAX_COMPANIES = 8  # 登録できる最大企業数

# 比較マトリクスの固定軸
MATRIX_AXES_FIXED: list[str] = [
    "事業の安定性・将来性",
    "働き方・ワークライフバランス",
    "成長機会・キャリアパス",
    "社風・カルチャーフィット",
    "給与・待遇",
    "社会的意義・インパクト",
    "自分の強みとの一致度（参考）",  # ※学生の価値観との相性はあくまで参考スコアです
]

# 価値観軸であることを明示するキー（UIで注釈を出すために参照）
VALUE_FIT_AXIS_KEY = "自分の強みとの一致度（参考）"
VALUE_FIT_NOTE = "※「自分の強みとの一致度」はインタビュー情報をもとにしたAIの参考スコアです。実際の相性は個人の判断で確認してください。"

# スコア表示用ラベル
SCORE_LABELS = {1: "低", 2: "やや低", 3: "中", 4: "やや高", 5: "高"}


# ============================================================
# 内部ヘルパー
# ============================================================

def _build_student_block(pr_text: str, conversation_history: str) -> str:
    """学生の情報ブロックを整形する。"""
    parts = []
    if pr_text.strip():
        parts.append(f"【学生の自己PR】\n{wrap_user_content(pr_text)}")
    if conversation_history.strip():
        parts.append(f"【インタビュー履歴（要約）】\n{wrap_user_content(conversation_history, max_length=3000)}")
    return "\n\n".join(parts) if parts else "（学生情報なし）"


def _sanitize_company(company: dict) -> dict:
    """企業情報辞書をサニタイズする。"""
    return {
        "name": sanitize_user_input(company.get("name", "企業名不明")),
        "info": sanitize_user_input(company.get("info", ""), max_length=2000),
        "industry": sanitize_user_input(company.get("industry", "")),
    }


def _industry_prompt_line(industry: str) -> str:
    """プロンプト埋め込み用の「業界: 」行を生成する。

    業界が未入力（空文字）の場合は行ごと省略する。
    呼び出し側では f"{_industry_prompt_line(...)}次の項目" のように、
    改行込みでそのまま埋め込める形にしている。
    """
    return f"業界: {industry}\n" if industry else ""


def _format_company_line(company: dict, info_max_length: int) -> str:
    """企業1社分の概要行を「・企業名（業界）: 企業情報」の形式で整形する。

    業界・企業情報が未入力の場合は、その部分（括弧やコロン以降）を省略し、
    空括弧（「・〇〇社（）」）のような不自然な表記が出ないようにする。
    """
    industry_part = f"（{company['industry']}）" if company["industry"] else ""
    if company["info"]:
        return f"・{company['name']}{industry_part}: {company['info'][:info_max_length]}"
    return f"・{company['name']}{industry_part}"


# ============================================================
# 公開API
# ============================================================

def generate_company_motivation(
    model: str,
    company: dict,
    pr_text: str = "",
    conversation_history: str = "",
    word_count: int = 300,
) -> dict:
    """単一企業の志望動機文を生成する。

    Args:
        model: Ollamaモデル名
        company: {"name": str, "info": str, "industry": str}
        pr_text: 自己PR本文（任意）
        conversation_history: インタビュー履歴（任意）
        word_count: 目標文字数（デフォルト300字）

    Returns:
        {
          "company_name": str,
          "motivation_text": str,     # 志望動機文
          "key_points": [str, ...],   # アピールポイント（2〜3点）
          "ok": bool,
          "error_msg": str | None,
        }
    """
    safe_company = _sanitize_company(company)
    student_block = _build_student_block(pr_text, conversation_history)

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
以下の学生情報と企業情報をもとに、説得力のある志望動機文を生成してください。
{HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
【志望企業】
企業名: {safe_company['name']}
{_industry_prompt_line(safe_company['industry'])}企業情報: {safe_company['info']}

{student_block}

【志望動機文の作成ルール】
・構成: 「なぜこの業界か → なぜこの企業か → 入社後に何をしたいか」の3段構成
・文字数: {word_count}字程度、敬体（です・ます調）
・学生の自己PR・履歴にある具体的なエピソードを1〜2個盛り込むこと
・企業の特徴・強みに具体的に触れること（抽象的な「御社に魅力を感じています」ではなく）
・インタビュー記録にない事実は創作しないこと
・key_points: この志望動機でアピールできているポイントを2〜3点、箇条書きで

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。
{{
  "motivation_text": "志望動機文（{word_count}字程度、敬体）",
  "key_points": ["アピールポイント1", "アピールポイント2"]
}}
"""
    fallback = {"motivation_text": "", "key_points": []}
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["motivation_text", "key_points"],
        fallback=fallback,
        max_retries=2,
    )
    points = result.get("key_points", [])
    if not isinstance(points, list):
        points = []

    return {
        "company_name": safe_company["name"],
        "motivation_text": str(result.get("motivation_text", "")).strip(),
        "key_points": [str(p).strip() for p in points if str(p).strip()],
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


def generate_motivation_for_all(
    model: str,
    companies: list[dict],
    pr_text: str = "",
    conversation_history: str = "",
) -> list[dict]:
    """登録企業全社の志望動機を順次生成する。

    各社を個別に呼び出す（一括プロンプトはトークン数が爆発するため）。

    Returns:
        list of generate_company_motivation() の戻り値
    """
    if not companies:
        return []
    companies = companies[:MAX_COMPANIES]
    results = []
    for company in companies:
        result = generate_company_motivation(
            model=model,
            company=company,
            pr_text=pr_text,
            conversation_history=conversation_history,
        )
        results.append(result)
    return results


def generate_comparison_matrix(
    model: str,
    companies: list[dict],
    pr_text: str = "",
    additional_axes: list[str] | None = None,
) -> dict:
    """複数企業の比較マトリクスを生成する。

    各軸について各企業を1〜5点でスコアリング + 短い根拠コメントを返す。

    Args:
        model: Ollamaモデル名
        companies: [{"name": str, "info": str, "industry": str}, ...]
        pr_text: 自己PR本文（任意）
        additional_axes: ユーザーが追加する比較軸（最大3軸）

    Returns:
        {
          "axes": [str, ...],               # 比較軸リスト
          "companies": [str, ...],          # 企業名リスト
          "matrix": {                       # matrix[axis][company_name] = {"score": int, "comment": str}
              "事業の安定性": {
                  "A社": {"score": 4, "comment": "..."},
                  ...
              },
              ...
          },
          "overall_recommendation": str,   # 総合的な推薦コメント
          "ok": bool,
          "error_msg": str | None,
        }
    """
    companies = companies[:MAX_COMPANIES]
    safe_companies = [_sanitize_company(c) for c in companies]
    company_names = [c["name"] for c in safe_companies]

    axes = MATRIX_AXES_FIXED.copy()
    if additional_axes:
        for ax in additional_axes[:3]:
            safe_ax = sanitize_user_input(ax)
            if safe_ax and safe_ax not in axes:
                axes.append(safe_ax)

    # 企業情報ブロックを構築（業界が未入力の場合は空括弧を出さない）
    company_blocks = [_format_company_line(c, info_max_length=300) for c in safe_companies]
    companies_info = "\n".join(company_blocks)

    axes_list = "\n".join(f"  - {ax}" for ax in axes)
    company_list = ", ".join(f'"{n}"' for n in company_names)
    profile_hint = wrap_user_content(pr_text) if pr_text.strip() else "（自己PR未生成）"

    # JSON出力のスキーマ例を構築
    example_axis = axes[0]
    example_company = company_names[0] if company_names else "A社"
    schema_example = (
        f'{{"score": 4, "comment": "根拠（1文）"}}'
    )

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
以下の複数企業を、指定した比較軸でスコアリングした「比較マトリクス」を生成してください。
{HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
【学生の自己PR（参考）】
{profile_hint}

【比較対象の企業情報】
{companies_info}

【比較軸（全{len(axes)}軸）】
{axes_list}

【スコアリングのルール】
・各軸・各企業を1〜5点で評価し、判断根拠を1文で添えてください。
・学生の自己PR・価値観との相性も考慮してスコアを付けてください。
・企業情報が不足している場合はスコア2〜3に留め、commentに「情報不足」と明記してください。
・overall_recommendation には、この学生にとって最もフィットしそうな企業と、その理由を2〜3文で書いてください。

【出力ルール】
必ず以下のJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号は一切不要です。

{{
  "matrix": {{
    "{example_axis}": {{
      "{example_company}": {schema_example}
    }}
  }},
  "overall_recommendation": "総合推薦コメント（2〜3文）"
}}

matrix には全{len(axes)}軸 × 全{len(company_names)}社分のデータを含めてください。
"""
    fallback_matrix: dict = {}
    for ax in axes:
        fallback_matrix[ax] = {name: {"score": 3, "comment": "生成に失敗しました"} for name in company_names}

    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["matrix", "overall_recommendation"],
        fallback={"matrix": fallback_matrix, "overall_recommendation": ""},
        max_retries=2,
    )

    # matrix の正規化
    raw_matrix = result.get("matrix", {})
    normalized_matrix: dict = {}
    for ax in axes:
        normalized_matrix[ax] = {}
        ax_data = raw_matrix.get(ax, {}) if isinstance(raw_matrix, dict) else {}
        for name in company_names:
            entry = ax_data.get(name, {}) if isinstance(ax_data, dict) else {}
            try:
                score = max(1, min(5, int(entry.get("score", 3))))
            except (TypeError, ValueError):
                score = 3
            normalized_matrix[ax][name] = {
                "score": score,
                "comment": str(entry.get("comment", "")).strip() or "評価データなし",
            }

    return {
        "axes": axes,
        "companies": company_names,
        "matrix": normalized_matrix,
        "overall_recommendation": str(result.get("overall_recommendation", "")).strip(),
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


def generate_why_not_others(
    model: str,
    target_company: dict,
    other_companies: list[dict],
    pr_text: str = "",
    conversation_history: str = "",
) -> dict:
    """「なぜ他社ではなくこの企業か」差別化ポイントを生成する。

    Args:
        target_company: メインの志望企業
        other_companies: 比較対象の他社リスト（同業他社等）

    Returns:
        {
          "target_name": str,
          "differentiators": [       # 差別化ポイント（2〜4点）
            {"point": str, "vs_others": str}  # vs_others: 他社と何が違うか
          ],
          "answer_template": str,    # 「なぜ他社でなく御社か」に答えるテンプレート文（200字程度）
          "ok": bool,
          "error_msg": str | None,
        }
    """
    safe_target = _sanitize_company(target_company)
    safe_others = [_sanitize_company(c) for c in other_companies[:5]]
    student_block = _build_student_block(pr_text, conversation_history)

    others_block = "\n".join(
        _format_company_line(c, info_max_length=200) for c in safe_others
    ) or "（他社情報なし）"

    prompt = f"""あなたはプロの就職活動キャリアアドバイザーです。
学生が面接で必ず聞かれる「なぜ他社ではなくうちの会社なのか」という質問への
差別化ポイントと回答テンプレートを生成してください。
{HALLUCINATION_GUARD}
{USER_INPUT_BOUNDARY_NOTE}
【第一志望企業】
企業名: {safe_target['name']}
{_industry_prompt_line(safe_target['industry'])}企業情報: {safe_target['info'][:500] if safe_target['info'] else '（情報なし）'}

【比較される可能性のある他社】
{others_block}

{student_block}

【生成のルール】
・differentiators: 第一志望企業だけが持つ独自の魅力・差別化点を2〜4つ挙げてください。
  各pointには「他社と何が違うか」をvs_othersとして1文で添えてください。
  学生の価値観・強みと結びついた説明にしてください。
・answer_template: 「なぜ他社でなく御社を志望しているのですか？」への回答テンプレート（200字程度、敬体）
  学生の自己PR・経験を踏まえた具体的な内容にしてください。

【出力ルール】
必ず以下のJSON形式のみで出力してください。
{{
  "differentiators": [
    {{"point": "差別化ポイント（タイトル）", "vs_others": "他社との違い（1文）"}}
  ],
  "answer_template": "「なぜ他社でなく御社か」への回答テンプレート文（200字程度、敬体）"
}}
"""
    fallback = {"differentiators": [], "answer_template": ""}
    result = call_ollama_with_json_retry(
        model=model,
        prompt=prompt,
        required_keys=["differentiators", "answer_template"],
        fallback=fallback,
        max_retries=2,
    )
    diff_raw = result.get("differentiators", [])
    if not isinstance(diff_raw, list):
        diff_raw = []
    differentiators = []
    for item in diff_raw:
        if not isinstance(item, dict):
            continue
        point = str(item.get("point", "")).strip()
        vs = str(item.get("vs_others", "")).strip()
        if point:
            differentiators.append({"point": point, "vs_others": vs})

    return {
        "target_name": safe_target["name"],
        "differentiators": differentiators,
        "answer_template": str(result.get("answer_template", "")).strip(),
        "ok": result["ok"],
        "error_msg": result.get("error_msg"),
    }


def export_matrix_to_csv_rows(matrix_result: dict) -> str:
    """generate_comparison_matrix() の結果をCSV文字列に変換する。

    出力形式:
        比較軸, 企業名, スコア, コメント

    Returns:
        CSVテキスト（UTF-8、BOM付きでExcelでも開ける）
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["比較軸", "企業名", "スコア（1〜5）", "コメント"])

    axes = matrix_result.get("axes", [])
    matrix = matrix_result.get("matrix", {})
    companies = matrix_result.get("companies", [])

    for ax in axes:
        ax_data = matrix.get(ax, {})
        for company in companies:
            entry = ax_data.get(company, {})
            score = entry.get("score", "")
            comment = entry.get("comment", "")
            writer.writerow([ax, company, score, comment])

    recommendation = matrix_result.get("overall_recommendation", "")
    if recommendation:
        writer.writerow([])
        writer.writerow(["総合推薦コメント", recommendation])

    # BOM付きUTF-8でExcel対応
    csv_text = "\ufeff" + output.getvalue()
    return csv_text


def get_company_template() -> dict:
    """企業情報入力用のテンプレート辞書を返す（app.py でのフォーム初期値として使用）。"""
    return {
        "name": "",
        "industry": "",
        "info": "",  # 事業内容・求める人物像・特徴など（自由入力 or RAGで取得）
    }
