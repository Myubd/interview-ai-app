/**
 * pages/MockInterviewPage.tsx
 * AI模擬面接 UI — 設定 → 面接中 → 評価 の3フェーズ
 */
import React, { useState, useEffect, useRef } from 'react'
import {
  Mic2, Send, Square, RotateCcw, RefreshCw, User, Bot,
  AlertCircle, CheckCircle2, ChevronRight, Loader2, History,
} from 'lucide-react'
import { apiGetPersonas, apiGetThemes, type PersonaInfo, type ThemeInfo } from '@/api/client'
import { useMockInterview } from '@/hooks/useMockInterview'
import { Button, Badge, Spinner, TypingIndicator, Card, ProgressBar } from '@/components/ui'
import type { InterviewDraft } from '@/utils/interviewDraft'

// ── 中断していた面接の再開バナー ─────────────────────────────────
const ResumeBanner: React.FC<{
  draft: InterviewDraft
  onResume: () => void
  onDiscard: () => void
}> = ({ draft, onResume, onDiscard }) => (
  <div
    role="status"
    className="mb-6 p-4 rounded-xl border border-brand-200 bg-brand-50 flex items-start gap-3 animate-fade-in"
  >
    <History className="w-5 h-5 text-brand-500 mt-0.5 flex-shrink-0" />
    <div className="flex-1 min-w-0">
      <p className="text-sm font-medium text-brand-800">前回、途中で終了した面接があります</p>
      <p className="text-xs text-brand-600 mt-0.5">
        {draft.themeTitle || '面接'}・回答済み {draft.messages.filter(m => m.role === 'user').length}件
        の続きから再開できます。
      </p>
      <div className="flex gap-2 mt-3">
        <Button size="sm" onClick={onResume} icon={<RefreshCw className="w-3.5 h-3.5" />}>
          続きから再開
        </Button>
        <Button size="sm" variant="ghost" onClick={onDiscard}>
          破棄して新しく始める
        </Button>
      </div>
    </div>
  </div>
)

// ── フェーズ1: 設定画面 ──────────────────────────────────────────
const SetupPanel: React.FC<{
  personas: PersonaInfo[]
  onStart: (personaKey: string, profileText: string) => void
  loading: boolean
  draft: InterviewDraft | null
  onResumeDraft: () => void
  onDiscardDraft: () => void
}> = ({ personas, onStart, loading, draft, onResumeDraft, onDiscardDraft }) => {
  const [personaKey, setPersonaKey] = useState('standard')
  const [profileText, setProfileText] = useState('')

  return (
    <div className="max-w-xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900 mb-1">AI模擬面接</h1>
        <p className="text-sm text-slate-500">面接官のタイプを選んで練習を始めましょう。</p>
      </div>

      {draft && (
        <ResumeBanner draft={draft} onResume={onResumeDraft} onDiscard={onDiscardDraft} />
      )}

      <div className="mb-6">
        <p className="text-sm font-medium text-slate-700 mb-3" id="persona-type-label">面接官タイプ</p>
        <div className="space-y-2" role="radiogroup" aria-labelledby="persona-type-label">
          {personas.length === 0 ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-4">
              <Loader2 className="w-4 h-4 animate-spin" />読み込み中...
            </div>
          ) : personas.map(p => (
            <label
              key={p.key}
              className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
                personaKey === p.key
                  ? 'border-brand-300 bg-brand-50'
                  : 'border-surface-200 hover:border-surface-300'
              }`}
            >
              <input
                type="radio" name="persona" value={p.key}
                checked={personaKey === p.key}
                onChange={() => setPersonaKey(p.key)}
                className="mt-0.5 accent-brand-500"
              />
              <div>
                <p className="text-sm font-medium text-slate-800">{p.name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{p.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="mb-8">
        <label htmlFor="profile-text" className="text-sm font-medium text-slate-700 mb-1 block">
          プロフィール <span className="text-slate-400 font-normal">(任意)</span>
        </label>
        <p className="text-xs text-slate-400 mb-2">学校・専攻・経験などを入力すると質問がパーソナライズされます。</p>
        <textarea
          id="profile-text"
          value={profileText}
          onChange={e => setProfileText(e.target.value)}
          rows={4}
          placeholder="例: ○○大学 情報工学科 4年。Webアプリ開発のインターンを1年経験..."
          className="w-full text-sm border border-surface-200 rounded-xl px-4 py-3 resize-none
                     focus:outline-none focus:ring-2 focus:ring-brand-300
                     text-slate-700 placeholder:text-slate-300"
        />
      </div>

      <Button
        size="lg"
        onClick={() => onStart(personaKey, profileText)}
        loading={loading}
        className="w-full justify-center"
        icon={<Mic2 className="w-5 h-5" />}
      >
        面接を始める
      </Button>
    </div>
  )
}

// ── フェーズ2: 面接チャット ──────────────────────────────────────
const ChatPanel: React.FC<{
  state: ReturnType<typeof useMockInterview>['state']
  themes: ThemeInfo[]
  onSend: (answer: string) => void
  onFinish: () => void
}> = ({ state, themes, onSend, onFinish }) => {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.messages, state.status])

  const handleSend = () => {
    const text = input.trim()
    if (!text || state.status === 'waiting') return
    setInput('')
    onSend(text)
  }

  const totalThemes = themes.length || 5
  const progress = Math.round(((state.themeIndex + 1) / totalThemes) * 100)

  return (
    <div className="flex flex-col h-full">
      {/* ヘッダー：テーマ進捗 */}
      <div className="px-6 py-3 border-b border-surface-100">
        <div className="flex items-center gap-3 mb-2">
          <Badge variant="info" className="flex-shrink-0">{state.themeTitle || '...'}</Badge>
          <ProgressBar
            value={progress}
            label={`面接の進捗: ${totalThemes}テーマ中${state.themeIndex + 1}テーマ目`}
            className="flex-1"
          />
          <span className="text-xs text-slate-400 flex-shrink-0" aria-hidden="true">
            {state.themeIndex + 1}/{totalThemes}
          </span>
          <Button
            variant="ghost" size="sm"
            onClick={onFinish}
            icon={<Square className="w-4 h-4" />}
            aria-label="面接を終了して評価に進む"
          >
            終了
          </Button>
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
          <div
            key={i}
            className={`flex gap-3 animate-slide-up ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
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

        {state.status === 'waiting' && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center" aria-hidden="true">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-surface-50 rounded-2xl rounded-tl-sm px-4 py-3">
              <TypingIndicator />
            </div>
          </div>
        )}

        {state.status === 'finished' && (
          <div className="flex justify-center animate-fade-in">
            <span className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 rounded-full text-sm">
              <CheckCircle2 className="w-4 h-4" aria-hidden="true" />全テーマ完了
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 入力エリア */}
      {state.status === 'in_progress' && (
        <div className="px-6 py-4 border-t border-surface-100">
          <div className="flex gap-3">
            <label htmlFor="answer-input" className="sr-only">回答を入力</label>
            <textarea
              id="answer-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
              }}
              rows={2}
              placeholder="回答を入力… (Shift+Enter で改行)"
              className="flex-1 text-sm border border-surface-200 rounded-xl px-4 py-3 resize-none
                         focus:outline-none focus:ring-2 focus:ring-brand-300
                         text-slate-700 placeholder:text-slate-300"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim()}
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

// ── フェーズ3: 評価画面 ──────────────────────────────────────────
const EvalPanel: React.FC<{
  state: ReturnType<typeof useMockInterview>['state']
  onEvaluate: () => void
  onReset: () => void
}> = ({ state, onEvaluate, onReset }) => {
  if (state.status === 'evaluating') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4" role="status" aria-live="polite">
        <Spinner className="w-8 h-8" />
        <p className="text-sm text-slate-500">評価を生成しています…</p>
      </div>
    )
  }

  const ev = state.evaluation
  if (!ev) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 animate-fade-in px-6">
        <CheckCircle2 className="w-12 h-12 text-emerald-400" />
        <div className="text-center">
          <p className="text-lg font-bold text-slate-900 mb-1">お疲れさまでした！</p>
          <p className="text-sm text-slate-500">AI による評価レポートを生成しますか？</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={onEvaluate} icon={<ChevronRight className="w-4 h-4" />}>
            評価を見る
          </Button>
          <Button variant="secondary" onClick={onReset} icon={<RotateCcw className="w-4 h-4" />}>
            もう一度
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 overflow-y-auto animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">評価レポート</h2>
          <p className="text-sm text-slate-500">総合スコア: <span className="font-bold text-brand-600">{ev.overall_score}</span> / 100</p>
        </div>
        <Button variant="secondary" size="sm" onClick={onReset} icon={<RotateCcw className="w-4 h-4" />}>
          もう一度
        </Button>
      </div>

      {/* 項目別スコア */}
      <Card className="p-5 mb-4">
        <p className="text-xs font-semibold text-slate-600 mb-3">項目別スコア</p>
        {Object.entries(ev.axes ?? {}).map(([axis, score]) => (
          <div key={axis} className="flex items-center gap-3 mb-2">
            <span className="text-xs text-slate-500 w-24 flex-shrink-0">{axis}</span>
            <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-400 rounded-full transition-all"
                style={{ width: `${score}%` }}
              />
            </div>
            <span className="text-xs font-mono text-slate-600 w-8 text-right">{score}</span>
          </div>
        ))}
      </Card>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <Card className="p-4">
          <p className="text-xs font-semibold text-emerald-700 mb-2">強み</p>
          <ul className="space-y-1.5">
            {(ev.strengths ?? []).map((s, i) => (
              <li key={i} className="text-xs text-slate-600 flex gap-1.5">
                <span className="text-emerald-400 flex-shrink-0">✓</span>{s}
              </li>
            ))}
          </ul>
        </Card>
        <Card className="p-4">
          <p className="text-xs font-semibold text-amber-700 mb-2">改善点</p>
          <ul className="space-y-1.5">
            {(ev.improvements ?? []).map((s, i) => (
              <li key={i} className="text-xs text-slate-600 flex gap-1.5">
                <span className="text-amber-400 flex-shrink-0">△</span>{s}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {(ev.next_steps ?? []).length > 0 && (
        <Card className="p-4">
          <p className="text-xs font-semibold text-brand-700 mb-2">次回の練習ポイント</p>
          <ul className="space-y-1.5">
            {ev.next_steps.map((s, i) => (
              <li key={i} className="text-xs text-slate-600 flex gap-1.5">
                <span className="text-brand-400 flex-shrink-0">→</span>{s}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {ev.overall_summary && (
        <Card className="p-4 mt-4">
          <p className="text-xs font-semibold text-slate-600 mb-2">総合コメント</p>
          <p className="text-xs text-slate-700 leading-relaxed">{ev.overall_summary}</p>
        </Card>
      )}

      {(ev.model_answers ?? []).length > 0 && (
        <Card className="p-4 mt-4">
          <p className="text-xs font-semibold text-violet-700 mb-3">模範回答例</p>
          <div className="space-y-4">
            {ev.model_answers!.map((item, i) => (
              <div key={i}>
                <p className="text-xs font-medium text-slate-600 mb-1">Q. {item.question}</p>
                <p className="text-xs text-slate-700 bg-violet-50 rounded-lg px-3 py-2 leading-relaxed">
                  {item.model_answer}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

// ── メインページ ─────────────────────────────────────────────────
type Phase = 'setup' | 'interview' | 'eval'

export const MockInterviewPage: React.FC = () => {
  const [phase, setPhase] = useState<Phase>('setup')
  const [personas, setPersonas] = useState<PersonaInfo[]>([])
  const [themes, setThemes] = useState<ThemeInfo[]>([])
  const [draft, setDraft] = useState<InterviewDraft | null>(null)
  const [retrying, setRetrying] = useState(false)

  const {
    state, start, sendAnswer, retryLastAnswer, evaluate, reset,
    getSavedDraft, resumeFromDraft, discardDraft,
  } = useMockInterview()

  useEffect(() => {
    apiGetPersonas().then(setPersonas).catch(console.error)
    apiGetThemes().then(setThemes).catch(console.error)
    // 前回中断した面接がないか確認し、あれば再開バナーを出す
    setDraft(getSavedDraft())
  }, [getSavedDraft])

  const handleStart = async (personaKey: string, profileText: string) => {
    await start({ industryKey: 'general', personaKey, profileText })
    setPhase('interview')
  }

  const handleResumeDraft = () => {
    if (!draft) return
    resumeFromDraft(draft)
    setDraft(null)
    setPhase('interview')
  }

  const handleDiscardDraft = () => {
    discardDraft()
    setDraft(null)
  }

  const handleFinish = () => setPhase('eval')

  const handleReset = () => {
    reset()
    setDraft(null)
    setPhase('setup')
  }

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await retryLastAnswer()
    } finally {
      setRetrying(false)
    }
  }

  // エラー：回答内容は state.messages に残っているので、
  // 可能な場合は「再送信」で会話を失わずに続行できるようにする
  if (state.status === 'error') {
    const hasConversation = state.messages.length > 0
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 animate-fade-in px-6" role="alert">
        <AlertCircle className="w-10 h-10 text-red-400" aria-hidden="true" />
        <div className="text-center max-w-sm">
          <p className="text-sm text-red-600 font-medium">{state.error}</p>
          {state.errorHint && (
            <p className="text-xs text-slate-500 mt-1.5">{state.errorHint}</p>
          )}
          {hasConversation && (
            <p className="text-xs text-slate-400 mt-3">
              これまでの回答（{state.messages.filter(m => m.role === 'user').length}件）は保持されています。
            </p>
          )}
        </div>
        <div className="flex gap-3">
          {state.canRetry && state.lastAnswer && (
            <Button onClick={handleRetry} loading={retrying} icon={<RefreshCw className="w-4 h-4" />}>
              再送信する
            </Button>
          )}
          <Button variant="secondary" onClick={handleReset} icon={<RotateCcw className="w-4 h-4" />}>
            最初からやり直す
          </Button>
        </div>
      </div>
    )
  }

  if (phase === 'eval' || state.status === 'finished' || state.status === 'evaluating' || state.status === 'evaluated') {
    return <EvalPanel state={state} onEvaluate={evaluate} onReset={handleReset} />
  }

  if (phase === 'interview') {
    return (
      <div className="flex flex-col h-full">
        <ChatPanel state={state} themes={themes} onSend={sendAnswer} onFinish={handleFinish} />
      </div>
    )
  }

  return (
    <SetupPanel
      personas={personas}
      onStart={handleStart}
      loading={state.status === 'starting'}
      draft={draft}
      onResumeDraft={handleResumeDraft}
      onDiscardDraft={handleDiscardDraft}
    />
  )
}
