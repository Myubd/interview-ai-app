"""
pages/career_page.py
AIキャリアアドバイザーページ

[shared/ 一本化]
プロンプト・LLM呼び出し本体は career_advisor.py（shared/ に一本化済み）に
切り出した。このファイルにはUIと、DB永続化に依存する
_build_advisor_context() のみを残す。
"""

import logging
import streamlit as st

from favorites import (
    add_favorite, remove_favorite_by_item, is_favorited,
)
from career_advisor import generate_career_advice
from utils import sanitize_user_input


def _build_advisor_context() -> str:
    parts: list[str] = []

    if st.session_state.get("profile_text"):
        parts.append(f"【学生プロフィール（事前入力）】\n{st.session_state.profile_text}")

    interview_msgs = st.session_state.get("messages", [])
    if interview_msgs:
        lines = []
        for m in interview_msgs:
            role = "面接官" if m["role"] == "assistant" else "学生"
            lines.append(f"{role}: {m['content']}")
        parts.append("【自己PRインタビュー履歴】\n" + "\n".join(lines))

    if st.session_state.get("final_pr"):
        parts.append(f"【完成した自己PR】\n{st.session_state.final_pr}")

    summary = st.session_state.get("interview_summary")
    if summary:
        strength_lines = [f"・{s['point']}: {s['evidence']}" for s in summary.get("strengths", [])]
        weakness_lines = [f"・{w['point']}: {w['evidence']}" for w in summary.get("weaknesses", [])]
        fit_lines = [
            f"・{k}: {v['score']}点 ({v.get('reason','')})"
            for k, v in summary.get("industry_fit", {}).items()
        ]
        summary_text = (
            "【面接サマリー】\n"
            + (("強み:\n" + "\n".join(strength_lines) + "\n") if strength_lines else "")
            + (("成長余地:\n" + "\n".join(weakness_lines) + "\n") if weakness_lines else "")
            + (("業界別フィット度:\n" + "\n".join(fit_lines) + "\n") if fit_lines else "")
            + (f"向いている職種・環境: {summary.get('fit_roles','')}\n" if summary.get("fit_roles") else "")
            + (f"総評: {summary.get('overall_comment','')}" if summary.get("overall_comment") else "")
        )
        parts.append(summary_text)

    pa_result = st.session_state.get("pa_result")
    pa_scores = st.session_state.get("pa_axis_scores")
    if pa_result and pa_scores:
        score_lines = [f"・{k}: {v:.1f}/5" for k, v in pa_scores.items()]
        pa_text = (
            "【性格診断結果（ビッグファイブ）】\n"
            + "\n".join(score_lines) + "\n"
            + (f"サマリー: {pa_result.get('personality_summary','')}" if pa_result.get("personality_summary") else "")
        )
        if pa_result.get("interview_tips"):
            pa_text += f"\n面接での活かし方: {pa_result['interview_tips']}"
        parts.append(pa_text)

    mock_eval = st.session_state.get("mock_evaluation")
    if mock_eval:
        score_lines = [f"・{k}: {v}/5" for k, v in mock_eval.get("scores", {}).items()]
        mock_text = (
            "【模擬面接評価】\n"
            + f"総合評価: {mock_eval.get('overall_summary','')}\n"
            + ("スコア:\n" + "\n".join(score_lines) + "\n" if score_lines else "")
            + ("強みTOP3: " + " / ".join(mock_eval.get("top_strengths", [])) + "\n")
            + ("改善点TOP3: " + " / ".join(mock_eval.get("top_improvements", [])) + "\n")
            + ("次回練習ポイント: " + " / ".join(mock_eval.get("next_practice_points", [])))
        )
        parts.append(mock_text)

    company_prs = st.session_state.get("company_prs", {})
    if company_prs:
        parts.append("【志望企業（カスタマイズPR作成済み）】\n" + "\n".join(f"・{n}" for n in company_prs.keys()))

    if not parts:
        return ""
    return "\n\n".join(parts)


def render(model_name: str):
    st.title("🤖 AIキャリアアドバイザー")
    st.write(
        "ガクチカ・ES・業界研究・面接不安・企業比較など、就活に関することを何でも相談できます。"
        "あなたのインタビュー内容・自己PR・性格診断・模擬面接結果をすべて踏まえた上でアドバイスします。"
    )

    if st.button("← 自己PR作成に戻る"):
        st.session_state.app_mode = "interview"
        st.rerun()

    st.write("---")

    context_text = _build_advisor_context()
    has_context = bool(context_text.strip())

    if not has_context:
        st.info(
            "💡 まだ「自己PR作成」インタビューや「性格診断」「AI模擬面接」が完了していません。\n\n"
            "これらを先に進めると、あなたの強み・エピソード・診断結果を踏まえた"
            "より個別具体的なアドバイスができます。\n\n"
            "データがなくても就活の一般的な相談は可能です。"
        )
    else:
        badges = []
        if st.session_state.get("final_pr"):
            badges.append("✅ 自己PR")
        if st.session_state.get("interview_summary"):
            badges.append("✅ 面接サマリー")
        if st.session_state.get("pa_result"):
            badges.append("✅ 性格診断")
        if st.session_state.get("mock_evaluation"):
            badges.append("✅ 模擬面接評価")
        if st.session_state.get("company_prs"):
            badges.append(f"✅ 志望企業{len(st.session_state.company_prs)}社")
        st.caption("参照中のデータ: " + "　".join(badges))

    for msg in st.session_state.ca_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.ca_messages:
        with st.chat_message("assistant"):
            if has_context:
                st.markdown(
                    "こんにちは！AIキャリアアドバイザーです。\n\n"
                    "あなたのインタビュー内容・自己PR・診断結果などを確認しました。"
                    "ガクチカの相談、ES添削、業界・企業比較、面接対策など、"
                    "就活に関することは何でもお気軽にどうぞ！"
                )
            else:
                st.markdown(
                    "こんにちは！AIキャリアアドバイザーです。\n\n"
                    "ガクチカの相談、ES添削、業界研究、企業比較、面接の不安など、"
                    "就活に関することなら何でもお気軽にどうぞ！"
                )

    if st.session_state.ca_is_thinking:
        with st.spinner("考え中..."):
            result = generate_career_advice(
                model=model_name,
                context_text=context_text,
                history_messages=st.session_state.ca_messages[-20:],
            )
            reply = result["reply"]
            if not result["ok"]:
                # リトライ後も失敗した場合はエラー詳細をログに残す
                logging.getLogger(__name__).warning("キャリアアドバイザー応答失敗: %s", result["error_msg"])

        st.session_state.ca_messages.append({"role": "assistant", "content": reply})
        st.session_state.ca_is_thinking = False
        st.rerun()

    if user_q := st.chat_input("就活の相談を入力してください（例：ガクチカの磨き方を教えて）"):
        safe_q = sanitize_user_input(user_q, max_length=1000)
        if safe_q.strip():
            st.session_state.ca_messages.append({"role": "user", "content": safe_q})
            st.session_state.ca_is_thinking = True
            st.rerun()

    if st.session_state.ca_messages:
        st.write("")
        _ca_cols = st.columns([1, 1])
        with _ca_cols[0]:
            if st.button("🔄 会話をリセットする", use_container_width=False):
                st.session_state.ca_messages = []
                st.session_state.ca_is_thinking = False
                st.rerun()
        with _ca_cols[1]:
            _ca_session_id = st.session_state.get("current_session_id")
            _ca_is_fav = is_favorited("career_advice", session_id=_ca_session_id) if _ca_session_id else False
            if _ca_is_fav:
                if st.button("⭐ お気に入り解除", key="ca_fav_remove", use_container_width=True):
                    remove_favorite_by_item("career_advice", session_id=_ca_session_id)
                    st.rerun()
            else:
                if st.button("☆ お気に入りに追加", key="ca_fav_add", use_container_width=True,
                             help="この相談履歴をお気に入りに保存（先にセッション保存が必要）"):
                    if not _ca_session_id:
                        st.toast("先にサイドバーからセッションを保存してください。", icon="⚠️")
                    else:
                        _ca_msgs = st.session_state.ca_messages
                        _last_snippet = _ca_msgs[-1]["content"][:80] if _ca_msgs else ""
                        add_favorite(
                            item_type="career_advice",
                            session_id=_ca_session_id,
                            company_name=st.session_state.get("current_company_name") or None,
                            label="AIキャリア相談",
                            content_snapshot={
                                "message_count": len(_ca_msgs),
                                "last_snippet": _last_snippet,
                            },
                        )
                        st.toast("お気に入りに追加しました ⭐", icon="⭐")
                        st.rerun()
