/**
 * pages/HomePage.tsx
 * アプリ起動後の最初の画面。Ollama の接続状態を表示し、各機能へ誘導する。
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mic2, History, Database, Settings, AlertCircle, CheckCircle2, Loader2, ExternalLink } from 'lucide-react'
import { apiHealth, type HealthResponse } from '@/api/client'
import { Button, Card } from '@/components/ui'

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
    title: '面接履歴',
    description: 'これまでの面接セッションを保存・閲覧。続きから再開したりJSONでエクスポートも可能。',
    icon: <History className="w-6 h-6" />,
    to: '/history',
    color: 'text-emerald-500',
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
    <div className="max-w-3xl mx-auto px-6 py-10 animate-fade-in">
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
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {FEATURES.map(f => (
          <Card key={f.to} onClick={() => navigate(f.to)} className="p-5 hover:shadow-md">
            <div className={`${f.color} mb-3`}>{f.icon}</div>
            <h2 className="text-sm font-semibold text-slate-900 mb-1">{f.title}</h2>
            <p className="text-xs text-slate-500 leading-relaxed">{f.description}</p>
          </Card>
        ))}
      </div>

      {/* Streamlit 誘導 */}
      <div className="mt-8 p-4 bg-surface-50 rounded-xl border border-surface-200">
        <p className="text-xs text-slate-500 mb-1 font-medium">自己PR生成・企業比較など他の機能</p>
        <p className="text-xs text-slate-400 mb-3">
          これらの機能は移行作業中のため、別画面（Streamlit版）で新しいタブが開きます。
          今の画面はそのまま残ります。
        </p>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => window.open('http://localhost:8501', '_blank', 'noopener,noreferrer')}
          icon={<ExternalLink className="w-3.5 h-3.5" />}
          aria-label="Streamlit版を新しいタブで開く"
        >
          Streamlit版を開く（別タブ）
        </Button>
      </div>
    </div>
  )
}
