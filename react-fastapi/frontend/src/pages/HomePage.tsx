/**
 * pages/HomePage.tsx
 * アプリ起動後の最初の画面。Ollama の接続状態を表示し、各機能へ誘導する。
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Mic2,
  History,
  Database,
  Settings,
  AlertCircle,
  CheckCircle2,
  Loader2,
  MessageSquareText,
  Sparkles,
  Brain,
  Building2,
  Bot,
  BarChart2,
} from 'lucide-react'
import { apiHealth, type HealthResponse } from '@/api/client'
import { Card } from '@/components/ui'

interface FeatureCard {
  title: string
  description: string
  icon: React.ReactNode
  to: string
  color: string
}

const FEATURES: FeatureCard[] = [
  {
    title: 'AI模擬面接',
    description: '4種類の面接官ペルソナから選んで本番さながらの練習。終了後に詳細評価を自動生成。',
    icon: <Mic2 className="w-6 h-6" />,
    to: '/mock-interview',
    color: 'text-brand-500',
  },
  {
    title: '自己PR作成',
    description: 'テーマ制のインタビューで強みを掘り下げ、自己PR（3パターン）を生成・評価・微調整する。',
    icon: <MessageSquareText className="w-6 h-6" />,
    to: '/interview',
    color: 'text-indigo-500',
  },
  {
    title: '想定質問生成',
    description: '自己PRと企業情報から、模範回答例つきの想定質問セットを生成する。',
    icon: <Sparkles className="w-6 h-6" />,
    to: '/predicted-questions',
    color: 'text-pink-500',
  },
  {
    title: '性格診断',
    description: 'ビッグファイブ30問から5因子スコア・業界フィット度・おすすめ職種を分析する。',
    icon: <Brain className="w-6 h-6" />,
    to: '/personality',
    color: 'text-purple-500',
  },
  {
    title: '企業比較マトリクス',
    description: '複数企業の志望動機を一括生成し、比較マトリクス・差別化ポイントをまとめて作成する。',
    icon: <Building2 className="w-6 h-6" />,
    to: '/company-matrix',
    color: 'text-cyan-600',
  },
  {
    title: 'AIキャリアアドバイザー',
    description: 'ガクチカ相談・ES添削・業界研究など、就活に関することは何でも相談できるチャット。',
    icon: <Bot className="w-6 h-6" />,
    to: '/career-advisor',
    color: 'text-orange-500',
  },
  {
    title: '面接履歴',
    description: 'これまでの面接セッションを保存・閲覧。続きから再開したりJSONでエクスポートも可能。',
    icon: <History className="w-6 h-6" />,
    to: '/history',
    color: 'text-emerald-500',
  },
  {
    title: 'ダッシュボード',
    description: 'これまでのセッションを横断して、強み・弱みの傾向や練習の進捗を可視化する。',
    icon: <BarChart2 className="w-6 h-6" />,
    to: '/dashboard',
    color: 'text-teal-500',
  },
  {
    title: 'ナレッジベース',
    description: '履歴書や企業情報を登録。RAGが面接の質問生成・評価に自動で活用する。',
    icon: <Database className="w-6 h-6" />,
    to: '/knowledge',
    color: 'text-amber-500',
  },
  {
    title: '設定',
    description: 'LLMモデル・埋め込みモデル・Ollamaホストを変更できる。',
    icon: <Settings className="w-6 h-6" />,
    to: '/settings',
    color: 'text-slate-500',
  },
]

export const HomePage: React.FC = () => {
  const navigate = useNavigate()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    apiHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'degraded', ollama: false, models: [] }))
      .finally(() => setChecking(false))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 animate-fade-in">
      {/* ヘッダー */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">就活インタビューAI</h1>
        <p className="text-slate-500 text-sm">
          ローカル LLM を使った就活支援アシスタント。個人情報は外部に送信されません。
        </p>
      </div>

      {/* Ollama ステータス */}
      <div className="mb-8">
        {checking ? (
          <div className="flex items-center gap-2 text-slate-500 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Ollama に接続中...</span>
          </div>
        ) : health?.ollama ? (
          <div className="flex items-start gap-3 p-4 bg-emerald-50 rounded-xl border border-emerald-100">
            <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-emerald-800">Ollama 接続済み</p>
              <p className="text-xs text-emerald-600 mt-0.5">
                利用可能モデル: {health.models.length > 0 ? health.models.join(', ') : 'なし'}
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 p-4 bg-amber-50 rounded-xl border border-amber-100">
            <AlertCircle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">Ollama に接続できません</p>
              <p className="text-xs text-amber-700 mt-0.5">
                Ollama が起動しているか確認してください。
                <code className="mx-1 px-1 bg-amber-100 rounded font-mono">ollama serve</code>
                で起動できます。
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 機能カード */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {FEATURES.map(f => (
          <Card key={f.to} onClick={() => navigate(f.to)} className="p-5 hover:shadow-md">
            <div className={`${f.color} mb-3`}>{f.icon}</div>
            <h2 className="text-sm font-semibold text-slate-900 mb-1">{f.title}</h2>
            <p className="text-xs text-slate-500 leading-relaxed">{f.description}</p>
          </Card>
        ))}
      </div>
    </div>
  )
}
