"use client"

import Link from "next/link"
import { HelpCircle } from "lucide-react"
import { ProjectSelector } from "./project-selector"
import { UserMenu } from "./user-menu"
import { useSession } from "@/components/providers/app-providers"
import type { Project, User } from "@/lib/types"

interface TopbarProps {
  user: User
  projects: Project[]
  activeProjectId: string
  onProjectChange?: (id: string) => void
}

export function Topbar({
  user,
  projects,
  activeProjectId,
  onProjectChange,
}: TopbarProps) {
  const { mode } = useSession()
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      {/* Left: project selector + demo-data hint (mock only) */}
      <div className="flex min-w-0 items-center gap-3">
        <ProjectSelector
          projects={projects}
          activeProjectId={activeProjectId}
          onChange={onProjectChange}
        />
        {mode === "mock" && (
          <span
            className="hidden shrink-0 items-center rounded-full border border-border bg-muted/50 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground sm:inline-flex"
            title="Beispieldaten · keine echten Antragsdaten"
          >
            Demo-Daten · keine echten Antragsdaten
          </span>
        )}
      </div>

      {/* Right: Hilfe link + user menu. Nothing else — no search, no notifications. */}
      <div className="flex items-center gap-2">
        <Link
          href="/hilfe"
          className="flex min-h-[44px] items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <HelpCircle className="size-4" />
          Hilfe
        </Link>
        <UserMenu user={user} />
      </div>
    </header>
  )
}
