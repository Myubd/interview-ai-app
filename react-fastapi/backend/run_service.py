"""
run_service.py
----------------
interview_app backend の、gateway統合exe向けの最小ランチャー。

このファイルは launch_fastapi.py(単体exe配布・方式B)とは別物。
launch_fastapi.py はOllamaのインストール確認・モデル管理・ブラウザ起動まで
自分で行う「フル装備」のランチャーだが、gateway統合exe(方式A)では
それら全部をgateway自身(launch_gateway.py)が1回だけ行うため、
ここではuvicornの起動だけを行う軽量版にしている。

archlife-fastapi/launch_fastapi.py と同じ契約(PORT/DATA_DIRを環境変数で
受け取る)にしている。

launch_gateway.py側との約束事:
  - 環境変数 PORT: 待ち受けポート(既定 8000)
  - 環境変数 DATA_DIR: career_support.db の保存先ディレクトリ
  - 環境変数 GATEWAY_AUTH_TOKEN: service_auth.py が検証する共有シークレット
    (LAUNCH_FASTAPI_ORCHESTRATED は立てない = 認証は有効なまま)
  - 環境変数 OLLAMA_HOST: 既定 http://localhost:11434 のまま
"""
from __future__ import annotations

import multiprocessing
import os

from local_ai_core import launcher_kit as lk

if __name__ == "__main__":
    multiprocessing.freeze_support()


def main() -> None:
    lk.hide_console_window()
    lk.fix_stdio()
    lk.suppress_child_console()

    port = int(os.environ.get("PORT", "8000"))
    data_dir = os.environ.get("DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lifesupportos")
    os.makedirs(data_dir, exist_ok=True)

    os.environ.setdefault("INTERVIEW_DB_PATH", os.path.join(data_dir, "career_support.db"))
    os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")

    lk.kill_existing_process(port)

    print(f"[interview_backend] starting on 127.0.0.1:{port}", flush=True)
    print(f"[interview_backend] db path: {os.environ['INTERVIEW_DB_PATH']}", flush=True)

    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="warning", loop="asyncio")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            lk.fix_stdio()
        except Exception:
            pass
        lk.write_crash_log("LifeSupportOS", "interview_backend run_service.py の main()内で例外が発生しました", e)
        raise
