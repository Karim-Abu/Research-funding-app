import type { Metadata } from 'next'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppProviders } from '@/components/providers/app-providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'Evidenzbasierte Proposal-Unterstützung',
  description:
    'Interner Arbeitsbereich für Innosuisse-Innovationsprojekte (Beta).',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  // Server-controlled backend mode — read here (server component) and injected
  // via AppProviders. Never exposed as a NEXT_PUBLIC value.
  const mode = process.env.APP_BACKEND_MODE === 'live' ? 'live' : 'mock'
  return (
    <html lang="de" className="bg-background">
      <body className="font-sans antialiased">
        <AppProviders mode={mode}>
          <TooltipProvider>{children}</TooltipProvider>
        </AppProviders>
      </body>
    </html>
  )
}
