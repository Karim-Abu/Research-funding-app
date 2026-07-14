"use client"

import { PublicResearchPanel } from "@/components/quellen/public-research-panel"

/**
 * Editor entry point for market research.
 *
 * It deliberately renders the same persistent, brief-bound research workspace as the
 * Sources page.  There is no second topic/query simulation and no client-only result
 * state that could disagree with firewall or approval provenance after a reload.
 */
export function MarketResearchPanel({
  projectId,
  onImported,
}: {
  projectId: string
  onImported?: () => void
}) {
  return (
    <section data-testid="market-research-panel" className="flex flex-col gap-2">
      <p className="text-[11px] text-muted-foreground">
        Marktquellen werden im gemeinsamen Recherchearbeitsbereich geplant, geprüft und
        übernommen. Ein Snippet allein ist kein Beleg.
      </p>
      <PublicResearchPanel projectId={projectId} onImported={onImported} />
    </section>
  )
}
