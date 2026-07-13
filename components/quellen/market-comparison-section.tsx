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
  ITEM_CATEGORY_LABELS,
  ITEM_RELATION_LABELS,
  ITEM_STATUS_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  SUMMARY_SECTIONS,
  type ItemStatus,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
} from "@/lib/market-comparison"

type State = "loading" | "idle" | "generating" | "ready" | "error"

export function MarketComparisonSection({
  projectId,
  sourceNames,
}: {
  projectId: string
  // Anzeigenamen der Projektquellen (source_id → Name) für den Abschnitt
  // «Verwendete Quellen» — es werden nie rohe IDs angezeigt.
  sourceNames?: Record<string, string>
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
    async (itemId: string, status: ItemStatus) => {
      try {
        await updateItemStatus(itemId, status)
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
        <div className="flex items-center gap-2">
          <BarChart3 className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">
            Markt- und Konkurrenzvergleich
          </h3>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={state === "generating"}
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
        Nur aus importierten öffentlichen Quellen. Webquellen müssen fachlich
        geprüft werden — kein automatischer Eintrag in den Antrag.
      </p>

      {error && (
        <p role="alert" className="mb-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {state === "idle" && !comparison && (
        <p className="text-sm text-muted-foreground">
          Noch kein Vergleich. Importieren Sie öffentliche Quellen und erstellen
          Sie einen Vergleich.
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
                      <th className="py-2 pr-3 font-medium">Eintrag</th>
                      <th className="py-2 pr-3 font-medium">Kategorie</th>
                      <th className="py-2 pr-3 font-medium">Kurzbeschreibung</th>
                      <th className="py-2 pr-3 font-medium">Relevanz</th>
                      <th className="py-2 pr-3 font-medium">Differenzierungshinweis</th>
                      <th className="py-2 pr-3 font-medium">Quelle</th>
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

      {comparison && comparison.items.length === 0 && state === "ready" && (
        <p className="text-sm text-muted-foreground">
          Keine belegten Vergleichseinträge aus den öffentlichen Quellen.
        </p>
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
  onSetStatus: (itemId: string, status: ItemStatus) => void
}) {
  return (
    <tr className="border-b border-border/60 align-top">
      <td className="py-2 pr-3 font-medium text-foreground">{item.name}</td>
      <td className="py-2 pr-3 text-muted-foreground">
        {ITEM_CATEGORY_LABELS[item.category]}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">{item.description ?? "—"}</td>
      <td className="py-2 pr-3 text-muted-foreground">
        {ITEM_RELATION_LABELS[item.relation_to_project]}
      </td>
      <td className="py-2 pr-3 text-muted-foreground">
        {item.differentiation_relevance ?? "—"}
      </td>
      <td className="py-2 pr-3">
        {item.evidence_quotes.length > 0 ? (
          <blockquote className="border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
            „{item.evidence_quotes[0].quote}“
          </blockquote>
        ) : (
          <span className="text-[11px] text-muted-foreground">Kein belegtes Zitat</span>
        )}
      </td>
      <td className="py-2 pr-3">
        <Badge variant="secondary" className={CONFIDENCE_STYLE[item.confidence_label]}>
          {item.status === "accepted"
            ? ITEM_STATUS_LABELS.accepted
            : CONFIDENCE_LABELS[item.confidence_label]}
        </Badge>
        <div className="mt-1 flex gap-1">
          <button
            type="button"
            className="text-[11px] text-muted-foreground hover:text-foreground"
            onClick={() => onSetStatus(item.item_id, "accepted")}
          >
            Übernehmen
          </button>
          <span className="text-[11px] text-muted-foreground">·</span>
          <button
            type="button"
            className="text-[11px] text-muted-foreground hover:text-foreground"
            onClick={() => onSetStatus(item.item_id, "needs_human_review")}
          >
            Prüfen
          </button>
        </div>
      </td>
    </tr>
  )
}
