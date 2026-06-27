# -*- coding: utf-8 -*-
"""
tests/test_json_parse.py
-------------------------
utils._clean_json_raw / validate_json_schema のユニットテスト。

LLM出力に含まれる「コードブロック・前置き文・余分なテキスト」を正しく除去して
JSON本体を取り出せるか、またスキーマ検証が期待通り動くかを確認する。
"""
from __future__ import annotations

import json

import pytest

from utils import _clean_json_raw, validate_json_schema


# ============================================================
# _clean_json_raw
# ============================================================

class TestCleanJsonRaw:
    """LLM出力の前処理関数のテスト。"""

    def test_plain_json_object(self):
        """素のJSONオブジェクトはそのまま返る。"""
        raw = '{"continue": true, "question": "テスト"}'
        result = _clean_json_raw(raw)
        assert json.loads(result) == {"continue": True, "question": "テスト"}

    def test_plain_json_array(self):
        """素のJSON配列はそのまま返る。"""
        raw = '[{"q": "質問1"}, {"q": "質問2"}]'
        result = _clean_json_raw(raw)
        assert json.loads(result) == [{"q": "質問1"}, {"q": "質問2"}]

    def test_strip_markdown_code_block_json(self):
        """```json ... ``` で囲まれた出力からJSON本体を取り出せる。"""
        raw = '```json\n{"key": "value"}\n```'
        result = _clean_json_raw(raw)
        assert json.loads(result) == {"key": "value"}

    def test_strip_markdown_code_block_plain(self):
        """``` ... ``` で囲まれた出力（json ラベルなし）からJSON本体を取り出せる。"""
        raw = '```\n{"foo": 42}\n```'
        result = _clean_json_raw(raw)
        assert json.loads(result) == {"foo": 42}

    def test_strip_preamble_text(self):
        """前置きテキストがあってもJSON部分だけ返る。"""
        raw = 'もちろんです。以下がJSONです:\n{"answer": "はい"}'
        result = _clean_json_raw(raw)
        assert json.loads(result) == {"answer": "はい"}

    def test_strip_trailing_text(self):
        """後置きテキストがあってもJSON部分だけ返る。"""
        raw = '{"score": 5}\n以上になります。'
        result = _clean_json_raw(raw)
        assert json.loads(result) == {"score": 5}

    def test_nested_json_object(self):
        """ネストしたJSONオブジェクトも正しく抽出できる。"""
        raw = '```json\n{"scores": {"論理構成": 4, "具体性": 3}}\n```'
        result = _clean_json_raw(raw)
        parsed = json.loads(result)
        assert parsed["scores"]["論理構成"] == 4

    def test_json_with_japanese_values(self):
        """日本語の値を含むJSONも正しく処理できる。"""
        raw = '{"question": "あなたの強みを教えてください。"}'
        result = _clean_json_raw(raw)
        assert json.loads(result)["question"] == "あなたの強みを教えてください。"

    def test_empty_string(self):
        """空文字列は空文字列のまま返る（JSON解析エラーはこのレイヤーでは起こらない）。"""
        result = _clean_json_raw("")
        assert result == ""

    def test_only_preamble_no_json(self):
        """JSONブラケットがない純粋なテキストはそのまま返る。"""
        raw = "すみません、エラーが発生しました。"
        result = _clean_json_raw(raw)
        # {} も [] もないのでそのまま返るはず
        assert "{" not in result or result == raw

    def test_boolean_values(self):
        """true/false のJSONブール値が正しく解析される。"""
        raw = '{"continue": false, "question": ""}'
        result = _clean_json_raw(raw)
        parsed = json.loads(result)
        assert parsed["continue"] is False

    def test_array_inside_code_block(self):
        """配列もコードブロックから正しく取り出せる。"""
        raw = '```json\n[{"q": "Q1", "a": "A1"}, {"q": "Q2", "a": "A2"}]\n```'
        result = _clean_json_raw(raw)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["q"] == "Q1"

    def test_multiline_json(self):
        """整形された複数行JSONも正しく扱える。"""
        raw = """```json
{
  "overall_summary": "良好な面接でした。",
  "scores": {"論理構成": 4},
  "top_strengths": ["明確な説明", "具体的なエピソード"]
}
```"""
        result = _clean_json_raw(raw)
        parsed = json.loads(result)
        assert parsed["scores"]["論理構成"] == 4
        assert "明確な説明" in parsed["top_strengths"]

    def test_object_preferred_over_array_when_both_present(self):
        """{ が [ より先にある場合はオブジェクトとして解釈される。"""
        raw = '{"key": ["item1", "item2"]}'
        result = _clean_json_raw(raw)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["key"] == ["item1", "item2"]


# ============================================================
# validate_json_schema
# ============================================================

class TestValidateJsonSchema:
    """スキーマ検証関数のテスト。"""

    def test_valid_object_with_required_keys(self):
        """必須キーが全て揃っている場合は True を返す。"""
        data = {"continue": True, "question": "次の質問"}
        assert validate_json_schema(data, ["continue", "question"]) is True

    def test_missing_required_key(self):
        """必須キーが欠けている場合は False を返す。"""
        data = {"continue": True}
        assert validate_json_schema(data, ["continue", "question"]) is False

    def test_empty_required_keys(self):
        """必須キーリストが空なら任意の dict で True になる。"""
        assert validate_json_schema({"any": "value"}, []) is True

    def test_type_check_passes(self):
        """型チェックが通る場合は True を返す。"""
        data = {"continue": False, "question": "質問文"}
        assert validate_json_schema(
            data,
            required_keys=["continue", "question"],
            type_checks={"continue": bool, "question": str},
        ) is True

    def test_type_check_fails_wrong_type(self):
        """型が一致しない場合は False を返す。"""
        data = {"continue": "true", "question": "質問文"}  # continue は str (誤り)
        assert validate_json_schema(
            data,
            required_keys=["continue", "question"],
            type_checks={"continue": bool},
        ) is False

    def test_not_a_dict_returns_false(self):
        """dict でないデータ（list 等）は False を返す。"""
        assert validate_json_schema([], ["key"]) is False  # type: ignore[arg-type]
        assert validate_json_schema("string", []) is False  # type: ignore[arg-type]

    def test_extra_keys_are_allowed(self):
        """余分なキーがあっても必須キーが揃っていれば True を返す。"""
        data = {"continue": True, "question": "Q", "extra": "ignored"}
        assert validate_json_schema(data, ["continue", "question"]) is True

    def test_type_check_only_for_existing_keys(self):
        """type_checks に指定されたキーがデータに存在しない場合はスキップ（True）。"""
        data = {"continue": True}   # question キーなし
        # required_keys に question が含まれていないので必須チェックは通る
        # type_checks の question は存在しないキーなのでスキップ
        assert validate_json_schema(
            data,
            required_keys=["continue"],
            type_checks={"question": str},  # question はデータにない → スキップ
        ) is True

    def test_interview_engine_schema(self):
        """interview_engine が期待するスキーマの正常ケース。"""
        data = {"continue": False, "question": ""}
        assert validate_json_schema(
            data,
            required_keys=["continue", "question"],
            type_checks={"continue": bool},
        ) is True

    def test_mock_evaluation_schema_partial(self):
        """模擬面接評価の主要キーが揃っている場合は True。"""
        data = {
            "overall_summary": "良好でした。",
            "scores": {"論理構成": 4, "具体性": 3},
            "top_strengths": ["強み1"],
            "top_improvements": ["改善点1"],
            "model_answers": [{"question": "Q", "model_answer": "A"}],
            "next_practice_points": ["ポイント1"],
        }
        required = [
            "overall_summary", "scores", "top_strengths",
            "top_improvements", "model_answers", "next_practice_points",
        ]
        assert validate_json_schema(data, required) is True
