"""
page_modules/company_matrix_page.py
企業比較マトリクスページ（company_page.py から分離）
"""

import streamlit as st
from collections import defaultdict

from company_matrix import (
    MATRIX_AXES_FIXED,
    VALUE_FIT_AXIS_KEY,
    VALUE_FIT_NOTE,
    MAX_COMPANIES,
    generate_motivation_for_all,
    generate_comparison_matrix,
    generate_why_not_others,
    export_matrix_to_csv_rows,
)
from rag import (
    load_active_documents, get_or_create_knowledge_base,
    list_knowledge_bases, format_context, RESUME_KB_NAME,
)
from favorites import (
    add_favorite, remove_favorite, is_favorited,
    count_favorites, ITEM_TYPE_LABELS,
)

def render_company_matrix(model_name: str, build_conversation_history):
    st.title("🏢 企業比較マトリクス")
    st.write(
        "保存済みの企業情報（サイドバーの「📎 参考資料（RAG）」から登録）の中から最大"
        f"{MAX_COMPANIES}社を選んで、志望動機の一括生成・複数軸での比較・"
        "「なぜ他社でなくこの企業か」の差別化ポイントをまとめて作成します。"
    )

    if st.button("← 自己PR作成に戻る", key="cm_back_button"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    _cm_company_kbs = list_knowledge_bases(kb_type="company")

    if not _cm_company_kbs:
        st.warning(
            "比較対象の企業情報がまだ保存されていません。サイドバーの「📎 参考資料（RAG）」から、"
            "会社名を入力して企業情報をアップロードしてください（複数社分、繰り返し登録できます）。"
        )
        st.stop()

    # 企業選択
    st.subheader("① 比較する企業を選択")
    _cm_kb_name_by_id = {kb["id"]: kb["name"] for kb in _cm_company_kbs}
    _cm_selected_ids: list[int] = []
    _cm_cols = st.columns(2)
    for _i, kb in enumerate(_cm_company_kbs):
        with _cm_cols[_i % 2]:
            checked = st.checkbox(
                kb["name"],
                value=kb["id"] in st.session_state.cm_selected_kb_ids,
                key=f"cm_kb_check_{kb['id']}",
            )
            if checked:
                _cm_selected_ids.append(kb["id"])

    if len(_cm_selected_ids) > MAX_COMPANIES:
        st.warning(f"比較できるのは最大{MAX_COMPANIES}社までです。先頭{MAX_COMPANIES}社のみ使用します。")
        _cm_selected_ids = _cm_selected_ids[:MAX_COMPANIES]

    if set(_cm_selected_ids) != set(st.session_state.cm_selected_kb_ids):
        st.session_state.cm_motivations = None
        st.session_state.cm_matrix_result = None
        st.session_state.cm_why_not_others = {}

    st.session_state.cm_selected_kb_ids = _cm_selected_ids

    if len(_cm_selected_ids) < 2:
        st.info("比較には2社以上の選択が必要です（志望動機の一括生成のみなら1社でも可）。")

    def _cm_build_company_dict(kb_id: int) -> dict:
        docs = load_active_documents([kb_id])
        info_text = "\n".join(chunk for doc in docs for chunk in doc.chunks)
        return {"name": _cm_kb_name_by_id.get(kb_id, "企業名不明"), "info": info_text, "industry": ""}

    _cm_selected_companies = [_cm_build_company_dict(kb_id) for kb_id in _cm_selected_ids]

    # 追加比較軸
    st.subheader("② 比較軸（任意で追加）")
    st.caption(
        "固定の7軸（" + "／".join(MATRIX_AXES_FIXED) + "）に加えて、"
        "最大3軸まで自由に追加できます。"
    )
    _cm_axes_text = st.text_input(
        "追加軸（カンマ区切り、例: 海外展開の積極性, 研修制度の充実度）",
        value=", ".join(st.session_state.cm_additional_axes),
        key="cm_additional_axes_input",
    )
    _cm_new_additional_axes = [a.strip() for a in _cm_axes_text.split(",") if a.strip()][:3]
    if _cm_new_additional_axes != st.session_state.cm_additional_axes:
        st.session_state.cm_matrix_result = None
    st.session_state.cm_additional_axes = _cm_new_additional_axes

    st.caption(VALUE_FIT_NOTE)

    if st.session_state.cm_error:
        st.error(st.session_state.cm_error)

    st.write("---")

    tab_motivation, tab_matrix, tab_why_not = st.tabs(
        ["📝 志望動機（一括）", "📊 比較マトリクス", "🆚 差別化ポイント"]
    )

    # タブ1: 志望動機
    with tab_motivation:
        st.caption("選択した企業ごとに、自己PR・インタビュー履歴を踏まえた志望動機文を生成します。")
        if not _cm_selected_companies:
            st.info("企業を選択してください。")
        else:
            if st.session_state.cm_motivations is None:
                if not st.session_state.cm_is_generating:
                    if st.button("📝 志望動機を一括生成する", key="cm_gen_motivation_btn"):
                        st.session_state.cm_is_generating = True
                        st.session_state.cm_error = None
                        st.rerun()
                else:
                    with st.spinner("各社の志望動機を生成中...（社数が多いほど時間がかかります）"):
                        try:
                            history = build_conversation_history()
                            st.session_state.cm_motivations = generate_motivation_for_all(
                                model=model_name,
                                companies=_cm_selected_companies,
                                pr_text=st.session_state.final_pr or "",
                                conversation_history=history,
                            )
                        except Exception as e:
                            st.session_state.cm_error = "志望動機の生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
                        st.session_state.cm_is_generating = False
                        st.rerun()
            else:
                for result in st.session_state.cm_motivations:
                    with st.expander(f"🏢 {result['company_name']}", expanded=True):
                        if not result.get("ok", True):
                            st.warning(f"生成に失敗しました: {result.get('error_msg', '')}")
                        if result.get("motivation_text"):
                            st.write(result["motivation_text"])
                        if result.get("key_points"):
                            st.caption("アピールポイント:")
                            for p in result["key_points"]:
                                st.caption(f"・{p}")
                if st.button("🔄 志望動機を再生成する", key="cm_regen_motivation_btn"):
                    st.session_state.cm_motivations = None
                    st.rerun()

    # タブ2: 比較マトリクス
    with tab_matrix:
        st.caption("複数企業を比較軸ごとにスコアリングします。2社以上を選択してください。")
        if len(_cm_selected_companies) < 2:
            st.info("比較マトリクスの生成には2社以上の選択が必要です。")
        else:
            if st.session_state.cm_matrix_result is None:
                if not st.session_state.cm_is_generating:
                    if st.button("📊 比較マトリクスを生成する", key="cm_gen_matrix_btn"):
                        st.session_state.cm_is_generating = True
                        st.session_state.cm_error = None
                        st.rerun()
                else:
                    with st.spinner("比較マトリクスを生成中..."):
                        try:
                            st.session_state.cm_matrix_result = generate_comparison_matrix(
                                model=model_name,
                                companies=_cm_selected_companies,
                                pr_text=st.session_state.final_pr or "",
                                additional_axes=st.session_state.cm_additional_axes,
                            )
                        except Exception as e:
                            st.session_state.cm_error = "比較マトリクスの生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
                        st.session_state.cm_is_generating = False
                        st.rerun()
            else:
                _cm_result = st.session_state.cm_matrix_result
                if not _cm_result.get("ok", True):
                    st.warning(f"生成中にエラーが発生しました: {_cm_result.get('error_msg', '')}")

                _cm_axes = _cm_result.get("axes", [])
                _cm_companies = _cm_result.get("companies", [])
                _cm_matrix = _cm_result.get("matrix", {})

                for ax in _cm_axes:
                    note = " 　" + VALUE_FIT_NOTE if ax == VALUE_FIT_AXIS_KEY else ""
                    st.markdown(f"**{ax}**{note}")
                    score_cols = st.columns(len(_cm_companies)) if _cm_companies else [st]
                    for col, company in zip(score_cols, _cm_companies):
                        entry = _cm_matrix.get(ax, {}).get(company, {})
                        with col:
                            st.metric(company, f"{entry.get('score', '-')} / 5")
                            st.caption(entry.get("comment", ""))
                    st.write("")

                if _cm_result.get("overall_recommendation"):
                    st.success(f"💡 総合推薦コメント: {_cm_result['overall_recommendation']}")

                _cm_csv = export_matrix_to_csv_rows(_cm_result)
                st.download_button(
                    "⬇️ 比較マトリクスをCSVでダウンロード",
                    data=_cm_csv.encode("utf-8"),
                    file_name="company_comparison_matrix.csv",
                    mime="text/csv",
                    key="cm_csv_download",
                )

                if st.button("🔄 比較マトリクスを再生成する", key="cm_regen_matrix_btn"):
                    st.session_state.cm_matrix_result = None
                    st.rerun()

    # タブ3: 差別化ポイント
    with tab_why_not:
        st.caption("第一志望企業を1社選び、他社と比べた差別化ポイントと回答テンプレートを生成します。")
        if not _cm_selected_companies:
            st.info("企業を選択してください。")
        else:
            _cm_target_name = st.selectbox(
                "第一志望企業（メインで深掘りする企業）",
                options=[c["name"] for c in _cm_selected_companies],
                key="cm_target_company_selector",
            )
            _cm_target = next(c for c in _cm_selected_companies if c["name"] == _cm_target_name)
            _cm_target_kb_id = next(
                kb_id for kb_id in _cm_selected_ids if _cm_kb_name_by_id.get(kb_id) == _cm_target_name
            )
            _cm_others = [c for c in _cm_selected_companies if c["name"] != _cm_target_name]
            _cm_existing_result = st.session_state.cm_why_not_others.get(_cm_target_kb_id)

            if _cm_existing_result is None:
                if not _cm_others:
                    st.info("比較対象となる他社をもう1社以上選択してください。")
                elif not st.session_state.cm_is_generating:
                    if st.button("🆚 差別化ポイントを生成する", key="cm_gen_why_not_btn"):
                        st.session_state.cm_is_generating = True
                        st.session_state.cm_error = None
                        st.rerun()
                else:
                    with st.spinner("差別化ポイントを生成中..."):
                        try:
                            history = build_conversation_history()
                            result = generate_why_not_others(
                                model=model_name,
                                target_company=_cm_target,
                                other_companies=_cm_others,
                                pr_text=st.session_state.final_pr or "",
                                conversation_history=history,
                            )
                            st.session_state.cm_why_not_others[_cm_target_kb_id] = result
                        except Exception as e:
                            st.session_state.cm_error = "差別化ポイントの生成に失敗しました。Ollamaが起動しているか、モデル名をご確認ください。"
                        st.session_state.cm_is_generating = False
                        st.rerun()
            else:
                if not _cm_existing_result.get("ok", True):
                    st.warning(f"生成中にエラーが発生しました: {_cm_existing_result.get('error_msg', '')}")
                for diff in _cm_existing_result.get("differentiators", []):
                    st.markdown(f"**・{diff['point']}**")
                    if diff.get("vs_others"):
                        st.caption(f"他社との違い: {diff['vs_others']}")
                if _cm_existing_result.get("answer_template"):
                    st.write("---")
                    st.markdown("**回答テンプレート例:**")
                    st.info(_cm_existing_result["answer_template"])
                if st.button("🔄 差別化ポイントを再生成する", key="cm_regen_why_not_btn"):
                    st.session_state.cm_why_not_others.pop(_cm_target_kb_id, None)
                    st.rerun()


# ──────────────────────────────────────────────────────────────
