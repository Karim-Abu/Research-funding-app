"use client"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"
import type { PortalSection } from "@/lib/editor-data"

interface SectionHeaderCardProps {
  section: PortalSection
  sections: PortalSection[]
  onSectionChange: (id: string) => void
  /** Live character count from the draft textarea (overrides section.charCount). */
  liveCharCount?: number
}

function formatThousands(n: number) {
  return n.toLocaleString("de-CH").replace(/,/g, "'")
}

export function SectionHeaderCard({
  section,
  sections,
  onSectionChange,
  liveCharCount,
}: SectionHeaderCardProps) {
  const charCount = liveCharCount ?? section.charCount
  const over = charCount > section.charLimit
  const pct = Math.min((charCount / section.charLimit) * 100, 100)

  return (
    <div className="flex flex-col gap-4 border-b border-border bg-card px-6 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold text-foreground">
              {section.name}
            </h1>
            {section.mandatory && (
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                  section.status === "fulfilled"
                    ? "bg-status-fulfilled/12 text-status-fulfilled"
                    : "bg-status-partial/12 text-status-partial"
                )}
              >
                {section.status === "fulfilled"
                  ? "Pflichtfeld · Erfüllt"
                  : "Pflichtfeld · Offen"}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">{section.guidance}</p>
        </div>

        {/* Section switcher with small status dots */}
        <Select
          value={section.id}
          onValueChange={(v) => {
            if (v !== null) onSectionChange(v)
          }}
        >
          <SelectTrigger className="h-9 w-[300px] shrink-0" aria-label="Abschnitt wechseln">
            <span className="flex items-center gap-2 truncate">
              <span
                className={cn(
                  "size-2 shrink-0 rounded-full",
                  section.status === "fulfilled"
                    ? "bg-status-fulfilled"
                    : "bg-status-partial"
                )}
              />
              <span className="truncate">{section.name}</span>
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {sections.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  <span className="flex items-center gap-2">
                    <span
                      className={cn(
                        "size-2 rounded-full",
                        s.status === "fulfilled"
                          ? "bg-status-fulfilled"
                          : "bg-status-partial"
                      )}
                    />
                    {s.name}
                  </span>
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex flex-1 flex-col gap-1">
          <Progress
            value={pct}
            className={cn("h-1.5", over && "[&>*]:bg-destructive")}
          />
        </div>
        <span
          className={cn(
            "text-xs font-medium tabular-nums",
            over ? "text-destructive" : "text-muted-foreground"
          )}
        >
          {`${formatThousands(charCount)} / ${formatThousands(section.charLimit)}`}
        </span>
        <span className="text-xs text-muted-foreground">
          Automatisch gespeichert
        </span>
      </div>
    </div>
  )
}
