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
 */
import { useState, useCallback, useRef } from 'react'
import type { Message, MockEvaluation } from '@/api/client'
import {
  apiStartMockInterview,
  apiEvaluateMockInterview,
  apiCreateSession,
  apiUpdateSession,
} from '@/api/client'

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

// ── フック本体 ─────────────────────────────────────────────────
export function useMockInterview() {
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
    sessionId: null,
  }

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
      setStateSync(s => ({ ...s, status: 'error', error: String(err) }))
    }
  }, [setStateSync])

  // ── 回答送信（SSE）─────────────────────────────────────────
  const sendAnswer = useCallback(async (answer: string) => {
    const cur = stateRef.current

    // ユーザーメッセージを即時追加
    const updatedMessages: Message[] = [
      ...cur.messages,
      { role: 'user', content: answer },
    ]
    setStateSync(s => ({ ...s, status: 'waiting', messages: updatedMessages }))

    abortRef.current = new AbortController()

    try {
      const res = await fetch('/api/v1/mock-interview/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          theme_index: cur.themeIndex,
          followups_asked: cur.followupsAsked,
          messages: updatedMessages,
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
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setStateSync(s => ({ ...s, status: 'error', error: String(err) }))
      }
    }
  }, [setStateSync])

  function applyEvent(eventType: string, data: Record<string, unknown>) {
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
      case 'error':
        setStateSync(s => ({ ...s, status: 'error', error: data['message'] as string }))
        break
    }
  }

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
      setStateSync(s => ({ ...s, status: 'error', error: String(err) }))
    }
  }, [setStateSync])

  // ── 中断 ────────────────────────────────────────────────────
  const abort = useCallback(() => { abortRef.current?.abort() }, [])

  // ── リセット ────────────────────────────────────────────────
  const reset = useCallback(() => {
    abort()
    setStateSync(() => INITIAL)
  }, [abort, setStateSync])

  return { state, start, sendAnswer, evaluate, abort, reset }
}
