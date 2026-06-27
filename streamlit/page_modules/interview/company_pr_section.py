"""
interview/company_pr_section.py
企業別カスタマイズ自己PRセクション
"""

import streamlit as st

from pr_generation import generate_company_pr
from page_modules.interview.helpers import build_conversation_history


def render_company_pr_section(model_name: str):
    st.subheader("🏢 企業別カスタマイズ自己PR")
    st.caption("企業情報を入力すると、その企業の求める人物像に合わせた自己PRを自動生成します。企業は動的に追加できます。")

    inputs = st.session_state.company_pr_inputs

    _render_company_inputs(inputs)
    _render_generate_button(inputs, model_name)

    if st.session_state.company_pr_error:
        st.error(st.session_state.company_pr_error)

    if st.session_state.is_generating_company_prs:
        _run_generation(inputs, model_name)

    if st.session_state.company_prs:
        _render_results()

    st.write("---")
    _render_footer_buttons()


# ──────────────────────────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────────────────────────

def _render_company_inputs(inputs: list):
    for i, entry in enumerate(inputs):
        with st.container(border=True):
            col_name, col_del = st.columns([4, 1])
            with col_name:
                name_val = st.text_input(
                    f"企業名 {i+1}", value=entry["name"], key=f"company_name_{i}",
                    placeholder="例）株式会社〇〇",
                )
            with col_del:
                st.write("")
                if len(inputs) > 1 and st.button("✕", key=f"del_company_{i}"):
                    st.session_state.company_pr_inputs.pop(i)
                    st.rerun()
            info_val = st.text_area(
                f"企業情報（事業内容・求める人物像・バリューなど）{i+1}",
                value=entry["info"], key=f"company_info_{i}", height=100,
                placeholder="例）〇〇業界のリーディングカンパニー。チャレンジ精神と協調性を重視。DX推進に注力中。",
            )
            st.session_state.company_pr_inputs[i]["name"] = name_val
            st.session_state.company_pr_inputs[i]["info"] = info_val


def _render_generate_button(inputs: list, model_name: str):
    col_add, col_gen = st.columns([1, 2])
    valid_inputs = [e for e in inputs if e["name"].strip() and e["info"].strip()]

    with col_add:
        if st.button("＋ 企業を追加する"):
            st.session_state.company_pr_inputs.append({"name": "", "info": ""})
            st.rerun()
    with col_gen:
        gen_disabled = not valid_inputs or st.session_state.is_generating_company_prs
        if st.button(
            f"✨ {len(valid_inputs)}社分のカスタマイズPRを生成する",
            type="primary", disabled=gen_disabled, use_container_width=True,
        ):
            st.session_state.is_generating_company_prs = True
            st.session_state.company_pr_error = None
            st.rerun()

    if not valid_inputs and not st.session_state.company_prs:
        st.caption("企業名と企業情報を入力してから「生成する」を押してください。")


def _run_generation(inputs: list, model_name: str):
    valid_inputs = [e for e in inputs if e["name"].strip() and e["info"].strip()]
    history = build_conversation_history()
    errors = []
    progress_bar = st.progress(0, text="企業別PRを生成中...")

    for idx, entry in enumerate(valid_inputs):
        progress_bar.progress(
            idx / len(valid_inputs),
            text=f"生成中: {entry['name']} ({idx+1}/{len(valid_inputs)})",
        )
        try:
            result = generate_company_pr(
                model=model_name,
                base_pr=st.session_state.final_pr,
                company_name=entry["name"],
                company_info=entry["info"],
                conversation_history=history,
            )
            st.session_state.company_prs[entry["name"]] = {
                "pr_text": result["pr_text"],
                "points": result["points"],
                "info": entry["info"],
                "ok": result["ok"],
            }
            if not result["ok"]:
                errors.append(f"{entry['name']}: {result.get('error_msg', '不明なエラー')}")
        except Exception as e:
            errors.append(f"{entry['name']} の生成中にエラーが発生しました。Ollamaの状態をご確認ください。")

    progress_bar.progress(1.0, text="完了")
    st.session_state.is_generating_company_prs = False
    if errors:
        st.session_state.company_pr_error = "一部の企業でエラーが発生しました: " + " / ".join(errors)
    st.rerun()


def _render_results():
    st.markdown("#### 生成済みカスタマイズPR")
    for company_name, data in st.session_state.company_prs.items():
        with st.expander(f"🏢 {company_name}", expanded=True):
            if data.get("points"):
                st.caption("カスタマイズポイント: " + " / ".join(f"・{p}" for p in data["points"]))
            st.write(data["pr_text"])
            st.caption(f"{len(data['pr_text'])}文字")
    if st.button("🔄 すべて再生成する"):
        st.session_state.company_prs = {}
        st.rerun()


def _render_footer_buttons():
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ 他の案を選び直す"):
            st.session_state.selected_variant_index = None
            st.session_state.final_pr = None
            st.session_state.pr_evaluation = None
            st.rerun()
    with col2:
        if st.button("🔁 3パターンを再生成する"):
            st.session_state.pr_variants = None
            st.session_state.selected_variant_index = None
            st.session_state.final_pr = None
            st.session_state.pr_evaluation = None
            st.rerun()
    with col3:
        if st.button("🆕 最初からインタビューを受ける"):
            st.session_state.clear()
            st.rerun()
