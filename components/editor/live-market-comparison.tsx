"use client"

// Compact, read-only market-comparison context for the Value Creation editor (M9I-B).
// Shows a derived status, source-backed items + open questions from the latest
// comparison, and offers the wide comparison sheet as the working surface.
// No draft mutation here, no provider/model/confidence.

import { Info } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { MarketComparisonDto } from "@/lib/market-comparison"
import {
  comparisonToMarketStatus,
  MARKET_STATUS_LABELS,
  MARKET_STATUS_STYLE,
} from "@/lib/market-view"

interface LiveMarketComparisonProps {
  comparison: MarketComparisonDto | null
  /** True once the latest-comparison request has settled (data or none). */
  loaded: boolean
  /** Opens the wide comparison sheet (table + "Als Argument übernehmen"). */
  onOpenComparison?: () => void
}

export function LiveMarketComparison({
  comparison,
  loaded,
  onOpenComparison,
}: LiveMarketComparisonProps) {
  if (!loaded) return null

  const status = comparisonToMarketStatus(comparison)
  const sourceBacked =
    comparison?.items.filter((i) => i.confidence_label === "source_backed") ?? []
  const hasItems = (comparison?.items.length ?? 0) > 0
  // RUN 4B §8 — Anzahl geprüfter Quellen (dedupliziert über die Einträge).
  const sourceCount = new Set(
    (comparison?.items ?? []).flatMap((item) => item.source_document_ids)
  ).size
  const limitedWithoutItems = comparison?.status === "limited" && !hasItems

  return (
    <div className="flex flex-col gap-3" data-testid="live-market-comparison">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Markt &amp; Wettbewerb
        </h4>
        <span className="flex shrink-0 items-center gap-1.5">
          {comparison && (
            <span className="text-[11px] text-muted-foreground">
              {sourceCount === 1
                ? "1 geprüfte Quelle"
                : `${sourceCount} geprüfte Quellen`}
            </span>
          )}
          <span
            className={cn(
              "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
              MARKET_STATUS_STYLE[status]
            )}
          >
            {MARKET_STATUS_LABELS[status]}
          </span>
        </span>
      </div>

      <p className="flex items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        Hinweise aus öffentlichen Quellen — fachlich zu prüfen. Kein automatischer
        Eintrag in den Antrag.
      </p>

      {!comparison || sourceBacked.length === 0 ? (
        <p className="text-xs text-muted-foreground" data-testid="market-editor-empty">
          {/* RUN 4B §8 — limited ohne Einträge ist KEIN leerer Erfolg. */}
          {limitedWithoutItems
            ? "Marktinformationen vorhanden, aber noch kein belastbarer Anbieter-/Alternativenvergleich. Details unter "
            : "Noch kein belegter Markt- und Konkurrenzvergleich. Erstellen Sie ihn unter "}
          <a href="/quellen" className="font-medium text-primary hover:underline">
            Quellen
          </a>
          .
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {/* RUN 4B §8 — höchstens drei relevante Findings. */}
          {sourceBacked.slice(0, 3).map((item) => (
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
                Textstelle gefunden
              </span>
            </li>
          ))}
        </ul>
      )}

      {comparison && comparison.research_gaps.length > 0 && (
        <div>
          <p className="text-[11px] font-medium text-foreground">Offene Evidenzlücken</p>
          <ul className="mt-1 list-disc pl-5 text-[11px] text-muted-foreground">
            {comparison.research_gaps.slice(0, 3).map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t border-border pt-2">
        <Button
          size="xs"
          variant="outline"
          onClick={onOpenComparison}
          disabled={!hasItems || !onOpenComparison}
          title={
            hasItems
              ? "Vollständige Vergleichstabelle mit Übernahme-Aktionen"
              : "Noch kein Marktvergleich mit Einträgen vorhanden — erstellen Sie ihn unter Quellen."
          }
        >
          Marktvergleich öffnen
        </Button>
        <Button
          size="xs"
          variant="ghost"
          render={<a href="/quellen" />}
          nativeButton={false}
        >
          Quellen öffnen
        </Button>
      </div>
    </div>
  )
}
