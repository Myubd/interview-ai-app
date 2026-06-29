# 就活インタビューAI — Streamlit 版

Streamlit + ローカル LLM（Ollama）で動く就活支援アプリのメイン実装。  
個人情報を外部に送信せず、**完全オフライン**で動作します。

---

## アーキテクチャ概要

```mermaid
graph TB
    subgraph Streamlit UI
        APP[app.py<br/>ページルーティング]
        APP --> P1[動的インタビュー<br/>自己PR生成]
        APP --> P2[AI模擬面接]
        APP --> P3[企業比較マトリクス]
        APP --> P4[性格診断 Big Five]
        APP --> P5[AIキャリアアドバイザー]
        APP --> P6[想定質問生成]
        APP --> P7[面接履歴]
    end

    subgraph shared/ 共通ロジック
        ENG[interview_engine<br/>mock_interview_engine]
        PE[persona_engine]
        RAG[rag/ RAGコア]
        DB[(SQLite)]
        PROMPTS[prompts/]
        ENG --> PROMPTS
        PE --> PROMPTS
        ENG --> DB
        RAG --> DB
    end

    subgraph Ollama ローカルLLM
        LLM[qwen3:8b<br/>チャット・生成]
        EMB[nomic-embed-text<br/>埋め込み]
    end

    P1 & P2 & P6 --> ENG
    P2 --> PE
    P1 & P2 --> RAG
    RAG --> EMB
    ENG --> LLM
    PE --> LLM
```

---

## 機能一覧

| 機能 | 説明 |
|------|------|
| 動的インタビュー・自己PR生成 | 履歴書・企業情報をもとに面接対策コンテンツを生成 |
| AI模擬面接 | ペルソナ・業界別テーマで本番に近い面接を体験 |
| 企業比較マトリクス | 複数企業の特徴を表形式で比較 |
| 性格診断（Big Five） | 自己分析をサポート |
| AIキャリアアドバイザー | 志望方向・強みのアドバイスを生成 |
| 想定質問生成 | 企業・業界に合わせた予想質問を事前生成 |
| ナレッジベース管理（RAG） | 履歴書・企業情報をPDF/テキストで登録 |
| 面接履歴 | セッションをDBに保存・振り返り |

---

## セットアップ

### インストーラー版（推奨・Windows）

[Releases](../../../releases) からインストーラーをダウンロードして実行するだけです。  
**Ollama のインストール・起動は自動で行われます（初回起動時にインターネット接続が必要です）。**

初回起動後、以下のコマンドで LLM モデルをダウンロードしてください。

```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

### 開発者向け（ソースから起動）

```bash
# Ollama を手動でインストール: https://ollama.com
ollama pull qwen3:8b
ollama pull nomic-embed-text

cd streamlit
pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501
```

### 別マシンの Ollama に接続する場合

```bash
OLLAMA_HOST=http://192.168.1.10:11434 streamlit run app.py
```

---

## AI模擬面接フロー

```mermaid
stateDiagram-v2
    [*] --> 設定: ペルソナ・プロフィール入力
    設定 --> 面接中: 面接開始

    state 面接中 {
        [*] --> 自己紹介
        自己紹介 --> ガクチカ
        ガクチカ --> 志望動機
        志望動機 --> 企業理解
        企業理解 --> 逆質問
        逆質問 --> [*]

        state 各テーマ {
            質問 --> 回答
            回答 --> 深掘り判定
            深掘り判定 --> 質問: 深掘りあり
            深掘り判定 --> [*]: 次テーマへ
        }
    }

    面接中 --> 評価待ち: 全テーマ完了 or 途中終了
    評価待ち --> 評価レポート: 評価生成
    評価レポート --> [*]
```

---

## ディレクトリ構成

```
streamlit/
├── app.py                        # エントリポイント・ページルーティング
├── startup/                      # 起動フェーズ（DB初期化・Ollama確認・バージョンチェック）
├── state/                        # セッション状態の定義・初期化
├── components/sidebar/           # サイドバー UI（ナビ・RAGパネル・設定）
├── page_modules/                 # ページごとの UI ロジック
│   ├── interview/                # 動的インタビュー・自己PR生成
│   ├── mock_interview/           # AI模擬面接
│   ├── career_page.py            # AIキャリアアドバイザー
│   ├── company_matrix_page.py    # 企業比較マトリクス
│   ├── personality_page.py       # 性格診断（Big Five）
│   ├── predict_questions_page.py # 想定質問生成
│   └── history_page.py           # 面接履歴
├── utils/                        # LLM呼び出し・サニタイズ等のユーティリティ
├── rag/                          # RAGコアロジック（チャンク分割・埋め込み・検索）
├── db/                           # SQLiteデータベース層
├── session_io/                   # セッションのDB/JSON入出力
├── prompts/                      # プロンプトテンプレート
├── shared -> ../shared/          # 共通モジュール（シンボリックリンク）
└── tests/                        # ユニット・統合テスト
```

---

## データフロー（RAG）

```mermaid
flowchart LR
    subgraph 登録
        A[PDF / テキスト] --> B[テキスト抽出]
        B --> C[チャンク分割]
        C --> D[埋め込み生成<br/>nomic-embed-text]
        D --> E[(SQLite<br/>ベクトル保存)]
    end

    subgraph 検索・生成
        F[質問・プロフィール] --> G[埋め込み生成]
        G --> H[類似検索]
        E --> H
        H --> I[RAGコンテキスト]
        I --> J[LLM プロンプト<br/>qwen3:8b]
        J --> K[回答・質問・評価]
    end
```

---

## テスト

```bash
pip install -r requirements-dev.txt

# ユニットテスト（外部依存なし）
pytest tests/ -m "not integration"

# 統合テスト（DB使用）
pytest tests/ -m "integration"

# カバレッジ付き
pytest tests/ -m "not integration" --cov=utils --cov=rag --cov-report=term-missing
```

---

## 共通仕様

| 項目 | 内容 |
|------|------|
| LLM | Ollama（ローカル） |
| 推奨チャットモデル | qwen3:8b |
| 推奨埋め込みモデル | nomic-embed-text |
| データ保存 | SQLite（`db/career_support.db`） |
| 外部送信 | **なし** |
