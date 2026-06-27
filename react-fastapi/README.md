# 就活インタビューAI v4 — React + FastAPI 版

## 概要

Streamlit 版 (`interview_app/`) の一部機能を **React + FastAPI** に移植したプロジェクト。

| 機能 | 担当 |
|------|------|
| AI模擬面接 | ✅ React + FastAPI |
| 面接履歴 | ✅ React + FastAPI |
| ナレッジベース管理 | ✅ React + FastAPI |
| 設定 | ✅ React + FastAPI |
| 自己PR生成・インタビュー | Streamlit版に残存 |
| 企業比較マトリクス | Streamlit版に残存 |
| 性格診断 (Big Five) | Streamlit版に残存 |
| AIキャリアアドバイザー | Streamlit版に残存 |

---

## セットアップ

### 前提条件

```bash
# Ollama を起動してモデルを取得
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

### バックエンド

```bash
cd interview_app_v2/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API ドキュメント: http://localhost:8000/docs

### フロントエンド

```bash
cd interview_app_v2/frontend
npm install
npm run dev
# → http://localhost:5173
```

### Streamlit 版（既存機能）

```bash
cd interview_app
streamlit run app.py
# → http://localhost:8501
```

---

## アーキテクチャ

```
interview_app_v2/
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
│   ├── db/                        # ← Streamlit版から流用
│   ├── rag/                       # ← Streamlit版から流用
│   ├── prompts/                   # ← Streamlit版から流用
│   ├── mock_interview_engine.py   # ← Streamlit版から流用
│   ├── persona_engine.py          # ← Streamlit版から流用
│   └── utils.py                   # ← Streamlit版から流用
│
└── frontend/
    └── src/
        ├── api/client.ts          # 型付き API クライアント
        ├── hooks/useMockInterview.ts  # SSE ストリーミングフック
        ├── components/
        │   ├── Sidebar.tsx        # ナビゲーション
        │   └── ui.tsx             # Button, Card, Badge 等
        └── pages/
            ├── HomePage.tsx
            ├── MockInterviewPage.tsx
            ├── HistoryPage.tsx
            ├── KnowledgePage.tsx
            └── SettingsPage.tsx
```

---

## LLM プロバイダーの拡張

将来 OpenAI / Claude に切り替える場合は `llm/ollama_provider.py` の
`OpenAIProvider` / `ClaudeProvider` スタブを実装し、
`llm/__init__.py` の `get_provider()` を変更するだけで全 API に反映されます。

```python
# llm/__init__.py
def get_provider() -> LLMProvider:
    # return OllamaProvider()          # 現在
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
