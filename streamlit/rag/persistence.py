"""
rag/persistence.py
------------------
RAG ドキュメントの永続化（保存・読み込み）ロジック。

[永続化方針 v2]
- knowledge_bases / documents / document_chunks テーブル（db/database.py）に
  メタ情報・チャンクテキストを保存する。
- embeddingsはDBに直接入れず、document単位で1つの .npy ファイルとして
  rag_data/ ディレクトリに保存し、documents.embedding_path にパスのみ持たせる
  （shape: (n_chunks, dim) の2次元配列）。
- アップロードされたPDF原本は uploads/ ディレクトリに保存し、
  documents.file_path にパスを持たせる（履歴として複数バージョン保持）。

[v3: リポジトリ層への分離]
- 実際のDB読み書き（SQL）は db/knowledge_base_repository.py に委譲する。
- このファイルは「保存・読み込みのオーケストレーション」に専念する。

提供する関数（app.py 等から使う想定）:
    get_or_create_knowledge_base()  - kb_repo の薄いラッパー
    list_knowledge_bases()          - kb_repo の薄いラッパー
    save_document_to_kb()           - チャンク→埋め込み→DB保存を一括
    save_resume()                   - 「共通履歴書」KB への保存
    save_company_document()         - 会社名単位の KB への保存
    load_active_documents()         - アクティブな Document リストを復元
    list_document_versions()        - 過去バージョン含む一覧（メタ情報のみ）
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from db import knowledge_base_repository as kb_repo
from rag.core import Document, chunk_text, embed_texts

logger = logging.getLogger(__name__)

# このファイルからの相対パスでプロジェクトルートを指す
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RESUME_KB_NAME = "共通履歴書"  # 履歴書は企業に紐付かない、常に単一のグローバルKB


# ============================================================
# 永続化: knowledge_bases（kb_repo への薄いラッパー）
# ============================================================

get_or_create_knowledge_base = kb_repo.get_or_create_knowledge_base
list_knowledge_bases = kb_repo.list_knowledge_bases


# ============================================================
# 永続化: documents の保存
# ============================================================

def save_document_to_kb(
    knowledge_base_id: int,
    doc_type: str,
    source_name: str,
    raw_text: str,
    raw_bytes: bytes | None = None,
    deactivate_previous_versions: bool = True,
) -> Document | None:
    """生テキストをチャンク分割→埋め込み→永続化、を一括で行う。

    PDF・txt等、どのファイル形式から抽出されたテキストでも受け付ける
    （テキスト抽出自体は呼び出し側の責務とする）。

    Args:
        knowledge_base_id: 保存先のknowledge_bases.id
        doc_type: "resume" or "company"
        source_name: 元ファイル名（表示用）
        raw_text: 抽出済みの本文テキスト（PDFなら extract_text_from_pdf 済み、
            txtならデコード済みのもの）
        raw_bytes: 原本ファイルのバイト列。uploads/ に保存する対象。
            Noneの場合はテキストをUTF-8エンコードしたものを原本として保存する
            （例: テキストエリアへの直接貼り付けなど、元ファイルが存在しないケース）。
        deactivate_previous_versions: Trueの場合、同じknowledge_base内の
            既存document（is_active=1）をすべて is_active=0 にしてから
            今回のdocumentをversion+1・is_active=1で登録する。

    Returns:
        永続化されたDocument（embeddings込み）。チャンクが作れない場合はNone。
    """
    chunks = chunk_text(raw_text)
    if not chunks:
        return None

    embeddings = embed_texts(chunks)

    file_bytes_to_save = raw_bytes if raw_bytes is not None else raw_text.encode("utf-8")
    file_path: str | None = None
    embedding_path: str | None = None

    try:
        file_path = kb_repo.save_uploaded_file(knowledge_base_id, source_name, file_bytes_to_save)
        embedding_path = kb_repo.save_embedding_npy(embeddings)

        document_id = kb_repo.save_document(
            knowledge_base_id=knowledge_base_id,
            source_name=source_name,
            chunks=chunks,
            file_path=file_path,
            embedding_path=embedding_path,
            deactivate_previous_versions=deactivate_previous_versions,
        )
    except Exception:
        logger.error("ドキュメント保存失敗。一時ファイルをクリーンアップします", exc_info=True)
        for relative_path in (file_path, embedding_path):
            if not relative_path:
                continue
            try:
                (PROJECT_ROOT / relative_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise

    return Document(
        doc_type=doc_type,
        source_name=source_name,
        chunks=chunks,
        embeddings=embeddings,
        document_id=document_id,
    )


# ============================================================
# 永続化: 高レベルラッパー（app.py から使う想定）
# ============================================================

def save_resume(
    source_name: str, raw_text: str, raw_bytes: bytes | None = None
) -> tuple[Document | None, int]:
    """履歴書を「共通履歴書」KB（企業非依存・常に単一）に保存する。

    Args:
        source_name: 元ファイル名（表示用）
        raw_text: 抽出済み本文テキスト
        raw_bytes: 原本のバイト列（PDF等）。Noneならテキストをそのまま原本として保存。

    Returns:
        (Document, knowledge_base_id)。テキストが空などで保存できなかった場合は (None, kb_id)。
    """
    kb_id = kb_repo.get_or_create_knowledge_base(RESUME_KB_NAME, "resume")
    doc = save_document_to_kb(
        knowledge_base_id=kb_id,
        doc_type="resume",
        source_name=source_name,
        raw_text=raw_text,
        raw_bytes=raw_bytes,
    )
    return doc, kb_id


def save_company_document(
    company_name: str, source_name: str, raw_text: str, raw_bytes: bytes | None = None
) -> tuple[Document | None, int]:
    """企業情報を「会社名」単位のKBに保存する。

    会社名ごとにKBが自動的に作成・再利用される
    （例: 同じ「ソニー」で複数回アップロードしても同じKBのバージョンとして積み上がる）。

    Args:
        company_name: 会社名（必須。KB名として使われる）
        source_name: 元ファイル名（表示用）
        raw_text: 抽出済み本文テキスト
        raw_bytes: 原本のバイト列（PDF等）。Noneならテキストをそのまま原本として保存。

    Returns:
        (Document, knowledge_base_id)。テキストが空などで保存できなかった場合は (None, kb_id)。
    """
    kb_id = kb_repo.get_or_create_knowledge_base(company_name, "company")
    doc = save_document_to_kb(
        knowledge_base_id=kb_id,
        doc_type="company",
        source_name=source_name,
        raw_text=raw_text,
        raw_bytes=raw_bytes,
    )
    return doc, kb_id


# ============================================================
# 永続化: documents の読み込み
# ============================================================

def _load_document_row(doc_row: dict, kb_type: str) -> Document | None:
    """documentsテーブルの1行からDocumentを復元する（チャンク・embedding込み）。"""
    embedding_path = doc_row.get("embedding_path")
    if not embedding_path:
        return None

    full_embedding_path = PROJECT_ROOT / embedding_path
    if not full_embedding_path.exists():
        # ファイルが見つからない場合は壊れたレコードとして扱い、スキップする
        return None

    embeddings = np.load(full_embedding_path)

    chunk_rows = kb_repo.get_document_chunks(doc_row["id"])
    chunks = [r["chunk_text"] for r in chunk_rows]
    if len(chunks) != embeddings.shape[0]:
        # チャンク数とembedding行数が食い違う場合は不整合とみなしスキップする
        return None

    return Document(
        doc_type=kb_type,
        source_name=doc_row["source_name"],
        chunks=chunks,
        embeddings=embeddings,
        document_id=doc_row["id"],
    )


def load_active_documents(knowledge_base_ids: list[int]) -> list[Document]:
    """指定したknowledge_base群の「現在アクティブな」documentをDocumentリストとして読み込む。

    Args:
        knowledge_base_ids: 読み込み対象のknowledge_bases.idのリスト
            （例: 学生の共通履歴書KB + 今回の企業KB をまとめて渡す）

    Returns:
        search_balanced() にそのまま渡せる Document のリスト
    """
    if not knowledge_base_ids:
        return []

    documents: list[Document] = []
    for doc_row in kb_repo.list_active_documents(knowledge_base_ids):
        kb_type = doc_row.get("kb_type", "company")
        doc = _load_document_row(doc_row, kb_type)
        if doc is not None:
            documents.append(doc)

    return documents


def list_document_versions(knowledge_base_id: int) -> list[dict]:
    """指定knowledge_base内の全document（過去バージョン含む）を新しい順で返す。

    履歴の振り返り・バージョン切り替えUI向け。embeddingsは含まない（軽量なメタ情報のみ）。
    """
    return kb_repo.list_document_versions(knowledge_base_id)
