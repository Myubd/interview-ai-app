"""
utils/interview_helpers.py
---------------------------
面接官インタビュー共通プロンプト部品。

interview_engine.py / mock_interview_engine.py で共有するロジック。

提供するもの:
    polish_interviewer_japanese() - 面接官AIが出しやすい不自然な日本語を軽く整える
    format_theme_history()        - テーマ内会話履歴をプロンプト埋め込み用テキストに整形
"""

from __future__ import annotations

import re

from utils.sanitizer import sanitize_user_input


# ============================================================
# 公開API
# ============================================================

def polish_interviewer_japanese(text: str) -> str:
    """面接官AIが出しやすい不自然な日本語だけを、意味を変えずに軽く整える。"""
    if not text:
        return ""

    replacements = [
        ("現在お世話になっている学校", "現在通っている学校"),
        ("学校と学部、そして少しでもお話しできる雰囲気を教えていただけますか", "大学・学部・専攻と、これまで力を入れてきたことを簡単に教えていただけますか"),
        ("学校と学部、そして少しでもお話しできる雰囲気を教えてください", "大学・学部・専攻と、これまで力を入れてきたことを簡単に教えてください"),
        ("少しでもお話しできる雰囲気", "自己紹介として話しやすいこと"),
        ("お話しできる雰囲気を教えていただけますか", "自己紹介として話しやすいことを簡単に教えていただけますか"),
        ("お話しできる雰囲気を教えてください", "自己紹介として話しやすいことを簡単に教えてください"),
        ("お話しできる雰囲気", "話しやすいこと"),
        ("学校と学部、そして", "学校や学部に加えて、"),
    ]
    polished = text.strip()
    for old, new in replacements:
        polished = polished.replace(old, new)
    polished = re.sub(r"、\s*、+", "、", polished)
    return polished


def format_theme_history(theme_messages: list[dict]) -> str:
    """1テーマ内の面接官・学生のやり取りを、プロンプト埋め込み用のテキストに整形する。

    学生発言（role == "user"）はプロンプトに埋め込む直前の再サニタイズとして
    sanitize_user_input() を通す（呼び出し元で既にサニタイズ済みでも、
    二重に通しても安全なため防御的に行う）。
    """
    if not theme_messages:
        return "（まだやり取りなし。このテーマの最初の質問をしてください）"
    lines = []
    for m in theme_messages:
        label = "面接官" if m["role"] == "assistant" else "学生"
        content = sanitize_user_input(m["content"]) if m["role"] == "user" else m["content"]
        lines.append(f"{label}: {content}")
    return "\n".join(lines)
