"use client"

import { FileCheck2, UserRoundCheck } from "lucide-react"
import type { KiTeamPhase, KiTeamRole } from "@/lib/ki-team-data"
import { RoleCard } from "./role-card"

interface PhaseBandProps {
  phases: KiTeamPhase[]
  openInstanceId: string | null
  onOpenRole: (
    role: KiTeamRole,
    instanceId: string,
    element: HTMLButtonElement
  ) => void
}

function instanceId(phase: KiTeamPhase, role: KiTeamRole): string {
  return `phase-${phase.step.step}-${role.id}`
}

function PhaseNode({ step }: Readonly<{ step: number }>) {
  return (
    <span className="relative z-10 flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-card text-sm font-semibold text-foreground shadow-sm">
      {step}
    </span>
  )
}

export function PhaseBand({
  phases,
  openInstanceId,
  onOpenRole,
}: Readonly<PhaseBandProps>) {
  return (
    <section aria-labelledby="workflow-view-title">
      <div className="mb-5">
        <h2
          id="workflow-view-title"
          className="font-heading text-lg font-semibold text-foreground"
        >
          Verantwortungen entlang des Ablaufs
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Jede Phase zeigt beteiligte Funktionen, ihr Ergebnis und Ihren
          Kontrollpunkt.
        </p>
      </div>

      <ol className="flex flex-col">
        {phases.map((phase, index) => {
          const isLast = index === phases.length - 1
          return (
            <li
              key={phase.step.step}
              className="relative flex gap-3 pb-5 sm:gap-4 last:pb-0"
            >
              {!isLast && (
                <span
                  aria-hidden="true"
                  className="absolute top-9 bottom-0 left-[18px] w-px -translate-x-1/2 bg-border"
                />
              )}

              <PhaseNode step={phase.step.step} />

              <article className="min-w-0 flex-1 rounded-xl border border-border bg-card p-4 sm:p-5">
                <div className="mb-5">
                  <h3 className="font-heading text-base font-semibold text-foreground sm:text-lg">
                    {phase.step.label}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {phase.step.subLabel}
                  </p>
                </div>

                <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(17rem,0.8fr)] lg:items-start">
                  <div className="min-w-0">
                    <h4 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                      Wer arbeitet?
                    </h4>
                    <div className="mt-2 divide-y divide-border/70 rounded-lg bg-muted/35 p-1">
                      {phase.roles.map((role) => {
                        const id = instanceId(phase, role)
                        return (
                          <RoleCard
                            key={id}
                            role={role}
                            instanceId={id}
                            expanded={openInstanceId === id}
                            onOpen={onOpenRole}
                          />
                        )
                      })}
                    </div>
                  </div>

                  <div className="rounded-lg bg-muted/45 p-4">
                    <div>
                      <h4 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                        <FileCheck2
                          aria-hidden="true"
                          className="size-4 text-status-fulfilled"
                        />
                        Was entsteht?
                      </h4>
                      <p className="mt-2 text-sm leading-relaxed font-medium text-foreground">
                        {phase.result}
                      </p>
                    </div>
                    <div className="mt-4 border-t border-border pt-4">
                      <h4 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                        <UserRoundCheck
                          aria-hidden="true"
                          className="size-4 text-status-partial"
                        />
                        Ihre Aufgabe
                      </h4>
                      <p className="mt-2 text-sm leading-relaxed text-foreground">
                        {phase.humanAction}
                      </p>
                    </div>
                  </div>
                </div>
              </article>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
