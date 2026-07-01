# db/（react-fastapi/backend）

SQLite データベース層。**`streamlit/db/` と内容が完全に一致している必要がある**パッケージです（`shared/check_sync.py` で3箇所（`shared/` / `streamlit/` / `react-fastapi/backend/`）の一致をCI検証しています）。

テーブル構成（ER図）・各テーブルの用途・マイグレーション方法・バックアップ手順などの詳細は、重複を避けるため以下を参照してください。

👉 [`streamlit/db/README.md`](../../../streamlit/db/README.md)

## このアプリ固有の差分

- DBパスの上書きは環境変数 `INTERVIEW_DB_PATH` を使用（ルートREADMEの「共通仕様」参照）
- 呼び出し元は `backend/services/interview_service.py` など

このパッケージを編集する場合は、`streamlit/db/` と `shared/db/`（参照用の正本）にも同じ変更を反映し、次のコマンドでズレがないか確認してください。

```bash
python3 shared/check_sync.py
```
