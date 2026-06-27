"""
rag/__init__.py
---------------
後方互換のための re-export。

既存コードが `from rag import Document` や `import rag; rag.search_balanced(...)` と
書いていても、モジュール分割後もそのまま動くようにすべてのパブリックシンボルを
ここで再エクスポートする。

テストコードが `import rag; rag._QUERY_EMBED_CACHE` のようにモジュール直接参照を
しているため、プライベートシンボルも同様に re-export している。

サブモジュール構成:
    rag/core.py        - Document, chunk_text, embed_texts, search_balanced, ...
    rag/extraction.py  - extract_text_from_pdf, extract_text_from_image
    rag/persistence.py - save_resume, save_company_document, load_active_documents, ...
"""

# core（プライベートシンボル含む、テストが直接参照するため）
from rag.core import (
    EMBED_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    Document,
    chunk_text,
    embed_texts,
    build_document,
    search_balanced,
    build_query_from_student_answers,
    format_context,
    _cosine_similarity,
    _get_query_embedding,
    _QUERY_EMBED_CACHE,
)

# extraction
from rag.extraction import (
    extract_text_from_pdf,
    extract_text_from_image,
)

# persistence
from rag.persistence import (
    get_or_create_knowledge_base,
    list_knowledge_bases,
    save_document_to_kb,
    save_resume,
    save_company_document,
    load_active_documents,
    list_document_versions,
    RESUME_KB_NAME,
)

__all__ = [
    # core
    "EMBED_MODEL",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "TOP_K",
    "Document",
    "chunk_text",
    "embed_texts",
    "build_document",
    "search_balanced",
    "build_query_from_student_answers",
    "format_context",
    "_cosine_similarity",
    "_get_query_embedding",
    "_QUERY_EMBED_CACHE",
    # extraction
    "extract_text_from_pdf",
    "extract_text_from_image",
    # persistence
    "get_or_create_knowledge_base",
    "list_knowledge_bases",
    "save_document_to_kb",
    "save_resume",
    "save_company_document",
    "load_active_documents",
    "list_document_versions",
    "RESUME_KB_NAME",
]
