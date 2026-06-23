"""
rag.py
------
履歴書・企業情報を対象にした軽量RAG（Retrieval Augmented Generation）モジュール。

設計方針:
- 追加の重量級ライブラリ（chromadb等のベクトルDB）は使わない
- 埋め込みは Ollama のローカル埋め込みモデル（nomic-embed-text）を利用
- 類似検索は numpy によるコサイン類似度計算で自前実装
- PDFは pypdf でテキスト抽出（スキャンPDFには非対応。その場合は空文字を返す）

[永続化方針 v2]
- knowledge_bases / documents / document_chunks テーブル（db/database.py）に
  メタ情報・チャンクテキストを保存する。
- embeddingsはDBに直接入れず、document単位で1つの .npy ファイルとして
  rag_data/ ディレクトリに保存し、documents.embedding_path にパスのみ持たせる
  （shape: (n_chunks, dim) の2次元配列）。
- アップロードされたPDF原本は uploads/ ディレクトリに保存し、
  documents.file_path にパスを持たせる（履歴として複数バージョン保持）。
- 既存の Document / search_balanced() 等のメモリ上の検索ロジックは変更しない。
  永続化関数はDBとファイルからこれらの型へ変換するアダプタとして働く。

[v3: リポジトリ層への分離]
- knowledge_bases / documents / document_chunks への実際のDB読み書き（SQL）は
  db/knowledge_base_repository.py に移動した。
- このファイルは、テキスト抽出・チャンク分割・埋め込み生成・類似検索という
  「RAGそのもののロジック」と、Document データクラスの定義に専念する。
  保存・読み込み系の関数（save_resume, save_company_document,
  load_active_documents 等）は、db/knowledge_base_repository.py の
  リポジトリ関数を呼び出すアダプタとして残している。

[v2.1]
- resume/companyを区別せず横断検索する旧 search() を削除した。
  片方の文書種別の結果が0件になりうる既知の問題があり、かつ呼び出し元
  （app.py）は実際には常に search_balanced() のみを使っていたため、
  未使用かつリスクのあるAPIとして廃止した。
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np
import ollama

from db import knowledge_base_repository as kb_repo
from db.settings_repository import get_setting

EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 400        # 1チャンクあたりの目安文字数
CHUNK_OVERLAP = 80      # チャンク間のオーバーラップ文字数
TOP_K = 4                # 検索時に取得する上位チャンク数

# このファイル（プロジェクトルートの rag.py）からの相対パスで各ディレクトリを指す
PROJECT_ROOT = Path(__file__).resolve().parent
RAG_DATA_DIR = PROJECT_ROOT / "rag_data"
UPLOADS_DIR = PROJECT_ROOT / "uploads"


@dataclass
class Document:
    """RAG対象の1文書（履歴書 or 企業情報）を表す"""
    doc_type: str          # "resume" or "company"
    source_name: str       # ファイル名や識別用ラベル
    chunks: list[str] = field(default_factory=list)
    embeddings: np.ndarray | None = None  # shape: (n_chunks, dim)
    document_id: int | None = None  # DB(documents.id)と紐付ける場合に設定。新規未保存ならNone


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """PDFバイト列からテキストを抽出する。スキャンPDF等で失敗した場合は空文字を返す。"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts).strip()
    except Exception:
        logger.warning("PDF テキスト抽出失敗", exc_info=True)
        return ""


def extract_text_from_image(file_bytes: bytes) -> str:
    """画像（PNG/JPG等）バイト列からTesseract OCRでテキストを抽出する。

    失敗時（pytesseract未インストール、Tesseract本体未インストール、
    画像が破損している等）は空文字を返す。extract_text_from_pdf と同じ
    「失敗時は空文字」という規約を踏襲し、呼び出し側のエラーハンドリングを統一する。

    日本語認識には Tesseract の日本語言語データ（jpn）が必要。
    未インストールの場合は lang="eng" にフォールバックして再試行する
    （英語表記の履歴書などは最低限読めるようにするため）。
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(file_bytes))
        try:
            text = pytesseract.image_to_string(image, lang="jpn+eng")
        except pytesseract.TesseractError:
            # 日本語言語データ(jpn)が未インストールの環境向けフォールバック
            text = pytesseract.image_to_string(image, lang="eng")
        return text.strip()
    except Exception:
        logger.warning("画像テキスト抽出失敗（pytesseract/Tesseract 未インストールの可能性あり）", exc_info=True)
        return ""


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
        res = ollama.embeddings(model=model, prompt=text)
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
            ollama.embeddings(model=model, prompt=query)["embedding"], dtype=np.float32
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
            content = line[len("学生:") :].strip()
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



# ============================================================
# 永続化: knowledge_bases
# ============================================================
# [v3] 実際のDB読み書きは db/knowledge_base_repository.py に移動した。
# ここでは互換性のため同名関数を薄いラッパーとして再エクスポートする。

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
            今回のdocumentをversion+1・is_active=1で登録する
            （= 「最低限の履歴を持つ」設計: 古いバージョンはDB/ファイルに残るが、
            RAG検索や表示ではis_active=1のものだけを使う）

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

RESUME_KB_NAME = "共通履歴書"  # 履歴書は企業に紐付かない、常に単一のグローバルKB


def save_resume(source_name: str, raw_text: str, raw_bytes: bytes | None = None) -> tuple[Document | None, int]:
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
        search() / search_balanced() にそのまま渡せる Document のリスト
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
