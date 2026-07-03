/**
 * hooks/useInterviewFlow.ts
 *
 * 「自己PR引き出しインタビュー」の質問応答ループ（②）の状態管理。
 * streamlit版 page_modules/interview/interview_ui.py が相当。
 *
 * ポスト・インタビュー（サマリー・自己PR生成・評価・微調整・想定質問・
 * 企業別PR）は状態がシンプルな逐次フローのため、このフックではなく
 * InterviewPage.tsx 側の各セクションコンポーネントで直接 API を呼ぶ。
 *
 * バックエンドはステートレス設計（mock-interviewと同様）のため、
 * フロントが messages（画面表示用の全履歴）と theme_messages
 * （テーマ内の会話）を保持し、毎回のリクエストで渡す。
 */
import { useState, useCallback, useRef } from 'react'
import type { Message } from '@/api/client'
import {
  apiInterviewStart,
  apiInterviewNext,
  apiInterviewChooseCategory,
  apiCreateSession,
} from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

export type InterviewFlowStatus =
  | 'idle'
  | 'starting'
  | 'in_progress'
  | 'waiting'
  | 'awaiting_category_choice'
  | 'complete'
  | 'error'

export interface InterviewFlowState {
  status: InterviewFlowStatus
  messages: Message[]
  themeMessages: Message[]
  themeIndex: number
  themeTitle: string
  questionsAskedInTheme: number
  categoryOptions: string[]
  profileText: string
  sessionId: number | null
  error: string | null
  errorHint: string | null
}

export function useInterviewFlow() {
  const INITIAL: InterviewFlowState = {
    status: 'idle',
    messages: [],
    themeMessages: [],
    themeIndex: 0,
    themeTitle: '',
    questionsAskedInTheme: 0,
    categoryOptions: [],
    profileText: '',
    sessionId: null,
    error: null,
    errorHint: null,
  }

  const [state, setState] = useState<InterviewFlowState>(INITIAL)
  const stateRef = useRef<InterviewFlowState>(INITIAL)
  const setStateSync = useCallback((updater: (s: InterviewFlowState) => InterviewFlowState) => {
    setState(prev => {
      const next = updater(prev)
      stateRef.current = next
      return next
    })
  }, [])

  // ── 開始 ──────────────────────────────────────────────────
  const start = useCallback(async (profileText: string) => {
    setStateSync(() => ({ ...INITIAL, status: 'starting', profileText }))
    try {
      const sessionRes = await apiCreateSession({ profile_text: profileText, session_type: 'interview' })
      const res = await apiInterviewStart(profileText)
      setStateSync(s => ({
        ...s,
        status: 'in_progress',
        messages: [{ role: 'assistant', content: res.question }],
        themeMessages: [{ role: 'assistant', content: res.question }],
        themeIndex: res.theme_index,
        themeTitle: res.theme_title,
        questionsAskedInTheme: res.questions_asked_in_theme,
        sessionId: sessionRes.id,
      }))
    } catch (err) {
      const friendly = toFriendlyError(err)
      setStateSync(s => ({ ...s, status: 'error', error: friendly.message, errorHint: friendly.hint ?? null }))
    }
  }, [setStateSync])

  const applyQuestionResult = (
    s: InterviewFlowState,
    res: Awaited<ReturnType<typeof apiInterviewStart>>,
  ): InterviewFlowState => {
    if (res.status === 'complete') {
      return {
        ...s,
        status: 'complete',
        messages: [
          ...s.messages,
          {
            role: 'assistant',
            content:
              '質問は以上です！ご協力ありがとうございました。あなたの経歴と人間性がよく分かりました。\n\n' +
              'それでは、これまでの内容をもとに自己PRを生成します。下のボタンを押してください。',
          },
        ],
      }
    }
    if (res.status === 'awaiting_category_choice') {
      return {
        ...s,
        status: 'awaiting_category_choice',
        themeIndex: res.theme_index,
        themeTitle: res.theme_title,
        categoryOptions: res.category_options,
        themeMessages: [],
        questionsAskedInTheme: 0,
      }
    }
    // 'question'（同一テーマの深掘り、またはカテゴリ選択不要な次テーマ）
    const isNewTheme = res.theme_index !== s.themeIndex
    return {
      ...s,
      status: 'in_progress',
      themeIndex: res.theme_index,
      themeTitle: res.theme_title,
      questionsAskedInTheme: res.questions_asked_in_theme,
      messages: [...s.messages, { role: 'assistant', content: res.question }],
      themeMessages: isNewTheme
        ? [{ role: 'assistant', content: res.question }]
        : [...s.themeMessages, { role: 'assistant', content: res.question }],
    }
  }

  // ── 回答送信 ──────────────────────────────────────────────
  const sendAnswer = useCallback(async (answer: string) => {
    const cur = stateRef.current
    const userMsg: Message = { role: 'user', content: answer }
    const updatedMessages = [...cur.messages, userMsg]
    const updatedThemeMessages = [...cur.themeMessages, userMsg]
    setStateSync(s => ({
      ...s,
      status: 'waiting',
      messages: updatedMessages,
      themeMessages: updatedThemeMessages,
      error: null,
      errorHint: null,
    }))
    try {
      const res = await apiInterviewNext({
        theme_index: cur.themeIndex,
        theme_messages: updatedThemeMessages,
        questions_asked_in_theme: cur.questionsAskedInTheme,
        selected_category: null,
        profile_text: cur.profileText,
        messages: updatedMessages,
      })
      setStateSync(s => applyQuestionResult(s, res))
    } catch (err) {
      const friendly = toFriendlyError(err)
      setStateSync(s => ({ ...s, status: 'error', error: friendly.message, errorHint: friendly.hint ?? null }))
    }
  }, [setStateSync])

  // ── カテゴリ選択 ──────────────────────────────────────────
  const chooseCategory = useCallback(async (category: string) => {
    const cur = stateRef.current
    const updatedMessages: Message[] = [
      ...cur.messages,
      { role: 'user', content: `（選んだカテゴリ: ${category}）` },
    ]
    setStateSync(s => ({ ...s, status: 'waiting', messages: updatedMessages, error: null, errorHint: null }))
    try {
      const res = await apiInterviewChooseCategory({
        theme_index: cur.themeIndex,
        category,
        profile_text: cur.profileText,
        messages: updatedMessages,
      })
      setStateSync(s => ({
        ...applyQuestionResult({ ...s, messages: updatedMessages }, res),
      }))
    } catch (err) {
      const friendly = toFriendlyError(err)
      setStateSync(s => ({ ...s, status: 'error', error: friendly.message, errorHint: friendly.hint ?? null }))
    }
  }, [setStateSync])

  const reset = useCallback(() => {
    setStateSync(() => INITIAL)
  }, [setStateSync])

  return { state, start, sendAnswer, chooseCategory, reset }
}
