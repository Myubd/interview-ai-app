# -*- coding: utf-8 -*-
"""
page_modules/dashboard_page.py
--------------------------------
模擬面接スコアのダッシュボードページ。

評価済みセッションの mock_interview_evaluation を集計し、以下を表示する:
  - サマリーカード（総セッション数・評価済み数・平均・最高スコア）
  - 総合スコア推移グラフ（Streamlit の st.line_chart）
  - 軸別平均スコアのレーダー風バーチャート（st.bar_chart）
  - 軸別スコア推移テーブル

注意:
  Streamlit版の評価結果は scores が 1-5 スケール（5段階）。
  表示用に 0-100% へ変換して統一表示する（× 20）。
  React版評価（FastAPI 経由）では 0-100 で保存済みのため、
  値の範囲を自動検出して変換の有無を判定する。

軸キーの日本語ラベルは AXIS_LABELS で管理し、
未知のキーはそのまま表示する。
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from session_io import list_sessions
from shared.db import session_repository as session_repo

# 軸キー → 日本語ラベル
AXIS_LABELS: dict[str, str] = {
    "logic":         "論理性",
    "communication": "コミュニケーション",
    "motivation":    "志望動機",
    "self_analysis": "自己分析",
    "adaptability":  "応用力",
    "expression":    "表現力",
    "concrete":      "具体性",
    "enthusiasm":    "熱意",
}


def _axis_label(key: str) -> str:
    return AXIS_LABELS.get(key, key)


def _normalize_score(value: float) -> float:
    """スコアを 0-100 スケールに正規化する。
    1-5 スケール（Streamlit版）は × 20 で変換する。
    0-100 スケール（React版）はそのまま返す。
    """
    if value <= 5:
        return round(value * 20, 1)
    return round(float(value), 1)


def _load_evaluated_sessions() -> list[dict]:
    """評価済みセッションを古い順で返す。

    Returns:
        [
          {
            "session_id": int,
            "company_name": str | None,
            "created_at": str,
            "overall_score": float,   # 0-100 に正規化済み
            "axes": {axis_key: float, ...},
          },
          ...
        ]
    """
    metas = list_sessions()
    evaluated: list[dict] = []

    for meta in metas:
        if not meta.get("has_mock_evaluation"):
            continue

        detail = session_repo.get_session(meta["id"])
        if detail is None:
            continue

        raw_eval = detail["session"].get("mock_interview_evaluation")
        if not raw_eval:
            continue

        if isinstance(raw_eval, str):
            try:
                raw_eval = json.loads(raw_eval)
            except (ValueError, TypeError):
                continue

        raw_scores: dict = raw_eval.get("scores", {})
        if not raw_scores:
            continue

        axes = {k: _normalize_score(v) for k, v in raw_scores.items()}
        overall = round(sum(axes.values()) / len(axes), 1) if axes else 0.0

        evaluated.append({
            "session_id":   meta["id"],
            "company_name": meta.get("company_name"),
            "created_at":   meta["created_at"],
            "overall_score": overall,
            "axes":         axes,
        })

    # 古い順（グラフが左→右で時系列）
    evaluated.sort(key=lambda x: x["created_at"])
    return evaluated


def _format_label(entry: dict, idx: int) -> str:
    """グラフのX軸ラベル用文字列を生成する。"""
    name = entry["company_name"] or f"#{entry['session_id']}"
    date = entry["created_at"][:10]
    return f"{idx + 1}. {name}\n{date}"


# ============================================================
# メイン描画関数
# ============================================================

def render() -> None:
    """ダッシュボードページを描画する。app.py から呼び出す。"""

    st.title("📊 ダッシュボード")
    st.caption("AI模擬面接の評価結果を集計してスコアの推移を確認できます。")

    if st.button("← ホームに戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.divider()

    # ── データ取得 ──────────────────────────────────────────────
    with st.spinner("評価データを集計中..."):
        evaluated = _load_evaluated_sessions()

    all_metas = list_sessions()
    total = len(all_metas)
    ev_count = len(evaluated)

    # ── 未データ時の案内 ───────────────────────────────────────
    if ev_count == 0:
        st.info(
            "まだ評価データがありません。\n\n"
            "「🎤 AI模擬面接」を完了して評価を生成すると、ここにスコアの推移が表示されます。"
        )
        return

    # ── サマリーカード ──────────────────────────────────────────
    overall_scores = [e["overall_score"] for e in evaluated]
    avg_score = round(sum(overall_scores) / len(overall_scores), 1)
    best_score = max(overall_scores)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("総面接数", f"{total} 件")
    col2.metric("評価済み", f"{ev_count} 件")
    col3.metric("平均スコア", f"{avg_score} / 100")
    col4.metric("最高スコア", f"{best_score} / 100")

    st.divider()

    # ── ラベルを生成 ────────────────────────────────────────────
    labels = [_format_label(e, i) for i, e in enumerate(evaluated)]

    # ── 総合スコア推移 ──────────────────────────────────────────
    st.subheader("📈 総合スコア推移")

    if ev_count == 1:
        st.info(f"現在 1 件の評価データがあります（スコア: {evaluated[0]['overall_score']} / 100）。\n"
                "2 件以上になるとグラフが表示されます。")
    else:
        df_overall = pd.DataFrame(
            {"総合スコア": [e["overall_score"] for e in evaluated]},
            index=labels,
        )
        st.line_chart(df_overall, height=260)

    st.divider()

    # ── 軸別スコア推移 ──────────────────────────────────────────
    # 全セッションに登場する軸キーを収集
    all_axes_keys: list[str] = []
    for e in evaluated:
        for k in e["axes"]:
            if k not in all_axes_keys:
                all_axes_keys.append(k)

    if all_axes_keys and ev_count >= 2:
        st.subheader("📉 軸別スコア推移")

        # 軸の表示選択
        axis_options = {_axis_label(k): k for k in all_axes_keys}
        selected_labels = st.multiselect(
            "表示する軸を選択",
            options=list(axis_options.keys()),
            default=list(axis_options.keys()),
            key="dashboard_axes_select",
        )
        selected_keys = [axis_options[lbl] for lbl in selected_labels]

        if selected_keys:
            axes_data = {
                _axis_label(k): [e["axes"].get(k, 0) for e in evaluated]
                for k in selected_keys
            }
            df_axes = pd.DataFrame(axes_data, index=labels)
            st.line_chart(df_axes, height=300)
        else:
            st.caption("軸を1つ以上選択してください。")

        st.divider()

    # ── 軸別平均スコア ──────────────────────────────────────────
    if all_axes_keys:
        st.subheader("📊 軸別 平均スコア")

        axes_avg = {
            _axis_label(k): round(
                sum(e["axes"].get(k, 0) for e in evaluated) / ev_count, 1
            )
            for k in all_axes_keys
        }
        df_avg = pd.DataFrame.from_dict(
            {"平均スコア": axes_avg}, orient="columns"
        )
        st.bar_chart(df_avg, height=280)

        st.divider()

    # ── 詳細テーブル ────────────────────────────────────────────
    with st.expander("📋 セッション別スコア一覧", expanded=False):
        rows = []
        for i, e in enumerate(evaluated):
            row: dict = {
                "#": i + 1,
                "企業名": e["company_name"] or "未設定",
                "日付": e["created_at"][:10],
                "総合スコア": e["overall_score"],
            }
            for k in all_axes_keys:
                row[_axis_label(k)] = e["axes"].get(k, "-")
            rows.append(row)

        df_table = pd.DataFrame(rows).set_index("#")
        st.dataframe(df_table, use_container_width=True)
