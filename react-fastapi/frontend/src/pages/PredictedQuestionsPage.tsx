/**
 * pages/PredictedQuestionsPage.tsx
 * 想定質問生成（RAGベース版）。
 *
 * 既存コードとの対応:
 *   streamlit版 page_modules/predict_questions_page.py が相当する。
 *   質問生成本体は question_prediction.py（shared/ に一本化済み）を
 *   backend/services/prediction_service.py 経由で呼び出す。
 *
 * Streamlit版との違い:
 *   - 「先にサイドバーからセッションを保存」という前提を撤廃し、
 *     お気に入り保存時にこの機能専用のセッションを暗黙的に作成する
 *     （詳細は shared/MIGRATION_GUIDE.md ではなく、本機能実装時の設計メモを参照）。
 */
import React, { useEffect, useState } from 'react'
import { ChevronDown, Sparkles, Star } from 'lucide-react'
import {
  apiGetKnowledgeBases,
  apiGeneratePredictedQuestions,
  apiSavePredictedQuestionsAndFavorite,
  type KnowledgeBase,
  type PredictedQuestion,
} from '@/api/client'
import { Button, Card, EmptyState, Spinner, Toast } from '@/components/ui'

// question_prediction.CATEGORY_LABELS と同じ並び順（shared/question_prediction.py 参照）
const CATEGORY_ORDER = ['deep_dive', 'motivation', 'weakness', 'situational']

export const PredictedQuestionsPage: React.FC = () => {
  const [companies, setCompanies] = useState<KnowledgeBase[]>([])
  const [loadingCompanies, setLoadingCompanies] = useState(true)
  const [selectedKbId, setSelectedKbId] = useState<number | null>(null)

  const [generating, setGenerating] = useState(false)
  const [questions, setQuestions] = useState<PredictedQuestion[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const [toast, setToast] = useState<{ msg: string; variant: 'success' | 'error' } | null>(null)
  const showToast = (msg: string, variant: 'success' | 'error' = 'success') => {
    setToast({ msg, variant })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    apiGetKnowledgeBases('company')
      .then(list => {
        setCompanies(list)
        if (list.length > 0) setSelectedKbId(list[0].id)
      })
      .catch(console.error)
      .finally(() => setLoadingCompanies(false))
  }, [])

  const selectedCompany = companies.find(c => c.id === selectedKbId) ?? null

  const handleGenerate = async () => {
    if (!selectedKbId) return
    setGenerating(true)
    setError(null)
    setQuestions(null)
    setSaved(false)
    try {
      const res = await apiGeneratePredictedQuestions(selectedKbId)
      setQuestions(res.questions)
    } catch (err) {
      setError(String(err))
    } finally {
      setGenerating(false)
    }
  }

  const handleSaveAndFavorite = async () => {
    if (!selectedKbId || !selectedCompany || !questions) return
    setSaving(true)
    try {
      await apiSavePredictedQuestionsAndFavorite({
        company_kb_id: selectedKbId,
        company_name: selectedCompany.name,
        questions,
      })
      setSaved(true)
      showToast('お気に入りに保存しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  const grouped = React.useMemo(() => {
    if (!questions) return []
    return CATEGORY_ORDER
      .map(cat => ({ category: cat, items: questions.filter(q => q.category === cat) }))
      .filter(g => g.items.length > 0)
  }, [questions])

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-brand-500" />
          想定質問生成
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          共通の履歴書と、選んだ企業の情報から、面接本番で聞かれそうな質問と模範回答例を生成します。
        </p>
      </div>

      {loadingCompanies ? (
        <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
      ) : companies.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="w-12 h-12" />}
          title="企業情報が登録されていません"
          description="「ナレッジベース」ページで企業情報を登録すると、想定質問を生成できます。"
        />
      ) : (
        <>
          <Card className="p-5 mb-6">
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">企業を選択</label>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <select
                  value={selectedKbId ?? ''}
                  onChange={e => setSelectedKbId(Number(e.target.value))}
                  className="w-full appearance-none text-sm border border-surface-200 rounded-lg pl-3 pr-9 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700 bg-white"
                >
                  {companies.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <Button onClick={handleGenerate} loading={generating} icon={<Sparkles className="w-4 h-4" />}>
                {questions ? '再生成' : '生成する'}
              </Button>
            </div>
          </Card>

          {error && (
            <Card className="p-4 mb-6 border-red-200 bg-red-50">
              <p className="text-sm text-red-600">{error}</p>
            </Card>
          )}

          {generating && !questions && (
            <div className="flex flex-col items-center gap-3 py-16 text-slate-400">
              <Spinner className="w-8 h-8" />
              <p className="text-sm">想定質問を生成しています...</p>
            </div>
          )}

          {questions && questions.length > 0 && (
            <div className="space-y-6 animate-slide-up">
              {grouped.map(group => (
                <section key={group.category}>
                  <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    {group.items[0].category_label}
                  </h2>
                  <ul className="space-y-2">
                    {group.items.map((q, i) => (
                      <QuestionItem key={`${group.category}-${i}`} question={q} />
                    ))}
                  </ul>
                </section>
              ))}

              <div className="flex justify-end pt-2">
                {saved ? (
                  <Button variant="secondary" size="sm" disabled icon={<Star className="w-4 h-4 fill-current text-accent-400" />}>
                    お気に入りに保存済み
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSaveAndFavorite}
                    loading={saving}
                    icon={<Star className="w-4 h-4" />}
                  >
                    お気に入りに保存
                  </Button>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {toast && <Toast message={toast.msg} variant={toast.variant} />}
    </div>
  )
}

const QuestionItem: React.FC<{ question: PredictedQuestion }> = ({ question }) => {
  const [open, setOpen] = useState(false)
  return (
    <Card className="p-0 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface-50 transition-colors"
        aria-expanded={open}
      >
        <p className="text-sm font-medium text-slate-800">{question.question}</p>
        <ChevronDown className={`w-4 h-4 text-slate-400 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-surface-100">
          <p className="text-xs font-semibold text-slate-400 mb-1">模範回答例</p>
          <p className="text-sm text-slate-600 whitespace-pre-wrap leading-relaxed">{question.model_answer}</p>
        </div>
      )}
    </Card>
  )
}
