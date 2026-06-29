/**
 * pages/SetupProgressPage.tsx
 * ---------------------------
 * アプリ初回起動時に Ollama のインストール・モデルダウンロードの
 * 進捗をリアルタイムで表示するページ。
 *
 * App.tsx でアプリ起動直後にレンダリングし、セットアップ完了後に
 * メインUIへ遷移させる。
 */
import React, { useEffect, useRef, useState } from 'react'
import { CheckCircle, AlertCircle, Loader2, Terminal } from 'lucide-react'
import {
  subscribeSetupProgress,
  apiGetSetupStatus,
  type SetupLogEntry,
} from '@/api/client'

interface Props {
  onComplete: () => void
}

const LEVEL_COLOR: Record<string, string> = {
  INFO:    'text-slate-300',
  SUCCESS: 'text-emerald-400',
  WARNING: 'text-amber-400',
  ERROR:   'text-red-400',
}

export const SetupProgressPage: React.FC<Props> = ({ onComplete }) => {
  const [logs, setLogs] = useState<SetupLogEntry[]>([])
  const [done, setDone] = useState(false)
  const [hasError, setHasError] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // すでにセットアップ済みならスキップ
    apiGetSetupStatus().then(s => {
      if (s.done) {
        onComplete()
      }
    }).catch(() => {
      // バックエンド未起動の場合は無視してSSEを待つ
    })
  }, [onComplete])

  useEffect(() => {
    const unsubscribe = subscribeSetupProgress(
      (entry) => setLogs(prev => [...prev, entry]),
      () => {
        setDone(true)
        setTimeout(onComplete, 1500)
      },
      () => setHasError(true),
    )
    return unsubscribe
  }, [onComplete])

  // 新しいログが来たら自動スクロール
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* ヘッダー */}
        <div className="flex items-center gap-3 mb-6">
          {done ? (
            <CheckCircle className="w-7 h-7 text-emerald-400 shrink-0" />
          ) : hasError ? (
            <AlertCircle className="w-7 h-7 text-red-400 shrink-0" />
          ) : (
            <Loader2 className="w-7 h-7 text-brand-400 animate-spin shrink-0" />
          )}
          <div>
            <h1 className="text-lg font-bold text-white">
              {done
                ? 'セットアップ完了'
                : hasError
                ? 'セットアップ中にエラーが発生しました'
                : 'セットアップ中...'}
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              {done
                ? 'まもなく起動します'
                : hasError
                ? '手動で Ollama を起動してからアプリを再起動してください'
                : 'Ollama とモデルの準備をしています。数分かかることがあります。'}
            </p>
          </div>
        </div>

        {/* ログターミナル */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-700 bg-slate-800">
            <Terminal className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-xs font-mono text-slate-400">セットアップログ</span>
          </div>
          <div className="h-80 overflow-y-auto p-4 font-mono text-xs space-y-0.5">
            {logs.length === 0 && (
              <span className="text-slate-500">バックエンドに接続しています...</span>
            )}
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2 leading-relaxed">
                <span className="text-slate-600 shrink-0">{log.ts}</span>
                <span className={`shrink-0 w-14 ${LEVEL_COLOR[log.level] ?? 'text-slate-300'}`}>
                  {log.level}
                </span>
                <span className="text-slate-300 break-all">{log.message}</span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {hasError && (
          <div className="mt-4 p-4 bg-red-900/30 border border-red-700 rounded-lg text-sm text-red-300">
            <p className="font-semibold mb-1">対処方法</p>
            <ol className="list-decimal list-inside space-y-1 text-xs">
              <li>
                <a
                  href="https://ollama.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-red-200"
                >
                  ollama.com
                </a>{' '}
                から Ollama を手動インストールしてください
              </li>
              <li>インストール後、アプリを再起動してください</li>
              <li>
                モデルが不足している場合は{' '}
                <code className="bg-red-900/50 px-1 rounded">ollama pull qwen3:8b</code>{' '}
                を実行してください
              </li>
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}
