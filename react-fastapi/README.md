# 就活インタビューAI — React + FastAPI 版

Streamlit 版の主要機能を **React + FastAPI** に移植したプロジェクト。  
Docker で一発起動、または `start.sh` でローカル起動できます。

---

## アーキテクチャ概要

```mermaid
graph LR
    subgraph ブラウザ
        FE[React フロントエンド<br/>:3000 / :5173]
    end

    subgraph バックエンド
        API[FastAPI<br/>:8000]
        SVC[InterviewService]
        DB[(SQLite)]
        API --> SVC
        SVC --> DB
    end

    subgraph 共通ロジック shared/
        ENG[mock_interview_engine<br/>persona_engine]
        RAG[RAG コア<br/>埋め込み・検索]
        PROMPTS[プロンプト<br/>テンプレート]
        ENG --> PROMPTS
        SVC --> ENG
        SVC --> RAG
    end

    subgraph Ollama ローカルLLM
        LLM[qwen3:8b<br/>チャット]
        EMB[nomic-embed-text<br/>埋め込み]
    end

    FE -- REST / SSE --> API
    ENG --> LLM
    RAG --> EMB
```

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
| 想定質問生成 | 🔜 Streamlit版に残存 |

---

## セットアップ

### インストーラー版（推奨・Windows）

[Releases](../../../../releases) からインストーラーをダウンロードして実行するだけです。  
**Ollama のインストール・起動は自動で行われます（初回起動時にインターネット接続が必要です）。**

初回起動後、以下のコマンドで LLM モデルをダウンロードしてください。

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

### 開発者向け（Docker・推奨）

```bash
cd react-fastapi

# 初回のみ：モデルをコンテナ内でセットアップ
docker compose --profile setup run --rm model_setup

# 起動
docker compose up --build
# → http://localhost:3000
```

### 開発者向け（ローカル起動）

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

## AI模擬面接フロー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant B as FastAPI
    participant E as InterviewService
    participant L as Ollama (LLM)

    U->>F: 面接官タイプ・プロフィールを選択
    F->>B: POST /mock-interview/start
    B->>E: InterviewService.start()
    E->>L: 最初の質問を生成
    L-->>E: 質問テキスト
    E-->>B: StartResult
    B-->>F: { question, theme_index, theme_title }
    F-->>U: 質問を表示

    loop 各テーマ（自己紹介→ガクチカ→志望動機→企業理解→逆質問）
        U->>F: 回答を入力・送信
        F->>B: POST /mock-interview/answer
        B->>E: answer_stream() → SSE
        E->>L: 深掘り要否を判定・次の質問を生成
        L-->>E: 質問 or テーマ遷移
        E-->>F: SSE イベント (question / transition / finished)
        F-->>U: 次の質問 or テーマ移動を表示
    end

    U->>F: 評価を依頼
    F->>B: POST /mock-interview/evaluate
    B->>E: InterviewService.evaluate()
    E->>L: 総合評価を生成
    L-->>E: 評価JSON
    E-->>F: { overall_score, axes, strengths, ... }
    F-->>U: 評価レポートを表示
```

---

## ディレクトリ構成

```
react-fastapi/
├── backend/
│   ├── main.py                    # FastAPI エントリポイント・CORS・ルーター登録
│   ├── api/routes/
│   │   ├── health.py              # GET /api/v1/health
│   │   ├── mock_interview.py      # POST /api/v1/mock-interview/* (SSE対応)
│   │   ├── sessions.py            # CRUD /api/v1/sessions/*
│   │   ├── knowledge_base.py      # /api/v1/knowledge-bases/*
│   │   └── settings.py            # /api/v1/settings/
│   ├── services/
│   │   └── interview_service.py   # 面接ビジネスロジック・SSEイベント生成
│   ├── llm/
│   │   ├── base.py                # LLMProvider 抽象クラス
│   │   ├── ollama_provider.py     # Ollama 実装（OpenAI/Claude スタブあり）
│   │   └── __init__.py            # DI 管理
│   ├── shared -> ../../shared/    # 共通モジュール（シンボリックリンク）
│   └── tests/
│       ├── test_unit.py
│       ├── test_api.py
│       └── test_integration.py
└── frontend/
    └── src/
        ├── api/client.ts              # 型付き REST API クライアント
        ├── hooks/useMockInterview.ts  # 面接状態管理・SSE ストリーミング
        ├── components/
        │   ├── Sidebar.tsx            # ナビゲーション
        │   └── ui.tsx                 # Button / Card / Badge 等
        └── pages/
            ├── HomePage.tsx
            ├── MockInterviewPage.tsx  # 設定→面接→評価の3フェーズ
            ├── HistoryPage.tsx
            ├── KnowledgePage.tsx
            └── SettingsPage.tsx
```

---

## API エンドポイント一覧

```mermaid
mindmap
  root((API v1))
    health
      GET /health
    mock-interview
      POST /start
      POST /answer SSE
      POST /evaluate
      GET /personas
      GET /themes
    sessions
      GET POST /
      GET PATCH DELETE /:id
      GET /:id/export
      POST /import
    knowledge-bases
      GET /
      POST /text
      POST /upload
      DELETE /:id
      PATCH /:id/active
      POST /:id/search
    settings
      GET PATCH /
```

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/v1/health | Ollama 疎通確認 |
| POST | /api/v1/mock-interview/start | 模擬面接開始・最初の質問取得 |
| POST | /api/v1/mock-interview/answer | 回答送信（**SSEストリーミング**） |
| POST | /api/v1/mock-interview/evaluate | 終了後評価生成 |
| GET | /api/v1/mock-interview/personas | ペルソナ一覧 |
| GET | /api/v1/mock-interview/themes | テーマ一覧 |
| GET / POST | /api/v1/sessions/ | セッション一覧・作成 |
| GET / PATCH / DELETE | /api/v1/sessions/{id} | セッション取得・更新・削除 |
| GET | /api/v1/sessions/{id}/export | JSON エクスポート |
| POST | /api/v1/sessions/import | JSON インポート |
| GET | /api/v1/knowledge-bases/ | KB 一覧 |
| POST | /api/v1/knowledge-bases/text | テキストから KB 作成 |
| POST | /api/v1/knowledge-bases/upload | ファイルアップロードから KB 作成 |
| DELETE | /api/v1/knowledge-bases/{id} | KB 削除 |
| PATCH | /api/v1/knowledge-bases/{id}/active | アクティブ切り替え |
| POST | /api/v1/knowledge-bases/{id}/search | RAG 類似検索 |
| GET / PATCH | /api/v1/settings/ | 設定取得・更新 |

全エンドポイントの詳細は起動後に http://localhost:8000/docs で確認できます。

---

## LLM プロバイダーの拡張

将来 OpenAI / Claude に切り替える場合は `backend/llm/ollama_provider.py` の
スタブを実装し、`backend/llm/__init__.py` の `get_provider()` を変更するだけで
全 API に反映されます。

```python
# llm/__init__.py
def get_provider() -> LLMProvider:
    return OllamaProvider()             # 現在
    # return OpenAIProvider(api_key=...) # 切り替え例
    # return ClaudeProvider(api_key=...) # 切り替え例
```

---

## テスト

```bash
cd react-fastapi/backend
pip install -r requirements.txt pytest httpx

# ユニット・APIテスト（外部依存なし）
pytest tests/ -m "not integration"

# 統合テスト（DB使用）
pytest tests/ -m "integration"

# Docker で実行
docker compose --profile test run --rm test
```
