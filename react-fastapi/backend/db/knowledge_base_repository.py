# -*- coding: utf-8 -*-
"""
db/knowledge_base_repository.py
---------------------------------
knowledge_bases / documents / document_chunks テーブルに対するCRUD処理を担うリポジトリ。

[元 rag.py からの分離について]
rag.py にあった「永続化: knowledge_bases」「永続化: documents の保存」
「永続化: documents の読み込み」セクションの関数をここに移植した。
チャンク分割・埋め込み生成・類似検索などの純粋なRAGロジック
（chunk_text, embed_texts, search_balanced 等）や Document データクラスは
rag.py 側に残し、このモジュールはDBとファイル（rag_data/, uploads/）への
読み書きのみを担当する。

embeddingの実体（.npy）やアップロード原本ファイルの読み書きは、
documentsテーブルの file_path / embedding_path 列と密接に関わるため、
ここに含めている。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np

from db.database import db_session

try:
    from core_sync.knowledge_sync import sync_company_knowledge_base
except ImportError:  # pragma: no cover - core_sync未導入環境でも本体機能は動くようにする
    sync_company_knowledge_base = None  # type: ignore[assignment]

# このファイル（db/knowledge_base_repository.py）から見て1階層上（プロジェクトルート）を指す
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAG_DATA_DIR = PROJECT_ROOT / "rag_data"
UPLOADS_DIR = PROJECT_ROOT / "uploads"


# ============================================================
# knowledge_bases
# ============================================================

def get_or_create_knowledge_base(name: str, kb_type: str) -> int:
    """同名・同typeのknowledge_baseがあればそのidを返し、なければ新規作成する。

    Args:
        name: 知識ベースの表示名（例: "ソニー", "共通履歴書"）
        kb_type: "resume" or "company"

    Returns:
        knowledge_bases.id
    """
    with db_session() as conn:
        row = conn.execute(
            "SELECT id FROM knowledge_bases WHERE name = ? AND kb_type = ?",
            (name, kb_type),
        ).fetchone()
        if row is not None:
            kb_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO knowledge_bases (name, kb_type) VALUES (?, ?)",
                (name, kb_type),
            )
            kb_id = cur.lastrowid

    # 企業研究ノートは、他アプリからも参照できるよう共通台帳(knowledge_items)にも
    # 要約を反映する。ユーザーが許可していなければ core_sync 側で静かにスキップされる。
    if kb_type == "company" and sync_company_knowledge_base is not None:
        try:
            sync_company_knowledge_base(kb_id, name)
        except Exception:  # pragma: no cover - 共通台帳同期の失敗で本体機能を止めない
            pass

    return kb_id


def list_knowledge_bases(kb_type: str | None = None) -> list[dict]:
    """knowledge_baseの一覧を返す（新しい順）。

    Args:
        kb_type: "resume" / "company" で絞り込む。Noneなら全件。
    """
    with db_session() as conn:
        if kb_type is None:
            rows = conn.execute(
                "SELECT * FROM knowledge_bases ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM knowledge_bases WHERE kb_type = ? ORDER BY created_at DESC",
                (kb_type,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_knowledge_base(knowledge_base_id: int) -> dict | None:
    """knowledge_base 1件を返す。見つからない場合はNone。"""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM knowledge_bases WHERE id = ?", (knowledge_base_id,)
        ).fetchone()
        return dict(row) if row is not None else None


def delete_knowledge_base(knowledge_base_id: int) -> None:
    """knowledge_baseを削除する（documents, document_chunksもCASCADEで連動削除される）。

    注意: documents.file_path / embedding_path が指す実ファイル（uploads/, rag_data/）は
    このリポジトリの責務外であり、削除されない。必要であれば呼び出し側で
    list_document_versions() 等を使って事前にファイルパスを回収してから削除すること。
    """
    with db_session() as conn:
        conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (knowledge_base_id,))


# ============================================================
# documents の保存
# ============================================================

def save_embedding_npy(embeddings: np.ndarray) -> str:
    """embeddings配列を rag_data/ に一意なファイル名で保存し、相対パス文字列を返す。"""
    RAG_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.npy"
    full_path = RAG_DATA_DIR / filename
    np.save(full_path, embeddings)
    # DBにはプロジェクトルートからの相対パスを保存する（環境間の可搬性のため）
    return str(full_path.relative_to(PROJECT_ROOT))


def save_uploaded_file(knowledge_base_id: int, source_name: str, file_bytes: bytes) -> str:
    """アップロードされたファイル原本（PDF or テキスト等）を uploads/ に保存し、相対パス文字列を返す。

    ファイル名衝突を避けるため、knowledge_base_id と一意なuuidをファイル名に含める。
    元の拡張子がない場合（例: 貼り付けテキストの保存）は .txt を使う。
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_suffix = Path(source_name).suffix or ".txt"
    filename = f"kb{knowledge_base_id}_{uuid.uuid4().hex}{safe_suffix}"
    full_path = UPLOADS_DIR / filename
    full_path.write_bytes(file_bytes)
    return str(full_path.relative_to(PROJECT_ROOT))


def save_document(
    knowledge_base_id: int,
    source_name: str,
    chunks: list[str],
    file_path: str | None,
    embedding_path: str | None,
    deactivate_previous_versions: bool = True,
) -> int:
    """documents 1行 + document_chunks 複数行を保存する。

    Args:
        knowledge_base_id: 保存先のknowledge_bases.id
        source_name: 元ファイル名（表示用）
        chunks: チャンク分割済みテキストのリスト（document_chunksに1行ずつ保存される）
        file_path: 原本ファイルの相対パス（save_uploaded_fileの戻り値）
        embedding_path: embeddingの.npyファイルの相対パス（save_embedding_npyの戻り値）
        deactivate_previous_versions: Trueの場合、同じknowledge_base内の
            既存document（is_active=1）をすべて is_active=0 にしてから
            今回のdocumentをversion+1・is_active=1で登録する
            （= 「最低限の履歴を持つ」設計: 古いバージョンはDB/ファイルに残るが、
            RAG検索や表示ではis_active=1のものだけを使う）

    Returns:
        作成された documents.id
    """
    with db_session() as conn:
        if deactivate_previous_versions:
            conn.execute(
                "UPDATE documents SET is_active = 0 WHERE knowledge_base_id = ?",
                (knowledge_base_id,),
            )
            prev_max = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS max_v FROM documents WHERE knowledge_base_id = ?",
                (knowledge_base_id,),
            ).fetchone()
            next_version = prev_max["max_v"] + 1
        else:
            next_version = 1

        cur = conn.execute(
            """
            INSERT INTO documents
                (knowledge_base_id, source_name, file_path, version, is_active, embedding_path)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (knowledge_base_id, source_name, file_path, next_version, embedding_path),
        )
        document_id = cur.lastrowid

        for idx, chunk in enumerate(chunks):
            conn.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text)
                VALUES (?, ?, ?)
                """,
                (document_id, idx, chunk),
            )

    return document_id


# ============================================================
# documents の読み込み
# ============================================================

def get_document_chunks(document_id: int) -> list[dict]:
    """指定document_idのチャンクをchunk_index昇順で返す。"""
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT chunk_index, chunk_text FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_active_documents(knowledge_base_ids: list[int]) -> list[dict]:
    """指定したknowledge_base群の「現在アクティブな」document行を返す。

    Args:
        knowledge_base_ids: 対象のknowledge_bases.idのリスト

    Returns:
        documentsテーブルの行（dict）のリスト。各行にkb_typeも付与して返す。
    """
    if not knowledge_base_ids:
        return []

    with db_session() as conn:
        placeholders = ",".join("?" for _ in knowledge_base_ids)
        kb_rows = conn.execute(
            f"SELECT id, kb_type FROM knowledge_bases WHERE id IN ({placeholders})",
            knowledge_base_ids,
        ).fetchall()
        kb_type_by_id = {r["id"]: r["kb_type"] for r in kb_rows}

        doc_rows = conn.execute(
            f"""
            SELECT * FROM documents
            WHERE knowledge_base_id IN ({placeholders}) AND is_active = 1
            """,
            knowledge_base_ids,
        ).fetchall()
        doc_rows = [dict(r) for r in doc_rows]

    for doc_row in doc_rows:
        doc_row["kb_type"] = kb_type_by_id.get(doc_row["knowledge_base_id"], "company")

    return doc_rows


def list_document_versions(knowledge_base_id: int) -> list[dict]:
    """指定knowledge_base内の全document（過去バージョン含む）を新しい順で返す。

    履歴の振り返り・バージョン切り替えUI向け。embeddingsは含まない（軽量なメタ情報のみ）。
    """
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, source_name, file_path, version, is_active, created_at
            FROM documents
            WHERE knowledge_base_id = ?
            ORDER BY version DESC
            """,
            (knowledge_base_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_document(document_id: int) -> None:
    """documentを削除する（document_chunksもCASCADEで連動削除される）。

    注意: file_path / embedding_path が指す実ファイルは削除されない
    （呼び出し側で必要なら別途unlinkすること）。
    """
    with db_session() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


__all__ = [
    "PROJECT_ROOT",
    "RAG_DATA_DIR",
    "UPLOADS_DIR",
    "get_or_create_knowledge_base",
    "list_knowledge_bases",
    "get_knowledge_base",
    "delete_knowledge_base",
    "save_embedding_npy",
    "save_uploaded_file",
    "save_document",
    "get_document_chunks",
    "list_active_documents",
    "list_document_versions",
    "delete_document",
]
