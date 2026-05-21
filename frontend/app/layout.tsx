import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { RootProvider } from 'fumadocs-ui/provider'
import './globals.css'

// Inter as a robust fallback for Google Sans
const fallbackBody = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-fallback-body',
  display: 'swap',
})

const monoFont = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'Quorum',
    template: 'Quorum',
  },
  description:
    'Convene a swarm of AI agents for your toughest decisions. Upload a doc, build a knowledge graph, run a multi-agent debate, and get a structured report.',
  icons: {
    icon: '/icon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/*
          Google Sans is Google's proprietary family and is not in the
          next/font/google catalog, so it is loaded via a stylesheet link.
          Inter (loaded above via next/font) is the fallback.
        */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Google+Sans+Text:wght@400;500;700&family=Google+Sans:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className={`${fallbackBody.variable} ${monoFont.variable} min-h-screen`}
      >
        <RootProvider
          theme={{
            attribute: 'class',
            defaultTheme: 'light',
            enableSystem: true,
          }}
        >
          {children}
        </RootProvider>
      </body>
    </html>
  )
}
