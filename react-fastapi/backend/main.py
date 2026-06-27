"""
main.py
--------
FastAPI アプリケーションのエントリポイント。
OpenAPI メタデータ・タグ説明を整備し、Swagger UI を充実させる。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import health, mock_interview, sessions, knowledge_base, settings
from db.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# タグメタデータ（Swagger UI のセクション説明）
# ============================================================
TAGS_METADATA = [
    {
        "name": "health",
        "description": "サーバーと Ollama の疎通確認。起動直後に叩いて LLM が使える状態か確認する。",
    },
    {
        "name": "mock-interview",
        "description": """
**AI模擬面接**のコアエンドポイント。

- `POST /start` でセッションを開始し最初の質問を取得
- `POST /answer` で回答を送信（**SSE ストリーミング**で次の質問を受け取る）
- `POST /evaluate` で面接終了後の総合評価を生成

SSE イベント種別:
| event | データ | 説明 |
|-------|--------|------|
| `question` | `{text, is_followup, theme_index}` | 次の質問 |
| `transition` | `{theme_index, theme_title}` | テーマ遷移 |
| `finished` | `{message}` | 全テーマ終了 |
| `error` | `{message}` | エラー |
        """,
    },
    {
        "name": "sessions",
        "description": "面接セッションの CRUD。メッセージ履歴・評価結果の保存と JSON エクスポート/インポートに対応。",
    },
    {
        "name": "knowledge-base",
        "description": "**RAG ナレッジベース**の管理。履歴書・企業情報をテキストまたはファイル（PDF/画像）で登録し、面接の質問生成・評価に活用する。",
    },
    {
        "name": "settings",
        "description": "LLM モデル名・埋め込みモデル名・Ollama ホストの取得と更新。変更は即時反映される。",
    },
]

# ============================================================
# lifespan（DB初期化）
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリ起動時にDBを初期化し、終了時にクリーンアップする。"""
    init_db()
    logger.info("DB initialized")
    yield
    # 終了時の処理が必要であればここに追加


# ============================================================
# アプリ初期化
# ============================================================
app = FastAPI(
    lifespan=lifespan,
    title="就活インタビューAI API",
    description="""
## 概要
ローカル LLM（Ollama）を使った就活支援バックエンド。
面接練習・履歴書管理・RAG検索など、個人情報を外部に送信せずに動作します。

## 認証
現バージョンは認証なし（ローカル専用）。

## LLM プロバイダー
デフォルトは **Ollama**（ローカル）。`OLLAMA_HOST` 環境変数で接続先を変更できます。

```
OLLAMA_HOST=http://localhost:11434  # デフォルト
OLLAMA_HOST=http://ollama:11434     # Docker Compose 内
```

## SSE ストリーミング
`POST /api/v1/mock-interview/answer` は **Server-Sent Events** でレスポンスを返します。
EventSource または fetch + ReadableStream で受け取ってください。
    """,
    version="4.0.0",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "就活インタビューAI",
        "url": "https://github.com/your-repo/interview-app",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────
# 環境変数 ALLOWED_ORIGINS でカンマ区切りに複数指定可能。
# 未設定時はローカル開発用のデフォルト値を使用する。
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB 初期化（lifespan に移動済み） ─────────────────────────

# ── ルーター登録 ─────────────────────────────────────────────
app.include_router(health.router,          prefix="/api/v1",                 tags=["health"])
app.include_router(mock_interview.router,  prefix="/api/v1/mock-interview",  tags=["mock-interview"])
app.include_router(sessions.router,        prefix="/api/v1/sessions",        tags=["sessions"])
app.include_router(knowledge_base.router,  prefix="/api/v1/knowledge-bases", tags=["knowledge-base"])
app.include_router(settings.router,        prefix="/api/v1/settings",        tags=["settings"])

# ── 静的ファイル配信（exe ビルド時のみ） ─────────────────────
# INTERVIEW_STATIC_DIR が設定されている場合、React ビルド済みファイルを配信する
_static_dir = os.environ.get("INTERVIEW_STATIC_DIR", "")
if _static_dir and os.path.isdir(_static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(_static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        """API以外のパスはすべてReactのindex.htmlを返す（SPA対応）。"""
        index = os.path.join(_static_dir, "index.html")
        return FileResponse(index)

