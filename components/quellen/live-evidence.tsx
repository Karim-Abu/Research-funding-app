"use client"

import * as React from "react"
import { ChevronDown, ChevronRight, Info, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import {
  listEvidence,
  VERIFICATION_LABELS,
  VERIFIED_EXPLANATION,
  type EvidenceAnchorDto,
  type VerificationStatus,
} from "@/lib/evidence"
import { listRequirements } from "@/lib/requirements"

const SOURCE_TYPE_LABEL: Record<string, string> = {
  pdf: "PDF",
  docx: "DOCX",
  txt: "Text",
  url: "URL",
}

const STATUS_VARIANT: Record<
  VerificationStatus,
  "default" | "secondary" | "outline" | "destructive"
> = {
  exact_verified: "default",
  unverified: "outline",
  rejected: "destructive",
  human_verified: "secondary", // never rendered in M5
}

// Verification statuses surfaced in M5 (human_verified is never produced).
const FILTERABLE: VerificationStatus[] = ["exact_verified", "unverified", "rejected"]

interface JoinedAnchor extends EvidenceAnchorDto {
  requirementTitle: string | null
}

function fundstelle(anchor: EvidenceAnchorDto): string {
  const parts: string[] = []
  if (anchor.page != null) parts.push(`S. ${anchor.page}`)
  if (anchor.section) parts.push(anchor.section)
  return parts.join(", ")
}

export function LiveEvidence({ runId }: { runId: string }) {
  const [anchors, setAnchors] = React.useState<JoinedAnchor[] | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [statusFilter, setStatusFilter] = React.useState<VerificationStatus | "all">(
    "all"
  )
  const [expanded, setExpanded] = React.useState<string | null>(null)
  const [expandedTech, setExpandedTech] = React.useState<string | null>(null)

  const load = React.useCallback(() => {
    setError(null)
    setAnchors(null)
    // Join listEvidence (anchors) with listRequirements.evidence_links so each
    // anchor can show its requirement context — the anchor API stays pure.
    Promise.all([listEvidence(runId), listRequirements(runId).catch(() => [])])
      .then(([evidence, assessments]) => {
        const anchorToTitle = new Map<string, string>()
        for (const a of assessments) {
          const title = a.title ?? "Keine zugeordnete Anforderung"
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
  const visible = anchors.filter(
    (a) => statusFilter === "all" || a.verification_status === statusFilter
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{VERIFIED_EXPLANATION}</span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as VerificationStatus | "all")}
        >
          <SelectTrigger className="h-9 w-56">
            <span className="truncate">
              {statusFilter === "all"
                ? "Alle Verifikationsstatus"
                : VERIFICATION_LABELS[statusFilter]}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Verifikationsstatus</SelectItem>
            {FILTERABLE.map((s) => (
              <SelectItem key={s} value={s}>
                {VERIFICATION_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
            return (
              <li
                key={anchor.anchor_id}
                className="rounded-lg border border-border bg-card px-5 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-xs font-medium text-muted-foreground">
                      {anchor.source_name}
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5">
                        {SOURCE_TYPE_LABEL[anchor.source_type] ?? anchor.source_type}
                      </span>
                    </span>
                    {fundstelle(anchor) && (
                      <span className="text-xs text-muted-foreground">
                        {fundstelle(anchor)}
                      </span>
                    )}
                  </div>
                  <Badge variant={STATUS_VARIANT[anchor.verification_status]}>
                    {VERIFICATION_LABELS[anchor.verification_status]}
                  </Badge>
                </div>

                <p className="mt-3 border-l-2 border-border pl-3 text-sm leading-relaxed text-foreground">
                  {anchor.quote}
                </p>

                {anchor.requirementTitle && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Anforderung: {anchor.requirementTitle}
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : anchor.anchor_id)}
                  aria-expanded={isOpen}
                  className="mt-3 flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
                >
                  {isOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  Details
                </button>
                {isOpen && (
                  <div className="mt-2 flex flex-col gap-2">
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <dt>Quelle</dt>
                      <dd>{anchor.source_name}</dd>
                    </dl>
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
