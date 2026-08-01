"""
api/routes/knowledge_base.py
-----------------------------
ナレッジベース（履歴書・企業情報）の管理エンドポイント。

既存コードとの対応:
  rag/extraction.py   → extract_text_from_pdf / extract_text_from_image
  rag/persistence.py  → save_document_to_kb / load_active_documents
  rag/core.py         → search_balanced / format_context
  db/knowledge_base_repository.py → list/get/delete/get_or_create

GET    /                一覧（type フィルタ可）
POST   /text            テキスト貼り付けから新規作成
POST   /upload          ファイルアップロードから新規作成
GET    /{id}            詳細取得
DELETE /{id}            削除
PATCH  /{id}/active     アクティブ状態の切り替え
POST   /{id}/search     類似検索（RAGクエリ）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from db.knowledge_base_repository import (
    list_knowledge_bases,
    get_or_create_knowledge_base,
    delete_knowledge_base,
    get_knowledge_base,
    list_document_versions,
)
from rag.extraction import extract_text_from_pdf, extract_text_from_image
from rag.persistence import save_document_to_kb, load_active_documents, PROJECT_ROOT
from rag.core import search_balanced, format_context

from local_ai_core.documents import DocumentStore
from local_ai_core.permissions import PermissionDenied
from db.database import get_core_db_path
from core_sync import get_gate, get_profile_id

logger = logging.getLogger(__name__)
router = APIRouter()

APP_KEY = "interview_app"


def _sync_document_to_center(kb_id: int, document_id: int, name: str, kb_type: str) -> None:
    """アップロードされたファイルの「所在」を、全アプリ共通のドキュメントセンターに
    登録する。これまでdocuments:write/readはplugin_manifest.jsonで申告されていた
    だけで、実際に登録するコードがどこにも存在しなかった
    (career.*メモリー・life.*メモリーと同種の欠落を、ドキュメントセンターでも
    ここで初めて塞ぐ)。

    登録するのはファイルの絶対パスとメタデータのみで、ファイルの内容そのものは
    どこにもコピーしない(ドキュメントセンターの設計方針通り)。実体は
    このアプリの uploads/ 配下に元々あるものを指すだけ。

    memory:write:career.* 等と同様、documents:write が未許可でもアップロード
    機能自体は今まで通り使える(PermissionDeniedは静かに無視する)。
    """
    try:
        versions = list_document_versions(kb_id)
        match = next((v for v in versions if v["id"] == document_id), None)
        if match is None or not match.get("file_path"):
            return
        abs_path = str((PROJECT_ROOT / match["file_path"]).resolve())

        gate = get_gate()
        docs = DocumentStore(get_core_db_path(), gate=gate)
        docs.register(
            get_profile_id(), APP_KEY, abs_path, title=name,
            source_ref_id=f"kb:{kb_id}:doc:{document_id}",
            category=kb_type,  # "resume" or "company"
        )
    except PermissionDenied:
        pass
    except Exception:
        logger.exception("ドキュメントセンターへの同期に失敗(アップロード自体には影響なし)")


# ── ヘルパー: ファイル種別によるテキスト抽出 ─────────────────────

def _extract_text(content: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return extract_text_from_image(content)
    # .txt / その他はUTF-8デコードを試みる
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


# ── ヘルパー: KB の is_active を DB で更新 ───────────────────────

def _set_kb_active(kb_id: int, is_active: bool) -> None:
    from db.database import db_session
    with db_session() as conn:
        conn.execute(
            "UPDATE knowledge_bases SET is_active = ? WHERE id = ?",
            (int(is_active), kb_id),
        )


# ============================================================
# スキーマ
# ============================================================

class KBCreateTextRequest(BaseModel):
    name: str
    kb_type: str   # "resume" | "company"
    text: str


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 4


class ActiveToggleRequest(BaseModel):
    is_active: bool


# ============================================================
# 一覧
# ============================================================

@router.get("/")
async def get_knowledge_bases(kb_type: str | None = None) -> list[dict]:
    return list_knowledge_bases(kb_type=kb_type)


# ============================================================
# テキストから新規作成
# ============================================================

@router.post("/text", status_code=201)
async def create_from_text(req: KBCreateTextRequest) -> dict:
    if req.kb_type not in ("resume", "company"):
        raise HTTPException(status_code=400, detail="kb_type must be 'resume' or 'company'")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    kb_id = get_or_create_knowledge_base(req.name, req.kb_type)
    doc = save_document_to_kb(
        knowledge_base_id=kb_id,
        doc_type=req.kb_type,
        source_name=req.name,
        raw_text=req.text,
        raw_bytes=None,  # テキスト直接入力時は None → UTF-8 バイト列として保存される
    )
    if doc is None:
        raise HTTPException(status_code=422, detail="テキストからチャンクを作成できませんでした")

    _sync_document_to_center(kb_id, doc.document_id, req.name, req.kb_type)

    kb = get_knowledge_base(kb_id)
    return kb or {"id": kb_id, "name": req.name, "kb_type": req.kb_type}


# ============================================================
# ファイルアップロードから新規作成
# ============================================================

@router.post("/upload", status_code=201)
async def create_from_upload(
    name: str = Form(...),
    kb_type: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if kb_type not in ("resume", "company"):
        raise HTTPException(status_code=400, detail="kb_type must be 'resume' or 'company'")

    content = await file.read()
    filename = file.filename or "upload"

    text = _extract_text(content, filename)
    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="テキストを抽出できませんでした。PDF が画像のみの場合は OCR が必要です。",
        )

    kb_id = get_or_create_knowledge_base(name, kb_type)
    doc = save_document_to_kb(
        knowledge_base_id=kb_id,
        doc_type=kb_type,
        source_name=filename,
        raw_text=text,
        raw_bytes=content,
    )
    if doc is None:
        raise HTTPException(status_code=422, detail="テキストからチャンクを作成できませんでした")

    _sync_document_to_center(kb_id, doc.document_id, name, kb_type)

    kb = get_knowledge_base(kb_id)
    return kb or {"id": kb_id, "name": name, "kb_type": kb_type}


# ============================================================
# 詳細取得
# ============================================================

@router.get("/{kb_id}")
async def get_kb(kb_id: int) -> dict:
    kb = get_knowledge_base(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb


# ============================================================
# 削除
# ============================================================

@router.delete("/{kb_id}", status_code=204)
async def delete_kb(kb_id: int) -> None:
    if get_knowledge_base(kb_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    delete_knowledge_base(kb_id)


# ============================================================
# アクティブ状態の切り替え
# ============================================================

@router.patch("/{kb_id}/active")
async def toggle_active(kb_id: int, req: ActiveToggleRequest) -> dict:
    if get_knowledge_base(kb_id) is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    _set_kb_active(kb_id, req.is_active)
    return {"id": kb_id, "is_active": req.is_active}


# ============================================================
# 類似検索（RAGクエリ）
# ============================================================

@router.post("/{kb_id}/search")
async def search_kb(kb_id: int, req: KBSearchRequest) -> dict:
    documents = load_active_documents(knowledge_base_ids=[kb_id])
    if not documents:
        raise HTTPException(
            status_code=404,
            detail="このナレッジベースにドキュメントがありません",
        )
    results = search_balanced(
        query=req.query,
        documents=documents,
        top_k_per_type=req.top_k,
    )
    context = format_context(results)
    return {"context": context, "chunks": [
        {"text": text, "source": source, "score": float(score)}
        for text, source, score in results
    ]}
