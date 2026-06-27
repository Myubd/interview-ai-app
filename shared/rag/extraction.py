"""
rag/extraction.py
-----------------
各種ファイル形式からテキストを抽出するユーティリティ。

提供する関数:
    extract_text_from_pdf(file_bytes)   - PDFバイト列 → テキスト
    extract_text_from_image(file_bytes) - 画像バイト列 → テキスト (OCR)

どちらも抽出に失敗した場合は空文字を返し、例外を上位に伝播しない。
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


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
        logger.warning(
            "画像テキスト抽出失敗（pytesseract/Tesseract 未インストールの可能性あり）",
            exc_info=True,
        )
        return ""
