"""
main.py
--------
FastAPI アプリケーションのエントリポイント。
OpenAPI メタデータ・タグ説明を整備し、Swagger UI を充実させる。
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

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
# アプリ初期化
# ============================================================
app = FastAPI(
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB 初期化 ────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    logger.info("DB initialized")

# ── ルーター登録 ─────────────────────────────────────────────
app.include_router(health.router,          prefix="/api/v1",                 tags=["health"])
app.include_router(mock_interview.router,  prefix="/api/v1/mock-interview",  tags=["mock-interview"])
app.include_router(sessions.router,        prefix="/api/v1/sessions",        tags=["sessions"])
app.include_router(knowledge_base.router,  prefix="/api/v1/knowledge-bases", tags=["knowledge-base"])
app.include_router(settings.router,        prefix="/api/v1/settings",        tags=["settings"])
