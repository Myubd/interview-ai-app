# 就活インタビューAI — React + FastAPI 版

Streamlit 版の主要機能を **React + FastAPI** に移植したプロジェクト。  
Docker で一発起動、または `start.sh` でローカル起動できます。

---

## 機能

| 機能 | 状態 |
|------|------|
| AI模擬面接 | ✅ |
| 面接履歴 | ✅ |
| ナレッジベース管理（RAG） | ✅ |
| 設定 | ✅ |
| 動的インタビュー・自己PR生成 | 🔜 Streamlit版に残存 |
| 企業比較マトリクス | 🔜 Streamlit版に残存 |
| 性格診断（Big Five） | 🔜 Streamlit版に残存 |
| AIキャリアアドバイザー | 🔜 Streamlit版に残存 |

---

## セットアップ

### 前提条件

```bash
# Ollama をインストール後、モデルを取得（初回のみ）
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

### Docker で起動（推奨）

```bash
cd react-fastapi

# 初回のみ：モデルをコンテナ内でセットアップ
docker compose --profile setup run --rm model_setup

# 起動
docker compose up --build
# → http://localhost:3000
```

### ローカルで起動

```bash
cd react-fastapi
./start.sh
# フロントエンド: http://localhost:5173
# バックエンド API: http://localhost:8000/docs
```

#### バックエンドのみ

```bash
cd react-fastapi/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### フロントエンドのみ

```bash
cd react-fastapi/frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## ディレクトリ構成

```
react-fastapi/
├── backend/
│   ├── main.py                    # FastAPI エントリポイント
│   ├── llm/
│   │   ├── base.py                # LLMProvider 抽象クラス
│   │   ├── ollama_provider.py     # Ollama 実装（+ OpenAI/Claude スタブ）
│   │   └── __init__.py            # DI 管理
│   ├── api/routes/
│   │   ├── health.py              # GET /api/v1/health
│   │   ├── mock_interview.py      # POST /api/v1/mock-interview/* (SSE対応)
│   │   ├── sessions.py            # CRUD /api/v1/sessions/*
│   │   ├── knowledge_base.py      # /api/v1/knowledge-bases/*
│   │   └── settings.py            # /api/v1/settings/
│   ├── services/
│   │   └── interview_service.py   # 面接ビジネスロジック
│   ├── shared -> ../../shared/    # 共通モジュール（シンボリックリンク）
│   │   ├── db/                    # SQLiteデータベース層
│   │   ├── rag/                   # RAGロジック
│   │   ├── prompts/               # プロンプトテンプレート
│   │   ├── mock_interview_engine.py
│   │   └── persona_engine.py
│   └── tests/
│       ├── conftest.py
│       ├── test_unit.py
│       ├── test_api.py
│       └── test_integration.py
└── frontend/
    └── src/
        ├── api/client.ts              # 型付き API クライアント
        ├── hooks/useMockInterview.ts  # SSE ストリーミングフック
        ├── components/
        │   ├── Sidebar.tsx            # ナビゲーション
        │   └── ui.tsx                 # Button, Card, Badge 等
        └── pages/
            ├── HomePage.tsx
            ├── MockInterviewPage.tsx
            ├── HistoryPage.tsx
            ├── KnowledgePage.tsx
            └── SettingsPage.tsx
```

---

## LLM プロバイダーの拡張

将来 OpenAI / Claude に切り替える場合は `backend/llm/ollama_provider.py` の
`OpenAIProvider` / `ClaudeProvider` スタブを実装し、
`backend/llm/__init__.py` の `get_provider()` を変更するだけで全 API に反映されます。

```python
# llm/__init__.py
def get_provider() -> LLMProvider:
    # return OllamaProvider()            # 現在
    # return OpenAIProvider(api_key=...) # 切り替え例
```

---

## API エンドポイント一覧

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/v1/health | Ollama 疎通確認 |
| POST | /api/v1/mock-interview/start | 模擬面接開始・最初の質問取得 |
| POST | /api/v1/mock-interview/answer | 回答送信（SSEストリーミング） |
| POST | /api/v1/mock-interview/evaluate | 終了後評価生成 |
| GET | /api/v1/mock-interview/personas | ペルソナ一覧 |
| GET | /api/v1/mock-interview/themes | テーマ一覧 |
| GET/POST | /api/v1/sessions/ | セッション一覧・作成 |
| GET/PATCH/DELETE | /api/v1/sessions/{id} | セッション取得・更新・削除 |
| GET | /api/v1/sessions/{id}/export | JSON エクスポート |
| POST | /api/v1/sessions/import | JSON インポート |
| GET/POST | /api/v1/knowledge-bases/ | KB 一覧・テキスト作成 |
| POST | /api/v1/knowledge-bases/upload | ファイルアップロード |
| DELETE | /api/v1/knowledge-bases/{id} | KB 削除 |
| PATCH | /api/v1/knowledge-bases/{id}/active | アクティブ切り替え |
| POST | /api/v1/knowledge-bases/{id}/search | RAG 類似検索 |
| GET/PATCH | /api/v1/settings/ | 設定取得・更新 |

全エンドポイントの詳細は起動後に http://localhost:8000/docs で確認できます。

---

## テスト

```bash
cd react-fastapi/backend
pip install -r requirements.txt pytest pytest-cov httpx

# ユニット・APIテスト（外部依存なし）
pytest tests/ -m "not integration"

# 統合テスト（DB使用）
pytest tests/ -m "integration"
```
