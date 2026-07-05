/**
 * hooks/useMockInterview.ts
 *
 * 模擬面接セッションの状態管理と SSE ストリーミング処理。
 *
 * 設計ポイント:
 *  - industryKey / personaKey は start() 時に state に保存し、
 *    sendAnswer() が stateRef 経由で参照する（クロージャ問題を回避）
 *  - 同期エンジンの処理時間中も UI はフリーズしない（バックエンドが executor に逃がす）
 *  - SSE は event: / data: のブロック単位でパース
 *  - 通信エラー時も回答は state.messages に残ったままなので、
 *    retryLastAnswer() で「入力しなおし」なしに再送信できる
 *  - 進行中の会話は localStorage にも保存し、SSE切断や誤操作で
 *    タブが失われても resumeFromDraft() で復元できる
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import type { Message, MockEvaluation } from '@/api/client'
import {
  apiStartMockInterview,
  apiEvaluateMockInterview,
  apiCreateSession,
  apiUpdateSession,
} from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'
import {
  saveInterviewDraft,
  loadInterviewDraft,
  clearInterviewDraft,
  type InterviewDraft,
} from '@/utils/interviewDraft'

export type InterviewStatus =
  | 'idle'
  | 'starting'
  | 'in_progress'
  | 'waiting'
  | 'finished'
  | 'evaluating'
  | 'evaluated'
  | 'error'

export interface MockInterviewState {
  status: InterviewStatus
  messages: Message[]
  themeIndex: number
  themeTitle: string
  followupsAsked: number
  industryKey: string
  personaKey: string
  profileText: string
  evaluation: MockEvaluation | null
  error: string | null
  errorHint: string | null
  /** 直前に送信しようとした回答。エラー時の再送信に使う */
  lastAnswer: string | null
  /** 直前のエラーが再送信可能な種類かどうか */
  canRetry: boolean
  sessionId: number | null   // 保存済みセッションID
}

interface StartOptions {
  industryKey: string
  personaKey: string
  profileText: string
  ragBlock?: string
  predictedQuestions?: unknown[]
}

// ── SSE パーサー ────────────────────────────────────────────────
interface SseEvent {
  eventType: string
  data: Record<string, unknown>
}

function parseSseChunk(text: string): SseEvent[] {
  const events: SseEvent[] = []
  for (const block of text.split('\n\n')) {
    if (!block.trim()) continue
    let eventType = 'message'
    let dataLine = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) eventType = line.slice(7).trim()
      else if (line.startsWith('data: ')) dataLine = line.slice(6).trim()
    }
    if (!dataLine) continue
    try {
      events.push({ eventType, data: JSON.parse(dataLine) as Record<string, unknown> })
    } catch { /* ignore */ }
  }
  return events
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

const INITIAL: MockInterviewState = {
  status: 'idle',
  messages: [],
  themeIndex: 0,
  themeTitle: '',
  followupsAsked: 0,
  industryKey: 'general',
  personaKey: 'standard',
  profileText: '',
  evaluation: null,
  error: null,
  errorHint: null,
  lastAnswer: null,
  canRetry: false,
  sessionId: null,
}

// ── フック本体 ─────────────────────────────────────────────────
export function useMockInterview() {
  const [state, setState] = useState<MockInterviewState>(INITIAL)
  const stateRef = useRef<MockInterviewState>(INITIAL)
  // setState をラップして ref を常に最新に保つ
  const setStateSync = useCallback((updater: (s: MockInterviewState) => MockInterviewState) => {
    setState(prev => {
      const next = updater(prev)
      stateRef.current = next
      return next
    })
  }, [])

  const abortRef = useRef<AbortController | null>(null)

  // 会話が進んでいる間は localStorage にも保存しておく（エラー・誤操作からの復旧用）
  useEffect(() => {
    const s = state
    if (s.messages.length > 0 && (s.status === 'in_progress' || s.status === 'waiting' || s.status === 'error')) {
      saveInterviewDraft({
        messages: s.messages,
        themeIndex: s.themeIndex,
        themeTitle: s.themeTitle,
        followupsAsked: s.followupsAsked,
        industryKey: s.industryKey,
        personaKey: s.personaKey,
        profileText: s.profileText,
        sessionId: s.sessionId,
      })
    } else if (s.status === 'finished' || s.status === 'evaluated' || s.status === 'idle') {
      clearInterviewDraft()
    }
  }, [state])

  // ── 面接開始 ────────────────────────────────────────────────
  const start = useCallback(async (options: StartOptions) => {
    setStateSync(() => ({ ...INITIAL, status: 'starting' }))
    try {
      // セッションをDBに先行作成
      const sessionRes = await apiCreateSession({
        profile_text: options.profileText,
        session_type: 'mock',
      })
      const sessionId = sessionRes.id

      const res = await apiStartMockInterview({
        industry_key: options.industryKey,
        persona_key: options.personaKey,
        profile_text: options.profileText,
        rag_block: options.ragBlock,
        predicted_questions: options.predictedQuestions,
      })
      setStateSync(s => ({
        ...s,
        status: 'in_progress',
        messages: [{ role: 'assistant', content: res.question }],
        themeIndex: res.theme_index,
        themeTitle: res.theme_title,
        followupsAsked: 0,
        industryKey: options.industryKey,
        personaKey: options.personaKey,
        profileText: options.profileText,
        sessionId,
      }))
    } catch (err) {
      const friendly = toFriendlyError(err)
      setStateSync(s => ({
        ...s,
        status: 'error',
        error: friendly.message,
        errorHint: friendly.hint ?? null,
        canRetry: false, // 開始前なので「最初からやり直す」以外に選択肢はない
      }))
    }
  }, [setStateSync])

  // ── 回答送信の実処理（SSE）─────────────────────────────────
  // messagesForRequest にはすでに送信対象の回答が含まれている前提。
  // retry の場合は同じ回答を重複追加せずにこの関数を呼び直す。
  const applyEvent = useCallback((eventType: string, data: Record<string, unknown>) => {
    switch (eventType) {
      case 'question':
        setStateSync(s => ({
          ...s,
          status: 'in_progress',
          messages: [...s.messages, { role: 'assistant', content: data['text'] as string }],
          followupsAsked: data['is_followup'] ? s.followupsAsked + 1 : 0,
        }))
        break
      case 'transition':
        setStateSync(s => ({
          ...s,
          themeIndex: data['theme_index'] as number,
          themeTitle: data['theme_title'] as string,
          followupsAsked: 0,
        }))
        break
      case 'finished':
        setStateSync(s => ({ ...s, status: 'finished' }))
        break
      case 'error': {
        const friendly = toFriendlyError(new Error(String(data['message'] ?? '')))
        setStateSync(s => ({
          ...s,
          status: 'error',
          error: (data['message'] as string) || friendly.message,
          errorHint: friendly.hint ?? null,
          canRetry: true,
        }))
        break
      }
    }
  }, [setStateSync])

  const performSend = useCallback(async (answer: string, messagesForRequest: Message[]) => {
    const cur = stateRef.current
    setStateSync(s => ({ ...s, status: 'waiting', lastAnswer: answer, error: null, errorHint: null }))

    abortRef.current = new AbortController()

    try {
      const res = await fetch('/api/v1/mock-interview/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          theme_index: cur.themeIndex,
          followups_asked: cur.followupsAsked,
          messages: messagesForRequest,
          answer,
          industry_key: cur.industryKey,
          persona_key: cur.personaKey,
          profile_text: cur.profileText,
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // \n\n 区切りで完成したブロックだけ処理
        const cut = buffer.lastIndexOf('\n\n')
        if (cut === -1) continue
        const chunk = buffer.slice(0, cut + 2)
        buffer = buffer.slice(cut + 2)

        for (const { eventType, data } of parseSseChunk(chunk)) {
          applyEvent(eventType, data)
        }
      }
      // バッファ残り
      if (buffer.trim()) {
        for (const { eventType, data } of parseSseChunk(buffer + '\n\n')) {
          applyEvent(eventType, data)
        }
      }
      // 正常に完了したのでリトライ用の回答は不要
      setStateSync(s => (s.status === 'error' ? s : { ...s, lastAnswer: null }))
    } catch (err) {
      if (!isAbortError(err)) {
        const friendly = toFriendlyError(err)
        setStateSync(s => ({
          ...s,
          status: 'error',
          error: friendly.message,
          errorHint: friendly.hint ?? null,
          canRetry: friendly.retryable,
        }))
      }
    }
  }, [setStateSync, applyEvent])
  const sendAnswer = useCallback(async (answer: string) => {
    const cur = stateRef.current
    const updatedMessages: Message[] = [
      ...cur.messages,
      { role: 'user', content: answer },
    ]
    setStateSync(s => ({ ...s, messages: updatedMessages }))
    await performSend(answer, updatedMessages)
  }, [performSend, setStateSync])

  // ── エラー後の再送信（回答内容・会話履歴は失わない）────────
  const retryLastAnswer = useCallback(async () => {
    const cur = stateRef.current
    if (!cur.lastAnswer) return
    // messages にはすでにユーザーの回答が含まれているので、そのまま使う
    await performSend(cur.lastAnswer, cur.messages)
  }, [performSend])

  // ── 終了後評価 ──────────────────────────────────────────────
  const evaluate = useCallback(async () => {
    const cur = stateRef.current
    setStateSync(s => ({ ...s, status: 'evaluating' }))
    try {
      const ev = await apiEvaluateMockInterview({
        messages: cur.messages,
        industry_key: cur.industryKey,
        profile_text: cur.profileText,
      })
      setStateSync(s => ({ ...s, status: 'evaluated', evaluation: ev }))
      clearInterviewDraft()

      // ── セッションにメッセージ履歴・評価結果を保存 ──────────
      if (cur.sessionId != null) {
        try {
          await apiUpdateSession(cur.sessionId, {
            messages: cur.messages,
            mock_evaluation: ev,
            interview_complete: true,
          })
        } catch (saveErr) {
          // 保存失敗は面接体験を壊さないようコンソールに留める
          console.warn('[useMockInterview] セッション保存に失敗しました:', saveErr)
        }
      }
    } catch (err) {
      const friendly = toFriendlyError(err)
      setStateSync(s => ({
        ...s,
        status: 'error',
        error: friendly.message,
        errorHint: friendly.hint ?? null,
        canRetry: friendly.retryable,
      }))
    }
  }, [setStateSync])

  // ── 中断 ────────────────────────────────────────────────────
  const abort = useCallback(() => { abortRef.current?.abort() }, [])

  // ── リセット（下書きも破棄）────────────────────────────────
  const reset = useCallback(() => {
    abort()
    clearInterviewDraft()
    setStateSync(() => INITIAL)
  }, [abort, setStateSync])

  // ── 保存済み下書きの確認・復元 ──────────────────────────────
  const getSavedDraft = useCallback((): InterviewDraft | null => loadInterviewDraft(), [])

  const resumeFromDraft = useCallback((draft: InterviewDraft) => {
    setStateSync(() => ({
      ...INITIAL,
      status: 'in_progress',
      messages: draft.messages,
      themeIndex: draft.themeIndex,
      themeTitle: draft.themeTitle,
      followupsAsked: draft.followupsAsked,
      industryKey: draft.industryKey,
      personaKey: draft.personaKey,
      profileText: draft.profileText,
      sessionId: draft.sessionId,
    }))
  }, [setStateSync])

  const discardDraft = useCallback(() => {
    clearInterviewDraft()
  }, [])

  return {
    state, start, sendAnswer, retryLastAnswer, evaluate, abort, reset,
    getSavedDraft, resumeFromDraft, discardDraft,
  }
}
