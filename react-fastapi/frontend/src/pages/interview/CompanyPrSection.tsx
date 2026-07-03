/**
 * pages/interview/CompanyPrSection.tsx
 * 企業別カスタマイズ自己PRセクション。
 * streamlit版 company_pr_section.py に相当。
 */
import React, { useState } from 'react'
import { Building2, Plus, X, RotateCcw } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { apiInterviewCompanyPrs, type Message, type CompanyPrResult } from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

interface CompanyEntry { name: string; info: string }

interface CompanyPrSectionProps {
  finalPr: string
  profileText: string
  messages: Message[]
  onBackToVariants: () => void
  onRegenerateVariants: () => void
  onStartOver: () => void
}

export const CompanyPrSection: React.FC<CompanyPrSectionProps> = ({
  finalPr, profileText, messages, onBackToVariants, onRegenerateVariants, onStartOver,
}) => {
  const [inputs, setInputs] = useState<CompanyEntry[]>([{ name: '', info: '' }])
  const [results, setResults] = useState<CompanyPrResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const validInputs = inputs.filter(e => e.name.trim() && e.info.trim())

  const updateEntry = (i: number, field: 'name' | 'info', value: string) => {
    setInputs(prev => prev.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)))
  }

  const removeEntry = (i: number) => {
    setInputs(prev => prev.filter((_, idx) => idx !== i))
  }

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiInterviewCompanyPrs({
        base_pr: finalPr,
        companies: validInputs,
        profile_text: profileText,
        messages,
      })
      setResults(res)
      const failed = res.filter(r => !r.ok)
      if (failed.length > 0) {
        setError('一部の企業でエラーが発生しました: ' + failed.map(f => `${f.company_name}: ${f.error_msg ?? '不明なエラー'}`).join(' / '))
      }
    } catch (err) {
      setError(toFriendlyError(err).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <Building2 className="w-5 h-5 text-brand-500" />
        <h2 className="text-lg font-bold text-slate-900">企業別カスタマイズ自己PR</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">企業情報を入力すると、その企業の求める人物像に合わせた自己PRを自動生成します。企業は動的に追加できます。</p>

      <div className="space-y-3 mb-4">
        {inputs.map((entry, i) => (
          <Card key={i} className="p-4">
            <div className="flex items-start gap-2 mb-2">
              <input
                value={entry.name}
                onChange={e => updateEntry(i, 'name', e.target.value)}
                placeholder="例）株式会社〇〇"
                className="flex-1 text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
              {inputs.length > 1 && (
                <Button variant="ghost" size="sm" onClick={() => removeEntry(i)} icon={<X className="w-4 h-4" />} aria-label="この企業を削除" />
              )}
            </div>
            <textarea
              value={entry.info}
              onChange={e => updateEntry(i, 'info', e.target.value)}
              rows={3}
              placeholder="例）〇〇業界のリーディングカンパニー。チャレンジ精神と協調性を重視。DX推進に注力中。"
              className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
          </Card>
        ))}
      </div>

      <div className="flex gap-2 mb-2">
        <Button variant="secondary" onClick={() => setInputs(prev => [...prev, { name: '', info: '' }])} icon={<Plus className="w-4 h-4" />}>
          企業を追加する
        </Button>
        <Button disabled={validInputs.length === 0} loading={loading} onClick={generate}>
          {validInputs.length}社分のカスタマイズPRを生成する
        </Button>
      </div>
      {validInputs.length === 0 && results.length === 0 && (
        <p className="text-xs text-slate-400 mb-2">企業名と企業情報を入力してから「生成する」を押してください。</p>
      )}
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

      {results.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-semibold text-slate-800 mb-2">生成済みカスタマイズPR</p>
          <div className="space-y-3">
            {results.map((data, i) => (
              <Card key={i} className="p-4">
                <p className="text-sm font-semibold text-brand-700 mb-2">🏢 {data.company_name}</p>
                {data.points.length > 0 && (
                  <p className="text-xs text-slate-500 mb-2">カスタマイズポイント: {data.points.map(p => `・${p}`).join(' / ')}</p>
                )}
                <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{data.pr_text}</p>
                <p className="text-xs text-slate-400 mt-2">{data.pr_text.length}文字</p>
              </Card>
            ))}
          </div>
          <Button variant="secondary" size="sm" className="mt-3" onClick={() => setResults([])} icon={<RotateCcw className="w-3.5 h-3.5" />}>
            すべて再生成する
          </Button>
        </div>
      )}

      <div className="flex gap-2 mt-6 pt-4 border-t border-surface-100">
        <Button variant="secondary" size="sm" onClick={onBackToVariants}>⬅️ 他の案を選び直す</Button>
        <Button variant="secondary" size="sm" onClick={onRegenerateVariants}>🔁 3パターンを再生成する</Button>
        <Button variant="ghost" size="sm" onClick={onStartOver}>🆕 最初からインタビューを受ける</Button>
      </div>
    </div>
  )
}
