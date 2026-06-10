"use client"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import type { Project } from "@/lib/types"

interface ProjectSelectorProps {
  projects: Project[]
  activeProjectId: string
  onChange?: (id: string) => void
}

export function ProjectSelector({
  projects,
  activeProjectId,
  onChange,
}: ProjectSelectorProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground">Projekt</span>
      <Select value={activeProjectId} onValueChange={onChange}>
        <SelectTrigger className="h-9 w-[280px]" aria-label="Projekt auswählen">
          <span className="truncate">
            {projects.find((p) => p.id === activeProjectId)?.title ?? activeProjectId}
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {projects.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.title}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
