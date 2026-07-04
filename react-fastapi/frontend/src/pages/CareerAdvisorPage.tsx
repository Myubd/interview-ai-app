/**
 * pages/CareerAdvisorPage.tsx
 * AIキャリアアドバイザー（就活相談チャット）。
 *
 * 既存コードとの対応:
 *   streamlit版 page_modules/career_page.py が相当する。
 *   プロンプト・LLM呼び出し本体は career_advisor.py（shared/ に一本化済み）。
 *
 * Streamlit版との違い:
 *   streamlit版はグローバルなセッション状態（面接内容・自己PR・診断結果等）を
 *   自動で参照するが、React版はページごとに状態が独立しているため、
 *   「保存済みセッション」をドロップダウンで選んでコンテキストとして
 *   読み込む方式にした（面接履歴ページと同じ一覧から選択する）。
 */
import React, { useEffect, useRef, useState } from 'react'
import { Bot, MessageSquareText, Send, User } from 'lucide-react'
import {
  apiGetCareerAdvisorSessions,
  apiCareerAdvisorChat,
  type CareerAdvisorSessionSummary,
  type Message,
} from '@/api/client'
import { Button, Card, Spinner, TypingIndicator } from '@/components/ui'

export const CareerAdvisorPage: React.FC = () => {
  const [sessions, setSessions] = useState<CareerAdvisorSessionSummary[]>([])
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [sessionId, setSessionId] = useState<number | null>(null)

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiGetCareerAdvisorSessions()
      .then(setSessions)
      .catch(err => setError(String(err)))
      .finally(() => setLoadingSessions(false))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  const hasContext = sessionId !== null

  const handleSend = async () => {
    const text = input.trim()
    if (!text || thinking) return
    const nextMessages: Message[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setInput('')
    setThinking(true)
    setError(null)
    try {
      const res = await apiCareerAdvisorChat({ messages: nextMessages, session_id: sessionId })
      setMessages(prev => [...prev, { role: 'assistant', content: res.reply }])
    } catch (err) {
      setError(String(err))
    } finally {
      setThinking(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 flex flex-col h-full">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <MessageSquareText className="w-5 h-5 text-brand-500" />
          AIキャリアアドバイザー
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          ガクチカの相談、ES添削、業界研究、企業比較、面接の不安など、就活に関することなら何でもお気軽にどうぞ。
        </p>
      </div>

      <Card className="p-3 mb-4">
        <label className="text-xs font-medium text-slate-500 block mb-1.5">
          参照するデータ（任意）
        </label>
        {loadingSessions ? (
          <Spinner className="w-4 h-4" />
        ) : sessions.length === 0 ? (
          <p className="text-xs text-slate-400">
            保存済みのセッションがありません。面接内容や自己PRを踏まえた相談をしたい場合は、
            先に「自己PR作成」や「AI模擬面接」でセッションを保存してください。
          </p>
        ) : (
          <select
            value={sessionId ?? ''}
            onChange={e => setSessionId(e.target.value ? Number(e.target.value) : null)}
            className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300"
          >
            <option value="">参照しない（一般的な相談として話す）</option>
            {sessions.map(s => (
              <option key={s.id} value={s.id}>
                {(s.company_name || '（企業名未設定）')} {s.session_type ?? ''} - {new Date(s.created_at).toLocaleString('ja-JP')}
              </option>
            ))}
          </select>
        )}
      </Card>

      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <ChatBubble
            role="assistant"
            content={
              hasContext
                ? 'こんにちは！AIキャリアアドバイザーです。\n\n選択いただいたセッションの内容を確認しました。ガクチカの相談、ES添削、業界・企業比較、面接対策など、就活に関することは何でもお気軽にどうぞ！'
                : 'こんにちは！AIキャリアアドバイザーです。\n\nガクチカの相談、ES添削、業界研究、企業比較、面接の不安など、就活に関することなら何でもお気軽にどうぞ！'
            }
          />
        )}
        {messages.map((m, i) => (
          <ChatBubble key={i} role={m.role} content={m.content} />
        ))}
        {thinking && (
          <div className="flex items-start gap-2">
            <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-brand-600" />
            </div>
            <div className="bg-surface-100 rounded-2xl rounded-tl-sm px-4 py-2.5">
              <TypingIndicator />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <Card className="p-3 mb-3 border-red-200 bg-red-50">
          <p className="text-xs text-red-600">{error}</p>
        </Card>
      )}

      <div className="flex items-end gap-2 border-t border-surface-200 pt-4">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="就活の相談を入力してください（例：ガクチカの磨き方を教えて）"
          rows={2}
          className="flex-1 text-sm border border-surface-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-300"
        />
        <Button
          icon={<Send className="w-4 h-4" />}
          disabled={!input.trim()}
          loading={thinking}
          onClick={handleSend}
        >
          送信
        </Button>
      </div>
    </div>
  )
}

const ChatBubble: React.FC<{ role: string; content: string }> = ({ role, content }) => {
  const isUser = role === 'user'
  return (
    <div className={`flex items-start gap-2 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${isUser ? 'bg-slate-200' : 'bg-brand-100'}`}>
        {isUser ? <User className="w-4 h-4 text-slate-600" /> : <Bot className="w-4 h-4 text-brand-600" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
          isUser ? 'bg-brand-500 text-white rounded-tr-sm' : 'bg-surface-100 text-slate-700 rounded-tl-sm'
        }`}
      >
        {content}
      </div>
    </div>
  )
}
