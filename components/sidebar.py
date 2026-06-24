"""
components/sidebar.py
サイドバー全体（ナビゲーション・設定・RAGパネル・セッション保存パネル）を描画する。
呼び出し側は `from components.sidebar import render_sidebar` して
`model_name = render_sidebar()` のように使う。
"""

import streamlit as st

from db.settings_repository import get_setting, set_setting
from interview_engine import MAX_QUESTIONS_PER_THEME
from session_io import (
    serialize_session, make_filename,
    save_session_to_db, list_sessions,
    export_session_as_json, import_json_as_session,
)
from favorites import (
    add_favorite,
    is_favorited,
    build_auto_save_snapshot,
)
from rag import (
    Document,
    extract_text_from_pdf, extract_text_from_image, format_context,
    save_resume, save_company_document, load_active_documents,
    get_or_create_knowledge_base, list_knowledge_bases, RESUME_KB_NAME,
)
from utils import APP_VERSION

DEFAULT_CHAT_MODEL = "qwen3:8b"
DEFAULT_EMBED_MODEL = "nomic-embed-text"


def render_sidebar() -> str:
    """
    サイドバーを描画し、選択されたモデル名を返す。
    ナビゲーションのクリックは st.session_state.app_mode を直接書き換える。
    """
    with st.sidebar:
        st.caption(f"ver {APP_VERSION}")
        _render_warning_banner()
        _render_navigation()
        st.write("---")
        model_name = _render_settings()
        st.write("---")
        _render_rag_panel()
        _render_session_panel(model_name)

    return model_name


# ──────────────────────────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────────────────────────

def _render_warning_banner():
    st.markdown(
        "━━━━━━━━━━━━━━━━  \n"
        "⚠️ **ご利用上の注意**  \n"
        "ブラウザの自動翻訳機能をご利用の場合、文字表示やAIの応答に問題が発生する場合があります。"
        "翻訳をオフにするか「原文を表示」でご利用ください。  \n"
        "━━━━━━━━━━━━━━━━"
    )


def _render_navigation():
    st.subheader("サイドバー")

    _nav_items = [
        ("📄", "自己PR作成", "interview"),
        ("🤖", "AIキャリアアドバイザー", "career_advisor"),
        ("📊", "性格診断", "personality"),
        ("🎯", "想定質問生成", "predict_questions"),
        ("🎤", "AI模擬面接", "mock_interview"),
        ("🏢", "企業比較マトリクス", "company_matrix"),
        ("✅", "面接履歴", "history"),
    ]
    for _icon, _label, _mode in _nav_items:
        _is_current = st.session_state.app_mode == _mode
        _button_label = f"{_icon} {_label}" + ("　◀" if _is_current else "")
        if st.button(
            _button_label,
            key=f"nav_{_mode}",
            use_container_width=True,
            type="primary" if _is_current else "secondary",
        ):
            if _mode == "personality":
                st.session_state.app_mode = "personality"
                st.session_state.pa_answers = {}
                st.session_state.pa_current_q = 0
                st.session_state.pa_result = None
                st.session_state.pa_axis_scores = None
                st.session_state.pa_error = None
            elif _mode == "mock_interview":
                st.session_state.app_mode = "mock_interview"
                st.session_state.mock_messages = []
                st.session_state.mock_theme_index = 0
                st.session_state.mock_theme_messages = []
                st.session_state.mock_followups_asked = 0
                st.session_state.mock_started = False
                st.session_state.mock_complete = False
                st.session_state.mock_used_predicted_indices = set()
                st.session_state.mock_evaluation = None
                st.session_state.mock_evaluation_error = None
                st.session_state.mock_is_generating = False
                st.session_state.mock_answer_reviews = {}
                st.session_state.mock_review_generating_for = None
                st.session_state.mock_persona_confirmed = False
                # ペルソナはリセットせず前回の選択を引き継ぐ
            else:
                st.session_state.app_mode = _mode
            st.rerun()


def _render_settings() -> str:
    st.header("⚙️ 設定")

    saved_model = get_setting("chat_model", DEFAULT_CHAT_MODEL)
    model_name = st.text_input("Ollamaチャットモデル名", value=saved_model)
    if model_name and model_name != saved_model:
        set_setting("chat_model", model_name)
    st.caption("例: qwen3:8b / qwen3:4b / gpt-oss:20b")

    saved_embed = get_setting("embed_model", DEFAULT_EMBED_MODEL)
    embed_model = st.text_input("Ollama埋め込みモデル名", value=saved_embed)
    if embed_model and embed_model != saved_embed:
        set_setting("embed_model", embed_model)
    st.caption("例: nomic-embed-text / mxbai-embed-large")

    st.caption(
        f"質問はテーマごとに、直前の回答を踏まえてAIがその場で生成します"
        f"（1テーマあたり最大{MAX_QUESTIONS_PER_THEME}問まで自動で深掘りします）。"
    )
    return model_name or DEFAULT_CHAT_MODEL


def _render_rag_panel():
    st.header("📎 参考資料（RAG）")
    embed_model = get_setting("embed_model", DEFAULT_EMBED_MODEL)
    st.caption(
        f"アップロードした内容は、質問の深掘りと最終的な自己PR生成の精度向上に使われます。"
        f"（埋め込みモデル: {embed_model}。事前に `ollama pull {embed_model}` が必要です）"
        f"\n\nここで読み込んだ資料はサーバー（ローカルDB）に保存され、次回以降も再利用できます。"
    )

    resume_file = st.file_uploader(
        "履歴書（PDF・画像（PNG/JPG）・テキスト）", type=["pdf", "png", "jpg", "jpeg", "txt"], key="resume_uploader"
    )

    st.caption("企業情報は「会社名」ごとに知識ベースとして保存されます。")
    rag_company_name = st.text_input("会社名（必須）", key="rag_company_name_input")
    company_file = st.file_uploader(
        "企業情報（PDF・画像（PNG/JPG）・テキスト）", type=["pdf", "png", "jpg", "jpeg", "txt"], key="company_uploader"
    )
    company_text_input = st.text_area("企業情報を直接貼り付け（任意）", height=100)

    if st.button("📚 資料を読み込む / 更新する"):
        st.session_state.rag_documents = []
        errors = []

        _IMAGE_EXTS = (".png", ".jpg", ".jpeg")
        _OCR_LOW_TEXT_THRESHOLD = 30

        def _extract_text_from_upload(file) -> str:
            if file is None:
                return ""
            name_lower = file.name.lower()
            file_bytes = file.read()
            if name_lower.endswith(".pdf"):
                return extract_text_from_pdf(file_bytes)
            if name_lower.endswith(_IMAGE_EXTS):
                return extract_text_from_image(file_bytes)
            for encoding in ("utf-8", "cp932", "shift_jis", "euc_jp"):
                try:
                    return file_bytes.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    continue
            return file_bytes.decode("utf-8", errors="ignore")

        with st.spinner("資料を解析し、埋め込みベクトルを作成・保存中..."):
            try:
                if resume_file is not None:
                    resume_file.seek(0)
                    resume_raw_bytes = resume_file.read()
                    resume_file.seek(0)
                    resume_text = _extract_text_from_upload(resume_file)

                    if resume_text:
                        doc, _resume_kb_id = save_resume(
                            source_name=resume_file.name,
                            raw_text=resume_text,
                            raw_bytes=resume_raw_bytes,
                        )
                        if doc:
                            st.session_state.rag_documents.append(doc)
                            is_image = resume_file.name.lower().endswith(_IMAGE_EXTS)
                            if is_image and len(resume_text.strip()) < _OCR_LOW_TEXT_THRESHOLD:
                                errors.append(
                                    f"⚠️ 履歴書画像から読み取れた文字数が少なめです"
                                    f"（{len(resume_text.strip())}文字）。"
                                    "OCRが正しく読み取れていない可能性があるため、"
                                    "内容が反映されているかご確認ください。"
                                )
                        else:
                            errors.append("履歴書からテキストを抽出できませんでした（スキャンPDFの可能性があります）。")
                    else:
                        is_image = resume_file.name.lower().endswith(_IMAGE_EXTS)
                        if is_image:
                            errors.append(
                                "履歴書画像からテキストを読み取れませんでした。"
                                "Tesseract OCRが正しくインストールされているか、画像が鮮明かご確認ください。"
                            )
                        else:
                            errors.append("履歴書ファイルの読み込みに失敗しました。")

                company_raw = ""
                company_raw_bytes = None
                company_source_name = "貼り付けテキスト"
                company_image_text_len: int | None = None
                if company_file is not None:
                    company_file.seek(0)
                    company_raw_bytes = company_file.read()
                    company_file.seek(0)
                    company_file_text = _extract_text_from_upload(company_file)
                    if company_file.name.lower().endswith(_IMAGE_EXTS):
                        company_image_text_len = len(company_file_text.strip())
                    company_raw += company_file_text + "\n"
                    company_source_name = company_file.name
                if company_text_input.strip():
                    company_raw += company_text_input.strip()

                if company_raw.strip():
                    if not rag_company_name.strip():
                        errors.append("企業情報を保存するには「会社名」の入力が必須です。")
                    else:
                        doc, _company_kb_id = save_company_document(
                            company_name=rag_company_name.strip(),
                            source_name=company_source_name,
                            raw_text=company_raw,
                            raw_bytes=company_raw_bytes,
                        )
                        if doc:
                            st.session_state.rag_documents.append(doc)
                            st.session_state.current_company_name = rag_company_name.strip()
                            if (
                                company_image_text_len is not None
                                and company_image_text_len < _OCR_LOW_TEXT_THRESHOLD
                            ):
                                errors.append(
                                    f"⚠️ 企業情報画像から読み取れた文字数が少なめです"
                                    f"（{company_image_text_len}文字）。"
                                    "OCRが正しく読み取れていない可能性があるため、"
                                    "内容が反映されているかご確認ください。"
                                )
                        else:
                            errors.append("企業情報からテキストを抽出できませんでした。")
            except Exception as e:
                current_embed = get_setting("embed_model", DEFAULT_EMBED_MODEL)
                errors.append(
                    f"埋め込み処理でエラーが発生しました。Ollamaが起動しているか、"
                    f"埋め込みモデル「{current_embed}」が取得済みかご確認ください。詳細: {e}"
                )

        for err in errors:
            st.warning(err)
        if st.session_state.get("rag_documents"):
            st.success(f"{len(st.session_state.rag_documents)}件の資料を読み込み・保存しました。")

    if st.session_state.get("rag_documents"):
        st.caption("📄 読み込み済み資料（今回のセッション）:")
        for doc in st.session_state.rag_documents:
            label = "履歴書" if doc.doc_type == "resume" else "企業情報"
            st.caption(f"・[{label}] {doc.source_name}（{len(doc.chunks)}チャンク）")

    company_kbs = list_knowledge_bases(kb_type="company")
    if company_kbs:
        st.caption("📚 過去に保存した企業情報を読み込む:")
        kb_options = {kb["name"]: kb["id"] for kb in company_kbs}
        selected_kb_name = st.selectbox(
            "企業を選択", options=["（選択してください）"] + list(kb_options.keys()), key="existing_kb_selector"
        )
        if selected_kb_name != "（選択してください）":
            if st.button("📂 この企業の資料を読み込む", use_container_width=True):
                resume_kb_id = get_or_create_knowledge_base(RESUME_KB_NAME, "resume")
                company_kb_id = kb_options[selected_kb_name]
                loaded_docs = load_active_documents([resume_kb_id, company_kb_id])
                if loaded_docs:
                    st.session_state.rag_documents = loaded_docs
                    st.session_state.current_company_name = selected_kb_name
                    st.success(f"「{selected_kb_name}」の資料（{len(loaded_docs)}件）を読み込みました。")
                    st.rerun()
                else:
                    st.warning("保存済みの資料が見つかりませんでした。")


def _render_session_panel(model_name: str):
    st.write("---")
    st.header("💾 現在のセッションを保存")
    st.caption(
        "面接内容・自己PR・診断結果はこのPC内のデータベース（SQLite）に保存されます。"
        "外部サーバーへの送信は一切行いません。過去の履歴は「面接履歴」ページから確認できます。"
    )

    _save_messages_count = len(st.session_state.get("messages") or [])
    _save_has_pr = bool(st.session_state.get("final_pr"))
    _save_has_summary = bool(st.session_state.get("interview_summary"))
    _save_has_predicted_q = bool(st.session_state.get("predicted_questions"))
    _save_has_company_prs = bool(st.session_state.get("company_prs"))
    _save_has_personality = bool(st.session_state.get("pa_result"))
    _save_has_mock_eval = bool(st.session_state.get("mock_evaluation"))

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
        "会社名", value=st.session_state.get("current_company_name", ""), key="session_save_company_name"
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

    st.write("---")
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
          st.session_state.current_session_id = None  # 古いIDをリセット
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

    restore_file = st.file_uploader("📂 JSONファイルから面接履歴を取り込む", type=["json"], key="session_restore_uploader")
    if restore_file is not None:
        if st.button("✅ このファイルを新しいセッションとして取り込む", use_container_width=True):
            new_session_id, err = import_json_as_session(restore_file.read())
            if err:
                st.error(f"読み込みに失敗しました: {err}")
            else:
                st.success(f"セッションを取り込みました（新しいID: {new_session_id}）。一覧から開いてください。")
                st.rerun()

    st.write("---")
    if st.button("🔄 最初からやり直す（未保存の内容は消えます）"):
        st.session_state.clear()
        st.rerun()
