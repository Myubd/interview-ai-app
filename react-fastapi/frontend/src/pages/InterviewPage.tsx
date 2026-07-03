/**
 * pages/InterviewPage.tsx
 * 🗣️ 一問一答：自己PR引き出しインタビュー（メインフロー）
 * streamlit版 page_modules/interview/page.py に相当。
 *
 * フロー: 事前入力フォーム → インタビュー本体（②）→ サマリー（③）
 *        → 自己PR生成・選択（④）→ 評価・微調整（⑤）
 *        → 想定質問（⑥）→ 企業別カスタマイズPR（⑦）
 */
import React, { useState } from 'react'
import { Bot, User } from 'lucide-react'
import type { PrVariant } from '@/api/client'
import { useInterviewFlow } from '@/hooks/useInterviewFlow'
import { ProfileForm } from '@/pages/interview/ProfileForm'
import { InterviewChat } from '@/pages/interview/InterviewChat'
import { SummarySection } from '@/pages/interview/SummarySection'
import { PrGenerationSection } from '@/pages/interview/PrGenerationSection'
import { PrEvaluationSection } from '@/pages/interview/PrEvaluationSection'
import { PredictedQuestionsSection } from '@/pages/interview/PredictedQuestionsSection'
import { CompanyPrSection } from '@/pages/interview/CompanyPrSection'

type Phase = 'profile' | 'interview'

export const InterviewPage: React.FC = () => {
  const [phase, setPhase] = useState<Phase>('profile')
  const { state, start, sendAnswer, chooseCategory, reset } = useInterviewFlow()

  // ポストインタビューの選択状態（PR案の選定）はページ側で保持する
  const [selectedVariantIndex, setSelectedVariantIndex] = useState<number | null>(null)
  const [finalPr, setFinalPr] = useState<string>('')
  const [selectedLabel, setSelectedLabel] = useState<string>('')
  const [variantsResetKey, setVariantsResetKey] = useState(0)

  const handleProfileSubmit = (profileText: string) => {
    setPhase('interview')
    start(profileText)
  }

  const handleStartOver = () => {
    reset()
    setSelectedVariantIndex(null)
    setFinalPr('')
    setSelectedLabel('')
    setVariantsResetKey(k => k + 1)
    setPhase('profile')
  }

  const handleSelectVariant = (index: number, variant: PrVariant) => {
    setSelectedVariantIndex(index)
    setFinalPr(variant.content)
    setSelectedLabel(variant.label)
  }

  if (phase === 'profile') {
    return <ProfileForm onSubmit={handleProfileSubmit} />
  }

  if (state.status !== 'complete') {
    return (
      <div className="flex flex-col h-full">
        <div className="px-6 pt-6">
          <h1 className="text-lg font-bold text-slate-900 mb-0.5">🗣️ 一問一答：自己PR引き出しインタビュー</h1>
          <p className="text-xs text-slate-500 mb-2">AIがあなたの回答を踏まえながら質問を考え、強みを掘り下げて、最後に自己PRを作成します。</p>
        </div>
        <InterviewChat
          state={state}
          onSend={sendAnswer}
          onChooseCategory={chooseCategory}
          onReset={handleStartOver}
        />
      </div>
    )
  }

  // ── インタビュー完了後（③〜⑦をスクロールページとして表示） ──────
  return (
    <div className="max-w-2xl mx-auto px-6 py-8 animate-fade-in">
      <h1 className="text-lg font-bold text-slate-900 mb-4">🗣️ 一問一答：自己PR引き出しインタビュー</h1>

      {/* 会話履歴（折りたたみ） */}
      <details className="mb-6">
        <summary className="cursor-pointer text-sm text-slate-500 hover:text-slate-700 mb-2">
          これまでの会話を見る（{state.messages.filter(m => m.role === 'user').length}件の回答）
        </summary>
        <div className="space-y-3 mt-3 max-h-96 overflow-y-auto pr-1">
          {state.messages.map((msg, i) => (
            <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'assistant' ? 'bg-brand-100 text-brand-600' : 'bg-surface-100 text-slate-500'
              }`}>
                {msg.role === 'assistant' ? <Bot className="w-3 h-3" /> : <User className="w-3 h-3" />}
              </div>
              <div className={`max-w-[80%] rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                msg.role === 'assistant' ? 'bg-surface-50 text-slate-700' : 'bg-brand-500 text-white'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
        </div>
      </details>

      <div className="border-t border-surface-100 pt-6 mb-6">
        <SummarySection profileText={state.profileText} messages={state.messages} />
      </div>

      <div className="border-t border-surface-100 pt-6">
        {selectedVariantIndex === null ? (
          <PrGenerationSection
            key={variantsResetKey}
            profileText={state.profileText}
            messages={state.messages}
            onSelect={handleSelectVariant}
          />
        ) : (
          <>
            <PrEvaluationSection
              selectedLabel={selectedLabel}
              finalPr={finalPr}
              onFinalPrChange={setFinalPr}
              profileText={state.profileText}
              messages={state.messages}
            />

            <div className="border-t border-surface-100 mt-6 pt-6">
              <PredictedQuestionsSection
                finalPr={finalPr}
                profileText={state.profileText}
                messages={state.messages}
                sessionId={state.sessionId}
              />
            </div>

            <div className="border-t border-surface-100 mt-6 pt-6">
              <CompanyPrSection
                finalPr={finalPr}
                profileText={state.profileText}
                messages={state.messages}
                onBackToVariants={() => { setSelectedVariantIndex(null); setFinalPr(''); }}
                onRegenerateVariants={() => {
                  setSelectedVariantIndex(null)
                  setFinalPr('')
                  setVariantsResetKey(k => k + 1)
                }}
                onStartOver={handleStartOver}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
