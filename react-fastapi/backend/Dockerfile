# ── ビルドステージ ──────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# システム依存（OCR用 tesseract はランタイム側で入れる）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── ランタイムステージ ────────────────────────────────────────
FROM python:3.11-slim

# OCR（PDF内画像のテキスト化）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ビルドステージの site-packages をコピー
COPY --from=builder /install /usr/local

# アプリコード
COPY . .

# DB / データディレクトリ
RUN mkdir -p /app/data

# 非rootユーザー
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INTERVIEW_DB_PATH=/app/data/career_support.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
