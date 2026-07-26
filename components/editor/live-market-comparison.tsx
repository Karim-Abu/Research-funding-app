"use client"

// Compact, read-only market-comparison context for the Value Creation editor (M9I-B).
// Ergebnis zuerst: nur Status + drei Kennzahlen + ein Link zur Detailansicht
// (Sheet). Marktbild, Gesamturteil-Begründung und Einzelfunde liegen dort,
// einen Klick entfernt — die Rail selbst ist real nur ~220–300px breit.
// No draft mutation here, no provider/model/confidence.

import * as React from "react"
import { Info } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { MarketComparisonDto } from "@/lib/market-comparison"
import {
  MARKET_TONE_STYLE,
  candidateTypeOf,
  marketSummaryCounts,
  marketUiState,
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

  const ui = marketUiState(comparison)
  // Nur Lösungskandidaten zählen als Funde — Marktstatistiken sind keine
  // Wettbewerbs-Findings.
  const sourceBacked =
    comparison?.items.filter(
      (i) => i.confidence_label === "source_backed" && candidateTypeOf(i) !== null
    ) ?? []
  const onlyMarketClaims =
    sourceBacked.length === 0 &&
    (comparison?.items.some((i) => candidateTypeOf(i) === null) ?? false)
  const hasItems = (comparison?.items.length ?? 0) > 0
  // Sichtbarer Grund, warum „Details öffnen" ggf. deaktiviert ist
  // (Tooltip allein reicht nicht — CLAUDEX §5).
  const openDisabledReason = !onOpenComparison
    ? null
    : comparison?.status === "failed"
      ? "Letzter Versuch fehlgeschlagen — unter Quellen erneut erstellen."
      : !hasItems
        ? "Noch kein Vergleich mit Einträgen — unter Quellen erstellen."
        : null
  const limitedWithoutItems = comparison?.status === "limited" && !hasItems
  const summary = marketSummaryCounts(comparison)

  return (
    <div className="flex flex-col gap-3" data-testid="live-market-comparison">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Markt &amp; Wettbewerb
        </h4>
        <span
          data-testid="market-editor-status"
          className={cn(
            "inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
            MARKET_TONE_STYLE[ui.tone]
          )}
        >
          {ui.label}
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
            : onlyMarketClaims
              ? "Bisher nur Marktinformationen gefunden, noch keine vergleichbaren Lösungen. Details unter "
              : "Noch kein belegter Markt- und Konkurrenzvergleich. Erstellen Sie ihn unter "}
          <a href="/quellen" className="font-medium text-primary hover:underline">
            Quellen
          </a>
          .
        </p>
      ) : (
        <div
          data-testid="market-editor-summary"
          className="flex flex-col gap-0.5 rounded-md border border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground"
        >
          <p>
            {summary.sourceCount === 1 ? "1 geprüfte Quelle" : `${summary.sourceCount} geprüfte Quellen`}
          </p>
          <p>
            {summary.solutionCount === 1 ? "1 Lösung gefunden" : `${summary.solutionCount} Lösungen gefunden`}
          </p>
          {summary.gapCount > 0 && (
            <p>
              {summary.gapCount === 1 ? "1 zentrale Lücke" : `${summary.gapCount} zentrale Lücken`}
            </p>
          )}
        </div>
      )}

      <div className="flex flex-col gap-1.5 border-t border-border pt-2">
        <div className="flex flex-wrap gap-2">
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
            Details öffnen
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
        {openDisabledReason && (
          <p className="text-[11px] text-muted-foreground" data-testid="market-editor-open-disabled-reason">
            {openDisabledReason}
          </p>
        )}
      </div>
    </div>
  )
}
