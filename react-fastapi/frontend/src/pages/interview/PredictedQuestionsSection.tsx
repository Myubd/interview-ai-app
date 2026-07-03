/**
 * pages/interview/PredictedQuestionsSection.tsx
 * 面接想定質問＆模範回答例セクション（自己PR＋会話履歴ベース版）。
 * streamlit版 predicted_questions_section.py に相当。
 */
import React, { useState, useEffect } from 'react'
import { MessageCircle, RefreshCw, Star } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import {
  apiGeneratePredictedQuestionsFromPr,
  apiSavePredictedQuestionsPrBased,
  apiIsFavorited,
  apiDeleteFavoriteByItem,
  type Message,
  type PredictedQuestion,
} from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

const CATEGORY_ORDER = ['deep_dive', 'motivation', 'weakness', 'situational']

interface PredictedQuestionsSectionProps {
  finalPr: string
  profileText: string
  messages: Message[]
  sessionId: number | null
  companyName?: string | null
}

export const PredictedQuestionsSection: React.FC<PredictedQuestionsSectionProps> = ({
  finalPr, profileText, messages, sessionId, companyName,
}) => {
  const [questions, setQuestions] = useState<PredictedQuestion[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isFavorited, setIsFavorited] = useState(false)
  const [favLoading, setFavLoading] = useState(false)

  useEffect(() => {
    if (!sessionId) return
    apiIsFavorited('question_set', { session_id: sessionId })
      .then(res => setIsFavorited(res.favorited))
      .catch(() => {})
  }, [sessionId, questions])

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiGeneratePredictedQuestionsFromPr({ pr_text: finalPr, profile_text: profileText, messages })
      setQuestions(res.questions)
    } catch (err) {
      setError(toFriendlyError(err).message)
    } finally {
      setLoading(false)
    }
  }

  const toggleFavorite = async () => {
    if (!sessionId) return
    setFavLoading(true)
    try {
      if (isFavorited) {
        await apiDeleteFavoriteByItem('question_set', { session_id: sessionId })
        setIsFavorited(false)
      } else {
        await apiSavePredictedQuestionsPrBased({ questions: questions ?? [], company_name: companyName ?? null })
        setIsFavorited(true)
      }
    } finally {
      setFavLoading(false)
    }
  }

  const grouped = new Map<string, PredictedQuestion[]>()
  for (const q of questions ?? []) {
    const list = grouped.get(q.category) ?? []
    list.push(q)
    grouped.set(q.category, list)
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <MessageCircle className="w-5 h-5 text-brand-500" />
        <h2 className="text-lg font-bold text-slate-900">面接想定質問＆模範回答例</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">この自己PRを読んだ面接官が次に聞きそうな質問と、そのまま話せる模範回答例を生成します。</p>

      {!questions ? (
        <div>
          <Button onClick={generate} loading={loading}>💬 想定質問を生成する（8問）</Button>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </div>
      ) : (
        <div>
          <div className="space-y-4">
            {CATEGORY_ORDER.map(catKey => {
              const items = grouped.get(catKey)
              if (!items || items.length === 0) return null
              return (
                <div key={catKey}>
                  <p className="text-sm font-semibold text-slate-700 mb-2">{items[0].category_label}</p>
                  <div className="space-y-2">
                    {items.map((item, i) => (
                      <details key={i} className="group">
                        <summary className="cursor-pointer text-sm text-slate-800 font-medium px-3 py-2 rounded-lg bg-surface-50 hover:bg-surface-100 transition-colors">
                          Q: {item.question}
                        </summary>
                        <Card className="p-3 mt-1.5">
                          <p className="text-xs font-semibold text-slate-500 mb-1">模範回答例:</p>
                          <p className="text-sm text-slate-700 leading-relaxed">{item.model_answer}</p>
                        </Card>
                      </details>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="flex gap-2 mt-4">
            <Button variant="secondary" size="sm" onClick={() => setQuestions(null)} icon={<RefreshCw className="w-3.5 h-3.5" />}>
              想定質問を再生成する
            </Button>
            <Button
              variant={isFavorited ? 'primary' : 'secondary'}
              size="sm"
              loading={favLoading}
              disabled={!sessionId}
              onClick={toggleFavorite}
              icon={<Star className="w-3.5 h-3.5" />}
            >
              {isFavorited ? 'お気に入り解除' : 'お気に入りに追加'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
