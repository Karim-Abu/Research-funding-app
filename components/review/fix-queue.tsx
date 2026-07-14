"use client"

// R2.5 — Fix Queue: «Nächste Aufgaben» (Top-5, priorisiert) und gruppierte
// Findings («4 × …», aufklappbar mit Beispielen). Datenquelle ist die
// R2.4-Gruppierungs-API; diese Komponenten sind reine Anzeige (read-only)
// und erzeugen keine eigene Zähl- oder Gruppierungslogik.

import * as React from "react"
import { ChevronDown, ChevronRight } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ClaimDetailsDrawer } from "@/components/review/claim-details-drawer"
import {
  SEVERITY_CLASS_LABELS,
  groupDisplayTitle,
  type GroupedFindingDto,
} from "@/lib/fix-queue"

function targetHref(group: GroupedFindingDto): string {
  if (group.target_field_id) {
    return `/editor?field=${encodeURIComponent(group.target_field_id)}`
  }
  if (group.severity_class === "eligibility_blocker" || group.severity_class === "budget_blocker") {
    return "/anforderungen"
  }
  if (group.affected_fields.length > 0) {
    return `/editor?field=${encodeURIComponent(group.affected_fields[0])}`
  }
  return "/review"
}

function targetLabel(group: GroupedFindingDto): string {
  if (group.target_field_id || group.affected_fields.length > 0) {
    return "Im Entwurf öffnen"
  }
  if (group.severity_class === "eligibility_blocker" || group.severity_class === "budget_blocker") {
    return "Zu den Anforderungen"
  }
  return "Zur Prüfung"
}

function classBadgeVariant(group: GroupedFindingDto): "destructive" | "secondary" {
  return group.severity === "blocker" ? "destructive" : "secondary"
}

/** «Nächste Aufgaben» — die Top-N-Gruppen in Prioritätsreihenfolge. */
export function NextActionsCard({
  groups,
  limit = 5,
}: {
  groups: GroupedFindingDto[]
  limit?: number
}) {
  const top = groups.slice(0, limit)
  return (
    <section
      data-testid="fix-queue-next"
      className="flex flex-col gap-2 rounded-lg border border-border bg-card px-5 py-4"
    >
      <h2 className="text-sm font-semibold text-foreground">Nächste Aufgaben</h2>
      {top.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Keine offenen Aufgaben — prüfen Sie den Entwurf final.
        </p>
      ) : (
        <ol className="flex flex-col gap-1.5">
          {top.map((group, index) => (
            <li
              key={group.group_key}
              data-testid="fix-queue-next-item"
              className="flex flex-wrap items-center gap-2 text-sm"
            >
              <span className="text-muted-foreground">{index + 1}.</span>
              <Badge variant={classBadgeVariant(group)}>
                {SEVERITY_CLASS_LABELS[group.severity_class]}
              </Badge>
              <span className="min-w-0 flex-1 text-foreground">
                {group.count > 1 ? `${group.count} × ` : ""}
                {groupDisplayTitle(group)}
              </span>
              <Button
                size="xs"
                variant="outline"
                render={<a href={targetHref(group)} />}
                nativeButton={false}
              >
                {targetLabel(group)}
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

/** Gruppierte Findings — aufklappbar, Beispiele zeigen die Einzelmeldungen. */
export function GroupedFindingsSection({
  groups,
  runId,
}: {
  groups: GroupedFindingDto[]
  /** Ermöglicht den Claim-Drawer «Technische Details» (nur mit runId). */
  runId?: string
}) {
  if (groups.length === 0) return null
  return (
    <section className="flex flex-col gap-3" data-testid="grouped-findings">
      <h2 className="text-sm font-semibold text-foreground">
        Offene Punkte (gruppiert)
      </h2>
      <div className="flex flex-col gap-2">
        {groups.map((group) => (
          <GroupRow key={group.group_key} group={group} runId={runId} />
        ))}
      </div>
    </section>
  )
}

/** Eine gruppierte Aufgabe — aufklappbar mit Beispielen. Wird auch von den
 *  Prüfbereichs-Zeilen der Qualitätsprüfung eingebettet. */
export function GroupRow({
  group,
  runId,
}: {
  group: GroupedFindingDto
  runId?: string
}) {
  const [open, setOpen] = React.useState(false)
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  // Claim-Level-Details nur im Drawer «Technische Details» (B4): verfügbar,
  // wenn die Gruppe claimgebundene Findings bündelt und runId bekannt ist.
  const claimDetails =
    Boolean(runId) &&
    group.examples.some((e) => e.target_type === "draft_claim")
  return (
    <section
      className="overflow-hidden rounded-lg border border-border bg-card"
      data-testid="grouped-finding"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        <Badge variant={classBadgeVariant(group)}>
          {SEVERITY_CLASS_LABELS[group.severity_class]}
        </Badge>
        <span className="min-w-0 flex-1 text-sm font-medium text-foreground">
          {group.count > 1 ? `${group.count} × ` : ""}
          {groupDisplayTitle(group)}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-2 border-t border-border bg-muted/20 px-4 py-3">
          {group.recommended_next_action && (
            <p className="text-xs text-muted-foreground">
              Empfehlung: {group.recommended_next_action}
            </p>
          )}
          <ul className="flex flex-col gap-1.5">
            {group.examples.map((example) => (
              <li
                key={example.finding_id}
                className="flex flex-wrap items-center gap-2 text-xs text-foreground"
              >
                <span className="min-w-0 flex-1">{example.description}</span>
                {example.field_id && (
                  <Button
                    size="xs"
                    variant="ghost"
                    render={
                      <a
                        href={`/editor?field=${encodeURIComponent(example.field_id)}`}
                      />
                    }
                    nativeButton={false}
                  >
                    Im Entwurf öffnen
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {group.count > group.examples.length && (
            <p className="text-xs text-muted-foreground">
              … und {group.count - group.examples.length} weitere gleichartige{" "}
              {group.count - group.examples.length === 1
                ? "Meldung"
                : "Meldungen"}
              .
            </p>
          )}
          {claimDetails && runId && (
            <>
              <Button
                size="xs"
                variant="ghost"
                className="self-start"
                onClick={() => setDrawerOpen(true)}
              >
                Alle {group.count} Hinweise anzeigen (Technische Details)
              </Button>
              <ClaimDetailsDrawer
                runId={runId}
                fieldId={group.target_field_id}
                open={drawerOpen}
                onOpenChange={setDrawerOpen}
              />
            </>
          )}
        </div>
      )}
    </section>
  )
}
