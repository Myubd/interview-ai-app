/**
 * pages/HistoryPage.tsx
 * 面接セッション履歴の一覧・閲覧・削除・エクスポート。
 * list_sessions() の実際の返却型 (SessionMeta) に対応。
 */
import React, { useEffect, useState } from 'react'
import { Trash2, Download, Clock, Search, Mic2, FileText } from 'lucide-react'
import {
  apiGetSessions, apiDeleteSession, apiExportSession,
  type SessionMeta,
} from '@/api/client'
import { Button, Card, Badge, EmptyState, Spinner } from '@/components/ui'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ja-JP', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export const HistoryPage: React.FC = () => {
  const [sessions, setSessions] = useState<SessionMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [deleting, setDeleting] = useState<number | null>(null)

  useEffect(() => {
    apiGetSessions()
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = sessions.filter(s =>
    (s.company_name ?? '').toLowerCase().includes(query.toLowerCase())
  )

  const handleDelete = async (id: number) => {
    if (!window.confirm('このセッションを削除しますか？')) return
    setDeleting(id)
    try {
      await apiDeleteSession(id)
      setSessions(prev => prev.filter(s => s.id !== id))
    } finally {
      setDeleting(null)
    }
  }

  const handleExport = async (id: number, companyName: string | null) => {
    const data = await apiExportSession(id)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_${id}_${companyName ?? 'unknown'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">面接履歴</h1>
        <Badge variant="default">{sessions.length} 件</Badge>
      </div>

      {/* 検索 */}
      <div className="relative mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="企業名で検索..."
          className="w-full pl-9 pr-4 py-2.5 text-sm border border-surface-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700 placeholder:text-slate-300"
        />
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="w-8 h-8" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<Clock className="w-12 h-12" />}
          title="履歴がありません"
          description="AI模擬面接を行うと、ここに履歴が保存されます。"
        />
      ) : (
        <ul className="space-y-3">
          {filtered.map(s => (
            <li key={s.id}>
              <Card className="p-4">
                <div className="flex items-start gap-3">
                  {/* アイコン */}
                  <div className="w-9 h-9 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
                    {s.session_type === 'mock'
                      ? <Mic2 className="w-4 h-4 text-brand-500" />
                      : <FileText className="w-4 h-4 text-slate-400" />
                    }
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {s.company_name || '会社名未設定'}
                      </p>
                      {Boolean(s.has_mock_evaluation) && (
                        <Badge variant="success">評価済み</Badge>
                      )}
                      {Boolean(s.interview_complete) && (
                        <Badge variant="info">完了</Badge>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDate(s.created_at)}
                    </p>
                  </div>

                  <div className="flex gap-1 flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleExport(s.id, s.company_name)}
                      title="JSONエクスポート"
                      icon={<Download className="w-4 h-4" />}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(s.id)}
                      loading={deleting === s.id}
                      title="削除"
                      icon={<Trash2 className="w-4 h-4 text-red-400" />}
                    />
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
