"""
components/sidebar/session_panel.py
-------------------------------------
セッションの保存・バックアップ（JSON出力/取り込み）・リセットUIを描画する。
"""

import streamlit as st

from session_io import (
    serialize_session,
    make_filename,
    save_session_to_db,
    export_session_as_json,
    import_json_as_session,
)
from favorites import (
    add_favorite,
    build_auto_save_snapshot,
)
from rag import get_or_create_knowledge_base


def render_session_panel(model_name: str) -> None:
    """セッション保存・バックアップ・リセットパネルを描画する。"""
    st.write("---")
    _render_save_section()
    st.write("---")
    _render_backup_section()
    st.write("---")
    if st.button("🔄 最初からやり直す（未保存の内容は消えます）"):
        st.session_state.clear()
        st.rerun()


def _render_save_section() -> None:
    """現在のセッションをDBに保存するUIを描画する。"""
    st.header("💾 現在のセッションを保存")
    st.caption(
        "面接内容・自己PR・診断結果はこのPC内のデータベース（SQLite）に保存されます。"
        "外部サーバーへの送信は一切行いません。過去の履歴は「面接履歴」ページから確認できます。"
    )

    _save_messages_count = len(st.session_state.get("messages") or [])
    _save_has_pr = bool(st.session_state.get("final_pr"))
    _save_has_personality = bool(st.session_state.get("pa_result"))
    _save_has_mock_eval = bool(st.session_state.get("mock_evaluation"))
    _save_has_summary = bool(st.session_state.get("interview_summary"))
    _save_has_predicted_q = bool(st.session_state.get("predicted_questions"))
    _save_has_company_prs = bool(st.session_state.get("company_prs"))

    _summary_parts = [f"会話履歴{_save_messages_count}件"]
    _summary_parts.append("自己PRあり" if _save_has_pr else "自己PRなし")
    _summary_parts.append("性格診断あり" if _save_has_personality else "性格診断なし")
    _summary_parts.append("模擬面接結果あり" if _save_has_mock_eval else "模擬面接結果なし")
    st.caption("📦 今保存すると: " + "・".join(_summary_parts))

    with st.expander("保存内容の詳細を確認する"):
        st.markdown(f"- 会話履歴（チャットメッセージ）: **{_save_messages_count}件**")
        st.markdown(f"- 自己PR本文: {'**あり**' if _save_has_pr else 'なし'}")
        st.markdown(f"- 面接サマリー: {'**あり**' if _save_has_summary else 'なし'}")
        st.markdown(f"- 想定質問・模範回答: {'**あり**' if _save_has_predicted_q else 'なし'}")
        st.markdown(f"- 企業別カスタマイズ自己PR: {'**あり**' if _save_has_company_prs else 'なし'}")
        st.markdown(f"- 性格診断結果: {'**あり**' if _save_has_personality else 'なし'}")
        st.markdown(f"- AI模擬面接の結果（完了後の評価）: {'**あり**' if _save_has_mock_eval else 'なし'}")
        st.caption(
            "※ AI模擬面接は「完了後の評価結果」のみ保存されます。面接途中の会話のやり取りは保存されません。"
            "結果を保存したい場合は、模擬面接を最後まで終えてから保存してください。"
        )

    save_company_name = st.text_input(
        "会社名",
        value=st.session_state.get("current_company_name", ""),
        key="session_save_company_name",
    )
    save_session_type = st.selectbox(
        "面接種別",
        options=["模擬面接", "一次面接対策", "最終面接対策", "その他"],
        key="session_save_type",
    )

    _has_question_set = bool(
        st.session_state.get("predicted_questions") or st.session_state.get("pq_questions")
    )
    _save_question_set = False
    if _has_question_set:
        _save_question_set = st.checkbox(
            "📋 想定質問セットをお気に入りに含める",
            value=True,
            key="save_include_question_set",
            help="チェックを外すとこのセッションの想定質問はお気に入りに保存されません。",
        )

    _auto_snap = build_auto_save_snapshot(st.session_state)
    _auto_parts = []
    if _auto_snap.get("career_advice"):
        _n = _auto_snap["career_advice"]["message_count"]
        _auto_parts.append(f"🤖 AIキャリア相談（{_n}件）")
    if _auto_snap.get("company_matrix"):
        _companies = _auto_snap["company_matrix"].get("companies", [])
        _auto_parts.append(f"🏢 企業比較（{len(_companies)}社）")
    if _auto_parts:
        st.caption("✅ セッション保存時に自動でお気に入いに追加: " + "・".join(_auto_parts))

    if st.button("💾 現在の内容をセッションとして保存する", use_container_width=True):
        current_kb_id = None
        if save_company_name.strip():
            current_kb_id = get_or_create_knowledge_base(save_company_name.strip(), "company")
        saved_id = save_session_to_db(
            st.session_state,
            session_id=st.session_state.get("current_session_id"),
            company_name=save_company_name.strip() or None,
            session_type=save_session_type,
            knowledge_base_id=current_kb_id,
        )
        st.session_state.current_session_id = saved_id

        _save_company = save_company_name.strip() or None
        _save_stype = save_session_type

        if _auto_snap.get("career_advice"):
            add_favorite(
                item_type="career_advice",
                session_id=saved_id,
                company_name=_save_company,
                session_type=_save_stype,
                label="AIキャリア相談",
                content_snapshot=_auto_snap["career_advice"],
            )
        if _auto_snap.get("company_matrix"):
            add_favorite(
                item_type="company_matrix",
                session_id=saved_id,
                company_name=_save_company,
                session_type=_save_stype,
                label="企業比較マトリクス",
                content_snapshot=_auto_snap["company_matrix"],
            )
        if _has_question_set and _save_question_set:
            _q_data = st.session_state.get("predicted_questions") or st.session_state.get("pq_questions")
            add_favorite(
                item_type="question_set",
                session_id=saved_id,
                company_name=_save_company,
                session_type=_save_stype,
                label="想定質問セット",
                content_snapshot={"question_count": len(_q_data) if _q_data else 0},
            )

        st.success(f"セッションを保存しました（ID: {saved_id}）。")

    if st.session_state.get("rag_restore_error"):
        st.warning(
            f"※ 直前に読み込んだセッションのRAG資料（履歴書・企業情報）復元中にエラーが発生しました: "
            f"{st.session_state.rag_restore_error}"
        )


def _render_backup_section() -> None:
    """JSONエクスポート・インポートによるバックアップUIを描画する。"""
    st.header("🗄️ バックアップ（JSON）")
    st.caption("他のPCへの移行やバックアップ用に、セッションをJSONファイルとして出力・取り込みできます。")

    if st.session_state.get("current_session_id"):
        try:
            backup_bytes = export_session_as_json(st.session_state.current_session_id)
            st.download_button(
                label="⬇️ 現在のセッションをJSONでエクスポート",
                data=backup_bytes,
                file_name=make_filename(),
                mime="application/json",
                use_container_width=True,
            )
        except ValueError:
            # DBにセッションが見つからない場合（DB再作成・削除後など）
            st.session_state.current_session_id = None
            session_bytes = serialize_session(st.session_state)
            st.download_button(
                label="⬇️ 現在のセッションをJSONでエクスポート（未保存）",
                data=session_bytes,
                file_name=make_filename(),
                mime="application/json",
                use_container_width=True,
            )
            st.caption("⚠️ 保存済みセッションが見つかりませんでした。再度「セッションとして保存」してください。")
    else:
        session_bytes = serialize_session(st.session_state)
        st.download_button(
            label="⬇️ 現在のセッションをJSONでエクスポート（未保存）",
            data=session_bytes,
            file_name=make_filename(),
            mime="application/json",
            use_container_width=True,
        )

    restore_file = st.file_uploader(
        "📂 JSONファイルから面接履歴を取り込む", type=["json"], key="session_restore_uploader"
    )
    if restore_file is not None:
        if st.button("✅ このファイルを新しいセッションとして取り込む", use_container_width=True):
            new_session_id, err = import_json_as_session(restore_file.read())
            if err:
                st.error(f"読み込みに失敗しました: {err}")
            else:
                st.success(f"セッションを取り込みました（新しいID: {new_session_id}）。一覧から開いてください。")
                st.rerun()
