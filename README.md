# 就活インタビューAI

ローカル LLM（Ollama）を使った就活支援アプリ。面接内容・職務経歴などの個人情報は外部に送信せず、LLM処理は**ローカル（オフライン）**で完結します。
※アプリ起動時のアップデート確認、および初回のOllamaインストールには別途インターネット接続が必要です。

![AI模擬面接の画面](./streamlit/screenshots/screenshot_04.png)

---

## プロジェクト構成

```mermaid
graph TD
    subgraph このリポジトリ
        A[interview_app/]
        A --> B[streamlit/<br/>全機能版・現メイン]
        A --> C[react-fastapi/<br/>移植中]
        A --> D[shared/<br/>共通ロジック]
        B -.シンボリックリンク.-> D
        C -.シンボリックリンク.-> D
    end
```

| フォルダ | 説明 |
|---------|------|
| [`streamlit/`](./streamlit/) | Streamlit 版（全機能）← **現在のメイン**。バージョンは [`streamlit/version.txt`](./streamlit/version.txt) で管理 |
| [`react-fastapi/`](./react-fastapi/) | React + FastAPI 版（移植中。下表の🔜は今後対応予定） |
| [`shared/`](./shared/) | 両版が共有するエンジン・DB・プロンプト |

---

## 機能対応表

| 機能 | Streamlit版 | React+FastAPI版 |
|------|:-----------:|:---------------:|
| AI模擬面接 | ✅ | ✅ |
| 面接履歴 | ✅ | ✅ |
| ダッシュボード（スコア集計） | ✅ | ✅ |
| ナレッジベース管理（RAG） | ✅ | ✅ |
| 設定 | ✅ | ✅ |
| 動的インタビュー・自己PR生成 | ✅ | 🔜 |
| 企業比較マトリクス | ✅ | 🔜 |
| 性格診断（Big Five） | ✅ | 🔜 |
| AIキャリアアドバイザー | ✅ | 🔜 |
| 想定質問生成 | ✅ | 🔜 |

---

## 動作要件

| 項目 | 内容 |
|------|------|
| OS | インストーラー版は Windows のみ。開発者向け起動は Windows / macOS / Linux 可（Docker利用時） |
| Python | 3.10 以降（Streamlit版・開発者向け起動時） |
| Node.js | React+FastAPI版のフロントエンドをソースから起動する場合に必要 |
| メモリ / VRAM | `qwen3:8b` をストレスなく動かす場合、目安として **メモリ16GB以上**（GPU利用時はVRAM 8GB以上）を推奨 |
| Docker | React+FastAPI版をDockerで起動する場合に必要（Docker Compose対応版） |

> モデルサイズや実行速度はOllama・使用ハードウェアに依存します。スペックが厳しい場合は、より軽量なモデル（例: `qwen3:4b`）への変更もご検討ください。

---

## クイックスタート

### インストーラー版（推奨・Windows）

[Releases](../../releases) からインストーラーをダウンロードして実行するだけです。  
**Ollama のインストール・起動は自動で行われます（初回起動時にインターネット接続が必要です）。**

> ただし、LLM モデルの初回ダウンロードは別途必要です（後述）。

### 開発者向け（ソースから起動）

#### Streamlit版（全機能）

```bash
# Ollama を手動でインストール: https://ollama.com
ollama pull qwen3:8b
ollama pull nomic-embed-text

cd streamlit
pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501
```

#### React + FastAPI版（Docker）

```bash
cd react-fastapi

# 初回のみ：モデルをコンテナ内でセットアップ
docker compose --profile setup run --rm model_setup

# 起動
docker compose up --build
# → http://localhost:3000
```

---

## モデルのセットアップ（初回のみ）

インストーラー版・開発者版いずれも、**LLM モデルの初回ダウンロードは手動**で行ってください。

```bash
ollama pull qwen3:8b          # チャット・生成用
ollama pull nomic-embed-text  # 埋め込み（RAG）用
```

---

## トラブルシューティング

| 症状 | 対処法 |
|------|--------|
| 起動時に「Ollamaに接続できません」と表示される | `ollama serve` でOllamaが起動しているか確認してください（`http://localhost:11434` に応答があればOK）。インストーラー版は自動起動を試みますが、失敗した場合は手動で起動してください |
| モデルが見つからない、と言われる | 「モデルのセットアップ」の手順（`ollama pull qwen3:8b` / `ollama pull nomic-embed-text`）が完了しているか確認してください |
| 応答が極端に遅い・固まる | ハードウェアスペック不足の可能性があります。軽量モデルへの変更、またはGPU利用（Docker版は`docker-compose.yml`のGPU設定コメントを参照）をご検討ください |
| Ollamaの自動インストールに失敗する（インストーラー版） | [https://ollama.com](https://ollama.com) から手動でインストールしてください |

---

## 共通仕様

| 項目 | 内容 |
|------|------|
| LLM | Ollama（ローカル） |
| 推奨チャットモデル | qwen3:8b |
| 推奨埋め込みモデル | nomic-embed-text |
| データ保存 | SQLite（ローカルのみ）。デフォルトは `db/career_support.db`。インストーラー版（exe実行時）は `%APPDATA%\InterviewApp\db\` 配下、環境変数 `INTERVIEW_DB_PATH`（React+FastAPI版）で保存先を上書き可能 |
| 外部送信 | 面接内容・個人情報は**なし**（LLM処理はすべてローカルOllamaで完結）。ただしアップデート確認等でGitHubへの通信は発生 |

---

## テスト

```bash
# Streamlit版
cd streamlit
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -m "not integration"   # 高速なユニットテストのみ
pytest tests/                        # 全テスト

# React+FastAPI版
cd react-fastapi
docker compose --profile test run --rm test           # 全テスト
docker compose --profile test run --rm test pytest -m unit  # 高速なユニットテストのみ
```

詳細なテスト方針は [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) を参照してください。

---

## ドキュメント

- [Streamlit版 詳細README](./streamlit/README.md)
- [React+FastAPI版 詳細README](./react-fastapi/README.md)
- [React+FastAPI版 APIドキュメント](http://localhost:8000/docs)（起動後にアクセス）

---

## ライセンス

[MIT License](./LICENSE) © 2026 Myubd
