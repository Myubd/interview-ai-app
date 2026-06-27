# db/

SQLite データベースはここに自動生成されます。

- `career_support.db` は `.gitignore` で除外されています
- アプリ初回起動時に `startup.run()` → `init_db()` が自動でテーブルを作成します
- 手動で作成する必要はありません

## バックアップ

データをバックアップしたい場合は `career_support.db` をコピーしてください。
