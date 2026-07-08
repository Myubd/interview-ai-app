/**
 * pages/SettingsPage.tsx
 * LLMモデル・埋め込みモデル・Ollama ホストの設定。
 * キー名は既存 DB に合わせて chat_model / embed_model。
 */
import React, { useEffect, useState } from 'react'
import { Save, Terminal, Share2, ShieldCheck } from 'lucide-react'
import {
  apiGetSettings, apiUpdateSettings, type AppSettings,
  apiGetPendingPermissions, apiGetGrantedPermissions,
  apiGrantPermission, apiRevokePermission,
  type PendingScope, type GrantedScope,
} from '@/api/client'
import { Button, Card, Toast } from '@/components/ui'

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>({
    chat_model: 'qwen3:8b',
    embed_model: 'nomic-embed-text',
    ollama_host: 'http://localhost:11434',
  })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ msg: string; variant: 'success' | 'error' } | null>(null)

  const [pending, setPending] = useState<PendingScope[]>([])
  const [granted, setGranted] = useState<GrantedScope[]>([])
  const [permBusyKey, setPermBusyKey] = useState<string | null>(null)

  const reloadPermissions = () => {
    apiGetPendingPermissions().then(setPending).catch(console.error)
    apiGetGrantedPermissions().then(setGranted).catch(console.error)
  }

  useEffect(() => {
    apiGetSettings().then(setSettings).catch(console.error)
    reloadPermissions()
  }, [])

  const showToast = (msg: string, variant: 'success' | 'error' = 'success') => {
    setToast({ msg, variant })
    setTimeout(() => setToast(null), 3000)
  }

  const handleGrant = async (item: PendingScope) => {
    setPermBusyKey(item.scope)
    try {
      await apiGrantPermission(item.app_key, item.scope)
      reloadPermissions()
      showToast('許可しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setPermBusyKey(null)
    }
  }

  const handleRevoke = async (item: GrantedScope) => {
    setPermBusyKey(item.scope)
    try {
      await apiRevokePermission(item.app_key, item.scope)
      reloadPermissions()
      showToast('許可を取り消しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setPermBusyKey(null)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await apiUpdateSettings(settings)
      setSettings(updated)
      showToast('設定を保存しました')
    } catch (err) {
      showToast(String(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-10 animate-fade-in">
      <h1 className="text-xl font-bold text-slate-900 mb-8">設定</h1>

      <Card className="p-6 space-y-5 mb-6">
        <Field
          label="チャットモデル"
          hint="模擬面接の質問生成・評価に使用します。"
          value={settings.chat_model}
          onChange={v => setSettings(s => ({ ...s, chat_model: v }))}
          placeholder="qwen3:8b"
        />
        <Field
          label="埋め込みモデル"
          hint="ナレッジベース（RAG）の検索に使用します。"
          value={settings.embed_model}
          onChange={v => setSettings(s => ({ ...s, embed_model: v }))}
          placeholder="nomic-embed-text"
        />
        <Field
          label="Ollama ホスト"
          hint="Ollama が別ホストで動作している場合のみ変更します。"
          value={settings.ollama_host}
          onChange={v => setSettings(s => ({ ...s, ollama_host: v }))}
          placeholder="http://localhost:11434"
        />
        <div className="pt-2">
          <Button onClick={handleSave} loading={saving} icon={<Save className="w-4 h-4" />}>
            保存
          </Button>
        </div>
      </Card>

      {/* データ共有の許可(local-ai-core PermissionGate) */}
      <Card className="p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Share2 className="w-4 h-4 text-slate-400" />
          <p className="text-xs font-semibold text-slate-600">データ共有の許可</p>
        </div>
        <p className="text-xs text-slate-400 mb-4">
          ライフサポートOSなど、他のローカルAIエコシステムのアプリとメモリー/資料/予定を
          共有してよいかをここで管理します。許可しない限り何も共有されません。
        </p>

        {pending.length === 0 && granted.length === 0 && (
          <p className="text-xs text-slate-400">現在、共有のリクエストはありません。</p>
        )}

        {pending.length > 0 && (
          <div className="space-y-2 mb-4">
            <p className="text-xs font-medium text-slate-500">許可を求められています</p>
            {pending.map(item => (
              <div
                key={`${item.app_key}:${item.scope}`}
                className="flex items-start justify-between gap-3 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5"
              >
                <div>
                  <p className="text-xs font-mono text-slate-600">{item.app_key} · {item.scope}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{item.purpose}</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  loading={permBusyKey === item.scope}
                  onClick={() => handleGrant(item)}
                  className="shrink-0"
                >
                  許可する
                </Button>
              </div>
            ))}
          </div>
        )}

        {granted.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-500 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" /> 許可済み
            </p>
            {granted.map(item => (
              <div
                key={`${item.app_key}:${item.scope}`}
                className="flex items-start justify-between gap-3 bg-surface-50 rounded-lg px-3 py-2.5"
              >
                <div>
                  <p className="text-xs font-mono text-slate-600">{item.app_key} · {item.scope}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{item.purpose}</p>
                </div>
                <button
                  onClick={() => handleRevoke(item)}
                  disabled={permBusyKey === item.scope}
                  className="text-xs text-slate-400 hover:text-red-500 transition-colors shrink-0 disabled:opacity-50"
                >
                  取り消す
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* モデル取得コマンド */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <Terminal className="w-4 h-4 text-slate-400" />
          <p className="text-xs font-semibold text-slate-600">モデルの取得コマンド</p>
        </div>
        <div className="space-y-1.5">
          {[
            'ollama pull qwen3:8b',
            'ollama pull nomic-embed-text',
          ].map(cmd => (
            <div key={cmd} className="flex items-center justify-between bg-surface-50 rounded-lg px-3 py-2">
              <code className="text-xs font-mono text-slate-600">{cmd}</code>
              <button
                onClick={() => navigator.clipboard.writeText(cmd)}
                className="text-xs text-slate-400 hover:text-brand-500 transition-colors ml-3"
              >
                コピー
              </button>
            </div>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-3">
          他のモデルは <a href="https://ollama.com/library" target="_blank" rel="noopener noreferrer" className="text-brand-500 underline">ollama.com/library</a> で確認できます。
        </p>
      </Card>

      {toast && <Toast message={toast.msg} variant={toast.variant} />}
    </div>
  )
}

const Field: React.FC<{
  label: string
  hint: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}> = ({ label, hint, value, onChange, placeholder }) => (
  <div>
    <label className="block text-sm font-medium text-slate-700 mb-0.5">{label}</label>
    <p className="text-xs text-slate-400 mb-1.5">{hint}</p>
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full text-sm border border-surface-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-300 text-slate-700 font-mono"
    />
  </div>
)
