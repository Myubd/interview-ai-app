"""
components/sidebar/rag_panel.py
---------------------------------
履歴書・企業情報のアップロードと、過去保存済み資料の読み込みUIを描画する。
"""

import streamlit as st

from db.settings_repository import get_setting
from rag import (
    extract_text_from_pdf,
    extract_text_from_image,
    save_resume,
    save_company_document,
    load_active_documents,
    get_or_create_knowledge_base,
    list_knowledge_bases,
    RESUME_KB_NAME,
)

DEFAULT_EMBED_MODEL = "nomic-embed-text"
_IMAGE_EXTS = (".png", ".jpg", ".jpeg")
_OCR_LOW_TEXT_THRESHOLD = 30


def _extract_text_from_upload(file) -> str:
    """アップロードファイルの種類に応じてテキストを抽出する。"""
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


def render_rag_panel() -> None:
    """RAGパネル（履歴書・企業情報のアップロードと読み込み）を描画する。"""
    st.header("📎 参考資料（RAG）")
    embed_model = get_setting("embed_model", DEFAULT_EMBED_MODEL)
    st.caption(
        f"アップロードした内容は、質問の深掘りと最終的な自己PR生成の精度向上に使われます。"
        f"（埋め込みモデル: {embed_model}。事前に `ollama pull {embed_model}` が必要です）"
        f"\n\nここで読み込んだ資料はサーバー（ローカルDB）に保存され、次回以降も再利用できます。"
    )

    resume_file = st.file_uploader(
        "履歴書（PDF・画像（PNG/JPG）・テキスト）",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        key="resume_uploader",
    )

    st.caption("企業情報は「会社名」ごとに知識ベースとして保存されます。")
    rag_company_name = st.text_input("会社名（必須）", key="rag_company_name_input")
    company_file = st.file_uploader(
        "企業情報（PDF・画像（PNG/JPG）・テキスト）",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        key="company_uploader",
    )
    company_text_input = st.text_area("企業情報を直接貼り付け（任意）", height=100)

    if st.button("📚 資料を読み込む / 更新する"):
        st.session_state.rag_documents = []
        errors = []

        with st.spinner("資料を解析し、埋め込みベクトルを作成・保存中..."):
            try:
                errors += _process_resume(resume_file)
                errors += _process_company(company_file, company_text_input, rag_company_name)
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

    _render_loaded_docs()
    _render_existing_kb_loader()


def _process_resume(resume_file) -> list[str]:
    """履歴書ファイルを処理してRAGドキュメントに追加する。エラーメッセージのリストを返す。"""
    errors = []
    if resume_file is None:
        return errors

    resume_file.seek(0)
    resume_raw_bytes = resume_file.read()
    resume_file.seek(0)
    resume_text = _extract_text_from_upload(resume_file)

    if resume_text:
        doc, _ = save_resume(
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
    return errors


def _process_company(company_file, company_text_input: str, rag_company_name: str) -> list[str]:
    """企業情報ファイル・テキストを処理してRAGドキュメントに追加する。エラーメッセージのリストを返す。"""
    errors = []
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

    if not company_raw.strip():
        return errors

    if not rag_company_name.strip():
        errors.append("企業情報を保存するには「会社名」の入力が必須です。")
        return errors

    doc, _ = save_company_document(
        company_name=rag_company_name.strip(),
        source_name=company_source_name,
        raw_text=company_raw,
        raw_bytes=company_raw_bytes,
    )
    if doc:
        st.session_state.rag_documents.append(doc)
        st.session_state.current_company_name = rag_company_name.strip()
        if company_image_text_len is not None and company_image_text_len < _OCR_LOW_TEXT_THRESHOLD:
            errors.append(
                f"⚠️ 企業情報画像から読み取れた文字数が少なめです"
                f"（{company_image_text_len}文字）。"
                "OCRが正しく読み取れていない可能性があるため、"
                "内容が反映されているかご確認ください。"
            )
    else:
        errors.append("企業情報からテキストを抽出できませんでした。")
    return errors


def _render_loaded_docs() -> None:
    """今回のセッションで読み込み済みの資料を一覧表示する。"""
    if st.session_state.get("rag_documents"):
        st.caption("📄 読み込み済み資料（今回のセッション）:")
        for doc in st.session_state.rag_documents:
            label = "履歴書" if doc.doc_type == "resume" else "企業情報"
            st.caption(f"・[{label}] {doc.source_name}（{len(doc.chunks)}チャンク）")


def _render_existing_kb_loader() -> None:
    """過去に保存した企業情報KBを選択して読み込むUIを描画する。"""
    company_kbs = list_knowledge_bases(kb_type="company")
    if not company_kbs:
        return

    st.caption("📚 過去に保存した企業情報を読み込む:")
    kb_options = {kb["name"]: kb["id"] for kb in company_kbs}
    selected_kb_name = st.selectbox(
        "企業を選択",
        options=["（選択してください）"] + list(kb_options.keys()),
        key="existing_kb_selector",
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
