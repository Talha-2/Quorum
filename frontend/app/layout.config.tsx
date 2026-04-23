import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared'
import QuorumMark from '@/components/site/quorum-mark'

export const baseOptions: BaseLayoutProps = {
  nav: {
    title: (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ color: '#FF4500', display: 'inline-flex' }}>
          <QuorumMark size={24} />
        </span>
        <span style={{ fontWeight: 600, letterSpacing: '-0.01em' }}>Quorum</span>
      </span>
    ),
  },
  links: [
    {
      text: 'Workspace',
      url: '/workspace',
      active: 'nested-url',
    },
    {
      text: 'Docs',
      url: '/docs',
      active: 'nested-url',
    },
    {
      text: 'GitHub',
      url: 'https://github.com',
      external: true,
    },
  ],
}
