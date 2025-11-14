import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'UI State Agent',
  description: 'AI-powered UI state capture agent for automated workflow documentation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  )
}
