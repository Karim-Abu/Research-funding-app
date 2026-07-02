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

// Labelled switcher for the active application ("Aktueller Antrag"): the
// selected Antrag governs every project-scoped screen, so the label and the
// current title must always be visible — never a bare, unexplained dropdown.
export function ProjectSelector({
  projects,
  activeProjectId,
  onChange,
}: ProjectSelectorProps) {
  const active = projects.find((p) => p.id === activeProjectId)
  return (
    <div className="flex items-center gap-2">
      <span className="shrink-0 text-xs font-medium text-muted-foreground">
        Aktueller Antrag
      </span>
      <Select
        value={active ? activeProjectId : ""}
        onValueChange={(v) => {
          if (v) onChange?.(v)
        }}
      >
        <SelectTrigger
          className="h-9 w-[280px]"
          aria-label="Aktuellen Antrag auswählen"
          data-testid="active-project-switcher"
        >
          <span className={active ? "truncate" : "truncate text-muted-foreground"}>
            {active?.title ?? "Antrag auswählen"}
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {projects.length === 0 ? (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                Keine Anträge vorhanden
              </div>
            ) : (
              projects.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.title}
                </SelectItem>
              ))
            )}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
