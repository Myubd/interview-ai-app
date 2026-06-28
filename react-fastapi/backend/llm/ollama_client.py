# -*- coding: utf-8 -*-
"""
llm/ollama_client.py
---------------------
Ollamaクライアントのシングルトン管理モジュール。

モンキーパッチ（ollama.chat = client.chat）の代わりに、
このモジュールから get_client() でクライアントを取得して使う。
これにより import 順序に依存しない安全な設計になる。

[変更点]
- 設定画面で OLLAMA_HOST を変更した際、プロセス再起動なしに即時反映されるよう改善。
  以前は起動時に環境変数を一度だけ読んでシングルトンをキャッシュしていたため、
  DB 上のホスト設定を変えても反映されなかった。

  新しい戦略:
    1. get_client() 呼び出し時に DB（settings テーブル）からホストを取得する。
    2. 前回と同じホストであればキャッシュ済みのクライアントを再利用する（パフォーマンス維持）。
    3. ホストが変わっていれば新しいクライアントを生成してキャッシュを更新する。

  これにより、設定変更 → 即座に反映 かつ 毎回インスタンス生成しないという
  両立が実現できる。

- reset_client() を公開 API として追加。
  テスト・再接続などで強制リセットしたい場合に使う。

使用方法:
    from llm.ollama_client import get_client

    client = get_client()
    response = client.chat(model=..., messages=..., format="json")
    vec = client.embeddings(model=..., prompt=...)
"""
from __future__ import annotations

import logging
import os

import ollama

logger = logging.getLogger(__name__)

# 環境変数から読んだフォールバックホスト（DB に設定がない場合に使用）
_ENV_OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# キャッシュ状態
_client: ollama.Client | None = None
_cached_host: str | None = None  # 直前に使ったホスト。差分検知に使う


def _resolve_host() -> str:
    """使用すべき Ollama ホストを解決する。

    優先順位:
        1. DB（settings テーブル）の "ollama_host" キー
        2. 環境変数 OLLAMA_HOST
        3. デフォルト "http://localhost:11434"

    DB アクセスは軽量な SQLite SELECT 1 回なので、呼び出しごとに行っても
    パフォーマンス上の問題はない。
    """
    try:
        # 循環 import を避けるため関数内で遅延 import する
        from db.settings_repository import get_setting
        db_host = get_setting("ollama_host")
        if db_host and db_host.strip():
            return db_host.strip()
    except Exception:
        # DB が初期化前（起動直後など）でも動作できるよう例外を握りつぶす
        logger.debug("_resolve_host: DB からホストを取得できませんでした。環境変数を使用します。")
    return _ENV_OLLAMA_HOST


def get_client() -> ollama.Client:
    """Ollamaクライアントを返す。

    ホストが変わっていなければキャッシュ済みインスタンスを再利用し、
    変わっていれば新しいインスタンスを生成してキャッシュを更新する。
    """
    global _client, _cached_host

    current_host = _resolve_host()

    if _client is None or current_host != _cached_host:
        if _cached_host is not None and current_host != _cached_host:
            logger.info(
                "Ollama ホストが変更されました: %s → %s。クライアントを再生成します。",
                _cached_host,
                current_host,
            )
        _client = ollama.Client(host=current_host)
        _cached_host = current_host

    return _client


def reset_client() -> None:
    """キャッシュ済みクライアントを強制リセットする。

    次回の get_client() 呼び出しで新しいインスタンスが生成される。
    テスト・強制再接続などに使う。
    """
    global _client, _cached_host
    _client = None
    _cached_host = None
    logger.debug("Ollama クライアントをリセットしました。")
