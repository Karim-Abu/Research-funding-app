"use client"

import Link from "next/link"
import { HelpCircle } from "lucide-react"
import { ProjectSelector } from "./project-selector"
import { UserMenu } from "./user-menu"
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
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-card px-4">
      {/* Left: project selector */}
      <ProjectSelector
        projects={projects}
        activeProjectId={activeProjectId}
        onChange={onProjectChange}
      />

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
