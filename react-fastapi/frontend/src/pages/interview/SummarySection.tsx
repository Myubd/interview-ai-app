/**
 * pages/interview/SummarySection.tsx
 * 面接サマリー（強み・弱み・向いている職種・業界別フィット度）セクション。
 * streamlit版 summary_section.py に相当。
 */
import React, { useState } from 'react'
import { BarChart3, RefreshCw } from 'lucide-react'
import { Button, Card, Spinner } from '@/components/ui'
import { apiInterviewSummary, type Message, type InterviewSummary } from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

interface SummarySectionProps {
  profileText: string
  messages: Message[]
}

export const SummarySection: React.FC<SummarySectionProps> = ({ profileText, messages }) => {
  const [summary, setSummary] = useState<InterviewSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiInterviewSummary({ profile_text: profileText, messages })
      setSummary(result)
    } catch (err) {
      setError(toFriendlyError(err).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 className="w-5 h-5 text-brand-500" />
        <h2 className="text-lg font-bold text-slate-900">面接サマリー（強み・弱み・向いている職種）</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">インタビュー内容から、あなたの特性と業界別フィット度を分析します。</p>

      {!summary ? (
        <div>
          <Button onClick={generate} loading={loading}>🔍 面接サマリーを生成する</Button>
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </div>
      ) : (
        <div className="space-y-4">
          {summary.strengths?.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">💪 強み</p>
              <div className="space-y-2">
                {summary.strengths.map((item, i) => (
                  <Card key={i} className="p-3">
                    <p className="text-sm font-medium text-slate-800">{item.point}</p>
                    {item.evidence && <p className="text-xs text-slate-500 mt-1">根拠: {item.evidence}</p>}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {summary.weaknesses?.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">🌱 成長余地</p>
              <div className="space-y-2">
                {summary.weaknesses.map((item, i) => (
                  <Card key={i} className="p-3">
                    <p className="text-sm font-medium text-slate-800">{item.point}</p>
                    {item.evidence && <p className="text-xs text-slate-500 mt-1">ヒント: {item.evidence}</p>}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {summary.fit_roles && (
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">🎯 向いている職種・環境</p>
              <div className="text-sm text-brand-800 bg-brand-50 rounded-lg px-3 py-2">{summary.fit_roles}</div>
            </div>
          )}

          {summary.industry_fit && Object.keys(summary.industry_fit).length > 0 && (
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">🏢 業界別フィット度</p>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(summary.industry_fit).map(([key, data]) => (
                  <Card key={key} className="p-3">
                    <p className="text-sm font-medium text-slate-800">{key}</p>
                    <p className="text-sm">{'⭐'.repeat(data.score)}{'☆'.repeat(Math.max(0, 5 - data.score))} <span className="text-xs text-slate-400">{data.score}/5</span></p>
                    {data.reason && <p className="text-xs text-slate-500 mt-1">{data.reason}</p>}
                  </Card>
                ))}
              </div>
            </div>
          )}

          {summary.overall_comment && (
            <div>
              <p className="text-sm font-semibold text-slate-700 mb-2">💬 総評</p>
              <div className="text-sm text-emerald-800 bg-emerald-50 rounded-lg px-3 py-2">{summary.overall_comment}</div>
            </div>
          )}

          <Button variant="secondary" size="sm" onClick={() => setSummary(null)} icon={<RefreshCw className="w-3.5 h-3.5" />}>
            サマリーを再生成する
          </Button>
        </div>
      )}

      {loading && !summary && (
        <div className="flex items-center gap-2 text-sm text-slate-500 mt-3">
          <Spinner className="w-4 h-4" />インタビュー内容を分析中...
        </div>
      )}
    </div>
  )
}
