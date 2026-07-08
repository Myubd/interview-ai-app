"""
api/routes/setup_progress.py
-----------------------------
Ollama セットアップの進捗を SSE（Server-Sent Events）で配信するエンドポイント。

GET /api/v1/setup/progress
  → text/event-stream でセットアップログを順次送信する。
    セットアップ完了時に {"done": true} を送って接続を閉じる。

GET /api/v1/setup/status
  → セットアップの現在状態を JSON で返す（ポーリング用）。
"""
from __future__ import annotations

import asyncio
import json
import os
import queue

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# launch_fastapi が注入するグローバルオブジェクトをインポート
# （開発時に直接 uvicorn で起動する場合は空のダミーを使う）
#
# 注意: launch_fastapi.py はただ import しただけでは _ensure_ollama() が
# 実行されず、setup_done が永遠にセットされない。実際に launch_fastapi.py
# 経由で起動された場合にだけ LAUNCH_FASTAPI_ORCHESTRATED 環境変数が
# セットされるので、それを見て本当にオーケストレーションされているかを判定する。
try:
    if os.environ.get("LAUNCH_FASTAPI_ORCHESTRATED") != "1":
        raise ImportError("launch_fastapi module present but not orchestrating this process")
    import launch_fastapi as _launcher
    _progress_queue: queue.Queue = _launcher.setup_progress_queue
    _done_event = _launcher.setup_done
    _error_event = _launcher.setup_error
except ImportError:
    import threading
    _progress_queue = queue.Queue()
    _done_event = threading.Event()
    _error_event = threading.Event()
    _done_event.set()   # 開発時（uvicorn直接起動）はセットアップ済み扱い

router = APIRouter()


class SetupStatus(BaseModel):
    done: bool
    error: bool


@router.get(
    "/setup/status",
    response_model=SetupStatus,
    summary="セットアップ状態確認",
    description="Ollama セットアップが完了しているかポーリングで確認します。",
    tags=["setup"],
)
async def get_setup_status() -> SetupStatus:
    return SetupStatus(
        done=_done_event.is_set(),
        error=_error_event.is_set(),
    )


@router.get(
    "/setup/progress",
    summary="セットアップ進捗（SSE）",
    description=(
        "Ollama のインストール・モデルダウンロードの進捗を "
        "Server-Sent Events でリアルタイム配信します。\n\n"
        "セットアップ完了時に `event: done` を送信して接続を閉じます。"
    ),
    tags=["setup"],
)
async def stream_setup_progress() -> StreamingResponse:
    async def _generator():
        loop = asyncio.get_event_loop()

        while True:
            # キューからメッセージを非同期で取り出す
            try:
                msg = await loop.run_in_executor(
                    None,
                    lambda: _progress_queue.get(timeout=0.3),
                )
                data = json.dumps(msg, ensure_ascii=False)
                yield f"event: log\ndata: {data}\n\n"
            except queue.Empty:
                pass

            # 完了 or エラーでキューが空になったら終了
            if (_done_event.is_set() or _error_event.is_set()) and _progress_queue.empty():
                status = "error_event" if _error_event.is_set() else "done"
                yield f"event: {status}\ndata: {{}}\n\n"
                return

            # ハートビート（接続維持）
            yield ": heartbeat\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
