/**
 * components/Sidebar.tsx
 * React版のページナビゲーション。
 * Streamlit 版に残る機能はリンクでなく外部遷移ボタンとして表示。
 *
 * [変更点]
 * - ダッシュボードページへのナビゲーション項目を追加。
 */
import React from 'react'
import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  Home,
  Mic2,
  History,
  BarChart2,
  Database,
  Settings,
  ExternalLink,
} from 'lucide-react'

interface NavItem {
  to: string
  icon: React.ReactNode
  label: string
  badge?: string
}

const REACT_PAGES: NavItem[] = [
  { to: '/',               icon: <Home className="w-5 h-5" />,      label: 'ホーム' },
  { to: '/mock-interview', icon: <Mic2 className="w-5 h-5" />,      label: 'AI模擬面接' },
  { to: '/history',        icon: <History className="w-5 h-5" />,   label: '面接履歴' },
  { to: '/dashboard',      icon: <BarChart2 className="w-5 h-5" />, label: 'ダッシュボード' },
  { to: '/knowledge',      icon: <Database className="w-5 h-5" />,  label: 'ナレッジベース' },
  { to: '/settings',       icon: <Settings className="w-5 h-5" />,  label: '設定' },
]

// Streamlitに残る機能
const STREAMLIT_FEATURES = [
  '📄 自己PR作成',
  '🏢 企業比較マトリクス',
  '🎯 想定質問生成',
  '📊 性格診断 (Big Five)',
  '💬 AIキャリアアドバイザー',
]

export const Sidebar: React.FC = () => {

  return (
    <nav className="w-60 flex-shrink-0 bg-white border-r border-surface-200 flex flex-col h-screen sticky top-0">
      {/* ロゴ */}
      <div className="px-5 py-5 border-b border-surface-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-white text-sm font-bold">
            面
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900 leading-tight">就活インタビューAI</p>
            <p className="text-xs text-slate-400">React版</p>
          </div>
        </div>
      </div>

      {/* React ページ */}
      <div className="flex-1 overflow-y-auto py-3">
        <div className="px-3 mb-1">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 mb-1">メニュー</p>
          <ul className="space-y-0.5">
            {REACT_PAGES.map(item => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                      isActive
                        ? 'bg-brand-50 text-brand-700 font-medium'
                        : 'text-slate-600 hover:bg-surface-50 hover:text-slate-900',
                    )
                  }
                >
                  {item.icon}
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className="text-xs bg-accent-400 text-white rounded-full px-1.5 py-0.5">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>

        {/* Streamlit 版へのリンク */}
        <div className="px-3 mt-4 pt-4 border-t border-surface-100">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 mb-2">
            Streamlit版の機能
          </p>
          <ul className="space-y-0.5">
            {STREAMLIT_FEATURES.map(f => (
              <li key={f}>
                <a
                  href="http://localhost:8501"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-500 hover:text-slate-700 hover:bg-surface-50 transition-colors"
                >
                  <span className="flex-1">{f}</span>
                  <ExternalLink className="w-3 h-3 opacity-50" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* フッター */}
      <div className="px-5 py-4 border-t border-surface-100">
        <p className="text-xs text-slate-400">ローカル動作 · データ非送信</p>
      </div>
    </nav>
  )
}
