'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { Menu, X, ArrowUpRight } from 'lucide-react'
import QuorumMark from './quorum-mark'
import ThemeToggle from './theme-toggle'

const navLinks = [
  { href: '/workspace', label: 'Workspace' },
  { href: '/docs', label: 'Docs' },
  { href: '/#capabilities', label: 'Capabilities' },
  { href: '/#workflow', label: 'Workflow' },
]

export default function SiteHeader() {
  const pathname = usePathname()
  const [open, setOpen] = useState(false)

  const isActive = (href: string) =>
    href.startsWith('/#') ? false : pathname === href || pathname?.startsWith(href + '/')

  return (
    <header className="sticky top-0 z-50 bg-[var(--bg)]/85 backdrop-blur-md border-b border-[var(--line)]">
      <div className="container-2xl flex items-center justify-between h-16">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="text-[var(--brand)] group-hover:rotate-12 transition-transform inline-flex">
            <QuorumMark size={26} />
          </span>
          <span className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
            Quorum
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`px-3 py-2 text-sm font-medium rounded-md transition-colors hover:bg-[var(--brand-soft)] hover:text-[var(--brand)] ${
                isActive(link.href) ? 'text-[var(--brand)]' : 'text-[var(--ink)]'
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-ghost btn-sm"
          >
            GitHub
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
          <Link href="/workspace" className="btn btn-primary btn-sm">
            Launch
          </Link>
        </div>

        {/* Mobile toggle */}
        <button
          className="md:hidden p-2 rounded-md hover:bg-[var(--bg-soft)] text-[var(--ink)]"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden border-t border-[var(--line)] bg-[var(--bg)]">
          <div className="container-2xl py-4 flex flex-col gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="px-3 py-2 text-sm font-medium rounded-md hover:bg-[var(--brand-soft)] hover:text-[var(--brand)] text-[var(--ink)]"
              >
                {link.label}
              </Link>
            ))}
            <div className="flex gap-2 mt-3">
              <ThemeToggle />
              <Link
                href="/workspace"
                className="btn btn-primary btn-sm flex-1"
                onClick={() => setOpen(false)}
              >
                Launch workspace
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
