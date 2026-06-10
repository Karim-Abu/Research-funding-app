"use client"

import { Construction } from "lucide-react"
import { AppShell } from "@/components/shell/app-shell"
import { currentUser, projects, activeProjectId } from "@/lib/mock-data"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty"

export function PlaceholderScreen({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <AppShell
      user={currentUser}
      projects={projects}
      activeProjectId={activeProjectId}
    >
      <div className="flex h-full items-center justify-center px-6 py-16">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Construction />
            </EmptyMedia>
            <EmptyTitle>{title}</EmptyTitle>
            <EmptyDescription>{description}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </AppShell>
  )
}
