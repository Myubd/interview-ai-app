/**
 * pages/interview/PrEvaluationSection.tsx
 * 自己PR評価・微調整セクション（ステップ3）。
 * streamlit版 pr_evaluation_section.py に相当。
 */
import React, { useState } from 'react'
import { Search, Wrench, RefreshCw } from 'lucide-react'
import { Button, Card, ProgressBar } from '@/components/ui'
import {
  apiInterviewPrEvaluate,
  apiInterviewPrRefine,
  type Message,
  type PrEvaluation,
} from '@/api/client'
import { toFriendlyError } from '@/utils/errorMessages'

const PRESET_LABELS: Record<string, string> = {
  concise: '✂️ 簡潔に',
  passionate: '🔥 熱意を強く',
  formal: '🎩 フォーマルに',
  specific: '🔢 具体性を強化',
}

const PRESET_INSTRUCTIONS: Record<string, string> = {
  concise: '全体的にもっと簡潔にしてください。冗長な表現を削り、要点を絞ってください。',
  passionate: 'もっと熱意や意欲が伝わる表現にしてください。ただし誇張しすぎず、誠実さは保ってください。',
  formal: 'より丁寧でフォーマルな印象にしてください。砕けた表現があれば改めてください。',
  specific: '数字や固有名詞をできるだけ活かし、エピソードの具体性をさらに高めてください（インタビュー記録にない情報は創作しないでください）。',
}

interface PrEvaluationSectionProps {
  selectedLabel: string
  finalPr: string
  onFinalPrChange: (text: string) => void
  profileText: string
  messages: Message[]
}

export const PrEvaluationSection: React.FC<PrEvaluationSectionProps> = ({
  selectedLabel, finalPr, onFinalPrChange, profileText, messages,
}) => {
  const [evaluation, setEvaluation] = useState<PrEvaluation | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  const [targetChars, setTargetChars] = useState(0)
  const [customInstruction, setCustomInstruction] = useState('')
  const [refining, setRefining] = useState(false)
  const [refineError, setRefineError] = useState<string | null>(null)

  const prLen = finalPr.length
  const pct = targetChars > 0 ? Math.min(Math.round((prLen / targetChars) * 100), 100) : 0

  const runEvaluate = async () => {
    setEvalLoading(true)
    setEvalError(null)
    try {
      const result = await apiInterviewPrEvaluate(finalPr)
      setEvaluation(result)
    } catch {
      setEvalError('評価の取得に失敗しました。Ollamaの状態をご確認の上、もう一度お試しください。')
    } finally {
      setEvalLoading(false)
    }
  }

  const runRefine = async (instruction: string) => {
    setRefining(true)
    setRefineError(null)
    try {
      const result = await apiInterviewPrRefine({
        pr_text: finalPr, instruction, profile_text: profileText, messages,
      })
      onFinalPrChange(result.pr_text)
      setEvaluation(null)
      if (!result.ok) {
        setRefineError(`リライトに失敗したため、内容は変更されていません。詳細: ${result.error_msg ?? ''}`)
      }
    } catch (err) {
      setRefineError(toFriendlyError(err).message)
    } finally {
      setRefining(false)
    }
  }

  return (
    <div>
      <div className="mb-4 px-4 py-2.5 rounded-lg bg-emerald-50 text-emerald-800 text-sm font-medium">
        🎉「{selectedLabel}」を選択中です
      </div>

      <Card className="p-4 mb-4">
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{finalPr}</p>
      </Card>

      <div className="flex items-center gap-4 mb-6">
        <p className="text-xs text-slate-500 flex-shrink-0">📝 現在の文字数: <span className="font-semibold">{prLen}文字</span></p>
        <div className="flex items-center gap-2 flex-1">
          <input
            type="number" min={0} max={2000} step={50}
            value={targetChars || ''}
            onChange={e => setTargetChars(Number(e.target.value) || 0)}
            placeholder="目標文字数（任意）"
            className="w-32 text-xs border border-surface-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-300"
          />
          {targetChars > 0 && (
            <ProgressBar value={pct} label={`${prLen}/${targetChars}文字（${pct}%）`} className="flex-1" />
          )}
        </div>
      </div>

      {/* 評価 */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Search className="w-4 h-4 text-brand-500" />
          <p className="text-sm font-semibold text-slate-800">AIによるセルフ評価</p>
        </div>
        {!evaluation ? (
          <div>
            <Button onClick={runEvaluate} loading={evalLoading}>📊 採用担当者視点で評価してもらう</Button>
            {evalError && <p className="text-sm text-amber-600 mt-2">{evalError}</p>}
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-4 gap-3 mb-3">
              {Object.entries(evaluation.scores).map(([axis, score]) => (
                <Card key={axis} className="p-3 text-center">
                  <p className="text-xs text-slate-500 mb-1">{axis}</p>
                  <p className="text-lg font-bold text-brand-600">{score} <span className="text-xs text-slate-400 font-normal">/ 5</span></p>
                </Card>
              ))}
            </div>
            {evaluation.summary && (
              <div className="text-sm text-brand-800 bg-brand-50 rounded-lg px-3 py-2 mb-2">{evaluation.summary}</div>
            )}
            {evaluation.improvements.length > 0 && (
              <div className="mb-2">
                <p className="text-xs font-semibold text-slate-600 mb-1">改善のヒント:</p>
                <ul className="space-y-1">
                  {evaluation.improvements.map((tip, i) => (
                    <li key={i} className="text-xs text-slate-600">・{tip}</li>
                  ))}
                </ul>
              </div>
            )}
            <Button variant="secondary" size="sm" onClick={() => setEvaluation(null)} icon={<RefreshCw className="w-3.5 h-3.5" />}>
              評価をやり直す
            </Button>
          </div>
        )}
      </div>

      {/* 微調整 */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Wrench className="w-4 h-4 text-brand-500" />
          <p className="text-sm font-semibold text-slate-800">微調整</p>
        </div>
        <p className="text-xs text-slate-500 mb-3">現在の自己PRをベースに、トーンや簡潔さを調整できます（ゼロから作り直しません）。</p>
        <div className="grid grid-cols-4 gap-2 mb-3">
          {Object.entries(PRESET_LABELS).map(([key, label]) => (
            <Button key={key} variant="secondary" size="sm" disabled={refining} onClick={() => runRefine(PRESET_INSTRUCTIONS[key])}>
              {label}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={customInstruction}
            onChange={e => setCustomInstruction(e.target.value)}
            disabled={refining}
            placeholder="または自由記述で指示（例: もっと協調性を強調して）"
            className="flex-1 text-sm border border-surface-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300"
          />
          <Button
            variant="secondary"
            disabled={refining || !customInstruction.trim()}
            loading={refining}
            onClick={() => { runRefine(customInstruction.trim()); setCustomInstruction('') }}
          >
            この指示でリライト
          </Button>
        </div>
        {refineError && <p className="text-sm text-red-600 mt-2">{refineError}</p>}
      </div>
    </div>
  )
}
