'use client'

import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import { useEffect, useState } from 'react'

export default function ThemeToggle({ size = 'sm' }: { size?: 'sm' | 'md' }) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  const isDark = mounted && (resolvedTheme === 'dark' || theme === 'dark')
  const dim = size === 'md' ? 'h-10 w-10' : 'h-8 w-8'
  const iconSize = size === 'md' ? 'h-4 w-4' : 'h-3.5 w-3.5'

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label="Toggle theme"
      className={`${dim} inline-flex items-center justify-center rounded-md border border-[var(--line)] hover:border-[var(--brand)] hover:text-[var(--brand)] transition-colors`}
    >
      {mounted ? (
        isDark ? (
          <Sun className={iconSize} />
        ) : (
          <Moon className={iconSize} />
        )
      ) : (
        <span className={iconSize} />
      )}
    </button>
  )
}
