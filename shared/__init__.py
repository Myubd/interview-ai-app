"""
shared/
--------
StreamlitとFastAPI（react-fastapi）の両バックエンドで共通利用するロジック。

## 含まれるモジュール
- answer_assist.py        : 回答アシスト機能
- industry_engine.py      : 業界別面接モード定義
- mock_interview_engine.py: AI模擬面接エンジン
- persona_engine.py       : 面接官ペルソナ管理
- db/                     : SQLiteデータベース層
- prompts/                : プロンプトテンプレート
- rag/                    : RAGコアロジック・永続化

## セットアップ方法

各バックエンドのルートに `shared` へのシンボリックリンクを張ることで、
コードを複製せずに共通ロジックを参照できる。

### Streamlit側
```bash
cd interview_app/streamlit
ln -s ../shared shared
```

### FastAPI側
```bash
cd interview_app/react-fastapi/backend
ln -s ../../shared shared
```

## 変更時の注意
- このディレクトリへの変更は両バックエンドに影響する。
- 一方のバックエンド固有の変更はそれぞれのディレクトリで行うこと。
- `rag/core.py` はStreamlit/FastAPIで微差分があるため shared には含めず、
  各バックエンドに個別に保持する。
"""
