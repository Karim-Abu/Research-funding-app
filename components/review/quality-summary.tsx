"use client"

// Sichtbare Qualitätsprüfung der Belege (MAS reliability, M9K) im Review Center.
// Standardansicht: ein Status, höchstens drei konkrete Prüfpunkte in Klartext,
// genau eine Hauptaktion. Alle Kennzahlen und Fachbegriffe bleiben in den
// technischen Prüfinformationen erhalten (verlagert, nicht gelöscht).
// Deterministisch; keine Provider-/Modellnamen, keine Konfidenzprozente.

import * as React from "react"
import { ShieldCheck, AlertTriangle, Loader2, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  getReliability,
  runReliabilityPass,
  ReliabilityError,
  type ReliabilityViewDto,
} from "@/lib/reliability"
import {
  CHECKPOINT_SCOPE_NOTE,
  checkpointGroups,
  type CheckpointGroup,
} from "@/lib/reliability-view"

/** Höchstens drei Prüfpunkte in der Standardansicht; der Rest steht
 *  vollständig in den technischen Prüfinformationen. */
const VISIBLE_CHECKPOINTS = 3

// R2.5 — identische Meldungen werden gebündelt angezeigt («31 × …») statt als
// lange Wiederholungsliste; die Reihenfolge des ersten Auftretens bleibt.
function groupByDescription(
  findings: { finding_id: string; description: string }[]
): { description: string; count: number; key: string }[] {
  const order: string[] = []
  const counts = new Map<string, { count: number; key: string }>()
  for (const f of findings) {
    const entry = counts.get(f.description)
    if (entry) {
      entry.count += 1
    } else {
      counts.set(f.description, { count: 1, key: f.finding_id })
      order.push(f.description)
    }
  }
  return order.map((description) => ({
    description,
    count: counts.get(description)!.count,
    key: counts.get(description)!.key,
  }))
}

// Explains why the four metrics don't necessarily add up — not every claim
// requires evidence, and the categories track different check states.
const METRICS_LEGEND =
  "Nicht jede Aussage ist evidenzpflichtig; die Kategorien bilden unterschiedliche Prüfzustände ab. Die Zahlen müssen sich deshalb nicht zur Gesamtzahl aufsummieren."

export function QualitySummary({
  runId,
  onShowCheckpoints,
}: {
  runId: string
  /** Führt zur Aufgabenliste mit den betroffenen Stellen (Hauptaktion). */
  onShowCheckpoints: () => void
}) {
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
  const findings = view?.findings ?? []
  const stale = Boolean(view?.reliability_stale)
  const groups = checkpointGroups(findings)
  const visible = groups.slice(0, VISIBLE_CHECKPOINTS)
  const overflow = groups.slice(VISIBLE_CHECKPOINTS)
  const hasCritical = groups.some((g) => g.critical)

  return (
    <section
      data-testid="quality-summary"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <ShieldCheck className="size-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">
          Qualitätsprüfung: Belege
        </h3>
        {summary && (
          <Badge
            variant="outline"
            data-testid="quality-status"
            className={cn(
              "border-transparent",
              groups.length === 0
                ? "bg-status-fulfilled/12 text-status-fulfilled"
                : hasCritical
                  ? "bg-destructive/10 text-destructive"
                  : "bg-status-partial/12 text-status-partial"
            )}
          >
            {groups.length === 0 ? "Keine offenen Prüfpunkte" : "Prüfung erforderlich"}
          </Badge>
        )}
        {stale && (
          <Badge variant="outline" data-testid="reliability-stale">
            Veraltet – bitte erneut prüfen
          </Badge>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-status-incomplete">
          {error}
        </p>
      )}

      {!summary && !error && (
        <p className="text-sm text-muted-foreground">
          Die Belege dieses Entwurfs wurden noch nicht geprüft.
        </p>
      )}

      {summary && (
        <>
          {stale ? (
            <p className="text-sm text-foreground">
              Der Entwurf wurde nach der letzten Prüfung geändert. Bitte prüfen
              Sie ihn erneut, damit die Prüfpunkte wieder aktuell sind.
            </p>
          ) : groups.length === 0 ? (
            <p className="text-sm text-foreground">
              Alle geprüften Angaben haben einen ausreichenden Beleg. Prüfen Sie
              den Entwurf final.
            </p>
          ) : (
            <>
              <p className="text-sm text-foreground">
                {hasCritical
                  ? "Diese Punkte müssen vor dem Export geklärt werden:"
                  : "Vor dem Export sind noch Punkte zu prüfen:"}
              </p>
              <ul
                className="mt-2 flex flex-col gap-1.5"
                data-testid="quality-checkpoints"
              >
                {visible.map((group) => (
                  <CheckpointRow key={group.family} group={group} />
                ))}
              </ul>
              {overflow.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  … und {overflow.length} weitere{" "}
                  {overflow.length === 1 ? "Prüfpunkt" : "Prüfpunkte"} in den
                  technischen Prüfinformationen.
                </p>
              )}
            </>
          )}
        </>
      )}

      {/* Genau eine Hauptaktion: eine fehlende oder veraltete Prüfung wird
          zuerst aktualisiert, sonst führt die Karte zu den betroffenen
          Stellen. Ist alles belegt und aktuell, bleibt nichts zu tun. */}
      {(!summary || stale) && (
        <div className="mt-4">
          <Button type="button" size="sm" disabled={busy} onClick={runPass}>
            {busy ? (
              <>
                <Loader2 className="size-3.5 animate-spin" /> Prüfung läuft …
              </>
            ) : (
              <>
                <RefreshCw className="size-3.5" />
                {summary ? "Erneut prüfen" : "Belege jetzt prüfen"}
              </>
            )}
          </Button>
        </div>
      )}
      {summary && !stale && groups.length > 0 && (
        <div className="mt-4">
          <Button type="button" size="sm" onClick={onShowCheckpoints}>
            Prüfpunkte anzeigen
          </Button>
        </div>
      )}

      {summary && (
        <p className="mt-3 text-xs text-muted-foreground">
          {CHECKPOINT_SCOPE_NOTE}
        </p>
      )}

      {summary && (
        // Kennzahlen und Prüfbegriffe bleiben vollständig verfügbar (Audit,
        // Tests, Bachelorarbeit) — nur nicht in der Standardansicht.
        <details
          className="mt-2 text-xs text-muted-foreground"
          data-testid="quality-audit-details"
        >
          <summary className="cursor-pointer">Technische Prüfinformationen</summary>
          <p className="mt-1" data-testid="quality-metrics">
            {summary.claim_count} Aussagen geprüft — {summary.supported_claims}{" "}
            gestützt, {summary.review_required_count} mit Prüfbedarf,{" "}
            {summary.unsupported_claims} ohne verknüpften Beleg. Qualitätssignal:{" "}
            {summary.quality_flag === "risky" ? "Qualitätsrisiko" : "In Ordnung"}.
          </p>
          <p className="mt-1">{METRICS_LEGEND}</p>
          <p className="mt-1">
            Beleg-Suffizienzprüfung nach definierten Kriterien – kein Nachweis
            der inhaltlichen Wahrheit. Konfliktende Belege:{" "}
            {summary.conflicting_claims}. Falsches Konsensrisiko:{" "}
            {summary.false_consensus_risk_count}. Semantische Drift:{" "}
            {summary.semantic_drift_count}.
          </p>
          <p className="mt-1">
            Abdeckung (ein Beleg ist verknüpft) ist nicht dasselbe wie
            Suffizienz (der Beleg scheint die Aussage zu stützen).
          </p>
          {overflow.length > 0 && (
            <div className="mt-2" data-testid="quality-checkpoints-overflow">
              <p className="font-medium">Weitere Prüfpunkte</p>
              <ul className="mt-1 flex flex-col gap-1">
                {overflow.map((group) => (
                  <li key={group.family}>{group.text}</li>
                ))}
              </ul>
            </div>
          )}
          {findings.length > 0 && (
            <div className="mt-2" data-testid="quality-findings-verbatim">
              <p className="font-medium">Alle Meldungen im Wortlaut</p>
              <ul className="mt-1 flex flex-col gap-1">
                {groupByDescription(findings).map((g) => (
                  <li key={g.key}>
                    {g.count > 1 ? `${g.count} × ` : ""}
                    {g.description}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </details>
      )}
    </section>
  )
}

/** Ein Prüfpunkt: Klartextsatz, «kritisch» nur bei echter Export-Blockade. */
function CheckpointRow({ group }: { group: CheckpointGroup }) {
  return (
    <li className="flex items-start gap-2 text-sm text-foreground">
      {group.critical ? (
        <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
      ) : (
        <span
          aria-hidden
          className="mt-1.5 size-1.5 shrink-0 rounded-full bg-status-partial"
        />
      )}
      <span className="min-w-0 flex-1">{group.text}</span>
      {group.critical && (
        <Badge
          variant="outline"
          className="border-transparent bg-destructive/10 text-destructive"
        >
          kritisch
        </Badge>
      )}
    </li>
  )
}
