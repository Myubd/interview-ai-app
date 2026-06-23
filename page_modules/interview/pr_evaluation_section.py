"""
interview/pr_evaluation_section.py
自己PR評価・微調整セクション（ステップ3）
"""

import streamlit as st

from pr_generation import REFINE_PRESETS, evaluate_pr, refine_pr
from page_modules.interview.helpers import build_conversation_history


def render_pr_evaluation_section(model_name: str):
    """選択済みの自己PRに対する評価・微調整UIを描画する。"""

    selected_label = st.session_state.pr_variants[st.session_state.selected_variant_index]["label"]
    st.success(f"🎉 「{selected_label}」を選択中です")
    st.write("---")
    st.markdown(st.session_state.final_pr)

    # 文字数カウント（ES提出時の文字数管理に便利なよう目標文字数も表示）
    pr_len = len(st.session_state.final_pr)
    _char_col1, _char_col2 = st.columns([2, 3])
    with _char_col1:
        st.caption(f"📝 現在の文字数: **{pr_len}文字**")
    with _char_col2:
        _target = st.number_input(
            "目標文字数（任意）", min_value=0, max_value=2000, value=0, step=50,
            key="pr_target_chars", label_visibility="collapsed",
            help="ES提出先の文字数制限を入力すると達成率が表示されます（0で非表示）",
        )
        if _target > 0:
            _pct = min(int(pr_len / _target * 100), 100)
            _color = "normal" if _pct <= 100 else "inverse"
            st.progress(_pct / 100, text=f"{pr_len}/{_target}文字 （{_pct}%）")

    st.write("---")

    _render_evaluation(model_name)
    st.write("---")
    _render_refine(model_name)


# ──────────────────────────────────────────────────────────────
# 評価サブセクション
# ──────────────────────────────────────────────────────────────

def _render_evaluation(model_name: str):
    st.subheader("🔍 AIによるセルフ評価")

    if st.session_state.pr_evaluation is None:
        eval_label = "📊 採用担当者視点で評価してもらう"
        if not st.session_state.is_evaluating:
            if st.button(eval_label):
                st.session_state.is_evaluating = True
                st.session_state.pr_evaluation_error = False
                st.rerun()
            if st.session_state.pr_evaluation_error:
                st.warning("評価の取得に失敗しました。Ollamaの状態をご確認の上、もう一度お試しください。")
        else:
            st.button(eval_label, disabled=True)
            with st.spinner("評価中..."):
                st.session_state.pr_evaluation = evaluate_pr(model_name, st.session_state.final_pr)
                st.session_state.pr_evaluation_error = st.session_state.pr_evaluation is None
            st.session_state.is_evaluating = False
            st.rerun()
    else:
        ev = st.session_state.pr_evaluation
        score_cols = st.columns(len(ev["scores"]) or 1)
        for col, (axis, score) in zip(score_cols, ev["scores"].items()):
            with col:
                st.metric(axis, f"{score} / 5")
        if ev["summary"]:
            st.info(ev["summary"])
        if ev["improvements"]:
            st.markdown("**改善のヒント:**")
            for tip in ev["improvements"]:
                st.markdown(f"- {tip}")
        if st.button("🔄 評価をやり直す"):
            st.session_state.pr_evaluation = None
            st.rerun()


# ──────────────────────────────────────────────────────────────
# 微調整サブセクション
# ──────────────────────────────────────────────────────────────

def _render_refine(model_name: str):
    st.subheader("🛠️ 微調整")
    st.caption("現在の自己PRをベースに、トーンや簡潔さを調整できます（ゼロから作り直しません）。")

    preset_labels = {
        "concise":    "✂️ 簡潔に",
        "passionate": "🔥 熱意を強く",
        "formal":     "🎩 フォーマルに",
        "specific":   "🔢 具体性を強化",
    }

    if not st.session_state.is_refining:
        preset_cols = st.columns(4)
        clicked_preset = None
        for col, (key, label) in zip(preset_cols, preset_labels.items()):
            with col:
                if st.button(label, key=f"preset_{key}"):
                    clicked_preset = key

        custom_instruction = st.text_input(
            "または自由記述で指示（例: もっと協調性を強調して）",
            key="custom_refine_instruction",
        )
        custom_clicked = st.button("✏️ この指示でリライト")

        instruction_to_use = None
        if clicked_preset:
            instruction_to_use = REFINE_PRESETS[clicked_preset]
        elif custom_clicked and custom_instruction.strip():
            instruction_to_use = custom_instruction.strip()
        elif custom_clicked:
            st.toast("指示を入力してください🙏", icon="⚠️")

        if instruction_to_use:
            st.session_state.pending_refine_instruction = instruction_to_use
            st.session_state.is_refining = True
            st.session_state.pr_refine_error = None
            st.rerun()

        if st.session_state.pr_refine_error:
            st.error(st.session_state.pr_refine_error)
    else:
        preset_cols = st.columns(4)
        for col, (key, label) in zip(preset_cols, preset_labels.items()):
            with col:
                st.button(label, key=f"preset_{key}_disabled", disabled=True)
        st.text_input(
            "または自由記述で指示（例: もっと協調性を強調して）",
            key="custom_refine_instruction_disabled", disabled=True, value="",
        )
        st.button("✏️ この指示でリライト", disabled=True, key="custom_refine_disabled")

        with st.spinner("リライト中..."):
            try:
                history = build_conversation_history()
                refine_result = refine_pr(
                    model_name,
                    st.session_state.final_pr,
                    st.session_state.pending_refine_instruction,
                    history,
                )
                st.session_state.final_pr = refine_result["pr_text"]
                st.session_state.pr_evaluation = None
                if refine_result["ok"]:
                    st.session_state.pr_refine_error = None
                else:
                    st.session_state.pr_refine_error = (
                        f"リライトに失敗したため、内容は変更されていません。詳細: {refine_result['error_msg']}"
                    )
            except Exception as e:
                st.session_state.pr_refine_error = "自己PRのリライトに失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
        st.session_state.pending_refine_instruction = None
        st.session_state.is_refining = False
        st.rerun()
