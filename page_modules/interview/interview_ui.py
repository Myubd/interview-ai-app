"""
interview/interview_ui.py
プロフィール入力フォーム・インタビュー本体（質問応答ループ）
"""

import streamlit as st

from interview_engine import (
    CATEGORY_OPTIONS, THEMES,
    get_first_question_for_theme, judge_and_generate_next_question,
)
from utils import sanitize_user_input
from page_modules.interview.helpers import build_profile_text
from db.settings_repository import get_setting, set_setting

# settings テーブルに保存するキー
_PROFILE_EDUCATION_KEY = "saved_profile_education"
_PROFILE_WORK_KEY      = "saved_profile_work"
_PROFILE_LICENSES_KEY  = "saved_profile_licenses"


# ──────────────────────────────────────────────────────────────
# プロフィールフォーム
# ──────────────────────────────────────────────────────────────

def render_profile_form():
    st.subheader("📋 はじめに（事前入力・任意）")
    st.write(
        "学歴・職歴・資格／免許をあらかじめ入力しておくと、インタビュー中にAIが同じ内容を"
        "聞き返さずに済むため、より少ない質問数でテンポよく進められます。"
        "（未入力のまま始めることもできます）"
    )

    # 前回保存したプロフィールがあれば読み込んでデフォルト値にする
    saved_education = get_setting(_PROFILE_EDUCATION_KEY, "") or ""
    saved_work      = get_setting(_PROFILE_WORK_KEY, "") or ""
    saved_licenses  = get_setting(_PROFILE_LICENSES_KEY, "") or ""
    has_saved = bool(saved_education or saved_work or saved_licenses)

    if has_saved:
        st.caption("💾 前回保存したプロフィールを読み込みました（編集して上書き保存できます）")

    with st.form("profile_form"):
        education_input = st.text_area(
            "学歴",
            value=saved_education,
            placeholder="例）〇〇大学 〇〇学部 〇〇学科\n2027年3月 卒業見込み",
            height=80,
        )
        work_history_input = st.text_area(
            "職歴（インターン・アルバイト等）",
            value=saved_work,
            placeholder="例）〇〇株式会社にて長期インターン（2024年6月〜現在）\n△△カフェにてアルバイト（2023年4月〜2024年3月）",
            height=80,
        )
        licenses_input = st.text_area(
            "資格・免許",
            value=saved_licenses,
            placeholder="例）TOEIC 850点\n普通自動車第一種運転免許\n基本情報技術者試験",
            height=80,
        )
        _fcol1, _fcol2 = st.columns([3, 1])
        with _fcol1:
            submitted = st.form_submit_button("✅ この内容でインタビューを始める", type="primary", use_container_width=True)
        with _fcol2:
            save_profile = st.form_submit_button("💾 保存だけする", use_container_width=True,
                                                  help="入力内容をこのPCに保存し、次回起動時にも使えるようにします")

    if submitted or save_profile:
        # 入力内容を settings テーブルに保存
        set_setting(_PROFILE_EDUCATION_KEY, education_input)
        set_setting(_PROFILE_WORK_KEY, work_history_input)
        set_setting(_PROFILE_LICENSES_KEY, licenses_input)

    if submitted:
        st.session_state.profile_text = build_profile_text(education_input, work_history_input, licenses_input)
        st.session_state.profile_done = True
        st.rerun()

    if save_profile:
        st.toast("プロフィールを保存しました 💾", icon="💾")
        st.rerun()

    if st.button("入力せずに始める"):
        st.session_state.profile_text = ""
        st.session_state.profile_done = True
        st.rerun()


# ──────────────────────────────────────────────────────────────
# インタビュー開始・進行
# ──────────────────────────────────────────────────────────────

def start_interview(model_name: str):
    intro = (
        "こんにちは！あなたの隠れた強みを見つけるために、いくつか質問をさせてください。"
        "回答に合わせて、こちらからの質問も都度変わっていきます。\n\n"
    )
    first_theme = THEMES[0]
    with st.spinner("質問を準備中..."):
        result = get_first_question_for_theme(model_name, first_theme, None, None, st.session_state.profile_text)
    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、簡易的な質問で開始します。Ollamaの状態をご確認ください。", icon="⚠️")
    first_question = result["question"]
    st.session_state.messages.append({"role": "assistant", "content": intro + f"**「{first_question}」**"})
    st.session_state.theme_messages.append({"role": "assistant", "content": first_question})
    st.session_state.questions_asked_in_theme = 1
    st.session_state.interview_started = True


def enter_category_choice_if_needed():
    idx = st.session_state.current_theme_index
    if idx >= len(THEMES):
        return
    theme = THEMES[idx]
    if theme["needs_category_choice"] and st.session_state.selected_category is None:
        st.session_state.awaiting_category_choice = True


def advance_to_theme(model_name: str, new_index: int):
    st.session_state.current_theme_index = new_index
    st.session_state.theme_messages = []
    st.session_state.questions_asked_in_theme = 0
    st.session_state.selected_category = None

    if new_index >= len(THEMES):
        st.session_state.interview_complete = True
        finish_msg = (
            "質問は以上です！ご協力ありがとうございました。あなたの経歴と人間性がよく分かりました。\n\n"
            "それでは、これまでの内容をもとに自己PRを生成します。下のボタンを押してください。"
        )
        st.session_state.messages.append({"role": "assistant", "content": finish_msg})
        return

    theme = THEMES[new_index]
    if theme["needs_category_choice"]:
        st.session_state.awaiting_category_choice = True
        if st.session_state.messages:
            recent = st.session_state.messages[-2:]
            st.session_state.pending_prev_exchange = "\n".join(
                f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}" for m in recent
            )
        else:
            st.session_state.pending_prev_exchange = None
        lead_in = "ありがとうございます。次に、学生時代に最も力を入れたことについて伺いたいのですが、まずは近いものを選んでください。"
        st.session_state.messages.append({"role": "assistant", "content": lead_in})
        return

    prev_last = None
    if st.session_state.messages:
        recent = st.session_state.messages[-2:]
        prev_last = "\n".join(
            f"{'面接官' if m['role'] == 'assistant' else '学生'}: {m['content']}" for m in recent
        )
    with st.spinner("次の質問を考え中..."):
        result = get_first_question_for_theme(model_name, theme, None, prev_last, st.session_state.profile_text)
    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、簡易的な質問にしました。Ollamaの状態をご確認ください。", icon="⚠️")
    question = result["question"]
    st.session_state.messages.append({"role": "assistant", "content": f"**「{question}」**"})
    st.session_state.theme_messages.append({"role": "assistant", "content": question})
    st.session_state.questions_asked_in_theme = 1


def start_category_theme_with_choice(model_name: str, category: str):
    idx = st.session_state.current_theme_index
    theme = THEMES[idx]
    st.session_state.selected_category = category
    st.session_state.awaiting_category_choice = False
    st.session_state.messages.append({"role": "user", "content": f"（選んだカテゴリ: {category}）"})

    prev_exchange = st.session_state.get("pending_prev_exchange")
    with st.spinner("質問を考え中..."):
        result = get_first_question_for_theme(model_name, theme, category, prev_exchange, st.session_state.profile_text)
    if not result["ok"]:
        st.toast("⚠️ AIとの通信に問題が発生したため、簡易的な質問にしました。Ollamaの状態をご確認ください。", icon="⚠️")
    question = result["question"]
    st.session_state.messages.append({"role": "assistant", "content": f"**「{question}」**"})
    st.session_state.theme_messages.append({"role": "assistant", "content": question})
    st.session_state.questions_asked_in_theme = 1
    st.session_state.pending_prev_exchange = None
    st.rerun()


# ──────────────────────────────────────────────────────────────
# インタビューUIメイン（会話ループ部分）
# ──────────────────────────────────────────────────────────────

def render_interview_ui(model_name: str):
    """インタビュー開始〜質問応答ループ部分を描画する。"""

    if not st.session_state.interview_started:
        start_interview(model_name)

    # 会話履歴表示
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # テーマ遷移チェック
    enter_category_choice_if_needed()

    # ユーザー入力受付
    if not st.session_state.interview_complete:
        if st.session_state.awaiting_category_choice:
            st.write("**どれに近いですか？**")
            cols = st.columns(2)
            for i, option in enumerate(CATEGORY_OPTIONS):
                with cols[i % 2]:
                    if st.button(option, key=f"category_choice_{i}", use_container_width=True):
                        start_category_theme_with_choice(model_name, option)

        elif user_input := st.chat_input("ここに回答を入力してください..."):
            sanitized_input = sanitize_user_input(user_input)
            if len(sanitized_input.strip()) < 2:
                st.toast("もう少し詳しく教えてください🙏", icon="⚠️")
            else:
                st.session_state.messages.append({"role": "user", "content": sanitized_input})
                st.session_state.theme_messages.append({"role": "user", "content": sanitized_input})

                theme_idx = st.session_state.current_theme_index
                theme = THEMES[theme_idx]

                with st.spinner("回答を確認中..."):
                    result = judge_and_generate_next_question(
                        model=model_name,
                        theme=theme,
                        theme_messages=st.session_state.theme_messages,
                        questions_asked_in_theme=st.session_state.questions_asked_in_theme,
                        selected_category=st.session_state.selected_category,
                        profile_text=st.session_state.profile_text,
                    )
                if not result["ok"]:
                    st.toast("⚠️ AIとの通信に問題が発生したため、このテーマを終了して次へ進みます。Ollamaの状態をご確認ください。", icon="⚠️")

                if result["continue"] and result["question"]:
                    st.session_state.messages.append({"role": "assistant", "content": f"**「{result['question']}」**"})
                    st.session_state.theme_messages.append({"role": "assistant", "content": result["question"]})
                    st.session_state.questions_asked_in_theme += 1
                else:
                    advance_to_theme(model_name, theme_idx + 1)

                st.rerun()
