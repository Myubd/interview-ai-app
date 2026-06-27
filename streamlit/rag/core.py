"""
rag/core.py
-----------
RAG の中核ロジック。

提供するもの:
    Document           - RAG対象の1文書を表すデータクラス
    chunk_text()       - テキストをオーバーラップありで分割
    embed_texts()      - 複数テキストをOllamaで並列ベクトル化
    build_document()   - テキスト → Document（チャンク分割＋埋め込み）
    search_balanced()  - resume/company 別々にtop_kを取る偏りのない類似検索
    build_query_from_student_answers() - 会話履歴から学生発言のみ抽出
    format_context()   - 検索結果をプロンプト注入用テキストに整形

永続化（DB読み書き）は rag/persistence.py に分離している。
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

import numpy as np
import ollama

from db.settings_repository import get_setting

# Docker / 環境変数でOllamaホストを切り替える（utils/ollama_client.py と同じパターン）
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)

logger = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 400        # 1チャンクあたりの目安文字数
CHUNK_OVERLAP = 80      # チャンク間のオーバーラップ文字数
TOP_K = 4               # 検索時に取得する上位チャンク数


# ============================================================
# データクラス
# ============================================================

@dataclass
class Document:
    """RAG対象の1文書（履歴書 or 企業情報）を表す"""
    doc_type: str          # "resume" or "company"
    source_name: str       # ファイル名や識別用ラベル
    chunks: list[str] = field(default_factory=list)
    embeddings: np.ndarray | None = None  # shape: (n_chunks, dim)
    document_id: int | None = None  # DB(documents.id)と紐付ける場合に設定。新規未保存ならNone


# ============================================================
# チャンク分割
# ============================================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """テキストを一定文字数ごとに重複ありで分割する。

    日本語は単語区切りが曖昧なため、句読点・改行を優先した素朴な分割にする。
    """
    text = re.sub(r"\n{2,}", "\n", text.strip())
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # 句読点や改行の位置でできるだけ綺麗に切る
        if end < len(text):
            cut_candidates = [text.rfind(c, start, end) for c in "。\n、"]
            best_cut = max(cut_candidates)
            if best_cut > start + chunk_size // 2:
                end = best_cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end - overlap > start else end
    return chunks


# ============================================================
# 埋め込み生成
# ============================================================

def embed_texts(texts: list[str]) -> np.ndarray:
    """複数テキストをまとめて埋め込みベクトル化する。失敗時は例外を呼び出し元に伝播する。

    埋め込みモデルは settings テーブルの "embed_model" キーから取得し、
    未設定の場合は EMBED_MODEL（デフォルト値）にフォールバックする。

    Ollama の埋め込みAPIはバッチ処理に対応していないため、
    ThreadPoolExecutor を使って並列呼び出しを行い、登録時間を短縮する。
    並列数は Ollama がローカルで処理できる現実的な上限として 4 に固定。

    複数スレッドが同時に失敗した場合、全エラーを収集して最後にまとめてスローする。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    model = get_setting("embed_model", EMBED_MODEL)

    def _embed_one(idx_text: tuple[int, str]) -> tuple[int, list]:
        idx, text = idx_text
        res = _ollama_client.embeddings(model=model, prompt=text)
        return idx, res["embedding"]

    MAX_WORKERS = 4
    results: list[list | None] = [None] * len(texts)
    errors: list[tuple[int, Exception]] = []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(texts))) as executor:
        futures = {executor.submit(_embed_one, (i, t)): i for i, t in enumerate(texts)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                _, vec = future.result()
                results[idx] = vec
            except Exception as e:
                errors.append((idx, e))

    if errors:
        detail = "; ".join(f"chunk[{i}]: {e}" for i, e in sorted(errors))
        raise RuntimeError(f"埋め込み生成に失敗したチャンクがあります: {detail}")

    return np.array(results, dtype=np.float32)


def build_document(doc_type: str, source_name: str, raw_text: str) -> Document | None:
    """生テキストからDocumentを構築（チャンク分割＋埋め込み）する。テキストが空ならNone。"""
    chunks = chunk_text(raw_text)
    if not chunks:
        return None
    embeddings = embed_texts(chunks)
    return Document(doc_type=doc_type, source_name=source_name, chunks=chunks, embeddings=embeddings)


# ============================================================
# 類似検索
# ============================================================

def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
    return matrix_norm @ query_norm


# セッション内の埋め込みクエリキャッシュ（同一クエリへのOllama呼び出しを省略）
# { (model_name, query_text): np.ndarray } の形式で保持する。
# プロセスが生きている間（Streamlitセッション単位）のみ有効。
_QUERY_EMBED_CACHE: dict[tuple[str, str], np.ndarray] = {}


def _get_query_embedding(query: str) -> np.ndarray:
    """クエリ文字列の埋め込みベクトルを返す。同一クエリはキャッシュから返す。"""
    model = get_setting("embed_model", EMBED_MODEL)
    cache_key = (model, query)
    if cache_key not in _QUERY_EMBED_CACHE:
        _QUERY_EMBED_CACHE[cache_key] = np.array(
            _ollama_client.embeddings(model=model, prompt=query)["embedding"], dtype=np.float32
        )
    return _QUERY_EMBED_CACHE[cache_key]


def search_balanced(
    query: str, documents: list[Document], top_k_per_type: int = TOP_K
) -> list[tuple[str, str, float]]:
    """resume/companyそれぞれの文書群から個別にtop_kを取る、偏りのない検索。

    [v2で旧 search() を削除]
    以前は resume/company を区別せず全文書を横断して一つのランキングにする
    search() も存在したが、片方の文書種別（例えば学生の回答内容と意味的に
    近い「履歴書」）ばかりが上位を占め、もう片方（「企業情報」）が一件も
    結果に含まれないことがあるという既知の問題があった。
    呼び出し元（app.py）は実際には常にこの search_balanced() のみを使っており、
    search() はどこからも呼ばれていない未使用コードであり、かつ将来誤って
    呼び出された場合に上記の偏りが再発するリスクがあったため削除した。
    自己PR生成では「履歴書の実績」と「企業の特徴」の両方を反映したいため、
    doc_type ごとに個別にtop_kを取り、両方が必ず一定数含まれるようにする。

    Returns: [(doc_type, chunk_text, score), ...]  doc_typeごとにscore降順でまとめたもの
    """
    if not documents:
        return []

    query_vec = _get_query_embedding(query)

    results_by_type: dict[str, list[tuple[str, str, float]]] = {}
    for doc in documents:
        if doc.embeddings is None or len(doc.chunks) == 0:
            continue
        sims = _cosine_similarity(query_vec, doc.embeddings)
        bucket = results_by_type.setdefault(doc.doc_type, [])
        for chunk, score in zip(doc.chunks, sims):
            bucket.append((doc.doc_type, chunk, float(score)))

    merged: list[tuple[str, str, float]] = []
    for doc_type, items in results_by_type.items():
        items.sort(key=lambda x: x[2], reverse=True)
        merged.extend(items[:top_k_per_type])
    return merged


# ============================================================
# クエリ・コンテキスト整形
# ============================================================

def build_query_from_student_answers(conversation_history: str) -> str:
    """会話履歴から「学生:」発言だけを抜き出し、検索クエリとして整形する。

    会話履歴をそのまま埋め込みクエリにすると、面接官の質問文（定型的な
    言い回しが多く、履歴書・企業情報の内容とは意味的に遠い）が混ざって
    ベクトルが薄まり、類似検索の精度が下がりやすい。学生自身の発言
    （エピソードの内容そのもの）だけを残すことで、検索精度を上げる。

    学生の発言が見つからない場合は、フォールバックとして元の文字列を返す。
    """
    lines = []
    for line in conversation_history.splitlines():
        line = line.strip()
        if line.startswith("学生:"):
            content = line[len("学生:"):].strip()
            if content:
                lines.append(content)
    extracted = "\n".join(lines)
    return extracted if extracted else conversation_history


def format_context(results: list[tuple[str, str, float]]) -> str:
    """検索結果をプロンプト注入用のテキストに整形する。"""
    if not results:
        return ""

    label_map = {"resume": "【履歴書より抜粋】", "company": "【企業情報より抜粋】"}
    lines = []
    for doc_type, chunk, _score in results:
        label = label_map.get(doc_type, "【参考情報】")
        lines.append(f"{label}\n{chunk}")
    return "\n\n".join(lines)
