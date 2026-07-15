"use client"

import * as React from "react"
import {
  CheckCircle2,
  Loader2,
  AlertTriangle,
  MinusCircle,
  OctagonX,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { AnalysisProgressStep } from "@/lib/quellen-mock-data"
import type { RunPhaseView } from "@/lib/run-steps"
import type { RunCostDto } from "@/lib/backend-contract"

// ---------------------------------------------------------------------------
// Running-analysis banner with plain-language progress steps
// ---------------------------------------------------------------------------

interface AnalysisProgressBannerProps {
  steps: AnalysisProgressStep[]
  /** Persistierte Backend-Phasen (Live-Pfad) — hat Vorrang vor steps. */
  phases?: RunPhaseView[]
  /** Laufende Kosten aus den Run-Daten (kein Dummy). */
  cost?: RunCostDto
  /** Called when the user clicks "Analyse abbrechen" */
  onStop?: () => void
}

export function AnalysisProgressBanner({
  steps,
  phases,
  cost,
  onStop,
}: AnalysisProgressBannerProps) {
  const runningPhase = phases?.find((p) => p.state === "running")
  const runningStep = phases ? undefined : steps.find((s) => s.state === "running")
  const runningLabel = runningPhase?.label ?? runningStep?.label

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-lg border border-border bg-muted/40 px-5 py-4"
    >
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 shrink-0 animate-spin text-foreground" />
          <span className="text-sm font-medium text-foreground">
            Analyse läuft
            {runningLabel ? (
              <span className="ml-1 font-normal text-muted-foreground">
                — {runningLabel}…
              </span>
            ) : null}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {cost && (
            <span className="text-xs text-muted-foreground">
              {`~CHF ${cost.usedChf.toFixed(2)} von CHF ${cost.limitChf.toFixed(2)}`}
            </span>
          )}
          {onStop && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onStop}
              className="h-8 px-3 text-xs"
            >
              Analyse abbrechen
            </Button>
          )}
        </div>
      </div>

      {phases ? (
        <ol className="flex flex-col gap-1.5">
          {phases.map((phase) => (
            <li key={phase.key} className="flex items-start gap-1.5">
              <PhaseIcon state={phase.state} />
              <span className="flex flex-col">
                <span
                  className={cn(
                    "text-xs",
                    phase.state === "done"
                      ? "text-muted-foreground"
                      : phase.state === "running"
                        ? "font-medium text-foreground"
                        : phase.state === "failed"
                          ? "font-medium text-foreground"
                          : "text-muted-foreground"
                  )}
                >
                  {phase.label}
                  {phase.state === "running" ? "…" : ""}
                  {(phase.info || phase.durationSeconds !== undefined) && (
                    <span className="ml-1 font-normal text-muted-foreground">
                      {phase.info ? `— ${phase.info}` : ""}
                      {phase.durationSeconds !== undefined
                        ? ` (${phase.durationSeconds} s)`
                        : ""}
                    </span>
                  )}
                </span>
                {phase.error && (
                  <span className="text-xs text-destructive">{phase.error}</span>
                )}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <ol className="flex flex-col gap-1.5 sm:flex-row sm:flex-wrap sm:gap-x-6 sm:gap-y-1">
          {steps.map((step) => (
            <li key={step.id} className="flex items-center gap-1.5">
              <ProgressStepIcon state={step.state} />
              <span
                className={cn(
                  "text-xs",
                  step.state === "done"
                    ? "text-muted-foreground line-through decoration-muted-foreground/50"
                    : step.state === "running"
                      ? "font-medium text-foreground"
                      : "text-muted-foreground"
                )}
              >
                {step.label}
                {step.state === "running" ? "…" : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function ProgressStepIcon({ state }: { state: AnalysisProgressStep["state"] }) {
  if (state === "done")
    return <CheckCircle2 className="size-3.5 shrink-0 text-muted-foreground" />
  if (state === "running")
    return <Loader2 className="size-3.5 shrink-0 animate-spin text-foreground" />
  return (
    <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/50" />
  )
}

function PhaseIcon({ state }: { state: RunPhaseView["state"] }) {
  if (state === "done")
    return (
      <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-status-fulfilled" />
    )
  if (state === "running")
    return (
      <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-foreground" />
    )
  if (state === "failed")
    return <OctagonX className="mt-0.5 size-3.5 shrink-0 text-destructive" />
  if (state === "skipped")
    return (
      <MinusCircle className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/60" />
    )
  return (
    <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/50" />
  )
}

// ---------------------------------------------------------------------------
// Stopped-analysis banner
// ---------------------------------------------------------------------------

interface StoppedAnalysisBannerProps {
  /** Fortsetzen-Button nur, wenn das Backend resume erlaubt. */
  canResume?: boolean
  onResume?: () => void
}

export function StoppedAnalysisBanner({
  canResume = false,
  onResume,
}: StoppedAnalysisBannerProps) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-5 py-4"
    >
      <div className="flex items-start gap-2">
        <OctagonX className="mt-0.5 size-4 shrink-0 text-status-partial" />
        <p className="text-sm text-foreground">
          Durchlauf gestoppt: Kostenlimit erreicht. Bisherige Ergebnisse sind
          gespeichert.
        </p>
      </div>
      {canResume && onResume && (
        <Button variant="outline" size="sm" onClick={onResume}>
          Analyse fortsetzen
        </Button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Completed-analysis banner
// ---------------------------------------------------------------------------

interface CompletedAnalysisBannerProps {
  /** Called when the user clicks "Zu den Anforderungen" */
  onGoToRequirements?: () => void
  /** Called when the user clicks "Belege ansehen" */
  onShowEvidence?: () => void
  /** Label der fehlgeschlagenen Phase — macht aus «abgeschlossen» ehrlich
   *  «teilweise abgeschlossen» (z. B. Kritik fehlgeschlagen). */
  partialPhaseLabel?: string | null
  /** Ruhiger Hinweis zum Live-Ausführungsstatus (z. B. partial_live) —
   *  siehe lib/runs.ts::liveStatusNotice; null = kein Hinweis nötig. */
  liveNotice?: string | null
}

export function CompletedAnalysisBanner({
  onGoToRequirements,
  onShowEvidence,
  partialPhaseLabel,
  liveNotice,
}: CompletedAnalysisBannerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-5 py-4"
    >
      <div className="flex items-start gap-2">
        {partialPhaseLabel || liveNotice ? (
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-partial" />
        ) : (
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-status-fulfilled" />
        )}
        <div className="flex flex-col gap-1">
          <p className="text-sm text-foreground">
            {partialPhaseLabel
              ? `Analyse teilweise abgeschlossen — «${partialPhaseLabel}» ist fehlgeschlagen. Die erstellten Prüfergebnisse und Feldvorschläge bleiben erhalten.`
              : "Analyse abgeschlossen. Öffnen Sie Anforderungen und Evidenz für die Ergebnisse."}
          </p>
          {liveNotice && (
            <p className="text-sm text-foreground">{liveNotice}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {onShowEvidence && (
          <Button variant="ghost" size="sm" onClick={onShowEvidence}>
            Belege ansehen
          </Button>
        )}
        {onGoToRequirements && (
          <Button size="sm" onClick={onGoToRequirements}>
            Zu den Anforderungen
          </Button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Local-only confidentiality banner
// ---------------------------------------------------------------------------

export function LocalOnlyBanner() {
  return (
    <div
      role="note"
      className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3"
    >
      <AlertTriangle className="size-4 shrink-0 text-muted-foreground" />
      <p className="text-xs text-muted-foreground">
        Für diese Datenklasse ist kein freigegebener KI-Provider konfiguriert.
        Die Analyse bleibt regelbasiert; Inhalte verlassen Ihre Umgebung nicht.
      </p>
    </div>
  )
}
