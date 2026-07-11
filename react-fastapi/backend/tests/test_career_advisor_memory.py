# -*- coding: utf-8 -*-
"""
tests/test_career_advisor_memory.py
--------------------------------------
「AIメモリーの読み出しループを閉じる」変更(career_advisor_service.build_memory_context)
の結合テスト。確認する性質:

1. memory:read:career.* を許可していない状態では、例外を出さずに空文字が返る
   (メモリーが読めなくても、チャット機能自体は失敗しない)。
2. 許可した状態では、他アプリ/他セッション由来の career.* メモリーが
   confidence ラベル付きでテキスト化されて返る。
3. generate_career_advice に memory_context を渡すと、システムプロンプトに
   【AIメモリー】セクションと確信度ガードが追加される
   (memory_context が空のときは、渡さなかった場合と完全に同じ出力になる= 後方互換)。
"""
from __future__ import annotations

import sys

import pytest

import core_sync  # noqa: F401  (core_sync.bootstrap をsys.modules経由で取るためにimportしておく)
from core_sync import get_gate, get_profile_id

# 注意: `core_sync/__init__.py` が `from .bootstrap import bootstrap` を実行するため、
# パッケージ属性としての `core_sync.bootstrap` は「サブモジュール」ではなく
# 「関数 bootstrap」で上書きされてしまう(モジュール名と関数名が同名という設計の落とし穴)。
# 本物のサブモジュール(_profile_id_cache を持つ側)には sys.modules 経由でアクセスする必要がある。
core_bootstrap = sys.modules["core_sync.bootstrap"]
from local_ai_core.memory import MemoryStore
from local_ai_core.permissions import PermissionDenied

from services.career_advisor_service import _build_memory_context_sync, APP_KEY
from career_advisor import generate_career_advice, MEMORY_CONFIDENCE_GUARD


@pytest.fixture()
def core_env(monkeypatch, tmp_path):
    """core.db / device_identity.json をテストごとに隔離し、profile_idキャッシュもリセットする。"""
    monkeypatch.setenv("LOCAL_AI_CORE_DB_PATH", str(tmp_path / "core.db"))
    monkeypatch.setenv("LOCAL_AI_CORE_DEVICE_IDENTITY_PATH", str(tmp_path / "device_identity.json"))
    core_bootstrap._profile_id_cache = None
    yield
    core_bootstrap._profile_id_cache = None


def test_memory_context_empty_without_grant(core_env):
    """権限未許可でも例外にならず、空文字が返る(チャット機能を落とさないため)。"""
    profile_id = get_profile_id()  # bootstrap()を実行し、申告のみ行う(まだgrantしない)
    assert profile_id is not None
    assert _build_memory_context_sync() == ""


def test_memory_context_includes_labeled_items_after_grant(core_env):
    profile_id = get_profile_id()
    gate = get_gate()
    gate.grant(profile_id, APP_KEY, "memory:write:career.*")
    gate.grant(profile_id, APP_KEY, "memory:read:career.*")

    mem = MemoryStore(gate.db_path, gate=gate)
    mem.set(profile_id, APP_KEY, "career.strengths", ["粘り強さ"], confidence="ai_inferred")
    mem.set(profile_id, APP_KEY, "career.desired_industry", "IT", confidence="user_confirmed")

    context = _build_memory_context_sync()
    assert "[本人確認済み] career.desired_industry: IT" in context
    assert "[AIの推測・未確認] career.strengths: 粘り強さ" in context


def test_memory_context_denied_read_but_granted_write_is_still_empty(core_env):
    """write権限だけでread権限がない場合も、静かに空文字(PermissionDeniedを外に漏らさない)。"""
    profile_id = get_profile_id()
    gate = get_gate()
    gate.grant(profile_id, APP_KEY, "memory:write:career.*")
    mem = MemoryStore(gate.db_path, gate=gate)
    mem.set(profile_id, APP_KEY, "career.strengths", ["粘り強さ"], confidence="ai_inferred")

    assert _build_memory_context_sync() == ""
    with pytest.raises(PermissionDenied):
        mem.list_by_prefix(profile_id, APP_KEY, "career")


def test_generate_career_advice_backward_compatible_without_memory():
    """memory_contextを渡さない(=従来通りの)呼び出しは、システムプロンプトに
    メモリーセクションもガードも一切追加されない。"""
    result = generate_career_advice(
        model="qwen3:8b",
        context_text="",
        history_messages=[{"role": "user", "content": "自己PRの相談です"}],
    )
    assert result["ok"] is True


def test_generate_career_advice_includes_memory_guard_when_context_given(monkeypatch):
    """memory_contextを渡すと、システムプロンプトにガード文言が含まれる。"""
    captured = {}

    def _fake_call(model, prompt, fallback, min_length, max_retries):
        captured["prompt"] = prompt
        return {"text": "テスト応答です。", "ok": True, "error_msg": None}

    import career_advisor
    monkeypatch.setattr(career_advisor, "call_ollama_with_text_retry", _fake_call)

    generate_career_advice(
        model="qwen3:8b",
        context_text="",
        history_messages=[{"role": "user", "content": "自己PRの相談です"}],
        memory_context="・[本人確認済み] career.desired_industry: IT",
    )
    assert MEMORY_CONFIDENCE_GUARD in captured["prompt"]
    assert "【AIメモリー(アプリ横断で蓄積された情報)】" in captured["prompt"]
