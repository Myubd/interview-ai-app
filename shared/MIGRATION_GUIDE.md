# shared/ 移行ガイド

## 背景

`streamlit/` と `react-fastapi/backend/` の間で完全に同一のファイルが19個存在しており、
片方を修正するともう一方も更新し忘れるリスクがありました。

これらを `shared/` ディレクトリに一元化し、シンボリックリンクで両環境から参照します。

## 対象ファイル（shared/ 管理に移行済み）

| ファイル | 説明 |
|---------|------|
| `answer_assist.py` | 回答アシスト機能 |
| `industry_engine.py` | 業界別面接モード定義 |
| `mock_interview_engine.py` | AI模擬面接エンジン |
| `persona_engine.py` | 面接官ペルソナ管理 |
| `db/` (6ファイル) | SQLiteデータベース層 |
| `prompts/` (5ファイル) | プロンプトテンプレート |
| `rag/__init__.py`, `rag/extraction.py`, `rag/persistence.py` | RAGロジック |

## 管理対象外（個別保持）

| ファイル | 理由 |
|---------|------|
| `rag/core.py` | Streamlit/FastAPI間で軽微な差分あり |
| `utils.py` / `utils/` | Streamlit側はパッケージ化済み、FastAPI側は別管理 |

## セットアップ手順

```bash
# Streamlit側
cd interview_app/streamlit
ln -s ../shared shared

# FastAPI側
cd interview_app/react-fastapi/backend
ln -s ../../shared shared
```

シンボリックリンクを張った後は、既存の `from industry_engine import ...` 等のimportは
**変更不要** です（Pythonのモジュール探索パスが通っていれば動作します）。

## 開発時のルール

- `shared/` のファイルを編集した場合、両バックエンドで動作確認を行う。
- どちらか一方のバックエンド固有の変更は、そのバックエンドのディレクトリに独自ファイルを作成する。
- `shared/` に新ファイルを追加する際は、もう一方のバックエンドにも同じファイルが必要かを確認する。
