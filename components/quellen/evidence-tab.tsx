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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { HumanCheckMark } from "@/components/status/human-check-mark"
import { cn } from "@/lib/utils"
import type {
  EvidenceCard,
  EvidenceSection,
} from "@/lib/quellen-mock-data"
import { EVIDENCE_SECTIONS } from "@/lib/quellen-mock-data"
import type { MachineStatus } from "@/lib/types"

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

interface EvidenceFiltersProps {
  sectionFilter: EvidenceSection | "all"
  statusFilter: MachineStatus | "all"
  onSectionChange: (v: EvidenceSection | "all") => void
  onStatusChange: (v: MachineStatus | "all") => void
}

function EvidenceFilters({
  sectionFilter,
  statusFilter,
  onSectionChange,
  onStatusChange,
}: EvidenceFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Section filter */}
      <Select
        value={sectionFilter}
        onValueChange={(v) => onSectionChange(v as EvidenceSection | "all")}
      >
        <SelectTrigger className="h-9 w-52">
          <span className="truncate">
            {sectionFilter === "all" ? "Alle Abschnitte" : sectionFilter}
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Alle Abschnitte</SelectItem>
          {EVIDENCE_SECTIONS.map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Status filter */}
      <Select
        value={statusFilter}
        onValueChange={(v) => onStatusChange(v as MachineStatus | "all")}
      >
        <SelectTrigger className="h-9 w-44">
          <span className="truncate">
            {statusFilter === "all"
              ? "Alle Status"
              : STATUS_LABEL[statusFilter as MachineStatus]}
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Alle Status</SelectItem>
          <SelectItem value="verified">Verifiziert</SelectItem>
          <SelectItem value="partial">Prüfen</SelectItem>
          <SelectItem value="open">Offen</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

const STATUS_LABEL: Record<MachineStatus, string> = {
  verified: "Verifiziert",
  partial: "Prüfen",
  open: "Offen",
  blocker: "Blockierend",
}

// ---------------------------------------------------------------------------
// Evidence drawer (Sheet)
// ---------------------------------------------------------------------------

interface EvidenceDrawerProps {
  card: EvidenceCard | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onMarkChecked?: (id: string, comment: string) => void
}

function EvidenceDrawer({
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
          {/* Machine status + confidence (only here) */}
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

// ---------------------------------------------------------------------------
// Evidence card
// ---------------------------------------------------------------------------

interface EvidenceCardItemProps {
  card: EvidenceCard
  onClick: () => void
  onMarkChecked: (id: string) => void
}

function EvidenceCardItem({
  card,
  onClick,
  onMarkChecked,
}: EvidenceCardItemProps) {
  return (
    <article
      className={cn(
        "flex cursor-pointer flex-col gap-3 rounded-lg border border-border bg-card px-5 py-4",
        "transition-colors hover:bg-accent/40",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      )}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      aria-label={`Beleg öffnen: ${card.claimQuote.slice(0, 60)}`}
    >
      {/* Header: source + fundstelle */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-xs font-medium text-muted-foreground">
            {card.sourceTitle}
          </span>
          <span className="text-xs text-muted-foreground">{card.fundstelle}</span>
        </div>
        <MachineStatusBadge status={card.machineStatus} />
      </div>

      {/* Claim quote — max 2 lines */}
      <p className="line-clamp-2 text-sm leading-relaxed text-foreground">
        {card.claimQuote}
      </p>

      {/* Footer: human check or quick-mark + details affordance */}
      <div className="flex items-center justify-between gap-2" onClick={(e) => e.stopPropagation()}>
        {card.humanCheck ? (
          <HumanCheckMark check={card.humanCheck} />
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => onMarkChecked(card.id)}
          >
            <UserCheck className="mr-1.5 size-3.5" />
            Als geprüft markieren
          </Button>
        )}
        <span className="shrink-0 text-xs text-muted-foreground">
          Details anzeigen →
        </span>
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Evidence tab (top-level export)
// ---------------------------------------------------------------------------

interface EvidenceTabProps {
  cards: EvidenceCard[]
}

export function EvidenceTab({ cards }: EvidenceTabProps) {
  const [sectionFilter, setSectionFilter] = React.useState<
    EvidenceSection | "all"
  >("all")
  const [statusFilter, setStatusFilter] = React.useState<MachineStatus | "all">(
    "all"
  )
  const [drawerCard, setDrawerCard] = React.useState<EvidenceCard | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  // Track locally-marked cards (prototype only — no backend)
  const [localCards, setLocalCards] = React.useState<EvidenceCard[]>(cards)

  function openDrawer(card: EvidenceCard) {
    setDrawerCard(card)
    setDrawerOpen(true)
  }

  function handleCardMarkChecked(id: string) {
    // Immediately apply optimistic update — no drawer needed from the card.
    setLocalCards((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              humanCheck: {
                name: "Anna Keller",
                timestamp: "gerade eben",
              },
            }
          : c
      )
    )
  }

  function handleMarkChecked(id: string, comment: string) {
    setLocalCards((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              humanCheck: {
                name: "Anna Keller",
                timestamp: "gerade eben",
              },
            }
          : c
      )
    )
    setDrawerOpen(false)
  }

  const filtered = localCards.filter((c) => {
    if (sectionFilter !== "all" && c.section !== sectionFilter) return false
    if (statusFilter !== "all" && c.machineStatus !== statusFilter) return false
    return true
  })

  // Group by section in display order
  const grouped = EVIDENCE_SECTIONS.reduce<
    Record<string, EvidenceCard[]>
  >((acc, sec) => {
    const items = filtered.filter((c) => c.section === sec)
    if (items.length > 0) acc[sec] = items
    return acc
  }, {})

  return (
    <div className="flex flex-col gap-6">
      <EvidenceFilters
        sectionFilter={sectionFilter}
        statusFilter={statusFilter}
        onSectionChange={setSectionFilter}
        onStatusChange={setStatusFilter}
      />

      {filtered.length === 0 ? (
        <p
          role="status"
          className="py-10 text-center text-sm text-muted-foreground"
        >
          {localCards.length === 0
            ? "Noch keine Belege. Belege entstehen, wenn Sie die Analyse starten."
            : "Keine Belege entsprechen dem aktuellen Filter."}
        </p>
      ) : (
        <div className="flex flex-col gap-8">
          {Object.entries(grouped).map(([section, items]) => (
            <section key={section} aria-labelledby={`section-${section}`}>
              <h3
                id={`section-${section}`}
                className="mb-3 text-sm font-semibold text-foreground"
              >
                {section}
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  ({items.length})
                </span>
              </h3>
              <div className="grid gap-3 lg:grid-cols-2">
                {items.map((card) => (
                  <EvidenceCardItem
                    key={card.id}
                    card={card}
                    onClick={() => openDrawer(card)}
                    onMarkChecked={handleCardMarkChecked}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <EvidenceDrawer
        card={drawerCard}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        onMarkChecked={handleMarkChecked}
      />
    </div>
  )
}
