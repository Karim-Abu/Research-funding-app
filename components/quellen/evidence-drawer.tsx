"use client"

import * as React from "react"
import { ExternalLink, UserCheck } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { HumanCheckMark } from "@/components/status/human-check-mark"
import type { EvidenceCard } from "@/lib/quellen-mock-data"

export interface EvidenceDrawerProps {
  card: EvidenceCard | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onMarkChecked?: (id: string, comment: string) => void
}

/**
 * Shared evidence detail drawer.
 * Reused by both the Quellen/Evidenz tab and the Anforderungen screen.
 */
export function EvidenceDrawer({
  card,
  open,
  onOpenChange,
  onMarkChecked,
}: EvidenceDrawerProps) {
  const [comment, setComment] = React.useState("")
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    if (!open) setComment("")
  }, [open])

  if (!card) return null

  function handleMarkChecked() {
    if (!card) return
    setSaving(true)
    setTimeout(() => {
      setSaving(false)
      onMarkChecked?.(card.id, comment)
      onOpenChange(false)
    }, 600)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-[520px] flex-col gap-0 overflow-y-auto p-0 sm:max-w-[520px]"
      >
        <SheetHeader className="border-b border-border px-6 py-5">
          <SheetTitle className="text-base">{card.section}</SheetTitle>
          <SheetDescription className="flex items-center gap-2 text-xs">
            <span className="font-medium text-foreground">
              {card.sourceTitle}
            </span>
            <span className="text-muted-foreground">·</span>
            <span className="text-muted-foreground">{card.fundstelle}</span>
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-5 px-6 py-5">
          {/* Machine status + confidence (only shown inside drawer) */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <MachineStatusBadge status={card.machineStatus} />
              <span className="text-xs text-muted-foreground">
                Konfidenz:{" "}
                <span className="font-medium text-foreground">
                  {card.confidencePercent} %
                </span>{" "}
                (automatische Einschätzung)
              </span>
            </div>
          </div>

          <Separator />

          {/* Full passage */}
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Vollständiger Textabschnitt
            </p>
            <blockquote className="rounded-md border-l-2 border-border bg-muted/30 px-4 py-3 text-sm leading-relaxed text-foreground">
              {card.fullPassage}
            </blockquote>
            <div className="flex flex-col gap-0.5">
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                <ExternalLink className="size-3" />
                Originalquelle öffnen
              </a>
              <span className="text-xs text-muted-foreground">
                Öffnet die hochgeladene Quelle oder URL.
              </span>
            </div>
          </div>

          <Separator />

          {/* Linked sections */}
          {card.linkedSections.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Verknüpfte Abschnitte
              </p>
              <div className="flex flex-wrap gap-1.5">
                {card.linkedSections.map((sec) => (
                  <span
                    key={sec}
                    className="inline-flex items-center rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-xs text-foreground"
                  >
                    {sec}
                  </span>
                ))}
              </div>
            </div>
          )}

          <Separator />

          {/* Human check area */}
          {card.humanCheck ? (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Menschliche Prüfung
              </p>
              <HumanCheckMark check={card.humanCheck} />
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Als geprüft markieren
              </p>
              <Textarea
                placeholder="Optionaler Kommentar zur Prüfung…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                className="resize-none text-sm"
              />
              <Button
                onClick={handleMarkChecked}
                disabled={saving}
                className="self-start"
              >
                {saving ? (
                  <>Wird gespeichert…</>
                ) : (
                  <>
                    <UserCheck className="mr-1.5 size-4" />
                    Als geprüft markieren
                  </>
                )}
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
