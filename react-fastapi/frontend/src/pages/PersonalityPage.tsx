/**
 * pages/PersonalityPage.tsx
 * 性格診断・適性検査（ビッグファイブ30問）。
 *
 * 既存コードとの対応:
 *   streamlit版 page_modules/personality_page.py + personality_assessment.py が相当する。
 *   personality_assessment.py は shared/ に一本化済み（backend/services/personality_service.py 経由で呼び出す）。
 *
 * Streamlit版との違い:
 *   - 「先にサイドバーからセッションを保存」という前提を撤廃し、
 *     お気に入り保存時にこの機能専用のセッションを暗黙的に作成する
 *     （想定質問生成ページと同じ設計）。
 */
import React, { useEffect, useState } from 'react'
import { Brain, ChevronLeft, ChevronRight, RotateCcw, Sparkles, Star } from 'lucide-react'
import {
  apiGetPersonalityQuestions,
  apiSubmitPersonality,
  apiSavePersonalityAndFavorite,
  type PersonalityQuestionsResponse,
  type PersonalityResult,
} from '@/api/client'
import { Button, Card, Spinner, Toast, ProgressBar } from '@/components/ui'

const AXIS_SHORT_LABEL: Record<string, string> = {
  extraversion: '外向性',
  conscientiousness: '誠実性',
  agreeableness: '協調性',
  openness: '開放性',
  neuroticism: '情緒安定性',
}

type Phase = 'intro' | 'quiz' | 'generating' | 'result' | 'error'

export const PersonalityPage: React.FC = () => {
  const [info, setInfo] = useState<PersonalityQuestionsResponse | null>(null)
  const [loadingInfo, setLoadingInfo] = useState(true)

  const [phase, setPhase] = useState<Phase>('intro')
  const [currentIdx, setCurrentIdx] = useState(0) // 0-based
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [result, setResult] = useState<PersonalityResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [toast, setToast] = useState<{ msg: string; variant: 'success' | 'error' } | null>(null)
  const showToast = (msg: string, variant: 'success' | 'error' = 'success') => {
    setToast({ msg, variant })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    apiGetPersonalityQuestions()
      .then(setInfo)
      .catch(err => setError(String(err)))
      .finally(() => setLoadingInfo(false))
  }, [])

  const totalQuestions = info?.total_questions ?? 0
  const answeredCount = Object.keys(answers).length
  const canFinish = totalQuestions > 0 && answeredCount >= totalQuestions * 0.8

  const handleAnswer = (questionId: number, score: number) => {
    setAnswers(prev => ({ ...prev, [questionId]: score }))
    if (info && currentIdx < info.questions.length - 1) {
      setCurrentIdx(idx => idx + 1)
    }
  }

  const handleFinish = async () => {
    setPhase('generating')
    setError(null)
    try {
      const res = await apiSubmitPersonality(answers)
      setResult(res)
      setPhase('result')
    } catch (err) {
      setError(String(err))
      setPhase('error')
    }
  }

  const handleRetry = () => {
    setAnswers({})
    setCurrentIdx(0)
    setResult(null)
    setSaved(false)
    setError(null)
    setPhase('intro')
  }

  const handleSaveAndFavorite = async () => {
    if (!result) return
    setSaving(true)
    try {
      await apiSavePersonalityAndFavorite({
        answers,
        axis_scores: result.axis_scores,
        result,
      })
      setSaved(true)
      showToast('お気に入りに保存しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loadingInfo) {
    return (
      <div className="flex justify-center py-24">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  if (!info) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <Card className="p-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-600">設問の読み込みに失敗しました。{error}</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Brain className="w-5 h-5 text-brand-500" />
          性格診断・適性検査
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          ビッグファイブ（5因子モデル）準拠の{totalQuestions}問で、就活に活かせるあなたのパーソナリティを分析します。
        </p>
      </div>

      {phase === 'intro' && (
        <Card className="p-6">
          <ul className="text-sm text-slate-600 space-y-1.5 mb-6">
            <li><b>所要時間:</b> 約3〜5分</li>
            <li><b>設問数:</b> {totalQuestions}問（5段階回答）</li>
            <li><b>測定軸:</b> {Object.values(info.axes).map(a => a.split('（')[0]).join(' / ')}</li>
          </ul>
          <p className="text-sm text-slate-500 mb-6">
            各設問に対して、自分にどの程度当てはまるかを5段階で回答してください。「正解」はありません。直感で答えるのがおすすめです。
          </p>
          <Button size="lg" className="w-full justify-center" onClick={() => setPhase('quiz')}>
            診断を開始する
          </Button>
        </Card>
      )}

      {phase === 'quiz' && (
        <QuizView
          info={info}
          currentIdx={currentIdx}
          setCurrentIdx={setCurrentIdx}
          answers={answers}
          onAnswer={handleAnswer}
          onFinish={handleFinish}
          canFinish={canFinish}
          answeredCount={answeredCount}
        />
      )}

      {phase === 'generating' && (
        <div className="flex flex-col items-center gap-3 py-16 text-slate-400">
          <Spinner className="w-8 h-8" />
          <p className="text-sm">回答を分析中...（少しお待ちください）</p>
        </div>
      )}

      {phase === 'error' && (
        <Card className="p-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-600 mb-4">分析に失敗しました: {error}\nOllamaの状態をご確認ください。</p>
          <Button variant="secondary" icon={<RotateCcw className="w-4 h-4" />} onClick={() => setPhase('quiz')}>
            設問に戻る
          </Button>
        </Card>
      )}

      {phase === 'result' && result && (
        <ResultView
          result={result}
          saved={saved}
          saving={saving}
          onSave={handleSaveAndFavorite}
          onRetry={handleRetry}
        />
      )}

      {toast && <Toast message={toast.msg} variant={toast.variant} />}
    </div>
  )
}

// ============================================================
// 設問フェーズ
// ============================================================

const QuizView: React.FC<{
  info: PersonalityQuestionsResponse
  currentIdx: number
  setCurrentIdx: (updater: (idx: number) => number) => void
  answers: Record<number, number>
  onAnswer: (questionId: number, score: number) => void
  onFinish: () => void
  canFinish: boolean
  answeredCount: number
}> = ({ info, currentIdx, setCurrentIdx, answers, onAnswer, onFinish, canFinish, answeredCount }) => {
  const q = info.questions[currentIdx]
  const isLast = currentIdx === info.questions.length - 1
  const scaleEntries = Object.entries(info.scale_labels).sort((a, b) => Number(a[0]) - Number(b[0]))

  return (
    <div>
      <ProgressBar
        value={currentIdx + 1}
        max={info.questions.length}
        label={`設問 ${currentIdx + 1} / ${info.questions.length}`}
        className="mb-2"
      />
      <p className="text-xs text-slate-400 mb-4">設問 {currentIdx + 1} / {info.questions.length}</p>

      <Card className="p-6 mb-4">
        <p className="font-medium text-slate-900 mb-5">Q{q.id}. {q.text}</p>
        <div className="grid grid-cols-5 gap-2">
          {scaleEntries.map(([scoreStr, label]) => {
            const score = Number(scoreStr)
            const selected = answers[q.id] === score
            return (
              <button
                key={score}
                onClick={() => onAnswer(q.id, score)}
                title={label}
                className={`flex flex-col items-center justify-center gap-1 py-3 rounded-lg border text-sm font-semibold transition-colors ${
                  selected
                    ? 'bg-brand-500 border-brand-500 text-white'
                    : 'bg-white border-surface-200 text-slate-600 hover:border-brand-300 hover:bg-brand-50'
                }`}
              >
                {score}
              </button>
            )
          })}
        </div>
        <div className="grid grid-cols-5 gap-2 mt-2">
          {scaleEntries.map(([scoreStr, label]) => (
            <p key={scoreStr} className="text-[10px] text-slate-400 text-center leading-tight">{label}</p>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={currentIdx === 0}
          icon={<ChevronLeft className="w-4 h-4" />}
          onClick={() => setCurrentIdx(idx => Math.max(0, idx - 1))}
        >
          前へ
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={isLast}
          icon={<ChevronRight className="w-4 h-4" />}
          onClick={() => setCurrentIdx(idx => Math.min(info.questions.length - 1, idx + 1))}
        >
          次へ
        </Button>
        <div className="flex-1" />
        {canFinish ? (
          <Button size="sm" icon={<Sparkles className="w-4 h-4" />} onClick={onFinish}>
            結果を見る（{answeredCount}/{info.questions.length}問回答済み）
          </Button>
        ) : (
          <p className="text-xs text-slate-400">
            あと{Math.ceil(info.questions.length * 0.8) - answeredCount}問以上回答すると結果を表示できます
          </p>
        )}
      </div>
    </div>
  )
}

// ============================================================
// 結果フェーズ
// ============================================================

const ResultView: React.FC<{
  result: PersonalityResult
  saved: boolean
  saving: boolean
  onSave: () => void
  onRetry: () => void
}> = ({ result, saved, saving, onSave, onRetry }) => {
  const consistencyLevel =
    result.consistency_score >= 85 ? { label: '高', color: 'text-emerald-600' }
      : result.consistency_score >= 70 ? { label: '普通', color: 'text-amber-600' }
      : { label: '低', color: 'text-red-600' }

  return (
    <div className="space-y-6 animate-slide-up">
      {result.personality_summary && (
        <Card className="p-5 bg-brand-50 border-brand-100">
          <p className="text-sm text-slate-700 leading-relaxed">{result.personality_summary}</p>
        </Card>
      )}

      <section>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">🔢 5因子スコア</h2>
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(result.axis_scores).map(([axis, score]) => (
            <Card key={axis} className="p-3 text-center">
              <p className="text-[11px] text-slate-400 mb-1">{AXIS_SHORT_LABEL[axis] ?? axis}</p>
              <p className="text-lg font-bold text-brand-600">{score.toFixed(1)}</p>
              <p className="text-[10px] text-slate-400">/ 5</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-slate-700 mb-2">🎯 回答信頼度</h2>
        <p className={`text-sm font-medium ${consistencyLevel.color}`}>
          {result.consistency_score}/100 （信頼度: {consistencyLevel.label}）
        </p>
      </section>

      {result.strengths.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">💪 強み</h2>
          <div className="space-y-2">
            {result.strengths.map((item, i) => (
              <Card key={i} className="p-3">
                <p className="text-sm font-medium text-slate-800">{item.point}</p>
                {item.detail && <p className="text-xs text-slate-500 mt-0.5">{item.detail}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}

      {result.cautions.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">🌱 成長余地</h2>
          <div className="space-y-2">
            {result.cautions.map((item, i) => (
              <Card key={i} className="p-3">
                <p className="text-sm font-medium text-slate-800">{item.point}</p>
                {item.hint && <p className="text-xs text-slate-500 mt-0.5">ヒント: {item.hint}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}

      {result.fit_environments && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">🎯 向いている職種・環境</h2>
          <Card className="p-4 bg-brand-50 border-brand-100">
            <p className="text-sm text-slate-700">{result.fit_environments}</p>
          </Card>
        </section>
      )}

      {Object.keys(result.industry_fit).length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">🏢 業界別フィット度</h2>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(result.industry_fit).map(([industry, entry]) => (
              <Card key={industry} className="p-3">
                <p className="text-sm font-medium text-slate-800">{industry}</p>
                <p className="text-amber-500 text-sm">{'⭐'.repeat(entry.score)}{'☆'.repeat(5 - entry.score)} {entry.score}/5</p>
                {entry.reason && <p className="text-xs text-slate-500 mt-1">{entry.reason}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}

      {result.recommended_roles.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">💼 おすすめ職種</h2>
          <div className="space-y-2">
            {result.recommended_roles.map((item, i) => (
              <Card key={i} className="p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-sm font-medium text-slate-800">{item.role}</p>
                  <p className="text-xs text-slate-400">適性スコア {item.score.toFixed(2)}</p>
                </div>
                <ProgressBar value={item.score} max={5} />
              </Card>
            ))}
          </div>
        </section>
      )}

      {result.interview_strengths.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">🎤 面接でアピールできる強み</h2>
          <div className="space-y-1.5">
            {result.interview_strengths.map((s, i) => (
              <p key={i} className="text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{s}</p>
            ))}
          </div>
        </section>
      )}

      {result.interview_risks.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">⚠️ 面接で注意するポイント</h2>
          <div className="space-y-1.5">
            {result.interview_risks.map((s, i) => (
              <p key={i} className="text-sm text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{s}</p>
            ))}
          </div>
        </section>
      )}

      {result.interview_tips && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">💬 面接での活かし方</h2>
          <p className="text-sm text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2">{result.interview_tips}</p>
        </section>
      )}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button variant="ghost" size="sm" icon={<RotateCcw className="w-4 h-4" />} onClick={onRetry}>
          もう一度診断する
        </Button>
        {saved ? (
          <Button variant="secondary" size="sm" disabled icon={<Star className="w-4 h-4 fill-current text-accent-400" />}>
            お気に入りに保存済み
          </Button>
        ) : (
          <Button variant="secondary" size="sm" loading={saving} icon={<Star className="w-4 h-4" />} onClick={onSave}>
            お気に入りに保存
          </Button>
        )}
      </div>
    </div>
  )
}
