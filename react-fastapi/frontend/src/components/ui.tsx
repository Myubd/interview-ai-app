/**
 * components/ui.tsx
 * 最小限の共通 UI コンポーネント。
 * shadcn/ui 未導入のため Tailwind で自前実装。
 */
import React from 'react'
import { clsx } from 'clsx'
import { Loader2 } from 'lucide-react'

// ── Button ────────────────────────────────────────────────────────

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ReactNode
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}) => {
  const base = 'inline-flex items-center gap-2 font-medium rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed'

  const variants: Record<ButtonVariant, string> = {
    primary:   'bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-700',
    secondary: 'bg-surface-100 text-slate-700 hover:bg-surface-200 border border-surface-200',
    ghost:     'text-slate-600 hover:bg-surface-100 hover:text-slate-900',
    danger:    'bg-red-500 text-white hover:bg-red-600',
  }

  const sizes: Record<ButtonSize, string> = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }

  return (
    <button
      className={clsx(base, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

// ── Badge ─────────────────────────────────────────────────────────

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info'

interface BadgeProps {
  variant?: BadgeVariant
  children: React.ReactNode
  className?: string
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'default', children, className }) => {
  const variants: Record<BadgeVariant, string> = {
    default: 'bg-surface-100 text-slate-600',
    success: 'bg-emerald-50 text-emerald-700',
    warning: 'bg-amber-50 text-amber-700',
    error:   'bg-red-50 text-red-700',
    info:    'bg-brand-50 text-brand-700',
  }
  return (
    <span className={clsx('inline-block px-2 py-0.5 rounded-full text-xs font-medium', variants[variant], className)}>
      {children}
    </span>
  )
}

// ── Card ──────────────────────────────────────────────────────────

interface CardProps {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}

export const Card: React.FC<CardProps> = ({ children, className, onClick }) => (
  <div
    className={clsx(
      'bg-white rounded-xl border border-surface-200 shadow-sm',
      onClick && 'cursor-pointer hover:border-brand-200 hover:shadow-md transition-all',
      className,
    )}
    onClick={onClick}
  >
    {children}
  </div>
)

// ── Spinner ───────────────────────────────────────────────────────

export const Spinner: React.FC<{ className?: string }> = ({ className }) => (
  <Loader2 className={clsx('animate-spin text-brand-500', className ?? 'w-5 h-5')} />
)

// ── TypingIndicator ───────────────────────────────────────────────

export const TypingIndicator: React.FC = () => (
  <div className="flex items-center gap-0.5 px-1 py-0.5" role="status" aria-label="AIが入力中です">
    <span className="typing-dot" aria-hidden="true" />
    <span className="typing-dot" aria-hidden="true" />
    <span className="typing-dot" aria-hidden="true" />
  </div>
)

// ── ProgressBar ───────────────────────────────────────────────────
// スクリーンリーダーにも進捗が伝わるよう role="progressbar" を付与した棒グラフ。

interface ProgressBarProps {
  value: number
  max?: number
  label?: string
  className?: string
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ value, max = 100, label, className }) => (
  <div
    role="progressbar"
    aria-valuenow={Math.round(value)}
    aria-valuemin={0}
    aria-valuemax={max}
    aria-label={label}
    className={clsx('h-1.5 bg-surface-100 rounded-full overflow-hidden', className)}
  >
    <div
      className="h-full bg-brand-400 rounded-full transition-all duration-500"
      style={{ width: `${Math.min(100, Math.round((value / max) * 100))}%` }}
    />
  </div>
)

// ── EmptyState ────────────────────────────────────────────────────

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => (
  <div className="flex flex-col items-center justify-center py-16 px-4 text-center animate-fade-in">
    {icon && <div className="mb-4 text-slate-300">{icon}</div>}
    <p className="text-slate-700 font-medium mb-1">{title}</p>
    {description && <p className="text-slate-500 text-sm mb-4">{description}</p>}
    {action}
  </div>
)

// ── Toast（超シンプル版、状態は親が管理）─────────────────────────

interface ToastProps {
  message: string
  variant?: 'success' | 'error'
}

export const Toast: React.FC<ToastProps> = ({ message, variant = 'success' }) => (
  <div
    className={clsx(
      'fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-3 rounded-xl shadow-lg text-sm font-medium animate-slide-up z-50',
      variant === 'success' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white',
    )}
  >
    {message}
  </div>
)
