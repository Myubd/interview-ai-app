"""
pages/personality_page.py
性格診断・適性検査ページ（ビッグファイブ30問）
"""

import streamlit as st

from favorites import add_favorite, remove_favorite_by_item, is_favorited
from personality_assessment import (
    AXES, QUESTIONS, SCALE_LABELS, TOTAL_QUESTIONS,
    compute_axis_scores, generate_personality_result,
)
from utils import INDUSTRY_KEYS


def render(model_name: str):
    st.title("🧠 性格診断・適性検査")
    st.write("ビッグファイブ（5因子モデル）準拠の30問で、就活に活かせるあなたのパーソナリティを分析します。")

    if st.button("← インタビューに戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    # ── 結果表示フェーズ ────────────────────────────────────────
    if st.session_state.pa_result is not None:
        _render_result()

    # ── AI生成中フェーズ ────────────────────────────────────────
    elif st.session_state.pa_is_generating:
        with st.spinner("回答を分析中...（少しお待ちください）"):
            try:
                axis_scores = compute_axis_scores(st.session_state.pa_answers)
                result = generate_personality_result(model_name, st.session_state.pa_answers, axis_scores)
                if result and result.get("ok"):
                    st.session_state.pa_axis_scores = axis_scores
                    st.session_state.pa_result = result
                    st.session_state.pa_error = None
                else:
                    err = result.get("error_msg", "不明なエラー") if result else "生成に失敗しました"
                    st.session_state.pa_error = err
            except Exception as e:
                st.session_state.pa_error = str(e)
        st.session_state.pa_is_generating = False
        st.rerun()

    # ── 設問フェーズ ────────────────────────────────────────────
    else:
        _render_questions()


# ──────────────────────────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────────────────────────

def _render_result():
    result = st.session_state.pa_result
    scores = st.session_state.pa_axis_scores or {}

    st.subheader("📋 診断結果")

    if result.get("personality_summary"):
        st.info(result["personality_summary"])

    st.markdown("#### 🔢 5因子スコア")
    axis_cols = st.columns(len(AXES))
    for col, (axis_key, axis_label) in zip(axis_cols, AXES.items()):
        score = scores.get(axis_key, 0.0)
        short_label = axis_label.split("（")[0]
        with col:
            st.metric(short_label, f"{score:.1f} / 5")

    if result.get("consistency_score") is not None:
        score = result["consistency_score"]
        if score >= 85:
            level, color = "高", "🟢"
        elif score >= 70:
            level, color = "普通", "🟡"
        else:
            level, color = "低", "🔴"
        st.markdown("#### 🎯 回答信頼度")
        st.info(f"{color} {score}/100 （信頼度: {level}）")

    if result.get("strengths"):
        st.markdown("#### 💪 強み")
        for item in result["strengths"]:
            with st.container(border=True):
                st.markdown(f"**{item.get('point', '')}**")
                if item.get("detail"):
                    st.caption(item["detail"])

    if result.get("cautions"):
        st.markdown("#### 🌱 成長余地")
        for item in result["cautions"]:
            with st.container(border=True):
                st.markdown(f"**{item.get('point', '')}**")
                if item.get("hint"):
                    st.caption(f"ヒント: {item['hint']}")

    if result.get("fit_environments"):
        st.markdown("#### 🎯 向いている職種・環境")
        st.info(result["fit_environments"])

    industry_fit = result.get("industry_fit", {})
    if industry_fit:
        st.markdown("#### 🏢 業界別フィット度")
        for row_start in range(0, len(INDUSTRY_KEYS), 2):
            row_keys = INDUSTRY_KEYS[row_start : row_start + 2]
            cols = st.columns(2)
            for col, key in zip(cols, row_keys):
                entry = industry_fit.get(key, {})
                score = entry.get("score", 0) if isinstance(entry, dict) else 0
                reason = entry.get("reason", "") if isinstance(entry, dict) else ""
                stars = "⭐" * score + "☆" * (5 - score)
                with col:
                    st.markdown(f"**{key}**")
                    st.markdown(f"{stars}　{score}/5")
                    if reason:
                        st.caption(reason)

    recommended_roles = result.get("recommended_roles", [])
    if recommended_roles:
        st.markdown("#### 💼 おすすめ職種")
        for item in recommended_roles:
            role = item.get("role", "")
            score = item.get("score", 0)
            with st.container(border=True):
                st.markdown(f"**{role}**")
                st.progress(min(score / 5.0, 1.0))
                st.caption(f"適性スコア {score:.2f}")

    interview_strengths = result.get("interview_strengths", [])
    if interview_strengths:
        st.markdown("#### 🎤 面接でアピールできる強み")
        for item in interview_strengths:
            st.success(item)

    interview_risks = result.get("interview_risks", [])
    if interview_risks:
        st.markdown("#### ⚠️ 面接で注意するポイント")
        for item in interview_risks:
            st.warning(item)

    if result.get("interview_tips"):
        st.markdown("#### 💬 面接での活かし方")
        st.success(result["interview_tips"])

    st.write("---")
    col_fav, col_retry, col_back = st.columns(3)
    with col_fav:
        _pa_fav_session_id = st.session_state.get("current_session_id")
        _pa_is_fav = is_favorited("personality", session_id=_pa_fav_session_id) if _pa_fav_session_id else False
        if _pa_is_fav:
            if st.button("⭐ お気に入り解除", key="pa_fav_remove", use_container_width=True):
                remove_favorite_by_item("personality", session_id=_pa_fav_session_id)
                st.rerun()
        else:
            if st.button("☆ お気に入りに追加", key="pa_fav_add", use_container_width=True,
                         help="この診断結果をお気に入りに保存します。先にサイドバーからセッションを保存してください。"):
                if not _pa_fav_session_id:
                    st.toast("先にサイドバーからセッションを保存してください。", icon="⚠️")
                else:
                    _pa_result = st.session_state.pa_result or {}
                    add_favorite(
                        item_type="personality",
                        session_id=_pa_fav_session_id,
                        company_name=st.session_state.get("current_company_name") or None,
                        label="性格診断結果",
                        content_snapshot={
                            "summary": _pa_result.get("personality_summary", "")[:80],
                        },
                    )
                    st.toast("お気に入りに追加しました ⭐", icon="⭐")
                    st.rerun()
    with col_retry:
        if st.button("🔁 もう一度診断する"):
            st.session_state.pa_answers = {}
            st.session_state.pa_current_q = 0
            st.session_state.pa_result = None
            st.session_state.pa_axis_scores = None
            st.session_state.pa_error = None
            st.rerun()
    with col_back:
        if st.button("← インタビューに戻る", key="back_from_result"):
            st.session_state.app_mode = "interview"
            st.rerun()


def _render_questions():
    current_q_idx = st.session_state.pa_current_q

    if current_q_idx == 0:
        st.markdown("""
**所要時間:** 約3〜5分  
**設問数:** 30問（5段階回答）  
**測定軸:** 外向性 / 誠実性 / 協調性 / 開放性 / 情緒安定性（ビッグファイブ準拠）

各設問に対して、自分にどの程度当てはまるかを5段階で回答してください。  
「正解」はありません。直感で答えるのがおすすめです。
""", unsafe_allow_html=True)
        if st.button("▶ 診断を開始する", type="primary", use_container_width=True):
            st.session_state.pa_current_q = 1
            st.rerun()
        return

    progress = len(st.session_state.pa_answers) / TOTAL_QUESTIONS
    st.progress(progress, text=f"設問 {current_q_idx} / {TOTAL_QUESTIONS}")

    q = QUESTIONS[current_q_idx - 1]

    with st.container(border=True):
        st.markdown(f"**Q{q['id']}. {q['text']}**")
        st.write("")

        btn_cols = st.columns(5)
        for score_val, score_label in SCALE_LABELS.items():
            with btn_cols[score_val - 1]:
                already = st.session_state.pa_answers.get(q["id"])
                is_selected = already == score_val
                btn_label = f"{'✅ ' if is_selected else ''}{score_val}"
                if st.button(
                    btn_label,
                    key=f"pa_q{q['id']}_s{score_val}",
                    use_container_width=True,
                    help=score_label,
                ):
                    st.session_state.pa_answers[q["id"]] = score_val
                    if current_q_idx < TOTAL_QUESTIONS:
                        st.session_state.pa_current_q += 1
                    st.rerun()

        label_cols = st.columns(5)
        for i, (_, lbl) in enumerate(SCALE_LABELS.items()):
            with label_cols[i]:
                st.caption(lbl)

    st.write("")

    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 2])
    with nav_col1:
        if current_q_idx > 1:
            if st.button("← 前へ"):
                st.session_state.pa_current_q -= 1
                st.rerun()
    with nav_col2:
        if current_q_idx < TOTAL_QUESTIONS:
            if st.button("次へ →"):
                st.session_state.pa_current_q += 1
                st.rerun()

    answered_count = len(st.session_state.pa_answers)
    with nav_col3:
        can_finish = answered_count >= TOTAL_QUESTIONS * 0.8
        if can_finish:
            finish_label = f"✨ 結果を見る（{answered_count}/{TOTAL_QUESTIONS}問回答済み）"
            if st.button(finish_label, type="primary", use_container_width=True):
                st.session_state.pa_is_generating = True
                st.rerun()
        else:
            st.caption(f"あと{int(TOTAL_QUESTIONS * 0.8) - answered_count}問以上回答すると結果を表示できます")

    if st.session_state.pa_error:
        st.error(f"分析に失敗しました: {st.session_state.pa_error}\nOllamaの状態をご確認ください。")
