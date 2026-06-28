"use client"

import * as React from "react"
import { UserCheck, ExternalLink, PencilLine, Info } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { MachineStatusBadge } from "@/components/status/machine-status-badge"
import { HumanCheckMark } from "@/components/status/human-check-mark"
import { EvidenceDrawer } from "@/components/quellen/evidence-drawer"
import { EvidenceFilterBar } from "@/components/quellen/evidence-filter-bar"
import {
  EVIDENCE_VERIFIED_HINT,
  REVIEWER_FALLBACK,
  type EvidenceFilter,
  type EvidenceStatusFilter,
} from "@/lib/evidence"
import type { EvidenceCard } from "@/lib/quellen-mock-data"
import { EVIDENCE_SECTIONS } from "@/lib/quellen-mock-data"
import { MACHINE_STATUS_LABELS, type MachineStatus } from "@/lib/types"

// Map the machine status onto the shared evidence filter status.
const MACHINE_TO_FILTER: Record<MachineStatus, EvidenceStatusFilter> = {
  verified: "verified",
  partial: "review",
  open: "open",
  blocker: "error",
}

type GroupBy = "section" | "source" | "status"

const GROUP_BY_LABELS: Record<GroupBy, string> = {
  section: "Portalabschnitt",
  source: "Quelle",
  status: "Status",
}

// ---------------------------------------------------------------------------
// Evidence card
// ---------------------------------------------------------------------------

interface EvidenceCardItemProps {
  card: EvidenceCard
  onOpenDetails: () => void
  onCorrect: () => void
  onMarkChecked: (id: string) => void
}

function EvidenceCardItem({
  card,
  onOpenDetails,
  onCorrect,
  onMarkChecked,
}: EvidenceCardItemProps) {
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border bg-card px-5 py-4">
      {/* Header: source + Fundstelle + status */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-xs font-medium text-muted-foreground">
            {card.sourceTitle}
          </span>
          <span className="text-xs text-muted-foreground">{card.fundstelle}</span>
        </div>
        <MachineStatusBadge status={card.machineStatus} />
      </div>

      {/* Aussage / Zitat */}
      <p className="line-clamp-3 text-sm leading-relaxed text-foreground">
        {card.claimQuote}
      </p>

      {/* Prüferanzeige */}
      <div>
        {card.humanCheck ? (
          <HumanCheckMark check={card.humanCheck} />
        ) : (
          <span className="text-xs text-muted-foreground">{REVIEWER_FALLBACK}</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-border pt-3">
        <a
          href="#"
          onClick={(e) => e.preventDefault()}
          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <ExternalLink className="size-3.5" />
          Quelle öffnen
        </a>
        {!card.humanCheck && (
          <button
            type="button"
            onClick={() => onMarkChecked(card.id)}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <UserCheck className="size-3.5" />
            Als geprüft markieren
          </button>
        )}
        <button
          type="button"
          onClick={onCorrect}
          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <PencilLine className="size-3.5" />
          Korrigieren
        </button>
        <button
          type="button"
          onClick={onOpenDetails}
          className="ml-auto text-xs font-medium text-primary hover:underline"
        >
          Details anzeigen
        </button>
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
  const [filter, setFilter] = React.useState<EvidenceFilter>("all")
  const [groupBy, setGroupBy] = React.useState<GroupBy>("section")
  const [drawerCard, setDrawerCard] = React.useState<EvidenceCard | null>(null)
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  // Track locally-marked cards (prototype only — no backend)
  const [localCards, setLocalCards] = React.useState<EvidenceCard[]>(cards)

  React.useEffect(() => setLocalCards(cards), [cards])

  function openDrawer(card: EvidenceCard) {
    setDrawerCard(card)
    setDrawerOpen(true)
  }

  function markCheckedLocally(id: string) {
    setLocalCards((prev) =>
      prev.map((c) =>
        c.id === id
          ? { ...c, humanCheck: { name: "Anna Keller", timestamp: "gerade eben" } }
          : c
      )
    )
  }

  function handleDrawerMarkChecked(id: string) {
    markCheckedLocally(id)
    setDrawerOpen(false)
  }

  // Data-driven filter chips: only statuses that actually occur.
  const availableStatuses = Array.from(
    new Set(localCards.map((c) => MACHINE_TO_FILTER[c.machineStatus]))
  )

  const filtered = localCards.filter((c) => {
    if (filter === "all") return true
    // Mock cards always carry a readable Fundstelle, so "no_location" is empty.
    if (filter === "no_location") return false
    return MACHINE_TO_FILTER[c.machineStatus] === filter
  })

  const groups = groupCards(filtered, groupBy)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{EVIDENCE_VERIFIED_HINT}</span>
      </div>

      {/* Filters + Gruppierung */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <EvidenceFilterBar
          available={availableStatuses}
          showNoLocation={false}
          value={filter}
          onChange={setFilter}
        />
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Gruppieren nach</span>
          <Select value={groupBy} onValueChange={(v) => setGroupBy(v as GroupBy)}>
            <SelectTrigger className="h-9 w-44">
              <span className="truncate">{GROUP_BY_LABELS[groupBy]}</span>
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(GROUP_BY_LABELS) as GroupBy[]).map((g) => (
                <SelectItem key={g} value={g}>
                  {GROUP_BY_LABELS[g]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p role="status" className="py-10 text-center text-sm text-muted-foreground">
          {localCards.length === 0
            ? "Noch keine Belege. Belege entstehen, wenn Sie die Analyse starten."
            : "Keine Belege entsprechen dem aktuellen Filter."}
        </p>
      ) : (
        <div className="flex flex-col gap-8">
          {groups.map(({ key, items }) => (
            <section key={key} aria-labelledby={`group-${key}`}>
              <h3
                id={`group-${key}`}
                className="mb-3 text-sm font-semibold text-foreground"
              >
                {key}
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  ({items.length})
                </span>
              </h3>
              <div className="grid gap-3 lg:grid-cols-2">
                {items.map((card) => (
                  <EvidenceCardItem
                    key={card.id}
                    card={card}
                    onOpenDetails={() => openDrawer(card)}
                    onCorrect={() => openDrawer(card)}
                    onMarkChecked={markCheckedLocally}
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
        onMarkChecked={handleDrawerMarkChecked}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Grouping helper — preserves a sensible order per dimension.
// ---------------------------------------------------------------------------
function groupCards(
  cards: EvidenceCard[],
  groupBy: GroupBy
): { key: string; items: EvidenceCard[] }[] {
  const keyOf = (c: EvidenceCard): string => {
    if (groupBy === "source") return c.sourceTitle
    if (groupBy === "status") return MACHINE_STATUS_LABELS[c.machineStatus]
    return c.section
  }

  // Fixed order for known dimensions; otherwise first-seen order.
  let order: string[]
  if (groupBy === "section") {
    order = [...EVIDENCE_SECTIONS]
  } else if (groupBy === "status") {
    order = (["verified", "partial", "open", "blocker"] as MachineStatus[]).map(
      (s) => MACHINE_STATUS_LABELS[s]
    )
  } else {
    order = Array.from(new Set(cards.map(keyOf)))
  }

  const result: { key: string; items: EvidenceCard[] }[] = []
  for (const key of order) {
    const items = cards.filter((c) => keyOf(c) === key)
    if (items.length > 0) result.push({ key, items })
  }
  return result
}
