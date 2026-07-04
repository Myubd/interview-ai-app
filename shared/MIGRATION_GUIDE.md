# shared/ 移行ガイド

## 背景

`streamlit/` と `react-fastapi/backend/` の間で完全に同一のファイルが多数存在しており、
片方を修正するともう一方も更新し忘れるリスクがありました。

これらのうち、**アプリ固有の兄弟モジュールに依存しないファイル**を `shared/` に一元化し、
物理コピーを削除しました。各アプリの起動エントリポイントで `shared/` を `sys.path` の
末尾に追加することで、アプリ側に存在しないモジュールだけが `shared/` にフォールバックして
解決される仕組みです。

> 過去バージョンの本ガイドには「シンボリックリンクを張れば import は変更不要で動作する」と
> 記載していましたが、これは誤りでした。実際にはシンボリックリンクを張っただけでは
> `industry_engine` 等の import は解決されず、`streamlit/` と `react-fastapi/backend/` に
> 残っていた**物理コピーの方が読み込まれ続けていました**。本ガイドは、実装を検証した上で
> 2026年7月に修正しています。

## 一本化の仕組み（sys.path ブートストラップ）

各アプリの最初期の起動コードで、以下のように `shared/` を `sys.path` の**末尾**に追加します。

```python
import sys
from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent / "shared"  # パスはアプリごとに異なる
if str(_SHARED_DIR) not in sys.path:
    sys.path.append(str(_SHARED_DIR))   # ← 必ず append。insert(0, ...) は禁止（後述）
```

実装箇所:

| アプリ | ファイル |
|---|---|
| Streamlit版 | `streamlit/startup/__init__.py`（`run()` が呼ばれる前、モジュール読み込み時に実行） |
| React+FastAPI版 | `react-fastapi/backend/main.py`（`api.routes` の import より前） |
| 各種テスト | `streamlit/tests/conftest.py`, `react-fastapi/backend/tests/conftest.py`（アプリ本体を経由しない単体テストのため個別に必要） |

**なぜ `insert(0, ...)` ではなく `append(...)` なのか**（重要）:

`shared/` には `db/` と `rag/` も参考として存在しますが、これらは下記の理由で
**アプリ側にも物理コピーを維持する必要があります**（一本化の対象外）。もし `shared/` を
`sys.path` の先頭に挿入すると、`import db` や `import rag` の名前解決が `shared/db/` /
`shared/rag/` に奪われてしまい、DB保存先が意図せず変わる、`rag.core` が見つからず
`ModuleNotFoundError` になる、といった事故につながります。必ずアプリ側の実装を
優先させるため、`shared/` は「アプリ側に存在しない名前だけを拾うフォールバック」として
末尾に追加してください。

## 一本化済み（shared/ の実体のみ、物理コピーなし）

| ファイル | 説明 |
|---------|------|
| `answer_assist.py` | 回答アシスト機能 |
| `industry_engine.py` | 業界別面接モード定義 |
| `mock_interview_engine.py` | AI模擬面接エンジン |
| `persona_engine.py` | 面接官ペルソナ管理 |
| `interview_engine.py` | 自己PR引き出しインタビューのテーマ制Q&Aエンジン（utils・prompts.interviewer にのみ依存） |
| `pr_generation.py` | 自己PR生成・評価・企業別カスタマイズ・微調整リライト（utils にのみ依存） |
| `summary_generation.py` | 面接サマリー（強み・弱み・業界フィット度）生成（utils にのみ依存） |
| `question_prediction.py` | 想定質問生成（自己PR・履歴書＋企業情報から模範回答例つき質問セットを生成。utils にのみ依存） |
| `personality_assessment.py` | 性格診断（ビッグファイブ30問・スコア集計・業界適性・AI結果生成。utils にのみ依存。React版移行時に一本化） |
| `company_matrix.py` | 企業比較マトリクス（志望動機一括生成・比較マトリクス・差別化ポイント生成。utils にのみ依存。React版移行時に一本化） |
| `career_advisor.py` | AIキャリアアドバイザーのプロンプト・LLM呼び出し（utils にのみ依存。コンテキスト構築はDB依存のためアプリ側に残す。React版移行時に一本化） |
| `prompts/` (5ファイル) | プロンプトテンプレート（他モジュールへの依存なし・完全に自己完結） |

これらのファイルは now **`shared/` にしか存在しません**。`streamlit/` や
`react-fastapi/backend/` に同名ファイルを新規作成しないでください（フォールバックが
機能しなくなるだけでなく、意図せず古い実装が復活し、再びズレの原因になります）。

## 管理対象外（アプリごとに物理コピーを維持・意図的な重複）

| ファイル/ディレクトリ | 理由 |
|---|---|
| `db/`（`database.py`, `session_repository.py`, `knowledge_base_repository.py`, `settings_repository.py`, `personality_repository.py`, `favorites_repository.py`, `__init__.py`） | パッケージ相対 import（`from db.database import ...` 等）はパッケージの `__init__.py` と同一ディレクトリ内でサブモジュールを探索するため、`db/` パッケージ全体を分割配置できない。さらに `database.py` はデフォルトDB保存先を `__file__` の場所から算出するため、アプリごとに物理的に独立している必要がある |
| `rag/__init__.py`, `rag/extraction.py`, `rag/persistence.py` | 同上の理由（`rag.__init__` が `from rag.core import ...` するため、`core.py` と同一ディレクトリに存在する必要がある） |
| `rag/core.py` | Streamlit/FastAPI間で埋め込みAPIの呼び出し方が異なる（Streamlit: 直接 `ollama.Client`、FastAPI: 接続プーリング付き `llm.ollama_client`）、正当な実装差分 |
| `utils.py` / `utils/` | Streamlit側はパッケージ化済み、FastAPI側は別管理。両者とも `industry_engine.py` 等から `from utils import ...` で参照されるが、これは通常のトップレベル import なので `sys.path` 上でどちらのアプリのものが見つかるかは問題にならない（各アプリ自身のディレクトリが `shared/` より先に解決されるため、意図通りアプリ固有の `utils` が使われる） |

`db/` と `rag/`（`core.py`除く）は**内容が完全に一致しているべき**ファイル群です。
`shared/db/`, `shared/rag/` に「参照用の正本」を置いていますが、実行時には読み込まれません
（読み込まれるのはアプリ側の物理コピー）。編集時は 3箇所（`shared/`, `streamlit/`,
`react-fastapi/backend/`）を手動で同期してください。ズレがないか確認するには:

```bash
diff shared/db/database.py streamlit/db/database.py
diff shared/db/database.py react-fastapi/backend/db/database.py
diff shared/rag/extraction.py streamlit/rag/extraction.py
diff shared/rag/extraction.py react-fastapi/backend/rag/extraction.py
diff shared/rag/persistence.py streamlit/rag/persistence.py
diff shared/rag/persistence.py react-fastapi/backend/rag/persistence.py
# db/session_repository.py, knowledge_base_repository.py, settings_repository.py,
# personality_repository.py, favorites_repository.py, __init__.py, rag/__init__.py も同様に確認
```

## セットアップ手順（新規クローン時）

シンボリックリンクは「`shared/` の実体がどこにあるか」を分かりやすくするための補助であり、
import解決そのものは sys.path ブートストラップが担っています。念のため両方セットアップします。

```bash
# Streamlit側
cd interview_app/streamlit
ln -s ../shared shared

# FastAPI側
cd interview_app/react-fastapi/backend
ln -s ../../shared shared
```

## 開発時のルール

- 「一本化済み」の5ファイルを編集する場合は `shared/` のファイルのみを編集する。
  `streamlit/` や `react-fastapi/backend/` に同名ファイルは存在しないはずなので、
  誤って新規作成しないよう注意する。
- 「管理対象外」の `db/` パッケージ・`rag/`（`core.py`除く）を編集する場合は、
  3箇所すべてに同じ変更を反映し、上記の `diff` コマンドでズレがないことを確認する。
- 新しい共有ロジックを追加する場合、そのファイルが `db.database` や `rag.core` のような
  アプリ固有の兄弟モジュールに依存していないか確認する。依存していなければ `shared/` に
  直接置いて一本化できる。依存していれば `db/`・`rag/` と同様、アプリごとに物理コピーが
  必要になる。
