"""
page_modules/mock_interview/evaluation_section.py
面接終了後の総合評価生成・表示セクション
"""

import streamlit as st

import mock_interview_engine as mie

from .helpers import build_rag_block, full_history_for_rag


def render_result(model_name: str) -> None:
    """総合評価フェーズ全体を制御する。生成→表示の状態遷移を管理する。"""
    if st.session_state.mock_is_generating:
        _generate_evaluation(model_name)

    elif st.session_state.mock_evaluation is None:
        _handle_missing_evaluation()

    else:
        _show_evaluation()


# ── 内部関数 ─────────────────────────────────────────────────────

def _generate_evaluation(model_name: str) -> None:
    """評価をAIで生成してセッションに保存する。"""
    with st.spinner("面接内容を評価しています..."):
        history = full_history_for_rag()
        rag_block = build_rag_block(history)
        evaluation = mie.generate_mock_interview_evaluation(
            model=model_name,
            full_history=history,
            profile_text=st.session_state.profile_text,
            rag_block=rag_block,
            industry_key=st.session_state.get("mock_industry_key", "general"),
        )

    st.session_state.mock_is_generating = False
    if evaluation["ok"]:
        st.session_state.mock_evaluation = evaluation
        st.session_state.mock_evaluation_error = None
    else:
        st.session_state.mock_evaluation_error = evaluation.get("error_msg")
    st.rerun()


def _handle_missing_evaluation() -> None:
    """評価が未生成または失敗した場合の分岐処理。"""
    if st.session_state.mock_evaluation_error:
        st.error(
            f"評価の生成に失敗しました: {st.session_state.mock_evaluation_error}\n"
            "Ollamaの状態をご確認ください。"
        )
        if st.button("🔄 評価を再生成する", type="primary"):
            st.session_state.mock_is_generating = True
            st.rerun()
    else:
        st.session_state.mock_is_generating = True
        st.rerun()


def _show_evaluation() -> None:
    """生成済みの評価結果を画面に表示し、やり直しボタンを提供する。"""
    ev = st.session_state.mock_evaluation

    from industry_engine import get_industry
    industry = get_industry(st.session_state.get("mock_industry_key", "general"))

    st.subheader("📋 模擬面接 結果")
    st.caption(f"{industry['icon']} 業界モード: **{industry['name']}**")

    st.markdown("#### 総合評価")
    st.info(ev["overall_summary"] or "（評価コメントを生成できませんでした）")

    # 業界別評価軸（評価結果に含まれる eval_axes を優先、なければ業界定義から取得）
    active_axes = ev.get("eval_axes") or industry["eval_axes"]

    if ev["scores"] and active_axes:
        st.markdown("#### 項目別スコア")
        cols = st.columns(len(active_axes))
        for col, axis in zip(cols, active_axes):
            with col:
                score = ev["scores"].get(axis, 0)
                delta = "★" * score + "☆" * (5 - score)
                st.metric(axis, f"{score}/5", delta=delta, delta_color="off")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 💪 強みTOP3")
        for i, item in enumerate(ev["top_strengths"], start=1):
            st.markdown(f"{i}. {item}")
    with col_b:
        st.markdown("#### 📈 改善点TOP3")
        for i, item in enumerate(ev["top_improvements"], start=1):
            st.markdown(f"{i}. {item}")

    if ev["model_answers"]:
        st.markdown("#### 📝 模範回答例")
        for item in ev["model_answers"]:
            with st.container(border=True):
                st.markdown(f"**Q. {item['question']}**")
                st.write(item["model_answer"])

    if ev["next_practice_points"]:
        st.markdown("#### 🎯 次回の練習ポイント")
        for item in ev["next_practice_points"]:
            st.markdown(f"・{item}")

    st.write("---")

    # 会話ログのダウンロード
    mock_messages = st.session_state.get("mock_messages", [])
    if mock_messages:
        log_lines = ["# 模擬面接 会話ログ", ""]
        for msg in mock_messages:
            role_label = "面接官" if msg["role"] == "assistant" else "あなた"
            log_lines.append(f"【{role_label}】")
            log_lines.append(msg["content"])
            log_lines.append("")
        log_text = "\n".join(log_lines)
        st.download_button(
            label="💾 会話ログをダウンロード（.txt）",
            data=log_text.encode("utf-8"),
            file_name="mock_interview_log.txt",
            mime="text/plain",
            use_container_width=True,
        )

    if st.button("🔄 もう一度模擬面接をやり直す", use_container_width=True):
        _reset_session()
        st.rerun()


def _reset_session() -> None:
    """模擬面接に関わるセッション状態をすべてリセットする。"""
    st.session_state.mock_messages = []
    st.session_state.mock_theme_index = 0
    st.session_state.mock_theme_messages = []
    st.session_state.mock_followups_asked = 0
    st.session_state.mock_started = False
    st.session_state.mock_complete = False
    st.session_state.mock_used_predicted_indices = set()
    st.session_state.mock_evaluation = None
    st.session_state.mock_evaluation_error = None
    st.session_state.mock_star_reviews = {}
    st.session_state.mock_star_generating_for = None
