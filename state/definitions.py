"""
session_state の初期値を一元管理するモジュール。

各キーに対応するデフォルト値を辞書で定義します。
型ヒントが必要なものは TYPE_HINTS に記載します。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# デフォルト値の定義
# ---------------------------------------------------------------------------
# 値に None を使う場合、TYPE_HINTS で実際の型を補足してください。

STATE_DEFAULTS: dict[str, object] = {
    # ── アプリ全体 ──────────────────────────────────────────────────
    "app_mode": "interview",

    # ── インタビュー用 ───────────────────────────────────────────────
    "messages": [],
    "current_theme_index": 0,
    "questions_asked_in_theme": 0,
    "theme_messages": [],
    "selected_category": None,
    "awaiting_category_choice": False,
    "pending_prev_exchange": None,
    "interview_complete": False,
    "interview_started": False,
    "final_pr": None,
    "is_generating": False,
    "pr_generation_error": None,
    "pr_variants": None,
    "selected_variant_index": None,
    "pr_evaluation": None,
    "pr_evaluation_error": False,
    "is_evaluating": False,
    "is_refining": False,
    "pending_refine_instruction": None,
    "pr_refine_error": None,
    "rag_documents": [],        # list[Document]
    "rag_restore_error": None,
    "current_session_id": None,
    "current_company_name": "",
    "profile_done": False,
    "profile_text": "",
    "interview_summary": None,
    "is_generating_summary": False,
    "summary_error": None,

    # ── 想定質問用 ──────────────────────────────────────────────────
    "predicted_questions": None,
    "is_predicting_questions": False,
    "predict_questions_error": None,

    # ── 企業別カスタマイズPR用 ───────────────────────────────────────
    "company_prs": {},
    "company_pr_inputs": [{"name": "", "info": ""}],
    "is_generating_company_prs": False,
    "company_pr_error": None,

    # ── 性格診断用 ──────────────────────────────────────────────────
    "pa_answers": {},           # dict[int, int]
    "pa_current_q": 0,
    "pa_result": None,
    "pa_axis_scores": None,
    "pa_error": None,
    "pa_is_generating": False,

    # ── AI模擬面接用 ────────────────────────────────────────────────
    "mock_messages": [],
    "mock_theme_index": 0,
    "mock_theme_messages": [],
    "mock_followups_asked": 0,
    "mock_started": False,
    "mock_complete": False,
    "mock_used_predicted_indices": set(),   # set[int]
    "mock_evaluation": None,
    "mock_evaluation_error": None,
    "mock_is_generating": False,
    "mock_persona_key": "standard",
    "mock_answer_reviews": {},              # dict[int, dict]
    "mock_review_generating_for": None,    # int | None
    "mock_persona_confirmed": False,
    # 業界別モード
    "mock_industry_key": "general",        # str: 選択中の業界キー
    # STAR法評価（各回答のstar_reviewを管理）
    "mock_star_reviews": {},               # dict[int, dict]: user_turn_index -> star_review
    "mock_star_generating_for": None,      # int | None

    # ── 想定質問生成（独立ページ）用 ─────────────────────────────────
    "pq_selected_company_kb_id": None,
    "pq_questions": None,
    "pq_is_generating": False,
    "pq_error": None,

    # ── AIキャリアアドバイザー用 ─────────────────────────────────────
    "ca_messages": [],          # list[dict]
    "ca_is_thinking": False,

    # ── 企業比較マトリクス用 ─────────────────────────────────────────
    "cm_selected_kb_ids": [],   # list[int]
    "cm_additional_axes": [],   # list[str]
    "cm_motivations": None,
    "cm_matrix_result": None,
    "cm_why_not_others": {},    # dict[int, dict]
    "cm_is_generating": False,
    "cm_error": None,
}
