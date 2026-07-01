# shared/

`streamlit/` 版と `react-fastapi/` 版の両方から使われる、UI に依存しない共通ロジックの置き場です。

設計思想・import の解決順序・編集時のルールなど詳細な背景は [`MIGRATION_GUIDE.md`](./MIGRATION_GUIDE.md) を参照してください。ここでは「何が入っているか」の見取り図のみをまとめます。

---

## 中身

| ファイル / ディレクトリ | 役割 |
|---|---|
| `mock_interview_engine.py` | AI模擬面接エンジン（質問生成・深掘り判定・評価） |
| `persona_engine.py` | 面接官ペルソナの管理 |
| `industry_engine.py` | 業界別面接モードの定義 |
| `answer_assist.py` | 回答アシスト機能 |
| `prompts/` | LLM プロンプトテンプレート一式。ハルシネーション防止ガード（`guards.py`）を含む |
| `check_sync.py` | `db/` `rag/`（`core.py`除く）が `shared/` / `streamlit/` / `react-fastapi/backend/` の3箇所で内容一致しているかを検証するスクリプト（CIで実行） |
| `db/`, `rag/` | 参照用の正本。実行時に読み込まれるのはアプリ側の物理コピーで、こちらは編集時の同期対象（詳細は `MIGRATION_GUIDE.md`） |

## 注意

- `mock_interview_engine.py` などの一本化済みファイルは **`shared/` にしか存在しません**。`streamlit/` や `react-fastapi/backend/` に同名ファイルを新規作成しないでください。
- `db/` / `rag/` を編集する場合は3箇所すべてに反映し、`python3 shared/check_sync.py` でズレがないか確認してください。
