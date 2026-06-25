import { useEffect, useState } from 'react'

/**
 * 樱花飘落 — 极简版。
 *
 * 之前用 emoji `🌸`/`🌷` 在 macOS / Windows 上部分字体下会出现
 * "黑块/方块"（font-fallback 问题），且 emoji 本身偏 AI 味。
 * 改成纯 CSS 圆点 — 轻、柔、有温度。
 */
interface Petal {
  id: number
  left: number
  delay: number
  duration: number
  size: number
  opacity: number
}

const PALETTE = ['#C97B8A', '#F5E6E9', '#9A5A68', '#E8B5BE']

export default function SakuraPetals({ count = 8 }: { count?: number }) {
  const [petals, setPetals] = useState<Petal[]>([])

  useEffect(() => {
    const arr: Petal[] = Array.from({ length: count }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      delay: Math.random() * 14,
      duration: 14 + Math.random() * 8,
      size: 4 + Math.random() * 4,
      opacity: 0.25 + Math.random() * 0.3,
    }))
    setPetals(arr)
  }, [count])

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden" aria-hidden>
      {petals.map((p) => (
        <div
          key={p.id}
          className="petal-dot"
          style={{
            left: `${p.left}%`,
            width: `${p.size}px`,
            height: `${p.size}px`,
            backgroundColor: PALETTE[p.id % PALETTE.length],
            opacity: p.opacity,
            animationDelay: `${p.delay}s`,
            animationDuration: `${p.duration}s`,
          }}
        />
      ))}
    </div>
  )
}
