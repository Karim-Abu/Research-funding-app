"use client"

import * as React from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  FileJson,
  FileText,
  FileType2,
  Loader2,
  RotateCcw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { FeedbackDialog } from "@/components/export/feedback-dialog"
import { cn } from "@/lib/utils"
import {
  EXPORT_CARDS,
  KIND_LABEL,
  PAGE_SCENARIOS,
  PRIOR_EXPORTS,
  type ApprovalBannerState,
  type ExportCard,
  type ExportCardStatus,
  type ExportKind,
  type PageScenario,
  type PriorExport,
} from "@/lib/export-mock-data"
import {
  createExport,
  exportDownloadUrl,
  USE_MOCKS,
  CURRENT_RUN_ID,
} from "@/lib/api"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function kindIcon(kind: ExportKind, className?: string) {
  const cls = cn("shrink-0", className)
  if (kind === "word") return <FileType2 className={cls} />
  if (kind === "markdown") return <FileText className={cls} />
  return <FileJson className={cls} />
}

// ---------------------------------------------------------------------------
// Approval banner
// ---------------------------------------------------------------------------

function ApprovalBanner({ state }: { state: ApprovalBannerState }) {
  if (state === "approved") {
    return (
      <div
        role="status"
        className="flex items-center gap-2.5 rounded-md border border-human/30 bg-human/8 px-4 py-3"
      >
        <CheckCircle2 className="size-4 shrink-0 text-human" />
        <p className="text-sm text-foreground">
          <span className="font-medium text-human">Review freigegeben</span>
          {" durch Anna Keller am 12. Juni — "}
          <span className="text-muted-foreground">
            Dies ist keine Einreichfreigabe.
          </span>
        </p>
      </div>
    )
  }

  if (state === "stale") {
    return (
      <div
        role="status"
        className="flex items-center gap-2.5 rounded-md border border-status-partial/30 bg-status-partial/8 px-4 py-3"
      >
        <AlertTriangle className="size-4 shrink-0 text-status-partial" />
        <p className="text-sm text-foreground">
          <span className="font-medium text-status-partial">
            Freigabe veraltet — seitdem geändert.
          </span>{" "}
          Exporte werden als Entwurf gekennzeichnet.
        </p>
      </div>
    )
  }

  // not_approved
  return (
    <div
      role="status"
      className="flex items-center gap-2.5 rounded-md border border-border bg-muted/40 px-4 py-3"
    >
      <Clock className="size-4 shrink-0 text-muted-foreground" />
      <p className="text-sm text-foreground">
        Noch nicht freigegeben — Exporte werden als Entwurf gekennzeichnet.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Export card
// ---------------------------------------------------------------------------

interface ExportCardProps {
  card: ExportCard
  approvalState: ApprovalBannerState
  disabled: boolean
  onGenerate: (id: string) => void
  onDownload: (id: string) => void
  onRetry: (id: string) => void
}

function ExportCardItem({
  card,
  approvalState,
  disabled,
  onGenerate,
  onDownload,
  onRetry,
}: ExportCardProps) {
  const isDraft = approvalState !== "approved"
  const isLeading = card.leading

  return (
    <div
      className={cn(
        "flex flex-1 flex-col gap-4 rounded-lg border bg-card p-5",
        isLeading
          ? "border-foreground/20 shadow-sm ring-1 ring-foreground/10"
          : "border-border"
      )}
    >
      {/* Icon + title */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-md border",
            isLeading
              ? "border-foreground/15 bg-foreground/5"
              : "border-border bg-muted/40"
          )}
        >
          {kindIcon(card.kind, "size-5 text-foreground")}
        </div>
        <div className="flex flex-col gap-0.5">
          <h3 className="text-sm font-semibold leading-snug text-foreground">
            {card.title}
          </h3>
          <p className="text-xs text-muted-foreground">{card.subtitle}</p>
        </div>
      </div>

      {/* ENTWURF tag */}
      {isDraft && (
        <span className="inline-flex w-fit items-center rounded border border-status-partial/40 bg-status-partial/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-status-partial">
          Entwurf
        </span>
      )}

      {/* Status */}
      <div className="flex-1">
        {card.status === "generating" && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Wird erstellt…
          </div>
        )}
        {card.status === "error" && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-status-blocker">
              Export fehlgeschlagen. Bitte erneut versuchen.
            </p>
          </div>
        )}
      </div>

      {/* Action button */}
      <div className="mt-auto">
        {disabled ? (
          <span
            role="button"
            aria-disabled="true"
            className="inline-flex h-9 w-full cursor-not-allowed select-none items-center justify-center rounded-md border border-border bg-muted px-4 text-sm font-medium text-muted-foreground opacity-60"
          >
            Erstellen
          </span>
        ) : card.status === "error" ? (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => onRetry(card.id)}
          >
            <RotateCcw className="mr-1.5 size-4" />
            Erneut versuchen
          </Button>
        ) : card.status === "generating" ? (
          <Button disabled className="w-full cursor-not-allowed opacity-60">
            <Loader2 className="mr-1.5 size-4 animate-spin" />
            Wird erstellt…
          </Button>
        ) : card.status === "ready" ? (
          // After generation, show Download; before first generation show Erstellen
          isLeading ? (
            <Button className="w-full" onClick={() => onGenerate(card.id)}>
              Erstellen
            </Button>
          ) : (
            <Button
              variant="outline"
              className="w-full"
              onClick={() => onGenerate(card.id)}
            >
              Erstellen
            </Button>
          )
        ) : null}
      </div>
    </div>
  )
}

// Download button variant after a card has been generated
function ExportCardDownloadItem({
  card,
  approvalState,
  onDownload,
}: {
  card: ExportCard
  approvalState: ApprovalBannerState
  onDownload: (id: string) => void
}) {
  const isDraft = approvalState !== "approved"
  const isLeading = card.leading

  return (
    <div
      className={cn(
        "flex flex-1 flex-col gap-4 rounded-lg border bg-card p-5",
        isLeading
          ? "border-foreground/20 shadow-sm ring-1 ring-foreground/10"
          : "border-border"
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-md border",
            isLeading
              ? "border-foreground/15 bg-foreground/5"
              : "border-border bg-muted/40"
          )}
        >
          {kindIcon(card.kind, "size-5 text-foreground")}
        </div>
        <div className="flex flex-col gap-0.5">
          <h3 className="text-sm font-semibold leading-snug text-foreground">
            {card.title}
          </h3>
          <p className="text-xs text-muted-foreground">{card.subtitle}</p>
        </div>
      </div>

      {isDraft && (
        <span className="inline-flex w-fit items-center rounded border border-status-partial/40 bg-status-partial/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-status-partial">
          Entwurf
        </span>
      )}

      <div className="flex-1">
        <div className="flex items-center gap-1.5 text-sm text-foreground">
          <CheckCircle2 className="size-4 text-muted-foreground" />
          Download verfügbar
        </div>
      </div>

      <div className="mt-auto">
        {isLeading ? (
          <Button className="w-full" onClick={() => onDownload(card.id)}>
            <Download className="mr-1.5 size-4" />
            Herunterladen
          </Button>
        ) : (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => onDownload(card.id)}
          >
            <Download className="mr-1.5 size-4" />
            Herunterladen
          </Button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Prior exports list
// ---------------------------------------------------------------------------

function PriorExportsList({
  exports,
  approvalState,
}: {
  exports: PriorExport[]
  approvalState: ApprovalBannerState
}) {
  if (exports.length === 0) return null

  return (
    <section aria-labelledby="prior-exports-heading">
      <h2
        id="prior-exports-heading"
        className="mb-3 text-sm font-semibold text-foreground"
      >
        Letzte Exporte
      </h2>
      <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-card">
        {exports.slice(0, 5).map((ex) => {
          // A row is a draft if the current session is not approved/stale,
          // or if the file itself was originally exported as a draft.
          const showDraftTag = ex.isDraft || approvalState !== "approved"
          return (
            <li
              key={ex.id}
              className="flex min-h-[44px] items-center gap-3 px-4 py-3"
            >
              {kindIcon(ex.kind, "size-4 text-muted-foreground")}
              <span className="flex-1 truncate text-sm text-foreground">
                {ex.filename}
              </span>
              {showDraftTag && (
                <span className="shrink-0 rounded border border-status-partial/40 bg-status-partial/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-status-partial">
                  Entwurf
                </span>
              )}
              <span className="shrink-0 text-xs text-muted-foreground">
                {KIND_LABEL[ex.kind]}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {ex.timestamp}
              </span>
              <button
                type="button"
                aria-label={`${ex.filename} herunterladen`}
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded text-muted-foreground",
                  "transition-colors hover:bg-accent hover:text-foreground",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                )}
              >
                <Download className="size-4" />
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-6 px-6 py-8">
      <Skeleton className="h-12 w-full rounded-md" />
      <div className="grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-col gap-3 rounded-lg border border-border p-5">
            <div className="flex items-start gap-3">
              <Skeleton className="size-10 rounded-md" />
              <div className="flex flex-col gap-1.5 flex-1">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
            <Skeleton className="h-9 w-full rounded-md mt-auto" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

// Mock-Downloads: echte Dateien mit ENTWURF-Kennzeichnung (Dummy-Inhalt).
// Im Real-Modus liefert die Bridge das Binary über /api/runs/{id}/export.
const MOCK_DOWNLOADS: Record<
  ExportKind,
  { filename: string; mime: string; body: string }
> = {
  word: {
    filename: "KI-Materialentwicklung_Antrag_ENTWURF_Platzhalter.txt",
    mime: "text/plain;charset=utf-8",
    body: "ENTWURF — nicht eingereicht (Dummy)\n\nWord-Arbeitsdokument: Platzhalter aus dem Demo-Modus. Die Einreichung erfolgt durch Sie im Innosuisse-Portal.",
  },
  markdown: {
    filename: "KI-Materialentwicklung_Zusammenfassung_ENTWURF.md",
    mime: "text/markdown;charset=utf-8",
    body: "# Antrag — ENTWURF (Dummy)\n\nMarkdown-Zusammenfassung aus dem Demo-Modus. Nicht eingereicht.",
  },
  json_audit: {
    filename: "KI-Materialentwicklung_Nachweis_ENTWURF.json",
    mime: "application/json",
    body: JSON.stringify({ entwurf: true, dummy: true, hinweis: "Demo-Modus" }, null, 2),
  },
}

type LocalCardState = "idle" | "generating" | "ready" | "error"

export interface ExportScreenProps {
  scenario?: PageScenario
  /** Offene, nicht überschriebene Blocker-Issues (Gating). */
  openBlockerCount?: number
}

export function ExportScreen({
  scenario = "default",
  openBlockerCount = 0,
}: ExportScreenProps) {
  // Derive approval banner state from scenario
  const approvalState: ApprovalBannerState =
    scenario === "approved"
      ? "approved"
      : scenario === "stale"
        ? "stale"
        : "not_approved"

  const nothingToExport = scenario === "nothing_to_export"
  const blocked = openBlockerCount > 0

  const [cardStates, setCardStates] = React.useState<
    Record<string, LocalCardState>
  >({})
  const [feedbackOpen, setFeedbackOpen] = React.useState(false)

  function setCardState(id: string, state: LocalCardState) {
    setCardStates((prev) => ({ ...prev, [id]: state }))
  }

  // Build card state: scenario overrides (debug) > local API-driven state
  const cards: ExportCard[] = EXPORT_CARDS.map((c) => {
    if (scenario === "generating" && c.id === "word") {
      return { ...c, status: "generating" as ExportCardStatus }
    }
    if (scenario === "error" && c.id === "word") {
      return { ...c, status: "error" as ExportCardStatus }
    }
    const local = cardStates[c.id]
    if (local === "generating") {
      return { ...c, status: "generating" as ExportCardStatus }
    }
    if (local === "error") {
      return { ...c, status: "error" as ExportCardStatus }
    }
    return c
  })

  async function handleGenerate(id: string) {
    const card = EXPORT_CARDS.find((c) => c.id === id)
    if (!card || blocked) return
    setCardState(id, "generating")
    try {
      await createExport(card.kind)
      setCardState(id, "ready")
    } catch {
      setCardState(id, "error")
    }
  }

  function handleDownload(id: string) {
    const card = EXPORT_CARDS.find((c) => c.id === id)
    if (!card) return
    const a = document.createElement("a")
    if (USE_MOCKS) {
      const download = MOCK_DOWNLOADS[card.kind]
      const blob = new Blob([download.body], { type: download.mime })
      a.href = URL.createObjectURL(blob)
      a.download = download.filename
    } else {
      a.href = exportDownloadUrl(CURRENT_RUN_ID, card.kind)
    }
    document.body.appendChild(a)
    a.click()
    a.remove()
    if (USE_MOCKS) {
      // Deferred: revoking synchronously can cancel the download.
      const blobUrl = a.href
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
    }
  }

  function handleRetry(id: string) {
    void handleGenerate(id)
  }

  return (
    <div className="flex min-h-full flex-col gap-8 px-6 py-8">
      {/* Page header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-foreground">Export</h1>
        <p className="text-sm text-muted-foreground">
          Exportieren Sie Arbeitsdokumente für die Weiterarbeit und den Übertrag ins Innosuisse-Portal.
        </p>
      </div>

      {/* Approval banner */}
      <ApprovalBanner state={approvalState} />

      {/* Nothing to export state */}
      {nothingToExport ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <FileText className="size-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">
            Es gibt noch keine Inhalte zu exportieren.
          </p>
          <p className="text-xs text-muted-foreground">
            Schliessen Sie zuerst die vorherigen Schritte ab.
          </p>
        </div>
      ) : (
        <>
          {/* Blocker gating — export only after blockers are decided */}
          {blocked && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-status-blocker/30 bg-status-blocker/5 px-4 py-3"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-blocker" />
              <p className="text-sm text-foreground">
                {`Export nicht möglich: ${openBlockerCount} blockierende ${openBlockerCount === 1 ? "Punkt" : "Punkte"} offen — im Review entscheiden.`}
              </p>
            </div>
          )}

          {/* Export cards — 3 columns */}
          <section aria-labelledby="export-cards-heading">
            <h2 id="export-cards-heading" className="sr-only">
              Exportformate
            </h2>
            <div className="grid grid-cols-3 gap-4">
              {cards.map((card) =>
                cardStates[card.id] === "ready" ? (
                  <ExportCardDownloadItem
                    key={card.id}
                    card={card}
                    approvalState={approvalState}
                    onDownload={handleDownload}
                  />
                ) : (
                  <ExportCardItem
                    key={card.id}
                    card={card}
                    approvalState={approvalState}
                    disabled={blocked}
                    onGenerate={handleGenerate}
                    onDownload={handleDownload}
                    onRetry={handleRetry}
                  />
                )
              )}
            </div>
          </section>

          {/* Prior exports */}
          <PriorExportsList exports={PRIOR_EXPORTS} approvalState={approvalState} />
        </>
      )}

      {/* Sticky bottom disclaimer — stays in flow inside the scrollable main */}
      <div className="sticky bottom-0 -mx-6 mt-auto border-t border-border bg-background/95 px-6 py-4 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-muted-foreground">
            Die Einreichung erfolgt durch Sie im Innosuisse-Portal. Diese Plattform reicht nichts automatisch ein.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={() => setFeedbackOpen(true)}
          >
            Beta-Feedback geben
          </Button>
        </div>
      </div>

      <FeedbackDialog open={feedbackOpen} onOpenChange={setFeedbackOpen} />
    </div>
  )
}
