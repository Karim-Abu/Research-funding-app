"use client"

import * as React from "react"
import { Plus, FileText, PanelRightClose, PanelRightOpen, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { EvidenceCard } from "@/components/evidence/evidence-card"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { cn } from "@/lib/utils"
import type { EvidenceAnchor } from "@/lib/editor-data"

interface EvidencePanelProps {
  evidence: EvidenceAnchor[]
  /** Candidates offered in the "Beleg verknüpfen" sheet. */
  linkCandidates: EvidenceAnchor[]
  /** Number of statements without evidence (neutral orange counter). */
  unsupportedCount: number
}

export function EvidencePanel({
  evidence,
  linkCandidates,
  unsupportedCount,
}: EvidencePanelProps) {
  const [collapsed, setCollapsed] = React.useState(false)
  const [linked, setLinked] = React.useState(evidence)
  const [sheetOpen, setSheetOpen] = React.useState(false)

  function linkEvidence(anchor: EvidenceAnchor) {
    setLinked((prev) => [...prev, anchor])
    setSheetOpen(false)
  }

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
          {linked.map((e) => (
            <EvidenceCard key={e.id} evidence={e} />
          ))}
        </div>
      </ScrollArea>

      <div className="border-t border-border p-3">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => setSheetOpen(true)}
        >
          <Plus data-icon="inline-start" />
          Beleg hinzufügen
        </Button>
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Beleg verknüpfen</SheetTitle>
            <SheetDescription>
              Wählen Sie einen Beleg aus den Projektunterlagen für diesen
              Abschnitt aus.
            </SheetDescription>
          </SheetHeader>
          <div className="flex flex-col gap-2 px-4 pb-4">
            {linkCandidates.map((candidate) => {
              const alreadyLinked = linked.some((e) => e.id === candidate.id)
              return (
                <div
                  key={candidate.id}
                  className={cn(
                    "flex items-center gap-3 rounded-md border border-border p-3",
                    alreadyLinked && "bg-muted/40"
                  )}
                >
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate text-sm font-medium text-foreground">
                      {candidate.sourceTitle}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {candidate.location}
                    </span>
                    <MachineStatusBadge status={candidate.status} />
                  </div>
                  {alreadyLinked ? (
                    <span className="shrink-0 text-xs text-muted-foreground">
                      Bereits verknüpft
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      onClick={() => linkEvidence(candidate)}
                    >
                      Verknüpfen
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
