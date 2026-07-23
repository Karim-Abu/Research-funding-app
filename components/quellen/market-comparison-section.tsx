"use client"

// "Markt- und Konkurrenzvergleich" — M9I-B. Built only from imported public sources.
// Every shown item is source-backed (verified quote) or marked needs-review /
// insufficient-evidence. No draft is changed; no provider/model/confidence is shown.

import * as React from "react"
import { BarChart3, Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { pollOperation } from "@/lib/operations"
import {
  createComparison,
  getLatestComparison,
  MarketComparisonError,
  updateItemStatus,
  COMPARISON_STATUS_LABELS,
  ITEM_CATEGORY_LABELS,
  ITEM_RELATION_LABELS,
  ITEM_STATUS_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  SUMMARY_SECTIONS,
  CENTRALIZATION_LABELS,
  SUPPORT_STATUS_LABELS,
  type ItemStatus,
  type SupportStatus,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
} from "@/lib/market-comparison"

type State = "loading" | "idle" | "generating" | "ready" | "error"

export function MarketComparisonSection({
  projectId,
  sourceNames,
  disabledReason,
}: {
  projectId: string
  // Anzeigenamen der Projektquellen (source_id → Name) für den Abschnitt
  // «Verwendete Quellen» — es werden nie rohe IDs angezeigt.
  sourceNames?: Record<string, string>
  /** Konkreter Grund, warum aktuell kein Vergleich erstellt werden kann —
   *  deaktiviert «Vergleich erstellen» sichtbar statt still. */
  disabledReason?: string | null
}) {
  const [state, setState] = React.useState<State>("loading")
  const [comparison, setComparison] = React.useState<MarketComparisonDto | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const pollRef = React.useRef<{ stop: () => void } | null>(null)

  const load = React.useCallback(async () => {
    try {
      const latest = await getLatestComparison(projectId)
      setComparison(latest)
      setState(latest ? "ready" : "idle")
    } catch {
      setState("idle")
    }
  }, [projectId])

  React.useEffect(() => {
    void load()
    return () => pollRef.current?.stop()
  }, [load])

  const generate = React.useCallback(async () => {
    setState("generating")
    setError(null)
    try {
      const accepted = await createComparison(projectId)
      pollRef.current = pollOperation(accepted.operation_id, {
        onTerminal: async (op) => {
          if (op.status !== "succeeded") {
            setState("error")
            setError("Der Vergleich konnte nicht erstellt werden.")
            return
          }
          await load()
        },
      })
    } catch (err) {
      setState("error")
      setError(
        err instanceof MarketComparisonError
          ? err.message
          : "Es ist ein Fehler aufgetreten."
      )
    }
  }, [projectId, load])

  const setItemStatus = React.useCallback(
    async (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => {
      try {
        await updateItemStatus(itemId, status, supportStatus)
        await load()
      } catch {
        // keep the current view on transient errors
      }
    },
    [load]
  )

  return (
    <section
      data-testid="market-comparison-section"
      className="rounded-lg border border-border bg-card p-5"
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <BarChart3 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">
            Markt- und Konkurrenzvergleich
          </h3>
          {/* RUN 4A: ehrlicher Gesamtstatus des Vergleichs im Sektionskopf. */}
          {comparison && (
            <Badge variant="outline" data-testid="market-comparison-status">
              {COMPARISON_STATUS_LABELS[comparison.status]}
            </Badge>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={state === "generating" || Boolean(disabledReason)}
          onClick={generate}
        >
          {state === "generating" ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Wird erstellt …
            </>
          ) : comparison ? (
            "Neu erstellen"
          ) : (
            "Vergleich erstellen"
          )}
        </Button>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Nur aus live abgerufenen, vollständig importierten und inhaltlich positiv
        geprüften öffentlichen Quellen — kein automatischer Eintrag in den Antrag.
      </p>
      {disabledReason && (
        <p
          className="mb-3 text-xs text-muted-foreground"
          data-testid="market-comparison-disabled-reason"
        >
          {disabledReason}
        </p>
      )}

      {error && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {state === "idle" && !comparison && (
        <p className="text-sm text-muted-foreground">
          Noch kein Vergleich. Rufen Sie öffentliche Quellen live ab, importieren
          und prüfen Sie deren Inhalt positiv und erstellen Sie danach den Vergleich.
        </p>
      )}

      {/* RUN 4A: Limitationshinweise VOR der Tabelle — eine schmale Datenlage
          darf nie wie ein vollständiger Vergleich wirken. */}
      {comparison?.status === "insufficient_external_evidence" && (
        <p className="mb-3 text-sm text-status-partial" role="status">
          Für einen belastbaren Marktvergleich fehlen geeignete geprüfte
          Quellen.
        </p>
      )}

      {comparison?.status === "limited" && (
        <p className="mb-3 text-xs text-status-partial" role="status">
          Begrenzte externe Evidenz: Es liegen geprüfte Marktquellen vor, aber
          der Konkurrenzvergleich ist noch nicht vollständig.
        </p>
      )}

      {comparison && comparison.items.length > 0 && (
        <div className="overflow-x-auto" data-testid="market-comparison-table">
          {SUMMARY_SECTIONS.map((section) => {
            const items = comparison.items.filter((i) =>
              section.categories.includes(i.category)
            )
            if (items.length === 0) return null
            return (
              <div key={section.title} className="mb-4 last:mb-0">
                <p className="mb-1 text-xs font-medium text-foreground">
                  {section.title}
                </p>
                <table className="w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Anbieter/Alternative</th>
                      <th className="py-2 pr-3 font-medium">Zielgruppe</th>
                      <th className="py-2 pr-3 font-medium">Kernnutzen</th>
                      <th className="py-2 pr-3 font-medium">Differenzierung</th>
                      <th className="py-2 pr-3 font-medium">Geschäftsmodell</th>
                      <th className="py-2 pr-3 font-medium">Schweiz-Relevanz</th>
                      <th className="py-2 pr-3 font-medium">Belege</th>
                      <th className="py-2 pr-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <ItemRow
                        key={item.item_id}
                        item={item}
                        onSetStatus={setItemStatus}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )
          })}
        </div>
      )}

      {comparison &&
        comparison.items.length === 0 &&
        state === "ready" &&
        (comparison.status === "limited" ||
        comparison.status === "insufficient_external_evidence" ? (
          // RUN 4A: eine leere Tabelle ist kein Erfolg — konkret benennen,
          // dass belastbare Vergleiche fehlen (Details in den Evidenzlücken).
          <p className="text-sm text-status-partial" role="status">
            Es liegen noch keine belastbaren Anbieter- oder
            Alternativenvergleiche vor. Die offenen Evidenzlücken unten zeigen,
            welche geprüften Quellen fehlen.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Keine Vergleichseinträge aus live abgerufenen und inhaltlich positiv
            geprüften öffentlichen Quellen.
          </p>
        ))}

      {/* RUN 4A: höchstens fünf konkrete Konsequenzen für den Antrag. */}
      {comparison && (comparison.consequences?.length ?? 0) > 0 && (
        <div className="mt-4" data-testid="market-consequences">
          <p className="text-xs font-medium text-foreground">
            Was das für den Antrag bedeutet
          </p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
            {(comparison.consequences ?? []).slice(0, 5).map((entry, i) => (
              <li key={i}>{entry}</li>
            ))}
          </ul>
        </div>
      )}

      {comparison && comparison.research_gaps.length > 0 && (
        <div className="mt-4" data-testid="market-research-gaps">
          <p className="text-xs font-medium text-foreground">Offene Evidenzlücken</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
            {comparison.research_gaps.map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      {comparison && comparison.items.some((i) => i.source_document_ids.length > 0) && (
        <div className="mt-4" data-testid="market-used-sources">
          <p className="text-xs font-medium text-foreground">Verwendete Quellen</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
            {usedSourceNames(comparison, sourceNames).map((name, i) => (
              <li key={i}>{name}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function usedSourceNames(
  comparison: MarketComparisonDto,
  sourceNames?: Record<string, string>
): string[] {
  const ids = new Set<string>()
  for (const item of comparison.items) {
    for (const id of item.source_document_ids) ids.add(id)
  }
  // Nie rohe IDs anzeigen: unbekannte Quellen erscheinen als generischer Eintrag.
  const names = new Set<string>()
  for (const id of ids) {
    names.add(sourceNames?.[id] ?? "Importierte öffentliche Quelle")
  }
  return [...names].sort((a, b) => a.localeCompare(b, "de"))
}

function ItemRow({
  item,
  onSetStatus,
}: {
  item: MarketComparisonItemDto
  onSetStatus: (itemId: string, status: ItemStatus, supportStatus?: SupportStatus) => void
}) {
  return (
    <tr className="border-b border-border/60 align-top">
      <td className="py-2 pr-3 font-medium text-foreground">
        {item.name}
        <span className="block text-[11px] font-normal text-muted-foreground">
          {ITEM_CATEGORY_LABELS[item.category]} ·{" "}
          {ITEM_RELATION_LABELS[item.relation_to_project]}
        </span>
        {/* RUN 4A: sekundäre Vergleichsdimensionen progressiv statt als
            eigene, immer sichtbare Spalte. */}
        <details className="mt-1 text-[11px] font-normal text-muted-foreground">
          <summary className="cursor-pointer">Weitere Details</summary>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2">
            <dt>Kurzbeschreibung</dt><dd>{item.description ?? "—"}</dd>
            <dt>Lösungstyp</dt><dd>{item.solution_type ?? "—"}</dd>
            <dt>Zentralität</dt><dd>{CENTRALIZATION_LABELS[item.centralization ?? "unclear"]}</dd>
            <dt>Daten/Zugriff</dt><dd>{item.data_access_model ?? "—"}</dd>
            <dt>Funktionen</dt><dd>{item.relevant_functions?.join(", ") || "nicht öffentlich belegt"}</dd>
          </dl>
        </details>
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.target_customer_segment ?? "nicht öffentlich belegt"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.core_problem_or_benefit ?? item.description ?? "—"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.differentiation_relevance ?? "—"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.price_business_model ?? "nicht öffentlich belegt"}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.swiss_relevance ?? "unbestätigt"}
      </td>
      <td className="py-2 pr-3">
        {item.evidence_quotes.length > 0 ? (
          <blockquote className="border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
            „{item.evidence_quotes[0].quote}“
          </blockquote>
        ) : (
          <span className="text-[11px] text-muted-foreground">Kein belegtes Zitat</span>
        )}
        {item.evidence_quotes[0]?.source_url && (
          <a href={item.evidence_quotes[0].source_url} target="_blank" rel="noreferrer" className="mt-1 block break-all text-[11px] text-primary hover:underline">
            Quelle öffnen
          </a>
        )}
      </td>
      <td className="py-2 pr-3">
        <Badge variant="secondary" className={CONFIDENCE_STYLE[item.confidence_label]}>
          {item.status === "accepted"
            ? ITEM_STATUS_LABELS.accepted
            : CONFIDENCE_LABELS[item.confidence_label]}
        </Badge>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Fundstelle: {item.coverage_status === "exact_quote_verified" ? "exakt gefunden" : "ungeprüft"}
          {" · "}Inhalt: {SUPPORT_STATUS_LABELS[item.support_status ?? "unreviewed"]}
        </p>
        {/* RUN 4A A11y: Aktionen pro Eintrag eindeutig benennen (Screenreader
            hören sonst nur mehrfach «Übernehmen»/«Prüfen»). */}
        <div className="mt-1 flex gap-1">
          <button
            type="button"
            aria-label={`${item.name}: Übernehmen`}
            className="rounded text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => onSetStatus(item.item_id, "accepted")}
          >
            Übernehmen
          </button>
          <span aria-hidden className="text-[11px] text-muted-foreground">·</span>
          <button
            type="button"
            aria-label={`${item.name}: Prüfen`}
            className="rounded text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => onSetStatus(item.item_id, "needs_human_review")}
          >
            Prüfen
          </button>
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          <button type="button" aria-label={`${item.name}: Stützt`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "supports")}>Stützt</button>
          <button type="button" aria-label={`${item.name}: Stützt teilweise`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "partial")}>Teilweise</button>
          <button type="button" aria-label={`${item.name}: Stützt nicht`} className="rounded text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => onSetStatus(item.item_id, item.status, "does_not_support")}>Stützt nicht</button>
        </div>
      </td>
    </tr>
  )
}
