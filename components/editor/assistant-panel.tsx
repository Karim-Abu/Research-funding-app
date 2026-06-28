"use client"

import * as React from "react"
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import { ReqBucketBadge } from "@/components/anforderungen/requirements-controls"
import { MarketCompetitionPanel } from "@/components/editor/market-competition-panel"
import { DRAFT_EVIDENCE_LABELS, DRAFT_EVIDENCE_STYLE } from "@/lib/draft-view"
import type { MarketDataset } from "@/lib/market-view"
import type { AssistantTab, DraftFieldViewModel } from "@/lib/draft-viewmodel"

const TABS: [AssistantTab, string][] = [
  ["markt", "Markt"],
  ["belege", "Belege"],
  ["anforderungen", "Anforderungen"],
  ["kommentare", "Kommentare"],
  ["versionen", "Versionen"],
]

interface AssistantPanelProps {
  vm: DraftFieldViewModel
  defaultTab: AssistantTab
  market: {
    data: MarketDataset | null
    relevant: boolean
    live: boolean
    onApply?: (improvement: string, text: string) => void
  }
  suggestionExists: boolean
  /** Live supplies its evidence + linking UI; mock falls back to the VM list. */
  belegeContent?: React.ReactNode
  /** Both modes supply the comment-tab body (mock: thread; live: findings + box + approve). */
  kommentareContent: React.ReactNode
}

export function AssistantPanel({
  vm,
  defaultTab,
  market,
  suggestionExists,
  belegeContent,
  kommentareContent,
}: AssistantPanelProps) {
  const [tab, setTab] = React.useState<AssistantTab>(defaultTab)
  const [techOpen, setTechOpen] = React.useState(false)

  return (
    <div className="flex gap-3">
      <div className="flex w-[132px] shrink-0 flex-col gap-1" role="tablist" aria-label="Assistent">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
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
          onApply={market.onApply}
        />
      )}

      {tab === "belege" && (
        <Section title="Verknüpfte Belege">
          {belegeContent ?? (
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
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                          DRAFT_EVIDENCE_STYLE[ev.status]
                        )}
                      >
                        {DRAFT_EVIDENCE_LABELS[ev.status]}
                      </span>
                      <a
                        href="/quellen?tab=evidenz"
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

      {tab === "anforderungen" && (
        <Section title="Betroffene Anforderungen">
          {vm.requirementItems.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Noch keine Anforderungen mit diesem Feld verknüpft.
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
        </Section>
      )}

      {tab === "kommentare" && (
        <Section title="Kommentare">
          <PeopleRow responsible={vm.responsible} reviewer={vm.reviewer} />
          {kommentareContent}
        </Section>
      )}

      {tab === "versionen" && (
        <Section title="Versionen">
          {suggestionExists && (
            <div className="flex items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
              <span className="text-xs font-medium text-foreground">KI-Vorschlag (temporär)</span>
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
        </Section>
      )}

      {/* Technical details — collapsed, never in the standard view */}
      {vm.technicalDetails.length > 0 && (
        <div className="border-t border-border pt-2">
          <button
            type="button"
            onClick={() => setTechOpen((v) => !v)}
            aria-expanded={techOpen}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {techOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            Technische Details
          </button>
          {techOpen && (
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {vm.technicalDetails.map((d) => (
                <React.Fragment key={d.label}>
                  <dt>{d.label}</dt>
                  <dd className="font-mono break-all">{d.value}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}
        </div>
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
