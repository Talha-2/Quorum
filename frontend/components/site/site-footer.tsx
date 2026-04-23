import Link from 'next/link'
import { Github, Twitter, ArrowUpRight } from 'lucide-react'
import QuorumMark from './quorum-mark'

const linkGroups = [
  {
    title: 'Product',
    links: [
      { label: 'Workspace', href: '/workspace' },
      { label: 'Documentation', href: '/docs' },
      { label: 'Capabilities', href: '/#capabilities' },
      { label: 'Workflow', href: '/#workflow' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Quick start', href: '/docs' },
      { label: 'API reference', href: '/docs/api-reference' },
      { label: 'System model', href: '/docs/system-model' },
      { label: 'Workspace guide', href: '/docs/workspace-guide' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'GitHub', href: 'https://github.com' },
      { label: 'Blog', href: '#' },
      { label: 'Contact', href: '#' },
    ],
  },
]

export default function SiteFooter() {
  return (
    <footer className="border-t border-[var(--line)] bg-[var(--bg-soft)] mt-24">
      <div className="container-2xl py-16">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" className="flex items-center gap-2.5">
              <span className="text-[var(--brand)] inline-flex">
                <QuorumMark size={28} />
              </span>
              <span className="font-display text-lg font-semibold text-[var(--ink)]">
                Quorum
              </span>
            </Link>
            <p className="mt-4 text-sm text-[var(--muted)] max-w-xs leading-relaxed">
              A swarm of AI agents that debate your decisions in real time, build a knowledge
              graph, and converge on consensus.
            </p>
            <div className="mt-6 flex gap-3">
              <Link
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--line)] hover:border-[var(--brand)] hover:text-[var(--brand)] transition-colors"
                aria-label="GitHub"
              >
                <Github className="h-4 w-4" />
              </Link>
              <Link
                href="https://twitter.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[var(--line)] hover:border-[var(--brand)] hover:text-[var(--brand)] transition-colors"
                aria-label="Twitter"
              >
                <Twitter className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {linkGroups.map((group) => (
            <div key={group.title}>
              <h4 className="label-mono mb-4">{group.title}</h4>
              <ul className="space-y-3">
                {group.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="inline-flex items-center gap-1 text-sm text-[var(--ink)] hover:text-[var(--brand)] transition-colors"
                    >
                      {link.label}
                      {link.href.startsWith('http') && (
                        <ArrowUpRight className="h-3 w-3 text-[var(--muted)]" />
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-16 pt-8 border-t border-[var(--line)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-sm text-[var(--muted)]">
            © {new Date().getFullYear()} Quorum. Multi-agent reasoning for any decision.
          </p>
          <p className="text-xs text-[var(--muted-soft)] font-mono">v0.1.0 · MIT License</p>
        </div>
      </div>
    </footer>
  )
}
