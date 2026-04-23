'use client'

import { useState, useCallback, useRef } from 'react'

export interface AnimationConfig {
  duration: number
  delay?: number
  easing?: string
}

interface ActiveAnimation {
  id: string
  startTime: number
  duration: number
  onComplete?: () => void
}

export function useAnimation() {
  const [animatingIds, setAnimatingIds] = useState<Set<string>>(new Set())
  const animations = useRef<Map<string, ActiveAnimation>>(new Map())
  const frameRequest = useRef<number>()

  const startAnimation = useCallback((
    id: string,
    config: AnimationConfig,
    onComplete?: () => void
  ) => {
    const animation: ActiveAnimation = {
      id,
      startTime: Date.now() + (config.delay || 0),
      duration: config.duration,
      onComplete,
    }

    animations.current.set(id, animation)
    setAnimatingIds(prev => {
      const next = new Set(prev)
      next.add(id)
      return next
    })

    // Schedule completion
    const timeout = setTimeout(() => {
      animations.current.delete(id)
      setAnimatingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      onComplete?.()
    }, config.duration + (config.delay || 0))

    return () => clearTimeout(timeout)
  }, [])

  const stopAnimation = useCallback((id: string) => {
    animations.current.delete(id)
    setAnimatingIds(prev => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }, [])

  const stopAll = useCallback(() => {
    animations.current.clear()
    setAnimatingIds(new Set())
  }, [])

  const getProgress = useCallback((id: string): number => {
    const animation = animations.current.get(id)
    if (!animation) return 0

    const elapsed = Date.now() - animation.startTime
    return Math.min(elapsed / animation.duration, 1)
  }, [])

  const isAnimating = useCallback((id: string): boolean => {
    return animatingIds.has(id)
  }, [animatingIds])

  // Easing functions
  const easings = {
    linear: (t: number) => t,
    easeIn: (t: number) => t * t,
    easeOut: (t: number) => t * (2 - t),
    easeInOut: (t: number) => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
    easeInQuad: (t: number) => t * t,
    easeOutQuad: (t: number) => t * (2 - t),
    easeInCubic: (t: number) => t * t * t,
    easeOutCubic: (t: number) => (--t) * t * t + 1,
    easeInQuart: (t: number) => t * t * t * t,
    easeOutQuart: (t: number) => 1 - (--t) * t * t * t,
  }

  return {
    animatingIds,
    startAnimation,
    stopAnimation,
    stopAll,
    getProgress,
    isAnimating,
    easings,
  }
}
