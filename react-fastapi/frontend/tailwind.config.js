/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── ブランドカラー ──────────────────────────────────
        // 就活というシリアスなコンテキストに合わせ、
        // 信頼感のある深い青と温かみのあるアクセントを採用。
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          400: '#818cf8',
          500: '#6366f1',  // primary
          600: '#4f46e5',
          700: '#4338ca',
          900: '#1e1b4b',
        },
        accent: {
          400: '#fb923c',  // warm orange — 強調・CTA
          500: '#f97316',
        },
        surface: {
          0:   '#ffffff',
          50:  '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
        },
      },
      fontFamily: {
        sans: ['"Noto Sans JP"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'fade-in':  'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.25s ease-out',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:   { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:  { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        pulseDot: { '0%,80%,100%': { transform: 'scale(0)' }, '40%': { transform: 'scale(1)' } },
      },
    },
  },
  plugins: [],
}
