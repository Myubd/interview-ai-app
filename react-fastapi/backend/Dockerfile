# 配置先: interview_app/react-fastapi/backend/Dockerfile (既存ファイルの修正版)
#
# 元のDockerfileから3点変更:
#   1. build contextが interview_app/react-fastapi/backend だけだと、
#      backend/shared -> ../../shared へのシンボリックリンクの実体
#      (interview_app/shared/) がcontextの外になり、コンテナ内で
#      "ModuleNotFoundError: No module named 'question_prediction'" になる。
#      → docker-compose.yml側でcontextを interview_app/ 直下まで広げ、
#        このDockerfile内のCOPYパスもそれに合わせて調整した。
#   2. local_ai_core submoduleのpipインストールを追加。
#   3. 共有ボリューム(/shared/core)用ディレクトリをchownより前に作成。
#
# docker-compose.yml側の対応する設定:
#   build:
#     context: ./interview_app
#     dockerfile: react-fastapi/backend/Dockerfile

# ── ビルドステージ ──────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY react-fastapi/backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── ランタイムステージ ────────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local

# [変更1] backendの中身をコピー。ここには "shared" という壊れたシンボリック
# リンク(../../shared を指す)が含まれるが、リンク先はbuild contextの外なので
# 実体を伴わない(≒無視される)。次のCOPYで実体を正しい場所に上書きする。
COPY react-fastapi/backend/ .

# [変更1つづき] interview_app/shared/ の実体を、シンボリックリンクが
# 本来指していた場所と同じパス(/app/shared)に実ファイルとしてコピーする。
COPY shared/ /app/shared

# [変更2] local_ai_core は requirements.txt に載らない(gitのsubmoduleであり、
# PyPIパッケージではないため)ので、ここで明示的にpipインストールする。
RUN pip install --no-cache-dir ./local_ai_core

RUN mkdir -p /app/data

# [変更3] 共有ボリューム(/shared/core)用のディレクトリも、chownより前に作成。
RUN mkdir -p /shared/core

RUN useradd -m appuser && chown -R appuser /app /shared/core
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INTERVIEW_DB_PATH=/app/data/career_support.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
