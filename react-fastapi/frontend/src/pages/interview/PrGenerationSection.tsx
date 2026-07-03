/**
 * pages/interview/PrGenerationSection.tsx
 * 自己PR生成セクション（ステップ1: 生成・ステップ2: 3案選択）。
 * streamlit版 pr_generation_section.py に相当。
 */
import React, { useState } from 'react'
import { Sparkles, RotateCcw } from 'lucide-react'
import { Button, Card } from '@/components/ui'
import { apiInterviewPrVariants, type Message, type PrVariant } from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

interface PrGenerationSectionProps {
  profileText: string
  messages: Message[]
  onSelect: (index: number, variant: PrVariant) => void
}

export const PrGenerationSection: React.FC<PrGenerationSectionProps> = ({ profileText, messages, onSelect }) => {
  const [variants, setVariants] = useState<PrVariant[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await apiInterviewPrVariants({ profile_text: profileText, messages })
      setVariants(result)
    } catch (err) {
      setError(toFriendlyError(err).message)
    } finally {
      setLoading(false)
    }
  }

  if (!variants) {
    return (
      <div>
        <Button onClick={generate} loading={loading} icon={<Sparkles className="w-4 h-4" />}>
          この内容で自己PRを自動生成する（3パターン）
        </Button>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        {loading && (
          <p className="text-xs text-slate-400 mt-2">
            これまでの回答から、3パターンの自己PRを生成中...（複数案生成のため通常より時間がかかります）
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      <p className="text-sm font-semibold text-slate-800 mb-1">📝 3つの案から選んでください</p>
      <p className="text-xs text-slate-500 mb-4">切り口の異なる3パターンを生成しました。気に入ったものを選ぶと、評価・微調整ができます。</p>
      <div className="space-y-3">
        {variants.map((variant, i) => (
          <Card key={i} className="p-4">
            <p className="text-sm font-semibold text-brand-700 mb-2">{variant.label}</p>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap mb-3">{variant.content}</p>
            <Button size="sm" onClick={() => onSelect(i, variant)}>この案を選ぶ</Button>
          </Card>
        ))}
      </div>
      <Button variant="secondary" size="sm" className="mt-4" onClick={() => setVariants(null)} icon={<RotateCcw className="w-3.5 h-3.5" />}>
        3パターンを再生成する
      </Button>
    </div>
  )
}
