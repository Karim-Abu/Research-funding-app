"use client"

import * as React from "react"
import { ExternalLink } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { ReqBucketBadge } from "@/components/anforderungen/requirements-controls"
import { MarketCompetitionPanel } from "@/components/editor/market-competition-panel"
import { SupportStatusBadge } from "@/components/status/support-status-badge"
import type { DraftEvidenceStatus } from "@/lib/draft-view"
import type { SupportStatus } from "@/lib/evidence-ladder"
import type { MarketDataset } from "@/lib/market-view"
import type { MarketComparisonDto } from "@/lib/market-comparison"
import type { AssistantTab, DraftFieldViewModel } from "@/lib/draft-viewmodel"

// R6-Zieltabs zuerst; Kommentare/Versionen bleiben nachgeordnet erhalten.
const TABS: [AssistantTab, string][] = [
  ["quellen", "Quellen"],
  ["fehlende", "Fehlende Angaben"],
  ["schwaechen", "Schwächen"],
  ["markt", "Markt & Wettbewerb"],
  ["kommentare", "Kommentare"],
  ["versionen", "Versionen"],
]

// Mock-Belegstatus → Statusleiter (Coverage ≠ Correctness): "verified" ist
// nur eine gefundene Textstelle, nie grünes "belegt".
const MOCK_EVIDENCE_TO_SUPPORT: Record<DraftEvidenceStatus, SupportStatus> = {
  verified: "location_found",
  review: "human_review_required",
  open: "evidence_missing",
}

interface AssistantPanelProps {
  vm: DraftFieldViewModel
  defaultTab: AssistantTab
  /** Controlled active tab (live uses this for "Belege öffnen" shortcuts). */
  tab?: AssistantTab
  onTabChange?: (tab: AssistantTab) => void
  market: {
    data: MarketDataset | null
    relevant: boolean
    live: boolean
    projectId?: string
    onApply?: (improvement: string, text: string) => void
    /** M10.3: latest live comparison + capability gate + sheet opener. */
    comparison?: MarketComparisonDto | null
    comparisonLoaded?: boolean
    comparisonEnabled?: boolean
    onOpenComparison?: () => void
    /** capabilities.features.web_research — gates the Market Research flow (RESEARCH.1b). */
    marketResearchEnabled?: boolean
    onSourceImported?: () => void
  }
  suggestionExists: boolean
  /** Live supplies its evidence + linking UI; mock falls back to the VM list. */
  quellenContent?: React.ReactNode
  /** "Fehlende Angaben" als konkrete Fragen (live); mock fällt auf die
   * Anforderungsliste des ViewModels zurück. */
  fehlendeContent?: React.ReactNode
  /** Feldbezogene Schwächen/Findings (live); mock zeigt einen Leerzustand. */
  schwaechenContent?: React.ReactNode
  /** Both modes supply the comment-tab body (mock: thread; live: findings + box + approve). */
  kommentareContent: React.ReactNode
  /** RUN 4B: live liefert die echte Versionshistorie mit Wiederherstellen;
   * mock fällt auf die VM-Liste zurück. */
  versionsContent?: React.ReactNode
  /** Rendered under the version list (live: "history not available" note). */
  versionsFootnote?: React.ReactNode
}

export function AssistantPanel({
  vm,
  defaultTab,
  tab: controlledTab,
  onTabChange,
  market,
  suggestionExists,
  quellenContent,
  fehlendeContent,
  schwaechenContent,
  kommentareContent,
  versionsContent,
  versionsFootnote,
}: AssistantPanelProps) {
  const [internalTab, setInternalTab] = React.useState<AssistantTab>(defaultTab)
  const tab = controlledTab ?? internalTab

  function selectTab(next: AssistantTab) {
    setInternalTab(next)
    onTabChange?.(next)
  }

  return (
    <div className="flex gap-3">
      <div className="flex w-[132px] shrink-0 flex-col gap-1" role="tablist" aria-label="Assistent">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => selectTab(key)}
            className={cn(
              "rounded-md px-2.5 py-1.5 text-left text-xs font-medium transition-colors",
              tab === key
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-3">

      {tab === "markt" && (
        <MarketCompetitionPanel
          data={market.data}
          relevant={market.relevant}
          live={market.live}
          projectId={market.projectId}
          onApply={market.onApply}
          comparison={market.comparison ?? null}
          comparisonLoaded={market.comparisonLoaded ?? false}
          comparisonEnabled={market.comparisonEnabled ?? false}
          onOpenComparison={market.onOpenComparison}
          marketResearchEnabled={market.marketResearchEnabled ?? false}
          onSourceImported={market.onSourceImported}
        />
      )}

      {tab === "quellen" && (
        <Section title="Quellen & Belege">
          {quellenContent ?? (
            vm.evidenceItems.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Noch keine Belege mit diesem Feld verknüpft.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {vm.evidenceItems.map((ev) => (
                  <li key={ev.id} className="flex flex-col gap-1 rounded-md border border-border px-3 py-2">
                    <p className="text-xs text-foreground">{ev.claim}</p>
                    <p className="text-[11px] text-muted-foreground">{ev.source} · {ev.fundstelle}</p>
                    <div className="flex items-center justify-between gap-2">
                      <SupportStatusBadge
                        short
                        status={MOCK_EVIDENCE_TO_SUPPORT[ev.status]}
                      />
                      <a
                        href="/anforderungen?tab=evidenz"
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="size-3" />
                        Quelle öffnen
                      </a>
                    </div>
                  </li>
                ))}
              </ul>
            )
          )}
        </Section>
      )}

      {tab === "fehlende" && (
        <Section title="Fehlende Angaben">
          {fehlendeContent ?? (
            <>
              {vm.requirementItems.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Keine offenen Angaben für dieses Feld bekannt.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {vm.requirementItems.map((req) => (
                    <li key={req.id} className="flex items-center justify-between gap-2">
                      <span className="min-w-0 flex-1 truncate text-xs text-foreground">{req.title}</span>
                      <ReqBucketBadge bucket={req.status} />
                    </li>
                  ))}
                </ul>
              )}
              <a href="/anforderungen" className="mt-1 inline-block text-xs font-medium text-primary hover:underline">
                In Anforderungen öffnen
              </a>
            </>
          )}
        </Section>
      )}

      {tab === "schwaechen" && (
        <Section title="Schwächen">
          {schwaechenContent ?? (
            <p className="text-xs text-muted-foreground">
              Für dieses Feld liegen keine Schwächen-Hinweise vor. Die
              Gesamtprüfung finden Sie unter „Prüfung“.
            </p>
          )}
        </Section>
      )}

      {tab === "kommentare" && (
        <Section title="Kommentare">
          <PeopleRow responsible={vm.responsible} reviewer={vm.reviewer} />
          {kommentareContent}
        </Section>
      )}

      {tab === "versionen" && versionsContent && (
        <Section title="Versionen">{versionsContent}</Section>
      )}

      {tab === "versionen" && !versionsContent && (
        <Section title="Versionen">
          {suggestionExists && (
            <div className="flex items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
              <span className="text-xs font-medium text-foreground">Strukturvorlage (temporär)</span>
              <span className="text-[11px] text-primary">nicht übernommen</span>
            </div>
          )}
          {vm.versions.length === 0 ? (
            <p className="text-xs text-muted-foreground">Noch keine Versionshistorie vorhanden.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {vm.versions.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-foreground">{v.label}</p>
                    <p className="text-[11px] text-muted-foreground">{v.author} · {v.timestamp}</p>
                  </div>
                  {v.current && (
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                      Aktuell
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {versionsFootnote}
        </Section>
      )}

      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  )
}

function PeopleRow({
  responsible,
  reviewer,
}: {
  responsible?: { name: string; initials: string }
  reviewer?: { name: string; initials: string }
}) {
  if (!responsible && !reviewer) {
    return <p className="text-xs text-muted-foreground">Keine verantwortliche Person zugewiesen</p>
  }
  return (
    <div className="flex flex-wrap gap-3">
      {responsible && (
        <div className="flex items-center gap-1.5">
          <Avatar size="sm">
            <AvatarFallback>{responsible.initials}</AvatarFallback>
          </Avatar>
          <span className="text-[11px] text-muted-foreground">
            Verantwortlich: <span className="text-foreground">{responsible.name}</span>
          </span>
        </div>
      )}
      {reviewer && (
        <div className="flex items-center gap-1.5">
          <Avatar size="sm">
            <AvatarFallback>{reviewer.initials}</AvatarFallback>
          </Avatar>
          <span className="text-[11px] text-muted-foreground">
            Review: <span className="text-foreground">{reviewer.name}</span>
          </span>
        </div>
      )}
    </div>
  )
}
