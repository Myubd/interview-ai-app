/**
 * pages/interview/InterviewChat.tsx
 * インタビュー本体（質問応答ループ）UI。
 * streamlit版 interview_ui.py の render_interview_ui() に相当。
 */
import React, { useState, useEffect, useRef } from 'react'
import { Send, User, Bot, AlertCircle, RotateCcw } from 'lucide-react'
import { Button, Badge, TypingIndicator, ProgressBar } from '@/components/ui'
import type { useInterviewFlow } from '@/hooks/useInterviewFlow'

const TOTAL_THEMES = 4

interface InterviewChatProps {
  state: ReturnType<typeof useInterviewFlow>['state']
  onSend: (answer: string) => void
  onChooseCategory: (category: string) => void
  onReset: () => void
}

export const InterviewChat: React.FC<InterviewChatProps> = ({ state, onSend, onChooseCategory, onReset }) => {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.messages, state.status])

  const handleSend = () => {
    const text = input.trim()
    if (text.length < 2 || state.status === 'waiting') return
    setInput('')
    onSend(text)
  }

  if (state.status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 animate-fade-in px-6" role="alert">
        <AlertCircle className="w-10 h-10 text-red-400" aria-hidden="true" />
        <div className="text-center max-w-sm">
          <p className="text-sm text-red-600 font-medium">{state.error}</p>
          {state.errorHint && <p className="text-xs text-slate-500 mt-1.5">{state.errorHint}</p>}
          <p className="text-xs text-slate-400 mt-3">
            これまでの回答（{state.messages.filter(m => m.role === 'user').length}件）は保持されています。
          </p>
        </div>
        <Button variant="secondary" onClick={onReset} icon={<RotateCcw className="w-4 h-4" />}>
          最初からやり直す
        </Button>
      </div>
    )
  }

  const progress = Math.round(((state.themeIndex + 1) / TOTAL_THEMES) * 100)

  return (
    <div className="flex flex-col h-full">
      {/* ヘッダー：テーマ進捗 */}
      <div className="px-6 py-3 border-b border-surface-100">
        <div className="flex items-center gap-3 mb-2">
          <Badge variant="info" className="flex-shrink-0">{state.themeTitle || '...'}</Badge>
          <ProgressBar
            value={progress}
            label={`インタビューの進捗: ${TOTAL_THEMES}テーマ中${state.themeIndex + 1}テーマ目`}
            className="flex-1"
          />
          <span className="text-xs text-slate-400 flex-shrink-0" aria-hidden="true">
            {state.themeIndex + 1}/{TOTAL_THEMES}
          </span>
        </div>
      </div>

      {/* メッセージ一覧 */}
      <div
        className="flex-1 overflow-y-auto px-6 py-6 space-y-4"
        role="log"
        aria-live="polite"
        aria-label="面接官との会話"
      >
        {state.messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 animate-slide-up ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'assistant' ? 'bg-brand-100 text-brand-600' : 'bg-surface-100 text-slate-500'
              }`}
              aria-hidden="true"
            >
              {msg.role === 'assistant' ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
            </div>
            <div className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
              msg.role === 'assistant'
                ? 'bg-surface-50 text-slate-800 rounded-tl-sm'
                : 'bg-brand-500 text-white rounded-tr-sm'
            }`}>
              <span className="sr-only">{msg.role === 'assistant' ? '面接官: ' : 'あなた: '}</span>
              {msg.content}
            </div>
          </div>
        ))}

        {(state.status === 'waiting' || state.status === 'starting') && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center" aria-hidden="true">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-surface-50 rounded-2xl rounded-tl-sm px-4 py-3">
              <TypingIndicator />
            </div>
          </div>
        )}

        {/* カテゴリ選択 */}
        {state.status === 'awaiting_category_choice' && (
          <div className="animate-fade-in pl-11">
            <p className="text-sm font-medium text-slate-700 mb-3">どれに近いですか？</p>
            <div className="grid grid-cols-2 gap-2 max-w-md">
              {state.categoryOptions.map(option => (
                <Button key={option} variant="secondary" onClick={() => onChooseCategory(option)}>
                  {option}
                </Button>
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 入力エリア */}
      {state.status === 'in_progress' && (
        <div className="px-6 py-4 border-t border-surface-100">
          <div className="flex gap-3">
            <label htmlFor="interview-answer-input" className="sr-only">回答を入力</label>
            <textarea
              id="interview-answer-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
              }}
              rows={2}
              placeholder="ここに回答を入力してください… (Shift+Enter で改行)"
              className="flex-1 text-sm border border-surface-200 rounded-xl px-4 py-3 resize-none
                         focus:outline-none focus:ring-2 focus:ring-brand-300
                         text-slate-700 placeholder:text-slate-300"
            />
            <Button
              onClick={handleSend}
              disabled={input.trim().length < 2}
              icon={<Send className="w-4 h-4" />}
              className="self-end"
            >
              送信
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
