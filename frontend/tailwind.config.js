/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /* 暖纸感背景 — 60% */
        bg: {
          DEFAULT: '#FAF8F5',
          subtle: '#F5F2EC',
        },
        /* 表面层 — 30% */
        surface: {
          DEFAULT: '#FFFFFF',
          hover: '#FCFAF7',
        },
        /* 边框 */
        border: {
          DEFAULT: '#E8E4DD',
          strong: '#D8D3CA',
        },
        /* 暖墨文字 */
        ink: {
          DEFAULT: '#1A1715',
          soft: '#4A4540',
          muted: '#6B655C',
          faint: '#A8A299',
        },
        /* 柔粉强调 — 10% */
        sakura: {
          50: '#FBF3F5',
          100: '#F5E6E9',
          200: '#EBCDD4',
          300: '#DCAAB5',
          400: '#C97B8A',
          500: '#B56B7A',
          600: '#9A5A68',
          700: '#8C4A57',
        },
        /* 语义色 — 柔和 */
        sage: {
          soft: '#EBF0EB',
          DEFAULT: '#6B8E6B',
        },
        amber: {
          soft: '#F5EDE2',
          DEFAULT: '#C4955E',
        },
        clay: {
          soft: '#F5EAEA',
          DEFAULT: '#B56B6B',
        },
        /* 兼容旧代码 — aurora 映射到 ink 系 */
        aurora: {
          50: '#F5F2EC',
          100: '#E8E4DD',
          200: '#D8D3CA',
          300: '#A8A299',
          400: '#6B655C',
          500: '#4A4540',
          600: '#1A1715',
          700: '#1A1715',
        },
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['"Fraunces"', '"Noto Serif SC"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'sm': '0 1px 2px rgba(26, 23, 21, 0.04)',
        'md': '0 1px 3px rgba(26, 23, 21, 0.06), 0 4px 12px -2px rgba(26, 23, 21, 0.04)',
        'lg': '0 2px 8px rgba(26, 23, 21, 0.06), 0 12px 32px -4px rgba(26, 23, 21, 0.08)',
      },
      animation: {
        'fade-up': 'fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both',
        'fade-in': 'fadeIn 0.4s ease-out both',
        'float': 'float 6s ease-in-out infinite',
        'breathe': 'breathe 4s ease-in-out infinite',
        'petal-fall': 'petalFall 14s linear infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeUp: { '0%': { opacity: '0', transform: 'translateY(16px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        float: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-8px)' } },
        breathe: { '0%,100%': { opacity: '1', transform: 'scale(1)' }, '50%': { opacity: '0.85', transform: 'scale(0.98)' } },
        petalFall: {
          '0%': { transform: 'translateY(-10vh) rotate(0deg)', opacity: '0' },
          '10%': { opacity: '0.4' },
          '90%': { opacity: '0.2' },
          '100%': { transform: 'translateY(110vh) rotate(360deg)', opacity: '0' },
        },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
    },
  },
  plugins: [],
}
