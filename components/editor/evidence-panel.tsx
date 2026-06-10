"use client"

import * as React from "react"
import { Plus, PanelRightClose, PanelRightOpen, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { EvidenceCard } from "@/components/evidence/evidence-card"
import { cn } from "@/lib/utils"
import type { EvidenceAnchor } from "@/lib/editor-data"

interface EvidencePanelProps {
  evidence: EvidenceAnchor[]
  /** Number of statements without evidence (neutral orange counter). */
  unsupportedCount: number
}

export function EvidencePanel({
  evidence,
  unsupportedCount,
}: EvidencePanelProps) {
  const [collapsed, setCollapsed] = React.useState(false)

  const counterChip = (
    <span className="inline-flex items-center gap-1 rounded-full bg-status-partial/12 px-2 py-0.5 text-xs font-medium text-status-partial">
      <AlertTriangle className="size-3.5" />
      {`${unsupportedCount} Aussagen ohne Beleg`}
    </span>
  )

  if (collapsed) {
    return (
      <div className="flex w-10 shrink-0 flex-col items-center gap-3 border-l border-border bg-card py-3">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Belege einblenden"
          onClick={() => setCollapsed(false)}
        >
          <PanelRightOpen />
        </Button>
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="flex size-6 items-center justify-center rounded-full bg-status-partial/12 text-xs font-semibold text-status-partial outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`${unsupportedCount} Aussagen ohne Beleg`}
          title={`${unsupportedCount} Aussagen ohne Beleg`}
        >
          {unsupportedCount}
        </button>
      </div>
    )
  }

  return (
    <div className="flex w-80 shrink-0 flex-col border-l border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">
          Belege für diesen Abschnitt
        </h2>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Belege ausblenden"
          onClick={() => setCollapsed(true)}
        >
          <PanelRightClose />
        </Button>
      </div>

      <div className="px-4 py-2">{counterChip}</div>

      <ScrollArea className="min-h-0 flex-1 px-4">
        <div className="flex flex-col gap-2 pb-4">
          {evidence.map((e) => (
            <EvidenceCard key={e.id} evidence={e} />
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-border p-3">
        <Button variant="outline" className="w-full">
          <Plus data-icon="inline-start" />
          Beleg hinzufügen
        </Button>
      </div>
    </div>
  )
}
