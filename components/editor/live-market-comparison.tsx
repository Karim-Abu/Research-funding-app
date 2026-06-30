"use client"

// Compact, read-only market-comparison context for the Value Creation editor (M9I-B).
// Shows source-backed items + open questions from the latest comparison. No actions, no
// draft mutation, no provider/model/confidence — the full table lives in Quellen.

import * as React from "react"
import { Info } from "lucide-react"

import {
  getLatestComparison,
  type MarketComparisonDto,
} from "@/lib/market-comparison"

export function LiveMarketComparison({ projectId }: { projectId: string }) {
  const [comparison, setComparison] = React.useState<MarketComparisonDto | null>(null)
  const [loaded, setLoaded] = React.useState(false)

  React.useEffect(() => {
    let active = true
    void getLatestComparison(projectId)
      .then((c) => {
        if (active) setComparison(c)
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setLoaded(true)
      })
    return () => {
      active = false
    }
  }, [projectId])

  if (!loaded) return null

  const sourceBacked =
    comparison?.items.filter((i) => i.confidence_label === "source_backed") ?? []

  return (
    <div className="flex flex-col gap-3" data-testid="live-market-comparison">
      <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        Hinweise aus öffentlichen Quellen — fachlich zu prüfen. Kein automatischer
        Eintrag in den Antrag.
      </p>

      {!comparison || sourceBacked.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Noch kein belegter Markt- und Konkurrenzvergleich. Erstellen Sie ihn unter{" "}
          <a href="/quellen" className="font-medium text-primary hover:underline">
            Quellen
          </a>
          .
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {sourceBacked.slice(0, 4).map((item) => (
            <li
              key={item.item_id}
              className="rounded-md border border-border px-3 py-2"
            >
              <p className="text-xs font-medium text-foreground">{item.name}</p>
              {item.differentiation_relevance && (
                <p className="text-[11px] text-muted-foreground">
                  {item.differentiation_relevance}
                </p>
              )}
              {item.evidence_quotes.length > 0 && (
                <blockquote className="mt-1 border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
                  „{item.evidence_quotes[0].quote}“
                </blockquote>
              )}
              <span className="mt-1 inline-block text-[11px] text-muted-foreground">
                Quelle erwähnt
              </span>
            </li>
          ))}
        </ul>
      )}

      {comparison && comparison.research_gaps.length > 0 && (
        <div>
          <p className="text-[11px] font-medium text-foreground">Offene Marktfragen</p>
          <ul className="mt-1 list-disc pl-5 text-[11px] text-muted-foreground">
            {comparison.research_gaps.slice(0, 3).map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
