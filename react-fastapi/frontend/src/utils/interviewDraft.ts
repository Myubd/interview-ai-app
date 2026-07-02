/**
 * utils/interviewDraft.ts
 *
 * 模擬面接の進行状況をブラウザの localStorage に保存し、
 * SSE切断やタイムアウトでエラー画面に飛んだ場合や、誤って
 * タブを閉じてしまった場合でも、それまでの回答を失わずに
 * 再開できるようにするためのユーティリティ。
 *
 * 保存内容はサーバーに送信されず、この端末のブラウザ内にのみ残る。
 */
import type { Message } from '@/api/client'

const STORAGE_KEY = 'mockInterview:draft:v1'
// 古い下書きを再開させないための有効期限（6時間）
const MAX_AGE_MS = 6 * 60 * 60 * 1000

export interface InterviewDraft {
  messages: Message[]
  themeIndex: number
  themeTitle: string
  followupsAsked: number
  industryKey: string
  personaKey: string
  profileText: string
  sessionId: number | null
  savedAt: number
}

export function saveInterviewDraft(draft: Omit<InterviewDraft, 'savedAt'>): void {
  try {
    const payload: InterviewDraft = { ...draft, savedAt: Date.now() }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // localStorage が使えない環境（プライベートモード等）では保存をあきらめる。
    // 面接自体は継続できるので、ここでは何もしない。
  }
}

export function loadInterviewDraft(): InterviewDraft | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const draft = JSON.parse(raw) as InterviewDraft
    if (!draft.messages || draft.messages.length === 0) return null
    if (Date.now() - draft.savedAt > MAX_AGE_MS) {
      clearInterviewDraft()
      return null
    }
    return draft
  } catch {
    return null
  }
}

export function clearInterviewDraft(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // 無視して問題ない
  }
}
