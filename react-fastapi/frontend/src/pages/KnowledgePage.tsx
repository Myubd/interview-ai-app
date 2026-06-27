/**
 * pages/KnowledgePage.tsx
 * 履歴書・企業情報の登録・管理（RAGナレッジベース）。
 */
import React, { useEffect, useState, useRef } from 'react'
import { Plus, Trash2, FileText, Building2, ToggleLeft, ToggleRight, Upload } from 'lucide-react'
import {
  apiGetKnowledgeBases, apiDeleteKnowledgeBase, apiToggleKnowledgeBaseActive,
  apiCreateKnowledgeBaseText, apiCreateKnowledgeBaseUpload,
  type KnowledgeBase,
} from '@/api/client'
import { Button, Badge, Card, EmptyState, Spinner, Toast } from '@/components/ui'

type AddMode = 'none' | 'text' | 'file'

const TYPE_LABELS: Record<string, string> = {
  resume:  '履歴書',
  company: '企業情報',
}

export const KnowledgePage: React.FC = () => {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [addMode, setAddMode] = useState<AddMode>('none')
  const [toast, setToast] = useState<{ msg: string; variant: 'success' | 'error' } | null>(null)

  // テキスト追加フォーム
  const [name, setName] = useState('')
  const [kbType, setKbType] = useState<'resume' | 'company'>('resume')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  // ファイルアップロード
  const fileRef = useRef<HTMLInputElement>(null)

  const showToast = (msg: string, variant: 'success' | 'error' = 'success') => {
    setToast({ msg, variant })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    apiGetKnowledgeBases()
      .then(setKbs)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id: number) => {
    if (!window.confirm('このナレッジベースを削除しますか？')) return
    await apiDeleteKnowledgeBase(id)
    setKbs(prev => prev.filter(k => k.id !== id))
    showToast('削除しました')
  }

  const handleToggle = async (kb: KnowledgeBase) => {
    const updated = await apiToggleKnowledgeBaseActive(kb.id, !kb.is_active)
    setKbs(prev => prev.map(k => k.id === kb.id ? { ...k, is_active: updated.is_active } : k))
  }

  const handleTextSave = async () => {
    if (!name.trim() || !text.trim()) return
    setSaving(true)
    try {
      const created = await apiCreateKnowledgeBaseText({ name, kb_type: kbType, text })
      setKbs(prev => [created, ...prev])
      setName(''); setText(''); setAddMode('none')
      showToast('登録しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !name.trim()) { showToast('名前を先に入力してください', 'error'); return }
    setSaving(true)
    try {
      const form = new FormData()
      form.append('name', name)
      form.append('kb_type', kbType)
      form.append('file', file)
      const created = await apiCreateKnowledgeBaseUpload(form)
      setKbs(prev => [created, ...prev])
      setName(''); setAddMode('none')
      showToast('登録しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setSaving(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const resumes  = kbs.filter(k => k.kb_type === 'resume')
  const companies = kbs.filter(k => k.kb_type === 'company')

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">ナレッジベース</h1>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => setAddMode('text')} icon={<Plus className="w-4 h-4" />}>
            テキスト入力
          </Button>
          <Button size="sm" onClick={() => setAddMode('file')} icon={<Upload className="w-4 h-4" />}>
            ファイル追加
          </Button>
        </div>
      </div>

      {/* 追加フォーム */}
      {addMode !== 'none' && (
        <Card className="p-5 mb-6 animate-slide-up">
          <h2 className="text-sm font-semibold text-slate-800 mb-4">新規登録</h2>
          <div className="space-y-3">
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="名前 (例: 共通履歴書、ソニー)"
              className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700"
            />
            <div className="flex gap-3">
              {(['resume', 'company'] as const).map(t => (
                <label key={t} className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="kb_type" value={t} checked={kbType === t} onChange={() => setKbType(t)} className="accent-brand-500" />
                  <span className="text-sm text-slate-600">{TYPE_LABELS[t]}</span>
                </label>
              ))}
            </div>
            {addMode === 'text' ? (
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                rows={6}
                placeholder="テキストを貼り付け..."
                className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700"
              />
            ) : (
              <div>
                <input ref={fileRef} type="file" accept=".txt,.pdf,.png,.jpg,.jpeg" onChange={handleFileChange} className="text-sm text-slate-600" />
                <p className="text-xs text-slate-400 mt-1">対応形式: PDF, テキスト, 画像 (OCR)</p>
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setAddMode('none')}>キャンセル</Button>
              {addMode === 'text' && (
                <Button size="sm" onClick={handleTextSave} loading={saving}>保存</Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
      ) : kbs.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-12 h-12" />}
          title="登録されていません"
          description="履歴書や企業情報を登録すると、面接・自己PR生成で活用されます。"
        />
      ) : (
        <div className="space-y-6">
          {resumes.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4" /> 履歴書 ({resumes.length})
              </h2>
              <ul className="space-y-2">
                {resumes.map(kb => <KbItem key={kb.id} kb={kb} onDelete={handleDelete} onToggle={handleToggle} />)}
              </ul>
            </section>
          )}
          {companies.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <Building2 className="w-4 h-4" /> 企業情報 ({companies.length})
              </h2>
              <ul className="space-y-2">
                {companies.map(kb => <KbItem key={kb.id} kb={kb} onDelete={handleDelete} onToggle={handleToggle} />)}
              </ul>
            </section>
          )}
        </div>
      )}

      {toast && <Toast message={toast.msg} variant={toast.variant} />}
    </div>
  )
}

const KbItem: React.FC<{
  kb: KnowledgeBase
  onDelete: (id: number) => void
  onToggle: (kb: KnowledgeBase) => void
}> = ({ kb, onDelete, onToggle }) => (
  <Card className="p-3">
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 truncate">{kb.name}</p>
        <p className="text-xs text-slate-400">{kb.kb_type === 'resume' ? '履歴書' : '企業情報'}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <Badge variant={kb.is_active ? 'success' : 'default'}>
          {kb.is_active ? 'ON' : 'OFF'}
        </Badge>
        <button onClick={() => onToggle(kb)} className="text-slate-400 hover:text-brand-500 transition-colors">
          {kb.is_active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
        </button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(kb.id)} icon={<Trash2 className="w-4 h-4 text-red-400" />} />
      </div>
    </div>
  </Card>
)
