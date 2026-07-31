"use client"

import { ArrowRight, UserRoundCheck } from "lucide-react"
import type { KiTeamPhase, KiTeamRole } from "@/lib/ki-team-data"
import { RoleCard } from "./role-card"

const SECTION_LABEL =
  "flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase"

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
          Beteiligte Funktionen, Ergebnis und Ihr Kontrollpunkt auf einen Blick.
        </p>
      </div>

      <ol className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
        {phases.map((phase) => (
          <li key={phase.step.step}>
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 bg-muted/30 px-4 py-3 sm:px-5">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-background text-xs font-semibold text-foreground">
                {phase.step.step}
              </span>
              <h3 className="font-heading text-base font-semibold text-foreground">
                {phase.step.label}
              </h3>
              <p className="text-sm text-muted-foreground">
                {phase.step.subLabel}
              </p>
            </div>

            <div className="grid items-start gap-5 border-t border-border p-4 sm:p-5 lg:grid-cols-2 lg:gap-8">
              <div className="min-w-0">
                <h4 className={SECTION_LABEL}>Beteiligte Rollen</h4>
                <ul className="mt-2.5 flex flex-col gap-2">
                  {phase.roles.map((role) => {
                    const id = instanceId(phase, role)
                    return (
                      <li key={id}>
                        <RoleCard
                          role={role}
                          instanceId={id}
                          expanded={openInstanceId === id}
                          onOpen={onOpenRole}
                        />
                      </li>
                    )
                  })}
                </ul>
              </div>

              <dl className="grid min-w-0 gap-3">
                <div className="rounded-lg border border-border bg-background p-3.5">
                  <dt className={SECTION_LABEL}>
                    <ArrowRight aria-hidden="true" className="size-3.5" />
                    Ergebnis
                  </dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-foreground">
                    {phase.result}
                  </dd>
                </div>
                <div className="rounded-lg border border-status-partial/35 bg-status-partial/5 p-3.5">
                  <dt className={SECTION_LABEL}>
                    <UserRoundCheck
                      aria-hidden="true"
                      className="size-3.5 text-status-partial"
                    />
                    Ihre Freigabe
                  </dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-foreground">
                    {phase.humanAction}
                  </dd>
                </div>
              </dl>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
