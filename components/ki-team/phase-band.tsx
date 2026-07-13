"use client"

import { cn } from "@/lib/utils"
import type { KiTeamPhase, KiTeamRole, RoleMode } from "@/lib/ki-team-data"
import { RoleCard } from "./role-card"

interface PhaseBandProps {
  phases: KiTeamPhase[]
  detailMode: boolean
  highlight: RoleMode | null
  openInstanceId: string | null
  onOpenRole: (role: KiTeamRole, instanceId: string, element: HTMLButtonElement) => void
}

function instanceId(phase: KiTeamPhase, role: KiTeamRole): string {
  return `phase-${phase.step.step}-${role.id}`
}

/** Marker, wo Nutzer:innen prüfen — Symbol + Text, nie Farbe allein. */
function HumanMarker() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-status-partial/30 bg-status-partial/10 px-2.5 py-1 text-xs font-medium text-status-partial">
      <span aria-hidden="true">●</span> Sie prüfen
    </span>
  )
}

/** Nummerierter Timeline-Knoten je Phase. */
function PhaseNode({ step }: Readonly<{ step: number }>) {
  return (
    <span className="relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-card text-sm font-semibold text-foreground/80 shadow-sm">
      {step}
    </span>
  )
}

/**
 * Der Ablauf als vertikale Timeline: nummerierte Knoten mit durchgehender
 * Verbindungslinie, je Phase eine Karte mit Rollen als volle Zeilen (kein
 * Abschneiden). Von Natur aus responsiv — eine Spalte auf jeder Breite.
 */
export function PhaseBand({
  phases,
  detailMode,
  highlight,
  openInstanceId,
  onOpenRole,
}: Readonly<PhaseBandProps>) {
  return (
    <section aria-label="Der Ablauf">
      <h2 className="font-heading text-base font-medium text-foreground">
        Der Ablauf
      </h2>

      <ol className="mt-4 flex flex-col">
        {phases.map((phase, index) => {
          const isLast = index === phases.length - 1
          return (
            <li key={phase.step.step} className="relative flex gap-4 pb-4 last:pb-0">
              {/* Durchgehende Verbindungslinie, zentriert unter dem Knoten. */}
              {!isLast && (
                <span
                  aria-hidden="true"
                  className="absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 bg-border"
                />
              )}

              {/* Nummerierter Timeline-Knoten. */}
              <PhaseNode step={phase.step.step} />

              {/* Phasenkarte. */}
              <div className="flex-1 rounded-xl border border-border/80 bg-card/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-heading text-sm font-medium leading-tight text-foreground">
                      {phase.step.label}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {phase.step.subLabel}
                    </p>
                  </div>
                  {phase.hatMenschlichePruefung && <HumanMarker />}
                </div>

                <div className={cn("mt-3 flex flex-col gap-2")}>
                  {phase.roles.map((role) => {
                    const id = instanceId(phase, role)
                    return (
                      <RoleCard
                        key={id}
                        role={role}
                        instanceId={id}
                        detailMode={detailMode}
                        highlight={highlight}
                        expanded={openInstanceId === id}
                        onOpen={onOpenRole}
                      />
                    )
                  })}
                </div>
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
