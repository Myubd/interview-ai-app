/**
 * pages/CompanyMatrixPage.tsx
 * 企業比較マトリクス（company_page.py から分離）。
 *
 * 既存コードとの対応:
 *   streamlit版 page_modules/company_matrix_page.py + company_matrix.py が相当する。
 *   company_matrix.py は shared/ に一本化済み（backend/services/company_matrix_service.py 経由で呼び出す）。
 *
 * Streamlit版との違い:
 *   - React版はページ単位で状態が独立しているため、「自己PR」はサイドバーの
 *     グローバル状態ではなく、このページ内のテキストエリアに直接貼り付ける形にした。
 */
import React, { useEffect, useMemo, useState } from 'react'
import { Building2, Download, RefreshCw, Sparkles } from 'lucide-react'
import {
  apiGetCompanyMatrixConstants,
  apiGetCompanyMatrixCompanies,
  apiGenerateMotivations,
  apiGenerateMatrix,
  apiExportMatrixCsv,
  apiGenerateWhyNotOthers,
  type CompanyMatrixConstants,
  type KnowledgeBase,
  type MotivationResult,
  type MatrixResult,
  type WhyNotResult,
} from '@/api/client'
import { Button, Card, EmptyState, Spinner } from '@/components/ui'

type Tab = 'motivation' | 'matrix' | 'why-not'

export const CompanyMatrixPage: React.FC = () => {
  const [constants, setConstants] = useState<CompanyMatrixConstants | null>(null)
  const [companies, setCompanies] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [prText, setPrText] = useState('')
  const [additionalAxesText, setAdditionalAxesText] = useState('')
  const [tab, setTab] = useState<Tab>('motivation')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([apiGetCompanyMatrixConstants(), apiGetCompanyMatrixCompanies()])
      .then(([c, comps]) => {
        setConstants(c)
        setCompanies(comps)
      })
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  const additionalAxes = useMemo(
    () => additionalAxesText.split(',').map(a => a.trim()).filter(Boolean).slice(0, 3),
    [additionalAxesText],
  )

  const toggleCompany = (id: number) => {
    setSelectedIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (constants && prev.length >= constants.max_companies) return prev
      return [...prev, id]
    })
  }

  const selectedCompanyNames = companies
    .filter(c => selectedIds.includes(c.id))
    .map(c => ({ id: c.id, name: c.name }))

  if (loading) {
    return <div className="flex justify-center py-24"><Spinner className="w-8 h-8" /></div>
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Building2 className="w-5 h-5 text-brand-500" />
          企業比較マトリクス
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          「ナレッジベース」ページに登録した企業情報の中から最大{constants?.max_companies ?? 8}社を選んで、
          志望動機の一括生成・複数軸での比較・「なぜ他社でなくこの企業か」の差別化ポイントをまとめて作成します。
        </p>
      </div>

      {error && (
        <Card className="p-4 mb-6 border-red-200 bg-red-50">
          <p className="text-sm text-red-600">{error}</p>
        </Card>
      )}

      {companies.length === 0 ? (
        <EmptyState
          icon={<Building2 className="w-12 h-12" />}
          title="比較対象の企業情報がまだ保存されていません"
          description={'「ナレッジベース」ページから企業情報を登録してください（複数社分、繰り返し登録できます）。'}
        />
      ) : (
        <>
          <Card className="p-5 mb-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">① 比較する企業を選択</h2>
            <div className="grid grid-cols-2 gap-2">
              {companies.map(c => (
                <label
                  key={c.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-200 text-sm cursor-pointer hover:bg-surface-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(c.id)}
                    onChange={() => toggleCompany(c.id)}
                  />
                  {c.name}
                </label>
              ))}
            </div>
            {selectedIds.length < 2 && (
              <p className="text-xs text-slate-400 mt-2">
                比較には2社以上の選択が必要です（志望動機の一括生成のみなら1社でも可）。
              </p>
            )}
          </Card>

          <Card className="p-5 mb-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-2">② 自己PR（任意）</h2>
            <textarea
              value={prText}
              onChange={e => setPrText(e.target.value)}
              placeholder="完成済みの自己PR文を貼り付けると、志望動機・比較・差別化ポイントの精度が上がります。"
              className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 min-h-[80px]"
            />
          </Card>

          <Card className="p-5 mb-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-2">③ 比較軸（任意で追加）</h2>
            <p className="text-xs text-slate-400 mb-2">
              固定の7軸（{constants?.matrix_axes_fixed.join('／')}）に加えて、最大3軸まで自由に追加できます。
            </p>
            <input
              type="text"
              value={additionalAxesText}
              onChange={e => setAdditionalAxesText(e.target.value)}
              placeholder="例: 海外展開の積極性, 研修制度の充実度"
              className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
            {constants?.value_fit_note && (
              <p className="text-[11px] text-slate-400 mt-2">{constants.value_fit_note}</p>
            )}
          </Card>

          <div className="flex gap-2 border-b border-surface-200 mb-6">
            {([
              ['motivation', '📝 志望動機（一括）'],
              ['matrix', '📊 比較マトリクス'],
              ['why-not', '🆚 差別化ポイント'],
            ] as [Tab, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  tab === key ? 'border-brand-500 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'motivation' && (
            <MotivationTab companyKbIds={selectedIds} prText={prText} />
          )}
          {tab === 'matrix' && (
            <MatrixTab
              companyKbIds={selectedIds}
              prText={prText}
              additionalAxes={additionalAxes}
              valueFitAxisKey={constants?.value_fit_axis_key ?? ''}
              valueFitNote={constants?.value_fit_note ?? ''}
            />
          )}
          {tab === 'why-not' && (
            <WhyNotTab companies={selectedCompanyNames} prText={prText} />
          )}
        </>
      )}
    </div>
  )
}

// ============================================================
// タブ1: 志望動機（一括）
// ============================================================

const MotivationTab: React.FC<{ companyKbIds: number[]; prText: string }> = ({ companyKbIds, prText }) => {
  const [results, setResults] = useState<MotivationResult[] | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await apiGenerateMotivations({ company_kb_ids: companyKbIds, pr_text: prText })
      setResults(res)
    } catch (err) {
      setError(String(err))
    } finally {
      setGenerating(false)
    }
  }

  if (companyKbIds.length === 0) {
    return <p className="text-sm text-slate-400">企業を選択してください。</p>
  }

  return (
    <div>
      <p className="text-xs text-slate-400 mb-4">選択した企業ごとに、自己PRを踏まえた志望動機文を生成します。</p>
      {error && <Card className="p-4 mb-4 border-red-200 bg-red-50"><p className="text-sm text-red-600">{error}</p></Card>}
      {!results ? (
        <Button onClick={handleGenerate} loading={generating} icon={<Sparkles className="w-4 h-4" />}>
          志望動機を一括生成する
        </Button>
      ) : (
        <div className="space-y-4">
          {results.map((r, i) => (
            <Card key={i} className="p-4">
              <p className="font-semibold text-slate-800 mb-2">🏢 {r.company_name}</p>
              {!r.ok && <p className="text-sm text-amber-600 mb-2">生成に失敗しました: {r.error_msg}</p>}
              {r.motivation_text && <p className="text-sm text-slate-700 whitespace-pre-wrap mb-2">{r.motivation_text}</p>}
              {r.key_points.length > 0 && (
                <div className="text-xs text-slate-500 space-y-0.5">
                  <p>アピールポイント:</p>
                  {r.key_points.map((p, j) => <p key={j}>・{p}</p>)}
                </div>
              )}
            </Card>
          ))}
          <Button variant="secondary" size="sm" icon={<RefreshCw className="w-4 h-4" />} onClick={() => setResults(null)}>
            志望動機を再生成する
          </Button>
        </div>
      )}
    </div>
  )
}

// ============================================================
// タブ2: 比較マトリクス
// ============================================================

const MatrixTab: React.FC<{
  companyKbIds: number[]
  prText: string
  additionalAxes: string[]
  valueFitAxisKey: string
  valueFitNote: string
}> = ({ companyKbIds, prText, additionalAxes, valueFitAxisKey, valueFitNote }) => {
  const [result, setResult] = useState<MatrixResult | null>(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await apiGenerateMatrix({ company_kb_ids: companyKbIds, pr_text: prText, additional_axes: additionalAxes })
      setResult(res)
    } catch (err) {
      setError(String(err))
    } finally {
      setGenerating(false)
    }
  }

  const handleExportCsv = async () => {
    if (!result) return
    try {
      const csv = await apiExportMatrixCsv(result)
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'company_comparison_matrix.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(String(err))
    }
  }

  if (companyKbIds.length < 2) {
    return <p className="text-sm text-slate-400">比較マトリクスの生成には2社以上の選択が必要です。</p>
  }

  return (
    <div>
      <p className="text-xs text-slate-400 mb-4">複数企業を比較軸ごとにスコアリングします。</p>
      {error && <Card className="p-4 mb-4 border-red-200 bg-red-50"><p className="text-sm text-red-600">{error}</p></Card>}
      {!result ? (
        <Button onClick={handleGenerate} loading={generating} icon={<Sparkles className="w-4 h-4" />}>
          比較マトリクスを生成する
        </Button>
      ) : (
        <div className="space-y-5">
          {!result.ok && <p className="text-sm text-amber-600">生成中にエラーが発生しました: {result.error_msg}</p>}
          {result.axes.map(ax => (
            <div key={ax}>
              <p className="text-sm font-semibold text-slate-800 mb-2">
                {ax}
                {ax === valueFitAxisKey && <span className="text-[11px] text-slate-400 font-normal">　{valueFitNote}</span>}
              </p>
              <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${result.companies.length}, minmax(0, 1fr))` }}>
                {result.companies.map(company => {
                  const cell = result.matrix[ax]?.[company]
                  return (
                    <Card key={company} className="p-3 text-center">
                      <p className="text-xs text-slate-500 mb-1">{company}</p>
                      <p className="text-lg font-bold text-brand-600">{cell?.score ?? '-'} / 5</p>
                      <p className="text-[11px] text-slate-400 mt-1">{cell?.comment}</p>
                    </Card>
                  )
                })}
              </div>
            </div>
          ))}
          {result.overall_recommendation && (
            <Card className="p-4 bg-emerald-50 border-emerald-100">
              <p className="text-sm text-emerald-800">💡 総合推薦コメント: {result.overall_recommendation}</p>
            </Card>
          )}
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={<Download className="w-4 h-4" />} onClick={handleExportCsv}>
              CSVでダウンロード
            </Button>
            <Button variant="secondary" size="sm" icon={<RefreshCw className="w-4 h-4" />} onClick={() => setResult(null)}>
              再生成する
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================
// タブ3: 差別化ポイント
// ============================================================

const WhyNotTab: React.FC<{ companies: { id: number; name: string }[]; prText: string }> = ({ companies, prText }) => {
  const [targetId, setTargetId] = useState<number | null>(companies[0]?.id ?? null)
  const [results, setResults] = useState<Record<number, WhyNotResult>>({})
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!targetId && companies.length > 0) setTargetId(companies[0].id)
  }, [companies, targetId])

  if (companies.length === 0) {
    return <p className="text-sm text-slate-400">企業を選択してください。</p>
  }

  const others = companies.filter(c => c.id !== targetId)
  const existing = targetId ? results[targetId] : undefined

  const handleGenerate = async () => {
    if (!targetId) return
    setGenerating(true)
    setError(null)
    try {
      const res = await apiGenerateWhyNotOthers({
        target_kb_id: targetId,
        other_kb_ids: others.map(o => o.id),
        pr_text: prText,
      })
      setResults(prev => ({ ...prev, [targetId]: res }))
    } catch (err) {
      setError(String(err))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div>
      <p className="text-xs text-slate-400 mb-3">第一志望企業を1社選び、他社と比べた差別化ポイントと回答テンプレートを生成します。</p>
      <select
        value={targetId ?? ''}
        onChange={e => setTargetId(Number(e.target.value))}
        className="text-sm border border-surface-200 rounded-lg px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-brand-300"
      >
        {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>

      {error && <Card className="p-4 mb-4 border-red-200 bg-red-50"><p className="text-sm text-red-600">{error}</p></Card>}

      {!existing ? (
        others.length === 0 ? (
          <p className="text-sm text-slate-400">比較対象となる他社をもう1社以上選択してください。</p>
        ) : (
          <Button onClick={handleGenerate} loading={generating} icon={<Sparkles className="w-4 h-4" />}>
            差別化ポイントを生成する
          </Button>
        )
      ) : (
        <div className="space-y-3">
          {!existing.ok && <p className="text-sm text-amber-600">生成中にエラーが発生しました: {existing.error_msg}</p>}
          {existing.differentiators.map((d, i) => (
            <Card key={i} className="p-3">
              <p className="text-sm font-semibold text-slate-800">・{d.point}</p>
              {d.vs_others && <p className="text-xs text-slate-500 mt-1">他社との違い: {d.vs_others}</p>}
            </Card>
          ))}
          {existing.answer_template && (
            <Card className="p-4 bg-brand-50 border-brand-100">
              <p className="text-xs font-semibold text-slate-500 mb-1">回答テンプレート例:</p>
              <p className="text-sm text-slate-700">{existing.answer_template}</p>
            </Card>
          )}
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={() => setResults(prev => { const next = { ...prev }; if (targetId) delete next[targetId]; return next })}
          >
            差別化ポイントを再生成する
          </Button>
        </div>
      )}
    </div>
  )
}
