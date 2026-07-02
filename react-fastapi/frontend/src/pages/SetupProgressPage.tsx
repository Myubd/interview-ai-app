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
import { CheckCircle, AlertCircle, Loader2, Terminal, ChevronDown, ChevronUp } from 'lucide-react'
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

/**
 * 技術者向けの生ログから、就活生など非エンジニアにも伝わる
 * 一言サマリーを推定する。バックエンドのログ文言（日本語）に含まれる
 * キーワードで大まかな「今どの段階か」を判定するだけなので、
 * 未知の文言が来ても最後に見えた段階のサマリーを表示し続ける。
 */
function summarizeStage(logs: SetupLogEntry[]): string {
  for (let i = logs.length - 1; i >= 0; i--) {
    const msg = logs[i].message
    if (/モデル.*ダウンロード|pull/.test(msg)) return 'AIモデルをダウンロードしています（数分かかることがあります）'
    if (/モデル.*確認|インストール済み/.test(msg)) return '必要なAIモデルを確認しています'
    if (/起動するまで待機|起動しました|Ollama プロセス/.test(msg)) return 'Ollama を起動しています'
    if (/インストール中|インストール完了|ダウンロード完了|Ollama のインストール/.test(msg)) return 'Ollama をインストールしています'
    if (/ブラウザを開いて/.test(msg)) return 'アプリの準備が整いました'
  }
  return 'セットアップの準備をしています'
}

export const SetupProgressPage: React.FC<Props> = ({ onComplete }) => {
  const [logs, setLogs] = useState<SetupLogEntry[]>([])
  const [done, setDone] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
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
      (entry) => setLogs(prev => {
        // group が付いている行（ダウンロード進捗バーなど）は、
        // 同じ group の直前の行を上書きして縦に積み上げないようにする
        if (entry.group) {
          const idx = prev.findIndex(l => l.group === entry.group)
          if (idx !== -1) {
            const next = [...prev]
            next[idx] = entry
            return next
          }
        }
        return [...prev, entry]
      }),
      () => {
        setDone(true)
        setTimeout(onComplete, 1500)
      },
      () => {
        setHasError(true)
        setShowDetails(true) // エラー時は原因調査のため詳細ログを自動展開
      },
    )
    return unsubscribe
  }, [onComplete])

  // 新しいログが来たら自動スクロール
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const stageSummary = summarizeStage(logs)

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* ヘッダー */}
        <div className="flex items-center gap-3 mb-4">
          {done ? (
            <CheckCircle className="w-7 h-7 text-emerald-400 shrink-0" aria-hidden="true" />
          ) : hasError ? (
            <AlertCircle className="w-7 h-7 text-red-400 shrink-0" aria-hidden="true" />
          ) : (
            <Loader2 className="w-7 h-7 text-brand-400 animate-spin shrink-0" aria-hidden="true" />
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
                : 'AIモデルを使う準備をしています。初回のみ数分〜十数分かかることがあります。'}
            </p>
          </div>
        </div>

        {/* 非エンジニア向けの一言サマリー */}
        {!done && (
          <div
            role="status"
            aria-live="polite"
            className="mb-4 px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 flex items-center gap-3"
          >
            {!hasError && <Loader2 className="w-4 h-4 text-brand-400 animate-spin shrink-0" aria-hidden="true" />}
            <p className="text-sm text-slate-200">{hasError ? '準備中にエラーが発生しました' : stageSummary}</p>
          </div>
        )}

        {/* 詳細ログ（折りたたみ） */}
        <div className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
          <button
            onClick={() => setShowDetails(v => !v)}
            aria-expanded={showDetails}
            aria-controls="setup-log-detail"
            className="w-full flex items-center justify-between gap-2 px-4 py-2 border-b border-slate-700 bg-slate-800 hover:bg-slate-700/60 transition-colors"
          >
            <span className="flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
              <span className="text-xs font-mono text-slate-400">詳細ログ（技術情報）</span>
            </span>
            {showDetails
              ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
              : <ChevronDown className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />}
          </button>
          {showDetails && (
            <div id="setup-log-detail" className="h-80 overflow-y-auto p-4 font-mono text-xs space-y-0.5">
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
          )}
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
