"use client"

import * as React from "react"
import {
  ChevronDown,
  ChevronRight,
  Info,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { EvidenceFilterBar } from "@/components/quellen/evidence-filter-bar"
import { cn } from "@/lib/utils"
import {
  listEvidence,
  VERIFICATION_LABELS,
  EVIDENCE_VERIFIED_HINT,
  REQUIREMENT_FALLBACK,
  REVIEWER_FALLBACK,
  formatFundstelle,
  hasPreciseLocation,
  formatReviewer,
  verificationToFilter,
  type EvidenceAnchorDto,
  type EvidenceFilter,
  type EvidenceStatusFilter,
  type VerificationStatus,
} from "@/lib/evidence"
import { listRequirements } from "@/lib/requirements"

const SOURCE_TYPE_LABEL: Record<string, string> = {
  pdf: "PDF",
  docx: "DOCX",
  txt: "Text",
  url: "URL",
}

// Colour + icon per verification status (green / orange / red). Labels stay in
// VERIFICATION_LABELS so the wording remains "Fundstelle bestätigt" etc.
const STATUS_STYLE: Record<
  VerificationStatus,
  { className: string; icon: typeof CheckCircle2 }
> = {
  exact_verified: {
    className: "bg-status-fulfilled/12 text-status-fulfilled",
    icon: CheckCircle2,
  },
  human_verified: {
    className: "bg-status-fulfilled/12 text-status-fulfilled",
    icon: CheckCircle2,
  },
  unverified: {
    className: "bg-status-partial/12 text-status-partial",
    icon: AlertTriangle,
  },
  rejected: {
    className: "bg-destructive/10 text-destructive",
    icon: XCircle,
  },
}

interface JoinedAnchor extends EvidenceAnchorDto {
  requirementTitle: string | null
}

interface LiveEvidenceProps {
  runId: string
  /** Deep link (?anchor=…): expand + scroll to this anchor after load. */
  focusAnchorId?: string | null
  /** When set, the source name becomes a button that opens the source detail. */
  onOpenSource?: (sourceId: string) => void
}

export function LiveEvidence({ runId, focusAnchorId, onOpenSource }: LiveEvidenceProps) {
  const [anchors, setAnchors] = React.useState<JoinedAnchor[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [filter, setFilter] = React.useState<EvidenceFilter>("all")
  const [expanded, setExpanded] = React.useState<string | null>(null)
  const [expandedTech, setExpandedTech] = React.useState<string | null>(null)

  // Requirement → evidence deep link: open the referenced card once loaded.
  React.useEffect(() => {
    if (!focusAnchorId || anchors === null) return
    if (!anchors.some((a) => a.anchor_id === focusAnchorId)) return
    setExpanded(focusAnchorId)
    document
      .getElementById(`evidence-${focusAnchorId}`)
      ?.scrollIntoView?.({ behavior: "smooth", block: "center" })
  }, [focusAnchorId, anchors])

  const load = React.useCallback(() => {
    setError(null)
    setAnchors(null)
    // Join listEvidence (anchors) with listRequirements.evidence_links so each
    // anchor can show its requirement context — the anchor API stays pure.
    Promise.all([listEvidence(runId), listRequirements(runId).catch(() => [])])
      .then(([evidence, assessments]) => {
        const anchorToTitle = new Map<string, string>()
        for (const a of assessments) {
          // No raw requirement_id as a title — fall back to a readable phrase.
          const title = a.title ?? REQUIREMENT_FALLBACK
          for (const link of a.evidence_links ?? []) {
            if (!anchorToTitle.has(link.anchor_id)) {
              anchorToTitle.set(link.anchor_id, title)
            }
          }
        }
        setAnchors(
          evidence.map((anchor) => ({
            ...anchor,
            requirementTitle: anchorToTitle.get(anchor.anchor_id) ?? null,
          }))
        )
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Belege konnten nicht geladen werden.")
      )
  }, [runId])

  React.useEffect(() => load(), [load])

  if (error) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" className="mt-4" onClick={load}>
          <RefreshCw data-icon="inline-start" />
          Erneut versuchen
        </Button>
      </div>
    )
  }

  if (anchors === null) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    )
  }

  const verifiedCount = anchors.filter(
    (a) => a.verification_status === "exact_verified"
  ).length

  // Data-driven filter chips: only show statuses / "ohne Fundstelle" that occur.
  const availableStatuses = Array.from(
    new Set(anchors.map((a) => verificationToFilter(a.verification_status)))
  ) as EvidenceStatusFilter[]
  const anyWithoutLocation = anchors.some((a) => !hasPreciseLocation(a))

  const visible = anchors.filter((a) => {
    if (filter === "all") return true
    if (filter === "no_location") return !hasPreciseLocation(a)
    return verificationToFilter(a.verification_status) === filter
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{EVIDENCE_VERIFIED_HINT}</span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <EvidenceFilterBar
          available={availableStatuses}
          showNoLocation={anyWithoutLocation}
          value={filter}
          onChange={setFilter}
        />
        <span className="text-xs text-muted-foreground">
          {verifiedCount} bestätigte Fundstelle(n)
        </span>
      </div>

      {visible.length === 0 ? (
        <p role="status" className="py-10 text-center text-sm text-muted-foreground">
          {anchors.length === 0
            ? "Noch keine Belege. Belege entstehen mit der deterministischen Analyse."
            : "Keine Belege entsprechen dem aktuellen Filter."}
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {visible.map((anchor) => {
            const isOpen = expanded === anchor.anchor_id
            const isTechOpen = expandedTech === anchor.anchor_id
            const style = STATUS_STYLE[anchor.verification_status]
            const StatusIcon = style.icon
            const reviewer = formatReviewer(
              anchor.human_checked_by,
              anchor.human_checked_at
            )
            const isUrlSource = anchor.source_type === "url"
            return (
              <li
                key={anchor.anchor_id}
                id={`evidence-${anchor.anchor_id}`}
                className={cn(
                  "rounded-lg border border-border bg-card px-5 py-4",
                  focusAnchorId === anchor.anchor_id && "ring-2 ring-primary/40"
                )}
              >
                {/* Header: source + Fundstelle + status */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-xs font-medium text-muted-foreground">
                      {onOpenSource ? (
                        <button
                          type="button"
                          onClick={() => onOpenSource(anchor.source_id)}
                          aria-label={`Quelle „${anchor.source_name}“ anzeigen`}
                          className="rounded underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {anchor.source_name}
                        </button>
                      ) : (
                        anchor.source_name
                      )}
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5">
                        {SOURCE_TYPE_LABEL[anchor.source_type] ?? anchor.source_type}
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatFundstelle(anchor)}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                      style.className
                    )}
                  >
                    <StatusIcon className="size-3.5" />
                    {VERIFICATION_LABELS[anchor.verification_status]}
                  </span>
                </div>

                {/* Aussage / Zitat */}
                <p className="mt-3 border-l-2 border-border pl-3 text-sm leading-relaxed text-foreground">
                  {anchor.quote}
                </p>

                {/* Zugeordnete Anforderung — always shown, with fallback */}
                <p className="mt-2 text-xs text-muted-foreground">
                  Anforderung: {anchor.requirementTitle ?? REQUIREMENT_FALLBACK}
                </p>

                {/* Prüferanzeige */}
                <p className="mt-1 text-xs text-muted-foreground">
                  {reviewer ?? REVIEWER_FALLBACK}
                </p>

                {/* Actions */}
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  {isUrlSource && (
                    <a
                      href={anchor.source_name}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Quelle öffnen
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => setExpanded(isOpen ? null : anchor.anchor_id)}
                    aria-expanded={isOpen}
                    className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
                  >
                    {isOpen ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    {isOpen ? "Details ausblenden" : "Details anzeigen"}
                  </button>
                </div>

                {isOpen && (
                  <div className="mt-2 flex flex-col gap-2">
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <dt>Quelle</dt>
                      <dd>{anchor.source_name}</dd>
                      <dt>Fundstelle</dt>
                      <dd>{formatFundstelle(anchor)}</dd>
                    </dl>
                    {/* Technische Details — backend/normalizer internals only here */}
                    <div>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedTech(isTechOpen ? null : anchor.anchor_id)
                        }
                        aria-expanded={isTechOpen}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      >
                        {isTechOpen ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                        Technische Details
                      </button>
                      {isTechOpen && (
                        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <dt>Normalizer</dt>
                          <dd>{anchor.normalizer_version}</dd>
                          {anchor.start_offset != null && (
                            <>
                              <dt>Position</dt>
                              <dd>
                                {anchor.start_offset}–{anchor.end_offset}
                              </dd>
                            </>
                          )}
                          <dt>Quell-ID</dt>
                          <dd className="font-mono break-all">{anchor.source_id}</dd>
                          <dt>Fragment-ID</dt>
                          <dd className="font-mono break-all">{anchor.fragment_id}</dd>
                          {anchor.match_type && (
                            <>
                              <dt>Treffer-Typ</dt>
                              <dd>{anchor.match_type}</dd>
                            </>
                          )}
                        </dl>
                      )}
                    </div>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
