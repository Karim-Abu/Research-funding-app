"use client"

// Read-only "Qualitätsübersicht" (MAS reliability, M9K) for the Review Center. Shows how
// many claims are supported / need review / are unsupported and lists reliability findings.
// Deterministic; no provider/model names, no confidence percentages.

import * as React from "react"
import { ShieldCheck, AlertTriangle, Loader2, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  getReliability,
  runReliabilityPass,
  ReliabilityError,
  type ReliabilityViewDto,
} from "@/lib/reliability"

const FLAG_LABEL: Record<string, string> = { ok: "In Ordnung", risky: "Qualitätsrisiko" }

// Explains why the four metrics don't necessarily add up — not every claim
// requires evidence, and the categories track different check states.
const METRICS_LEGEND =
  "Nicht jede Aussage ist evidenzpflichtig; die Kategorien bilden unterschiedliche Prüfzustände ab. Die Zahlen müssen sich deshalb nicht zur Gesamtzahl aufsummieren."

export function QualitySummary({ runId }: { runId: string }) {
  const [view, setView] = React.useState<ReliabilityViewDto | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const load = React.useCallback(async () => {
    try {
      setView(await getReliability(runId))
    } catch (err) {
      setError(err instanceof ReliabilityError ? err.message : "Fehler beim Laden.")
    }
  }, [runId])

  React.useEffect(() => {
    void load()
  }, [load])

  const runPass = React.useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await runReliabilityPass(runId)
      await load()
    } catch (err) {
      setError(
        err instanceof ReliabilityError ? err.message : "Prüfung fehlgeschlagen."
      )
    } finally {
      setBusy(false)
    }
  }, [runId, load])

  const summary = view?.summary ?? null
  const blockers = (view?.findings ?? []).filter((f) => f.severity === "blocker")
  const warnings = (view?.findings ?? []).filter((f) => f.severity === "warning")

  return (
    <section
      data-testid="quality-summary"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Qualitätsübersicht</h3>
          {summary && (
            <Badge variant={summary.quality_flag === "risky" ? "destructive" : "secondary"}>
              {FLAG_LABEL[summary.quality_flag] ?? summary.quality_flag}
            </Badge>
          )}
          {view?.reliability_stale && (
            <Badge variant="outline" data-testid="reliability-stale">
              Veraltet – bitte erneut prüfen
            </Badge>
          )}
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={runPass}>
          {busy ? (
            <>
              <Loader2 className="size-3.5 animate-spin" /> Prüfung läuft …
            </>
          ) : (
            <>
              <RefreshCw className="size-3.5" /> Zuverlässigkeit prüfen
            </>
          )}
        </Button>
      </div>

      {error && (
        <p role="alert" className="text-sm text-status-incomplete">
          {error}
        </p>
      )}

      {!summary && !error && (
        <p className="text-sm text-muted-foreground">
          Noch keine Zuverlässigkeitsprüfung ausgeführt.
        </p>
      )}

      {summary && (
        <>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="quality-metrics">
            <Metric label="Aussagen" value={summary.claim_count} />
            <Metric label="Belegt" value={summary.supported_claims} />
            <Metric label="Zu prüfen" value={summary.review_required_count} />
            <Metric label="Nicht belegt" value={summary.unsupported_claims} />
          </dl>
          <p className="mt-2 text-xs text-muted-foreground">{METRICS_LEGEND}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Beleg-Suffizienzprüfung nach definierten Kriterien – kein Nachweis der inhaltlichen
            Wahrheit. Konfliktende Belege: {summary.conflicting_claims}. Falsches Konsensrisiko:{" "}
            {summary.false_consensus_risk_count}. Semantische Drift: {summary.semantic_drift_count}.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Abdeckung (ein Beleg ist verknüpft) ist nicht dasselbe wie Suffizienz (der Beleg
            scheint die Aussage zu stützen). «Qualitätsrisiko» ist ein Risikosignal für die
            menschliche Prüfung — kein Fehler der Anwendung und keine Aussage zur
            Förderwahrscheinlichkeit.
          </p>

          {blockers.length > 0 && (
            <div className="mt-3" data-testid="reliability-blockers">
              <p className="mb-1 flex items-center gap-1 text-sm font-medium text-foreground">
                <AlertTriangle className="size-4 text-destructive" /> Zuverlässigkeits-Blocker
              </p>
              <ul className="flex flex-col gap-1">
                {blockers.map((f) => (
                  <li key={f.finding_id} className="text-xs text-foreground">
                    {f.description}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="mt-3" data-testid="reliability-warnings">
              <p className="mb-1 text-sm font-medium text-foreground">Hinweise (Prüfung nötig)</p>
              <ul className="flex flex-col gap-1">
                {warnings.map((f) => (
                  <li key={f.finding_id} className="text-xs text-muted-foreground">
                    {f.description}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-background p-2 text-center">
      <div className="text-lg font-semibold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  )
}
