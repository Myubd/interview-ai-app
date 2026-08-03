"""
service_auth.py
-----------------
このサービス単体(gatewayを経由しない直接アクセス)を保護するための、
最小限の認証。health-support/study-support/archlife-fastapiに追加した
ものと全く同じ設計。

背景:
- main.pyのOpenAPI descriptionには長らく「現バージョンは認証なし
  （ローカル専用）」と書かれていたが、docker-compose.yml では個別に
  ホストへポート公開しており(直接デバッグ・単体exe用途)、
  「ローカル専用」が「同一マシン上の誰でもアクセス可能」を意味して
  しまっていた。gatewayが唯一の入口という設計を保つため、本サービス
  自身でも最低限の検証を行う。

設計方針(新しい認証の仕組みは増やさない):
- gatewayが発行する `gw_session` Cookie(値は GATEWAY_AUTH_TOKEN と
  同じ共有シークレット)をそのまま検証するだけ。
- gateway経由のリクエストは、gatewayの `_proxy()` がCookieヘッダーを
  含む全ヘッダーを転送するため、追加の変更なしにそのまま認証が通る。
- ログイン/ログアウトのエンドポイントはこのサービスには持たせない
  (ログインは常にgateway側で行う。ここは検証のみ)。
- GATEWAY_AUTH_TOKEN が未設定の場合は、起動を拒否する(安全側にフェイル)。
- 単体exe配布(launch_fastapi.py)でgateway自体を経由しない使い方も
  想定されるため、その場合はこのミドルウェア自体をスキップできるように
  しておく。判定には新しいフラグを増やさず、launch_fastapi.py が既に
  設定している `LAUNCH_FASTAPI_ORCHESTRATED=1`(api/routes/setup_progress.py
  も同じフラグで「単体exe起動かどうか」を判定している)をそのまま使う。
"""
from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

SESSION_COOKIE_NAME = "gw_session"

# API以外(SPAの静的シェル・/docs等)は認証対象外にする。
# 実データは "/api/*" 配下のエンドポイントで守る。
_PUBLIC_EXACT_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/v1/health"}


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT_PATHS:
        return True
    # "/api/" 以外(SPAの静的シェル・アセット類)は公開のままにする。
    # gatewayの"/"公開ポリシーと同じ考え方。
    return not path.startswith("/api/")


def is_standalone_mode() -> bool:
    """単体exe配布(launch_fastapi.py経由・gatewayを経由しない使い方)向けの
    明示的な無効化フラグ。launch_fastapi.py が設定する既存の
    LAUNCH_FASTAPI_ORCHESTRATED をそのまま流用する(新しいフラグを増やさない)。
    """
    return os.environ.get("LAUNCH_FASTAPI_ORCHESTRATED") == "1"


def get_auth_token() -> str:
    token = os.environ.get("GATEWAY_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError(
            "GATEWAY_AUTH_TOKEN が設定されていません。このサービスはホストへ"
            "個別ポート公開されており、無防備なまま起動しないようにこの"
            "チェックを入れています。gateway統合で使う場合はgatewayと同じ値の"
            "GATEWAY_AUTH_TOKEN を設定してください。単体exeとして意図的に"
            "gatewayを経由しない使い方をする場合は、代わりに"
            "INTERVIEW_APP_STANDALONE=1 を設定してください。"
        )
    return token


def _is_authenticated(request: Request) -> bool:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not cookie_value:
        return False
    # タイミング攻撃を避けるため定数時間比較を使う(gatewayのauth.pyと同じ)
    return hmac.compare_digest(cookie_value, get_auth_token())


async def service_auth_middleware(request: Request, call_next):
    if is_standalone_mode():
        return await call_next(request)

    if request.method == "OPTIONS" or _is_public(request.url.path):
        return await call_next(request)

    if not _is_authenticated(request):
        return JSONResponse(
            status_code=401,
            content={
                "detail": (
                    "認証が必要です。http://localhost:3000 (gateway) から"
                    "ログインしてください。"
                )
            },
        )
    return await call_next(request)
