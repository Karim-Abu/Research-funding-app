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
    // R1: kein eigener Erklärsatz — das Panel darunter führt seinen eigenen Kopf
    // samt Datenschutzregel; ein fünfter Disclaimer über derselben Fläche
    // erhöht nur die Dichte.
    <section data-testid="market-research-panel" className="flex flex-col gap-2">
      <PublicResearchPanel projectId={projectId} onImported={onImported} />
    </section>
  )
}
