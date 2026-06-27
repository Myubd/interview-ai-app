"""
page_modules/mock_interview/interview_chat.py
会話履歴表示・回答振り返り（レビュー）・STAR法評価・チャット入力UI
"""

import streamlit as st

import mock_interview_engine as mie
from persona_engine import get_persona, build_persona_prompt_block, judge_and_generate_followup as persona_judge_followup
from answer_assist import generate_answer_review, generate_star_review
from utils import sanitize_user_input

from .helpers import build_rag_block, full_history_for_rag
from .interview_flow import advance_to_next_theme


def _industry_key() -> str:
    return st.session_state.get("mock_industry_key", "general")


def render_chat_history(model_name: str) -> None:
    """会話履歴をメッセージごとに描画し、ユーザー発言には振り返りUIを付与する。"""
    user_turn_index = 0

    for msg_i, msg in enumerate(st.session_state.mock_messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

        if msg["role"] == "user":
            _render_answer_review(msg_i, msg["content"], user_turn_index, model_name)
            user_turn_index += 1


def _render_answer_review(msg_i: int, answer: str, review_key: int, model_name: str) -> None:
    """ユーザー回答1件分の振り返りウィジェットを描画する。"""
    # ── 通常レビュー ─────────────────────────────────────────────
    if review_key in st.session_state.mock_answer_reviews:
        _show_review_expander(review_key)
    elif st.session_state.mock_review_generating_for != review_key:
        prev_q = _find_previous_question(msg_i)
        if st.button(
            "📊 この回答を振り返る",
            key=f"mock_review_btn_{review_key}",
            help="質問意図・改善点・アピールポイントを表示します",
        ):
            st.session_state.mock_review_generating_for = review_key
            st.session_state._mock_pending_review = {
                "key": review_key,
                "question": prev_q,
                "answer": answer,
            }
            st.rerun()
    else:  # 生成中
        with st.spinner("振り返りを生成中..."):
            pending = st.session_state.get("_mock_pending_review", {})
            persona_b = build_persona_prompt_block(st.session_state.mock_persona_key)
            persona_n = get_persona(st.session_state.mock_persona_key)["name"]
            history_text = mie.build_full_history_text(st.session_state.mock_messages)
            review = generate_answer_review(
                model=model_name,
                question=pending.get("question", ""),
                student_answer=pending.get("answer", ""),
                persona_block=persona_b,
                persona_name=persona_n,
                pr_text=st.session_state.get("final_pr", "") or "",
                conversation_history=history_text,
            )
        st.session_state.mock_answer_reviews[review_key] = review
        st.session_state.mock_review_generating_for = None
        st.session_state._mock_pending_review = None
        st.rerun()

    # ── STAR法評価 ───────────────────────────────────────────────
    _render_star_review(msg_i, answer, review_key, model_name)


def _render_star_review(msg_i: int, answer: str, review_key: int, model_name: str) -> None:
    """STAR法評価ウィジェットを描画する。"""
    if review_key in st.session_state.mock_star_reviews:
        _show_star_expander(review_key)

    elif st.session_state.mock_star_generating_for != review_key:
        prev_q = _find_previous_question(msg_i)
        if st.button(
            "⭐ STAR法で分析する",
            key=f"mock_star_btn_{review_key}",
            help="Situation / Task / Action / Result の充足度を分析します",
        ):
            st.session_state.mock_star_generating_for = review_key
            st.session_state._mock_pending_star = {
                "key": review_key,
                "question": prev_q,
                "answer": answer,
            }
            st.rerun()

    else:  # STAR評価生成中
        with st.spinner("STAR法分析中..."):
            pending = st.session_state.get("_mock_pending_star", {})
            star = generate_star_review(
                model=model_name,
                question=pending.get("question", ""),
                student_answer=pending.get("answer", ""),
            )
        st.session_state.mock_star_reviews[review_key] = star
        st.session_state.mock_star_generating_for = None
        st.session_state._mock_pending_star = None
        st.rerun()


def _show_star_expander(review_key: int) -> None:
    """生成済みのSTAR評価をエクスパンダーで表示する。"""
    star = st.session_state.mock_star_reviews[review_key]

    STAR_ELEMENTS = [
        ("situation", "S：状況（Situation）", "どのような状況・背景だったか"),
        ("task",      "T：課題・役割（Task）", "担った課題や役割は何か"),
        ("action",    "A：行動（Action）",     "課題に対して具体的にどう行動したか"),
        ("result",    "R：結果（Result）",     "行動の結果、何が達成されたか"),
    ]
    SCORE_COLORS = {0: "🔴", 1: "🟠", 2: "🟡", 3: "🟢"}
    SCORE_LABELS = {0: "未言及", 1: "薄い", 2: "まあまあ", 3: "十分"}

    with st.expander("⭐ STAR法分析", expanded=False):
        total = star.get("star_total", 0)
        total_pct = int(total / 12 * 100)

        # 総合スコアバー
        st.markdown(f"**総合スコア: {total}/12 pts（{total_pct}%）**")
        st.progress(total / 12)

        # 各要素
        cols = st.columns(4)
        for col, (key, label, _) in zip(cols, STAR_ELEMENTS):
            elem = star.get(key, {})
            score = elem.get("score", 0)
            with col:
                st.markdown(
                    f"**{label.split('（')[0]}**\n\n"
                    f"{SCORE_COLORS.get(score, '⚪')} {score}/3\n\n"
                    f"*{SCORE_LABELS.get(score, '')}*"
                )

        # 各要素のコメント
        st.markdown("---")
        for key, label, description in STAR_ELEMENTS:
            elem = star.get(key, {})
            score = elem.get("score", 0)
            comment = elem.get("comment", "")
            color = SCORE_COLORS.get(score, "⚪")
            if comment:
                st.markdown(f"{color} **{label}**")
                st.caption(f"　*{description}*")
                st.info(comment)

        # まとめ・アドバイス
        if star.get("star_summary"):
            st.markdown("**📝 総評**")
            st.write(star["star_summary"])

        if star.get("star_tip"):
            st.markdown("**💡 最優先改善ポイント**")
            st.warning(star["star_tip"])


def _show_review_expander(review_key: int) -> None:
    """生成済みの振り返りデータをエクスパンダーで表示する。"""
    rev = st.session_state.mock_answer_reviews[review_key]
    with st.expander("📊 この回答の振り返り", expanded=False):
        persona = get_persona(st.session_state.mock_persona_key)
        st.caption(f"面接官タイプ: {persona['icon']} {persona['name']}")

        if rev.get("intent"):
            st.markdown("**🔍 質問意図 ／ 面接官が見ているポイント**")
            st.info(rev["intent"])

        col_good, col_imp = st.columns(2)
        with col_good:
            if rev.get("good_points"):
                st.markdown("**✅ 良かった点**")
                for pt in rev["good_points"]:
                    st.success(f"・{pt}")
        with col_imp:
            if rev.get("improvements"):
                st.markdown("**📈 改善提案**")
                for pt in rev["improvements"]:
                    st.warning(f"・{pt}")

        if rev.get("appeal_points"):
            st.markdown("**💡 アピールできた／すべき要素**")
            for pt in rev["appeal_points"]:
                st.markdown(f"・{pt}")

        if rev.get("revised_example"):
            st.markdown("**✍️ より良い回答の例**")
            st.write(rev["revised_example"])


def _find_previous_question(msg_i: int) -> str:
    """指定インデックスより前の直近の assistant メッセージを返す。"""
    for back_i in range(msg_i - 1, -1, -1):
        if st.session_state.mock_messages[back_i]["role"] == "assistant":
            return st.session_state.mock_messages[back_i]["content"]
    return ""


def render_chat_input(model_name: str) -> None:
    """チャット入力欄と「面接を終える」ボタンを描画し、回答を処理する。"""
    industry = _industry_key()
    st.write("")
    if st.button("🛑 面接を終える", use_container_width=True):
        st.session_state.mock_complete = True
        st.rerun()

    if user_input := st.chat_input("ここに回答を入力してください..."):
        sanitized_input = sanitize_user_input(user_input)
        if len(sanitized_input.strip()) < 2:
            st.toast("もう少し詳しく教えてください🙏", icon="⚠️")
        else:
            _process_user_answer(model_name, sanitized_input)
            st.rerun()

    if st.session_state.mock_messages and mie.is_interview_finished(
        st.session_state.mock_theme_index, industry_key=industry
    ):
        st.write("")
        if st.button("✨ 結果を見る", type="primary", use_container_width=True):
            st.session_state.mock_complete = True
            st.rerun()


def _process_user_answer(model_name: str, sanitized_input: str) -> None:
    """ユーザー回答をセッションに追記し、フォローアップ判定を行う。"""
    industry = _industry_key()
    st.session_state.mock_messages.append({"role": "user", "content": sanitized_input})
    st.session_state.mock_theme_messages.append({"role": "user", "content": sanitized_input})

    theme = mie.get_theme(st.session_state.mock_theme_index, industry_key=industry)
    rag_block = build_rag_block(full_history_for_rag())

    with st.spinner("回答を確認中..."):
        result = persona_judge_followup(
            model=model_name,
            persona_key=st.session_state.mock_persona_key,
            theme=theme,
            theme_messages=st.session_state.mock_theme_messages,
            followups_asked_in_theme=st.session_state.mock_followups_asked,
            profile_text=st.session_state.profile_text,
            rag_block=rag_block,
            industry_key=industry,
        )

    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、このテーマを終了して次へ進みます。", icon="⚠️")

    if result["continue"] and result["question"]:
        st.session_state.mock_messages.append({"role": "assistant", "content": result["question"]})
        st.session_state.mock_theme_messages.append({"role": "assistant", "content": result["question"]})
        st.session_state.mock_followups_asked += 1
    else:
        advance_to_next_theme(model_name)
