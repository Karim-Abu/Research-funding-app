"use client"

// Wide, read-only market-comparison table for the Entwurf screen (M10.3).
// A competitor comparison needs horizontal space — the compact Markt tab links
// here. "Als Argument übernehmen" inserts a German sentence into the LOCAL
// editor buffer only (HITL: the user reviews and saves; nothing is auto-saved).
// Status changes (accept/reject) stay on the Quellen screen.

import * as React from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MARKET_HYPOTHESIS_NOTE } from "@/lib/market-view"
import {
  ITEM_CATEGORY_LABELS,
  CONFIDENCE_LABELS,
  CONFIDENCE_STYLE,
  ITEM_STATUS_LABELS,
  type MarketComparisonDto,
  type MarketComparisonItemDto,
} from "@/lib/market-comparison"

const INSERT_BLOCKED_HINT =
  "Nur belegte, nicht abgelehnte Einträge mit Differenzierungshinweis können übernommen werden."

interface MarketComparisonSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  comparison: MarketComparisonDto | null
  /** Inserts the argument sentence into the local draft buffer (unsaved). */
  onInsertArgument: (item: MarketComparisonItemDto) => void
}

export function MarketComparisonSheet({
  open,
  onOpenChange,
  comparison,
  onInsertArgument,
}: MarketComparisonSheetProps) {
  const [inserted, setInserted] = React.useState(false)

  React.useEffect(() => {
    if (!open) setInserted(false)
  }, [open])

  const items = comparison?.items ?? []
  const insertableOf = (item: MarketComparisonItemDto) =>
    item.confidence_label === "source_backed" &&
    item.status !== "rejected" &&
    Boolean(item.differentiation_relevance?.trim())
  const hasBlockedRows = items.some((item) => !insertableOf(item))

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-[760px] gap-0 overflow-y-auto sm:max-w-[760px]"
        data-testid="market-comparison-sheet"
      >
        <SheetHeader>
          <SheetTitle>Markt- und Konkurrenzvergleich</SheetTitle>
          <SheetDescription>{MARKET_HYPOTHESIS_NOTE}</SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-3 px-4 pb-4">
          {inserted && (
            <p
              role="status"
              className="rounded-md border border-status-fulfilled/30 bg-status-fulfilled/8 px-3 py-2 text-xs text-foreground"
            >
              Argument eingefügt — noch nicht gespeichert. Prüfen und speichern
              Sie den Text im Editor.
            </p>
          )}

          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Noch keine Vergleichseinträge. Erstellen Sie den Vergleich unter
              Quellen aus importierten öffentlichen Quellen.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">Wettbewerber / Lösung</th>
                    <th className="py-2 pr-3 font-medium">Zielgruppe</th>
                    <th className="py-2 pr-3 font-medium">Stärke</th>
                    <th className="py-2 pr-3 font-medium">Schwäche / Lücke</th>
                    <th className="py-2 pr-3 font-medium">Differenzierung</th>
                    <th className="py-2 pr-3 font-medium">Quelle</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 font-medium">
                      <span className="sr-only">Aktion</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const insertable = insertableOf(item)
                    return (
                      <tr key={item.item_id} className="border-b border-border/60 align-top">
                        <td className="py-2 pr-3">
                          <p className="font-medium text-foreground">{item.name}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {ITEM_CATEGORY_LABELS[item.category]}
                          </p>
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {item.target_customer_segment?.trim() || "—"}
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {item.strengths?.trim() || "—"}
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {item.weaknesses?.trim() || "—"}
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">
                          {item.differentiation_relevance?.trim() || "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {item.evidence_quotes.length > 0 ? (
                            <blockquote className="border-l-2 border-border pl-2 text-[11px] italic text-muted-foreground">
                              „{item.evidence_quotes[0].quote}“
                            </blockquote>
                          ) : (
                            <span className="text-[11px] text-muted-foreground">
                              Kein belegtes Zitat
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          <div className="flex flex-col items-start gap-1">
                            <Badge
                              variant="secondary"
                              className={CONFIDENCE_STYLE[item.confidence_label]}
                            >
                              {CONFIDENCE_LABELS[item.confidence_label]}
                            </Badge>
                            {item.status !== "proposed" && (
                              <span className="text-[11px] text-muted-foreground">
                                {ITEM_STATUS_LABELS[item.status]}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2">
                          <Button
                            size="xs"
                            variant="outline"
                            disabled={!insertable}
                            title={insertable ? undefined : INSERT_BLOCKED_HINT}
                            onClick={() => {
                              onInsertArgument(item)
                              setInserted(true)
                            }}
                          >
                            Als Argument übernehmen
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {/* Visible reason — disabled buttons swallow their title tooltip
                  (pointer-events-none), so the rule is stated once below. */}
              {hasBlockedRows && (
                <p className="mt-2 text-[11px] text-muted-foreground">
                  {INSERT_BLOCKED_HINT}
                </p>
              )}
            </div>
          )}

          {comparison && comparison.research_gaps.length > 0 && (
            <div>
              <p className="text-xs font-medium text-foreground">Offene Evidenzlücken</p>
              <ul className="mt-1 list-disc pl-5 text-xs text-muted-foreground">
                {comparison.research_gaps.map((gap, i) => (
                  <li key={i}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center gap-2 border-t border-border pt-3">
            <Button
              size="sm"
              variant="ghost"
              render={<a href="/quellen" />}
              nativeButton={false}
            >
              Quellen öffnen
            </Button>
            <span className="text-[11px] text-muted-foreground">
              Einträge übernehmen/ablehnen erfolgt unter Quellen.
            </span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
