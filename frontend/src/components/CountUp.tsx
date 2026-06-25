/**
 * 数字滚动动画 — 从 0 增长到目标值。
 *
 * 借鉴 opendesign / Linear / Vercel 的"实时指标"组件。
 * 使用 requestAnimationFrame + 缓动函数（easeOutCubic）让动画自然。
 * 支持千分位 / 后缀（+ / % / 位 / 小时 / 次）。
 *
 * 修复 React 18 StrictMode 双 mount 导致的 startedRef 不重置问题：
 * cleanup 里必须把 startedRef 重置回 false,这样第二次 mount 时 run() 才能跑。
 */

import { useEffect, useRef, useState } from 'react'

interface CountUpProps {
  end: number
  duration?: number           // 毫秒
  start?: number
  prefix?: string
  suffix?: string
  decimals?: number
  separator?: string          // 千分位
  className?: string
  delay?: number              // 延迟启动（ms）
  /** 当数字进入视口才触发（默认 true） */
  triggerOnView?: boolean
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

export default function CountUp({
  end,
  duration = 1800,
  start = 0,
  prefix = '',
  suffix = '',
  decimals = 0,
  separator = ',',
  className = '',
  delay = 0,
  triggerOnView = true,
}: CountUpProps) {
  const [value, setValue] = useState(start)
  const ref = useRef<HTMLSpanElement>(null)
  const startedRef = useRef(false)
  const rafRef = useRef<number | null>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const run = () => {
      if (startedRef.current) return
      startedRef.current = true
      const t0 = performance.now() + delay
      const tick = (now: number) => {
        if (now < t0) {
          rafRef.current = requestAnimationFrame(tick)
          return
        }
        const progress = Math.min(1, (now - t0) / duration)
        const eased = easeOutCubic(progress)
        const current = start + (end - start) * eased
        setValue(current)
        if (progress < 1) {
          rafRef.current = requestAnimationFrame(tick)
        } else {
          setValue(end)
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    if (!triggerOnView) {
      run()
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            run()
            observer.disconnect()
            observerRef.current = null
            break
          }
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -10% 0px' }
    )
    observer.observe(el)
    observerRef.current = observer

    return () => {
      // ★ 关键:cleanup 必须重置 startedRef,否则 React 18 StrictMode 双 mount 后
      //   第二次 mount 时 startedRef.current === true,run() 被守卫拒,数字卡死。
      observer.disconnect()
      observerRef.current = null
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      startedRef.current = false
    }
  }, [end, duration, start, delay, triggerOnView])

  const display = (() => {
    const fixed = value.toFixed(decimals)
    if (!separator) return fixed
    const [intPart, decPart] = fixed.split('.')
    const withSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, separator)
    return decPart !== undefined ? `${withSep}.${decPart}` : withSep
  })()

  return (
    <span ref={ref} className={className}>
      {prefix}{display}{suffix}
    </span>
  )
}
