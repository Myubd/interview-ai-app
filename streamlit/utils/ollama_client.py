"""
utils/ollama_client.py
-----------------------
Ollama LLM呼び出し・リトライ・JSONスキーマ検証ユーティリティ。

提供するもの:
    _clean_json_raw()                   - LLM出力からJSON本体を抽出
    validate_json_schema()              - 必須キー・型チェック
    call_ollama_with_json_retry()       - JSONオブジェクト返答・リトライ付き
    call_ollama_with_json_array_retry() - JSON配列返答・リトライ付き
    call_ollama_with_text_retry()       - 自由テキスト返答・リトライ付き

[ホスト設定]
    環境変数 OLLAMA_HOST でOllamaのエンドポイントを切り替えられる。
    未設定時は http://localhost:11434 を使用する。
    例: OLLAMA_HOST=http://192.168.1.10:11434 streamlit run app.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import ollama

logger = logging.getLogger(__name__)

# ============================================================
# Ollamaクライアント（OLLAMA_HOST 環境変数対応）
# ============================================================
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_ollama_client = ollama.Client(host=_OLLAMA_HOST)


# ============================================================
# 内部ヘルパー
# ============================================================

def _clean_json_raw(raw: str) -> str:
    """LLM出力からコードブロック・前置き文を除去してJSON本体を取り出す。"""
    # コードブロック除去
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    # 最初の { または [ から最後の } または ] まで
    starts = [(cleaned.find("{"), "{"), (cleaned.find("["), "[")]
    starts = [(i, c) for i, c in starts if i != -1]
    if not starts:
        return cleaned
    start_idx, start_char = min(starts, key=lambda x: x[0])
    end_char = "}" if start_char == "{" else "]"
    end_idx = cleaned.rfind(end_char)
    if end_idx == -1 or end_idx < start_idx:
        return cleaned
    return cleaned[start_idx : end_idx + 1]


def validate_json_schema(
    data: dict,
    required_keys: list[str],
    type_checks: dict[str, type] | None = None,
) -> bool:
    """必須キーの存在と型（オプション）を検証する。"""
    if not isinstance(data, dict):
        return False
    for key in required_keys:
        if key not in data:
            return False
    if type_checks:
        for key, expected_type in type_checks.items():
            if key in data and not isinstance(data[key], expected_type):
                return False
    return True


# ============================================================
# 公開API
# ============================================================

def call_ollama_with_json_retry(
    model: str,
    prompt: str,
    required_keys: list[str],
    type_checks: dict[str, type] | None = None,
    fallback: dict | None = None,
    max_retries: int = 2,
    retry_wait_sec: float = 0.5,
) -> dict:
    """JSONを期待するOllama呼び出しを、スキーマ検証付きでリトライする。

    Args:
        model: Ollamaモデル名
        prompt: ユーザーメッセージ（システムプロンプト込みの完成形プロンプト）
        required_keys: 必須キーのリスト
        type_checks: {key: expected_type} の型チェック辞書（省略可）
        fallback: 最終失敗時のデフォルト値（Noneの場合は空dict）
        max_retries: 最大リトライ回数（初回を含まない）
        retry_wait_sec: リトライ間隔（秒）

    Returns:
        dict に "ok" (bool) と "error_msg" (str | None) を追加したもの。
        ok=False の場合は fallback の内容に ok/error_msg を追記して返す。
    """
    if fallback is None:
        fallback = {}

    _RETRY_SUFFIX = (
        "\n\n⚠️ 前回の出力はJSONとして正しく解析できませんでした。"
        "今度は必ずJSON形式のみで出力してください。前置き・説明・Markdownのコードブロック記号（```）は一切不要です。"
    )

    last_error: str = ""
    for attempt in range(max_retries + 1):
        effective_prompt = prompt if attempt == 0 else prompt + _RETRY_SUFFIX
        try:
            # format="json" でOllama側にもJSON出力モードを要求する。
            # プロンプト側の指示と二重になるが、対応モデルでは出力が崩れにくくなり
            # リトライ発生率を下げられる（非対応モデルでも無視されるだけで実害はない）。
            response = _ollama_client.chat(
                model=model,
                messages=[{"role": "user", "content": effective_prompt}],
                format="json",
            )
            raw = response["message"]["content"]
            json_str = _clean_json_raw(raw)
            data = json.loads(json_str)

            if not validate_json_schema(data, required_keys, type_checks):
                missing = [k for k in required_keys if k not in data]
                last_error = f"必須キーが不足しています: {missing}。LLM出力: {raw[:200]}"
                if attempt < max_retries:
                    time.sleep(retry_wait_sec)
                continue

            return {**data, "ok": True, "error_msg": None}

        except json.JSONDecodeError as e:
            last_error = f"JSONパースエラー: {e}"
        except Exception as e:
            last_error = f"Ollama呼び出しエラー: {e}"
            logger.warning("Ollama呼び出しエラー (attempt %d)", attempt, exc_info=True)

        if attempt < max_retries:
            time.sleep(retry_wait_sec)

    return {**fallback, "ok": False, "error_msg": last_error}


def call_ollama_with_json_array_retry(
    model: str,
    prompt: str,
    item_required_keys: list[str],
    fallback: list | None = None,
    max_retries: int = 2,
    retry_wait_sec: float = 0.5,
) -> tuple[list, bool, str | None]:
    """JSON配列を期待するOllama呼び出しを、スキーマ検証付きでリトライする。

    generate_pr_variants のように出力がリスト形式の場合に使用する。

    Args:
        model: Ollamaモデル名
        prompt: プロンプト文字列
        item_required_keys: 配列の各要素（dict）が持つべき必須キーのリスト
        fallback: 最終失敗時のデフォルトリスト（Noneの場合は空リスト）
        max_retries: 最大リトライ回数（初回を含まない）
        retry_wait_sec: リトライ間隔（秒）

    Returns:
        (data: list, ok: bool, error_msg: str | None) のタプル
    """
    if fallback is None:
        fallback = []

    _RETRY_SUFFIX = (
        "\n\n⚠️ 前回の出力はJSON配列として正しく解析できませんでした。"
        "今度は必ずJSON配列形式のみで出力してください。前置き・説明・Markdownのコードブロック記号（```）は一切不要です。"
    )

    last_error: str = ""
    for attempt in range(max_retries + 1):
        effective_prompt = prompt if attempt == 0 else prompt + _RETRY_SUFFIX
        try:
            response = _ollama_client.chat(
                model=model,
                messages=[{"role": "user", "content": effective_prompt}],
                format="json",
            )
            raw = response["message"]["content"]
            json_str = _clean_json_raw(raw)
            data = json.loads(json_str)

            if not isinstance(data, list):
                last_error = f"配列形式ではありません。LLM出力: {raw[:200]}"
                if attempt < max_retries:
                    time.sleep(retry_wait_sec)
                continue

            # 各要素の必須キーを検証
            invalid_items = [
                i for i, item in enumerate(data)
                if not isinstance(item, dict) or any(k not in item for k in item_required_keys)
            ]
            if invalid_items:
                last_error = f"配列要素 {invalid_items} に必須キーが不足しています。LLM出力: {raw[:200]}"
                if attempt < max_retries:
                    time.sleep(retry_wait_sec)
                continue

            return data, True, None

        except json.JSONDecodeError as e:
            last_error = f"JSONパースエラー: {e}"
        except Exception as e:
            last_error = f"Ollama呼び出しエラー: {e}"
            logger.warning("Ollama呼び出しエラー (attempt %d)", attempt, exc_info=True)

        if attempt < max_retries:
            time.sleep(retry_wait_sec)

    return fallback, False, last_error


def call_ollama_with_text_retry(
    model: str,
    prompt: str,
    fallback: str = "",
    min_length: int = 1,
    max_retries: int = 1,
    retry_wait_sec: float = 0.5,
) -> dict:
    """自由テキスト出力（JSON形式を要求しない）を期待するOllama呼び出しを、
    軽量なリトライ・空応答チェック付きで行う。

    Args:
        model: Ollamaモデル名
        prompt: 完成済みプロンプト文字列
        fallback: 最終失敗時に返す値（例: リライト前の元テキスト）
        min_length: 出力が「有効」と見なす最小文字数
        max_retries: 最大リトライ回数（初回を含まない）
        retry_wait_sec: リトライ間隔（秒）

    Returns:
        {"text": str, "ok": bool, "error_msg": str | None}
    """
    last_error: str = ""
    for attempt in range(max_retries + 1):
        try:
            response = _ollama_client.chat(model=model, messages=[{"role": "user", "content": prompt}])
            text = response["message"]["content"].strip()
            if len(text) < min_length:
                last_error = f"出力が空または短すぎます（{len(text)}文字）。"
                if attempt < max_retries:
                    time.sleep(retry_wait_sec)
                continue
            return {"text": text, "ok": True, "error_msg": None}
        except Exception as e:
            last_error = f"Ollama呼び出しエラー: {e}"
            logger.warning("Ollama呼び出しエラー (attempt %d)", attempt, exc_info=True)
            if attempt < max_retries:
                time.sleep(retry_wait_sec)

    return {"text": fallback, "ok": False, "error_msg": last_error}
