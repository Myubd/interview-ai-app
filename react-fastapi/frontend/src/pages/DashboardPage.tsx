/**
 * pages/DashboardPage.tsx
 * 面接スコアのダッシュボード。
 *
 * - 総合スコア推移グラフ（SVG折れ線）
 * - 軸別スコア推移グラフ（SVG折れ線、凡例付き）
 * - 軸別平均スコア（横棒グラフ）
 * - サマリーカード（総セッション数・評価済み・平均・最高）
 *
 * recharts 等の外部ライブラリに依存せず、SVG で自前描画することで
 * ビルド設定の変更ゼロで動作する。
 */
import React, { useEffect, useState } from 'react'
import { BarChart2, TrendingUp, Award, Layers, Mic2 } from 'lucide-react'
import { apiGetDashboard, type DashboardData, type ScoreTrendEntry } from '@/api/client'
import { Card, Spinner, EmptyState } from '@/components/ui'

// ── ユーティリティ ────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })
}

// 軸ラベルの日本語マッピング（バックエンドのキー名に対応）
const AXIS_LABELS: Record<string, string> = {
  logic:         '論理性',
  communication: 'コミュニケーション',
  motivation:    '志望動機',
  self_analysis: '自己分析',
  adaptability:  '応用力',
  expression:    '表現力',
  concrete:      '具体性',
  enthusiasm:    '熱意',
}

function axisLabel(key: string): string {
  return AXIS_LABELS[key] ?? key
}

// 折れ線グラフ用の SVG パス生成
function buildLinePath(
  points: { x: number; y: number }[],
): string {
  if (points.length === 0) return ''
  return points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ')
}

// スコア → Y座標変換
function scoreToY(score: number, height: number, padding: number): number {
  return padding + (height - padding * 2) * (1 - score / 100)
}

// インデックス → X座標変換
function indexToX(i: number, total: number, width: number, padding: number): number {
  if (total <= 1) return width / 2
  return padding + (i / (total - 1)) * (width - padding * 2)
}

// 軸別カラーパレット
const AXIS_COLORS = [
  '#6366f1', // brand
  '#10b981', // emerald
  '#f97316', // orange
  '#3b82f6', // blue
  '#a855f7', // purple
  '#ec4899', // pink
  '#14b8a6', // teal
  '#eab308', // yellow
]

// ── サマリーカード ────────────────────────────────────────────

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
  color?: string
}

const StatCard: React.FC<StatCardProps> = ({ icon, label, value, sub, color = 'text-brand-500' }) => (
  <Card className="p-5 flex items-center gap-4">
    <div className={`w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center flex-shrink-0 ${color}`}>
      {icon}
    </div>
    <div className="min-w-0">
      <p className="text-xs text-slate-400 mb-0.5">{label}</p>
      <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  </Card>
)

// ── 総合スコア折れ線グラフ ────────────────────────────────────

interface OverallLineChartProps {
  trend: ScoreTrendEntry[]
}

const OverallLineChart: React.FC<OverallLineChartProps> = ({ trend }) => {
  const W = 560
  const H = 200
  const PAD = 40

  const [hovered, setHovered] = useState<number | null>(null)

  const points = trend.map((t, i) => ({
    x: indexToX(i, trend.length, W, PAD),
    y: scoreToY(t.overall_score, H, PAD),
    score: t.overall_score,
    label: t.company_name ?? `#${t.session_id}`,
    date: formatDate(t.created_at),
  }))

  const yTicks = [0, 25, 50, 75, 100]

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ minWidth: 280 }}
        onMouseLeave={() => setHovered(null)}
      >
        {/* グリッド線 */}
        {yTicks.map(tick => {
          const y = scoreToY(tick, H, PAD)
          return (
            <g key={tick}>
              <line x1={PAD} y1={y} x2={W - PAD} y2={y}
                stroke="#e2e8f0" strokeWidth="1" strokeDasharray={tick === 0 ? '0' : '4 3'} />
              <text x={PAD - 6} y={y + 4} textAnchor="end"
                fontSize="10" fill="#94a3b8">{tick}</text>
            </g>
          )
        })}

        {/* X軸ラベル（5件以下は全件、多い場合は間引き） */}
        {points.map((p, i) => {
          const show = trend.length <= 5 || i % Math.ceil(trend.length / 5) === 0 || i === trend.length - 1
          return show ? (
            <text key={i} x={p.x} y={H - PAD + 18}
              textAnchor="middle" fontSize="9" fill="#94a3b8">
              {p.date}
            </text>
          ) : null
        })}

        {/* グラデーション塗りつぶし */}
        <defs>
          <linearGradient id="overallGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* 塗りつぶしエリア */}
        {points.length > 0 && (
          <path
            d={`${buildLinePath(points)} L ${points[points.length - 1].x} ${scoreToY(0, H, PAD)} L ${points[0].x} ${scoreToY(0, H, PAD)} Z`}
            fill="url(#overallGrad)"
          />
        )}

        {/* 折れ線 */}
        <path
          d={buildLinePath(points)}
          fill="none"
          stroke="#6366f1"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* データポイント */}
        {points.map((p, i) => (
          <g key={i}>
            <circle
              cx={p.x} cy={p.y} r="5"
              fill="white" stroke="#6366f1" strokeWidth="2.5"
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHovered(i)}
            />
            {hovered === i && (
              <g>
                {/* ツールチップ背景 */}
                <rect
                  x={Math.min(p.x - 48, W - PAD - 96)}
                  y={p.y - 48}
                  width="96" height="36"
                  rx="6"
                  fill="#1e293b"
                />
                <text
                  x={Math.min(p.x - 48, W - PAD - 96) + 48}
                  y={p.y - 34}
                  textAnchor="middle" fontSize="10" fill="white" fontWeight="600">
                  {p.label}
                </text>
                <text
                  x={Math.min(p.x - 48, W - PAD - 96) + 48}
                  y={p.y - 20}
                  textAnchor="middle" fontSize="11" fill="#a5b4fc">
                  {p.score} / 100
                </text>
              </g>
            )}
          </g>
        ))}
      </svg>
    </div>
  )
}

// ── 軸別スコア折れ線グラフ ────────────────────────────────────

interface AxesLineChartProps {
  trend: ScoreTrendEntry[]
  axesKeys: string[]
}

const AxesLineChart: React.FC<AxesLineChartProps> = ({ trend, axesKeys }) => {
  const W = 560
  const H = 220
  const PAD = 40
  const [hiddenAxes, setHiddenAxes] = useState<Set<string>>(new Set())

  const toggleAxis = (key: string) => {
    setHiddenAxes(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const yTicks = [0, 25, 50, 75, 100]

  return (
    <div>
      {/* 凡例 */}
      <div className="flex flex-wrap gap-2 mb-3">
        {axesKeys.map((key, idx) => {
          const color = AXIS_COLORS[idx % AXIS_COLORS.length]
          const hidden = hiddenAxes.has(key)
          return (
            <button
              key={key}
              onClick={() => toggleAxis(key)}
              aria-pressed={!hidden}
              aria-label={`${axisLabel(key)}をグラフに${hidden ? '表示' : '非表示'}`}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-opacity ${
                hidden ? 'opacity-30' : 'opacity-100'
              }`}
              style={{ borderColor: color, color }}
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} aria-hidden="true" />
              {axisLabel(key)}
            </button>
          )
        })}
      </div>

      <div className="w-full overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 280 }}>
          {/* グリッド線 */}
          {yTicks.map(tick => {
            const y = scoreToY(tick, H, PAD)
            return (
              <g key={tick}>
                <line x1={PAD} y1={y} x2={W - PAD} y2={y}
                  stroke="#e2e8f0" strokeWidth="1" strokeDasharray={tick === 0 ? '0' : '4 3'} />
                <text x={PAD - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#94a3b8">{tick}</text>
              </g>
            )
          })}

          {/* X軸ラベル */}
          {trend.map((t, i) => {
            const x = indexToX(i, trend.length, W, PAD)
            const show = trend.length <= 5 || i % Math.ceil(trend.length / 5) === 0 || i === trend.length - 1
            return show ? (
              <text key={i} x={x} y={H - PAD + 18}
                textAnchor="middle" fontSize="9" fill="#94a3b8">
                {formatDate(t.created_at)}
              </text>
            ) : null
          })}

          {/* 軸ごとの折れ線 */}
          {axesKeys.map((key, idx) => {
            if (hiddenAxes.has(key)) return null
            const color = AXIS_COLORS[idx % AXIS_COLORS.length]
            const pts = trend.map((t, i) => ({
              x: indexToX(i, trend.length, W, PAD),
              y: scoreToY(t.axes[key] ?? 0, H, PAD),
            }))
            return (
              <g key={key}>
                <path
                  d={buildLinePath(pts)}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray={idx % 2 === 1 ? '6 3' : undefined}
                  opacity="0.85"
                />
                {pts.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r="3.5"
                    fill="white" stroke={color} strokeWidth="2" />
                ))}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

// ── 軸別平均棒グラフ ──────────────────────────────────────────

interface AxesBarChartProps {
  axesAvg: Record<string, number>
  axesKeys: string[]
}

const AxesBarChart: React.FC<AxesBarChartProps> = ({ axesAvg, axesKeys }) => (
  <div className="space-y-3">
    {axesKeys.map((key, idx) => {
      const score = axesAvg[key] ?? 0
      const color = AXIS_COLORS[idx % AXIS_COLORS.length]
      return (
        <div key={key}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-slate-600">{axisLabel(key)}</span>
            <span className="text-sm font-semibold" style={{ color }}>{score}</span>
          </div>
          <div className="h-2 rounded-full bg-surface-100 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${score}%`, background: color }}
            />
          </div>
        </div>
      )
    })}
  </div>
)

// ── メインページ ──────────────────────────────────────────────

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiGetDashboard()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-red-500">データの取得に失敗しました: {error}</p>
      </div>
    )
  }

  if (!data || data.evaluated_sessions === 0) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10 animate-fade-in">
        <h1 className="text-xl font-bold text-slate-900 mb-6">ダッシュボード</h1>
        <EmptyState
          icon={<BarChart2 className="w-12 h-12" />}
          title="まだデータがありません"
          description="AI模擬面接を完了して評価を受けると、ここにスコアの推移が表示されます。"
        />
      </div>
    )
  }

  const hasAxes = data.axes_keys.length > 0

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 animate-fade-in space-y-8">
      {/* ヘッダー */}
      <div>
        <h1 className="text-xl font-bold text-slate-900">ダッシュボード</h1>
        <p className="text-sm text-slate-400 mt-1">全 {data.total_sessions} セッション中 {data.evaluated_sessions} 件の評価データ</p>
      </div>

      {/* サマリーカード */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Mic2 className="w-5 h-5" />}
          label="総面接数"
          value={data.total_sessions}
          sub="セッション"
          color="text-brand-500"
        />
        <StatCard
          icon={<Layers className="w-5 h-5" />}
          label="評価済み"
          value={data.evaluated_sessions}
          sub="セッション"
          color="text-slate-500"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="平均スコア"
          value={data.avg_overall_score}
          sub="/ 100"
          color={`${data.avg_overall_score >= 70 ? 'text-emerald-500' : 'text-accent-500'}`}
        />
        <StatCard
          icon={<Award className="w-5 h-5" />}
          label="最高スコア"
          value={data.best_overall_score}
          sub="/ 100"
          color="text-emerald-500"
        />
      </div>

      {/* 総合スコア推移 */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-brand-500" />
          <h2 className="text-sm font-semibold text-slate-700">総合スコア推移</h2>
        </div>
        {data.score_trend.length === 1 ? (
          <div className="text-center py-8">
            <p className="text-4xl font-bold text-brand-600">{data.score_trend[0].overall_score}</p>
            <p className="text-sm text-slate-400 mt-1">/ 100 — {data.score_trend[0].company_name ?? '1回目の評価'}</p>
            <p className="text-xs text-slate-300 mt-3">2回以上評価するとグラフが表示されます</p>
          </div>
        ) : (
          <OverallLineChart trend={data.score_trend} />
        )}
      </Card>

      {/* 軸別スコア推移 */}
      {hasAxes && data.score_trend.length >= 2 && (
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="w-4 h-4 text-brand-500" />
            <h2 className="text-sm font-semibold text-slate-700">軸別スコア推移</h2>
            <span className="text-xs text-slate-400">— クリックで表示/非表示</span>
          </div>
          <AxesLineChart trend={data.score_trend} axesKeys={data.axes_keys} />
        </Card>
      )}

      {/* 軸別平均 */}
      {hasAxes && (
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-5">
            <Layers className="w-4 h-4 text-brand-500" />
            <h2 className="text-sm font-semibold text-slate-700">軸別 平均スコア</h2>
          </div>
          <AxesBarChart axesAvg={data.axes_avg} axesKeys={data.axes_keys} />
        </Card>
      )}
    </div>
  )
}
