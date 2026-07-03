"""
main.py
--------
FastAPI アプリケーションのエントリポイント。
OpenAPI メタデータ・タグ説明を整備し、Swagger UI を充実させる。
"""
from __future__ import annotations

# ============================================================
# shared/ ブートストラップ（他のどの import よりも先に実行する）
# ------------------------------------------------------------
# industry_engine / persona_engine / mock_interview_engine /
# answer_assist / question_prediction / interview_engine / pr_generation /
# summary_generation / prompts パッケージは shared/ に一本化されており、
# backend/ 側には物理コピーを置かない。
# shared/ を sys.path の末尾に「追加」することで、backend/ 側に
# 存在しないモジュール（上記5つ）だけが shared/ にフォールバックする。
#
# 注意: 先頭に insert してはいけない。shared/ には db/・rag/ も
# 参考として存在するが、これらは Python のパッケージ相対 import
# （`from db.database import ...` 等）の都合上アプリ固有の兄弟
# モジュール（database.py の DB パス解決、rag/core.py の埋め込み
# 実装）と同一ディレクトリに存在する必要があるため、backend/db/・
# backend/rag/ に物理コピーを維持している。shared/ を先頭に挿入
# すると db・rag の名前解決が shared/ 側に奪われ、DB保存先が
# 意図せず変わる等の事故につながるため、必ず backend/ 側の解決を
# 優先させる（= shared/ は末尾に追加してフォールバック専用にする）。
#
# uvicorn は `main:app` 起動時に CWD（backend/）を sys.path[0] に
# 挿入するため、shared/ の追加はそれより後（＝末尾）で問題ない。
# 詳細は shared/MIGRATION_GUIDE.md を参照。
# ============================================================
import sys as _sys
from pathlib import Path as _Path

_SHARED_DIR = _Path(__file__).resolve().parent / "shared"
if str(_SHARED_DIR) not in _sys.path:
    _sys.path.append(str(_SHARED_DIR))

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import health, mock_interview, sessions, knowledge_base, settings
from api.routes import setup_progress   # ← 追加
from api.routes import favorites        # ← 追加（お気に入り機能）
from api.routes import predicted_questions  # ← 追加（想定質問生成）
from api.routes import version          # ← 追加（アプリバージョン表示）
from api.routes import interview        # ← 追加（自己PR作成フロー）
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
        "name": "setup",
        "description": (
            "Ollama のインストール・モデルダウンロードの進捗確認。\n\n"
            "- `GET /setup/status` : 完了フラグをポーリング\n"
            "- `GET /setup/progress` : SSE でリアルタイム進捗を受信"
        ),
    },
    {
        "name": "mock-interview",
        "description": """\
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
    {
        "name": "favorites",
        "description": (
            "**お気に入り**の管理。性格診断・企業比較・想定質問・面接履歴・AIキャリア相談など、\n"
            "各機能から生成された結果を (item_type, item_id, session_id) 単位で保存/解除できる。"
        ),
    },
    {
        "name": "predicted-questions",
        "description": (
            "**想定質問生成**（RAGベース版）。共通履歴書KB + 選択した企業KBから、\n"
            "面接本番で聞かれそうな質問と模範回答例を8問生成する。\n"
            "自己PR・インタビュー履歴の完成を前提としない独立した入口。"
        ),
    },
    {
        "name": "version",
        "description": "アプリのバージョン文字列を返す。サイドバーの表示用。",
    },
    {
        "name": "interview",
        "description": (
            "**自己PR引き出しインタビュー**。テーマ制のQ&Aで学生の強みを掘り下げ、\n"
            "面接サマリー・自己PR（3パターン）・評価・微調整リライト・企業別カスタマイズPRを生成する。\n"
            "mock-interview と同じくサーバー側に会話状態を持たないステートレス設計。"
        ),
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


# ============================================================
# アプリ初期化
# ============================================================
app = FastAPI(
    lifespan=lifespan,
    title="就活インタビューAI API",
    description="""\
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
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ────────────────────────────────────────────────────
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ルーター登録 ─────────────────────────────────────────────
app.include_router(health.router,          prefix="/api/v1",                 tags=["health"])
app.include_router(setup_progress.router,  prefix="/api/v1",                 tags=["setup"])   # ← 追加
app.include_router(mock_interview.router,  prefix="/api/v1/mock-interview",  tags=["mock-interview"])
app.include_router(sessions.router,        prefix="/api/v1/sessions",        tags=["sessions"])
app.include_router(knowledge_base.router,  prefix="/api/v1/knowledge-bases", tags=["knowledge-base"])
app.include_router(settings.router,        prefix="/api/v1/settings",        tags=["settings"])
app.include_router(favorites.router,       prefix="/api/v1/favorites",       tags=["favorites"])
app.include_router(predicted_questions.router, prefix="/api/v1/predicted-questions", tags=["predicted-questions"])
app.include_router(version.router,         prefix="/api/v1/version",          tags=["version"])
app.include_router(interview.router,       prefix="/api/v1/interview",        tags=["interview"])

# ── 静的ファイル配信（exe ビルド時のみ） ─────────────────────
_static_dir = os.environ.get("INTERVIEW_STATIC_DIR", "")
if _static_dir and os.path.isdir(_static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(_static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        """API以外のパスはすべてReactのindex.htmlを返す（SPA対応）。"""
        index = os.path.join(_static_dir, "index.html")
        return FileResponse(index)
