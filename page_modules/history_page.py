"""
page_modules/history_page.py
面接履歴ページ（company_page.py から分離）
"""

import streamlit as st

from favorites import (
    remove_favorite_by_item,
    add_favorite, remove_favorite, is_favorited,
    list_favorites, list_distinct_companies, list_distinct_session_types,
    count_favorites, ITEM_TYPE_LABELS,
)
from session_io import load_session_from_db, list_sessions, delete_session

def render_history():
    st.title("✅ 面接履歴")

    if st.button("← インタビューに戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    if st.session_state.get("rag_restore_error"):
        st.warning(
            f"※ 直前に読み込んだセッションのRAG資料（履歴書・企業情報）復元中にエラーが発生しました: "
            f"{st.session_state.rag_restore_error}"
        )

    _fav_count = count_favorites()
    _tab_history, _tab_favorites = st.tabs([
        "📋 面接セッション一覧",
        f"⭐ お気に入り（{_fav_count}件）",
    ])

    with _tab_history:
        st.write("過去に保存した面接セッションの一覧です。「開く」を押すとその内容を読み込んで続きから操作できます。")
        past_sessions = list_sessions()
        if not past_sessions:
            st.info("まだ保存された面接履歴はありません。サイドバーの「💾 現在のセッションを保存」から保存できます。")
        else:
            for s in past_sessions:
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
                    with col1:
                        status_icon = "✅ 完了" if s["interview_complete"] else "📝 進行中"
                        st.markdown(f"**{s['company_name'] or '（会社名未設定）'}** ・ {s['session_type'] or ''}")
                        _badge = " ・ 🎤 模擬面接結果あり" if s.get("has_mock_evaluation") else ""
                        st.caption(f"{status_icon} ・ 最終更新: {s['updated_at'][:16].replace('-', '/')}{_badge}")
                    with col2:
                        if st.button("開く", key=f"hist_open_{s['id']}", use_container_width=True):
                            load_session_from_db(st.session_state, s["id"])
                            st.session_state.current_session_id = s["id"]
                            st.session_state.current_company_name = s["company_name"]
                            st.session_state.app_mode = "interview"
                            st.success(f"セッション（ID: {s['id']}）を読み込みました。")
                            st.rerun()
                    with col3:
                        _is_fav = is_favorited("interview", item_id=s["id"], session_id=s["id"])
                        _fav_icon = "⭐" if _is_fav else "☆"
                        if st.button(_fav_icon, key=f"hist_fav_{s['id']}", use_container_width=True,
                                     help="お気に入りに追加/解除"):
                            if _is_fav:
                                remove_favorite_by_item("interview", item_id=s["id"], session_id=s["id"])
                            else:
                                add_favorite(
                                    item_type="interview",
                                    item_id=s["id"],
                                    session_id=s["id"],
                                    company_name=s.get("company_name"),
                                    session_type=s.get("session_type"),
                                    label=f"{s['company_name'] or '未設定'} ・ {s['session_type'] or ''}",
                                    content_snapshot={
                                        "status": "完了" if s["interview_complete"] else "進行中",
                                        "updated_at": s["updated_at"][:16],
                                    },
                                )
                            st.rerun()
                    with col4:
                        if st.button("削除", key=f"hist_delete_{s['id']}", use_container_width=True):
                            delete_session(s["id"])
                            if st.session_state.get("current_session_id") == s["id"]:
                                st.session_state.current_session_id = None
                            st.success(f"セッション（ID: {s['id']}）を削除しました。")
                            st.rerun()

    with _tab_favorites:
        st.write("「後で見返したいもの」を種類・会社・面接種別で絞り込んで確認できます。")

        _fav_companies = ["（すべて）"] + list_distinct_companies()
        _fav_stypes = ["（すべて）"] + list_distinct_session_types()
        _fav_item_types_options = ["（すべて）"] + list(ITEM_TYPE_LABELS.keys())
        _fav_item_type_labels = {"（すべて）": "（すべて）"} | ITEM_TYPE_LABELS

        _filter_cols = st.columns(3)
        with _filter_cols[0]:
            _sel_type = st.selectbox(
                "種類", options=_fav_item_types_options,
                format_func=lambda k: _fav_item_type_labels.get(k, k),
                key="fav_filter_type",
            )
        with _filter_cols[1]:
            _sel_company = st.selectbox("会社名", options=_fav_companies, key="fav_filter_company")
        with _filter_cols[2]:
            _sel_stype = st.selectbox("面接種別", options=_fav_stypes, key="fav_filter_stype")

        _filter_item_type = None if _sel_type == "（すべて）" else _sel_type
        _filter_company = None if _sel_company == "（すべて）" else _sel_company
        _filter_stype = None if _sel_stype == "（すべて）" else _sel_stype

        favorites = list_favorites(
            item_type=_filter_item_type,
            company_name=_filter_company,
            session_type=_filter_stype,
        )

        if not favorites:
            st.info(
                "お気に入りはまだありません。\n\n"
                "面接セッション一覧の ☆ ボタン、または各ページの ⭐ ボタンから追加できます。"
            )
        else:
            st.caption(f"{len(favorites)}件のお気に入り")
            for fav in favorites:
                with st.container(border=True):
                    _fcol1, _fcol2 = st.columns([5, 1])
                    with _fcol1:
                        _type_label = ITEM_TYPE_LABELS.get(fav["item_type"], fav["item_type"])
                        _company_str = fav.get("company_name") or ""
                        _stype_str = fav.get("session_type") or ""
                        _meta = " ・ ".join(filter(None, [_company_str, _stype_str]))
                        _label = fav.get("label") or _type_label
                        st.markdown(f"**{_type_label}**　{_label}")
                        if _meta:
                            st.caption(_meta)
                        _saved = fav.get("saved_at", "")
                        if _saved:
                            st.caption(f"保存日時: {_saved[:16].replace('-', '/')}")
                        _snap = fav.get("content_snapshot") or {}
                        _item_type = fav["item_type"]
                        if _item_type == "career_advice" and isinstance(_snap, dict):
                            _n = _snap.get("message_count", 0)
                            _snippet = _snap.get("last_snippet", "")
                            st.caption(f"メッセージ数: {_n}件" + (f" ／ 最後のメッセージ: 「{_snippet}…」" if _snippet else ""))
                        elif _item_type == "company_matrix" and isinstance(_snap, dict):
                            _cos = _snap.get("companies", [])
                            if _cos:
                                st.caption("比較企業: " + "・".join(_cos))
                        elif _item_type == "question_set" and isinstance(_snap, dict):
                            st.caption(f"質問数: {_snap.get('question_count', 0)}件")
                        elif _item_type == "interview" and isinstance(_snap, dict):
                            _status = _snap.get("status", "")
                            _upd = _snap.get("updated_at", "")
                            st.caption(f"ステータス: {_status}" + (f" ・ 最終更新: {_upd}" if _upd else ""))
                        elif _item_type == "personality" and isinstance(_snap, dict):
                            _summary = _snap.get("summary", "")
                            if _summary:
                                st.caption(_summary[:60] + ("…" if len(_summary) > 60 else ""))
                        if fav.get("session_id"):
                            if st.button("このセッションを開く", key=f"fav_open_session_{fav['id']}"):
                                _sid = fav["session_id"]
                                load_session_from_db(st.session_state, _sid)
                                st.session_state.current_session_id = _sid
                                st.session_state.current_company_name = fav.get("company_name") or ""
                                st.session_state.app_mode = "interview"
                                st.rerun()
                    with _fcol2:
                        if st.button("⭐ 解除", key=f"fav_remove_{fav['id']}", use_container_width=True):
                            remove_favorite(fav["id"])
                            st.rerun()
